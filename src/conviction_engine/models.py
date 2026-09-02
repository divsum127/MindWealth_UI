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
    BANK = "bank"
    HIGH_MARGIN_HARDWARE = "high_margin_hardware"
    UNKNOWN = "unknown"


# The 6 calibrated types with real scoring/valuation modules (v2, 30 July 2026 answers).
# Anything else (insurer, deep_value, genuinely unresolved sector data -> "unknown") fires
# the `coverage_incomplete` hard gate instead of silently defaulting to `compounder`.
KNOWN_BUSINESS_TYPES: frozenset[str] = frozenset(
    {
        BusinessType.SAAS.value,
        BusinessType.COMPOUNDER.value,
        BusinessType.INCOME.value,
        BusinessType.CYCLICAL.value,
        BusinessType.BANK.value,
        BusinessType.HIGH_MARGIN_HARDWARE.value,
    }
)


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
    coverage_incomplete: bool = False
    business_type: str | None = None
    bq_raw: float | None = None
    valuation_tax: float | None = None
    fd_direction: str | None = None
    asset_type: str | None = None
    rationale: list[str] = field(default_factory=list)
    position_layers: PositionLayers = field(default_factory=PositionLayers)
    not_applicable_reason: str | None = None
    # Why the sell verdict is what it is — QUALITY_COLLAPSE vs VALUATION_STRETCH vs
    # NORMAL_TECHNICAL, or the hard gate that fired. The label used to imply a cause it
    # had not tested (Rohit 1 Sep, C4).
    sell_reason_code: str | None = None

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
        "fd_sizing_adj": 0.0,
        "debt_purpose": None,
        "revenue_accelerating": None,
        "valuation_tax_breakdown": None,
        "yield_trap_mkt_threshold": None,
        "yield_trap_breakdown": None,
        "fs_cap_breakdown": None,
        "pe_history_insufficient": False,
        "pe_history_thin": False,
        "pe_history_years": None,
        "buyback_suspension_flag": None,
        "dividend_cut_flag": None,
        "capital_return_penalty": 0.0,
        "manual_overrides": {},
        # Agentic dimension provenance (Rohit 1 Sep, E1): "ran" | "skipped" |
        # "no_api_key", plus a per-dimension breakdown, so a 0 on an agentic line can
        # never again be read as evidence when it only means the search never ran.
        "agent_dims_status": "skipped",
        "agent_dims_ran": False,
        "agent_dim_provenance": {},
        "price": None,
        "market_cap": None,
        "enterprise_value": None,
        "pe_ttm": None,
        # Adjusted earnings (Rohit 26 Aug, conviction spec gap 1). `pe_ttm` stays the
        # raw feed number; `pe_ttm_adjusted` is populated only when one-off items clear
        # the 5%-of-net-income materiality gate.
        "pe_ttm_adjusted": None,
        "adjusted_eps_ttm": None,
        "adjusted_eps_basis": None,
        "one_off_pct_of_ni": None,
        "one_off_review_needed": False,
        "pe_percentile_20y": None,
        "ev_fwd_rev": None,
        "owner_earnings_yield": None,
        "dividend_yield_current": None,
        "dividend_yield_zscore": None,
        # Dividend basis split (Rohit 26 Aug, spec gap 4): the trap runs on the
        # forward declared dividend where one exists; the trailing figures are kept
        # alongside so a basis-driven flip is visible instead of silent.
        "dividend_yield_forward": None,
        "dividend_yield_trailing": None,
        "dividend_yield_zscore_trailing": None,
        "dividend_yield_basis": None,
        "dividend_basis_conflict": False,
        "valuation_tax": 0.0,
        "conviction_score": 0.0,
        "fs_score": 50.0,
        "fs_class": FsClass.MODERATE.value,
        "yield_trap_warning": False,
        "sell_reason_code": None,
        "flags": [],
        "position_layers": PositionLayers().to_dict(),
        "last_full_calc": None,
        "last_daily_update": None,
        "days_below_high": 0,
        "divergence_state": {},
        "m_and_a_activity": False,
        "eps_estimate_current": None,
        "eps_estimate_prior": None,
        "created_at": now,
        "updated_at": now,
    }
