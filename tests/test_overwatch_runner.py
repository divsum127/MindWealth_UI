"""In-process Overwatch scheduler + SSE bus delivery.

The bus is per-process, so publishing from a cron interpreter reached nobody.
These tests pin the two things that make push work: a bound loop lets a worker
thread deliver to live subscribers, and the scan loops are actually started.
"""

from __future__ import annotations

import asyncio
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.services import overwatch_runner as runner
from api.services.overwatch_event_bus import OverwatchEventBus


class TestBusDeliversFromWorkerThread(unittest.TestCase):
    def test_publish_sync_off_loop_reaches_a_subscriber(self) -> None:
        async def scenario() -> dict:
            bus = OverwatchEventBus()
            bus.bind_loop(asyncio.get_running_loop())

            received: list[dict] = []
            ready = asyncio.Event()

            async def consume() -> None:
                agen = bus.subscribe()
                # subscribe() registers on first anext()
                task = asyncio.ensure_future(agen.__anext__())
                await asyncio.sleep(0.05)
                ready.set()
                received.append(await task)

            consumer = asyncio.ensure_future(consume())
            await ready.wait()

            # This is what a scan thread does.
            await asyncio.to_thread(bus.publish_sync, {"id": "from-thread"})
            await asyncio.wait_for(consumer, timeout=2)
            return received[0]

        alert = asyncio.run(scenario())
        self.assertEqual(alert["id"], "from-thread")

    def test_unbound_bus_without_a_loop_does_not_raise(self) -> None:
        bus = OverwatchEventBus()
        bus.publish_sync({"id": "orphan"})  # standalone cron process


class TestSchedulerWiring(unittest.TestCase):
    def test_start_creates_one_task_per_scan(self) -> None:
        async def scenario() -> list[str]:
            tasks = runner.start()
            names = sorted(t.get_name() for t in tasks)
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            return names

        self.assertEqual(
            asyncio.run(scenario()),
            ["overwatch-macro", "overwatch-signals", "overwatch-system"],
        )

    def test_scheduler_can_be_disabled(self) -> None:
        async def scenario() -> list:
            with patch.dict(os.environ, {"OVERWATCH_SCHEDULER": "0"}):
                return runner.start()

        self.assertEqual(asyncio.run(scenario()), [])

    def test_a_failing_scan_does_not_kill_the_loop(self) -> None:
        """A scan that raises must be logged and retried, not terminate the task."""
        calls: list[int] = []

        def boom() -> int:
            calls.append(1)
            raise RuntimeError("scan exploded")

        async def scenario() -> None:
            from datetime import datetime, timedelta, timezone

            def always_due(now: datetime) -> datetime:
                return now - timedelta(seconds=1)

            task = asyncio.create_task(runner._loop_for("test", always_due, boom))
            await asyncio.sleep(2.5)
            still_running = not task.done()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            self.assertTrue(still_running)

        asyncio.run(scenario())
        self.assertGreaterEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
