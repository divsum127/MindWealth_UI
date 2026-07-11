"""Auth API schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    email: str
    name: str
    role: Literal["admin", "user"]


class UserProfile(BaseModel):
    email: str
    name: str
    role: Literal["admin", "user"]
    status: str
    activity_logging_enabled: bool = False


class AcceptInviteRequest(BaseModel):
    token: str = Field(min_length=8)
    password: str = Field(min_length=8)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


class AdminInviteRequest(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    role: Literal["admin", "user"] = "user"


class AdminInviteResponse(BaseModel):
    email: str
    invite_url: str
    invite_token: str
    invite_expires_at: str


class AdminUserSummary(BaseModel):
    email: str
    name: str
    role: Literal["admin", "user"]
    status: str
    invite_expires_at: str | None = None
    activity_logging_enabled: bool = False


class AdminUserPatchRequest(BaseModel):
    status: Literal["invited", "active", "disabled"] | None = None
    resend_invite: bool = False
    name: str | None = None
    role: Literal["admin", "user"] | None = None
    activity_logging_enabled: bool | None = None
