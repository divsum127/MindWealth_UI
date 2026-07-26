#!/usr/bin/env python3
"""Manually load a P/E history series for a non-US ticker into conviction_store.

Non-US tickers (``.TO``/``.NS``/``.NZ``/``.AX``/``.HK``/``.KS``/``.SI``/``.PA``/``.F``/
etc.) are out of scope for the FMP auto-fetch fallback (``src/conviction_engine/
pe_history_fmp.py``) — FMP's coverage is strongest on US/major exchanges, and this
repo's own spec (ConvictionEngine_v5_FINAL.pdf Sec 10.2) already routes non-US names to
manual entry from Gurufocus / TIKR / Screener.in. This script operationalizes that
fallback instead of hand-editing conviction_store JSON.

Usage:
    python scripts/set_manual_pe_history.py TICKER --csv path/to/pe_history.csv

CSV format: two columns, ``date`` (YYYY-MM-DD) and ``pe`` (trailing P/E as of that
date), one row per sample (monthly or quarterly cadence recommended). Example:

    date,pe
    2015-03-31,18.2
    2015-06-30,19.4
    ...

Writes ``pe_20y_array`` / ``pe_history_meta`` into ``conviction_store/{TICKER}.json``
using the exact meta shape ``compute_pe_history()`` produces (so ``daily_update`` /
``calculate_valuation_tax_components`` treat it identically to a yfinance- or
FMP-derived series), tagged ``source="manual"``.
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.conviction_engine.fundamentals_enriched import (  # noqa: E402
    PE_HISTORY_MAX_STORED_POINTS,
    PE_HISTORY_TARGET_YEARS,
)
from src.conviction_engine.store import load_or_create_record, save_record  # noqa: E402


def parse_pe_history_csv(csv_path: Path) -> list[tuple[str, float]]:
    """Read (date, pe) pairs from CSV, sorted ascending by date. Raises ValueError on
    malformed rows so bad manual entry is caught before it's written to the store."""
    rows: list[tuple[str, float]] = []
    with open(csv_path, "r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None or "date" not in reader.fieldnames or "pe" not in reader.fieldnames:
            raise ValueError(f"CSV must have 'date' and 'pe' columns, got: {reader.fieldnames}")
        for i, row in enumerate(reader, start=2):
            date_str = (row.get("date") or "").strip()
            pe_str = (row.get("pe") or "").strip()
            if not date_str or not pe_str:
                continue
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError as exc:
                raise ValueError(f"row {i}: invalid date {date_str!r} (expected YYYY-MM-DD)") from exc
            try:
                pe_val = float(pe_str)
            except ValueError as exc:
                raise ValueError(f"row {i}: invalid pe value {pe_str!r}") from exc
            if not (0 < pe_val < 500):
                raise ValueError(f"row {i}: pe value {pe_val} out of sane range (0, 500)")
            rows.append((dt.strftime("%Y-%m-%d"), round(pe_val, 4)))

    rows.sort(key=lambda pair: pair[0])
    return rows


def build_manual_pe_bundle(rows: list[tuple[str, float]], *, target_years: int = PE_HISTORY_TARGET_YEARS) -> dict[str, Any]:
    """Compute the same {values, meta} shape compute_pe_history() produces, tagged
    source='manual', so downstream code (daily_update, scoring) can't tell the
    difference from an auto-fetched series."""
    if not rows:
        raise ValueError("no usable rows found in CSV")

    stored = rows[-PE_HISTORY_MAX_STORED_POINTS:]
    dates = [r[0] for r in stored]
    values = [r[1] for r in stored]

    first_dt = datetime.strptime(dates[0], "%Y-%m-%d")
    last_dt = datetime.strptime(dates[-1], "%Y-%m-%d")
    years_available = round((last_dt - first_dt).days / 365.25, 2)

    meta = {
        "years_available": years_available,
        "price_years_available": years_available,
        "eps_quarters": len(values),
        "eps_years_available": years_available,
        "start_date": dates[0],
        "end_date": dates[-1],
        "point_count": len(values),
        "stored_point_count": len(values),
        "target_years": target_years,
        "insufficient_20y": years_available < target_years,
        "source": "manual",
    }
    return {"values": values, "meta": meta}


def apply_manual_pe_history(ticker: str, bundle: dict[str, Any], store_dir: Path | None = None) -> Path:
    record = load_or_create_record(ticker, store_dir)
    record["pe_20y_array"] = bundle["values"]
    record["pe_history_meta"] = bundle["meta"]
    return save_record(record, store_dir)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load a manually-sourced P/E history series (Gurufocus/TIKR/Screener.in) "
        "into conviction_store for a non-US ticker."
    )
    parser.add_argument("ticker", help="Ticker symbol, e.g. SHOP.TO, INFY.NS")
    parser.add_argument("--csv", type=Path, required=True, help="CSV with 'date,pe' columns")
    parser.add_argument("--store-dir", type=Path, help="conviction_store directory override (for testing)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not args.csv.exists():
        print(f"error: CSV not found: {args.csv}", file=sys.stderr)
        return 1

    try:
        rows = parse_pe_history_csv(args.csv)
        bundle = build_manual_pe_bundle(rows)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    path = apply_manual_pe_history(args.ticker, bundle, args.store_dir)
    meta = bundle["meta"]
    print(f"Wrote {meta['point_count']} manual P/E points ({meta['start_date']} -> {meta['end_date']}, "
          f"{meta['years_available']}y) to {path}")
    if meta["insufficient_20y"]:
        print(f"Note: still < {PE_HISTORY_TARGET_YEARS}y target, insufficient_20y stays True "
              f"(PE percentile will be neutralized, not this record's fault).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
