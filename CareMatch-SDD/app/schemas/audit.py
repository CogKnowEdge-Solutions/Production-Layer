from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    audit_id: UUID
    timestamp: datetime
    user_id: UUID | None
    hospital_id: str | None
    action: str
    resource_type: str | None
    resource_id: str | None
    data_accessed: dict | None
    result: str
    ip_address: str | None
    reason_code: str | None
    message: str | None


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    offset: int
    limit: int
