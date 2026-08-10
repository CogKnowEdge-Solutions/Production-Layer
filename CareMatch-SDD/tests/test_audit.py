class TestAuditTrail:
    def test_auditor_can_list_logs(self, client, auth_headers):
        resp = client.get("/api/v1/audit/logs", headers=auth_headers("auditor"))
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert body["total"] >= 0

    def test_provider_forbidden_from_audit_logs(self, client, auth_headers):
        resp = client.get("/api/v1/audit/logs", headers=auth_headers("provider"))
        assert resp.status_code == 403

    def test_audit_trail_records_login(self, client, auth_headers):
        auth_headers("admin")
        resp = client.get("/api/v1/audit/logs", headers=auth_headers("auditor"))
        assert resp.status_code == 200
        actions = [item["action"] for item in resp.json()["items"]]
        assert "token_issued" in actions
