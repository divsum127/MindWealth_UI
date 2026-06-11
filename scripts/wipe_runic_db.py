#!/usr/bin/env python3
"""Truncate Runic backfill tables (keeps schema and variables seed)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.db.connection import get_connection, init_db

TABLES = [
    "forward_returns",
    "combo_fires",
    "signal_fires",
    "daily_readings",
    "macro_regime_log",
    "persistence_fires",
    "rule_library",
    "cftc_positioning",
    "data_pull_log",
    "pending_releases",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Wipe Runic historical data tables")
    parser.add_argument("--yes", action="store_true", help="Confirm wipe")
    args = parser.parse_args()
    if not args.yes:
        print("Pass --yes to truncate backfill tables.")
        return 1

    from src.macro_intelligence.db.migrate import migrate_db

    migrate_db()
    with get_connection() as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        for table in TABLES:
            try:
                conn.execute(f"DELETE FROM {table}")
                print(f"  cleared {table}")
            except Exception as exc:
                print(f"  skip {table}: {exc}")
        conn.execute("UPDATE combo_c_cancel SET wti_potential_week=0, active=0 WHERE id=1")
        conn.execute(
            "DELETE FROM sqlite_sequence WHERE name IN ({})".format(
                ",".join(f"'{t}'" for t in TABLES)
            )
        )
    print("Wipe complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
