"""Analytics REST routes (sigma, sentiment, performance, YTD, AI Analyst)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from api.dependencies import optional_api_key
from api.schemas.analyst import AnalystAlertsResponse, AnalystBriefResponse
from api.services import analyst_service as analyst_svc
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


@router.get(
    "/analyst/alerts",
    operation_id="get_analyst_alerts",
    summary="AI Analyst Overwatch panel alerts",
    response_model=AnalystAlertsResponse,
)
def get_analyst_alerts(
    include_macro: bool = Query(default=True),
    include_degradation: bool = Query(default=True),
    floor_pct: float = Query(default=60.0, ge=0, le=100),
    gap_threshold_pp: float = Query(default=10.0, ge=0),
    since: str | None = Query(default=None, description="ISO datetime — only alerts after"),
) -> dict[str, Any]:
    return analyst_svc.get_panel_alerts(
        include_macro=include_macro,
        include_degradation=include_degradation,
        floor_pct=floor_pct,
        gap_threshold_pp=gap_threshold_pp,
        since=since,
    )


@router.get(
    "/analyst/brief",
    operation_id="get_analyst_brief",
    summary="Dashboard AI analyst snippet",
    response_model=AnalystBriefResponse,
)
def get_analyst_brief() -> dict[str, Any]:
    return analyst_svc.get_analyst_brief()
