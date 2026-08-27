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


def _ttm_sum(df: pd.DataFrame | None, *row_labels: str, periods: int = 4) -> float | None:
    """Sum the last ``periods`` reported columns of the first matching row label."""
    if df is None or getattr(df, "empty", True):
        return None
    for label in row_labels:
        if label not in df.index:
            continue
        row = df.loc[label].dropna().sort_index()
        if row.empty:
            continue
        try:
            return float(row.iloc[-periods:].sum())
        except (TypeError, ValueError):
            continue
    return None


def compute_effective_tax_rate(
    q_inc: pd.DataFrame | None,
    periods: int = 4,
) -> tuple[float, bool]:
    """Tax provision / pretax income over the trailing ``periods`` columns.

    ``periods`` is 4 for quarterly filers and 1 for the annual fallback used by
    semi-annual filers (see ``compute_adjusted_eps_bundle``).

    Returns ``(rate, is_fallback)`` — ``is_fallback`` is True when the flat 21%
    fallback was used because pretax income was zero/negative/missing.
    """
    tax_provision = _ttm_sum(q_inc, "Tax Provision", "Income Tax Expense", periods=periods)
    pretax_income = _ttm_sum(q_inc, "Pretax Income", "Income Before Tax", periods=periods)
    if tax_provision is None or pretax_income is None or pretax_income <= 0:
        return FLAT_TAX_RATE_FALLBACK, True
    rate = tax_provision / pretax_income
    # Sanity-clamp: extreme quarters (e.g. one-time tax credits) can produce a
    # nonsensical effective rate; fall back rather than propagate a bad number.
    if rate < 0 or rate > 0.6:
        return FLAT_TAX_RATE_FALLBACK, True
    return rate, False


def compute_one_off_items_ttm(q_inc: pd.DataFrame | None, periods: int = 4) -> float | None:
    """Pre-tax "Total Unusual Items" over the trailing ``periods`` columns — yfinance's
    own catch-all row for exactly this purpose (restructuring, gains/losses on sale,
    impairments, etc.)."""
    return _ttm_sum(q_inc, "Total Unusual Items", "Unusual Items", periods=periods)


def compute_adjusted_eps_bundle(
    fundamentals: dict[str, Any],
    q_inc: pd.DataFrame | None,
    annual_inc: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Compute adjusted EPS + materiality-gated adjusted PE for a ticker.

    Quarterly filers use the trailing four quarters. Semi-annual filers (NZX, ASX and
    most of Europe) have no quarterly income statement at all — yfinance returns an
    empty frame — so the latest full financial year is used instead, and the basis is
    published in ``adjusted_eps_basis`` so nobody reads an FY number as a TTM one.
    SPK.NZ is the case that forced this: reported FY26 EPS 26.4c against 11.9c
    adjusted, a reported P/E of 8.3x against a real 18.4x, on a single disclosed
    line item (Rohit 26 Aug, conviction spec gap 1).

    Returns an empty dict when there isn't enough data to compute anything
    (never raises) — callers should keep raw ``eps_ttm``/``pe_ttm`` in that case.
    """
    shares = _float_or_none(fundamentals.get("shares_outstanding_now"))
    price = _float_or_none(fundamentals.get("price"))
    net_income_ttm = _float_or_none(fundamentals.get("net_income_ttm"))

    # Prefer quarterly. Fall back to the annual statement only when the quarterly
    # frame genuinely has nothing to say about one-off items.
    statement, periods, basis = q_inc, 4, "quarterly_ttm"
    one_off_pretax = compute_one_off_items_ttm(q_inc, periods=4)
    if one_off_pretax is None:
        annual_one_off = compute_one_off_items_ttm(annual_inc, periods=1)
        if annual_one_off is not None:
            statement, periods, basis = annual_inc, 1, "annual_fy"
            one_off_pretax = annual_one_off
        elif q_inc is not None and not getattr(q_inc, "empty", True):
            # The statement is there and simply reports no unusual items. Adjusted EPS
            # then equals raw EPS, which is worth publishing: it is the difference
            # between "clean earnings" and "we never looked", and the unclassified
            # residual review below still runs.
            one_off_pretax = 0.0
        elif annual_inc is not None and not getattr(annual_inc, "empty", True):
            statement, periods, basis = annual_inc, 1, "annual_fy"
            one_off_pretax = 0.0
        else:
            return {}
        if basis == "annual_fy":
            # On the annual basis the earnings figure must come from the same statement,
            # or a full-year one-off would be netted against a TTM profit from elsewhere.
            annual_net_income = _ttm_sum(
                annual_inc,
                "Net Income",
                "Net Income Common Stockholders",
                "Net Income From Continuing Operation Net Minority Interest",
                periods=1,
            )
            if annual_net_income is not None:
                net_income_ttm = annual_net_income

    if net_income_ttm is None or not shares:
        return {}

    effective_tax_rate, tax_rate_is_fallback = compute_effective_tax_rate(statement, periods=periods)
    one_off_after_tax = one_off_pretax * (1.0 - effective_tax_rate)
    adjusted_net_income = net_income_ttm - one_off_after_tax
    adjusted_eps = adjusted_net_income / shares

    one_off_pct_of_ni = abs(one_off_after_tax) / abs(net_income_ttm) if net_income_ttm else None
    materiality_gate_fired = bool(one_off_pct_of_ni is not None and one_off_pct_of_ni > MATERIALITY_THRESHOLD_PCT_OF_NI)

    result: dict[str, Any] = {
        "adjusted_eps_ttm": round(adjusted_eps, 4),
        "adjusted_eps_basis": basis,
        "one_off_pct_of_ni": round(one_off_pct_of_ni, 4) if one_off_pct_of_ni is not None else None,
        "effective_tax_rate": round(effective_tax_rate, 4),
        "effective_tax_rate_is_fallback": tax_rate_is_fallback,
        "one_off_items_pretax": round(one_off_pretax, 2),
    }
    result.update(
        unclassified_one_off_review(statement, net_income_ttm, effective_tax_rate, periods=periods)
    )

    if materiality_gate_fired and price and adjusted_eps > 0:
        result["pe_ttm_adjusted"] = round(price / adjusted_eps, 4)

    return result


# Rows yfinance classifies as unusual are summed by ``Total Unusual Items``. What it does
# NOT classify is the "other non-operating" bucket, and that is where a disclosed one-off
# can sit: SPK.NZ's FY26 sale of 75% of its data centre business booked a NZ$278m gain
# that lands in ``Other Non Operating Income Expenses`` (NZ$301m) while ``Total Unusual
# Items`` reads NZ$12m -- the gain on sale of PPE, a different item entirely. Stripping
# that whole bucket by default would be wrong: for many companies it holds recurring FX
# and interest items. So the bucket is measured, never silently stripped, and a row whose
# unclassified residual is material is flagged for review instead of reporting an adjusted
# EPS that is quietly almost identical to the raw one.
UNCLASSIFIED_ONE_OFF_ROWS = (
    "Other Non Operating Income Expenses",
    "Other Income Expense",
)


def unclassified_one_off_review(
    statement: pd.DataFrame | None,
    net_income: float | None,
    effective_tax_rate: float,
    periods: int = 4,
) -> dict[str, Any]:
    """Size the non-operating residual the one-off detector could not classify."""
    residual_pretax = _ttm_sum(statement, *UNCLASSIFIED_ONE_OFF_ROWS, periods=periods)
    if residual_pretax is None or not net_income:
        return {"one_off_unclassified_pretax": None, "one_off_review_needed": False}

    residual_after_tax = residual_pretax * (1.0 - effective_tax_rate)
    pct_of_ni = abs(residual_after_tax) / abs(net_income)
    return {
        "one_off_unclassified_pretax": round(residual_pretax, 2),
        "one_off_unclassified_pct_of_ni": round(pct_of_ni, 4),
        # Material residual: the adjusted EPS above may be missing a real one-off that
        # the feed filed under a catch-all. Treat the number as unreviewed, not wrong.
        "one_off_review_needed": bool(pct_of_ni > MATERIALITY_THRESHOLD_PCT_OF_NI),
    }
