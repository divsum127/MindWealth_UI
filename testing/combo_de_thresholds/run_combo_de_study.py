#!/usr/bin/env python3
"""Combo D & E threshold study — sweeps, sync, regime overlay, recommendations."""

from __future__ import annotations

import csv
import json
import sys
from datetime import UTC, datetime
from itertools import product
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.analysis.combo_threshold_sweep import (  # noqa: E402
    _aligned_dates,
    _reading_on,
    load_readings_panel,
)
from src.macro_intelligence.config import load_config  # noqa: E402
from src.macro_intelligence.data.yahoo_pull import fetch_yahoo_close  # noqa: E402
from src.macro_intelligence.db.connection import get_connection, init_db  # noqa: E402
from src.macro_intelligence.engine.forward_returns import (  # noqa: E402
    _nyse_sessions,
    forward_return_pct,
)

OUT_DIR = Path(__file__).resolve().parent / "output_files"
COOLDOWN_DAYS = 5
N_TARGET_LO, N_TARGET_HI = 15, 50

D_HORIZONS = [("1W", 5), ("2W", 10), ("3W", 15), ("4W", 20)]
E_HORIZONS = [("6M", 126), ("9M", 189), ("12M", 252)]

D_VXTS = [1.10, 1.12, 1.15, 1.18, 1.20, 1.22, 1.25]
D_CFTC = [85, 88, 90, 92, 95]
D_VIX = [14, 15, 16, 17, 18]
D_LEGS = [2, 3]

E_CAPE = [30, 32, 35, 38, 40, 42]
E_NFCI = [-0.20, -0.25, -0.30, -0.35, -0.40, -0.50]
E_CFTC = [85, 88, 90, 92, 95]
E_LEGS = [2, 3]


def _fridays(dates: list[str]) -> list[str]:
    return [d for d in dates if pd.Timestamp(d).dayofweek == 4]


def _crossing_indices(in_band: np.ndarray, dates: list[str]) -> list[int]:
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


def _load_curve_regime() -> dict[str, str]:
    init_db()
    out: dict[str, str] = {}
    with get_connection() as conn:
        try:
            rows = conn.execute(
                "SELECT date, regime_json FROM macro_regime_log_v2"
            ).fetchall()
        except Exception:
            rows = conn.execute(
                "SELECT date, regime_json FROM macro_regime_log"
            ).fetchall()
    for r in rows:
        try:
            reg = json.loads(r["regime_json"] or "{}")
        except json.JSONDecodeError:
            continue
        curve = (
            reg.get("curve_regime_v2")
            or reg.get("curve_regime")
            or reg.get("curve_regime_legacy")
            or "UNKNOWN"
        )
        out[r["date"]] = str(curve).upper()
    return out


def _precompute_returns(
    dates: list[str], spx: pd.Series, sessions: pd.DatetimeIndex, horizons: list[tuple[str, int]]
) -> dict[int, dict[str, float | None]]:
    cache: dict[int, dict[str, float | None]] = {}
    for i, ds in enumerate(dates):
        cache[i] = {}
        ts = pd.Timestamp(ds)
        for label, td in horizons:
            cache[i][label] = forward_return_pct(spx, ts, td, sessions=sessions)
    return cache


def _stats(indices: list[int], fwd: dict[int, dict[str, float | None]], label: str) -> dict[str, Any]:
    rets = [fwd[i][label] for i in indices if fwd[i][label] is not None]
    if not rets:
        return {"n_mature": 0, "bear_hit_pct": None, "avg_spx_pct": None, "min_spx_pct": None, "max_spx_pct": None}
    arr = np.array(rets, dtype=float)
    hr = float((arr < 0).mean() * 100)
    return {
        "n_mature": len(rets),
        "bear_hit_pct": round(hr, 2),
        "avg_spx_pct": round(float(arr.mean()), 4),
        "min_spx_pct": round(float(arr.min()), 4),
        "max_spx_pct": round(float(arr.max()), 4),
    }


def _d_pass(vxts: np.ndarray, cftc: np.ndarray, vix: np.ndarray, v: float, c: float, x: float, legs: int) -> np.ndarray:
    cnt = (vxts >= v).astype(int) + (cftc >= c).astype(int) + (vix <= x).astype(int)
    return cnt >= legs


def _e_pass(cape: np.ndarray, nfci: np.ndarray, cftc: np.ndarray, cape_m: float, nfci_m: float, cftc_m: float, legs: int) -> np.ndarray:
    cnt = (cape >= cape_m).astype(int) + (nfci <= nfci_m).astype(int) + (cftc >= cftc_m).astype(int)
    return cnt >= legs


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    keys: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for k in row:
            if k not in seen:
                seen.add(k)
                keys.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def sweep_d(
    dates: list[str],
    vxts: np.ndarray,
    cftc: np.ndarray,
    vix: np.ndarray,
    valid: np.ndarray,
    fwd: dict[int, dict[str, float | None]],
    cfg: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    detail: list[dict[str, Any]] = []
    summary: list[dict[str, Any]] = []
    seen: set[tuple] = set()

    def run(v: float, c: float, x: float, legs: int, sweep: str) -> None:
        key = (v, c, x, legs)
        if key in seen:
            return
        seen.add(key)
        in_band = _d_pass(vxts, cftc, vix, v, c, x, legs) & valid
        idx = _crossing_indices(in_band, dates)
        eid = f"D_v{v:.2f}_c{int(c)}_x{int(x)}_l{legs}"
        is_cfg = (
            abs(v - cfg.get("vxts_min", 1.1)) < 1e-9
            and abs(c - cfg.get("cftc_min_pctile", 85)) < 1e-9
            and abs(x - cfg.get("vix_max", 18)) < 1e-9
            and legs == 3
        )
        hstats = {lbl: _stats(idx, fwd, lbl) for lbl, _ in D_HORIZONS}
        hits = [hstats[l]["bear_hit_pct"] for l, _ in D_HORIZONS if hstats[l]["bear_hit_pct"] is not None]
        avgs = [hstats[l]["avg_spx_pct"] for l, _ in D_HORIZONS if hstats[l]["avg_spx_pct"] is not None]
        row = {
            "experiment_id": eid,
            "combo": "D",
            "sweep_type": "config_baseline" if is_cfg else sweep,
            "is_config_baseline": is_cfg,
            "vxts_min": v,
            "cftc_min_pctile": c,
            "vix_max": x,
            "legs_required": legs,
            "n_events": len(idx),
            "bear_hit_1W": hstats["1W"]["bear_hit_pct"],
            "bear_hit_4W": hstats["4W"]["bear_hit_pct"],
            "bear_hit_mean_1W_4W": round(float(np.mean(hits)), 2) if hits else None,
            "avg_spx_1W": hstats["1W"]["avg_spx_pct"],
            "avg_spx_mean_1W_4W": round(float(np.mean(avgs)), 4) if avgs else None,
            "meets_n_target": N_TARGET_LO <= len(idx) <= N_TARGET_HI,
            "meets_80pct_1W": (hstats["1W"]["bear_hit_pct"] or 0) >= 80,
        }
        summary.append(row)
        for lbl, _ in D_HORIZONS:
            detail.append({**row, "horizon": lbl, **{f"h_{k}": v for k, v in hstats[lbl].items()}})
        summary[-1]["event_indices"] = idx  # stripped before csv write

    bv, bc, bx = cfg.get("vxts_min", 1.1), cfg.get("cftc_min_pctile", 85), cfg.get("vix_max", 18)
    run(bv, bc, bx, 3, "config_baseline")
    for v in D_VXTS:
        run(v, bc, bx, 3, "univariate_vxts")
    for c in D_CFTC:
        run(bv, c, bx, 3, "univariate_cftc")
    for x in D_VIX:
        run(bv, bc, x, 3, "univariate_vix")
    for v, c, x, legs in product(D_VXTS, D_CFTC, D_VIX, D_LEGS):
        run(v, c, x, legs, "factorial")

    for r in summary:
        r.pop("event_indices", None)
    return detail, summary


def sweep_e(
    dates: list[str],
    cape: np.ndarray,
    nfci: np.ndarray,
    cftc: np.ndarray,
    valid: np.ndarray,
    fwd: dict[int, dict[str, float | None]],
    cfg: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    detail: list[dict[str, Any]] = []
    summary: list[dict[str, Any]] = []
    seen: set[tuple] = set()

    def run(cm: float, nm: float, cf: float, legs: int, sweep: str) -> None:
        key = (cm, nm, cf, legs)
        if key in seen:
            return
        seen.add(key)
        in_band = _e_pass(cape, nfci, cftc, cm, nm, cf, legs) & valid
        idx = _crossing_indices(in_band, dates)
        eid = f"E_cape{int(cm)}_nfci{nm:.2f}_cftc{int(cf)}_l{legs}"
        is_cfg = (
            abs(cm - cfg.get("cape_min", 28)) < 1e-9
            and abs(nm - cfg.get("nfci_easy_max", -0.3)) < 1e-9
            and abs(cf - cfg.get("cftc_min_pctile", 80)) < 1e-9
            and legs == cfg.get("min_of_three", 2)
        )
        hstats = {lbl: _stats(idx, fwd, lbl) for lbl, _ in E_HORIZONS}
        hits = [hstats[l]["bear_hit_pct"] for l, _ in E_HORIZONS if hstats[l]["bear_hit_pct"] is not None]
        avgs = [hstats[l]["avg_spx_pct"] for l, _ in E_HORIZONS if hstats[l]["avg_spx_pct"] is not None]
        row = {
            "experiment_id": eid,
            "combo": "E",
            "sweep_type": "config_baseline" if is_cfg else sweep,
            "is_config_baseline": is_cfg,
            "cape_min": cm,
            "nfci_easy_max": nm,
            "cftc_min_pctile": cf,
            "legs_required": legs,
            "n_events": len(idx),
            "bear_hit_6M": hstats["6M"]["bear_hit_pct"],
            "bear_hit_12M": hstats["12M"]["bear_hit_pct"],
            "bear_hit_mean_6M_12M": round(float(np.mean(hits)), 2) if hits else None,
            "avg_spx_12M": hstats["12M"]["avg_spx_pct"],
            "avg_spx_mean_6M_12M": round(float(np.mean(avgs)), 4) if avgs else None,
            "meets_n_target": N_TARGET_LO <= len(idx) <= N_TARGET_HI,
            "meets_80pct_12M": (hstats["12M"]["bear_hit_pct"] or 0) >= 80,
        }
        summary.append(row)
        for lbl, _ in E_HORIZONS:
            detail.append({**row, "horizon": lbl, **{f"h_{k}": v for k, v in hstats[lbl].items()}})
        summary[-1]["event_indices"] = idx

    bc = cfg.get("cape_min", 28)
    bn = cfg.get("nfci_easy_max", -0.3)
    bf = cfg.get("cftc_min_pctile", 80)
    bl = cfg.get("min_of_three", 2)
    run(bc, bn, bf, bl, "config_baseline")
    for cm in E_CAPE:
        run(cm, bn, bf, bl, "univariate_cape")
    for nm in E_NFCI:
        run(bc, nm, bf, bl, "univariate_nfci")
    for cf in E_CFTC:
        run(bc, bn, cf, bl, "univariate_cftc")
    for cm, nm, cf, legs in product(E_CAPE, E_NFCI, E_CFTC, E_LEGS):
        run(cm, nm, cf, legs, "factorial")

    for r in summary:
        r.pop("event_indices", None)
    return detail, summary


def _pick_best(summary: list[dict[str, Any]], combo: str) -> dict[str, Any] | None:
    primary = "bear_hit_1W" if combo == "D" else "bear_hit_12M"
    in_band = [r for r in summary if r.get("meets_n_target")]
    pool = in_band or summary
    pool = sorted(
        pool,
        key=lambda r: (
            -(r.get(primary) or 0),
            r.get("avg_spx_1W" if combo == "D" else "avg_spx_12M") or 999,
            -abs(r.get("n_events", 0) - 30),
        ),
    )
    return pool[0] if pool else None


def sync_and_regime(
    d_dates: list[str],
    e_dates: list[str],
    d_idx: list[int],
    e_idx: list[int],
    fwd_d: dict[int, dict[str, float | None]],
    fwd_e: dict[int, dict[str, float | None]],
    curve_map: dict[str, str],
    d_label: str,
    e_label: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    d_by_date = {d_dates[i]: i for i in d_idx}
    e_by_date = {e_dates[i]: i for i in e_idx}
    sync_dates = sorted(set(d_by_date) & set(e_by_date))
    d_sync_idx = [d_by_date[d] for d in sync_dates]
    e_sync_idx = [e_by_date[d] for d in sync_dates]
    sync_rows: list[dict[str, Any]] = []
    regime_rows: list[dict[str, Any]] = []

    def slice_stats(label: str, indices: list[int], horizon: str, fwd: dict) -> dict[str, Any]:
        s = _stats(indices, fwd, horizon)
        return {"slice": label, "horizon": horizon, "n_events": len(indices), **s}

    sync_rows.append({**slice_stats("D_alone", d_idx, "1W", fwd_d), "d_experiment": d_label, "e_experiment": e_label})
    sync_rows.append({**slice_stats("E_alone", e_idx, "12M", fwd_e), "d_experiment": d_label, "e_experiment": e_label})
    sync_rows.append({**slice_stats("D_and_E_sync", d_sync_idx, "1W", fwd_d), "d_experiment": d_label, "e_experiment": e_label})
    if e_sync_idx:
        rets12 = [fwd_e[i]["12M"] for i in e_sync_idx if fwd_e[i]["12M"] is not None]
        if rets12:
            arr = np.array(rets12)
            sync_rows.append(
                {
                    "slice": "D_and_E_sync",
                    "horizon": "12M",
                    "n_events": len(e_sync_idx),
                    "n_mature": len(rets12),
                    "bear_hit_pct": round(float((arr < 0).mean() * 100), 2),
                    "avg_spx_pct": round(float(arr.mean()), 4),
                    "min_spx_pct": round(float(arr.min()), 4),
                    "max_spx_pct": round(float(arr.max()), 4),
                    "d_experiment": d_label,
                    "e_experiment": e_label,
                }
            )

    for regime in ("STEEPENING", "NORMAL", "INVERTED", "UNKNOWN"):
        r_idx_d = [i for i in d_idx if curve_map.get(d_dates[i], "UNKNOWN") == regime]
        r_idx_e = [i for i in e_idx if curve_map.get(e_dates[i], "UNKNOWN") == regime]
        r_sync_d = [d_by_date[d] for d in sync_dates if curve_map.get(d, "UNKNOWN") == regime]
        r_sync_e = [e_by_date[d] for d in sync_dates if curve_map.get(d, "UNKNOWN") == regime]
        if r_idx_d:
            regime_rows.append(
                {**slice_stats(f"D_{regime}", r_idx_d, "1W", fwd_d), "curve_regime": regime, "pair": d_label}
            )
        if r_idx_e:
            regime_rows.append(
                {**slice_stats(f"E_{regime}", r_idx_e, "12M", fwd_e), "curve_regime": regime, "pair": e_label}
            )
        if r_sync_d:
            regime_rows.append(
                {
                    **slice_stats(f"sync_{regime}", r_sync_d, "1W", fwd_d),
                    "curve_regime": regime,
                    "pair": f"{d_label}+{e_label}",
                }
            )
        if r_sync_e and r_sync_e != r_sync_d:
            regime_rows.append(
                {
                    **slice_stats(f"sync_{regime}_12M", r_sync_e, "12M", fwd_e),
                    "curve_regime": regime,
                    "pair": f"{d_label}+{e_label}",
                }
            )

    return sync_rows, regime_rows


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    d_cfg = cfg.get("named_combos", {}).get("D", {})
    e_cfg = cfg.get("named_combos", {}).get("E", {})

    panel = load_readings_panel("2007-01-01")
    spx = fetch_yahoo_close("^GSPC", "1990-01-01")
    sessions = _nyse_sessions()
    curve_map = _load_curve_regime()

    d_dates_all = _aligned_dates(panel, ["VXTS", "CFTC", "VIX"])
    e_dates_all = _aligned_dates(panel, ["CAPE", "NFCI", "CFTC"])
    d_dates = _fridays(d_dates_all)
    e_dates = _fridays(e_dates_all)

    def arrays(dates: list[str], vars_: list[str]) -> tuple[np.ndarray, ...]:
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

    print(f"Precomputing returns: D {len(d_dates)} Fridays, E {len(e_dates)} Fridays...")
    fwd_d = _precompute_returns(d_dates, spx, sessions, D_HORIZONS)
    fwd_e = _precompute_returns(e_dates, spx, sessions, E_HORIZONS)

    print("Sweeping Combo D...")
    d_detail, d_summary = sweep_d(d_dates, vxts, cftc_d, vix, d_valid, fwd_d, d_cfg)
    print("Sweeping Combo E...")
    e_detail, e_summary = sweep_e(e_dates, cape, nfci, cftc_e, e_valid, fwd_e, e_cfg)

    # Re-attach indices for best configs (recompute)
    def d_indices(v, c, x, legs):
        in_band = _d_pass(vxts, cftc_d, vix, v, c, x, legs) & d_valid
        return _crossing_indices(in_band, d_dates)

    def e_indices(cm, nm, cf, legs):
        in_band = _e_pass(cape, nfci, cftc_e, cm, nm, cf, legs) & e_valid
        return _crossing_indices(in_band, e_dates)

    best_d = _pick_best(d_summary, "D")
    best_e = _pick_best(e_summary, "E")

    recommendations: list[dict[str, Any]] = []

    def rec_row(name: str, row: dict[str, Any] | None, combo: str) -> None:
        if not row:
            return
        recommendations.append(
            {
                "recommendation_tier": name,
                "combo": combo,
                **{k: v for k, v in row.items() if k != "combo"},
                "target_80pct_met": row.get(
                    "meets_80pct_1W" if combo == "D" else "meets_80pct_12M", False
                ),
                "target_n_20_40_met": row.get("meets_n_target", False),
            }
        )

    cfg_d_row = next((r for r in d_summary if r.get("is_config_baseline")), None)
    cfg_e_row = next((r for r in e_summary if r.get("is_config_baseline")), None)
    rec_row("CONFIG_BASELINE", cfg_d_row, "D")
    rec_row("CONFIG_BASELINE", cfg_e_row, "E")
    rec_row("BEST_IN_TARGET_N", best_d, "D")
    rec_row("BEST_IN_TARGET_N", best_e, "E")
    best_d_any = sorted(d_summary, key=lambda r: -(r.get("bear_hit_1W") or 0))[0] if d_summary else None
    best_e_any = sorted(e_summary, key=lambda r: -(r.get("bear_hit_12M") or 0))[0] if e_summary else None
    rec_row("BEST_ANY_N", best_d_any, "D")
    rec_row("BEST_ANY_N", best_e_any, "E")

    sync_rows_all: list[dict[str, Any]] = []
    regime_rows_all: list[dict[str, Any]] = []

    def run_pair(tag: str, dr: dict[str, Any], er: dict[str, Any]) -> None:
        di = d_indices(dr["vxts_min"], dr["cftc_min_pctile"], dr["vix_max"], dr["legs_required"])
        ei = e_indices(er["cape_min"], er["nfci_easy_max"], er["cftc_min_pctile"], er["legs_required"])
        sr, rr = sync_and_regime(
            d_dates,
            e_dates,
            di,
            ei,
            fwd_d,
            fwd_e,
            curve_map,
            dr["experiment_id"],
            er["experiment_id"],
        )
        for r in sr:
            r["config_pair"] = tag
        for r in rr:
            r["config_pair"] = tag
        sync_rows_all.extend(sr)
        regime_rows_all.extend(rr)

    if cfg_d_row and cfg_e_row:
        run_pair("CONFIG", cfg_d_row, cfg_e_row)
    if best_d and best_e:
        run_pair("BEST_TARGET_N", best_d, best_e)
    if best_d_any and best_e_any:
        run_pair("BEST_ANY_N", best_d_any, best_e_any)

    master: list[dict[str, Any]] = []
    for r in d_summary:
        master.append({**r, "analysis_type": "D_sweep"})
    for r in e_summary:
        master.append({**r, "analysis_type": "E_sweep"})

    _write_csv(OUT_DIR / "combo_d_sweep_results.csv", d_detail)
    _write_csv(OUT_DIR / "combo_e_sweep_results.csv", e_detail)
    _write_csv(OUT_DIR / "combo_d_sweep_summary.csv", d_summary)
    _write_csv(OUT_DIR / "combo_e_sweep_summary.csv", e_summary)
    _write_csv(OUT_DIR / "combo_de_sync_analysis.csv", sync_rows_all)
    _write_csv(OUT_DIR / "combo_de_regime_overlay.csv", regime_rows_all)
    _write_csv(OUT_DIR / "combo_de_recommended_thresholds.csv", recommendations)
    _write_csv(OUT_DIR / "combo_de_analysis_master.csv", master)

    meta = {
        "generated_at": datetime.now(UTC).isoformat(),
        "n_d_experiments": len(d_summary),
        "n_e_experiments": len(e_summary),
        "friday_d_dates": len(d_dates),
        "friday_e_dates": len(e_dates),
        "config_d": cfg_d_row,
        "config_e": cfg_e_row,
        "best_d_in_target_n": best_d,
        "best_e_in_target_n": best_e,
        "best_d_any_n": best_d_any,
        "best_e_any_n": best_e_any,
        "target_80pct_achieved_d": any(r.get("meets_80pct_1W") for r in d_summary),
        "target_80pct_achieved_e": any(r.get("meets_80pct_12M") for r in e_summary),
        "note": "Episode = first Friday crossing with 5d cooldown. 80% bear hit target likely unreachable without n<10.",
    }
    (OUT_DIR / "study_meta.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    print(json.dumps(meta, indent=2, default=str))


if __name__ == "__main__":
    main()
