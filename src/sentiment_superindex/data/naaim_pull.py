"""NAAIM Exposure Index — scrape naaim.org table + CSV cache."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config_paths import SSI_DATA_DIR
from src.sentiment_superindex.data.scraper_utils import (
    BROWSER_HEADERS,
    http_get,
    load_cached_series,
    merge_series,
    parse_html_table_dates,
    save_cached_series,
)

NAAIM_URL = "https://www.naaim.org/programs/naaim-exposure-index/"
CACHE_CSV = SSI_DATA_DIR / "naaim_exposure.csv"


def fetch_naaim_exposure() -> pd.Series:
    cached = load_cached_series(CACHE_CSV, value_col="exposure")
    live = _scrape_naaim()
    merged = merge_series(cached, live)
    if not merged.empty:
        save_cached_series(merged, CACHE_CSV, value_col="exposure")
    return merged


def _scrape_naaim() -> pd.Series:
    try:
        resp = http_get(NAAIM_URL, headers=BROWSER_HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception:
        return pd.Series(dtype=float)

    df = parse_html_table_dates(
        resp.text,
        value_cols=[
            "naaim_number_mean/average",
            "naaim_number_mean_average",
        ],
    )
    if df.empty:
        return pd.Series(dtype=float)

    col = next(
        (
            c
            for c in df.columns
            if "naaim" in c.lower() and "mean" in c.lower()
        ),
        None,
    )
    if col is None:
        col = df.columns[0]
    s = pd.to_numeric(df[col], errors="coerce").dropna()
    s.name = "naaim_exposure"
    return s.astype(float)
