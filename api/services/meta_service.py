"""Report meta: market-close data_updated_at and source file paths."""

from __future__ import annotations

from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from api.services.reports_service import _report_date_from_path, resolve_report_path
from src.config_paths import DATA_FETCH_DATETIME_JSON
from src.utils.helpers import get_data_fetch_datetime

US_EASTERN = ZoneInfo("America/New_York")
MARKET_CLOSE = time(16, 0, 0)


def market_close_data_updated_at(report_date: str) -> dict[str, str]:
    """Return data_updated_at for US market close (4:00 PM) on report_date."""
    day = datetime.strptime(report_date, "%Y-%m-%d").date()
    close_dt = datetime.combine(day, MARKET_CLOSE, tzinfo=US_EASTERN)
    return {
        "date": report_date,
        "time": "16:00:00",
        "datetime": close_dt.isoformat(),
        "timezone": "US/Eastern",
    }


def resolve_report_date() -> str | None:
    """Report date from data_fetch_datetime.json, else latest outstanding_signal CSV."""
    fetch = get_data_fetch_datetime(str(DATA_FETCH_DATETIME_JSON))
    if fetch and fetch.get("date"):
        return str(fetch["date"])
    path = resolve_report_path("outstanding_signal")
    if path:
        return _report_date_from_path(path)
    return None


def get_meta() -> dict[str, Any]:
    report_date = resolve_report_date()
    data_updated_at = market_close_data_updated_at(report_date) if report_date else None
    source_files: dict[str, str] = {}
    path = resolve_report_path("outstanding_signal")
    if path:
        source_files["outstanding_signal"] = str(path)
    return {
        "data_updated_at": data_updated_at,
        "market_label": "US Market",
        "source_files": source_files or None,
    }
