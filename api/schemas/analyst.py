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


class OverwatchPanelMacroDetail(BaseModel):
    model_config = ConfigDict(extra="allow")

    combo: str | None = None
    reason: str | None = None
    narrative: str | None = None
    brave_fearful: str | None = None
    variant: Literal["ssi", "dominant"] = "dominant"
    historical_analogs: HistoricalAnalogsBlock | None = None


class OverwatchPanelAlert(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    type: Literal["degradation", "runic", "system"]
    label: str
    html: str
    recommendation: str | None = None
    fwd_trend: list[float] | None = None
    footer: str | None = None
    created_at: str
    border_color: str | None = None
    severity: Literal["watch", "breach"] | None = None
    signal: OverwatchPanelSignalDetail | None = None
    macro: OverwatchPanelMacroDetail | None = None


class AnalystAlertsMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    data_updated_at: dict[str, Any] | None = None
    floor_pct: float = 60.0
    gap_threshold_pp: float = 10.0
    next_signal_check: str | None = None
    next_macro_scan: str | None = None
    stale_reason: str | None = None


class AnalystAlertsResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    meta: AnalystAlertsMeta
    count: int
    panel_alerts: list[OverwatchPanelAlert]


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
