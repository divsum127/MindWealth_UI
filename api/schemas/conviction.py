"""Conviction Engine API schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SignalEvaluateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str
    technical_signal: Literal["BUY", "SELL"]
    signal_timeframe: Literal["long", "short"]
    signal_strength: float = Field(default=0.75, ge=0.0, le=1.0)
    long_position_near_stop: bool = False
    persist: bool = False
    update_layers: bool = False
    quant_model_name: str | None = None
    signal_date: str | None = None


class SignalModificationResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    ticker: str
    original_signal: str
    signal_timeframe: str
    verdict: str
    sizing_pct: float
    conviction_score: float | None = None
    conviction_raw: float | None = None
    fs_score: float | None = None
    fs_class: str | None = None
    yield_trap_warning: bool = False
    business_type: str | None = None
    bq_raw: float | None = None
    valuation_tax: float | None = None
    asset_type: str | None = None
    rationale: str | list[str] | None = None
    not_applicable_reason: str | None = None


class TickerOverridesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overrides: dict[str, Any] = Field(default_factory=dict)
    recompute: bool = True


class DailyPipelineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str | None = None
    fundamentals_mode: str = "daily"
    skip_fundamentals: bool = False
    skip_overlays: bool = False
    dry_run: bool = False
    fail_fast: bool = False
    limit: int | None = Field(default=None, ge=1)
    overlay_reports: list[str] | None = None


class OverlayFileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str | None = None
    report_name: str = "new_signal.csv"
    save_output: bool = False
    update_layers: bool = False


class OverlaySummaryResponse(BaseModel):
    total_signals: int
    applicable: int
    cancel_buy: int
    max_conviction: int
    yield_traps: int
    tactical_plus: int


class HealthResponse(BaseModel):
    status: str
    version: str
    conviction_store: str
    conviction_store_writable: bool
