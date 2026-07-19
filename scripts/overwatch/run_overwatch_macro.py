#!/usr/bin/env python3
"""Overwatch macro scan — publish runic combo alerts after nightly macro run."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.services.analyst_service import get_panel_alerts, scan_and_publish_new_alerts  # noqa: E402


def main() -> int:
    store = _ROOT / "overwatch_store" / "alert_state.json"
    payload = get_panel_alerts(include_macro=True, include_degradation=False)
    macro_count = sum(1 for a in payload["panel_alerts"] if a.get("type") == "runic")
    new_alerts = scan_and_publish_new_alerts(state_path=str(store))
    macro_new = sum(1 for a in new_alerts if a.get("type") == "runic")
    print(f"overwatch_macro: {macro_count} runic active, published {macro_new} new")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
