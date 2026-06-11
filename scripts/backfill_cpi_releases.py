#!/usr/bin/env python3
"""Seed historical CPI MoM releases (TE/Investing consensus + BLS actual) into pending_releases."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.data.investing_cpi_consensus import (
    _investing_fallback_enabled,
    build_cpi_backfill_rows,
    fetch_tradingeconomics_cpi_calendar,
    upsert_cpi_releases,
)
from src.macro_intelligence.db.connection import get_connection, init_db


def _count_cpi_rows() -> tuple[int, str | None, str | None]:
    with get_connection() as conn:
        n = conn.execute(
            "SELECT COUNT(*) AS n FROM pending_releases WHERE release_type='CPI'"
        ).fetchone()["n"]
        row = conn.execute(
            "SELECT MIN(release_date) AS lo, MAX(release_date) AS hi "
            "FROM pending_releases WHERE release_type='CPI'"
        ).fetchone()
    return int(n), row["lo"], row["hi"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill CPI releases into pending_releases")
    parser.add_argument("--weeks-back", type=int, default=520, help="Investing.com history window when proxy set")
    parser.add_argument("--start-year", type=int, default=1990)
    parser.add_argument("--no-bls", action="store_true", help="Skip BLS actual enrichment")
    args = parser.parse_args()

    init_db()
    before_n, before_lo, before_hi = _count_cpi_rows()
    print(f"pending_releases CPI before: {before_n} rows ({before_lo} .. {before_hi})")

    te = fetch_tradingeconomics_cpi_calendar()
    headline_te = [r for r in te if "core" not in r.event_name.lower()]
    print(f"Trading Economics headline rows (live HTML): {len(headline_te)}")
    if headline_te:
        print(f"  TE date range: {headline_te[0].release_date} .. {headline_te[-1].release_date}")
    if _investing_fallback_enabled():
        print(f"Investing.com fallback enabled (weeks_back={args.weeks_back})")
    else:
        print("Investing.com disabled (set INVESTING_HTTP_PROXY for deeper consensus history)")

    rows = build_cpi_backfill_rows(
        weeks_back=args.weeks_back,
        start_year=args.start_year,
        enrich_bls_actual=not args.no_bls,
    )
    with_consensus = [r for r in rows if r.consensus is not None and r.actual is not None]
    print(f"Backfill candidates (actual+consensus): {len(with_consensus)}")
    if with_consensus:
        print(
            f"  Candidate range: {with_consensus[0].release_date} .. {with_consensus[-1].release_date}"
        )
        hot = [r for r in with_consensus if abs((r.actual or 0) - (r.consensus or 0)) >= 0.2]
        print(f"  Hot surprises (|surprise|>=0.2pp): {len(hot)}")
        for r in with_consensus[-5:]:
            surprise = (r.actual or 0) - (r.consensus or 0)
            print(
                f"    {r.release_date} actual={r.actual} consensus={r.consensus} "
                f"surprise={surprise:+.2f} [{r.source}]"
            )

    stats = upsert_cpi_releases(with_consensus)
    after_n, after_lo, after_hi = _count_cpi_rows()
    print(f"Upserted: {stats['upserted']}, skipped: {stats['skipped']}")
    print(f"pending_releases CPI after: {after_n} rows ({after_lo} .. {after_hi})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
