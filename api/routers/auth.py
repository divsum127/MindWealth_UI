"""Authentication and user admin routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import CurrentUser, get_current_user, require_admin, require_api_key
from api.schemas.auth import (
    AcceptInviteRequest,
    AdminInviteRequest,
    AdminInviteResponse,
    AdminUserPatchRequest,
    AdminUserSummary,
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    UserProfile,
)
from api.services import auth_service as auth_svc

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
    dependencies=[Depends(require_api_key)],
)


@router.post("/login", operation_id="auth_login", response_model=LoginResponse)
def login(body: LoginRequest) -> LoginResponse:
    try:
        payload = auth_svc.login(body.email, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return LoginResponse(**payload)


@router.post("/logout", operation_id="auth_logout")
def logout() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/me", operation_id="auth_me", response_model=UserProfile)
def me_profile(user: Annotated[CurrentUser, Depends(get_current_user)]) -> UserProfile:
    try:
        profile = auth_svc.user_profile(user.email)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return UserProfile(**profile)


@router.post("/accept-invite", operation_id="auth_accept_invite", response_model=LoginResponse)
def accept_invite(body: AcceptInviteRequest) -> LoginResponse:
    try:
        payload = auth_svc.accept_invite(body.token, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return LoginResponse(**payload)


@router.post("/change-password", operation_id="auth_change_password")
def change_password(
    body: ChangePasswordRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, str]:
    try:
        auth_svc.change_password(user.email, body.current_password, body.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"status": "ok"}


@router.post(
    "/admin/invite",
    operation_id="auth_admin_invite",
    response_model=AdminInviteResponse,
)
def admin_invite(
    body: AdminInviteRequest,
    _admin: Annotated[CurrentUser, Depends(require_admin)],
) -> AdminInviteResponse:
    try:
        payload = auth_svc.admin_invite(email=body.email, name=body.name, role=body.role)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return AdminInviteResponse(**payload)


@router.get(
    "/admin/users",
    operation_id="auth_admin_list_users",
    response_model=list[AdminUserSummary],
)
def admin_list_users(_admin: Annotated[CurrentUser, Depends(require_admin)]) -> list[AdminUserSummary]:
    return [AdminUserSummary(**row) for row in auth_svc.admin_list_users()]


@router.patch("/admin/users/{email}", operation_id="auth_admin_patch_user")
def admin_patch_user(
    email: str,
    body: AdminUserPatchRequest,
    _admin: Annotated[CurrentUser, Depends(require_admin)],
) -> dict:
    try:
        return auth_svc.admin_patch_user(
            email,
            status=body.status,
            resend_invite=body.resend_invite,
            name=body.name,
            role=body.role,
            activity_logging_enabled=body.activity_logging_enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
