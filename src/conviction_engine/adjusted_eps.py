"""Adjusted EPS + materiality-gated adjusted-PE substitution (items 10-11).

Strips one-off items from trailing EPS using the company's own trailing effective
tax rate (Q9 answer — more precise than the original plan's flat 21%/25% rate):

    effective_tax_rate = trailing-4Q tax provision / trailing-4Q pretax income

both already available in the same ``quarterly_income_stmt`` pull made for every
other BQ dimension — zero new data source. Falls back to a flat 21% rate only when
pretax income is zero/negative/missing (documented edge case, not a live-data gap).

The materiality gate (Q10 answer, confirms the original plan): Adjusted PE only
substitutes for raw PE in the ``pe_percentile_20y`` calculation when one-off items
exceed 5% of trailing net income — otherwise the raw ``pe_ttm`` keeps being used,
so small noise-level one-offs never move the percentile ranking.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

FLAT_TAX_RATE_FALLBACK = 0.21
MATERIALITY_THRESHOLD_PCT_OF_NI = 0.05


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ttm_sum(df: pd.DataFrame | None, *row_labels: str) -> float | None:
    if df is None or getattr(df, "empty", True):
        return None
    for label in row_labels:
        if label not in df.index:
            continue
        row = df.loc[label].dropna().sort_index()
        if row.empty:
            continue
        try:
            return float(row.iloc[-4:].sum())
        except (TypeError, ValueError):
            continue
    return None


def compute_effective_tax_rate(q_inc: pd.DataFrame | None) -> tuple[float, bool]:
    """Trailing-4Q tax provision / trailing-4Q pretax income.

    Returns ``(rate, is_fallback)`` — ``is_fallback`` is True when the flat 21%
    fallback was used because pretax income was zero/negative/missing.
    """
    tax_provision = _ttm_sum(q_inc, "Tax Provision", "Income Tax Expense")
    pretax_income = _ttm_sum(q_inc, "Pretax Income", "Income Before Tax")
    if tax_provision is None or pretax_income is None or pretax_income <= 0:
        return FLAT_TAX_RATE_FALLBACK, True
    rate = tax_provision / pretax_income
    # Sanity-clamp: extreme quarters (e.g. one-time tax credits) can produce a
    # nonsensical effective rate; fall back rather than propagate a bad number.
    if rate < 0 or rate > 0.6:
        return FLAT_TAX_RATE_FALLBACK, True
    return rate, False


def compute_one_off_items_ttm(q_inc: pd.DataFrame | None) -> float | None:
    """Pre-tax trailing-4Q "Total Unusual Items" — yfinance's own catch-all row for
    exactly this purpose (restructuring, gains/losses on sale, impairments, etc.)."""
    return _ttm_sum(q_inc, "Total Unusual Items", "Unusual Items")


def compute_adjusted_eps_bundle(
    fundamentals: dict[str, Any],
    q_inc: pd.DataFrame | None,
) -> dict[str, Any]:
    """Compute adjusted EPS + materiality-gated adjusted PE for a ticker.

    Returns an empty dict when there isn't enough data to compute anything
    (never raises) — callers should keep raw ``eps_ttm``/``pe_ttm`` in that case.
    """
    net_income_ttm = _float_or_none(fundamentals.get("net_income_ttm"))
    shares = _float_or_none(fundamentals.get("shares_outstanding_now"))
    price = _float_or_none(fundamentals.get("price"))
    one_off_pretax = compute_one_off_items_ttm(q_inc)

    if net_income_ttm is None or not shares or one_off_pretax is None:
        return {}

    effective_tax_rate, _is_fallback = compute_effective_tax_rate(q_inc)
    one_off_after_tax = one_off_pretax * (1.0 - effective_tax_rate)
    adjusted_net_income = net_income_ttm - one_off_after_tax
    adjusted_eps = adjusted_net_income / shares

    one_off_pct_of_ni = abs(one_off_after_tax) / abs(net_income_ttm) if net_income_ttm else None
    materiality_gate_fired = bool(one_off_pct_of_ni is not None and one_off_pct_of_ni > MATERIALITY_THRESHOLD_PCT_OF_NI)

    result: dict[str, Any] = {
        "adjusted_eps_ttm": round(adjusted_eps, 4),
        "one_off_pct_of_ni": round(one_off_pct_of_ni, 4) if one_off_pct_of_ni is not None else None,
        "effective_tax_rate": round(effective_tax_rate, 4),
    }

    if materiality_gate_fired and price and adjusted_eps > 0:
        result["pe_ttm_adjusted"] = round(price / adjusted_eps, 4)

    return result
