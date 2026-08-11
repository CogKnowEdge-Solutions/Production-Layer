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

## Table of Contents

- [System architecture](#system-architecture)
- [Repository layout](#repository-layout)
- [Run locally](#run-locally)
  - [1. Clone (this folder only)](#1-clone-this-folder-only)
  - [2. Environment setup](#2-environment-setup)
  - [3. Backend API (FastAPI)](#3-backend-api-fastapi)
  - [4. Web UI (Streamlit)](#4-web-ui-streamlit)
  - [5. AI agent team (optional)](#5-ai-agent-team-optional)
  - [6. Verify](#6-verify)
- [Run in deployment](#run-in-deployment)
  - [Option A — Docker Compose (full stack)](#option-a--docker-compose-full-stack)
  - [Option B — Kubernetes](#option-b--kubernetes)
- [Web UI (Streamlit)](#web-ui-streamlit)
- [AI agent team](#ai-agent-team)
  - [Multi-agent orchestration](#multi-agent-orchestration)
- [Eligibility engine](#eligibility-engine)
  - [Human-in-the-loop review](#human-in-the-loop-review)
- [Auditing & compliance](#auditing--compliance)
- [Environment variables](#environment-variables)
- [Testing & quality](#testing--quality)
- [API surface](#api-surface)
- [Key flows](#key-flows)

## System architecture

```mermaid
flowchart LR
    User["Clinician / Coordinator"]
    UI["Streamlit Web UI<br/><b>:8501</b> frontend/app.py"]
    AG["AI Agent Team<br/><b>:8100</b> agent/main.py"]
    API["FastAPI API<br/><b>:8000</b> app/main.py"]
    PG[("PostgreSQL<br/>postgres:5432")]
    RD[("Redis cache<br/>redis:6379")]
    PROM["Prometheus<br/>:9090"]
    GRAF["Grafana<br/>:3000"]
    OR["OpenRouter<br/>(free LLM models)"]

    User --> UI
    User --> AG
    UI -->|"REST /api/v1 (JWT)"| API
    AG -->|"REST /api/v1 (JWT)"| API
    UI -->|"POST /agent/chat"| AG
    AG -->|"LLM tool-calling"| OR
    API --> PG
    API --> RD
    API -->|"/metrics"| PROM
    PROM --> GRAF
    AG --> API
```

## Repository layout

```mermaid
flowchart TD
    subgraph API["<b>app/</b> — FastAPI service"]
        direction TB
        R["api/v1/<br/>auth · patients · trials · caregivers<br/>assessments · audit · metrics"]
        S["services/<br/>fhir_processor · rules_engine<br/>protocol_parser · eligibility"]
        D["db/<br/>SQLAlchemy models + repositories"]
        M["middleware/<br/>RBAC auth · audit · metrics · rate limiting"]
        SC["schemas/<br/>Pydantic request/response"]
        R --> S
        S --> D
        M -.-> R
        SC -.-> R
    end

    subgraph AGENT["<b>agent/</b> — AI agent team"]
        direction TB
        A1["main.py<br/>POST /agent/chat"]
        A2["coordinator.py<br/>delegates to subagents"]
        A3["subagents.py<br/>6 specialists"]
        A4["tools.py<br/>LangChain tools → REST"]
        A1 --> A2 --> A3 --> A4
    end

    subgraph FE["<b>frontend/</b> — Streamlit UI"]
        F1["app.py<br/>login + 6 tabs"]
    end

    subgraph OPS["<b>ops</b> — observability & deployment"]
        P1["prometheus/ scrape + alert rules"]
        P2["monitoring/ Grafana dashboards"]
        P3["kubernetes/ manifests"]
        P4["docker-compose.yml"]
    end

    FE --> R
    AGENT --> R
```

## Run locally

### 1. Clone (this folder only)

CareMatch-SDD lives in the `Production-Layer` monorepo. To fetch only this
folder without the rest of the repo, use a sparse checkout:

```bash
git clone --depth 1 --filter=blob:none --sparse https://github.com/CogKnowEdge-Solutions/Production-Layer.git
cd Production-Layer
git sparse-checkout set CareMatch-SDD
cd CareMatch-SDD
```

### 2. Environment setup

Requires Python 3.11+.

```bash
python -m venv .venv && source .venv/bin/activate   # macOS/Linux; .\.venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env          # adjust secrets for production
```

### 3. Backend API (FastAPI)

```bash
uvicorn app.main:app --reload                       # http://localhost:8000
```

- Interactive docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health
- Prometheus metrics: http://localhost:8000/api/v1/metrics
- On first startup the DB is auto-created (SQLite by default) and seeded with
  four dev users; the seed user table below.

Optional services used by the API: PostgreSQL (set `DATABASE_URL`) and Redis
(`REDIS_URL`). Without Redis the app falls back to an in-memory cache.

### 4. Web UI (Streamlit)

```bash
pip install -r frontend/requirements.txt
streamlit run frontend/app.py        # http://localhost:8501
# API_URL / AGENT_URL env vars override the default localhost endpoints
```

### 5. AI agent team (optional)

```bash
pip install -r agent/requirements.txt
cp .env.example .env                 # already done above; add OPENROUTER_API_KEY
uvicorn agent.main:app --port 8100   # http://localhost:8100 (POST /agent/chat)
# OPENROUTER_API_KEY + OPENROUTER_MODEL come from .env (see .env.example)
```

### 6. Verify

```bash
pip install -r requirements-dev.txt
pytest                        # full suite (API + agent tools + frontend)
ruff check app agent frontend tests
```

Four seed users are created on first startup (dev only):

| Username      | Role          | Password                    |
|---------------|---------------|-----------------------------|
| `admin`       | ADMINISTRATOR | `admin-password-change-me`  |
| `coordinator` | COORDINATOR   | `coordinator-password-change-me` |
| `provider`    | PROVIDER      | `provider-password-change-me` |
| `auditor`     | AUDITOR       | `auditor-password-change-me` |

## Run in deployment

### Option A — Docker Compose (full stack)

Runs the API, agent, UI, Postgres, Redis, Prometheus, Alertmanager, and Grafana
in production mode (`ENV=production`) against Postgres.

**Quick start (3 steps):**

```bash
# 1. Clone and navigate to the project:
git clone --depth 1 --filter=blob:none --sparse https://github.com/CogKnowEdge-Solutions/Production-Layer.git
cd Production-Layer && git sparse-checkout set CareMatch-SDD && cd CareMatch-SDD

# 2. Set up environment variables:
cp .env.example .env
# Edit .env to set OPENROUTER_API_KEY if you want the agent to work
# (or leave it empty to skip agent features)
export JWT_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(64))')"

# 3. Build and start everything:
docker compose up --build -d
```

That's it! The system will auto-initialize the database with seed users on first startup.

**Access the stack:**

| Service | URL | Notes |
|---------|-----|-------|
| **Streamlit Web UI** | http://localhost:8501 | Login: `admin` / `admin-password-change-me` |
| **FastAPI Docs** | http://localhost:8000/docs | Interactive API explorer |
| **Agent API** | http://localhost:8100 | POST `/agent/chat` for multi-agent requests |
| **Grafana Dashboards** | http://localhost:3000 | Login: `admin` / `admin` |
| **Prometheus Metrics** | http://localhost:9090 | Prometheus scrape targets and alerts |
| **PostgreSQL** | `localhost:5432` | User: `carematch`, Password: `carematch` |
| **Redis Cache** | `localhost:6379` | In-memory cache (optional, graceful fallback) |

**Manage the stack:**

```bash
# View logs in real-time:
docker compose logs -f

# View logs for a single service:
docker compose logs -f api
docker compose logs -f frontend

# Stop all containers (keep volumes):
docker compose down

# Stop and remove volumes (resets database):
docker compose down -v

# Rebuild after code changes:
docker compose up --build -d
```

**Troubleshooting Docker startup:**

1. **API takes 30+ seconds to start?** → It's running database migrations. Check logs: `docker compose logs api`
2. **"Connection refused" on port 8501?** → Streamlit takes a moment to bind. Wait 10s and refresh.
3. **"PostgreSQL not ready" error?** → Postgres health check is strict. Retry: `docker compose restart api`
4. **Database locked error?** → Run `docker compose down -v && docker compose up -d` to reset.
5. **Agent always times out?** → Missing or invalid `OPENROUTER_API_KEY` in `.env`. Set one or leave feature disabled.

**For production deployments:**

Before deploying to a shared/public environment:
1. Generate a strong `JWT_SECRET`: `python -c 'import secrets; print(secrets.token_urlsafe(64))'`
2. Change all `SEED_*` credentials in `.env`
3. Use a real PostgreSQL instance (not in-container), set `DATABASE_URL` properly
4. Use a real Redis instance for caching
5. Point ports through a TLS-terminating reverse proxy (nginx/Caddy/Traefik)

| Service       | URL                                    |
|---------------|----------------------------------------|
| API           | http://localhost:8000/docs             |
| Web UI        | http://localhost:8501                  |
| Agent         | http://localhost:8100 (`POST /agent/chat`) |
| Prometheus    | http://localhost:9090                  |
| Grafana       | http://localhost:3000 (admin/admin)    |
| Postgres      | `localhost:5432` (carematch/carematch) |
| Redis         | `localhost:6379`                       |

For a production host, point the API and UI `ports` at a TLS-terminating
reverse proxy (nginx/Caddy/Traefik) and set strong `SEED_*` credentials plus a
real `JWT_SECRET` and `DATABASE_URL` before first boot.

### Option B — Kubernetes

Prereqs: a cluster with `kubectl` configured, an image registry, and (if you
want Postgres managed in-cluster) a way to persist `postgres` data.

1. **Build and push the image**:

   ```bash
   docker build -t <registry>/carematch-api:latest .
   docker push <registry>/carematch-api:latest
   ```

2. **Set production secrets** (the sample secret ships with dev defaults —
   rotate `jwt-secret` and `database-url` before applying):

   ```bash
   kubectl create secret generic carematch-secrets \
     --from-literal=database-url='postgresql+psycopg://carematch:CHANGE_ME@postgres:5432/carematch' \
     --from-literal=jwt-secret='CHANGE_ME_IN_PRODUCTION' \
     --dry-run=client -o yaml | kubectl apply -f -
   ```

3. **Point the manifest at your image and apply** — edit
   `kubernetes/manifests.yaml` to replace `image: carematch-api:latest` with
   your pushed image, then:

   ```bash
   kubectl apply -f kubernetes/manifests.yaml
   kubectl rollout status deployment/carematch-api
   kubectl get pods,svc -l app=carematch
   ```

   This deploys the API (2 replicas with readiness/liveness probes), a Redis
   service, and the `carematch-secrets` Secret. Postgres is expected to be
   reachable at `postgres:5432`; provision it in-cluster or point
   `database-url` at a managed instance (RDS, Cloud SQL, etc.). Expose the
   `carematch-api` Service to the internet via an ingress or LoadBalancer.

4. **Scale and update**:

   ```bash
   kubectl scale deployment/carematch-api --replicas=4
   kubectl set image deployment/carematch-api api=<registry>/carematch-api:<tag>
   ```

## Web UI (Streamlit)

```bash
pip install -r frontend/requirements.txt
API_URL=http://localhost:8000 AGENT_URL=http://localhost:8100 streamlit run frontend/app.py
# Or just: streamlit run frontend/app.py (defaults to localhost:8000 and :8100)
```

**UI Tabs:**

- **📋 Trials** — create trials from free-text protocol documents or bullet-point rules.
  Inspect the parsed rules, status, and protocol version. Rules are re-versioned when
  protocols change.

- **🧪 Evaluate** — paste a **FHIR R4 Patient resource** (single patient demographics)
  or a **Bundle** (patient + conditions, medications, lab observations, etc.).
  - **Patient resource**: Recommended for simple demographics only; API will process it as-is.
  - **Bundle**: Use when you have related clinical data (diagnoses, meds, labs) to include.
  - Both formats are normalized internally; the engine extracts the same structured data either way.
  - Results show per-rule evidence, confidence, and overall recommendation (AI recommendation only—
    requires coordinator approval).

- **✅ Review** — coordinators see all assessments (pending review). For each:
  - Approve it to finalize the recommendation, OR
  - Override individual rule results (with mandatory reasoning). Overrides are tracked and audited.

- **👥 Caregivers** — register and manage patient caregivers with relationship types:
  `PRIMARY`, `EMERGENCY_CONTACT`, `LEGAL_PROXY`, `POWER_OF_ATTORNEY`.

- **🕵️ Audit** — read the HIPAA audit trail (auth events, data access, approvals, overrides).
  Filter by date range, user, action type. Also view Prometheus metrics (latency, errors, etc.).

- **🤖 Agent** — chat with the AI agent team to automate workflows in plain language:
  "Create a diabetes trial, evaluate Jane Smith against it, then approve the assessment."

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

### Multi-agent orchestration

A single user request can fan out across several subagents. The coordinator
decides the routing, and every subagent shares one `AgentSession`, so a token
obtained by `auth` is available to every tool:

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Coord as Coordinator<br/>(coordinator.py)
    participant Auth as auth subagent
    participant Tri as trials subagent
    participant Eli as eligibility subagent
    participant Rev as assessments subagent
    participant API as CareMatch API

    User->>Coord: "Create a diabetes trial, evaluate Jane, then review the result"
    Coord->>Auth: delegate login (admin / password)
    Auth->>API: POST /auth/token
    API-->>Auth: access_token
    Auth-->>Coord: "Logged in" (token cached in AgentSession)
    Coord->>Tri: create trial (bullet protocol text)
    Tri->>API: POST /trials/create
    API-->>Tri: trial_id + N parsed rules
    Tri-->>Coord: trial_id
    Coord->>Eli: evaluate patient FHIR bundle
    Eli->>API: POST /patients/evaluate-eligibility
    API-->>Eli: assessment_id + per-rule evidence
    Eli-->>Coord: assessment_id, overall status
    Coord->>Rev: approve assessment
    Rev->>API: PUT /assessments/{id}/approve
    API-->>Rev: review_status=APPROVED, final_status
    Rev-->>Coord: final eligibility
    Coord-->>User: plain-language summary + IDs
```

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

```mermaid
flowchart LR
    subgraph INPUT["Input"]
        P["Protocol document<br/>(free text or structured rules)"]
        F["FHIR R4<br/>Patient or Bundle"]
    end
    P --> PP["protocol_parser.py<br/>classify lines → rule objects"]
    PP --> RULES["Rules<br/>age_range · medication · diagnosis<br/>lab_value · temporal · caregiver · description<br/>category: inclusion | exclusion"]
    F --> FP["fhir_processor.py<br/>normalize → PatientData<br/>+ data completeness score"]
    RULES --> RE["rules_engine.py<br/>evaluate_rule() per rule"]
    FP --> RE
    RE --> AGG{"eligibility.py<br/>aggregate"}
    AGG -->|"any rule UNCLEAR"| U["UNCLEAR"]
    AGG -->|"inclusion fails or exclusion matches"| I["LIKELY_INELIGIBLE"]
    AGG -->|"otherwise"| E["LIKELY_ELIGIBLE"]
    U --> ASM["Assessment<br/>overall + ai_confidence + evidence<br/>review_status = PENDING"]
    I --> ASM
    E --> ASM
```

### Data flow and formats

**FHIR Input** — The API accepts two FHIR R4 formats, both of which are normalized to the same internal `PatientData` model:

1. **Patient Resource** (recommended for raw patient data):
   ```json
   {
     "resourceType": "Patient",
     "id": "p-123",
     "identifier": [{"system": "http://hospital/mrn", "value": "M-12345"}],
     "name": [{"family": "Doe", "given": ["Jane"]}],
     "birthDate": "1980-05-15",
     "gender": "female"
   }
   ```
   → Use this for demographics-only data (age, gender, name, MRN).

2. **Bundle** (recommended when you have related clinical data):
   ```json
   {
     "resourceType": "Bundle",
     "type": "collection",
     "entry": [
       {"resource": {"resourceType": "Patient", ...}},
       {"resource": {"resourceType": "Condition", ...}},
       {"resource": {"resourceType": "MedicationRequest", ...}},
       {"resource": {"resourceType": "Observation", ...}}
     ]
   }
   ```
   → Use this when you have conditions (diagnoses), medications, labs, allergies, procedures, or caregivers.

Both formats are processed by `fhir_processor.py` to extract a normalized `PatientData` object containing:
- Demographics (name, birth_date, gender, MRN)
- Active medications (RxNorm codes, status)
- Conditions (ICD-10 codes, clinical status, onset dates)
- Lab observations (LOINC codes, values, units, dates)
- Allergies and procedures
- Caregiver relationships and ages
- Data quality score (0.0–1.0, based on completeness)

### Evaluation flow

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

### Human-in-the-loop review

```mermaid
flowchart TD
    A["Assessment created<br/>review_status = PENDING"] --> R{"Coordinator<br/>decision"}
    R -->|"approve (FR-051)"| AP["review_status = APPROVED<br/>final_status = overall"]
    R -->|"override a rule (FR-053)"| OV["PUT /assessments/{id}/override<br/>reasoning REQUIRED"]
    OV --> RC{"Recalculate overall<br/>from all rule statuses"}
    RC -->|"any UNCLEAR"| U2["overall = UNCLEAR"]
    RC -->|"inclusion fails / exclusion matches"| I2["overall = LIKELY_INELIGIBLE"]
    RC -->|"otherwise"| E2["overall = LIKELY_ELIGIBLE"]
    U2 --> OD["review_status = OVERRIDDEN<br/>override_count++<br/>impact_on_eligibility tracked"]
    I2 --> OD
    E2 --> OD
    AP --> AUD["audit_logger.log()"]
    OD --> AUD
    AUD --> DB[("PostgreSQL")]
```

## Auditing & compliance

Every auth event, data access, assessment creation, approval, and override is
written to an audit trail with PII redacted for HIPAA compliance. AUDITOR and
ADMINISTRATOR roles can read the trail at `/api/v1/audit/logs`.

```mermaid
flowchart LR
    E["Event<br/>auth · data access · approve · override"] --> LOG["audit_logger.py<br/>PII redacted"]
    LOG --> DB[("PostgreSQL<br/>audit_logs")]
    AUD["AUDITOR / ADMIN"] -->|"GET /api/v1/audit/logs"| LOG
    DB --> LOG
```

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
