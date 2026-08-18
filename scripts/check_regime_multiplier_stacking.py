#!/usr/bin/env python3
"""How often do TIGHTENING and INVERTED co-occur, and what does the stacked cut look like?

Rohit 6 Aug: "TIGHTENING is x0.82 and INVERTED is x0.78. Multiply them and you're at 0.64 — a
36% cut — before any other overlay has touched the book. And those two states go together
often: the Fed tightens, the curve inverts. So that isn't a rare combination, it's a normal
one. Check what the combined cut looks like across history before signing either number."

Read-only. Prints a report and writes JSON next to the other regime-uplift outputs.

    PYTHONPATH=. .venv/bin/python scripts/check_regime_multiplier_stacking.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.output.regime_feed_export import (  # noqa: E402
    CURVE_MULT,
    FED_MULT,
    MAX_MULT,
    MIN_MULT,
    MULTIPLIER_VERSION,
    regime_feed_as_records,
)

OUT_PATH = ROOT / "testing" / "5_regime_uplift" / "output_files" / "multiplier_stacking_check.json"


def main() -> None:
    rows = regime_feed_as_records()
    if not rows:
        print("No regime rows available — nothing to check.")
        return

    # One row per evaluation Friday, so a long forward-filled stretch is not counted repeatedly.
    fridays: dict[str, dict] = {}
    for row in rows:
        fridays.setdefault(str(row.get("evaluation_date")), row)
    evals = list(fridays.values())
    n = len(evals)

    tightening = [r for r in evals if r["fed_cycle_v2"] == "TIGHTENING"]
    inverted = [r for r in evals if r["curve_regime_v2"] == "INVERTED"]
    both = [
        r
        for r in evals
        if r["fed_cycle_v2"] == "TIGHTENING" and r["curve_regime_v2"] == "INVERTED"
    ]

    m_tight = FED_MULT["TIGHTENING"]
    m_inv = CURVE_MULT["INVERTED"]
    stacked = m_tight * m_inv

    # Independence check: if the states were independent, P(both) = P(a) x P(b).
    p_tight = len(tightening) / n
    p_inv = len(inverted) / n
    expected_if_independent = p_tight * p_inv * n

    print(f"Regime evaluations (Fridays): {n}")
    print(f"multiplier_version: {MULTIPLIER_VERSION}")
    print()
    print(f"TIGHTENING           : {len(tightening):5d}  ({p_tight:6.2%})  mult x{m_tight}")
    print(f"INVERTED             : {len(inverted):5d}  ({p_inv:6.2%})  mult x{m_inv}")
    print(f"BOTH                 : {len(both):5d}  ({len(both)/n:6.2%})  stacked x{stacked:.4f}"
          f"  =  {(1-stacked)*100:.1f}% cut")
    print(f"  expected if independent: {expected_if_independent:.1f} Fridays")
    if expected_if_independent > 0:
        ratio = len(both) / expected_if_independent
        verdict = "MORE often than independence implies" if ratio > 1.2 else (
            "about as often as independence implies" if ratio > 0.8 else
            "LESS often than independence implies"
        )
        print(f"  observed / expected    : {ratio:.2f}x — they co-occur {verdict}")
    print()

    if both:
        dates = sorted(str(r["evaluation_date"]) for r in both)
        print(f"  first co-occurrence: {dates[0]}   last: {dates[-1]}")
        years = Counter(d[:4] for d in dates)
        print(f"  by year: {dict(sorted(years.items()))}")
        print()

    # What does the full 5-dimension product actually reach on those days?
    if both:
        gross = sorted(float(r["gross_mult"]) for r in both)
        print("  gross_mult on co-occurrence Fridays (all 5 dimensions, clipped):")
        print(f"    min {gross[0]:.4f}  median {gross[len(gross)//2]:.4f}  max {gross[-1]:.4f}")
        at_floor = sum(1 for g in gross if abs(g - MIN_MULT) < 1e-9)
        print(f"    pinned at the {MIN_MULT} floor: {at_floor} of {len(gross)}")
        print()

    all_gross = sorted(float(r["gross_mult"]) for r in evals)
    at_floor_all = sum(1 for g in all_gross if abs(g - MIN_MULT) < 1e-9)
    at_ceiling_all = sum(1 for g in all_gross if abs(g - MAX_MULT) < 1e-9)
    print("  gross_mult across ALL Fridays:")
    print(f"    min {all_gross[0]:.4f}  median {all_gross[len(all_gross)//2]:.4f}  max {all_gross[-1]:.4f}")
    print(f"    at floor {MIN_MULT}: {at_floor_all}   at ceiling {MAX_MULT}: {at_ceiling_all}")
    print()
    print("  NOTE: the clip is one-sided (max 1.00) while VIX and SSI reach 1.20, so this")
    print("        overlay can only ever shrink the book. Unchanged pending sign-off.")

    payload = {
        "multiplier_version": MULTIPLIER_VERSION,
        "n_evaluations": n,
        "tightening_count": len(tightening),
        "inverted_count": len(inverted),
        "both_count": len(both),
        "both_pct": round(len(both) / n * 100, 2),
        "expected_if_independent": round(expected_if_independent, 2),
        "m_tightening": m_tight,
        "m_inverted": m_inv,
        "stacked_mult": round(stacked, 4),
        "stacked_cut_pct": round((1 - stacked) * 100, 2),
        "both_dates": sorted(str(r["evaluation_date"]) for r in both),
        "gross_mult_all": {
            "min": all_gross[0],
            "median": all_gross[len(all_gross) // 2],
            "max": all_gross[-1],
            "at_floor": at_floor_all,
            "at_ceiling": at_ceiling_all,
        },
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2))
    print(f"\nWrote {OUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
