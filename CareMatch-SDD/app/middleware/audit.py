import json

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.services.security import redact_pii


class AuditMiddleware(BaseHTTPMiddleware):
    """Logs data-access events for requests touching patient-bearing resources.

    PHI is never stored: request bodies are PII-redacted before logging.
    """

    SENSITIVE_PATHS = ("/patients", "/assessments", "/caregivers")

    @staticmethod
    def _is_sensitive(path: str) -> bool:
        prefixed = any(f"/api/v1{segment}" in path for segment in AuditMiddleware.SENSITIVE_PATHS)
        return prefixed or any(
            path.startswith(segment) for segment in AuditMiddleware.SENSITIVE_PATHS
        )

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method in ("POST", "PUT", "PATCH"):
            body = await request.body()
            if body:
                try:
                    request.state.redacted_body = redact_pii(json.loads(body))
                except Exception:
                    request.state.redacted_body = None

                async def receive():
                    return {"type": "http.request", "body": body}

                request._receive = receive

        response = await call_next(request)
        try:
            if self._is_sensitive(request.url.path):
                from app.db.database import SessionLocal
                from app.services.audit_logger import get_audit_logger

                audit_db = SessionLocal()
                try:
                    get_audit_logger().log(
                        audit_db,
                        action=f"data_accessed_{request.method.lower()}",
                        user_id=getattr(request.state, "user_id", None),
                        hospital_id=getattr(request.state, "hospital_id", None),
                        resource_type=request.url.path,
                        data_accessed=getattr(request.state, "redacted_body", None),
                        result="success" if response.status_code < 400 else "error",
                        reason_code=None
                        if response.status_code < 400
                        else str(response.status_code),
                        ip_address=request.client.host if request.client else None,
                        commit=False,
                    )
                    audit_db.commit()
                finally:
                    audit_db.close()
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning("Audit middleware failed: %s", exc)
        return response
