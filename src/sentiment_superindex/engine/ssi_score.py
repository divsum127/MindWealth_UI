"""Composite SSI level and 5-year percentile (3-layer superindex)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.sentiment_superindex.config import load_config
from src.sentiment_superindex.data.pull_all import load_all_series
from src.sentiment_superindex.engine.superindex import build_superindex, normalize_component

# Re-export for tests and validation scripts that import from ssi_score.
_normalize_component = normalize_component

_HIST_CACHE: pd.Series | None = None


def invalidate_ssi_history_cache() -> None:
    global _HIST_CACHE
    _HIST_CACHE = None


def build_ssi_history(start: str = "2015-01-01", *, force: bool = False) -> pd.Series:
    global _HIST_CACHE
    if _HIST_CACHE is not None and not force:
        return _HIST_CACHE
    series = load_all_series(force=True)
    idx = series["hyg_lqd"].index
    for s in series.values():
        idx = idx.union(s.index)
    idx = idx[idx >= pd.Timestamp(start)].sort_values()

    levels: list[tuple[pd.Timestamp, float]] = []
    for dt in idx:
        result = build_superindex(dt, series=series)
        layers = result.get("layers", {})
        if any(layer.get("score") is None for layer in layers.values()):
            continue
        levels.append((dt, float(result["ssi_level"])))
    if not levels:
        out = pd.Series(dtype=float)
    else:
        out = pd.Series(dict(levels)).sort_index().rename("ssi_level")
    _HIST_CACHE = out
    return out


def compute_ssi_at_date(as_of: str | pd.Timestamp) -> tuple[float, float | None, dict[str, Any]]:
    as_of_ts = pd.Timestamp(as_of)
    cfg = load_config()
    years = cfg.get("ssi_score", {}).get("history_years", 5)

    result = build_superindex(as_of_ts)
    level = float(result["ssi_level"])
    components: dict[str, Any] = {"layers": result.get("layers", {})}
    for layer in result.get("layers", {}).values():
        for key, comp in layer.get("components", {}).items():
            components[key] = comp

    hist_levels = build_ssi_history()
    hist_slice = hist_levels.loc[as_of_ts - pd.DateOffset(years=years) : as_of_ts]
    if len(hist_slice) < 20:
        hist_slice = hist_levels.loc[:as_of_ts]
    pctile = None
    if len(hist_slice) >= 10:
        pctile = float((hist_slice <= level).sum() / len(hist_slice) * 100)

    return level, pctile, components
