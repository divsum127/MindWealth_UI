#!/usr/bin/env python3
"""Update Conviction Engine fundamentals and scores from yfinance."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.conviction_engine.engine import apply_to_signal_file  # noqa: E402
from src.conviction_engine.fundamentals import discover_universe, update_universe_fundamentals  # noqa: E402
from src.conviction_engine.signals import discover_signal_sources  # noqa: E402


def _parse_tickers(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip().upper() for item in value.split(",") if item.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch fundamentals, update conviction_store JSON records, and optionally refresh conviction overlays."
    )
    parser.add_argument(
        "--mode",
        choices=["auto", "daily", "full"],
        default="auto",
        help="auto=full for missing records and daily for existing; daily=price-sensitive update; full=refresh static fundamentals too.",
    )
    parser.add_argument("--tickers", help="Comma-separated ticker list. If omitted, tickers are discovered from trade_store signals.")
    parser.add_argument(
        "--include-signal-tickers",
        action="store_true",
        help="When --tickers is provided, also include tickers discovered from trade_store signals.",
    )
    parser.add_argument("--universe-file", type=Path, help="Optional newline-separated ticker universe file.")
    parser.add_argument("--trade-store-dir", type=Path, help="Directory containing signal CSVs, defaults to trade_store/US.")
    parser.add_argument("--store-dir", type=Path, help="Optional conviction_store override for testing or alternate stores.")
    parser.add_argument("--include-existing-records", action="store_true", help="Also update tickers already present in conviction_store.")
    parser.add_argument("--limit", type=int, help="Limit number of tickers processed, useful for smoke tests.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and report fields without writing JSON records.")
    parser.add_argument("--fail-fast", action="store_true", help="Stop on first ticker failure.")
    parser.add_argument(
        "--write-overlays",
        action="store_true",
        help="After updating fundamentals, write conviction overlay CSVs for latest supported signal files.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    explicit_tickers = _parse_tickers(args.tickers)
    tickers = discover_universe(
        trade_store_dir=args.trade_store_dir,
        universe_file=args.universe_file,
        extra_tickers=explicit_tickers,
        include_existing_records=args.include_existing_records,
        include_signal_sources=(not explicit_tickers or args.include_signal_tickers),
    )
    if args.limit is not None:
        tickers = tickers[: args.limit]

    if not tickers:
        print(json.dumps({"status": "no_tickers_found", "updated": 0}, indent=2))
        return 0

    results = update_universe_fundamentals(
        tickers,
        mode=args.mode,
        store_dir=args.store_dir,
        dry_run=args.dry_run,
        fail_fast=args.fail_fast,
    )

    overlay_outputs: list[str] = []
    if args.write_overlays and not args.dry_run:
        for source in discover_signal_sources(args.trade_store_dir).values():
            result = apply_to_signal_file(source, store_dir=args.store_dir, save_output=True)
            if not result.empty:
                overlay_outputs.append(str(source))

    errors = [result for result in results if result.get("status") == "error"]
    payload = {
        "status": "completed_with_errors" if errors else "completed",
        "mode": args.mode,
        "tickers_requested": len(tickers),
        "updated": sum(1 for result in results if result.get("status") in {"updated", "dry_run"}),
        "errors": len(errors),
        "overlay_sources_refreshed": overlay_outputs,
        "results": results,
    }
    print(json.dumps(payload, indent=2, default=str))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
