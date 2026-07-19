"""In-process pub/sub for Overwatch SSE alerts (single uvicorn worker)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any


class OverwatchEventBus:
    """Thread-safe fan-out bus using asyncio queues per subscriber."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._lock = asyncio.Lock()

    async def publish(self, alert: dict[str, Any]) -> None:
        async with self._lock:
            dead: list[asyncio.Queue[dict[str, Any]]] = []
            for queue in self._subscribers:
                try:
                    queue.put_nowait(alert)
                except asyncio.QueueFull:
                    dead.append(queue)
            for queue in dead:
                self._subscribers.discard(queue)

    async def subscribe(self) -> AsyncIterator[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=64)
        async with self._lock:
            self._subscribers.add(queue)
        try:
            while True:
                alert = await queue.get()
                yield alert
        finally:
            async with self._lock:
                self._subscribers.discard(queue)

    def publish_sync(self, alert: dict[str, Any]) -> None:
        """Best-effort publish from sync cron scripts."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            for queue in list(self._subscribers):
                try:
                    queue.put_nowait(alert)
                except asyncio.QueueFull:
                    self._subscribers.discard(queue)
            return
        loop.create_task(self.publish(alert))

    @staticmethod
    def format_sse(alert: dict[str, Any]) -> str:
        return f"data: {json.dumps(alert, default=str)}\n\n"


event_bus = OverwatchEventBus()
