"""CNN Fear & Greed index — CNN graphdata API + CSV cache + free-source historical backfill.

Fixed 2026-08-02 (was returning only ~12 months of real data): `fetch_cnn_history()` now appends
a start-date to `CNN_URL` (see `CNN_EARLIEST_START_DATE`), which makes CNN's own backend return
its full real history instead of a short default window. Real CNN stock-market F&G data is now
retrieved for 2020-07-14 -> today on every call (~1500+ rows, live-verified).

For dates before 2020-07-14, CNN's own API has nothing (confirmed: any earlier start-date makes
the endpoint 500 instead of returning more data) -- no code fix can get more from CNN directly.
Two other free sources cover most of the remaining gap (see
`docs/ssi_validation/cnn_fg_wayback_backfill_2026-08-02.md` and
`scripts/backfill_cnn_feargreed_free_sources.py`):
  - 2012-05-25 -> 2020-07-13: a community-maintained, Wayback-Machine-reconstructed dataset
    (`whit3rabbit/fear-greed-data`), validated against CNN's real live API on overlapping dates.
  - 2011-01 -> 2012-05-24 (~16 months): genuinely no free source found (confirmed via direct
    Wayback CDX query: zero snapshots of the CNN F&G page exist before 2012-05-25) -- stays on
    the Alternative.me CRYPTO Fear & Greed backfill below, disclosed as a proxy, not real CNN data.

WARNING: The Alternative.me backfill (`ALTME_URL`) provides the CRYPTO Fear & Greed index
(alternative.me/fng), NOT the CNN stock market Fear & Greed index. These are different products.
Alternative.me starts 2018-02-01. It is now used only for the disclosed 2011-01 -> 2012-05-24
residual gap above (previously it silently covered 2018-02-01 -> ~12 months ago before this fix).
Cache rows carry a `source` column (`real_cnn_api` / `wayback_reconstructed` / `crypto_proxy`) so
provenance is visible at a glance -- see `scraper_utils.load_cached_series`/`save_cached_series`.
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
from src.sentiment_superindex.data.pull_guard import log_pull_empty, log_pull_failure

CNN_CACHE = SSI_DATA_DIR / "cnn_fear_greed.csv"
CNN_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
# CNN's graphdata endpoint returns only a short default window (~last 12 months) unless a
# start-date is appended to the URL path. Live-verified 2026-08-02: appending any date on/after
# 2020-07-14 returns everything CNN's backend actually has (currently 2020-07-14 -> today, 1519+
# rows); any date before 2020-07-14 makes the endpoint 500 instead of clamping -- so this constant
# must stay >= 2020-07-14, it cannot be pushed earlier to "ask for more" (CNN simply has nothing
# free before that date; see cnn_fg_wayback_backfill_2026-08-02.md for the free source that covers
# 2012-05-25 -> 2020-07-13 instead).
CNN_EARLIEST_START_DATE = "2020-07-14"
# NOTE: Alternative.me provides the CRYPTO Fear & Greed index (NOT the CNN stock market version).
# It is used here as a backfill proxy because no free source exists for CNN F&G history pre-2025.
# Alternative.me crypto F&G starts 2018-02-01 (not 2011 as previously documented incorrectly).
ALTME_URL = "https://api.alternative.me/fng/?limit=5000&format=json&date_format=us"


def load_cnn_series() -> pd.Series:
    cached, cached_source = load_cached_series(CNN_CACHE, value_col="score", extra_col="source")
    live = fetch_cnn_history()
    if not live.empty:
        live = live.copy()
        live.index = live.index.normalize()
        live = live[~live.index.duplicated(keep="last")]
    merged = merge_series(cached, live)
    if not merged.empty:
        # `live` (real CNN API) always wins its own dates and is tagged accordingly; every other
        # date keeps whatever provenance tag it already had (wayback_reconstructed / crypto_proxy
        # / real_cnn_api from a prior run) -- this is what stops the 2026-08-02 free-source
        # backfill's `source` column from being silently dropped on the next nightly pull.
        source = cached_source.reindex(merged.index)
        if not live.empty:
            source.loc[live.index] = "real_cnn_api"
        source = source.fillna("real_cnn_api")
        save_cached_series(merged, CNN_CACHE, value_col="score", extra_col="source", extra_series=source)
    return merged


def fetch_cnn_history() -> pd.Series:
    try:
        resp = http_get(f"{CNN_URL}/{CNN_EARLIEST_START_DATE}", headers=CNN_HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        log_pull_failure("ssi_cnn_fg", exc, note="serving cached CNN F&G history")
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
    except Exception as exc:
        log_pull_failure("ssi_cnn_fg_altme_proxy", exc, note=ALTME_URL)
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

    Only fills dates with no existing row (`merge_series(altme, cached)` -- cached takes priority
    for overlapping dates), so this cannot overwrite the 2026-08-02 free-source backfill's real
    (`real_cnn_api`) or reconstructed (`wayback_reconstructed`) rows -- any date it does add is, by
    definition, the crypto proxy, tagged accordingly.

    Returns the number of new rows added.
    """
    altme = fetch_altme_history()
    if altme.empty:
        return 0
    cached, cached_source = load_cached_series(CNN_CACHE, value_col="score", extra_col="source")
    merged = merge_series(altme, cached)  # cached takes priority for overlapping dates
    before = len(cached)
    source = cached_source.reindex(merged.index)
    source.loc[merged.index.difference(cached.index)] = "crypto_proxy"
    source = source.fillna("crypto_proxy")
    save_cached_series(merged, CNN_CACHE, value_col="score", extra_col="source", extra_series=source)
    return len(merged) - before


def append_cnn_score(date: str, score: float, *, source: str = "manual") -> None:
    validated = clamp_index_score(score)
    if validated is None:
        raise ValueError(f"CNN score must be 0-100, got {score}")
    cached, cached_source = load_cached_series(CNN_CACHE, value_col="score", extra_col="source")
    dt = pd.Timestamp(date).normalize()
    merged = merge_series(cached, pd.Series({dt: validated}))
    tags = cached_source.reindex(merged.index)
    tags.loc[dt] = source
    tags = tags.fillna(source)
    save_cached_series(merged, CNN_CACHE, value_col="score", extra_col="source", extra_series=tags)
