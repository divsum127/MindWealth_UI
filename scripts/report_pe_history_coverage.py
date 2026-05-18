#!/usr/bin/env python3
"""Report P/E history span (years) across conviction_store equity records."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.conviction_engine.data_coverage import summarize_pe_history_distribution  # noqa: E402
from src.conviction_engine.store import list_records  # noqa: E402


def _ascii_histogram(distribution: list[dict[str, object]], width: int = 40) -> str:
    if not distribution:
        return ""
    max_count = max(int(row.get("count", 0)) for row in distribution) or 1
    lines: list[str] = []
    for row in distribution:
        label = str(row.get("bucket", "?"))
        count = int(row.get("count", 0))
        bar_len = int((count / max_count) * width) if count else 0
        lines.append(f"  {label:>6} | {'#' * bar_len} {count}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize P/E history years available per equity ticker.")
    parser.add_argument("--store-dir", type=Path, help="conviction_store directory override")
    parser.add_argument("--output-json", type=Path, help="Write full summary JSON to this path")
    parser.add_argument("--no-tickers", action="store_true", help="Omit per-ticker list from JSON output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    records = list_records(args.store_dir)
    summary = summarize_pe_history_distribution(records)
    if args.no_tickers:
        summary = {k: v for k, v in summary.items() if k != "tickers"}

    print(json.dumps(summary, indent=2, default=str))
    print("\nP/E history years distribution (equity records with conviction_score):\n")
    print(_ascii_histogram(summary.get("years_distribution", [])))
    print(
        f"\n{summary.get('insufficient_20y_count', 0)} / {summary.get('total_equity_records', 0)} "
        f"({summary.get('insufficient_20y_pct', 0)}%) have < {summary.get('target_years', 20)} years of P/E history."
    )

    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
        print(f"\nWrote {args.output_json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
