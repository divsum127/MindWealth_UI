"""Yahoo-derived SSI inputs.

All four derived series below combine two or more Yahoo legs. They read through
``yahoo_cache.cached_yahoo_close`` rather than calling ``fetch_yahoo_close`` directly, because
the join is where a partial Yahoo response used to become a missing SSI input: an inner join
against a truncated leg silently shortens the result to the shorter leg's index, and anything
past the staleness cap is then dropped from scoring entirely.

Concretely (audit 2026-08-18): ^VIX returned through the current day while ^VIX3M stopped at
2026-07-17, so ``vix_ratio`` -- computed as an inner join of the two -- had no value newer than
2026-07-17 and was dropped as expired, taking a Layer 2 gate with it. Reading both legs from
cache first means the older leg is carried forward from disk and the ratio survives.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.sentiment_superindex.data.yahoo_cache import cached_yahoo_close


def fetch_close(ticker: str, start: str = "2010-01-01") -> pd.Series:
    return cached_yahoo_close(ticker, start=start)


def hyg_lqd_ratio(start: str = "2010-01-01") -> pd.Series:
    hyg = cached_yahoo_close("HYG", start=start)
    lqd = cached_yahoo_close("LQD", start=start)
    df = pd.DataFrame({"hyg": hyg, "lqd": lqd}).dropna()
    return (df["hyg"] / df["lqd"]).rename("hyg_lqd")


def vix_ratio_series(start: str = "2007-01-01") -> pd.Series:
    """VIX term structure as VIX / VIX3M (spot over 3-month).

    Ratio > 1 → backwardation (near-term vol elevated) — stress territory.
    Ratio < 1 → contango (normal calm market). Matches SSI thresholds and docs.

    Note the convention is the reciprocal of ``macro_intelligence.data.yahoo_pull``'s
    ``vix_term_structure`` (VIX3M / VIX). Both are correct for their own consumers and
    ``scripts/verify_vxts_feed.py`` exists to keep the two from being confused.
    """
    vix = cached_yahoo_close("^VIX", start=start)
    vix3m = cached_yahoo_close("^VIX3M", start=start)
    df = pd.DataFrame({"vix": vix, "vix3m": vix3m}).dropna()
    return (df["vix"] / df["vix3m"]).rename("vix_ratio")


def dbmf_beta_vs_spy(window: int = 21, start: str = "2015-01-01") -> pd.Series:
    dbmf = cached_yahoo_close("DBMF", start=start)
    spy = cached_yahoo_close("SPY", start=start)
    dbmf_ret = dbmf.pct_change()
    spy_ret = spy.pct_change()
    aligned = pd.DataFrame({"dbmf": dbmf_ret, "spy": spy_ret}).dropna()
    cov = aligned["dbmf"].rolling(window).cov(aligned["spy"])
    var = aligned["spy"].rolling(window).var()
    beta = cov / var.replace(0, np.nan)
    return beta.rename("dbmf_beta")
