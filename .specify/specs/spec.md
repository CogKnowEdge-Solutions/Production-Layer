# Feature Specification: CareMatch API & Data Models

**Feature Branch**: `spec-api-endpoints`

**Created**: 2026-08-08

**Status**: Draft

**Input**: Extracted from CareMatch_API_Full_Guide_.pdf

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Patient Trial Eligibility Evaluation (Priority: P1)

Research coordinators screen patients for clinical trial eligibility using CareMatch's AI-powered analysis. Instead of manually reading through long medical files, the coordinator submits patient data and receives a detailed, evidence-backed report showing which trial rules the patient matches, doesn't match, or has unclear data for.

**Why this priority**: This is the core value proposition. If patients can't be quickly and accurately evaluated, the entire system fails.

**Independent Test**: Can be fully tested by: (1) submitting sample patient data via the API, (2) receiving structured eligibility report, (3) verifying evidence trails for each rule evaluation.

**Acceptance Scenarios**:

1. **Given** a patient's medical record (FHIR-formatted) and a trial protocol, **When** coordinator submits eligibility request, **Then** system returns report with status "likely eligible", "likely ineligible", or "needs more information"
2. **Given** system produces assessment, **When** report is delivered, **Then** each trial rule shows: status (matches/does-not-match/unclear), evidence citation, confidence level
3. **Given** coordinator reviews report, **When** they approve or override assessment, **Then** decision is logged with timestamp and reasoning

---

### User Story 2 - Provider Clinical Trial Integration (Priority: P1)

Healthcare providers and hospital systems integrate CareMatch into their existing workflows without requiring custom infrastructure changes. They send patient data through a standard FHIR-based API endpoint and receive structured reports that fit into their existing screening process.

**Why this priority**: Hospitals won't adopt if integration is expensive and complex. This is the "cheap and easy to plug in" promise.

**Independent Test**: Can be fully tested by: (1) hospital system sending FHIR-formatted request, (2) API accepting and processing request, (3) receiving valid response within SLA, (4) verifying HIPAA-compliant data handling.

**Acceptance Scenarios**:

1. **Given** hospital system has valid OAuth 2.0 credentials, **When** POST request sent to `/api/v1/patients/evaluate-eligibility`, **Then** system authenticates and processes request
2. **Given** request includes valid FHIR patient resource and trial protocol, **When** system processes, **Then** returns JSON response with structured evaluation results
3. **Given** data is patient health information, **When** processed, **Then** all data encrypted in transit (TLS 1.3+) and at rest (AES-256)

---

### User Story 3 - Trial Protocol Management & Standardization (Priority: P2)

Trial sponsors maintain standardized protocol rulebooks in the system. Different hospitals screening for the same trial use identical logic, ensuring consistency across sites while reducing manual protocol entry errors.

**Why this priority**: Without standardized protocols, each hospital would interpret rules differently, defeating the purpose of using CareMatch.

**Independent Test**: Can be fully tested by: (1) uploading trial protocol, (2) converting human-written rules to machine-readable format, (3) validating protocol syntax, (4) using same protocol across multiple patient evaluations.

**Acceptance Scenarios**:

1. **Given** trial sponsor provides protocol document, **When** submitted via `/api/v1/trials/create`, **Then** system parses and converts rules to structured format
2. **Given** protocol rules are stored, **When** multiple hospitals request evaluation with same trial, **Then** all receive identical rule-evaluation logic

---

### User Story 4 - Research Coordinator Caregiver Context (Priority: P2)

For patients with caregivers involved in care coordination, the system captures caregiver information and relationship context. This is relevant for trials requiring caregiver involvement or consent from care proxies.

**Why this priority**: Some clinical trials require caregiver participation or decision-making authority. This enables evaluation of that requirement.

**Independent Test**: Can be fully tested by: (1) submitting patient with associated caregiver record, (2) evaluating trial rules that reference caregiver qualifications, (3) generating report showing caregiver-related compliance status.

**Acceptance Scenarios**:

1. **Given** patient has designated caregiver, **When** caregiver data included in FHIR record, **Then** system evaluates caregiver-related trial rules separately
2. **Given** trial rule requires "approved caregiver present", **When** report generated, **Then** caregiver match status clearly indicated

---

### User Story 5 - AI Decision Override & Feedback Loop (Priority: P2)

When coordinators disagree with the AI's assessment, they can override specific rule evaluations. The system logs all overrides with reasoning, creating a feedback dataset that improves AI accuracy over time.

**Why this priority**: The human-in-the-loop design requires capturing and learning from human corrections.

**Independent Test**: Can be fully tested by: (1) coordinator viewing AI assessment, (2) overriding specific rule, (3) providing reasoning, (4) verifying override is logged and accessible for model retraining.

**Acceptance Scenarios**:

1. **Given** coordinator reviews AI assessment and disagrees, **When** they update rule status via `/api/v1/assessments/{id}/override`, **Then** override is logged with timestamp, user ID, and reasoning
2. **Given** override recorded, **When** system retrains, **Then** feedback is used to improve future assessments

---

## Requirements *(mandatory)*

### Functional Requirements

**Patient Data & Matching**:
- **FR-001**: System MUST accept patient data in FHIR R4 format (HL7 FHIR standard for healthcare interoperability)
- **FR-002**: System MUST support ingestion of: demographics, medical history, medications, allergies, vital signs, lab results, diagnoses, procedures
- **FR-003**: System MUST evaluate patient against each trial rule individually, producing one of three outcomes per rule: "matches", "does not match", or "unclear"
- **FR-004**: System MUST provide evidence citation for each rule evaluation — exact data point from patient record that supports the conclusion
- **FR-005**: System MUST generate overall eligibility status: "likely eligible", "likely ineligible", or "needs more information" based on aggregated rule results

**API Endpoints & Integration**:
- **FR-010**: System MUST expose RESTful API at `/api/v1/` with endpoints for: patient evaluation, trial protocol management, assessment retrieval, override logging
- **FR-011**: System MUST support healthcare provider system integration via FHIR-formatted requests/responses
- **FR-012**: System MUST return structured JSON responses with machine-readable status codes and human-readable explanations
- **FR-013**: System MUST support pagination for list endpoints (default 50 items, max 1000)
- **FR-014**: System MUST provide API versioning via URL path (e.g., `/api/v1/`, `/api/v2/`)

**Authentication & Authorization**:
- **FR-020**: System MUST enforce OAuth 2.0 or JWT-based authentication for all API endpoints
- **FR-021**: System MUST implement role-based access control (RBAC) with roles: Administrator, Provider, Coordinator, Auditor
- **FR-022**: System MUST require token expiration: 15 minutes for access tokens, 7 days for refresh tokens
- **FR-023**: System MUST log all data access with: timestamp, user ID, action performed, data accessed, result

**Trial Protocol Management**:
- **FR-030**: System MUST support creation and storage of trial protocols from human-readable documents
- **FR-031**: System MUST convert trial rules into machine-executable format with explicit criteria and thresholds
- **FR-032**: System MUST support rule types: age range, medication exclusion, diagnosis requirement, lab value thresholds, temporal constraints
- **FR-033**: System MUST provide protocol versioning and audit trail for protocol changes

**Caregiver Management**:
- **FR-040**: System MUST support caregiver relationship definitions: primary caregiver, emergency contact, legal proxy, power of attorney
- **FR-041**: System MUST include caregiver information in FHIR patient bundles
- **FR-042**: System MUST evaluate caregiver-related trial eligibility rules (e.g., "primary caregiver must be adult", "proxy consent required")
- **FR-043**: System MUST track caregiver contact information securely with audit logging

**Human-in-the-Loop Decision Making**:
- **FR-050**: System MUST NOT make final eligibility decisions; AI only produces "recommendation" with reasoning
- **FR-051**: System MUST require human coordinator to review, approve, or override AI assessment before eligibility is final
- **FR-052**: System MUST log all overrides with: original AI assessment, override decision, coordinator ID, timestamp, reasoning provided
- **FR-053**: System MUST prevent coordinators from approving an assessment without providing reasoning for any override

**Monitoring & Observability**:
- **FR-060**: System MUST track metrics: request throughput, response latency (p50/p95/p99), error rates, AI confidence levels
- **FR-061**: System MUST generate alerts when: response time > 500ms, error rate > 1%, AI confidence trending downward, coordinator override rate > 20%
- **FR-062**: System MUST expose metrics via Prometheus-compatible endpoint
- **FR-063**: System MUST provide real-time dashboard (Grafana) showing system health and AI performance

### Key Entities

**Patient**:
- Unique patient identifier (MRN, NHS number, or system-generated UUID)
- Demographics (name, DOB, gender, contact info)
- Medical history (diagnoses, procedures, hospitalizations)
- Medications (current, historical, with dates and dosages)
- Allergies (substance, severity, reaction type)
- Vital signs (recent measurements with timestamps)
- Lab results (test type, value, reference range, date)
- Insurance/coverage information
- Relationship to caregivers

**TrialProtocol**:
- Trial identifier (NCT number, internal trial ID)
- Protocol version and effective date
- Inclusion rules (must match for eligibility)
- Exclusion rules (must not match for eligibility)
- Rule definitions (type, criteria, threshold values)
- Rule priority/weighting
- Evidence requirements (what data needed to evaluate each rule)

**EligibilityAssessment**:
- Assessment ID (unique per patient-trial evaluation)
- Patient reference
- Trial reference
- Overall status (likely eligible / likely ineligible / needs more info)
- Rule evaluations (one per trial rule)
- Evidence citations (links to specific patient data supporting conclusion)
- AI confidence level per rule
- AI confidence level overall
- Generated timestamp
- Coordinator review status (pending / approved / overridden)

**RuleEvaluation**:
- Rule ID (reference to specific trial rule)
- Rule description
- Evaluation status (matches / does not match / unclear)
- Evidence citations (specific data points from patient record)
- Confidence level (AI's certainty in this evaluation)
- Data needed (if unclear, what information is missing)

**Caregiver**:
- Caregiver ID (unique identifier)
- Relationship to patient (primary, emergency contact, proxy, etc.)
- Name, contact information, address
- Qualifications/attributes (age, employment, specific requirements per trial)
- Authorization status (verified, pending, revoked)
- Consent status (for trials requiring caregiver consent)

**AssessmentOverride**:
- Override ID
- Assessment ID (which assessment was overridden)
- Rule ID (which specific rule was overridden)
- Original AI status
- New human status
- Reasoning provided by coordinator
- Coordinator ID and timestamp
- Impact on overall eligibility

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: API response time for patient evaluation must be < 200ms (95th percentile) under normal load
- **SC-002**: System must correctly assess patient eligibility in 95% of cases compared to experienced human coordinator (validated in Phase 5 testing)
- **SC-003**: Critical error rate (AI wrongly rejects eligible patient) must be < 2% — this is the single most dangerous mistake
- **SC-004**: 90% of coordinators report they trust the AI's reasoning and feel confident overriding it when needed
- **SC-005**: Average time to evaluate one patient must decrease by at least 60% compared to manual screening (from ~30 min to ~12 min)
- **SC-006**: System must maintain 99.9% uptime SLA in production with proper redundancy
- **SC-007**: 100% of AI decisions must be logged with full audit trail and evidence chain
- **SC-008**: Integration with hospital systems must be achievable in < 5 days of IT effort (vs. $250k-$500k and months for traditional AI platforms)

## Assumptions

- Hospital systems provide patient data in FHIR R4 format or system provides conversion layer
- Trial protocols can be digitized into structured rule formats by clinical staff with domain knowledge
- Internet connectivity between hospital and CareMatch system is reliable (99.9%+)
- Coordinators are available to review and approve/override AI assessments within reasonable timeframe
- Patient privacy laws (HIPAA in US, GDPR in EU) must be followed for all data handling
- System will be deployed on hospital infrastructure or cloud platform (AWS/Azure/GCP) under healthcare compliance
- Encryption and data residency requirements will be met per hospital's compliance policies
- Existing authentication systems (Active Directory, Okta, etc.) can integrate via OAuth 2.0
- Database will support ACID transactions and provide backup/disaster recovery
- Monitoring and logging infrastructure (Prometheus, Grafana, ELK) will be available
- No real patient data will be used in development/testing — only anonymized test data until Phase 5

---

## API Endpoint Specification

### Patient Evaluation Endpoints

**POST /api/v1/patients/evaluate-eligibility**
- Description: Submit patient data and trial protocol for eligibility assessment
- Authentication: Required (Bearer token)
- Request body: FHIR Patient resource + Trial protocol reference or inline rules
- Response: EligibilityAssessment with rule-by-rule evaluation
- Status codes: 200 (success), 201 (assessment created), 400 (invalid input), 401 (unauthorized), 422 (validation error)
- SLA: Response within 200ms p95

**GET /api/v1/assessments/{assessment_id}**
- Description: Retrieve previously created assessment
- Authentication: Required
- Response: Full EligibilityAssessment with evidence chains
- Status codes: 200 (success), 404 (not found), 401 (unauthorized)

**PUT /api/v1/assessments/{assessment_id}/override**
- Description: Coordinator overrides AI decision for specific rule or overall status
- Authentication: Required (Coordinator or Admin role)
- Request body: Rule ID, new status, reasoning
- Response: Updated assessment with override recorded
- Status codes: 200 (success), 400 (invalid override), 401 (unauthorized), 404 (not found)

### Trial Protocol Management

**POST /api/v1/trials/create**
- Description: Create new trial protocol from document or structured rules
- Authentication: Required (Admin or Provider role)
- Request body: Trial metadata + rules array
- Response: Trial ID, created timestamp, protocol version
- Status codes: 201 (created), 400 (invalid protocol), 401 (unauthorized)

**GET /api/v1/trials/{trial_id}**
- Description: Retrieve trial protocol details
- Authentication: Required
- Response: Full protocol with rules, metadata, version history
- Status codes: 200 (success), 404 (not found)

### Caregiver Management

**POST /api/v1/caregivers**
- Description: Register or update caregiver information
- Authentication: Required (Provider or Admin role)
- Request body: Caregiver details (name, relationship, qualifications)
- Response: Caregiver ID, verification status
- Status codes: 201 (created), 200 (updated), 400 (invalid), 401 (unauthorized)

**GET /api/v1/patients/{patient_id}/caregivers**
- Description: Retrieve caregivers associated with patient
- Authentication: Required
- Response: List of caregivers with relationship types and qualifications
- Status codes: 200 (success), 404 (patient not found)

---

## Data Security & Privacy Requirements

- All FHIR data encrypted with TLS 1.3+ in transit
- Patient data encrypted with AES-256 at rest
- PII never logged or exposed in error messages
- Database query results reviewed for data leakage before response
- All data access logged: timestamp, user, action, data accessed, result
- Audit logs retained for 7 years per healthcare compliance
- PHI masked in system logs, dashboards, error messages
- Data minimization: only collect/retain what's necessary for patient evaluation
- Implement HIPAA Business Associate Agreement (BAA) with hospital partners
- Right to deletion: Patients can request data removal (implemented within 30 days)
- Incident response plan for potential data breaches

---

**Version**: 1.0.0 | **Ratified**: 2026-08-08 | **Last Amended**: 2026-08-08
