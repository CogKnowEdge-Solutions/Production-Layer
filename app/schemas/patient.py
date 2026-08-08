from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.caregiver import CaregiverCreate


class EligibilityRequest(BaseModel):
    trial_id: UUID
    fhir_bundle: dict = Field(
        ...,
        description="FHIR R4 Patient resource or Bundle containing patient data",
    )
    caregivers: list[CaregiverCreate] | None = None


class PatientResponse(BaseModel):
    patient_id: UUID
    hospital_id: str | None = None
    mrn: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: str | None = None
    gender: str | None = None
    data_quality_score: float | None = None
