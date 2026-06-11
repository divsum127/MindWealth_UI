#!/usr/bin/env python3
"""Daily job: sync emission_vectors from daily_readings for as-of date.

Starts the 6-month live-vector clock for production HMM (Dec 2026 target).
Safe to run Mon–Fri after nightly pull; idempotent UPSERT per (date, var_id).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.analysis.regime_experiments.shadow_backfill import (  # noqa: E402
    backfill_emission_vectors,
    ensure_v2_tables,
)
from src.macro_intelligence.db.connection import get_connection, init_db  # noqa: E402


def sync_date(as_of: str) -> dict:
    init_db()
    ensure_v2_tables()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT var_id, unconditional_pctile, regime_pctile
            FROM daily_readings WHERE date = ?
            """,
            (as_of,),
        ).fetchall()
        n = 0
        for r in rows:
            un = r["unconditional_pctile"]
            rp = r["regime_pctile"]
            if un is None and rp is None:
                continue
            fallback = 1 if rp is None and un is not None else 0
            conn.execute(
                """
                INSERT INTO emission_vectors (date, var_id, unconditional_pctile, regime_pctile, fallback_used)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(date, var_id) DO UPDATE SET
                  unconditional_pctile=excluded.unconditional_pctile,
                  regime_pctile=excluded.regime_pctile,
                  fallback_used=excluded.fallback_used
                """,
                (as_of, r["var_id"], un, rp, fallback),
            )
            n += 1
        conn.commit()
        stats = conn.execute(
            "SELECT COUNT(*) AS cnt, MIN(date) AS mn, MAX(date) AS mx FROM emission_vectors"
        ).fetchone()
    return {
        "as_of": as_of,
        "rows_upserted": n,
        "total_emission_rows": stats["cnt"],
        "min_date": stats["mn"],
        "max_date": stats["mx"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync daily emission_vectors")
    parser.add_argument("--date", help="YYYY-MM-DD (default: today)")
    parser.add_argument("--backfill-from", help="Optional: run full backfill from date")
    args = parser.parse_args()
    if args.backfill_from:
        n = backfill_emission_vectors(args.backfill_from)
        print(json.dumps({"backfill_rows": n}, indent=2))
        return
    as_of = args.date or datetime.now().strftime("%Y-%m-%d")
    print(json.dumps(sync_date(as_of), indent=2))


if __name__ == "__main__":
    main()
