"""
Tests the full pipeline WITHOUT calling a real LLM. We inject a fake
`call_llm` function that returns pre-written answers, matching what a
real model would plausibly say for each of our three test patients.

This proves the plumbing works: prompt-building, schema validation,
rule_id enforcement, and aggregation logic. It does NOT prove the LLM
itself reasons well -- that's what run_real_assessment.py is for, once
you add your own API key.

NOTE: the EXC-01 rule text and its fake answers below were corrected
after real-model testing revealed that negated ("must not...") exclusion
rules confused the model into answering "does_not_match" almost
regardless of the actual facts. See protocol.py for the full explanation.
"""

import pytest

from engine import assess_patient
from schema import AssessmentResult
from test_data.fixtures import (
    DIABETES_TRIAL,
    PATIENT_CLEARLY_ELIGIBLE,
    PATIENT_CLEARLY_EXCLUDED,
    PATIENT_MISSING_INFO,
)

# Canned answers per rule_text, keyed by patient, simulating what a real
# LLM would plausibly return after actually reading each fake record above.
FAKE_ANSWERS = {
    "P-1001": {
        "Patient must be 50 years of age or older": {
            "status": "matches",
            "evidence": "Date of Birth: 1968-03-11 (age 57)",
        },
        "Patient must have a diagnosis of Type 2 Diabetes": {
            "status": "matches",
            "evidence": "Diagnoses: Type 2 Diabetes Mellitus, diagnosed 2019",
        },
        "Patient is currently taking Warfarin": {
            "status": "does_not_match",  # they do NOT have this disqualifying condition -- good
            "evidence": "Current Medications: Metformin 500mg twice daily (no Warfarin listed)",
        },
    },
    "P-1002": {
        "Patient must be 50 years of age or older": {
            "status": "matches",
            "evidence": "Date of Birth: 1975-06-20 (age 51)",
        },
        "Patient must have a diagnosis of Type 2 Diabetes": {
            "status": "matches",
            "evidence": "Diagnoses: Type 2 Diabetes Mellitus, diagnosed 2021",
        },
        "Patient is currently taking Warfarin": {
            "status": "matches",  # they DO have this disqualifying condition -- bad, triggers exclusion
            "evidence": "Current Medications: Warfarin 5mg daily, Metformin 500mg twice daily",
        },
    },
    "P-1003": {
        "Patient must be 50 years of age or older": {
            "status": "matches",
            "evidence": "Date of Birth: 1970-01-15 (age 55)",
        },
        "Patient must have a diagnosis of Type 2 Diabetes": {
            "status": "unclear",
            "evidence": "no relevant information found",
        },
        "Patient is currently taking Warfarin": {
            "status": "does_not_match",
            "evidence": "Current Medications: Lisinopril 10mg daily (no Warfarin listed)",
        },
    },
}


def make_fake_llm(patient_id: str):
    def fake_call_llm(rule_text: str, patient_record: str, category: str) -> dict:
        return FAKE_ANSWERS[patient_id][rule_text]

    return fake_call_llm


# ---- Tests ----


def test_clearly_eligible_patient_aggregates_correctly():
    fake_llm = make_fake_llm("P-1001")
    result = assess_patient(
        patient_id=PATIENT_CLEARLY_ELIGIBLE["patient_id"],
        patient_record=PATIENT_CLEARLY_ELIGIBLE["record"],
        protocol=DIABETES_TRIAL,
        call_llm=fake_llm,
    )
    assert isinstance(result, AssessmentResult)
    assert result.suggested_status == PATIENT_CLEARLY_ELIGIBLE["expected_status"]
    assert result.requires_coordinator_approval is True
    assert len(result.rule_results) == 3


def test_excluded_patient_aggregates_correctly():
    fake_llm = make_fake_llm("P-1002")
    result = assess_patient(
        patient_id=PATIENT_CLEARLY_EXCLUDED["patient_id"],
        patient_record=PATIENT_CLEARLY_EXCLUDED["record"],
        protocol=DIABETES_TRIAL,
        call_llm=fake_llm,
    )
    assert result.suggested_status == PATIENT_CLEARLY_EXCLUDED["expected_status"]
    # Under the corrected phrasing, an exclusion rule "matches" means the
    # disqualifying condition IS present -- that's what should trigger exclusion.
    exclusion_result = next(r for r in result.rule_results if r.rule_id == "EXC-01")
    assert exclusion_result.status == "matches"


def test_missing_info_patient_aggregates_correctly():
    fake_llm = make_fake_llm("P-1003")
    result = assess_patient(
        patient_id=PATIENT_MISSING_INFO["patient_id"],
        patient_record=PATIENT_MISSING_INFO["record"],
        protocol=DIABETES_TRIAL,
        call_llm=fake_llm,
    )
    assert result.suggested_status == PATIENT_MISSING_INFO["expected_status"]


def test_requires_coordinator_approval_cannot_be_false():
    """This should be structurally impossible, not just a convention."""
    with pytest.raises(Exception):
        AssessmentResult(
            patient_id="P-1",
            trial_id="T-1",
            suggested_status="likely_eligible",
            requires_coordinator_approval=False,  # must be rejected
            rule_results=[],
        )


def test_rule_id_format_is_enforced():
    from schema import RuleResult

    with pytest.raises(Exception):
        RuleResult(
            rule_id="RULE-1",  # wrong format, should be INC-## or EXC-##
            rule_text="some rule",
            status="matches",
            evidence="no relevant information found",
        )


def test_confidence_field_does_not_exist():
    """Phase 0 decision: no confidence field, anywhere. Prove it's not there."""
    result = assess_patient(
        patient_id=PATIENT_CLEARLY_ELIGIBLE["patient_id"],
        patient_record=PATIENT_CLEARLY_ELIGIBLE["record"],
        protocol=DIABETES_TRIAL,
        call_llm=make_fake_llm("P-1001"),
    )
    assert "confidence" not in result.model_dump()
    for rule_result in result.rule_results:
        assert "confidence" not in rule_result.model_dump()


# --- Harness hardening: malformed LLM output must never crash the engine ---


def test_missing_field_in_llm_response_falls_back_to_unclear():
    """The model forgot to include 'evidence' entirely -- a real thing
    models sometimes do. This must not crash the whole assessment."""

    def broken_llm(rule_text, patient_record, category):
        return {"status": "matches"}  # no "evidence" key at all

    result = assess_patient(
        patient_id="P-1001",
        patient_record=PATIENT_CLEARLY_ELIGIBLE["record"],
        protocol=DIABETES_TRIAL,
        call_llm=broken_llm,
    )
    assert result.suggested_status == "needs_more_info"  # unclear wins, as designed
    for rule_result in result.rule_results:
        assert rule_result.status == "unclear"
        assert "malformed" in rule_result.evidence.lower()


def test_invalid_status_value_falls_back_to_unclear():
    """The model returned a status value outside our three allowed
    options -- e.g. "yes" instead of "matches". Must not crash, and must
    NOT silently guess which of our three values was intended."""

    def broken_llm(rule_text, patient_record, category):
        return {"status": "yes", "evidence": "some evidence"}

    result = assess_patient(
        patient_id="P-1001",
        patient_record=PATIENT_CLEARLY_ELIGIBLE["record"],
        protocol=DIABETES_TRIAL,
        call_llm=broken_llm,
    )
    assert result.suggested_status == "needs_more_info"
    for rule_result in result.rule_results:
        assert rule_result.status == "unclear"


def test_completely_wrong_type_falls_back_to_unclear():
    """The model returned something structurally unexpected entirely
    (not even a dict with the right keys). Must not crash."""

    def broken_llm(rule_text, patient_record, category):
        return {"status": None, "evidence": 12345}  # wrong types entirely

    result = assess_patient(
        patient_id="P-1001",
        patient_record=PATIENT_CLEARLY_ELIGIBLE["record"],
        protocol=DIABETES_TRIAL,
        call_llm=broken_llm,
    )
    assert result.suggested_status == "needs_more_info"
    for rule_result in result.rule_results:
        assert rule_result.status == "unclear"


def test_one_malformed_rule_does_not_affect_other_valid_rules():
    """If only ONE rule's output is malformed, the other rules should
    still be evaluated normally -- one bad response shouldn't nuke
    everything else that worked fine."""

    def mixed_llm(rule_text, patient_record, category):
        if "50 years" in rule_text:
            return {"status": "not_a_real_status", "evidence": "broken"}  # malformed
        return {"status": "matches", "evidence": "this one is fine"}  # valid

    result = assess_patient(
        patient_id="P-1001",
        patient_record=PATIENT_CLEARLY_ELIGIBLE["record"],
        protocol=DIABETES_TRIAL,
        call_llm=mixed_llm,
    )
    statuses = {r.rule_id: r.status for r in result.rule_results}
    assert statuses["INC-01"] == "unclear"  # the malformed one, safely handled
    assert statuses["INC-02"] == "matches"  # the valid ones still work correctly
    assert statuses["EXC-01"] == "matches"