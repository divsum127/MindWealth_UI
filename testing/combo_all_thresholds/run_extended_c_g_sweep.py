#!/usr/bin/env python3
"""Extended threshold sweeps for Combo C and G (sparse in base study)."""

from __future__ import annotations

import sys
from itertools import product
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from testing.combo_all_thresholds.run_all_combos_study import (  # noqa: E402
    COMBO_SPECS,
    OUT_DIR,
    _aligned_dates,
    _crossing_indices,
    _experiment_stats,
    _panel_col,
    _precompute_returns,
    _write_csv_with_header,
    load_readings_panel,
)
from src.macro_intelligence.config import load_config  # noqa: E402
from src.macro_intelligence.data.yahoo_pull import fetch_yahoo_close  # noqa: E402
from src.macro_intelligence.engine.forward_returns import _nyse_sessions  # noqa: E402


def sweep_combo_c_extended(panel, dates, fwd, cfg) -> list[dict]:
    wti = _panel_col(panel, "WTI", dates)
    cpi = _panel_col(panel, "CPI", dates)
    walcl = _panel_col(panel, "WALCL", dates)
    valid = ~(np.isnan(wti) | np.isnan(cpi) | np.isnan(walcl))
    rows: list[dict] = []
    seen: set[tuple] = set()
    spec = COMBO_SPECS["C"]

    def run(wmin, cmin, fmax, legs, sweep):
        key = (wmin, cmin, fmax, legs)
        if key in seen:
            return
        seen.add(key)
        w_ok = wti >= wmin
        c_ok = cpi >= cmin
        f_ok = np.abs(walcl) < fmax
        cnt = w_ok.astype(int) + c_ok.astype(int) + f_ok.astype(int)
        in_band = (cnt >= legs) & valid
        idx = _crossing_indices(in_band.astype(float), dates)
        is_cfg = (
            wmin == cfg.get("wti_4wk_min", 10.0)
            and cmin == cfg.get("cpi_surprise_min", 0.2)
            and fmax == 0.8
            and legs == 3
        )
        leg_txt = f"{legs}-of-3"
        row = {
            "experiment_id": f"C_ext_w{wmin}_cpi{cmin}_wcl{fmax}_l{legs}",
            "sweep_type": "config_baseline" if is_cfg else sweep,
            "is_config_baseline": is_cfg,
            "wti_4wk_min_pct": wmin,
            "cpi_surprise_min": cmin,
            "walcl_flat_max_pct": fmax,
            "legs_required": legs,
            "gate_text": f"WTI 4wk>={wmin}%; CPI surprise>={cmin}; |WALCL MoM|<{fmax}%; {leg_txt}",
            "n_events": len(idx),
        }
        row.update(_experiment_stats(idx, fwd, spec.horizons, bullish=False))
        rows.append(row)

    bw, bc = cfg.get("wti_4wk_min", 10.0), cfg.get("cpi_surprise_min", 0.2)
    run(bw, bc, 0.8, 3, "config_baseline")
    for w in [5, 6, 7, 8, 10, 12, 15]:
        for legs in [2, 3]:
            run(w, bc, 1.0, legs, "extended_wti")
    for c in [0.0, 0.05, 0.1, 0.15, 0.2, 0.25]:
        for legs in [2, 3]:
            run(8, c, 1.2, legs, "extended_cpi")
    for f in [0.8, 1.0, 1.2, 1.5, 2.0, 2.5]:
        for legs in [2, 3]:
            run(8, 0.15, f, legs, "extended_walcl")
    for w, c, f, legs in product([6, 8, 10], [0.1, 0.15, 0.2], [1.0, 1.5, 2.0], [2, 3]):
        run(w, c, f, legs, "extended_factorial")
    return rows


def sweep_combo_g_extended(panel, dates, fwd, cfg) -> list[dict]:
    from testing.combo_all_thresholds.run_all_combos_study import _hy_4wk_bps_series

    vxts = _panel_col(panel, "VXTS", dates)
    vix = _panel_col(panel, "VIX", dates)
    hy4 = _hy_4wk_bps_series(dates)
    valid = ~(np.isnan(vxts) | np.isnan(vix) | np.isnan(hy4))
    rows: list[dict] = []
    seen: set[tuple] = set()
    spec = COMBO_SPECS["G"]
    bvx, bv, bh = cfg.get("vxts_max", 1.0), cfg.get("vix_max", 20), cfg.get("hy_widen_4wk_bps", 30)

    def run(vxmax, vmax, hmin, sweep):
        key = (vxmax, vmax, hmin)
        if key in seen:
            return
        seen.add(key)
        in_band = (vxts < vxmax) & (vix <= vmax) & (hy4 >= hmin) & valid
        idx = _crossing_indices(in_band.astype(float), dates)
        is_cfg = vxmax == bvx and vmax == bv and hmin == bh
        row = {
            "experiment_id": f"G_ext_vxts{vxmax}_vix{int(vmax)}_hy{int(hmin)}",
            "sweep_type": "config_baseline" if is_cfg else sweep,
            "is_config_baseline": is_cfg,
            "vxts_max": vxmax,
            "vix_max": vmax,
            "hy_widen_4wk_bps_min": hmin,
            "gate_text": f"VXTS<{vxmax}; VIX<={vmax}; HY 4wk widen>={hmin}bps; 3-of-3",
            "n_events": len(idx),
        }
        row.update(_experiment_stats(idx, fwd, spec.horizons, bullish=False))
        rows.append(row)

    run(bvx, bv, bh, "config_baseline")
    for vx in [1.0, 1.05, 1.08, 1.10, 1.12, 1.15, 1.20]:
        run(vx, bv, bh, "extended_vxts")
    for v in [18, 20, 22, 24, 25, 28]:
        run(1.10, v, bh, "extended_vix")
    for h in [10, 15, 20, 25, 30, 35, 40, 50]:
        run(1.10, 22, h, "extended_hy")
    for vx, v, h in product([1.05, 1.08, 1.10, 1.12, 1.15], [20, 22, 24, 25], [15, 20, 25, 30, 35]):
        run(vx, v, h, "extended_factorial")
    return rows


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cfg = load_config().get("named_combos", {})
    panel = load_readings_panel("1996-01-01")
    spx = fetch_yahoo_close("^GSPC", "1990-01-01")
    sessions = _nyse_sessions()

    c_dates = _aligned_dates(panel, ["WTI", "CPI", "WALCL"])
    c_fwd = _precompute_returns(c_dates, spx, sessions, COMBO_SPECS["C"].horizons)
    c_rows = sweep_combo_c_extended(panel, c_dates, c_fwd, cfg.get("C", {}))
    _write_csv_with_header(
        OUT_DIR / "combo_C_extended_sweep_summary.csv",
        [f"Extended Combo C sweep — {len(c_rows)} experiments"],
        c_rows,
    )
    print(f"Combo C extended: {len(c_rows)} experiments, max n={max(r['n_events'] for r in c_rows)}")

    g_dates = _aligned_dates(panel, ["VXTS", "VIX"])
    g_fwd = _precompute_returns(g_dates, spx, sessions, COMBO_SPECS["G"].horizons)
    g_rows = sweep_combo_g_extended(panel, g_dates, g_fwd, cfg.get("G", {}))
    _write_csv_with_header(
        OUT_DIR / "combo_G_extended_sweep_summary.csv",
        [f"Extended Combo G sweep — {len(g_rows)} experiments"],
        g_rows,
    )
    print(f"Combo G extended: {len(g_rows)} experiments, max n={max(r['n_events'] for r in g_rows)}")


if __name__ == "__main__":
    main()
