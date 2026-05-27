"""Nightly Mon-Fri job: dominant signal, Claude narrative, JSON output."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src.macro_intelligence.claude.nightly_briefing import generate_nightly_briefing
from src.macro_intelligence.claude.regime_classifier import classify_regime
from src.macro_intelligence.data.pull_all import get_readings_as_of, pull_all_series
from src.macro_intelligence.db.connection import init_db
from src.macro_intelligence.engine.combo_detector import detect_named_combos
from src.macro_intelligence.engine.dominant import find_analog_dates, resolve_dominant
from src.macro_intelligence.engine.hit_rates import raw_hit_rate
from src.macro_intelligence.engine.persistence import run_persistence_scan
from src.macro_intelligence.engine.vix_bypass import compute_vix_bypass
from src.macro_intelligence.output.json_writer import build_payload, write_runic_json


def _active_combo_dicts(fires) -> tuple[list[dict[str, Any]], list[str]]:
    active: list[dict[str, Any]] = []
    watch: list[str] = []
    for f in fires:
        d = {
            "combo": f.runic_combo,
            "status": f.status,
            "duration_weeks": f.duration_weeks,
            "duration_bucket": f.duration_bucket.value if f.duration_bucket else None,
        }
        if f.status == "WATCH":
            watch.append(f.runic_combo or "?")
        elif f.status in ("ACTIVE", "PARTIAL"):
            active.append(d)
    return active, watch


def _variables_dashboard(readings: dict[str, dict]) -> list[dict[str, Any]]:
    order = ["NFCI", "HY", "WALCL", "CNH", "WTI", "VIX", "VXTS", "CFTC", "CURVE", "CPI", "GSR", "CAPE"]
    rows = []
    for i, vid in enumerate(order, 1):
        r = readings.get(vid, {})
        rows.append(
            {
                "num": i,
                "variable": vid,
                "current": r.get("raw_value"),
                "tier": r.get("signal_tier", "NORMAL"),
                "pctile_3yr": r.get("pctile_rank_3yr"),
                "direction": r.get("direction"),
            }
        )
    return rows


def run_nightly(as_of: str | None = None, use_claude: bool = True) -> dict[str, Any]:
    init_db()
    as_of = as_of or datetime.now().strftime("%Y-%m-%d")
    pull_all_series(as_of)
    readings = get_readings_as_of(as_of)
    persistence = run_persistence_scan(as_of)
    fires = detect_named_combos(as_of, readings)
    active, watch = _active_combo_dicts(fires)

    regime = classify_regime(as_of, context=_regime_context(readings), use_claude=use_claude)
    dominant, reason, brave = resolve_dominant(active)
    analogs = find_analog_dates(dominant)
    hr = raw_hit_rate(dominant or "C", bullish=(dominant in ("B", "F")))

    f_active = any(c.get("combo") == "F" and c.get("status") == "ACTIVE" for c in active)
    f_weeks = next((c.get("duration_weeks") for c in active if c.get("combo") == "F"), None)
    vix_bypass = compute_vix_bypass(active)

    payload = build_payload(
        as_of=as_of,
        regime=regime.to_dict(),
        dominant_signal=dominant,
        dominant_reason=reason,
        brave_fearful=brave,
        active_combos=active,
        watch_combos=watch,
        persistence_signals=persistence,
        analog_dates=analogs,
        spx_3m_forward_avg=hr.get("avg_return"),
        spx_3m_hit_rate=hr.get("hit_rate"),
        combo_f_active=f_active,
        combo_f_weeks_elapsed=f_weeks,
        narrative="",
        vix_bypass=vix_bypass,
        variables_dashboard=_variables_dashboard(readings),
    )
    payload["narrative"] = generate_nightly_briefing(payload, use_claude=use_claude)
    path = write_runic_json(payload)
    payload["output_path"] = str(path)
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
