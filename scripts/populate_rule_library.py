#!/usr/bin/env python3
"""Populate rule_library from backfilled combo hit rates."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.analysis.combo_threshold_sweep import hit_rate_for_combo
from src.macro_intelligence.db.connection import get_connection, init_db


def main() -> int:
    init_db()
    combos = ["A", "B", "C", "D", "E", "F", "G"]
    with get_connection() as conn:
        conn.execute("DELETE FROM rule_library")
        for combo in combos:
            bullish = combo in ("B", "F")
            hr = hit_rate_for_combo(combo, bullish=bullish)
            conn.execute(
                """
                INSERT INTO rule_library (rule_name, signal_condition, n_obs, hit_rate, avg_return_3m, regime_hit_rates)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    f"Combo_{combo}",
                    f"runic_combo={combo}",
                    hr.get("n_obs"),
                    hr.get("hit_rate"),
                    hr.get("avg_return"),
                    json.dumps(hr),
                ),
            )
            print(f"Combo {combo}: n={hr.get('n_obs')} hit_rate={hr.get('hit_rate')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
