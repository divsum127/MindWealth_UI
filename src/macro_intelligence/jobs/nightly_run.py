"""Nightly Mon-Fri job: dominant signal, Claude narrative, JSON output."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src.macro_intelligence.claude.nightly_briefing import generate_nightly_briefing
from src.macro_intelligence.claude.regime_classifier import classify_regime
from src.macro_intelligence.data.pull_all import get_readings_as_of, pull_all_series
from src.macro_intelligence.db.connection import init_db
from src.macro_intelligence.engine.combo_detector import detect_all_combos, detect_named_combos
from src.macro_intelligence.engine.prefilter import apply_prefilter
from src.macro_intelligence.models import GateFlag
from src.macro_intelligence.engine.dominant import find_analog_dates, find_analog_details, resolve_dominant
from src.macro_intelligence.engine.combo_c_cancel import run_combo_c_cancel_check
from src.macro_intelligence.engine.combo_cancel_probability import (
    combo_c_total_cancel_prob,
    combo_cancel_probability_wti,
)
from src.macro_intelligence.engine.combo_metadata import combo_bullish, combo_hit_rate_stats, posture_display
from src.macro_intelligence.engine.persistence import run_persistence_scan
from src.macro_intelligence.engine.vix_bypass import compute_vix_bypass
from src.macro_intelligence.engine.regime_rules import build_python_regime
from src.macro_intelligence.output.briefing_renderer import (
    build_combo_status_rows,
    build_regime_grid,
    build_system_recommendation,
    write_briefing,
)
from src.macro_intelligence.output.json_writer import (
    build_payload,
    read_ssi_layer2_status,
    ssi_confirmed_for_combo_f,
    write_runic_json,
)
from src.macro_intelligence.db.connection import get_connection
from src.macro_intelligence.output.json_writer import _combo_c_cancel_state


def _active_combo_dicts(fires) -> tuple[list[dict[str, Any]], list[str]]:
    active: list[dict[str, Any]] = []
    watch: list[str] = []
    for f in fires:
        meta = f.macro_regime or {}
        d: dict[str, Any] = {
            "combo": f.runic_combo,
            "status": f.status,
            "duration_weeks": f.duration_weeks,
            "duration_bucket": f.duration_bucket.value if f.duration_bucket else None,
            "episode_start": meta.get("episode_start"),
            "confirmed_legs": meta.get("confirmed_legs"),
        }
        if f.status in ("WATCH", "CONTESTED"):
            watch.append(f.runic_combo or "?")
        elif f.status in ("ACTIVE", "PARTIAL", "CONFIRMED", "CONFIRMED_3_OF_3"):
            stats = combo_hit_rate_stats(f.runic_combo or "C")
            d.update(stats)
            d["hit_rate_3m"] = stats.get("hit_rate_primary")
            d["avg_return_3m"] = stats.get("avg_return_primary")
            active.append(d)
    return active, watch


def _variables_dashboard(readings: dict[str, dict]) -> list[dict[str, Any]]:
    order = ["NFCI", "HY", "WALCL", "CNH", "WTI", "VIX", "VXTS", "CFTC", "CURVE", "CPI", "GSR", "CAPE"]
    rows = []
    cftc_rm_pct = None
    with get_connection() as conn:
        cftc_row = conn.execute(
            "SELECT rm_pctile FROM cftc_positioning ORDER BY date DESC LIMIT 1"
        ).fetchone()
        if cftc_row:
            cftc_rm_pct = cftc_row["rm_pctile"]
    for i, vid in enumerate(order, 1):
        r = readings.get(vid, {})
        row = {
            "num": i,
            "variable": vid,
            "current": r.get("raw_value"),
            "tier": r.get("signal_tier", "NORMAL"),
            "pctile_3yr": r.get("pctile_rank_3yr"),
            "unconditional_pctile": r.get("unconditional_pctile"),
            "regime_pctile": r.get("regime_pctile"),
            "direction": r.get("direction"),
        }
        if vid == "CFTC":
            if cftc_rm_pct is not None:
                row["cftc_rm_pctile"] = cftc_rm_pct
            row["source_note"] = (
                "CFTC.gov TFF · S&P 500 Consolidated · Lev Money net (Fri report = Tue positions)"
            )
        rows.append(row)
    return rows


def run_nightly(as_of: str | None = None, use_claude: bool = True) -> dict[str, Any]:
    init_db()
    as_of = as_of or datetime.now().strftime("%Y-%m-%d")
    pull_all_series(as_of)
    readings = get_readings_as_of(as_of)
    persistence = run_persistence_scan(as_of)
    fires = detect_named_combos(as_of, readings)
    active, watch = _active_combo_dicts(fires)

    # Generic combos: detect + prefilter gate (v3); surface passed candidates in JSON
    all_fires = detect_all_combos(as_of, persist=False)
    generic_watch: list[dict[str, Any]] = []
    for g in all_fires:
        if g.runic_combo:
            continue
        sig = "+".join(sorted(g.var_ids))
        gate = apply_prefilter(None, sig if sig else "?")
        if gate == GateFlag.SIGNAL:
            generic_watch.append(
                {"vars": g.var_ids, "status": g.status, "gate": gate.value}
            )

    regime_base = build_python_regime(as_of, readings)
    regime_obj = classify_regime(
        as_of, context=_regime_context(readings), use_claude=use_claude, readings=readings
    )
    regime_dict = {**regime_base, **regime_obj.to_dict()}
    dominant, reason, brave = resolve_dominant(active, regime_dict)
    analogs = find_analog_dates(dominant)
    analog_details = find_analog_details(dominant)
    dom_stats = combo_hit_rate_stats(dominant or "C")
    wti_val = readings.get("WTI", {}).get("raw_value")
    c_active = any(c.runic_combo == "C" and c.status == "ACTIVE" for c in fires)
    cancel_result = run_combo_c_cancel_check(as_of, wti_val, c_active)
    wti_mc = combo_cancel_probability_wti(float(wti_val or 70.0))
    cancel_model = combo_c_total_cancel_prob(wti_mc, cpi_not_hot_rate=0.52)

    f_active = any(c.get("combo") == "F" and c.get("status") == "ACTIVE" for c in active)
    f_weeks = next((c.get("duration_weeks") for c in active if c.get("combo") == "F"), None)
    vix_bypass = compute_vix_bypass(active, ssi_confirmed_f=ssi_confirmed_for_combo_f())

    payload = build_payload(
        as_of=as_of,
        regime=regime_dict,
        dominant_signal=dominant,
        dominant_reason=reason,
        brave_fearful=brave,
        active_combos=active,
        watch_combos=watch,
        persistence_signals=persistence,
        analog_dates=analogs,
        analog_details=analog_details,
        spx_3m_forward_avg=dom_stats.get("avg_return_primary"),
        spx_3m_hit_rate=dom_stats.get("hit_rate_primary"),
        combo_f_active=f_active,
        combo_f_weeks_elapsed=f_weeks,
        narrative="",
        vix_bypass=vix_bypass,
        variables_dashboard=_variables_dashboard(readings),
        ssi_layer2_status=read_ssi_layer2_status(),
    )
    payload["generic_combo_watch"] = generic_watch[:10]
    payload["combo_c_cancel"] = {
        **_combo_c_cancel_state(),
        **{k: v for k, v in cancel_result.items() if k not in ("governing_cpi",)},
        "model_cancel_prob": cancel_model.get("combined_cancel_prob"),
        "model_wti_leg_prob": wti_mc.get("monte_carlo_prob_all_4"),
        "model_cpi_leg_prob": cancel_model.get("cpi_leg_prob"),
    }
    payload["brave_fearful_display"] = posture_display(brave)
    payload["narrative"] = generate_nightly_briefing(payload, use_claude=use_claude)
    payload["combo_status_rows"] = build_combo_status_rows(payload)
    payload["regime_grid"] = build_regime_grid(payload)
    payload["system_recommendation"] = build_system_recommendation(payload)
    path = write_runic_json(payload)
    briefing_paths = write_briefing(payload)
    payload["output_path"] = str(path)
    payload["briefing_paths"] = {k: str(v) for k, v in briefing_paths.items()}
    return payload


def _regime_context(readings: dict[str, dict]) -> dict[str, Any]:
    curve = readings.get("CURVE", {})
    nfci = readings.get("NFCI", {})
    cape = readings.get("CAPE", {})
    return {
        "curve": curve.get("raw_value", 0),
        "curve_dir": "steepening" if (curve.get("raw_value") or 0) > 0 else "flat",
        "nfci_sign": "tight" if (nfci.get("raw_value") or 0) > 0 else "loose",
        "cape_decile": "high" if (cape.get("raw_value") or 0) > 30 else "mid",
        "ffr": "unknown",
        "walcl_dir": "flat",
    }
