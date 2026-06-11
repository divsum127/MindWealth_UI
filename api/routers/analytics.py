"""Analytics REST routes (sigma, sentiment, performance, YTD)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from api.dependencies import optional_api_key
from api.services import reports_service as svc

router = APIRouter(prefix="/analytics", tags=["analytics"], dependencies=[Depends(optional_api_key)])


@router.get("/sigma", operation_id="get_sigma_report")
def get_sigma() -> dict[str, Any]:
    return svc.latest_sigma()


@router.get("/sentiment", operation_id="get_sentiment_signals")
def get_sentiment() -> dict[str, Any]:
    return svc.latest_sentiment_signals()


@router.get("/sentiment/layers", operation_id="get_sentiment_layers")
def get_sentiment_layers() -> dict[str, Any]:
    return svc.sentiment_layers()


@router.get("/performance", operation_id="get_performance_summary")
def get_performance() -> dict[str, Any]:
    return svc.performance_summary()


@router.get("/portfolio-ytd", operation_id="get_portfolio_ytd")
def get_portfolio_ytd() -> dict[str, Any]:
    return svc.forced_portfolio_ytd()
