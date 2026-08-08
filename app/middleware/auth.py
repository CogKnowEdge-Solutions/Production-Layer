from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import User
from app.services.oauth import AuthService, TokenExpired

ROLE_ADMINISTRATOR = "ADMINISTRATOR"
ROLE_PROVIDER = "PROVIDER"
ROLE_COORDINATOR = "COORDINATOR"
ROLE_AUDITOR = "AUDITOR"

_ALL_ROLES = {ROLE_ADMINISTRATOR, ROLE_PROVIDER, ROLE_COORDINATOR, ROLE_AUDITOR}


def _extract_bearer(request: Request) -> str:
    authorization = request.headers.get("Authorization", "")
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return authorization[7:].strip()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = _extract_bearer(request)
    auth = AuthService()
    try:
        payload = auth.decode_access_token(token)
    except TokenExpired as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from exc

    from app.services.oauth import _user_from_payload

    user = _user_from_payload(db, payload)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    request.state.user_id = user.user_id
    request.state.hospital_id = user.hospital_id
    request.state.user_role = user.role
    return user


def require_roles(*roles: str):
    if not roles:
        roles = tuple(sorted(_ALL_ROLES))

    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' is not authorized for this operation",
            )
        return user

    return dependency


def require_admin(user: User = Depends(require_roles(ROLE_ADMINISTRATOR))) -> User:
    return user
