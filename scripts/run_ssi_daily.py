#!/usr/bin/env python3
"""Daily SSI job: write positioning.json for C++."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.sentiment_superindex.jobs.daily_run import run_ssi_daily  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run SSI daily positioning.json")
    parser.add_argument("--date", default=None, help="As-of date YYYY-MM-DD")
    parser.add_argument(
        "--allow-degraded",
        action="store_true",
        help="Exit 0 even when a layer is below its coverage minimum (cron should not set this)",
    )
    args = parser.parse_args()

    # Without a handler the coverage/pull warnings this job now emits would go nowhere, which
    # is the failure mode being fixed: ssi_daily.log used to contain nothing but pandas noise.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )

    payload = run_ssi_daily(args.date)
    print(
        json.dumps(
            {
                "date": payload["date"],
                "path": payload.get("output_path"),
                "ssi_multiplier": payload["ssi_multiplier"],
                "coverage_ok": payload.get("coverage_ok", True),
                "unreliable_layers": sorted(payload.get("coverage_unreliable_layers") or {}),
            },
            indent=2,
        )
    )

    # Non-zero exit so cron surfaces a degraded run instead of reporting success on a
    # positioning.json that is missing inputs.
    if not payload.get("coverage_healthy", True) and not args.allow_degraded:
        sys.exit(2)


if __name__ == "__main__":
    main()
