"""
Market price lookups for Deep Research — yfinance, trade_store, Stooq, NZX fallbacks.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

# NZ name / alias → primary listing symbol
NZ_TICKER_ALIASES: Dict[str, str] = {
    "z energy": "ZEL.NZ",
    "zel": "ZEL.NZ",
    "zel.nz": "ZEL.NZ",
    "infratil": "IFT.NZ",
    "ift": "IFT.NZ",
    "contact": "CEN.NZ",
    "contact energy": "CEN.NZ",
    "cen": "CEN.NZ",
    "cen.nz": "CEN.NZ",
    "trustpower": "TPW.NZ",
    "tpw": "TPW.NZ",
    "genesis": "GNE.NZ",
    "genesis energy": "GNE.NZ",
    "gne": "GNE.NZ",
    "meridian": "MEL.NZ",
    "meridian energy": "MEL.NZ",
    "mel": "MEL.NZ",
    "mercury": "MCY.NZ",
    "mercury nz": "MCY.NZ",
    "mcy": "MCY.NZ",
    "air new zealand": "AIR.NZ",
    "air nz": "AIR.NZ",
    "air": "AIR.NZ",
    "origin energy": "ORG.AX",
    "origin": "ORG.AX",
    "org": "ORG.AX",
    "org.nz": "ORG.AX",
}


def to_yfinance_symbol(ticker: str) -> str:
    """Normalize ticker to primary symbol (NZ listings stay .NZ for Z Energy etc.)."""
    raw = (ticker or "").strip()
    if not raw:
        return raw
    key = raw.lower().replace(".nz", "").strip()
    if key in NZ_TICKER_ALIASES:
        return NZ_TICKER_ALIASES[key]
    for alias, sym in NZ_TICKER_ALIASES.items():
        if alias in key or key in alias:
            return sym
    upper = raw.upper()
    if upper.endswith(".NZ") or upper.endswith(".AX"):
        return upper
    if re.match(r"^[A-Z]{2,6}$", upper):
        return f"{upper}.NZ"
    return upper


def _is_nz_listed(symbol: str) -> bool:
    return (symbol or "").upper().endswith(".NZ")


def _parse_date(d: str) -> pd.Timestamp:
    """Timezone-naive midnight timestamp for comparisons with normalized OHLC index."""
    ts = pd.Timestamp(d)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    else:
        ts = ts.tz_localize(None)
    return ts.normalize()


def _normalize_ohlc_index(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize OHLC index to timezone-naive dates so yfinance (tz-aware) and
    trade_store (naive) series compare safely.
    """
    if df is None or df.empty:
        return df
    out = df.copy()
    out = out.reset_index()
    date_col = out.columns[0]
    out[date_col] = pd.to_datetime(out[date_col], utc=True)
    if hasattr(out[date_col].dt, "tz_localize"):
        out[date_col] = out[date_col].dt.tz_localize(None)
    out[date_col] = out[date_col].dt.normalize()
    out = out.set_index(date_col).sort_index()
    cols = [c for c in ("Close", "close") if c in out.columns]
    return out[cols] if cols else out


def _cache_ohlc_to_trade_store(
    df: pd.DataFrame,
    symbol: str,
    stock_data_dir: Path,
) -> None:
    """Persist fetched NZ series for faster repeat lookups."""
    try:
        from chatbot.config import CACHE_NZ_OHLC_TO_TRADE_STORE

        if not CACHE_NZ_OHLC_TO_TRADE_STORE:
            return
        stock_data_dir.mkdir(parents=True, exist_ok=True)
        sym = to_yfinance_symbol(symbol).upper()
        path = stock_data_dir / f"{sym}.csv"
        export = df.reset_index()
        export.columns = ["Date", "Close"]
        export.to_csv(path, index=False)
        logger.info("[market_price] Cached OHLC to %s", path)
    except Exception as exc:
        logger.warning("Failed to cache OHLC for %s: %s", symbol, exc)


def _load_trade_store_ohlc(symbol: str, stock_data_dir: Path) -> Optional[pd.DataFrame]:
    sym = to_yfinance_symbol(symbol)
    base = sym.replace(".NZ", "").replace(".AX", "")
    for candidate in (sym, base, f"{base}.NZ"):
        path = stock_data_dir / f"{candidate}.csv"
        if not path.is_file():
            path = stock_data_dir / f"{candidate.upper()}.csv"
        if path.is_file():
            try:
                df = pd.read_csv(path)
                date_col = "Date" if "Date" in df.columns else "date"
                if date_col not in df.columns:
                    return None
                df[date_col] = pd.to_datetime(df[date_col])
                df = df.set_index(date_col).sort_index()
                if "Close" not in df.columns and "close" in df.columns:
                    df["Close"] = df["close"]
                if "Close" in df.columns:
                    return _normalize_ohlc_index(df[["Close"]].copy())
            except Exception as exc:
                logger.warning("trade_store load failed for %s: %s", candidate, exc)
    return None


def _load_yfinance_ohlc(symbol: str) -> Optional[pd.DataFrame]:
    try:
        import yfinance as yf
    except ImportError:
        return None

    from chatbot.tools.nz_ohlc_fallback import yfinance_symbol_candidates

    for sym in yfinance_symbol_candidates(symbol):
        try:
            t = yf.Ticker(sym)
            hist = t.history(period="max", auto_adjust=False)
            if hist is None or hist.empty or "Close" not in hist.columns:
                continue
            return _normalize_ohlc_index(hist[["Close"]].copy())
        except Exception as exc:
            logger.warning("yfinance history failed for %s: %s", sym, exc)
    return None


def _load_nz_external_ohlc(symbol: str, stock_data_dir: Optional[Path]) -> Tuple[Optional[pd.DataFrame], str]:
    from chatbot.config import (
        ENABLE_NZX_OHLC_FALLBACK,
        ENABLE_STOOQ_OHLC_FALLBACK,
        NZXPLORER_API_KEY,
        NZX_API_KEY,
        NZX_PRICE_REQUEST_TIMEOUT_SECONDS,
        STOOQ_API_KEY,
        STOOQ_REQUEST_TIMEOUT_SECONDS,
    )
    from chatbot.tools.nz_ohlc_fallback import load_nz_fallback_ohlc

    sym = to_yfinance_symbol(symbol)
    if not _is_nz_listed(sym):
        return None, "none"

    df, src = load_nz_fallback_ohlc(
        sym,
        stooq_api_key=STOOQ_API_KEY,
        nzxplorer_api_key=NZXPLORER_API_KEY,
        nzx_api_key=NZX_API_KEY,
        enable_stooq=ENABLE_STOOQ_OHLC_FALLBACK,
        enable_nzx=ENABLE_NZX_OHLC_FALLBACK,
        stooq_timeout=STOOQ_REQUEST_TIMEOUT_SECONDS,
        nzx_timeout=NZX_PRICE_REQUEST_TIMEOUT_SECONDS,
    )
    if df is not None and not df.empty:
        norm = _normalize_ohlc_index(df)
        if stock_data_dir is not None:
            _cache_ohlc_to_trade_store(norm, sym, stock_data_dir)
        return norm, src
    return None, "none"


def fetch_ohlc_series(
    ticker: str,
    stock_data_dir: Optional[Path] = None,
    prefer: str = "yfinance",
) -> Tuple[Optional[pd.DataFrame], str]:
    """Return (close series DataFrame, data_source label)."""
    sym = to_yfinance_symbol(ticker)

    if prefer == "trade_store" and stock_data_dir:
        df = _load_trade_store_ohlc(sym, stock_data_dir)
        if df is not None and not df.empty:
            return df, "trade_store"

    df = _load_yfinance_ohlc(sym)
    if df is not None and not df.empty:
        return df, "yfinance"

    if stock_data_dir:
        df = _load_trade_store_ohlc(sym, stock_data_dir)
        if df is not None and not df.empty:
            return df, "trade_store"

    df, src = _load_nz_external_ohlc(sym, stock_data_dir)
    if df is not None and not df.empty:
        return df, src

    return None, "none"


def fetch_close_on_or_near(
    ticker: str,
    target_date: str,
    stock_data_dir: Optional[Path] = None,
) -> Tuple[Optional[float], Optional[str], str]:
    """
    Close on or after target_date (nearest trading day forward).
    Returns (close, actual_date_iso, data_source).
    """
    series, source = fetch_ohlc_series(ticker, stock_data_dir)
    if series is None or series.empty:
        return None, None, source
    series = _normalize_ohlc_index(series)
    if getattr(series.index, "tz", None) is not None:
        series = series.copy()
        series.index = series.index.tz_convert("UTC").tz_localize(None).normalize()
    target = _parse_date(target_date)
    subset = series.loc[series.index >= target]
    if subset.empty:
        subset = series[series.index <= target]
        if subset.empty:
            return None, None, source
        row = subset.iloc[-1]
    else:
        row = subset.iloc[0]
    actual = row.name
    if hasattr(actual, "strftime"):
        actual_str = pd.Timestamp(actual).strftime("%Y-%m-%d")
    else:
        actual_str = str(actual)[:10]
    return float(row["Close"]), actual_str, source


def _add_months(ts: pd.Timestamp, months: int) -> pd.Timestamp:
    return ts + pd.DateOffset(months=months)


def compute_post_event_returns(
    seller_ticker: Optional[str],
    sold_ticker: Optional[str],
    event_date: str,
    months: Tuple[int, ...] = (1, 3, 6),
    stock_data_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Compute T0 and T+N month closes and % change from T0 for seller and sold tickers.
    """
    warnings: List[str] = []
    event_ts = _parse_date(event_date)
    result: Dict[str, Any] = {
        "event_date": event_ts.strftime("%Y-%m-%d"),
        "seller": None,
        "sold": None,
        "data_source": "none",
        "warnings": warnings,
    }

    def _leg(ticker: Optional[str], label: str) -> Optional[Dict[str, Any]]:
        if not ticker:
            return None
        sym = to_yfinance_symbol(ticker)
        series, source = fetch_ohlc_series(sym, stock_data_dir)
        if series is None or series.empty:
            hint = ""
            if _is_nz_listed(sym):
                hint = (
                    " — try STOOQ_API_KEY or NZXPLORER_API_KEY for delisted NZ names"
                )
            warnings.append(f"No OHLC data for {sym}{hint}")
            return None
        if result["data_source"] == "none":
            result["data_source"] = source

        t0_price, t0_actual, leg_source = fetch_close_on_or_near(
            sym, event_date, stock_data_dir
        )
        if t0_price is None:
            warnings.append(f"No T0 price for {sym} near {event_date}")
            return None

        leg: Dict[str, Any] = {
            "ticker": sym,
            "T0_date": t0_actual,
            "T0": round(t0_price, 4),
            "data_source": leg_source,
        }
        for m in months:
            target = _add_months(event_ts, m)
            price, actual, _ = fetch_close_on_or_near(
                sym, target.strftime("%Y-%m-%d"), stock_data_dir
            )
            key = f"T+{m}m"
            if price is not None:
                leg[key] = round(price, 4)
                leg[f"pct_{m}m"] = round((price / t0_price - 1) * 100, 2)
                leg[f"{key}_date"] = actual
            else:
                leg[key] = None
                warnings.append(f"No {key} price for {sym}")
        return leg

    if seller_ticker:
        result["seller"] = _leg(seller_ticker, "seller")
    if sold_ticker:
        result["sold"] = _leg(sold_ticker, "sold")
    result["warnings"] = warnings
    return result


def format_price_table_md(price_result: Dict[str, Any], precedent_name: str = "") -> str:
    """Markdown table for synthesis evidence pack."""
    lines = ["=== COMPUTED PRICE DATA (yfinance / trade_store / stooq / nzx) ==="]
    if precedent_name:
        lines.append(f"Precedent: {precedent_name}")
    lines.append(f"Event date: {price_result.get('event_date', 'unknown')}")
    lines.append(f"Data source: {price_result.get('data_source', 'none')}")
    for role in ("seller", "sold"):
        leg = price_result.get(role)
        if not leg:
            continue
        src = leg.get("data_source", "")
        src_note = f" [{src}]" if src else ""
        lines.append(f"\n### {role.title()} — {leg.get('ticker', '?')}{src_note}")
        lines.append("| Metric | Value |")
        lines.append(f"| T0 ({leg.get('T0_date', '')}) | {leg.get('T0')} |")
        for key, val in leg.items():
            if key.startswith("T+") and "m" in key and not key.endswith("_date"):
                pct = leg.get(f"pct_{key.replace('T+', '').replace('m', '')}m")
                pct_s = f" ({pct}%)" if pct is not None else ""
                date_k = leg.get(f"{key}_date", "")
                lines.append(f"| {key} ({date_k}) | {val}{pct_s} |")
    if price_result.get("warnings"):
        lines.append("\nWarnings: " + "; ".join(price_result["warnings"]))
    lines.append("=== END COMPUTED PRICE DATA ===")
    return "\n".join(lines)
