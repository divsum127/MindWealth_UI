"""Typed payloads for portfolio NAV history providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class NavPoint:
    date: str
    value: float
    drawdown_pct: float
    high_water_mark: float


@dataclass(frozen=True)
class MonthlyReturn:
    month: str
    return_pct: float


@dataclass(frozen=True)
class AttributionRow:
    id: str
    label: str
    return_pct: float
    description: str


@dataclass(frozen=True)
class NavHistoryBundle:
    """Monthly + optional daily NAV history for one MODEL valuation book."""

    book: str
    source: str
    inception_nav: float
    mtm: list[NavPoint] = field(default_factory=list)
    closed: list[NavPoint] = field(default_factory=list)
    mtm_daily: list[NavPoint] = field(default_factory=list)
    closed_daily: list[NavPoint] = field(default_factory=list)
    benchmark: list[NavPoint] = field(default_factory=list)
    monthly_returns: list[MonthlyReturn] = field(default_factory=list)
    attribution: list[AttributionRow] = field(default_factory=list)
    position_limit: int | None = None
    nav_history_note: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def latest_nav(self) -> float | None:
        if not self.mtm:
            return None
        return self.mtm[-1].value

    @property
    def since_go_live_pct(self) -> float | None:
        if not self.mtm or self.inception_nav <= 0:
            return None
        return round((self.mtm[-1].value / self.inception_nav - 1.0) * 100.0, 2)
