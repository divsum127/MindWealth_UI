"""Overwatch scan schedule — single source of truth for cron *and* the API.

The three Overwatch scans were only ever expressed as crontab lines in
``scripts/install_aws_cron_dual.sh``. That had two consequences:

  * ``meta.next_signal_check`` / ``meta.next_macro_scan`` were always ``null``,
    because nothing in the API knew when the next scan was due; and
  * publishing over SSE from cron could never work — ``overwatch_event_bus`` is
    an in-process asyncio bus, so a separate cron process fans out to its own
    empty subscriber set and the alert is dropped.

Running the scans inside the API process fixes both. Times are UTC, matching the
existing crontab entries, so behaviour is unchanged if cron is also installed
(the alert-state file dedupes, so a double scan publishes nothing twice).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

WEEKDAYS = {0, 1, 2, 3, 4}  # Mon-Fri, matching `* * 1-5` in the crontab


@dataclass(frozen=True)
class DailySchedule:
    """A scan that runs at a fixed UTC time on given weekdays."""

    hour: int
    minute: int
    weekdays: frozenset[int]

    def next_after(self, now: datetime) -> datetime:
        candidate = now.astimezone(timezone.utc).replace(
            hour=self.hour, minute=self.minute, second=0, microsecond=0
        )
        if candidate <= now:
            candidate += timedelta(days=1)
        for _ in range(8):
            if candidate.weekday() in self.weekdays:
                return candidate
            candidate += timedelta(days=1)
        return candidate


@dataclass(frozen=True)
class IntervalSchedule:
    """A scan that runs every N minutes, on the wall-clock grid."""

    minutes: int

    def next_after(self, now: datetime) -> datetime:
        now = now.astimezone(timezone.utc)
        floor = now.replace(second=0, microsecond=0) - timedelta(
            minutes=now.minute % self.minutes
        )
        return floor + timedelta(minutes=self.minutes)


# Mirrors scripts/install_aws_cron_dual.sh lines 40-42.
MACRO_SCAN = DailySchedule(hour=18, minute=30, weekdays=frozenset(WEEKDAYS))
SIGNALS_SCAN = DailySchedule(hour=19, minute=0, weekdays=frozenset(WEEKDAYS))
SYSTEM_SCAN = IntervalSchedule(minutes=15)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def next_signal_check(now: datetime | None = None) -> str:
    return _iso(SIGNALS_SCAN.next_after(now or datetime.now(timezone.utc)))


def next_macro_scan(now: datetime | None = None) -> str:
    return _iso(MACRO_SCAN.next_after(now or datetime.now(timezone.utc)))


def next_system_scan(now: datetime | None = None) -> str:
    return _iso(SYSTEM_SCAN.next_after(now or datetime.now(timezone.utc)))
