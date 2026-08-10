from tests.conftest import SAMPLE_FHIR_BUNDLE


class TestProviderIntegration:
    """Full provider flow: FHIR request in -> structured JSON report out."""

    def test_end_to_end_fhir_to_report(self, client, auth_headers, trial_id):
        headers = auth_headers()
        resp = client.post(
            "/api/v1/patients/evaluate-eligibility",
            json={"trial_id": trial_id, "fhir_bundle": SAMPLE_FHIR_BUNDLE},
            headers=headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["patient_id"]
        assert body["trial_id"] == trial_id
        for rule in body["rule_evaluations"]:
            assert "evidence" in rule

    def test_versioned_api_path(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401  # path exists (auth enforced)

    def test_pagination_on_trials(self, client, auth_headers):
        headers = auth_headers()
        for i in range(5):
            client.post(
                "/api/v1/trials/create",
                json={
                    "trial_name": f"Trial {i}",
                    "rules": [
                        {
                            "rule_id": f"r{i}",
                            "type": "age_range",
                            "description": "adult",
                            "criteria": {"min_age": 18},
                        }
                    ],
                },
                headers=headers,
            )
        resp = client.get("/api/v1/trials", params={"limit": 3, "offset": 0}, headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 3
        assert resp.json()["total"] >= 5

    def test_pagination_limit_capped_at_1000(self, client, auth_headers):
        resp = client.get("/api/v1/trials", params={"limit": 5000}, headers=auth_headers())
        assert resp.status_code == 422  # max 1000 enforced by validation (FR-013)

    def test_metrics_endpoint(self, client):
        resp = client.get("/api/v1/metrics")
        assert resp.status_code == 200
        assert "http_requests_total" in resp.text
