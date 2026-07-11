#!/usr/bin/env python3
"""Persist v2 shadow regime tags onto combo_fires.macro_regime (merge, not wipe)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.analysis.regime_v2_enrich import retag_combo_fires_in_db  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge v2 regime tags into combo_fires")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Retag all combo_fires (default: generic / unnamed only)",
    )
    args = parser.parse_args()
    stats = retag_combo_fires_in_db(generic_only=not args.all)
    print(stats)


if __name__ == "__main__":
    main()
