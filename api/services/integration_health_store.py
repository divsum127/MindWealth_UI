"""Persist integration timestamps for system health checks."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config_paths import BASE_DIR, CHATBOT_DATA_DIR, CONVICTION_DAILY_DIR, CONVICTION_STORE_DIR

TAVILY_MARKER = CHATBOT_DATA_DIR / ".last_tavily_search.json"
SHEETS_MARKER = CONVICTION_STORE_DIR / ".last_sheets_sync"


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_marker(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _read_marker(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def record_tavily_search(*, latency_ms: int, success: bool = True, query: str = "") -> None:
    _write_marker(
        TAVILY_MARKER,
        {
            "last_success_at": _utc_iso() if success else None,
            "last_attempt_at": _utc_iso(),
            "latency_ms": latency_ms,
            "success": success,
            "query": query[:120],
        },
    )


def record_sheets_sync(*, source: str = "conviction_daily") -> None:
    _write_marker(
        SHEETS_MARKER,
        {
            "last_success_at": _utc_iso(),
            "source": source,
        },
    )


def latest_conviction_daily_mtime() -> float | None:
    if not CONVICTION_DAILY_DIR.exists():
        return None
    mtimes = [p.stat().st_mtime for p in CONVICTION_DAILY_DIR.iterdir() if p.is_dir()]
    return max(mtimes) if mtimes else None


def tavily_health_info() -> dict[str, Any]:
    marker = _read_marker(TAVILY_MARKER)
    if marker and marker.get("last_success_at"):
        age_h = (time.time() - datetime.fromisoformat(
            marker["last_success_at"].replace("Z", "+00:00")
        ).timestamp()) / 3600
        return {
            "name": "Tavily",
            "status": "ok" if marker.get("success", True) else "fail",
            "detail": f"last search {int(age_h * 60)}m ago · {marker.get('latency_ms', '?')}ms",
            "last_success_at": marker.get("last_success_at"),
        }
    return {
        "name": "Tavily",
        "status": "warn",
        "detail": "no successful search recorded",
        "last_success_at": None,
    }


def sheets_health_info() -> dict[str, Any]:
    marker = _read_marker(SHEETS_MARKER)
    if marker and marker.get("last_success_at"):
        return {
            "name": "Google Sheets sync",
            "status": "ok",
            "detail": f"synced via {marker.get('source', 'unknown')}",
            "last_success_at": marker.get("last_success_at"),
        }
    daily_mtime = latest_conviction_daily_mtime()
    if daily_mtime:
        age_h = (time.time() - daily_mtime) / 3600
        status = "ok" if age_h <= 48 else ("warn" if age_h <= 96 else "fail")
        return {
            "name": "Google Sheets sync",
            "status": status,
            "detail": f"conviction daily archive {age_h:.1f}h ago (proxy)",
            "last_success_at": datetime.fromtimestamp(daily_mtime, tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
        }
    return {
        "name": "Google Sheets sync",
        "status": "warn",
        "detail": "no sync marker or daily archive",
        "last_success_at": None,
    }
