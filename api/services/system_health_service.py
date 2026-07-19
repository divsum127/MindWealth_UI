"""System health checks for AI Analyst SYSTEM tab (admin only)."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from src.config_paths import (
    BASE_DIR,
    DATA_FETCH_DATETIME_JSON,
    MACRO_INTEL_JSON_PATH,
    MINDWEALTH_ROOT,
    SSI_POSITIONING_JSON,
    TRADE_STORE_DIR,
)

CheckStatus = Literal["ok", "warn", "fail"]

_US_EXPECTED_HOURS = 24
_IN_EXPECTED_HOURS = 24
_WARN_MULTIPLIER = 2.0


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _file_age_hours(path: Path) -> float | None:
    if not path.exists():
        return None
    mtime = path.stat().st_mtime
    return (time.time() - mtime) / 3600.0


def _status_from_age(age_hours: float | None, expected_hours: float) -> CheckStatus:
    if age_hours is None:
        return "fail"
    if age_hours <= expected_hours:
        return "ok"
    if age_hours <= expected_hours * _WARN_MULTIPLIER:
        return "warn"
    return "fail"


def _detail_from_age(age_hours: float | None) -> str:
    if age_hours is None:
        return "unavailable"
    if age_hours < 1:
        return f"{int(age_hours * 60)}m ago"
    return f"{age_hours:.1f}h ago"


def _check_us_csv_pipeline() -> dict[str, Any]:
    age = _file_age_hours(DATA_FETCH_DATETIME_JSON)
    status = _status_from_age(age, _US_EXPECTED_HOURS)
    last_at = None
    if DATA_FETCH_DATETIME_JSON.exists():
        try:
            payload = json.loads(DATA_FETCH_DATETIME_JSON.read_text(encoding="utf-8"))
            last_at = payload.get("datetime") or payload.get("last_updated")
        except Exception:
            last_at = _iso(datetime.fromtimestamp(DATA_FETCH_DATETIME_JSON.stat().st_mtime, tz=timezone.utc))
    return {
        "name": "US CSV pipeline",
        "status": status,
        "detail": _detail_from_age(age),
        "last_success_at": last_at,
    }


def _check_india_csv_pipeline() -> dict[str, Any]:
    india_json = TRADE_STORE_DIR / "India" / "data_fetch_datetime.json"
    if not india_json.exists():
        india_json = MINDWEALTH_ROOT / "trade_store" / "India" / "data_fetch_datetime.json"
    age = _file_age_hours(india_json)
    status = _status_from_age(age, _IN_EXPECTED_HOURS) if india_json.exists() else "fail"
    return {
        "name": "India CSV pipeline",
        "status": status,
        "detail": _detail_from_age(age) if india_json.exists() else "path not found",
        "last_success_at": _iso(datetime.fromtimestamp(india_json.stat().st_mtime, tz=timezone.utc))
        if india_json.exists()
        else None,
    }


def _check_claude_api() -> dict[str, Any]:
    api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
    if not api_key:
        return {
            "name": "Claude API",
            "status": "fail",
            "detail": "ANTHROPIC_API_KEY not configured",
            "last_success_at": None,
        }
    try:
        import anthropic

        start = time.perf_counter()
        client = anthropic.Anthropic(api_key=api_key)
        client.models.list(limit=1)
        ms = int((time.perf_counter() - start) * 1000)
        return {
            "name": "Claude API",
            "status": "ok",
            "detail": f"reachable · {ms}ms",
            "last_success_at": _iso(_utc_now()),
        }
    except Exception as exc:
        return {
            "name": "Claude API",
            "status": "fail",
            "detail": str(exc)[:120],
            "last_success_at": None,
        }


def _check_tavily() -> dict[str, Any]:
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return {
            "name": "Tavily",
            "status": "warn",
            "detail": "TAVILY_API_KEY not configured",
            "last_success_at": None,
        }
    try:
        from tavily import TavilyClient

        start = time.perf_counter()
        TavilyClient(api_key=api_key).search(query="SPX", max_results=1)
        ms = int((time.perf_counter() - start) * 1000)
        return {
            "name": "Tavily",
            "status": "ok",
            "detail": f"reachable · {ms}ms",
            "last_success_at": _iso(_utc_now()),
        }
    except Exception as exc:
        return {
            "name": "Tavily",
            "status": "fail",
            "detail": str(exc)[:120],
            "last_success_at": None,
        }


def _check_google_sheets_sync() -> dict[str, Any]:
    sync_marker = BASE_DIR / "conviction_store" / ".last_sheets_sync"
    age = _file_age_hours(sync_marker)
    if sync_marker.exists():
        status = _status_from_age(age, 48)
        return {
            "name": "Google Sheets sync",
            "status": status,
            "detail": _detail_from_age(age),
            "last_success_at": _iso(datetime.fromtimestamp(sync_marker.stat().st_mtime, tz=timezone.utc)),
        }
    return {
        "name": "Google Sheets sync",
        "status": "warn",
        "detail": "sync marker not tracked",
        "last_success_at": None,
    }


def _check_macro_agent() -> dict[str, Any]:
    age = _file_age_hours(MACRO_INTEL_JSON_PATH)
    status = _status_from_age(age, 36)
    return {
        "name": "Macro agent",
        "status": status,
        "detail": _detail_from_age(age),
        "last_success_at": _iso(datetime.fromtimestamp(MACRO_INTEL_JSON_PATH.stat().st_mtime, tz=timezone.utc))
        if MACRO_INTEL_JSON_PATH.exists()
        else None,
    }


def _check_ssi_json_write() -> dict[str, Any]:
    age = _file_age_hours(SSI_POSITIONING_JSON)
    status = _status_from_age(age, 36)
    return {
        "name": "SSI JSON write",
        "status": status,
        "detail": _detail_from_age(age),
        "last_success_at": _iso(datetime.fromtimestamp(SSI_POSITIONING_JSON.stat().st_mtime, tz=timezone.utc))
        if SSI_POSITIONING_JSON.exists()
        else None,
    }


def _aggregate_status(checks: list[dict[str, Any]]) -> CheckStatus:
    statuses = [c.get("status") for c in checks]
    if "fail" in statuses:
        return "fail"
    if "warn" in statuses:
        return "warn"
    return "ok"


def run_system_health(version: str) -> dict[str, Any]:
    checks = [
        _check_us_csv_pipeline(),
        _check_india_csv_pipeline(),
        _check_claude_api(),
        _check_tavily(),
        _check_google_sheets_sync(),
        _check_macro_agent(),
        _check_ssi_json_write(),
    ]
    return {
        "status": _aggregate_status(checks),
        "version": version,
        "checked_at": _iso(_utc_now()) or "",
        "checks": checks,
    }


def system_checks_to_panel_alerts(checks: list[dict[str, Any]], checked_at: str) -> list[dict[str, Any]]:
    """Convert non-ok system checks into panel alerts for SYSTEM tab."""
    alerts: list[dict[str, Any]] = []
    for check in checks:
        if check.get("status") == "ok":
            continue
        name = check.get("name", "System")
        alerts.append({
            "id": f"system-{name.lower().replace(' ', '-')}",
            "type": "system",
            "label": "SYSTEM HEALTH · INTERNAL MONITOR",
            "html": f"{name}: {check.get('detail', '')}",
            "created_at": checked_at,
            "border_color": "#252525",
        })
    return alerts
