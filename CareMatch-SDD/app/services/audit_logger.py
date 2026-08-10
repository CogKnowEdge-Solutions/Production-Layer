import logging
import uuid

from sqlalchemy.orm import Session

from app.db.models import AuditLog
from app.services.security import redact_pii

logger = logging.getLogger(__name__)


class AuditLogger:
    """Compliance audit logging. PII is never stored — payloads are redacted."""

    def log(
        self,
        db: Session,
        *,
        action: str,
        user_id: uuid.UUID | None = None,
        hospital_id: str | None = None,
        resource_type: str | None = None,
        resource_id: str | uuid.UUID | None = None,
        data_accessed: dict | None = None,
        result: str = "success",
        ip_address: str | None = None,
        reason_code: str | None = None,
        message: str | None = None,
        commit: bool = True,
    ) -> AuditLog:
        entry = AuditLog(
            user_id=user_id,
            hospital_id=hospital_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            data_accessed=redact_pii(data_accessed) if data_accessed else None,
            result=result,
            ip_address=ip_address,
            reason_code=reason_code,
            message=message,
        )
        db.add(entry)
        if commit:
            db.commit()
        else:
            db.flush()
        return entry


_audit_logger: AuditLogger | None = None


def get_audit_logger() -> AuditLogger:
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
