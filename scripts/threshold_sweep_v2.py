#!/usr/bin/env python3
"""Threshold validation sweep v2: raw CONFIG bands, first-crossing, PW returns."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.analysis.regime_experiments.metrics import (  # noqa: E402
    probability_weighted_summary,
)
from src.macro_intelligence.config import load_config  # noqa: E402
from src.macro_intelligence.data.yahoo_pull import fetch_yahoo_close  # noqa: E402
from src.macro_intelligence.db.connection import get_connection, init_db  # noqa: E402
from src.macro_intelligence.engine.forward_returns import (  # noqa: E402
    _nyse_sessions,
    forward_return_pct,
)

HORIZONS = [
    ("spx_1m", 21, 0.5),
    ("spx_3m", 63, 2.5),
    ("spx_6m", 126, 5.0),
    ("spx_9m", 189, 7.5),
    ("spx_12m", 252, 10.0),
]

HOSTILE_FED = {"HIKING_EARLY", "HIKING_LATE", "TIGHTENING"}
COOLDOWN_DAYS = 5

PRIMARY_HORIZON = {
    "VIX": "spx_3m",
    "HY": "spx_3m",
    "CFTC": "spx_3m",
    "NFCI": "spx_3m",
    "WALCL": "spx_3m",
    "WTI": "spx_6m",
    "CNH": "spx_3m",
    "GSR": "spx_3m",
    "VXTS": "spx_3m",
    "CAPE": "spx_12m",
    "CPI": "spx_3m",
    "CURVE": "spx_3m",
}


def _norm_pctile(p: float | None) -> float | None:
    if p is None:
        return None
    val = float(p)
    if 0 < val <= 1.0:
        return val * 100.0
    return val


def _hy_bps(raw: float | None) -> float:
    if raw is None:
        return 0.0
    val = float(raw)
    return val * 100.0 if val < 50 else val


def _parse_meta(meta_json: str | None) -> dict[str, Any]:
    if not meta_json:
        return {}
    try:
        return json.loads(meta_json)
    except json.JSONDecodeError:
        return {}


def load_regime_map() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    with get_connection() as conn:
        for table in ("macro_regime_log", "macro_regime_log_v2"):
            try:
                rows = conn.execute(f"SELECT date, regime_json FROM {table}").fetchall()
            except Exception:
                continue
            for r in rows:
                if r["date"] not in out:
                    out[r["date"]] = json.loads(r["regime_json"])
    return out


def regime_at(reg_map: dict[str, dict[str, Any]], dt: pd.Timestamp) -> dict[str, Any]:
    ds = dt.strftime("%Y-%m-%d")
    if ds in reg_map:
        return reg_map[ds]
    for i in range(1, 8):
        key = (dt - pd.Timedelta(days=i)).strftime("%Y-%m-%d")
        if key in reg_map:
            return reg_map[key]
    return {}


def is_hostile(regime: dict[str, Any]) -> bool:
    fed = regime.get("fed_cycle") or regime.get("fed_cycle_legacy") or regime.get("fed_cycle_v2")
    curve = regime.get("curve_regime") or regime.get("curve_regime_v2") or regime.get("curve_regime_legacy")
    if fed in HOSTILE_FED:
        return True
    if curve == "INVERTED":
        return True
    return False


@dataclass
class BandSpec:
    band_label: str
    threshold_value: Any
    direction: str
    bullish: bool
    is_current: bool
    in_band: Callable[[dict[str, Any]], bool]


def load_var_series(var_id: str, start: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT date, raw_value, unconditional_pctile, meta_json
            FROM daily_readings
            WHERE var_id = ? AND date >= ?
            ORDER BY date
            """,
            (var_id, start),
        ).fetchall()
    series: list[dict[str, Any]] = []
    for r in rows:
        meta = _parse_meta(r["meta_json"])
        series.append(
            {
                "date": r["date"],
                "raw": float(r["raw_value"]) if r["raw_value"] is not None else None,
                "pctile": _norm_pctile(r["unconditional_pctile"]),
                "meta": meta,
                "steepen": meta.get("steepen_4wk_bps") or meta.get("steepen_4wk") or 0.0,
            }
        )
    return series


def first_crossings(
    series: list[dict[str, Any]],
    in_band_fn: Callable[[dict[str, Any]], bool],
    *,
    cooldown_days: int = COOLDOWN_DAYS,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    prev_in = False
    cooldown_until: pd.Timestamp | None = None
    for row in series:
        dt = pd.Timestamp(row["date"])
        in_band = in_band_fn(row)
        if cooldown_until is not None and dt <= cooldown_until:
            prev_in = in_band
            continue
        if in_band and not prev_in:
            events.append(row)
            cooldown_until = dt + pd.Timedelta(days=cooldown_days)
        if not in_band:
            prev_in = False
        else:
            prev_in = True
    return events


def compute_pw_returns(
    crossing_dates: list[str],
    spx: pd.Series,
    sessions: pd.DatetimeIndex,
    *,
    bullish: bool,
    regime_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    horizons_out: dict[str, Any] = {}
    hostile_by_h: dict[str, list[float]] = {h: [] for h, _, _ in HORIZONS}

    for h_key, days, bench in HORIZONS:
        rets: list[float] = []
        for ds in crossing_dates:
            ret = forward_return_pct(spx, pd.Timestamp(ds), days, sessions=sessions)
            if ret is not None:
                rets.append(ret)
                reg = regime_at(regime_map, pd.Timestamp(ds))
                if is_hostile(reg):
                    hostile_by_h[h_key].append(ret)
        horizons_out[h_key] = probability_weighted_summary(
            rets, bullish=bullish, benchmark_pct=bench, horizon=h_key
        )
        horizons_out[h_key]["hostile"] = probability_weighted_summary(
            hostile_by_h[h_key], bullish=bullish, benchmark_pct=bench, horizon=h_key
        )

    return horizons_out


def _vix_bands() -> list[BandSpec]:
    specs: list[BandSpec] = []
    for level, label, current in [
        (15, "VIX_15plus", False),
        (18, "VIX_18plus", False),
        (20, "VIX_20plus", False),
        (25, "VIX_25plus_CURRENT_RARE", True),
        (28, "VIX_28plus", False),
        (30, "VIX_30plus", False),
        (35, "VIX_35plus_CURRENT_EXTREME", True),
        (40, "VIX_40plus", False),
    ]:
        specs.append(
            BandSpec(
                band_label=label,
                threshold_value=level,
                direction="UP",
                bullish=False,
                is_current=current,
                in_band=lambda r, lv=level: (r["raw"] or 0) >= lv and (r["pctile"] or 0) >= 80,
            )
        )
    specs.append(
        BandSpec(
            band_label="VIX_pctile_65_79",
            threshold_value=65,
            direction="UP",
            bullish=False,
            is_current=False,
            in_band=lambda r: r["pctile"] is not None and 65 <= r["pctile"] <= 79,
        )
    )
    return specs


def _hy_bands() -> list[BandSpec]:
    specs: list[BandSpec] = []
    for bps, label, current in [
        (300, "HY_300bps", False),
        (350, "HY_350bps", False),
        (400, "HY_400bps_CURRENT_RARE", True),
        (450, "HY_450bps", False),
        (500, "HY_500bps_CURRENT_EXTREME", True),
        (600, "HY_600bps", False),
    ]:
        specs.append(
            BandSpec(
                band_label=label,
                threshold_value=bps,
                direction="UP",
                bullish=False,
                is_current=current,
                in_band=lambda r, b=bps: _hy_bps(r["raw"]) >= b,
            )
        )
    for pct, label in [(70, "HY_pctile_70plus"), (75, "HY_pctile_75plus")]:
        specs.append(
            BandSpec(
                band_label=label,
                threshold_value=pct,
                direction="UP",
                bullish=False,
                is_current=False,
                in_band=lambda r, p=pct: (r["pctile"] or 0) >= p,
            )
        )
    return specs


def _cftc_bands() -> list[BandSpec]:
    specs: list[BandSpec] = []
    for pct, label, current, bullish in [
        (30, "CFTC_short_30", False, True),
        (20, "CFTC_short_20", False, True),
        (15, "CFTC_short_15_CURRENT_RARE", True, True),
        (10, "CFTC_short_10", False, True),
        (5, "CFTC_short_5_CURRENT_EXTREME", True, True),
    ]:
        specs.append(
            BandSpec(
                band_label=label,
                threshold_value=pct,
                direction="DOWN",
                bullish=bullish,
                is_current=current,
                in_band=lambda r, p=pct: r["pctile"] is not None and r["pctile"] <= p,
            )
        )
    for pct, label, current in [
        (70, "CFTC_long_70", False),
        (80, "CFTC_long_80", False),
        (85, "CFTC_long_85_CURRENT_RARE", True),
        (90, "CFTC_long_90", False),
        (95, "CFTC_long_95_CURRENT_EXTREME", True),
    ]:
        specs.append(
            BandSpec(
                band_label=label,
                threshold_value=pct,
                direction="UP",
                bullish=False,
                is_current=current,
                in_band=lambda r, p=pct: (r["pctile"] or 0) >= p,
            )
        )
    return specs


def _nfci_bands() -> list[BandSpec]:
    specs: list[BandSpec] = []
    for sd, pct, label, current in [
        (-0.1, 35, "NFCI_easy_0.1", False),
        (-0.2, 25, "NFCI_easy_0.2", False),
        (-0.3, 20, "NFCI_easy_0.3_CURRENT", True),
        (-0.5, 12, "NFCI_easy_0.5", False),
        (-0.8, 5, "NFCI_easy_0.8", False),
    ]:
        specs.append(
            BandSpec(
                band_label=label,
                threshold_value=sd,
                direction="DOWN",
                bullish=True,
                is_current=current,
                in_band=lambda r, s=sd, p=pct: (r["raw"] or 0) <= s or (r["pctile"] or 100) <= p,
            )
        )
    for sd, pct, label, current in [
        (0.3, 80, "NFCI_tight_0.3_CURRENT", True),
        (0.5, 88, "NFCI_tight_0.5", False),
        (0.8, 95, "NFCI_tight_0.8", False),
    ]:
        specs.append(
            BandSpec(
                band_label=label,
                threshold_value=sd,
                direction="UP",
                bullish=False,
                is_current=current,
                in_band=lambda r, s=sd, p=pct: (r["raw"] or 0) >= s or (r["pctile"] or 0) >= p,
            )
        )
    return specs


def _walcl_bands() -> list[BandSpec]:
    specs: list[BandSpec] = []
    for mom, label, current in [
        (0.3, "WALCL_expand_0.3", False),
        (0.5, "WALCL_expand_0.5", False),
        (0.8, "WALCL_expand_0.8_CURRENT_RARE", True),
        (1.5, "WALCL_expand_1.5", False),
        (2.0, "WALCL_expand_2.0_CURRENT_EXTREME", True),
        (3.0, "WALCL_expand_3.0", False),
    ]:
        specs.append(
            BandSpec(
                band_label=label,
                threshold_value=mom,
                direction="UP",
                bullish=True,
                is_current=current,
                in_band=lambda r, m=mom: (r["raw"] or 0) >= m,
            )
        )
    for mom, label, current in [
        (-0.3, "WALCL_contract_0.3", False),
        (-0.5, "WALCL_contract_0.5", False),
        (-0.8, "WALCL_contract_0.8_CURRENT_RARE", True),
        (-1.5, "WALCL_contract_1.5", False),
        (-2.0, "WALCL_contract_2.0_CURRENT_EXTREME", True),
    ]:
        specs.append(
            BandSpec(
                band_label=label,
                threshold_value=mom,
                direction="DOWN",
                bullish=False,
                is_current=current,
                in_band=lambda r, m=mom: (r["raw"] or 0) <= m,
            )
        )
    return specs


def _roc_bands(
    var_id: str,
    down_levels: list[tuple[float, str, bool]],
    up_levels: list[tuple[float, str, bool]],
    *,
    down_bullish: bool = True,
    up_bullish: bool = False,
) -> list[BandSpec]:
    specs: list[BandSpec] = []
    for thresh, label, current in down_levels:
        specs.append(
            BandSpec(
                band_label=label,
                threshold_value=-thresh,
                direction="DOWN",
                bullish=down_bullish,
                is_current=current,
                in_band=lambda r, t=thresh: (r["raw"] or 0) <= -t,
            )
        )
    for thresh, label, current in up_levels:
        specs.append(
            BandSpec(
                band_label=label,
                threshold_value=thresh,
                direction="UP",
                bullish=up_bullish,
                is_current=current,
                in_band=lambda r, t=thresh: (r["raw"] or 0) >= t,
            )
        )
    return specs


def _vxts_bands() -> list[BandSpec]:
    specs: list[BandSpec] = []
    for ratio, label, current in [
        (1.02, "VXTS_backward_1.02", False),
        (1.05, "VXTS_backward_1.05", False),
        (1.10, "VXTS_backward_1.10_CURRENT_RARE", True),
        (1.15, "VXTS_backward_1.15", False),
        (1.20, "VXTS_backward_1.20_CURRENT_EXTREME", True),
    ]:
        specs.append(
            BandSpec(
                band_label=label,
                threshold_value=ratio,
                direction="UP",
                bullish=False,
                is_current=current,
                in_band=lambda r, rt=ratio: (r["raw"] or 0) >= rt,
            )
        )
    for ratio, label, current in [
        (0.95, "VXTS_contango_0.95_CURRENT_RARE", True),
        (0.90, "VXTS_contango_0.90", False),
        (0.85, "VXTS_contango_0.85_CURRENT_EXTREME", True),
        (0.80, "VXTS_contango_0.80", False),
    ]:
        specs.append(
            BandSpec(
                band_label=label,
                threshold_value=ratio,
                direction="DOWN",
                bullish=True,
                is_current=current,
                in_band=lambda r, rt=ratio: (r["raw"] or 999) <= rt,
            )
        )
    return specs


def _cape_bands() -> list[BandSpec]:
    specs: list[BandSpec] = []
    for level, label, current in [
        (22, "CAPE_high_22", False),
        (25, "CAPE_high_25", False),
        (28, "CAPE_high_28_CURRENT_RARE", True),
        (30, "CAPE_high_30", False),
        (32, "CAPE_high_32_CURRENT_EXTREME", True),
        (35, "CAPE_high_35", False),
        (38, "CAPE_high_38", False),
    ]:
        specs.append(
            BandSpec(
                band_label=label,
                threshold_value=level,
                direction="UP",
                bullish=False,
                is_current=current,
                in_band=lambda r, lv=level: (r["raw"] or 0) >= lv,
            )
        )
    for level, label, current in [
        (16, "CAPE_low_16_CURRENT_RARE", True),
        (14, "CAPE_low_14", False),
        (12, "CAPE_low_12_CURRENT_EXTREME", True),
    ]:
        specs.append(
            BandSpec(
                band_label=label,
                threshold_value=level,
                direction="DOWN",
                bullish=True,
                is_current=current,
                in_band=lambda r, lv=level: (r["raw"] or 999) <= lv,
            )
        )
    return specs


def _cpi_bands() -> list[BandSpec]:
    specs: list[BandSpec] = []
    for surprise, label, current in [
        (0.05, "CPI_hot_0.05", False),
        (0.10, "CPI_hot_0.10", False),
        (0.20, "CPI_hot_0.20_CURRENT_RARE", True),
        (0.30, "CPI_hot_0.30", False),
        (0.40, "CPI_hot_0.40_CURRENT_EXTREME", True),
        (0.60, "CPI_hot_0.60", False),
    ]:
        specs.append(
            BandSpec(
                band_label=label,
                threshold_value=surprise,
                direction="UP",
                bullish=False,
                is_current=current,
                in_band=lambda r, s=surprise: (r["raw"] or 0) >= s,
            )
        )
    return specs


def _curve_bands() -> list[BandSpec]:
    specs: list[BandSpec] = []
    for spread, label, current in [
        (-10, "CURVE_invert_10bps", False),
        (-20, "CURVE_invert_20bps", False),
        (-30, "CURVE_invert_30bps_CURRENT_RARE", True),
        (-50, "CURVE_invert_50bps", False),
        (-80, "CURVE_invert_80bps_CURRENT_EXTREME", True),
        (-100, "CURVE_invert_100bps", False),
    ]:
        specs.append(
            BandSpec(
                band_label=label,
                threshold_value=spread,
                direction="DOWN",
                bullish=False,
                is_current=current,
                in_band=lambda r, sp=spread: (r["raw"] or 0) <= sp,
            )
        )
    for steep, label, current in [
        (5, "CURVE_steepen_5bps", False),
        (10, "CURVE_steepen_10bps", False),
        (15, "CURVE_steepen_15bps_CURRENT_RARE", True),
        (25, "CURVE_steepen_25bps", False),
        (40, "CURVE_steepen_40bps_CURRENT_EXTREME", True),
    ]:
        specs.append(
            BandSpec(
                band_label=label,
                threshold_value=steep,
                direction="UP",
                bullish=True,
                is_current=current,
                in_band=lambda r, st=steep: (r["steepen"] or 0) >= st,
            )
        )
    return specs


VAR_BAND_BUILDERS: dict[str, Callable[[], list[BandSpec]]] = {
    "VIX": _vix_bands,
    "HY": _hy_bands,
    "CFTC": _cftc_bands,
    "NFCI": _nfci_bands,
    "WALCL": _walcl_bands,
    "WTI": lambda: _roc_bands(
        "WTI",
        [(3, "WTI_down_3pct", False), (5, "WTI_down_5pct", False), (6, "WTI_down_6pct_CURRENT_RARE", True),
         (8, "WTI_down_8pct", False), (10, "WTI_down_10pct_CURRENT_EXTREME", True), (15, "WTI_down_15pct", False)],
        [(5, "WTI_up_5pct", False), (6, "WTI_up_6pct_CURRENT_RARE", True), (8, "WTI_up_8pct", False),
         (10, "WTI_up_10pct_CURRENT_EXTREME", True), (15, "WTI_up_15pct", False)],
        down_bullish=True,
        up_bullish=False,
    ),
    "CNH": lambda: _roc_bands(
        "CNH",
        [(0.5, "CNH_down_0.5pct", False), (1.0, "CNH_down_1.0pct", False), (1.5, "CNH_down_1.5pct_CURRENT_RARE", True),
         (2.5, "CNH_down_2.5pct", False), (3.5, "CNH_down_3.5pct_CURRENT_EXTREME", True)],
        [(0.5, "CNH_up_0.5pct", False), (1.0, "CNH_up_1.0pct", False), (1.5, "CNH_up_1.5pct_CURRENT_RARE", True),
         (2.5, "CNH_up_2.5pct", False), (3.5, "CNH_up_3.5pct_CURRENT_EXTREME", True)],
    ),
    "GSR": lambda: _roc_bands(
        "GSR",
        [],
        [(2, "GSR_up_2pct", False), (3, "GSR_up_3pct", False), (4, "GSR_up_4pct", False),
         (5, "GSR_up_5pct_CURRENT_RARE", True), (6, "GSR_up_6pct", False),
         (8, "GSR_up_8pct_CURRENT_EXTREME", True), (10, "GSR_up_10pct", False)],
    ),
    "VXTS": _vxts_bands,
    "CAPE": _cape_bands,
    "CPI": _cpi_bands,
    "CURVE": _curve_bands,
}


def sweep_variable(
    var_id: str,
    *,
    spx: pd.Series,
    sessions: pd.DatetimeIndex,
    regime_map: dict[str, dict[str, Any]],
    start: str,
    cfg: dict[str, Any],
) -> dict[str, Any]:
    series = load_var_series(var_id, start)
    bands = VAR_BAND_BUILDERS[var_id]()
    var_cfg = next((v for v in cfg.get("variables", []) if v["id"] == var_id), {})
    results: list[dict[str, Any]] = []

    for band in bands:
        crossings = first_crossings(series, band.in_band)
        dates = [c["date"] for c in crossings]
        horizons = compute_pw_returns(
            dates, spx, sessions, bullish=band.bullish, regime_map=regime_map
        )
        results.append(
            {
                "band_label": band.band_label,
                "threshold_value": band.threshold_value,
                "direction": band.direction,
                "bullish": band.bullish,
                "is_current": band.is_current,
                "n": len(dates),
                "horizons": horizons,
            }
        )

    rare = var_cfg.get("rare", {})
    extreme = var_cfg.get("extreme", {})
    return {
        "variable": var_id,
        "current_rare_threshold": rare,
        "current_extreme_threshold": extreme,
        "primary_horizon": PRIMARY_HORIZON.get(var_id, "spx_3m"),
        "sweep_results": results,
        "run_date": datetime.now().strftime("%Y-%m-%d"),
    }


def _meets_criteria(row: dict[str, Any], current_excess: float | None) -> bool:
    if row.get("n", 0) < 5:
        return False
    hr = row.get("hit_rate")
    if hr is None or hr < 0.60:
        return False
    excess = row.get("excess_pct")
    if excess is None or current_excess is None:
        return False
    if excess < current_excess + 2.0:
        return False
    hostile = row.get("hostile") or {}
    h_excess = hostile.get("excess_pct")
    if h_excess is not None and current_excess is not None:
        cur_hostile_excess = row.get("current_hostile_excess")
        if cur_hostile_excess is not None and h_excess < cur_hostile_excess - 2.0:
            return False
    return True


def build_summary(all_results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    summary_rows: list[dict[str, Any]] = []
    for var_id, payload in sorted(all_results.items()):
        ph = payload.get("primary_horizon", "spx_3m")
        current_band = None
        best_band = None
        best_excess = None
        current_excess = None
        current_hostile_excess = None

        for band in payload.get("sweep_results", []):
            h = (band.get("horizons") or {}).get(ph) or {}
            excess = h.get("excess_pct")
            if band.get("is_current"):
                label = band.get("band_label") or ""
                if "CURRENT_RARE" in label or "CURRENT" in label and current_band is None:
                    current_band = band
                    current_excess = excess
                    current_hostile_excess = (h.get("hostile") or {}).get("excess_pct")
                elif current_band is None:
                    current_band = band
                    current_excess = excess
                    current_hostile_excess = (h.get("hostile") or {}).get("excess_pct")
            if excess is None or band.get("n", 0) < 5:
                continue
            if best_excess is None or excess > best_excess:
                best_excess = excess
                best_band = band

        justified = None
        if current_band and best_band and best_band != current_band:
            h = (best_band.get("horizons") or {}).get(ph) or {}
            h["current_hostile_excess"] = current_hostile_excess
            justified = _meets_criteria(h, current_excess)

        cur_h = (current_band or {}).get("horizons", {}).get(ph, {}) if current_band else {}
        best_h = (best_band or {}).get("horizons", {}).get(ph, {}) if best_band else {}

        summary_rows.append(
            {
                "variable": var_id,
                "primary_horizon": ph,
                "current_band": (current_band or {}).get("band_label"),
                "current_n": cur_h.get("n"),
                "current_hit_rate": cur_h.get("hit_rate"),
                "current_pw_excess": current_excess,
                "current_hostile_excess": current_hostile_excess,
                "best_band": (best_band or {}).get("band_label"),
                "best_n": best_h.get("n"),
                "best_hit_rate": best_h.get("hit_rate"),
                "best_pw_excess": best_excess,
                "excess_delta_pp": (best_excess - current_excess) if best_excess is not None and current_excess is not None else None,
                "change_justified": justified,
                "confirmed": justified is False or justified is None,
            }
        )

    return {
        "run_date": datetime.now().strftime("%Y-%m-%d"),
        "success_criteria": {
            "pw_excess_delta_pp": 2.0,
            "min_n": 5,
            "min_hit_rate": 0.60,
            "hostile_excess_drop_pp": 2.0,
        },
        "variables": summary_rows,
    }


def run_full_sweep(start: str = "1990-01-01", out_dir: Path | None = None) -> dict[str, Any]:
    init_db()
    cfg = load_config()
    out_dir = out_dir or ROOT / "macro_intelligence/analysis/regime_v2_experiments/threshold_sweep_v2"
    out_dir.mkdir(parents=True, exist_ok=True)

    spx = fetch_yahoo_close("^GSPC", start)
    sessions = _nyse_sessions()
    regime_map = load_regime_map()

    all_results: dict[str, dict[str, Any]] = {}
    for var_id in VAR_BAND_BUILDERS:
        print(f"sweeping {var_id}...", flush=True)
        result = sweep_variable(
            var_id, spx=spx, sessions=sessions, regime_map=regime_map, start=start, cfg=cfg
        )
        all_results[var_id] = result
        out_path = out_dir / f"{var_id}_sweep.json"
        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"  wrote {out_path}", flush=True)

    summary = build_summary(all_results)
    summary_path = out_dir / "SUMMARY.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"wrote {summary_path}", flush=True)
    return {"out_dir": str(out_dir), "n_variables": len(all_results)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="1990-01-01")
    parser.add_argument(
        "--out-dir",
        default="macro_intelligence/analysis/regime_v2_experiments/threshold_sweep_v2",
    )
    args = parser.parse_args()
    result = run_full_sweep(args.start, out_dir=ROOT / args.out_dir)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
