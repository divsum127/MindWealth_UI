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
from src.sentiment_superindex.data.pull_guard import log_pull_empty, log_pull_failure

# The WordPress page carried the exposure table until roughly end of July 2026, then dropped it
# in favour of iframes pointing at index.naaim.org. Kept as the first source because it is the
# canonical page and would be the one to come back.
NAAIM_URL = "https://www.naaim.org/programs/naaim-exposure-index/"
# The iframe the page now embeds. Still publicly readable and still a real <table>, but as of
# 2026-08-18 it is frozen at 2026-05-13 -- older than our own cache. Kept as a second source so
# the feed resumes automatically if NAAIM unfreezes it.
NAAIM_EMBED_URL = "https://index.naaim.org/embeddable/table"
CACHE_CSV = SSI_DATA_DIR / "naaim_exposure.csv"

SOURCE_SCRAPE = "naaim_scrape"
SOURCE_UNKNOWN = "naaim_legacy"
# Tag reserved for rows typed in by hand while the public feed is unavailable. Nothing writes
# it automatically -- it exists so a manual print is never mistaken for a scraped one.
SOURCE_MANUAL = "manual"


def fetch_naaim_exposure() -> pd.Series:
    """NAAIM exposure index, merged into the local cache.

    RE-CHECKED 2026-08-20 (cache last print 2026-07-29, 22 days stale): still nothing free.
    ``index.naaim.org/embeddable/table`` and ``/embeddable/chart`` both answer 200 but are frozen
    at 2026-05-13 and 2026-05-06; ``naaim.org/programs/naaim-exposure-index/`` 301s; the WordPress
    REST API returns newsletters only; the newest Wayback snapshot of the index page is
    2026-05-31; ``index.naaim.org/api/exposure`` 404s and ``api.naaim.org`` does not resolve.
    Do not spend another pass on this without a membership -- it is a product decision.

    NOTE (2026-08-18 audit): NAAIM has moved this index behind a member login. Every free
    source is now either gone or frozen -- the page's table was removed, index.naaim.org
    requires sign-in, both public iframes stopped updating in May 2026, the Wayback Machine has
    no snapshot after June 2026, the WordPress REST API exposes only monthly newsletters, and
    FRED carries no NAAIM series. This function therefore serves cached history that is ageing,
    and the layer-coverage gate in `superindex` is what keeps that from silently distorting the
    Layer 1 score. NAAIM is the single largest Layer 1 weight (0.35), so restoring it needs a
    product decision (membership, manual entry, or re-specced Layer 1 weights), not a code fix.
    """
    cached, cached_source = load_cached_series(
        CACHE_CSV, value_col="exposure", extra_col="source"
    )
    live = _scrape_naaim()
    merged = merge_series(cached, live)
    if not merged.empty:
        source = cached_source.reindex(merged.index)
        if not live.empty:
            source.loc[live.index.intersection(merged.index)] = SOURCE_SCRAPE
        source = source.fillna(SOURCE_UNKNOWN)
        save_cached_series(
            merged,
            CACHE_CSV,
            value_col="exposure",
            extra_col="source",
            extra_series=source,
        )
    return merged


def _scrape_naaim() -> pd.Series:
    """Scrape whichever NAAIM surface still publishes the table. Empty if none do."""
    for source_id, url in (
        ("ssi_naaim", NAAIM_URL),
        ("ssi_naaim_embed", NAAIM_EMBED_URL),
    ):
        series = _scrape_naaim_url(source_id, url)
        if not series.empty:
            return series

    log_pull_empty(
        "ssi_naaim",
        note=(
            "no NAAIM table on the page or the embeddable iframe; the public feed moved behind "
            "a member login (2026-08-18). Serving cached history only"
        ),
    )
    return pd.Series(dtype=float)


def _scrape_naaim_url(source_id: str, url: str) -> pd.Series:
    try:
        resp = http_get(url, headers=BROWSER_HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as exc:
        log_pull_failure(source_id, exc, note=url)
        return pd.Series(dtype=float)

    df = parse_html_table_dates(
        resp.text,
        # The page and the iframe label the column differently, so every spelling seen in the
        # wild is listed; parse_html_table_dates only coerces the ones actually present.
        value_cols=[
            "naaim_number",
            "naaim_number_mean/average",
            "naaim_number_mean_average",
        ],
    )
    if df.empty:
        return pd.Series(dtype=float)

    col = next(
        (c for c in df.columns if "naaim" in c.lower() and "number" in c.lower()),
        None,
    )
    if col is None:
        col = next(
            (c for c in df.columns if "naaim" in c.lower() and "mean" in c.lower()),
            None,
        )
    if col is None:
        col = df.columns[0]
    s = pd.to_numeric(df[col], errors="coerce").dropna()
    if s.empty:
        return pd.Series(dtype=float)
    s.name = "naaim_exposure"
    return s.astype(float)
