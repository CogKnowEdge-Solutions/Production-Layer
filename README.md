# CareMatch API

Clinical trial patient eligibility screening with explainable, evidence-backed AI
recommendations and human-in-the-loop review. FHIR R4 patient data is evaluated
against trial protocols using a rules engine; every recommendation is traceable
to evidence, and coordinators can override with mandatory reasoning.

Built with FastAPI, SQLAlchemy, and OAuth 2.0-style JWT auth with role-based
access control (RBAC).

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
docker compose up --build     # API, Postgres, Redis, Prometheus, Grafana
```

- API: http://localhost:8000
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin/admin)

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
app/
  api/v1/          HTTP routers (auth, patients, trials, caregivers, assessments, audit, metrics)
  db/              SQLAlchemy models and repositories
  middleware/      RBAC auth, audit, metrics, rate limiting, error handlers
  services/        FHIR processing, rules engine, protocol parser, eligibility, OAuth, security
  schemas/         Pydantic request/response models
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
