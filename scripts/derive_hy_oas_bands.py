#!/usr/bin/env python3
"""Re-derive the HY OAS credit-multiplier bands from the real ICE series.

Rohit 6 Aug on the ceiling table: "HY OAS bands: NEITHER. Re-derive."

The current 300 / 500 / 700bp bands were never derived from data. Now that the HY history is
real ICE BofA OAS back to Dec 1996 (not the old BAA10Y+VIX proxy), the distribution can speak.
This script reports where the empirical breakpoints actually fall and what share of history
each candidate band covers.

Output is a PROPOSAL for Rohit's sign-off. It changes no thresholds and no live behaviour.

    PYTHONPATH=. .venv/bin/python scripts/derive_hy_oas_bands.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.db.connection import get_connection  # noqa: E402

OUT_PATH = ROOT / "macro_intelligence" / "analysis" / "hy_oas_band_derivation.json"
CURRENT_BANDS_BPS = [300, 500, 700]
CURRENT_MULTS = {"<300": 1.00, "300-500": 0.90, "500-700": 0.80, ">700": 0.70}
PERCENTILES = [50, 60, 70, 75, 80, 85, 90, 95, 97.5, 99]


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return float("nan")
    k = (len(sorted_values) - 1) * pct / 100.0
    lo, hi = int(k), min(int(k) + 1, len(sorted_values) - 1)
    if lo == hi:
        return sorted_values[lo]
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (k - lo)


def main() -> None:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT date, raw_value, signal_tier
               FROM daily_readings
               WHERE var_id='HY' AND raw_value IS NOT NULL
               ORDER BY date"""
        ).fetchall()

    if not rows:
        print("No HY readings found — cannot derive bands.")
        return

    real = [r for r in rows if (r["signal_tier"] or "").upper() != "PROXY"]
    proxy_count = len(rows) - len(real)
    # raw_value is stored as a PERCENTAGE (2.66 = 266bps).
    bps = sorted(float(r["raw_value"]) * 100 for r in real)
    dates = [str(r["date"]) for r in real]

    print(f"HY observations total     : {len(rows)}")
    print(f"  real ICE OAS            : {len(real)}  ({dates[0]} to {dates[-1]})")
    print(f"  excluded as PROXY       : {proxy_count}")
    print()
    print(f"min {bps[0]:.0f}bps   median {_percentile(bps, 50):.0f}bps   max {bps[-1]:.0f}bps")
    print()
    print("Empirical distribution (real data only):")
    pct_table = {}
    for pct in PERCENTILES:
        value = _percentile(bps, pct)
        pct_table[str(pct)] = round(value, 1)
        print(f"  p{pct:<5} {value:8.0f} bps")
    print()

    print("Coverage of the CURRENT bands:")
    current_rows = []
    prev = 0
    for edge in CURRENT_BANDS_BPS:
        share = sum(1 for b in bps if prev <= b < edge) / len(bps)
        label = f"{prev}-{edge}" if prev else f"<{edge}"
        current_rows.append({"band": label, "share_pct": round(share * 100, 2)})
        print(f"  {label:>10} bps : {share:7.2%} of history")
        prev = edge
    tail = sum(1 for b in bps if b >= CURRENT_BANDS_BPS[-1]) / len(bps)
    current_rows.append({"band": f">{CURRENT_BANDS_BPS[-1]}", "share_pct": round(tail * 100, 2)})
    print(f"  {'>' + str(CURRENT_BANDS_BPS[-1]):>10} bps : {tail:7.2%} of history")
    print()

    # A percentile-anchored alternative: cut where the distribution actually thins out.
    proposal = {
        "benign_below": round(_percentile(bps, 50), -1),
        "mild_below": round(_percentile(bps, 80), -1),
        "stress_below": round(_percentile(bps, 95), -1),
    }
    print("PERCENTILE-ANCHORED PROPOSAL (for sign-off, not applied):")
    print(f"  benign   : < {proposal['benign_below']:.0f} bps   (below median)")
    print(f"  mild     : {proposal['benign_below']:.0f}-{proposal['mild_below']:.0f} bps   (median to p80)")
    print(f"  stress   : {proposal['mild_below']:.0f}-{proposal['stress_below']:.0f} bps   (p80 to p95)")
    print(f"  crisis   : > {proposal['stress_below']:.0f} bps   (above p95)")
    print()
    print("  Why this shape: each band then holds a known share of history (50 / 30 / 15 / 5),")
    print("  so the multiplier attached to it is calibrated against something. The current")
    print("  300/500/700 edges were not derived from this distribution.")
    print()

    # How many days would change band under the proposal?
    def band_of(value: float, edges: list[float]) -> int:
        return sum(1 for e in edges if value >= e)

    current_edges = [float(e) for e in CURRENT_BANDS_BPS]
    proposed_edges = [
        float(proposal["benign_below"]),
        float(proposal["mild_below"]),
        float(proposal["stress_below"]),
    ]
    changed = sum(1 for b in bps if band_of(b, current_edges) != band_of(b, proposed_edges))
    print(f"Days that would change band: {changed} of {len(bps)} ({changed/len(bps):.1%})")
    print()
    print("NOTE: today's live ceiling only ever reads TODAY's HY value, so this is a")
    print("      historical-calibration question, not an immediate live-behaviour change.")

    payload = {
        "observations_total": len(rows),
        "observations_real": len(real),
        "observations_proxy_excluded": proxy_count,
        "date_range": [dates[0], dates[-1]],
        "min_bps": round(bps[0], 1),
        "max_bps": round(bps[-1], 1),
        "percentiles_bps": pct_table,
        "current_bands_bps": CURRENT_BANDS_BPS,
        "current_multipliers": CURRENT_MULTS,
        "current_band_coverage": current_rows,
        "percentile_anchored_proposal_bps": proposal,
        "days_changing_band": changed,
        "days_changing_band_pct": round(changed / len(bps) * 100, 2),
        "status": "PROPOSAL — awaiting Rohit sign-off, no thresholds changed",
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2))
    print(f"\nWrote {OUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
