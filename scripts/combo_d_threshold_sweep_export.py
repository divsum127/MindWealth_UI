#!/usr/bin/env python3
"""Combo D threshold sweep — all horizons, CSV detail + experiment summary."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import UTC, datetime
from itertools import product
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.analysis.combo_threshold_sweep import (  # noqa: E402
    _aligned_dates,
    _reading_on,
    load_readings_panel,
)
from src.macro_intelligence.config import load_config  # noqa: E402
from src.macro_intelligence.data.yahoo_pull import fetch_yahoo_close  # noqa: E402
from src.macro_intelligence.engine.forward_returns import (  # noqa: E402
    _nyse_sessions,
    forward_return_pct,
)

DEFAULT_OUT = (
    ROOT
    / "testing/macro_th_exp/testingv1_feedback/csv_exports/combo_d_threshold_sweep"
)

HORIZONS: list[tuple[str, int, float]] = [
    ("1W", 5, 0.5),
    ("2W", 10, 1.0),
    ("3W", 15, 1.25),
    ("4W", 20, 1.25),
    ("1M", 21, 1.25),
    ("2M", 42, 2.5),
]

VXTS_GRID = [1.05, 1.08, 1.10, 1.12, 1.15, 1.18, 1.20]
CFTC_GRID = [75, 80, 85, 90, 92, 95]
VIX_GRID = [14, 15, 16, 18, 20, 22]
LEGS_GRID = [2, 3]
COOLDOWN_DAYS = 5


def _experiment_id(vxts: float, cftc: float, vix: float, legs: int) -> str:
    return f"D_vxts{vxts:.2f}_cftc{int(cftc)}_vix{int(vix)}_leg{legs}"


def _build_panel_arrays(
    panel: dict[str, list[dict[str, Any]]], dates: list[str]
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    vxts, cftc, vix = [], [], []
    for ds in dates:
        v = _reading_on(panel, "VXTS", ds)
        c = _reading_on(panel, "CFTC", ds)
        x = _reading_on(panel, "VIX", ds)
        vxts.append(float(v["raw"]) if v and v["raw"] is not None else np.nan)
        cftc.append(float(c["pctile"]) if c and c["pctile"] is not None else np.nan)
        vix.append(float(x["raw"]) if x and x["raw"] is not None else np.nan)
    return np.array(vxts), np.array(cftc), np.array(vix)


def _crossing_indices(in_band: np.ndarray, dates: list[str]) -> list[int]:
    """First-crossing indices with cooldown (same logic as _first_combo_crossings)."""
    events: list[int] = []
    prev = False
    cooldown_until: pd.Timestamp | None = None
    for i, ds in enumerate(dates):
        if np.isnan(in_band[i]):
            prev = False
            continue
        dt = pd.Timestamp(ds)
        if cooldown_until is not None and dt <= cooldown_until:
            prev = bool(in_band[i])
            continue
        cur = bool(in_band[i])
        if cur and not prev:
            events.append(i)
            cooldown_until = dt + pd.Timedelta(days=COOLDOWN_DAYS)
        prev = cur
    return events


def _precompute_forward_returns(
    dates: list[str],
    spx: pd.Series,
    sessions: pd.DatetimeIndex,
) -> dict[int, dict[str, float | None]]:
    """date_index -> horizon_label -> return %."""
    cache: dict[int, dict[str, float | None]] = {}
    for i, ds in enumerate(dates):
        cache[i] = {}
        for label, td, _ in HORIZONS:
            cache[i][label] = forward_return_pct(spx, pd.Timestamp(ds), td, sessions=sessions)
    return cache


def _horizon_stats_from_indices(
    indices: list[int],
    fwd_cache: dict[int, dict[str, float | None]],
    label: str,
    trading_days: int,
    benchmark: float,
    n_dates: int,
) -> dict[str, Any]:
    rets = [fwd_cache[i][label] for i in indices if fwd_cache[i][label] is not None]
    if not rets:
        return {
            "horizon": label,
            "trading_days": trading_days,
            "benchmark_pct": benchmark,
            "n_events": len(indices),
            "n_mature": 0,
            "bear_hit_rate_pct": None,
            "avg_spx_change_pct": None,
            "median_spx_change_pct": None,
            "min_spx_change_pct": None,
            "max_spx_change_pct": None,
            "std_spx_change_pct": None,
            "bear_avg_win_pct": None,
            "bear_avg_loss_pct": None,
            "pw_bear_expected_pct": None,
            "bear_excess_vs_benchmark_pp": None,
        }
    arr = np.array(rets, dtype=float)
    bear_hits = arr < 0
    hr = float(bear_hits.mean())
    wins = arr[bear_hits]
    losses = arr[~bear_hits]
    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss = float(losses.mean()) if len(losses) else 0.0
    pw = hr * avg_win + (1 - hr) * avg_loss
    return {
        "horizon": label,
        "trading_days": trading_days,
        "benchmark_pct": benchmark,
        "n_events": len(indices),
        "n_mature": len(rets),
        "bear_hit_rate_pct": round(hr * 100, 2),
        "avg_spx_change_pct": round(float(arr.mean()), 4),
        "median_spx_change_pct": round(float(np.median(arr)), 4),
        "min_spx_change_pct": round(float(arr.min()), 4),
        "max_spx_change_pct": round(float(arr.max()), 4),
        "std_spx_change_pct": round(float(arr.std()), 4),
        "bear_avg_win_pct": round(avg_win, 4),
        "bear_avg_loss_pct": round(avg_loss, 4),
        "pw_bear_expected_pct": round(pw, 4),
        "bear_excess_vs_benchmark_pp": round(pw - benchmark, 4),
    }


def _build_experiments(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    base_v = float(cfg.get("vxts_min", 1.10))
    base_c = float(cfg.get("cftc_min_pctile", 85))
    base_x = float(cfg.get("vix_max", 18))
    seen: set[tuple[float, float, float, int]] = set()
    exps: list[dict[str, Any]] = []

    def add(vxts: float, cftc: float, vix: float, legs: int, sweep_type: str) -> None:
        key = (vxts, cftc, vix, legs)
        if key in seen:
            return
        seen.add(key)
        is_config = (
            abs(vxts - base_v) < 1e-9
            and abs(cftc - base_c) < 1e-9
            and abs(vix - base_x) < 1e-9
            and legs == 3
        )
        exps.append(
            {
                "experiment_id": _experiment_id(vxts, cftc, vix, legs),
                "sweep_type": "config_baseline" if is_config else sweep_type,
                "vxts_min": vxts,
                "cftc_min_pctile": cftc,
                "vix_max": vix,
                "legs_required": legs,
                "is_config_baseline": is_config,
            }
        )

    add(base_v, base_c, base_x, 3, "config_baseline")
    add(base_v, base_c, base_x, 2, "legs_only")
    for vxts in VXTS_GRID:
        add(vxts, base_c, base_x, 3, "univariate_vxts")
    for cftc in CFTC_GRID:
        add(base_v, cftc, base_x, 3, "univariate_cftc")
    for vix in VIX_GRID:
        add(base_v, base_c, vix, 3, "univariate_vix")
    for vxts, cftc, vix, legs in product(VXTS_GRID, CFTC_GRID, VIX_GRID, LEGS_GRID):
        add(vxts, cftc, vix, legs, "factorial_grid")
    return exps


def run_sweep(
    out_dir: Path,
    panel_start: str = "2007-01-01",
    spx_start: str = "1990-01-01",
) -> dict[str, Any]:
    cfg = load_config().get("named_combos", {}).get("D", {})
    panel = load_readings_panel(panel_start)
    spx = fetch_yahoo_close("^GSPC", spx_start)
    sessions = _nyse_sessions()
    dates = _aligned_dates(panel, ["VXTS", "CFTC", "VIX"])
    vxts_arr, cftc_arr, vix_arr = _build_panel_arrays(panel, dates)
    valid = ~(np.isnan(vxts_arr) | np.isnan(cftc_arr) | np.isnan(vix_arr))

    print(f"Precomputing forward returns for {len(dates)} dates x {len(HORIZONS)} horizons...")
    fwd_cache = _precompute_forward_returns(dates, spx, sessions)

    experiments = _build_experiments(cfg)
    detail_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []

    for n, exp in enumerate(experiments, 1):
        vxts = exp["vxts_min"]
        cftc = exp["cftc_min_pctile"]
        vix = exp["vix_max"]
        legs = exp["legs_required"]
        leg_count = (
            (vxts_arr >= vxts).astype(int)
            + (cftc_arr >= cftc).astype(int)
            + (vix_arr <= vix).astype(int)
        )
        in_band = (leg_count >= legs) & valid
        event_idx = _crossing_indices(in_band, dates)

        horizon_stats: list[dict[str, Any]] = []
        for label, td, bench in HORIZONS:
            hs = _horizon_stats_from_indices(event_idx, fwd_cache, label, td, bench, len(dates))
            detail_rows.append(
                {
                    "experiment_id": exp["experiment_id"],
                    "sweep_type": exp["sweep_type"],
                    "is_config_baseline": exp["is_config_baseline"],
                    "vxts_min": vxts,
                    "cftc_min_pctile": cftc,
                    "vix_max": vix,
                    "legs_required": legs,
                    **hs,
                }
            )
            horizon_stats.append(hs)

        mature = [h for h in horizon_stats if h["n_mature"] > 0]
        hit_rates = [h["bear_hit_rate_pct"] for h in mature if h["bear_hit_rate_pct"] is not None]
        avg_changes = [h["avg_spx_change_pct"] for h in mature if h["avg_spx_change_pct"] is not None]
        best_hit_h = max(mature, key=lambda h: h["bear_hit_rate_pct"] or -1) if mature else None
        best_neg_avg_h = min(mature, key=lambda h: h["avg_spx_change_pct"] or 1e9) if mature else None

        summary_rows.append(
            {
                "experiment_id": exp["experiment_id"],
                "sweep_type": exp["sweep_type"],
                "is_config_baseline": exp["is_config_baseline"],
                "vxts_min": vxts,
                "cftc_min_pctile": cftc,
                "vix_max": vix,
                "legs_required": legs,
                "n_events": len(event_idx),
                "bear_hit_rate_mean_pct": round(float(np.mean(hit_rates)), 2) if hit_rates else None,
                "bear_hit_rate_min_pct": round(float(np.min(hit_rates)), 2) if hit_rates else None,
                "bear_hit_rate_max_pct": round(float(np.max(hit_rates)), 2) if hit_rates else None,
                "bear_hit_rate_std_pct": round(float(np.std(hit_rates)), 2) if len(hit_rates) > 1 else 0.0,
                "avg_spx_change_mean_pct": round(float(np.mean(avg_changes)), 4) if avg_changes else None,
                "avg_spx_change_min_pct": round(float(np.min(avg_changes)), 4) if avg_changes else None,
                "avg_spx_change_max_pct": round(float(np.max(avg_changes)), 4) if avg_changes else None,
                "best_bear_hit_horizon": best_hit_h["horizon"] if best_hit_h else None,
                "best_bear_hit_rate_pct": best_hit_h["bear_hit_rate_pct"] if best_hit_h else None,
                "most_negative_avg_horizon": best_neg_avg_h["horizon"] if best_neg_avg_h else None,
                "most_negative_avg_spx_pct": best_neg_avg_h["avg_spx_change_pct"] if best_neg_avg_h else None,
                **{f"hit_{h['horizon']}": h["bear_hit_rate_pct"] for h in horizon_stats},
                **{f"avg_spx_{h['horizon']}": h["avg_spx_change_pct"] for h in horizon_stats},
            }
        )
        if n % 50 == 0:
            print(f"  {n}/{len(experiments)} experiments done")

    out_dir.mkdir(parents=True, exist_ok=True)
    detail_path = out_dir / "combo_d_threshold_sweep_all_horizons.csv"
    summary_path = out_dir / "combo_d_threshold_sweep_experiment_summary.csv"
    top_path = out_dir / "combo_d_threshold_sweep_top_candidates.csv"

    if detail_rows:
        with detail_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(detail_rows[0].keys()))
            w.writeheader()
            w.writerows(detail_rows)

    summary_rows.sort(
        key=lambda r: (
            -(r["bear_hit_rate_max_pct"] or 0),
            r["avg_spx_change_mean_pct"] if r["avg_spx_change_mean_pct"] is not None else 999,
            -(r["n_events"] or 0),
        ),
    )
    if summary_rows:
        with summary_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
            w.writeheader()
            w.writerows(summary_rows)

    candidates = [r for r in summary_rows if (r["n_events"] or 0) >= 10 and r.get("hit_1W") is not None]
    candidates.sort(key=lambda r: (-(r["hit_1W"] or 0), r.get("avg_spx_1W") or 999, -(r["n_events"] or 0)))
    if candidates:
        top_n = candidates[:25]
        with top_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(top_n[0].keys()))
            w.writeheader()
            w.writerows(top_n)

    meta = {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "combo": "D",
        "variables": ["VXTS", "CFTC", "VIX"],
        "direction": "bearish",
        "panel_start": panel_start,
        "aligned_dates": len(dates),
        "n_experiments": len(experiments),
        "n_detail_rows": len(detail_rows),
        "horizons": [h[0] for h in HORIZONS],
        "grids": {"vxts_min": VXTS_GRID, "cftc_min_pctile": CFTC_GRID, "vix_max": VIX_GRID, "legs": LEGS_GRID},
        "config_baseline": cfg,
        "paths": {
            "all_horizons": str(detail_path),
            "experiment_summary": str(summary_path),
            "top_candidates": str(top_path),
        },
        "config_baseline_summary": next((r for r in summary_rows if r["is_config_baseline"]), None),
        "best_1w_hit_among_n_ge_10": candidates[0] if candidates else None,
        "note": (
            "Sweep uses first-crossing events on daily_readings (VXTS+CFTC+VIX), "
            "not full combo_fires WATCH backfill. Stricter 3-of-3 gates yield fewer events "
            "than production partial-leg rows."
        ),
    }
    meta_path = out_dir / "combo_d_threshold_sweep_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    meta["meta_json"] = str(meta_path)
    return meta


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    parser.add_argument("--panel-start", default="2007-01-01")
    parser.add_argument("--spx-start", default="1990-01-01")
    args = parser.parse_args()
    meta = run_sweep(Path(args.out_dir), panel_start=args.panel_start, spx_start=args.spx_start)
    print(json.dumps(meta, indent=2, default=str))


if __name__ == "__main__":
    main()
