"""CBOE total put/call ratio — bulk CSV history + CNN live component, 10-week EMA.

Sources (merged, later/higher-priority wins on duplicate dates):
  1. CBOE totalpcarchive.csv — 2003-10-17 → ~2012-06-07
  2. CBOE totalpc.csv — 2006-11-01 → 2019-10-04
  3. CNN fear-and-greed graphdata put_call_options — 2020-07-14 → today (live)
  4. Optional Equibles API when EQUIBLES_API_KEY is set — fills 2019-10 → 2020-07 gap

The Layer 1 SSI input is the 10-week EMA (span=50 trading days) of the daily ratio.
"""

from __future__ import annotations

import io
import os
from typing import Iterable

import pandas as pd

from src.config_paths import SSI_DATA_DIR
from src.sentiment_superindex.data.scraper_utils import (
    CNN_HEADERS,
    BROWSER_HEADERS,
    http_get,
    load_cached_series,
    merge_series,
    parse_cnn_historical_points,
    save_cached_series,
)
from src.sentiment_superindex.data.pull_guard import log_pull_empty, log_pull_failure

CBOE_TOTAL_URL = "https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/totalpc.csv"
CBOE_ARCHIVE_URL = "https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/totalpcarchive.csv"
CNN_GRAPHDATA_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
CNN_EARLIEST_START_DATE = "2020-07-14"
EQUIBLES_URL = "https://api.equibles.com/v1/market/put-call-ratios"

# 10 calendar weeks ≈ 50 NYSE trading days on a daily series.
EMA_SPAN_TRADING_DAYS = 50

CACHE_CSV = SSI_DATA_DIR / "put_call_ema.csv"
CACHE_RAW_CSV = SSI_DATA_DIR / "put_call_ratio_raw.csv"


def _find_header_line(lines: Iterable[str], *prefixes: str) -> int | None:
    for i, line in enumerate(lines):
        upper = line.strip().upper()
        if any(upper.startswith(p.upper()) for p in prefixes):
            return i
    return None


def _parse_cboe_ratio_csv(text: str, *, date_headers: tuple[str, ...], ratio_headers: tuple[str, ...]) -> pd.Series:
    lines = text.splitlines()
    header_idx = _find_header_line(lines, *date_headers)
    if header_idx is None:
        return pd.Series(dtype=float, name="put_call_ratio")
    df = pd.read_csv(io.StringIO("\n".join(lines[header_idx:])))
    df.columns = [str(c).strip() for c in df.columns]
    date_col = next((c for c in df.columns if c.upper() in {h.upper() for h in date_headers}), df.columns[0])
    ratio_col = next(
        (
            c
            for c in df.columns
            if c.upper() in {h.upper() for h in ratio_headers}
            or "p/c" in c.lower()
            or "ratio" in c.lower()
        ),
        df.columns[-1],
    )
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    ratio = pd.to_numeric(df[ratio_col], errors="coerce")
    out = pd.Series(ratio.values, index=df[date_col], name="put_call_ratio").dropna()
    out.index = pd.to_datetime(out.index).normalize()
    return out[~out.index.duplicated(keep="last")].sort_index().astype(float)


def _fetch_cboe_totalpc() -> pd.Series:
    try:
        resp = http_get(CBOE_TOTAL_URL, headers=BROWSER_HEADERS, timeout=45)
        resp.raise_for_status()
    except Exception as exc:
        log_pull_failure("ssi_put_call_cboe_total", exc, note=CBOE_TOTAL_URL)
        return pd.Series(dtype=float, name="put_call_ratio")
    return _parse_cboe_ratio_csv(
        resp.text,
        date_headers=("DATE",),
        ratio_headers=("P/C Ratio", "P/C RATIO"),
    )


def _fetch_cboe_archive() -> pd.Series:
    try:
        resp = http_get(CBOE_ARCHIVE_URL, headers=BROWSER_HEADERS, timeout=45)
        resp.raise_for_status()
    except Exception as exc:
        log_pull_failure("ssi_put_call_cboe_archive", exc, note=CBOE_ARCHIVE_URL)
        return pd.Series(dtype=float, name="put_call_ratio")
    return _parse_cboe_ratio_csv(
        resp.text,
        date_headers=("Trade_date", "DATE"),
        ratio_headers=("P/C Ratio", "P/C RATIO"),
    )


def _fetch_cnn_put_call_ratio() -> pd.Series:
    try:
        resp = http_get(f"{CNN_GRAPHDATA_URL}/{CNN_EARLIEST_START_DATE}", headers=CNN_HEADERS, timeout=45)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        log_pull_failure("ssi_put_call_cnn", exc, note=CNN_GRAPHDATA_URL)
        return pd.Series(dtype=float, name="put_call_ratio")
    series = parse_cnn_historical_points(data.get("put_call_options"), clamp_0_100=False)
    if series.empty:
        return series
    series.index = pd.to_datetime(series.index).normalize()
    series.name = "put_call_ratio"
    return series.astype(float)


def _fetch_equibles_put_call_ratio(api_key: str, *, max_pages: int = 20) -> pd.Series:
    """Optional gap-fill source (2019-10 → 2020-07) when EQUIBLES_API_KEY is configured."""
    rows: list[tuple[pd.Timestamp, float]] = []
    offset = 0
    limit = 500
    headers = {"Authorization": f"Bearer {api_key}"}
    for _ in range(max_pages):
        try:
            resp = http_get(
                f"{EQUIBLES_URL}?limit={limit}&offset={offset}",
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
            payload = resp.json()
        except Exception:
            break
        data = payload.get("data") if isinstance(payload, dict) else None
        if not data:
            break
        for item in data:
            if not isinstance(item, dict):
                continue
            dt_raw = item.get("date") or item.get("trade_date")
            ratio = item.get("put_call_ratio") or item.get("pc_ratio") or item.get("ratio")
            if dt_raw is None or ratio is None:
                continue
            try:
                dt = pd.Timestamp(dt_raw).normalize()
                val = float(ratio)
            except (TypeError, ValueError):
                continue
            if val > 0:
                rows.append((dt, val))
        if len(data) < limit:
            break
        offset += limit
    if not rows:
        return pd.Series(dtype=float, name="put_call_ratio")
    s = pd.Series({d: v for d, v in rows}, name="put_call_ratio").sort_index()
    s.index = pd.to_datetime(s.index).normalize()
    return s[~s.index.duplicated(keep="last")].astype(float)


def _merge_raw_sources(*series_list: pd.Series) -> pd.Series:
    """Merge with ascending priority — later series override earlier on duplicate dates."""
    merged = pd.Series(dtype=float, name="put_call_ratio")
    for s in series_list:
        if s is None or s.empty:
            continue
        clean = s.dropna().astype(float)
        clean.index = pd.to_datetime(clean.index).normalize()
        merged = merge_series(merged, clean)
    return merged.sort_index()


def compute_put_call_ema(raw_ratio: pd.Series, *, span: int = EMA_SPAN_TRADING_DAYS) -> pd.Series:
    if raw_ratio is None or raw_ratio.empty:
        return pd.Series(dtype=float, name="put_call_ema")
    daily = raw_ratio.dropna().astype(float).sort_index()
    daily.index = pd.to_datetime(daily.index).normalize()
    ema = daily.ewm(span=span, adjust=False, min_periods=max(10, span // 5)).mean()
    ema.name = "put_call_ema"
    return ema.dropna().astype(float)


def fetch_put_call_ratio_raw() -> pd.Series:
    """Daily CBOE total put/call ratio (unsmoothed)."""
    cached = load_cached_series(CACHE_RAW_CSV, value_col="put_call_ratio")
    sources: list[pd.Series] = [_fetch_cboe_archive(), _fetch_cboe_totalpc()]
    api_key = os.environ.get("EQUIBLES_API_KEY", "").strip()
    if api_key:
        sources.append(_fetch_equibles_put_call_ratio(api_key))
    sources.append(_fetch_cnn_put_call_ratio())
    live = _merge_raw_sources(*sources)
    merged = merge_series(cached, live)
    if not merged.empty:
        save_cached_series(merged, CACHE_RAW_CSV, value_col="put_call_ratio")
    return merged


def fetch_put_call_ema() -> pd.Series:
    """10-week EMA of CBOE total put/call ratio — SSI Layer 1 input."""
    raw = fetch_put_call_ratio_raw()
    ema = compute_put_call_ema(raw)
    if not ema.empty:
        save_cached_series(ema, CACHE_CSV, value_col="put_call_ema")
    if ema.empty:
        return load_cached_series(CACHE_CSV, value_col="put_call_ema")
    return ema
