from tests.conftest import SAMPLE_FHIR_PATIENT, SEED_CREDENTIALS


class TestAuthContract:
    def test_token_issue(self, client):
        resp = client.post(
            "/api/v1/auth/token",
            json={"username": "admin", "password": SEED_CREDENTIALS["admin"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["access_token"]
        assert body["refresh_token"]
        assert body["token_type"] == "bearer"
        assert body["expires_in"] == 900

    def test_token_reject_invalid_credentials(self, client):
        resp = client.post(
            "/api/v1/auth/token", json={"username": "admin", "password": "wrong-password"}
        )
        assert resp.status_code == 401

    def test_refresh_flow(self, client):
        token = client.post(
            "/api/v1/auth/token",
            json={"username": "admin", "password": SEED_CREDENTIALS["admin"]},
        ).json()
        resp = client.post("/api/v1/auth/refresh", json={"refresh_token": token["refresh_token"]})
        assert resp.status_code == 200
        assert resp.json()["access_token"]

    def test_refresh_rejects_access_token(self, client):
        token = client.post(
            "/api/v1/auth/token",
            json={"username": "admin", "password": SEED_CREDENTIALS["admin"]},
        ).json()
        resp = client.post("/api/v1/auth/refresh", json={"refresh_token": token["access_token"]})
        assert resp.status_code == 401

    def test_me_endpoint(self, client, auth_headers):
        resp = client.get("/api/v1/auth/me", headers=auth_headers("admin"))
        assert resp.status_code == 200
        assert resp.json()["role"] == "ADMINISTRATOR"

    def test_me_rejects_missing_token(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401


class TestRBAC:
    def test_auditor_cannot_create_trial(self, client, auth_headers):
        resp = client.post(
            "/api/v1/trials/create",
            json={"trial_name": "Blocked", "rules": []},
            headers=auth_headers("auditor"),
        )
        assert resp.status_code in (403, 400)

    def test_coordinator_can_evaluate(self, client, auth_headers, trial_id):
        resp = client.post(
            "/api/v1/patients/evaluate-eligibility",
            json={"trial_id": trial_id, "fhir_bundle": SAMPLE_FHIR_PATIENT},
            headers=auth_headers("coordinator"),
        )
        assert resp.status_code == 201

    def test_auditor_can_read_overrides(self, client, auth_headers, trial_id):
        headers = auth_headers("coordinator")
        assessment = client.post(
            "/api/v1/patients/evaluate-eligibility",
            json={"trial_id": trial_id, "fhir_bundle": SAMPLE_FHIR_PATIENT},
            headers=headers,
        ).json()
        rule = assessment["rule_evaluations"][0]
        client.put(
            f"/api/v1/assessments/{assessment['assessment_id']}/override",
            json={
                "rule_eval_id": rule["rule_eval_id"],
                "new_status": "MATCHES",
                "reasoning": "Re-checked chart",
            },
            headers=headers,
        )
        resp = client.get(
            f"/api/v1/assessments/{assessment['assessment_id']}/overrides",
            headers=auth_headers("auditor"),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1
