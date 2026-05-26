"""
Validate target/stop ladder levels against signal direction and today price.
Used after SmartDataFetcher returns entry rows to flag stale or mislabeled levels.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from .smart_data_fetcher import SYMBOL_SIGNAL_COMPOUND_COL

TARGET_COLUMN = (
    "Targets (Historic Rise or Fall to Pivot/Avg % Gain of Historic Winning trades/"
    "Function Specific Target/Horizontal/F-Stack 1/F-Stack 2/EMA 200) [$]"
)
STOP_COLUMN = (
    "Stop Loss (Recent Extrema/Horizontal/F-Stack 1/F-Stack 2/F-Track 1/F-Track 2/EMA 200) [$]"
)
TODAY_PRICE_COLUMN = "Today Trading Date/Price[$], Today Price vs Signal"
SIGNAL_OPEN_PRICE_COLUMN = "Signal Open Price"

LADDER_SLOT_LABELS = (
    "Pivot",
    "AvgGain",
    "FuncSpecific",
    "Horizontal",
    "FStack1",
    "FStack2",
    "EMA200",
)

_STOP_SKIP = re.compile(
    r"no\s+(?:stop\s+loss|support|f-track|f-stack|target|ema)",
    re.I,
)
_NUMERIC = re.compile(r"(\d+(?:\.\d+)?)")


def _parse_direction(compound: str) -> Optional[str]:
    if ", Long," in compound:
        return "Long"
    if ", Short," in compound:
        return "Short"
    return None


def _parse_today_price(today_field: str) -> Optional[float]:
    if not today_field or not str(today_field).strip():
        return None
    m = re.search(r"\(Price:\s*([\d.]+)\)", str(today_field), re.I)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def _parse_ladder(raw: Any) -> Dict[str, Optional[float]]:
    slots: Dict[str, Optional[float]] = {label: None for label in LADDER_SLOT_LABELS}
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return slots
    text = str(raw).strip()
    if not text:
        return slots
    parts = text.split("/")
    for i, label in enumerate(LADDER_SLOT_LABELS):
        if i >= len(parts):
            break
        part = parts[i].strip()
        if _STOP_SKIP.search(part):
            continue
        m = _NUMERIC.search(part)
        if m:
            try:
                slots[label] = float(m.group(1))
            except ValueError:
                pass
    return slots


def _first_numeric_stop(stop_slots: Dict[str, Optional[float]]) -> Optional[Tuple[str, float]]:
    for label in ("Pivot", "Horizontal", "FStack1", "FStack2", "EMA200", "AvgGain", "FuncSpecific"):
        val = stop_slots.get(label)
        if val is not None:
            return label, val
    return None


def validate_entry_record(record: Dict[str, Any]) -> List[str]:
    """Return human-readable warnings for one entry signal record."""
    warnings: List[str] = []
    compound = str(record.get(SYMBOL_SIGNAL_COMPOUND_COL, ""))
    direction = _parse_direction(compound)
    today_raw = record.get(TODAY_PRICE_COLUMN, "")
    today_price = _parse_today_price(str(today_raw))
    if today_price is None:
        return warnings

    stop_raw = record.get(STOP_COLUMN, "")
    stop_slots = _parse_ladder(stop_raw)
    first_stop = _first_numeric_stop(stop_slots)
    if first_stop:
        slot_name, stop_price = first_stop
        if direction == "Long" and stop_price >= today_price:
            warnings.append(
                f"Long signal: Recent/numeric stop ({slot_name}=${stop_price:.4f}) is at or above "
                f"today price (${today_price:.4f}) — treat as stale/breached, not active protection."
            )
        elif direction == "Short" and stop_price <= today_price:
            warnings.append(
                f"Short signal: stop ({slot_name}=${stop_price:.4f}) is at or below "
                f"today price (${today_price:.4f}) — likely stale or mislabeled."
            )

    target_raw = record.get(TARGET_COLUMN, "")
    target_slots = _parse_ladder(target_raw)
    ema_target = target_slots.get("EMA200")
    ema_stop = stop_slots.get("EMA200")
    if ema_target is not None and ema_stop is None:
        stop_text = str(stop_raw).lower()
        if "no ema 200 stop" in stop_text or "no ema 200 support" in stop_text:
            warnings.append(
                f"EMA 200 value ${ema_target:.4f} appears only under Targets — do not report it as "
                "an EMA 200 stop when Stop Loss column has no EMA 200 level."
            )

    return warnings


def build_entry_validation_section(df: pd.DataFrame) -> str:
    """Build a prompt appendix listing per-row target/stop consistency warnings."""
    if df is None or df.empty:
        return ""
    lines: List[str] = []
    for idx, row in df.iterrows():
        rec = row.to_dict()
        row_warnings = validate_entry_record(rec)
        if not row_warnings:
            continue
        sym = str(rec.get(SYMBOL_SIGNAL_COMPOUND_COL, f"row {idx}"))[:80]
        lines.append(f"- {sym}")
        for w in row_warnings:
            lines.append(f"  - {w}")
    if not lines:
        return ""
    header = (
        "=== SIGNAL LEVEL VALIDATION (auto-check) ===\n"
        "Use these warnings when citing stops/targets. Each bullet is one signal row.\n"
    )
    return header + "\n".join(lines) + "\n"
