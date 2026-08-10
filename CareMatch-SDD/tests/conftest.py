import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["ENV"] = "testing"
os.environ["JWT_SECRET"] = "test-secret-key-at-least-32-bytes-long!!"

import pytest
from fastapi.testclient import TestClient

SEED_CREDENTIALS = {
    "admin": "admin-password-change-me",
    "coordinator": "coordinator-password-change-me",
    "provider": "provider-password-change-me",
    "auditor": "auditor-password-change-me",
}

SAMPLE_PROTOCOL = """Inclusion criteria:
- Patient must be at least 18 years old
- Patient has diabetes

Exclusion criteria:
- Patient is taking "Warfarin"
"""

SAMPLE_FHIR_PATIENT = {
    "resourceType": "Patient",
    "id": "p-100",
    "identifier": [{"system": "http://hospital/mrn", "value": "M-1000"}],
    "name": [{"family": "Doe", "given": ["Jane"]}],
    "birthDate": "1980-05-15",
    "gender": "female",
}

SAMPLE_FHIR_BUNDLE = {
    "resourceType": "Bundle",
    "type": "collection",
    "entry": [
        {
            "resource": {
                "resourceType": "Patient",
                "id": "p-200",
                "identifier": [{"system": "http://hospital/mrn", "value": "M-2000"}],
                "name": [{"family": "Smith", "given": ["John"]}],
                "birthDate": "1975-01-10",
                "gender": "male",
            }
        },
        {
            "resource": {
                "resourceType": "Condition",
                "code": {
                    "text": "Diabetes",
                    "coding": [{"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": "E11.9"}],
                },
                "clinicalStatus": {"coding": [{"code": "active"}]},
            }
        },
        {
            "resource": {
                "resourceType": "MedicationRequest",
                "status": "active",
                "medicationCodeableConcept": {
                    "text": "Warfarin",
                    "coding": [
                        {"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "11289"}
                    ],
                },
            }
        },
    ],
}


@pytest.fixture()
def client():
    from app.db.database import init_db
    from app.main import create_app

    init_db(force=True)
    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_headers(client):
    def _get(role: str = "admin"):
        username = role
        password = SEED_CREDENTIALS[role]
        resp = client.post("/api/v1/auth/token", json={"username": username, "password": password})
        assert resp.status_code == 200, resp.text
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    return _get


@pytest.fixture()
def trial_id(client, auth_headers):
    resp = client.post(
        "/api/v1/trials/create",
        json={"trial_name": "Diabetes Study", "protocol_text": SAMPLE_PROTOCOL},
        headers=auth_headers(),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["trial_id"]
