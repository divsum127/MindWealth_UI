"""Report meta REST routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.dependencies import require_api_key
from api.schemas.meta import MetaResponse
from api.services import meta_service as meta_svc

router = APIRouter(prefix="/meta", tags=["meta"], dependencies=[Depends(require_api_key)])


@router.get("", operation_id="get_meta", response_model=MetaResponse)
def get_meta() -> MetaResponse:
    return MetaResponse(**meta_svc.get_meta())
