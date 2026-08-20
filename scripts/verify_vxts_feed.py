#!/usr/bin/env python3
"""Verify the stored VXTS term-structure ratio against independently fetched VIX / VIX3M closes.

Rohit 6 Aug, on the U-shaped ladder proposal: "VXTS (USE PRIOR DAY ACCURATE CLOSING LEVELS
FOR VIX AND VIX3M TO CALCULATE THIS - TEST TO SEE THE FEED IS RIGHT - WHEN I MET A HEDGE
FUND, OUR FEED WAS WRONG)."

There are TWO reciprocal conventions in this codebase, both deliberate inside their own
module, both called some form of "VXTS":

  * macro  `yahoo_pull.vix_term_structure()`  = VIX3M / VIX  (>1 contango)   -> daily_readings.VXTS
  * SSI    `yahoo_inputs.vix_ratio_series()`  = VIX  / VIX3M  (>1 backwardation)

Rohit's ladder proposal says "VXTS below 1.0 (backwardation)", which is the SSI convention,
while Combo D's VXTS>=1.18 gate reads the macro series. Same name, reciprocal scales, opposite
meaning at the 1.0 crossing — so this script recomputes BOTH from Yahoo closes, reports which
convention the stored series actually matches, and only calls a deviation a fault once the
convention is pinned.

Read-only. Prints a report and writes JSON under macro_intelligence/analysis/.

    PYTHONPATH=. .venv/bin/python scripts/verify_vxts_feed.py [--days 250]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.data.yahoo_pull import fetch_yahoo_close  # noqa: E402
from src.macro_intelligence.db.connection import get_connection  # noqa: E402

OUT_PATH = ROOT / "macro_intelligence" / "analysis" / "vxts_feed_verification.json"
BACKWARDATION_THRESHOLD = 1.0
# Deviations above this are worth a look; the ratio is dimensionless and normally ~0.85-1.15.
TOLERANCE = 0.005


def main() -> None:
    parser = argparse.ArgumentParser(description="VXTS feed verification")
    parser.add_argument("--days", type=int, default=250, help="trading days to check")
    args = parser.parse_args()

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT date, raw_value FROM daily_readings WHERE var_id='VXTS' ORDER BY date DESC LIMIT ?",
            (args.days,),
        ).fetchall()
    stored = {str(r["date"]): float(r["raw_value"]) for r in rows if r["raw_value"] is not None}
    if not stored:
        print("No stored VXTS readings — nothing to verify.")
        return

    vix = fetch_yahoo_close("^VIX", start="2015-01-01").dropna()
    vix3m = fetch_yahoo_close("^VIX3M", start="2015-01-01").dropna()
    if vix.empty or vix3m.empty:
        print("Could not fetch ^VIX / ^VIX3M — verification inconclusive.")
        return

    vix_by_date = {d.date().isoformat(): float(v) for d, v in vix.items()}
    vix3m_by_date = {d.date().isoformat(): float(v) for d, v in vix3m.items()}

    compared: list[dict] = []
    for date, stored_value in sorted(stored.items()):
        v, v3 = vix_by_date.get(date), vix3m_by_date.get(date)
        if v is None or v3 is None or v3 == 0 or v == 0:
            continue
        macro_convention = v3 / v   # VIX3M / VIX  — what daily_readings.VXTS should hold
        ssi_convention = v / v3     # VIX  / VIX3M — Rohit's ladder / SSI convention
        dev_macro = abs(stored_value - macro_convention)
        dev_ssi = abs(stored_value - ssi_convention)
        matches = "macro_vix3m_over_vix" if dev_macro <= dev_ssi else "ssi_vix_over_vix3m"
        deviation = min(dev_macro, dev_ssi)
        compared.append({
            "date": date,
            "stored": round(stored_value, 6),
            "macro_convention": round(macro_convention, 6),
            "ssi_convention": round(ssi_convention, 6),
            "matches_convention": matches,
            "vix": round(v, 4),
            "vix3m": round(v3, 4),
            "abs_deviation": round(deviation, 6),
            # Only meaningful once the convention is pinned: does the stored value sit on the
            # same side of 1.0 as the convention it claims to follow?
            "threshold_disagreement": (
                (stored_value < BACKWARDATION_THRESHOLD)
                != (macro_convention < BACKWARDATION_THRESHOLD)
            ),
        })

    if not compared:
        print("No overlapping dates between the stored series and the Yahoo closes.")
        return

    worst = sorted(compared, key=lambda r: -r["abs_deviation"])
    flips = [r for r in compared if r["threshold_disagreement"]]
    over_tol = [r for r in compared if r["abs_deviation"] > TOLERANCE]
    macro_matched = [r for r in compared if r["matches_convention"] == "macro_vix3m_over_vix"]
    ssi_matched = [r for r in compared if r["matches_convention"] == "ssi_vix_over_vix3m"]

    print(f"Dates compared                     : {len(compared)}")
    print(f"Stored matches macro (VIX3M/VIX)   : {len(macro_matched)}")
    print(f"Stored matches SSI  (VIX/VIX3M)    : {len(ssi_matched)}")
    print(f"Max deviation vs its own convention: {worst[0]['abs_deviation']:.6f}"
          f"  on {worst[0]['date']}")
    print(f"Deviations above {TOLERANCE}             : {len(over_tol)}")
    print(f"Cross-1.0 disagreements            : {len(flips)}")
    print()
    print("Worst 10 deviations (against the convention each row matches):")
    header = f"  {'date':<12} {'stored':>9} {'VIX3M/VIX':>10} {'VIX/VIX3M':>10} {'dev':>9}  matches"
    print(header)
    for r in worst[:10]:
        print(
            f"  {r['date']:<12} {r['stored']:>9.4f} {r['macro_convention']:>10.4f} "
            f"{r['ssi_convention']:>10.4f} {r['abs_deviation']:>9.5f}  {r['matches_convention']}"
        )

    print()
    if len(macro_matched) == len(compared):
        verdict = "PASS" if not over_tol else "REVIEW"
        print("Stored VXTS follows the macro convention (VIX3M / VIX) on every compared date,")
        print("consistent with Combo D's VXTS>=1.18 complacency gate and Combo G's <=0.95.")
    elif len(ssi_matched) == len(compared):
        verdict = "FAIL"
        print("Stored VXTS follows the SSI convention (VIX / VIX3M) on every compared date,")
        print("which is the RECIPROCAL of what Combo D's gate expects.")
    else:
        verdict = "FAIL"
        print("Stored VXTS switches convention mid-series — the worst possible outcome, because")
        print("every gate reading spans two incompatible scales.")

    print()
    print("CONVENTION COLLISION (report this regardless of verdict):")
    print("  Rohit's U-shaped ladder spec says 'VXTS below 1.0 (backwardation)', which is the")
    print("  SSI convention (VIX/VIX3M). Combo D's VXTS>=1.18 gate reads the macro series")
    print("  (VIX3M/VIX). The same name means reciprocal things in the two paths, so a ladder")
    print("  built on the wrong one inverts the trigger. Pin one convention before building.")
    print()
    print(f"VERDICT: {verdict}")

    payload = {
        "days_requested": args.days,
        "dates_compared": len(compared),
        "tolerance": TOLERANCE,
        "n_matching_macro_convention": len(macro_matched),
        "n_matching_ssi_convention": len(ssi_matched),
        "max_abs_deviation": worst[0]["abs_deviation"],
        "max_abs_deviation_date": worst[0]["date"],
        "n_over_tolerance": len(over_tol),
        "n_cross_threshold_disagreements": len(flips),
        "worst_10": worst[:10],
        "verdict": verdict,
        "convention_collision": {
            "macro_series": "daily_readings.VXTS = VIX3M / VIX (>1 contango); Combo D >=1.18, Combo G <=0.95",
            "ssi_series": "yahoo_inputs.vix_ratio_series = VIX / VIX3M (>1 backwardation)",
            "rohit_ladder_spec": "'VXTS below 1.0 (backwardation)' — the SSI convention",
            "risk": "a ladder built on the macro series inverts the intended trigger",
        },
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2))
    print(f"\nWrote {OUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
