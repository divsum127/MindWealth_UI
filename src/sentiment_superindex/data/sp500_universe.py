"""S&P 500 constituents — GitHub dataset (no Wikipedia scrape)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests

from src.config_paths import SSI_DATA_DIR
from src.sentiment_superindex.data.scraper_utils import BROWSER_HEADERS, http_get

CONSTITUENTS_URL = (
    "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"
)
CACHE_CSV = SSI_DATA_DIR / "sp500_constituents.csv"
_FALLBACK_TICKERS: list[str] | None = None


def load_sp500_tickers(*, force_refresh: bool = False) -> list[str]:
    global _FALLBACK_TICKERS
    if CACHE_CSV.exists() and not force_refresh:
        df = pd.read_csv(CACHE_CSV)
        col = "Symbol" if "Symbol" in df.columns else df.columns[0]
        tickers = df[col].astype(str).str.replace(".", "-", regex=False).tolist()
        return tickers

    try:
        resp = http_get(CONSTITUENTS_URL, headers=BROWSER_HEADERS, timeout=60)
        resp.raise_for_status()
        CACHE_CSV.parent.mkdir(parents=True, exist_ok=True)
        CACHE_CSV.write_bytes(resp.content)
        df = pd.read_csv(CACHE_CSV)
        col = "Symbol" if "Symbol" in df.columns else df.columns[0]
        tickers = df[col].astype(str).str.replace(".", "-", regex=False).tolist()
        _FALLBACK_TICKERS = tickers
        return tickers
    except Exception:
        if _FALLBACK_TICKERS:
            return _FALLBACK_TICKERS
        from src.sentiment_superindex.data.sp500_sample_tickers import SP500_SAMPLE_TICKERS

        return list(SP500_SAMPLE_TICKERS)
