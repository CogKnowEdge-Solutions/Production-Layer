import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.config import get_settings
from app.db.models import User
from app.services.security import verify_password


class AuthError(Exception):
    pass


class InvalidCredentials(AuthError):
    pass


class TokenExpired(AuthError):
    pass


class InvalidToken(AuthError):
    pass


class AuthService:
    """JWT access/refresh token issuance and validation (OAuth 2.0 compatible)."""

    def __init__(self, settings=None):
        self.settings = settings or get_settings()

    # --- Password verification ---
    def authenticate(self, user: User | None, password: str) -> User:
        if user is None or not user.is_active:
            raise InvalidCredentials("Invalid username or password")
        if not verify_password(password, user.password_hash):
            raise InvalidCredentials("Invalid username or password")
        return user

    # --- Token creation ---
    def _create_token(
        self,
        user: User,
        token_type: str,
        expires_delta: timedelta,
        extra_claims: dict | None = None,
    ) -> str:
        now = datetime.now(UTC)
        claims: dict[str, Any] = {
            "sub": user.username,
            "user_id": str(user.user_id),
            "roles": [user.role],
            "hospital_id": user.hospital_id,
            "aud": "carematch-api",
            "iat": int(now.timestamp()),
            "exp": int((now + expires_delta).timestamp()),
            "token_type": token_type,
        }
        if extra_claims:
            claims.update(extra_claims)
        return jwt.encode(claims, self.settings.jwt_secret, algorithm=self.settings.jwt_algorithm)

    def create_access_token(self, user: User) -> str:
        delta = timedelta(minutes=self.settings.access_token_expire_minutes)
        return self._create_token(user, "access", delta)

    def create_refresh_token(self, user: User) -> str:
        delta = timedelta(days=self.settings.refresh_token_expire_days)
        return self._create_token(user, "refresh", delta)

    def create_token_pair(self, user: User) -> dict:
        return {
            "access_token": self.create_access_token(user),
            "refresh_token": self.create_refresh_token(user),
            "token_type": "bearer",
            "expires_in": self.settings.access_token_expire_minutes * 60,
        }

    # --- Token validation ---
    def decode_token(self, token: str, expected_type: str = "access") -> dict:
        try:
            payload = jwt.decode(
                token,
                self.settings.jwt_secret,
                algorithms=[self.settings.jwt_algorithm],
                audience="carematch-api",
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenExpired("Token has expired") from exc
        except jwt.InvalidTokenError as exc:
            raise InvalidToken("Invalid token") from exc
        if payload.get("token_type") != expected_type:
            raise InvalidToken(f"Expected {expected_type} token")
        return payload

    def decode_access_token(self, token: str) -> dict:
        return self.decode_token(token, expected_type="access")

    def decode_refresh_token(self, token: str) -> dict:
        return self.decode_token(token, expected_type="refresh")


def _user_from_payload(db, payload: dict) -> User | None:
    try:
        user_id = uuid.UUID(payload["user_id"])
    except (KeyError, ValueError):
        return None
    return db.get(User, user_id)
