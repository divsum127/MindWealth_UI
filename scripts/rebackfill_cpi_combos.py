#!/usr/bin/env python3
"""Re-run CPI daily_readings and Combo C detection for dates near historical CPI releases."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.data.pull_all import load_all_series, pull_all_series
from src.macro_intelligence.db.connection import get_connection, init_db
from src.macro_intelligence.engine.combo_detector import detect_all_combos


def _cpi_release_dates(start: str | None, end: str | None) -> list[str]:
    with get_connection() as conn:
        q = "SELECT release_date FROM pending_releases WHERE release_type='CPI'"
        params: list[str] = []
        if start:
            q += " AND release_date >= ?"
            params.append(start)
        if end:
            q += " AND release_date <= ?"
            params.append(end)
        q += " ORDER BY release_date"
        rows = conn.execute(q, params).fetchall()
    return [str(r["release_date"])[:10] for r in rows]


def _fridays_near_releases(
    release_dates: list[str],
    *,
    lookback_days: int,
    forward_days: int,
) -> list[str]:
    out: set[str] = set()
    for rd in release_dates:
        anchor = datetime.strptime(rd, "%Y-%m-%d")
        start = anchor - timedelta(days=lookback_days)
        end = anchor + timedelta(days=forward_days)
        cur = start
        while cur <= end:
            if cur.weekday() == 4:
                out.add(cur.strftime("%Y-%m-%d"))
            cur += timedelta(days=1)
    return sorted(out)


def _combo_c_count() -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM combo_fires WHERE runic_combo='C'"
        ).fetchone()
    return int(row["n"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Targeted Combo C / CPI re-pass")
    parser.add_argument("--start", default=None, help="Only CPI releases on/after this date")
    parser.add_argument("--end", default=None)
    parser.add_argument("--lookback-days", type=int, default=14, help="Days before release to include Fridays")
    parser.add_argument("--forward-days", type=int, default=28, help="Days after release to include Fridays")
    parser.add_argument("--weekly-only", action="store_true", default=True)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    init_db()
    releases = _cpi_release_dates(args.start, args.end)
    if not releases:
        print("No CPI rows in pending_releases — run scripts/backfill_cpi_releases.py first")
        return 1

    dates = _fridays_near_releases(
        releases,
        lookback_days=args.lookback_days,
        forward_days=args.forward_days,
    )
    if args.limit:
        dates = dates[: args.limit]

    combo_c_before = _combo_c_count()
    print(f"CPI releases in scope: {len(releases)} ({releases[0]} .. {releases[-1]})")
    print(f"Fridays to reprocess: {len(dates)}")
    print(f"combo_fires Combo C before: {combo_c_before}")

    load_all_series(force=True)
    for i, ds in enumerate(dates, 1):
        pull_all_series(ds)
        detect_all_combos(ds, persist=True)
        if i % 25 == 0 or i == len(dates):
            print(f"  ... {i}/{len(dates)} ({ds})", flush=True)

    combo_c_after = _combo_c_count()
    print(f"combo_fires Combo C after: {combo_c_after} (delta {combo_c_after - combo_c_before})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
