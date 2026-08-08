from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class AuditMiddleware(BaseHTTPMiddleware):
    """Logs data-access events for requests touching patient-bearing resources.

    PHI is never stored: request bodies are PII-redacted before logging.
    """

    SENSITIVE_PATHS = ("/patients", "/assessments", "/caregivers")

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        try:
            if request.url.path.startswith(self.SENSITIVE_PATHS):
                db = getattr(request.state, "db", None)
                if db is not None and request.method in ("POST", "PUT", "PATCH"):
                    from app.services.audit_logger import get_audit_logger

                    body = None
                    if hasattr(request.state, "redacted_body"):
                        body = request.state.redacted_body
                    get_audit_logger().log(
                        db,
                        action=f"data_accessed_{request.method.lower()}",
                        user_id=getattr(request.state, "user_id", None),
                        hospital_id=getattr(request.state, "hospital_id", None),
                        resource_type=request.url.path,
                        data_accessed=body,
                        result="success" if response.status_code < 400 else "error",
                        reason_code=None
                        if response.status_code < 400
                        else str(response.status_code),
                        ip_address=request.client.host if request.client else None,
                        commit=False,
                    )
        except Exception:
            pass
        return response
