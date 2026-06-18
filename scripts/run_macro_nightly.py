#!/usr/bin/env python3
"""Nightly Mon-Fri: generate runic_output.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.jobs.nightly_run import run_nightly  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Runic Agent nightly run")
    parser.add_argument("--date", help="As-of date YYYY-MM-DD")
    parser.add_argument("--no-claude", action="store_true", help="Skip Claude API calls")
    args = parser.parse_args()
    result = run_nightly(args.date, use_claude=not args.no_claude)
    print(json.dumps({k: v for k, v in result.items() if k not in ("narrative",)}, indent=2, default=str))
    if result.get("source_freshness"):
        print("\n--- source freshness (CAPE / CFTC) ---")
        print(json.dumps(result["source_freshness"], indent=2))
    if result.get("briefing_paths"):
        print("\n--- briefing outputs ---")
        for fmt, path in result["briefing_paths"].items():
            print(f"  {fmt}: {path}")
    print("\n--- narrative ---\n")
    print(result.get("narrative", ""))


if __name__ == "__main__":
    main()
