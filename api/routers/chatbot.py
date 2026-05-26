"""Chatbot REST routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse

from api.dependencies import optional_api_key
from api.schemas.chatbot import (
    ChatMessageRequest,
    CreateSessionRequest,
    FlagExchangeRequest,
    FlagExchangeResponse,
    JobAcceptedResponse,
    PresetLaunchRequest,
    PresetLaunchResponse,
    PublicConfigResponse,
    SignalTypesPreviewRequest,
    SignalTypesPreviewResponse,
    UpdateSessionRequest,
)
from api.services import chatbot_service as svc

router = APIRouter(
    prefix="/chatbot",
    tags=["chatbot"],
    dependencies=[Depends(optional_api_key)],
)


@router.post(
    "/sessions",
    operation_id="create_chat_session",
    status_code=status.HTTP_201_CREATED,
)
def create_session(body: CreateSessionRequest) -> dict[str, Any]:
    session_id = svc.create_session(title=body.title)
    return {"session_id": session_id, "title": body.title or "New Chat"}


@router.get("/sessions", operation_id="list_chat_sessions")
def list_sessions(
    sort_by: str = Query(default="last_updated"),
    search: str | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=500),
) -> list[dict[str, Any]]:
    return svc.list_sessions(sort_by=sort_by, search=search, limit=limit)


@router.get("/sessions/{session_id}", operation_id="get_chat_session")
def get_session(session_id: str) -> dict[str, Any]:
    try:
        return svc.get_session(session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/sessions/{session_id}", operation_id="update_chat_session")
def update_session(session_id: str, body: UpdateSessionRequest) -> dict[str, Any]:
    try:
        ok = svc.update_session_title(session_id, body.title)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return {"session_id": session_id, "title": body.title}


@router.delete(
    "/sessions/{session_id}",
    operation_id="delete_chat_session",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_session(session_id: str) -> Response:
    if not svc.delete_session(session_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/sessions/{session_id}/finalize", operation_id="finalize_chat_session")
def finalize_session(session_id: str) -> dict[str, Any]:
    try:
        saved = svc.finalize_session(session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"session_id": session_id, "memory_saved": saved}


@router.get("/sessions/{session_id}/history", operation_id="get_chat_history")
def get_history(
    session_id: str,
    display: bool = Query(default=False, description="Use display_prompt for user messages"),
) -> list[dict[str, Any]]:
    try:
        return svc.get_history(session_id, display=display)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/sessions/{session_id}/messages",
    operation_id="enqueue_chat_message",
    response_model=JobAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def enqueue_message(session_id: str, body: ChatMessageRequest) -> JSONResponse:
    try:
        payload = svc.enqueue_message(session_id, body)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content=payload)


@router.post(
    "/analyze-asset",
    operation_id="launch_analyze_asset",
    response_model=PresetLaunchResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def launch_analyze_asset(body: PresetLaunchRequest) -> JSONResponse:
    if not body.asset:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="asset is required for analyze-asset",
        )
    try:
        payload = svc.launch_preset(
            "analyze_asset",
            asset=body.asset,
            from_date=body.from_date,
            to_date=body.to_date,
            title=body.title,
            deep_research_enabled=body.deep_research_enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content=payload)


@router.post(
    "/signal-insights",
    operation_id="launch_signal_insights",
    response_model=PresetLaunchResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def launch_signal_insights(body: PresetLaunchRequest) -> JSONResponse:
    payload = svc.launch_preset(
        "signal_insights",
        from_date=body.from_date,
        to_date=body.to_date,
        title=body.title,
        deep_research_enabled=body.deep_research_enabled,
    )
    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content=payload)


@router.post(
    "/breadth-analysis",
    operation_id="launch_breadth_analysis",
    response_model=PresetLaunchResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def launch_breadth_analysis(body: PresetLaunchRequest) -> JSONResponse:
    payload = svc.launch_preset(
        "breadth_analysis",
        from_date=body.from_date,
        to_date=body.to_date,
        title=body.title,
        deep_research_enabled=body.deep_research_enabled,
    )
    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content=payload)


@router.get("/jobs/{job_id}", operation_id="get_chat_job")
def get_job(job_id: str) -> dict[str, Any]:
    job = svc.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job not found: {job_id}")
    return job


@router.get("/jobs", operation_id="list_chat_jobs")
def list_jobs(
    session_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    return svc.list_jobs(session_id=session_id, limit=limit)


@router.get(
    "/config",
    operation_id="get_chatbot_config",
    response_model=PublicConfigResponse,
)
def get_config() -> dict[str, Any]:
    return svc.get_public_config()


@router.get("/signal-types", operation_id="get_signal_types")
def get_signal_types() -> dict[str, Any]:
    return svc.get_signal_types_catalog()


@router.post(
    "/signal-types/preview",
    operation_id="preview_signal_types",
    response_model=SignalTypesPreviewResponse,
)
def preview_signal_types(body: SignalTypesPreviewRequest) -> SignalTypesPreviewResponse:
    try:
        types, reasoning = svc.preview_signal_types(body.message, body.session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return SignalTypesPreviewResponse(signal_types=types, reasoning=reasoning)


@router.get("/tickers", operation_id="get_chatbot_tickers")
def get_tickers() -> list[str]:
    return svc.get_tickers()


@router.get("/functions", operation_id="get_chatbot_functions")
def get_functions(ticker: str | None = Query(default=None)) -> list[str]:
    return svc.get_functions(ticker=ticker)


@router.get("/memory/stats", operation_id="get_memory_stats")
def get_memory_stats() -> dict[str, Any]:
    return svc.get_memory_stats()


@router.post(
    "/sessions/{session_id}/flag",
    operation_id="flag_chat_exchange",
    response_model=FlagExchangeResponse,
)
def flag_exchange(session_id: str, body: FlagExchangeRequest) -> FlagExchangeResponse:
    try:
        path = svc.flag_exchange(
            session_id,
            message_index=body.message_index,
            notes=body.notes,
            include_full_tables=body.include_full_tables,
            max_rows_sample=body.max_rows_sample,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (IndexError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return FlagExchangeResponse(path=str(path), session_id=session_id)
