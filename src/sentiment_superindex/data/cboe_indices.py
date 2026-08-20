"""CBOE daily index history (VIX, VIX3M, SKEW) -- the authoritative free source.

These three SSI legs used to come from Yahoo, which stopped being reliable for them. As of the
2026-08-18 audit ``yf.download("^VIX3M")`` returns a frame that ends 2026-07-17 and never
advances, and ``^VXV`` -- the fallback ``macro_intelligence.data.yahoo_pull`` reaches for -- is
delisted outright. Because ``vix_ratio`` inner-joins ^VIX with ^VIX3M, a dead ^VIX3M silently
deleted the whole VIX term-structure input from Layer 2.

CBOE publishes the same series itself, free, no key, updated same-day:

    https://cdn.cboe.com/api/global/us_indices/daily_prices/<INDEX>_History.csv

Verified 2026-08-18 -- VIX 1990-01-02..2026-08-17 (9,252 rows), VIX3M 2009-09-18..2026-08-17
(4,253 rows), SKEW 1990-01-02..2026-08-17 (9,207 rows), all carrying Monday's close while Yahoo
was still four days behind on SKEW and a month behind on VIX3M. Values agree with the previous
Yahoo prints (SKEW 138.36 on 2026-08-14).

CBOE is the index publisher, so it is upstream of Yahoo rather than another scrape of it. It is
used as primary and Yahoo is kept as fallback: VIX3M history on CBOE begins 2009-09-18 whereas
Yahoo reaches back to 2007, and the disk cache in ``yahoo_cache`` unions both so the older
Yahoo-sourced history is preserved rather than truncated to CBOE's start.

The repo already scrapes CBOE for the put/call ratio (``put_call_pull``), so this adds a source
host that is already trusted here, not a new dependency.
"""

from __future__ import annotations

import io

import pandas as pd

from src.sentiment_superindex.data.pull_guard import (
    log_pull_empty,
    log_pull_failure,
    log_pull_ok,
)
from src.sentiment_superindex.data.scraper_utils import BROWSER_HEADERS, http_get

CBOE_HISTORY_URL = (
    "https://cdn.cboe.com/api/global/us_indices/daily_prices/{index}_History.csv"
)

# Yahoo ticker -> CBOE index name. Only indices CBOE itself publishes belong here; ETFs
# (HYG, LQD, DBMF, SPY) stay on Yahoo because CBOE does not carry them.
CBOE_INDEX_BY_TICKER: dict[str, str] = {
    "^VIX": "VIX",
    "^VIX3M": "VIX3M",
    "^SKEW": "SKEW",
}


def supports(ticker: str) -> bool:
    return ticker.upper() in CBOE_INDEX_BY_TICKER


def fetch_cboe_index_close(index: str) -> pd.Series:
    """Daily close for a CBOE index. Empty Series on any failure -- never raises.

    The history files are either OHLC (VIX, VIX3M) or a single value column (SKEW), so the
    close is resolved by name with a positional fallback rather than assumed.
    """
    source_id = f"ssi_cboe_{index}"
    url = CBOE_HISTORY_URL.format(index=index)
    try:
        resp = http_get(url, headers=BROWSER_HEADERS, timeout=40)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
    except Exception as exc:
        log_pull_failure(source_id, exc)
        return pd.Series(dtype=float)

    if df.empty or df.shape[1] < 2:
        log_pull_empty(source_id, note=f"{url} returned {df.shape} frame")
        return pd.Series(dtype=float)

    cols = {str(c).strip().upper(): c for c in df.columns}
    date_col = cols.get("DATE", df.columns[0])
    value_col = cols.get("CLOSE") or cols.get(index.upper()) or df.columns[-1]

    out = df[[date_col, value_col]].copy()
    out[date_col] = pd.to_datetime(out[date_col], errors="coerce")
    out[value_col] = pd.to_numeric(out[value_col], errors="coerce")
    out = out.dropna()
    if out.empty:
        log_pull_empty(source_id, note=f"{url} parsed to zero usable rows")
        return pd.Series(dtype=float)

    series = (
        out.set_index(date_col)[value_col]
        .sort_index()
        .astype(float)
        .rename(index.lower())
    )
    series = series[~series.index.duplicated(keep="last")]
    log_pull_ok(source_id, len(series), series.index.max())
    return series


def fetch_for_ticker(ticker: str) -> pd.Series:
    """CBOE close series for a Yahoo-style ticker, or empty if CBOE does not publish it."""
    index = CBOE_INDEX_BY_TICKER.get(ticker.upper())
    if not index:
        return pd.Series(dtype=float)
    return fetch_cboe_index_close(index)
