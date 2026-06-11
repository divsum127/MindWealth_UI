#!/usr/bin/env python3
"""Historical backfill for macro intelligence database."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.data.pull_all import load_all_series, pull_all_series
from src.macro_intelligence.db.connection import init_db
from src.macro_intelligence.db.migrate import migrate_db
from src.macro_intelligence.db.regime_log import upsert_macro_regime_log
from src.macro_intelligence.engine.combo_detector import detect_all_combos
from src.macro_intelligence.engine.fed_cycle import build_fed_cycle_series, clear_fed_cycle_cache
from src.macro_intelligence.engine.forward_returns import backfill_forward_returns
from src.macro_intelligence.engine.regime_rules import build_python_regime
from src.macro_intelligence.engine.persistence import run_persistence_scan


def _fridays(start: datetime, end: datetime) -> list[str]:
    cur = start
    out: list[str] = []
    while cur <= end:
        if cur.weekday() == 4:
            out.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill Runic macro history")
    parser.add_argument("--regime-from", default="1990-01-01")
    parser.add_argument("--combos-from", default="2006-01-06")
    parser.add_argument("--end", default=None)
    parser.add_argument("--weekly-only", action="store_true", default=True)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--wipe", action="store_true", help="Wipe tables before backfill")
    parser.add_argument("--skip-combos", action="store_true")
    parser.add_argument("--skip-persistence", action="store_true", default=True)
    parser.add_argument("--with-persistence", action="store_true", help="Run persistence scan each date")
    args = parser.parse_args()

    if args.wipe:
        subprocess.check_call(
            [sys.executable, str(ROOT / "scripts" / "wipe_runic_db.py"), "--yes"],
            cwd=str(ROOT),
        )

    init_db()
    migrate_db()
    clear_fed_cycle_cache()
    load_all_series(force=True)
    build_fed_cycle_series(force=True)

    end = datetime.strptime(args.end, "%Y-%m-%d") if args.end else datetime.now()
    regime_start = datetime.strptime(args.regime_from, "%Y-%m-%d")
    combo_start = datetime.strptime(args.combos_from, "%Y-%m-%d")

    dates = _fridays(regime_start, end)
    if args.limit:
        dates = dates[: args.limit]

    n = 0
    for ds in dates:
        pull_all_series(ds, persist_cftc=True)
        regime = build_python_regime(ds)
        upsert_macro_regime_log(ds, regime, model="python_backfill")

        if not args.skip_combos and pd_timestamp(ds) >= combo_start:
            detect_all_combos(ds, persist=True, macro_regime=regime)
            if args.with_persistence and not args.skip_persistence:
                run_persistence_scan(ds)

        n += 1
        if n % 50 == 0:
            print(f"  ... {n} dates ({ds})", flush=True)

    print("Filling SPX forward returns for combo fires...", flush=True)
    filled = backfill_forward_returns()
    print(f"Backfill complete: {n} dates processed, forward_returns filled: {filled}", flush=True)
    return 0


def pd_timestamp(s: str):
    return datetime.strptime(s, "%Y-%m-%d")


if __name__ == "__main__":
    raise SystemExit(main())
