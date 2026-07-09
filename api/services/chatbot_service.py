"""Chatbot API service adapters."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from chatbot import ChatbotEngine, SessionManager
from chatbot.flagged_export import save_flagged_pair
from chatbot.signal_type_selector import (
    ALLOWED_SIGNAL_TYPES,
    DEFAULT_SIGNAL_TYPES,
    SIGNAL_TYPE_DESCRIPTIONS,
)
from prompts.ui_buttons import (
    format_analyze_asset_prompt,
    format_breadth_analysis_prompt,
    format_signal_insights_prompt,
)

from api.jobs.runner import enqueue_chatbot_job
from api.jobs.store import get_job_store
from api.schemas.chatbot import ChatMessageRequest, PresetType

API_PREFIX = "/api/v1/chatbot"


def _default_dates(preset: PresetType) -> tuple[str, str]:
    today = datetime.now().date()
    if preset == "analyze_asset":
        start = today - timedelta(days=90)
    else:
        start = today - timedelta(days=15)
    return start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")


def _resolve_dates(body: ChatMessageRequest) -> tuple[str, str]:
    if body.from_date and body.to_date:
        return body.from_date[:10], body.to_date[:10]
    return _default_dates(body.preset)


def build_followup_kwargs(body: ChatMessageRequest) -> dict[str, Any]:
    """Map API request to smart_followup_query kwargs."""
    from_date, to_date = _resolve_dates(body)
    preset = body.preset

    if preset == "analyze_asset":
        if not body.asset and not (body.assets and len(body.assets) == 1):
            raise ValueError("analyze_asset preset requires asset or a single assets entry")
        asset = (body.asset or body.assets[0]).strip()
        message = format_analyze_asset_prompt(asset, from_date, to_date)
        return {
            "user_message": message,
            "selected_signal_types": ["entry", "exit"],
            "assets": [asset],
            "from_date": from_date,
            "to_date": to_date,
            "functions": body.functions,
            "additional_context": body.additional_context,
            "auto_extract_tickers": False,
            "signal_type_reasoning": "API preset: analyze_asset",
            "query_kind": "deep_dive",
            "deep_research_enabled": body.deep_research_enabled,
        }

    if preset == "signal_insights":
        message = format_signal_insights_prompt(from_date, to_date)
        return {
            "user_message": message,
            "selected_signal_types": ["entry"],
            "assets": None,
            "from_date": from_date,
            "to_date": to_date,
            "functions": body.functions,
            "additional_context": body.additional_context,
            "auto_extract_tickers": True,
            "signal_type_reasoning": "API preset: signal_insights",
            "query_kind": body.query_kind,
            "deep_research_enabled": body.deep_research_enabled,
        }

    if preset == "breadth_analysis":
        message = format_breadth_analysis_prompt(from_date, to_date)
        return {
            "user_message": message,
            "selected_signal_types": ["breadth"],
            "assets": body.assets,
            "from_date": from_date,
            "to_date": to_date,
            "functions": body.functions,
            "additional_context": body.additional_context,
            "auto_extract_tickers": body.auto_extract_tickers,
            "signal_type_reasoning": "API preset: breadth_analysis",
            "query_kind": body.query_kind,
            "deep_research_enabled": body.deep_research_enabled,
        }

    # freeform
    if not (body.message or "").strip():
        raise ValueError("message is required for freeform preset")
    return {
        "user_message": body.message.strip(),
        "selected_signal_types": body.selected_signal_types,
        "assets": body.assets,
        "from_date": from_date,
        "to_date": to_date,
        "functions": body.functions,
        "additional_context": body.additional_context,
        "auto_extract_tickers": body.auto_extract_tickers,
        "signal_type_reasoning": None,
        "query_kind": body.query_kind,
        "deep_research_enabled": body.deep_research_enabled,
    }


def _request_snapshot(body: ChatMessageRequest) -> dict[str, Any]:
    return body.model_dump()


def _poll_url(job_id: str) -> str:
    return f"{API_PREFIX}/jobs/{job_id}"


def _job_accepted(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "job_id": job["job_id"],
        "session_id": job["session_id"],
        "status": job["status"],
        "poll_url": _poll_url(job["job_id"]),
    }


def ensure_session_exists(session_id: str) -> None:
    if not SessionManager.session_exists(session_id):
        raise FileNotFoundError(f"Session not found: {session_id}")


def get_session_owner_email(session_id: str) -> str | None:
    meta = SessionManager.get_session_metadata(session_id)
    if meta is None:
        return None
    owner = (meta.get("owner_email") or "").strip().lower()
    return owner or None


def user_can_access_session(session_id: str, user_email: str) -> bool:
    ensure_session_exists(session_id)
    owner = get_session_owner_email(session_id)
    if owner is None:
        return True
    return owner == user_email.strip().lower()


def create_session(title: str | None = None, *, owner_email: str | None = None) -> str:
    return SessionManager.create_new_session(title=title, owner_email=owner_email)


def list_sessions(
    *,
    sort_by: str = "last_updated",
    search: str | None = None,
    limit: int | None = None,
    owner_email: str | None = None,
) -> list[dict[str, Any]]:
    if search:
        sessions = SessionManager.search_sessions(search, owner_email=owner_email)
    else:
        sessions = SessionManager.list_all_sessions(sort_by=sort_by, owner_email=owner_email)
    if limit is not None:
        sessions = sessions[:limit]
    return sessions


def get_session(session_id: str) -> dict[str, Any]:
    ensure_session_exists(session_id)
    meta = SessionManager.get_session_metadata(session_id)
    if meta is None:
        raise FileNotFoundError(f"Session not found: {session_id}")
    engine = ChatbotEngine(session_id=session_id)
    summary = engine.get_session_summary()
    return {**meta, **summary}


def update_session_title(session_id: str, title: str) -> bool:
    ensure_session_exists(session_id)
    return SessionManager.update_session_title(session_id, title)


def delete_session(session_id: str) -> bool:
    return SessionManager.delete_session(session_id)


def finalize_session(session_id: str) -> bool:
    ensure_session_exists(session_id)
    engine = ChatbotEngine(session_id=session_id)
    return engine.finalize_session(reason="api_finalize")


def get_history(session_id: str, *, display: bool = False) -> list[dict[str, Any]]:
    ensure_session_exists(session_id)
    engine = ChatbotEngine(session_id=session_id)
    messages = engine.get_conversation_history()
    if not display:
        return messages
    out: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role")
        meta = msg.get("metadata") or {}
        if role == "user":
            content = meta.get("display_prompt") or msg.get("content", "")
        elif role == "assistant":
            content = msg.get("content", "")
        else:
            content = msg.get("content", "")
        out.append(
            {
                "role": role,
                "content": content,
                "timestamp": msg.get("timestamp"),
                "metadata": meta if role == "assistant" else None,
            }
        )
    return out


def enqueue_message(session_id: str, body: ChatMessageRequest) -> dict[str, Any]:
    ensure_session_exists(session_id)
    followup_kwargs = build_followup_kwargs(body)
    job = enqueue_chatbot_job(session_id, followup_kwargs, _request_snapshot(body))
    return _job_accepted(job)


def launch_preset(
    preset: PresetType,
    *,
    asset: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    title: str | None = None,
    deep_research_enabled: bool = False,
    owner_email: str | None = None,
) -> dict[str, Any]:
    session_id = SessionManager.create_new_session(title=title, owner_email=owner_email)
    body = ChatMessageRequest(
        message="",
        preset=preset,
        asset=asset,
        from_date=from_date,
        to_date=to_date,
        deep_research_enabled=deep_research_enabled,
    )
    return enqueue_message(session_id, body)


def get_job(job_id: str) -> dict[str, Any] | None:
    return get_job_store().get(job_id)


def list_jobs(
    session_id: str | None = None,
    limit: int = 50,
    owner_email: str | None = None,
) -> list[dict[str, Any]]:
    store = get_job_store()
    if session_id:
        return store.list_by_session(session_id, limit=limit)
    jobs: list[dict[str, Any]] = []
    root = store.root
    for path in sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            import json

            data = json.loads(path.read_text(encoding="utf-8"))
            if owner_email:
                sid = data.get("session_id")
                if sid and not user_can_access_session(str(sid), owner_email):
                    continue
            jobs.append(data)
        except (OSError, json.JSONDecodeError):
            continue
        if len(jobs) >= limit:
            break
    return jobs


def get_public_config() -> dict[str, Any]:
    from chatbot import config as cfg

    return {
        "features": {
            "enable_web_search": cfg.ENABLE_WEB_SEARCH,
            "llm_router_enabled": cfg.LLM_ROUTER_ENABLED,
            "enable_deep_research": cfg.ENABLE_DEEP_RESEARCH,
            "parallel_hybrid_enabled": cfg.PARALLEL_HYBRID_ENABLED,
            "enable_batch_processing": cfg.ENABLE_BATCH_PROCESSING,
        },
        "models": {
            "claude_model": cfg.CLAUDE_MODEL,
            "openai_model": cfg.OPENAI_MODEL,
        },
        "limits": {
            "max_history_length": cfg.MAX_HISTORY_LENGTH,
            "deep_research_total_timeout_seconds": cfg.DEEP_RESEARCH_TOTAL_TIMEOUT_SECONDS,
            "max_rows_to_include": cfg.MAX_ROWS_TO_INCLUDE,
        },
    }


def get_signal_types_catalog() -> dict[str, Any]:
    return {
        "allowed": ALLOWED_SIGNAL_TYPES,
        "default": DEFAULT_SIGNAL_TYPES,
        "descriptions": {
            key: {"label": desc[0], "description": desc[1]}
            for key, desc in SIGNAL_TYPE_DESCRIPTIONS.items()
        },
    }


def preview_signal_types(message: str, session_id: str | None = None) -> tuple[list[str], str]:
    if session_id:
        ensure_session_exists(session_id)
        engine = ChatbotEngine(session_id=session_id)
    else:
        engine = ChatbotEngine()
    return engine.determine_signal_types(message)


def get_tickers() -> list[str]:
    engine = ChatbotEngine()
    return engine.get_available_tickers()


def get_functions(ticker: str | None = None) -> list[str]:
    engine = ChatbotEngine()
    return engine.get_available_functions(ticker=ticker)


def get_memory_stats() -> dict[str, Any]:
    engine = ChatbotEngine()
    return engine.get_memory_stats()


def flag_exchange(
    session_id: str,
    *,
    message_index: int,
    notes: str = "",
    include_full_tables: bool = False,
    max_rows_sample: int = 50,
) -> Path:
    ensure_session_exists(session_id)
    engine = ChatbotEngine(session_id=session_id)
    history = engine.get_conversation_history()
    assistant_indices = [i for i, m in enumerate(history) if m.get("role") == "assistant"]
    if message_index >= len(assistant_indices):
        raise IndexError(f"message_index {message_index} out of range ({len(assistant_indices)} assistant messages)")
    ai_idx = assistant_indices[message_index]
    if ai_idx == 0:
        raise ValueError("No preceding user message for assistant at index 0")
    user_msg = history[ai_idx - 1]
    assistant_msg = history[ai_idx]
    if user_msg.get("role") != "user":
        raise ValueError("Expected user message before assistant")
    return save_flagged_pair(
        session_id=session_id,
        notes=notes,
        user_message=user_msg,
        assistant_message=assistant_msg,
        include_full_tables=include_full_tables,
        max_rows_sample=max_rows_sample,
    )
