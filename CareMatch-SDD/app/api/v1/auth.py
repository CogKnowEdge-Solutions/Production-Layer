from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db import repositories as repo
from app.db.database import get_db
from app.db.models import User
from app.middleware.auth import get_current_user
from app.schemas.auth import RefreshRequest, TokenRequest, TokenResponse, UserInfo
from app.services.audit_logger import get_audit_logger
from app.services.oauth import AuthService, TokenExpired

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/token", response_model=TokenResponse)
def token_issue(
    body: TokenRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """OAuth 2.0-compatible token endpoint. Validates credentials and issues a
    15-minute access token plus a 7-day refresh token."""
    auth = AuthService()
    user = repo.get_user_by_username(db, body.username)
    try:
        user = auth.authenticate(user, body.password)
    except Exception as exc:
        get_audit_logger().log(
            db,
            action="authentication_failed",
            hospital_id=user.hospital_id if user else None,
            result="denied",
            reason_code="invalid_credentials",
            ip_address=request.client.host if request.client else None,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password"
        ) from exc

    tokens = auth.create_token_pair(user)
    get_audit_logger().log(
        db,
        action="token_issued",
        user_id=user.user_id,
        hospital_id=user.hospital_id,
        resource_type="Token",
        result="success",
        ip_address=request.client.host if request.client else None,
    )
    return TokenResponse(**tokens)


@router.post("/refresh", response_model=TokenResponse)
def token_refresh(
    body: RefreshRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Exchange a valid refresh token for a new access/refresh token pair."""
    auth = AuthService()
    try:
        payload = auth.decode_refresh_token(body.refresh_token)
        user = _user_from_refresh_payload(db, payload)
    except TokenExpired as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        ) from exc

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    tokens = auth.create_token_pair(user)
    return TokenResponse(**tokens)


def _user_from_refresh_payload(db: Session, payload: dict) -> User | None:

    from app.services.oauth import _user_from_payload

    return _user_from_payload(db, payload)


@router.get("/me", response_model=UserInfo)
def me(user: User = Depends(get_current_user)):
    return UserInfo(
        user_id=user.user_id,
        username=user.username,
        role=user.role,
        hospital_id=user.hospital_id,
    )
