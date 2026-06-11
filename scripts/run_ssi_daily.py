#!/usr/bin/env python3
"""Daily SSI job: write positioning.json for C++."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.sentiment_superindex.jobs.daily_run import run_ssi_daily  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run SSI daily positioning.json")
    parser.add_argument("--date", default=None, help="As-of date YYYY-MM-DD")
    args = parser.parse_args()
    payload = run_ssi_daily(args.date)
    print(json.dumps({"date": payload["date"], "path": payload.get("output_path"), "ssi_multiplier": payload["ssi_multiplier"]}, indent=2))


if __name__ == "__main__":
    main()
