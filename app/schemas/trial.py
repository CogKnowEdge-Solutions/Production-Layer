from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TrialRule(BaseModel):
    rule_id: str
    description: str
    type: str = Field(
        ...,
        description=(
            "age_range | medication | diagnosis | lab_value | temporal | caregiver | description"
        ),
    )
    category: str = "inclusion"
    criteria: dict = Field(default_factory=dict)


class TrialCreate(BaseModel):
    trial_name: str
    nct_number: str | None = None
    protocol_text: str | None = Field(
        None, description="Human-readable protocol document; parsed into structured rules"
    )
    rules: list[TrialRule] | None = Field(
        None, description="Alternatively, pass pre-structured rules directly"
    )
    inclusion_rules: list[TrialRule] | None = None
    exclusion_rules: list[TrialRule] | None = None
    status: str = "ACTIVE"


class TrialUpdate(BaseModel):
    trial_name: str | None = None
    protocol_text: str | None = None
    rules: list[TrialRule] | None = None
    inclusion_rules: list[TrialRule] | None = None
    exclusion_rules: list[TrialRule] | None = None
    status: str | None = None


class TrialResponse(BaseModel):
    trial_id: UUID
    nct_number: str | None = None
    trial_name: str | None = None
    protocol_version: int
    status: str
    rules: list[dict]
    inclusion_rules: list[dict] = []
    exclusion_rules: list[dict] = []
    created_at: datetime
    updated_at: datetime | None = None
    published_at: datetime | None = None


class TrialListResponse(BaseModel):
    items: list[TrialResponse]
    total: int
    offset: int
    limit: int
