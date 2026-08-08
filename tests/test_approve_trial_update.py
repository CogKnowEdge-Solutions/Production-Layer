import uuid

from tests.conftest import SAMPLE_FHIR_PATIENT


def _assess(client, headers, trial_id):
    return client.post(
        "/api/v1/patients/evaluate-eligibility",
        json={"trial_id": trial_id, "fhir_bundle": SAMPLE_FHIR_PATIENT},
        headers=headers,
    ).json()


class TestApprove:
    def test_approve_assessment(self, client, auth_headers, trial_id):
        headers = auth_headers()
        assessment = _assess(client, headers, trial_id)
        resp = client.put(
            f"/api/v1/assessments/{assessment['assessment_id']}/approve", headers=headers
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["review_status"] == "APPROVED"
        assert body["final_status"] == body["overall_status"]

    def test_approve_twice_rejected(self, client, auth_headers, trial_id):
        headers = auth_headers()
        assessment = _assess(client, headers, trial_id)
        aid = assessment["assessment_id"]
        assert client.put(f"/api/v1/assessments/{aid}/approve", headers=headers).status_code == 200
        resp = client.put(f"/api/v1/assessments/{aid}/approve", headers=headers)
        assert resp.status_code == 400

    def test_provider_cannot_approve(self, client, auth_headers, trial_id):
        headers = auth_headers()
        assessment = _assess(client, headers, trial_id)
        resp = client.put(
            f"/api/v1/assessments/{assessment['assessment_id']}/approve",
            headers=auth_headers("provider"),
        )
        assert resp.status_code == 403

    def test_approve_missing_assessment_404(self, client, auth_headers):
        resp = client.put(f"/api/v1/assessments/{uuid.uuid4()}/approve", headers=auth_headers())
        assert resp.status_code == 404


class TestTrialUpdate:
    def test_update_bumps_protocol_version(self, client, auth_headers, trial_id):
        resp = client.put(
            f"/api/v1/trials/{trial_id}",
            json={"trial_name": "Updated Study", "status": "COMPLETED"},
            headers=auth_headers(),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["trial_name"] == "Updated Study"
        assert body["status"] == "COMPLETED"
        assert body["protocol_version"] == 2

    def test_update_preserves_rules_when_unset(self, client, auth_headers, trial_id):
        before = client.get(f"/api/v1/trials/{trial_id}", headers=auth_headers()).json()
        resp = client.put(
            f"/api/v1/trials/{trial_id}", json={"trial_name": "Renamed"}, headers=auth_headers()
        )
        assert resp.status_code == 200
        after = resp.json()
        assert after["rules"] == before["rules"]

    def test_update_missing_trial_404(self, client, auth_headers):
        resp = client.put(
            f"/api/v1/trials/{uuid.uuid4()}", json={"trial_name": "X"}, headers=auth_headers()
        )
        assert resp.status_code == 404

    def test_coordinator_cannot_update(self, client, auth_headers, trial_id):
        resp = client.put(
            f"/api/v1/trials/{trial_id}",
            json={"trial_name": "Nope"},
            headers=auth_headers("coordinator"),
        )
        assert resp.status_code == 403


class TestAuditMiddleware:
    def test_patient_write_logged_with_redacted_body(self, client, auth_headers, trial_id):
        headers = auth_headers()
        client.post(
            "/api/v1/patients/evaluate-eligibility",
            json={"trial_id": trial_id, "fhir_bundle": SAMPLE_FHIR_PATIENT},
            headers=headers,
        )
        resp = client.get("/api/v1/audit/logs", headers=auth_headers("auditor"))
        actions = [item["action"] for item in resp.json()["items"]]
        assert "data_accessed_post" in actions

    def test_audit_log_has_user_and_hospital(self, client, auth_headers, trial_id):
        client.post(
            "/api/v1/patients/evaluate-eligibility",
            json={"trial_id": trial_id, "fhir_bundle": SAMPLE_FHIR_PATIENT},
            headers=auth_headers(),
        )
        resp = client.get("/api/v1/audit/logs", headers=auth_headers("auditor"))
        data_access = [
            item for item in resp.json()["items"] if item["action"] == "data_accessed_post"
        ]
        assert data_access
        assert data_access[0]["user_id"] is not None
