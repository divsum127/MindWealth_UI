#!/usr/bin/env python3
"""One-time migration: scale legacy 0-1 unconditional_pctile rows to 0-100."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.db.connection import get_connection, init_db  # noqa: E402


def normalize_pctiles(*, dry_run: bool = False) -> dict:
    init_db()
    with get_connection() as conn:
        before = conn.execute(
            """
            SELECT COUNT(*) AS c FROM daily_readings
            WHERE unconditional_pctile IS NOT NULL
              AND unconditional_pctile > 0
              AND unconditional_pctile <= 1.0
            """
        ).fetchone()["c"]
        by_var = conn.execute(
            """
            SELECT var_id, COUNT(*) AS c FROM daily_readings
            WHERE unconditional_pctile IS NOT NULL
              AND unconditional_pctile > 0
              AND unconditional_pctile <= 1.0
            GROUP BY var_id ORDER BY var_id
            """
        ).fetchall()
        if not dry_run and before:
            conn.execute(
                """
                UPDATE daily_readings
                SET unconditional_pctile = unconditional_pctile * 100.0
                WHERE unconditional_pctile IS NOT NULL
                  AND unconditional_pctile > 0
                  AND unconditional_pctile <= 1.0
                """
            )
        after = 0 if dry_run else conn.execute(
            """
            SELECT COUNT(*) AS c FROM daily_readings
            WHERE unconditional_pctile IS NOT NULL
              AND unconditional_pctile > 0
              AND unconditional_pctile <= 1.0
            """
        ).fetchone()["c"]
    return {
        "dry_run": dry_run,
        "rows_normalized": before,
        "rows_remaining_legacy": after,
        "by_var": {r["var_id"]: r["c"] for r in by_var},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = normalize_pctiles(dry_run=args.dry_run)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
