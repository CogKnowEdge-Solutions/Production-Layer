from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import repositories as repo
from app.db.database import get_db
from app.db.models import User
from app.middleware.auth import ROLE_ADMINISTRATOR, ROLE_AUDITOR, require_roles
from app.schemas.audit import AuditLogListResponse

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs", response_model=AuditLogListResponse)
def list_audit_logs(
    offset: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(ROLE_AUDITOR, ROLE_ADMINISTRATOR)),
):
    """Audit trail for HIPAA compliance review (FR-030)."""
    logs = repo.list_audit_logs(db, offset=offset, limit=limit)
    total = repo.count_audit_logs(db)
    return {
        "items": logs,
        "total": total,
        "offset": offset,
        "limit": limit,
    }
