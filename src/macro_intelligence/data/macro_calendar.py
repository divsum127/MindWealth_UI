"""Scheduled macro event calendar — CPI, FOMC, NFP."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import requests

from src.macro_intelligence.config import load_config
from src.macro_intelligence.db.connection import get_connection

# Reuse Investing.com plumbing from CPI module
from src.macro_intelligence.data.investing_cpi_consensus import (
    _calendar_post_payloads,
    _investing_fallback_enabled,
    _investing_proxies,
    _parse_numeric,
    sync_cpi_releases_to_db,
)

_FOMC_PATTERNS = (
    r"fed interest rate decision",
    r"fomc",
    r"federal funds rate",
)
_NFP_PATTERNS = (
    r"nonfarm payrolls",
    r"non-farm payrolls",
    r"non farm payrolls",
)


@dataclass
class MacroReleaseRow:
    release_type: str
    release_date: str
    consensus: float | None = None
    actual: float | None = None
    previous: float | None = None
    event_name: str = ""
    source: str = "fred"


def _scheduled_cfg() -> dict[str, Any]:
    return load_config().get("scheduled_events", {})


def _fred_release_ids() -> dict[str, int]:
    cfg = _scheduled_cfg()
    defaults = {"CPI": 10, "FOMC": 19, "NFP": 50}
    return {**defaults, **(cfg.get("fred_release_ids") or {})}


def fetch_fred_release_dates(release_type: str, *, limit: int = 500) -> list[str]:
    """Release dates from FRED release calendar API."""
    release_id = _fred_release_ids().get(release_type.upper())
    if release_id is None:
        return []
    key = os.environ.get("FRED_API_KEY")
    if not key:
        return []
    try:
        resp = requests.get(
            "https://api.stlouisfed.org/fred/release/dates",
            params={
                "release_id": release_id,
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


def _is_event_match(name: str, patterns: tuple[str, ...]) -> bool:
    n = name.lower()
    return any(re.search(p, n) for p in patterns)


def _parse_investing_events(html: str, release_type: str, patterns: tuple[str, ...]) -> list[MacroReleaseRow]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    rows: list[MacroReleaseRow] = []
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

        if not event_name or not _is_event_match(event_name, patterns):
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
            MacroReleaseRow(
                release_type=release_type,
                release_date=release_date,
                consensus=_parse_numeric(fore.get_text(strip=True) if fore else ""),
                actual=_parse_numeric(act.get_text(strip=True) if act else ""),
                previous=_parse_numeric(prev.get_text(strip=True) if prev else ""),
                event_name=event_name,
                source="investing.com",
            )
        )
    return rows


def _fetch_investing_macro_events(*, weeks_back: int = 8) -> list[MacroReleaseRow]:
    if not _investing_fallback_enabled():
        return []
    try:
        import requests as req

        session = req.Session()
        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0",
                "Accept": "text/html,application/xhtml+xml",
            }
        )
        proxies = _investing_proxies()
        from src.macro_intelligence.data.investing_cpi_consensus import (
            INVESTING_CALENDAR_URL,
            INVESTING_FILTER_URL,
            _INVESTING_HEADERS,
            _INVESTING_XHR_HEADERS,
            _post_with_backoff,
        )

        warmup = session.get(INVESTING_CALENDAR_URL, headers=_INVESTING_HEADERS, proxies=proxies, timeout=30)
        if warmup.status_code != 200:
            return []
        post_headers = {**_INVESTING_HEADERS, **_INVESTING_XHR_HEADERS}
        all_html = ""
        for payload in _calendar_post_payloads(weeks_back=weeks_back):
            resp = _post_with_backoff(
                session,
                INVESTING_FILTER_URL,
                data=payload,
                headers=post_headers,
                proxies=proxies,
            )
            if resp is None or resp.status_code != 200:
                continue
            try:
                all_html += resp.json().get("data", "")
            except Exception:
                continue
        if not all_html:
            return []
        fomc = _parse_investing_events(all_html, "FOMC", _FOMC_PATTERNS)
        nfp = _parse_investing_events(all_html, "NFP", _NFP_PATTERNS)
        return fomc + nfp
    except Exception:
        return []


def fetch_macro_release_calendar() -> list[MacroReleaseRow]:
    """CPI + FOMC + NFP release rows (dates primary; consensus when available)."""
    rows: list[MacroReleaseRow] = []

    for release_type in ("FOMC", "NFP"):
        for d in fetch_fred_release_dates(release_type):
            rows.append(
                MacroReleaseRow(
                    release_type=release_type,
                    release_date=d,
                    event_name=release_type,
                    source="fred_release_calendar",
                )
            )

    for item in _fetch_investing_macro_events():
        rows.append(item)

    return _dedupe_macro_rows(rows)


def _dedupe_macro_rows(rows: list[MacroReleaseRow]) -> list[MacroReleaseRow]:
    merged: dict[tuple[str, str], MacroReleaseRow] = {}
    priority = {"investing.com": 2, "fred_release_calendar": 1}
    for row in rows:
        key = (row.release_type, row.release_date)
        existing = merged.get(key)
        if existing is None or priority.get(row.source, 0) > priority.get(existing.source, 0):
            merged[key] = row
    return sorted(merged.values(), key=lambda r: (r.release_date, r.release_type))


def ingest_macro_release_date(
    release_type: str,
    release_date: str,
    *,
    source: str = "fred",
    consensus: float | None = None,
    actual: float | None = None,
    event_name: str | None = None,
) -> None:
    surprise = None
    if actual is not None and consensus is not None:
        surprise = actual - consensus
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO pending_releases
            (release_type, release_date, actual, consensus, surprise_pp, source, applied)
            VALUES (?, ?, ?, ?, ?, ?, 0)
            ON CONFLICT(release_type, release_date) DO UPDATE SET
              actual=COALESCE(excluded.actual, pending_releases.actual),
              consensus=COALESCE(excluded.consensus, pending_releases.consensus),
              surprise_pp=COALESCE(excluded.surprise_pp, pending_releases.surprise_pp),
              source=excluded.source
            """,
            (release_type, release_date, actual, consensus, surprise, source),
        )


def sync_macro_releases_to_db() -> int:
    """Sync CPI (existing) plus FOMC/NFP dates into pending_releases."""
    n = 0
    try:
        n += sync_cpi_releases_to_db()
    except Exception:
        pass

    for row in fetch_macro_release_calendar():
        if row.release_type == "CPI":
            continue
        ingest_macro_release_date(
            row.release_type,
            row.release_date,
            source=row.source,
            consensus=row.consensus,
            actual=row.actual,
            event_name=row.event_name,
        )
        n += 1
    return n


def _event_time_et(release_type: str) -> tuple[int, int]:
    cfg = _scheduled_cfg().get("event_times_et", {})
    default = "08:30" if release_type in ("CPI", "NFP") else "14:00"
    raw = str(cfg.get(release_type, default))
    parts = raw.split(":")
    return int(parts[0]), int(parts[1]) if len(parts) > 1 else 0


def event_datetime_et(release_type: str, release_date: str) -> pd.Timestamp:
    hour, minute = _event_time_et(release_type)
    return pd.Timestamp(f"{release_date} {hour:02d}:{minute:02d}")


def hours_since_event(release_type: str, release_date: str, as_of: str) -> float:
    """Hours from scheduled event time to nightly as_of (~18:00 ET)."""
    event_dt = event_datetime_et(release_type, release_date)
    as_of_dt = pd.Timestamp(f"{as_of} 18:00")
    return float((as_of_dt - event_dt).total_seconds() / 3600.0)


def days_to_event(release_type: str, release_date: str, as_of: str) -> int:
    return (pd.Timestamp(release_date) - pd.Timestamp(as_of)).days


def list_scheduled_events(
    as_of: str | None = None,
    *,
    types: list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
) -> list[dict[str, Any]]:
    as_of = as_of or datetime.now().strftime("%Y-%m-%d")
    cfg = _scheduled_cfg()
    event_types = types or list(cfg.get("types", ["CPI", "FOMC", "NFP"]))
    start = start or (pd.Timestamp(as_of) - timedelta(days=14)).strftime("%Y-%m-%d")
    end = end or (pd.Timestamp(as_of) + timedelta(days=cfg.get("pre_event_window_days", 7))).strftime("%Y-%m-%d")

    placeholders = ",".join("?" for _ in event_types)
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT release_type, release_date, consensus, actual, source
            FROM pending_releases
            WHERE release_type IN ({placeholders})
              AND release_date >= ? AND release_date <= ?
            ORDER BY release_date ASC
            """,
            (*event_types, start, end),
        ).fetchall()
    return [dict(r) for r in rows]


def get_upcoming_event(as_of: str | None = None) -> dict[str, Any] | None:
    """Next scheduled event within pre_event_window_days (inclusive of today)."""
    as_of = as_of or datetime.now().strftime("%Y-%m-%d")
    cfg = _scheduled_cfg()
    window = int(cfg.get("pre_event_window_days", 7))
    end = (pd.Timestamp(as_of) + timedelta(days=window)).strftime("%Y-%m-%d")
    events = list_scheduled_events(as_of, start=as_of, end=end)
    future = [e for e in events if e["release_date"] >= as_of]
    if not future:
        return None
    row = future[0]
    return {
        "type": row["release_type"],
        "date": row["release_date"],
        "days_to_event": days_to_event(row["release_type"], row["release_date"], as_of),
        "source": row.get("source"),
    }


def get_recent_event_in_window(as_of: str | None = None) -> dict[str, Any] | None:
    """Most recent event within post_event_window_hours before as_of."""
    as_of = as_of or datetime.now().strftime("%Y-%m-%d")
    cfg = _scheduled_cfg()
    window_h = float(cfg.get("post_event_window_hours", 48))
    lookback = max(7, int(window_h / 24) + 2)
    start = (pd.Timestamp(as_of) - timedelta(days=lookback)).strftime("%Y-%m-%d")
    events = list_scheduled_events(as_of, start=start, end=as_of)
    past = [e for e in events if e["release_date"] <= as_of]
    if not past:
        return None
    for row in reversed(past):
        hrs = hours_since_event(row["release_type"], row["release_date"], as_of)
        if 0 <= hrs <= window_h:
            return {
                "type": row["release_type"],
                "date": row["release_date"],
                "hours_since_event": round(hrs, 1),
                "source": row.get("source"),
            }
    return None


__all__ = [
    "MacroReleaseRow",
    "fetch_macro_release_calendar",
    "fetch_fred_release_dates",
    "sync_macro_releases_to_db",
    "get_upcoming_event",
    "get_recent_event_in_window",
    "hours_since_event",
    "ingest_macro_release_date",
    "list_scheduled_events",
]
