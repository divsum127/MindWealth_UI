#!/usr/bin/env python3
"""Sync CPI consensus/actual from Trading Economics (+ optional Investing.com) into pending_releases."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.data.investing_cpi_consensus import (
    _investing_fallback_enabled,
    fetch_cpi_consensus_calendar,
    fetch_fred_cpi_release_dates,
    fetch_tradingeconomics_cpi_calendar,
    latest_cpi_consensus_row,
    sync_cpi_releases_to_db,
)


def main() -> int:
    te = fetch_tradingeconomics_cpi_calendar()
    print(f"Trading Economics CPI rows parsed: {len(te)}")
    if _investing_fallback_enabled():
        print("INVESTING_HTTP_PROXY set — Investing.com fallback enabled")
    else:
        print("Investing.com fallback disabled (set INVESTING_HTTP_PROXY to enable)")
    fred_dates = fetch_fred_cpi_release_dates(limit=6)
    if fred_dates:
        print(f"FRED CPI release dates (latest): {fred_dates[-3:]}")
    live = fetch_cpi_consensus_calendar()
    print(f"Live CPI rows (TE + optional Investing + FRED dates): {len(live)}")
    for r in live:
        if r.consensus is not None or r.actual is not None:
            print(
                f"  {r.release_date} {r.event_name} [{r.source}]: "
                f"consensus={r.consensus} actual={r.actual} previous={r.previous}"
            )
    latest = latest_cpi_consensus_row()
    if latest:
        print(f"Latest headline consensus: {latest.consensus} ({latest.source}) date={latest.release_date}")
    else:
        print("No headline CPI consensus available from live sources")
    n = sync_cpi_releases_to_db()
    print(f"Synced {n} rows to pending_releases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
