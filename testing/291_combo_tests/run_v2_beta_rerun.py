#!/usr/bin/env python3
"""Re-run Part H funnel with v2 regimes; compare before/after beta + shortlist impact."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.analysis.combo_discovery_pipeline import (  # noqa: E402
    _discovery_cfg,
    _evaluate_signature,
    _group_fires_by_signature,
    combo_signature,
    enumerate_all_signatures,
    load_generic_fires,
)
from src.macro_intelligence.analysis.regime_v2_enrich import retag_combo_fires_in_db  # noqa: E402

OUT = Path(__file__).resolve().parent

SHORTLIST = [
    "CURVE+WALCL",
    "CNH+VIX",
    "CNH+GSR+WTI",
    "CFTC+VIX+VXTS",
    "CAPE+VIX+VXTS",
    "CURVE+GSR+WALCL",
    "CNH+CURVE+WALCL",
    "CAPE+HY",
]


def _run(enrich_v2: bool) -> dict:
    cfg = _discovery_cfg()
    all_sigs = enumerate_all_signatures()
    all_fires = load_generic_fires(enrich_v2=enrich_v2)
    grouped = _group_fires_by_signature(all_fires)
    results = []
    for var_ids in all_sigs:
        sig = combo_signature(var_ids)
        fires = grouped.get(sig, [])
        results.append(_evaluate_signature(var_ids, fires, all_fires, cfg))
    promos = [r for r in results if r.promotion_candidate]
    survivors = [r for r in results if r.gate_stage == "survivor"]
    surfaced = [r for r in results if r.surfaced]
    hostile_nonnull = sum(1 for r in survivors if r.beta_hostile_hit_rate_55 is not None)
    return {
        "summary": {
            "surfaced": len(surfaced),
            "beta_pass": sum(1 for r in results if r.beta_pass),
            "survivors": len(survivors),
            "promotion_candidates": len(promos),
            "hostile_hr_computed": hostile_nonnull,
        },
        "by_sig": {r.signature: r for r in results},
        "promos": promos,
    }


def main() -> None:
    before = _run(enrich_v2=False)
    retag_stats = retag_combo_fires_in_db(generic_only=True)
    after = _run(enrich_v2=True)

    # baselines from after run fires
    all_fires = load_generic_fires(enrich_v2=True)
    vals = [f.returns["spx_3m"] for f in all_fires if f.returns.get("spx_3m") is not None]
    uncond_avg = sum(vals) / len(vals) if vals else 0.0
    hostile_n = sum(
        1
        for f in all_fires
        if f.regime.get("fed_cycle_v2") == "TIGHTENING"
        or f.regime.get("curve_regime_v2") == "INVERTED"
        or "TIGHTENING" in str(f.regime.get("fed_cycle", ""))
        or f.regime.get("curve_regime") == "INVERTED"
    )

    comparison_rows = []
    for sig in sorted(
        set(before["by_sig"]) | set(after["by_sig"]),
        key=lambda s: (
            -(after["by_sig"].get(s) and after["by_sig"][s].primary_hit_rate or 0),
            -(after["by_sig"].get(s) and after["by_sig"][s].n_fires or 0),
        ),
    ):
        b = before["by_sig"].get(sig)
        a = after["by_sig"].get(sig)
        if not a or a.n_fires == 0:
            continue
        comparison_rows.append(
            {
                "signature": sig,
                "n_fires": a.n_fires,
                "hit_rate_3m": a.primary_hit_rate,
                "avg_3m": a.primary_avg_return,
                "beta_pass_before": b.beta_pass if b else False,
                "beta_pass_after": a.beta_pass,
                "hostile_hr_after": a.beta_hostile_hit_rate_55,
                "beats_uncond": a.beta_beats_unconditional,
                "beats_single": a.beta_beats_single_var,
                "beats_regime": a.beta_beats_regime_base,
                "promo_before": bool(b and b.promotion_candidate),
                "promo_after": a.promotion_candidate,
                "gate_after": a.gate_stage,
                "dir_dims": a.directionality_dims_passing,
            }
        )

    # promo delta
    promo_before = {r.signature for r in before["promos"]}
    promo_after = {r.signature for r in after["promos"]}
    dropped = sorted(promo_before - promo_after)
    gained = sorted(promo_after - promo_before)

    shortlist_rows = []
    for sig in SHORTLIST:
        a = after["by_sig"].get(sig)
        if not a:
            continue
        fires = _group_fires_by_signature(all_fires).get(sig, [])
        from src.macro_intelligence.analysis.combo_discovery_pipeline import _is_hostile

        cfg = _discovery_cfg()
        h_fires = [f for f in fires if _is_hostile(f.regime, cfg)]
        h_vals = [f.returns["spx_3m"] for f in h_fires if f.returns.get("spx_3m") is not None]
        shortlist_rows.append(
            {
                "signature": sig,
                "n_fires": a.n_fires,
                "hit_rate_3m": a.primary_hit_rate,
                "avg_3m": a.primary_avg_return,
                "beta_pass": a.beta_pass,
                "hostile_n": len(h_fires),
                "hostile_hr": a.beta_hostile_hit_rate_55,
                "hostile_avg_3m": round(sum(h_vals) / len(h_vals), 4) if h_vals else None,
                "promotion_candidate": a.promotion_candidate,
                "gate_stage": a.gate_stage,
                "beats_unconditional": a.beta_beats_unconditional,
                "beats_single_var": a.beta_beats_single_var,
                "beats_regime_base": a.beta_beats_regime_base,
            }
        )

    payload = {
        "retag_stats": retag_stats,
        "unconditional_avg_spx_3m": round(uncond_avg, 4),
        "generic_fires_with_hostile_tag": hostile_n,
        "funnel_before_no_v2": before["summary"],
        "funnel_after_v2": after["summary"],
        "promotion_dropped": dropped,
        "promotion_gained": gained,
        "shortlist": shortlist_rows,
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "v2_beta_rerun_summary.json").write_text(json.dumps(payload, indent=2))

    with open(OUT / "v2_promotion_comparison.csv", "w", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "signature",
                "n_fires",
                "hit_rate_3m",
                "avg_3m",
                "beta_pass_before",
                "beta_pass_after",
                "hostile_hr_after",
                "beats_uncond",
                "beats_single",
                "beats_regime",
                "promo_before",
                "promo_after",
                "gate_after",
                "dir_dims",
            ],
        )
        w.writeheader()
        for row in comparison_rows:
            if row["promo_before"] or row["promo_after"] or row["beta_pass_before"] != row["beta_pass_after"]:
                w.writerow(row)

    with open(OUT / "v2_shortlist_beta.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(shortlist_rows[0].keys()) if shortlist_rows else [])
        if shortlist_rows:
            w.writeheader()
            w.writerows(shortlist_rows)

    # markdown report
    lines = [
        "# Part H Beta Re-run with v2 Shadow Regimes",
        "",
        f"**Unconditional baseline (all generic fires, spx_3m avg):** {uncond_avg:.2f}%",
        f"**Generic fires retagged:** {retag_stats}",
        f"**Fires in hostile regimes (TIGHTENING fed or INVERTED curve):** {hostile_n}",
        "",
        "## Funnel before vs after",
        "",
        "| Stage | Before (no v2) | After (v2) |",
        "|-------|----------------:|-----------:|",
    ]
    for key in ("surfaced", "beta_pass", "survivors", "promotion_candidates"):
        lines.append(
            f"| {key} | {before['summary'][key]} | {after['summary'][key]} |"
        )
    lines.append(f"| hostile_hr_computed (survivors) | {before['summary']['hostile_hr_computed']} | {after['summary']['hostile_hr_computed']} |")
    lines.extend(
        [
            "",
            f"**Dropped from promotion ({len(dropped)}):** " + (", ".join(dropped) if dropped else "none"),
            f"**Gained promotion ({len(gained)}):** " + (", ".join(gained) if gained else "none"),
            "",
            "## 8-theme shortlist after v2 beta",
            "",
            "| Signature | n | HR | hostile n | hostile HR | beta pass | promo |",
            "|-----------|--:|---:|----------:|-----------:|----------:|------:|",
        ]
    )
    for r in shortlist_rows:
        hr = r["hostile_hr"]
        hr_s = f"{hr:.1%}" if hr is not None else "n/a"
        lines.append(
            f"| {r['signature']} | {r['n_fires']} | {r['hit_rate_3m']:.1%} | {r['hostile_n']} | {hr_s} | {r['beta_pass']} | {r['promotion_candidate']} |"
        )
    (OUT / "ANALYSIS_REPORT_v2_beta.md").write_text("\n".join(lines) + "\n")

    print(json.dumps(payload["funnel_after_v2"], indent=2))
    print("Dropped promos:", len(dropped))
    print("Wrote", OUT / "ANALYSIS_REPORT_v2_beta.md")


if __name__ == "__main__":
    main()
