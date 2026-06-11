"""Load all SSI input series (Layers 1–3 per DATA_SOURCES.yaml)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.sentiment_superindex.data.aaii_pull import fetch_aaii_spread
from src.sentiment_superindex.data.cftc_ssi import cftc_layer3_snapshot
from src.sentiment_superindex.data.cnn_fear_greed import load_cnn_series
from src.sentiment_superindex.data.mcclellan_pull import fetch_mcclellan_oscillator
from src.sentiment_superindex.data.naaim_pull import fetch_naaim_exposure
from src.sentiment_superindex.data.nh_nl_pull import fetch_nh_nl_ratio
from src.sentiment_superindex.data.pct_200dma_pull import fetch_pct_above_200dma
from src.sentiment_superindex.data.skew_pull import fetch_skew
from src.sentiment_superindex.data.yahoo_inputs import dbmf_beta_vs_spy, hyg_lqd_ratio, vix_ratio_series

_CACHE: dict[str, pd.Series] = {}


def load_all_series(force: bool = False) -> dict[str, pd.Series]:
    if _CACHE and not force:
        return _CACHE
    _CACHE.clear()
    _CACHE.update(
        {
            "hyg_lqd": hyg_lqd_ratio("2010-01-01"),
            "dbmf_beta": dbmf_beta_vs_spy(21, "2015-01-01"),
            "cnn_fg": load_cnn_series(),
            "vix_ratio": vix_ratio_series("2007-01-01"),
            "aaii_spread": fetch_aaii_spread(),
            "naaim_exposure": fetch_naaim_exposure(),
            "pct_above_200dma": fetch_pct_above_200dma("2015-01-01"),
            "mcclellan": fetch_mcclellan_oscillator("2010-01-01"),
            "skew": fetch_skew("1990-01-01"),
            "nh_nl_ratio": fetch_nh_nl_ratio("2010-01-01"),
        }
    )
    return _CACHE


def values_as_of(series: dict[str, pd.Series], as_of: pd.Timestamp) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for key, s in series.items():
        if s is None or s.empty:
            out[key] = None
            continue
        sl = s.loc[:as_of].dropna()
        out[key] = float(sl.iloc[-1]) if not sl.empty else None
    return out


def layer3_for_date(as_of: str) -> dict[str, Any]:
    return cftc_layer3_snapshot(as_of)
