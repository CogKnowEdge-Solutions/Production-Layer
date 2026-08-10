from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CaregiverCreate(BaseModel):
    patient_id: UUID = Field(..., description="Patient this caregiver is associated with")
    relationship_type: str = Field(
        ...,
        description="PRIMARY | EMERGENCY_CONTACT | LEGAL_PROXY | POWER_OF_ATTORNEY",
    )
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    date_of_birth: str | None = None
    qualifications: dict | None = None
    authorization_status: str = "PENDING"
    consent_status: str | None = None


class CaregiverResponse(BaseModel):
    caregiver_id: UUID
    patient_id: UUID
    relationship_type: str
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    date_of_birth: str | None = None
    qualifications: dict | None = None
    authorization_status: str
    consent_status: str | None = None
    created_at: datetime


class CaregiverListResponse(BaseModel):
    items: list[CaregiverResponse]
    total: int
