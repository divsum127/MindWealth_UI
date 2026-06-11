"""FRED data pulls for Runic variables."""

from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import requests

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"


def _fred_api_key() -> str | None:
    return os.environ.get("FRED_API_KEY") or None


def fetch_fred_series(series_id: str, start: str = "1990-01-01") -> pd.Series:
    key = _fred_api_key()
    if key:
        try:
            from fredapi import Fred

            fred = Fred(api_key=key)
            s = fred.get_series(series_id, observation_start=start)
            s.index = pd.to_datetime(s.index)
            return s.dropna().astype(float)
        except Exception:
            pass
    # Fallback: FRED public CSV
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={start}"
    df = pd.read_csv(url)
    date_col = "DATE" if "DATE" in df.columns else "observation_date"
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.set_index(date_col)
    col = series_id if series_id in df.columns else df.columns[0]
    s = pd.to_numeric(df[col], errors="coerce").dropna()
    s = s[s.index >= pd.Timestamp(start)]
    s.index = pd.to_datetime(s.index)
    return s.astype(float)


def fetch_dff(start: str = "1990-01-01") -> pd.Series:
    """Daily effective federal funds rate (FRED DFF)."""
    return fetch_fred_series("DFF", start=start)


def walcl_mom_pct(walcl: pd.Series) -> pd.Series:
    walcl = walcl.sort_index().dropna()
    weekly = walcl.resample("W-FRI").last().dropna()
    mom = weekly.pct_change(4) * 100
    return mom.dropna()


def steepen_bps_post_inversion_trough(spread_bps: pd.Series) -> pd.Series:
    """
    Weekly steepening metric for curve regime labelling.

    After an inversion episode (spread < 0), track the trough and measure rise
    from trough. Also compute 4-week change. Use the larger of the two when a
    post-inversion trough exists — matches F4 steepening-short mechanism and
    fixes false NORMAL when simple diff(20) is negative but spread is recovering
    from a deep inversion trough.
    """
    weekly = spread_bps.resample("W-FRI").last().dropna()
    if weekly.empty:
        return pd.Series(dtype=float)

    trough: float | None = None
    was_positive = False
    steepen_weekly: list[float] = []
    for i, val in enumerate(weekly):
        if val < 0:
            if was_positive:
                trough = float(val)
                was_positive = False
            else:
                trough = min(trough, val) if trough is not None else float(val)
        elif val >= 0 and trough is not None:
            was_positive = True
        chg_4wk = float(val - weekly.iloc[i - 4]) if i >= 4 else float("nan")
        if trough is not None:
            from_trough = float(val - trough)
            if i >= 4 and chg_4wk == chg_4wk:
                steepen_weekly.append(max(from_trough, chg_4wk))
            else:
                steepen_weekly.append(from_trough)
        else:
            steepen_weekly.append(chg_4wk)

    steepen_w = pd.Series(steepen_weekly, index=weekly.index)
    return steepen_w.reindex(spread_bps.index, method="ffill")


def curve_features(t10y2y: pd.Series) -> pd.DataFrame:
    t10y2y = t10y2y.sort_index()
    spread_bps = t10y2y * 100  # FRED T10Y2Y is in percent
    steepen_simple = spread_bps.diff(20)  # ~4 weeks daily (legacy)
    steepen_post_trough = steepen_bps_post_inversion_trough(spread_bps)
    steepen_4wk = steepen_post_trough.combine_first(steepen_simple)
    return pd.DataFrame(
        {
            "spread_bps": spread_bps,
            "steepen_4wk_bps": steepen_4wk,
            "steepen_4wk_simple_bps": steepen_simple,
        }
    )
