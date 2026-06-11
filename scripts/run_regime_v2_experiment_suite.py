#!/usr/bin/env python3
"""Run Macro Regime v2 experiment suite (Parts A–I + FM track)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.analysis.regime_experiments.run_all import run_all_experiments
from src.macro_intelligence.analysis.regime_experiments.report_builder import write_master_report
from src.macro_intelligence.db.migrate import migrate_db


def main() -> int:
    parser = argparse.ArgumentParser(description="Macro Regime v2 experiment suite")
    parser.add_argument("--skip-report", action="store_true")
    parser.add_argument("--skip-h-part", action="store_true", help="Skip combo discovery re-run")
    args = parser.parse_args()

    migrate_db()
    manifest = run_all_experiments()

    if not args.skip_h_part:
        try:
            from src.macro_intelligence.analysis.combo_discovery_pipeline import (
                run_combo_discovery_pipeline,
                write_pipeline_artifacts,
            )

            payload = run_combo_discovery_pipeline(use_claude=False)
            write_pipeline_artifacts(payload, write_report=True)
            manifest["part_h"] = {"summary": payload["summary"], "status": "COMPLETE"}
        except Exception as exc:
            manifest["part_h"] = {"status": "ERROR", "error": str(exc)}

    if not args.skip_report:
        report_path = write_master_report(manifest)
        manifest["master_report"] = str(report_path)
        print(json.dumps({"master_report": str(report_path)}, indent=2))

    out = Path("macro_intelligence/analysis/regime_v2_experiments/experiment_manifest.json")
    out.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"manifest": str(out), "keys": list(manifest.keys())}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
