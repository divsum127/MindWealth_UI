"""FINRA / Fed margin debt (monthly) — FRED pull + CSV cache."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config_paths import SSI_DATA_DIR
from src.macro_intelligence.data.fred_pull import fetch_fred_series
from src.sentiment_superindex.data.scraper_utils import load_cached_series, merge_series, save_cached_series
from src.sentiment_superindex.data.pull_guard import log_pull_empty, log_pull_failure

CACHE_CSV = SSI_DATA_DIR / "margin_debt.csv"
# BOGZFL224066003Q needs FRED API key; MDSP is public monthly debit balances fallback.
FRED_SERIES_IDS = ("BOGZFL224066003Q", "MDSP")


def fetch_margin_debt() -> pd.Series:
    """Monthly margin / debit balances in billions USD (FRED)."""
    cached = load_cached_series(CACHE_CSV, value_col="margin_debt")
    live = _fetch_fred_margin_debt()
    merged = merge_series(cached, live)
    if not merged.empty:
        save_cached_series(merged, CACHE_CSV, value_col="margin_debt")
    merged.name = "margin_debt"
    if live.attrs.get("fred_series"):
        merged.attrs["fred_series"] = live.attrs["fred_series"]
    return merged.astype(float)


def _fetch_fred_margin_debt() -> pd.Series:
    for series_id in FRED_SERIES_IDS:
        try:
            s = fetch_fred_series(series_id, "1997-01-01")
            if s.empty:
                continue
            s.name = "margin_debt"
            s.attrs["fred_series"] = series_id
            return s.astype(float)
        except Exception as exc:
            log_pull_failure("ssi_margin_debt", exc, note=f"FRED series {series_id}")
            continue
    log_pull_empty("ssi_margin_debt", note="no FRED margin-debt series returned data")
    return pd.Series(dtype=float, name="margin_debt")
