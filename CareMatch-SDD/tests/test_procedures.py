from app.services.fhir_processor import FHIRProcessor, data_completeness


class TestProcedureExtraction:
    def test_procedure_extracted_from_bundle(self):
        bundle = {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Patient",
                        "id": "p1",
                        "name": [{"family": "Doe", "given": ["Jane"]}],
                        "birthDate": "1980-05-15",
                    }
                },
                {
                    "resource": {
                        "resourceType": "Procedure",
                        "status": "completed",
                        "code": {
                            "text": "Coronary artery bypass",
                            "coding": [
                                {"system": "http://hl7.org/fhir/sid/icd-10-pcs", "code": "02100"}
                            ],
                        },
                        "performedDateTime": "2020-01-15",
                    }
                },
            ],
        }
        data = FHIRProcessor().process(bundle)
        assert len(data.procedures) == 1
        assert data.procedures[0].name == "Coronary artery bypass"
        assert data.procedures[0].code == "02100"
        assert data.procedures[0].status == "completed"
        assert data.procedures[0].performed_date == "2020-01-15"

    def test_procedure_boosts_data_completeness(self):
        bundle = {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Patient",
                        "id": "p1",
                        "name": [{"family": "Doe", "given": ["Jane"]}],
                        "birthDate": "1980-05-15",
                    }
                },
                {"resource": {"resourceType": "Procedure", "code": {"text": "Surgery"}}},
                {
                    "resource": {
                        "resourceType": "AllergyIntolerance",
                        "code": {"text": "Penicillin"},
                    }
                },
            ],
        }
        data = FHIRProcessor().process(bundle)
        assert data.procedures
        assert data.allergies
        score = data_completeness(data)
        assert score > 0.5
