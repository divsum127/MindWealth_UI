#!/usr/bin/env python3
"""Import AAII sentiment from CSV or XLS (when AAII blocks automated download)."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config_paths import MACRO_INTEL_DATA_DIR
from src.sentiment_superindex.data.aaii_pull import CACHE_XLS, ingest_aaii_csv


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest AAII sentiment file")
    parser.add_argument("path", type=Path, help="CSV (date,bullish,bearish) or .xls from aaii.com")
    args = parser.parse_args()
    src = args.path.resolve()
    if not src.exists():
        print(f"File not found: {src}")
        return 1
    if src.suffix.lower() in (".xls", ".xlsx"):
        MACRO_INTEL_DATA_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, CACHE_XLS)
        from src.sentiment_superindex.data.aaii_pull import fetch_aaii_spread

        s = fetch_aaii_spread()
    else:
        s = ingest_aaii_csv(src)
    print(f"AAII spread series: {len(s)} rows")
    if len(s):
        print(f"  last: {s.index[-1].date()} = {float(s.iloc[-1]):.2f}")
    return 0 if len(s) else 1


if __name__ == "__main__":
    raise SystemExit(main())
