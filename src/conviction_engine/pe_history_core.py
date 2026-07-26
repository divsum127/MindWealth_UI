"""Shared trailing-P/E-history construction, used by every data source.

Extracted from ``fundamentals_enriched.py`` (2026-07-24) so both the yfinance path
(``fundamentals_enriched.build_fundamentals_from_raw``) and the deep-history fallback
sources (``pe_history_sec.py`` for SEC EDGAR, ``pe_history_fmp.py`` for Financial
Modeling Prep) can share one tested implementation instead of each re-deriving trailing
P/E from price + quarterly EPS. ``fundamentals_enriched.py`` re-exports these names so
existing ``from .fundamentals_enriched import compute_pe_history`` imports keep working
unchanged.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

PE_HISTORY_TARGET_YEARS = 20
PE_HISTORY_MAX_STORED_POINTS = 240  # ~20Y of month-end P/E samples for JSON + percentile


def _empty_pe_history_bundle() -> dict[str, Any]:
    return {
        "values": [],
        "meta": {
            "years_available": 0.0,
            "price_years_available": 0.0,
            "eps_quarters": 0,
            "eps_years_available": 0.0,
            "start_date": None,
            "end_date": None,
            "point_count": 0,
            "stored_point_count": 0,
            "target_years": PE_HISTORY_TARGET_YEARS,
            "insufficient_20y": True,
        },
    }


def compute_pe_history(price_series: pd.Series, quarterly_eps: pd.Series) -> dict[str, Any]:
    """Build trailing P/E history: each day's close / TTM EPS known as of that date.

    Uses **historical** prices from ``history(period='max')`` (not today's spot for past dates).
    Returns monthly-sampled values for storage plus metadata on calendar span vs 20Y target.

    Source-agnostic: ``quarterly_eps`` may come from yfinance's ``quarterly_income_stmt``,
    an SEC EDGAR XBRL-reconstructed quarterly series (with Q4 plugged from the 10-K annual
    total), or any other source that yields one EPS value per fiscal quarter indexed by
    quarter-end date.
    """
    if price_series is None or price_series.empty or quarterly_eps is None or quarterly_eps.empty:
        return _empty_pe_history_bundle()

    prices = price_series.dropna().sort_index()
    eps = quarterly_eps.dropna().sort_index()
    if eps.index.tz is not None:
        eps.index = eps.index.tz_localize(None)
    if len(eps) < 4:
        return _empty_pe_history_bundle()

    price_years = 0.0
    if len(prices) > 1:
        price_years = (prices.index[-1] - prices.index[0]).days / 365.25
    eps_years = 0.0
    if len(eps) > 1:
        eps_years = (eps.index[-1] - eps.index[0]).days / 365.25

    ttm_eps = eps.rolling(window=4, min_periods=4).sum()
    pe_dates: list[pd.Timestamp] = []
    pe_values: list[float] = []
    for dt, price in prices.items():
        mask = ttm_eps.index <= dt
        if not mask.any():
            continue
        eps_val = float(ttm_eps[mask].iloc[-1])
        if eps_val > 0:
            pe = float(price) / eps_val
            if 0 < pe < 500:
                pe_dates.append(pd.Timestamp(dt))
                pe_values.append(round(pe, 4))

    if not pe_values:
        bundle = _empty_pe_history_bundle()
        bundle["meta"]["price_years_available"] = round(price_years, 2)
        bundle["meta"]["eps_quarters"] = len(eps)
        bundle["meta"]["eps_years_available"] = round(eps_years, 2)
        return bundle

    pe_series = pd.Series(pe_values, index=pd.DatetimeIndex(pe_dates)).sort_index()
    monthly = pe_series.resample("ME").last().dropna()
    stored = monthly.tail(PE_HISTORY_MAX_STORED_POINTS).round(4)

    first_dt = pe_series.index[0]
    last_dt = pe_series.index[-1]
    years_available = (last_dt - first_dt).days / 365.25

    meta = {
        "years_available": round(years_available, 2),
        "price_years_available": round(price_years, 2),
        "eps_quarters": len(eps),
        "eps_years_available": round(eps_years, 2),
        "start_date": first_dt.strftime("%Y-%m-%d"),
        "end_date": last_dt.strftime("%Y-%m-%d"),
        "point_count": len(pe_values),
        "stored_point_count": len(stored),
        "target_years": PE_HISTORY_TARGET_YEARS,
        "insufficient_20y": years_available < PE_HISTORY_TARGET_YEARS,
    }
    return {"values": stored.tolist(), "meta": meta}
