from tests.conftest import SAMPLE_FHIR_BUNDLE, SAMPLE_FHIR_PATIENT


class TestEligibilityContract:
    def test_evaluation_returns_rule_by_rule_report(self, client, auth_headers, trial_id):
        resp = client.post(
            "/api/v1/patients/evaluate-eligibility",
            json={"trial_id": trial_id, "fhir_bundle": SAMPLE_FHIR_PATIENT},
            headers=auth_headers(),
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["assessment_id"]
        assert body["overall_status"] in ("LIKELY_ELIGIBLE", "LIKELY_INELIGIBLE", "UNCLEAR")
        assert body["review_status"] == "PENDING"
        assert len(body["rule_evaluations"]) >= 1
        for rule in body["rule_evaluations"]:
            assert rule["status"] in ("MATCHES", "DOES_NOT_MATCH", "UNCLEAR")
            assert rule["rule_eval_id"]
            assert rule["confidence"] is not None

    def test_ineligible_patient_rejected_with_evidence(self, client, auth_headers, trial_id):
        resp = client.post(
            "/api/v1/patients/evaluate-eligibility",
            json={"trial_id": trial_id, "fhir_bundle": SAMPLE_FHIR_BUNDLE},
            headers=auth_headers(),
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["overall_status"] == "LIKELY_INELIGIBLE"
        medication_rules = [r for r in body["rule_evaluations"] if r["type"] == "medication"]
        assert medication_rules
        assert medication_rules[0]["status"] == "MATCHES"
        assert medication_rules[0]["evidence"]

    def test_missing_data_yields_unclear_not_guess(self, client, auth_headers, trial_id):
        """The single most important design rule: never guess eligibility."""
        resp = client.post(
            "/api/v1/patients/evaluate-eligibility",
            json={"trial_id": trial_id, "fhir_bundle": SAMPLE_FHIR_PATIENT},
            headers=auth_headers(),
        )
        body = resp.json()
        assert body["overall_status"] == "UNCLEAR"
        for rule in body["rule_evaluations"]:
            if rule["status"] == "UNCLEAR":
                assert rule["missing_data"], "UNCLEAR rules must explain what data is missing"

    def test_unknown_trial_returns_404(self, client, auth_headers):
        import uuid

        resp = client.post(
            "/api/v1/patients/evaluate-eligibility",
            json={"trial_id": str(uuid.uuid4()), "fhir_bundle": SAMPLE_FHIR_PATIENT},
            headers=auth_headers(),
        )
        assert resp.status_code == 404

    def test_invalid_fhir_returns_422(self, client, auth_headers, trial_id):
        resp = client.post(
            "/api/v1/patients/evaluate-eligibility",
            json={"trial_id": trial_id, "fhir_bundle": {"resourceType": "Observation"}},
            headers=auth_headers(),
        )
        assert resp.status_code == 422

    def test_requires_authentication(self, client, trial_id):
        resp = client.post(
            "/api/v1/patients/evaluate-eligibility",
            json={"trial_id": trial_id, "fhir_bundle": SAMPLE_FHIR_PATIENT},
        )
        assert resp.status_code == 401
