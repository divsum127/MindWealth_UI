"""Financial Modeling Prep (FMP) PE-history fallback for thin yfinance history.

Background: ``ConvictionEngine_v5_FINAL.pdf`` (Sec 10.2) originally spec'd Macrotrends
as the auto-fetch source when a US ticker's yfinance-derived PE history has fewer than
20 points. Confirmed 2026-07-24 that Macrotrends is behind a Cloudflare Managed
Challenge (Turnstile) that none of this repo's scraping tools can pass — ``requests``,
``curl_cffi`` (Chrome TLS impersonation), ``cloudscraper``, and headless Playwright
with ``playwright-stealth`` (15s wait) all got stuck on the "Just a moment..." page.
Macrotrends' own ticker-search endpoint is behind the same wall, so slug resolution
isn't viable either. Per direction, this is replaced with a real API instead of a
scrape: Financial Modeling Prep (FMP).

Caveat: FMP's free/Basic tier (250 calls/day) is End-of-Day data with a 5-year
historical range, not 20-30 years — that requires FMP's paid Premium plan. This still
meaningfully improves on yfinance's typical ~0.5-2 year quarterly-EPS depth (e.g. PYPL
was 0.56y from 5 EPS quarters), even though ``insufficient_20y`` will usually still be
True under the current ``PE_HISTORY_TARGET_YEARS`` threshold until/unless that
threshold or the FMP plan tier changes.

Non-US tickers (``.TO``/``.NS``/``.NZ``/etc.) are intentionally out of scope here —
they route to the manual-entry workflow instead (``scripts/set_manual_pe_history.py``),
matching the PDF's own documented fallback for non-US names.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import requests

from src.config_paths import CONVICTION_STORE_DIR

logger = logging.getLogger(__name__)

FMP_RATIOS_URL = "https://financialmodelingprep.com/stable/ratios"
FMP_CACHE_DIR = CONVICTION_STORE_DIR / "pe_history_cache"
FMP_CACHE_MAX_AGE_DAYS = 80  # ~quarterly refresh cadence; avoids re-hitting the 250/day cap
FMP_QUARTERS_REQUESTED = 80  # ~20y of quarters requested; free tier will only return ~20 (5y)

# Ratio field name varies across FMP API versions/docs; try each in order.
_PE_FIELD_CANDIDATES = ("priceToEarningsRatio", "priceEarningsRatio", "peRatio")

# Non-US suffixes used across this universe's ticker naming convention
# (Canada/TSX, India/NSE+BSE, New Zealand, Australia, Hong Kong, Korea, Singapore,
# Paris, Frankfurt/Germany, London). Bare tickers (AAPL, PYPL, MSFT) are treated as US.
_NON_US_SUFFIXES: tuple[str, ...] = (
    ".TO",
    ".V",
    ".NE",
    ".NS",
    ".BO",
    ".NZ",
    ".AX",
    ".HK",
    ".KS",
    ".KQ",
    ".SI",
    ".PA",
    ".F",
    ".DE",
    ".L",
)


def is_us_ticker(ticker: str) -> bool:
    """US-style tickers carry no exchange suffix in this universe's naming convention."""
    if not ticker:
        return False
    symbol = ticker.upper().strip()
    return not any(symbol.endswith(suffix) for suffix in _NON_US_SUFFIXES)


def _cache_path(ticker: str, cache_dir: Path) -> Path:
    return cache_dir / f"{ticker.upper()}.json"


def _load_cache(ticker: str, cache_dir: Path) -> dict[str, Any] | None:
    path = _cache_path(ticker, cache_dir)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text())
    except Exception:
        return None
    fetched_at = payload.get("fetched_at")
    if not isinstance(fetched_at, (int, float)):
        return None
    age_days = (time.time() - fetched_at) / 86400.0
    if age_days > FMP_CACHE_MAX_AGE_DAYS:
        return None
    bundle = payload.get("bundle")
    if not isinstance(bundle, dict) or not bundle.get("values"):
        return None
    return bundle


def _save_cache(ticker: str, bundle: dict[str, Any], cache_dir: Path) -> None:
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        _cache_path(ticker, cache_dir).write_text(
            json.dumps({"fetched_at": time.time(), "bundle": bundle})
        )
    except Exception:
        logger.debug("pe_history_fmp: failed to write cache for %s", ticker, exc_info=True)


def _get_with_backoff(url: str, params: dict[str, Any], *, max_attempts: int = 2, timeout: int = 20) -> requests.Response | None:
    delay = 2.0
    resp: requests.Response | None = None
    for _ in range(max_attempts):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
        except Exception:
            resp = None
        if resp is not None and resp.status_code == 200:
            return resp
        if resp is not None and resp.status_code in (429, 500, 502, 503):
            time.sleep(delay)
            delay = min(delay * 2, 20.0)
            continue
        break
    return resp


def _parse_fmp_ratios_response(rows: list[dict[str, Any]], *, target_years: int) -> dict[str, Any] | None:
    """Turn FMP's ``/stable/ratios`` quarterly rows into the same ``{values, meta}``
    shape ``compute_pe_history()`` produces, so callers can treat the two sources
    identically. Returns ``None`` when no usable PE points are present.
    """
    if not rows:
        return None

    points: list[tuple[str, float]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        date_str = row.get("date")
        if not date_str:
            continue
        pe_val = None
        for field in _PE_FIELD_CANDIDATES:
            if row.get(field) is not None:
                pe_val = row.get(field)
                break
        if pe_val is None:
            continue
        try:
            pe_float = float(pe_val)
        except (TypeError, ValueError):
            continue
        if not (0 < pe_float < 500):
            continue
        points.append((str(date_str), round(pe_float, 4)))

    if not points:
        return None

    points.sort(key=lambda pair: pair[0])
    dates = [p[0] for p in points]
    values = [p[1] for p in points]

    from datetime import datetime

    first_dt = datetime.fromisoformat(dates[0])
    last_dt = datetime.fromisoformat(dates[-1])
    years_available = round((last_dt - first_dt).days / 365.25, 2)

    meta = {
        "years_available": years_available,
        "price_years_available": years_available,
        "eps_quarters": len(values),
        "eps_years_available": years_available,
        "start_date": dates[0],
        "end_date": dates[-1],
        "point_count": len(values),
        "stored_point_count": len(values),
        "target_years": target_years,
        "insufficient_20y": years_available < target_years,
        "source": "fmp",
    }
    return {"values": values, "meta": meta}


def fetch_pe_history_fmp(
    ticker: str,
    *,
    target_years: int = 20,
    cache_dir: Path | None = None,
    api_key: str | None = None,
) -> dict[str, Any] | None:
    """Fetch quarterly PE history from FMP for a US ticker.

    Returns ``None`` (never raises) when: no API key is configured, the ticker isn't
    US-style, the request fails/rate-limits out, or the response has no usable points
    — callers should keep whatever yfinance-derived bundle they already had in that
    case. A successful result is cached on disk for ``FMP_CACHE_MAX_AGE_DAYS`` so
    repeated ``full_recalculation`` runs don't re-spend the 250-calls/day budget.
    """
    if not is_us_ticker(ticker):
        return None

    key = api_key if api_key is not None else os.environ.get("FMP_API_KEY")
    if not key:
        logger.debug("pe_history_fmp: FMP_API_KEY not set, skipping fetch for %s", ticker)
        return None

    resolved_cache_dir = cache_dir if cache_dir is not None else FMP_CACHE_DIR
    cached = _load_cache(ticker, resolved_cache_dir)
    if cached is not None:
        return cached

    resp = _get_with_backoff(
        FMP_RATIOS_URL,
        {"symbol": ticker, "period": "quarter", "limit": FMP_QUARTERS_REQUESTED, "apikey": key},
    )
    if resp is None or resp.status_code != 200:
        logger.warning("pe_history_fmp: fetch failed for %s (status=%s)", ticker, getattr(resp, "status_code", None))
        return None

    try:
        rows = resp.json()
    except Exception:
        logger.warning("pe_history_fmp: non-JSON response for %s", ticker)
        return None

    if not isinstance(rows, list):
        return None

    bundle = _parse_fmp_ratios_response(rows, target_years=target_years)
    if bundle is None:
        return None

    _save_cache(ticker, bundle, resolved_cache_dir)
    return bundle
