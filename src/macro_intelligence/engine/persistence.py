"""Persistence / streak signal engine."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pandas as pd

from src.macro_intelligence.config import load_config
from src.macro_intelligence.data.pull_all import load_all_series
from src.macro_intelligence.data.yahoo_pull import fetch_yahoo_close, spx_with_50wma
from src.macro_intelligence.db.connection import get_connection


def run_persistence_scan(as_of: str | None = None) -> list[dict[str, Any]]:
    as_of = as_of or datetime.now().strftime("%Y-%m-%d")
    cfg = load_config()
    rules = cfg.get("persistence_rules", [])
    series = load_all_series()
    fires: list[dict[str, Any]] = []

    for rule in rules:
        hit = _eval_rule(rule, series, as_of)
        if hit:
            fires.append(hit)
            _persist(hit)

    return fires


def _eval_rule(rule: dict[str, Any], series: dict[str, Any], as_of: str) -> dict[str, Any] | None:
    name = rule["name"]
    var = rule.get("variable", "")
    as_of_ts = pd.Timestamp(as_of)

    if name == "7WK_GRIND" or name == "3WK_SURGE":
        spx_w = series.get("SPX_W")
        if spx_w is None or spx_w.empty:
            spx_w = spx_with_50wma()
        recent = spx_w.loc[:as_of_ts].tail(rule["periods"] + 1)
        if len(recent) < rule["periods"]:
            return None
        rets = recent["weekly_ret_pct"].dropna().tail(rule["periods"])
        if name == "7WK_GRIND":
            ok = (rets > rule["value"]).all()
        else:
            ok = (rets >= rule["value"]).all()
        if ok:
            return _fire_dict(name, "SPX", as_of, rule["periods"], float(rets.iloc[-1]))
        return None

    if name == "VIX_SUPPRESSED":
        vix = series.get("VIX")
        if vix is None or vix.empty:
            return None
        daily = vix.loc[:as_of_ts].tail(rule["periods"])
        if len(daily) < rule["periods"]:
            return None
        if (daily < rule["value"]).all():
            return _fire_dict(name, "VIX", as_of, rule["periods"], float(daily.iloc[-1]))
        return None

    if name == "FCI_EASING_STREAK":
        nfci = series.get("NFCI")
        if nfci is None:
            return None
        weekly = nfci.resample("W-FRI").last().loc[:as_of_ts].tail(rule["periods"] + 1)
        if len(weekly) < rule["periods"] + 1:
            return None
        improving = (weekly.diff().dropna() < 0).tail(rule["periods"])
        if improving.all():
            return _fire_dict(name, "NFCI", as_of, rule["periods"], float(weekly.iloc[-1]))
        return None

    if name == "OIL_VOLATILE":
        wti = series.get("WTI")
        if wti is None:
            return None
        weekly = wti.resample("W-FRI").last().loc[:as_of_ts].tail(rule["periods"])
        if len(weekly) < rule["periods"]:
            return None
        rets = weekly.pct_change().dropna().tail(rule["periods"])
        if (rets.abs() >= rule["value"]).all():
            return _fire_dict(name, "WTI", as_of, rule["periods"], float(rets.iloc[-1]))
        return None

    return None


def _fire_dict(name: str, var_id: str, as_of: str, weeks: int, val: float) -> dict[str, Any]:
    return {
        "signal_name": name,
        "var_id": var_id,
        "start_date": as_of,
        "end_date": None,
        "weeks_count": weeks,
        "trigger_value": val,
        "active": True,
    }


def _persist(hit: dict[str, Any]) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO persistence_fires
            (signal_name, var_id, start_date, end_date, weeks_count, trigger_value, active, meta_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                hit["signal_name"],
                hit["var_id"],
                hit["start_date"],
                hit.get("end_date"),
                hit["weeks_count"],
                hit["trigger_value"],
                1 if hit.get("active") else 0,
                json.dumps({}),
            ),
        )
