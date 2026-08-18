"""Disk-cached Yahoo closes for SSI inputs.

Why this exists (audit 2026-08-18). Six SSI inputs are derived from Yahoo closes -- HYG, LQD,
DBMF, SPY, ^VIX, ^VIX3M, ^SKEW -- and, alone among the fourteen inputs, they had no cache.
Every other input already persists a CSV and merges each pull into it
(``naaim_pull``, ``cnn_fear_greed``, ``put_call_pull``, ``nh_nl_pull``, ...). The Yahoo ones
re-fetched from scratch nightly and kept whatever came back.

That turned an upstream hiccup into a scoring event. ``yf.download`` returns a *short* frame
rather than raising when Yahoo truncates a series, and the derived inputs inner-join their
legs with ``.dropna()`` -- so on 2026-08-18 a ^VIX3M response that stopped at 2026-07-17
erased the whole VIX term-structure series even though ^VIX was current, and four of Layer 2's
six inputs aged past their staleness cap at once. Layer 2 fell to 2 of 6 and the SSI size
multiplier moved 1.2x -> 0.8x on missing data alone.

Caching the *closes* (not the derived ratios) is what fixes it at the root: a truncated tail is
refilled from disk before the join happens, so one flaky leg can no longer delete a ratio that
the other leg could still support. It also means a total Yahoo outage degrades to "carried
forward, ageing visibly through ``stale_days``" instead of "gone".

The cache is deliberately append-only in effect: ``merge_series`` keeps the live value for any
date it returns and keeps history for every date it does not. Yahoo restating a recent close is
honoured; Yahoo forgetting one is not.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from src.config_paths import SSI_DATA_DIR
from src.macro_intelligence.data.yahoo_pull import fetch_yahoo_close
from src.sentiment_superindex.data import cboe_indices
from src.sentiment_superindex.data.pull_guard import (
    log_pull_empty,
    log_pull_failure,
    log_pull_ok,
)
from src.sentiment_superindex.data.scraper_utils import (
    load_cached_series,
    merge_series,
    save_cached_series,
)

YAHOO_CACHE_DIR = SSI_DATA_DIR / "yahoo"

# Provenance tags written to the cache's `source` column, mirroring the CNN F&G convention
# (`real_cnn_api` / `wayback_reconstructed` / `crypto_proxy`) so a reader can always tell a
# live print from a carried-forward one.
SOURCE_LIVE = "yahoo_live"
SOURCE_CACHED = "yahoo_cached"
SOURCE_CBOE = "cboe_live"


def cache_path_for(ticker: str) -> Path:
    """`^VIX` -> `.../yahoo/vix.csv`, `BRK-B` -> `.../yahoo/brk_b.csv`."""
    slug = re.sub(r"[^a-z0-9]+", "_", ticker.lower()).strip("_")
    return YAHOO_CACHE_DIR / f"{slug}.csv"


def cached_yahoo_close(ticker: str, start: str = "1990-01-01") -> pd.Series:
    """Yahoo close series for `ticker`, merged into and served from a local CSV cache.

    Never raises: a failed or empty fetch is logged (see ``pull_guard``) and the cached history
    is returned unchanged, so the caller sees an ageing series rather than an empty one.
    """
    source_id = f"ssi_yahoo_{ticker}"
    path = cache_path_for(ticker)
    cached, cached_source = load_cached_series(path, value_col="close", extra_col="source")

    # CBOE publishes VIX / VIX3M / SKEW itself and is current same-day, so it is tried first
    # for those three. Yahoo remains the fallback (and the only source for ETF legs), which
    # also preserves the pre-2009 VIX3M history Yahoo has and CBOE does not.
    live_tag = SOURCE_LIVE
    live = cboe_indices.fetch_for_ticker(ticker)
    if not live.empty:
        live_tag = SOURCE_CBOE
    else:
        try:
            live = fetch_yahoo_close(ticker, start=start)
        except Exception as exc:
            log_pull_failure(source_id, exc, note=f"falling back to {len(cached)} cached rows")
            return cached

    if live.empty:
        log_pull_empty(
            source_id,
            note=f"no live rows from CBOE or yfinance; serving {len(cached)} cached rows",
        )
        return cached

    live = live[~live.index.duplicated(keep="last")].sort_index()

    # A shorter-than-cached tail is exactly the ^VIX3M failure mode this module exists for:
    # worth a log line, but the merge below already repairs it.
    if not cached.empty and live.index.max() < cached.index.max():
        log_pull_empty(
            source_id,
            note=(
                f"live tail {live.index.max().date()} is behind cached "
                f"{cached.index.max().date()}; cache retained"
            ),
        )

    merged = merge_series(cached, live)
    if not merged.empty:
        source = cached_source.reindex(merged.index)
        source.loc[live.index.intersection(merged.index)] = live_tag
        source = source.fillna(SOURCE_CACHED)
        save_cached_series(
            merged, path, value_col="close", extra_col="source", extra_series=source
        )

    log_pull_ok(source_id, len(merged), merged.index.max() if not merged.empty else None)
    return merged
