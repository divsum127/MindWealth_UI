#!/usr/bin/env python3
"""Sync CPI, FOMC, and NFP scheduled releases into pending_releases."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.db.connection import init_db
from src.macro_intelligence.data.macro_calendar import sync_macro_releases_to_db


def main() -> None:
    init_db()
    n = sync_macro_releases_to_db()
    print(f"Synced {n} macro release rows to pending_releases")


if __name__ == "__main__":
    main()
