"""FastAPI dependencies."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Annotated, Literal

from fastapi import Cookie, Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.services import auth_service as auth_svc

API_KEY_HEADER = "X-API-Key"
REQUIRE_API_KEY = os.getenv("REQUIRE_API_KEY", "").strip().lower() in {"1", "true", "yes"}
CHATBOT_REQUIRE_USER = os.getenv("CHATBOT_REQUIRE_USER", "true").strip().lower() not in {"0", "false", "no"}

# Backward-compatible module constant (tests may patch this)
API_KEY = os.getenv("API_KEY", "").strip()


def _configured_api_key() -> str:
    if "API_KEY" in os.environ:
        return os.environ.get("API_KEY", "").strip()
    return API_KEY.strip()

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    email: str
    name: str
    role: Literal["admin", "user"]


async def require_api_key(
    x_api_key: Annotated[str | None, Header(alias=API_KEY_HEADER)] = None,
) -> None:
    """Require X-API-Key when API_KEY env is set (or REQUIRE_API_KEY forces it)."""
    key = _configured_api_key()
    if not key and not REQUIRE_API_KEY:
        return
    if not key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API_KEY is not configured",
        )
    if not x_api_key or x_api_key != key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )


async def optional_api_key(
    x_api_key: Annotated[str | None, Header(alias=API_KEY_HEADER)] = None,
) -> None:
    """Backward-compatible alias for require_api_key."""
    await require_api_key(x_api_key)


def _token_from_request(
    credentials: HTTPAuthorizationCredentials | None,
    cookie_token: str | None,
) -> str | None:
    if credentials and credentials.scheme.lower() == "bearer" and credentials.credentials:
        return credentials.credentials
    if cookie_token:
        return cookie_token
    return None


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
    mw_access_token: Annotated[str | None, Cookie(alias="mw_access_token")] = None,
) -> CurrentUser:
    token = _token_from_request(credentials, mw_access_token)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = auth_svc.decode_access_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    email = str(payload.get("sub", "")).lower()
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        profile = auth_svc.user_profile(email)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return CurrentUser(
        email=profile["email"],
        name=profile["name"],
        role=profile["role"],
    )


async def optional_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
    mw_access_token: Annotated[str | None, Cookie(alias="mw_access_token")] = None,
) -> CurrentUser | None:
    try:
        return await get_current_user(credentials=credentials, mw_access_token=mw_access_token)
    except HTTPException:
        return None


async def require_chatbot_user(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    return user


async def require_admin(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user
