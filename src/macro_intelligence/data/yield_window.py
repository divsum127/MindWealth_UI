"""Yield snapshots and event-window deltas from FRED daily series."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import pandas as pd

from src.macro_intelligence.data.fred_pull import (
    fetch_dgs10,
    fetch_dgs2,
    fetch_dgs30,
    fetch_fred_series,
    fetch_t10y2y,
)


@lru_cache(maxsize=1)
def _yield_cache() -> dict[str, pd.Series]:
    return {
        "DGS2": fetch_dgs2("1990-01-01"),
        "DGS10": fetch_dgs10("1990-01-01"),
        "DGS30": fetch_dgs30("1990-01-01"),
        "T10Y2Y": fetch_t10y2y("1976-01-01"),
        "HY": fetch_fred_series("BAMLH0A0HYM2", "2010-01-01"),
    }


def _value_on_or_before(series: pd.Series, as_of: str) -> float | None:
    s = series.loc[: pd.Timestamp(as_of)].dropna()
    if s.empty:
        return None
    return float(s.iloc[-1])


def yield_snapshot(as_of: str) -> dict[str, float | None]:
    cache = _yield_cache()
    spread = _value_on_or_before(cache["T10Y2Y"], as_of)
    return {
        "dgs2": _value_on_or_before(cache["DGS2"], as_of),
        "dgs10": _value_on_or_before(cache["DGS10"], as_of),
        "dgs30": _value_on_or_before(cache["DGS30"], as_of),
        "t10y2y_bps": spread * 100 if spread is not None else None,
        "hy_oas": _value_on_or_before(cache["HY"], as_of),
    }


def yield_changes_bps(pre_date: str, post_date: str) -> dict[str, float | None]:
    """Yield and spread changes in bps between two anchor dates."""
    pre = yield_snapshot(pre_date)
    post = yield_snapshot(post_date)

    def _delta(key: str, scale: float = 100.0) -> float | None:
        if pre.get(key) is None or post.get(key) is None:
            return None
        return (float(post[key]) - float(pre[key])) * scale

    dgs2_bps = _delta("dgs2")
    dgs10_bps = _delta("dgs10")
    dgs30_bps = _delta("dgs30")
    curve_bps = None
    if pre.get("t10y2y_bps") is not None and post.get("t10y2y_bps") is not None:
        curve_bps = float(post["t10y2y_bps"]) - float(pre["t10y2y_bps"])

    hy_bps = None
    if pre.get("hy_oas") is not None and post.get("hy_oas") is not None:
        hy_bps = (float(post["hy_oas"]) - float(pre["hy_oas"])) * 100

    long_bps = None
    if dgs10_bps is not None or dgs30_bps is not None:
        candidates = [abs(x) for x in (dgs10_bps, dgs30_bps) if x is not None]
        if dgs10_bps is not None and dgs30_bps is not None:
            long_bps = dgs30_bps if abs(dgs30_bps) >= abs(dgs10_bps) else dgs10_bps
        elif dgs10_bps is not None:
            long_bps = dgs10_bps
        else:
            long_bps = dgs30_bps

    return {
        "dgs2_bps": dgs2_bps,
        "dgs10_bps": dgs10_bps,
        "dgs30_bps": dgs30_bps,
        "long_bps": long_bps,
        "curve_bps": curve_bps,
        "hy_bps": hy_bps,
    }


def trading_day_on_or_before(date: str) -> str:
    ts = pd.Timestamp(date)
    while ts.weekday() >= 5:
        ts -= pd.Timedelta(days=1)
    return ts.strftime("%Y-%m-%d")


def trading_day_before(date: str) -> str:
    ts = pd.Timestamp(date) - pd.Timedelta(days=1)
    while ts.weekday() >= 5:
        ts -= pd.Timedelta(days=1)
    return ts.strftime("%Y-%m-%d")


def event_window_anchors(event_date: str, as_of: str) -> dict[str, str]:
    """Pre = last trading day before event; post = latest trading day on/before as_of."""
    return {
        "pre_date": trading_day_before(event_date),
        "post_date": trading_day_on_or_before(as_of),
    }


def build_event_metrics(pre_date: str, post_date: str) -> dict[str, Any]:
    """Combine yield/HY deltas with VIX and USD proxy moves."""
    from src.macro_intelligence.data.yahoo_pull import fetch_yahoo_close

    yields = yield_changes_bps(pre_date, post_date)
    vix = fetch_yahoo_close("^VIX", "2010-01-01")
    cnh = fetch_yahoo_close("USDCNH=X", "2010-01-01")

    vix_pts = None
    if not vix.empty:
        pre_v = _value_on_or_before(vix, pre_date)
        post_v = _value_on_or_before(vix, post_date)
        if pre_v is not None and post_v is not None:
            vix_pts = float(post_v) - float(pre_v)

    usd_pct = None
    if not cnh.empty:
        pre_c = _value_on_or_before(cnh, pre_date)
        post_c = _value_on_or_before(cnh, post_date)
        if pre_c is not None and post_c is not None and pre_c != 0:
            usd_pct = (float(pre_c) - float(post_c)) / float(pre_c) * 100.0

    return {
        **yields,
        "vix_pts": vix_pts,
        "usd_pct": usd_pct,
    }
