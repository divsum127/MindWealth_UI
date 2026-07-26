"""Chatbot API schemas."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

PresetType = Literal["freeform", "analyze_asset", "signal_insights", "breadth_analysis"]


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None


class UpdateSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)


class PageContext(BaseModel):
    """Overwatch panel / page context for cross-page PULL-mode chat."""

    model_config = ConfigDict(extra="forbid")

    route: str | None = Field(default=None, description="Current app route, e.g. /portfolio")
    page_title: str | None = None
    active_tab: Literal["all", "signals", "macro", "system"] | None = Field(
        default=None,
        description="Overwatch panel tab: all | signals | macro | system",
    )
    panel_open: bool | None = None
    alert_ids: list[str] = Field(default_factory=list)
    dominant_combo: str | None = None


class ChatMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = ""
    preset: PresetType = "freeform"
    asset: str | None = None
    from_date: str | None = Field(default=None, description="YYYY-MM-DD")
    to_date: str | None = Field(default=None, description="YYYY-MM-DD")
    assets: list[str] | None = None
    functions: list[str] | None = None
    selected_signal_types: list[str] = Field(default_factory=list)
    auto_extract_tickers: bool = True
    deep_research_enabled: bool = False
    query_kind: str | None = None
    additional_context: str | None = None
    page_context: PageContext | None = None


class PresetLaunchRequest(BaseModel):
    """Convenience body for analyze-asset / signal-insights / breadth-analysis."""

    model_config = ConfigDict(extra="forbid")

    asset: str | None = None
    from_date: str | None = None
    to_date: str | None = None
    title: str | None = None
    deep_research_enabled: bool = False


class JobAcceptedResponse(BaseModel):
    job_id: str
    session_id: str
    status: str
    poll_url: str


class PresetLaunchResponse(BaseModel):
    job_id: str
    session_id: str
    status: str
    poll_url: str


class SignalTypesPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1)
    session_id: str | None = None


class SignalTypesPreviewResponse(BaseModel):
    signal_types: list[str]
    reasoning: str


class FlagExchangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_index: int = Field(ge=0, description="Index of assistant message in conversation")
    notes: str = ""
    include_full_tables: bool = False
    max_rows_sample: int = Field(default=50, ge=1, le=500)


class FlagExchangeResponse(BaseModel):
    path: str
    session_id: str


class PublicConfigResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    features: dict[str, Any]
    models: dict[str, str]
    limits: dict[str, Any]
