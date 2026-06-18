"""CAPE / CFTC source-date checks vs report as_of; refresh when lagging."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

import pandas as pd

from src.macro_intelligence.config import load_config
from src.macro_intelligence.data.cape_scrape import fetch_cape_history, load_cape_series
from src.macro_intelligence.data.cftc_pull import (
    fetch_cftc_fast_money_net,
    force_refresh_cftc_zip,
    refresh_cftc_zip_if_stale,
)

logger = logging.getLogger(__name__)

_LAST_FRESHNESS_AUDIT: dict[str, Any] | None = None


@dataclass
class SourceFreshnessRow:
    variable: str
    report_date: str
    source_date: str | None
    expected_source_date: str | None
    lag_days: int | None
    stale: bool
    refreshed: bool
    note: str = ""


def get_last_freshness_audit() -> dict[str, Any]:
    return dict(_LAST_FRESHNESS_AUDIT or {})


def latest_observation_as_of(series: pd.Series, as_of: str) -> tuple[pd.Timestamp | None, float | None]:
    if series is None or series.empty:
        return None, None
    hist = series.loc[: pd.Timestamp(as_of)]
    if hist.empty:
        return None, None
    return pd.Timestamp(hist.index[-1]), float(hist.iloc[-1])


def expected_latest_cftc_tuesday(as_of: str) -> pd.Timestamp:
    """Latest CFTC Tuesday position that should be published by report as_of (Fri = Tue + 3)."""
    as_of_ts = pd.Timestamp(as_of).normalize()
    d = as_of_ts
    for _ in range(60):
        while d.weekday() != 1:
            d -= pd.Timedelta(days=1)
        if d + pd.Timedelta(days=3) <= as_of_ts:
            return d
        d -= pd.Timedelta(days=1)
    return as_of_ts - pd.Timedelta(days=7)


def _freshness_cfg() -> dict[str, Any]:
    return load_config().get("source_freshness", {})


def check_cape_freshness(as_of: str, cape: pd.Series | None = None) -> SourceFreshnessRow:
    cape = cape if cape is not None else load_cape_series()
    cfg = _freshness_cfg()
    max_lag = int(cfg.get("cape_max_lag_days", 7))
    src_date, _ = latest_observation_as_of(cape, as_of)
    lag = (pd.Timestamp(as_of) - src_date).days if src_date is not None else None
    stale = src_date is None or (lag is not None and lag > max_lag)
    note = ""
    if src_date is None:
        note = "CAPE series empty"
    elif stale:
        note = f"CAPE source {src_date.strftime('%Y-%m-%d')} is {lag}d before report (max {max_lag}d)"
    return SourceFreshnessRow(
        variable="CAPE",
        report_date=as_of,
        source_date=src_date.strftime("%Y-%m-%d") if src_date is not None else None,
        expected_source_date=None,
        lag_days=lag,
        stale=stale,
        refreshed=False,
        note=note,
    )


def check_cftc_freshness(as_of: str, cftc: pd.Series | None = None) -> SourceFreshnessRow:
    cftc = cftc if cftc is not None else fetch_cftc_fast_money_net(2006)
    expected = expected_latest_cftc_tuesday(as_of)
    src_date, _ = latest_observation_as_of(cftc, as_of)
    lag = (pd.Timestamp(as_of) - src_date).days if src_date is not None else None
    stale = src_date is None or src_date < expected
    note = ""
    if src_date is None:
        note = "CFTC series empty"
    elif stale:
        exp_lag = (pd.Timestamp(as_of) - expected).days
        note = (
            f"CFTC source {src_date.strftime('%Y-%m-%d')} older than expected "
            f"{expected.strftime('%Y-%m-%d')} (report lag {lag}d, expected max {exp_lag}d)"
        )
    return SourceFreshnessRow(
        variable="CFTC",
        report_date=as_of,
        source_date=src_date.strftime("%Y-%m-%d") if src_date is not None else None,
        expected_source_date=expected.strftime("%Y-%m-%d"),
        lag_days=lag,
        stale=stale,
        refreshed=False,
        note=note,
    )


def ensure_cape_cftc_fresh(as_of: str | None = None) -> dict[str, Any]:
    """
    Compare CAPE and CFTC source observation dates to report as_of.
    Re-scrape CAPE / re-download CFTC ZIP when data lags expectations.
    """
    global _LAST_FRESHNESS_AUDIT

    as_of = as_of or datetime.now().strftime("%Y-%m-%d")
    rows: list[SourceFreshnessRow] = []

    cape = load_cape_series()
    cape_row = check_cape_freshness(as_of, cape)
    if cape_row.stale:
        logger.info("CAPE stale for %s — re-scraping multpl.com (%s)", as_of, cape_row.note)
        refreshed = fetch_cape_history()
        if not refreshed.empty:
            cape = refreshed
            cape_row = check_cape_freshness(as_of, cape)
            cape_row.refreshed = True
            if cape_row.stale:
                cape_row.note += " (re-scrape did not improve source date)"
        else:
            cape_row.note += " (re-scrape failed; using cache)"
    rows.append(cape_row)

    refresh_cftc_zip_if_stale()
    cftc = fetch_cftc_fast_money_net(2006)
    cftc_row = check_cftc_freshness(as_of, cftc)
    if cftc_row.stale:
        logger.info("CFTC stale for %s — forcing ZIP refresh (%s)", as_of, cftc_row.note)
        if force_refresh_cftc_zip():
            cftc = fetch_cftc_fast_money_net(2006)
            cftc_row = check_cftc_freshness(as_of, cftc)
            cftc_row.refreshed = True
            if cftc_row.stale:
                cftc_row.note += " (ZIP refresh did not reach expected Tuesday)"
        else:
            cftc_row.note += " (ZIP refresh failed)"
    rows.append(cftc_row)

    audit = {
        "report_date": as_of,
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "sources": {r.variable: asdict(r) for r in rows},
        "any_stale_after_refresh": any(r.stale for r in rows),
    }
    _LAST_FRESHNESS_AUDIT = audit

    for r in rows:
        if r.stale:
            logger.warning("%s freshness: %s", r.variable, r.note)
        else:
            logger.info(
                "%s OK — source %s, lag %sd vs report %s",
                r.variable,
                r.source_date,
                r.lag_days,
                as_of,
            )

    return audit
