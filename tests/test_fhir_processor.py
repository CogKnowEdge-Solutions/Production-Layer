import pytest

from app.services.fhir_processor import (
    FHIRProcessor,
    FHIRValidationError,
    data_completeness,
)
from tests.conftest import SAMPLE_FHIR_BUNDLE, SAMPLE_FHIR_PATIENT


@pytest.fixture()
def processor():
    return FHIRProcessor()


class TestPatientResource:
    def test_extracts_demographics(self, processor):
        data = processor.process(SAMPLE_FHIR_PATIENT)
        assert data.name == "Jane Doe"
        assert data.birth_date == "1980-05-15"
        assert data.gender == "female"
        assert data.mrn == "M-1000"

    def test_age_computation(self, processor):
        data = processor.process(SAMPLE_FHIR_PATIENT)
        assert data.age() is not None
        assert data.age() > 18

    def test_missing_name_flag(self, processor):
        patient = dict(SAMPLE_FHIR_PATIENT, name=[])
        data = processor.process(patient)
        assert "name" in data.missing_required


class TestBundle:
    def test_extracts_condition_and_medication(self, processor):
        data = processor.process(SAMPLE_FHIR_BUNDLE)
        assert data.mrn == "M-2000"
        assert data.conditions and data.conditions[0].icd10 == ["E11.9"]
        assert data.medications and data.medications[0].rxnorm == ["11289"]
        assert data.medications[0].active is True

    def test_bundle_without_patient_rejected(self, processor):
        bundle = {"resourceType": "Bundle", "entry": []}
        with pytest.raises(FHIRValidationError):
            processor.process(bundle)


class TestValidation:
    def test_non_object_rejected(self, processor):
        with pytest.raises(FHIRValidationError):
            processor.process("not-a-dict")

    def test_unsupported_resource_rejected(self, processor):
        with pytest.raises(FHIRValidationError):
            processor.process({"resourceType": "Observation"})


class TestDataCompleteness:
    def test_complete_patient(self):
        data = FHIRProcessor().process(SAMPLE_FHIR_BUNDLE)
        score = data_completeness(data)
        assert 0.0 <= score <= 1.0

    def test_minimal_patient_low_score(self):
        data = FHIRProcessor().process(SAMPLE_FHIR_PATIENT)
        assert data_completeness(data) <= 0.6
