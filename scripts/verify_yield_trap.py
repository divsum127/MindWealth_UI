#!/usr/bin/env python3
"""Print yield-trap inputs and PDF rule evaluation for one or more tickers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.conviction_engine.engine import daily_update  # noqa: E402
from src.conviction_engine.fundamentals import update_ticker_fundamentals  # noqa: E402
from src.conviction_engine.scoring import is_yield_trap, market_yield_threshold  # noqa: E402
from src.conviction_engine.store import load_record  # noqa: E402


def evaluate(ticker: str, store_dir: Path | None, refresh: bool) -> dict:
    symbol = ticker.upper()
    if refresh:
        update_ticker_fundamentals(symbol, mode="full", store_dir=store_dir)
    record = load_record(symbol, store_dir)
    if record is None:
        update_ticker_fundamentals(symbol, mode="full", store_dir=store_dir)
        record = load_record(symbol, store_dir)
    elif not refresh:
        record = daily_update(symbol, record=record, store_dir=store_dir, save=True)
    cy = record.get("dividend_yield_current")
    z = record.get("dividend_yield_zscore")
    mean = record.get("dividend_yield_5y_mean")
    std = record.get("dividend_yield_5y_std")
    thresh = market_yield_threshold(symbol)
    return {
        "ticker": symbol,
        "dividend_yield_current": cy,
        "dividend_yield_zscore": z,
        "dividend_yield_5y_mean": mean,
        "dividend_yield_5y_std": std,
        "market_threshold": thresh,
        "z_above_1_5": z is not None and float(z) > 1.5,
        "yield_above_market": cy is not None and float(cy) > thresh,
        "yield_trap_warning": record.get("yield_trap_warning"),
        "is_yield_trap": is_yield_trap(record, symbol),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tickers", nargs="+", help="Ticker symbols, e.g. T.TO PFE")
    parser.add_argument("--store-dir", type=Path, default=None)
    parser.add_argument("--refresh", action="store_true", help="Run full_recalculation before evaluate")
    args = parser.parse_args(argv)
    rows = [evaluate(t, args.store_dir, args.refresh) for t in args.tickers]
    print(json.dumps(rows, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
