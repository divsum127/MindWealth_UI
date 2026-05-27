"""298-combo detector and named combo A–G rules."""

from __future__ import annotations

import itertools
import json
from datetime import datetime
from typing import Any

import pandas as pd

from src.macro_intelligence.config import load_config
from src.macro_intelligence.data.pull_all import get_readings_as_of, load_all_series
from src.macro_intelligence.data.yahoo_pull import spx_with_50wma
from src.macro_intelligence.db.connection import get_connection
from src.macro_intelligence.engine.percentiles import compute_pctile_for_series
from src.macro_intelligence.models import ComboFire, DurationBucket, GateFlag, SignalTier

VAR_IDS = [
    "NFCI", "HY", "WALCL", "CNH", "WTI", "VIX", "VXTS", "CFTC", "CURVE", "CPI", "GSR", "CAPE"
]


def _is_rare_or_extreme(reading: dict[str, Any] | None) -> bool:
    if not reading:
        return False
    tier = reading.get("signal_tier", "NORMAL")
    return tier in (SignalTier.RARE.value, SignalTier.EXTREME.value, "RARE", "EXTREME")


def detect_named_combos(as_of: str, readings: dict[str, dict[str, Any]] | None = None) -> list[ComboFire]:
    readings = readings or get_readings_as_of(as_of)
    cfg = load_config()
    named = cfg.get("named_combos", {})
    fires: list[ComboFire] = []

    # Combo B — ALL 3 required
    b_cfg = named.get("B", {})
    vix_r = readings.get("VIX")
    hy_r = readings.get("HY")
    cftc_r = readings.get("CFTC")
    b_watch = False
    b_fire = False
    if vix_r and hy_r and cftc_r:
        vix_ok = (vix_r.get("raw_value") or 0) >= b_cfg.get("vix_min", 25)
        hy_ok = (hy_r.get("raw_value") or 0) >= b_cfg.get("hy_bps_min", 400)
        cftc_ok = (cftc_r.get("pctile_rank_3yr") or 100) <= b_cfg.get("cftc_max_pctile", 15)
        count = sum([vix_ok, hy_ok, cftc_ok])
        if count == 3:
            b_fire = True
        elif count >= 1:
            b_watch = True

    if b_fire:
        fires.append(
            ComboFire(
                date=as_of,
                runic_combo="B",
                var_ids=["VIX", "HY", "CFTC"],
                directions=[
                    vix_r.get("direction"),
                    hy_r.get("direction"),
                    cftc_r.get("direction"),
                ],
                status="ACTIVE",
            )
        )
    elif b_watch:
        fires.append(
            ComboFire(
                date=as_of,
                runic_combo="B",
                var_ids=["VIX", "HY", "CFTC"],
                directions=[None, None, None],
                status="WATCH",
            )
        )

    # Combo F — SPX 50WMA reclaim
    f_cfg = named.get("F", {})
    series = load_all_series()
    spx_w: pd.DataFrame = series.get("SPX_W")  # type: ignore[assignment]
    cftc_r = readings.get("CFTC")
    if spx_w is not None and not spx_w.empty and cftc_r:
        as_of_ts = pd.Timestamp(as_of)
        row = spx_w.loc[:as_of_ts].iloc[-1]
        prev = spx_w.loc[:as_of_ts].iloc[-2] if len(spx_w.loc[:as_of_ts]) > 1 else row
        reclaim = bool(row["above_50wma"]) and not bool(prev["above_50wma"])
        weekly_gain = float(row.get("weekly_ret_pct", 0) or 0)
        cftc_pct = cftc_r.get("pctile_rank_3yr") or 50
        if (reclaim or weekly_gain >= f_cfg.get("spx_50wma_reclaim_weekly_pct", 3.0)) and cftc_pct <= f_cfg.get(
            "cftc_max_pctile", 50
        ):
            fires.append(
                ComboFire(
                    date=as_of,
                    runic_combo="F",
                    var_ids=["SPX", "CFTC"],
                    directions=["UP", cftc_r.get("direction")],
                    status="ACTIVE",
                )
            )

    # Combo C
    c_cfg = named.get("C", {})
    wti_r = readings.get("WTI")
    cpi_r = readings.get("CPI")
    walcl_r = readings.get("WALCL")
    if wti_r and (wti_r.get("raw_value") or 0) >= c_cfg.get("wti_4wk_min", 10.0):
        cpi_ok = cpi_r and abs(cpi_r.get("raw_value") or 0) >= c_cfg.get("cpi_surprise_min", 0.2)
        walcl_flat = walcl_r and abs(walcl_r.get("raw_value") or 0) < 0.8
        if cpi_ok and walcl_flat:
            weeks = _combo_c_weeks(as_of)
            bucket = _duration_bucket(weeks)
            fires.append(
                ComboFire(
                    date=as_of,
                    runic_combo="C",
                    var_ids=["WTI", "CPI", "WALCL"],
                    directions=[wti_r.get("direction"), cpi_r.get("direction"), walcl_r.get("direction")],
                    status="ACTIVE",
                    duration_weeks=weeks,
                    duration_bucket=bucket,
                )
            )

    # Combo D — partial / watch
    d_cfg = named.get("D", {})
    vxts_r = readings.get("VXTS")
    vix_r = readings.get("VIX")
    cftc_r = readings.get("CFTC")
    if vxts_r and vix_r and cftc_r:
        vxts_val = vxts_r.get("raw_value") or 0
        if vxts_val >= d_cfg.get("vxts_min", 1.10) and (vix_r.get("raw_value") or 99) < d_cfg.get("vix_max", 18):
            status = "ACTIVE" if (cftc_r.get("pctile_rank_3yr") or 0) >= d_cfg.get("cftc_min_pctile", 85) else "WATCH"
            fires.append(
                ComboFire(
                    date=as_of,
                    runic_combo="D",
                    var_ids=["VXTS", "CFTC", "VIX"],
                    directions=[vxts_r.get("direction"), cftc_r.get("direction"), vix_r.get("direction")],
                    status=status,
                )
            )

    # Combo E — 2 of 3
    e_cfg = named.get("E", {})
    cape_r = readings.get("CAPE")
    nfci_r = readings.get("NFCI")
    cftc_r = readings.get("CFTC")
    e_hits = 0
    e_vars: list[str] = []
    if cape_r and (cape_r.get("raw_value") or 0) >= e_cfg.get("cape_min", 28):
        e_hits += 1
        e_vars.append("CAPE")
    if nfci_r and (nfci_r.get("raw_value") or 0) < e_cfg.get("nfci_easy_max", -0.3):
        e_hits += 1
        e_vars.append("NFCI")
    if cftc_r and (cftc_r.get("pctile_rank_3yr") or 0) >= e_cfg.get("cftc_min_pctile", 80):
        e_hits += 1
        e_vars.append("CFTC")
    if e_hits >= e_cfg.get("min_of_three", 2):
        fires.append(
            ComboFire(
                date=as_of,
                runic_combo="E",
                var_ids=e_vars,
                directions=[None] * len(e_vars),
                status="PARTIAL" if e_hits == 2 else "ACTIVE",
            )
        )

    # Combo G
    g_cfg = named.get("G", {})
    vxts_r = readings.get("VXTS")
    hy_r = readings.get("HY")
    vix_r = readings.get("VIX")
    if vxts_r and hy_r and vix_r:
        if (vxts_r.get("raw_value") or 1) < g_cfg.get("vxts_max", 1.0) and (vix_r.get("raw_value") or 99) < g_cfg.get(
            "vix_max", 20
        ):
            fires.append(
                ComboFire(
                    date=as_of,
                    runic_combo="G",
                    var_ids=["VXTS", "HY", "VIX"],
                    directions=[vxts_r.get("direction"), hy_r.get("direction"), vix_r.get("direction")],
                    status="ACTIVE",
                )
            )

    # Combo A — 2 of 4 at rare+
    a_cfg = named.get("A", {})
    a_vars = a_cfg.get("vars", ["NFCI", "HY", "WALCL", "CNH"])
    rare_count = sum(1 for v in a_vars if _is_rare_or_extreme(readings.get(v)))
    if rare_count >= a_cfg.get("min_of_four", 2):
        fires.append(
            ComboFire(
                date=as_of,
                runic_combo="A",
                var_ids=[v for v in a_vars if _is_rare_or_extreme(readings.get(v))],
                directions=[readings[v].get("direction") for v in a_vars if _is_rare_or_extreme(readings.get(v))],
                status="ACTIVE",
            )
        )

    return fires


def _combo_c_weeks(as_of: str) -> int:
    """Weeks since WTI extreme — simplified from DB history."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT date FROM combo_fires WHERE runic_combo='C' ORDER BY date DESC LIMIT 1"
        ).fetchall()
    if not rows:
        return 1
    start = pd.Timestamp(rows[0]["date"])
    return max(1, int((pd.Timestamp(as_of) - start).days / 7))


def _duration_bucket(weeks: int) -> DurationBucket:
    if weeks < 6:
        return DurationBucket.SHORT
    if weeks <= 16:
        return DurationBucket.MEDIUM
    return DurationBucket.LONG


def detect_generic_combos(as_of: str, readings: dict[str, dict[str, Any]] | None = None) -> list[ComboFire]:
    readings = readings or get_readings_as_of(as_of)
    rare_vars = [v for v in VAR_IDS if _is_rare_or_extreme(readings.get(v))]
    fires: list[ComboFire] = []
    for r in itertools.combinations(rare_vars, 1):
        fires.append(_generic_fire(as_of, list(r), readings))
    for r in itertools.combinations(rare_vars, 2):
        fires.append(_generic_fire(as_of, list(r), readings))
    for r in itertools.combinations(rare_vars, 3):
        fires.append(_generic_fire(as_of, list(r), readings))
    return fires


def _generic_fire(as_of: str, var_ids: list[str], readings: dict[str, dict]) -> ComboFire:
    dirs = [readings[v].get("direction") if readings.get(v) else None for v in var_ids]
    return ComboFire(
        date=as_of,
        runic_combo=None,
        var_ids=var_ids,
        directions=dirs,
        status="ACTIVE",
        gate_flag=GateFlag.BELOW_GATE,
    )


def detect_all_combos(as_of: str | None = None, persist: bool = True) -> list[ComboFire]:
    as_of = as_of or datetime.now().strftime("%Y-%m-%d")
    readings = get_readings_as_of(as_of)
    named = detect_named_combos(as_of, readings)
    generic = detect_generic_combos(as_of, readings)

    # Dedupe: skip generic that match named var sets
    named_keys = {tuple(sorted(f.var_ids)) for f in named if f.runic_combo}
    filtered_generic = [g for g in generic if tuple(sorted(g.var_ids)) not in named_keys]

    all_fires = named + filtered_generic
    if persist:
        _persist_fires(all_fires)
    return all_fires


def _persist_fires(fires: list[ComboFire]) -> None:
    with get_connection() as conn:
        for f in fires:
            conn.execute(
                """
                INSERT INTO combo_fires
                (date, var1_id, var2_id, var3_id, var1_direction, var2_direction, var3_direction,
                 runic_combo, status, duration_weeks, duration_bucket, gate_flag, macro_regime)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f.date,
                    f.var_ids[0] if len(f.var_ids) > 0 else None,
                    f.var_ids[1] if len(f.var_ids) > 1 else None,
                    f.var_ids[2] if len(f.var_ids) > 2 else None,
                    f.directions[0] if len(f.directions) > 0 else None,
                    f.directions[1] if len(f.directions) > 1 else None,
                    f.directions[2] if len(f.directions) > 2 else None,
                    f.runic_combo,
                    f.status,
                    f.duration_weeks,
                    f.duration_bucket.value if f.duration_bucket else None,
                    f.gate_flag.value,
                    json.dumps(f.macro_regime) if f.macro_regime else None,
                ),
            )


def evaluate_combo_b_at_date(
    as_of: str,
    vix: float,
    hy_bps: float,
    cftc_pctile: float,
) -> bool:
    """Direct evaluation for validation tests."""
    return vix >= 25 and hy_bps >= 400 and cftc_pctile <= 15


def evaluate_combo_f_at_date(
    as_of: str,
    weekly_gain_pct: float,
    cftc_pctile: float,
    above_50wma: bool,
    was_below_prior_week: bool = False,
) -> bool:
    reclaim = above_50wma and (was_below_prior_week or weekly_gain_pct >= 3.0)
    return reclaim and cftc_pctile <= 50
