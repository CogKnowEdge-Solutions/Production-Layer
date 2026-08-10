# Tasks: CareMatch API

**Input**: Design documents from `.specify/specs/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Included. The CareMatch Constitution mandates test-first development with minimum 80% coverage on critical paths, so test tasks are generated for every user story.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Backend (FastAPI)**: `app/`, `tests/` at repository root (per plan.md `/app/` structure)
- Deployment configs: `Dockerfile`, `docker-compose.yml`, `kubernetes/`, `prometheus/`, `monitoring/`
- CI/CD: `.github/workflows/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Create project structure per implementation plan (`app/`, `app/api/v1/`, `app/db/`, `app/middleware/`, `app/schemas/`, `app/services/`, `tests/`)
- [x] T002 Create `requirements.txt` with pinned dependencies (fastapi, uvicorn, sqlalchemy, pydantic, pydantic-settings, PyJWT, passlib, bcrypt, httpx, pytest, prometheus-client, redis, python-multipart)
- [x] T003 [P] Create environment configuration in `app/config.py` using pydantic-settings (DATABASE_URL, JWT_SECRET, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS, REDIS_URL, ENV, seed credentials)
- [x] T004 [P] Create `.env.example` documenting all configurable environment variables
- [x] T005 [P] Create pytest configuration in `pyproject.toml` and extend `.gitignore`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T006 Setup SQLAlchemy engine, session factory, and `Base` in `app/db/database.py` (SQLite default for dev/tests, PostgreSQL via DATABASE_URL)
- [x] T007 Create SQLAlchemy ORM models in `app/db/models.py`: Patient, Trial, Assessment, RuleEvaluation, Caregiver, AssessmentOverride, AuditLog, User
- [x] T008 Create repository layer in `app/db/repositories.py` (CRUD for patients, trials, assessments, rule evaluations, caregivers, overrides, audit logs, users)
- [x] T009 Implement JWT authentication service in `app/services/oauth.py` (PyJWT: access token 15-min, refresh token 7-day, token validation, role claims)
- [x] T010 Implement auth middleware and RBAC dependencies in `app/middleware/auth.py` and `app/dependencies.py` (roles: Administrator, Provider, Coordinator, Auditor; require_role dependency)
- [x] T011 Implement audit logging service in `app/services/audit_logger.py` (log data access/actions with timestamp, user, action, resource, result; PII masking)
- [x] T012 Implement caching service in `app/services/cache.py` (Redis via redis-py with graceful in-memory fallback when Redis unavailable)
- [x] T013 Implement global error handlers in `app/middleware/error.py` (structured errors, no PII in messages)
- [x] T014 Implement audit logging middleware in `app/middleware/audit.py` (request-scoped data access logging)
- [x] T015 Wire FastAPI application in `app/main.py` (router registration, middleware, startup/shutdown, seed default users: admin/coordinator/provider/auditor)
- [x] T016 Implement health endpoints `GET /health` and `GET /ready` in `app/api/v1/health.py`

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Patient Trial Eligibility Evaluation (Priority: P1) 🎯 MVP

**Goal**: Coordinator submits FHIR patient data + trial reference; system evaluates each trial rule individually producing matches/does-not-match/unclear with evidence, and returns overall eligibility status.

**Independent Test**: Submit sample FHIR patient bundle via API, receive structured eligibility report, verify evidence trails exist for each rule evaluation.

### Tests for User Story 1 ⚠️ (write FIRST, ensure they FAIL before implementation)

- [x] T017 [P] [US1] Unit tests for rules engine (age_range, medication, diagnosis, lab_value, temporal, caregiver) in `tests/test_rules_engine.py`
- [x] T018 [P] [US1] Unit tests for FHIR processor extraction/validation in `tests/test_fhir_processor.py`
- [x] T019 [P] [US1] Contract test for `POST /api/v1/patients/evaluate-eligibility` in `tests/test_eligibility.py`

### Implementation for User Story 1

- [x] T020 [P] [US1] Create patient/assessment Pydantic schemas in `app/schemas/patient.py` and `app/schemas/assessment.py`
- [x] T021 [US1] Implement FHIR R4 processor in `app/services/fhir_processor.py` (validate Patient bundle, extract demographics, medications, conditions, observations/labs, allergies, caregiver references; detect missing required fields)
- [x] T022 [US1] Implement rules engine in `app/services/rules_engine.py` (rule types: age range, medication exclusion, diagnosis requirement, lab value thresholds, temporal constraints, caregiver; output per-rule status, confidence, evidence citations, missing-data notes)
- [x] T023 [US1] Implement eligibility orchestration in `app/services/eligibility.py` (evaluate rules, aggregate status: any UNCLEAR -> UNCLEAR, inclusion fail -> INELIGIBLE, else ELIGIBLE; overall confidence = avg(rule confidence) * data completeness)
- [x] T024 [US1] Implement `POST /api/v1/patients/evaluate-eligibility` in `app/api/v1/patients.py` (persist patient, create Assessment + RuleEvaluation rows, return report)
- [x] T025 [US1] Implement patient data quality scoring in `app/services/eligibility.py`

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - Provider Clinical Trial Integration (Priority: P1)

**Goal**: Healthcare provider systems integrate via standard FHIR-based API with OAuth 2.0/JWT auth, receiving structured JSON responses.

**Independent Test**: Hospital system sends FHIR request with Bearer token; API authenticates, processes, returns valid JSON within SLA; verify versioning and pagination.

### Tests for User Story 2 ⚠️

- [x] T026 [P] [US2] Contract tests for auth endpoints (`POST /api/v1/auth/token`, refresh) in `tests/test_auth.py`
- [x] T027 [P] [US2] Integration test for provider flow (FHIR request -> structured JSON response) in `tests/test_provider_integration.py`

### Implementation for User Story 2

- [x] T028 [P] [US2] Implement `POST /api/v1/auth/token` and refresh endpoint in `app/api/v1/auth.py` (OAuth2 password + client-credentials flows, RBAC role claims, token expiration 15-min access / 7-day refresh)
- [x] T029 [US2] Register `/api/v1` versioning prefix and router wiring in `app/main.py`
- [x] T030 [US2] Implement pagination for list endpoints (default 50 items, max 1000) in `app/dependencies.py` + repositories
- [x] T031 [US2] Implement basic per-hospital rate limiting in `app/middleware/ratelimit.py` (100 req/min per hospital)
- [x] T032 [US2] Implement PII masking/security helpers in `app/services/security.py` (mask names, hash MRNs, redact PII from logs/errors)

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - Trial Protocol Management & Standardization (Priority: P2)

**Goal**: Trial sponsors create and store standardized protocol rulebooks that all hospitals evaluate against identically.

**Independent Test**: Upload trial protocol via `POST /api/v1/trials/create`, retrieve via `GET /api/v1/trials/{trial_id}`, verify structured rules and versioning.

### Tests for User Story 3 ⚠️

- [x] T033 [P] [US3] Contract tests for trial endpoints in `tests/test_trials.py`
- [x] T034 [P] [US3] Unit tests for protocol parser in `tests/test_protocol_parser.py`

### Implementation for User Story 3

- [x] T035 [P] [US3] Create trial Pydantic schemas in `app/schemas/trial.py`
- [x] T036 [US3] Implement protocol parser/converter in `app/services/protocol_parser.py` (human-readable rules -> structured rule objects with type, criteria, thresholds)
- [x] T037 [US3] Implement `POST /api/v1/trials/create` in `app/api/v1/trials.py` (Admin/Provider role, versioned protocol, audit trail)
- [x] T038 [US3] Implement `GET /api/v1/trials/{trial_id}` in `app/api/v1/trials.py` (full protocol with rules, metadata, version history)

**Checkpoint**: All user stories should now be independently functional

---

## Phase 6: User Story 4 - Research Coordinator Caregiver Context (Priority: P2)

**Goal**: System captures caregiver info and evaluates caregiver-related trial rules (e.g., "primary caregiver must be adult", "proxy consent required").

**Independent Test**: Register caregiver via `POST /api/v1/caregivers`, retrieve via `GET /api/v1/patients/{patient_id}/caregivers`, evaluate trial rule referencing caregiver.

### Tests for User Story 4 ⚠️

- [x] T039 [P] [US4] Contract tests for caregiver endpoints in `tests/test_caregivers.py`

### Implementation for User Story 4

- [x] T040 [P] [US4] Create caregiver Pydantic schemas in `app/schemas/caregiver.py`
- [x] T041 [US4] Implement `POST /api/v1/caregivers` in `app/api/v1/caregivers.py` (Provider/Admin role, relationships: primary, emergency contact, legal proxy, power of attorney)
- [x] T042 [US4] Implement `GET /api/v1/patients/{patient_id}/caregivers` in `app/api/v1/caregivers.py`
- [x] T043 [US4] Implement caregiver rule type in rules engine (`app/services/rules_engine.py`) and caregiver inclusion in FHIR bundle processing

**Checkpoint**: At this point, User Stories 1-4 should all work independently

---

## Phase 7: User Story 5 - AI Decision Override & Feedback Loop (Priority: P2)

**Goal**: Coordinators review AI assessments, approve or override specific rules with reasoning; all decisions logged as feedback for model improvement.

**Independent Test**: Retrieve assessment via `GET /api/v1/assessments/{id}`, override a rule via `PUT /api/v1/assessments/{id}/override` with reasoning, verify override logged and overall status recalculated.

### Tests for User Story 5 ⚠️

- [x] T044 [P] [US5] Contract tests for assessment retrieval + override in `tests/test_assessments.py`

### Implementation for User Story 5

- [x] T045 [P] [US5] Create override Pydantic schemas in `app/schemas/assessment.py` (original status, new status, reasoning, coordinator id)
- [x] T046 [US5] Implement `GET /api/v1/assessments/{assessment_id}` in `app/api/v1/assessments.py` (full assessment with evidence chains)
- [x] T047 [US5] Implement `PUT /api/v1/assessments/{assessment_id}/override` in `app/api/v1/assessments.py` (Coordinator/Admin role, require reasoning for override, synchronous audit log, recalculate overall status, mark OVERRIDDEN)
- [x] T048 [US5] Implement `GET /api/v1/assessments/{assessment_id}/overrides` feedback export in `app/api/v1/assessments.py` (Auditor/Admin access for retraining dataset)

**Checkpoint**: All 5 user stories functional and independently testable

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T049 [P] Implement Prometheus metrics middleware and `GET /metrics` in `app/middleware/metrics.py` + `app/api/v1/metrics.py` (http_requests_total, http_request_duration_seconds, assessments_created_total, assessments_override_count, ai_confidence_distribution, error rates)
- [x] T050 [P] Create Prometheus scrape config in `prometheus/prometheus.yml`
- [x] T051 [P] Create Grafana dashboard JSON in `monitoring/grafana/carematch-dashboard.json` (System Health, API Performance, AI Assessment Quality)
- [x] T052 [P] Create multi-stage `Dockerfile` and `.dockerignore`
- [x] T053 [P] Create `docker-compose.yml` (api, postgres, redis, prometheus, grafana)
- [x] T054 [P] Create Kubernetes manifests in `kubernetes/` (api-deployment.yaml, api-service.yaml, ingress.yaml, hpa.yaml, postgres-statefulset.yaml)
- [x] T055 [P] Create GitHub Actions CI workflow in `.github/workflows/ci.yml` (lint, test with coverage, build)
- [x] T056 [P] Write `README.md` with architecture overview, setup, run, and test instructions
- [x] T057 Run full test suite and fix any failures
- [x] T058 Final validation: coverage report >= 80% on critical paths, `python -m pytest` green, app boots with `uvicorn`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - User stories proceed sequentially in priority order (US1 -> US2 -> US3 -> US4 -> US5)
- **Polish (Final Phase)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational (Phase 2)
- **US2 (P1)**: Can start after Foundational (Phase 2); provides auth surface used by all stories
- **US3 (P2)**: Can start after Foundational (Phase 2); US1 depends on trial data for evaluation
- **US4 (P2)**: Can start after Foundational (Phase 2); caregiver rule type integrates with US1 rules engine
- **US5 (P2)**: Can start after Foundational (Phase 2); depends on US1 assessment persistence

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models/schemas before services
- Services before endpoints
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- All tests for a user story marked [P] can run in parallel
- Schemas/models within a story marked [P] can run in parallel
- Polish tasks marked [P] (metrics, docker, k8s, docs, CI) can run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Unit tests for rules engine in tests/test_rules_engine.py"
Task: "Unit tests for FHIR processor in tests/test_fhir_processor.py"
Task: "Contract test for POST /api/v1/patients/evaluate-eligibility in tests/test_eligibility.py"

# Launch all schemas for User Story 1 together:
Task: "Create patient schemas in app/schemas/patient.py"
Task: "Create assessment schemas in app/schemas/assessment.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational -> Foundation ready
2. Add User Story 1 -> Test independently -> Deploy/Demo (MVP!)
3. Add User Story 2 -> Test independently -> Deploy/Demo
4. Add User Story 3 -> Test independently -> Deploy/Demo
5. Add User Story 4 -> Test independently -> Deploy/Demo
6. Add User Story 5 -> Test independently -> Deploy/Demo
7. Each story adds value without breaking previous stories

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
