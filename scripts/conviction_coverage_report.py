#!/usr/bin/env python3
"""Universe coverage reports (Rohit 1 Sep, G1 and G2).

G1 — "send me a CSV over the full universe with pe_ttm, pe_ttm_adjusted,
adjusted_eps_basis, adjusted_eps_source and one_off_review_needed. One name on a page
proves nothing about coverage."

G2 — "The problem is that a missing statement returned nothing instead of raising an
error, so it failed silently for a year. Make it fail loudly, and send me a report
showing which fields came back empty for every name at the last recalc."

Both read the stored records only. Nothing is fetched, recomputed or written.

    .venv/bin/python scripts/conviction_coverage_report.py --out-dir reports/
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

# Fields whose absence changes a score or a verdict, as opposed to merely being absent.
LOAD_BEARING_FIELDS = (
    "price",
    "market_cap",
    "eps_ttm",
    "net_income_ttm",
    "fcf_ttm",
    "ev_fwd_rev",
    "owner_earnings_yield",
    "pe_ttm",
    "pe_percentile_20y",
    "revenue_growth",
    "net_debt_ebitda",
    "dividend_yield_current",
    "dividend_yield_5y_mean",
)

AGENT_DIMENSIONS = (
    "ceo_quality",
    "competitive_moat",
    "macro_tailwind",
    "deal_delay_risk",
    "reinvestment_runway",
)


def _records() -> list[tuple[str, dict[str, Any]]]:
    out = []
    for path in sorted(glob.glob(str(Path(CONVICTION_STORE_DIR) / "*.json"))):
        ticker = os.path.basename(path)[:-5]
        try:
            out.append((ticker, json.loads(Path(path).read_text(encoding="utf-8"))))
        except (OSError, ValueError):
            continue
    return out


def earnings_report(records: list[tuple[str, dict[str, Any]]]) -> pd.DataFrame:
    """G1: the adjusted-earnings picture across the whole universe."""
    rows = []
    for ticker, record in records:
        rows.append(
            {
                "ticker": ticker,
                "business_type": record.get("business_type"),
                "framework_coverage": record.get("framework_coverage"),
                "pe_ttm": record.get("pe_ttm"),
                "pe_ttm_adjusted": record.get("pe_ttm_adjusted"),
                "adjusted_eps_ttm": record.get("adjusted_eps_ttm"),
                "adjusted_eps_source": record.get("adjusted_eps_source"),
                "adjusted_eps_basis": record.get("adjusted_eps_basis"),
                "adjusted_eps_citation": record.get("adjusted_eps_citation"),
                "one_off_pct_of_ni": record.get("one_off_pct_of_ni"),
                "one_off_unclassified_pct_of_ni": record.get("one_off_unclassified_pct_of_ni"),
                "one_off_review_needed": record.get("one_off_review_needed"),
                "one_off_sizing_cap_pct": record.get("one_off_sizing_cap_pct"),
                "bq_raw": record.get("bq_raw"),
                "valuation_tax": record.get("valuation_tax"),
                "conviction_score": record.get("conviction_score"),
                "fs_class": record.get("fs_class"),
                "last_full_calc": record.get("last_full_calc"),
            }
        )
    return pd.DataFrame(rows)


def field_coverage_report(records: list[tuple[str, dict[str, Any]]]) -> pd.DataFrame:
    """G2: which fields came back empty, per name, at the last recalculation."""
    rows = []
    for ticker, record in records:
        coverage = record.get("statement_coverage") or {}
        provenance = record.get("agent_dim_provenance") or {}
        missing = [f for f in LOAD_BEARING_FIELDS if record.get(f) is None]
        agents_not_run = [
            dim for dim in AGENT_DIMENSIONS
            if (provenance.get(dim) or {}).get("source") in (None, "not_run", "agent_failed")
        ]
        rows.append(
            {
                "ticker": ticker,
                "business_type": record.get("business_type"),
                "quarterly_income_cols": coverage.get("quarterly_income_cols"),
                "quarterly_income_empty": coverage.get("quarterly_income_empty"),
                "annual_income_cols": coverage.get("annual_income_cols"),
                "quarterly_cashflow_cols": coverage.get("quarterly_cashflow_cols"),
                "cashflow_prior_year_available": coverage.get("cashflow_prior_year_available"),
                "missing_field_count": len(missing),
                "missing_fields": ";".join(missing),
                "agent_dims_status": record.get("agent_dims_status"),
                "agent_dims_not_scored": ";".join(agents_not_run),
                "fetch_errors": ";".join(record.get("fetch_errors") or []),
                "last_full_calc": record.get("last_full_calc"),
            }
        )
    return pd.DataFrame(rows).sort_values(["missing_field_count", "ticker"], ascending=[False, True])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default=".")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    records = _records()
    if not records:
        print("No stored records found.")
        return 1

    earnings = earnings_report(records)
    coverage = field_coverage_report(records)
    earnings_path = out_dir / "conviction_universe_earnings.csv"
    coverage_path = out_dir / "conviction_field_coverage.csv"
    earnings.to_csv(earnings_path, index=False)
    coverage.to_csv(coverage_path, index=False)

    scored = earnings[earnings["conviction_score"].notna()]
    print(f"Records: {len(earnings)}  (scored: {len(scored)})")
    print("\n-- Adjusted earnings coverage (G1) --")
    source_counts = earnings["adjusted_eps_source"].fillna("none").value_counts().to_dict()
    print(f"  adjusted_eps_source: {source_counts}")
    print(f"  pe_ttm present:          {int(earnings['pe_ttm'].notna().sum())}")
    print(f"  pe_ttm_adjusted present: {int(earnings['pe_ttm_adjusted'].notna().sum())}")
    print(f"  one_off_review_needed:   {int(earnings['one_off_review_needed'].fillna(False).astype(bool).sum())}")
    print(f"  sizing capped:           {int(earnings['one_off_sizing_cap_pct'].notna().sum())}")

    print("\n-- Field coverage (G2) --")
    print(f"  empty quarterly income statement: {int(coverage['quarterly_income_empty'].fillna(False).astype(bool).sum())}")
    print(f"  no prior-year cash flow:          {int((~coverage['cashflow_prior_year_available'].fillna(False).astype(bool)).sum())}")
    agent_status = coverage["agent_dims_status"].fillna("unknown").value_counts().to_dict()
    print(f"  agent_dims_status:                {agent_status}")
    worst = coverage.head(10)
    print("\n  Ten names with the most missing load-bearing fields:")
    for _, row in worst.iterrows():
        print(f"    {row['ticker']:16s} {row['missing_field_count']:2d}  {row['missing_fields'][:90]}")

    print(f"\nWritten:\n  {earnings_path}\n  {coverage_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
