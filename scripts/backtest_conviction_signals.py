#!/usr/bin/env python3
"""Backtest conviction scores vs forward mark-to-market on matched signal exports.

Compares a *historical* dated report to a *forward* report of the same type
(e.g. outstanding_signal), joins rows on Function + symbol line, and scores
equity rows with the *current* conviction store (see limitations in --help).

Example:
  python scripts/backtest_conviction_signals.py \\
    --historical trade_store/US/2026-04-01_outstanding_signal.csv \\
    --forward trade_store/US/2026-05-14_outstanding_signal.csv \\
    --output-json conviction_backtest_out.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.conviction_engine.backtest import (  # noqa: E402
    backtest_from_paths,
    correlation_conviction_outcome,
    find_report_csv,
    latest_matching_report,
)
from src.config_paths import TRADE_STORE_US_DIR  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--historical", type=Path, help="Path to older dated signal CSV.")
    p.add_argument("--forward", type=Path, help="Path to newer dated signal CSV (same report type).")
    p.add_argument(
        "--report-base",
        default="outstanding_signal.csv",
        help="Base filename (e.g. outstanding_signal.csv, all_signal.csv) when using --from-date.",
    )
    p.add_argument("--from-date", help="YYYY-MM-DD to resolve historical path under trade-store-dir.")
    p.add_argument(
        "--forward-date",
        help="YYYY-MM-DD for forward file; default = latest dated file for report-base.",
    )
    p.add_argument("--trade-store-dir", type=Path, default=TRADE_STORE_US_DIR)
    p.add_argument("--store-dir", type=Path, default=None, help="Optional conviction_store override.")
    p.add_argument("--output-csv", type=Path, help="Write per-row detail CSV.")
    p.add_argument("--output-json", type=Path, help="Write summary JSON.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    hist_path = args.historical
    fwd_path = args.forward

    if args.from_date:
        found = find_report_csv(args.trade_store_dir, args.report_base, args.from_date)
        if not found:
            print(json.dumps({"error": f"No file {args.from_date}_{args.report_base} under {args.trade_store_dir}"}))
            return 2
        hist_path = found

    if fwd_path is None and args.forward_date:
        fwd_path = find_report_csv(args.trade_store_dir, args.report_base, args.forward_date)
        if not fwd_path:
            print(json.dumps({"error": f"No forward file for {args.forward_date}"}))
            return 2

    if fwd_path is None:
        fwd_path = latest_matching_report(args.trade_store_dir, args.report_base)
        if not fwd_path:
            print(json.dumps({"error": f"No dated *_{args.report_base} under {args.trade_store_dir}"}))
            return 2

    if hist_path is None:
        print(json.dumps({"error": "Provide --historical or --from-date"}))
        return 2

    store_dir = Path(args.store_dir) if args.store_dir else None

    detail, summary = backtest_from_paths(hist_path, fwd_path, store_dir=store_dir)
    if detail.empty:
        print(json.dumps({"error": "Empty historical or forward dataframe"}))
        return 3

    eq_buy = detail[
        (detail["asset_type"].astype(str).str.upper() == "EQUITY")
        & (detail["original_signal"].astype(str).str.upper() == "BUY")
    ]
    matched = eq_buy[eq_buy["_merge_forward"] == "both"]

    payload: dict = {
        "historical": str(hist_path),
        "forward": str(fwd_path),
        "same_file_warning": str(hist_path.resolve()) == str(fwd_path.resolve()),
        "limitations": [
            "Conviction scores use the current conviction_store at run time (not fundamentals as of historical report date).",
            "Forward outcome is the newer file's '% vs signal' from its Today price column (same signal line match).",
        ],
        "row_counts": {
            "historical_detail": int(detail.shape[0]),
            "equity_buy_rows": int(eq_buy.shape[0]),
            "equity_buy_matched_to_forward": int(matched.shape[0]),
        },
        "correlation_conviction_vs_forward_mtm": correlation_conviction_outcome(matched),
        "bucket_summary": json.loads(summary.to_json(orient="records")) if not summary.empty else [],
    }

    if args.output_csv:
        Path(args.output_csv).parent.mkdir(parents=True, exist_ok=True)
        detail.to_csv(args.output_csv, index=False)
        payload["detail_csv"] = str(args.output_csv)

    print(json.dumps(payload, indent=2))

    if args.output_json:
        Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output_json).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
