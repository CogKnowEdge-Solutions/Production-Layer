from uuid import UUID

from pydantic import BaseModel


class TokenRequest(BaseModel):
    username: str
    password: str
    grant_type: str = "password"


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class UserInfo(BaseModel):
    user_id: UUID
    username: str
    role: str
    hospital_id: str | None = None
    permissions: list[str] = []


class UserResponse(BaseModel):
    user_id: UUID
    username: str
    role: str
    hospital_id: str | None = None
    is_active: bool
