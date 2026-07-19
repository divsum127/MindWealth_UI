#!/usr/bin/env python3
"""Overwatch system health scan — every 15 minutes."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.services import system_health_service as health_svc  # noqa: E402
from api.services.overwatch_event_bus import event_bus  # noqa: E402


def main() -> int:
    from api.main import API_VERSION  # noqa: PLC0415

    result = health_svc.run_system_health(API_VERSION)
    alerts = health_svc.system_checks_to_panel_alerts(result["checks"], result["checked_at"])
    for alert in alerts:
        event_bus.publish_sync(alert)
    print(
        f"overwatch_system: status={result['status']} "
        f"checks={len(result['checks'])} alerts_published={len(alerts)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
