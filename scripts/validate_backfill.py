#!/usr/bin/env python3
"""Post-backfill validation report."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.analysis.combo_threshold_sweep import hit_rate_for_combo
from src.macro_intelligence.db.connection import get_connection, init_db
from src.macro_intelligence.engine.fed_cycle import fed_cycle_at_date
from src.macro_intelligence.engine.hit_rates import regime_adjusted_hit_rate, raw_hit_rate

FED_FIXTURES = {
    "2022-10-13": "HIKING_LATE",
    "2020-03-23": "QE",
    "2020-06-29": "QE",
    "2015-12-16": "HIKING_EARLY",
    "2024-09-18": "CUTTING_EARLY",
}


def main() -> int:
    init_db()
    report: dict = {"fed_fixtures": {}, "counts": {}, "hit_rates": {}}

    with get_connection() as conn:
        report["counts"]["macro_regime_log"] = conn.execute(
            "SELECT COUNT(*) FROM macro_regime_log"
        ).fetchone()[0]
        report["counts"]["combo_fires"] = conn.execute(
            "SELECT COUNT(*) FROM combo_fires"
        ).fetchone()[0]
        report["counts"]["combo_fires_with_regime"] = conn.execute(
            "SELECT COUNT(*) FROM combo_fires WHERE macro_regime IS NOT NULL AND macro_regime != ''"
        ).fetchone()[0]
        report["counts"]["forward_returns"] = conn.execute(
            "SELECT COUNT(*) FROM forward_returns WHERE spx_3m IS NOT NULL"
        ).fetchone()[0]
        dupes = conn.execute(
            "SELECT COUNT(*) FROM (SELECT date FROM macro_regime_log GROUP BY date HAVING COUNT(*) > 1)"
        ).fetchone()[0]
        report["counts"]["regime_duplicate_dates"] = dupes

    for date, expected in FED_FIXTURES.items():
        actual, src = fed_cycle_at_date(date)
        report["fed_fixtures"][date] = {
            "expected": expected,
            "actual": actual,
            "source": src,
            "ok": actual == expected,
        }

    for combo in ("B", "F"):
        hr = hit_rate_for_combo(combo, bullish=True)
        report["hit_rates"][combo] = hr

    report["regime_adjusted_B_cut"] = regime_adjusted_hit_rate("B", "CUT%")
    report["regime_adjusted_B_hike"] = regime_adjusted_hit_rate("B", "HIK%")

    out = ROOT / "macro_intelligence/output/backfill_validation.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
