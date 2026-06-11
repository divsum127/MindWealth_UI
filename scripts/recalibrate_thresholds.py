#!/usr/bin/env python3
"""Annual / on-demand Runic threshold review (Combo B/F priority)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.analysis.combo_threshold_sweep import (  # noqa: E402
    hit_rate_for_combo,
    suggest_threshold_changes,
)
from src.macro_intelligence.db.connection import get_connection, init_db


def _log_suggestions(findings: list[dict]) -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    with get_connection() as conn:
        for f in findings:
            conn.execute(
                """
                INSERT INTO threshold_review_log (review_date, combo_key, suggestion_json, status)
                VALUES (?, ?, ?, 'PENDING')
                """,
                (today, f.get("combo", "?"), json.dumps(f)),
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Runic threshold recalibration")
    parser.add_argument("--confirm", action="store_true", help="Log only; CONFIG edit is manual")
    parser.add_argument("--json", action="store_true", help="Print JSON summary")
    args = parser.parse_args()

    init_db()
    findings = suggest_threshold_changes()
    stats = {
        "B": hit_rate_for_combo("B"),
        "F": hit_rate_for_combo("F"),
    }
    out = {"stats": stats, "findings": findings, "confirm": args.confirm}
    _log_suggestions(findings)

    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print("Threshold review logged to threshold_review_log (PENDING)")
        for k, v in stats.items():
            print(f"  {k}: n={v['n_obs']} hit_rate={v['hit_rate']} avg_3m={v['avg_return']}")
        if not args.confirm:
            print("Edit macro_intelligence/CONFIG.yaml manually after Rohit approval.")


if __name__ == "__main__":
    main()
