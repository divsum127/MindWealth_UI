"""Authenticated user activity ingestion."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from api.dependencies import CurrentUser, get_current_user, require_api_key
from api.schemas.activity import ActivityEventBatch
from api.services import activity_log_service as activity_svc

router = APIRouter(
    prefix="/activity",
    tags=["activity"],
    dependencies=[Depends(require_api_key)],
)


@router.post("/events", operation_id="ingest_activity_events")
def ingest_activity_events(
    body: ActivityEventBatch,
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> JSONResponse:
    if not activity_svc.is_activity_logging_enabled(user.email):
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "skipped", "written": 0, "reason": "logging_disabled"},
        )
    written = activity_svc.ingest_client_events(
        user.email,
        [event.model_dump() for event in body.events],
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "ok", "written": written},
    )
