"""Sweep named combo thresholds vs forward returns in runic.db."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.macro_intelligence.analysis.regime_experiments.metrics import (
    probability_weighted_summary,
)
from src.macro_intelligence.config import load_config
from src.macro_intelligence.data.yahoo_pull import fetch_yahoo_close, spx_with_50wma
from src.macro_intelligence.db.connection import get_connection
from src.macro_intelligence.engine.combo_detector import _hy_oas_bps
from src.macro_intelligence.engine.forward_returns import _nyse_sessions, forward_return_pct


def _norm_pctile(p: float | None) -> float | None:
    if p is None:
        return None
    val = float(p)
    if 0 < val <= 1.0:
        return val * 100.0
    return val


def load_readings_panel(start: str = "1990-01-01") -> dict[str, list[dict[str, Any]]]:
    """All daily_readings rows keyed by var_id."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT date, var_id, raw_value, unconditional_pctile, meta_json
            FROM daily_readings
            WHERE date >= ?
            ORDER BY date, var_id
            """,
            (start,),
        ).fetchall()
    panel: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        panel.setdefault(r["var_id"], []).append(
            {
                "date": r["date"],
                "raw": float(r["raw_value"]) if r["raw_value"] is not None else None,
                "pctile": _norm_pctile(r["unconditional_pctile"]),
            }
        )
    return panel


def _reading_on(panel: dict[str, list[dict[str, Any]]], var_id: str, date: str) -> dict[str, Any] | None:
    rows = panel.get(var_id) or []
    for r in rows:
        if r["date"] == date:
            return r
    return None


def _aligned_dates(panel: dict[str, list[dict[str, Any]]], var_ids: list[str]) -> list[str]:
    sets = []
    for vid in var_ids:
        sets.append({r["date"] for r in panel.get(vid, [])})
    if not sets:
        return []
    common = set.intersection(*sets)
    return sorted(common)


def _first_combo_crossings(
    dates: list[str],
    check_fn,
    *,
    cooldown_days: int = 5,
) -> list[str]:
    events: list[str] = []
    prev_in = False
    cooldown_until: pd.Timestamp | None = None
    for ds in dates:
        dt = pd.Timestamp(ds)
        in_band = check_fn(ds)
        if cooldown_until is not None and dt <= cooldown_until:
            prev_in = in_band
            continue
        if in_band and not prev_in:
            events.append(ds)
            cooldown_until = dt + pd.Timedelta(days=cooldown_days)
        prev_in = in_band
    return events


def _pw_at_horizon(
    dates: list[str],
    spx: pd.Series,
    sessions: pd.DatetimeIndex,
    *,
    horizon_key: str,
    trading_days: int,
    benchmark: float,
    bullish: bool,
) -> dict[str, Any]:
    rets = [
        forward_return_pct(spx, pd.Timestamp(ds), trading_days, sessions=sessions)
        for ds in dates
    ]
    return probability_weighted_summary(
        [r for r in rets if r is not None],
        bullish=bullish,
        benchmark_pct=benchmark,
        horizon=horizon_key,
    )


def sweep_combo_b_gates(
    panel: dict[str, list[dict[str, Any]]] | None = None,
    spx: pd.Series | None = None,
    sessions: pd.DatetimeIndex | None = None,
) -> dict[str, Any]:
    """Combo B leg replay with gate sweeps at 3M validated horizon."""
    panel = panel or load_readings_panel("1996-01-01")
    if spx is None:
        spx = fetch_yahoo_close("^GSPC", "1990-01-01")
    if sessions is None:
        sessions = _nyse_sessions()
    dates = _aligned_dates(panel, ["VIX", "HY", "CFTC"])

    def combo_b_pass(
        ds: str,
        *,
        vix_min: float = 25,
        hy_bps_min: float = 400,
        cftc_max: float = 15,
        legs_required: int = 3,
    ) -> bool:
        vix = _reading_on(panel, "VIX", ds)
        hy = _reading_on(panel, "HY", ds)
        cftc = _reading_on(panel, "CFTC", ds)
        if not vix or not hy or not cftc:
            return False
        vix_ok = (vix["raw"] or 0) >= vix_min and (vix["pctile"] or 0) >= 80
        hy_ok = _hy_oas_bps(hy["raw"]) >= hy_bps_min or (hy["pctile"] or 0) >= 80
        cftc_ok = (cftc["pctile"] or 100) <= cftc_max
        return sum([vix_ok, hy_ok, cftc_ok]) >= legs_required

    tests: list[dict[str, Any]] = []
    for vix_min in [20, 25, 30]:
        label = f"CB_VIX_{int(vix_min)}"
        ev = _first_combo_crossings(dates, lambda ds, v=vix_min: combo_b_pass(ds, vix_min=v))
        tests.append(
            {
                "test_id": label,
                "param": "vix_min",
                "value": vix_min,
                "hy_bps_min": 400,
                "cftc_max_pctile": 15,
                "legs_required": 3,
                "n": len(ev),
                "pw_3m": _pw_at_horizon(ev, spx, sessions, horizon_key="spx_3m", trading_days=63, benchmark=2.5, bullish=True),
            }
        )
    for hy_bps in [350, 400, 450]:
        label = f"CB_HY_{int(hy_bps)}"
        ev = _first_combo_crossings(dates, lambda ds, h=hy_bps: combo_b_pass(ds, hy_bps_min=h))
        tests.append(
            {
                "test_id": label,
                "param": "hy_bps_min",
                "value": hy_bps,
                "vix_min": 25,
                "cftc_max_pctile": 15,
                "legs_required": 3,
                "n": len(ev),
                "pw_3m": _pw_at_horizon(ev, spx, sessions, horizon_key="spx_3m", trading_days=63, benchmark=2.5, bullish=True),
            }
        )
    for cftc_max in [10, 15, 20]:
        label = f"CB_CFTC_{int(cftc_max)}"
        ev = _first_combo_crossings(dates, lambda ds, c=cftc_max: combo_b_pass(ds, cftc_max=c))
        tests.append(
            {
                "test_id": label,
                "param": "cftc_max_pctile",
                "value": cftc_max,
                "vix_min": 25,
                "hy_bps_min": 400,
                "legs_required": 3,
                "n": len(ev),
                "pw_3m": _pw_at_horizon(ev, spx, sessions, horizon_key="spx_3m", trading_days=63, benchmark=2.5, bullish=True),
            }
        )
    ev_2of3 = _first_combo_crossings(dates, lambda ds: combo_b_pass(ds, legs_required=2))
    tests.append(
        {
            "test_id": "CB_2of3_legs",
            "param": "legs_required",
            "value": 2,
            "vix_min": 25,
            "hy_bps_min": 400,
            "cftc_max_pctile": 15,
            "legs_required": 2,
            "n": len(ev_2of3),
            "pw_3m": _pw_at_horizon(ev_2of3, spx, sessions, horizon_key="spx_3m", trading_days=63, benchmark=2.5, bullish=True),
        }
    )
    current = next((t for t in tests if t["test_id"] == "CB_VIX_25" and t["param"] == "vix_min"), None)
    return {
        "combo": "B",
        "validated_horizon": "spx_3m",
        "direction": "bullish",
        "current_gates": load_config().get("named_combos", {}).get("B", {}),
        "note": "Leg replay on daily_readings; HY leg uses CONFIG OR (OAS≥threshold OR pctile≥80); VIX uses AND (level+pctile)",
        "tests": tests,
        "current_baseline": current,
        "run_date": datetime.now().strftime("%Y-%m-%d"),
    }


def sweep_combo_f_spx_threshold(
    spx: pd.Series | None = None,
    sessions: pd.DatetimeIndex | None = None,
    panel: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Combo F SPX threshold sweep at 6M horizon."""
    if spx is None:
        spx = fetch_yahoo_close("^GSPC", "1990-01-01")
    if sessions is None:
        sessions = _nyse_sessions()
    panel = panel or load_readings_panel("2010-01-01")
    spx_w = spx_with_50wma()
    cftc_dates = {r["date"] for r in panel.get("CFTC", [])}

    tests: list[dict[str, Any]] = []
    for pct_thresh in [1.0, 2.0, 3.0, 5.0]:
        events: list[str] = []
        prev_in = False
        cooldown_until: pd.Timestamp | None = None
        hist = spx_w.sort_index()
        for i in range(1, len(hist)):
            row = hist.iloc[i]
            prev = hist.iloc[i - 1]
            dt = row.name
            ds = dt.strftime("%Y-%m-%d")
            if ds not in cftc_dates:
                prev_in = False
                continue
            cftc = _reading_on(panel, "CFTC", ds)
            if not cftc:
                prev_in = False
                continue
            above = bool(row["above_50wma"])
            pct_above = (float(row["close"]) / float(row["wma50"]) - 1.0) * 100.0
            reclaim = above and not bool(prev["above_50wma"])
            cftc_ok = (cftc["pctile"] or 50) <= 50
            in_band = above and cftc_ok and (reclaim or pct_above >= pct_thresh)
            if cooldown_until is not None and dt <= cooldown_until:
                prev_in = in_band
                continue
            if in_band and not prev_in:
                events.append(ds)
                cooldown_until = dt + pd.Timedelta(days=5)
            prev_in = in_band

        tests.append(
            {
                "test_id": f"CF_SPX_{int(pct_thresh)}pct",
                "param": "spx_50wma_reclaim_weekly_pct",
                "value": pct_thresh,
                "cftc_max_pctile": 50,
                "n": len(events),
                "pw_6m": _pw_at_horizon(
                    events, spx, sessions, horizon_key="spx_6m", trading_days=126, benchmark=5.0, bullish=True
                ),
            }
        )

    return {
        "combo": "F",
        "validated_horizon": "spx_6m",
        "direction": "bullish",
        "current_gates": load_config().get("named_combos", {}).get("F", {}),
        "tests": tests,
        "run_date": datetime.now().strftime("%Y-%m-%d"),
    }


def sweep_combo_e_gates(
    panel: dict[str, list[dict[str, Any]]] | None = None,
    spx: pd.Series | None = None,
    sessions: pd.DatetimeIndex | None = None,
) -> dict[str, Any]:
    """Combo E gate sweep at 12M horizon."""
    panel = panel or load_readings_panel("1990-01-01")
    if spx is None:
        spx = fetch_yahoo_close("^GSPC", "1990-01-01")
    if sessions is None:
        sessions = _nyse_sessions()
    dates = _aligned_dates(panel, ["CAPE", "NFCI", "CFTC"])

    def combo_e_pass(
        ds: str,
        *,
        cape_min: float = 28,
        nfci_easy_max: float = -0.3,
        cftc_min: float = 80,
        min_legs: int = 2,
    ) -> bool:
        cape = _reading_on(panel, "CAPE", ds)
        nfci = _reading_on(panel, "NFCI", ds)
        cftc = _reading_on(panel, "CFTC", ds)
        if not cape or not nfci or not cftc:
            return False
        hits = 0
        if (cape["raw"] or 0) >= cape_min:
            hits += 1
        if (nfci["raw"] or 0) <= nfci_easy_max:
            hits += 1
        if (cftc["pctile"] or 0) >= cftc_min:
            hits += 1
        return hits >= min_legs

    tests: list[dict[str, Any]] = []
    for cape_min in [25, 28, 30, 32]:
        ev = _first_combo_crossings(dates, lambda ds, c=cape_min: combo_e_pass(ds, cape_min=c))
        tests.append(
            {
                "test_id": f"CE_CAPE_{int(cape_min)}",
                "param": "cape_min",
                "value": cape_min,
                "nfci_easy_max": -0.3,
                "cftc_min_pctile": 80,
                "n": len(ev),
                "pw_12m": _pw_at_horizon(
                    ev, spx, sessions, horizon_key="spx_12m", trading_days=252, benchmark=10.0, bullish=False
                ),
            }
        )
    for nfci_max in [-0.2, -0.3, -0.4]:
        ev = _first_combo_crossings(dates, lambda ds, n=nfci_max: combo_e_pass(ds, nfci_easy_max=n))
        tests.append(
            {
                "test_id": f"CE_NFCI_{nfci_max}",
                "param": "nfci_easy_max",
                "value": nfci_max,
                "cape_min": 28,
                "cftc_min_pctile": 80,
                "n": len(ev),
                "pw_12m": _pw_at_horizon(
                    ev, spx, sessions, horizon_key="spx_12m", trading_days=252, benchmark=10.0, bullish=False
                ),
            }
        )
    for cftc_min in [75, 80, 85]:
        ev = _first_combo_crossings(dates, lambda ds, c=cftc_min: combo_e_pass(ds, cftc_min=c))
        tests.append(
            {
                "test_id": f"CE_CFTC_{int(cftc_min)}",
                "param": "cftc_min_pctile",
                "value": cftc_min,
                "cape_min": 28,
                "nfci_easy_max": -0.3,
                "n": len(ev),
                "pw_12m": _pw_at_horizon(
                    ev, spx, sessions, horizon_key="spx_12m", trading_days=252, benchmark=10.0, bullish=False
                ),
            }
        )

    return {
        "combo": "E",
        "validated_horizon": "spx_12m",
        "direction": "bearish",
        "current_gates": load_config().get("named_combos", {}).get("E", {}),
        "tests": tests,
        "run_date": datetime.now().strftime("%Y-%m-%d"),
    }


def sweep_combo_d_gates(
    panel: dict[str, list[dict[str, Any]]] | None = None,
    spx: pd.Series | None = None,
    sessions: pd.DatetimeIndex | None = None,
) -> dict[str, Any]:
    """Combo D gate sweep at 5D validated horizon."""
    panel = panel or load_readings_panel("2007-01-01")
    if spx is None:
        spx = fetch_yahoo_close("^GSPC", "1990-01-01")
    if sessions is None:
        sessions = _nyse_sessions()
    dates = _aligned_dates(panel, ["VXTS", "CFTC", "VIX"])

    def combo_d_pass(
        ds: str,
        *,
        vxts_min: float = 1.10,
        cftc_min: float = 85,
        vix_max: float = 18,
        legs_required: int = 3,
    ) -> bool:
        vxts = _reading_on(panel, "VXTS", ds)
        cftc = _reading_on(panel, "CFTC", ds)
        vix = _reading_on(panel, "VIX", ds)
        if not vxts or not cftc or not vix:
            return False
        vxts_ok = (vxts["raw"] or 0) >= vxts_min
        cftc_ok = (cftc["pctile"] or 0) >= cftc_min
        vix_ok = (vix["raw"] or 99) <= vix_max
        return sum([vxts_ok, cftc_ok, vix_ok]) >= legs_required

    tests: list[dict[str, Any]] = []
    for vxts_min in [1.05, 1.10, 1.15]:
        ev = _first_combo_crossings(dates, lambda ds, v=vxts_min: combo_d_pass(ds, vxts_min=v))
        tests.append(
            {
                "test_id": f"CD_VXTS_{vxts_min}",
                "param": "vxts_min",
                "value": vxts_min,
                "cftc_min_pctile": 85,
                "vix_max": 18,
                "legs_required": 3,
                "n": len(ev),
                "pw_5d": _pw_at_horizon(ev, spx, sessions, horizon_key="spx_1w", trading_days=5, benchmark=0.5, bullish=False),
            }
        )
    for cftc_min in [80, 85, 90]:
        ev = _first_combo_crossings(dates, lambda ds, c=cftc_min: combo_d_pass(ds, cftc_min=c))
        tests.append(
            {
                "test_id": f"CD_CFTC_{int(cftc_min)}",
                "param": "cftc_min_pctile",
                "value": cftc_min,
                "vxts_min": 1.10,
                "vix_max": 18,
                "legs_required": 3,
                "n": len(ev),
                "pw_5d": _pw_at_horizon(ev, spx, sessions, horizon_key="spx_1w", trading_days=5, benchmark=0.5, bullish=False),
            }
        )
    for vix_max in [15, 18, 20]:
        ev = _first_combo_crossings(dates, lambda ds, v=vix_max: combo_d_pass(ds, vix_max=v))
        tests.append(
            {
                "test_id": f"CD_VIX_{int(vix_max)}",
                "param": "vix_max",
                "value": vix_max,
                "vxts_min": 1.10,
                "cftc_min_pctile": 85,
                "legs_required": 3,
                "n": len(ev),
                "pw_5d": _pw_at_horizon(ev, spx, sessions, horizon_key="spx_1w", trading_days=5, benchmark=0.5, bullish=False),
            }
        )
    ev_2of3 = _first_combo_crossings(dates, lambda ds: combo_d_pass(ds, legs_required=2))
    tests.append(
        {
            "test_id": "CD_2of3_legs",
            "param": "legs_required",
            "value": 2,
            "vxts_min": 1.10,
            "cftc_min_pctile": 85,
            "vix_max": 18,
            "legs_required": 2,
            "n": len(ev_2of3),
            "pw_5d": _pw_at_horizon(ev_2of3, spx, sessions, horizon_key="spx_1w", trading_days=5, benchmark=0.5, bullish=False),
        }
    )

    return {
        "combo": "D",
        "validated_horizon": "spx_5d",
        "direction": "bearish",
        "current_gates": load_config().get("named_combos", {}).get("D", {}),
        "tests": tests,
        "run_date": datetime.now().strftime("%Y-%m-%d"),
    }


def run_all_combo_sweeps(out_dir: Path) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    spx = fetch_yahoo_close("^GSPC", "1990-01-01")
    sessions = _nyse_sessions()
    panel = load_readings_panel("1990-01-01")

    outputs = {
        "COMBO_B_gate_sweep.json": sweep_combo_b_gates(panel=panel, spx=spx, sessions=sessions),
        "COMBO_F_spx_sweep.json": sweep_combo_f_spx_threshold(spx=spx, sessions=sessions, panel=panel),
        "COMBO_E_cape_sweep.json": sweep_combo_e_gates(panel=panel, spx=spx, sessions=sessions),
        "COMBO_D_gate_sweep.json": sweep_combo_d_gates(panel=panel, spx=spx, sessions=sessions),
    }
    written: dict[str, str] = {}
    for fname, payload in outputs.items():
        path = out_dir / fname
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        written[fname] = str(path)
    return written


# Legacy stubs kept for backward compatibility
def sweep_combo_b_vix_thresholds(
    vix_levels: list[float] | None = None,
    hy_bps: float = 400.0,
    cftc_pctile: float = 15.0,
) -> list[dict[str, Any]]:
    """Evaluate Combo B gate across VIX thresholds on historical combo_fires dates."""
    result = sweep_combo_b_gates()
    return [t for t in result["tests"] if t.get("param") == "vix_min"]


def hit_rate_for_combo(runic_combo: str, bullish: bool = True) -> dict[str, Any]:
    col = "spx_3m"
    with get_connection() as conn:
        data = conn.execute(
            f"""
            SELECT fr.{col} AS ret
            FROM combo_fires cf
            JOIN forward_returns fr ON cf.combo_id = fr.combo_id
            WHERE cf.runic_combo = ? AND fr.{col} IS NOT NULL
            """,
            (runic_combo,),
        ).fetchall()
    if not data:
        return {"combo": runic_combo, "n_obs": 0, "hit_rate": None, "avg_return": None}
    rets = [float(r["ret"]) for r in data]
    if bullish:
        hits = sum(1 for x in rets if x > 0)
    else:
        hits = sum(1 for x in rets if x < 0)
    return {
        "combo": runic_combo,
        "n_obs": len(rets),
        "hit_rate": round(hits / len(rets), 4),
        "avg_return": round(sum(rets) / len(rets), 4),
    }


def suggest_threshold_changes() -> list[dict[str, Any]]:
    """Produce suggestions for CONFIG thresholds from DB hit rates."""
    cfg = load_config()
    suggestions: list[dict[str, Any]] = []

    b_hr = hit_rate_for_combo("B", bullish=True)
    if b_hr["n_obs"] >= 3 and b_hr["hit_rate"] is not None and b_hr["hit_rate"] < 0.6:
        suggestions.append(
            {
                "combo": "B",
                "issue": "low_hit_rate",
                "current": cfg.get("named_combos", {}).get("B", {}),
                "stats": b_hr,
                "suggestion": "Consider raising vix_min or hy_bps_min after review",
            }
        )

    f_hr = hit_rate_for_combo("F", bullish=True)
    if f_hr["n_obs"] >= 3 and f_hr["hit_rate"] is not None and f_hr["hit_rate"] < 0.6:
        suggestions.append(
            {
                "combo": "F",
                "issue": "low_hit_rate",
                "current": cfg.get("named_combos", {}).get("F", {}),
                "stats": f_hr,
                "suggestion": "Review spx_50wma_reclaim_weekly_pct or cftc_max_pctile",
            }
        )

    b_sweep = sweep_combo_b_gates()
    for t in b_sweep["tests"]:
        suggestions.append(
            {
                "combo": "B",
                "param_sweep": t.get("param"),
                "value": t.get("value"),
                "n": t.get("n"),
                "pw_excess_3m": (t.get("pw_3m") or {}).get("excess_pct"),
            }
        )

    return suggestions
