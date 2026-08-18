"""SSI Test 22: Layer 2 gate 2-D grid — z threshold × min_confirmed (6 gates).

Tests gate_z_min and min_confirmed jointly because they interact: a lower z bar
with a higher count requirement may be equivalent to the reverse.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.sentiment_superindex.analysis.forward_metrics import load_spx, returns_at_horizons, summarize_returns
from src.sentiment_superindex.analysis.report_utils import metrics_table, save_artifact, write_md_snippet
from src.sentiment_superindex.analysis.ssi_history import build_ssi_history_frame
from src.sentiment_superindex.config import load_config
from src.sentiment_superindex.data.pull_all import load_all_series, values_as_of
from src.sentiment_superindex.engine.layer2 import _pctile_in_history
from src.sentiment_superindex.engine.superindex import DEFAULT_LAYER_INPUTS, build_layer2

Z_THRESHOLDS = [0.0, 0.25, 0.5, 0.75, 1.0]
MIN_CONFIRMED_GRID = [1, 2, 3, 4]
GATE_TOTAL = 6
Z_GATE_KEYS = ("mcclellan", "nh_nl_ratio", "skew", "pct_above_200dma")


def _precompute_day_features(
    idx: pd.DatetimeIndex,
    *,
    series: dict[str, pd.Series],
    votes_cfg: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray, dict[str, np.ndarray]]:
    """Legacy long/short tallies + z-gate norm arrays for each trading day."""
    legacy_long = np.zeros(len(idx), dtype=np.int8)
    legacy_short = np.zeros(len(idx), dtype=np.int8)
    norms: dict[str, list[float]] = {key: [] for key in Z_GATE_KEYS}
    hyg_series = series.get("hyg_lqd")
    hyg_cfg = votes_cfg.get("hyg_lqd", {})
    vix_cfg = votes_cfg.get("vix_ratio", {})

    for i, dt in enumerate(idx):
        vals = values_as_of(series, dt)
        hyg = vals.get("hyg_lqd")
        if hyg is not None and hyg_series is not None:
            pct = _pctile_in_history(hyg, hyg_series.loc[:dt])
            if pct >= hyg_cfg.get("risk_on_pctile_min", 70):
                legacy_long[i] = 1
            elif pct <= hyg_cfg.get("risk_off_pctile_max", 30):
                legacy_short[i] = 1
        vr = vals.get("vix_ratio")
        if vr is not None:
            if vr >= vix_cfg.get("stress_min", 1.05):
                legacy_short[i] = 1
            elif vr <= vix_cfg.get("complacency_max", 0.95):
                legacy_long[i] = 1

        components = build_layer2(dt, series=series).get("components", {})
        for key in Z_GATE_KEYS:
            comp = components.get(key) or {}
            norm = comp.get("norm")
            norms[key].append(float(norm) if norm is not None else np.nan)

    norm_matrix = {key: np.array(vals, dtype=float) for key, vals in norms.items()}
    return legacy_long, legacy_short, norm_matrix


def _long_confirmed_mask(
    conf_long: np.ndarray,
    conf_short: np.ndarray,
    min_confirmed: int,
) -> np.ndarray:
    return (conf_long >= min_confirmed) & (conf_short < min_confirmed)


def run_and_report(start: str = "2015-01-01") -> dict[str, Any]:
    cfg = load_config()
    layer2_keys = cfg.get("ssi_score", {}).get("layers", {}).get(
        "layer2", DEFAULT_LAYER_INPUTS["layer2"]
    )
    votes_cfg = cfg.get("layer2", {}).get("votes", {})
    long_pctile = float(cfg.get("thresholds", {}).get("long_entry_pctile", 20))

    series = load_all_series()
    hist = build_ssi_history_frame(start)
    spx = load_spx(start)
    idx = hist.index
    long_gate = hist["ssi_pctile_5y"] <= long_pctile
    total_days = len(idx)

    legacy_long, legacy_short, norm_matrix = _precompute_day_features(idx, series=series, votes_cfg=votes_cfg)

    rows: list[dict[str, Any]] = []
    for z_thr in Z_THRESHOLDS:
        z_long = np.zeros(total_days, dtype=np.int8)
        z_short = np.zeros(total_days, dtype=np.int8)
        for key in Z_GATE_KEYS:
            norm = norm_matrix[key]
            valid = ~np.isnan(norm)
            z_long += (valid & (norm >= z_thr) & (norm > 0)).astype(np.int8)
            z_short += (valid & (norm <= -z_thr) & (norm < 0)).astype(np.int8)

        conf_long = legacy_long + z_long
        conf_short = legacy_short + z_short

        for min_conf in MIN_CONFIRMED_GRID:
            long_confirmed_mask = _long_confirmed_mask(conf_long, conf_short, min_conf)

            long_gate_dates = idx[long_confirmed_mask & long_gate.to_numpy()]
            fp_dates = idx[long_confirmed_mask & (~long_gate).to_numpy()]
            n_signal = int(long_confirmed_mask.sum())
            n_long_gate = int(len(long_gate_dates))
            n_fp = int(len(fp_dates))

            long_metrics = summarize_returns(returns_at_horizons(spx, long_gate_dates))
            fp_metrics = summarize_returns(returns_at_horizons(spx, fp_dates))

            rows.append(
                {
                    "z_threshold": z_thr,
                    "min_confirmed": min_conf,
                    "gate_total": GATE_TOTAL,
                    "n_trading_days": total_days,
                    "n_long_confirmed": n_signal,
                    "signal_frequency_pct": round(n_signal / total_days * 100, 2) if total_days else None,
                    "n_long_gate_confirmed": n_long_gate,
                    "n_false_positive": n_fp,
                    "hit_rate_3m_pct": long_metrics.get("3m", {}).get("win_pct"),
                    "false_positive_3m_pct": fp_metrics.get("3m", {}).get("win_pct"),
                    "long_gate_metrics": long_metrics,
                    "false_positive_metrics": fp_metrics,
                }
            )

    payload = {
        "test_id": "22_layer2_gate_grid",
        "description": (
            "Joint 2-D sweep of gate_z_min × min_confirmed on 6-gate Layer 2 "
            "(4 z-gate inputs + legacy HYG/VIX). LONG_CONFIRMED required."
        ),
        "start": start,
        "long_entry_pctile": long_pctile,
        "z_thresholds": Z_THRESHOLDS,
        "min_confirmed_grid": MIN_CONFIRMED_GRID,
        "production_defaults": {
            "gate_z_min": float(cfg.get("layer2", {}).get("gate_z_min", 0.5)),
            "min_confirmed": int(cfg.get("layer2", {}).get("min_confirmed", 2)),
        },
        "rows": rows,
    }
    save_artifact("22_layer2_gate_grid", payload)

    md = "# Test 22: Layer 2 gate 2-D grid (z threshold × min_confirmed)\n\n"
    md += (
        f"**6-gate production logic.** Long gate = SSI 5y pctile ≤ {long_pctile}. "
        f"Signal = `LONG_CONFIRMED` (≥N of 6 gates agree long, short tally < N). "
        f"Production today: `gate_z_min={payload['production_defaults']['gate_z_min']}`, "
        f"`min_confirmed={payload['production_defaults']['min_confirmed']}`.\n\n"
    )
    md += "## Summary grid (3m metrics)\n\n"
    md += (
        "| z ≥ | min of 6 | n signal | freq % | n long+gate | 3m hit % | n FP | 3m FP win % | 3m avg (long) | 3m avg (FP) |\n"
        "|-----|----------|----------|--------|-------------|----------|------|-------------|---------------|-------------|\n"
    )
    for r in rows:
        lm = r["long_gate_metrics"].get("3m", {})
        fm = r["false_positive_metrics"].get("3m", {})
        md += (
            f"| {r['z_threshold']} | {r['min_confirmed']} | {r['n_long_confirmed']} | "
            f"{r['signal_frequency_pct']} | {r['n_long_gate_confirmed']} | "
            f"{r['hit_rate_3m_pct']} | {r['n_false_positive']} | {r['false_positive_3m_pct']} | "
            f"{lm.get('avg', '—')} | {fm.get('avg', '—')} |\n"
        )

    md += "\n## Detail by cell\n"
    for r in rows:
        md += (
            f"\n### z ≥ {r['z_threshold']}, min_confirmed = {r['min_confirmed']} of {GATE_TOTAL}\n"
            f"- Signal frequency: {r['n_long_confirmed']} / {total_days} days ({r['signal_frequency_pct']}%)\n"
            f"- Long gate + confirmed: n={r['n_long_gate_confirmed']}\n"
            f"- False positives (confirmed, not long gate): n={r['n_false_positive']}\n"
        )
        md += metrics_table(r["long_gate_metrics"], "Long gate + LONG_CONFIRMED")
        md += metrics_table(r["false_positive_metrics"], "LONG_CONFIRMED, not long gate (FP)")

    write_md_snippet("22_layer2_gate_grid", md)
    return payload
