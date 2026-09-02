#!/usr/bin/env python3
"""Dividend-cut diff report (Rohit 1 Sep, C3).

    "Don't let it feed the score. The flag was inverted across the whole semi-annual
    universe and the new payment counting is untested against frequency changes and
    specials. Print the diff first — every name whose flag changes, old value, new
    value, payment count used, whether an excluded distribution was involved."

Reads the stored flag from ``conviction_store`` and recomputes it on the corrected
declaration-period basis, without writing anything. Nothing here touches a record or a
score: it produces the list to be approved first.

    .venv/bin/python scripts/dividend_cut_diff_report.py --out dividend_cut_diff.csv
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from src.config_paths import CONVICTION_STORE_DIR  # noqa: E402
from src.conviction_engine.capital_allocation import detect_dividend_cut  # noqa: E402
from src.conviction_engine.dividend_series import (  # noqa: E402
    frequency_changed,
    frequency_history,
    normalize_dividends,
    trailing_twelve_month_dividend,
)

# A payment this far above the name's own trailing median is very likely a special or a
# capital return rather than an ordinary dividend. Flagged for the report, never
# silently dropped — classification belongs in the ingest pipeline, not here.
SPECIAL_MULTIPLE = 2.5


def _float_or_none(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def prior_year_window(dividends: pd.Series, as_of: pd.Timestamp) -> dict[str, Any]:
    """The twelve months before the current trailing year, on the same basis."""
    current = trailing_twelve_month_dividend(dividends, as_of)
    series = normalize_dividends(dividends)
    if series is None or not current["payments_used"]:
        return {"amount": None, "payments_used": 0}
    used = current["payments_used"]
    remaining = series.iloc[: max(0, len(series) - used)]
    if remaining.empty:
        return {"amount": None, "payments_used": 0}
    return trailing_twelve_month_dividend(remaining, remaining.index[-1])


def build_report(tickers: list[str] | None = None) -> pd.DataFrame:
    import yfinance as yf

    store = Path(CONVICTION_STORE_DIR)
    paths = sorted(glob.glob(str(store / "*.json")))
    rows: list[dict[str, Any]] = []
    as_of = pd.Timestamp.today().normalize()

    for path in paths:
        ticker = os.path.basename(path)[:-5]
        if tickers and ticker not in tickers:
            continue
        try:
            record = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue

        stored_flag = record.get("dividend_cut_flag") or {}
        stored_triggered = bool(stored_flag.get("triggered")) if isinstance(stored_flag, dict) else False
        stored_penalty = _float_or_none(stored_flag.get("penalty")) if isinstance(stored_flag, dict) else None

        try:
            dividends = yf.Ticker(ticker).dividends
        except Exception:
            continue
        series = normalize_dividends(dividends)
        if series is None:
            continue

        current = trailing_twelve_month_dividend(series, as_of)
        prior = prior_year_window(series, as_of)

        median = float(series.median())
        specials = [
            (str(stamp.date()), float(value))
            for stamp, value in series.tail(current["payments_used"] + prior.get("payments_used", 0)).items()
            if median > 0 and value > SPECIAL_MULTIPLE * median
        ]

        recomputed = detect_dividend_cut(
            {
                "annual_div_declared_current": current["amount"],
                "annual_div_declared_prior": prior.get("amount"),
                "distribution_coverage_ratio": record.get("distribution_coverage_ratio"),
                "distribution_coverage_ratio_prior": record.get("distribution_coverage_ratio_prior"),
                "net_debt_ebitda": record.get("net_debt_ebitda"),
                "net_debt_ebitda_prior": record.get("net_debt_ebitda_prior"),
            }
        )

        rows.append(
            {
                "ticker": ticker,
                "flag_changed": bool(recomputed["triggered"]) != stored_triggered,
                "stored_triggered": stored_triggered,
                "new_triggered": bool(recomputed["triggered"]),
                "stored_penalty": stored_penalty,
                "new_penalty": recomputed["penalty"],
                "stored_current_rate": (stored_flag or {}).get("current_rate"),
                "stored_prior_rate": (stored_flag or {}).get("prior_rate"),
                "new_current_rate": current["amount"],
                "new_prior_rate": prior.get("amount"),
                "payments_used_current": current["payments_used"],
                "payments_used_prior": prior.get("payments_used", 0),
                "coverage_days_current": current["coverage_days"],
                "decline_pct": recomputed["decline_pct"],
                "policy_reset": recomputed["policy_reset"],
                "distress_signals": ";".join(recomputed.get("distress_signals") or []),
                "improvement_signals": ";".join(recomputed.get("improvement_signals") or []),
                "frequency_changed_5y": frequency_changed(series),
                "frequency_history": json.dumps(frequency_history(series)),
                "possible_special_in_window": ";".join(f"{d}:{v}" for d, v in specials) or "",
            }
        )

    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="dividend_cut_diff.csv")
    parser.add_argument("--tickers", help="Comma-separated subset")
    args = parser.parse_args()

    tickers = [t.strip() for t in args.tickers.split(",")] if args.tickers else None
    report = build_report(tickers)
    if report.empty:
        print("No dividend payers found.")
        return 0

    report = report.sort_values(["flag_changed", "ticker"], ascending=[False, True])
    report.to_csv(args.out, index=False)

    changed = report[report["flag_changed"]]
    print(f"Dividend payers examined: {len(report)}")
    print(f"Flag CHANGES: {len(changed)}")
    for _, row in changed.iterrows():
        print(
            f"  {row['ticker']:14s} triggered {row['stored_triggered']} -> {row['new_triggered']}"
            f" | penalty {row['stored_penalty']} -> {row['new_penalty']}"
            f" | {row['stored_current_rate']}/{row['stored_prior_rate']}"
            f" -> {row['new_current_rate']}/{row['new_prior_rate']}"
            f" | payments {row['payments_used_current']}/{row['payments_used_prior']}"
            f"{' | POLICY_RESET' if row['policy_reset'] else ''}"
            f"{' | SPECIAL: ' + row['possible_special_in_window'] if row['possible_special_in_window'] else ''}"
        )
    print(f"\nFrequency changed in 5y: {int(report['frequency_changed_5y'].sum())}")
    print(f"Names with a possible special in the window: {int((report['possible_special_in_window'] != '').sum())}")
    print(f"\nWritten to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
