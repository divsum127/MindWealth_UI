"""Divergence signal state — persistent days_below_high counter (July 2026 spec)."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

logger = logging.getLogger(__name__)


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def bootstrap_days_below_from_history(
    *,
    price_history: Any,
    fifty_two_week_high: float | None,
    current_price: float | None,
) -> int:
    """One-time bootstrap of days_below when no persisted state exists."""
    if current_price is None or fifty_two_week_high is None or fifty_two_week_high <= 0:
        return 0
    threshold = fifty_two_week_high * 0.85
    if current_price > threshold:
        return 0
    try:
        import pandas as pd

        series = price_history["Close"] if isinstance(price_history, pd.DataFrame) else price_history
        if not hasattr(series, "dropna"):
            return 0
        clean = series.dropna().sort_index()
        if clean.empty:
            return 0
        above = clean >= threshold
        if not above.any():
            return len(clean)
        last_above = clean.index[above][-1]
        return max(0, (clean.index[-1] - last_above).days)
    except Exception:
        return 0


def update_divergence_state(
    record: dict[str, Any],
    *,
    current_price: float | None,
    fifty_two_week_high: float | None,
    as_of: date | None = None,
) -> dict[str, Any]:
    """
    Persist days_below_high in conviction_store JSON.

    Counter increments on each daily run while price stays >=15% below 52W high;
  resets when price recovers above the 85% threshold.
    """
    today = (as_of or date.today()).isoformat()
    state = dict(record.get("divergence_state") or {})
    prev_days = int(state.get("days_below_high") or 0)
    prev_date = state.get("last_check_date")

    if current_price is None or fifty_two_week_high is None or fifty_two_week_high <= 0:
        state.update(
            {
                "days_below_high": prev_days,
                "last_check_date": today,
                "last_price": current_price,
                "last_52w_high": fifty_two_week_high,
            }
        )
        record["divergence_state"] = state
        record["days_below_high"] = prev_days
        return state

    threshold = fifty_two_week_high * 0.85
    below = current_price <= threshold

    if not below:
        days = 0
    elif prev_date == today:
        days = prev_days
    else:
        days = prev_days + 1

    state.update(
        {
            "days_below_high": days,
            "last_check_date": today,
            "last_price": current_price,
            "last_52w_high": fifty_two_week_high,
            "pct_below": round((fifty_two_week_high - current_price) / fifty_two_week_high, 4) if below else 0.0,
        }
    )
    record["divergence_state"] = state
    record["days_below_high"] = days
    return state


def detect_divergence_signal(
    *,
    current_price: float | None,
    fifty_two_week_high: float | None,
    days_below_high: int | None = None,
    fd_direction: str | None = None,
    manual_flag: bool | None = None,
    ticker: str | None = None,
) -> bool:
    """True when price >=15% below 52W high for >=60 persisted days and fd != negative."""
    if manual_flag is True:
        return True
    if manual_flag is False:
        return False
    if str(fd_direction or "").lower() == "negative":
        return False
    if current_price is None or fifty_two_week_high is None or fifty_two_week_high <= 0:
        return False

    threshold = fifty_two_week_high * 0.85
    if current_price > threshold:
        return False

    pct_below = (fifty_two_week_high - current_price) / fifty_two_week_high
    days = int(days_below_high or 0)

    if ticker:
        logger.info(
            "[divergence] %s: price=%s, 52Wh=%s, pct_below=%.1f%%, days=%s",
            ticker,
            current_price,
            fifty_two_week_high,
            pct_below * 100,
            days,
        )

    return days >= 60
