"""298-combo detector and named combo A–G rules."""

from __future__ import annotations

import itertools
import json
from datetime import datetime
from typing import Any

import pandas as pd

from src.macro_intelligence.config import load_config
from src.macro_intelligence.data.pull_all import get_readings_as_of, load_all_series
from src.macro_intelligence.data.fred_pull import fetch_fred_series
from src.macro_intelligence.data.yahoo_pull import spx_with_50wma
from src.macro_intelligence.db.connection import get_connection
from src.macro_intelligence.engine.percentiles import combo_pctile_from_reading, compute_pctile_for_series
from src.macro_intelligence.models import ComboFire, DurationBucket, GateFlag, SignalTier

VAR_IDS = [
    "NFCI", "HY", "WALCL", "CNH", "WTI", "VIX", "VXTS", "CFTC", "CURVE", "CPI", "GSR", "CAPE"
]


def _hy_oas_bps(hy_raw: float | None) -> float:
    """FRED BAMLH0A0HYM2 is in percent (4.0 = 400bps)."""
    if hy_raw is None:
        return 0.0
    val = float(hy_raw)
    return val * 100.0 if val < 50 else val


def _is_rare_or_extreme(reading: dict[str, Any] | None) -> bool:
    if not reading:
        return False
    tier = reading.get("signal_tier", "NORMAL")
    return tier in (SignalTier.RARE.value, SignalTier.EXTREME.value, "RARE", "EXTREME")


def _attach_macro_regime(fires: list[ComboFire], macro_regime: dict[str, Any] | None) -> list[ComboFire]:
    if not macro_regime:
        return fires
    for f in fires:
        merged = dict(macro_regime)
        if f.macro_regime:
            merged.update(f.macro_regime)
        f.macro_regime = merged
    return fires


def detect_named_combos(
    as_of: str,
    readings: dict[str, dict[str, Any]] | None = None,
    macro_regime: dict[str, Any] | None = None,
) -> list[ComboFire]:
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
        vix_pct = combo_pctile_from_reading(vix_r) or 0
        vix_ok = (vix_r.get("raw_value") or 0) >= b_cfg.get("vix_min", 25) and vix_pct >= 80
        hy_bps = _hy_oas_bps(hy_r.get("raw_value"))
        hy_pct = combo_pctile_from_reading(hy_r) or 0
        hy_ok = hy_bps >= b_cfg.get("hy_bps_min", 400) and hy_pct >= 80
        cftc_ok = (combo_pctile_from_reading(cftc_r) or 100) <= b_cfg.get("cftc_max_pctile", 15)
        count = sum([vix_ok, hy_ok, cftc_ok])
        if count == 3:
            b_fire = True
        elif count >= 1:
            # 1 or 2 of 3 legs met → WATCH (per architecture doc §4.6 and implementation status §P1)
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

    # Combo F — SPX 50WMA reclaim (v3 validation date 2020-06-08; 26-week active window)
    f_cfg = named.get("F", {})
    series = load_all_series()
    spx_w: pd.DataFrame = series.get("SPX_W")  # type: ignore[assignment]
    cftc_r = readings.get("CFTC")
    max_weeks = int(f_cfg.get("active_weeks", 26))
    if spx_w is not None and not spx_w.empty and cftc_r:
        as_of_ts = pd.Timestamp(as_of)
        row = spx_w.loc[:as_of_ts].iloc[-1]
        prev = spx_w.loc[:as_of_ts].iloc[-2] if len(spx_w.loc[:as_of_ts]) > 1 else row
        above = bool(row["above_50wma"])
        if not above:
            pass  # SPX below 50WMA — invalidate any active window
        else:
            reclaim = above and not bool(prev["above_50wma"])
            # Spec: "SPX weekly close was ≥3% higher than the 50-week moving average"
            # — this is a LEVEL test (close vs WMA), not a weekly return test.
            pct_above_wma = (float(row["close"]) / float(row["wma50"]) - 1.0) * 100.0
            cftc_pct = combo_pctile_from_reading(cftc_r) or 50
            new_entry = (
                reclaim or pct_above_wma >= f_cfg.get("spx_50wma_reclaim_weekly_pct", 3.0)
            ) and cftc_pct <= f_cfg.get("cftc_max_pctile", 50)
            f_weeks = _combo_f_weeks(as_of)  # None if no prior fire in DB
            in_window = f_weeks is not None and f_weeks <= max_weeks
            if new_entry or in_window:
                fw = f_weeks if in_window else 1
                ep_start = _combo_f_episode_start(as_of)
                fires.append(
                    ComboFire(
                        date=as_of,
                        runic_combo="F",
                        var_ids=["SPX", "CFTC"],
                        directions=["UP", cftc_r.get("direction")],
                        status="ACTIVE",
                        duration_weeks=fw,
                        duration_bucket=_duration_bucket(fw),
                        macro_regime={"episode_start": ep_start} if ep_start else None,
                    )
                )

    # Combo C — entry OR persistence (stays active until 4-Friday cancel rule fires)
    c_cfg = named.get("C", {})
    wti_r = readings.get("WTI")
    cpi_r = readings.get("CPI")
    walcl_r = readings.get("WALCL")
    cpi_surprise = (cpi_r.get("raw_value") or 0) if cpi_r else 0
    c_new_entry = bool(
        wti_r
        and (wti_r.get("raw_value") or 0) >= c_cfg.get("wti_4wk_min", 10.0)
        and cpi_r
        and cpi_surprise >= c_cfg.get("cpi_surprise_min", 0.2)
        and walcl_r
        and abs(walcl_r.get("raw_value") or 0) < 0.8
    )
    # Persist: WTI has dropped below entry threshold but cancel rule hasn't triggered yet
    c_persist = not c_new_entry and _combo_c_still_active()
    if c_new_entry or c_persist:
        weeks = _combo_c_weeks(as_of)
        bucket = _duration_bucket(weeks)
        ep_start = _combo_c_episode_start(as_of)
        fires.append(
            ComboFire(
                date=as_of,
                runic_combo="C",
                var_ids=["WTI", "CPI", "WALCL"],
                directions=[
                    wti_r.get("direction") if wti_r else None,
                    cpi_r.get("direction") if cpi_r else None,
                    walcl_r.get("direction") if walcl_r else None,
                ],
                status="ACTIVE",
                duration_weeks=weeks,
                duration_bucket=bucket,
                macro_regime={"episode_start": ep_start} if ep_start else None,
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
            status = "ACTIVE" if (combo_pctile_from_reading(cftc_r) or 0) >= d_cfg.get("cftc_min_pctile", 85) else "WATCH"
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
    # Spec: "NFCI ≤ −0.3" — inclusive boundary
    if nfci_r and (nfci_r.get("raw_value") or 0) <= e_cfg.get("nfci_easy_max", -0.3):
        e_hits += 1
        e_vars.append("NFCI")
    if cftc_r and (combo_pctile_from_reading(cftc_r) or 0) >= e_cfg.get("cftc_min_pctile", 80):
        e_hits += 1
        e_vars.append("CFTC")
    if e_hits >= e_cfg.get("min_of_three", 2):
        e_status = "CONFIRMED_3_OF_3" if e_hits >= 3 else "CONFIRMED"
        fires.append(
            ComboFire(
                date=as_of,
                runic_combo="E",
                var_ids=e_vars,
                directions=[None] * len(e_vars),
                status=e_status,
                macro_regime={"confirmed_legs": e_vars},
            )
        )

    # Combo G — complacency + HY 4wk widening (v3 hy_widen_4wk_bps)
    g_cfg = named.get("G", {})
    vxts_r = readings.get("VXTS")
    hy_r = readings.get("HY")
    vix_r = readings.get("VIX")
    if vxts_r and hy_r and vix_r:
        hy_4wk_bps = _hy_4wk_change_bps(as_of)
        hy_widen = hy_4wk_bps is not None and hy_4wk_bps >= g_cfg.get("hy_widen_4wk_bps", 30)
        # Spec: "VIX ≤ 20" — inclusive boundary
        if (
            (vxts_r.get("raw_value") or 1) < g_cfg.get("vxts_max", 1.0)
            and (vix_r.get("raw_value") or 99) <= g_cfg.get("vix_max", 20)
            and hy_widen
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

    # Combo A — 2 of 4 rare+ with EASY_MONEY/TIGHT_MONEY direction vote (CONTESTED if tie)
    a_cfg = named.get("A", {})
    a_vars = a_cfg.get("vars", ["NFCI", "HY", "WALCL", "CNH"])
    rare_legs = [v for v in a_vars if _is_rare_or_extreme(readings.get(v))]
    if len(rare_legs) >= a_cfg.get("min_of_four", 2):
        vote = _combo_a_direction_vote(readings, a_vars)
        if vote == "CONTESTED":
            fires.append(
                ComboFire(
                    date=as_of,
                    runic_combo="A",
                    var_ids=rare_legs,
                    directions=[readings[v].get("direction") for v in rare_legs],
                    status="CONTESTED",
                )
            )
        elif vote in ("EASY_MONEY", "TIGHT_MONEY", "FEARFUL"):
            fires.append(
                ComboFire(
                    date=as_of,
                    runic_combo="A",
                    var_ids=rare_legs,
                    directions=[readings[v].get("direction") for v in rare_legs],
                    status="ACTIVE",
                    macro_regime={"a_vote": vote},
                )
            )

    return _attach_macro_regime(fires, macro_regime)


def _hy_4wk_change_bps(as_of: str) -> float | None:
    """HY OAS 4-week change in basis points (calendar ~28d via last-two-months proxy)."""
    try:
        hy = fetch_fred_series("BAMLH0A0HYM2", "2010-01-01")
        if hy is None or len(hy) < 30:
            return None
        as_of_ts = pd.Timestamp(as_of)
        cur = float(hy.loc[:as_of_ts].iloc[-1])
        prior = float(hy.loc[: as_of_ts - pd.Timedelta(days=28)].iloc[-1])
        return (cur - prior) * 100  # index is already in % — convert to bps-like spread delta
    except Exception:
        return None


def _combo_a_direction_vote(readings: dict[str, dict[str, Any]], a_vars: list[str]) -> str:
    """Returns EASY_MONEY, TIGHT_MONEY, or CONTESTED per Combo A vote rules."""
    easy_money = tight_money = 0
    nfci = readings.get("NFCI", {})
    if nfci:
        v = nfci.get("raw_value") or 0
        if v < -0.3:
            easy_money += 1
        elif v > 0.3:
            tight_money += 1
    hy = readings.get("HY", {})
    if hy and hy.get("direction") == "UP":
        tight_money += 1
    elif hy and hy.get("direction") == "DOWN":
        easy_money += 1
    walcl = readings.get("WALCL", {})
    if walcl and walcl.get("direction") == "UP":
        easy_money += 1
    elif walcl and walcl.get("direction") == "DOWN":
        tight_money += 1
    cnh = readings.get("CNH", {})
    if cnh and cnh.get("direction") == "DOWN":
        easy_money += 1
    elif cnh and cnh.get("direction") == "UP":
        tight_money += 1
    if easy_money > tight_money:
        return "EASY_MONEY"
    if tight_money > easy_money:
        return "TIGHT_MONEY"
    return "CONTESTED"


def _combo_f_episode_start(as_of: str) -> str | None:
    """First F fire after the most recent SPX below-50WMA week."""
    as_of_ts = pd.Timestamp(as_of)
    spx_w = spx_with_50wma()
    history = spx_w.loc[:as_of_ts]
    below = history[~history["above_50wma"]]
    last_below_ts = below.index[-1] if not below.empty else pd.Timestamp("1900-01-01")
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT date FROM combo_fires WHERE runic_combo='F' AND date > ? AND date <= ? ORDER BY date ASC LIMIT 1",
            (last_below_ts.strftime("%Y-%m-%d"), as_of),
        ).fetchall()
    return rows[0]["date"] if rows else None


def _combo_f_weeks(as_of: str) -> int | None:
    """
    Weeks elapsed since the current Combo F episode started.

    Episode start = first F fire after the most recent week where SPX was below
    the 50-week WMA. This correctly counts weeks through the active window even
    though the nightly job writes a new DB row every Friday.
    """
    ep = _combo_f_episode_start(as_of)
    if not ep:
        return None
    as_of_ts = pd.Timestamp(as_of)
    episode_start = pd.Timestamp(ep)
    return max(1, int((as_of_ts - episode_start).days / 7) + 1)


def _combo_c_still_active() -> bool:
    """True when Combo C was previously triggered and the 4-Friday cancel rule has not yet fired."""
    with get_connection() as conn:
        row = conn.execute("SELECT active FROM combo_c_cancel WHERE id=1").fetchone()
    return bool(row and row["active"])


def _combo_c_episode_start(as_of: str) -> str | None:
    """First C fire after the most recent WTI 4wk reading below the 10% entry threshold."""
    as_of_ts = pd.Timestamp(as_of)
    series = load_all_series()
    wti: pd.Series = series.get("WTI")  # type: ignore[assignment]
    if wti is None or wti.empty:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT date FROM combo_fires WHERE runic_combo='C' AND date <= ? ORDER BY date ASC LIMIT 1",
                (as_of,),
            ).fetchall()
        return rows[0]["date"] if rows else None
    hist = wti.loc[:as_of_ts]
    below = hist[hist < 10.0]
    last_below_ts = below.index[-1] if not below.empty else pd.Timestamp("1900-01-01")
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT date FROM combo_fires WHERE runic_combo='C' AND date > ? AND date <= ? ORDER BY date ASC LIMIT 1",
            (last_below_ts.strftime("%Y-%m-%d"), as_of),
        ).fetchall()
    return rows[0]["date"] if rows else None


def _combo_c_weeks(as_of: str) -> int:
    """Weeks since current Combo C episode start (anchored like Combo F)."""
    ep = _combo_c_episode_start(as_of)
    if not ep:
        return 1
    return max(1, int((pd.Timestamp(as_of) - pd.Timestamp(ep)).days / 7) + 1)


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


def detect_all_combos(
    as_of: str | None = None,
    persist: bool = True,
    macro_regime: dict[str, Any] | None = None,
) -> list[ComboFire]:
    as_of = as_of or datetime.now().strftime("%Y-%m-%d")
    readings = get_readings_as_of(as_of)
    if macro_regime is None:
        from src.macro_intelligence.engine.regime_rules import build_python_regime

        macro_regime = build_python_regime(as_of, readings)
    named = detect_named_combos(as_of, readings, macro_regime)
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
    *,
    vix_pctile: float = 85.0,
    hy_pctile: float = 85.0,
) -> bool:
    """Direct evaluation for validation tests (hy_bps in basis points)."""
    return (
        vix >= 25
        and vix_pctile >= 80
        and hy_bps >= 400
        and hy_pctile >= 80
        and cftc_pctile <= 15
    )


def evaluate_combo_f_at_date(
    as_of: str,
    weekly_gain_pct: float,
    cftc_pctile: float,
    above_50wma: bool,
    was_below_prior_week: bool = False,
) -> bool:
    reclaim = above_50wma and (was_below_prior_week or weekly_gain_pct >= 3.0)
    return reclaim and cftc_pctile <= 50
