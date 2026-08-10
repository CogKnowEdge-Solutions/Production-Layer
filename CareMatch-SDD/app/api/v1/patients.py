from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.v1.serializers import assessment_to_response, patient_to_response
from app.db import repositories as repo
from app.db.database import get_db
from app.db.models import Patient, User
from app.middleware.auth import ROLE_ADMINISTRATOR, ROLE_COORDINATOR, ROLE_PROVIDER, require_roles
from app.middleware.metrics import assessments_created_total, assessments_status
from app.schemas.assessment import AssessmentResponse
from app.schemas.patient import EligibilityRequest, PatientResponse
from app.services.eligibility import EligibilityError, get_eligibility_service
from app.services.fhir_processor import (
    CaregiverRecord,
    FHIRProcessor,
    FHIRValidationError,
    PatientData,
    _age_on,
    _parse_date,
    data_completeness,
)

router = APIRouter(prefix="/patients", tags=["patients"])


def _patient_data_from_bundle(payload: dict) -> PatientData:
    processor = FHIRProcessor()
    try:
        return processor.process(payload)
    except FHIRValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc


def _upsert_patient(db: Session, data: PatientData, hospital_id: str | None) -> Patient:
    existing = repo.find_patient_by_mrn(db, hospital_id, data.mrn)
    if existing:
        return repo.update_patient(
            db,
            existing,
            fhir_data=data.to_dict(),
            data_quality_score=data_completeness(data),
            first_name=data.name.split(" ")[0] if data.name else None,
            last_name=" ".join(data.name.split(" ")[1:]) if data.name else None,
            date_of_birth=date.fromisoformat(data.birth_date) if data.birth_date else None,
            gender=data.gender,
        )
    return repo.create_patient(
        db,
        hospital_id=hospital_id,
        mrn=data.mrn,
        first_name=data.name.split(" ")[0] if data.name else None,
        last_name=" ".join(data.name.split(" ")[1:]) if data.name else None,
        date_of_birth=date.fromisoformat(data.birth_date) if data.birth_date else None,
        gender=data.gender,
        fhir_data=data.to_dict(),
        data_quality_score=data_completeness(data),
    )


@router.post(
    "/evaluate-eligibility",
    response_model=AssessmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def evaluate_eligibility(
    body: EligibilityRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(ROLE_COORDINATOR, ROLE_PROVIDER, ROLE_ADMINISTRATOR)),
):
    """Evaluate a patient against a trial's protocol, rule by rule, with evidence.

    The result is a RECOMMENDATION only — a coordinator must review, approve,
    or override before eligibility is final (spec FR-050/FR-051).
    """
    trial = repo.get_trial(db, body.trial_id)
    if trial is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trial not found")

    data = _patient_data_from_bundle(body.fhir_bundle)
    if body.caregivers:
        for caregiver in body.caregivers:
            caregiver_dob = _parse_date(caregiver.date_of_birth)
            data.caregivers.append(
                CaregiverRecord(
                    name=caregiver.name,
                    relationship_type=caregiver.relationship_type,
                    age=_age_on(caregiver_dob) if caregiver_dob else None,
                    verified=caregiver.authorization_status == "VERIFIED",
                    birth_date=caregiver.date_of_birth,
                )
            )

    hospital_id = user.hospital_id
    patient = _upsert_patient(db, data, hospital_id)

    for caregiver in body.caregivers or []:
        repo.create_caregiver(
            db,
            patient_id=patient.patient_id,
            relationship_type=caregiver.relationship_type,
            name=caregiver.name,
            phone=caregiver.phone,
            email=caregiver.email,
            date_of_birth=date.fromisoformat(caregiver.date_of_birth)
            if caregiver.date_of_birth
            else None,
            qualifications=caregiver.qualifications,
            authorization_status=caregiver.authorization_status,
            consent_status=caregiver.consent_status,
        )

    service = get_eligibility_service()
    try:
        assessment = service.evaluate(
            db,
            trial=trial,
            patient_data=data,
            patient_id=patient.patient_id,
            hospital_id=hospital_id,
            coordinator_id=user.user_id,
            ip_address=request.client.host if request.client else None,
        )
    except EligibilityError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    assessments_created_total.inc()
    assessments_status.labels(assessment.overall_status).inc()

    return assessment_to_response(assessment)


@router.get("/{patient_id}", response_model=PatientResponse)
def get_patient(
    patient_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(ROLE_COORDINATOR, ROLE_PROVIDER, ROLE_ADMINISTRATOR)),
):
    from uuid import UUID

    try:
        patient_uuid = UUID(patient_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Invalid patient id"
        ) from exc
    patient = repo.get_patient(db, patient_uuid)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient_to_response(patient)
