"""
NZ OHLC fallbacks when yfinance lacks data (delisted NZX names like ZEL.NZ).

Sources (in order, called from market_price_tool):
  1. Stooq daily CSV — optional STOOQ_API_KEY (https://stooq.com/q/d/l/)
  2. NZXplorer API — optional NZXPLORER_API_KEY (https://nzxplorer.co.nz/api/v1/prices/{ticker})
  3. NZX official API — optional NZX_API_KEY (https://api.nzx.com/)
"""

from __future__ import annotations

import io
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests

logger = logging.getLogger(__name__)

_STOOQ_HOSTS = ("https://stooq.pl", "https://stooq.com")
_NZXPLORER_BASE = "https://nzxplorer.co.nz/api/v1"
_NZX_API_BASE = "https://api.nzx.com/api/security"

_HTTP_HEADERS = {
    "User-Agent": "MindWealth-DeepResearch/1.0 (+https://github.com)",
    "Accept": "text/csv,application/json",
}


def to_stooq_symbol(ticker: str) -> str:
    """IFT.NZ -> ift.nz"""
    raw = (ticker or "").strip().upper()
    if not raw:
        return raw
    if "." in raw:
        base, suffix = raw.rsplit(".", 1)
        return f"{base.lower()}.{suffix.lower()}"
    return f"{raw.lower()}.nz"


def to_nzx_ticker(ticker: str) -> str:
    """IFT.NZ -> IFT"""
    raw = (ticker or "").strip().upper()
    return raw.replace(".NZ", "").replace(".AX", "")


def yfinance_symbol_candidates(ticker: str) -> List[str]:
    """Symbols to try on yfinance (NZ first, then AU cross-list)."""
    raw = (ticker or "").strip().upper()
    if not raw:
        return []
    out: List[str] = []
    if raw.endswith(".NZ"):
        out.append(raw)
        base = raw[:-3]
        if base:
            out.append(f"{base}.AX")
    elif raw.endswith(".AX"):
        out.append(raw)
        base = raw[:-3]
        if base:
            out.append(f"{base}.NZ")
    elif re.match(r"^[A-Z]{2,6}$", raw):
        out.extend([f"{raw}.NZ", f"{raw}.AX"])
    else:
        out.append(raw)
    seen: set = set()
    deduped: List[str] = []
    for s in out:
        if s not in seen:
            seen.add(s)
            deduped.append(s)
    return deduped


def _parse_stooq_csv(text: str) -> Optional[pd.DataFrame]:
    if not text or len(text) < 20:
        return None
    if "apikey" in text.lower() or "get your apikey" in text.lower():
        return None
    try:
        df = pd.read_csv(io.StringIO(text))
    except Exception:
        return None
    if df.empty:
        return None
    # Stooq: Date, Open, High, Low, Close, Volume
    cols = {c.lower(): c for c in df.columns}
    date_col = cols.get("date")
    close_col = cols.get("close")
    if not date_col or not close_col:
        return None
    out = df[[date_col, close_col]].copy()
    out.columns = ["Date", "Close"]
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
    out["Close"] = pd.to_numeric(out["Close"], errors="coerce")
    out = out.dropna().set_index("Date").sort_index()
    return out if not out.empty else None


def load_stooq_ohlc(
    ticker: str,
    *,
    api_key: Optional[str] = None,
    timeout: float = 12.0,
) -> Tuple[Optional[pd.DataFrame], str]:
    sym = to_stooq_symbol(ticker)
    params: Dict[str, str] = {"s": sym, "i": "d"}
    if api_key:
        params["apikey"] = api_key.strip()

    for host in _STOOQ_HOSTS:
        url = f"{host}/q/d/l/"
        try:
            resp = requests.get(
                url,
                params=params,
                headers=_HTTP_HEADERS,
                timeout=timeout,
            )
            resp.raise_for_status()
            df = _parse_stooq_csv(resp.text)
            if df is not None and not df.empty:
                logger.info("[market_price] Stooq OHLC for %s (%d rows)", sym, len(df))
                return df, "stooq"
        except requests.Timeout:
            logger.warning("Stooq timeout for %s via %s", sym, host)
        except Exception as exc:
            logger.warning("Stooq fetch failed for %s via %s: %s", sym, host, exc)
    return None, "none"


def _parse_nzxplorer_prices(payload: Any) -> Optional[pd.DataFrame]:
    """Normalize NZXplorer /prices JSON envelope to Date-indexed Close."""
    if payload is None:
        return None

    rows: List[Dict[str, Any]] = []
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        for key in ("prices", "history", "data", "records", "daily"):
            val = payload.get(key)
            if isinstance(val, list) and val:
                rows = val
                break
        if not rows and "data" in payload and isinstance(payload["data"], dict):
            inner = payload["data"]
            for key in ("prices", "history", "daily"):
                val = inner.get(key)
                if isinstance(val, list) and val:
                    rows = val
                    break
        if not rows:
            # flat envelope with single series
            for k, v in payload.items():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    rows = v
                    break

    if not rows:
        return None

    records = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        date_val = (
            row.get("date")
            or row.get("Date")
            or row.get("trading_date")
            or row.get("day")
        )
        close_val = (
            row.get("close")
            or row.get("Close")
            or row.get("adj_close")
            or row.get("last")
            or row.get("price")
        )
        if date_val is None or close_val is None:
            continue
        records.append({"Date": date_val, "Close": close_val})

    if not records:
        return None

    df = pd.DataFrame(records)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    df = df.dropna().set_index("Date").sort_index()
    return df if not df.empty else None


def load_nzxplorer_ohlc(
    ticker: str,
    *,
    api_key: Optional[str] = None,
    timeout: float = 15.0,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Tuple[Optional[pd.DataFrame], str]:
    if not api_key:
        return None, "none"

    nzx = to_nzx_ticker(ticker)
    url = f"{_NZXPLORER_BASE}/prices/{nzx}"
    params: Dict[str, Any] = {"limit": 2000}
    if start_date:
        params["from"] = start_date
    if end_date:
        params["to"] = end_date

    headers = {**_HTTP_HEADERS, "X-API-Key": api_key.strip()}

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=timeout)
        if resp.status_code == 404:
            logger.warning("NZXplorer: no price history for %s", nzx)
            return None, "none"
        resp.raise_for_status()
        body = resp.json()
        data = body.get("data", body) if isinstance(body, dict) else body
        df = _parse_nzxplorer_prices(data)
        if df is not None and not df.empty:
            logger.info("[market_price] NZXplorer OHLC for %s (%d rows)", nzx, len(df))
            return df, "nzxplorer"
    except Exception as exc:
        logger.warning("NZXplorer prices failed for %s: %s", nzx, exc)
    return None, "none"


def _parse_nzx_api_prices(payload: Any) -> Optional[pd.DataFrame]:
    if not isinstance(payload, dict):
        return None
    series = payload.get("prices") or payload.get("data") or payload.get("history")
    if isinstance(series, list):
        return _parse_nzxplorer_prices(series)
    return _parse_nzxplorer_prices(payload)


def load_nzx_api_ohlc(
    ticker: str,
    *,
    api_key: Optional[str] = None,
    timeout: float = 15.0,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Tuple[Optional[pd.DataFrame], str]:
    """Official api.nzx.com security prices (requires NZX_API_KEY)."""
    if not api_key:
        return None, "none"

    nzx = to_nzx_ticker(ticker)
    url = f"{_NZX_API_BASE}/{nzx}/prices"
    params: Dict[str, str] = {}
    if start_date:
        params["start"] = start_date
    if end_date:
        params["end"] = end_date

    headers = {
        **_HTTP_HEADERS,
        "Authorization": f"Bearer {api_key.strip()}",
    }

    try:
        resp = requests.get(url, params=params or None, headers=headers, timeout=timeout)
        if resp.status_code in (401, 403):
            logger.warning("NZX API auth failed for %s (%s)", nzx, resp.status_code)
            return None, "none"
        resp.raise_for_status()
        df = _parse_nzx_api_prices(resp.json())
        if df is not None and not df.empty:
            logger.info("[market_price] NZX API OHLC for %s (%d rows)", nzx, len(df))
            return df, "nzx_api"
    except Exception as exc:
        logger.warning("NZX API prices failed for %s: %s", nzx, exc)
    return None, "none"


def load_nz_fallback_ohlc(
    ticker: str,
    *,
    stooq_api_key: Optional[str] = None,
    nzxplorer_api_key: Optional[str] = None,
    nzx_api_key: Optional[str] = None,
    enable_stooq: bool = True,
    enable_nzx: bool = True,
    stooq_timeout: float = 12.0,
    nzx_timeout: float = 15.0,
) -> Tuple[Optional[pd.DataFrame], str]:
    """Try Stooq then NZXplorer then NZX API for NZ-listed tickers."""
    if not enable_stooq and not enable_nzx:
        return None, "none"

    if enable_stooq:
        df, src = load_stooq_ohlc(
            ticker, api_key=stooq_api_key, timeout=stooq_timeout
        )
        if df is not None:
            return df, src

    if enable_nzx:
        df, src = load_nzxplorer_ohlc(
            ticker, api_key=nzxplorer_api_key, timeout=nzx_timeout
        )
        if df is not None:
            return df, src

        df, src = load_nzx_api_ohlc(ticker, api_key=nzx_api_key, timeout=nzx_timeout)
        if df is not None:
            return df, src

    return None, "none"
