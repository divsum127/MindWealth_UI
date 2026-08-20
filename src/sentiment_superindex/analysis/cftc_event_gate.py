"""Event-coincidence gating for CFTC positioning episodes.

Rohit 13 Aug, point 3: if a CFTC pattern is only a stress marker, keep it at the equivalent of
VERY RARE unless it earns more -- and the way to test whether it earns more is to look at the
episodes that coincide with scheduled economic events, the same market-events logic the macro
agent already uses to cut its combo grid down.

The event set is the one the macro agent runs on: CPI, FOMC and NFP release dates
(``src/macro_intelligence/data/macro_calendar.py``). Dates come from the ``pending_releases``
table first and are topped up from FRED's release-dates API, because the table only carries CPI
from 2024 while the CFTC sample starts 2006-06-13.

Coverage caveat, stated rather than hidden: CPI and NFP come from FRED and cover the whole CFTC
sample. FOMC does not -- FRED has no meeting-date calendar (release 19 was a weekly reserves
report, release 101 returns publication timestamps), so FOMC dates exist only from 2011 via the
investing.com scraper. The gate rests on CPI and NFP for the pre-2011 years, and ``event_counts``
in the result reports what each type actually contributed.

Window convention: an episode is event-coincident when a release falls on it or within the
preceding ``window_days`` calendar days -- the episode follows the event, not the other way
round. The primary window is 3 days; 1 and 7 are reported beside it so the choice is visible
rather than buried in a constant.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Iterable, Sequence

import pandas as pd

from src.macro_intelligence.data.macro_calendar import (
    fetch_fred_release_dates,
    list_scheduled_events,
)
from src.sentiment_superindex.analysis.cftc_episode_metrics import (
    analyze_cell,
    collapse_episodes,
)

logger = logging.getLogger("ssi.cftc_event_gate")

EVENT_TYPES = ("CPI", "FOMC", "NFP")
PRIMARY_WINDOW_DAYS = 3
SENSITIVITY_WINDOWS = (1, 3, 7)
MIN_EPISODES = 3  # Rohit's floor: fewer than 3 episodes is not a result

CACHE_PATH = (
    Path(__file__).resolve().parents[3]
    / "macro_intelligence"
    / "data_cache"
    / "macro_event_dates.json"
)


def load_event_dates(
    start: str,
    end: str,
    *,
    types: Sequence[str] = EVENT_TYPES,
    refresh: bool = False,
) -> dict[str, list[str]]:
    """Release dates per event type over [start, end], DB first then FRED, cached on disk."""
    cached: dict[str, list[str]] = {}
    if CACHE_PATH.is_file() and not refresh:
        try:
            cached = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            cached = {}

    out: dict[str, list[str]] = {}
    for event_type in types:
        dates: set[str] = set(cached.get(event_type, []))
        if not dates or refresh:
            for row in list_scheduled_events(end, types=[event_type], start=start, end=end):
                if row.get("release_date"):
                    dates.add(str(row["release_date"])[:10])
            # The table is thin for older history (CPI only from 2024), so top up from FRED.
            dates.update(fetch_fred_release_dates(event_type))
        out[event_type] = sorted(d for d in dates if start <= d <= end)

    merged = {**cached, **{k: sorted(set(cached.get(k, [])) | set(v)) for k, v in out.items()}}
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(merged, indent=1), encoding="utf-8")
    except OSError as exc:  # cache is an optimisation, never a hard dependency
        logger.warning("could not write event-date cache: %s", exc)
    return out


def _event_index(events: dict[str, list[str]]) -> pd.DatetimeIndex:
    flat = {d for dates in events.values() for d in dates}
    return pd.DatetimeIndex(sorted(pd.Timestamp(d) for d in flat))


def days_since_nearest_event(
    dates: Iterable[pd.Timestamp], events: dict[str, list[str]]
) -> dict[pd.Timestamp, int | None]:
    """Calendar days from the most recent release on or before each date (None if none)."""
    idx = _event_index(events)
    out: dict[pd.Timestamp, int | None] = {}
    for dt in dates:
        ts = pd.Timestamp(dt).normalize()
        prior = idx[idx <= ts]
        out[ts] = int((ts - prior[-1]).days) if len(prior) else None
    return out


def event_coincident_dates(
    dates: Iterable[pd.Timestamp],
    events: dict[str, list[str]],
    *,
    window_days: int = PRIMARY_WINDOW_DAYS,
) -> pd.DatetimeIndex:
    lags = days_since_nearest_event(dates, events)
    kept = [dt for dt, lag in lags.items() if lag is not None and lag <= window_days]
    return pd.DatetimeIndex(sorted(kept))


def gate_cell(
    ctx: dict[str, Any],
    week_dates: pd.DatetimeIndex,
    events: dict[str, list[str]],
    *,
    window_days: int = PRIMARY_WINDOW_DAYS,
) -> dict[str, Any]:
    """One cell's metrics restricted to event-coincident weeks, with the episode floor applied."""
    gated = event_coincident_dates(week_dates, events, window_days=window_days)
    episodes = collapse_episodes(gated) if len(gated) else []
    result: dict[str, Any] = {
        "window_days": window_days,
        "n_weeks_all": len(week_dates),
        "n_weeks_event": len(gated),
        "n_episodes_event": len(episodes),
        "meets_episode_floor": len(episodes) >= MIN_EPISODES,
    }
    if not len(gated):
        result["metrics"] = None
        return result
    cell = analyze_cell(gated, ctx["spx"], benchmark=ctx["benchmark"], long_side=True)
    result["metrics"] = cell["metrics"]
    result["episodes"] = cell["episodes"]
    return result


def run_event_gated_grid(
    ctx: dict[str, Any],
    cells: Sequence[dict[str, Any]],
    *,
    windows: Sequence[int] = SENSITIVITY_WINDOWS,
    refresh_events: bool = False,
) -> dict[str, Any]:
    """Re-rank named cells on event-coincident episodes at each sensitivity window.

    ``cells`` are ``{"condition": str, "dates": DatetimeIndex}`` pairs, so the caller keeps
    ownership of what a cell means (the grid module already builds those masks).
    """
    idx = ctx["weekly_index"]
    events = load_event_dates(
        str(idx.min().date()), str(idx.max().date()), refresh=refresh_events
    )
    counts = {k: len(v) for k, v in events.items()}
    rows: list[dict[str, Any]] = []
    for cell in cells:
        entry: dict[str, Any] = {"condition": cell["condition"], "windows": []}
        for window in windows:
            entry["windows"].append(
                gate_cell(ctx, cell["dates"], events, window_days=window)
            )
        rows.append(entry)
    return {
        "test_id": "cftc_event_gated_cells",
        "spec": "rohit_2026-08-13_point_3",
        "event_types": list(EVENT_TYPES),
        "event_counts": counts,
        "min_episodes": MIN_EPISODES,
        "primary_window_days": PRIMARY_WINDOW_DAYS,
        "sample": {"start": str(idx.min().date()), "end": str(idx.max().date())},
        "rows": rows,
    }
