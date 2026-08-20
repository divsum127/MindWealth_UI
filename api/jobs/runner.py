"""Background execution of chatbot smart_followup_query jobs."""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from chatbot import ChatbotEngine
from chatbot.flagged_export import serialize_metadata_for_json

from .store import get_job_store

logger = logging.getLogger(__name__)

_MAX_WORKERS = int(os.getenv("CHATBOT_JOB_WORKERS", "2"))
_executor: ThreadPoolExecutor | None = None


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=_MAX_WORKERS, thread_name_prefix="chatbot-job")
    return _executor


def shutdown_executor() -> None:
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=False, cancel_futures=True)
        _executor = None


def _run_job(job_id: str, session_id: str, followup_kwargs: dict[str, Any]) -> None:
    from datetime import datetime, timezone

    store = get_job_store()
    store.update(job_id, status="running", started_at=datetime.now(timezone.utc).isoformat())

    def on_flow_step(stage: str, detail: str) -> None:
        store.append_flow_step(job_id, stage, detail)

    try:

        engine = ChatbotEngine(session_id=session_id)
        response, metadata = engine.smart_followup_query(**followup_kwargs, on_flow_step=on_flow_step)
        safe_meta = serialize_metadata_for_json(metadata or {})

        store.update(
            job_id,
            status="completed",
            completed_at=datetime.now(timezone.utc).isoformat(),
            result={"content": response, "metadata": safe_meta},
            error=None,
        )
    except Exception as exc:
        logger.exception("Chatbot job %s failed", job_id)

        # `error` is rendered directly by the chat client, so it must not carry
        # provider text (an Anthropic billing message once reached a user with
        # its request_id). The raw exception stays on the record as
        # `error_detail` and in the log above.
        from chatbot.error_messages import safe_error_metadata  # noqa: PLC0415

        safe = safe_error_metadata(exc)
        store.update(
            job_id,
            status="failed",
            completed_at=datetime.now(timezone.utc).isoformat(),
            error=safe["error"],
            error_detail=safe["error_detail"],
        )
        _persist_failure_to_history(session_id, exc)


def _persist_failure_to_history(session_id: str, exc: Exception) -> None:
    """
    Record a failed turn in the session history.

    Failures were previously never persisted anywhere the UI reads, so after a
    refresh a failed exchange vanished entirely and the user could not tell
    whether the question had been asked at all.
    """
    try:
        from chatbot.history_manager import HistoryManager

        from chatbot.error_messages import safe_error_metadata  # noqa: PLC0415

        safe = safe_error_metadata(exc)
        HistoryManager(session_id=session_id).add_message(
            "assistant",
            safe["error"],
            {**safe, "job_failed": True},
        )
    except Exception:
        logger.warning("Could not persist job failure to history for session %s", session_id)


def enqueue_chatbot_job(session_id: str, followup_kwargs: dict[str, Any], request_snapshot: dict[str, Any]) -> dict[str, Any]:
    store = get_job_store()
    job = store.create(session_id=session_id, request=request_snapshot)
    job_id = job["job_id"]
    _get_executor().submit(_run_job, job_id, session_id, followup_kwargs)
    return job
