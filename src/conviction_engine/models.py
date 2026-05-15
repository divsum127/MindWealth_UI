"""Typed data structures for the Conviction Engine overlay."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class BusinessType(str, Enum):
    SAAS = "saas"
    COMPOUNDER = "compounder"
    INCOME = "income"
    CYCLICAL = "cyclical"
    UNKNOWN = "unknown"


class FsClass(str, Enum):
    STRONG = "strong"
    MODERATE_HIGH = "moderate_high"
    MODERATE = "moderate"
    MODERATE_LOW = "moderate_low"
    WEAK = "weak"


class SignalTimeframe(str, Enum):
    SHORT = "short"
    LONG = "long"


class TechnicalSignal(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass
class PositionLayers:
    core_fraction: float = 0.0
    tactical_fraction: float = 0.0
    core_signal_date: str | None = None
    tactical_signal_date: str | None = None
    core_model: str | None = None
    tactical_model: str | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any] | None) -> "PositionLayers":
        if not value:
            return cls()
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{key: value.get(key) for key in allowed})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class QuantSignal:
    symbol: str
    function_name: str
    side: str
    interval: str
    technical_signal: str
    signal_timeframe: str
    signal_date: str | None = None
    signal_price: float | None = None
    exit_date: str | None = None
    exit_price: float | None = None
    today_price: float | None = None
    win_rate: float | None = None
    signal_strength: float = 0.75
    confirmation_status: str | None = None
    target: str | None = None
    stop_loss: str | None = None
    status: str | None = None
    source_file: str | None = None
    source_row: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SignalModification:
    ticker: str
    original_signal: str
    signal_timeframe: str
    verdict: str
    sizing_pct: float
    conviction_score: float | None
    conviction_raw: float | None
    fs_score: float | None
    fs_class: str | None
    yield_trap_warning: bool
    business_type: str | None = None
    bq_raw: float | None = None
    valuation_tax: float | None = None
    asset_type: str | None = None
    rationale: list[str] = field(default_factory=list)
    position_layers: PositionLayers = field(default_factory=PositionLayers)
    not_applicable_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["rationale"] = " | ".join(self.rationale)
        return data


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def default_record(ticker: str) -> dict[str, Any]:
    now = utc_now_iso()
    return {
        "ticker": ticker.upper(),
        "asset_type": "UNKNOWN",
        "business_type": BusinessType.UNKNOWN.value,
        "business_type_source": "unknown",
        "bq_raw": 0.0,
        "bq_components": {},
        "fs_quality_base": 50.0,
        "fd_votes": {},
        "fd_direction": "stable",
        "manual_overrides": {},
        "price": None,
        "market_cap": None,
        "enterprise_value": None,
        "pe_ttm": None,
        "pe_percentile_20y": None,
        "ev_fwd_rev": None,
        "owner_earnings_yield": None,
        "dividend_yield_current": None,
        "dividend_yield_zscore": None,
        "valuation_tax": 0.0,
        "conviction_score": 0.0,
        "fs_score": 50.0,
        "fs_class": FsClass.MODERATE.value,
        "yield_trap_warning": False,
        "flags": [],
        "position_layers": PositionLayers().to_dict(),
        "last_full_calc": None,
        "last_daily_update": None,
        "created_at": now,
        "updated_at": now,
    }
