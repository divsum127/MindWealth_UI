#!/usr/bin/env python3
"""Threshold sweep + spec comparison for named combos A–G."""

from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import product
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.analysis.combo_threshold_sweep import (  # noqa: E402
    _aligned_dates,
    _first_combo_crossings,
    _reading_on,
    load_readings_panel,
)
from src.macro_intelligence.config import load_config  # noqa: E402
from src.macro_intelligence.data.fred_pull import fetch_fred_series  # noqa: E402
from src.macro_intelligence.data.yahoo_pull import (  # noqa: E402
    fetch_yahoo_close,
    spx_with_50wma,
)
from src.macro_intelligence.engine.combo_detector import _hy_oas_bps  # noqa: E402
from src.macro_intelligence.engine.forward_returns import (  # noqa: E402
    _nyse_sessions,
    forward_return_pct,
)

OUT_DIR = Path(__file__).resolve().parent / "output_files"
COOLDOWN_DAYS = 5


@dataclass
class ComboSpec:
    letter: str
    label: str
    direction: str  # bullish | bearish
    spec_hit_pct: float
    spec_horizon_label: str
    primary_horizon: str
    horizons: list[tuple[str, int]]
    gate_description: str


COMBO_SPECS: dict[str, ComboSpec] = {
    "A": ComboSpec(
        "A",
        "Liquidity",
        "bullish",
        78.0,
        "6M",
        "6M",
        [("1M", 21), ("2M", 42), ("3M", 63), ("6M", 126)],
        "≥2 of 4 legs RARE/EXTREME (NFCI, HY, WALCL, CNH)",
    ),
    "B": ComboSpec(
        "B",
        "Capitulation",
        "bullish",
        87.5,
        "3M",
        "3M",
        [("2W", 10), ("1M", 21), ("6W", 30), ("2M", 42), ("3M", 63)],
        "VIX≥25 & pctile≥80; HY≥400bps & pctile≥80; CFTC≤15",
    ),
    "C": ComboSpec(
        "C",
        "Stagflation",
        "bearish",
        83.0,
        "6M",
        "6M",
        [("1M", 21), ("2M", 42), ("3M", 63), ("6M", 126)],
        "WTI 4wk≥10%; CPI surprise≥0.2; |WALCL MoM|<0.8%",
    ),
    "D": ComboSpec(
        "D",
        "FOMO Top",
        "bearish",
        78.0,
        "1W",
        "1W",
        [("1W", 5), ("2W", 10), ("3W", 15), ("4W", 20), ("1M", 21)],
        "VXTS≥1.10; CFTC≥85; VIX≤18; 3-of-3",
    ),
    "E": ComboSpec(
        "E",
        "Valuation Extreme",
        "bearish",
        73.0,
        "12M",
        "12M",
        [("3M", 63), ("6M", 126), ("9M", 189), ("12M", 252), ("15M", 315), ("18M", 378)],
        "CAPE≥28; NFCI≤−0.30; CFTC≥80; 2-of-3",
    ),
    "F": ComboSpec(
        "F",
        "Recovery",
        "bullish",
        78.0,
        "6M",
        "6M",
        [("1M", 21), ("2M", 42), ("3M", 63), ("6M", 126), ("9M", 189)],
        "SPX≥3% above 50WMA or reclaim; CFTC≤50",
    ),
    "G": ComboSpec(
        "G",
        "Hidden Stress",
        "bearish",
        75.0,
        "3W",
        "3W",
        [("1W", 5), ("2W", 10), ("3W", 15), ("4W", 20), ("6W", 30)],
        "VXTS<1.0; HY 4wk widen≥30bps; VIX≤20; 3-of-3",
    ),
}


def _fridays(dates: list[str]) -> list[str]:
    return [d for d in dates if pd.Timestamp(d).dayofweek == 4]


def _crossing_indices(in_band: np.ndarray, dates: list[str]) -> list[int]:
    events: list[int] = []
    prev = False
    cooldown_until: pd.Timestamp | None = None
    for i, ds in enumerate(dates):
        if in_band.dtype == float and np.isnan(in_band[i]):
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


def _hit_rate(rets: list[float], bullish: bool) -> float | None:
    if not rets:
        return None
    arr = np.array(rets, dtype=float)
    if bullish:
        return round(float((arr > 0).mean() * 100), 2)
    return round(float((arr < 0).mean() * 100), 2)


def _horizon_stats(indices: list[int], fwd: dict, label: str, bullish: bool) -> dict[str, Any]:
    rets = [fwd[i][label] for i in indices if fwd[i][label] is not None]
    if not rets:
        return {
            "n_mature": 0,
            "hit_rate_pct": None,
            "avg_spx_pct": None,
            "min_spx_pct": None,
            "max_spx_pct": None,
            "median_spx_pct": None,
        }
    arr = np.array(rets, dtype=float)
    return {
        "n_mature": len(rets),
        "hit_rate_pct": _hit_rate(rets, bullish),
        "avg_spx_pct": round(float(arr.mean()), 4),
        "min_spx_pct": round(float(arr.min()), 4),
        "max_spx_pct": round(float(arr.max()), 4),
        "median_spx_pct": round(float(np.median(arr)), 4),
    }


def _write_csv_with_header(path: Path, header_lines: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for k in row:
            if k not in seen:
                seen.add(k)
                keys.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        for line in header_lines:
            f.write(f"# {line}\n")
        if rows:
            w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)


def _hy_4wk_bps_series(dates: list[str]) -> np.ndarray:
    hy = fetch_fred_series("BAMLH0A0HYM2", "2010-01-01")
    out = np.full(len(dates), np.nan)
    for i, ds in enumerate(dates):
        ts = pd.Timestamp(ds)
        try:
            cur = float(hy.loc[:ts].iloc[-1])
            prior = float(hy.loc[: ts - pd.Timedelta(days=28)].iloc[-1])
            out[i] = (cur - prior) * 100
        except (IndexError, KeyError):
            continue
    return out


def _panel_col(panel, vid: str, dates: list[str], use_pctile: bool = False) -> np.ndarray:
    col = []
    for ds in dates:
        r = _reading_on(panel, vid, ds)
        if not r:
            col.append(np.nan)
        elif use_pctile:
            col.append(float(r["pctile"]) if r["pctile"] is not None else np.nan)
        else:
            col.append(float(r["raw"]) if r["raw"] is not None else np.nan)
    return np.array(col)


def _experiment_stats(
    indices: list[int],
    fwd: dict[int, dict[str, float | None]],
    horizons: list[tuple[str, int]],
    bullish: bool,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    hits = []
    for label, _ in horizons:
        s = _horizon_stats(indices, fwd, label, bullish)
        out[f"hit_{label}"] = s["hit_rate_pct"]
        out[f"avg_spx_{label}"] = s["avg_spx_pct"]
        out[f"min_spx_{label}"] = s["min_spx_pct"]
        out[f"max_spx_{label}"] = s["max_spx_pct"]
        if s["hit_rate_pct"] is not None:
            hits.append(s["hit_rate_pct"])
    out["hit_mean_all_horizons"] = round(float(np.mean(hits)), 2) if hits else None
    return out


def sweep_combo_b(panel, dates, fwd, cfg) -> list[dict[str, Any]]:
    vix = _panel_col(panel, "VIX", dates)
    vix_p = _panel_col(panel, "VIX", dates, True)
    hy = _panel_col(panel, "HY", dates)
    hy_p = _panel_col(panel, "HY", dates, True)
    cftc = _panel_col(panel, "CFTC", dates, True)
    valid = ~(np.isnan(vix) | np.isnan(hy) | np.isnan(cftc))
    hy_bps = np.array([_hy_oas_bps(x) if not np.isnan(x) else np.nan for x in hy])
    rows: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    bv = cfg.get("vix_min", 25)
    bh = cfg.get("hy_bps_min", 400)
    bc = cfg.get("cftc_max_pctile", 15)

    def run(vmin, hmin, cmax, legs, sweep):
        key = (vmin, hmin, cmax, legs)
        if key in seen:
            return
        seen.add(key)
        vix_ok = (vix >= vmin) & (vix_p >= 80)
        hy_ok = (hy_bps >= hmin) | (hy_p >= 80)
        cftc_ok = cftc <= cmax
        cnt = vix_ok.astype(int) + hy_ok.astype(int) + cftc_ok.astype(int)
        in_band = (cnt >= legs) & valid
        idx = _crossing_indices(in_band.astype(float), dates)
        is_cfg = vmin == bv and hmin == bh and cmax == bc and legs == 3
        row = {
            "experiment_id": f"B_vix{int(vmin)}_hy{int(hmin)}_cftc{int(cmax)}_l{legs}",
            "sweep_type": "config_baseline" if is_cfg else sweep,
            "is_config_baseline": is_cfg,
            "vix_min": vmin,
            "hy_bps_min": hmin,
            "cftc_max_pctile": cmax,
            "legs_required": legs,
            "gate_text": f"VIX>={vmin} & VIX pctile>=80; HY>={hmin}bps OR HY pctile>=80; CFTC<={cmax}; {legs}-of-3",
            "n_events": len(idx),
        }
        row.update(_experiment_stats(idx, fwd, COMBO_SPECS["B"].horizons, bullish=True))
        rows.append(row)

    run(bv, bh, bc, 3, "config_baseline")
    for v in [20, 22, 25, 28, 30]:
        run(v, bh, bc, 3, "univariate_vix")
    for h in [350, 375, 400, 425, 450]:
        run(bv, h, bc, 3, "univariate_hy")
    for c in [10, 12, 15, 18, 20]:
        run(bv, bh, c, 3, "univariate_cftc")
    for legs in [2, 3]:
        run(bv, bh, bc, legs, "legs")
    for v, h, c, legs in product([22, 25, 28], [375, 400, 425], [12, 15, 18], [2, 3]):
        run(v, h, c, legs, "factorial")
    return rows


def sweep_combo_c(panel, dates, fwd, cfg) -> list[dict[str, Any]]:
    wti = _panel_col(panel, "WTI", dates)
    cpi = _panel_col(panel, "CPI", dates)
    walcl = _panel_col(panel, "WALCL", dates)
    valid = ~(np.isnan(wti) | np.isnan(cpi) | np.isnan(walcl))
    rows: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    bw, bc, bf = cfg.get("wti_4wk_min", 10.0), cfg.get("cpi_surprise_min", 0.2), 0.8

    def run(wmin, cmin, fmax, sweep):
        key = (wmin, cmin, fmax)
        if key in seen:
            return
        seen.add(key)
        in_band = (wti >= wmin) & (cpi >= cmin) & (np.abs(walcl) < fmax) & valid
        idx = _crossing_indices(in_band.astype(float), dates)
        is_cfg = wmin == bw and cmin == bc and fmax == bf
        row = {
            "experiment_id": f"C_wti{wmin}_cpi{cmin}_walcl{fmax}",
            "sweep_type": "config_baseline" if is_cfg else sweep,
            "is_config_baseline": is_cfg,
            "wti_4wk_min_pct": wmin,
            "cpi_surprise_min": cmin,
            "walcl_flat_max_pct": fmax,
            "gate_text": f"WTI 4wk>={wmin}%; CPI surprise>={cmin}; |WALCL MoM|<{fmax}%; 3-of-3",
            "n_events": len(idx),
        }
        row.update(_experiment_stats(idx, fwd, COMBO_SPECS["C"].horizons, bullish=False))
        rows.append(row)

    run(bw, bc, bf, "config_baseline")
    for w in [8, 10, 12, 15]:
        run(w, bc, bf, "univariate_wti")
    for c in [0.1, 0.15, 0.2, 0.25, 0.3]:
        run(bw, c, bf, "univariate_cpi")
    for f in [0.6, 0.8, 1.0, 1.2]:
        run(bw, bc, f, "univariate_walcl")
    for w, c, f in product([8, 10, 12], [0.15, 0.2, 0.25], [0.6, 0.8, 1.0]):
        run(w, c, f, "factorial")
    return rows


def sweep_combo_d(panel, dates, fwd, cfg) -> list[dict[str, Any]]:
    vxts = _panel_col(panel, "VXTS", dates)
    cftc = _panel_col(panel, "CFTC", dates, True)
    vix = _panel_col(panel, "VIX", dates)
    valid = ~(np.isnan(vxts) | np.isnan(cftc) | np.isnan(vix))
    rows: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    bv, bc, bx = cfg.get("vxts_min", 1.1), cfg.get("cftc_min_pctile", 85), cfg.get("vix_max", 18)

    def run(v, c, x, legs, sweep):
        key = (v, c, x, legs)
        if key in seen:
            return
        seen.add(key)
        cnt = (vxts >= v).astype(int) + (cftc >= c).astype(int) + (vix <= x).astype(int)
        in_band = (cnt >= legs) & valid
        idx = _crossing_indices(in_band.astype(float), dates)
        is_cfg = abs(v - bv) < 1e-9 and c == bc and x == bx and legs == 3
        row = {
            "experiment_id": f"D_v{v:.2f}_c{int(c)}_x{int(x)}_l{legs}",
            "sweep_type": "config_baseline" if is_cfg else sweep,
            "is_config_baseline": is_cfg,
            "vxts_min": v,
            "cftc_min_pctile": c,
            "vix_max": x,
            "legs_required": legs,
            "gate_text": f"VXTS>={v}; CFTC>={c}; VIX<={x}; {legs}-of-3",
            "n_events": len(idx),
        }
        row.update(_experiment_stats(idx, fwd, COMBO_SPECS["D"].horizons, bullish=False))
        rows.append(row)

    run(bv, bc, bx, 3, "config_baseline")
    for v in [1.10, 1.15, 1.18, 1.20, 1.22, 1.25]:
        run(v, bc, bx, 3, "univariate_vxts")
    for c in [80, 85, 90, 92, 95]:
        run(bv, c, bx, 3, "univariate_cftc")
    for x in [14, 16, 18, 20]:
        run(bv, bc, x, 3, "univariate_vix")
    for v, c, x, legs in product([1.15, 1.18, 1.22, 1.25], [88, 90, 92, 95], [14, 16, 18], [2, 3]):
        run(v, c, x, legs, "factorial")
    return rows


def sweep_combo_e(panel, dates, fwd, cfg) -> list[dict[str, Any]]:
    cape = _panel_col(panel, "CAPE", dates)
    nfci = _panel_col(panel, "NFCI", dates)
    cftc = _panel_col(panel, "CFTC", dates, True)
    valid = ~(np.isnan(cape) | np.isnan(nfci) | np.isnan(cftc))
    rows: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    bcm, bnm, bcf, bl = cfg.get("cape_min", 28), cfg.get("nfci_easy_max", -0.3), cfg.get("cftc_min_pctile", 80), cfg.get("min_of_three", 2)

    def run(cm, nm, cf, legs, sweep):
        key = (cm, nm, cf, legs)
        if key in seen:
            return
        seen.add(key)
        cnt = (cape >= cm).astype(int) + (nfci <= nm).astype(int) + (cftc >= cf).astype(int)
        in_band = (cnt >= legs) & valid
        idx = _crossing_indices(in_band.astype(float), dates)
        is_cfg = cm == bcm and nm == bnm and cf == bcf and legs == bl
        row = {
            "experiment_id": f"E_cape{int(cm)}_nfci{nm:.2f}_cftc{int(cf)}_l{legs}",
            "sweep_type": "config_baseline" if is_cfg else sweep,
            "is_config_baseline": is_cfg,
            "cape_min": cm,
            "nfci_easy_max": nm,
            "cftc_min_pctile": cf,
            "legs_required": legs,
            "gate_text": f"CAPE>={cm}; NFCI<={nm}; CFTC>={cf}; {legs}-of-3",
            "n_events": len(idx),
        }
        row.update(_experiment_stats(idx, fwd, COMBO_SPECS["E"].horizons, bullish=False))
        rows.append(row)

    run(bcm, bnm, bcf, bl, "config_baseline")
    for cm in [26, 28, 30, 32, 35]:
        run(cm, bnm, bcf, bl, "univariate_cape")
    for nm in [-0.15, -0.20, -0.25, -0.30, -0.35]:
        run(bcm, nm, bcf, bl, "univariate_nfci")
    for cf in [75, 80, 85, 88, 92, 95]:
        run(bcm, bnm, cf, bl, "univariate_cftc")
    for cm, nm, cf, legs in product([28, 30, 32], [-0.20, -0.25, -0.30], [80, 85, 92], [2, 3]):
        run(cm, nm, cf, legs, "factorial")
    return rows


def sweep_combo_f(panel, dates_friday, fwd, cfg) -> list[dict[str, Any]]:
    spx_w = spx_with_50wma()
    cftc_dates = {r["date"] for r in panel.get("CFTC", [])}
    rows: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    bp, bc = cfg.get("spx_50wma_reclaim_weekly_pct", 3.0), cfg.get("cftc_max_pctile", 50)

    def run(pct_thresh, cmax, sweep):
        key = (pct_thresh, cmax)
        if key in seen:
            return
        seen.add(key)
        in_band = np.zeros(len(dates_friday), dtype=bool)
        hist = spx_w.sort_index()
        date_to_i = {d: i for i, d in enumerate(dates_friday)}
        prev_in = False
        cooldown_until: pd.Timestamp | None = None
        for i in range(1, len(hist)):
            row = hist.iloc[i]
            prev = hist.iloc[i - 1]
            dt = row.name
            ds = dt.strftime("%Y-%m-%d")
            if ds not in date_to_i or ds not in cftc_dates:
                continue
            cftc = _reading_on(panel, "CFTC", ds)
            if not cftc:
                continue
            above = bool(row["above_50wma"])
            pct_above = (float(row["close"]) / float(row["wma50"]) - 1.0) * 100.0
            reclaim = above and not bool(prev["above_50wma"])
            cftc_ok = (cftc["pctile"] or 50) <= cmax
            cur = above and cftc_ok and (reclaim or pct_above >= pct_thresh)
            if cooldown_until is not None and dt <= cooldown_until:
                prev_in = cur
                continue
            if cur and not prev_in:
                in_band[date_to_i[ds]] = True
                cooldown_until = dt + pd.Timedelta(days=COOLDOWN_DAYS)
            prev_in = cur
        idx = [i for i, v in enumerate(in_band) if v]
        is_cfg = pct_thresh == bp and cmax == bc
        row = {
            "experiment_id": f"F_spx{pct_thresh}_cftc{int(cmax)}",
            "sweep_type": "config_baseline" if is_cfg else sweep,
            "is_config_baseline": is_cfg,
            "spx_50wma_reclaim_pct": pct_thresh,
            "cftc_max_pctile": cmax,
            "gate_text": f"SPX above 50WMA AND (reclaim OR close>={pct_thresh}% above WMA); CFTC<={cmax}",
            "n_events": len(idx),
        }
        row.update(_experiment_stats(idx, fwd, COMBO_SPECS["F"].horizons, bullish=True))
        rows.append(row)

    run(bp, bc, "config_baseline")
    for p in [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]:
        run(p, bc, "univariate_spx")
    for c in [40, 45, 50, 55, 60]:
        run(bp, c, "univariate_cftc")
    for p, c in product([2.0, 3.0, 4.0, 5.0], [40, 50, 60]):
        run(p, c, "factorial")
    return rows


def sweep_combo_g(panel, dates, fwd, cfg) -> list[dict[str, Any]]:
    vxts = _panel_col(panel, "VXTS", dates)
    vix = _panel_col(panel, "VIX", dates)
    hy4 = _hy_4wk_bps_series(dates)
    valid = ~(np.isnan(vxts) | np.isnan(vix) | np.isnan(hy4))
    rows: list[dict[str, Any]] = []
    seen: set[tuple] = set()
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
            "experiment_id": f"G_vxts{vxmax}_vix{int(vmax)}_hy{int(hmin)}",
            "sweep_type": "config_baseline" if is_cfg else sweep,
            "is_config_baseline": is_cfg,
            "vxts_max": vxmax,
            "vix_max": vmax,
            "hy_widen_4wk_bps_min": hmin,
            "gate_text": f"VXTS<{vxmax}; VIX<={vmax}; HY 4wk widen>={hmin}bps; 3-of-3",
            "n_events": len(idx),
        }
        row.update(_experiment_stats(idx, fwd, COMBO_SPECS["G"].horizons, bullish=False))
        rows.append(row)

    run(bvx, bv, bh, "config_baseline")
    for vx in [0.92, 0.95, 1.0, 1.05]:
        run(vx, bv, bh, "univariate_vxts")
    for v in [16, 18, 20, 22]:
        run(bvx, v, bh, "univariate_vix")
    for h in [20, 25, 30, 40, 50]:
        run(bvx, bv, h, "univariate_hy")
    for vx, v, h in product([0.95, 1.0, 1.05], [18, 20, 22], [25, 30, 40]):
        run(vx, v, h, "factorial")
    return rows


def sweep_combo_a(panel, dates, fwd, cfg) -> list[dict[str, Any]]:
    nfci_p = _panel_col(panel, "NFCI", dates, True)
    hy = _panel_col(panel, "HY", dates)
    hy_p = _panel_col(panel, "HY", dates, True)
    walcl = _panel_col(panel, "WALCL", dates)
    cnh_p = _panel_col(panel, "CNH", dates, True)
    valid = ~(np.isnan(nfci_p) | np.isnan(hy) | np.isnan(walcl) | np.isnan(cnh_p))
    hy_bps = np.array([_hy_oas_bps(x) if not np.isnan(x) else np.nan for x in hy])
    rows: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    bmin = cfg.get("min_of_four", 2)

    def leg_rare(high, low, hy_b, walcl_m):
        nfci_r = (nfci_p >= high) | (nfci_p <= low)
        hy_r = (hy_bps >= hy_b) | (hy_p >= high)
        walcl_r = np.abs(walcl) >= walcl_m
        cnh_r = (cnh_p >= high) | (cnh_p <= low)
        return nfci_r, hy_r, walcl_r, cnh_r

    def run(min_legs, high, low, hy_b, walcl_m, sweep):
        key = (min_legs, high, low, hy_b, walcl_m)
        if key in seen:
            return
        seen.add(key)
        nfci_r, hy_r, walcl_r, cnh_r = leg_rare(high, low, hy_b, walcl_m)
        cnt = nfci_r.astype(int) + hy_r.astype(int) + walcl_r.astype(int) + cnh_r.astype(int)
        in_band = (cnt >= min_legs) & valid
        idx = _crossing_indices(in_band.astype(float), dates)
        is_cfg = min_legs == bmin and high == 80 and low == 20 and hy_b == 400 and walcl_m == 0.8
        row = {
            "experiment_id": f"A_min{min_legs}_p{int(high)}_{int(low)}_hy{int(hy_b)}_w{walcl_m}",
            "sweep_type": "config_baseline" if is_cfg else sweep,
            "is_config_baseline": is_cfg,
            "min_of_four": min_legs,
            "rare_pctile_high": high,
            "rare_pctile_low": low,
            "hy_bps_rare": hy_b,
            "walcl_mom_rare_pct": walcl_m,
            "gate_text": f"≥{min_legs} of 4 rare: NFCI/CNH pctile>={high} or <={low}; HY>={hy_b}bps or pctile>={high}; |WALCL|>={walcl_m}%",
            "n_events": len(idx),
        }
        row.update(_experiment_stats(idx, fwd, COMBO_SPECS["A"].horizons, bullish=True))
        rows.append(row)

    run(bmin, 80, 20, 400, 0.8, "config_baseline")
    for m in [2, 3]:
        run(m, 80, 20, 400, 0.8, "legs")
    for h in [75, 80, 85]:
        run(bmin, h, 100 - h, 400, 0.8, "univariate_pctile")
    for hb in [350, 400, 450]:
        run(bmin, 80, 20, hb, 0.8, "univariate_hy")
    for wm in [0.6, 0.8, 1.0]:
        run(bmin, 80, 20, 400, wm, "univariate_walcl")
    for m, h, hb in product([2, 3], [75, 80, 85], [350, 400, 450]):
        run(m, h, 100 - h, hb, 0.8, "factorial")
    return rows


def _pick_best(rows: list[dict], spec: ComboSpec, min_n: int = 5) -> dict | None:
    primary = f"hit_{spec.primary_horizon}"
    pool = [r for r in rows if r.get("n_events", 0) >= min_n]
    if not pool:
        pool = rows
    pool = sorted(
        pool,
        key=lambda r: (
            -(r.get(primary) or 0),
            -(r.get("hit_mean_all_horizons") or 0),
            -abs(r.get("n_events", 0) - 20),
        ),
    )
    return pool[0] if pool else None


def _config_row(rows: list[dict]) -> dict | None:
    return next((r for r in rows if r.get("is_config_baseline")), None)


def _summary_header(spec: ComboSpec, rows: list[dict], cfg_row: dict | None) -> list[str]:
    primary = f"hit_{spec.primary_horizon}"
    hits = [r[primary] for r in rows if r.get(primary) is not None and r.get("n_events", 0) >= 3]
    lines = [
        f"COMBO {spec.letter} — {spec.label}",
        f"Direction: {spec.direction} | Spec target: {spec.spec_hit_pct}% @ {spec.spec_horizon_label}",
        f"Horizons: {', '.join(h for h, _ in spec.horizons)}",
        f"Experiments: {len(rows)} | CONFIG: {cfg_row['gate_text'] if cfg_row else 'n/a'}",
    ]
    if cfg_row:
        lines.append(
            f"CONFIG n={cfg_row['n_events']} | primary {spec.primary_horizon} hit={cfg_row.get(primary)}% "
            f"(spec {spec.spec_hit_pct}%, delta {round((cfg_row.get(primary) or 0) - spec.spec_hit_pct, 1)}pp)"
        )
    if hits:
        lines.append(
            f"Sweep primary hit — min={min(hits):.1f}% max={max(hits):.1f}% avg={float(np.mean(hits)):.1f}%"
        )
    for label, _ in spec.horizons:
        col = f"hit_{label}"
        hvals = [r[col] for r in rows if r.get(col) is not None and r.get("n_events", 0) >= 3]
        if hvals:
            lines.append(
                f"  {label}: hit min={min(hvals):.1f}% max={max(hvals):.1f}% avg={float(np.mean(hvals)):.1f}%"
            )
    return lines


def _detail_rows(summary_rows: list[dict], spec: ComboSpec) -> list[dict]:
    detail: list[dict] = []
    for row in summary_rows:
        for label, td in spec.horizons:
            detail.append(
                {
                    **{k: v for k, v in row.items() if not k.startswith("avg_spx_") and not k.startswith("min_spx_") and not k.startswith("max_spx_")},
                    "horizon": label,
                    "trading_days": td,
                    "hit_rate_pct": row.get(f"hit_{label}"),
                    "avg_spx_pct": row.get(f"avg_spx_{label}"),
                    "min_spx_pct": row.get(f"min_spx_{label}"),
                    "max_spx_pct": row.get(f"max_spx_{label}"),
                }
            )
    return detail


def _build_analysis_md(
    comparisons: list[dict],
    best_rows: list[dict],
) -> str:
    lines = [
        "# All Combos Threshold Study — Analysis",
        "",
        f"Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "Method: first-crossing episodes, 5-day cooldown, aligned `daily_readings` panel (Friday-only for Combo F).",
        "Hit rate = % episodes where SPX moved in combo direction (bullish: up, bearish: down).",
        "",
        "## 1. CONFIG vs product spec",
        "",
        "| Combo | Spec hit % | Spec horizon | CONFIG n | CONFIG primary hit % | Delta vs spec |",
        "|-------|------------|--------------|----------|----------------------|---------------|",
    ]
    for c in comparisons:
        delta = c.get("delta_pp")
        dstr = f"{delta:+.1f}pp" if delta is not None else "n/a"
        lines.append(
            f"| {c['combo']} {c['label']} | {c['spec_hit_pct']}% | {c['spec_horizon']} "
            f"| {c['config_n']} | {c['config_primary_hit']}% | {dstr} |"
        )
    lines.extend(
        [
            "",
            "## 2. Recommended thresholds (best primary hit, n≥5)",
            "",
        ]
    )
    for b in best_rows:
        lines.append(f"### Combo {b['combo']} — {b['label']}")
        lines.append(f"- **Gates:** {b['gate_text']}")
        lines.append(f"- **Episodes:** {b['n_events']}")
        lines.append(f"- **Primary ({b['primary_horizon']}):** {b['primary_hit']}% hit (spec {b['spec_hit_pct']}%)")
        lines.append(f"- **Mean hit all horizons:** {b.get('hit_mean_all_horizons')}%")
        lines.append("")
    lines.extend(
        [
            "## 3. Interpretation notes",
            "",
            "- **A:** Proxy rare legs via pctile bands; production uses variable-engine RARE/EXTREME tiers.",
            "- **B:** Strongest empirical match to spec; CONFIG near ~80% at 3M in replay.",
            "- **C:** Very low n; treat sweep as indicative only.",
            "- **D/E:** CONFIG underperforms spec; tightened gates improve hit at cost of n (see combo_de_thresholds/).",
            "- **F:** CONFIG typically near spec at 6M on episode model.",
            "- **G:** Sparse fires; short-horizon bear hit is proxy for vol-spike timing spec.",
            "",
            "Full sweeps: `output_files/combo_*_sweep_summary.csv`",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cfg_all = load_config()
    named = cfg_all.get("named_combos", {})
    panel = load_readings_panel("1996-01-01")
    spx = fetch_yahoo_close("^GSPC", "1990-01-01")
    sessions = _nyse_sessions()

    sweep_fns: dict[str, Callable] = {
        "A": lambda p, d, f: sweep_combo_a(p, d, f, named.get("A", {})),
        "B": lambda p, d, f: sweep_combo_b(p, d, f, named.get("B", {})),
        "C": lambda p, d, f: sweep_combo_c(p, d, f, named.get("C", {})),
        "D": lambda p, d, f: sweep_combo_d(p, d, f, named.get("D", {})),
        "E": lambda p, d, f: sweep_combo_e(p, d, f, named.get("E", {})),
        "G": lambda p, d, f: sweep_combo_g(p, d, f, named.get("G", {})),
    }

    var_dates = {
        "A": _aligned_dates(panel, ["NFCI", "HY", "WALCL", "CNH"]),
        "B": _aligned_dates(panel, ["VIX", "HY", "CFTC"]),
        "C": _aligned_dates(panel, ["WTI", "CPI", "WALCL"]),
        "D": _aligned_dates(panel, ["VXTS", "CFTC", "VIX"]),
        "E": _aligned_dates(panel, ["CAPE", "NFCI", "CFTC"]),
        "G": _aligned_dates(panel, ["VXTS", "VIX"]),
    }

    comparisons: list[dict] = []
    best_rows: list[dict] = []
    meta: dict[str, Any] = {"combos": {}, "generated_at": datetime.now(UTC).isoformat()}

    for letter, spec in COMBO_SPECS.items():
        print(f"Sweeping Combo {letter}...")
        if letter == "F":
            dates = _fridays(_aligned_dates(panel, ["CFTC"]))
            fwd = _precompute_returns(dates, spx, sessions, spec.horizons)
            rows = sweep_combo_f(panel, dates, fwd, named.get("F", {}))
        else:
            dates = var_dates[letter]
            fwd = _precompute_returns(dates, spx, sessions, spec.horizons)
            rows = sweep_fns[letter](panel, dates, fwd)

        cfg_row = _config_row(rows)
        best = _pick_best(rows, spec)
        primary = f"hit_{spec.primary_horizon}"
        header = _summary_header(spec, rows, cfg_row)

        _write_csv_with_header(OUT_DIR / f"combo_{letter}_sweep_summary.csv", header, rows)
        _write_csv_with_header(
            OUT_DIR / f"combo_{letter}_sweep_detail.csv",
            header + ["# Detail: one row per experiment x horizon"],
            _detail_rows(rows, spec),
        )

        if cfg_row:
            cfg_hit = cfg_row.get(primary)
            comparisons.append(
                {
                    "combo": letter,
                    "label": spec.label,
                    "spec_hit_pct": spec.spec_hit_pct,
                    "spec_horizon": spec.spec_horizon_label,
                    "config_n": cfg_row["n_events"],
                    "config_primary_hit": cfg_hit,
                    "delta_pp": round((cfg_hit or 0) - spec.spec_hit_pct, 2) if cfg_hit is not None else None,
                    "gate_text": cfg_row["gate_text"],
                }
            )
        if best:
            best_rows.append(
                {
                    "combo": letter,
                    "label": spec.label,
                    "spec_hit_pct": spec.spec_hit_pct,
                    "primary_horizon": spec.primary_horizon,
                    "primary_hit": best.get(primary),
                    "hit_mean_all_horizons": best.get("hit_mean_all_horizons"),
                    "n_events": best["n_events"],
                    "gate_text": best["gate_text"],
                    "experiment_id": best["experiment_id"],
                    "is_config_baseline": best.get("is_config_baseline"),
                }
            )

        meta["combos"][letter] = {
            "n_experiments": len(rows),
            "config": cfg_row,
            "best": best,
            "spec": {
                "hit_pct": spec.spec_hit_pct,
                "horizon": spec.spec_horizon_label,
                "gate_description": spec.gate_description,
            },
        }

    _write_csv_with_header(
        OUT_DIR / "all_combos_config_vs_spec.csv",
        ["CONFIG baseline vs product spec at primary horizon"],
        comparisons,
    )
    _write_csv_with_header(
        OUT_DIR / "all_combos_best_thresholds.csv",
        ["Best primary hit rate per combo (n>=5 preferred)"],
        best_rows,
    )

    analysis = _build_analysis_md(comparisons, best_rows)
    (OUT_DIR / "ANALYSIS.md").write_text(analysis, encoding="utf-8")
    (OUT_DIR / "study_meta.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    print(analysis)


if __name__ == "__main__":
    main()
