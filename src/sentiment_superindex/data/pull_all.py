"""Load all SSI input series (Layers 1–3 per DATA_SOURCES.yaml)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.macro_intelligence.data.cftc_pull import (
    fetch_cftc_asset_manager_net,
    fetch_cftc_fast_money_net,
    refresh_cftc_zip_if_stale,
)
from src.sentiment_superindex.data.aaii_pull import fetch_aaii_spread
from src.sentiment_superindex.data.cftc_ssi import cftc_layer3_snapshot
from src.sentiment_superindex.data.cnn_fear_greed import load_cnn_series
from src.sentiment_superindex.data.margin_debt_pull import fetch_margin_debt
from src.sentiment_superindex.data.mcclellan_pull import fetch_mcclellan_oscillator
from src.sentiment_superindex.data.naaim_pull import fetch_naaim_exposure
from src.sentiment_superindex.data.nh_nl_pull import fetch_nh_nl_ratio
from src.sentiment_superindex.data.pct_200dma_pull import fetch_pct_above_200dma
from src.sentiment_superindex.data.put_call_pull import fetch_put_call_ema
from src.sentiment_superindex.data.skew_pull import fetch_skew
from src.sentiment_superindex.data.staleness import observation_as_of
from src.sentiment_superindex.data.yahoo_inputs import dbmf_beta_vs_spy, hyg_lqd_ratio, vix_ratio_series

_CACHE: dict[str, pd.Series] = {}


def _gross_net_series() -> pd.Series:
    fm = fetch_cftc_fast_money_net()
    rm = fetch_cftc_asset_manager_net()
    if fm.empty or rm.empty:
        return pd.Series(dtype=float, name="gross_net")
    combined = fm.add(rm, fill_value=0).sort_index()
    combined.name = "gross_net"
    return combined.astype(float)


def load_all_series(force: bool = False) -> dict[str, pd.Series]:
    if _CACHE and not force:
        return _CACHE

    # The SSI job had no way to obtain a newer COT file: only the *macro* pull path called
    # refresh, so SSI read whatever zip happened to be on disk. Combined with cron order --
    # SSI 04:00 ET against a CFTC release at Friday 15:30 ET -- Layer 3 ran up to 2.5 days
    # behind a release that had already published, then aged past its staleness cap and
    # dropped out entirely. Refreshing here is what closes that window.
    refresh_cftc_zip_if_stale()

    _CACHE.clear()
    _CACHE.update(
        {
            "hyg_lqd": hyg_lqd_ratio("2010-01-01"),
            "dbmf_beta": dbmf_beta_vs_spy(21, "2015-01-01"),
            "cnn_fg": load_cnn_series(),
            "vix_ratio": vix_ratio_series("2007-01-01"),
            "aaii_spread": fetch_aaii_spread(),
            "naaim_exposure": fetch_naaim_exposure(),
            "put_call_ema": fetch_put_call_ema(),
            "pct_above_200dma": fetch_pct_above_200dma("2015-01-01"),
            "mcclellan": fetch_mcclellan_oscillator("2010-01-01"),
            "skew": fetch_skew("1990-01-01"),
            "nh_nl_ratio": fetch_nh_nl_ratio("2010-01-01"),
            "cftc_fm_net": fetch_cftc_fast_money_net(),
            "cftc_rm_net": fetch_cftc_asset_manager_net(),
            "gross_net": _gross_net_series(),
            "margin_debt": fetch_margin_debt(),
        }
    )
    return _CACHE


def values_as_of(series: dict[str, pd.Series], as_of: pd.Timestamp) -> dict[str, float | None]:
    """Point-in-time values with cadence-aware max-stale drop (see observation_as_of)."""
    out: dict[str, float | None] = {}
    for key, s in series.items():
        raw, _, _ = observation_as_of(s, as_of, series_key=key)
        out[key] = raw
    return out


def layer3_for_date(as_of: str) -> dict[str, Any]:
    return cftc_layer3_snapshot(as_of)
