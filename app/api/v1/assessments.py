import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.v1.serializers import (
    assessment_to_response,
    override_to_response,
)
from app.db import repositories as repo
from app.db.database import get_db
from app.db.models import User
from app.middleware.auth import (
    ROLE_ADMINISTRATOR,
    ROLE_AUDITOR,
    ROLE_COORDINATOR,
    ROLE_PROVIDER,
    require_roles,
)
from app.middleware.metrics import (
    ai_confidence_distribution,
    assessments_override_count,
    coordinator_approval_rate,
)
from app.schemas.assessment import (
    AssessmentListResponse,
    AssessmentResponse,
    OverrideRequest,
    OverrideResponse,
)
from app.services.audit_logger import get_audit_logger

router = APIRouter(prefix="/assessments", tags=["assessments"])

_VALID_STATUSES = {"MATCHES", "DOES_NOT_MATCH", "UNCLEAR"}


@router.get("", response_model=AssessmentListResponse)
def list_assessments(
    offset: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(ROLE_COORDINATOR, ROLE_PROVIDER, ROLE_ADMINISTRATOR)),
):
    limit = min(limit, 1000)
    items = repo.list_assessments(db, offset=offset, limit=limit)
    total = repo.count_assessments(db)
    return AssessmentListResponse(
        items=[assessment_to_response(a) for a in items], total=total, offset=offset, limit=limit
    )


@router.get("/{assessment_id}", response_model=AssessmentResponse)
def get_assessment(
    assessment_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(ROLE_COORDINATOR, ROLE_PROVIDER, ROLE_ADMINISTRATOR)),
):
    """Retrieve a previously created assessment with full evidence chains."""
    try:
        assessment_uuid = uuid.UUID(assessment_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Invalid assessment id"
        ) from exc
    assessment = repo.get_assessment(db, assessment_uuid)
    if assessment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")

    get_audit_logger().log(
        db,
        action="assessment_viewed",
        user_id=user.user_id,
        hospital_id=user.hospital_id,
        resource_type="Assessment",
        resource_id=assessment.assessment_id,
        data_accessed={"overall_status": assessment.overall_status},
    )
    return assessment_to_response(assessment)


@router.put("/{assessment_id}/override", response_model=AssessmentResponse)
def override_assessment(
    assessment_id: str,
    body: OverrideRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(ROLE_COORDINATOR, ROLE_ADMINISTRATOR)),
):
    """Coordinator overrides a specific rule evaluation.

    Reasoning is REQUIRED (spec FR-053). The override is audit-logged
    synchronously (plan.md: critical - never async) and the overall status is
    recalculated.
    """
    try:
        assessment_uuid = uuid.UUID(assessment_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Invalid assessment id"
        ) from exc

    assessment = repo.get_assessment(db, assessment_uuid)
    if assessment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")

    if body.new_status not in _VALID_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"new_status must be one of {sorted(_VALID_STATUSES)}",
        )

    evaluation = repo.get_rule_evaluation(db, body.rule_eval_id)
    if evaluation is None or evaluation.assessment_id != assessment.assessment_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule evaluation not found for this assessment",
        )
    if evaluation.is_overridden:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This rule evaluation has already been overridden",
        )

    original_status = evaluation.status
    old_overall = assessment.overall_status

    repo.update_rule_evaluation(
        db,
        evaluation,
        is_overridden=True,
        override_reason=body.reasoning,
        original_status=original_status,
        status=body.new_status,
        overridden_by_user_id=user.user_id,
        overridden_at=datetime.now(UTC),
    )

    # --- Recalculate overall status ---
    evaluations = assessment.rule_evaluations
    has_unclear = any(e.status == "UNCLEAR" for e in evaluations)
    inclusion_fails = any(
        e.status == "DOES_NOT_MATCH" and e.category == "inclusion" for e in evaluations
    )
    exclusion_matches = any(
        e.status == "MATCHES" and e.category == "exclusion" for e in evaluations
    )
    if has_unclear:
        new_overall = "UNCLEAR"
    elif inclusion_fails or exclusion_matches:
        new_overall = "LIKELY_INELIGIBLE"
    else:
        new_overall = "LIKELY_ELIGIBLE"

    impact = new_overall != old_overall

    # --- Synchronous audit log (critical, never async) ---
    repo.create_override(
        db,
        assessment_id=assessment.assessment_id,
        rule_id=evaluation.rule_id,
        original_status=original_status,
        new_status=body.new_status,
        reasoning=body.reasoning,
        coordinator_id=user.user_id,
        impact_on_eligibility=impact,
    )
    get_audit_logger().log(
        db,
        action="override_applied",
        user_id=user.user_id,
        hospital_id=user.hospital_id,
        resource_type="Assessment",
        resource_id=assessment.assessment_id,
        data_accessed={
            "rule_id": evaluation.rule_id,
            "original_status": original_status,
            "new_status": body.new_status,
            "impact_on_eligibility": impact,
        },
        result="success",
        ip_address=request.client.host if request.client else None,
    )

    repo.update_assessment(
        db,
        assessment,
        overall_status=new_overall,
        review_status="OVERRIDDEN",
        final_status=new_overall,
        override_count=assessment.override_count + 1,
        reviewed_at=datetime.now(UTC),
    )

    assessments_override_count.inc()
    coordinator_approval_rate.labels("overridden").inc()
    ai_confidence_distribution.observe(assessment.ai_confidence or 0.0)

    db.refresh(assessment)
    return assessment_to_response(assessment)


@router.put("/{assessment_id}/approve", response_model=AssessmentResponse)
def approve_assessment(
    assessment_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(ROLE_COORDINATOR, ROLE_ADMINISTRATOR)),
):
    """Coordinator approves the AI recommendation, finalizing eligibility (FR-051)."""
    try:
        assessment_uuid = uuid.UUID(assessment_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Invalid assessment id"
        ) from exc

    assessment = repo.get_assessment(db, assessment_uuid)
    if assessment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")

    if assessment.review_status in ("APPROVED", "OVERRIDDEN"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Assessment is already {assessment.review_status.lower()}",
        )

    repo.update_assessment(
        db,
        assessment,
        review_status="APPROVED",
        final_status=assessment.overall_status,
        reviewed_at=datetime.now(UTC),
    )

    get_audit_logger().log(
        db,
        action="assessment_approved",
        user_id=user.user_id,
        hospital_id=user.hospital_id,
        resource_type="Assessment",
        resource_id=assessment.assessment_id,
        data_accessed={"final_status": assessment.overall_status},
        result="success",
        ip_address=request.client.host if request.client else None,
    )

    coordinator_approval_rate.labels("approved").inc()

    db.refresh(assessment)
    return assessment_to_response(assessment)


@router.get("/{assessment_id}/overrides", response_model=list[OverrideResponse])
def list_overrides(
    assessment_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(ROLE_AUDITOR, ROLE_ADMINISTRATOR)),
):
    """Feedback dataset for retraining: all overrides on an assessment."""
    try:
        assessment_uuid = uuid.UUID(assessment_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Invalid assessment id"
        ) from exc
    if repo.get_assessment(db, assessment_uuid) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")
    overrides = repo.list_overrides_for_assessment(db, assessment_uuid)
    return [override_to_response(o) for o in overrides]
