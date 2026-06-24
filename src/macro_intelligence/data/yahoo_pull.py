"""Yahoo Finance pulls for Runic variables."""

from __future__ import annotations

import pandas as pd
import yfinance as yf


def fetch_yahoo_close(ticker: str, start: str = "1990-01-01") -> pd.Series:
    data = yf.download(ticker, start=start, progress=False, auto_adjust=True)
    if data.empty:
        return pd.Series(dtype=float)
    if isinstance(data.columns, pd.MultiIndex):
        close = data["Close"].iloc[:, 0] if "Close" in data.columns.get_level_values(0) else data.iloc[:, 0]
    else:
        close = data["Close"] if "Close" in data.columns else data.iloc[:, 0]
    close.index = pd.to_datetime(close.index).tz_localize(None)
    return close.dropna().astype(float)


def rolling_pct_change(series: pd.Series, periods: int = 20) -> pd.Series:
    s = series.sort_index()
    return ((s / s.shift(periods)) - 1) * 100


def calendar_pct_change(series: pd.Series, calendar_days: int = 28) -> pd.Series:
    """v3 ROC: percent change vs value N calendar days ago (not trading bars)."""
    s = series.sort_index()
    prior = s.reindex(s.index - pd.Timedelta(days=calendar_days), method="ffill")
    prior.index = s.index
    return ((s / prior) - 1) * 100


def vix_term_structure(start: str = "2007-01-01") -> pd.Series:
    """VIX term structure ratio: ^VIX3M (93-day) ÷ ^VIX (30-day).

    Ratio > 1  → contango (calm, normal).  Threshold ≥ 1.10 = Combo D watch.
    Ratio < 1  → backwardation (near-term panic). Threshold ≤ 0.95 = Combo G watch.

    Primary ticker : ^VIX3M  (CBOE 93-day implied vol — available from ~2007)
    Fallback ticker: ^VXV    (equivalent 93-day series; now delisted, useful for
                              older historical research only)
    """
    vix3m = fetch_yahoo_close("^VIX3M", start=start)
    if vix3m.empty:
        # ^VXV was the predecessor 93-day series; delisted but may cover older history
        vix3m = fetch_yahoo_close("^VXV", start=start)
    vix = fetch_yahoo_close("^VIX", start=start)
    aligned = pd.DataFrame({"vix": vix, "vix3m": vix3m}).dropna()
    return (aligned["vix3m"] / aligned["vix"]).rename("vxts")


def gsr_ratio(start: str = "1990-01-01") -> pd.Series:
    gold = fetch_yahoo_close("GC=F", start=start)
    silver = fetch_yahoo_close("SI=F", start=start)
    df = pd.DataFrame({"gold": gold, "silver": silver}).dropna()
    return (df["gold"] / df["silver"]).rename("gsr")


def spx_weekly_returns(start: str = "1950-01-01") -> pd.Series:
    spx = fetch_yahoo_close("^GSPC", start=start)
    weekly = spx.resample("W-FRI").last().dropna()
    return weekly.pct_change() * 100


def spx_with_50wma(start: str = "1990-01-01") -> pd.DataFrame:
    spx = fetch_yahoo_close("^GSPC", start=start)
    if spx.empty:
        return pd.DataFrame(columns=["close", "wma50", "weekly_ret_pct", "above_50wma"])
    if not isinstance(spx.index, pd.DatetimeIndex):
        spx.index = pd.to_datetime(spx.index)
    weekly = spx.resample("W-FRI").last().dropna()
    wma50 = weekly.rolling(50).mean()
    weekly_ret = weekly.pct_change() * 100
    return pd.DataFrame(
        {
            "close": weekly,
            "wma50": wma50,
            "weekly_ret_pct": weekly_ret,
            "above_50wma": weekly > wma50,
        }
    ).dropna(subset=["close"])
