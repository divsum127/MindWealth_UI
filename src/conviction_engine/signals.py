"""Signal CSV discovery and normalization for Conviction Engine overlays."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd

from ..config_paths import TRADE_STORE_US_DIR
from ..utils.file_discovery import get_latest_csv_file
from .models import QuantSignal

COMPOUND_SIGNAL_COLUMN = "Symbol, Signal, Signal Date/Price[$]"
INTERVAL_COLUMN = "Interval, Confirmation Status"
WIN_RATE_COLUMN = "Win Rate [%], History Tested, Number of Trades"
TODAY_PRICE_COLUMN = "Today Trading Date/Price[$], Today price vs Signal"
TARGET_COLUMN = (
    "Targets (Historic Rise or Fall to Pivot/Avg % Gain of Historic Winning trades/"
    "Function Specific Target/Horizontal/F-Stack 1/F-Stack 2/EMA 200) [$]"
)
STOP_COLUMN = "Stop Loss (Recent Extrema/Horizontal/F-Stack 1/F-Stack 2/F-Track 1/F-Track 2/EMA 200) [$]"

SIGNAL_SOURCES = {
    "All Signal Report": "all_signal.csv",
    "New Signals": "new_signal.csv",
    "Outstanding Signals": "outstanding_signal.csv",
    "Virtual Trading Long": "virtual_trading_long.csv",
    "Virtual Trading Short": "virtual_trading_short.csv",
}

LONG_INTERVAL_TOKENS = {"monthly", "quarterly", "yearly", "1mo", "3mo", "1q", "1y", "month", "quarter", "year"}


def discover_signal_sources(trade_store_dir: Path | None = None) -> dict[str, Path]:
    base_dir = Path(trade_store_dir) if trade_store_dir else TRADE_STORE_US_DIR
    sources: dict[str, Path] = {}
    for label, filename in SIGNAL_SOURCES.items():
        latest = get_latest_csv_file(filename, str(base_dir))
        if latest:
            sources[label] = Path(latest)
    return sources


def load_signal_file(file_path: Path | str) -> pd.DataFrame:
    path = Path(file_path)
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def signal_timeframe_from_interval(interval: str | None) -> str:
    normalized = str(interval or "").strip().lower()
    if any(token in normalized for token in LONG_INTERVAL_TOKENS):
        return "long"
    return "short"


def _clean_text(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    return text


def _to_float(value: Any) -> float | None:
    text = _clean_text(value)
    if not text:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _parse_percent(value: Any) -> float | None:
    parsed = _to_float(value)
    return parsed


def _parse_compound_signal(value: Any) -> tuple[str | None, str | None, str | None, float | None]:
    text = _clean_text(value)
    if not text:
        return None, None, None, None

    parts = [part.strip() for part in text.split(",", 2)]
    symbol = parts[0] if parts else None
    side = parts[1] if len(parts) > 1 else None
    signal_date = None
    signal_price = None

    if len(parts) > 2:
        date_price = parts[2]
        signal_date = date_price.split("(")[0].strip() or None
        price_match = re.search(r"Price:\s*(-?\d+(?:\.\d+)?)", date_price.replace(",", ""))
        if price_match:
            signal_price = float(price_match.group(1))

    return symbol, side, signal_date, signal_price


def _parse_date_price(value: Any) -> tuple[str | None, float | None]:
    text = _clean_text(value)
    if not text or text.lower() == "no exit yet":
        return None, None
    date_part = text.split("(")[0].strip() or None
    price_match = re.search(r"Price:\s*(-?\d+(?:\.\d+)?)", text.replace(",", ""))
    price = float(price_match.group(1)) if price_match else None
    return date_part, price


def _extract_interval(row: pd.Series) -> tuple[str, str | None]:
    interval = _clean_text(row.get("Interval"))
    confirmation = None
    if interval:
        return interval, confirmation

    interval_info = _clean_text(row.get(INTERVAL_COLUMN))
    if not interval_info:
        return "Unknown", None

    if "," in interval_info:
        first, rest = interval_info.split(",", 1)
        return first.strip() or "Unknown", rest.strip() or None
    return interval_info, None


def _technical_signal_from_side(side: str | None) -> str:
    side_norm = str(side or "").strip().lower()
    if "long" in side_norm or side_norm == "buy":
        return "BUY"
    if "short" in side_norm or side_norm == "sell":
        return "SELL"
    return "NOT_APPLICABLE"


def normalize_signal_row(row: pd.Series | dict[str, Any], source_file: Path | str | None = None, source_row: int | None = None) -> QuantSignal:
    series = row if isinstance(row, pd.Series) else pd.Series(row)
    raw = {str(key): None if pd.isna(value) else value for key, value in series.to_dict().items()}

    symbol, side, signal_date, signal_price = _parse_compound_signal(series.get(COMPOUND_SIGNAL_COLUMN))
    symbol = symbol or _clean_text(series.get("Symbol")) or ""
    side = side or _clean_text(series.get("Signal")) or "Unknown"

    interval, confirmation_status = _extract_interval(series)
    exit_date, exit_price = _parse_date_price(series.get("Exit Signal Date/Price[$]") or series.get("Exit Date"))
    _, today_price = _parse_date_price(series.get(TODAY_PRICE_COLUMN))
    today_price = today_price if today_price is not None else _to_float(series.get("Today price"))

    signal_price = signal_price if signal_price is not None else _to_float(series.get("Entry Price"))
    signal_date = signal_date or _clean_text(series.get("Entry Date"))

    win_rate = _parse_percent(series.get(WIN_RATE_COLUMN))
    win_rate = win_rate if win_rate is not None else _parse_percent(series.get("Backtested Win Rate [%]"))
    strength = max(0.0, min(1.0, (win_rate or 75.0) / 100.0))

    status = _clean_text(series.get("Status"))
    if not status:
        status = "Closed" if exit_date else "Open"

    function_name = _clean_text(series.get("Function")) or "Unknown"
    technical_signal = _technical_signal_from_side(side)
    timeframe = signal_timeframe_from_interval(interval)

    return QuantSignal(
        symbol=str(symbol).strip(),
        function_name=function_name,
        side=str(side).strip(),
        interval=interval,
        technical_signal=technical_signal,
        signal_timeframe=timeframe,
        signal_date=signal_date,
        signal_price=signal_price,
        exit_date=exit_date,
        exit_price=exit_price,
        today_price=today_price,
        win_rate=win_rate,
        signal_strength=strength,
        confirmation_status=confirmation_status,
        target=_clean_text(series.get(TARGET_COLUMN)),
        stop_loss=_clean_text(series.get(STOP_COLUMN)),
        status=status,
        source_file=str(source_file) if source_file else None,
        source_row=source_row,
        raw=raw,
    )


def normalize_signal_dataframe(df: pd.DataFrame, source_file: Path | str | None = None) -> list[QuantSignal]:
    signals: list[QuantSignal] = []
    for idx, row in df.iterrows():
        signal = normalize_signal_row(row, source_file=source_file, source_row=int(idx))
        if signal.symbol:
            signals.append(signal)
    return signals
