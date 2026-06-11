"""Retry and last-known-good cache for BLS/CFTC and other shutdown-prone sources."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable, TypeVar

from src.macro_intelligence.db.connection import get_connection

T = TypeVar("T")


def log_pull(source_id: str, status: str, last_good: Any = None, error: str | None = None) -> None:
    payload = None if last_good is None else json.dumps(last_good, default=str)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO data_pull_log (source_id, pulled_at, status, last_good_value, error_message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (source_id, datetime.now(timezone.utc).isoformat(), status, payload, error),
        )


def get_last_good(source_id: str) -> Any | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT last_good_value FROM data_pull_log
            WHERE source_id=? AND status='OK' AND last_good_value IS NOT NULL
            ORDER BY log_id DESC LIMIT 1
            """,
            (source_id,),
        ).fetchone()
    if not row or not row["last_good_value"]:
        return None
    try:
        return json.loads(row["last_good_value"])
    except json.JSONDecodeError:
        return row["last_good_value"]


def pull_with_cache(
    source_id: str,
    fetch_fn: Callable[[], T],
    *,
    serialize: Callable[[T], Any] | None = None,
) -> T | None:
    """Run fetch; on failure return last good value and log — never propagate NULL writes."""
    try:
        result = fetch_fn()
        if result is None:
            raise ValueError("fetch returned None")
        log_pull(source_id, "OK", serialize(result) if serialize else result)
        return result
    except Exception as exc:
        log_pull(source_id, "ERROR", error=str(exc))
        cached = get_last_good(source_id)
        if cached is not None:
            log_pull(source_id, "CACHE_HIT", cached)
        return cached  # type: ignore[return-value]
