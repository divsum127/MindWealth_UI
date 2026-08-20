"""Shared trailing-P/E-history construction, used by every data source.

Extracted from ``fundamentals_enriched.py`` (2026-07-24) so both the yfinance path
(``fundamentals_enriched.build_fundamentals_from_raw``) and the deep-history fallback
sources (``pe_history_sec.py`` for SEC EDGAR, ``pe_history_fmp.py`` for Financial
Modeling Prep) can share one tested implementation instead of each re-deriving trailing
P/E from price + quarterly EPS. ``fundamentals_enriched.py`` re-exports these names so
existing ``from .fundamentals_enriched import compute_pe_history`` imports keep working
unchanged.

Split into ``_rolling_ttm_from_quarterly`` + ``_pe_from_ttm_series`` (2026-07-29, for the
pre-2009 SEC legacy-filing extension in ``pe_history_sec_legacy.py``): pre-XBRL annual
EPS figures (extracted from old 10-K "Selected Financial Data" tables / EX-27 Financial
Data Schedules) are *already* trailing-twelve-months as of their fiscal year end — they
don't need the rolling-4-quarter-sum step that reconstructed quarterly figures do. See
``compute_pe_history_with_legacy_annual`` for the merge entry point.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

PE_HISTORY_TARGET_YEARS = 20
# 30Y of month-end P/E samples for JSON + percentile ranking. Raised from 240 (~20Y)
# on 2026-07-29 when the SEC-legacy-filing extension (pe_history_sec_legacy.py) started
# pushing some tickers' real coverage past 20Y (e.g. MSFT to ~32Y via EX-27 schedules
# back to 1994) — keeping the old 240-point cap would have silently truncated the
# *stored* array back down to a 20Y rolling window even when 30Y of real data existed,
# so ``insufficient_20y`` would flip to False but ``pe_percentile_20y`` would still only
# ever rank against the trailing 20Y, defeating the point of the deeper extension.
PE_HISTORY_MAX_STORED_POINTS = 360


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


def _rolling_ttm_from_quarterly(quarterly_eps: pd.Series) -> pd.Series:
    """Reconstructed-quarterly EPS -> trailing-twelve-months EPS as of each quarter end."""
    eps = quarterly_eps.dropna().sort_index()
    if eps.index.tz is not None:
        eps.index = eps.index.tz_localize(None)
    return eps.rolling(window=4, min_periods=4).sum()


def _pe_from_ttm_series(
    price_series: pd.Series,
    ttm_eps: pd.Series,
    *,
    eps_point_count: int,
) -> dict[str, Any]:
    """Walk ``price_series`` and divide by the latest known TTM EPS as of each date.

    ``ttm_eps`` must already be trailing-twelve-months values indexed by the date each
    figure became known (quarter end for reconstructed-quarterly data, fiscal year end
    for annual-only legacy data) — this function no longer cares which source produced
    it, only that it represents "trailing EPS as of this date".
    """
    prices = price_series.dropna().sort_index()
    if prices.empty or ttm_eps.empty:
        return _empty_pe_history_bundle()

    price_years = 0.0
    if len(prices) > 1:
        price_years = (prices.index[-1] - prices.index[0]).days / 365.25
    eps_years = 0.0
    if len(ttm_eps) > 1:
        eps_years = (ttm_eps.index[-1] - ttm_eps.index[0]).days / 365.25

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
        bundle["meta"]["eps_quarters"] = eps_point_count
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
        "eps_quarters": eps_point_count,
        "eps_years_available": round(eps_years, 2),
        "start_date": first_dt.strftime("%Y-%m-%d"),
        "end_date": last_dt.strftime("%Y-%m-%d"),
        "point_count": len(pe_values),
        "stored_point_count": len(stored),
        "target_years": PE_HISTORY_TARGET_YEARS,
        "insufficient_20y": years_available < PE_HISTORY_TARGET_YEARS,
    }
    return {"values": stored.tolist(), "meta": meta}


def reconstruct_quarterly_eps_from_net_income(q_inc: pd.DataFrame | None) -> pd.Series:
    """Quarterly EPS = Net Income / Diluted (or Basic) Average Shares, column-aligned.

    Tier 2 fallback (item 16): many non-US filers' ``quarterly_income_stmt`` from
    yfinance don't carry a direct "Diluted EPS"/"Basic EPS" row at all (reporting
    convention differs by market), so the ``compute_pe_history()`` call in
    ``fundamentals_enriched.build_fundamentals_from_raw`` would otherwise be skipped
    entirely for e.g. WIPRO.NS, 005930.KS. Same net-income/shares division already
    used for the single-point ``eps_ttm`` PYPL fallback, just applied per-quarter
    across the *full* available window instead of only the latest TTM point, so it
    can feed the same rolling-TTM ``compute_pe_history()`` machinery every other
    source uses.
    """
    if q_inc is None or getattr(q_inc, "empty", True):
        return pd.Series(dtype=float)

    net_income_row: str | None = None
    for label in ("Net Income", "Net Income Common Stockholders"):
        if label in q_inc.index:
            net_income_row = label
            break
    shares_row: str | None = None
    for label in ("Diluted Average Shares", "Basic Average Shares"):
        if label in q_inc.index:
            shares_row = label
            break
    if net_income_row is None or shares_row is None:
        return pd.Series(dtype=float)

    net_income = q_inc.loc[net_income_row]
    shares = q_inc.loc[shares_row]
    valid = shares.notna() & (shares > 0) & net_income.notna()
    eps = (net_income[valid] / shares[valid]).replace([float("inf"), float("-inf")], pd.NA).dropna()
    return eps.sort_index()


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

    eps = quarterly_eps.dropna()
    if len(eps) < 4:
        return _empty_pe_history_bundle()

    ttm_eps = _rolling_ttm_from_quarterly(quarterly_eps)
    return _pe_from_ttm_series(price_series, ttm_eps, eps_point_count=len(eps))


def compute_pe_history_with_legacy_annual(
    price_series: pd.Series,
    quarterly_eps: pd.Series,
    legacy_annual_eps: pd.Series | None,
) -> dict[str, Any]:
    """Extend ``compute_pe_history`` with older annual-only EPS points (pre-2009 SEC
    filings, extracted by ``pe_history_sec_legacy.py`` from EX-27 Financial Data
    Schedules and "Selected Financial Data" 10-K tables — see that module's docstring).

    ``legacy_annual_eps`` values are already trailing-twelve-months as of their fiscal
    year end date (that's what an annual EPS figure *is*), so unlike ``quarterly_eps``
    they skip the rolling-4-quarter-sum step entirely. Only legacy points strictly
    *before* the earliest reconstructed-quarterly TTM point are used, so this can only
    extend history further back — it never overrides or duplicates modern-era coverage.

    Falls back to plain ``compute_pe_history`` behavior when ``legacy_annual_eps`` is
    ``None``/empty (e.g. no legacy filings found or parseable for this ticker).
    """
    if price_series is None or price_series.empty:
        return _empty_pe_history_bundle()

    modern_eps = quarterly_eps.dropna() if quarterly_eps is not None else pd.Series(dtype=float)
    legacy_eps = legacy_annual_eps.dropna() if legacy_annual_eps is not None else pd.Series(dtype=float)

    if legacy_eps.empty:
        return compute_pe_history(price_series, quarterly_eps)

    if getattr(legacy_eps.index, "tz", None) is not None:
        legacy_eps.index = legacy_eps.index.tz_localize(None)

    modern_ttm = _rolling_ttm_from_quarterly(modern_eps) if len(modern_eps) >= 4 else pd.Series(dtype=float)
    modern_ttm = modern_ttm.dropna()

    if not modern_ttm.empty:
        legacy_eps = legacy_eps[legacy_eps.index < modern_ttm.index.min()]

    if legacy_eps.empty and modern_ttm.empty:
        return _empty_pe_history_bundle()

    non_empty_series = [s for s in (legacy_eps, modern_ttm) if not s.empty]
    combined_ttm = pd.concat(non_empty_series).sort_index()
    combined_ttm = combined_ttm[~combined_ttm.index.duplicated(keep="first")]
    eps_point_count = len(modern_eps) + len(legacy_eps)
    return _pe_from_ttm_series(price_series, combined_ttm, eps_point_count=eps_point_count)
