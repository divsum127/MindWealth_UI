"""Composite SSI level and 5-year percentile."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.sentiment_superindex.config import load_config
from src.sentiment_superindex.data.pull_all import load_all_series


def _zscore(value: float, history: pd.Series, clip: float) -> float:
    h = history.dropna()
    if len(h) < 30:
        return 0.0
    mu, sigma = float(h.mean()), float(h.std())
    if sigma < 1e-9:
        return 0.0
    z = (value - mu) / sigma
    return float(np.clip(z, -clip, clip))


def _normalize_component(key: str, value: float, history: pd.Series, clip: float) -> float:
    """Map to roughly [-1, 1] risk-off (negative) vs risk-on (positive)."""
    z = _zscore(value, history, clip)
    if key == "hyg_lqd":
        return z
    if key == "dbmf_beta":
        return -z
    if key == "cnn_fg":
        if value <= 25:
            return 0.8
        if value >= 75:
            return -0.8
        return (50 - value) / 50
    if key == "vix_ratio":
        if value >= 1.1:
            return -0.7
        if value <= 0.95:
            return 0.5
        return (1.0 - value) * 2
    return z


def build_ssi_history(start: str = "2015-01-01") -> pd.Series:
    series = load_all_series(force=True)
    cfg = load_config()
    years = cfg.get("ssi_score", {}).get("history_years", 5)
    clip = cfg.get("ssi_score", {}).get("zscore_clip", 3.0)
    weights = cfg.get("ssi_score", {}).get("weights", {})

    idx = series["hyg_lqd"].index
    for s in series.values():
        idx = idx.union(s.index)
    idx = idx[idx >= pd.Timestamp(start)].sort_values()

    levels = []
    for dt in idx:
        vals = {k: float(s.loc[:dt].dropna().iloc[-1]) if not s.loc[:dt].dropna().empty else np.nan for k, s in series.items()}
        # Only require the weighted components to have data; auxiliary series (NAAIM, AAII, breadth)
        # are not part of the SSI score formula and should not gate history construction.
        if any(np.isnan(vals.get(key, float("nan"))) for key in weights if key in series):
            continue
        score = 0.0
        wsum = 0.0
        for key, w in weights.items():
            if key not in vals or key not in series:
                continue
            hist = series[key].loc[:dt]
            comp = _normalize_component(key, vals[key], hist, clip)
            score += float(w) * comp
            wsum += float(w)
        if wsum > 0:
            levels.append((dt, score / wsum))
    if not levels:
        return pd.Series(dtype=float)
    return pd.Series(dict(levels)).sort_index().rename("ssi_level")


def compute_ssi_at_date(as_of: str | pd.Timestamp) -> tuple[float, float | None, dict[str, Any]]:
    as_of_ts = pd.Timestamp(as_of)
    cfg = load_config()
    clip = cfg.get("ssi_score", {}).get("zscore_clip", 3.0)
    weights = cfg.get("ssi_score", {}).get("weights", {})
    years = cfg.get("ssi_score", {}).get("history_years", 5)

    series = load_all_series()
    vals = {k: float(s.loc[:as_of_ts].dropna().iloc[-1]) if not s.loc[:as_of_ts].dropna().empty else None for k, s in series.items()}

    score = 0.0
    wsum = 0.0
    components: dict[str, Any] = {}
    for key, w in weights.items():
        if vals.get(key) is None or key not in series:
            components[key] = {"raw": None, "norm": None}
            continue
        hist = series[key].loc[as_of_ts - pd.DateOffset(years=years) : as_of_ts]
        norm = _normalize_component(key, vals[key], hist, clip)
        components[key] = {"raw": vals[key], "norm": norm}
        score += float(w) * norm
        wsum += float(w)

    level = score / wsum if wsum > 0 else 0.0

    hist_levels = build_ssi_history()
    hist_slice = hist_levels.loc[as_of_ts - pd.DateOffset(years=years) : as_of_ts]
    if len(hist_slice) < 20:
        hist_slice = hist_levels.loc[:as_of_ts]
    pctile = None
    if len(hist_slice) >= 10:
        pctile = float((hist_slice <= level).sum() / len(hist_slice) * 100)

    return level, pctile, components
