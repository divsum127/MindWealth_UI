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
    declared_annual_dividends,
    frequency_changed,
    frequency_history,
    normalize_dividends,
)


def _float_or_none(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


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

        # Same function the engine scores with (ingest classifier, specials excluded,
        # covered-period years), so the approved diff is exactly what goes live.
        declared = declared_annual_dividends(series, as_of)
        current = {
            "amount": declared["current"],
            "payments_used": declared["payments_used_current"],
            "complete": declared["current_complete"],
            "coverage_days": None,
        }
        prior = {
            "amount": declared["prior"] if declared["prior_complete"] else None,
            "payments_used": declared["payments_used_prior"],
            "complete": declared["prior_complete"],
        }
        asset_type = str(record.get("asset_type") or record.get("quote_type") or "").upper()
        is_equity = asset_type in {"", "UNKNOWN", "EQUITY"}
        latest_payment = series.index[-1]
        latest_payment_age_days = int((as_of - latest_payment).days)
        stale_history = latest_payment_age_days > 550

        specials = [(e["date"], e["amount"]) for e in declared["excluded_specials"]]
        review = [(e["date"], e["amount"]) for e in declared["review_pending"]]

        recomputed = detect_dividend_cut(
            {
                "annual_div_declared_current": current["amount"],
                "annual_div_declared_prior": prior.get("amount"),
                "distribution_coverage_ratio": record.get("distribution_coverage_ratio"),
                "distribution_coverage_ratio_prior": record.get("distribution_coverage_ratio_prior"),
                "net_debt_ebitda": record.get("net_debt_ebitda"),
                "net_debt_ebitda_prior": record.get("net_debt_ebitda_prior"),
                "dividend_review_pending": declared["review_pending"],
                "dividend_excluded_specials": declared["excluded_specials"],
                "dividend_data_gaps": declared["data_gaps"],
            }
        )

        changed = bool(recomputed["triggered"]) != stored_triggered
        review_reasons: list[str] = []
        if not is_equity:
            review_reasons.append("not_equity")
        if stale_history:
            review_reasons.append("stale_dividend_history")
        if not current.get("complete"):
            review_reasons.append("incomplete_current_period")
        if not prior.get("complete"):
            review_reasons.append("incomplete_prior_period")
        if review:
            review_reasons.append("outlier_payment_queued_for_review")
        if declared["data_gaps"]:
            review_reasons.append("dividend_data_gap")
        if specials:
            review_reasons.append("special_excluded")

        rows.append(
            {
                "ticker": ticker,
                "asset_type": asset_type or "UNKNOWN",
                "is_equity": is_equity,
                "flag_changed": changed,
                "eligible_for_approval": changed and not review_reasons,
                "review_reasons": ";".join(review_reasons),
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
                "current_period_complete": current.get("complete"),
                "prior_period_complete": prior.get("complete"),
                "latest_payment_date": str(latest_payment.date()),
                "latest_payment_age_days": latest_payment_age_days,
                "decline_pct": recomputed["decline_pct"],
                "policy_reset": recomputed["policy_reset"],
                "distress_signals": ";".join(recomputed.get("distress_signals") or []),
                "improvement_signals": ";".join(recomputed.get("improvement_signals") or []),
                "frequency_changed_5y": frequency_changed(series),
                "frequency_history": json.dumps(frequency_history(series)),
                "possible_special_in_window": ";".join(f"{d}:{v}" for d, v in review) or "",
                "excluded_specials": ";".join(f"{d}:{v}" for d, v in specials) or "",
                "held_for_review": bool(recomputed.get("held_for_review")),
                "data_gaps": ";".join(f"{g['date']}:{g['gap_days']}d" for g in declared["data_gaps"]) or "",
                "held_penalty": recomputed.get("held_penalty"),
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
    clean = changed[changed["eligible_for_approval"]]
    print(f"Dividend payers examined: {len(report)}")
    print(f"Flag CHANGES: {len(changed)}")
    print(f"Clean approval candidates: {len(clean)}")
    for _, row in changed.iterrows():
        print(
            f"  {row['ticker']:14s} triggered {row['stored_triggered']} -> {row['new_triggered']}"
            f" | penalty {row['stored_penalty']} -> {row['new_penalty']}"
            f" | {row['stored_current_rate']}/{row['stored_prior_rate']}"
            f" -> {row['new_current_rate']}/{row['new_prior_rate']}"
            f" | payments {row['payments_used_current']}/{row['payments_used_prior']}"
            f"{' | REVIEW: ' + row['review_reasons'] if row['review_reasons'] else ''}"
            f"{' | POLICY_RESET' if row['policy_reset'] else ''}"
            f"{' | SPECIAL: ' + row['possible_special_in_window'] if row['possible_special_in_window'] else ''}"
        )
    print(f"\nFrequency changed in 5y: {int(report['frequency_changed_5y'].sum())}")
    print(f"Names with a possible special in the window: {int((report['possible_special_in_window'] != '').sum())}")
    print(f"\nWritten to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
