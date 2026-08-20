"""In-process Overwatch scan loop.

Why in-process: ``overwatch_event_bus`` is a module-level asyncio bus, so a
subscriber only ever sees events published from *the same process*. The cron
scripts in ``scripts/overwatch/`` run in their own interpreter, meaning
``publish_sync`` there fans out to an empty subscriber set and every alert is
dropped on the floor. SSE has therefore never delivered anything, whether or not
cron was installed.

Running the scans on the API's own event loop closes that gap without adding a
broker. It also means ``meta.next_signal_check`` describes something the API will
actually do.

Constraints, deliberately kept simple:

  * Single worker only. The bus is per-process, so with N workers each client is
    attached to one worker and would only see 1/N of the alerts. The API already
    runs ``--workers 1`` for exactly this reason.
  * Scans are blocking (pandas + CSV) and run in a thread, never on the loop.
  * ``scan_and_publish_new_alerts`` dedupes against ``alert_state.json``, so a
    still-installed crontab cannot cause double publishes.

Set ``OVERWATCH_SCHEDULER=0`` to disable, e.g. when cron owns the schedule.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

from api.services import overwatch_schedule as schedule

logger = logging.getLogger(__name__)

# Never sleep longer than this in one hop, so a clock jump or a suspended host
# cannot park the loop for hours.
_MAX_SLEEP_SECONDS = 300.0


def scheduler_enabled() -> bool:
    return os.getenv("OVERWATCH_SCHEDULER", "1").strip().lower() not in {"0", "false", "no"}


def _run_signals_scan() -> int:
    from api.services.analyst_service import scan_and_publish_new_alerts
    from api.services.degradation_service import warm_degradation_cache

    warm_degradation_cache()
    return len(scan_and_publish_new_alerts())


def _run_macro_scan() -> int:
    from api.services.analyst_service import scan_and_publish_new_alerts

    return len(scan_and_publish_new_alerts())


def _run_system_scan() -> int:
    from api.main import API_VERSION
    from api.services import system_health_service as health_svc
    from api.services.overwatch_event_bus import event_bus

    result = health_svc.run_system_health(API_VERSION)
    alerts = health_svc.system_checks_to_panel_alerts(result["checks"], result["checked_at"])
    for alert in alerts:
        event_bus.publish_sync(alert)
    return len(alerts)


async def _loop_for(name: str, next_due, runner) -> None:
    while True:
        now = datetime.now(timezone.utc)
        due = next_due(now)
        delay = max(1.0, (due - now).total_seconds())
        await asyncio.sleep(min(delay, _MAX_SLEEP_SECONDS))
        if datetime.now(timezone.utc) < due:
            continue  # capped sleep — go round again
        try:
            published = await asyncio.to_thread(runner)
            logger.info("overwatch %s scan: published %s alert(s)", name, published)
        except Exception as exc:  # a failed scan must not kill the loop
            logger.warning("overwatch %s scan failed: %s", name, exc)


def start(loop: asyncio.AbstractEventLoop | None = None) -> list[asyncio.Task]:
    """Start the three scan loops. Returns the tasks so lifespan can cancel them."""
    if not scheduler_enabled():
        logger.info("overwatch scheduler disabled via OVERWATCH_SCHEDULER")
        return []

    from api.services.overwatch_event_bus import event_bus

    event_bus.bind_loop(loop or asyncio.get_running_loop())

    specs = [
        ("signals", schedule.SIGNALS_SCAN.next_after, _run_signals_scan),
        ("macro", schedule.MACRO_SCAN.next_after, _run_macro_scan),
        ("system", schedule.SYSTEM_SCAN.next_after, _run_system_scan),
    ]
    tasks = [asyncio.create_task(_loop_for(n, d, r), name=f"overwatch-{n}") for n, d, r in specs]
    logger.info("overwatch scheduler started (%s loops)", len(tasks))
    return tasks
