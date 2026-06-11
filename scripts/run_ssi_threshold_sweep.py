#!/usr/bin/env python3
"""Run SSI threshold sweep and write analysis reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.sentiment_superindex.analysis.threshold_sweep import (  # noqa: E402
    apply_recommended_to_config,
    sweep_thresholds,
    write_sweep_report,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="SSI threshold sweep")
    parser.add_argument("--start", default="2015-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument("--horizon", type=int, default=63)
    parser.add_argument("--write-config", action="store_true", help="Patch SSI_CONFIG.yaml with best thresholds")
    args = parser.parse_args()

    result = sweep_thresholds(start=args.start, end=args.end, horizon_days=args.horizon)
    jp, cp = write_sweep_report(result)
    print(json.dumps({"json": str(jp), "csv": str(cp), "recommended": result.get("recommended")}, indent=2))
    if args.write_config and "error" not in result:
        apply_recommended_to_config(result)
        print("Updated macro_intelligence/SSI_CONFIG.yaml thresholds")


if __name__ == "__main__":
    main()
