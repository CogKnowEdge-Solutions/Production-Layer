from app.db.models import Assessment, AssessmentOverride, Caregiver, Patient, RuleEvaluation, Trial
from app.schemas.assessment import (
    AssessmentResponse,
    OverrideResponse,
    RuleEvaluationResponse,
)
from app.schemas.caregiver import CaregiverResponse
from app.schemas.patient import PatientResponse
from app.schemas.trial import TrialResponse


def assessment_to_response(assessment: Assessment) -> AssessmentResponse:
    return AssessmentResponse(
        assessment_id=assessment.assessment_id,
        patient_id=assessment.patient_id,
        trial_id=assessment.trial_id,
        overall_status=assessment.overall_status,
        ai_confidence=assessment.ai_confidence or 0.0,
        data_quality_score=assessment.data_quality_score,
        review_status=assessment.review_status,
        final_status=assessment.final_status,
        override_count=assessment.override_count,
        created_at=assessment.created_at,
        reviewed_at=assessment.reviewed_at,
        rule_evaluations=[rule_evaluation_to_response(re) for re in assessment.rule_evaluations],
    )


def rule_evaluation_to_response(re: RuleEvaluation) -> RuleEvaluationResponse:
    return RuleEvaluationResponse(
        rule_eval_id=re.rule_eval_id,
        rule_id=re.rule_id,
        description=re.rule_description,
        type=re.rule_type or "",
        category=re.category or "",
        status=re.status,
        confidence=re.confidence or 0.0,
        evidence=re.evidence if isinstance(re.evidence, list) else [],
        missing_data=re.missing_data if isinstance(re.missing_data, list) else [],
        is_overridden=re.is_overridden,
        override_reason=re.override_reason,
        original_status=re.original_status,
    )


def trial_to_response(trial: Trial) -> TrialResponse:
    return TrialResponse(
        trial_id=trial.trial_id,
        nct_number=trial.nct_number,
        trial_name=trial.trial_name,
        protocol_version=trial.protocol_version,
        status=trial.status,
        rules=trial.rules if isinstance(trial.rules, list) else [],
        inclusion_rules=trial.inclusion_rules if isinstance(trial.inclusion_rules, list) else [],
        exclusion_rules=trial.exclusion_rules if isinstance(trial.exclusion_rules, list) else [],
        created_at=trial.created_at,
        updated_at=trial.updated_at,
        published_at=trial.published_at,
    )


def caregiver_to_response(caregiver: Caregiver) -> CaregiverResponse:
    return CaregiverResponse(
        caregiver_id=caregiver.caregiver_id,
        patient_id=caregiver.patient_id,
        relationship_type=caregiver.relationship_type,
        name=caregiver.name,
        phone=caregiver.phone,
        email=caregiver.email,
        date_of_birth=caregiver.date_of_birth.isoformat() if caregiver.date_of_birth else None,
        qualifications=caregiver.qualifications,
        authorization_status=caregiver.authorization_status,
        consent_status=caregiver.consent_status,
        created_at=caregiver.created_at,
    )


def patient_to_response(patient: Patient) -> PatientResponse:
    return PatientResponse(
        patient_id=patient.patient_id,
        hospital_id=patient.hospital_id,
        mrn=patient.mrn,
        first_name=patient.first_name,
        last_name=patient.last_name,
        date_of_birth=patient.date_of_birth.isoformat() if patient.date_of_birth else None,
        gender=patient.gender,
        data_quality_score=patient.data_quality_score,
    )


def override_to_response(override: AssessmentOverride) -> OverrideResponse:
    return OverrideResponse(
        override_id=override.override_id,
        assessment_id=override.assessment_id,
        rule_id=override.rule_id,
        original_status=override.original_status,
        new_status=override.new_status,
        reasoning=override.reasoning,
        coordinator_id=override.coordinator_id,
        impact_on_eligibility=override.impact_on_eligibility,
        timestamp=override.timestamp,
    )
