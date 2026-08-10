"""CareMatch — Streamlit frontend.

Talks to the CareMatch API (default http://localhost:8000) and, optionally, the
AI agent team (default http://localhost:8100). Override with the API_URL and
AGENT_URL environment variables.

Run:  streamlit run frontend/app.py
"""

import json
import os

import httpx
import pandas as pd
import streamlit as st


def api_url() -> str:
    return os.environ.get("API_URL", "http://localhost:8000").rstrip("/")


def agent_url() -> str:
    return os.environ.get("AGENT_URL", "http://localhost:8100").rstrip("/")


SEED_CREDENTIALS = {
    "admin": "admin-password-change-me",
    "coordinator": "coordinator-password-change-me",
    "provider": "provider-password-change-me",
    "auditor": "auditor-password-change-me",
}

SAMPLE_FHIR_BUNDLE = {
    "resourceType": "Bundle",
    "type": "collection",
    "entry": [
        {
            "resource": {
                "resourceType": "Patient",
                "id": "p-200",
                "identifier": [{"system": "http://hospital/mrn", "value": "M-2000"}],
                "name": [{"family": "Smith", "given": ["John"]}],
                "birthDate": "1975-01-10",
                "gender": "male",
            }
        },
        {
            "resource": {
                "resourceType": "Condition",
                "code": {
                    "text": "Diabetes",
                    "coding": [{"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": "E11.9"}],
                },
                "clinicalStatus": {"coding": [{"code": "active"}]},
            }
        },
        {
            "resource": {
                "resourceType": "MedicationRequest",
                "status": "active",
                "medicationCodeableConcept": {
                    "text": "Warfarin",
                    "coding": [
                        {"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "11289"}
                    ],
                },
            }
        },
    ],
}

SAMPLE_PROTOCOL = """Inclusion criteria:
- Patient must be at least 18 years old
- Patient has diabetes
- Patient is not taking "Warfarin"
"""

st.set_page_config(page_title="CareMatch", page_icon="🧬", layout="wide")


def api_client() -> httpx.Client:
    headers = {"Content-Type": "application/json"}
    token = st.session_state.get("token")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.Client(base_url=api_url(), headers=headers, timeout=120.0)


def call(method: str, path: str, **kwargs):
    try:
        resp = api_client().request(method, path, **kwargs)
    except httpx.HTTPError as exc:
        st.error(f"API unreachable at {api_url()}: {exc}")
        st.stop()
    try:
        payload = resp.json()
    except Exception:
        payload = {"detail": resp.text[:500]}
    if resp.status_code >= 400:
        raise RuntimeError(f"HTTP {resp.status_code}: {payload.get('detail', payload)}")
    return payload


def login(username: str, password: str) -> dict:
    return call(
        "POST",
        "/api/v1/auth/token",
        json={"username": username, "password": password, "grant_type": "password"},
    )


def agent_metrics() -> dict:
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{agent_url()}/agent/metrics")
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Auth sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("🧬 CareMatch")
    st.caption("Clinical trial eligibility screening")

    username = st.text_input("Username", value="admin")
    password = st.text_input("Password", value="admin-password-change-me", type="password")
    col1, col2 = st.columns(2)
    if col1.button("Login", use_container_width=True):
        try:
            data = login(username, password)
            st.session_state["token"] = data["access_token"]
            st.session_state["username"] = username
            st.success(f"Logged in as {username}")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if col2.button("Logout", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    if st.session_state.get("token"):
        st.info(f"Authenticated as **{st.session_state.get('username')}**")

    st.divider()
    st.caption("Seed accounts (dev)")
    for role, pwd in SEED_CREDENTIALS.items():
        st.write(f"`{role}` / `{pwd}`")

if not st.session_state.get("token"):
    st.info("Log in with one of the seed accounts on the left to continue.")
    st.stop()

# ---------------------------------------------------------------------------
# Top metrics: AI agent time saved
# ---------------------------------------------------------------------------
_metrics = agent_metrics()
if _metrics.get("runs"):
    st.subheader("AI Agent Impact")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "Time saved",
        f"{_metrics['saved_minutes']:.0f} min",
        delta=None,
        help="Estimated time the agent team saved vs. doing the same tasks manually.",
    )
    c2.metric("Agent runs", _metrics.get("runs", 0))
    c3.metric(
        "Actions automated",
        sum(_metrics.get("actions", {}).values()),
        help="Total tool actions executed by the agent team.",
    )
    c4.metric(
        "Manual effort equivalent",
        f"{_metrics.get('manual_minutes', 0):.0f} min",
        help="Estimated minutes a human would have spent on these tasks.",
    )
    st.divider()
elif not _metrics:
    st.caption("🤖 AI agent team not running — agent metrics unavailable.")

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_trials, tab_eval, tab_review, tab_caregivers, tab_audit, tab_agent = st.tabs(
    ["📋 Trials", "🧪 Evaluate", "✅ Review", "👥 Caregivers", "🕵️ Audit", "🤖 Agent"]
)

# ============================ TRIALS ========================================
with tab_trials:
    st.subheader("Clinical Trials")

    with st.form("create_trial_form", clear_on_submit=True):
        st.markdown("**Create a trial** (protocol as bullet-point lines so it parses into rules)")
        trial_name = st.text_input("Trial name", value="")
        protocol_text = st.text_area("Protocol text", value=SAMPLE_PROTOCOL, height=150)
        submitted = st.form_submit_button("Create trial")
        if submitted and trial_name.strip():
            try:
                created = call(
                    "POST",
                    "/api/v1/trials/create",
                    json={"trial_name": trial_name.strip(), "protocol_text": protocol_text},
                )
                st.success(
                    f"Created **{created['trial_name']}** — "
                    f"{len(created.get('rules') or [])} rules parsed."
                )
                st.session_state["selected_trial"] = str(created["trial_id"])
            except Exception as exc:
                st.error(str(exc))

    trials = call("GET", "/api/v1/trials", params={"offset": 0, "limit": 50}).get("items", [])
    if trials:
        st.markdown(f"**{len(trials)} trial(s)**")
        names = {f"{t['trial_name']} ({t['status']})": str(t["trial_id"]) for t in trials}
        chosen = st.selectbox("Select trial to inspect", list(names.keys()))
        st.session_state["selected_trial"] = names[chosen]
        trial = call("GET", f"/api/v1/trials/{names[chosen]}")
        st.json(trial)
    else:
        st.info("No trials yet — create one above.")

# ============================ EVALUATE =====================================
with tab_eval:
    st.subheader("Evaluate Eligibility")
    trials = call("GET", "/api/v1/trials", params={"offset": 0, "limit": 50}).get("items", [])
    if not trials:
        st.warning("Create a trial first.")
    else:
        options = {f"{t['trial_name']} ({t['status']})": str(t["trial_id"]) for t in trials}
        selected = st.selectbox("Trial", list(options.keys()), key="eval_trial")
        fhir_text = st.text_area(
            "FHIR R4 bundle (JSON)",
            value=json.dumps(SAMPLE_FHIR_BUNDLE, indent=2),
            height=280,
        )
        if st.button("Evaluate", type="primary"):
            try:
                fhir = json.loads(fhir_text)
            except json.JSONDecodeError as exc:
                st.error(f"Invalid JSON: {exc}")
            else:
                try:
                    result = call(
                        "POST",
                        "/api/v1/patients/evaluate-eligibility",
                        json={"trial_id": options[selected], "fhir_bundle": fhir},
                    )
                    st.session_state["last_assessment_id"] = str(result["assessment_id"])
                    st.session_state["last_assessment"] = result
                except Exception as exc:
                    st.error(str(exc))

        if st.session_state.get("last_assessment"):
            _a = st.session_state["last_assessment"]
            st.markdown(
                f"### Overall: **{_a['overall_status']}** · confidence "
                f"{_a['ai_confidence']:.0%} · review **{_a['review_status']}**"
            )
            rows = []
            for r in _a.get("rule_evaluations", []):
                rows.append(
                    {
                        "rule": r["rule_id"],
                        "type": r["type"],
                        "category": r["category"],
                        "status": r["status"],
                        "confidence": round(r["confidence"], 2),
                        "overridden": r.get("is_overridden", False),
                        "evidence": len(r.get("evidence", [])),
                    }
                )
            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True)

# ============================ REVIEW =======================================
with tab_review:
    st.subheader("Review & Approve Assessments")
    assessments = call("GET", "/api/v1/assessments", params={"offset": 0, "limit": 50}).get(
        "items", []
    )
    if not assessments:
        st.info("No assessments yet — evaluate a patient first.")
    else:
        labels = {
            f"{a['overall_status']} · {a['review_status']} · {a['assessment_id'][:8]}": str(
                a["assessment_id"]
            )
            for a in assessments
        }
        chosen = st.selectbox("Assessment", list(labels.keys()))
        aid = labels[chosen]
        assessment = call("GET", f"/api/v1/assessments/{aid}")

        st.markdown(
            f"**Overall:** {assessment['overall_status']} · "
            f"**Review:** {assessment['review_status']} · "
            f"**Final:** {assessment.get('final_status') or '—'} · "
            f"**Overrides:** {assessment.get('override_count', 0)}"
        )

        for r in assessment.get("rule_evaluations", []):
            with st.expander(
                f"{r['rule_id']} · {r['type']} · {r['status']}"
                + (" (OVERRIDDEN)" if r.get("is_overridden") else "")
            ):
                st.markdown(f"**Description:** {r.get('description')}")
                st.markdown(f"**Confidence:** {r['confidence']:.0%}")
                for ev in r.get("evidence", []):
                    st.markdown(f"- {ev.get('source')}: {ev.get('detail')}")
                if r.get("is_overridden"):
                    st.warning(f"Override reason: {r.get('override_reason')}")

        col_ap, col_ov = st.columns(2)
        if col_ap.button("Approve assessment", type="primary", use_container_width=True):
            try:
                approved = call("PUT", f"/api/v1/assessments/{aid}/approve")
                st.success(
                    f"Approved → review **{approved['review_status']}**, "
                    f"final **{approved.get('final_status')}**"
                )
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

        with col_ov.form("override_form"):
            rule_options = {
                f"{r['rule_id']} · {r['type']}": str(r["rule_eval_id"])
                for r in assessment.get("rule_evaluations", [])
            }
            rule_choice = st.selectbox("Rule to override", list(rule_options.keys()))
            new_status = st.selectbox("New status", ["MATCHES", "DOES_NOT_MATCH", "UNCLEAR"])
            reasoning = st.text_area("Reasoning (required)")
            if st.form_submit_button("Apply override"):
                try:
                    result = call(
                        "PUT",
                        f"/api/v1/assessments/{aid}/override",
                        json={
                            "rule_eval_id": rule_options[rule_choice],
                            "new_status": new_status,
                            "reasoning": reasoning,
                        },
                    )
                    st.success(f"Override applied — review **{result['review_status']}**")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

# ============================ CAREGIVERS ===================================
with tab_caregivers:
    st.subheader("Caregivers")
    patient_id = st.text_input("Patient ID (for listing)", value="")
    if st.button("List caregivers"):
        try:
            caregivers = call("GET", f"/api/v1/patients/{patient_id}/caregivers")
            items = caregivers if isinstance(caregivers, list) else caregivers.get("items", [])
            if items:
                st.dataframe(pd.DataFrame(items), use_container_width=True)
            else:
                st.info("No caregivers for this patient.")
        except Exception as exc:
            st.error(str(exc))

    with st.form("create_caregiver_form"):
        st.markdown("**Register a caregiver**")
        cg_patient = st.text_input("Patient ID", value="")
        cg_relationship = st.selectbox(
            "Relationship",
            ["PRIMARY", "EMERGENCY_CONTACT", "LEGAL_PROXY", "POWER_OF_ATTORNEY"],
        )
        cg_name = st.text_input("Name", value="")
        cg_phone = st.text_input("Phone", value="")
        cg_email = st.text_input("Email", value="")
        cg_dob = st.date_input("Date of birth", value=None)
        if st.form_submit_button("Register caregiver"):
            try:
                created = call(
                    "POST",
                    "/api/v1/caregivers",
                    json={
                        "patient_id": cg_patient,
                        "relationship_type": cg_relationship,
                        "name": cg_name,
                        "phone": cg_phone,
                        "email": cg_email,
                        "date_of_birth": cg_dob.isoformat() if cg_dob else None,
                    },
                )
                st.success(f"Registered {created.get('name')}")
            except Exception as exc:
                st.error(str(exc))

# ============================ AUDIT ========================================
with tab_audit:
    st.subheader("Audit Log")
    if st.button("Fetch audit log"):
        try:
            logs = call("GET", "/api/v1/audit/logs", params={"offset": 0, "limit": 50})
            items = logs.get("items", [])
            if items:
                st.dataframe(pd.DataFrame(items), use_container_width=True)
            else:
                st.info("No audit events.")
        except Exception as exc:
            st.error(str(exc))

    if st.button("Fetch metrics"):
        try:
            metrics = call("GET", "/api/v1/metrics")
            st.text(metrics if isinstance(metrics, str) else json.dumps(metrics, indent=2))
        except Exception as exc:
            st.error(str(exc))

# ============================ AGENT ========================================
with tab_agent:
    st.subheader("AI Agent Team")
    st.caption(f"Coordinator + specialist subagents via {agent_url()}")
    message = st.text_area(
        "Ask the agent team (e.g. create a trial, evaluate a patient, review assessments)",
        value="Log in, list the trials, and summarize them.",
        height=100,
    )
    if st.button("Send to agent", type="primary"):
        try:
            with httpx.Client(timeout=300.0) as client:
                resp = client.post(
                    f"{agent_url()}/agent/chat",
                    json={
                        "message": message,
                        "username": st.session_state.get("username", "admin"),
                        "password": password,
                    },
                )
            resp.raise_for_status()
            st.markdown(resp.json().get("response", "(empty response)"))
        except Exception as exc:
            st.error(f"Agent error: {exc}")

st.caption(
    f"API: {api_url()} · Agent: {agent_url()} · "
    "Overrides require reasoning; the AI recommendation is never final without coordinator review."
)
