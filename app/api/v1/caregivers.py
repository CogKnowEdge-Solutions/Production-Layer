import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.serializers import caregiver_to_response
from app.db import repositories as repo
from app.db.database import get_db
from app.db.models import User
from app.middleware.auth import ROLE_ADMINISTRATOR, ROLE_PROVIDER, require_roles
from app.schemas.caregiver import CaregiverCreate, CaregiverListResponse, CaregiverResponse
from app.services.audit_logger import get_audit_logger

router = APIRouter(tags=["caregivers"])

_ALLOWED_RELATIONSHIPS = {"PRIMARY", "EMERGENCY_CONTACT", "LEGAL_PROXY", "POWER_OF_ATTORNEY"}


@router.post("/caregivers", response_model=CaregiverResponse, status_code=status.HTTP_201_CREATED)
def create_caregiver(
    body: CaregiverCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(ROLE_ADMINISTRATOR, ROLE_PROVIDER)),
):
    """Register or update caregiver information for a patient."""
    if body.relationship_type.upper() not in _ALLOWED_RELATIONSHIPS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"relationship_type must be one of {sorted(_ALLOWED_RELATIONSHIPS)}",
        )
    patient = repo.get_patient(db, body.patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    caregiver = repo.create_caregiver(
        db,
        patient_id=body.patient_id,
        relationship_type=body.relationship_type.upper(),
        name=body.name,
        phone=body.phone,
        email=body.email,
        date_of_birth=date.fromisoformat(body.date_of_birth) if body.date_of_birth else None,
        qualifications=body.qualifications,
        authorization_status=body.authorization_status.upper(),
        consent_status=body.consent_status,
    )
    get_audit_logger().log(
        db,
        action="caregiver_created",
        user_id=user.user_id,
        hospital_id=user.hospital_id,
        resource_type="Caregiver",
        resource_id=caregiver.caregiver_id,
        data_accessed={
            "patient_id": str(body.patient_id),
            "relationship": caregiver.relationship_type,
        },
    )
    return caregiver_to_response(caregiver)


@router.get(
    "/patients/{patient_id}/caregivers",
    response_model=CaregiverListResponse,
)
def list_caregivers_for_patient(
    patient_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(ROLE_ADMINISTRATOR, ROLE_PROVIDER, "COORDINATOR", "AUDITOR")
    ),
):
    try:
        patient_uuid = uuid.UUID(patient_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Invalid patient id"
        ) from exc
    if repo.get_patient(db, patient_uuid) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    caregivers = repo.list_caregivers_for_patient(db, patient_uuid)
    return CaregiverListResponse(
        items=[caregiver_to_response(c) for c in caregivers], total=len(caregivers)
    )
