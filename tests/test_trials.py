from app.services.protocol_parser import parse_protocol_document, parse_structured_rules
from tests.conftest import SAMPLE_PROTOCOL


class TestTrialEndpoints:
    def test_create_trial_from_protocol_text(self, client, auth_headers):
        resp = client.post(
            "/api/v1/trials/create",
            json={"trial_name": "Test Study", "protocol_text": SAMPLE_PROTOCOL},
            headers=auth_headers(),
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["trial_name"] == "Test Study"
        assert body["protocol_version"] == 1
        types = {r["type"] for r in body["rules"]}
        assert "age_range" in types
        assert "diagnosis" in types
        assert "medication" in types

    def test_create_trial_with_structured_rules(self, client, auth_headers):
        resp = client.post(
            "/api/v1/trials/create",
            json={
                "trial_name": "Structured Study",
                "rules": [
                    {
                        "rule_id": "A1",
                        "type": "age_range",
                        "description": ">=18",
                        "criteria": {"min_age": 18},
                    }
                ],
            },
            headers=auth_headers(),
        )
        assert resp.status_code == 201
        assert len(resp.json()["rules"]) == 1

    def test_create_trial_with_both_text_and_rules_rejected(self, client, auth_headers):
        resp = client.post(
            "/api/v1/trials/create",
            json={"trial_name": "Bad", "protocol_text": "x", "rules": []},
            headers=auth_headers(),
        )
        assert resp.status_code == 400

    def test_get_trial(self, client, auth_headers, trial_id):
        resp = client.get(f"/api/v1/trials/{trial_id}", headers=auth_headers())
        assert resp.status_code == 200
        assert resp.json()["trial_id"] == trial_id

    def test_get_missing_trial_404(self, client, auth_headers):
        import uuid

        resp = client.get(f"/api/v1/trials/{uuid.uuid4()}", headers=auth_headers())
        assert resp.status_code == 404


class TestProtocolParser:
    def test_parses_sections_and_rules(self):
        rules, warnings = parse_protocol_document(SAMPLE_PROTOCOL)
        assert len(rules) == 3
        categories = [r["category"] for r in rules]
        assert categories.count("inclusion") == 2
        assert categories.count("exclusion") == 1

    def test_rule_ids_sequential(self):
        rules, _ = parse_protocol_document(SAMPLE_PROTOCOL)
        assert [r["rule_id"] for r in rules] == ["R-001", "R-002", "R-003"]

    def test_age_rule_extraction(self):
        rules, _ = parse_protocol_document("- Patient must be at least 18 years old")
        assert rules[0]["type"] == "age_range"
        assert rules[0]["criteria"]["min_age"] == 18

    def test_structured_passthrough_with_defaults(self):
        rules, warnings = parse_structured_rules(
            [{"type": "age_range", "description": "adult", "criteria": {"min_age": 18}}]
        )
        assert rules[0]["rule_id"] == "R-001"
        assert rules[0]["category"] == "inclusion"
