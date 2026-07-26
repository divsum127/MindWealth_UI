#!/usr/bin/env python3
"""Follow-up experiments: production-viable gates (n>=10, no 80% target) + D+E sync overlay."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from itertools import product
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from testing.combo_de_thresholds.run_combo_de_study import (  # noqa: E402
    D_HORIZONS,
    E_HORIZONS,
    _crossing_indices,
    _d_pass,
    _e_pass,
    _fridays,
    _load_curve_regime,
    _precompute_returns,
    _stats,
    _write_csv,
)
from src.macro_intelligence.analysis.combo_threshold_sweep import (  # noqa: E402
    _aligned_dates,
    _reading_on,
    load_readings_panel,
)
from src.macro_intelligence.config import load_config  # noqa: E402
from src.macro_intelligence.data.yahoo_pull import fetch_yahoo_close  # noqa: E402
from src.macro_intelligence.engine.forward_returns import _nyse_sessions  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent / "output_files"
MIN_N = 10

# Finer extended grids (case 1)
D_VXTS = [1.10, 1.12, 1.14, 1.15, 1.16, 1.18, 1.20, 1.22, 1.24, 1.25, 1.26, 1.28]
D_CFTC = [80, 85, 88, 90, 92, 93, 95, 97]
D_VIX = [13, 14, 15, 16, 17, 18, 19]
D_LEGS = [2, 3]

E_CAPE = [28, 30, 32, 34, 35, 38, 40]
E_NFCI = [-0.15, -0.20, -0.25, -0.30, -0.35, -0.40, -0.50]
E_CFTC = [80, 85, 88, 90, 92, 95]
E_LEGS = [2, 3]

TACTICAL = [lbl for lbl, _ in D_HORIZONS]
STRUCTURAL = [lbl for lbl, _ in E_HORIZONS]


def _score_d(row: dict[str, Any]) -> float:
    n = row["n_events"]
    hit = row.get("bear_hit_1W") or 0
    avg = row.get("avg_spx_1W") or 0
    n_pen = abs(n - 30) * 0.15
    return hit - n_pen + (0.5 if avg < 0 else 0)


def _score_e(row: dict[str, Any]) -> float:
    n = row["n_events"]
    hit = row.get("bear_hit_12M") or 0
    avg = row.get("avg_spx_12M") or 0
    n_pen = abs(n - 30) * 0.15
    return hit - n_pen + (0.5 if avg < 0 else 0)


def _n_band(n: int) -> str:
    if n < 20:
        return "10-19"
    if n <= 40:
        return "20-40"
    if n <= 60:
        return "41-60"
    return "61+"


def _build_arrays(panel, d_dates, e_dates):
    def arrays(dates: list[str], vars_: list[str]):
        arrs = []
        for vid in vars_:
            col = []
            for ds in dates:
                r = _reading_on(panel, vid, ds)
                if vid == "CFTC":
                    col.append(float(r["pctile"]) if r and r["pctile"] is not None else np.nan)
                else:
                    col.append(float(r["raw"]) if r and r["raw"] is not None else np.nan)
            arrs.append(np.array(col))
        valid = np.ones(len(dates), dtype=bool)
        for a in arrs:
            valid &= ~np.isnan(a)
        return (*arrs, valid)

    vxts, cftc_d, vix, d_valid = arrays(d_dates, ["VXTS", "CFTC", "VIX"])
    cape, nfci, cftc_e, e_valid = arrays(e_dates, ["CAPE", "NFCI", "CFTC"])
    return vxts, cftc_d, vix, d_valid, cape, nfci, cftc_e, e_valid


def case1_production_sweeps(
    d_dates, e_dates, vxts, cftc_d, vix, d_valid, cape, nfci, cftc_e, e_valid, fwd_d, fwd_e, d_cfg, e_cfg
) -> tuple[list[dict], list[dict], list[dict]]:
    d_rows: list[dict[str, Any]] = []
    e_rows: list[dict[str, Any]] = []

    for v, c, x, legs in product(D_VXTS, D_CFTC, D_VIX, D_LEGS):
        in_band = _d_pass(vxts, cftc_d, vix, v, c, x, legs) & d_valid
        idx = _crossing_indices(in_band, d_dates)
        if len(idx) < MIN_N:
            continue
        hstats = {lbl: _stats(idx, fwd_d, lbl) for lbl, _ in D_HORIZONS}
        row = {
            "experiment_id": f"D_v{v:.2f}_c{int(c)}_x{int(x)}_l{legs}",
            "vxts_min": v,
            "cftc_min_pctile": c,
            "vix_max": x,
            "legs_required": legs,
            "n_events": len(idx),
            "n_band": _n_band(len(idx)),
            "is_config_baseline": (
                abs(v - d_cfg.get("vxts_min", 1.1)) < 1e-9
                and abs(c - d_cfg.get("cftc_min_pctile", 85)) < 1e-9
                and abs(x - d_cfg.get("vix_max", 18)) < 1e-9
                and legs == int(d_cfg.get("min_of_three", 3))
            ),
            **{f"bear_hit_{lbl}": hstats[lbl]["bear_hit_pct"] for lbl in TACTICAL},
            **{f"avg_spx_{lbl}": hstats[lbl]["avg_spx_pct"] for lbl in TACTICAL},
            "bear_hit_mean_1W_4W": round(
                float(np.mean([hstats[l]["bear_hit_pct"] for l in TACTICAL if hstats[l]["bear_hit_pct"] is not None])),
                2,
            ),
        }
        row["production_score"] = round(_score_d(row), 3)
        d_rows.append(row)

    for cm, nm, cf, legs in product(E_CAPE, E_NFCI, E_CFTC, E_LEGS):
        in_band = _e_pass(cape, nfci, cftc_e, cm, nm, cf, legs) & e_valid
        idx = _crossing_indices(in_band, e_dates)
        if len(idx) < MIN_N:
            continue
        hstats = {lbl: _stats(idx, fwd_e, lbl) for lbl, _ in E_HORIZONS}
        row = {
            "experiment_id": f"E_cape{int(cm)}_nfci{nm:.2f}_cftc{int(cf)}_l{legs}",
            "cape_min": cm,
            "nfci_easy_max": nm,
            "cftc_min_pctile": cf,
            "legs_required": legs,
            "n_events": len(idx),
            "n_band": _n_band(len(idx)),
            "is_config_baseline": (
                abs(cm - e_cfg.get("cape_min", 28)) < 1e-9
                and abs(nm - e_cfg.get("nfci_easy_max", -0.3)) < 1e-9
                and abs(cf - e_cfg.get("cftc_min_pctile", 80)) < 1e-9
                and legs == e_cfg.get("min_of_three", 2)
            ),
            **{f"bear_hit_{lbl}": hstats[lbl]["bear_hit_pct"] for lbl in STRUCTURAL},
            **{f"avg_spx_{lbl}": hstats[lbl]["avg_spx_pct"] for lbl in STRUCTURAL},
            "bear_hit_mean_6M_12M": round(
                float(np.mean([hstats[l]["bear_hit_pct"] for l in STRUCTURAL if hstats[l]["bear_hit_pct"] is not None])),
                2,
            ),
        }
        row["production_score"] = round(_score_e(row), 3)
        e_rows.append(row)

    d_rows.sort(key=lambda r: (-r["production_score"], -(r.get("bear_hit_1W") or 0)))
    e_rows.sort(key=lambda r: (-r["production_score"], -(r.get("bear_hit_12M") or 0)))

    pareto: list[dict[str, Any]] = []
    for combo, rows, primary in [("D", d_rows, "bear_hit_1W"), ("E", e_rows, "bear_hit_12M")]:
        best_hit = -1.0
        for r in rows:
            hit = r.get(primary) or 0
            if hit >= best_hit:
                best_hit = hit
                pareto.append({**r, "combo": combo, "pareto_reason": f"max {primary} at n>={MIN_N} for n<={r['n_events']}"})

    return d_rows, e_rows, pareto


def _d_key(row: dict) -> tuple:
    return (row["vxts_min"], row["cftc_min_pctile"], row["vix_max"], row["legs_required"])


def _e_key(row: dict) -> tuple:
    return (row["cape_min"], row["nfci_easy_max"], row["cftc_min_pctile"], row["legs_required"])


def _indices_d(d_dates, vxts, cftc_d, vix, d_valid, key) -> list[int]:
    v, c, x, legs = key
    return _crossing_indices(_d_pass(vxts, cftc_d, vix, v, c, x, legs) & d_valid, d_dates)


def _indices_e(e_dates, cape, nfci, cftc_e, e_valid, key) -> list[int]:
    cm, nm, cf, legs = key
    return _crossing_indices(_e_pass(cape, nfci, cftc_e, cm, nm, cf, legs) & e_valid, e_dates)


def case2_sync_matrix(
    d_dates,
    e_dates,
    d_candidates: list[dict],
    e_candidates: list[dict],
    vxts,
    cftc_d,
    vix,
    d_valid,
    cape,
    nfci,
    cftc_e,
    e_valid,
    fwd_d,
    fwd_e,
    top_n_pairs: int = 40,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Pair top D × top E configs; full tactical + structural sync stats."""
    d_top = d_candidates[:top_n_pairs]
    e_top = e_candidates[:top_n_pairs]

    d_cache: dict[tuple, list[int]] = {}
    e_cache: dict[tuple, list[int]] = {}
    for dr in d_top:
        k = _d_key(dr)
        d_cache[k] = _indices_d(d_dates, vxts, cftc_d, vix, d_valid, k)
    for er in e_top:
        k = _e_key(er)
        e_cache[k] = _indices_e(e_dates, cape, nfci, cftc_e, e_valid, k)

    matrix: list[dict[str, Any]] = []
    per_fire: list[dict[str, Any]] = []

    for dr in d_top:
        dk = _d_key(dr)
        di = d_cache[dk]
        d_by_date = {d_dates[i]: i for i in di}
        d_alone_1w = _stats(di, fwd_d, "1W").get("bear_hit_pct")

        for er in e_top:
            ek = _e_key(er)
            ei = e_cache[ek]
            e_by_date = {e_dates[i]: i for i in ei}
            sync_dates = sorted(set(d_by_date) & set(e_by_date))
            d_sync = [d_by_date[d] for d in sync_dates]
            e_sync = [e_by_date[d] for d in sync_dates]
            d_only_dates = sorted(set(d_by_date) - set(e_by_date))
            e_only_dates = sorted(set(e_by_date) - set(d_by_date))
            d_only = [d_by_date[d] for d in d_only_dates]
            e_only = [e_by_date[d] for d in e_only_dates]

            row: dict[str, Any] = {
                "d_experiment": dr["experiment_id"],
                "e_experiment": er["experiment_id"],
                "d_n": len(di),
                "e_n": len(ei),
                "sync_n": len(sync_dates),
                "d_only_n": len(d_only),
                "e_only_n": len(e_only),
                "sync_pct_of_d": round(100 * len(sync_dates) / len(di), 1) if di else None,
            }
            for lbl in TACTICAL:
                s_d = _stats(di, fwd_d, lbl)
                s_sync = _stats(d_sync, fwd_d, lbl)
                s_donly = _stats(d_only, fwd_d, lbl)
                row[f"d_alone_bear_{lbl}"] = s_d["bear_hit_pct"]
                row[f"sync_bear_{lbl}"] = s_sync["bear_hit_pct"]
                row[f"d_only_bear_{lbl}"] = s_donly["bear_hit_pct"]
                row[f"sync_lift_{lbl}"] = (
                    round((s_sync["bear_hit_pct"] or 0) - (s_d["bear_hit_pct"] or 0), 2)
                    if s_sync["bear_hit_pct"] is not None and s_d["bear_hit_pct"] is not None
                    else None
                )
                row[f"sync_avg_spx_{lbl}"] = s_sync["avg_spx_pct"]

            for lbl in STRUCTURAL:
                s_e = _stats(ei, fwd_e, lbl)
                s_sync_e = _stats(e_sync, fwd_e, lbl)
                s_eonly = _stats(e_only, fwd_e, lbl)
                row[f"e_alone_bear_{lbl}"] = s_e["bear_hit_pct"]
                row[f"sync_struct_bear_{lbl}"] = s_sync_e["bear_hit_pct"]
                row[f"e_only_bear_{lbl}"] = s_eonly["bear_hit_pct"]
                row[f"sync_struct_avg_spx_{lbl}"] = s_sync_e["avg_spx_pct"]

            row["tactical_sync_beats_d_alone_1W"] = (
                (row.get("sync_bear_1W") or 0) > (row.get("d_alone_bear_1W") or 0)
                if row.get("sync_n", 0) >= 3
                else None
            )
            row["structural_sync_bullish_12M"] = (
                (row.get("sync_struct_bear_12M") or 100) < 30 if row.get("sync_n", 0) >= 2 else None
            )
            matrix.append(row)

    matrix.sort(
        key=lambda r: (
            -(r.get("sync_lift_1W") or -999),
            -(r.get("sync_bear_1W") or 0),
            r.get("sync_n") or 0,
        )
    )

    # Per-fire detail for top 5 sync pairs (by 1W lift, sync_n>=3)
    top_pairs = [r for r in matrix if (r.get("sync_n") or 0) >= 3][:5]
    pair_rank = 0
    for pr in top_pairs:
        pair_rank += 1
        dr = next(x for x in d_top if x["experiment_id"] == pr["d_experiment"])
        er = next(x for x in e_top if x["experiment_id"] == pr["e_experiment"])
        dk, ek = _d_key(dr), _e_key(er)
        di, ei = d_cache[dk], e_cache[ek]
        d_by_date = {d_dates[i]: i for i in di}
        e_by_date = {e_dates[i]: i for i in ei}
        for ds in sorted(set(d_by_date) & set(e_by_date)):
            di_i, ei_i = d_by_date[ds], e_by_date[ds]
            pf = {
                "pair_rank": pair_rank,
                "trigger_date": ds,
                "d_experiment": pr["d_experiment"],
                "e_experiment": pr["e_experiment"],
            }
            for lbl in TACTICAL:
                pf[f"spx_pct_{lbl}"] = fwd_d[di_i][lbl]
                pf[f"bear_{lbl}"] = 1 if (fwd_d[di_i][lbl] or 0) < 0 else 0
            for lbl in STRUCTURAL:
                pf[f"spx_pct_{lbl}_e"] = fwd_e[ei_i][lbl]
                pf[f"bear_{lbl}_e"] = 1 if (fwd_e[ei_i][lbl] or 0) < 0 else 0
            per_fire.append(pf)

    # Aggregate tactical vs structural on sync
    agg_rows: list[dict[str, Any]] = []
    with_sync = [r for r in matrix if (r.get("sync_n") or 0) >= 3]
    for lbl in TACTICAL:
        lifts = [r[f"sync_lift_{lbl}"] for r in with_sync if r.get(f"sync_lift_{lbl}") is not None]
        sync_hits = [r[f"sync_bear_{lbl}"] for r in with_sync if r.get(f"sync_bear_{lbl}") is not None]
        d_hits = [r[f"d_alone_bear_{lbl}"] for r in with_sync if r.get(f"d_alone_bear_{lbl}") is not None]
        if lifts:
            agg_rows.append(
                {
                    "horizon": lbl,
                    "slice": "tactical_on_sync",
                    "pairs_with_sync_n_ge_3": len(with_sync),
                    "pairs_sync_beats_d_alone": sum(1 for r in with_sync if (r.get(f"sync_bear_{lbl}") or 0) > (r.get(f"d_alone_bear_{lbl}") or 0)),
                    "mean_sync_bear_hit_pct": round(float(np.mean(sync_hits)), 2),
                    "mean_d_alone_bear_hit_pct": round(float(np.mean(d_hits)), 2),
                    "mean_lift_pct": round(float(np.mean(lifts)), 2),
                    "median_lift_pct": round(float(np.median(lifts)), 2),
                }
            )
    for lbl in STRUCTURAL:
        sync_hits = [r[f"sync_struct_bear_{lbl}"] for r in with_sync if r.get(f"sync_struct_bear_{lbl}") is not None]
        e_hits = [r[f"e_alone_bear_{lbl}"] for r in with_sync if r.get(f"e_alone_bear_{lbl}") is not None]
        sync_avg = [r[f"sync_struct_avg_spx_{lbl}"] for r in with_sync if r.get(f"sync_struct_avg_spx_{lbl}") is not None]
        if sync_hits:
            agg_rows.append(
                {
                    "horizon": lbl,
                    "slice": "structural_on_sync_dates",
                    "pairs_with_sync_n_ge_3": len(with_sync),
                    "pairs_sync_bear_lt_30pct": sum(1 for h in sync_hits if h < 30),
                    "mean_sync_bear_hit_pct": round(float(np.mean(sync_hits)), 2),
                    "mean_e_alone_bear_hit_pct": round(float(np.mean(e_hits)), 2),
                    "mean_sync_avg_spx_pct": round(float(np.mean(sync_avg)), 2),
                    "note": "structural_on_sync = E 12M/6M returns on dates BOTH D+E fire (typically bullish)",
                }
            )

    return matrix, agg_rows, per_fire


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    d_cfg = cfg.get("named_combos", {}).get("D", {})
    e_cfg = cfg.get("named_combos", {}).get("E", {})

    panel = load_readings_panel("2007-01-01")
    spx = fetch_yahoo_close("^GSPC", "1990-01-01")
    sessions = _nyse_sessions()
    d_dates = _fridays(_aligned_dates(panel, ["VXTS", "CFTC", "VIX"]))
    e_dates = _fridays(_aligned_dates(panel, ["CAPE", "NFCI", "CFTC"]))
    vxts, cftc_d, vix, d_valid, cape, nfci, cftc_e, e_valid = _build_arrays(panel, d_dates, e_dates)

    print("Precomputing forward returns...")
    fwd_d = _precompute_returns(d_dates, spx, sessions, D_HORIZONS)
    fwd_e = _precompute_returns(e_dates, spx, sessions, E_HORIZONS)

    print("Case 1: production-viable sweeps (n>=10, no 80% target)...")
    d_prod, e_prod, pareto = case1_production_sweeps(
        d_dates, e_dates, vxts, cftc_d, vix, d_valid, cape, nfci, cftc_e, e_valid, fwd_d, fwd_e, d_cfg, e_cfg
    )
    print(f"  D viable: {len(d_prod)}, E viable: {len(e_prod)}")

    print("Case 2: D+E sync pair matrix (top 40 x top 40)...")
    matrix, agg, per_fire = case2_sync_matrix(
        d_dates, e_dates, d_prod, e_prod, vxts, cftc_d, vix, d_valid, cape, nfci, cftc_e, e_valid, fwd_d, fwd_e
    )
    print(f"  Pairs: {len(matrix)}, per-fire rows: {len(per_fire)}")

    _write_csv(OUT_DIR / "case1_production_viable_d.csv", d_prod)
    _write_csv(OUT_DIR / "case1_production_viable_e.csv", e_prod)
    _write_csv(OUT_DIR / "case1_production_pareto.csv", pareto)

    top_d = d_prod[:25]
    top_e = e_prod[:25]
    _write_csv(OUT_DIR / "case1_top25_d.csv", top_d)
    _write_csv(OUT_DIR / "case1_top25_e.csv", top_e)

    _write_csv(OUT_DIR / "case2_sync_pair_matrix.csv", matrix)
    _write_csv(OUT_DIR / "case2_sync_tactical_vs_structural.csv", agg)
    _write_csv(OUT_DIR / "case2_sync_per_fire_top_pairs.csv", per_fire)

    # Fixed pairs: CONFIG + best production scores
    fixed_pairs = []
    cfg_d = next((r for r in d_prod if r.get("is_config_baseline")), d_prod[0] if d_prod else None)
    cfg_e = next((r for r in e_prod if r.get("is_config_baseline")), e_prod[0] if e_prod else None)
    best_d = d_prod[0] if d_prod else None
    best_e = e_prod[0] if e_prod else None
    for tag, dr, er in [
        ("CONFIG", cfg_d, cfg_e),
        ("BEST_PRODUCTION_SCORE", best_d, best_e),
    ]:
        if not dr or not er:
            continue
        sub_matrix, sub_agg, _ = case2_sync_matrix(
            d_dates, e_dates, [dr], [er], vxts, cftc_d, vix, d_valid, cape, nfci, cftc_e, e_valid, fwd_d, fwd_e, top_n_pairs=1
        )
        for r in sub_matrix:
            r["pair_tag"] = tag
            fixed_pairs.append(r)
        for r in sub_agg:
            r["pair_tag"] = tag
    _write_csv(OUT_DIR / "case2_sync_fixed_pairs.csv", fixed_pairs)

    meta = {
        "generated_at": datetime.now(UTC).isoformat(),
        "case1": {
            "min_n": MIN_N,
            "d_viable_count": len(d_prod),
            "e_viable_count": len(e_prod),
            "best_d": best_d,
            "best_e": best_e,
            "config_d": cfg_d,
            "config_e": cfg_e,
        },
        "case2": {
            "pair_matrix_rows": len(matrix),
            "pairs_sync_beats_d_1W": sum(1 for r in matrix if r.get("tactical_sync_beats_d_alone_1W")),
            "pairs_structural_bullish_12M_on_sync": sum(1 for r in matrix if r.get("structural_sync_bullish_12M")),
            "top_sync_pair_by_lift_1W": matrix[0] if matrix else None,
        },
        "note": "Case1: no 80% target; score favors hit rate + negative avg SPX + n≈30. Case2: sync tactical uses D horizons on overlap dates; structural uses E horizons on same dates.",
    }
    (OUT_DIR / "followup_meta.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    print(json.dumps(meta, indent=2, default=str))


if __name__ == "__main__":
    main()
