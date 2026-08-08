# CareMatch

Clinical trial patient eligibility screening with explainable, evidence-backed AI
recommendations and human-in-the-loop review. FHIR R4 patient data is evaluated
against trial protocols using a rules engine; every recommendation is traceable
to evidence, and coordinators can override with mandatory reasoning.

Built with **FastAPI**, **SQLAlchemy**, and OAuth 2.0-style JWT auth with
role-based access control (RBAC). Ships with three clients on top of the REST
API:

- a **Streamlit web UI** for day-to-day operation,
- an **AI agent team** (LangChain coordinator + specialist subagents on
  OpenRouter) that operates the whole system in plain language, and
- a **Prometheus + Grafana** observability stack.

## Repository layout

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
  model.py         OpenRouter ChatOpenAI factory (retries, free-tier)
  smoke_test.py    live end-to-end agent check (run manually)
frontend/               # Web UI (Streamlit)
  app.py           login + trials/evaluate/review/caregivers/audit/agent tabs
monitoring/             # Grafana dashboard provisioning
prometheus/             # Prometheus scrape + alert rules
kubernetes/             # Helm-less manifests for the API, Redis, and Postgres
```

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env          # adjust secrets for production
uvicorn app.main:app --reload
```

Interactive docs: http://localhost:8000/docs · Metrics: http://localhost:8000/api/v1/metrics

Four seed users are created on first startup (dev only):

| Username      | Role          | Password                    |
|---------------|---------------|-----------------------------|
| `admin`       | ADMINISTRATOR | `admin-password-change-me`  |
| `coordinator` | COORDINATOR   | `coordinator-password-change-me` |
| `provider`    | PROVIDER      | `provider-password-change-me` |
| `auditor`     | AUDITOR       | `auditor-password-change-me` |

## Docker (full stack)

```bash
docker compose up --build     # API, agent, UI, Postgres, Redis, Prometheus, Grafana
```

| Service       | URL                                    |
|---------------|----------------------------------------|
| API           | http://localhost:8000/docs             |
| Web UI        | http://localhost:8501                  |
| Agent         | http://localhost:8100 (`POST /agent/chat`) |
| Prometheus    | http://localhost:9090                  |
| Grafana       | http://localhost:3000 (admin/admin)    |
| Postgres      | `localhost:5432` (carematch/carematch) |
| Redis         | `localhost:6379`                       |

## Web UI (Streamlit)

```bash
pip install -r frontend/requirements.txt
streamlit run frontend/app.py        # http://localhost:8501
# API_URL / AGENT_URL env vars override the default localhost endpoints
```

Tabs:

- **📋 Trials** — create trials (protocol text or structured rules) and inspect
  parsed rules, status, and protocol version.
- **🧪 Evaluate** — paste a FHIR R4 Patient/Bundle, run it against a trial, and
  see the per-rule evidence chain, confidence, and overall recommendation.
- **✅ Review** — approve an AI recommendation or override individual rules
  (reasoning is required); watch the review/final status update.
- **👥 Caregivers** — list and register caregivers with relationship types
  `PRIMARY`, `EMERGENCY_CONTACT`, `LEGAL_PROXY`, `POWER_OF_ATTORNEY`.
- **🕵️ Audit** — read the HIPAA audit trail and Prometheus metrics.
- **🤖 Agent** — chat with the AI agent team and have it do the work for you.

## AI agent team

The `agent/` service is a **coordinator agent** (LangChain) that never calls the
API directly — it delegates to six specialist subagents, each with its own tool
subset bound to the CareMatch REST API, then synthesizes their reports:

| Subagent        | Responsibility                                        |
|-----------------|-------------------------------------------------------|
| `auth`          | Log in and obtain a session token                     |
| `trials`        | Create, list, inspect, and update trial protocols     |
| `eligibility`   | Evaluate a patient (FHIR) against a trial             |
| `assessments`   | Review, approve, or override AI recommendations       |
| `caregivers`    | Manage patient caregivers                             |
| `audit`         | Read the audit trail and system metrics               |

Models come from OpenRouter (free tier by default — `openai/gpt-oss-20b:free`).

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

- The coordinator delegates one task at a time and chains subagents for
  multi-domain requests (e.g. evaluate → then review the assessment).
- All subagents share one `AgentSession`, so a token obtained by `auth` is
  available to every other tool in the same conversation.
- Rules created from free-text protocols require **bullet-point** lines (the
  parser skips prose paragraphs) — the trials subagent is prompted to format
  them accordingly.
- Overrides always require reasoning; the API enforces it server-side too.
- Free OpenRouter models are rate-limited and occasionally flaky; retries are
  enabled in `agent/model.py`.

## Eligibility engine

1. **Protocol parsing** — `POST /trials/create` accepts either a free-text
   protocol document or pre-structured rules. The parser classifies each
   bullet line into a rule type and keeps unclassifiable lines as
   `description` rules flagged for clinical review.
2. **Rule types** — `age_range`, `medication`, `diagnosis`, `lab_value`,
   `temporal`, `caregiver`, and `description`, each with a `category` of
   `inclusion` or `exclusion`.
3. **Evaluation** — each rule produces a per-rule `status` (`MATCHES`,
   `DOES_NOT_MATCH`, `UNCLEAR`), a confidence score, an evidence chain, and a
   list of missing data.
4. **Aggregation** —
   - any `UNCLEAR` rule → overall **UNCLEAR** (needs more information),
   - any inclusion rule that `DOES_NOT_MATCH` or exclusion rule that
     `MATCHES` → **LIKELY_INELIGIBLE**,
   - otherwise → **LIKELY_ELIGIBLE**.
5. **Human-in-the-loop** — the AI recommendation is **never final**. A
   coordinator reviews, then either **approves** it or **overrides** individual
   rule results with mandatory reasoning. The override's impact on overall
   eligibility is tracked and audited.

## Auditing & compliance

Every auth event, data access, assessment creation, approval, and override is
written to an audit trail with PII redacted for HIPAA compliance. AUDITOR and
ADMINISTRATOR roles can read the trail at `/api/v1/audit/logs`.

## Kubernetes

`kubectl apply -f kubernetes/manifests.yaml` deploys the API (2 replicas with
readiness/liveness probes), a Redis service, and the Postgres secret. Set the
`carematch-secrets` values for production.

## Environment variables

See `.env.example` for the full list. Highlights:

| Variable                  | Default                        | Purpose                                   |
|---------------------------|--------------------------------|-------------------------------------------|
| `DATABASE_URL`            | `sqlite:///./carematch.db`     | SQLAlchemy connection string (Postgres in prod) |
| `REDIS_URL`               | `redis://localhost:6379/0`     | Cache backend (in-memory fallback)        |
| `JWT_SECRET`              | `change-me-in-production`      | Token signing secret (set a long random value) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15`                       | Access token lifetime                     |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7`                          | Refresh token lifetime                    |
| `RATE_LIMIT_PER_MINUTE`   | `100`                          | API rate limit per client                 |
| `SEED_*_USERNAME/PASSWORD` | dev accounts                 | Seed users created on first startup       |
| `OPENROUTER_API_KEY`      | (empty)                        | Required for the agent service            |
| `OPENROUTER_MODEL`        | `openai/gpt-oss-20b:free`      | Agent model slug on OpenRouter            |
| `AGENT_API_URL`           | `http://localhost:8000`        | API base URL the agent talks to           |

## Testing & quality

```bash
pip install -r requirements-dev.txt
pytest                       # full suite (API + agent tools + frontend)
pytest --cov=app --cov-fail-under=80
ruff check app agent frontend tests   # lint
ruff format --check app agent frontend tests
mypy app agent               # type check
```

## API surface

All routes are prefixed `/api/v1`.

| Method | Path                                    | Roles                              |
|--------|-----------------------------------------|------------------------------------|
| GET    | `/health`, `/ready`                     | public                             |
| POST   | `/auth/token`                           | public                             |
| POST   | `/auth/refresh`                         | public                             |
| GET    | `/auth/me`                              | authenticated                      |
| POST   | `/patients/evaluate-eligibility`        | PROVIDER, COORDINATOR, ADMIN       |
| GET    | `/patients/{id}`                        | PROVIDER, COORDINATOR, ADMIN       |
| POST   | `/trials/create`                        | PROVIDER, ADMIN                    |
| GET    | `/trials`, `/trials/{id}`               | all roles                          |
| PUT    | `/trials/{id}`                          | PROVIDER, ADMIN (bumps protocol version) |
| POST   | `/caregivers`                           | PROVIDER, ADMIN                    |
| GET    | `/patients/{id}/caregivers`             | PROVIDER, COORDINATOR, ADMIN, AUDITOR |
| GET    | `/assessments`, `/assessments/{id}`     | PROVIDER, COORDINATOR, ADMIN       |
| PUT    | `/assessments/{id}/override`            | COORDINATOR, ADMIN                 |
| PUT    | `/assessments/{id}/approve`             | COORDINATOR, ADMIN                 |
| GET    | `/assessments/{id}/overrides`           | AUDITOR, ADMIN                     |
| GET    | `/audit/logs`                           | AUDITOR, ADMIN                     |
| GET    | `/metrics`                              | public (Prometheus)                |

## Key flows

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
