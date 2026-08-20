"""SSI daily job — write positioning.json (~08:00 ET)."""

from __future__ import annotations

import logging
from typing import Any

from src.sentiment_superindex.db.connection import init_db, persist_daily
from src.sentiment_superindex.engine.positioning import build_positioning_payload
from src.sentiment_superindex.output.json_writer import write_positioning_json

logger = logging.getLogger("ssi.daily")


def log_coverage(payload: dict[str, Any]) -> bool:
    """Report per-layer input coverage. Returns True when every layer is reliable.

    The payload has always described its own gaps in ``signal_coverage``; nothing ever read
    them, which is how NAAIM and ^VIX3M stayed dead for weeks behind a log containing only
    pandas warnings (audit 2026-08-18). This turns that existing structure into output.
    """
    healthy = True
    for layer_key, layer in (payload.get("layers") or {}).items():
        coverage = layer.get("signal_coverage") or {}
        if not coverage:
            continue
        available = coverage.get("available_count")
        configured = coverage.get("configured_count")
        missing = coverage.get("missing") or []
        expired = coverage.get("expired") or []
        if coverage.get("reliable", True):
            level = logger.warning if missing or expired else logger.info
            level(
                "SSI %s: %s/%s inputs%s",
                layer_key,
                available,
                configured,
                f" -- missing {missing}" if missing else "",
            )
        else:
            healthy = False
            logger.error(
                "SSI %s UNRELIABLE: %s/%s inputs -- %s (missing %s, expired %s)",
                layer_key,
                available,
                configured,
                coverage.get("unreliable_reason"),
                missing,
                expired,
            )
    if not payload.get("coverage_ok", True):
        logger.error(
            "SSI size multiplier forced to neutral %.2fx by the coverage gate",
            payload.get("ssi_multiplier", 1.0),
        )
    return healthy


def run_ssi_daily(as_of: str | None = None) -> dict[str, Any]:
    init_db()
    payload = build_positioning_payload(as_of)
    path = write_positioning_json(payload)
    persist_daily(payload)
    payload["output_path"] = str(path)
    payload["coverage_healthy"] = log_coverage(payload)
    return payload
