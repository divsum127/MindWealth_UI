"""AAII bull-bear spread — live fetch, GitHub-synced cache, local XLS/CSV fallback."""

from __future__ import annotations

import io
import logging
import os
import time
import urllib.request
from pathlib import Path
from typing import Any, Protocol

import pandas as pd
import requests
from bs4 import BeautifulSoup

from src.config_paths import MACRO_INTEL_DATA_DIR
from src.sentiment_superindex.data.scraper_utils import (
    BROWSER_HEADERS,
    is_excel_content,
    load_cached_series,
    merge_series,
    save_cached_series,
)

logger = logging.getLogger(__name__)

AAII_HOME = "https://www.aaii.com/"
AAII_URL = "https://www.aaii.com/files/surveys/sentiment.xls"
AAII_RESULTS_URL = "https://www.aaii.com/sentimentsurvey/sent_results"
CACHE_CSV = MACRO_INTEL_DATA_DIR / "aaii_sentiment.csv"
CACHE_XLS = MACRO_INTEL_DATA_DIR / "aaii_sentiment.xls"
AAII_IMPERSONATE = "chrome120"
# GitHub Actions commits fresh files here; AWS pulls via raw URL (no paid proxy).
DEFAULT_GITHUB_RAW_BASE = "https://raw.githubusercontent.com/divsum127/MindWealth_UI/main"

_AAII_HEADERS: dict[str, str] = {
    **BROWSER_HEADERS,
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*;q=0.8"
    ),
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}

_BOT_MARKERS = (
    "Pardon Our Interruption",
    "Incapsula incident ID",
    "_Incapsula_Resource",
    "initializeProtection",
)


class _HttpSession(Protocol):
    def get(self, url: str, **kwargs: Any) -> Any: ...


def _aaii_proxies() -> dict[str, str] | None:
    """Optional egress proxy (INVESTING_HTTP_PROXY or HTTP(S)_PROXY)."""
    proxy = (
        os.environ.get("INVESTING_HTTP_PROXY")
        or os.environ.get("HTTPS_PROXY")
        or os.environ.get("HTTP_PROXY")
    )
    if not proxy:
        return None
    return {"http": proxy, "https": proxy}


def _is_bot_wall(content: bytes | str) -> bool:
    text = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else content
    return any(marker in text for marker in _BOT_MARKERS)


def _pct_to_float(val: str) -> float:
    return float(str(val).replace("%", "").strip())


def _normalize_spread_units(bull: pd.Series, bear: pd.Series) -> pd.Series:
    """Return bull-minus-bear spread in percentage points (e.g. 13.5)."""
    b = pd.to_numeric(bull, errors="coerce")
    r = pd.to_numeric(bear, errors="coerce")
    if b.dropna().empty:
        return pd.Series(dtype=float)
    scale = 100.0 if float(b.dropna().abs().median()) <= 1.5 else 1.0
    return ((b - r) * scale).astype(float)


def _get_with_backoff(
    session: _HttpSession,
    url: str,
    *,
    headers: dict[str, str],
    proxies: dict[str, str] | None,
    referer: str | None = None,
    max_attempts: int = 2,
    timeout: int = 45,
) -> requests.Response | None:
    hdrs = {**headers, **({"Referer": referer} if referer else {})}
    delay = 2.0
    for _ in range(max_attempts):
        try:
            resp = session.get(url, headers=hdrs, timeout=timeout, proxies=proxies)
        except Exception:
            resp = None
        if resp is not None and resp.status_code == 200:
            if _is_bot_wall(resp.content):
                return None
            return resp
        if resp is not None and resp.status_code in (403, 429, 503):
            retry_after = getattr(resp, "headers", {}).get("Retry-After")
            wait = float(retry_after) if retry_after and str(retry_after).isdigit() else delay
            time.sleep(min(wait, 30.0))
            delay = min(delay * 2, 30.0)
            continue
        time.sleep(delay)
        delay = min(delay * 2, 30.0)
    return resp if resp is not None else None


def _fetch_aaii_curl_cffi(url: str, *, referer: str | None = None) -> bytes | None:
    try:
        from curl_cffi import requests as creq
    except ImportError:
        return None

    proxies = _aaii_proxies()
    session = creq.Session(impersonate=AAII_IMPERSONATE)
    if _get_with_backoff(session, AAII_HOME, headers=_AAII_HEADERS, proxies=proxies, timeout=30) is not None:
        time.sleep(0.5)
    resp = _get_with_backoff(
        session,
        url,
        headers=_AAII_HEADERS,
        proxies=proxies,
        referer=referer or AAII_HOME,
    )
    if resp is None or _is_bot_wall(resp.content):
        return None
    return resp.content


def _fetch_aaii_cloudscraper(url: str, *, referer: str | None = None) -> bytes | None:
    try:
        import cloudscraper
    except ImportError:
        return None

    proxies = _aaii_proxies()
    session = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False},
    )
    session.headers.update(_AAII_HEADERS)
    if proxies:
        session.proxies.update(proxies)
    _get_with_backoff(session, AAII_HOME, headers=_AAII_HEADERS, proxies=proxies)
    time.sleep(1.0)
    resp = _get_with_backoff(
        session,
        url,
        headers=_AAII_HEADERS,
        proxies=proxies,
        referer=referer or AAII_HOME,
    )
    if resp is None or _is_bot_wall(resp.content):
        return None
    return resp.content


def _fetch_aaii_urllib(url: str, *, referer: str | None = None) -> bytes | None:
    """Direct fetch without homepage warmup — works from AWS when Imperva blocks /."""
    req = urllib.request.Request(url)
    for key, val in _AAII_HEADERS.items():
        if key.lower() == "accept-encoding":
            continue
        req.add_header(key, val)
    if referer:
        req.add_header("Referer", referer)
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            content = resp.read()
    except Exception:
        return None
    if _is_bot_wall(content):
        return None
    return content


def _fetch_aaii_requests(url: str, *, referer: str | None = None) -> bytes | None:
    session = requests.Session()
    session.headers.update(_AAII_HEADERS)
    proxies = _aaii_proxies()
    _get_with_backoff(session, AAII_HOME, headers=_AAII_HEADERS, proxies=proxies)
    time.sleep(0.5)
    resp = _get_with_backoff(
        session,
        url,
        headers=_AAII_HEADERS,
        proxies=proxies,
        referer=referer or AAII_HOME,
    )
    if resp is None or _is_bot_wall(resp.content):
        return None
    return resp.content


def _fetch_aaii_bytes(url: str, *, referer: str | None = None) -> tuple[bytes | None, str]:
    """Try urllib (direct) → curl_cffi → cloudscraper → requests."""
    for fetcher, tag in (
        (_fetch_aaii_urllib, "aaii_urllib"),
        (_fetch_aaii_curl_cffi, "aaii_curl_cffi"),
        (_fetch_aaii_cloudscraper, "aaii_cloudscraper"),
        (_fetch_aaii_requests, "aaii_requests"),
    ):
        try:
            content = fetcher(url, referer=referer)
        except Exception:
            content = None
        if content and not _is_bot_wall(content):
            return content, tag
    return None, "aaii_blocked"


def _parse_sent_results_html(html: str) -> pd.Series:
    soup = BeautifulSoup(html, "lxml")
    rows: list[tuple[pd.Timestamp, float]] = []
    for table in soup.find_all("table"):
        headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        if not headers or "bullish" not in headers or "bearish" not in headers:
            continue
        bi = headers.index("bullish")
        bei = headers.index("bearish")
        di = headers.index("reported date") if "reported date" in headers else 0
        for tr in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if len(cells) <= max(bi, bei, di):
                continue
            if cells[di].lower() in ("reported date", ""):
                continue
            try:
                dt = pd.to_datetime(cells[di])
                spread = _pct_to_float(cells[bi]) - _pct_to_float(cells[bei])
                rows.append((dt, spread))
            except Exception:
                continue
    if not rows:
        return pd.Series(dtype=float)
    s = pd.Series({d: v for d, v in rows}).sort_index()
    s.name = "aaii_spread"
    return s.astype(float)


def _scrape_sent_results_table() -> pd.Series:
    series, _tag = _scrape_sent_results_live()
    return series


def _scrape_sent_results_live() -> tuple[pd.Series, str]:
    content, tag = _fetch_aaii_bytes(AAII_RESULTS_URL, referer=AAII_RESULTS_URL)
    if not content:
        return pd.Series(dtype=float), tag
    series = _parse_sent_results_html(content.decode("utf-8", errors="replace"))
    return series, tag if not series.empty else "aaii_blocked"


def _read_aaii_excel(source: Path | io.BytesIO) -> pd.Series:
    """Parse official AAII sentiment.xls (SENTIMENT sheet, header row 4)."""
    try:
        df = pd.read_excel(source, sheet_name="SENTIMENT", engine="xlrd", skiprows=3)
    except Exception:
        try:
            df = pd.read_excel(source, sheet_name=0, engine="xlrd", skiprows=3)
        except Exception:
            return pd.Series(dtype=float)

    if df.empty:
        return pd.Series(dtype=float)

    date_col = next((c for c in df.columns if "date" in str(c).lower()), df.columns[0])
    bull = next((c for c in df.columns if str(c).lower() == "bullish"), None)
    bear = next((c for c in df.columns if str(c).lower() == "bearish"), None)
    spread_col = next((c for c in df.columns if str(c).lower() == "spread"), None)

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])
    if df.empty:
        return pd.Series(dtype=float)

    if bull is not None:
        b = pd.to_numeric(df[bull], errors="coerce")
        df = df[(b <= 1.5) | ((b > 1.5) & (b <= 100))]
    if df.empty:
        return pd.Series(dtype=float)

    if bull is not None and bear is not None:
        spread = _normalize_spread_units(df[bull], df[bear])
    elif spread_col is not None:
        raw = pd.to_numeric(df[spread_col], errors="coerce")
        scale = 100.0 if float(raw.dropna().abs().median()) <= 1.5 else 1.0
        spread = (raw * scale).astype(float)
    else:
        return pd.Series(dtype=float)

    out = pd.Series(spread.values, index=df[date_col]).dropna()
    out = out[(out.index.notna()) & (out.abs() <= 100)]
    out = out.sort_index()
    out.name = "aaii_spread"
    return out.astype(float)


def _parse_aaii_frame(df: pd.DataFrame) -> pd.Series:
    """Parse CSV or generic Excel frame (ingest / fixtures)."""
    date_col = next((c for c in df.columns if "date" in str(c).lower()), df.columns[0])
    bull = next((c for c in df.columns if "bull" in str(c).lower()), None)
    bear = next((c for c in df.columns if "bear" in str(c).lower()), None)
    if "spread" in [str(c).lower() for c in df.columns]:
        spread_col = next(c for c in df.columns if str(c).lower() == "spread")
        spread = pd.to_numeric(df[spread_col], errors="coerce")
        if float(spread.dropna().abs().median()) <= 1.5:
            spread = spread * 100.0
    elif bull is not None and bear is not None:
        spread = _normalize_spread_units(df[bull], df[bear])
    else:
        return pd.Series(dtype=float)
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    out = pd.Series(spread.values, index=df[date_col]).dropna().sort_index()
    out.name = "aaii_spread"
    return out.astype(float)


def _load_xls(path: Path) -> tuple[pd.Series, str]:
    if not path.exists() or path.stat().st_size < 512:
        return pd.Series(dtype=float), "aaii_xls_missing"
    try:
        head = path.read_bytes()[:8]
        if head != b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" and head[:2] != b"PK":
            return pd.Series(dtype=float), "aaii_xls_invalid"
        series = _read_aaii_excel(path)
        if series.empty:
            return series, "aaii_xls_invalid"
        return series, "aaii_xls_cache"
    except Exception:
        return pd.Series(dtype=float), "aaii_xls_invalid"


def _download_xls() -> tuple[pd.Series, str]:
    content, tag = _fetch_aaii_bytes(AAII_URL, referer=AAII_RESULTS_URL)
    if not content or not is_excel_content(content):
        return pd.Series(dtype=float), tag
    CACHE_XLS.parent.mkdir(parents=True, exist_ok=True)
    CACHE_XLS.write_bytes(content)
    series = _read_aaii_excel(io.BytesIO(content))
    return series, tag if not series.empty else "aaii_blocked"


def _github_sync_urls() -> list[tuple[str, str]]:
    custom = os.environ.get("AAII_SYNC_RAW_URL")
    if custom:
        return [(custom.strip(), "aaii_github_raw")]
    base = os.environ.get("AAII_GITHUB_RAW_BASE", DEFAULT_GITHUB_RAW_BASE).rstrip("/")
    return [
        (f"{base}/macro_intelligence/data/aaii_sentiment.xls", "aaii_github_xls"),
        (f"{base}/macro_intelligence/data/aaii_sentiment.csv", "aaii_github_csv"),
    ]


def _fetch_github_synced() -> tuple[pd.Series, str]:
    """Pull AAII files committed by .github/workflows/sync_aaii_sentiment.yml."""
    for url, tag in _github_sync_urls():
        try:
            resp = requests.get(url, headers=BROWSER_HEADERS, timeout=45)
        except Exception:
            continue
        if resp.status_code != 200 or len(resp.content) < 64:
            continue
        series = pd.Series(dtype=float)
        if url.endswith(".csv") or "aaii_sentiment.csv" in url:
            try:
                series = _parse_aaii_frame(pd.read_csv(io.BytesIO(resp.content)))
            except Exception:
                continue
        elif is_excel_content(resp.content):
            CACHE_XLS.parent.mkdir(parents=True, exist_ok=True)
            CACHE_XLS.write_bytes(resp.content)
            series = _read_aaii_excel(io.BytesIO(resp.content))
        if not series.empty:
            logger.info("AAII GitHub sync: %s rows from %s", len(series), url)
            return series, tag
    return pd.Series(dtype=float), "aaii_github_miss"


def _aaii_stale_days(series: pd.Series) -> int | None:
    if series.empty or not isinstance(series.index, pd.DatetimeIndex):
        return None
    age = pd.Timestamp.now(tz=None).normalize() - series.index.max().normalize()
    return int(age.days)


def ingest_aaii_csv(path: Path) -> pd.Series:
    series = _parse_aaii_frame(pd.read_csv(path))
    if not series.empty:
        save_cached_series(series, CACHE_CSV, value_col="spread")
    return series


def fetch_aaii_spread() -> pd.Series:
    cached = load_cached_series(CACHE_CSV, value_col="spread")
    source = "aaii_csv_cache" if not cached.empty else "aaii_none"

    live = pd.Series(dtype=float)
    html_series, html_tag = _scrape_sent_results_live()
    live = merge_series(live, html_series)
    if not html_series.empty:
        source = html_tag

    xls_series, xls_tag = _download_xls()
    live = merge_series(live, xls_series)
    if not xls_series.empty and (live.empty or len(xls_series) >= len(live)):
        source = xls_tag

    gh_series, gh_tag = _fetch_github_synced()
    live = merge_series(live, gh_series)
    if not gh_series.empty and (live.empty or len(gh_series) >= len(live)):
        source = gh_tag

    if live.empty or len(live) < 20:
        xls_series, xls_tag = _load_xls(CACHE_XLS)
        live = merge_series(live, xls_series)
        if not xls_series.empty and (live.empty or len(xls_series) >= len(live)):
            source = xls_tag

    merged = merge_series(cached, live)
    if merged.empty and CACHE_XLS.exists():
        fallback, xls_tag = _load_xls(CACHE_XLS)
        merged = merge_series(cached, fallback)
        if not fallback.empty:
            source = xls_tag

    if not merged.empty:
        save_cached_series(merged, CACHE_CSV, value_col="spread")
        merged.attrs["aaii_source"] = source
        stale = _aaii_stale_days(merged)
        if stale is not None and stale > 8 and source in ("aaii_csv_cache", "aaii_xls_cache", "aaii_github_miss"):
            logger.warning("AAII data may be stale (%s days); enable GitHub Actions sync", stale)
        logger.info(
            "AAII spread: %s rows, source=%s, latest=%.2f",
            len(merged),
            source,
            float(merged.iloc[-1]),
        )
    else:
        merged.attrs["aaii_source"] = source
    return merged
