"""CNN Fear & Greed index — CNN graphdata API + CSV cache + Alternative.me backfill.

WARNING: The Alternative.me backfill (`ALTME_URL`) provides the CRYPTO Fear & Greed index
(alternative.me/fng), NOT the CNN stock market Fear & Greed index. These are different products.
Alternative.me starts 2018-02-01. True CNN stock F&G history before ~2025 is not publicly
available via API. The merged cache therefore contains:
  - CNN stock market F&G: last ~12 months (from CNN API)
  - Alternative.me CRYPTO F&G: 2018-02-01 to ~12 months ago (backfill proxy)
Any analysis using this cache should treat pre-2025 data as a crypto sentiment proxy,
not as the CNN stock market index.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config_paths import SSI_DATA_DIR
from src.sentiment_superindex.data.scraper_utils import (
    CNN_HEADERS,
    clamp_index_score,
    http_get,
    load_cached_series,
    merge_series,
    parse_cnn_historical_points,
    save_cached_series,
)

CNN_CACHE = SSI_DATA_DIR / "cnn_fear_greed.csv"
CNN_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
# NOTE: Alternative.me provides the CRYPTO Fear & Greed index (NOT the CNN stock market version).
# It is used here as a backfill proxy because no free source exists for CNN F&G history pre-2025.
# Alternative.me crypto F&G starts 2018-02-01 (not 2011 as previously documented incorrectly).
ALTME_URL = "https://api.alternative.me/fng/?limit=5000&format=json&date_format=us"


def load_cnn_series() -> pd.Series:
    cached = load_cached_series(CNN_CACHE, value_col="score")
    live = fetch_cnn_history()
    merged = merge_series(cached, live)
    if not merged.empty:
        save_cached_series(merged, CNN_CACHE, value_col="score")
    return merged


def fetch_cnn_history() -> pd.Series:
    try:
        resp = http_get(CNN_URL, headers=CNN_HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return load_cached_series(CNN_CACHE, value_col="score")

    hist = parse_cnn_historical_points(data.get("fear_and_greed_historical"))
    if hist.empty:
        hist = parse_cnn_historical_points(data.get("fear_and_greed"))

    fg = data.get("fear_and_greed") or {}
    score = clamp_index_score(fg.get("score"))
    ts = fg.get("timestamp")
    if score is not None and ts:
        try:
            dt = pd.to_datetime(ts)
            hist = merge_series(hist, pd.Series({dt.normalize(): score}, name="score"))
        except Exception:
            pass

    return hist.astype(float) if not hist.empty else pd.Series(dtype=float)


def fetch_altme_history() -> pd.Series:
    """Fetch CRYPTO Fear & Greed history from Alternative.me (starts 2018-02-01).

    This is the cryptocurrency sentiment index, not the CNN stock market F&G.
    Used as a proxy backfill for the CNN cache where true historical CNN data is unavailable.
    """
    try:
        resp = http_get(ALTME_URL, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return pd.Series(dtype=float)
    rows = []
    for pt in data.get("data") or []:
        try:
            # date_format=us → MM/DD/YYYY string
            dt = pd.to_datetime(pt["timestamp"], unit="s") if str(pt["timestamp"]).isdigit() else pd.to_datetime(pt["timestamp"])
            score = clamp_index_score(float(pt["value"]))
            if score is not None:
                rows.append((dt.normalize(), score))
        except Exception:
            continue
    if not rows:
        return pd.Series(dtype=float)
    s = pd.Series({d: v for d, v in rows}, name="score").sort_index()
    return s.astype(float)


def backfill_cnn_from_altme() -> int:
    """Extend the CNN cache backward using Alternative.me data.

    Returns the number of new rows added.
    """
    altme = fetch_altme_history()
    if altme.empty:
        return 0
    cached = load_cached_series(CNN_CACHE, value_col="score")
    merged = merge_series(altme, cached)  # cached takes priority for overlapping dates
    before = len(cached)
    save_cached_series(merged, CNN_CACHE, value_col="score")
    return len(merged) - before


def append_cnn_score(date: str, score: float) -> None:
    validated = clamp_index_score(score)
    if validated is None:
        raise ValueError(f"CNN score must be 0-100, got {score}")
    cached = load_cached_series(CNN_CACHE, value_col="score")
    dt = pd.Timestamp(date).normalize()
    merged = merge_series(cached, pd.Series({dt: validated}))
    save_cached_series(merged, CNN_CACHE, value_col="score")
