"""
Shared mark-to-market (MTM), holding-period, and latest-price helpers for signal pipelines.

Used by monitored trades (Streamlit) and chatbot consolidated CSV refresh so MTM and
"Today" columns stay consistent.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple, Union

import pandas as pd

# Consolidated CSV column names (single source of truth for refresh logic)
TODAY_PRICE_COLUMN = "Today Trading Date/Price[$], Today Price vs Signal"
# Raw outstanding-signal exports sometimes use this header (lowercase "price").
TODAY_PRICE_COLUMN_LEGACY = "Today Trading Date/Price[$], Today price vs Signal"
MTM_HOLDING_COLUMN = "Current Mark to Market and Holding Period"
TRADING_DAYS_COLUMN = "Trading Days between Signal and Today Date"


def normalize_today_price_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rename legacy \"Today ... price vs Signal\" to the canonical column and merge duplicates.

    Used when loading ``trade_store/US/*_outstanding_signal.csv`` directly.
    """
    if df is None or df.empty:
        return df

    if TODAY_PRICE_COLUMN in df.columns and TODAY_PRICE_COLUMN_LEGACY in df.columns:
        canonical_series = df[TODAY_PRICE_COLUMN]
        legacy_series = df[TODAY_PRICE_COLUMN_LEGACY]
        empty_mask = canonical_series.isna() | (canonical_series.astype(str).str.strip() == "")
        df = df.copy()
        df.loc[empty_mask, TODAY_PRICE_COLUMN] = legacy_series.loc[empty_mask]
        df = df.drop(columns=[TODAY_PRICE_COLUMN_LEGACY])
    elif TODAY_PRICE_COLUMN_LEGACY in df.columns:
        df = df.rename(columns={TODAY_PRICE_COLUMN_LEGACY: TODAY_PRICE_COLUMN})

    return df


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def default_stock_data_dir() -> Path:
    """Default `trade_store/stock_data` under the project root."""
    return _project_root() / "trade_store" / "stock_data"


def normalize_symbol(symbol: Optional[Union[str, float]]) -> str:
    if symbol is None or (isinstance(symbol, float) and pd.isna(symbol)):
        return ""
    return str(symbol).strip()


def parse_symbol_signal_column(value) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[float]]:
    """
    Parse the "Symbol, Signal, Signal Date/Price[$]" column.

    Example: "ETH-USD, Long, 2025-10-10 (Price: 4369.1436)"
    Returns: (symbol, signal_date, signal_type, price)
    """
    try:
        if value is None or pd.isna(value):
            return None, None, None, None

        value_str = str(value).strip()
        if not value_str or value_str.lower() in ("nan", "none", ""):
            return None, None, None, None

        parts = [p.strip() for p in value_str.split(",")]
        if len(parts) < 3:
            return None, None, None, None

        symbol = parts[0]
        signal_type = parts[1]
        date_price_part = parts[2]

        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", date_price_part)
        date = date_match.group(1) if date_match else None

        price_match = re.search(r"Price:\s*([-]?\d+(?:\.\d+)?(?:,\d{3})*)", date_price_part)
        if price_match:
            price_str = price_match.group(1).replace(",", "")
            price = float(price_str)
        else:
            price = None

        return symbol, date, signal_type, price

    except Exception:
        return None, None, None, None


def parse_today_trading_price(value) -> Tuple[Optional[str], Optional[float]]:
    """
    Parse the \"Today Trading Date/Price[$], Today Price vs Signal\" column.

    Example: \"2026-05-08 (Price: 520.3000), 29.67% above\"
    Returns: (yyyy-mm-dd date or None, price or None)
    """
    try:
        if value is None or pd.isna(value):
            return None, None
        value_str = str(value).strip()
        if not value_str:
            return None, None
        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", value_str)
        date_s = date_match.group(1) if date_match else None
        price_match = re.search(r"Price:\s*([-]?\d+(?:\.\d+)?(?:,\d{3})*)", value_str)
        if price_match:
            price = float(price_match.group(1).replace(",", ""))
        else:
            price = None
        return date_s, price
    except Exception:
        return None, None


def resolve_signal_basis(
    signal_open_price_cell,
    compound_symbol_signal_cell,
) -> Tuple[Optional[float], Optional[str], Optional[str]]:
    """
    Choose entry price for MTM: prefer numeric Signal Open Price when valid; else text column price.

    Returns:
        (signal_price, signal_type, signal_date)
    """
    _, sig_date, sig_type, text_price = parse_symbol_signal_column(compound_symbol_signal_cell)

    open_price: Optional[float] = None
    if signal_open_price_cell is not None and pd.notna(signal_open_price_cell):
        try:
            s = str(signal_open_price_cell).strip()
            if s and s.lower() not in ("nan", "none", ""):
                open_price = float(s)
        except (ValueError, TypeError):
            open_price = None

    if open_price is not None and open_price > 0:
        price = open_price
    else:
        price = text_price

    return price, sig_type if sig_type else None, sig_date if sig_date else None


def _find_date_column(df: pd.DataFrame) -> Optional[str]:
    for col in df.columns:
        if col.lower() == "date":
            return col
    return None


def _pick_price_column(df: pd.DataFrame, date_col: str) -> Optional[str]:
    preferred = [
        "Close",
        "close",
        "Adj Close",
        "Adj close",
        "adj close",
        "Adj_Close",
        "adj_close",
        "Price",
        "price",
    ]
    for col in preferred:
        if col in df.columns:
            return col
    for col in df.columns:
        if col != date_col and pd.api.types.is_numeric_dtype(df[col]):
            return col
    return None


def get_latest_price_from_stock_data(
    symbol: str,
    stock_data_dir: Optional[Union[str, Path]] = None,
) -> Tuple[Optional[float], Optional[str]]:
    """
    Latest close (or best available price column) on the most recent calendar date in the CSV.

    Returns:
        (price, date_yyyy_mm_dd) — same order as legacy monitored_trades helpers.
    """
    sym = normalize_symbol(symbol)
    if not sym:
        return None, None

    base = Path(stock_data_dir) if stock_data_dir is not None else default_stock_data_dir()
    stock_data_path = base / f"{sym}.csv"

    if not stock_data_path.exists():
        return None, None

    try:
        df = pd.read_csv(stock_data_path)
        if df.empty:
            return None, None

        date_col = _find_date_column(df)
        if date_col is None:
            return None, None

        df = df.copy()
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.dropna(subset=[date_col])
        if df.empty:
            return None, None

        df = df.sort_values(date_col, ascending=False)
        latest_row = df.iloc[0]

        price_col = _pick_price_column(df, date_col)
        if price_col is None:
            return None, None

        raw_price = latest_row[price_col]
        price = pd.to_numeric(raw_price, errors="coerce")
        if pd.isna(price):
            return None, None

        d = latest_row[date_col]
        if isinstance(d, pd.Timestamp):
            date_str = d.strftime("%Y-%m-%d")
        else:
            date_str = str(d)[:10] if d is not None else None

        return float(price), date_str

    except Exception as e:
        print(f"Error reading stock data for {sym}: {e}")
        return None, None


def batch_latest_prices(
    symbols: Iterable[str],
    stock_data_dir: Optional[Union[str, Path]] = None,
) -> Dict[str, Tuple[Optional[float], Optional[str]]]:
    """
    Load each distinct symbol's latest (price, date) once per refresh batch.

    Keys are normalized symbols as returned from parse_symbol_signal_column (trimmed).
    """
    out: Dict[str, Tuple[Optional[float], Optional[str]]] = {}
    seen = set()
    for s in symbols:
        ns = normalize_symbol(s)
        if not ns or ns in seen:
            continue
        seen.add(ns)
        out[ns] = get_latest_price_from_stock_data(ns, stock_data_dir)
    return out


def calculate_price_change_percentage(current_price, signal_price, signal_type) -> str:
    """Human-readable vs-signal string; inverts for SHORT (matches monitored_trades)."""
    current_price = pd.to_numeric(current_price, errors="coerce")
    signal_price = pd.to_numeric(signal_price, errors="coerce")
    if pd.isna(current_price) or pd.isna(signal_price) or signal_price == 0:
        return "0.0% below"

    try:
        change_pct = ((float(current_price) - float(signal_price)) / float(signal_price)) * 100
        if str(signal_type).upper() == "SHORT":
            change_pct = -change_pct

        if change_pct >= 0:
            return f"{change_pct:.2f}% above"
        return f"{abs(change_pct):.2f}% below"
    except Exception:
        return "0.0% below"


def calculate_holding_period(signal_date, current_date) -> int:
    """Calendar days from signal_date to current_date (non-negative)."""
    try:
        signal_dt = datetime.strptime(str(signal_date)[:10], "%Y-%m-%d")
        current_dt = datetime.strptime(str(current_date)[:10], "%Y-%m-%d")
        return max(0, (current_dt - signal_dt).days)
    except Exception:
        return 0


def calculate_mark_to_market(current_price, signal_price, signal_type) -> str:
    """MTM percentage string; inverts for SHORT."""
    current_price = pd.to_numeric(current_price, errors="coerce")
    signal_price = pd.to_numeric(signal_price, errors="coerce")
    if pd.isna(current_price) or pd.isna(signal_price) or signal_price == 0:
        return "0.0%"

    try:
        change_pct = ((float(current_price) - float(signal_price)) / float(signal_price)) * 100
        if str(signal_type).upper() == "SHORT":
            change_pct = -change_pct
        return f"{change_pct:.2f}%"
    except Exception:
        return "0.0%"


def format_today_trading_cell(latest_date: str, latest_price: float, signal_price, signal_type) -> str:
    """Full value for TODAY_PRICE_COLUMN."""
    if signal_price is not None and pd.notna(signal_price) and float(signal_price) > 0:
        price_change_str = calculate_price_change_percentage(latest_price, signal_price, signal_type)
    else:
        price_change_str = "0.0% below"
    return f"{latest_date} (Price: {float(latest_price):.4f}), {price_change_str}"


def format_mtm_holding_cell(mtm_pct_str: str, holding_days: int) -> str:
    """Full value for MTM_HOLDING_COLUMN."""
    return f"{mtm_pct_str}, {holding_days} days"


def parse_mtm_holding_cell(value) -> Tuple[Optional[str], Optional[int]]:
    """
    Parse ``Current Mark to Market and Holding Period`` cells written by
    ``format_mtm_holding_cell``, e.g. ``12.34%, 5 days`` or ``-3.00%, 10 days``.

    Returns:
        (mtm_pct_display_str including '%', calendar holding_days) or (None, None).
    """
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None, None
        s = str(value).strip()
        if not s or s.lower() in ("nan", "none"):
            return None, None
        m = re.search(r",\s*(\d+)\s*days\s*$", s, flags=re.IGNORECASE)
        if not m:
            return None, None
        days = int(m.group(1))
        mtm_part = s[: m.start()].strip().rstrip(",")
        if not mtm_part:
            return None, None
        return mtm_part, days
    except Exception:
        return None, None


def format_trading_days_cell(holding_days: int) -> str:
    """Full value for TRADING_DAYS_COLUMN."""
    return f"{holding_days} days"


def enrich_row_current_prices(
    row: pd.Series,
    latest_price: float,
    latest_date: str,
) -> Tuple[str, Optional[str], Optional[str]]:
    """
    Compute updated cell strings for today price, MTM+holidays, trading days.

    Returns:
        (today_cell, mtm_cell_or_none, trading_days_cell_or_none)
        If MTM/trading columns should not be written (missing inputs), returns None for those slots.
    """
    compound = row.get("Symbol, Signal, Signal Date/Price[$]", None)
    open_cell = row.get("Signal Open Price", None)
    signal_price, sig_type, sig_date = resolve_signal_basis(open_cell, compound)

    if signal_price is None or pd.isna(signal_price) or float(signal_price) <= 0:
        today_cell = format_today_trading_cell(latest_date, latest_price, None, sig_type or "Long")
        holding_days = calculate_holding_period(sig_date, latest_date) if sig_date else 0
        mtm_cell = format_mtm_holding_cell("0.0%", holding_days)
        td_cell = format_trading_days_cell(holding_days)
        return today_cell, mtm_cell, td_cell

    today_cell = format_today_trading_cell(latest_date, latest_price, signal_price, sig_type or "Long")
    mtm_pct = calculate_mark_to_market(latest_price, signal_price, sig_type or "Long")

    if sig_date:
        holding_days = calculate_holding_period(sig_date, latest_date)
    else:
        holding_days = 0

    mtm_cell = format_mtm_holding_cell(mtm_pct, holding_days)
    td_cell = format_trading_days_cell(holding_days)
    return today_cell, mtm_cell, td_cell
