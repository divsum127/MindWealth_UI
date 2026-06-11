"""NYSE new highs / new lows ratio from S&P 500 52-week high/low counts."""

from __future__ import annotations

from src.config_paths import SSI_DATA_DIR
from src.sentiment_superindex.data.scraper_utils import (
    filter_series_from,
    load_cached_series,
    merge_series,
    save_cached_series,
)
from src.sentiment_superindex.data.sp500_breadth import series_from_breadth

CACHE_CSV = SSI_DATA_DIR / "nh_nl_ratio.csv"


def fetch_nh_nl_ratio(start: str = "2010-01-01") -> pd.Series:
    cached = load_cached_series(CACHE_CSV, value_col="ratio")
    live = series_from_breadth("nh_nl_ratio", start)
    live = filter_series_from(live, start)
    cached = filter_series_from(cached, start)
    merged = merge_series(cached, live)
    if not merged.empty:
        save_cached_series(merged, CACHE_CSV, value_col="ratio")
    return merged
