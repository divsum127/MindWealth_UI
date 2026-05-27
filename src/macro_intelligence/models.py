"""Data models and enums for the Runic Agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SignalTier(str, Enum):
    NORMAL = "NORMAL"
    RARE = "RARE"
    EXTREME = "EXTREME"
    WATCH = "WATCH"


class GateFlag(str, Enum):
    SIGNAL = "SIGNAL"
    BELOW_GATE = "BELOW_GATE"


class DurationBucket(str, Enum):
    SHORT = "SHORT"
    MEDIUM = "MEDIUM"
    LONG = "LONG"


class ComboId(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"
    G = "G"


@dataclass
class VariableReading:
    var_id: str
    date: str
    raw_value: float | None
    pctile_rank_3yr: float | None = None
    signal_tier: SignalTier = SignalTier.NORMAL
    direction: str | None = None  # UP / DOWN
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ComboFire:
    date: str
    runic_combo: str | None
    var_ids: list[str]
    directions: list[str | None]
    status: str = "ACTIVE"  # ACTIVE, WATCH, PARTIAL, RESOLVED
    duration_weeks: int | None = None
    duration_bucket: DurationBucket | None = None
    gate_flag: GateFlag = GateFlag.SIGNAL
    macro_regime: dict[str, str] | None = None


@dataclass
class RegimeState:
    fed_cycle: str = "PAUSING"
    curve_regime: str = "NORMAL"
    geo_overlay: str = "NEUTRAL"
    val_regime: str = "FAIR"
    liquidity: str = "GLOBAL_EASY"

    def to_dict(self) -> dict[str, str]:
        return {
            "fed_cycle": self.fed_cycle,
            "curve_regime": self.curve_regime,
            "geo_overlay": self.geo_overlay,
            "val_regime": self.val_regime,
            "liquidity": self.liquidity,
        }
