"""Macro Intelligence service layer — reads runic_output.json and SQLite DB."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from src.config_paths import MACRO_INTEL_JSON_PATH
from src.macro_intelligence.engine.vix_bypass import VIX_BYPASS_BANNER, combo_b_is_active

# ─────────────────────────────────────────────────────────────────────────────
# JSON helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_runic() -> dict[str, Any]:
    if not MACRO_INTEL_JSON_PATH.exists():
        raise FileNotFoundError(f"Runic output not found: {MACRO_INTEL_JSON_PATH}")
    return json.loads(MACRO_INTEL_JSON_PATH.read_text(encoding="utf-8"))


def _safe(d: dict[str, Any], key: str, default: Any = None) -> Any:
    return d.get(key, default)


def _effective_vix_bypass(data: dict[str, Any]) -> bool:
    """Runtime guard: vix_bypass only when Combo B is ACTIVE (A6)."""
    if not _safe(data, "vix_bypass", False):
        return False
    active = _safe(data, "active_combos", [])
    return combo_b_is_active(active)


def _watch_combo_map(watch_list: list[Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for w in watch_list:
        if isinstance(w, dict) and w.get("combo"):
            out[w["combo"]] = w
        elif isinstance(w, str):
            out[w] = {"combo": w}
    return out


def _combo_confirmed_legs(
    letter: str,
    active_map: dict[str, dict[str, Any]],
    watch_map: dict[str, dict[str, Any]],
    status_row: dict[str, Any] | None,
) -> list[str]:
    live = active_map.get(letter, {})
    legs = live.get("confirmed_legs")
    if legs:
        return list(legs)
    watch = watch_map.get(letter, {})
    if watch.get("confirmed_legs"):
        return list(watch["confirmed_legs"])
    if status_row and status_row.get("confirmed_legs"):
        return list(status_row["confirmed_legs"])
    return []


# ─────────────────────────────────────────────────────────────────────────────
# DB helpers
# ─────────────────────────────────────────────────────────────────────────────

def _db_combo_c_cancel() -> dict[str, Any]:
    try:
        from src.macro_intelligence.db.connection import get_connection
        with get_connection() as conn:
            row = conn.execute(
                """SELECT wti_potential_week, active, last_check_date, cancel_date,
                          cpi_leg_passed
                   FROM combo_c_cancel WHERE id=1"""
            ).fetchone()
        if not row:
            return {"wti_potential_week": 0, "active": False, "cancel_date": None, "cpi_leg_passed": None}
        return {
            "wti_potential_week": row["wti_potential_week"],
            "active": bool(row["active"]),
            "last_check_date": row["last_check_date"],
            "cancel_date": row["cancel_date"],
            "cancelled": bool(row["cancel_date"]),
            "cpi_leg_passed": bool(row["cpi_leg_passed"]) if row["cpi_leg_passed"] is not None else None,
        }
    except Exception:
        return {"wti_potential_week": 0, "active": False, "cancel_date": None}


def _db_friday_cancel_log() -> list[dict[str, Any]]:
    """Return the last 8 Friday cancel check rows."""
    try:
        from src.macro_intelligence.db.connection import get_connection
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT date, wti_4wk_pct, wti_leg_ok, cpi_leg_ok, week_counter, status
                   FROM combo_c_cancel_log
                   ORDER BY date DESC LIMIT 8"""
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def _db_latest_cpi_print() -> dict[str, Any] | None:
    try:
        from src.macro_intelligence.db.connection import get_connection
        with get_connection() as conn:
            row = conn.execute(
                """SELECT release_date, actual, consensus, surprise_pp
                   FROM pending_releases
                   WHERE release_type='CPI' AND actual IS NOT NULL
                   ORDER BY release_date DESC LIMIT 1"""
            ).fetchone()
        if not row:
            return None
        return {
            "release_date": row["release_date"],
            "actual": float(row["actual"]),
            "consensus": float(row["consensus"]),
            "surprise_pp": row["surprise_pp"],
            "not_hot": float(row["actual"]) <= float(row["consensus"]),
        }
    except Exception:
        return None


def _db_upcoming_releases(days: int = 14) -> list[dict[str, Any]]:
    try:
        from src.macro_intelligence.db.connection import get_connection
        today = datetime.now().strftime("%Y-%m-%d")
        future = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT release_date, release_type, actual, consensus
                   FROM pending_releases
                   WHERE release_date > ? AND release_date <= ?
                     AND (actual IS NULL OR consensus IS NULL)
                   ORDER BY release_date ASC""",
                (today, future),
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def _db_analog_details(combo_id: str, limit: int = 6) -> list[dict[str, Any]]:
    try:
        from src.macro_intelligence.db.connection import get_connection
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT cf.date, cf.status, cf.runic_combo,
                          fr.spx_1m, fr.spx_3m, fr.spx_6m, fr.spx_9m, fr.spx_12m,
                          cf.macro_regime_json
                   FROM combo_fires cf
                   LEFT JOIN forward_returns fr ON cf.combo_id = fr.combo_id
                   WHERE cf.runic_combo = ?
                   ORDER BY cf.date DESC LIMIT ?""",
                (combo_id.upper(), limit),
            ).fetchall()
        results = []
        for r in rows:
            regime = {}
            if r["macro_regime_json"]:
                try:
                    regime = json.loads(r["macro_regime_json"])
                except Exception:
                    pass
            results.append({
                "date": r["date"],
                "status": r["status"],
                "combo": r["runic_combo"],
                "spx_1m_pct": round(float(r["spx_1m"]), 2) if r["spx_1m"] is not None else None,
                "spx_3m_pct": round(float(r["spx_3m"]), 2) if r["spx_3m"] is not None else None,
                "spx_6m_pct": round(float(r["spx_6m"]), 2) if r["spx_6m"] is not None else None,
                "spx_9m_pct": round(float(r["spx_9m"]), 2) if r["spx_9m"] is not None else None,
                "spx_12m_pct": round(float(r["spx_12m"]), 2) if r["spx_12m"] is not None else None,
                "regime": regime,
            })
        return results
    except Exception:
        return []


def _db_combo_fire_detail(combo_id: str) -> dict[str, Any] | None:
    """Latest active/watch fire for a given named combo."""
    try:
        from src.macro_intelligence.db.connection import get_connection
        with get_connection() as conn:
            row = conn.execute(
                """SELECT cf.combo_id, cf.date, cf.status, cf.duration_weeks,
                          cf.duration_bucket, cf.var_ids_json, cf.macro_regime_json,
                          cf.confirmed_legs_json
                   FROM combo_fires cf
                   WHERE cf.runic_combo = ?
                   ORDER BY cf.date DESC LIMIT 1""",
                (combo_id.upper(),),
            ).fetchone()
        if not row:
            return None
        meta = {}
        if row["macro_regime_json"]:
            try:
                meta = json.loads(row["macro_regime_json"])
            except Exception:
                pass
        legs = []
        if row["confirmed_legs_json"]:
            try:
                legs = json.loads(row["confirmed_legs_json"])
            except Exception:
                pass
        var_ids = []
        if row["var_ids_json"]:
            try:
                var_ids = json.loads(row["var_ids_json"])
            except Exception:
                pass
        return {
            "combo_id": row["combo_id"],
            "date": row["date"],
            "status": row["status"],
            "duration_weeks": row["duration_weeks"],
            "duration_bucket": row["duration_bucket"],
            "var_ids": var_ids,
            "confirmed_legs": legs,
            "episode_start": meta.get("episode_start"),
        }
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Public API service functions
# ─────────────────────────────────────────────────────────────────────────────

_COMBO_STATIC: dict[str, dict[str, Any]] = {
    "A": {
        "name": "Global Liquidity / FCI Regime",
        "direction": "BRAVE OR FEARFUL",
        "horizon": "3–6m",
        "legs_required": 2,
        "total_legs": 4,
        "variables": ["NFCI", "HY", "WALCL", "CNH"],
        "description": (
            "NFCI + HY direction + WALCL + CNH · ≥2 of 4 required simultaneously. "
            "BRAVE +12% avg / FEARFUL −8% avg SPX 3–6m."
        ),
    },
    "B": {
        "name": "Maximum Capitulation / Blood in Streets",
        "direction": "BULLISH CONTRARIAN",
        "horizon": "3m",
        "legs_required": 3,
        "total_legs": 3,
        "variables": ["VIX", "HY", "CFTC"],
        "description": (
            "VIX >25 AND >80th pctile AND HY >400bps AND CFTC <15th pctile. "
            "All 3 required. 87.5% hit rate. +14% avg SPX 3m."
        ),
    },
    "C": {
        "name": "Stagflation / Energy Shock",
        "direction": "BEARISH",
        "horizon": "1–6m",
        "legs_required": 3,
        "total_legs": 3,
        "variables": ["WTI", "CPI", "WALCL"],
        "description": (
            "WTI >+10% rolling 28-day AND CPI not hot AND WALCL flat. "
            "83% bearish 1–6m. ~4–5 instances since 2005."
        ),
    },
    "D": {
        "name": "FOMO Top / Euphoria Tactical",
        "direction": "BEARISH TACTICAL",
        "horizon": "1W primary (also 2W)",
        "legs_required": 2,
        "total_legs": 3,
        "variables": ["VXTS", "CFTC", "VIX"],
        "description": (
            "VXTS≥1.18 AND CFTC≥95th pctile AND VIX≤13. "
            "2 of 3 required. ~56.5% bear @1W (n=46 production score)."
        ),
    },
    "E": {
        "name": "Valuation Extreme / Slow Burn Top",
        "direction": "BEARISH STRUCTURAL",
        "horizon": "6–18m",
        "legs_required": 3,
        "total_legs": 3,
        "variables": ["CAPE", "NFCI", "CFTC"],
        "description": (
            "CAPE≥32 AND NFCI≤−0.15 AND CFTC≥85th pctile. "
            "3 of 3 required. CFTC escalation alert when FM pctile rises ≥5 pts over ~4 weeks. "
            "Structural slow-burn bear (12m primary)."
        ),
    },
    "F": {
        "name": "Recovery / Re-entry Signal",
        "direction": "BULLISH",
        "horizon": "3–6m (26-week window)",
        "legs_required": 3,
        "total_legs": 3,
        "variables": ["SPX50WMA", "CFTC", "PRIOR_BREAK"],
        "description": (
            "SPX reclaims 50-Week MA with ≥+3% weekly WHILE CFTC ≤50th pctile. "
            "Requires prior sustained break. 78% hit rate. +9.5% avg SPX 6m."
        ),
    },
    "G": {
        "name": "Hidden Stress / Credit-Vol Divergence",
        "direction": "WARNING LEADING",
        "horizon": "3–6 week lead",
        "legs_required": 3,
        "total_legs": 3,
        "variables": ["VXTS", "HY", "VIX"],
        "description": (
            "VXTS <1.0 (backwardation) AND HY widening >+30bps in 4wks WHILE VIX <20. "
            "Leads vol spike 3–6 weeks. ~75% hit rate. Watch for G→B cascade."
        ),
    },
}

_VARIABLE_META: dict[str, dict[str, Any]] = {
    "NFCI":  {"source": "FRED: NFCI", "compute": "Weekly level, 3yr pctile rank", "rare_gate": ">+0.3 (tight) or <−0.3 (easy)", "extreme_gate": ">+0.8 or <−0.6", "combos": ["A", "E"]},
    "HY":    {"source": "FRED: BAMLH0A0HYM2", "compute": "Daily OAS bps, 3yr pctile rank", "rare_gate": ">400bps OR >+1.0 SD 3yr", "extreme_gate": ">500bps OR >+2.0 SD", "combos": ["A", "B", "F", "G"]},
    "WALCL": {"source": "FRED: WALCL", "compute": "MoM % change, flat=±0.8%", "rare_gate": "±0.8% MoM", "extreme_gate": "±2.0% MoM", "combos": ["A", "C"]},
    "CNH":   {"source": "Yahoo Finance: USDCNH=X", "compute": "4-week % change", "rare_gate": "±1.5% in 4wks", "extreme_gate": "±3.5% in 4wks", "combos": ["A", "C", "G"]},
    "WTI":   {"source": "Yahoo Finance: CL=F", "compute": "(today − 28cd ago) ÷ 28cd ago daily", "rare_gate": "±6% in 4wks (fire: >+10%)", "extreme_gate": "±10% in 4wks", "combos": ["C"]},
    "VIX":   {"source": "Yahoo Finance: ^VIX", "compute": "Daily close, 3yr pctile rank", "rare_gate": ">25 AND >80th pctile 3yr", "extreme_gate": ">35 AND >95th pctile", "combos": ["B", "D", "G"]},
    "VXTS":  {"source": "Yahoo: ^VIX3M ÷ ^VIX", "compute": "Ratio daily, no pctile needed", "rare_gate": "<0.95 (backw.) or >1.10 (contango)", "extreme_gate": "<0.85 or >1.20", "combos": ["D", "G"]},
    "CFTC":  {"source": "CFTC.gov TFF report", "compute": "Lev_Money + Asset_Mgr, 3yr pctile", "rare_gate": "<15th or >85th pctile", "extreme_gate": "<5th or >95th pctile", "combos": ["B", "D", "E", "F"]},
    "CURVE": {"source": "FRED: T10Y2Y", "compute": "Spread bps + 4wk change rate", "rare_gate": "<−30bps OR steep >15bps/4wk", "extreme_gate": "<−80bps OR steep >40bps/4wk", "combos": ["A", "E"]},
    "CPI":   {"source": "BLS.gov / FRED (actual), Investing.com (consensus)", "compute": "Actual minus consensus pp", "rare_gate": "±0.2pp single", "extreme_gate": "±0.4pp OR 2× consec hot", "combos": ["C"]},
    "GSR":   {"source": "Yahoo: GC=F ÷ SI=F", "compute": "4-week % change of ratio", "rare_gate": "4wk Δ >±5%", "extreme_gate": "4wk Δ >±8%", "combos": ["A+"]},
    "CAPE":  {"source": "multpl.com scrape / FRED CAPE", "compute": "Absolute level, monthly", "rare_gate": ">28× or <16×", "extreme_gate": ">32× or <12×", "combos": ["E"]},
}


def get_status_bar() -> dict[str, Any]:
    """Header status strip — dominant signal, brave/fearful, active/watch, CFTC."""
    data = _load_runic()
    active = _safe(data, "active_combos", [])
    watch = _safe(data, "watch_combos", [])
    c_cancel = _safe(data, "combo_c_cancel", {})
    return {
        "date": _safe(data, "date"),
        "dominant_signal": _safe(data, "dominant_signal"),
        "brave_fearful": _safe(data, "brave_fearful"),
        "brave_fearful_display": _safe(data, "brave_fearful_display"),
        "active_combos": [c.get("combo") for c in active if c.get("combo")],
        "watch_combos": watch if isinstance(watch, list) else list(watch),
        "cftc_status": _safe(data, "cftc_status"),
        "vix_bypass": _effective_vix_bypass(data),
        "vix_bypass_banner": VIX_BYPASS_BANNER if _effective_vix_bypass(data) else None,
        "combo_c_cancel_week": c_cancel.get("wti_potential_week", 0),
        "combo_c_cancelled": bool(c_cancel.get("cancelled")),
        "pending_cpi_release": _safe(data, "pending_cpi_release", False),
    }


def get_overview_kpis() -> dict[str, Any]:
    """Five KPI cards for the overview tab."""
    data = _load_runic()
    active = _safe(data, "active_combos", [])
    variables = _safe(data, "variables_dashboard", [])
    var_map = {v["variable"]: v for v in variables if isinstance(v, dict)}

    dominant = _safe(data, "dominant_signal")
    dom_combo = next((c for c in active if c.get("combo") == dominant), {})

    cape_var = var_map.get("CAPE", {})
    wti_var = var_map.get("WTI", {})

    f_combo = next((c for c in active if c.get("combo") == "F"), None)

    return {
        "date": _safe(data, "date"),
        "dominant_signal": {
            "combo": dominant,
            "brave_fearful_display": _safe(data, "brave_fearful_display"),
            "hit_rate": dom_combo.get("hit_rate_3m"),
            "avg_return": dom_combo.get("avg_return_3m"),
        },
        "combo_c_duration": {
            "combo": "C",
            "duration_weeks": dom_combo.get("duration_weeks") if dominant == "C" else next(
                (c.get("duration_weeks") for c in active if c.get("combo") == "C"), None
            ),
            "duration_bucket": dom_combo.get("duration_bucket") if dominant == "C" else next(
                (c.get("duration_bucket") for c in active if c.get("combo") == "C"), None
            ),
            "active": any(c.get("combo") == "C" for c in active),
        },
        "combo_f_window": {
            "combo": "F",
            "weeks_elapsed": _safe(data, "combo_f_weeks_elapsed"),
            "active": _safe(data, "combo_f_active", False),
            "mtm_pct": f_combo.get("mtm_pct") if f_combo else None,
        },
        "cape": {
            "variable": "CAPE",
            "current": cape_var.get("current"),
            "tier": cape_var.get("tier"),
            "combo_e_status": next(
                (c.get("status") for c in active if c.get("combo") == "E"),
                "INACTIVE",
            ),
        },
        "wti_4wk": {
            "variable": "WTI",
            "current": wti_var.get("current"),
            "tier": wti_var.get("tier"),
            "cancel_week": _safe(data, "combo_c_cancel", {}).get("wti_potential_week", 0),
        },
    }


def get_regime() -> dict[str, Any]:
    """Regime classification — 5 dimensions, brave/fearful posture, narrative."""
    data = _load_runic()
    return {
        "date": _safe(data, "date"),
        "regime": _safe(data, "regime", {}),
        "brave_fearful": _safe(data, "brave_fearful"),
        "brave_fearful_display": _safe(data, "brave_fearful_display"),
        "dominant_signal": _safe(data, "dominant_signal"),
        "dominant_reason": _safe(data, "dominant_reason"),
        "narrative": _safe(data, "narrative"),
        "system_recommendation": _safe(data, "system_recommendation"),
        "vix_bypass": _effective_vix_bypass(data),
        "vix_bypass_banner": VIX_BYPASS_BANNER if _effective_vix_bypass(data) else None,
        "ssi_layer2_status": _safe(data, "ssi_layer2_status"),
        "ssi_multiplier": _safe(data, "ssi_multiplier"),
        "regime_grid": _safe(data, "regime_grid"),
    }


def get_pre_catalyst_intel() -> dict[str, Any]:
    """Pre-catalyst fragility score before scheduled CPI/FOMC/NFP (nightly JSON)."""
    data = _load_runic()
    block = _safe(data, "pre_catalyst", {}) or {}
    return {"date": _safe(data, "date"), **block}


def get_post_event_regime_intel() -> dict[str, Any]:
    """Post-event regime transition within 48h of CPI/FOMC/NFP (nightly JSON)."""
    data = _load_runic()
    block = _safe(data, "post_event_regime", {}) or {}
    return {"date": _safe(data, "date"), **block}


def get_scheduled_events_calendar(*, days: int = 21) -> dict[str, Any]:
    """Upcoming CPI, FOMC, and NFP release dates from pending_releases."""
    from src.macro_intelligence.data.macro_calendar import list_scheduled_events

    days = max(1, min(int(days), 90))
    today = datetime.now().strftime("%Y-%m-%d")
    end = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    events = list_scheduled_events(today, start=today, end=end)
    return {
        "as_of": today,
        "days_forward": days,
        "event_types": ["CPI", "FOMC", "NFP"],
        "events": events,
    }


def get_variables_heatmap() -> dict[str, Any]:
    """12-variable heatmap — tiers, current values, thresholds, combo links."""
    data = _load_runic()
    variables = _safe(data, "variables_dashboard", [])
    enriched = []
    for v in variables:
        vid = v.get("variable", "")
        meta = _VARIABLE_META.get(vid, {})
        enriched.append({
            **v,
            "source": meta.get("source"),
            "compute": meta.get("compute"),
            "rare_gate": meta.get("rare_gate"),
            "extreme_gate": meta.get("extreme_gate"),
            "combos": meta.get("combos", []),
        })
    return {
        "date": _safe(data, "date"),
        "variables": enriched,
        "pending_variables": [v["variable"] for v in enriched if v.get("tier") in ("PENDING", None) and v.get("variable")],
    }


def get_all_combos() -> dict[str, Any]:
    """All 7 named combos A–G with status, legs, hit rates from latest nightly JSON."""
    data = _load_runic()
    active = _safe(data, "active_combos", [])
    watch_list = _safe(data, "watch_combos", [])
    watch_map = _watch_combo_map(watch_list if isinstance(watch_list, list) else [])
    watch_ids = list(watch_map.keys())

    active_map = {c.get("combo"): c for c in active if c.get("combo")}
    status_rows = {
        row.get("combo"): row
        for row in (_safe(data, "combo_status_rows", []) or [])
        if isinstance(row, dict) and row.get("combo")
    }

    combos = []
    for letter in "ABCDEFG":
        static = _COMBO_STATIC.get(letter, {})
        live = active_map.get(letter, {})
        status_row = status_rows.get(letter)
        is_active = letter in active_map
        is_watch = letter in watch_ids
        confirmed_legs = _combo_confirmed_legs(letter, active_map, watch_map, status_row)
        watch_entry = watch_map.get(letter, {})
        combos.append({
            "combo": letter,
            "name": static.get("name"),
            "direction": static.get("direction"),
            "horizon": static.get("horizon"),
            "legs_required": static.get("legs_required"),
            "total_legs": static.get("total_legs"),
            "variables": static.get("variables", []),
            "description": static.get("description"),
            "status": live.get("status") or (status_row or {}).get("status") or ("WATCH" if is_watch else "INACTIVE"),
            "is_active": is_active,
            "is_watch": is_watch,
            "duration_weeks": live.get("duration_weeks"),
            "duration_bucket": live.get("duration_bucket"),
            "confirmed_legs": confirmed_legs,
            "legs_confirmed": watch_entry.get("legs_confirmed", len(confirmed_legs)),
            "pending": watch_entry.get("pending") or (status_row or {}).get("pending"),
            "episode_start": live.get("episode_start"),
            "hit_rate_primary": live.get("hit_rate_primary") or live.get("hit_rate_3m"),
            "avg_return_primary": live.get("avg_return_primary") or live.get("avg_return_3m"),
            "combo_status_row": status_row,
        })
    return {
        "date": _safe(data, "date"),
        "combos": combos,
        "active_count": len(active_map),
        "watch_count": len(watch_ids),
    }


def get_combo_detail(combo_id: str) -> dict[str, Any]:
    """Full detail for one named combo — live status + hit rate stats + analog dates."""
    combo_id = combo_id.upper()
    if combo_id not in "ABCDEFG":
        raise ValueError(f"Invalid combo ID: {combo_id}")

    data = _load_runic()
    active = _safe(data, "active_combos", [])
    watch_list = _safe(data, "watch_combos", [])
    watch_map = _watch_combo_map(watch_list if isinstance(watch_list, list) else [])
    watch_ids = list(watch_map.keys())
    active_map = {c.get("combo"): c for c in active if c.get("combo")}
    status_row = next(
        (row for row in (_safe(data, "combo_status_rows", []) or [])
         if isinstance(row, dict) and row.get("combo") == combo_id),
        None,
    )

    static = _COMBO_STATIC.get(combo_id, {})
    live = active_map.get(combo_id, {})
    watch_entry = watch_map.get(combo_id, {})
    fire_detail = _db_combo_fire_detail(combo_id)
    confirmed_legs = _combo_confirmed_legs(combo_id, active_map, watch_map, status_row)
    if not confirmed_legs:
        confirmed_legs = (fire_detail or {}).get("confirmed_legs", [])

    try:
        from src.macro_intelligence.engine.combo_metadata import (
            combo_fed_cycle_slice_stats,
            combo_hit_rate_stats,
        )
        hr_stats = combo_hit_rate_stats(combo_id)
        fed_cycle_slices = combo_fed_cycle_slice_stats(combo_id)
    except Exception:
        hr_stats = {}
        fed_cycle_slices = None

    analog_details = _safe(data, "analog_details", [])
    if not analog_details or (analog_details and analog_details[0].get("date") is None):
        analog_details = _db_analog_details(combo_id)

    return {
        "combo": combo_id,
        "name": static.get("name"),
        "direction": static.get("direction"),
        "horizon": static.get("horizon"),
        "legs_required": static.get("legs_required"),
        "total_legs": static.get("total_legs"),
        "variables": static.get("variables", []),
        "description": static.get("description"),
        "status": live.get("status") or (status_row or {}).get("status") or ("WATCH" if combo_id in watch_ids else "INACTIVE"),
        "is_active": combo_id in active_map,
        "is_watch": combo_id in watch_ids,
        "duration_weeks": live.get("duration_weeks") or (fire_detail or {}).get("duration_weeks"),
        "duration_bucket": live.get("duration_bucket") or (fire_detail or {}).get("duration_bucket"),
        "confirmed_legs": confirmed_legs,
        "legs_confirmed": watch_entry.get("legs_confirmed", len(confirmed_legs)),
        "pending": watch_entry.get("pending") or (status_row or {}).get("pending"),
        "episode_start": live.get("episode_start") or (fire_detail or {}).get("episode_start"),
        "hit_rate_stats": hr_stats,
        "hit_rate_primary": hr_stats.get("hit_rate_primary"),
        "avg_return_primary": hr_stats.get("avg_return_primary"),
        "primary_label": hr_stats.get("primary_label"),
        "fed_cycle_slices": fed_cycle_slices,
        "analog_dates": [a.get("date") for a in analog_details if a.get("date")],
        "analog_details": analog_details,
    }


def get_combo_c_cancel_tracker() -> dict[str, Any]:
    """Combo C cancel monitor — 0/4 Fridays, probabilities, CPI state."""
    data = _load_runic()
    cancel = _safe(data, "combo_c_cancel", {})
    db_cancel = _db_combo_c_cancel()
    friday_log = _db_friday_cancel_log()
    cpi_print = _db_latest_cpi_print()
    upcoming = _db_upcoming_releases(days=21)
    variables = _safe(data, "variables_dashboard", [])
    var_map = {v["variable"]: v for v in variables if isinstance(v, dict)}
    wti_var = var_map.get("WTI", {})
    cpi_var = var_map.get("CPI", {})

    wti_potential_week = (
        cancel.get("wti_potential_week")
        or db_cancel.get("wti_potential_week", 0)
    )
    cancelled = bool(cancel.get("cancelled") or db_cancel.get("cancelled"))

    return {
        "date": _safe(data, "date"),
        "combo_c_active": any(c.get("combo") == "C" for c in _safe(data, "active_combos", [])),
        "cancel_status": {
            "fridays_complete": wti_potential_week,
            "fridays_required": 4,
            "cancelled": cancelled,
            "cancel_date": cancel.get("cancel_date") or db_cancel.get("cancel_date"),
            "last_check_date": db_cancel.get("last_check_date"),
        },
        "current_wti": {
            "value": wti_var.get("current"),
            "tier": wti_var.get("tier"),
            "cancel_gate_pct": 5.0,
            "leg_passes": (wti_var.get("current") is not None and float(wti_var.get("current") or 100) < 5.0),
        },
        "current_cpi": {
            "tier": cpi_var.get("tier"),
            "latest_print": cpi_print,
            "not_hot": cpi_print.get("not_hot") if cpi_print else None,
            "leg_passes": db_cancel.get("cpi_leg_passed"),
        },
        "probability_model": {
            "model_cancel_prob": cancel.get("model_cancel_prob"),
            "model_wti_leg_prob": cancel.get("model_wti_leg_prob"),
            "model_cpi_leg_prob": cancel.get("model_cpi_leg_prob"),
        },
        "friday_log": friday_log,
        "upcoming_releases": [r for r in upcoming if r.get("release_type") in ("CPI", "PPI")],
        "ppi_cooling": _safe(data, "ppi_cooling"),
        "if_cancelled": {
            "f_becomes_dominant": True,
            "e_warning_persists": True,
            "note": "If C cancels → F becomes dominant (wk 8/26). D+F tension remains.",
        },
    }


def get_combo_f_window() -> dict[str, Any]:
    """Combo F 26-week recovery window tracker."""
    data = _load_runic()
    active = _safe(data, "active_combos", [])
    f_combo = next((c for c in active if c.get("combo") == "F"), None)
    fire_detail = _db_combo_fire_detail("F")

    weeks_elapsed = (
        (f_combo.get("duration_weeks") if f_combo else None)
        or _safe(data, "combo_f_weeks_elapsed")
        or (fire_detail or {}).get("duration_weeks")
        or 0
    )
    total_weeks = 26
    progress_pct = round((weeks_elapsed / total_weeks) * 100, 1) if weeks_elapsed else 0.0

    episode_start = (
        (f_combo.get("episode_start") if f_combo else None)
        or (fire_detail or {}).get("episode_start")
        or (fire_detail or {}).get("date")
    )

    expiry = None
    if episode_start:
        try:
            from datetime import timedelta
            fire_dt = datetime.strptime(episode_start, "%Y-%m-%d")
            expiry = (fire_dt + timedelta(weeks=26)).strftime("%Y-%m-%d")
        except Exception:
            pass

    try:
        from src.macro_intelligence.engine.combo_metadata import combo_hit_rate_stats
        hr_stats = combo_hit_rate_stats("F")
    except Exception:
        hr_stats = {}

    return {
        "date": _safe(data, "date"),
        "active": _safe(data, "combo_f_active", False),
        "fire_date": episode_start,
        "expiry_date": expiry,
        "weeks_elapsed": weeks_elapsed,
        "weeks_remaining": max(0, total_weeks - (weeks_elapsed or 0)),
        "total_weeks": total_weeks,
        "progress_pct": progress_pct,
        "mtm_pct": f_combo.get("mtm_pct") if f_combo else None,
        "hit_rate_primary": hr_stats.get("hit_rate_primary"),
        "avg_return_6m": hr_stats.get("avg_return_primary"),
        "cancel_condition": "Combo B fires (new full capitulation). Combo D does NOT cancel F.",
        "d_f_tension": "D = reduce new longs, tighten stops. F = hold core longs.",
        "analog_details": _db_analog_details("F"),
    }


def get_analog_table(combo_id: str) -> dict[str, Any]:
    """Historical analog fire dates with SPX forward returns for one combo."""
    combo_id = combo_id.upper()
    if combo_id not in "ABCDEFG":
        raise ValueError(f"Invalid combo ID: {combo_id}")

    data = _load_runic()
    static = _COMBO_STATIC.get(combo_id, {})
    analog_details = _db_analog_details(combo_id, limit=10)

    if not analog_details:
        analog_details = _safe(data, "analog_details", [])

    try:
        from src.macro_intelligence.engine.combo_metadata import combo_hit_rate_stats
        hr_stats = combo_hit_rate_stats(combo_id)
    except Exception:
        hr_stats = {}

    if analog_details:
        returns = {
            h: [r.get(f"spx_{h}_pct") for r in analog_details if r.get(f"spx_{h}_pct") is not None]
            for h in ["1m", "3m", "6m", "12m"]
        }
        summary = {
            f"median_{h}": round(sorted(v)[len(v) // 2], 2) if v else None
            for h, v in returns.items()
        }
    else:
        summary = {}

    return {
        "combo": combo_id,
        "name": static.get("name"),
        "direction": static.get("direction"),
        "analog_details": analog_details,
        "instance_count": len(analog_details),
        "hit_rate_stats": hr_stats,
        "summary_returns": summary,
    }


def get_narrative() -> dict[str, Any]:
    """Latest nightly narrative, system recommendation, geo classification."""
    data = _load_runic()
    return {
        "date": _safe(data, "date"),
        "narrative": _safe(data, "narrative"),
        "system_recommendation": _safe(data, "system_recommendation"),
        "brave_fearful_display": _safe(data, "brave_fearful_display"),
        "dominant_signal": _safe(data, "dominant_signal"),
        "dominant_reason": _safe(data, "dominant_reason"),
        "regime": _safe(data, "regime", {}),
        "cftc_status": _safe(data, "cftc_status"),
    }


def get_persistence_signals() -> dict[str, Any]:
    """Persistence / slow-grind signals from latest nightly run."""
    data = _load_runic()
    return {
        "date": _safe(data, "date"),
        "persistence_signals": _safe(data, "persistence_signals", []),
        "generic_combo_watch": _safe(data, "generic_combo_watch", []),
        "source_freshness": _safe(data, "source_freshness"),
    }


def get_source_freshness() -> dict[str, Any]:
    """Data source freshness audit from latest nightly run."""
    data = _load_runic()
    return {
        "date": _safe(data, "date"),
        "source_freshness": _safe(data, "source_freshness", {}),
        "cftc_status": _safe(data, "cftc_status"),
        "pending_cpi_release": _safe(data, "pending_cpi_release", False),
        "variables_dashboard": [
            {
                "variable": v.get("variable"),
                "source_date": v.get("source_date"),
                "lag_days": v.get("lag_days"),
                "expected_source_date": v.get("expected_source_date"),
                "source_note": v.get("source_note"),
                "tier": v.get("tier"),
            }
            for v in _safe(data, "variables_dashboard", [])
            if isinstance(v, dict)
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# SSI helpers (read from ssi.db directly)
# ─────────────────────────────────────────────────────────────────────────────

def _ssi_db_conn():
    """Return a sqlite3 connection to ssi.db (row_factory set)."""
    import sqlite3
    from src.config_paths import SSI_DB
    if not SSI_DB.exists():
        raise FileNotFoundError(f"SSI database not found: {SSI_DB}")
    conn = sqlite3.connect(SSI_DB)
    conn.row_factory = sqlite3.Row
    return conn


# Display rounding: 2 decimals for indicators (ratios, betas, oscillators, spreads).
# 4 decimals reserved for currency pairs (none of the SSI legacy inputs are FX).
def _round2(value: Any) -> float | None:
    return round(float(value), 2) if value is not None else None


def _parse_payload_json(payload_json: str | None) -> dict[str, Any]:
    if not payload_json:
        return {}
    try:
        data = json.loads(payload_json)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _parse_layer2_votes(payload_json: str | None) -> list[dict[str, Any]]:
    """Extract layer2 gate votes from the stored payload_json column."""
    data = _parse_payload_json(payload_json)
    inputs = data.get("inputs", {})
    votes = inputs.get("layer2_gate_votes") or inputs.get("layer2_votes")
    if isinstance(votes, list):
        return votes
    return []


def get_ssi_summary() -> dict[str, Any]:
    """
    Latest SSI snapshot: level, percentile, multiplier, layer2 status,
    and the 4 input values with individual votes.
    """
    conn = _ssi_db_conn()
    try:
        row = conn.execute(
            """SELECT date, ssi_level, ssi_percentile_5y, layer2_status,
                      layer2_confirmed_count, ssi_multiplier,
                      hyg_lqd, dbmf_beta, cnn_fg, vix_ratio, payload_json
               FROM ssi_daily ORDER BY date DESC LIMIT 1"""
        ).fetchone()
    finally:
        conn.close()

    if not row:
        raise FileNotFoundError("No SSI data in database yet.")

    votes = _parse_layer2_votes(row["payload_json"])
    vote_map = {v["input"]: v for v in votes}
    payload = _parse_payload_json(row["payload_json"])
    gate_label = payload.get("layer2_gate_label")
    gate_total = len(votes) if votes else 6
    min_confirmed = 2
    layer3_cftc = (payload.get("inputs") or {}).get("layer3_cftc") or {}

    def _vote(key: str) -> dict[str, Any]:
        v = vote_map.get(key, {})
        return {
            "raw": _round2(v.get("raw") if v.get("raw") is not None else row[key] if key in row.keys() else None),
            "vote": v.get("vote"),
            "signal": v.get("signal"),
            "pctile": v.get("pctile"),
            "norm": v.get("norm"),
        }

    gate_inputs: dict[str, dict[str, Any]] = {}
    for v in votes:
        key = v.get("input")
        if not key:
            continue
        gate_inputs[str(key)] = {
            "raw": _round2(v.get("raw")),
            "vote": v.get("vote"),
            "signal": v.get("signal"),
            "pctile": v.get("pctile"),
            "norm": _round2(v.get("norm")) if v.get("norm") is not None else None,
        }

    return {
        "date": row["date"],
        "ssi_level": row["ssi_level"],
        "ssi_percentile_5y": row["ssi_percentile_5y"],
        "ssi_multiplier": row["ssi_multiplier"],
        "layer2_status": row["layer2_status"],
        "layer2_confirmed_count": row["layer2_confirmed_count"],
        "layer2_required": min_confirmed,
        "layer2_gate_total": gate_total or 6,
        "layer2_gate_label": gate_label,
        "layer2_gate_direction": payload.get("layer2_gate_direction"),
        "layer3_cftc": layer3_cftc,
        "posture": (
            "RISK_ON" if row["ssi_level"] < -0.6
            else "RISK_OFF" if row["ssi_level"] > 0.85
            else "NEUTRAL"
        ),
        "long_signal_active": row["ssi_level"] < -0.6,
        "short_signal_active": row["ssi_level"] > 0.85,
        "inputs": gate_inputs or {
            "hyg_lqd": _vote("hyg_lqd"),
            "dbmf_beta": _vote("dbmf_beta"),
            "cnn_fg": _vote("cnn_fg"),
            "vix_ratio": _vote("vix_ratio"),
        },
    }


def get_ssi_history(days: int = 30) -> dict[str, Any]:
    """
    Daily SSI time series for the last N days.
    Returns each day's level, percentile, multiplier, layer2 status, and 4 inputs.
    """
    conn = _ssi_db_conn()
    try:
        rows = conn.execute(
            """SELECT date, ssi_level, ssi_percentile_5y, layer2_status,
                      layer2_confirmed_count, ssi_multiplier,
                      hyg_lqd, dbmf_beta, cnn_fg, vix_ratio
               FROM ssi_daily
               ORDER BY date DESC LIMIT ?""",
            (days,),
        ).fetchall()
    finally:
        conn.close()

    series = [
        {
            "date": r["date"],
            "ssi_level": r["ssi_level"],
            "ssi_percentile_5y": r["ssi_percentile_5y"],
            "ssi_multiplier": r["ssi_multiplier"],
            "layer2_status": r["layer2_status"],
            "layer2_confirmed_count": r["layer2_confirmed_count"],
            "inputs": {
                "hyg_lqd":   _round2(r["hyg_lqd"]),
                "dbmf_beta": _round2(r["dbmf_beta"]),
                "cnn_fg":    _round2(r["cnn_fg"]),
                "vix_ratio": _round2(r["vix_ratio"]),
            },
        }
        for r in rows
    ]
    # Return in chronological order for charting
    series.reverse()

    latest = series[-1] if series else {}
    return {
        "days_requested": days,
        "days_available": len(series),
        "latest_date": latest.get("date"),
        "latest_level": latest.get("ssi_level"),
        "latest_multiplier": latest.get("ssi_multiplier"),
        "series": series,
    }


def get_ssi_multiplier() -> dict[str, Any]:
    """
    Lightweight endpoint — just the current multiplier and sizing signals.
    Suitable for position-sizing checks without loading the full SSI payload.
    """
    conn = _ssi_db_conn()
    try:
        row = conn.execute(
            """SELECT date, ssi_level, ssi_multiplier, layer2_status,
                      layer2_confirmed_count
               FROM ssi_daily ORDER BY date DESC LIMIT 1"""
        ).fetchone()
    finally:
        conn.close()

    if not row:
        raise FileNotFoundError("No SSI data in database yet.")

    # Also pull from positioning.json for the signal thresholds
    pos_data: dict[str, Any] = {}
    try:
        from src.macro_intelligence.output.json_writer import read_positioning_data
        pos_data = read_positioning_data() or {}
    except Exception:
        pass

    signals = pos_data.get("signals", {})
    return {
        "date": row["date"],
        "ssi_multiplier": row["ssi_multiplier"],
        "ssi_level": row["ssi_level"],
        "layer2_status": row["layer2_status"],
        "layer2_confirmed_count": row["layer2_confirmed_count"],
        "long_size_mult": signals.get("long", {}).get("size_mult", 1.0),
        "short_size_mult": signals.get("short", {}).get("size_mult", 1.0),
        "long_active": signals.get("long", {}).get("active", False),
        "short_active": signals.get("short", {}).get("active", False),
        "long_entry_threshold": signals.get("long", {}).get("entry_threshold", -0.6),
        "short_entry_threshold": signals.get("short", {}).get("entry_threshold", 0.85),
    }


def trigger_nightly_run(as_of: str | None = None, use_claude: bool = False) -> dict[str, Any]:
    """Trigger the nightly run. use_claude=False by default for API calls (faster, no LLM cost)."""
    try:
        from src.macro_intelligence.jobs.nightly_run import run_nightly
        payload = run_nightly(as_of=as_of, use_claude=use_claude)
        return {
            "status": "completed",
            "date": payload.get("date"),
            "dominant_signal": payload.get("dominant_signal"),
            "active_combos": [c.get("combo") for c in payload.get("active_combos", [])],
            "watch_combos": payload.get("watch_combos", []),
            "output_path": payload.get("output_path"),
        }
    except Exception as exc:
        raise RuntimeError(f"Nightly run failed: {exc}") from exc
