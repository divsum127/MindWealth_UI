#!/usr/bin/env python3
"""Classification-only universe rollout pass (Conviction Engine v6 fixes v2, item 12).

Cheap two-step migration for the new bank / high_margin_hardware / coverage_incomplete
business-type buckets introduced in this pass: fetch only `yfinance` `.info` (no
statements, no price history) for every ticker in `conviction_store/`, diff the result
against each ticker's currently-stored `business_type`, and queue a full
`full_recalculation()` only for tickers that actually flip into one of those 3 buckets.
Everything that classifies the same stays on its normal daily/quarterly schedule.

Usage:
    python scripts/run_universe_classification_pass.py [--dry-run] [--output-json PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.conviction_engine.fundamentals import (  # noqa: E402
    classify_universe_diff,
    run_universe_classification_pass,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store-dir", type=Path, help="conviction_store directory override")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only classify and diff; do not run full_recalculation on flipped tickers",
    )
    parser.add_argument("--output-json", type=Path, help="Write full result JSON to this path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.dry_run:
        result = classify_universe_diff(store_dir=args.store_dir)
    else:
        result = run_universe_classification_pass(store_dir=args.store_dir)

    print(f"Universe size: {result['universe_size']}")
    print(f"Flipped tickers (bank / high_margin_hardware / coverage_incomplete): {result['flipped_count']}")
    for ticker in result["flipped_tickers"]:
        row = next((r for r in result["results"] if r["ticker"] == ticker), {})
        print(f"  {ticker}: {row.get('old_business_type')} -> {row.get('new_business_type')}")
    if not args.dry_run:
        print(f"Auto-recalculated: {result.get('auto_recalculated')}")

    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        print(f"\nWrote {args.output_json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
