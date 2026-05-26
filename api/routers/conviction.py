"""Conviction Engine REST routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.dependencies import optional_api_key
from api.schemas.conviction import (
    DailyPipelineRequest,
    OverlayFileRequest,
    OverlaySummaryResponse,
    SignalEvaluateRequest,
    SignalModificationResponse,
    TickerOverridesRequest,
)
from api.services import conviction_service as svc

router = APIRouter(
    prefix="/conviction",
    tags=["conviction"],
    dependencies=[Depends(optional_api_key)],
)


@router.get(
    "/tickers",
    operation_id="list_tickers",
    summary="List conviction ticker records",
)
def list_tickers(
    fs_class: str | None = Query(default=None, description="Filter by fs_class"),
    yield_trap: bool | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
    fields: str = Query(default="summary", pattern="^(summary|full)$"),
) -> list[dict[str, Any]]:
    return svc.list_ticker_records(
        fs_class=fs_class,
        yield_trap=yield_trap,
        limit=limit,
        offset=offset,
        fields=fields,
    )


@router.get(
    "/tickers/{ticker}",
    operation_id="get_ticker",
    summary="Get full conviction record for a ticker",
)
def get_ticker(ticker: str) -> dict[str, Any]:
    record = svc.get_ticker_record(ticker)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Ticker not found: {ticker}")
    return record


@router.post(
    "/tickers/{ticker}/recalculate",
    operation_id="recalculate_ticker",
    summary="Full fundamentals refresh (yfinance)",
    status_code=status.HTTP_200_OK,
)
def recalculate_ticker(ticker: str) -> dict[str, Any]:
    try:
        return svc.recalculate_ticker(ticker)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Recalculation failed for {ticker}: {exc}",
        ) from exc


@router.patch(
    "/tickers/{ticker}/daily",
    operation_id="daily_update_ticker",
    summary="Price-sensitive daily refresh",
)
def daily_update_ticker(ticker: str) -> dict[str, Any]:
    try:
        return svc.daily_refresh_ticker(ticker)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Daily update failed for {ticker}: {exc}",
        ) from exc


@router.patch(
    "/tickers/{ticker}/overrides",
    operation_id="update_ticker_overrides",
    summary="Apply manual BQ/FD/business_type overrides",
)
def update_ticker_overrides(ticker: str, body: TickerOverridesRequest) -> dict[str, Any]:
    return svc.patch_ticker_overrides(ticker, body.overrides, recompute=body.recompute)


@router.post(
    "/signals/evaluate",
    operation_id="evaluate_signal",
    response_model=SignalModificationResponse,
    summary="Score a single BUY/SELL signal",
)
def evaluate_signal(body: SignalEvaluateRequest) -> dict[str, Any]:
    try:
        return svc.evaluate_signal(
            ticker=body.ticker,
            technical_signal=body.technical_signal,
            signal_timeframe=body.signal_timeframe,
            signal_strength=body.signal_strength,
            long_position_near_stop=body.long_position_near_stop,
            persist=body.persist,
            update_layers=body.update_layers,
            quant_model_name=body.quant_model_name,
            signal_date=body.signal_date,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Signal evaluation failed: {exc}",
        ) from exc


@router.post(
    "/signals/overlay-file",
    operation_id="overlay_signal_file",
    summary="Overlay conviction scores onto a trade-store signal CSV",
)
def overlay_signal_file(body: OverlayFileRequest) -> dict[str, Any]:
    try:
        return svc.overlay_signal_file(
            report_date=body.report_date,
            report_name=body.report_name,
            save_output=body.save_output,
            update_layers=body.update_layers,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Overlay failed: {exc}",
        ) from exc


@router.get(
    "/overlays/dates",
    operation_id="list_overlay_dates",
    summary="List archived daily overlay report dates",
)
def list_overlay_dates() -> list[str]:
    return svc.get_overlay_dates()


@router.get(
    "/overlays/{report_date}/new-signals",
    operation_id="get_new_signals_overlay",
    summary="Archived New Signals conviction overlay",
)
def get_new_signals_overlay(report_date: str) -> dict[str, Any]:
    result = svc.get_new_signals_overlay(report_date)
    if result["row_count"] == 0 and result.get("overlay_file") is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No new-signals overlay for date {report_date}",
        )
    return result


@router.get(
    "/overlays/{report_date}/summary",
    operation_id="get_overlay_summary",
    response_model=OverlaySummaryResponse,
    summary="Aggregate metrics for archived New Signals overlay",
)
def get_overlay_summary(report_date: str) -> dict[str, Any]:
    summary = svc.get_overlay_summary(report_date)
    if summary.get("total_signals", 0) == 0:
        dates = svc.get_overlay_dates()
        if report_date not in dates:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No overlay snapshot for date {report_date}",
            )
    return summary


@router.get(
    "/overlays/{report_date}/score-sheet",
    operation_id="get_score_sheet",
    summary="Compact conviction score sheet for a report date",
)
def get_score_sheet(report_date: str) -> dict[str, Any]:
    result = svc.get_score_sheet(report_date)
    if result["row_count"] == 0:
        dates = svc.get_overlay_dates()
        if report_date not in dates:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No overlay snapshot for date {report_date}",
            )
    return result


@router.get(
    "/universe",
    operation_id="get_universe",
    summary="Discovered ticker universe",
)
def get_universe() -> list[str]:
    return svc.get_universe()


@router.get(
    "/coverage/pe-history",
    operation_id="get_pe_history_coverage",
    summary="P/E history coverage distribution across store",
)
def get_pe_history_coverage() -> dict[str, Any]:
    return svc.get_pe_history_coverage()


@router.post(
    "/pipeline/daily",
    operation_id="run_daily_pipeline",
    summary="Run daily conviction pipeline (fundamentals + overlays)",
)
def run_daily_pipeline(body: DailyPipelineRequest) -> dict[str, Any]:
    try:
        result = svc.run_pipeline(
            report_date=body.report_date,
            fundamentals_mode=body.fundamentals_mode,
            skip_fundamentals=body.skip_fundamentals,
            skip_overlays=body.skip_overlays,
            dry_run=body.dry_run,
            fail_fast=body.fail_fast,
            limit=body.limit,
            overlay_reports=body.overlay_reports,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Pipeline failed: {exc}",
        ) from exc
    if result.get("status") == "error":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("error", "Pipeline error"))
    return result


@router.get(
    "/alerts/daily",
    operation_id="get_daily_alerts",
    summary="Fundamental alert map and daily report text",
)
def get_daily_alerts() -> dict[str, Any]:
    return svc.get_daily_alerts()
