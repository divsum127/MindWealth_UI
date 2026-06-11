#!/usr/bin/env python3
"""Batch classify geo_overlay and merge into macro_regime_log."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.claude.regime_classifier import _classify_geo
from src.macro_intelligence.db.connection import get_connection, init_db
from src.macro_intelligence.db.regime_log import get_regime_json, upsert_macro_regime_log
from src.macro_intelligence.engine.regime_rules import build_python_regime

DEFAULT_ANCHORS = [
    "2008-09-15",
    "2020-03-23",
    "2020-06-08",
    "2022-02-24",
    "2022-10-13",
    "2024-09-18",
    "2025-04-01",
]


def _dates_from_db(limit: int = 400) -> list[str]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT cf.date
            FROM combo_fires cf
            WHERE cf.runic_combo IS NOT NULL
            ORDER BY cf.date DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    dates = [r["date"] for r in rows]
    for d in DEFAULT_ANCHORS:
        if d not in dates:
            dates.append(d)
    return sorted(set(dates))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dates", nargs="*", default=None)
    parser.add_argument("--from-db", action="store_true", help="Named combo fire dates + anchors")
    parser.add_argument("--limit", type=int, default=400)
    parser.add_argument("--use-claude", action="store_true", default=False)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    init_db()
    dates = args.dates or (_dates_from_db(args.limit) if args.from_db else DEFAULT_ANCHORS)

    for date in dates:
        geo = _classify_geo(date, use_claude=args.use_claude)
        existing = get_regime_json(date) or build_python_regime(date)
        existing["geo_overlay"] = geo
        existing["geo_source"] = "claude_batch" if args.use_claude else "heuristic"
        if args.dry_run:
            print(f"{date}: {geo}")
            continue
        upsert_macro_regime_log(date, existing, model="geo_batch")
        print(f"{date}: {geo}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
