"""Trade-store report REST routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.dependencies import optional_api_key
from api.services import reports_service as svc

router = APIRouter(prefix="/signals", tags=["signals"], dependencies=[Depends(optional_api_key)])


@router.get("/reports", operation_id="list_signal_reports")
def list_reports() -> list[dict[str, Any]]:
    return svc.list_available_reports()


@router.get("/reports/{report_name}/latest", operation_id="get_latest_signal_report")
def get_latest_report(report_name: str) -> dict[str, Any]:
    try:
        return svc.load_report_records(report_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/reports/{report_name}/{report_date}", operation_id="get_dated_signal_report")
def get_dated_report(report_name: str, report_date: str) -> dict[str, Any]:
    try:
        return svc.load_report_records(report_name, report_date=report_date)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/shortlist", operation_id="get_claude_shortlist")
def get_shortlist() -> dict[str, Any]:
    return svc.get_shortlist_report()


@router.get("/strategy-health", operation_id="get_strategy_health")
def get_strategy_health(
    report_date: str | None = Query(default=None, description="YYYY-MM-DD trade_store date"),
) -> dict[str, Any]:
    try:
        return svc.strategy_health_report(report_date=report_date)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
