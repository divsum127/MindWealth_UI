#!/usr/bin/env python3
"""Universe exports Rohit asked for on 1 Sep (G1, G2). Read-only.

    G1: "a CSV over the full universe with pe_ttm, pe_ttm_adjusted, adjusted_eps_basis,
        adjusted_eps_source and one_off_review_needed"
    G2: "send me a report showing which fields came back empty for every name at the
        last recalc"

    .venv/bin/python scripts/conviction_universe_export.py --out-dir reports/conviction_recalc_YYYY-MM-DD
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config_paths import CONVICTION_STORE_DIR  # noqa: E402

G1_FIELDS = (
    "ticker",
    "asset_type",
    "business_type",
    "pe_ttm",
    "pe_ttm_adjusted",
    "adjusted_eps_basis",
    "adjusted_eps_source",
    "one_off_pct_of_ni",
    "one_off_review_needed",
    "pe_history_confidence",
    "pe_history_years",
    "pe_history_source",
    "last_full_calc",
)


def _records(store: Path) -> list[dict[str, Any]]:
    out = []
    for path in sorted(store.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("ticker"):
            out.append(data)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, default=Path(CONVICTION_STORE_DIR))
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    records = _records(args.store)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    with (args.out_dir / "g1_pe_adjusted_eps_universe.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=G1_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow({field: record.get(field) for field in G1_FIELDS})

    empty_rows = 0
    with (args.out_dir / "g2_empty_statement_fields.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["ticker", "asset_type", "last_full_calc", "empty_statements", "fetch_errors"])
        for record in records:
            coverage = record.get("statement_coverage") or {}
            # Coverage holds column counts ("*_cols": 0 means the statement came back empty)
            # and "*_empty" booleans. "cashflow_prior_year_available" is a depth limit of
            # the feed (false for every name), not an empty statement, so it is not listed.
            empty = sorted(
                k
                for k, v in (coverage.items() if isinstance(coverage, dict) else [])
                if (k.endswith("_cols") and v == 0) or (k.endswith("_empty") and v is True)
            )
            errors = record.get("fetch_errors") or []
            if empty or errors:
                empty_rows += 1
                writer.writerow(
                    [record["ticker"], record.get("asset_type"), record.get("last_full_calc"), ";".join(empty), ";".join(map(str, errors))]
                )
    print(f"G1: {len(records)} records; G2: {empty_rows} records with empty statements or fetch errors")
    print(f"Written to {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
