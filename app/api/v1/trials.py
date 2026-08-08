import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.serializers import trial_to_response
from app.db import repositories as repo
from app.db.database import get_db
from app.db.models import User
from app.dependencies import Pagination
from app.middleware.auth import ROLE_ADMINISTRATOR, ROLE_PROVIDER, require_roles
from app.schemas.trial import TrialCreate, TrialListResponse, TrialResponse
from app.services.audit_logger import get_audit_logger
from app.services.protocol_parser import parse_protocol_document, parse_structured_rules

router = APIRouter(prefix="/trials", tags=["trials"])

_ROLE_ALLOWED = (ROLE_ADMINISTRATOR, ROLE_PROVIDER)


def _rules_to_dicts(rules):
    return [rule.model_dump() for rule in rules] if rules else None


@router.post("/create", response_model=TrialResponse, status_code=status.HTTP_201_CREATED)
def create_trial(
    body: TrialCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*_ROLE_ALLOWED)),
):
    """Create a trial protocol from a human-readable document or structured rules."""
    warnings: list[str] = []

    if body.protocol_text is not None and body.rules is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either protocol_text or rules, not both",
        )

    rules: list[dict] | None = None
    if body.protocol_text:
        rules, warnings = parse_protocol_document(body.protocol_text)
    elif body.rules:
        rules, warnings = parse_structured_rules([rule.model_dump() for rule in body.rules])
    elif body.inclusion_rules or body.exclusion_rules:
        rules = None
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide protocol_text, rules, or inclusion/exclusion rules",
        )

    now = datetime.now(UTC)

    trial = repo.create_trial(
        db,
        nct_number=body.nct_number,
        trial_name=body.trial_name,
        protocol_version=1,
        status=body.status.upper(),
        rules=rules,
        inclusion_rules=_rules_to_dicts(body.inclusion_rules),
        exclusion_rules=_rules_to_dicts(body.exclusion_rules),
        created_by=user.user_id,
        published_at=now,
    )

    get_audit_logger().log(
        db,
        action="trial_created",
        user_id=user.user_id,
        hospital_id=user.hospital_id,
        resource_type="Trial",
        resource_id=trial.trial_id,
        data_accessed={"nct": body.nct_number, "warning_count": len(warnings)},
    )
    return trial_to_response(trial)


@router.get("/{trial_id}", response_model=TrialResponse)
def get_trial(
    trial_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*_ROLE_ALLOWED, "COORDINATOR", "AUDITOR")),
):
    try:
        trial_uuid = uuid.UUID(trial_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Invalid trial id"
        ) from exc
    trial = repo.get_trial(db, trial_uuid)
    if trial is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trial not found")
    return trial_to_response(trial)


@router.get("", response_model=TrialListResponse)
def list_trials(
    pagination: Pagination,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*_ROLE_ALLOWED, "COORDINATOR", "AUDITOR")),
):
    offset, limit = pagination
    items = repo.list_trials(db, offset=offset, limit=limit)
    total = repo.count_trials(db)
    return TrialListResponse(
        items=[trial_to_response(t) for t in items], total=total, offset=offset, limit=limit
    )
