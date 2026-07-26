#!/usr/bin/env python3
"""Weekly M&A activity scan for conviction engine (cron)."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.conviction_engine.ma_activity import run_weekly_ma_scan

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan universe for M&A activity")
    parser.add_argument("--ticker", action="append", help="Limit to specific ticker(s)")
    parser.add_argument("--dry-run", action="store_true", help="List universe only")
    args = parser.parse_args()

    if args.dry_run:
        from src.conviction_engine.fundamentals import discover_universe

        tickers = args.ticker or discover_universe(include_existing_records=True)
        print(json.dumps({"universe_size": len(tickers), "tickers": tickers[:20]}, indent=2))
        return 0

    results = run_weekly_ma_scan(args.ticker)
    found = [r for r in results if r.get("found")]
    print(json.dumps({"scanned": len(results), "found": len(found), "hits": found}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
