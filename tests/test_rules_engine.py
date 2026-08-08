from app.services.fhir_processor import (
    CaregiverRecord,
    ConditionRecord,
    MedicationRecord,
    ObservationRecord,
    PatientData,
)
from app.services.rules_engine import (
    DOES_NOT_MATCH,
    MATCHES,
    UNCLEAR,
    evaluate_rule,
    validate_rule,
)


def make_patient(**kwargs) -> PatientData:
    defaults = {"name": "Jane Doe", "birth_date": "1980-05-15", "gender": "female"}
    defaults.update(kwargs)
    return PatientData(**defaults)


def rule(**kwargs) -> dict:
    defaults = {
        "rule_id": "R-001",
        "description": "test rule",
        "category": "inclusion",
        "criteria": {},
    }
    defaults.update(kwargs)
    return defaults


class TestAgeRange:
    def test_matches_within_range(self):
        result = evaluate_rule(
            make_patient(), rule(type="age_range", criteria={"min_age": 18, "max_age": 100})
        )
        assert result["status"] == MATCHES
        assert result["confidence"] == 1.0
        assert result["evidence"]

    def test_does_not_match_below_minimum(self):
        result = evaluate_rule(make_patient(), rule(type="age_range", criteria={"min_age": 50}))
        assert result["status"] == DOES_NOT_MATCH

    def test_unclear_when_no_birthdate(self):
        result = evaluate_rule(
            make_patient(birth_date=None), rule(type="age_range", criteria={"min_age": 18})
        )
        assert result["status"] == UNCLEAR
        assert result["missing_data"]


class TestMedication:
    def test_matches_active_medication(self):
        data = make_patient(
            medications=[MedicationRecord(name="Warfarin", rxnorm=["11289"], status="active")]
        )
        result = evaluate_rule(
            data,
            rule(type="medication", criteria={"rxnorm_codes": ["11289"]}),
        )
        assert result["status"] == MATCHES
        assert result["evidence"][0]["source"] == "medications"

    def test_matches_by_name(self):
        data = make_patient(medications=[MedicationRecord(name="Warfarin", status="active")])
        result = evaluate_rule(data, rule(type="medication", criteria={"names": ["warfarin"]}))
        assert result["status"] == MATCHES

    def test_does_not_match_when_absent(self):
        data = make_patient(medications=[MedicationRecord(name="Metformin", status="active")])
        result = evaluate_rule(data, rule(type="medication", criteria={"names": ["warfarin"]}))
        assert result["status"] == DOES_NOT_MATCH

    def test_unclear_when_no_medication_history(self):
        result = evaluate_rule(
            make_patient(), rule(type="medication", criteria={"names": ["warfarin"]})
        )
        assert result["status"] == UNCLEAR


class TestDiagnosis:
    def test_matches_icd10(self):
        data = make_patient(
            conditions=[ConditionRecord(name="Diabetes", icd10=["E11.9"], status="active")]
        )
        result = evaluate_rule(data, rule(type="diagnosis", criteria={"icd10_codes": ["E11.9"]}))
        assert result["status"] == MATCHES

    def test_unclear_when_no_conditions(self):
        result = evaluate_rule(
            make_patient(), rule(type="diagnosis", criteria={"names": ["diabetes"]})
        )
        assert result["status"] == UNCLEAR


class TestLabValue:
    def test_matches_threshold(self):
        data = make_patient(
            observations=[ObservationRecord(name="HbA1c", loinc="4548-4", value=7.5, unit="%")]
        )
        result = evaluate_rule(
            data,
            rule(
                type="lab_value", criteria={"loinc_code": "4548-4", "operator": ">=", "value": 7.0}
            ),
        )
        assert result["status"] == MATCHES

    def test_does_not_match_below_threshold(self):
        data = make_patient(
            observations=[ObservationRecord(name="HbA1c", loinc="4548-4", value=6.0, unit="%")]
        )
        result = evaluate_rule(
            data,
            rule(
                type="lab_value", criteria={"loinc_code": "4548-4", "operator": ">=", "value": 7.0}
            ),
        )
        assert result["status"] == DOES_NOT_MATCH

    def test_unclear_when_observation_missing(self):
        result = evaluate_rule(
            make_patient(),
            rule(
                type="lab_value", criteria={"loinc_code": "4548-4", "operator": ">=", "value": 7.0}
            ),
        )
        assert result["status"] == UNCLEAR


class TestTemporal:
    def test_present_event_matches(self):
        data = make_patient(conditions=[ConditionRecord(name="Hospitalization", status="active")])
        result = evaluate_rule(
            data,
            rule(
                type="temporal",
                criteria={
                    "field": "condition",
                    "days": 30,
                    "present": True,
                    "name": "hospitalization",
                },
            ),
        )
        assert result["status"] == MATCHES

    def test_absent_event_does_not_match_when_required(self):
        data = make_patient(conditions=[ConditionRecord(name="Asthma", status="active")])
        result = evaluate_rule(
            data,
            rule(
                type="temporal",
                criteria={
                    "field": "condition",
                    "days": 30,
                    "present": True,
                    "name": "hospitalization",
                },
            ),
        )
        assert result["status"] == DOES_NOT_MATCH


class TestCaregiver:
    def test_matches_with_primary_caregiver(self):
        data = make_patient(
            caregivers=[
                CaregiverRecord(
                    name="Mary Smith", relationship_type="PRIMARY", age=45, verified=True
                )
            ]
        )
        result = evaluate_rule(
            data, rule(type="caregiver", criteria={"relationship": "PRIMARY", "min_age": 18})
        )
        assert result["status"] == MATCHES

    def test_unclear_when_no_caregivers(self):
        result = evaluate_rule(
            make_patient(), rule(type="caregiver", criteria={"relationship": "PRIMARY"})
        )
        assert result["status"] == UNCLEAR


class TestDescription:
    def test_description_rule_is_unclear(self):
        result = evaluate_rule(
            make_patient(),
            rule(type="description", description="Rule requires clinical review"),
        )
        assert result["status"] == UNCLEAR
        assert result["missing_data"]


class TestValidateRule:
    def test_valid_rule_passes(self):
        assert validate_rule(rule(type="age_range", criteria={"min_age": 18})) == []

    def test_invalid_type_reported(self):
        problems = validate_rule(rule(type="bogus"))
        assert any("type" in p for p in problems)

    def test_missing_description_reported(self):
        problems = validate_rule({"rule_id": "R", "type": "age_range", "criteria": {}})
        assert any("description" in p for p in problems)
