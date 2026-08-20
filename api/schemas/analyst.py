"""AI Analyst / Overwatch panel API schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class OverwatchPanelSignalDetail(BaseModel):
    model_config = ConfigDict(extra="allow")

    strategy: str
    interval: str
    signal_type: str
    fwd_wr: float
    backtest_wr: float
    gap: float
    pattern: str
    above_floor: bool


class HistoricalAnalogInstance(BaseModel):
    model_config = ConfigDict(extra="allow")

    date: str
    description: str = ""
    spx_3m: float | None = None


class HistoricalAnalogSummary(BaseModel):
    model_config = ConfigDict(extra="allow")

    median_3m: float | None = None
    worst: float | None = None
    best: float | None = None
    hit_rate: float | None = None


class HistoricalAnalogsBlock(BaseModel):
    model_config = ConfigDict(extra="allow")

    combo: str
    instances: list[HistoricalAnalogInstance] = Field(default_factory=list)
    summary: HistoricalAnalogSummary = Field(default_factory=HistoricalAnalogSummary)


PanelAlertType = Literal[
    "degradation",
    "position_risk",
    "runic",
    "runic_watch",
    "regime_warning",
    "sentiment_warning",
    "persistence",
    "system",
]
PanelChannel = Literal["signals", "macro", "system"]
PanelTabId = Literal["all", "signals", "macro", "system"]


class OverwatchPanelMacroDetail(BaseModel):
    model_config = ConfigDict(extra="allow")

    combo: str | None = None
    reason: str | None = None
    narrative: str | None = None
    brave_fearful: str | None = None
    variant: Literal[
        "ssi",
        "dominant",
        "watch",
        "regime_warning",
        "sentiment",
        "persistence",
    ] = "dominant"
    historical_analogs: HistoricalAnalogsBlock | None = None


class OverwatchPanelPositionDetail(BaseModel):
    """Live-MTM / booked-loss detail. Carries P&L, never a win rate."""

    model_config = ConfigDict(extra="allow")

    symbol: str
    function: str = ""
    interval: str = ""
    direction: str = ""
    side: str = ""
    trigger_type: Literal["booked_loss", "live_mtm_breach"] = "booked_loss"
    entry_date: str | None = None
    exit_date: str | None = None
    profit_pct: float = 0.0
    floor_pct: float | None = None


class OverwatchPanelWarningDetail(BaseModel):
    model_config = ConfigDict(extra="allow")

    reasons: list[str] = Field(default_factory=list)
    regime: dict[str, Any] | None = None
    ssi_level: float | None = None
    ssi_posture: str | None = None
    signal_name: str | None = None
    var_id: str | None = None


class OverwatchPanelAlert(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    type: PanelAlertType
    channel: PanelChannel
    label: str
    html: str
    recommendation: str | None = None
    fwd_trend: list[float] | None = None
    footer: str | None = None
    created_at: str
    border_color: str | None = None
    severity: Literal["watch", "breach"] | None = None
    signal: OverwatchPanelSignalDetail | None = None
    position: OverwatchPanelPositionDetail | None = None
    macro: OverwatchPanelMacroDetail | None = None
    warning: OverwatchPanelWarningDetail | None = None


class AnalystTabBadge(BaseModel):
    model_config = ConfigDict(extra="allow")

    count: int = 0
    badge: str = ""
    drift_count: int | None = None
    position_count: int | None = None


class AnalystTabsMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    all: AnalystTabBadge
    signals: AnalystTabBadge
    macro: AnalystTabBadge
    system: AnalystTabBadge
    active_combo: str | None = None


class AnalystAlertsMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    data_updated_at: dict[str, Any] | None = None
    floor_pct: float = 60.0
    gap_threshold_pp: float = 10.0
    next_signal_check: str | None = None
    next_macro_scan: str | None = None
    stale_reason: str | None = None
    tabs: AnalystTabsMeta | None = None


class AnalystAlertsResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    meta: AnalystAlertsMeta
    count: int
    panel_alerts: list[OverwatchPanelAlert]


class AnalystRegimeSnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")

    date: str | None = None
    regime: dict[str, Any] = Field(default_factory=dict)
    brave_fearful: str | None = None
    brave_fearful_display: str | None = None
    dominant_signal: str | None = None
    dominant_reason: str | None = None
    macro_override: dict[str, Any] = Field(default_factory=dict)


class AnalystSentimentSnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")

    ssi_level: float | None = None
    ssi_percentile_5y: float | None = None
    ssi_multiplier: float | None = None
    layer2_status: str | None = None
    posture: str | None = None
    long_signal_active: bool = False
    short_signal_active: bool = False
    date: str | None = None


class AnalystChatIntegration(BaseModel):
    model_config = ConfigDict(extra="allow")

    create_session_path: str = "/api/v1/chatbot/sessions"
    messages_path_template: str = "/api/v1/chatbot/sessions/{session_id}/messages"
    history_path_template: str = "/api/v1/chatbot/sessions/{session_id}/history"
    supports_page_context: bool = True


class AnalystPanelContextResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    meta: AnalystAlertsMeta
    count: int
    panel_alerts: list[OverwatchPanelAlert]
    regime: AnalystRegimeSnapshot
    sentiment: AnalystSentimentSnapshot
    chat: AnalystChatIntegration


class AnalystBriefResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    snippet: str
    source: Literal["narrative", "template", "empty"] = "empty"
    updated_at: str | None = None


class SystemHealthCheck(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    status: Literal["ok", "warn", "fail"]
    detail: str
    last_success_at: str | None = None


class SystemHealthResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: Literal["ok", "warn", "fail"]
    version: str
    checked_at: str
    checks: list[SystemHealthCheck]
