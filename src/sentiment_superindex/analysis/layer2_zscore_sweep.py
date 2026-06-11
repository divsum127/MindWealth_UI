"""Part 1 / Test 10b: Layer 2 z-score confirmation threshold sweep (0–2.0)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.sentiment_superindex.analysis.forward_metrics import load_spx, returns_at_horizons, summarize_returns
from src.sentiment_superindex.analysis.report_utils import save_artifact, write_md_snippet
from src.sentiment_superindex.analysis.ssi_history import build_ssi_history_frame
from src.sentiment_superindex.config import load_config
from src.sentiment_superindex.data.pull_all import load_all_series


def _rolling_z_series(series: pd.Series, window: int = 756, clip: float = 3.0) -> pd.Series:
    mu = series.rolling(window, min_periods=60).mean()
    sigma = series.rolling(window, min_periods=60).std()
    z = (series - mu) / sigma.replace(0, np.nan)
    return z.clip(-clip, clip)


def _confirm_count_frame(series: dict[str, pd.Series], idx: pd.DatetimeIndex) -> pd.DataFrame:
    keys = ("hyg_lqd", "dbmf_beta", "cnn_fg", "vix_ratio")
    z_frames = []
    for key in keys:
        s = series.get(key)
        if s is None or s.empty:
            continue
        z = _rolling_z_series(s.reindex(idx).ffill())
        z_frames.append((abs(z) >= 0.5).astype(int).rename(key))
    if not z_frames:
        return pd.DataFrame(index=idx)
    return pd.concat(z_frames, axis=1).fillna(0)


def run_and_report(start: str = "2015-01-01") -> dict[str, Any]:
    cfg = load_config()
    min_conf = int(cfg.get("layer2", {}).get("min_confirmed", 2))
    series = load_all_series()
    hist = build_ssi_history_frame(start)
    spx = load_spx(start)
    idx = hist.index
    long_gate = hist["ssi_pctile_5y"] <= float(cfg.get("thresholds", {}).get("long_entry_pctile", 20))
    confirms = _confirm_count_frame(series, idx)
    abs_z = pd.DataFrame({k: _rolling_z_series(series[k].reindex(idx).ffill()).abs() for k in confirms.columns})

    thresholds = [round(x, 2) for x in np.arange(0, 2.01, 0.25)]
    rows: list[dict[str, Any]] = []
    for z_thr in thresholds:
        count = (abs_z >= z_thr).sum(axis=1)
        mask = count >= min_conf
        long_dates = idx[mask & long_gate]
        non_long_dates = idx[mask & ~long_gate]
        long_m = summarize_returns(returns_at_horizons(spx, long_dates))
        non_long_m = summarize_returns(returns_at_horizons(spx, non_long_dates))
        rows.append(
            {
                "z_threshold": z_thr,
                "min_confirmed": min_conf,
                "n_long_gate_confirmed": int(len(long_dates)),
                "n_non_long_confirmed": int(len(non_long_dates)),
                "hit_rate_3m_pct": long_m.get("3m", {}).get("win_pct"),
                "false_positive_3m_pct": non_long_m.get("3m", {}).get("win_pct"),
                "long_metrics": long_m,
                "non_long_metrics": non_long_m,
            }
        )

    payload = {"test_id": "20_layer2_zscore_sweep", "start": start, "rows": rows}
    save_artifact("20_layer2_zscore_sweep", payload)
    md = "# Test 10b: Layer 2 z-score threshold sweep\n\n"
    md += f"Require **≥{min_conf}** Layer-2 inputs with |z| ≥ threshold (3yr rolling).\n\n"
    md += "| z ≥ | n long+confirm | n non-long confirm | 3m hit % (long) | 3m win % (non-long) |\n"
    md += "|-----|----------------|--------------------|-----------------|---------------------|\n"
    for r in rows:
        md += (
            f"| {r['z_threshold']} | {r['n_long_gate_confirmed']} | {r['n_non_long_confirmed']} | "
            f"{r['hit_rate_3m_pct']} | {r['false_positive_3m_pct']} |\n"
        )
    write_md_snippet("20_layer2_zscore_sweep", md)
    return payload
