#!/usr/bin/env python3
"""
Daily Conviction Engine entry point.

Run after trade_store daily signal reports are synced (e.g. from update_trade_data.sh):
  1. Refresh conviction_store fundamentals (daily mode by default)
  2. Attach conviction scores to the New Signals report (default)
  3. Archive overlays under conviction_store/daily/YYYY-MM-DD/

Outputs per report date (default: new_signal only):
  conviction_store/daily/{date}/manifest.json
  conviction_store/daily/{date}/{date}_new_signal_conviction.csv
  conviction_store/daily/{date}/{date}_new_signal_conviction_scores.csv
  conviction_store/overlays/{date}_new_signal_conviction.csv
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.conviction_engine.daily_run import run_daily_conviction_pipeline  # noqa: E402
from src.conviction_engine.signals import PRIMARY_DAILY_REPORT  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run daily Conviction Engine: fundamentals + signal overlays + archive.")
    parser.add_argument(
        "--report-date",
        help="Trade report date YYYY-MM-DD (default: from latest dated new_signal.csv or data_fetch_datetime.json).",
    )
    parser.add_argument("--trade-store-dir", type=Path, help="trade_store/US directory override")
    parser.add_argument("--store-dir", type=Path, help="conviction_store directory override")
    parser.add_argument(
        "--fundamentals-mode",
        choices=["auto", "daily", "full"],
        default="daily",
        help="Fundamentals refresh mode before overlay (default: daily).",
    )
    parser.add_argument("--skip-fundamentals", action="store_true", help="Only overlay signals using existing JSON store.")
    parser.add_argument("--skip-overlays", action="store_true", help="Only refresh fundamentals; do not write CSV overlays.")
    parser.add_argument("--dry-run", action="store_true", help="Resolve paths and tickers without writing files.")
    parser.add_argument("--fail-fast", action="store_true", help="Stop on first ticker or overlay failure.")
    parser.add_argument("--limit", type=int, help="Limit tickers processed (smoke test).")
    parser.add_argument(
        "--overlay-reports",
        default=PRIMARY_DAILY_REPORT,
        help=f"Comma-separated trade_store base CSV names to overlay (default: {PRIMARY_DAILY_REPORT}).",
    )
    return parser


def _parse_overlay_reports(value: str) -> list[str]:
    names = [part.strip() for part in value.split(",") if part.strip()]
    return [name if name.endswith(".csv") else f"{name}.csv" for name in names]


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_daily_conviction_pipeline(
        report_date=args.report_date,
        trade_store_dir=args.trade_store_dir,
        store_dir=args.store_dir,
        fundamentals_mode=args.fundamentals_mode,
        skip_fundamentals=args.skip_fundamentals,
        skip_overlays=args.skip_overlays,
        dry_run=args.dry_run,
        fail_fast=args.fail_fast,
        limit=args.limit,
        overlay_reports=_parse_overlay_reports(args.overlay_reports),
    )

    payload = {k: v for k, v in result.items() if k != "fundamentals_results"}
    print(json.dumps(payload, indent=2, default=str))

    status = result.get("status", "")
    if status.startswith("error"):
        return 1
    if "error" in status:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
