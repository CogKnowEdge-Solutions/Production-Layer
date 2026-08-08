# CareMatch

Clinical trial patient eligibility screening with explainable, evidence-backed AI
recommendations and human-in-the-loop review. FHIR R4 patient data is evaluated
against trial protocols using a rules engine; every recommendation is traceable
to evidence, and coordinators can override with mandatory reasoning.

Built with FastAPI, SQLAlchemy, and OAuth 2.0-style JWT auth with role-based
access control (RBAC). An optional **AI agent team** (LangChain coordinator +
specialist subagents on OpenRouter) can operate the whole system in plain
language.

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env          # adjust secrets for production
uvicorn app.main:app --reload
```

Docs: http://localhost:8000/docs  ·  Metrics: http://localhost:8000/api/v1/metrics

Four seed users are created on first startup (dev only):

| Username      | Role          | Password                    |
|---------------|---------------|-----------------------------|
| `admin`       | ADMINISTRATOR | `admin-password-change-me`  |
| `coordinator` | COORDINATOR   | `coordinator-password-change-me` |
| `provider`    | PROVIDER      | `provider-password-change-me` |
| `auditor`     | AUDITOR       | `auditor-password-change-me` |

## Docker

```bash
docker compose up --build     # API, agent, UI, Postgres, Redis, Prometheus, Grafana
```

- API: http://localhost:8000
- UI (Streamlit): http://localhost:8501
- Agent: http://localhost:8100 (`POST /agent/chat`)
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin/admin)

## Web UI (Streamlit)

```bash
pip install -r frontend/requirements.txt
streamlit run frontend/app.py        # http://localhost:8501
# API_URL / AGENT_URL env vars override the default localhost endpoints
```

Tabs: **Trials** (create/inspect), **Evaluate** (FHIR → eligibility), **Review**
(approve/override assessments), **Caregivers**, **Audit** (logs + metrics), and
**Agent** (chat with the AI agent team).

## AI agent team

The `agent/` service is a coordinator agent (LangChain) that delegates to six
specialist subagents, each with its own tools that call the CareMatch API:
`auth`, `trials`, `eligibility`, `assessments`, `caregivers`, and `audit`.
Models come from OpenRouter (free tier by default).

```bash
pip install -r agent/requirements.txt
uvicorn agent.main:app --port 8100
# OPENROUTER_API_KEY + OPENROUTER_MODEL set in .env (see .env.example)
```

Try it:

```bash
curl -X POST http://localhost:8100/agent/chat -H 'Content-Type: application/json' \
  -d '{"message": "Log in as admin / admin-password-change-me, then create a diabetes trial and evaluate a 45-year-old patient against it.", "username": "admin", "password": "admin-password-change-me"}'
```

Design notes:

- The coordinator never calls the API directly — it delegates to subagents and
  synthesizes their reports.
- Each subagent shares one `AgentSession` so a token obtained by `auth` is
  available to every other tool.
- Rules created from free-text protocols require **bullet-point** lines (the
  parser skips prose paragraphs) — the trials subagent is prompted to format
  them accordingly.
- Overrides always require reasoning; the API enforces it server-side.
- Free OpenRouter models are rate-limited and occasionally flaky; retries are
  enabled in `agent/model.py`.

## Kubernetes

`kubectl apply -f kubernetes/manifests.yaml` deploys the API (2 replicas with
readiness/liveness probes), a Redis service, and the Postgres secret. Set the
`carematch-secrets` values for production.

## Testing & quality

```bash
pip install -r requirements-dev.txt
pytest                       # test suite
pytest --cov=app --cov-fail-under=80
ruff check app tests         # lint
ruff format --check app tests
mypy app                     # type check
```

## Architecture

```
app/                    # API service (FastAPI)
  api/v1/          HTTP routers (auth, patients, trials, caregivers, assessments, audit, metrics)
  db/              SQLAlchemy models and repositories
  middleware/      RBAC auth, audit, metrics, rate limiting, error handlers
  services/        FHIR processing, rules engine, protocol parser, eligibility, OAuth, security
  schemas/         Pydantic request/response models
agent/                  # AI agent team (LangChain + OpenRouter)
  main.py          FastAPI app: POST /agent/chat
  coordinator.py   coordinator agent that delegates to 6 subagents
  subagents.py     auth, trials, eligibility, assessments, caregivers, audit specialists
  tools.py         LangChain tools wrapping the CareMatch REST API
  smoke_test.py    live end-to-end agent check (run manually)
frontend/               # Web UI (Streamlit)
  app.py           login + trials/evaluate/review/caregivers/audit/agent tabs
```

Key flows:

- **Eligibility** — POST a FHIR bundle → `fhir_processor` normalizes it →
  `rules_engine` evaluates each rule → `eligibility` aggregates an overall
  status with per-rule evidence and confidence.
- **Trial protocols** — providers submit free-text protocols that are parsed
  into structured rules, or structured rules directly.
- **Human-in-the-loop** — coordinators override individual rule results with
  mandatory reasoning; impact on overall eligibility is tracked and audited.
- **Audit** — every data access, override, and auth event is logged with PII
  redacted for HIPAA compliance; AUDITOR/ADMIN can read the trail at
  `/api/v1/audit/logs`.

## API surface

All routes are prefixed `/api/v1`.

| Method | Path                              | Roles                         |
|--------|-----------------------------------|-------------------------------|
| GET    | `/health`, `/ready`               | public                        |
| POST   | `/auth/token`                     | public                        |
| POST   | `/auth/refresh`                   | public                        |
| GET    | `/auth/me`                        | authenticated                 |
| POST   | `/evaluate-eligibility`           | PROVIDER, COORDINATOR         |
| GET    | `/patients/{id}`                  | PROVIDER, COORDINATOR         |
| POST   | `/trials/create`                  | PROVIDER, COORDINATOR         |
| GET    | `/trials`, `/trials/{id}`         | all roles                     |
| PUT    | `/trials/{id}`                    | PROVIDER, ADMINISTRATOR (bumps protocol version) |
| POST   | `/caregivers`                     | PROVIDER, COORDINATOR         |
| GET    | `/patients/{id}/caregivers`       | all roles                     |
| GET    | `/assessments`, `/assessments/{id}` | COORDINATOR, PROVIDER       |
| PUT    | `/assessments/{id}/override`      | COORDINATOR, ADMINISTRATOR    |
| PUT    | `/assessments/{id}/approve`       | COORDINATOR, ADMINISTRATOR    |
| GET    | `/assessments/{id}/overrides`     | COORDINATOR, ADMINISTRATOR    |
| GET    | `/audit/logs`                     | AUDITOR, ADMINISTRATOR        |
| GET    | `/metrics`                        | public (Prometheus)           |
