"""Classic McClellan oscillator: EMA(19) − EMA(39) of daily net advances (S&P 500)."""

from __future__ import annotations

import pandas as pd

from src.config_paths import SSI_DATA_DIR
from src.sentiment_superindex.data.scraper_utils import (
    filter_series_from,
    load_cached_series,
    merge_series,
    save_cached_series,
)
from src.sentiment_superindex.data.sp500_breadth import series_from_breadth

CACHE_CSV = SSI_DATA_DIR / "mcclellan_oscillator.csv"


def _classic_mcclellan(net_advances: pd.Series) -> pd.Series:
    net = net_advances.fillna(0)
    ema19 = net.ewm(span=19, adjust=False).mean()
    ema39 = net.ewm(span=39, adjust=False).mean()
    osc = (ema19 - ema39).dropna()
    osc.name = "mcclellan"
    return osc.astype(float)


def fetch_mcclellan_oscillator(start: str = "2010-01-01") -> pd.Series:
    cached = load_cached_series(CACHE_CSV, value_col="oscillator")
    net = series_from_breadth("net_advances", start)
    live = _classic_mcclellan(net) if not net.empty else pd.Series(dtype=float)
    live = filter_series_from(live, start)
    cached = filter_series_from(cached, start)
    merged = merge_series(cached, live)
    if not merged.empty:
        save_cached_series(merged, CACHE_CSV, value_col="oscillator")
    return merged
