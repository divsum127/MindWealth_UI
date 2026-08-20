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
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Record the loop that owns the subscriber queues.

        Scans run in worker threads, where ``asyncio.get_running_loop()`` fails
        and touching a queue directly is not thread-safe. With the loop bound,
        ``publish_sync`` hands the work back to it instead.
        """
        self._loop = loop

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
        """Publish from sync code — a worker thread, or a standalone script."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None:
            loop.create_task(self.publish(alert))
            return

        bound = self._loop
        if bound is not None and bound.is_running():
            # Called off-loop (scan thread): schedule on the owning loop.
            asyncio.run_coroutine_threadsafe(self.publish(alert), bound)
            return

        # No loop anywhere — a standalone cron process. Its subscriber set is
        # empty by definition, so this is a no-op kept only for compatibility.
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(alert)
            except asyncio.QueueFull:
                self._subscribers.discard(queue)

    @staticmethod
    def format_sse(alert: dict[str, Any]) -> str:
        return f"data: {json.dumps(alert, default=str)}\n\n"


event_bus = OverwatchEventBus()
