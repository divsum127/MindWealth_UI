"""System health REST routes (admin)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from api.dependencies import CurrentUser, optional_api_key, require_admin
from api.schemas.analyst import SystemHealthResponse
from api.services import system_health_service as health_svc

router = APIRouter(
    prefix="/system",
    tags=["system"],
    dependencies=[Depends(optional_api_key)],
)


@router.get(
    "/health",
    operation_id="get_system_health",
    summary="AI Analyst system health checks (admin)",
    response_model=SystemHealthResponse,
)
def get_system_health(
    _admin: CurrentUser = Depends(require_admin),
) -> dict[str, Any]:
    from api.main import API_VERSION  # noqa: PLC0415

    return health_svc.run_system_health(API_VERSION)
