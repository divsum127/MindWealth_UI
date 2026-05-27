"""FRED data pulls for Runic variables."""

from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import requests

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"


def _fred_api_key() -> str | None:
    return os.environ.get("FRED_API_KEY")


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


def walcl_mom_pct(walcl: pd.Series) -> pd.Series:
    walcl = walcl.sort_index().dropna()
    weekly = walcl.resample("W-FRI").last().dropna()
    mom = weekly.pct_change(4) * 100
    return mom.dropna()


def curve_features(t10y2y: pd.Series) -> pd.DataFrame:
    t10y2y = t10y2y.sort_index()
    spread_bps = t10y2y * 100  # FRED T10Y2Y is in percent
    steepen_4wk = spread_bps.diff(20)  # ~4 weeks daily
    return pd.DataFrame({"spread_bps": spread_bps, "steepen_4wk_bps": steepen_4wk})
