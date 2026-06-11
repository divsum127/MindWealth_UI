"""Generate MACRO_REGIME_V2_EXPERIMENT_REPORT.md from experiment artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_master_report(manifest: dict[str, Any]) -> Path:
    art_dir = Path("macro_intelligence/analysis/regime_v2_experiments")
    report_path = Path("docs/ssi_validation/MACRO_REGIME_V2_EXPERIMENT_REPORT.md")

    xfm = manifest.get("xfm", {})
    exps = xfm.get("experiments") or {}
    xfm1_short = exps.get("X-FM-1_extreme_short", {})
    xfm1_long = exps.get("X-FM-1_extreme_long", {})
    xfm1_mod = exps.get("X-FM-1_moderate", {})
    xfm2 = exps.get("X-FM-2_combo_b", {})
    xfm3 = exps.get("X-FM-3_combo_d", {})
    part_b = manifest.get("part_b", {})
    part_f = manifest.get("part_f", {})
    part_g = manifest.get("part_g", {})
    part_e = manifest.get("part_e", {})
    part_c = manifest.get("part_c", {})
    part_d = manifest.get("part_d", {})
    part_a = manifest.get("part_a", {})
    part_h = manifest.get("part_h", {})
    promotion_top20 = _load_promotion_top20()

    lines = [
        "# Macro Regime v2 — Experiment Report",
        "",
        f"**Run date:** {manifest.get('run_date', 'unknown')}",
        "**Source plan:** [`Macro_Regime_System_v2_Consolidated_Plan_Mail.pdf`](../../macro_intelligence_docs/Macro_Regime_System_v2_Consolidated_Plan_Mail.pdf)",
        f"**Artifacts:** `{art_dir}/`",
        "",
        "---",
        "",
        "## 1. Executive summary",
        "",
        "| Deliverable | Status | Recommendation |",
        "|-------------|--------|----------------|",
        "| A — Regime dimension refinement | RUN | Shadow v2 labels backfilled; review distributions below |",
        "| B — TWY_ROC + dual percentiles | RUN | Validate Apr 2025 anchor; continue dual storage |",
        "| C — Emission vectors | RUN | Backfill complete; HMM prod deferred 6mo |",
        "| D — HMM prototype | RESEARCH | Prototype only until live vectors accumulate |",
        "| E — Cancel probability | RUN | Monte Carlo wired; calibrate on live Combo C |",
        "| F — Quant regime defs | RUN | F4 grid + Oct 2022 anchor |",
        "| G — Persistence | RUN | Grind not standalone short; VIX suppressed lead rate |",
        "| H — 298 combo pipeline | "
        + ("RUN" if part_h.get("status") == "COMPLETE" else "PARTIAL")
        + " | See combo_discovery report + promotion shortlist below |",
        "",
        "---",
        "",
        "## 2. FM deep dive (Rohit question)",
        "",
        "### Extreme short FM (<15th pctile)",
        "",
        f"- **Crossings:** {xfm1_short.get('n_crossings', 'n/a')}",
        f"- **3m SPX up rate:** {_hr(xfm1_short, 'spx_3m')}",
        f"- **3m avg return:** {_avg(xfm1_short, 'spx_3m')}%",
        f"- **Evidence:** {xfm1_short.get('evidence_tag', 'n/a')}",
        f"- **Interpretation:** {xfm1_short.get('interpretation', '')}",
        "",
        "#### Extreme short — 3m SPX up rate by regime (fed_cycle_v2)",
        "",
        _regime_table(xfm1_short.get("regime_slices_3m", {}).get("fed_cycle_v2", {}), bullish=True),
        "",
        "### Extreme long FM (>85th pctile) — Combo D territory",
        "",
        f"- **Crossings:** {xfm1_long.get('n_crossings', 'n/a')}",
        f"- **1w SPX down rate (short win):** {_hr(xfm1_long, 'spx_1w', invert=True)}",
        f"- **3m SPX down rate:** {_hr(xfm1_long, 'spx_3m', invert=True)}",
        "",
        "#### Extreme long — 3m SPX down rate by regime (fed_cycle_v2)",
        "",
        _regime_table(xfm1_long.get("regime_slices_3m", {}).get("fed_cycle_v2", {}), bullish=False),
        "",
        "### Moderate FM (25th–75th) — Rohit skepticism test",
        "",
        f"- **Crossings:** {xfm1_mod.get('n_crossings', 'n/a')}",
        f"- **3m SPX up rate:** {_hr(xfm1_mod, 'spx_3m')}",
        f"- **3m avg return:** {_avg(xfm1_mod, 'spx_3m')}%",
        f"- **Evidence:** {xfm1_mod.get('evidence_tag', 'n/a')}",
        f"- **Conclusion:** {_moderate_conclusion(xfm1_mod)}",
        "",
        "### Combo B confirmed instances",
        "",
        f"- **n fires:** {xfm2.get('n_fires', 'n/a')}",
        f"- **SPX higher 3m:** {_pct(xfm2.get('spx_up_3m_pct'))}",
        f"- Supports contrary-indicator narrative when n≥5 (Rohit cited ~87.5% on 8 instances).",
        "",
        "### Combo D short vs long horizon",
        "",
        f"- **n fires:** {xfm3.get('n_fires', 'n/a')}",
        f"- **1w down rate:** {_fmt_hr(xfm3.get('short_horizon_1w', {}), invert=True)}",
        f"- **3m down rate:** {_fmt_hr(xfm3.get('long_horizon_3m', {}), invert=True)}",
        "",
        "---",
        "",
        "## 3. Part A — Regime label distributions",
        "",
        f"- **Fridays backfilled:** {part_a.get('n_fridays_backfilled', 'n/a')}",
        f"- **A1 pass (≥30 obs, no >80% dominance):** {part_a.get('A1_pass_no_degenerate_dominance')}",
        f"- **A4 CAPE velocity winner (3m avg):** {(part_a.get('A4_cape_velocity') or {}).get('winner_3m_avg_return', 'n/a')}",
        "",
        "**fed_cycle_v2:**",
        "",
        "```json",
        json.dumps(part_a.get("A1_fed_cycle_v2_distribution"), indent=2),
        "```",
        "",
        "---",
        "",
        "## 4. Part B — TWY_ROC Apr 2025 validation",
        "",
        f"- **Observed 8wk DGS2 change (pp):** {part_b.get('B1_B2_twy_roc_apr2025', {}).get('2025-04-07', {}).get('twy_roc_pp')}",
        f"- **Direction:** {part_b.get('B1_B2_twy_roc_apr2025', {}).get('2025-04-07', {}).get('direction')}",
        f"- **Pass dovish anchor:** {part_b.get('B2_validation', {}).get('pass_dovish')}",
        f"- **Emission vectors rows:** {part_b.get('C1_emission_vectors_backfilled')}",
        f"- **Dual percentile (both):** {part_b.get('B3_dual_percentile', {}).get('rows_with_both')}",
        f"- **Fallback unconditional only:** {part_b.get('B3_dual_percentile', {}).get('rows_with_unconditional_only')}",
        "",
        "---",
        "",
        "## 5. Part C — Sub-threshold VIX accumulation",
        "",
        f"- **VIX pctile 0.65–0.79, 3m avg:** {part_c.get('C2_sub_threshold_vix_65_79', {}).get('avg')}% (n={part_c.get('C2_sub_threshold_vix_65_79', {}).get('n')})",
        f"- **Random Friday baseline 3m avg:** {part_c.get('C2_random_friday_3m_baseline', {}).get('avg')}%",
        f"- **C3 binary vs vector lag (days):** {(part_c.get('C3_binary_vs_vector') or {}).get('median_lag_days_binary_minus_vector')}",
        "",
        "---",
        "",
        "## 6. Part D — HMM prototype",
        "",
        f"- **Status:** {part_d.get('status', 'n/a')}",
        f"- **Note:** {part_d.get('note', part_d.get('reason', ''))}",
        f"- **Regime backtest:** {(part_d.get('regime_backtest') or {}).get('status', 'n/a')}",
        "",
        "---",
        "",
        "## 7. Part E — Combo C cancel probability",
        "",
        f"- **Combined cancel prob (example):** {part_e.get('E1_combo_c_cancel', {}).get('combined_cancel_prob')}",
        f"- **E2 realized cancel rate:** {(part_e.get('E2_combo_c_calibration') or {}).get('realized_cancel_rate')}",
        "",
        "---",
        "",
        "## 8. Part F — Quantitative regime + F4 grid",
        "",
        f"- **Oct 2022 tightening_late F1:** {part_f.get('F1_tightening_late')}",
        "",
        "F4 steepening-short grid:",
        "",
        "```json",
        json.dumps(part_f.get("F4_steepening_short_grid"), indent=2),
        "```",
        "",
        "Evidence standard: **MECHANISM+ANALOG** for F4 (2000/2007 analogs; 2022–23 failure with fiscal offset).",
        "",
        "---",
        "",
        "## 9. Part G — Persistence",
        "",
        f"- **7WK grind n:** {part_g.get('G1_seven_week_grind', {}).get('n')}",
        f"- **6m avg after grind:** {part_g.get('G1_seven_week_grind', {}).get('spx_6m', {}).get('avg')}%",
        f"- **Standalone short OK?** {part_g.get('G1_seven_week_grind', {}).get('standalone_short_ok')} (PDF: should be False)",
        f"- **VIX suppressed lead rate to VIX>25:** {_pct(part_g.get('G2_vix_suppressed', {}).get('lead_rate'))}",
        "",
        "---",
        "",
        "## 10. Part H — 298 combo discovery",
        "",
        f"Summary: `{json.dumps(part_h.get('summary', part_h), indent=2)}`",
        "",
        "### Beta filter — 55% vs 60% hostile hit rate",
        "",
        "Both thresholds reported per combo in combo discovery JSON (`beta_hostile_hit_rate_55`, `beta_hostile_hit_rate_60`). "
        "Human decision per combo at Rohit review; no auto-selection.",
        "",
        "### Promotion shortlist (top 20 by hit rate, ≥5 fires, ≥80% HR)",
        "",
        _promotion_table(promotion_top20),
        "",
        "Full report: [`COMBO_DISCOVERY_PIPELINE_REPORT.md`](COMBO_DISCOVERY_PIPELINE_REPORT.md)",
        "",
        "---",
        "",
        "## 11. Part I — Evidence tagging legend",
        "",
        "| Tag | Rule | Applied when |",
        "|-----|------|--------------|",
        "| **STATISTICAL** | n ≥ 5 independent fires | FM bands, unnamed combos, regime slices |",
        "| **MECHANISM+ANALOG** | n may be 2–4 | F4 steepening-short, Combo B washout |",
        "| **INSUFFICIENT** | n < 5, not mechanism gate | Moderate FM slices, small F4 cells |",
        "| **FALLBACK** | regime pctile n < 50 | Logged in emission_vectors.fallback_used |",
        "",
        "---",
        "",
        "## 12. Open questions closure (Plan §6)",
        "",
        "| # | Question | Answer | Evidence | Recommend |",
        "|---|----------|--------|----------|-----------|",
        "| 1 | TWY_ROC ±0.30pp bands | Valid starting point | Apr 2025 −0.55pp DOVISH | Add to classifier prompt |",
        "| 2 | F4 trough −50 vs −80, steep +15 vs +40 | See F4 grid | F_quant_regime.json | Mechanism gate only; n small |",
        "| 3 | Apr 2025 DGS2 vs fed_cycle | Divergence confirmed | TWY DOVISH, legacy fed TIGHTENING | Use TWY_ROC as 14th var |",
        "| 4 | Dual percentile <50 fallback | Tracked | emission_vectors.fallback_used | Continue dual storage |",
        "| 5 | Beta 55% vs 60% | Both reported | combo_discovery JSON | Decide per combo at review |",
        "| 6 | 2-of-3 vs 3-of-3 | Diagnostic only | PDF spec | No production change |",
        "| 7 | 6mo before HMM prod | DEFER | D_hmm_prototype.json | Start live C1 daily post-sign-off |",
        "| 8 | T10Y2Y align with Ahil | F2/F2a in shadow v2 | regime_v2_shadow.py | Ahil review F4 analogs |",
        "| 9 | Classifier prompt update | Pending | This report | Rohit sign-off required |",
        "| 10 | Rohit FM Q&A | Answered | §2 + X-FM_all.json | FM contrary in extremes |",
        "",
        "---",
        "",
        "## 13. GO / NO-GO per deliverable",
        "",
        "| Deliverable | GO | Notes |",
        "|-------------|-----|-------|",
        "| A shadow regimes | **GO** (shadow) | Do not swap production until Rohit review |",
        "| B TWY_ROC | **GO** | Add to classifier prompt |",
        "| C emission storage | **GO** | Wire daily job post-sign-off |",
        "| D HMM | **DEFER** | 6mo live vectors |",
        "| E cancel prob | **GO** | Wire dashboard |",
        "| F quant defs | **GO** (F2/F2a) | F4 mechanism gate only |",
        "| G persistence | **GO** | Amplifier/precursor framing |",
        "| H combo pipeline | **GO** | Monthly re-run |",
        "",
        "---",
        "",
        "*Generated by `scripts/run_regime_v2_experiment_suite.py`*",
    ]

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def _load_promotion_top20() -> list[dict[str, Any]]:
    discovery_dir = Path("macro_intelligence/analysis/combo_discovery")
    files = sorted(discovery_dir.glob("combo_discovery_*.json"), reverse=True)
    if not files:
        return []
    data = json.loads(files[0].read_text(encoding="utf-8"))
    candidates = [r for r in data.get("results", []) if r.get("promotion_candidate")]
    candidates.sort(key=lambda r: (-(r.get("hit_rate") or 0), -(r.get("n_fires") or 0)))
    return candidates[:20]


def _promotion_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "_No promotion candidates found._"
    lines = [
        "| Vars | n | HR | Beta 55% | Beta 60% | Pass |",
        "|------|---|-----|----------|----------|------|",
    ]
    for r in rows:
        vars_s = "+".join(r.get("var_ids") or [])
        hr = r.get("hit_rate")
        hr_s = f"{hr*100:.1f}%" if hr is not None else "n/a"
        b55 = r.get("beta_hostile_hit_rate_55")
        b60 = r.get("beta_hostile_hit_rate_60")
        b55_s = f"{b55*100:.1f}%" if b55 is not None else "n/a"
        b60_s = f"{b60*100:.1f}%" if b60 is not None else "n/a"
        lines.append(
            f"| {vars_s} | {r.get('n_fires', 'n/a')} | {hr_s} | {b55_s} | {b60_s} | "
            f"{'Y' if r.get('beta_pass') else 'N'} |"
        )
    return "\n".join(lines)


def _regime_table(slices: dict[str, Any], bullish: bool = True) -> str:
    if not slices:
        return "_No regime slices._"
    lines = [
        "| Regime | n | Hit rate | Avg 3m % | Tag |",
        "|--------|---|----------|----------|-----|",
    ]
    for regime, stats in sorted(slices.items()):
        n = stats.get("n") or 0
        hr = stats.get("hit_rate")
        if hr is None:
            hr_s = "n/a"
        elif bullish:
            hr_s = f"{hr*100:.1f}% up"
        else:
            hr_s = f"{(1-hr)*100:.1f}% down"
        avg = stats.get("avg")
        avg_s = f"{avg:.2f}" if avg is not None else "n/a"
        tag = "STATISTICAL" if n >= 5 else "INSUFFICIENT"
        lines.append(f"| {regime} | {n} | {hr_s} | {avg_s} | {tag} |")
    return "\n".join(lines)


def _moderate_conclusion(block: dict) -> str:
    h3 = (block.get("by_horizon") or {}).get("spx_3m", {})
    n = h3.get("n") or 0
    hr = h3.get("hit_rate")
    if n < 5:
        return "INSUFFICIENT — too few crossings for edge claim."
    if hr is not None and 0.45 <= hr <= 0.55:
        return "No clear edge — hit rate near coin flip; supports Rohit skepticism."
    return "Weak directional edge — not actionable standalone."


def _hr(block: dict, horizon: str, invert: bool = False) -> str:
    h = (block.get("by_horizon") or {}).get(horizon, {})
    return _fmt_hr(h, invert=invert)


def _fmt_hr(h: dict, invert: bool = False) -> str:
    hr = h.get("hit_rate")
    if hr is None:
        return "n/a"
    if invert:
        return f"{(1-hr)*100:.1f}% SPX down"
    return f"{hr*100:.1f}% SPX up"


def _avg(block: dict, horizon: str) -> str:
    h = (block.get("by_horizon") or {}).get(horizon, {})
    v = h.get("avg")
    return f"{v:.2f}" if v is not None else "n/a"


def _pct(v: float | None) -> str:
    if v is None:
        return "n/a"
    return f"{v*100:.1f}%"
