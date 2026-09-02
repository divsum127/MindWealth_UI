"""Dividend yield history statistics for yield-trap detection."""

from __future__ import annotations

import pandas as pd


def compute_dividend_yield_stats(history: pd.DataFrame | None, dividends: pd.Series | None) -> dict[str, float]:
    """5Y dividend-yield mean/std, delegating to the month-end series (Rohit 1 Sep, C2).

    These are the mean and standard deviation of dividend **yields**, not of dividend
    amounts — a distinction worth stating because the two were used interchangeably in
    earlier correspondence.

    The construction is his: a twelve-month dividend built from the periods each
    declaration covers, divided by the price, sampled at month-end, sixty observations
    over five years. It replaces a 365-day rolling sum which, for a semi-annual payer,
    flipped between two and three payments every year of history and inflated both the
    mean and the dispersion of the distribution the yield-trap z-score is measured
    against (SPK.NZ read an 11.5% mean yield on the old basis).
    """
    from .dividend_series import dividend_yield_stats

    close = None
    if history is not None and not getattr(history, "empty", True) and "Close" in history.columns:
        close = history["Close"]
    stats = dividend_yield_stats(close, dividends)
    # Keep the historical return contract: numeric stats only, empty when too thin.
    if "dividend_yield_5y_mean" not in stats:
        return {}
    return {
        "dividend_yield_5y_mean": stats["dividend_yield_5y_mean"],
        "dividend_yield_5y_std": stats["dividend_yield_5y_std"],
        "dividend_yield_observations": stats["dividend_yield_observations"],
        "dividend_frequency_history": stats["dividend_frequency_history"],
        "dividend_frequency_changed": stats["dividend_frequency_changed"],
        "dividend_series_basis": stats["dividend_series_basis"],
    }


def _normalized_dividend_series(dividends: pd.Series | None) -> pd.Series | None:
    if not isinstance(dividends, pd.Series) or dividends.empty:
        return None
    series = dividends.dropna()
    if series.empty:
        return None
    index = series.index
    if getattr(index, "tz", None) is not None:
        index = index.tz_localize(None)
    return pd.Series(series.values, index=index).sort_index()


def payments_per_year(dividends: pd.Series | None) -> int | None:
    """Payment cadence inferred from the median gap between payments.

    Returns 12/4/2/1 (monthly, quarterly, semi-annual, annual) or None when there
    are not enough payments to tell.
    """
    series = _normalized_dividend_series(dividends)
    if series is None or len(series) < 3:
        return None
    gaps = series.index.to_series().diff().dropna().dt.days
    gaps = gaps[gaps > 0]
    if gaps.empty:
        return None
    median_gap = float(gaps.median())
    if median_gap <= 45:
        return 12
    if median_gap <= 135:
        return 4
    if median_gap <= 270:
        return 2
    return 1


def annual_dividend_windows(dividends: pd.Series | None) -> dict[str, float | int | None]:
    """Trailing-year and prior-year dividends per share, counted by payment cadence.

    A plain "payments in the last 365 days" window is anchored on the most recent
    payment date, so one payment landing a day later than its anniversary pulls a
    third payment into a semi-annual payer's year. SPK.NZ hits exactly that: the
    365-day window sums 12.5c (Mar 2025) + 12.5c (Sep 2025) + 8c (Mar 2026) = 33c
    against a real trailing figure of 20.5c, which inverts its dividend cut into a
    raise. Counting the last N payments, where N is the cadence, is stable against
    that drift (Rohit 26 Aug, conviction spec gap 4).
    """
    result: dict[str, float | int | None] = {
        "annual_dividend_current": None,
        "annual_dividend_prior": None,
        "payments_per_year": None,
    }
    series = _normalized_dividend_series(dividends)
    if series is None:
        return result

    per_year = payments_per_year(series)
    if per_year is None:
        # Too few payments to infer cadence: fall back to a calendar window, which is
        # the best available answer and cannot mis-count what it cannot see.
        last_date = series.index[-1]
        current = series[series.index > last_date - pd.Timedelta(days=365)]
        prior = series[
            (series.index <= last_date - pd.Timedelta(days=365))
            & (series.index > last_date - pd.Timedelta(days=730))
        ]
        result["annual_dividend_current"] = float(current.sum()) if not current.empty else None
        result["annual_dividend_prior"] = float(prior.sum()) if not prior.empty else None
        return result

    result["payments_per_year"] = per_year
    if len(series) >= per_year:
        result["annual_dividend_current"] = float(series.iloc[-per_year:].sum())
    if len(series) >= per_year * 2:
        result["annual_dividend_prior"] = float(series.iloc[-per_year * 2 : -per_year].sum())
    return result
