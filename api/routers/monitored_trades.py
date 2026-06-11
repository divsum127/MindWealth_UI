"""Monitored trades REST routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from api.dependencies import optional_api_key
from api.services import reports_service as svc

router = APIRouter(prefix="/monitored-trades", tags=["monitored-trades"], dependencies=[Depends(optional_api_key)])


@router.get("", operation_id="list_monitored_trades")
def list_trades(refresh_prices: bool = Query(default=False)) -> list[dict[str, Any]]:
    return svc.list_monitored_trades(refresh_prices=refresh_prices)


@router.post("", operation_id="create_monitored_trade", status_code=status.HTTP_201_CREATED)
def create_trade(body: dict[str, Any]) -> dict[str, Any]:
    try:
        return svc.create_monitored_trade(body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete("/{trade_id}", operation_id="delete_monitored_trade", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_trade(trade_id: str) -> Response:
    if not svc.delete_monitored_trade(trade_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
