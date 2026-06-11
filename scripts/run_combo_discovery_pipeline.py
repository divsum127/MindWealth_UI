#!/usr/bin/env python3
"""Part H — run 298-combo discovery pipeline once (monthly thereafter)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.analysis.combo_discovery_pipeline import (  # noqa: E402
    run_combo_discovery_pipeline,
    write_pipeline_artifacts,
)
from src.macro_intelligence.db.migrate import migrate_db  # noqa: E402
from src.macro_intelligence.engine.forward_returns import (  # noqa: E402
    backfill_extended_returns,
    backfill_forward_returns,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Part H combo discovery pipeline (298 combos)")
    parser.add_argument("--from-db", action="store_true", default=True, help="Use runic.db (default)")
    parser.add_argument("--horizon", default=None, help="Primary horizon column e.g. spx_3m")
    parser.add_argument("--backfill-returns", action="store_true", help="Backfill forward returns incl. 9m/12m")
    parser.add_argument("--use-claude", action="store_true", help="Step 7 narratives for survivors")
    parser.add_argument("--write-report", action="store_true", help="Write JSON + markdown report")
    parser.add_argument("--dry-run", action="store_true", help="Stats only, no Claude narratives")
    args = parser.parse_args()

    migrate_db()

    if args.backfill_returns:
        n = backfill_forward_returns()
        print(f"backfill_forward_returns: {n} rows", flush=True)
        ext = backfill_extended_returns()
        print(f"backfill_extended_returns: {ext} rows", flush=True)

    use_claude = args.use_claude and not args.dry_run
    payload = run_combo_discovery_pipeline(horizon=args.horizon, use_claude=use_claude)

    if args.write_report:
        json_path, md_path = write_pipeline_artifacts(payload, write_report=True)
        print(json.dumps({"json": str(json_path), "report": str(md_path), "summary": payload["summary"]}, indent=2))
    else:
        print(json.dumps({"summary": payload["summary"], "survivors": len(payload["survivors"])}, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
