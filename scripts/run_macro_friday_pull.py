#!/usr/bin/env python3
"""Friday EOD: pull macro variables and run combo engine."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.jobs.friday_pull import run_friday_pull  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Runic Agent Friday data pull")
    parser.add_argument("--date", help="As-of date YYYY-MM-DD")
    args = parser.parse_args()
    result = run_friday_pull(args.date)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
