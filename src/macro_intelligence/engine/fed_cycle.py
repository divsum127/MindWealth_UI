"""Fed cycle labels from FRED DFF + WALCL QE/QT override.

HIKING_EARLY / HIKING_LATE = position within an active hiking cycle (<6 vs >=6 months
since the cycle started), NOT magnitude of 3-month rate change or "late to hike".
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.macro_intelligence.config import load_config
from src.macro_intelligence.data.fred_pull import fetch_dff, fetch_fred_series, walcl_mom_pct

_FED_CYCLE_CACHE: pd.Series | None = None
_WALCL_MOM_CACHE: pd.Series | None = None
_DFF_DAILY_CACHE: pd.Series | None = None

# FOMC cycle anchors where daily DFF lags the policy headline by a few days.
_FOMC_ANCHORS: dict[str, str] = {
    "2015-12-16": "HIKING_EARLY",
    "2024-09-18": "CUTTING_EARLY",
}


def _regime_cfg() -> dict[str, Any]:
    return load_config().get("regime", {})


def _load_dff_daily() -> pd.Series:
    global _DFF_DAILY_CACHE
    if _DFF_DAILY_CACHE is not None:
        return _DFF_DAILY_CACHE
    cfg = _regime_cfg()
    start = cfg.get("fed_funds_start", "1990-01-01")
    _DFF_DAILY_CACHE = fetch_dff(start).sort_index().astype(float)
    return _DFF_DAILY_CACHE


def _load_walcl_mom_weekly() -> pd.Series:
    walcl = fetch_fred_series("WALCL", "2003-01-01")
    return walcl_mom_pct(walcl)


def _rate_at(dff: pd.Series, as_of: pd.Timestamp) -> float | None:
    sl = dff.loc[:as_of].dropna()
    return float(sl.iloc[-1]) if not sl.empty else None


def _change_over(dff: pd.Series, as_of: pd.Timestamp, weeks: int) -> float:
    rate = _rate_at(dff, as_of)
    if rate is None:
        return 0.0
    prior_ts = as_of - pd.Timedelta(weeks=weeks)
    prior = _rate_at(dff, prior_ts)
    if prior is None:
        return 0.0
    return rate - prior


def _direction(chg_13w: float, chg_4w: float, hike_thresh: float, cut_thresh: float) -> str:
    if chg_13w >= hike_thresh or chg_4w >= hike_thresh:
        return "HIKE"
    if chg_13w <= cut_thresh or chg_4w <= cut_thresh:
        return "CUT"
    return "PAUSE"


def _label_from_state(
    direction: str,
    cycle_start: pd.Timestamp | None,
    as_of: pd.Timestamp,
    early_months: float,
) -> str:
    if direction == "PAUSE" or cycle_start is None:
        return "PAUSING"
    months = (as_of - cycle_start).days / 30.44
    early = months < early_months
    if direction == "HIKE":
        return "HIKING_EARLY" if early else "HIKING_LATE"
    return "CUTTING_EARLY" if early else "CUTTING_LATE"


def _qe_qt_override(walcl_mom: float | None, cfg: dict[str, Any]) -> str | None:
    if walcl_mom is None:
        return None
    if walcl_mom > cfg.get("qe_walcl_mom_min", 1.0):
        return "QE"
    if walcl_mom < cfg.get("qt_walcl_mom_max", -0.5):
        return "QT"
    return None


def _in_covid_qe_window(as_of: pd.Timestamp) -> bool:
    return pd.Timestamp("2020-03-01") <= as_of <= pd.Timestamp("2021-06-30")


def build_fed_cycle_series(force: bool = False) -> pd.Series:
    """Weekly (Friday) fed_cycle labels from 1990 onward."""
    global _FED_CYCLE_CACHE, _WALCL_MOM_CACHE
    if _FED_CYCLE_CACHE is not None and not force:
        return _FED_CYCLE_CACHE

    cfg = _regime_cfg()
    weeks_13 = int(cfg.get("fed_direction_weeks", 13))
    weeks_4 = int(cfg.get("fed_direction_weeks_short", 4))
    hike_thresh = float(cfg.get("fed_hike_3m_thresh", 0.25))
    cut_thresh = float(cfg.get("fed_cut_3m_thresh", -0.25))
    early_months = float(cfg.get("cycle_early_months", 6))

    dff = _load_dff_daily()
    walcl_mom = _load_walcl_mom_weekly()
    _WALCL_MOM_CACHE = walcl_mom

    fridays = pd.date_range(dff.index.min(), dff.index.max(), freq="W-FRI")
    labels: dict[pd.Timestamp, str] = {}
    hike_start: pd.Timestamp | None = None
    cut_start: pd.Timestamp | None = None
    prev_direction = "PAUSE"

    for dt in fridays:
        if dt > dff.index.max():
            break
        chg_13 = _change_over(dff, dt, weeks_13)
        chg_4 = _change_over(dff, dt, weeks_4)
        direction = _direction(chg_13, chg_4, hike_thresh, cut_thresh)

        if direction == "HIKE" and prev_direction != "HIKE":
            hike_start = dt
            cut_start = None
        elif direction == "CUT" and prev_direction != "CUT":
            cut_start = dt
            hike_start = None
        elif direction == "PAUSE":
            if prev_direction == "HIKE":
                hike_start = None
            if prev_direction == "CUT":
                cut_start = None

        cycle_start = hike_start if direction == "HIKE" else cut_start if direction == "CUT" else None
        label = _label_from_state(direction, cycle_start, dt, early_months)

        wm = walcl_mom.loc[:dt]
        walcl_val = float(wm.iloc[-1]) if not wm.empty else None
        if _qe_qt_override(walcl_val, cfg) == "QE":
            label = "QE"
        elif _qe_qt_override(walcl_val, cfg) == "QT" and label == "PAUSING":
            label = "QT"
        if _in_covid_qe_window(dt):
            label = "QE"
        wk = dt.strftime("%Y-%m-%d")
        if wk in _FOMC_ANCHORS:
            label = _FOMC_ANCHORS[wk]

        labels[dt] = label
        prev_direction = direction

    _FED_CYCLE_CACHE = pd.Series(labels).sort_index()
    _FED_CYCLE_CACHE.name = "fed_cycle"
    return _FED_CYCLE_CACHE


def fed_cycle_at_date(as_of: str, walcl_mom: float | None = None) -> tuple[str, str]:
    """Return (fed_cycle label, source tag) for any calendar date."""
    as_of_ts = pd.Timestamp(as_of)
    ds = as_of_ts.strftime("%Y-%m-%d")
    if ds in _FOMC_ANCHORS:
        return _FOMC_ANCHORS[ds], "FOMC_ANCHOR"

    cfg = _regime_cfg()
    dff = _load_dff_daily()

    if _in_covid_qe_window(as_of_ts):
        return "QE", "COVID_QE_WINDOW"

    chg_13 = _change_over(dff, as_of_ts, int(cfg.get("fed_direction_weeks", 13)))
    chg_4 = _change_over(dff, as_of_ts, int(cfg.get("fed_direction_weeks_short", 4)))
    hike_thresh = float(cfg.get("fed_hike_3m_thresh", 0.25))
    cut_thresh = float(cfg.get("fed_cut_3m_thresh", -0.25))
    early_months = float(cfg.get("cycle_early_months", 6))

    direction = _direction(chg_13, chg_4, hike_thresh, cut_thresh)

    series = build_fed_cycle_series()
    sl = series.loc[:as_of_ts]
    if not sl.empty and direction == "PAUSE":
        label = str(sl.iloc[-1])
        if label.startswith("HIKING") or label.startswith("CUTTING"):
            return label, "FRED_DFF"

    hike_start = cut_start = None
    for dt in series.loc[:as_of_ts].index:
        lab = str(series.loc[dt])
        if lab.startswith("HIKING"):
            if hike_start is None:
                hike_start = dt
            direction = "HIKE"
        elif lab.startswith("CUTTING"):
            if cut_start is None:
                cut_start = dt
            direction = "CUT"

    if direction == "HIKE" and hike_start is None:
        hike_start = as_of_ts
    if direction == "CUT" and cut_start is None:
        cut_start = as_of_ts

    cycle_start = hike_start if direction == "HIKE" else cut_start if direction == "CUT" else None
    label = _label_from_state(direction, cycle_start, as_of_ts, early_months)

    if walcl_mom is None and _WALCL_MOM_CACHE is not None:
        wm = _WALCL_MOM_CACHE.loc[:as_of_ts]
        walcl_mom = float(wm.iloc[-1]) if not wm.empty else None

    if _qe_qt_override(walcl_mom, cfg) == "QE":
        return "QE", "WALCL_PROXY"
    if _qe_qt_override(walcl_mom, cfg) == "QT" and label == "PAUSING":
        return "QT", "WALCL_PROXY"

    return label, "FRED_DFF"


def fed_cycle_dates_matching(label: str) -> set[pd.Timestamp]:
    series = build_fed_cycle_series()
    return {pd.Timestamp(d) for d, v in series.items() if v == label}


def clear_fed_cycle_cache() -> None:
    global _FED_CYCLE_CACHE, _WALCL_MOM_CACHE, _DFF_DAILY_CACHE
    _FED_CYCLE_CACHE = None
    _WALCL_MOM_CACHE = None
    _DFF_DAILY_CACHE = None
