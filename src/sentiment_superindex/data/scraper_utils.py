"""Shared helpers for SSI / macro scrapers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd
import requests

BROWSER_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

CNN_HEADERS: dict[str, str] = {
    **BROWSER_HEADERS,
    "Referer": "https://www.cnn.com/markets/fear-and-greed",
    "Origin": "https://www.cnn.com",
}


def http_get(url: str, *, headers: dict[str, str] | None = None, timeout: int = 30) -> requests.Response:
    return requests.get(url, headers=headers or BROWSER_HEADERS, timeout=timeout)


def is_excel_content(content: bytes) -> bool:
    if len(content) < 4:
        return False
    if content[:2] == b"PK":  # xlsx/zip
        return True
    if content[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":  # legacy xls
        return True
    return False


def clamp_index_score(value: float, *, low: float = 0.0, high: float = 100.0) -> float | None:
    if value is None or pd.isna(value):
        return None
    v = float(value)
    if v < low or v > high:
        return None
    return v


def parse_cnn_historical_points(
    block: dict[str, Any] | None,
    *,
    clamp_0_100: bool = True,
) -> pd.Series:
    """Parse CNN graphdata sub-block with {data: [{x,y}, ...]}."""
    if not block or not isinstance(block, dict):
        return pd.Series(dtype=float)
    rows = []
    for pt in block.get("data") or []:
        if not isinstance(pt, dict):
            continue
        ts = pt.get("x")
        val = pt.get("y") if pt.get("y") is not None else pt.get("score")
        if val is None or ts is None:
            continue
        score = clamp_index_score(val) if clamp_0_100 else float(val)
        if score is None:
            continue
        try:
            dt = pd.to_datetime(ts, unit="ms" if isinstance(ts, (int, float)) else None)
            rows.append((dt, score))
        except Exception:
            continue
    if not rows:
        return pd.Series(dtype=float)
    s = pd.Series({d: v for d, v in rows}).sort_index()
    s.name = "score"
    return s.astype(float)


def load_cached_series(cache_path: Path, *, value_col: str = "value", date_col: str = "date") -> pd.Series:
    if not cache_path.exists():
        return pd.Series(dtype=float)
    df = pd.read_csv(cache_path, parse_dates=[date_col])
    if value_col not in df.columns:
        cols = [c for c in df.columns if c != date_col]
        if not cols:
            return pd.Series(dtype=float)
        value_col = cols[0]
    return df.set_index(date_col)[value_col].sort_index().astype(float)


def save_cached_series(series: pd.Series, cache_path: Path, *, value_col: str = "value") -> None:
    if series.empty:
        return
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    out = series.dropna().sort_index().reset_index()
    out.columns = ["date", value_col]
    out.to_csv(cache_path, index=False)


def merge_series(existing: pd.Series, new: pd.Series) -> pd.Series:
    if existing.empty:
        return new.sort_index()
    if new.empty:
        return existing.sort_index()
    combined = pd.concat([existing, new])
    return combined[~combined.index.duplicated(keep="last")].sort_index()


def parse_html_table_dates(
    html: str,
    *,
    date_col_hint: str = "date",
    value_cols: list[str] | None = None,
) -> pd.DataFrame:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    if table is None:
        return pd.DataFrame()
    rows = []
    headers: list[str] = []
    for tr in table.find_all("tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all(["th", "td"])]
        if not cells:
            continue
        if not headers and any("date" in c.lower() for c in cells):
            headers = [c.lower().replace(" ", "_") for c in cells]
            continue
        if not headers:
            headers = [f"col{i}" for i in range(len(cells))]
        if len(cells) < len(headers):
            cells += [""] * (len(headers) - len(cells))
        rows.append(dict(zip(headers, cells[: len(headers)])))
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    date_col = next((c for c in df.columns if date_col_hint in c), df.columns[0])
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])
    if value_cols:
        for c in value_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", ""), errors="coerce")
    return df.set_index(date_col).sort_index()


def clean_numeric_series(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").dropna().astype(float)


def normalize_cnn_component(block: dict[str, Any] | None, window: int = 252) -> pd.Series:
    """Map CNN internal y-values to 0–100 via rolling percentile (for breadth/strength)."""
    raw = parse_cnn_historical_points(block, clamp_0_100=False)
    if raw.empty:
        return raw
    if raw.max() <= 100 and raw.min() >= 0:
        return raw.astype(float)
    out: list[float] = []
    for i in range(len(raw)):
        hist = raw.iloc[max(0, i - window + 1) : i + 1]
        out.append(float((hist <= raw.iloc[i]).sum() / len(hist) * 100))
    return pd.Series(out, index=raw.index, dtype=float)


def filter_series_from(series: pd.Series, start: str | None) -> pd.Series:
    if series.empty or not start:
        return series
    if not isinstance(series.index, pd.DatetimeIndex):
        return series
    return series.loc[series.index >= pd.Timestamp(start)]
