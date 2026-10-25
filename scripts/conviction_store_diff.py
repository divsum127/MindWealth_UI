#!/usr/bin/env python3
"""Before/after diff of two conviction_store snapshots (Rohit 1 Sep, G3).

    "Before the universe recalc goes to prod, send me the list of what changes."

Read-only. Compares the scoring fields of every record present in either snapshot and
writes one CSV row per ticker plus a short Markdown summary.

    .venv/bin/python scripts/conviction_store_diff.py \\
        --before /path/to/backup --after conviction_store --out-dir reports/conviction_recalc_YYYY-MM-DD
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

FIELDS = (
    "business_type",
    "business_type_source",
    "bq_raw",
    "valuation_tax",
    "conviction_score",
    "fs_score",
    "fs_class",
    "pe_percentile_20y",
    "pe_history_confidence",
    "pe_history_years",
    "yield_trap_warning",
    "framework_coverage",
    "framework_coverage_capped",
)
NUMERIC_TOLERANCE = 0.01


def _load(directory: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("ticker"):
            records[str(data["ticker"]).upper()] = data
    return records


def _dividend_state(record: dict[str, Any]) -> str:
    flag = record.get("dividend_cut_flag")
    if not isinstance(flag, dict):
        return "not_recorded"
    if flag.get("held_for_review"):
        return "held_for_review"
    if flag.get("triggered"):
        return "triggered_pending_approval" if not record.get("dividend_cut_penalty_applied") else "triggered_applied"
    return "no_cut"


def _same(a: Any, b: Any) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return abs(float(a) - float(b)) <= NUMERIC_TOLERANCE
    return a == b


def build_rows(before: dict[str, dict[str, Any]], after: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for ticker in sorted(set(before) | set(after)):
        old, new = before.get(ticker, {}), after.get(ticker, {})
        row: dict[str, Any] = {"ticker": ticker, "status": "added" if not old else "removed" if not new else "kept"}
        changed: list[str] = []
        for field in FIELDS:
            row[f"{field}_before"] = old.get(field)
            row[f"{field}_after"] = new.get(field)
            if not _same(old.get(field), new.get(field)):
                changed.append(field)
        row["dividend_before"] = _dividend_state(old)
        row["dividend_after"] = _dividend_state(new)
        if row["dividend_before"] != row["dividend_after"]:
            changed.append("dividend_cut_state")
        row["last_full_calc_after"] = new.get("last_full_calc")
        row["changed_fields"] = ";".join(changed)
        rows.append(row)
    return rows


def summarise(rows: list[dict[str, Any]]) -> str:
    kept = [r for r in rows if r["status"] == "kept"]
    changed = [r for r in kept if r["changed_fields"]]
    field_counts = Counter(f for r in changed for f in r["changed_fields"].split(";") if f)
    type_moves = Counter(
        f"{r['business_type_before']} -> {r['business_type_after']}"
        for r in kept
        if r["business_type_before"] != r["business_type_after"]
    )
    pe_tiers = Counter(str(r["pe_history_confidence_after"]) for r in kept)
    dividend = Counter(r["dividend_after"] for r in kept)

    big = sorted(
        (
            r for r in kept
            if isinstance(r["conviction_score_before"], (int, float)) and isinstance(r["conviction_score_after"], (int, float))
            and abs(r["conviction_score_after"] - r["conviction_score_before"]) >= 2
        ),
        key=lambda r: -abs(r["conviction_score_after"] - r["conviction_score_before"]),
    )
    lines = [
        f"- Records: {len(kept)} kept, {sum(r['status'] == 'added' for r in rows)} added, "
        f"{sum(r['status'] == 'removed' for r in rows)} removed; {len(changed)} with at least one changed field.",
        "- Changed fields: " + ", ".join(f"{k} {v}" for k, v in field_counts.most_common()),
        "- Business-type moves: " + (", ".join(f"{k} ({v})" for k, v in type_moves.most_common()) or "none"),
        "- P/E history confidence after: " + ", ".join(f"{k} {v}" for k, v in pe_tiers.most_common()),
        "- Dividend-cut state after: " + ", ".join(f"{k} {v}" for k, v in dividend.most_common()),
        f"- Conviction moved by 2 or more points: {len(big)}",
    ]
    for r in big[:40]:
        lines.append(
            f"  - {r['ticker']}: {r['conviction_score_before']} -> {r['conviction_score_after']} "
            f"(bq {r['bq_raw_before']} -> {r['bq_raw_after']}, tax {r['valuation_tax_before']} -> {r['valuation_tax_after']}, "
            f"type {r['business_type_after']})"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    rows = build_rows(_load(args.before), _load(args.after))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.out_dir / "conviction_store_diff.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else ["ticker"])
        writer.writeheader()
        writer.writerows(rows)
    summary = summarise(rows)
    (args.out_dir / "SUMMARY.md").write_text(summary + "\n", encoding="utf-8")
    print(summary)
    print(f"\nWritten {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
