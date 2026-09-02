#!/usr/bin/env python3
"""Repair stale quality columns in the consolidated chatbot CSVs.

Two problems accumulated in ``chatbot/data/*.csv``:

1. Several rows exist for the same signal identity, one per day the row was
   written. A later price refresh rewrote Today/MTM/trading-days on all of them,
   so every duplicate carries today's price beside the R:R, timeliness, reward
   remaining and stop ladder frozen on its own write date.
2. The surviving row's quality columns were never recomputed against the
   refreshed price.

This script collapses each identity to its freshest row and recomputes the
quality columns from the refreshed price, stamping ``quality_as_of``.

Usage:
    python scripts/repair_consolidated_quality_columns.py --dry-run
    python scripts/repair_consolidated_quality_columns.py
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.mtm_pricing import normalize_today_price_column_names  # noqa: E402
from src.utils.quality_refresh import (  # noqa: E402
    QUALITY_AS_OF_COLUMN,
    refresh_quality_columns,
)

SYMBOL_COL = "Symbol, Signal, Signal Date/Price[$]"
INTERVAL_COL = "Interval, Confirmation Status"
TARGET_FILES = ("entry.csv", "exit.csv", "portfolio_target_achieved.csv")


def identity_key(row: pd.Series) -> tuple:
    """Symbol + side + signal date + function + interval — one open signal."""
    sym_cell = str(row.get(SYMBOL_COL, ""))
    symbol = sym_cell.split(",")[0].strip()
    side = "Long" if ", Long," in sym_cell else ("Short" if ", Short," in sym_cell else "")
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", sym_cell)
    signal_date = date_match.group(1) if date_match else ""
    function = str(row.get("Function", "")).strip()
    interval = str(row.get(INTERVAL_COL, "")).split(",")[0].strip()
    return (symbol, side, signal_date, function, interval)


def collapse_to_freshest(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Keep the last-written row per identity — the writer appends refreshed rows."""
    if df.empty or SYMBOL_COL not in df.columns:
        return df, 0
    work = df.copy()
    work["_idkey"] = work.apply(identity_key, axis=1)
    work["_order"] = range(len(work))
    if QUALITY_AS_OF_COLUMN in work.columns:
        work["_vintage"] = work[QUALITY_AS_OF_COLUMN].astype(str)
    else:
        work["_vintage"] = ""
    work = work.sort_values(["_vintage", "_order"], ascending=[False, False])
    before = len(work)
    work = work.drop_duplicates(subset=["_idkey"], keep="first")
    removed = before - len(work)
    work = work.sort_values("_order")
    return work.drop(columns=["_idkey", "_order", "_vintage"], errors="ignore"), removed


def repair_file(path: Path, dry_run: bool) -> None:
    if not path.exists():
        print(f"skip {path.name}: not found")
        return
    df = normalize_today_price_column_names(pd.read_csv(path, low_memory=False))
    original_rows = len(df)
    collapsed, removed = collapse_to_freshest(df)
    refreshed = refresh_quality_columns(collapsed)

    changed_cols = []
    for column in ("R:R Static", "R:R Dynamic", "Timeliness Score", "Reward Remaining [%]"):
        if column not in collapsed.columns:
            continue
        before = collapsed[column].astype(str).reset_index(drop=True)
        after = refreshed[column].astype(str).reset_index(drop=True)
        diff = int((before != after).sum())
        if diff:
            changed_cols.append(f"{column}: {diff} rows")

    print(f"\n{path.name}: {original_rows} rows -> {len(refreshed)} ({removed} stale duplicates dropped)")
    for line in changed_cols:
        print(f"   recomputed {line}")

    if dry_run:
        print("   dry run — nothing written")
        return
    backup = path.with_suffix(path.suffix + ".prerepair")
    shutil.copy2(path, backup)
    refreshed.to_csv(path, index=False)
    print(f"   written (backup at {backup.name})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="report without writing")
    parser.add_argument("--data-dir", default=str(ROOT / "chatbot" / "data"))
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    for name in TARGET_FILES:
        repair_file(data_dir / name, args.dry_run)


if __name__ == "__main__":
    main()
