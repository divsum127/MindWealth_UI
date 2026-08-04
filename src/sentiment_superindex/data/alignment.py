"""Time-series alignment helpers for SSI and macro pipelines.

Forward-fill limit units (pandas contract)
----------------------------------------
``reindex(..., method="ffill", limit=N)`` counts **rows of the target ref_index**,
not abstract "days". The effective horizon depends entirely on which index you pass:

- ``limit=5`` on ``freq="B"`` (business days)  → 5 business days (~7 calendar days)
- ``limit=5`` on ``freq="D"`` (calendar days) → 5 calendar days (~3.5 business days)
- ``limit=5`` on a sparse trading-day union    → 5 trading-day observations (irregular)

House convention (Aug 2026 audit)
---------------------------------
- Weekly survey / CFTC inputs: ``forward_fill_weekly()`` → **business-day** index
- Daily dashboard / regime joins: ``align_to_daily()`` → **calendar-day** index
- Limit parameter names must include the unit (``*_calendar_days``, ``*_business_days``)
- Cadence-specific caps come from ``SSI_CONFIG.yaml`` via ``max_stale_days_for_cadence()``
"""

from __future__ import annotations

import pandas as pd

from src.sentiment_superindex.config import staleness_policy

_UNSET: object = object()

# Back-compat defaults (weekly cadence). Prefer cadence-aware helpers below.
MAX_FFORWARD_FILL_CALENDAR_DAYS = 5
MAX_FFORWARD_FILL_BUSINESS_DAYS = 5


def max_stale_days_for_cadence(cadence: str) -> int:
    """Calendar-day carry cap for a publication cadence (weekly/daily/monthly)."""
    max_stale, _ = staleness_policy()
    return int(max_stale.get(cadence, max_stale["weekly"]))


def calendar_day_index(
    start: pd.Timestamp | str,
    end: pd.Timestamp | str,
) -> pd.DatetimeIndex:
    """Dense calendar-day index (``freq="D"``), including weekends."""
    return pd.date_range(pd.Timestamp(start), pd.Timestamp(end), freq="D")


def business_day_index(
    start: pd.Timestamp | str,
    end: pd.Timestamp | str,
) -> pd.DatetimeIndex:
    """Dense business-day index (``freq="B"``), Mon–Fri excluding US holidays pandas knows."""
    return pd.date_range(pd.Timestamp(start), pd.Timestamp(end), freq="B")


def forward_fill_weekly(
    series: pd.Series,
    ref_index: pd.DatetimeIndex | None = None,
    *,
    start: pd.Timestamp | str | None = None,
    end: pd.Timestamp | str | None = None,
    max_ffill_business_days: int | None | object = _UNSET,
    cadence: str = "weekly",
) -> pd.Series:
    """Forward-fill a weekly (or sparser) series onto a **business-day** index.

    Parameters
    ----------
    series:
        Input series (typically weekly AAII / NAAIM / CFTC prints).
    ref_index:
        Target index. When omitted, built with ``freq="B"`` from ``start``/``end``
        (or from the series span if both are None).
    start, end:
        Bounds for the auto-built business-day index when ``ref_index`` is None.
    max_ffill_business_days:
        Forward-fill limit in **business-day rows** of ``ref_index``.
        ``None`` = unlimited carry-forward (use only when staleness is surfaced elsewhere).
        When omitted (default), uses ``max_stale_days_for_cadence(cadence)`` from SSI config.
        Pass ``None`` explicitly for unlimited carry-forward.
    cadence:
        Publication cadence key (``weekly``, ``daily``, ``monthly``) for default limit lookup.

    Returns
    -------
    Series reindexed onto ``ref_index`` (business days).
    """
    if max_ffill_business_days is _UNSET:
        max_ffill_business_days = max_stale_days_for_cadence(cadence)
    if series.empty:
        return series.copy()
    s = series.sort_index()
    idx = ref_index
    if idx is None:
        lo = pd.Timestamp(start) if start is not None else s.index.min()
        hi = pd.Timestamp(end) if end is not None else s.index.max()
        idx = business_day_index(lo, hi)
    return s.reindex(idx, method="ffill", limit=max_ffill_business_days)


def align_to_daily(
    series: pd.Series,
    ref_index: pd.DatetimeIndex,
    *,
    max_ffill_calendar_days: int | None | object = _UNSET,
    cadence: str = "weekly",
) -> pd.Series:
    """Reindex onto a **calendar-day** ``ref_index`` with optional forward-fill cap.

    Parameters
    ----------
    series:
        Input series (any cadence).
    ref_index:
        Target index — must be calendar-day (``freq="D"``) or equivalent dense daily
        calendar. ``limit`` counts **calendar-day rows** of this index.
    max_ffill_calendar_days:
        Forward-fill limit in **calendar-day rows** of ``ref_index``.
        ``None`` = unlimited (e.g. Friday regime carry-forward through the weekend).
        When omitted (default), uses ``max_stale_days_for_cadence(cadence)`` from SSI config.
        Pass ``None`` explicitly for unlimited carry-forward.
    cadence:
        Publication cadence key (``weekly``, ``daily``, ``monthly``) for default limit lookup.

    Returns
    -------
    Series aligned to ``ref_index``.
    """
    if max_ffill_calendar_days is _UNSET:
        max_ffill_calendar_days = max_stale_days_for_cadence(cadence)
    if series.empty:
        return series.reindex(ref_index)
    return series.sort_index().reindex(ref_index, method="ffill", limit=max_ffill_calendar_days)
