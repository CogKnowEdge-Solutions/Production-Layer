"""LangChain tools that wrap CareMatch API calls.

Each tool reads the auth token from the shared AgentSession, so once the auth
subagent logs in, every other tool can call authenticated endpoints.
"""

import json

from langchain_core.tools import tool

from agent.carematch_client import CareMatchClient
from agent.session import AgentSession

VALID_OVERRIDE_STATUSES = {"MATCHES", "DOES_NOT_MATCH", "UNCLEAR"}


def _json(value) -> str:
    return json.dumps(value, indent=2, default=str)


def build_tools(session: AgentSession) -> list:
    client = CareMatchClient(session.base_url)

    def _auth_headers() -> dict:
        if not session.token:
            raise RuntimeError(
                "Not authenticated. Ask the user for credentials and call login_to_carematch first."
            )
        return {"Authorization": f"Bearer {session.token}"}

    @tool("login_to_carematch")
    def login(username: str, password: str) -> str:
        """Authenticate with CareMatch using a username and password. Returns the access token.
        Run this BEFORE any other tool that needs authentication."""
        resp = client.login(username, password)
        session.token = resp["access_token"]
        session.notes.append(f"logged in as {username}")
        return f"Login successful. Token stored for this session. User: {username}"

    @tool("list_trials")
    def list_trials(limit: int = 50) -> str:
        """List clinical trials in CareMatch."""
        return _json(client.list_trials(session.token_or_raise(), limit=min(limit, 1000)))

    @tool("get_trial")
    def get_trial(trial_id: str) -> str:
        """Get full details of a trial by its trial_id, including its rules."""
        return _json(client.get_trial(session.token_or_raise(), trial_id))

    @tool("create_trial")
    def create_trial(trial_name: str, protocol_text: str = "") -> str:
        """Create a new clinical trial. protocol_text is a human-readable protocol document
        that CareMatch parses into structured eligibility rules."""
        if not trial_name:
            raise RuntimeError("trial_name is required")
        return _json(
            client.create_trial(
                session.token_or_raise(), trial_name=trial_name, protocol_text=protocol_text or None
            )
        )

    @tool("update_trial")
    def update_trial(
        trial_id: str, trial_name: str | None = None, status: str | None = None
    ) -> str:
        """Update a trial's name or status. Bumps the protocol version."""
        body = {
            k: v for k, v in {"trial_name": trial_name, "status": status}.items() if v is not None
        }
        return _json(client.update_trial(session.token_or_raise(), trial_id, **body))

    @tool("evaluate_eligibility")
    def evaluate_eligibility(trial_id: str, fhir_bundle_json: str) -> str:
        """Evaluate a patient's eligibility for a trial. fhir_bundle_json is a JSON string
        of a FHIR R4 Patient or Bundle resource (e.g. containing name, birthDate, gender,
        MedicationRequest, Condition, Observation resources)."""
        fhir_bundle = json.loads(fhir_bundle_json)
        return _json(client.evaluate(session.token_or_raise(), trial_id, fhir_bundle))

    @tool("list_assessments")
    def list_assessments(limit: int = 50) -> str:
        """List eligibility assessment recommendations."""
        return _json(client.list_assessments(session.token_or_raise(), limit=min(limit, 1000)))

    @tool("get_assessment")
    def get_assessment(assessment_id: str) -> str:
        """Get a single assessment with its per-rule evidence chain."""
        return _json(client.get_assessment(session.token_or_raise(), assessment_id))

    @tool("approve_assessment")
    def approve_assessment(assessment_id: str) -> str:
        """Approve an AI recommendation, finalizing eligibility."""
        return _json(client.approve_assessment(session.token_or_raise(), assessment_id))

    @tool("override_rule")
    def override_rule(
        assessment_id: str, rule_eval_id: str, new_status: str, reasoning: str
    ) -> str:
        """Override a single rule evaluation. new_status must be one of MATCHES, DOES_NOT_MATCH,
        UNCLEAR. reasoning is REQUIRED and must be at least 5 characters."""
        if new_status not in VALID_OVERRIDE_STATUSES:
            raise RuntimeError(f"new_status must be one of {sorted(VALID_OVERRIDE_STATUSES)}")
        if len(reasoning) < 5:
            raise RuntimeError("reasoning is required (min 5 characters) for any override")
        return _json(
            client.override_rule(
                session.token_or_raise(), assessment_id, rule_eval_id, new_status, reasoning
            )
        )

    @tool("list_caregivers_for_patient")
    def list_caregivers_for_patient(patient_id: str) -> str:
        """List caregivers associated with a patient."""
        return _json(client.list_caregivers(session.token_or_raise(), patient_id))

    @tool("create_caregiver")
    def create_caregiver(caregiver_json: str) -> str:
        """Register a caregiver. caregiver_json is JSON with patient_id, relationship_type
        (PRIMARY | EMERGENCY_CONTACT | LEGAL_PROXY | POWER_OF_ATTORNEY), name, phone, email,
        date_of_birth."""
        caregiver = json.loads(caregiver_json)
        return _json(client.create_caregiver(session.token_or_raise(), caregiver))

    @tool("list_audit_logs")
    def list_audit_logs(limit: int = 50) -> str:
        """List the audit trail (HIPAA compliance). Requires AUDITOR or ADMINISTRATOR role."""
        return _json(client.audit_logs(session.token_or_raise(), limit=min(limit, 1000)))

    @tool("get_metrics")
    def get_metrics() -> str:
        """Fetch CareMatch Prometheus metrics (throughput, latency, errors, AI confidence)."""
        return _json(client.metrics())

    return [
        login,
        list_trials,
        get_trial,
        create_trial,
        update_trial,
        evaluate_eligibility,
        list_assessments,
        get_assessment,
        approve_assessment,
        override_rule,
        list_caregivers_for_patient,
        create_caregiver,
        list_audit_logs,
        get_metrics,
    ]
