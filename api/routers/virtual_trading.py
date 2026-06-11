"""Virtual trading portfolio REST routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import optional_api_key
from api.services import reports_service as svc

router = APIRouter(prefix="/virtual-trading", tags=["virtual-trading"], dependencies=[Depends(optional_api_key)])


@router.get("/long", operation_id="get_virtual_trading_long")
def get_long() -> dict[str, Any]:
    return svc.load_virtual_trading("long")


@router.get("/short", operation_id="get_virtual_trading_short")
def get_short() -> dict[str, Any]:
    return svc.load_virtual_trading("short")


@router.get("/portfolio", operation_id="get_portfolio_summary")
def get_portfolio() -> dict[str, Any]:
    return svc.portfolio_summary()
