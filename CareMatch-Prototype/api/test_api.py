"""
Tests the API's HTTP layer: routing, validation, trial registration/lookup,
and error handling. The real LLM call is replaced with a deterministic mock
via unittest.mock.patch -- patching llm_client.call_llm from the test
file, never inside main.py -- so these tests cost nothing, make zero network
calls, and prove the plumbing works. Reasoning quality is proven separately
against the real model, not in these tests.

Also: since the API persists to Postgres, tests run against a throwaway
test database (never the real one), and one test proves the data really
landed by re-reading it over a brand-new psycopg2 connection -- the
storage-layer half of the "survives a hard kill" proof.

Unlike the old SQLite temp file, a Postgres test target cannot be
conjured on demand: point TEST_DATABASE_URL at a disposable database.
The default matches the local throwaway container:

    docker run -d --name carematch-test-pg \\
        -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=carematch_test \\
        -p 55432:5432 postgres:16-alpine
"""

import os
import re
from unittest import mock

import psycopg2
import pytest

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:55432/carematch_test"
)

# This suite DROPS the whole public schema. Pointing it at a Supabase
# project would destroy real data, and the SQLite version's "it's just a
# temp file" safety net no longer exists -- so refuse outright.
if "supabase.co" in TEST_DATABASE_URL or "supabase.com" in TEST_DATABASE_URL:
    raise RuntimeError(
        "TEST_DATABASE_URL points at a Supabase host. These tests drop and "
        "recreate the public schema and would destroy real data. Point it at "
        "a disposable local Postgres instead."
    )

os.environ["DATABASE_URL"] = TEST_DATABASE_URL

# Clean slate before main.py imports and calls db.init_db(), so every run
# starts from an empty schema regardless of what the previous run left.
_bootstrap = psycopg2.connect(TEST_DATABASE_URL)
_bootstrap.autocommit = True
with _bootstrap.cursor() as _cur:
    _cur.execute("DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;")
_bootstrap.close()

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402

client = TestClient(app)

MOCKED_LLM_RESPONSE = {"status": "unclear", "evidence": "mocked for testing"}


@pytest.fixture(autouse=True)
def _mock_real_llm():
    """Stand in for llm_client.call_llm across the whole test file.
    main.py contains zero knowledge of this substitution -- it always calls
    llm_client.call_llm, and the tests simply point that module
    attribute at a deterministic fake, so no test ever makes a real paid
    API call."""
    with mock.patch("llm_client.call_llm", return_value=MOCKED_LLM_RESPONSE):
        yield


def test_list_trials_returns_all_registered_trials():
    client.post(
        "/trials",
        json={
            "trial_id": "T-LIST-A",
            "trial_name": "List Test A",
            "rules": [{"rule_id": "INC-01", "rule_text": "test", "category": "inclusion"}],
        },
    )
    client.post(
        "/trials",
        json={
            "trial_id": "T-LIST-B",
            "trial_name": "List Test B",
            "rules": [{"rule_id": "INC-01", "rule_text": "test", "category": "inclusion"}],
        },
    )
    r = client.get("/trials")
    assert r.status_code == 200
    trial_ids = [t["trial_id"] for t in r.json()]
    assert "T-LIST-A" in trial_ids
    assert "T-LIST-B" in trial_ids


def test_assess_records_which_provider_and_model_were_used():
    """Harness traceability: every assessment must record exactly which
    model produced it, resolved from the real provider config -- not left
    implicit or guessable."""
    client.post(
        "/trials",
        json={
            "trial_id": "T-TRACE-TEST",
            "trial_name": "Traceability Test",
            "rules": [{"rule_id": "INC-01", "rule_text": "test rule", "category": "inclusion"}],
        },
    )
    with mock.patch.dict(
        os.environ,
        {"ANTHROPIC_MODEL": "claude-test-model"},
    ):
        r = client.post(
            "/assess",
            json={"trial_id": "T-TRACE-TEST", "patient_id": "P-1", "patient_record": "record"},
        )
    data = r.json()
    assert data["provider_used"] == "anthropic"
    assert data["model_used"] == "claude-test-model"


def test_metrics_endpoint_exposes_carematch_specific_metrics():
    """Phase 4, done properly this time: metrics live in the real API,
    not a separate toy service. Prove our custom metrics actually appear,
    not just the generic auto-instrumented HTTP ones."""
    client.post(
        "/trials",
        json={
            "trial_id": "T-METRICS-TEST",
            "trial_name": "Metrics Test",
            "rules": [{"rule_id": "INC-01", "rule_text": "test rule", "category": "inclusion"}],
        },
    )
    assess_resp = client.post(
        "/assess",
        json={"trial_id": "T-METRICS-TEST", "patient_id": "P-1", "patient_record": "record"},
    )
    assessment_id = assess_resp.json()["assessment_id"]
    client.post(f"/assessments/{assessment_id}/decision", json={"decision": "accepted"})

    metrics_text = client.get("/metrics").text
    assert "trials_registered_total" in metrics_text
    assert "assessments_total" in metrics_text
    assert "reasoning_duration_seconds" in metrics_text
    assert "coordinator_decisions_total" in metrics_text
    # Confirm the label values we expect actually show up, not just the metric names
    assert 'suggested_status="needs_more_info"' in metrics_text  # mocked LLM always returns unclear
    assert 'decision="accepted"' in metrics_text


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_register_and_fetch_trial():
    r = client.post(
        "/trials",
        json={
            "trial_id": "T-TEST-01",
            "trial_name": "Test Trial",
            "rules": [
                {"rule_id": "INC-01", "rule_text": "Patient must be 18 or older", "category": "inclusion"}
            ],
        },
    )
    assert r.status_code == 201
    assert r.json()["trial_id"] == "T-TEST-01"

    r2 = client.get("/trials/T-TEST-01")
    assert r2.status_code == 200
    assert r2.json()["trial_name"] == "Test Trial"


def test_get_unknown_trial_returns_404():
    r = client.get("/trials/DOES-NOT-EXIST")
    assert r.status_code == 404


def test_assess_unknown_trial_returns_404():
    r = client.post(
        "/assess",
        json={"trial_id": "DOES-NOT-EXIST", "patient_id": "P-1", "patient_record": "some record"},
    )
    assert r.status_code == 404


def test_assess_with_mocked_llm_returns_correct_schema():
    client.post(
        "/trials",
        json={
            "trial_id": "T-ASSESS-TEST",
            "trial_name": "Assess Test Trial",
            "rules": [
                {"rule_id": "INC-01", "rule_text": "Patient must be 18 or older", "category": "inclusion"},
                {"rule_id": "EXC-01", "rule_text": "Patient is taking Warfarin", "category": "exclusion"},
            ],
        },
    )
    r = client.post(
        "/assess",
        json={"trial_id": "T-ASSESS-TEST", "patient_id": "P-1", "patient_record": "some fake record"},
    )
    assert r.status_code == 201
    data = r.json()

    # /assess now returns an AssessmentRecord wrapping the AssessmentResult
    assert "assessment_id" in data
    assert data["decision"] is None  # never pre-decided, ever
    assessment = data["assessment"]

    # Mocked LLM always says "unclear" -> aggregation must produce needs_more_info
    assert assessment["suggested_status"] == "needs_more_info"
    assert assessment["requires_coordinator_approval"] is True
    assert len(assessment["rule_results"]) == 2

    # Phase 0 rule enforced end-to-end, through the actual HTTP layer this time
    assert "confidence" not in assessment
    for rule_result in assessment["rule_results"]:
        assert "confidence" not in rule_result


def test_list_assessments_returns_lightweight_summary_of_every_assessment():
    """The History endpoint: every assessment appears exactly once, with
    the summary fields, no rule_results detail, newest first. Includes a
    mix of decisions -- accepted, denied, needs_more_review -- plus one
    left undecided (decision must be None, not a crash or a phantom)."""
    client.post(
        "/trials",
        json={
            "trial_id": "T-HISTORY-TEST",
            "trial_name": "History Test Trial",
            "rules": [{"rule_id": "INC-01", "rule_text": "test rule", "category": "inclusion"}],
        },
    )

    # Four assessments: three with a decision, one deliberately undecided.
    created_ids = []
    for patient_id in ("P-HIST-1", "P-HIST-2", "P-HIST-3", "P-HIST-4"):
        create_resp = client.post(
            "/assess",
            json={"trial_id": "T-HISTORY-TEST", "patient_id": patient_id, "patient_record": "record"},
        )
        assert create_resp.status_code == 201
        created_ids.append(create_resp.json()["assessment_id"])

    # Decisions: accepted, denied, needs_more_review. The 4th stays undecided.
    decisions = [
        ("accepted", "Clean case, accepted"),
        ("denied", "Record contradicts inclusion criterion"),
        ("needs_more_review", "Awaiting pathology report"),
    ]
    for assessment_id, (decision, reason) in zip(created_ids, decisions):
        decision_resp = client.post(
            f"/assessments/{assessment_id}/decision",
            json={"decision": decision, "reason": reason},
        )
        assert decision_resp.status_code == 200

    r = client.get("/assessments")
    assert r.status_code == 200
    rows = r.json()

    # Exactly our 4 show up (plus anything earlier tests created -- the
    # key assertions below are membership + correct fields per id).
    by_id = {row["assessment_id"]: row for row in rows}
    for assessment_id in created_ids:
        assert assessment_id in by_id

    # Summary shape: no rule_results, but all the header fields present.
    row = by_id[created_ids[0]]
    assert set(row.keys()) == {
        "assessment_id",
        "trial_id",
        "patient_id",
        "suggested_status",
        "decision",
        "decision_reason",
        "created_at",
    }
    assert row["trial_id"] == "T-HISTORY-TEST"
    assert row["suggested_status"] == "needs_more_info"  # mocked LLM always returns unclear
    assert isinstance(row["created_at"], str) and row["created_at"]

    # Decision values come through correctly per assessment.
    assert by_id[created_ids[0]]["decision"] == "accepted"
    assert by_id[created_ids[0]]["decision_reason"] == "Clean case, accepted"
    assert by_id[created_ids[1]]["decision"] == "denied"
    assert by_id[created_ids[2]]["decision"] == "needs_more_review"
    assert by_id[created_ids[3]]["decision"] is None  # undecided
    assert by_id[created_ids[3]]["decision_reason"] is None

    # Newest first: created_at is second-granularity, so rows may share a
    # timestamp -- the sequence must still never increase over time.
    created_times = [row["created_at"] for row in rows]
    assert created_times == sorted(created_times, reverse=True)


def test_get_assessment_by_id():
    client.post(
        "/trials",
        json={
            "trial_id": "T-GET-TEST",
            "trial_name": "Get Test Trial",
            "rules": [{"rule_id": "INC-01", "rule_text": "test rule", "category": "inclusion"}],
        },
    )
    create_resp = client.post(
        "/assess",
        json={"trial_id": "T-GET-TEST", "patient_id": "P-1", "patient_record": "record"},
    )
    assessment_id = create_resp.json()["assessment_id"]

    r = client.get(f"/assessments/{assessment_id}")
    assert r.status_code == 200
    assert r.json()["assessment_id"] == assessment_id


def test_get_unknown_assessment_returns_404():
    r = client.get("/assessments/does-not-exist")
    assert r.status_code == 404


def test_recording_a_decision_updates_the_assessment():
    client.post(
        "/trials",
        json={
            "trial_id": "T-DECISION-TEST",
            "trial_name": "Decision Test Trial",
            "rules": [{"rule_id": "INC-01", "rule_text": "test rule", "category": "inclusion"}],
        },
    )
    create_resp = client.post(
        "/assess",
        json={"trial_id": "T-DECISION-TEST", "patient_id": "P-1", "patient_record": "record"},
    )
    assessment_id = create_resp.json()["assessment_id"]
    assert create_resp.json()["decision"] is None  # confirm it starts undecided

    decision_resp = client.post(
        f"/assessments/{assessment_id}/decision",
        json={"decision": "denied", "reason": "Coordinator saw additional labs not in the record"},
    )
    assert decision_resp.status_code == 200
    data = decision_resp.json()
    assert data["decision"] == "denied"
    assert data["decision_reason"] == "Coordinator saw additional labs not in the record"

    # Confirm it actually persisted, not just echoed back in the response
    fetch_resp = client.get(f"/assessments/{assessment_id}")
    assert fetch_resp.json()["decision"] == "denied"


def test_needs_more_review_can_be_changed_to_a_final_decision():
    """'Needs More Review' is a temporary flag, not a dead end. Recording it
    first, then coming back later to finalize as 'accepted' or 'denied',
    must work -- the second decision wins (set_decision overwrites via
    ON CONFLICT DO UPDATE)."""
    client.post(
        "/trials",
        json={
            "trial_id": "T-NMR-TEST",
            "trial_name": "Needs More Review Test Trial",
            "rules": [{"rule_id": "INC-01", "rule_text": "test rule", "category": "inclusion"}],
        },
    )
    create_resp = client.post(
        "/assess",
        json={"trial_id": "T-NMR-TEST", "patient_id": "P-1", "patient_record": "record"},
    )
    assessment_id = create_resp.json()["assessment_id"]

    # Step 1: flag for further review (optional reason)
    first = client.post(
        f"/assessments/{assessment_id}/decision",
        json={"decision": "needs_more_review", "reason": "Awaiting latest pathology report"},
    )
    assert first.status_code == 200
    assert first.json()["decision"] == "needs_more_review"
    assert first.json()["decision_reason"] == "Awaiting latest pathology report"

    # Step 2: confirm it persisted and is still reviewable, not final
    mid = client.get(f"/assessments/{assessment_id}")
    assert mid.json()["decision"] == "needs_more_review"

    # Step 3: coordinator returns later and finalizes as "accepted"
    final = client.post(
        f"/assessments/{assessment_id}/decision",
        json={"decision": "accepted"},
    )
    assert final.status_code == 200
    assert final.json()["decision"] == "accepted"

    # The second decision wins, and the stale note is replaced
    fetch = client.get(f"/assessments/{assessment_id}")
    assert fetch.json()["decision"] == "accepted"
    assert fetch.json()["decision_reason"] is None

    # And the same assessment can equally be finalized as "denied" instead
    denied = client.post(
        f"/assessments/{assessment_id}/decision",
        json={"decision": "denied", "reason": "Record contradicts inclusion criterion"},
    )
    assert denied.status_code == 200
    assert denied.json()["decision"] == "denied"
    assert denied.json()["decision_reason"] == "Record contradicts inclusion criterion"
    assert client.get(f"/assessments/{assessment_id}").json()["decision"] == "denied"


def test_legacy_decision_values_still_load_without_crashing():
    """Decisions written before the 3-option redesign used "approved" /
    "overridden". They are NOT migrated (plain TEXT in Postgres too), but
    they must still load and display through the API without a validation
    crash."""
    import db

    client.post(
        "/trials",
        json={
            "trial_id": "T-LEGACY-TEST",
            "trial_name": "Legacy Decision Trial",
            "rules": [{"rule_id": "INC-01", "rule_text": "test rule", "category": "inclusion"}],
        },
    )
    create_resp = client.post(
        "/assess",
        json={"trial_id": "T-LEGACY-TEST", "patient_id": "P-1", "patient_record": "record"},
    )
    assessment_id = create_resp.json()["assessment_id"]

    # Simulate data written by the old system, straight into the DB.
    conn = psycopg2.connect(db.DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO decisions (assessment_id, decision, decision_reason) VALUES (%s, %s, %s)",
                (assessment_id, "approved", "Legacy approval"),
            )
        conn.commit()
    finally:
        conn.close()

    r = client.get(f"/assessments/{assessment_id}")
    assert r.status_code == 200  # must NOT 500
    assert r.json()["decision"] == "approved"
    assert r.json()["decision_reason"] == "Legacy approval"


def test_recording_decision_on_unknown_assessment_returns_404():
    r = client.post(
        "/assessments/does-not-exist/decision",
        json={"decision": "accepted"},
    )
    assert r.status_code == 404


def test_invalid_rule_category_is_rejected():
    r = client.post(
        "/trials",
        json={
            "trial_id": "T-BAD",
            "trial_name": "Bad Trial",
            "rules": [{"rule_id": "INC-01", "rule_text": "test", "category": "not_a_real_category"}],
        },
    )
    assert r.status_code == 422  # FastAPI/pydantic request validation error


def test_invalid_rule_id_format_is_rejected_at_registration():
    """The INC-##/EXC-## format rule from Phase 0 is enforced on Rule itself
    (see reasoning_engine/protocol.py), so a bad rule_id is caught immediately
    at trial registration -- not deferred to a confusing failure later
    during assessment."""
    r = client.post(
        "/trials",
        json={
            "trial_id": "T-BAD-ID",
            "trial_name": "Bad Rule Id Trial",
            "rules": [{"rule_id": "RULE-1", "rule_text": "test", "category": "inclusion"}],
        },
    )
    assert r.status_code == 422


def test_data_persists_across_a_fresh_database_connection():
    """The storage-layer half of the persistence proof: everything the API
    wrote must be readable back through a brand-new psycopg2 connection,
    opened outside db.py's pool -- exactly what a freshly-started process
    would do. This exercises the full join across trials -> rules ->
    assessments -> rule_results -> decisions, not just one table in
    isolation."""
    import db

    client.post(
        "/trials",
        json={
            "trial_id": "T-PERSIST-1",
            "trial_name": "Persistent Trial",
            "rules": [
                {"rule_id": "INC-01", "rule_text": "Patient must be 50 or older", "category": "inclusion"},
                {"rule_id": "EXC-01", "rule_text": "Patient is taking Warfarin", "category": "exclusion"},
            ],
        },
    )
    assess_resp = client.post(
        "/assess",
        json={"trial_id": "T-PERSIST-1", "patient_id": "P-1", "patient_record": "some record"},
    )
    assessment_id = assess_resp.json()["assessment_id"]
    client.post(f"/assessments/{assessment_id}/decision", json={"decision": "accepted"})

    # New connection to the SAME database, opened directly rather than
    # through db.py's pool -- no reference to anything main.py or the
    # TestClient still holds in memory.
    conn = psycopg2.connect(db.DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT trial_id, trial_name FROM trials WHERE trial_id='T-PERSIST-1'")
            trial = cur.fetchone()
            assert trial is not None
            assert trial[1] == "Persistent Trial"

            cur.execute("SELECT rule_id FROM rules WHERE trial_id='T-PERSIST-1'")
            assert {r[0] for r in cur.fetchall()} == {"INC-01", "EXC-01"}

            cur.execute(
                "SELECT assessment_id, trial_id, patient_id FROM assessments WHERE assessment_id=%s",
                (assessment_id,),
            )
            assessment = cur.fetchone()
            assert assessment is not None
            assert assessment[1] == "T-PERSIST-1"
            assert assessment[2] == "P-1"

            cur.execute(
                "SELECT rule_id, status FROM rule_results WHERE assessment_id=%s",
                (assessment_id,),
            )
            rule_results = cur.fetchall()
            assert len(rule_results) == 2
            assert {rr[0] for rr in rule_results} == {"INC-01", "EXC-01"}

            cur.execute(
                "SELECT decision FROM decisions WHERE assessment_id=%s", (assessment_id,)
            )
            decision = cur.fetchone()
            assert decision is not None
            assert decision[0] == "accepted"
    finally:
        conn.close()


def test_assess_with_ssn_in_record_is_rejected_422_without_leaking():
    """An INPUT guardrail firing must come back as a clean 422 (well-formed
    request, rejected CONTENT), never a 500 -- and the error response must
    never echo the matched PII back to the caller."""
    client.post(
        "/trials",
        json={
            "trial_id": "T-GUARD-1",
            "trial_name": "Guardrail Trial",
            "rules": [{"rule_id": "INC-01", "rule_text": "test rule", "category": "inclusion"}],
        },
    )
    fake_ssn = "123-45-6789"
    r = client.post(
        "/assess",
        json={
            "trial_id": "T-GUARD-1",
            "patient_id": "P-1",
            "patient_record": f"Insurance card on file lists SSN {fake_ssn}.",
        },
    )
    assert r.status_code == 422  # NOT 500
    assert "possible ssn" in r.json()["detail"].lower()
    assert fake_ssn not in r.text  # the error response must not leak the value

    # The input_pii_rejected_total counter must actually fire, not just exist.
    metrics_text = client.get("/metrics").text
    assert re.search(r"input_pii_rejected_total(_total)?\s+1\.0", metrics_text)


def test_hallucinated_evidence_is_overridden_to_unclear_and_counted():
    """OUTPUT guardrail end to end through the API: when the LLM quotes
    evidence that is NOT in the patient record, the saved assessment must
    come out as "unclear" with the honest message -- and the
    hallucinated_evidence_caught_total counter must increment."""
    client.post(
        "/trials",
        json={
            "trial_id": "T-HALL-1",
            "trial_name": "Hallucination Trial",
            "rules": [{"rule_id": "INC-01", "rule_text": "test rule", "category": "inclusion"}],
        },
    )

    def hallucinating_llm(rule_text, patient_record, category):
        return {"status": "matches", "evidence": "this quote is not in the record"}

    with mock.patch("llm_client.call_llm", side_effect=hallucinating_llm):
        r = client.post(
            "/assess",
            json={
                "trial_id": "T-HALL-1",
                "patient_id": "P-1",
                "patient_record": "Patient has hypertension.",
            },
        )
    assert r.status_code == 201
    rule_result = r.json()["assessment"]["rule_results"][0]
    assert rule_result["status"] == "unclear"  # status forced to unclear
    assert "could not be verified" in rule_result["evidence"]

    # The hallucinated_evidence_caught_total counter must actually fire.
    metrics_text = client.get("/metrics").text
    assert re.search(r"hallucinated_evidence_caught_total(_total)?\s+1\.0", metrics_text)