#!/usr/bin/env python3
"""Fill forward_returns for combo_fires already in runic.db (fast path after date backfill)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.engine.forward_returns import backfill_forward_returns  # noqa: E402


def main() -> int:
    n = backfill_forward_returns()
    print(f"Done: {n} forward return rows upserted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
