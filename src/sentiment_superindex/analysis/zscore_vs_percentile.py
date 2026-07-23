"""Test 9: Z-score SSI vs 3yr rolling percentile composite."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.sentiment_superindex.analysis.forward_metrics import load_spx, summarize_returns
from src.sentiment_superindex.analysis.report_utils import save_artifact, write_md_snippet
from src.sentiment_superindex.analysis.ssi_history import build_ssi_history_frame
from src.sentiment_superindex.config import load_config
from src.sentiment_superindex.data.pull_all import load_all_series


def build_percentile_ssi_history(start: str = "2010-01-01", window_days: int = 756) -> pd.Series:
    """3yr rolling percentile rank composite (distribution-agnostic)."""
    series = load_all_series(force=True)
    cfg = load_config()
    weights = cfg.get("ssi_score", {}).get("legacy_composite_weights", {})
    idx = series["hyg_lqd"].index
    for s in series.values():
        idx = idx.union(s.index)
    idx = idx[idx >= pd.Timestamp(start)].sort_values()
    levels = []
    for dt in idx:
        score_parts = []
        wsum = 0.0
        for key, w in weights.items():
            if key not in series:
                continue
            hist = series[key].loc[:dt].dropna().tail(window_days)
            if len(hist) < 30:
                continue
            val = float(series[key].loc[:dt].dropna().iloc[-1])
            pct = float((hist <= val).sum() / len(hist))
            score_parts.append(float(w) * (pct - 0.5) * 2)
            wsum += float(w)
        if wsum > 0:
            levels.append((dt, sum(score_parts) / wsum))
    return pd.Series(dict(levels)).sort_index().rename("ssi_pctile_composite")


def _crisis_metrics(levels: pd.Series, spx: pd.Series, windows: list[tuple[str, str]]) -> dict[str, Any]:
    from src.sentiment_superindex.analysis.forward_metrics import returns_at_horizons

    out = {}
    for name, (a, b) in windows:
        mask = (levels.index >= pd.Timestamp(a)) & (levels.index <= pd.Timestamp(b))
        dates = levels.index[mask & (levels <= levels.quantile(0.2))]
        if len(dates) < 3:
            dates = levels.index[mask]
        out[name] = summarize_returns(returns_at_horizons(spx, dates))
    return out


def run_and_report(start: str = "2010-01-01") -> dict[str, Any]:
    spx = load_spx(start)
    z_hist = build_ssi_history_frame(start)["ssi_level"]
    p_hist = build_percentile_ssi_history(start)
    crises = [("covid_2020", ("2020-02-01", "2020-04-30")), ("oct_2022", ("2022-09-01", "2022-12-31"))]
    z_crisis = _crisis_metrics(z_hist, spx, crises)
    p_crisis = _crisis_metrics(p_hist, spx, crises)
    payload = {
        "test_id": "09_zscore_vs_percentile",
        "note": "Parallel path only; production still uses z-score in ssi_score.py",
        "zscore_crisis": z_crisis,
        "percentile_crisis": p_crisis,
    }
    save_artifact("09_zscore_vs_percentile", payload)
    md = "# Test 9: Z-score vs percentile SSI\n\nProduction unchanged until SIGNOFF.\n\n"
    for name in ("covid_2020", "oct_2022"):
        md += f"\n## {name} — z-score\n{z_crisis.get(name)}\n## {name} — percentile composite\n{p_crisis.get(name)}\n"
    write_md_snippet("09_zscore_vs_percentile", md)
    return payload
