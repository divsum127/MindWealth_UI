#!/usr/bin/env python3
"""Backfill post-event transition classification for historical macro events."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.data.macro_calendar import ingest_macro_release_date
from src.macro_intelligence.db.connection import init_db
from src.macro_intelligence.engine.post_event_transition import detect_post_event_transition


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate post-event transitions for event dates")
    parser.add_argument("--event-type", required=True, choices=["CPI", "FOMC", "NFP"])
    parser.add_argument("--event-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--as-of", required=True, help="Evaluation date within 48h after event")
    args = parser.parse_args()

    init_db()
    ingest_macro_release_date(args.event_type, args.event_date, source="backfill")
    result = detect_post_event_transition(args.as_of)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
