#!/usr/bin/env python3
"""Run named combo gate sweeps (B/F/E/D) for threshold validation v2."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.analysis.combo_threshold_sweep import run_all_combo_sweeps  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out-dir",
        default="macro_intelligence/analysis/regime_v2_experiments/threshold_sweep_v2",
    )
    args = parser.parse_args()
    out_dir = ROOT / args.out_dir
    written = run_all_combo_sweeps(out_dir)
    print(json.dumps({"written": written}, indent=2))


if __name__ == "__main__":
    main()
