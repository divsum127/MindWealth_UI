"""CPI MoM consensus/actual from economic calendars (Trading Economics primary, Investing.com optional)."""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

import pandas as pd
import requests
from bs4 import BeautifulSoup

from src.config_paths import MACRO_INTEL_DATA_DIR
from src.sentiment_superindex.data.scraper_utils import BROWSER_HEADERS

INVESTING_CALENDAR_URL = "https://www.investing.com/economic-calendar/"
INVESTING_FILTER_URL = "https://www.investing.com/economic-calendar/Service/getCalendarFilteredData"
TRADINGECONOMICS_CPI_URL = "https://tradingeconomics.com/united-states/inflation-rate-mom"
TRADINGECONOMICS_CORE_CPI_URL = "https://tradingeconomics.com/united-states/core-inflation-rate-mom"
FRED_CPI_RELEASE_ID = 10
CONSENSUS_CSV = MACRO_INTEL_DATA_DIR / "cpi_consensus.csv"
INVESTING_IMPERSONATE = "chrome120"
_INVESTING_CACHE_TTL_SEC = 120.0
_investing_cache: tuple[float, list[CpiReleaseRow]] | None = None

_INVESTING_HEADERS: dict[str, str] = {
    **BROWSER_HEADERS,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
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

_INVESTING_XHR_HEADERS: dict[str, str] = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": INVESTING_CALENDAR_URL,
    "Origin": "https://www.investing.com",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

_TE_HEADERS: dict[str, str] = {
    **BROWSER_HEADERS,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://tradingeconomics.com/united-states/indicators",
}

# US CPI MoM event names on Investing.com
_CPI_PATTERNS = (
    r"cpi\s*\(?\s*mom",
    r"consumer price index\s*\(?\s*mom",
    r"core cpi\s*\(?\s*mom",
)


class _HttpSession(Protocol):
    def get(self, url: str, **kwargs: Any) -> Any: ...

    def post(self, url: str, **kwargs: Any) -> Any: ...


@dataclass
class CpiReleaseRow:
    release_date: str
    consensus: float | None
    actual: float | None
    previous: float | None
    event_name: str
    source: str = "tradingeconomics.com"


def _investing_fallback_enabled() -> bool:
    """Investing.com is only attempted when an explicit egress proxy is configured."""
    return bool(os.environ.get("INVESTING_HTTP_PROXY"))


def _investing_proxies() -> dict[str, str] | None:
    """Optional egress proxy for Investing.com (Cloudflare blocks datacenter IPs on AWS)."""
    proxy = os.environ.get("INVESTING_HTTP_PROXY")
    if not proxy:
        return None
    return {"http": proxy, "https": proxy}


def _calendar_post_payloads(*, weeks_back: int) -> list[dict[str, Any]]:
    """Investing.com filter POST bodies: this/next week plus custom historical window."""
    base = {
        "country[]": 5,
        "timeZone": 55,
        "timeFilter": "timeRemain",
        "limit_from": 0,
    }
    payloads: list[dict[str, Any]] = [
        {**base, "currentTab": "thisWeek"},
        {**base, "currentTab": "nextWeek"},
    ]
    end = datetime.now()
    start = end - timedelta(weeks=max(weeks_back, 1))
    payloads.append(
        {
            **base,
            "currentTab": "custom",
            "dateFrom": start.strftime("%Y-%m-%d"),
            "dateTo": end.strftime("%Y-%m-%d"),
        }
    )
    return payloads


def _post_with_backoff(
    session: _HttpSession,
    url: str,
    *,
    data: dict[str, Any],
    headers: dict[str, str],
    proxies: dict[str, str] | None = None,
    max_attempts: int = 3,
    timeout: int = 30,
    extra_post_kwargs: dict[str, Any] | None = None,
) -> Any | None:
    """POST with exponential backoff on Cloudflare 429/403."""
    delay = 2.0
    post_kwargs = extra_post_kwargs or {}
    for _attempt in range(max_attempts):
        try:
            resp = session.post(
                url,
                data=data,
                headers=headers,
                timeout=timeout,
                proxies=proxies,
                **post_kwargs,
            )
        except Exception:
            resp = None
        if resp is not None and resp.status_code == 200:
            return resp
        if resp is not None and resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            wait = float(retry_after) if retry_after and str(retry_after).isdigit() else delay
            time.sleep(min(wait, 30.0))
            delay = min(delay * 2, 30.0)
            continue
        if resp is not None and resp.status_code in (403, 503):
            time.sleep(delay)
            delay = min(delay * 2, 30.0)
            continue
        return resp
    return None


def _dedupe_cpi_rows(rows: list[CpiReleaseRow]) -> list[CpiReleaseRow]:
    seen: set[tuple[str, str]] = set()
    out: list[CpiReleaseRow] = []
    for row in sorted(rows, key=lambda r: r.release_date):
        key = (row.release_date, row.event_name.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _fetch_investing_via_session(
    session: _HttpSession,
    *,
    weeks_back: int,
    proxies: dict[str, str] | None,
    extra_post_kwargs: dict[str, Any] | None = None,
) -> list[CpiReleaseRow]:
    """Shared Investing.com calendar fetch for any requests-compatible session."""
    try:
        warmup = session.get(
            INVESTING_CALENDAR_URL,
            headers=_INVESTING_HEADERS,
            timeout=30,
            proxies=proxies,
        )
        if warmup.status_code == 429:
            time.sleep(2.0)
            warmup = session.get(
                INVESTING_CALENDAR_URL,
                headers=_INVESTING_HEADERS,
                timeout=30,
                proxies=proxies,
            )
        if warmup.status_code != 200:
            return []
    except Exception:
        return []

    post_headers = {**_INVESTING_HEADERS, **_INVESTING_XHR_HEADERS}
    all_rows: list[CpiReleaseRow] = []
    for payload in _calendar_post_payloads(weeks_back=weeks_back):
        resp = _post_with_backoff(
            session,
            INVESTING_FILTER_URL,
            data=payload,
            headers=post_headers,
            proxies=proxies,
            extra_post_kwargs=extra_post_kwargs,
        )
        if resp is None or resp.status_code != 200:
            continue
        try:
            body = resp.json()
            all_rows.extend(_parse_calendar_html(body.get("data", "")))
        except Exception:
            continue
        time.sleep(0.35)
    return _dedupe_cpi_rows(all_rows)


def _fetch_investing_curl_cffi(*, weeks_back: int) -> list[CpiReleaseRow]:
    try:
        from curl_cffi import requests as creq
    except ImportError:
        return []

    proxies = _investing_proxies()
    session = creq.Session(impersonate=INVESTING_IMPERSONATE)
    return _fetch_investing_via_session(session, weeks_back=weeks_back, proxies=proxies)


def _fetch_investing_cloudscraper(*, weeks_back: int) -> list[CpiReleaseRow]:
    try:
        import cloudscraper
    except ImportError:
        return []

    proxies = _investing_proxies()
    session = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False},
    )
    session.headers.update(_INVESTING_HEADERS)
    if proxies:
        session.proxies.update(proxies)
    return _fetch_investing_via_session(session, weeks_back=weeks_back, proxies=proxies)


def _fetch_investing_requests(*, weeks_back: int) -> list[CpiReleaseRow]:
    session = requests.Session()
    session.headers.update(_INVESTING_HEADERS)
    return _fetch_investing_via_session(
        session,
        weeks_back=weeks_back,
        proxies=_investing_proxies(),
    )


def _parse_numeric(cell: str) -> float | None:
    if not cell or cell.strip() in ("", "-", "&nbsp;"):
        return None
    s = cell.strip().replace("%", "").replace(",", "")
    if s.endswith("K"):
        s = s[:-1]
    try:
        return float(s)
    except ValueError:
        return None


def _is_cpi_mom_event(name: str) -> bool:
    n = name.lower()
    if "yoy" in n or "y/y" in n:
        return False
    return any(re.search(p, n) for p in _CPI_PATTERNS)


def _parse_calendar_html(html: str) -> list[CpiReleaseRow]:
    soup = BeautifulSoup(html, "lxml")
    rows: list[CpiReleaseRow] = []
    current_date: str | None = None

    for tr in soup.find_all("tr"):
        if tr.find("td", class_="theDay"):
            day_text = tr.get_text(" ", strip=True)
            try:
                current_date = pd.to_datetime(day_text, errors="coerce").strftime("%Y-%m-%d")
            except Exception:
                current_date = None
            continue

        event_td = tr.find("td", class_=lambda c: c and "event" in str(c))
        if event_td is None:
            tds = tr.find_all("td")
            if len(tds) < 4:
                continue
            event_name = tds[2].get_text(" ", strip=True) if len(tds) > 2 else ""
        else:
            event_name = event_td.get_text(" ", strip=True)

        if not event_name or not _is_cpi_mom_event(event_name):
            continue

        act = tr.find("td", class_=lambda c: c and "act" in str(c))
        fore = tr.find("td", class_=lambda c: c and "fore" in str(c))
        prev = tr.find("td", class_=lambda c: c and "prev" in str(c))
        time_td = tr.find("td", class_=lambda c: c and "first" in str(c))

        dt_attr = tr.get("data-event-datetime") or (time_td.get("data-event-datetime") if time_td else None)
        if dt_attr:
            release_date = pd.to_datetime(dt_attr, errors="coerce").strftime("%Y-%m-%d")
        elif current_date:
            release_date = current_date
        else:
            continue

        rows.append(
            CpiReleaseRow(
                release_date=release_date,
                consensus=_parse_numeric(fore.get_text(strip=True) if fore else ""),
                actual=_parse_numeric(act.get_text(strip=True) if act else ""),
                previous=_parse_numeric(prev.get_text(strip=True) if prev else ""),
                event_name=event_name,
            )
        )
    return rows


def _te_consensus_from_cells(
    tds: list[str],
    *,
    actual: float | None,
    prior_release_actual: float | None,
) -> float | None:
    """Resolve pre-release consensus; TE may set Consensus=Actual after print."""
    consensus = _parse_numeric(tds[6]) if len(tds) > 6 else None
    previous = _parse_numeric(tds[5]) if len(tds) > 5 else None
    te_forecast = _parse_numeric(tds[7]) if len(tds) > 7 else None
    if actual is not None and consensus is not None and abs(consensus - actual) < 1e-9:
        if previous is not None and abs(previous - actual) > 1e-9:
            if prior_release_actual is not None and abs(previous - prior_release_actual) > 1e-9:
                consensus = previous
            elif prior_release_actual is None and previous < actual:
                consensus = previous
        elif te_forecast is not None and previous is None:
            consensus = te_forecast
    if consensus is None:
        consensus = te_forecast if te_forecast is not None else previous
    return consensus


def _te_event_matches_series(event_name: str, *, series: str) -> bool:
    name = event_name.lower()
    if "inflation rate mom" not in name:
        return False
    is_core = "core" in name
    if series == "core":
        return is_core
    return not is_core


def _parse_tradingeconomics_html(html: str, *, series: str = "headline") -> list[CpiReleaseRow]:
    """Parse Trading Economics CPI MoM calendar tables (headline or core series page)."""
    soup = BeautifulSoup(html, "lxml")
    parsed: list[tuple[str, list[str], str, float | None, float | None]] = []
    for table in soup.find_all("table"):
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        if not any("Consensus" in h for h in headers):
            continue
        for tr in table.find_all("tr"):
            tds = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
            if len(tds) < 7:
                continue
            event_name = tds[2] if len(tds) > 2 else ""
            if not _te_event_matches_series(event_name, series=series):
                continue
            release_date = pd.to_datetime(tds[0], errors="coerce")
            if pd.isna(release_date):
                continue
            parsed.append(
                (
                    release_date.strftime("%Y-%m-%d"),
                    tds,
                    event_name,
                    _parse_numeric(tds[4]) if len(tds) > 4 else None,
                    _parse_numeric(tds[5]) if len(tds) > 5 else None,
                )
            )
    if not parsed:
        return []
    parsed.sort(key=lambda x: x[0])
    rows: list[CpiReleaseRow] = []
    prior_actual: float | None = None
    for release_date, tds, event_name, actual, previous in parsed:
        consensus = _te_consensus_from_cells(
            tds, actual=actual, prior_release_actual=prior_actual
        )
        rows.append(
            CpiReleaseRow(
                release_date=release_date,
                consensus=consensus,
                actual=actual,
                previous=previous,
                event_name=event_name,
                source="tradingeconomics.com",
            )
        )
        if actual is not None:
            prior_actual = actual
    return rows


def _fetch_tradingeconomics_page(url: str, *, series: str) -> list[CpiReleaseRow]:
    try:
        resp = requests.get(url, headers=_TE_HEADERS, timeout=30)
        if resp.status_code != 200:
            return []
        return _parse_tradingeconomics_html(resp.text, series=series)
    except Exception:
        return []


def fetch_tradingeconomics_cpi_calendar() -> list[CpiReleaseRow]:
    """Fetch US headline + Core CPI MoM from Trading Economics (primary automated source)."""
    headline = _fetch_tradingeconomics_page(TRADINGECONOMICS_CPI_URL, series="headline")
    core = _fetch_tradingeconomics_page(TRADINGECONOMICS_CORE_CPI_URL, series="core")
    return _dedupe_cpi_rows(headline + core)


def fetch_fred_cpi_release_dates(*, limit: int = 1000) -> list[str]:
    """Upcoming/past CPI release dates from FRED release calendar (release_id=10)."""
    key = os.environ.get("FRED_API_KEY")
    if not key:
        return []
    try:
        resp = requests.get(
            "https://api.stlouisfed.org/fred/release/dates",
            params={
                "release_id": FRED_CPI_RELEASE_ID,
                "api_key": key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": limit,
                "include_release_dates_with_no_data": "true",
            },
            timeout=30,
        )
        if resp.status_code != 200:
            return []
        dates = [
            str(item["date"])[:10]
            for item in resp.json().get("release_dates", [])
            if item.get("date")
        ]
        return sorted(set(dates))
    except Exception:
        return []


def _merge_cpi_rows(primary: list[CpiReleaseRow], secondary: list[CpiReleaseRow]) -> list[CpiReleaseRow]:
    """Merge rows; primary wins on (release_date, normalized event_name)."""
    merged: dict[tuple[str, str], CpiReleaseRow] = {}
    for row in secondary:
        merged[(row.release_date, row.event_name.lower())] = row
    for row in primary:
        merged[(row.release_date, row.event_name.lower())] = row
    return sorted(merged.values(), key=lambda r: r.release_date)


def _is_headline_cpi_row(row: CpiReleaseRow) -> bool:
    name = row.event_name.lower()
    if "core" in name:
        return False
    if "inflation rate mom" in name:
        return True
    return any(re.search(p, name) for p in _CPI_PATTERNS)


def _enrich_with_fred_release_dates(rows: list[CpiReleaseRow]) -> list[CpiReleaseRow]:
    """Add FRED-scheduled CPI dates when TE/Investing have no row yet."""
    known_dates = {r.release_date for r in rows if "core" not in r.event_name.lower()}
    out = list(rows)
    for release_date in fetch_fred_cpi_release_dates():
        if release_date in known_dates:
            continue
        out.append(
            CpiReleaseRow(
                release_date=release_date,
                consensus=None,
                actual=None,
                previous=None,
                event_name="Inflation Rate MoM",
                source="fred_release_calendar",
            )
        )
        known_dates.add(release_date)
    return sorted(out, key=lambda r: r.release_date)


def fetch_cpi_consensus_calendar(*, weeks_back: int = 8) -> list[CpiReleaseRow]:
    """Live CPI rows: Trading Economics primary; Investing.com when INVESTING_HTTP_PROXY set."""
    rows = fetch_tradingeconomics_cpi_calendar()
    if _investing_fallback_enabled():
        investing = fetch_investing_cpi_calendar(weeks_back=weeks_back)
        rows = _merge_cpi_rows(rows, investing)
    return _enrich_with_fred_release_dates(rows)


def fetch_investing_cpi_calendar(*, weeks_back: int = 8) -> list[CpiReleaseRow]:
    """POST Investing.com filtered calendar (US). Requires INVESTING_HTTP_PROXY on AWS."""
    if not _investing_fallback_enabled():
        return []
    global _investing_cache
    now = time.time()
    if _investing_cache is not None and now - _investing_cache[0] < _INVESTING_CACHE_TTL_SEC:
        return list(_investing_cache[1])

    for fetcher in (_fetch_investing_curl_cffi, _fetch_investing_cloudscraper, _fetch_investing_requests):
        rows = fetcher(weeks_back=weeks_back)
        if rows:
            _investing_cache = (now, rows)
            return rows
    return []


def load_consensus_csv(path: Path | None = None) -> pd.DataFrame:
    p = path or Path(os.environ.get("CPI_CONSENSUS_CSV", str(CONSENSUS_CSV)))
    if not p.exists():
        return pd.DataFrame(columns=["release_date", "consensus", "actual", "event_name", "source"])
    return pd.read_csv(p)


def save_consensus_csv(df: pd.DataFrame, path: Path | None = None) -> None:
    p = path or CONSENSUS_CSV
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(p, index=False)


def latest_cpi_consensus_row() -> CpiReleaseRow | None:
    """Best available headline CPI MoM consensus: live TE/Investing first, CSV emergency cache last."""
    live = fetch_cpi_consensus_calendar()
    with_consensus = [r for r in live if r.consensus is not None and _is_headline_cpi_row(r)]
    if with_consensus:
        with_consensus.sort(key=lambda r: r.release_date, reverse=True)
        return with_consensus[0]

    df = load_consensus_csv()
    if df.empty or "consensus" not in df.columns:
        return None
    row = df.sort_values("release_date").iloc[-1]
    return CpiReleaseRow(
        release_date=str(row["release_date"])[:10],
        consensus=float(row["consensus"]) if pd.notna(row.get("consensus")) else None,
        actual=float(row["actual"]) if "actual" in row and pd.notna(row.get("actual")) else None,
        previous=None,
        event_name=str(row.get("event_name", "CPI MoM")),
        source=str(row.get("source", "csv")),
    )


def fetch_cpi_calendar_for_backfill(*, weeks_back: int = 520, headline_only: bool = True) -> list[CpiReleaseRow]:
    """TE headline calendar + optional Investing.com history when INVESTING_HTTP_PROXY is set."""
    rows = fetch_tradingeconomics_cpi_calendar()
    if not headline_only:
        rows = _dedupe_cpi_rows(rows)
    else:
        rows = [r for r in rows if _is_headline_cpi_row(r)]
    if _investing_fallback_enabled():
        inv = fetch_investing_cpi_calendar(weeks_back=weeks_back)
        inv = [r for r in inv if _is_headline_cpi_row(r)]
        rows = _merge_cpi_rows(rows, inv)
    return rows


def build_cpi_backfill_rows(
    *,
    weeks_back: int = 520,
    start_year: int = 1990,
    enrich_bls_actual: bool = True,
) -> list[CpiReleaseRow]:
    """Merge TE/Investing consensus with BLS actual MoM on FRED CPI release dates."""
    from src.macro_intelligence.data.bls_pull import (
        bls_mom_for_reference_month,
        fetch_bls_cpi_mom_history,
        reference_month_for_release,
    )

    calendar = fetch_cpi_calendar_for_backfill(weeks_back=weeks_back)
    df = load_consensus_csv()
    if not df.empty:
        for _, r in df.iterrows():
            calendar.append(
                CpiReleaseRow(
                    release_date=str(r["release_date"])[:10],
                    consensus=float(r["consensus"]) if pd.notna(r.get("consensus")) else None,
                    actual=float(r["actual"]) if pd.notna(r.get("actual")) else None,
                    previous=None,
                    event_name=str(r.get("event_name", "CPI MoM")),
                    source=str(r.get("source", "csv")),
                )
            )
    calendar = _merge_cpi_rows(
        [r for r in calendar if r.source == "tradingeconomics.com"],
        [r for r in calendar if r.source != "tradingeconomics.com"],
    )
    by_date: dict[str, CpiReleaseRow] = {
        r.release_date: r for r in calendar if _is_headline_cpi_row(r)
    }
    mom_df = fetch_bls_cpi_mom_history(start_year=start_year) if enrich_bls_actual else pd.DataFrame()
    release_dates = fetch_fred_cpi_release_dates()
    out: list[CpiReleaseRow] = []
    for release_date in release_dates:
        ref_month = reference_month_for_release(release_date)
        cal = by_date.get(release_date)
        consensus = cal.consensus if cal else None
        actual = cal.actual if cal else None
        bls_actual: float | None = None
        if enrich_bls_actual and not mom_df.empty:
            bls_actual = bls_mom_for_reference_month(mom_df, ref_month)
            if bls_actual is not None:
                actual = bls_actual
        if consensus is None and actual is None:
            continue
        if consensus is None or actual is None:
            continue
        if cal and bls_actual is not None:
            source = f"{cal.source}+bls"
        elif cal:
            source = cal.source
        else:
            source = "bls+fred_release"
        out.append(
            CpiReleaseRow(
                release_date=release_date,
                consensus=float(consensus),
                actual=float(actual),
                previous=cal.previous if cal else None,
                event_name=cal.event_name if cal else "Inflation Rate MoM",
                source=source,
            )
        )
    for release_date, cal in sorted(by_date.items()):
        if release_date in {r.release_date for r in out}:
            continue
        if cal.consensus is None or cal.actual is None:
            continue
        out.append(cal)
    return sorted(out, key=lambda r: r.release_date)


def upsert_cpi_releases(rows: list[CpiReleaseRow]) -> dict[str, int]:
    """Upsert headline CPI rows into pending_releases; returns insert/update/skip counts."""
    from src.macro_intelligence.data.bls_pull import ingest_cpi_release

    inserted = updated = skipped = 0
    seen: set[str] = set()
    for item in sorted(rows, key=lambda x: x.release_date):
        if not _is_headline_cpi_row(item):
            continue
        if item.release_date in seen:
            continue
        if item.consensus is None or item.actual is None:
            skipped += 1
            continue
        seen.add(item.release_date)
        ingest_cpi_release(
            item.release_date,
            float(item.actual),
            float(item.consensus),
            source=item.source,
        )
        inserted += 1
    return {"upserted": inserted, "skipped": skipped, "updated": updated}


def sync_cpi_releases_to_db() -> int:
    """Persist live calendar rows into pending_releases; merge CSV only as emergency cache."""
    from src.macro_intelligence.data.bls_pull import ingest_cpi_release

    rows = fetch_cpi_consensus_calendar()
    df = load_consensus_csv()
    if df.empty:
        csv_rows: list[CpiReleaseRow] = []
    else:
        csv_rows = [
            CpiReleaseRow(
                release_date=str(r["release_date"])[:10],
                consensus=float(r["consensus"]) if pd.notna(r.get("consensus")) else None,
                actual=float(r["actual"]) if pd.notna(r.get("actual")) else None,
                previous=None,
                event_name=str(r.get("event_name", "CPI MoM")),
                source="csv",
            )
            for _, r in df.iterrows()
            if pd.notna(r.get("consensus")) or pd.notna(r.get("actual"))
        ]
    live_rows = [r for r in rows if r.source != "fred_release_calendar"]
    rows = _merge_cpi_rows(live_rows, csv_rows)

    n = 0
    seen: set[str] = set()
    for item in sorted(rows, key=lambda x: x.release_date):
        if item.release_date in seen:
            continue
        if item.consensus is None and item.actual is None:
            continue
        seen.add(item.release_date)
        actual = item.actual if item.actual is not None else item.consensus
        consensus = item.consensus if item.consensus is not None else actual
        if actual is None or consensus is None:
            continue
        ingest_cpi_release(item.release_date, float(actual), float(consensus), source=item.source)
        n += 1
    return n
