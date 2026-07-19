"""Overwatch SSE push routes."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from api.dependencies import optional_api_key
from api.services.overwatch_event_bus import event_bus

router = APIRouter(
    prefix="/overwatch",
    tags=["overwatch"],
    dependencies=[Depends(optional_api_key)],
)


@router.get(
    "/stream",
    operation_id="overwatch_stream",
    summary="SSE stream for Overwatch auto-triggered alerts",
)
async def overwatch_stream() -> StreamingResponse:
    async def event_generator():
        heartbeat = 0
        try:
            async for alert in event_bus.subscribe():
                yield event_bus.format_sse(alert)
                heartbeat = 0
        except asyncio.CancelledError:
            return
        finally:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
