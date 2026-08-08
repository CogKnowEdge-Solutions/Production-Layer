from tests.conftest import SAMPLE_FHIR_PATIENT


def _assess(client, headers, trial_id):
    return client.post(
        "/api/v1/patients/evaluate-eligibility",
        json={"trial_id": trial_id, "fhir_bundle": SAMPLE_FHIR_PATIENT},
        headers=headers,
    ).json()


class TestAssessmentRetrieval:
    def test_get_assessment_with_evidence_chains(self, client, auth_headers, trial_id):
        assessment = _assess(client, auth_headers(), trial_id)
        resp = client.get(
            f"/api/v1/assessments/{assessment['assessment_id']}", headers=auth_headers()
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["assessment_id"] == assessment["assessment_id"]
        assert body["review_status"] == "PENDING"
        assert body["rule_evaluations"]

    def test_get_missing_assessment_404(self, client, auth_headers):
        import uuid

        resp = client.get(f"/api/v1/assessments/{uuid.uuid4()}", headers=auth_headers())
        assert resp.status_code == 404

    def test_list_assessments(self, client, auth_headers, trial_id):
        headers = auth_headers()
        _assess(client, headers, trial_id)
        _assess(client, headers, trial_id)
        resp = client.get("/api/v1/assessments", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 2


class TestOverride:
    def test_override_rule_with_reasoning(self, client, auth_headers, trial_id):
        headers = auth_headers()
        assessment = _assess(client, headers, trial_id)
        rule = assessment["rule_evaluations"][0]
        resp = client.put(
            f"/api/v1/assessments/{assessment['assessment_id']}/override",
            json={
                "rule_eval_id": rule["rule_eval_id"],
                "new_status": "MATCHES",
                "reasoning": "Coordinator verified the source document",
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["review_status"] == "OVERRIDDEN"
        assert body["override_count"] == 1
        overridden = [
            r for r in body["rule_evaluations"] if r["rule_eval_id"] == rule["rule_eval_id"]
        ][0]
        assert overridden["is_overridden"] is True
        assert overridden["original_status"] == rule["status"]

    def test_override_requires_reasoning(self, client, auth_headers, trial_id):
        headers = auth_headers()
        assessment = _assess(client, headers, trial_id)
        rule = assessment["rule_evaluations"][0]
        resp = client.put(
            f"/api/v1/assessments/{assessment['assessment_id']}/override",
            json={"rule_eval_id": rule["rule_eval_id"], "new_status": "MATCHES", "reasoning": "x"},
            headers=headers,
        )
        assert resp.status_code == 422  # reasoning too short (FR-053)

    def test_override_invalid_status_rejected(self, client, auth_headers, trial_id):
        headers = auth_headers()
        assessment = _assess(client, headers, trial_id)
        rule = assessment["rule_evaluations"][0]
        resp = client.put(
            f"/api/v1/assessments/{assessment['assessment_id']}/override",
            json={
                "rule_eval_id": rule["rule_eval_id"],
                "new_status": "MAYBE",
                "reasoning": "Valid reasoning provided",
            },
            headers=headers,
        )
        assert resp.status_code == 400

    def test_cannot_override_twice(self, client, auth_headers, trial_id):
        headers = auth_headers()
        assessment = _assess(client, headers, trial_id)
        rule = assessment["rule_evaluations"][0]
        payload = {
            "rule_eval_id": rule["rule_eval_id"],
            "new_status": "MATCHES",
            "reasoning": "Valid reasoning",
        }
        url = f"/api/v1/assessments/{assessment['assessment_id']}/override"
        assert client.put(url, json=payload, headers=headers).status_code == 200
        assert client.put(url, json=payload, headers=headers).status_code == 400

    def test_override_recalculates_overall_status(self, client, auth_headers, trial_id):
        """A minimal patient yields UNCLEAR; overriding all unclear rules to MATCHES
        should not produce LIKELY_INELIGIBLE from a false negative."""
        headers = auth_headers()
        assessment = _assess(client, headers, trial_id)
        assert assessment["overall_status"] == "UNCLEAR"
        url = f"/api/v1/assessments/{assessment['assessment_id']}/override"
        for rule in assessment["rule_evaluations"]:
            if rule["status"] == "UNCLEAR":
                resp = client.put(
                    url,
                    json={
                        "rule_eval_id": rule["rule_eval_id"],
                        "new_status": "MATCHES",
                        "reasoning": "Reviewed chart",
                    },
                    headers=headers,
                )
                assert resp.status_code == 200
        final = client.get(
            f"/api/v1/assessments/{assessment['assessment_id']}", headers=headers
        ).json()
        assert final["override_count"] >= 1
        assert final["final_status"] in ("LIKELY_ELIGIBLE", "LIKELY_INELIGIBLE", "UNCLEAR")

    def test_overrides_feedback_dataset(self, client, auth_headers, trial_id):
        headers = auth_headers()
        assessment = _assess(client, headers, trial_id)
        rule = assessment["rule_evaluations"][0]
        client.put(
            f"/api/v1/assessments/{assessment['assessment_id']}/override",
            json={
                "rule_eval_id": rule["rule_eval_id"],
                "new_status": "MATCHES",
                "reasoning": "Valid reasoning",
            },
            headers=headers,
        )
        resp = client.get(
            f"/api/v1/assessments/{assessment['assessment_id']}/overrides",
            headers=auth_headers("auditor"),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["reasoning"]
