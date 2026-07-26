"""Capital allocation dimension — float reduction / buyback scoring."""

from __future__ import annotations

from typing import Any

from .scoring import _float_or_none


def buyback_score_0_10(buyback_pct: float) -> int:
    """buyback_pct = (shares_12m_ago - shares_now) / shares_12m_ago"""
    if buyback_pct >= 0.07:
        return 9
    if buyback_pct >= 0.01:
        return 8
    if buyback_pct >= 0.005:
        return 6
    if buyback_pct >= 0.0:
        return 4
    if buyback_pct >= -0.02:
        return 2
    return 0


def score_0_10_to_bq(score_10: float) -> float:
    if score_10 >= 8:
        return 2.0
    if score_10 >= 6:
        return 1.0
    if score_10 >= 3:
        return 0.0
    return -1.0


def compute_buyback_pct(fundamentals: dict[str, Any], info: dict[str, Any] | None = None) -> float | None:
    """Shares retired over trailing 12 months."""
    info = info or {}
    change = _float_or_none(fundamentals.get("shares_outstanding_change_pct"))
    if change is not None:
        return -change  # negative change_pct means shares down → positive buyback

    shares_now = _float_or_none(fundamentals.get("shares_outstanding_now") or info.get("sharesOutstanding"))
    shares_12m = _float_or_none(fundamentals.get("shares_outstanding_12m_ago"))
    if shares_now and shares_12m and shares_12m > 0:
        return (shares_12m - shares_now) / shares_12m
    return None


def score_capital_allocation(
    fundamentals: dict[str, Any],
    overrides: dict[str, Any] | None = None,
    info: dict[str, Any] | None = None,
) -> tuple[float, dict[str, Any]]:
    overrides = overrides or {}
    if overrides.get("mgmt_alloc_score") is not None:
        from .scoring import score_manual

        return score_manual("mgmt_alloc_score", overrides), {}

    buyback_pct = compute_buyback_pct(fundamentals, info)
    if buyback_pct is None:
        return 0.0, {}
    score_10 = buyback_score_0_10(buyback_pct)
    return score_0_10_to_bq(float(score_10)), {
        "buyback_pct": round(buyback_pct, 4),
        "score_0_10": score_10,
    }
