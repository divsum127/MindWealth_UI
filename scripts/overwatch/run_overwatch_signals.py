#!/usr/bin/env python3
"""Daily Overwatch signals scan — publish new degradation alerts via SSE bus."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.services.analyst_service import scan_and_publish_new_alerts  # noqa: E402


def main() -> int:
    store = _ROOT / "overwatch_store" / "alert_state.json"
    new_alerts = scan_and_publish_new_alerts(
        state_path=str(store),
        floor_pct=60.0,
    )
    print(f"overwatch_signals: published {len(new_alerts)} new alert(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
