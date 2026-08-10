# Technical Architecture Specification: CareMatch API Platform

**Created**: 2026-08-08

**Version**: 1.0.0

**Status**: Approved for Implementation

---

## Executive Summary

CareMatch is a scalable healthcare clinical trial patient eligibility API built on Node.js/Express backend with PostgreSQL persistence, Redis caching, Docker containerization, and Kubernetes orchestration. The architecture supports:

- **Scale**: 5000+ concurrent patient evaluations
- **Performance**: < 200ms p95 latency for eligibility assessments
- **Reliability**: 99.9% uptime with multi-AZ deployment
- **Compliance**: HIPAA/GDPR with full audit logging and encryption
- **Security**: OAuth 2.0 authentication, RBAC authorization, encrypted data at rest/transit

---

## Architecture Pattern: Microservices with Hybrid Core

### Pattern Selection

**Selected Approach**: API Gateway + Hybrid Monolith Core + Specialized Microservices

**Rationale**:
- **Core Logic (Monolithic)**: Patient management, trial protocols, assessments are tightly coupled—microservices overhead adds complexity without benefit
- **Specialized Services (Microservices)**: FHIR processing, rules evaluation, audit logging have independent scalability needs and data isolation requirements
- **Benefits**: Simpler deployment initially, clean service boundaries for future scale, independent scaling where needed

### Architecture Layers

```
┌─────────────────────────────────────────────────┐
│         API Gateway (Kong/NGINX)                │
│  - Request routing, rate limiting               │
│  - TLS termination, request validation          │
│  - Request/response logging                     │
└─────────────────────────────────────────────────┘
         │
         ├─────────────────────────┬─────────────────────────┐
         │                         │                         │
         ▼                         ▼                         ▼
    ┌─────────────┐       ┌──────────────┐       ┌─────────────────┐
    │ Auth        │       │ Core API     │       │ Rules Engine    │
    │ Service     │       │ Service      │       │ Service         │
    └─────────────┘       └──────────────┘       └─────────────────┘
         │                      │                         │
         └──────────────────────┼─────────────────────────┘
                                │
                ┌───────────────┼───────────────┐
                │               │               │
                ▼               ▼               ▼
           ┌────────┐      ┌────────┐      ┌────────┐
           │PostgreSQL│    │Redis   │      │Elasticsearch│
           │(DB)     │      │(Cache) │     │(Logs)  │
           └────────┘      └────────┘      └────────┘
```

---

## Technology Stack Justification

| Layer | Technology | Justification |
|-------|-----------|---|
| **Runtime** | Python 3.11+ | Mature ecosystem, excellent async support, strong healthcare libraries |
| **Framework** | FastAPI 0.104+ | Modern async framework, automatic OpenAPI docs, ~7x faster than Flask, built-in validation |
| **Language** | Python 3.11+ | Type hints for schema validation, excellent FHIR libraries (fhirpy, fhir-parser) |
| **Database** | PostgreSQL 15+ | ACID transactions, JSON operators for FHIR, proven healthcare deployments |
| **Cache** | Redis 7.x | Sub-millisecond hits; session management; Pub/Sub for real-time invalidation |
| **Search/Logs** | Elasticsearch 8.x | Full-text audit log search; fast analytical queries; Kibana integration |
| **Container** | Docker | Multi-stage builds for minimal images; reproducible environments |
| **Orchestration** | Kubernetes 1.27+ | Auto-scaling, service discovery, healthcare-grade reliability |
| **Monitoring** | Prometheus + Grafana | Real-time metrics; healthcare compliance dashboards |
| **FHIR** | hl7-fhir-uv-core 4.0.1 | Standards-based data exchange; hospital ecosystem compatibility |
| **Auth** | Passport.js + JWT | OAuth 2.0 flows; hospital identity provider integration |

---

## Core Components

### 1. API Gateway (Kong/NGINX)
**Responsibilities**:
- Route requests to appropriate services
- Enforce rate limiting: 100 req/min per hospital system, 1000 req/sec global
- TLS 1.3 termination
- Request/response validation
- Metrics collection for all traffic

**Config**:
- Health checks every 10 seconds (200ms timeout)
- Max request body: 10MB (FHIR bundles)
- Connection pooling: 1000 persistent connections

### 2. Authentication Service
**Responsibilities**:
- OAuth 2.0 Authorization Code flow
- JWT token generation (15-min access, 7-day refresh)
- Token validation and revocation
- Role-based permission mapping
- Hospital identity provider integration (Okta, Active Directory)

**JWT Claims**:
```json
{
  "sub": "hospital-system-id",
  "user_id": "coordinator-id",
  "roles": ["Provider", "Coordinator"],
  "hospital_id": "hospital-123",
  "permissions": ["patients:read", "assessments:create"],
  "iat": 1691000000,
  "exp": 1691000900,
  "aud": "carewatch-api"
}
```

### 3. Core API Service (Monolithic)
**Responsibilities**:
- Patient CRUD endpoints
- Trial protocol management
- Assessment endpoints (create, retrieve, override)
- Caregiver management
- FHIR schema validation
- Request/response formatting

**Key Endpoints**:
```
POST   /api/v1/patients/evaluate-eligibility       (200ms SLA)
GET    /api/v1/assessments/{id}                   (100ms SLA)
PUT    /api/v1/assessments/{id}/override          (150ms SLA)
POST   /api/v1/trials/create                      (500ms SLA)
GET    /api/v1/trials/{trial_id}                  (100ms SLA)
POST   /api/v1/caregivers                         (200ms SLA)
```

### 4. FHIR Processor Service
**Responsibilities**:
- Validate FHIR R4 patient resources
- Extract clinical data into internal model
- Normalize values (dates, units, codes)
- Detect missing required fields
- Convert internal models back to FHIR

**Data Pipeline**:
```
FHIR Patient Bundle
    ↓ [Validation]
    ↓ [Extraction] - Demographics, medications, labs, vitals
    ↓ [Normalization] - Date formats, units, codes
    ↓ [Enrichment] - Timestamps, data quality scores
    ↓
Internal Patient Model (cached)
```

### 5. Rules Engine Service
**Responsibilities**:
- Parse trial protocol rules
- Evaluate patient against each rule independently
- Generate confidence scores (0.0-1.0)
- Link evidence to patient data
- Detect unclear/missing data
- Aggregate results to overall eligibility status

**Rule Types Supported**:
- Age range (min/max from DOB)
- Medication (active, RxNorm codes)
- Diagnosis (ICD-10, date ranges)
- Lab value (LOINC codes, numeric ranges)
- Temporal (trend analysis, data freshness)
- Caregiver (relationships, qualifications)

**Confidence Scoring**:
```
overall_confidence = AVG(rule_confidence) × data_completeness_factor

Overall Status Logic:
- If ANY rule = UNCLEAR → overall = UNCLEAR
- If ANY inclusion rule FAILS → LIKELY_INELIGIBLE
- If ALL inclusion rules PASS AND NO exclusion MATCH → LIKELY_ELIGIBLE
```

### 6. Audit Logger Service
**Responsibilities**:
- Log all data access (user, action, resource, timestamp)
- Log assessment decisions with evidence
- Log all overrides with reasoning
- Mask PII in logs (names, MRNs hashed)
- Long-term storage (7 years per HIPAA)
- Real-time alerting for suspicious patterns

**Audit Log Schema**:
```json
{
  "audit_id": "uuid",
  "timestamp": "2026-08-08T10:30:00Z",
  "user_id": "coordinator-id",
  "action": "assessment_created|override_applied|data_accessed",
  "resource_type": "Patient|Assessment|Trial",
  "resource_id": "uuid",
  "data_accessed": ["demographics", "medications", "labs"],
  "result": "success|denied|error",
  "ip_address": "192.168.1.1"
}
```

---

## Database Schema (PostgreSQL)

### patients table
```sql
CREATE TABLE patients (
  patient_id UUID PRIMARY KEY,
  hospital_id UUID NOT NULL,
  mrn VARCHAR(50) UNIQUE,
  first_name VARCHAR(100),
  last_name VARCHAR(100),
  date_of_birth DATE,
  fhir_data JSONB NOT NULL,           -- Full FHIR Patient resource
  data_quality_score NUMERIC(3,2),    -- 0.00-1.00 completeness
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  last_accessed_at TIMESTAMP,
  
  INDEX idx_hospital_mrn (hospital_id, mrn),
  INDEX idx_created (created_at DESC),
  INDEX idx_fhir_gin (fhir_data)
);
```

### trials table
```sql
CREATE TABLE trials (
  trial_id UUID PRIMARY KEY,
  nct_number VARCHAR(20) UNIQUE,
  trial_name VARCHAR(255),
  protocol_version INTEGER,
  rules JSONB NOT NULL,              -- Array of Rule objects
  inclusion_rules JSONB,              -- Must ALL match
  exclusion_rules JSONB,              -- Must NONE match
  status VARCHAR(50),                 -- Active, Recruiting, Completed
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  published_at TIMESTAMP,
  
  INDEX idx_nct (nct_number),
  INDEX idx_status (status, created_at DESC)
);
```

### assessments table
```sql
CREATE TABLE assessments (
  assessment_id UUID PRIMARY KEY,
  patient_id UUID NOT NULL,
  trial_id UUID NOT NULL,
  hospital_id UUID NOT NULL,
  overall_status VARCHAR(50),         -- LIKELY_ELIGIBLE, LIKELY_INELIGIBLE, UNCLEAR
  ai_confidence NUMERIC(3,2),
  assessment_data JSONB NOT NULL,     -- Full rule evaluations
  coordinator_id UUID,
  review_status VARCHAR(50),          -- PENDING, APPROVED, OVERRIDDEN
  final_status VARCHAR(50),           -- After human review
  override_count INTEGER DEFAULT 0,
  created_at TIMESTAMP,
  reviewed_at TIMESTAMP,
  
  INDEX idx_patient_trial (patient_id, trial_id),
  INDEX idx_status (review_status, created_at DESC),
  INDEX idx_hospital (hospital_id, created_at DESC)
);
```

### rule_evaluations table
```sql
CREATE TABLE rule_evaluations (
  rule_eval_id UUID PRIMARY KEY,
  assessment_id UUID NOT NULL,
  rule_id VARCHAR(255),
  status VARCHAR(50),                 -- MATCHES, DOES_NOT_MATCH, UNCLEAR
  confidence NUMERIC(3,2),
  evidence JSONB,                     -- Array of evidence citations
  is_overridden BOOLEAN DEFAULT FALSE,
  override_reason TEXT,
  original_status VARCHAR(50),
  overridden_by_user_id UUID,
  overridden_at TIMESTAMP,
  created_at TIMESTAMP,
  
  INDEX idx_assessment_rules (assessment_id),
  INDEX idx_overridden (is_overridden, overridden_at DESC)
);
```

### audit_logs table
```sql
CREATE TABLE audit_logs (
  audit_id UUID PRIMARY KEY,
  timestamp TIMESTAMP NOT NULL,
  user_id UUID,
  hospital_id UUID,
  action VARCHAR(100),                -- Data access, assessment, override, etc
  resource_type VARCHAR(50),
  resource_id UUID,
  data_accessed TEXT[],
  result VARCHAR(50),                 -- success, denied, error
  ip_address INET,
  reason_code VARCHAR(100),
  message TEXT,
  
  INDEX idx_timestamp (timestamp DESC),
  INDEX idx_user_action (user_id, action),
  INDEX idx_hospital (hospital_id, timestamp DESC)
);
```

---

## Caching Strategy (Redis)

### Cache Keys and TTLs

| Key Pattern | Content | TTL | Invalidation |
|---|---|---|---|
| `session:{token_hash}` | User roles, permissions | 7 days | On logout, token refresh |
| `trial:{trial_id}:v{version}` | Full protocol with rules | 30 days | Publish to "trial_updates" |
| `patient:{patient_id}` | Processed patient model | 1 hour | On patient data update |
| `rule_eval:{patient_id}:{trial_id}` | Pre-computed rule results | 2 hours | On patient data change |
| `assessment:{assessment_id}` | Full assessment with results | 24 hours | On override, archive after |
| `rate_limit:{api_key}:{minute}` | Request count | 60 seconds | Auto-expire |

### Cache Performance Targets
- Session cache hit rate: > 95%
- Trial protocol hit rate: > 90%
- Patient data hit rate: > 85%
- Rule evaluation hit rate: > 70%

---

## Data Flow: Patient Eligibility Evaluation

### End-to-End Flow (200ms SLA target)

```
1. Authentication (10ms)
   - Validate JWT token
   - Extract user context
   - Check permissions

2. Validation (20ms)
   - FHIR schema validation
   - Data completeness check
   - Detect missing fields

3. Patient Storage (30ms)
   - Check if patient exists
   - Create or update record
   - Store FHIR in DB + cache

4. Protocol Retrieval (5ms)
   - Check Redis cache
   - Fallback: Query DB
   - Return rules array

5. Rule Evaluation (100ms - parallelized)
   - Evaluate each rule (5-20ms each)
   - 6-10 rules typically
   - Run in parallel, max 10 concurrent

6. Confidence Aggregation (5ms)
   - Calculate weighted average
   - Determine overall status
   - Compute data quality score

7. Assessment Storage (10ms)
   - Create Assessment record
   - Create RuleEvaluation records
   - Cache result

8. Audit Logging (10ms - async)
   - Log data access event
   - Store in PostgreSQL
   - Sync to Elasticsearch

Total: ~190ms (under 200ms target)
```

---

## Data Flow: Assessment Override

```
1. Coordinator Request (5ms)
   - Validate JWT + Coordinator role
   - Fetch Assessment from cache

2. Override Validation (10ms)
   - Verify assessment is PENDING
   - Check coordinator authority
   - Validate override rules exist

3. Apply Overrides (15ms)
   - Update each RuleEvaluation
   - Recalculate overall_status
   - Track override impact

4. Audit Logging - SYNCHRONOUS (10ms)
   - Log override immediately
   - Ensure capture even if crash
   - Store with reasoning

5. Assessment Update (10ms)
   - Update Assessment state
   - Set review_status = OVERRIDDEN
   - Invalidate cache

Total: ~50ms (under 150ms target)

Critical: Audit logging is synchronous (don't async this)
```

---

## Security Architecture

### Authentication Flow (OAuth 2.0)

```
1. Hospital initiates login
   → Redirect to Okta/Active Directory

2. User authenticates
   → Hospital auth provider verifies credentials

3. Authorization callback
   → Returns authorization code

4. Token exchange
   → CareMatch exchanges code for JWT + refresh token

5. API authentication
   → Every request includes: Authorization: Bearer <token>

6. Token validation
   → Verify signature, expiration, claims

7. Token refresh
   → Use refresh_token to get new access_token
```

### Role-Based Access Control (RBAC)

**Roles**:
- **Administrator**: Manage users, view audit logs, override assessments, manage protocols
- **Provider**: Create protocols, view assessments, manage caregivers
- **Coordinator**: Submit patients, view assessments, override with reasoning
- **Auditor**: Read-only access to audit logs
- **Patient Portal User** (future): View own data only

### Data Encryption

**In Transit**:
- TLS 1.3+ on ALL endpoints
- Perfect Forward Secrecy enabled
- HSTS headers: 2-year max-age

**At Rest**:
- PostgreSQL: AES-256 for patient FHIR data
- Redis: AES-256 for session tokens and sensitive cache
- Elasticsearch: At-rest encryption enabled
- Encryption keys: AWS KMS managed

**Field-Level**:
- Patient names: Encrypted with hospital-specific key
- MRN: Encrypted, indexed via hash
- Phone/Email: Encrypted
- PII never in logs or error messages

### Audit Logging

**What Gets Logged**:
- Data access: patient record, assessment viewed, caregiver data read
- Data modification: patient created/updated, assessment created, override applied
- Authentication: login, token issued, failed auth attempts
- System events: API calls, errors, alerts

**Retention**: 7 years per HIPAA (PostgreSQL hot, Elasticsearch warm, S3 Glacier cold)

**PII Protection**: Names masked, MRNs hashed, phone/email hashed, lab values by code only

---

## Scalability & Performance

### Kubernetes Cluster Design

**Nodes**:
- General purpose (API): t3.2xlarge, 5-20 replicas
- Compute optimized (Rules): c5.4xlarge, 3-15 replicas
- Memory optimized (Database): r5.2xlarge, 3-5 instances
- Storage optimized (Elasticsearch): i3en.2xlarge, 3-5 nodes

**Horizontal Scaling**:
- CPU > 70% → Scale up
- CPU < 30% (5min) → Scale down
- Max replicas per service: 10-25 depending on workload

### Database Optimization

**PostgreSQL**:
- Primary (write): Single instance, 32 CPU, 128GB RAM
- Read replicas: 2-3 instances, 16 CPU, 64GB RAM
- Connection pooling: pgBouncer, max 500 connections
- Sharding (Phase 2): By hospital_id if needed

**Indexes** (critical for SLA):
- `patients(hospital_id, mrn)` - Patient lookup
- `assessments(patient_id, trial_id)` - Assessment queries
- `assessments(review_status, created_at DESC)` - Coordinator workflow
- `audit_logs(hospital_id, timestamp DESC)` - Compliance queries
- JSONB indexes on `fhir_data`, `assessment_data` - Search queries

**Query Performance**:
- All queries < 100ms
- Connection pooling prevents exhaustion
- Replication lag < 1 second

### Cache Optimization

**Hit Rates**:
- Session tokens: > 95% (JWT cached locally, Redis backup)
- Trial protocols: > 90% (loaded on startup, invalidated on change)
- Patient data: > 85% (1-hour TTL, refreshed on access)
- Rule evaluations: > 70% (2-hour TTL, patient-trial pair)

**Memory Management**:
- Redis cluster: 64-128GB total
- Eviction policy: LRU when > 80% full
- Alerts: Page on-call if > 75% utilization

---

## Deployment Architecture (Kubernetes)

### Deployment Strategy: Canary Rollout

```
1. Deploy to 5% of traffic (1-2 pods)
   ↓ Monitor for 5 minutes
   ↓
2. If healthy: Scale to 50% traffic
   ↓ Monitor for 5 minutes
   ↓
3. If healthy: Scale to 100% traffic
   ↓
4. Monitor for 24 hours post-deployment
   ↓
5. If issues detected: Auto-rollback to previous version
```

**Auto-Rollback Triggers**:
- Error rate > 1% for 2 minutes
- P95 latency > 500ms for 3 minutes
- Health check failures > 30% of replicas

### Service Manifests

**Core API Deployment**:
- Replicas: 5 (auto-scale 5-20)
- Strategy: RollingUpdate (maxSurge: 2, maxUnavailable: 1)
- Resource limits: 4 CPU, 8GB memory
- Health checks: Liveness (30s delay, 10s interval), Readiness (10s delay, 5s interval)
- Anti-affinity: Spread across nodes

**FHIR Processor Deployment**:
- Replicas: 3 (auto-scale 3-10)
- Resource limits: 2 CPU, 4GB memory
- Dedicated node pool: Compute optimized

**Rules Engine Deployment**:
- Replicas: 5 (auto-scale 5-25)
- Resource limits: 8 CPU, 8GB memory
- Dedicated node pool: High CPU
- Parallelization: Max 10 concurrent rule evaluations

### CI/CD Pipeline (GitHub Actions)

```
1. BUILD (Tests + Security)
   - Unit tests (required > 80% coverage)
   - Integration tests
   - Code coverage report
   - Security scan (OWASP, npm audit)
   - Build Docker image
   - Push to ECR

2. STAGING
   - Deploy to staging cluster
   - Smoke tests (API availability)
   - Integration tests (database, services)
   - Performance tests (latency benchmarks)
   - Security tests (auth, authorization)
   - Approval gate

3. PRODUCTION (Canary)
   - Deploy to 5% traffic
   - Monitor health for 5 minutes
   - Scale to 50%, monitor 5 minutes
   - Scale to 100%
   - Monitor for 24 hours

4. ROLLBACK (if needed)
   - Automatic on error rate > 1%
   - Manual trigger by on-call engineer
   - Instant switch to previous version
```

---

## Monitoring & Observability

### Key Metrics (Prometheus)

**API Metrics**:
- `http_requests_total` - Request count by endpoint, method, status
- `http_request_duration_seconds` - Latency histogram (p50/p95/p99)
- `http_connections_active` - Current connections

**Business Metrics**:
- `assessments_created_total` - Total assessments
- `assessments_status` - By status (eligible/ineligible/unclear)
- `assessments_override_count` - Overrides applied
- `ai_confidence_distribution` - Confidence score histogram
- `coordinator_approval_rate` - % approved vs overridden

**System Health**:
- `process_cpu_seconds_total` - CPU usage
- `process_resident_memory_bytes` - Memory usage
- `go_goroutines` - Active threads

**Database**:
- `pg_connections_active` - Active connections
- `pg_query_duration_seconds` - Query latency
- `pg_replication_lag_seconds` - Replica lag

**Cache**:
- `redis_hits_total` - Cache hits
- `redis_misses_total` - Cache misses
- `redis_used_memory_bytes` - Memory consumption

### Critical Alerts

**CRITICAL (Page on-call)**:
- API service down (any instance)
- Error rate > 1% for 5 minutes
- P95 latency > 500ms for 10 minutes
- Database down
- Redis down
- Data breach detection (bulk access)
- Authentication failures > 10 in 5 minutes

**WARNING (Slack notification)**:
- CPU > 80% for 10 minutes
- Memory > 90% available for 10 minutes
- Cache hit rate < 70% for 30 minutes
- Slow queries > 100ms for 5 minutes
- Queue buildup > 1000 items
- Override rate > 20% on specific rule

### Grafana Dashboards

1. **System Health** - On-call overview (uptime, requests/sec, error rate, latency, disk)
2. **API Performance** - Endpoint latency, throughput, status codes, request sizes
3. **AI Assessment Quality** - Created assessments, status distribution, confidence scores, overrides
4. **Infrastructure** - CPU, memory, network, disk, pod restarts
5. **Compliance & Audit** - Audit events, data access, overrides, violations
6. **Database Health** - Query latency, connections, replication lag, table sizes

---

## Implementation Sequence

### Phase 1: Foundation (Weeks 1-2)
- FastAPI project setup with Python 3.11+, async support
- Docker build pipeline (Python slim image)
- PostgreSQL schema and migrations
- Authentication service (OAuth/JWT with Authlib)
- Health check endpoints (/health, /ready)

### Phase 2: Core API (Weeks 3-4)
- Patient CRUD endpoints
- Trial protocol management
- Assessment endpoints
- FHIR validation

### Phase 3: Rules Engine (Weeks 5-6)
- Rule evaluation logic (all 6 types)
- Confidence scoring
- Evidence citation
- Redis caching

### Phase 4: Security & Compliance (Weeks 7-8)
- RBAC implementation (all 4 roles)
- Audit logging
- Encryption at rest/transit
- Request signing

### Phase 5: Observability (Weeks 9-10)
- Prometheus instrumentation
- Grafana dashboards
- Alerting rules
- SLA monitoring

### Phase 6: Scaling & Deployment (Weeks 11-12)
- Kubernetes deployments
- Horizontal Pod Autoscaler
- CI/CD pipeline
- Canary deployments

### Phase 7: Testing & Hardening (Weeks 13-14)
- Integration tests
- Load testing (200ms SLA validation)
- Security testing
- Chaos engineering

### Phase 8: Production Release (Weeks 15-16)
- Security audit
- Documentation
- Runbooks
- Production deployment

---

## Critical Implementation Files

### Backend Structure
- `/app/main.py` - FastAPI app setup, middleware, startup/shutdown
- `/app/config.py` - Configuration management (Pydantic settings)
- `/app/middleware/auth.py` - JWT validation, RBAC, Authlib integration
- `/app/middleware/audit.py` - Audit logging middleware
- `/app/middleware/error.py` - Global error handling
- `/app/dependencies.py` - FastAPI dependency injection (auth, db)

### API Endpoints
- `/app/api/v1/patients.py` - Patient CRUD endpoints
- `/app/api/v1/assessments.py` - Assessment management endpoints
- `/app/api/v1/trials.py` - Trial protocol endpoints
- `/app/api/v1/caregivers.py` - Caregiver management endpoints
- `/app/api/v1/health.py` - Health check endpoints

### Core Services
- `/app/services/eligibility.py` - Eligibility evaluation orchestration
- `/app/services/rules_engine.py` - Rule evaluation logic
- `/app/services/fhir_processor.py` - FHIR validation and processing
- `/app/services/audit_logger.py` - Compliance logging
- `/app/services/cache.py` - Redis cache management
- `/app/services/oauth.py` - OAuth 2.0 authentication flow

### Database
- `/app/db/models.py` - SQLAlchemy ORM models (Patient, Assessment, Trial, etc)
- `/app/db/migrations/` - Alembic migrations (001_initial_schema, 002_indexes, etc)
- `/app/db/repositories.py` - Repository pattern for data access
- `/app/db/database.py` - PostgreSQL connection, session management, pooling
- `/alembic/` - Alembic configuration for schema management

### Deployment
- `/Dockerfile` - Multi-stage build
- `/kubernetes/api-deployment.yaml` - Core API
- `/kubernetes/rules-engine-deployment.yaml` - Rules engine
- `/kubernetes/ingress.yaml` - API Gateway
- `/.github/workflows/ci-cd.yml` - CI/CD pipeline

---

## Success Criteria

- ✅ **Performance**: < 200ms p95 latency for patient evaluation
- ✅ **Reliability**: 99.9% uptime with < 15 minute recovery time
- ✅ **Scalability**: Support 5000+ concurrent sessions
- ✅ **Security**: Full OAuth/RBAC, AES-256 encryption, audit logging
- ✅ **Compliance**: HIPAA-ready with 7-year audit trail
- ✅ **Code Quality**: > 80% test coverage, TypeScript type safety
- ✅ **Deployment**: < 10 minute canary rollout, instant auto-rollback

---

**Version**: 1.0.0 | **Approved**: 2026-08-08 | **Next Review**: 2026-11-08
