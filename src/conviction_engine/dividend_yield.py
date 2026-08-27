"""Dividend yield history statistics for yield-trap detection."""

from __future__ import annotations

import pandas as pd


def compute_dividend_yield_stats(history: pd.DataFrame | None, dividends: pd.Series | None) -> dict[str, float]:
    """Compute 5Y dividend-yield mean/std from daily close and dividend series.

    Aligns price and dividend timestamps to calendar dates so yfinance dividend
    rows (often 09:30) match daily close rows (midnight).
    """
    if history is None or dividends is None or history.empty or dividends.empty or "Close" not in history.columns:
        return {}

    close = history["Close"].dropna()
    if close.empty:
        return {}

    dividends = dividends.dropna()
    if dividends.empty:
        return {}

    if close.index.tz is not None:
        close.index = close.index.tz_localize(None)
    if dividends.index.tz is not None:
        dividends.index = dividends.index.tz_localize(None)

    close_daily = close.groupby(close.index.normalize()).last()
    div_daily = dividends.groupby(dividends.index.normalize()).sum()

    # Trailing-year dividend at each date, counted by payment cadence rather than by a
    # 365-day rolling sum. A rolling sum over a semi-annual payer flips between two and
    # three payments as anniversaries drift, which inflates both the mean and the
    # dispersion of the very distribution the yield-trap z-score is measured against.
    # SPK.NZ came out at an 11.5% 5Y mean yield on the rolling basis against roughly
    # 6-7% on the real one (Rohit 26 Aug, conviction spec gap 4).
    per_year = payments_per_year(div_daily)
    if per_year is not None and len(div_daily) >= per_year:
        cumulative = div_daily.cumsum()
        trailing_at_payment = cumulative - cumulative.shift(per_year).fillna(0.0)
        # Only meaningful once a full cadence of payments has been seen.
        trailing_at_payment = trailing_at_payment.iloc[per_year - 1 :]
        annual_dividends = trailing_at_payment.reindex(close_daily.index, method="ffill")
    else:
        daily_dividends = div_daily.reindex(close_daily.index, fill_value=0.0)
        annual_dividends = daily_dividends.rolling(window=365, min_periods=60).sum()

    dividend_yield = (annual_dividends / close_daily).replace([float("inf"), float("-inf")], pd.NA).dropna()
    dividend_yield = dividend_yield[dividend_yield > 0]
    if len(dividend_yield) < 20:
        return {}

    return {
        "dividend_yield_5y_mean": round(float(dividend_yield.mean()), 6),
        "dividend_yield_5y_std": round(float(dividend_yield.std(ddof=0)), 6),
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
