from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.services.audit_logger import get_audit_logger


def _audit_error(app: FastAPI, request: Request, status_code: int, message: str) -> None:
    try:
        db = getattr(request.state, "db", None)
        if db is None:
            return
        get_audit_logger().log(
            db,
            action="api_error",
            user_id=getattr(request.state, "user_id", None),
            hospital_id=getattr(request.state, "hospital_id", None),
            resource_type=request.url.path,
            result="error",
            reason_code=str(status_code),
            message=message[:500],
            ip_address=request.client.host if request.client else None,
            commit=False,
        )
        db.rollback()
    except Exception:
        pass


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = []
        for error in exc.errors():
            loc = ".".join(str(part) for part in error.get("loc", []) if part != "body")
            errors.append({"field": loc, "message": error.get("msg")})
        _audit_error(app, request, status.HTTP_422_UNPROCESSABLE_CONTENT, "validation error")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": "Validation error", "errors": errors},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        _audit_error(app, request, status.HTTP_500_INTERNAL_SERVER_ERROR, type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )
