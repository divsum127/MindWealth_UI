#!/usr/bin/env python3
"""Ingest CPI release: actual and consensus -> surprise_pp in cpi_surprises.csv."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.data.cpi_pull import ingest_release, validate_cpi_csv  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest CPI surprise")
    parser.add_argument("--date", required=True, help="Release date YYYY-MM-DD")
    parser.add_argument("--actual", type=float, required=True)
    parser.add_argument("--consensus", type=float, required=True)
    args = parser.parse_args()
    surprise = ingest_release(args.date, args.actual, args.consensus)
    ok, msg = validate_cpi_csv()
    print(f"surprise_pp={surprise:.4f} validation={msg}" if ok else f"validation failed: {msg}")


if __name__ == "__main__":
    main()
