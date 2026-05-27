#!/usr/bin/env python3
"""Historical backfill for macro intelligence database."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.data.pull_all import load_all_series, pull_all_series
from src.macro_intelligence.db.connection import init_db
from src.macro_intelligence.engine.combo_detector import detect_named_combos
from src.macro_intelligence.engine.forward_returns import backfill_forward_returns


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill Runic macro history")
    parser.add_argument("--start", default="2010-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument("--weekly-only", action="store_true", help="Only Fridays")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    init_db()
    load_all_series(force=True)
    end = pd_timestamp(args.end) if args.end else datetime.now()
    start = datetime.strptime(args.start, "%Y-%m-%d")
    cur = start
    n = 0
    while cur <= end:
        if args.weekly_only and cur.weekday() != 4:
            cur += timedelta(days=1)
            continue
        ds = cur.strftime("%Y-%m-%d")
        pull_all_series(ds)
        detect_named_combos(ds, persist=True)
        n += 1
        if args.limit and n >= args.limit:
            break
        cur += timedelta(days=1)
    backfill_forward_returns()
    print(f"Backfill complete: {n} dates processed")


def pd_timestamp(s: str | None):
    if not s:
        return datetime.now()
    return datetime.strptime(s, "%Y-%m-%d")


if __name__ == "__main__":
    main()
