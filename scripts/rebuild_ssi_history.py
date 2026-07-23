#!/usr/bin/env python3
"""Backfill ssi.db with 3-layer superindex history (recomputes all dates)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.sentiment_superindex.data.pull_all import load_all_series  # noqa: E402
from src.sentiment_superindex.db.connection import init_db, persist_daily  # noqa: E402
from src.sentiment_superindex.engine.positioning import build_positioning_payload  # noqa: E402
from src.sentiment_superindex.engine.ssi_score import (  # noqa: E402
    build_ssi_history,
    invalidate_ssi_history_cache,
)


def rebuild_ssi_history(start: str = "2015-01-01", *, limit: int | None = None) -> dict[str, object]:
    invalidate_ssi_history_cache()
    load_all_series(force=True)
    levels = build_ssi_history(start, force=True)
    if levels.empty:
        return {"rows": 0, "error": "no history levels"}

    dates = [d.strftime("%Y-%m-%d") for d in levels.index]
    if limit is not None:
        dates = dates[-limit:]

    init_db()
    count = 0
    for as_of in dates:
        payload = build_positioning_payload(as_of)
        persist_daily(payload)
        count += 1

    return {
        "rows": count,
        "start": dates[0] if dates else None,
        "end": dates[-1] if dates else None,
        "latest_ssi_level": levels.iloc[-1] if not levels.empty else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild ssi.db from superindex history")
    parser.add_argument("--start", default="2015-01-01", help="History start YYYY-MM-DD")
    parser.add_argument("--limit", type=int, default=None, help="Only persist last N dates")
    args = parser.parse_args()
    summary = rebuild_ssi_history(args.start, limit=args.limit)
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
