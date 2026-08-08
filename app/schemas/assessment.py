from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EvidenceCitation(BaseModel):
    source: str
    detail: str


class RuleEvaluationResponse(BaseModel):
    rule_eval_id: UUID
    rule_id: str
    description: str | None = None
    type: str
    category: str
    status: str
    confidence: float
    evidence: list[dict] = []
    missing_data: list[str] = []
    is_overridden: bool = False
    override_reason: str | None = None
    original_status: str | None = None


class AssessmentResponse(BaseModel):
    assessment_id: UUID
    patient_id: UUID
    trial_id: UUID
    overall_status: str
    ai_confidence: float
    data_quality_score: float | None = None
    review_status: str
    final_status: str | None = None
    override_count: int = 0
    created_at: datetime
    reviewed_at: datetime | None = None
    rule_evaluations: list[RuleEvaluationResponse] = []


class OverrideRequest(BaseModel):
    rule_eval_id: UUID = Field(..., description="ID of the specific rule evaluation to override")
    new_status: str = Field(..., description="MATCHES, DOES_NOT_MATCH, or UNCLEAR")
    reasoning: str = Field(..., min_length=5, description="Reasoning is REQUIRED for any override")


class OverrideResponse(BaseModel):
    override_id: UUID
    assessment_id: UUID
    rule_id: str | None = None
    original_status: str
    new_status: str
    reasoning: str
    coordinator_id: UUID
    impact_on_eligibility: bool | None = None
    timestamp: datetime


class AssessmentListResponse(BaseModel):
    items: list[AssessmentResponse]
    total: int
    offset: int
    limit: int
