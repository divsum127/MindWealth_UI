#!/usr/bin/env python3
"""B4 original-spec window fix pipeline: CONFIG → recompute pctiles → sweeps → Part B JSON → D6 reslice."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.analysis.combo_threshold_sweep import (  # noqa: E402
    load_readings_panel,
    run_all_combo_sweeps,
    sweep_combo_b_gates,
    sweep_combo_d_gates,
)
from src.macro_intelligence.analysis.regime_experiments.run_all import (  # noqa: E402
    _run_b4_window_audit,
    run_part_b,
)
from src.macro_intelligence.config import load_config
from src.macro_intelligence.data.pull_all import _reading_for_var, _upsert_reading, load_all_series
from src.macro_intelligence.db.connection import get_connection
from src.macro_intelligence.engine.regime_rules import build_python_regime

OUT_DIR = Path(__file__).resolve().parent
DATE_TAG = datetime.now(UTC).strftime("%Y-%m-%d")
B4_VARS = ("HY", "VIX", "VXTS")
SWEEP_OUT = ROOT / "macro_intelligence/analysis/regime_v2_experiments/threshold_sweep_v2_b4_fix"


def recompute_pctiles_for_vars(var_ids: tuple[str, ...]) -> dict[str, Any]:
    cfg = load_config()
    var_cfgs = {v["id"]: v for v in cfg["variables"]}
    series = load_all_series(force=True)
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT DISTINCT date FROM daily_readings
            WHERE var_id IN ({",".join("?" * len(var_ids))})
            ORDER BY date
            """,
            var_ids,
        ).fetchall()
    dates = [r["date"] for r in rows]
    updated = 0
    tier_changes = 0
    for ds in dates:
        fed_cycle = build_python_regime(ds).get("fed_cycle")
        for vid in var_ids:
            reading = _reading_for_var(vid, var_cfgs[vid], series, ds, fed_cycle)
            if not reading:
                continue
            with get_connection() as conn:
                old = conn.execute(
                    "SELECT unconditional_pctile, signal_tier FROM daily_readings WHERE date=? AND var_id=?",
                    (ds, vid),
                ).fetchone()
            _upsert_reading(reading)
            updated += 1
            if old and (
                old["unconditional_pctile"] != reading.get("unconditional_pctile")
                or old["signal_tier"] != reading.get("signal_tier")
            ):
                tier_changes += 1
    return {"dates": len(dates), "rows_updated": updated, "rows_with_pctile_or_tier_change": tier_changes}


def sweep_combo_g_baseline(panel: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Minimal Combo G CONFIG baseline using updated panel (first-crossing model)."""
    from src.macro_intelligence.data.yahoo_pull import fetch_yahoo_close
    from src.macro_intelligence.engine.combo_detector import _hy_oas_bps
    from src.macro_intelligence.engine.forward_returns import _nyse_sessions, forward_return_pct
    from src.macro_intelligence.analysis.regime_experiments.metrics import probability_weighted_summary

    cfg = load_config().get("named_combos", {}).get("G", {})
    vxts_max = float(cfg.get("vxts_max", 1.0))
    vix_max = float(cfg.get("vix_max", 20))
    hy_widen = float(cfg.get("hy_widen_4wk_bps", 30))

    dates = sorted(
        set(r["date"] for r in panel.get("VXTS", []))
        & set(r["date"] for r in panel.get("VIX", []))
        & set(r["date"] for r in panel.get("HY", []))
    )
    spx = fetch_yahoo_close("^GSPC", "1990-01-01")
    sessions = _nyse_sessions()

    def hy4wk(ds: str) -> float | None:
        rows = panel.get("HY", [])
        idx = next((i for i, r in enumerate(rows) if r["date"] == ds), None)
        if idx is None or idx < 4:
            return None
        cur = rows[idx].get("raw")
        prev = rows[idx - 4].get("raw")
        if cur is None or prev is None:
            return None
        return (_hy_oas_bps(cur) or 0) - (_hy_oas_bps(prev) or 0)

    events: list[str] = []
    prev = False
    for ds in dates:
        vx = _reading_on(panel, "VXTS", ds)
        vi = _reading_on(panel, "VIX", ds)
        h4 = hy4wk(ds)
        if not vx or not vi or h4 is None:
            prev = False
            continue
        in_band = (vx["raw"] or 999) < vxts_max and (vi["raw"] or 999) <= vix_max and h4 >= hy_widen
        if in_band and not prev:
            events.append(ds)
        prev = in_band

    rets_3m = [
        forward_return_pct(spx, pd.Timestamp(ds), 63, sessions=sessions) for ds in events
    ]
    rets_3m = [r for r in rets_3m if r is not None]
    pw = probability_weighted_summary(rets_3m, bullish=False, benchmark_pct=0.0, horizon="3M")
    return {
        "combo": "G",
        "validated_horizon": "spx_3m",
        "direction": "bearish",
        "current_gates": cfg,
        "config_baseline": {
            "n_events": len(events),
            "bear_hit_3m_pct": round((pw.get("hit_rate") or 0) * 100, 1) if pw.get("n") else None,
            "avg_spx_3m_pct": round(pw.get("avg") or 0, 2) if pw.get("avg") is not None else None,
            "pw_summary": pw,
        },
        "run_date": DATE_TAG,
        "note": "CONFIG baseline first-crossing after B4 rolling_3y pctile fix",
    }


def _reading_on(panel: dict, var_id: str, date: str) -> dict | None:
    for r in panel.get(var_id, []):
        if r["date"] == date:
            return r
    return None


def feedback_backlog_triage() -> dict[str, Any]:
    return {
        "cheatsheet_compare": {
            "status": "BLOCKED",
            "reason": "i3 Invest Combo Cheatsheet reference numbers not in repo; need Rohit to share values for diff column.",
        },
        "liquidity_spx_tables": {
            "status": "PARTIAL",
            "reason": "D6 reslice produces FM band + 9-state/4-state liquidity combo-fire tables at 1M–12M (FM) and 3M (combo fires). Full A5 band grid (every liquidity slice × 1m/3m/6m/9m/12m) in separate export if needed.",
            "artifacts": [
                f"D6_fm_regime_slices_analytics_{DATE_TAG}.csv",
                f"D6_liquidity_9state_combo_fires_{DATE_TAG}.csv",
                f"D6_liquidity_4state_analytics_combo_fires_{DATE_TAG}.csv",
            ],
        },
        "geo_2state_prod": {
            "status": "PENDING",
            "reason": "D6 decision: 2-state NEUTRAL/ELEVATED approved in principle; production classifier still 3-state. Prompt + code switch deferred.",
        },
        "regime_score_validation": {
            "status": "PENDING",
            "reason": "Section D addendum tests (Spearman ρ, AND vs time-only, hit-rate weights, time-decay) not implemented as automated suite yet.",
        },
    }


def write_report(payload: dict[str, Any]) -> Path:
    b4 = payload["b4_audit"]
    recomp = payload["recompute"]
    sweeps = payload["sweeps"]
    backlog = payload["feedback_backlog"]

    lines = [
        "# B4 Window Fix Pipeline — Original Spec",
        "",
        f"**Date:** {DATE_TAG}",
        "",
        "## Authoritative rule",
        "",
        "This pipeline uses the **original B4 rule** from the consolidated plan / experiment suite — **not** Rohit's 2026-06-11 override.",
        "",
        "| Class | Variables | `pctile_window` |",
        "|-------|-----------|-----------------|",
        "| Structural / level | CAPE, NFCI, **WALCL**, CURVE, DXY | `full` |",
        "| Flow / ROC / pctile | **HY, VIX, VXTS**, CFTC, WTI, CNH, CPI, GSR | `rolling_3y` |",
        "",
        "Rohit's June 11 note (HY/VIX/VXTS = full, WALCL MoM = rolling) was **explicitly rejected** for this run per task instruction.",
        "",
        "## Step 1 — CONFIG applied",
        "",
        "- HY → `rolling_3y`",
        "- VIX → `rolling_3y`",
        "- VXTS → `rolling_3y`",
        "- WALCL → `full` (unchanged since 2026-06-09 fix)",
        "",
        "## Step 2 — Percentile recompute",
        "",
        f"- Dates touched: **{recomp['dates']}**",
        f"- Rows updated: **{recomp['rows_updated']}**",
        f"- Rows with pctile or tier change: **{recomp['rows_with_pctile_or_tier_change']}**",
        "",
        "## Step 3 — B4 audit",
        "",
        f"- **pass:** `{b4['pass']}`",
        f"- **mismatches:** {len(b4.get('mismatches', []))}",
        "",
    ]
    if b4.get("mismatches"):
        lines += ["| var_id | configured | expected |", "|--------|------------|----------|"]
        for m in b4["mismatches"]:
            lines.append(f"| {m['var_id']} | {m['configured']} | {m['expected']} |")
    else:
        lines.append("All 12 variables PASS.")
    lines += [
        "",
        "## Step 4 — Combo B / D / G sweeps (post-fix panel)",
        "",
        f"- Sweep output dir: `{sweeps['out_dir']}`",
        "",
    ]
    b = sweeps.get("combo_b_summary", {})
    d = sweeps.get("combo_d_summary", {})
    g = sweeps.get("combo_g_baseline", {})
    lines += [
        "### Combo B (bullish, 3M primary)",
        f"- CONFIG baseline tests in sweep JSON",
        "",
        "### Combo D (bearish)",
        f"- Sweep artifact: `COMBO_D_gate_sweep.json`",
        "",
        "### Combo G (bearish, CONFIG baseline)",
        f"- n_events: **{g.get('config_baseline', {}).get('n_events')}**",
        f"- bear hit 3M: **{g.get('config_baseline', {}).get('bear_hit_3m_pct')}%**",
        f"- avg SPX 3M: **{g.get('config_baseline', {}).get('avg_spx_3m_pct')}%**",
        "",
        "## Step 5 — Part B JSON refreshed",
        "",
        f"- `B_twy_and_percentiles.json` B4 pass: **{payload['part_b']['B4_window_audit']['pass']}**",
        f"- Dual percentile rows (both): **{payload['part_b']['B3_dual_percentile']['rows_with_both']}**",
        "",
        "## Step 6 — D6 analytics re-slice",
        "",
        f"- Artifacts: `D6_regime_analytics_{DATE_TAG}.*`",
        "",
        "## Feedback backlog triage",
        "",
    ]
    for key, item in backlog.items():
        lines.append(f"### {key}")
        lines.append(f"- **Status:** {item['status']}")
        lines.append(f"- {item['reason']}")
        if item.get("artifacts"):
            lines.append(f"- Artifacts: {', '.join(item['artifacts'])}")
        lines.append("")

    path = OUT_DIR / f"B4_window_fix_pipeline_{DATE_TAG}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> int:
    print("=== B4 window fix pipeline (original spec) ===", flush=True)

    recomp = recompute_pctiles_for_vars(B4_VARS)
    print(f"Recomputed: {recomp}", flush=True)

    b4 = _run_b4_window_audit()
    print(f"B4 pass={b4['pass']} mismatches={b4.get('mismatches')}", flush=True)

    panel = load_readings_panel("1990-01-01")
    written = run_all_combo_sweeps(SWEEP_OUT)
    g_baseline = sweep_combo_g_baseline(panel)
    g_path = SWEEP_OUT / "COMBO_G_config_baseline.json"
    g_path.write_text(json.dumps(g_baseline, indent=2), encoding="utf-8")
    written["COMBO_G_config_baseline.json"] = str(g_path)

    part_b = run_part_b()

    # D6 reslice subprocess
    reslice_script = OUT_DIR / "run_d6_regime_analytics_reslice.py"
    subprocess.check_call([sys.executable, str(reslice_script)], cwd=str(ROOT))

    payload = {
        "task": "B4_window_fix_pipeline",
        "date": DATE_TAG,
        "authoritative_rule": "original_b4_consolidated_plan",
        "rejected_override": "rohit_2026-06-11_structural_full_for_hy_vix_vxts",
        "recompute": recomp,
        "b4_audit": b4,
        "sweeps": {
            "out_dir": str(SWEEP_OUT),
            "written": written,
            "combo_g_baseline": g_baseline,
        },
        "part_b": part_b,
        "feedback_backlog": feedback_backlog_triage(),
    }
    json_path = OUT_DIR / f"B4_window_fix_pipeline_{DATE_TAG}.json"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    md_path = write_report(payload)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    return 0 if b4["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
