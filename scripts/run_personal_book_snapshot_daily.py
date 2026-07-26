#!/usr/bin/env python
"""Daily personal-book (book_id=personal) snapshot — run once per trading day.

Personal is a user-entered holdings tracker with no historical NAV series of its own — we don't
know what the user held on any past date, so ``get_personal_nav_payload()`` only ever returns a
single live snapshot today (see ``api/services/personal_book_service.py``). Rather than fabricate
a backfill, this job starts capturing that live snapshot once per day from today forward, same
"set up books from today" pattern as ``run_portfolio_book_snapshot_daily.py``. Once enough days
have accumulated, ``personal_book_service.get_personal_nav_history()`` can serve a real (if short)
daily series instead of always being empty — the no-backfill boundary is still disclosed via
``data_status``.

If the personal book is empty (no holdings, no cash) on a given day, the snapshot is still
written (NAV 0) so gaps in the series are explicit rather than silently missing.

Usage: python scripts/run_personal_book_snapshot_daily.py [--date YYYY-MM-DD]

Cron: installed by scripts/install_aws_cron.sh alongside the other daily book-state jobs.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("run_personal_book_snapshot_daily")


def run_snapshot(snapshot_date: str) -> dict[str, Any]:
    from api.services import personal_book_service
    from src.portfolio_nav import book_snapshot_store as store

    snap = personal_book_service.get_personal_snapshot()
    store.write_personal_book_snapshot(
        snapshot_date,
        nav_usd=snap.get("total_market_value_usd"),
        cash_usd=snap.get("cash_usd"),
        position_count=snap.get("position_count") or 0,
        total_pnl_usd=snap.get("total_pnl_usd"),
        total_pnl_pct=snap.get("total_pnl_pct"),
        holdings=snap.get("holdings"),
    )
    logger.info(
        "Personal book snapshot %s: NAV=%s, cash=%s, positions=%d",
        snapshot_date, snap.get("total_market_value_usd"), snap.get("cash_usd"),
        snap.get("position_count") or 0,
    )
    return {
        "date": snapshot_date,
        "nav_usd": snap.get("total_market_value_usd"),
        "position_count": snap.get("position_count") or 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=None, help="Snapshot date YYYY-MM-DD (default: today UTC)")
    args = parser.parse_args()

    snapshot_date = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        run_snapshot(snapshot_date)
    except Exception:
        logger.exception("Personal book snapshot failed for %s", snapshot_date)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
