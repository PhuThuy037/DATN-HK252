from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.common.enums import UserStatus


# =======================
# User (public output)
# =======================
class UserPublic(BaseModel):
    id: UUID
    email: EmailStr
    name: Optional[str] = None
    status: UserStatus

    model_config = {"from_attributes": True}


# =======================
# Register
# =======================
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=200)
    name: Optional[str] = Field(default=None, max_length=120)


class RegisterResponse(BaseModel):
    user: UserPublic


# =======================
# Login
# =======================
class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class TokenPairResponse(BaseModel):
    token_type: str = "bearer"
    access_token: str
    refresh_token: str
    expires_in: int  # seconds
    user: UserPublic


# =======================
# Refresh
# =======================
class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20)


class RefreshResponse(BaseModel):
    token_type: str = "bearer"
    access_token: str
    expires_in: int
    # nếu rotate refresh token thì trả refresh_token mới,
    # nếu không rotate thì để None
    refresh_token: Optional[str] = None


# =======================
# Logout
# =======================
class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=20)


class MessageResponse(BaseModel):
    message: str