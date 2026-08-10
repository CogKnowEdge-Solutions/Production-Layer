from tests.conftest import SAMPLE_FHIR_PATIENT


def _create_assessment(client, headers, trial_id):
    return client.post(
        "/api/v1/patients/evaluate-eligibility",
        json={"trial_id": trial_id, "fhir_bundle": SAMPLE_FHIR_PATIENT},
        headers=headers,
    ).json()


class TestCaregiverEndpoints:
    def test_create_caregiver(self, client, auth_headers, trial_id):
        headers = auth_headers()
        patient_id = _create_assessment(client, headers, trial_id)["patient_id"]
        resp = client.post(
            "/api/v1/caregivers",
            json={"patient_id": patient_id, "relationship_type": "PRIMARY", "name": "Mary Smith"},
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["relationship_type"] == "PRIMARY"

    def test_invalid_relationship_rejected(self, client, auth_headers, trial_id):
        headers = auth_headers()
        patient_id = _create_assessment(client, headers, trial_id)["patient_id"]
        resp = client.post(
            "/api/v1/caregivers",
            json={"patient_id": patient_id, "relationship_type": "UNCLE"},
            headers=headers,
        )
        assert resp.status_code == 400

    def test_list_caregivers_for_patient(self, client, auth_headers, trial_id):
        headers = auth_headers()
        patient_id = _create_assessment(client, headers, trial_id)["patient_id"]
        client.post(
            "/api/v1/caregivers",
            json={"patient_id": patient_id, "relationship_type": "PRIMARY", "name": "Mary Smith"},
            headers=headers,
        )
        resp = client.get(f"/api/v1/patients/{patient_id}/caregivers", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["name"] == "Mary Smith"

    def test_list_caregivers_missing_patient_404(self, client, auth_headers):
        import uuid

        resp = client.get(f"/api/v1/patients/{uuid.uuid4()}/caregivers", headers=auth_headers())
        assert resp.status_code == 404

    def test_provider_cannot_register_caregiver_for_unknown_patient(self, client, auth_headers):
        import uuid

        resp = client.post(
            "/api/v1/caregivers",
            json={"patient_id": str(uuid.uuid4()), "relationship_type": "PRIMARY"},
            headers=auth_headers("provider"),
        )
        assert resp.status_code == 404

    def test_coordinator_cannot_create_caregiver(self, client, auth_headers, trial_id):
        headers = auth_headers("coordinator")
        patient_id = _create_assessment(client, headers, trial_id)["patient_id"]
        resp = client.post(
            "/api/v1/caregivers",
            json={"patient_id": patient_id, "relationship_type": "PRIMARY"},
            headers=headers,
        )
        assert resp.status_code == 403
