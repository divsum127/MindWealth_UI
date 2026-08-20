#!/usr/bin/env python3
"""Run CFTC SQUEEZE / LIQUIDITY EXIT re-run per Rohit Aug 2026 email spec."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.sentiment_superindex.analysis.cftc_grid_v2 import build_robustness_report, run_and_report, run_robustness_checks
from src.sentiment_superindex.analysis.cftc_episode_metrics import load_analysis_context
from src.sentiment_superindex.analysis.report_utils import save_artifact, write_md_snippet


def main() -> None:
    parser = argparse.ArgumentParser(description="CFTC pattern re-run (Rohit spec)")
    parser.add_argument("--start", default="2006-01-01", help="Analysis start date for forward returns")
    parser.add_argument(
        "--robustness-only",
        action="store_true",
        help="Skip full grid; run 12-offset subsample stability + block bootstrap only",
    )
    parser.add_argument(
        "--no-bootstrap",
        action="store_true",
        help="Skip stationary block bootstrap (subsample stability still runs)",
    )
    args = parser.parse_args()
    if args.robustness_only:
        ctx = load_analysis_context(start=args.start, pctile_start="2006-01-01")
        robustness = run_robustness_checks(ctx, run_bootstrap=not args.no_bootstrap)
        save_artifact("cftc_robustness_subsample", robustness)
        md_path = write_md_snippet("cftc_robustness_subsample", build_robustness_report(robustness))
        print(f"Robustness report: {md_path}")
        for cell in robustness["cells"]:
            stab = cell["subsample_stability"]
            print(
                f"{cell['condition']}: full excess={stab['full']['mean_excess']}% "
                f"stable={stab['stable_across_offsets']} "
                f"offsets+={stab['offsets_positive_excess']}/{stab['offsets_with_data']}"
            )
        return
    result = run_and_report(start=args.start, run_bootstrap=not args.no_bootstrap)
    print(f"Report written: {result['report_md']}")
    print(f"Robustness report: {result['robustness_md']}")
    sq = result["squeeze"]
    print(f"SQUEEZE cells: {len(sq['rows'])} | par episodes: {sq['par'].get('n_episodes')}")
    liq = result["liquidity"]
    print(f"LIQUIDITY EXIT cells: {len(liq['rows'])}")
    reg = result["regression"]
    print("FM pctile regression:", reg.get("rows"))


if __name__ == "__main__":
    main()
