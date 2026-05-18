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
