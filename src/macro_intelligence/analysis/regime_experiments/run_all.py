"""All Part A–I experiment runners."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from src.macro_intelligence.analysis.regime_experiments.fm_events import run_xfm_experiments
from src.macro_intelligence.analysis.regime_experiments.metrics import (
    probability_weighted_summary,
    summarize_returns,
)
from src.macro_intelligence.analysis.regime_experiments.shadow_backfill import (
    backfill_emission_vectors,
    backfill_regime_v2,
    regime_label_distribution,
)
from src.macro_intelligence.config import load_config
from src.macro_intelligence.data.fred_pull import fetch_fred_series
from src.macro_intelligence.data.yahoo_pull import fetch_yahoo_close, spx_with_50wma
from src.macro_intelligence.db.connection import get_connection
from src.macro_intelligence.engine.combo_cancel_probability import (
    combo_c_total_cancel_prob,
    combo_cancel_probability_wti,
)
from src.macro_intelligence.engine.forward_returns import forward_return_pct
from src.macro_intelligence.engine.regime_v2_shadow import (
    build_regime_v2,
    clear_regime_v2_caches,
    twy_roc_at_date,
)


OUTPUT_DIR = Path("macro_intelligence/analysis/regime_v2_experiments")


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _write(name: str, payload: dict[str, Any]) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{name}.json"
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path


def run_part_a() -> dict[str, Any]:
    _log("Part A: backfill shadow v2 regimes...")
    n = backfill_regime_v2("1990-01-01")
    dist = regime_label_distribution()
    dims = dist.get("dimensions", {})
    fed_dist = dims.get("fed_cycle_v2", {})
    total_fed = sum(fed_dist.values()) or 1
    pass_a1 = all(c >= 30 for c in fed_dist.values()) and max(fed_dist.values()) / total_fed <= 0.8
    payload = {
        "A1_fed_cycle_v2_distribution": fed_dist,
        "A2_geo_overlay_v2_distribution": dims.get("geo_overlay_v2"),
        "A3_liquidity_v2_distribution": dims.get("liquidity_v2"),
        "A4_val_regime_distribution": dims.get("val_regime", {}),
        "A4_cape_velocity": _run_a4_cape_velocity(),
        "A5_fiscal_caveat": _run_a5_fiscal_caveat(),
        "n_fridays_backfilled": n,
        "A1_pass_no_degenerate_dominance": pass_a1,
        "A1_notes": "PIVOTING n=27 may fail ≥30 obs threshold; no state >80% dominance",
    }
    _write("A_regime_dimensions", payload)
    return payload


def _run_a4_cape_velocity() -> dict[str, Any]:
    """Compare CAPE level extreme vs fresh crossing vs 6m rank change on SPX 3m/6m."""
    spx = fetch_yahoo_close("^GSPC", "2010-01-01")
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT date, unconditional_pctile FROM daily_readings
            WHERE var_id='CAPE' AND date >= '2010-01-01'
            ORDER BY date
            """
        ).fetchall()
    if not rows:
        return {"status": "SKIPPED", "reason": "no CAPE readings"}
    df = pd.DataFrame([{"date": pd.Timestamp(r["date"]), "pctile": r["unconditional_pctile"]} for r in rows])
    df = df.set_index("date").sort_index()
    df["pctile_6m_ago"] = df["pctile"].shift(126)
    df["rank_delta_6m"] = df["pctile"] - df["pctile_6m_ago"]
    df["prev_pctile"] = df["pctile"].shift(1)

    level_extreme_rets_3m: list[float] = []
    fresh_cross_rets_3m: list[float] = []
    velocity_rets_3m: list[float] = []
    for dt, row in df.iterrows():
        p, prev = row["pctile"], row["prev_pctile"]
        if p is None or pd.isna(p):
            continue
        ret3 = forward_return_pct(spx, dt, 63)
        ret6 = forward_return_pct(spx, dt, 126)
        if ret3 is None:
            continue
        if p >= 0.90:
            level_extreme_rets_3m.append(ret3)
        if p >= 0.90 and prev is not None and prev < 0.90:
            fresh_cross_rets_3m.append(ret3)
        rd = row.get("rank_delta_6m")
        if rd is not None and not pd.isna(rd) and rd >= 0.10:
            velocity_rets_3m.append(ret3)

    s_level = summarize_returns(level_extreme_rets_3m)
    s_fresh = summarize_returns(fresh_cross_rets_3m)
    s_vel = summarize_returns(velocity_rets_3m)
    winner = max(
        [("level_extreme", s_level.get("avg") or -999), ("fresh_cross", s_fresh.get("avg") or -999), ("velocity_6m", s_vel.get("avg") or -999)],
        key=lambda x: x[1],
    )[0]
    return {
        "level_extreme_3m": s_level,
        "fresh_cross_into_extreme_3m": s_fresh,
        "velocity_rank_delta_6m_3m": s_vel,
        "winner_3m_avg_return": winner,
    }


def _run_a5_fiscal_caveat() -> dict[str, Any]:
    """Split inverted episodes by fiscal deficit proxy (FYFSD/GDP if available)."""
    try:
        deficit = fetch_fred_series("FYFSD", "1990-01-01")
    except Exception as exc:
        return {"status": "SKIPPED", "reason": str(exc)}
    curve = fetch_fred_series("T10Y2Y", "1990-01-01")
    spx = fetch_yahoo_close("^GSPC", "1990-01-01")
    weekly_curve = curve.resample("W-FRI").last().dropna()
    episodes: list[dict[str, Any]] = []
    in_inv = False
    start = None
    for dt, val in weekly_curve.items():
        if val < 0 and not in_inv:
            in_inv = True
            start = dt
        elif val >= 0 and in_inv and start is not None:
            def_at = deficit.loc[:dt].dropna()
            def_pct = float(def_at.iloc[-1]) if not def_at.empty else None
            ret = forward_return_pct(spx, dt, 63)
            episodes.append(
                {
                    "start": start.strftime("%Y-%m-%d"),
                    "end": dt.strftime("%Y-%m-%d"),
                    "fiscal_deficit_pct_gdp": def_pct,
                    "fiscal_offset": def_pct is not None and def_pct > 5.0,
                    "spx_3m_at_uninvert": ret,
                }
            )
            in_inv = False
            start = None
    high = [e for e in episodes if e.get("fiscal_offset")]
    low = [e for e in episodes if not e.get("fiscal_offset")]
    return {
        "n_episodes": len(episodes),
        "fiscal_offset_bucket": summarize_returns([e["spx_3m_at_uninvert"] for e in high if e["spx_3m_at_uninvert"] is not None]),
        "no_offset_bucket": summarize_returns([e["spx_3m_at_uninvert"] for e in low if e["spx_3m_at_uninvert"] is not None]),
        "note": "2022-23 invert may cluster in fiscal_offset bucket",
    }


def run_part_b() -> dict[str, Any]:
    _log("Part B: TWY_ROC + percentiles...")
    anchor = twy_roc_at_date("2025-04-07")
    anchor_alt = twy_roc_at_date("2025-04-04")
    with get_connection() as conn:
        fallback_rows = conn.execute(
            "SELECT COUNT(*) AS c FROM daily_readings WHERE unconditional_pctile IS NOT NULL AND regime_pctile IS NULL"
        ).fetchone()
        dual_rows = conn.execute(
            "SELECT COUNT(*) AS c FROM daily_readings WHERE unconditional_pctile IS NOT NULL AND regime_pctile IS NOT NULL"
        ).fetchone()
    n_em = backfill_emission_vectors("2010-01-01")
    payload = {
        "B1_B2_twy_roc_apr2025": {"2025-04-07": anchor, "2025-04-04": anchor_alt},
        "B2_validation": {
            "expected_dovish_bps": "65-75 over 8 weeks",
            "observed_pp": anchor.get("twy_roc_pp"),
            "direction": anchor.get("direction"),
            "pass_dovish": anchor.get("twy_roc_pp") is not None and anchor["twy_roc_pp"] < -0.30,
        },
        "B3_dual_percentile": {
            "rows_with_unconditional_only": fallback_rows["c"] if fallback_rows else 0,
            "rows_with_both": dual_rows["c"] if dual_rows else 0,
        },
        "B4_window_audit": _run_b4_window_audit(),
        "B5_cape_triple_storage": _run_b5_cape_sweep(),
        "C1_emission_vectors_backfilled": n_em,
    }
    _write("B_twy_and_percentiles", payload)
    return payload


def _run_b4_window_audit() -> dict[str, Any]:
    cfg = load_config()
    vars_cfg = cfg.get("variables", [])
    if isinstance(vars_cfg, dict):
        var_list = list(vars_cfg.items())
    else:
        var_list = [(v.get("id"), v) for v in vars_cfg if isinstance(v, dict)]
    mismatches = []
    structural = {"CAPE", "NFCI", "WALCL", "CURVE", "DXY"}
    for var_id, vcfg in var_list:
        if not var_id:
            continue
        window = vcfg.get("pctile_window", "rolling_3y")
        expected = "full" if var_id in structural else "rolling_3y"
        if window != expected:
            mismatches.append({"var_id": var_id, "configured": window, "expected": expected})
    return {"n_vars": len(var_list), "mismatches": mismatches, "pass": len(mismatches) == 0}


def _run_b5_cape_sweep() -> dict[str, Any]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT cf.date, fr.spx_6m, dr.unconditional_pctile AS cape_pctile
            FROM combo_fires cf
            JOIN forward_returns fr ON cf.combo_id = fr.combo_id
            LEFT JOIN daily_readings dr ON dr.date = cf.date AND dr.var_id = 'CAPE'
            WHERE cf.runic_combo = 'E' AND fr.spx_6m IS NOT NULL
            """
        ).fetchall()
    level_rets = [r["spx_6m"] for r in rows if r["cape_pctile"] and r["cape_pctile"] > 0.9]
    moderate_rets = [r["spx_6m"] for r in rows if r["cape_pctile"] and 0.5 <= r["cape_pctile"] <= 0.9]
    return {
        "combo_e_high_cape_6m": summarize_returns(level_rets),
        "combo_e_moderate_cape_6m": summarize_returns(moderate_rets),
        "winner": "level_extreme" if (summarize_returns(level_rets).get("avg") or 0) > (summarize_returns(moderate_rets).get("avg") or 0) else "moderate",
    }


def run_part_c() -> dict[str, Any]:
    _log("Part C: emission / sub-threshold...")
    spx = fetch_yahoo_close("^GSPC", "2010-01-01")
    with get_connection() as conn:
        vix_rows = conn.execute(
            """
            SELECT date, unconditional_pctile FROM daily_readings
            WHERE var_id='VIX' AND unconditional_pctile BETWEEN 0.65 AND 0.79
            AND date >= '2010-01-01'
            """
        ).fetchall()
    sub_thresh_rets = []
    for r in vix_rows:
        dt = pd.Timestamp(r["date"])
        ret = forward_return_pct(spx, dt, 63)
        if ret is not None:
            sub_thresh_rets.append(ret)
    with get_connection() as conn:
        all_fri = conn.execute(
            "SELECT DISTINCT date FROM daily_readings WHERE var_id='VIX' ORDER BY date"
        ).fetchall()
    random_rets = []
    for r in all_fri[::4][:200]:
        ret = forward_return_pct(spx, pd.Timestamp(r["date"]), 63)
        if ret is not None:
            random_rets.append(ret)
    payload = {
        "C2_sub_threshold_vix_65_79": summarize_returns(sub_thresh_rets),
        "C2_random_friday_3m_baseline": summarize_returns(random_rets),
        "C2_edge_delta_avg": (summarize_returns(sub_thresh_rets).get("avg") or 0)
        - (summarize_returns(random_rets).get("avg") or 0),
        "C3_binary_vs_vector": _run_c3_binary_vs_vector(spx),
    }
    _write("C_emission", payload)
    return payload


def _run_c3_binary_vs_vector(spx: pd.Series) -> dict[str, Any]:
    """First RARE binary cross vs mean emission vector threshold."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT date, var_id, unconditional_pctile FROM daily_readings
            WHERE date >= '2010-01-01' AND unconditional_pctile IS NOT NULL
            ORDER BY date
            """
        ).fetchall()
    by_date: dict[str, list[float]] = {}
    rare_first: dict[str, str] = {}
    for r in rows:
        d, vid, p = r["date"], r["var_id"], r["unconditional_pctile"]
        by_date.setdefault(d, []).append(float(p))
        if p >= 0.80 and d not in rare_first:
            rare_first[d] = vid
    vector_first: dict[str, str] = {}
    for d, vals in by_date.items():
        if sum(vals) / len(vals) >= 0.75:
            vector_first[d] = "mean>=0.75"
    rare_dates = sorted(rare_first.keys())
    vector_dates = sorted(vector_first.keys())
    return {
        "first_rare_binary_count": len(rare_dates),
        "first_vector_mean_count": len(vector_dates),
        "median_lag_days_binary_minus_vector": _median_lag_days(rare_dates, vector_dates),
    }


def _median_lag_days(a: list[str], b: list[str]) -> float | None:
    if not a or not b:
        return None
    lags = []
    for i, da in enumerate(a[:100]):
        db = b[i] if i < len(b) else b[-1]
        lags.append((pd.Timestamp(da) - pd.Timestamp(db)).days)
    return float(pd.Series(lags).median()) if lags else None


def run_part_e() -> dict[str, Any]:
    _log("Part E: cancel probability...")
    wti = fetch_yahoo_close("CL=F", "2020-01-01")
    current = float(wti.dropna().iloc[-1]) if not wti.empty else 70.0
    wti_res = combo_cancel_probability_wti(current)
    total = combo_c_total_cancel_prob(wti_res, cpi_not_hot_rate=0.52)
    payload = {
        "E1_combo_c_cancel": total,
        "E2_combo_c_calibration": _run_e2_calibration(),
        "E3_note": "Combo D/F/G formulas documented in report",
    }
    _write("E_cancel_probability", payload)
    return payload


def _run_e2_calibration() -> dict[str, Any]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT cf.date, cf.status
            FROM combo_fires cf
            WHERE cf.runic_combo = 'C'
            ORDER BY cf.date
            """
        ).fetchall()
    if not rows:
        return {"n": 0, "note": "no Combo C fires in DB"}
    cancelled = sum(1 for r in rows if (r["status"] or "").upper() in ("CANCELLED", "CANCELED"))
    return {
        "n_episodes": len(rows),
        "realized_cancel_rate": cancelled / len(rows),
        "predicted_example": combo_c_total_cancel_prob(
            combo_cancel_probability_wti(70.0), cpi_not_hot_rate=0.52
        ).get("combined_cancel_prob"),
    }


def run_part_f() -> dict[str, Any]:
    _log("Part F: quant regime grid...")
    oct22 = build_regime_v2("2022-10-13")
    f4_grid = []
    curve = fetch_fred_series("T10Y2Y", "1990-01-01")
    spx = fetch_yahoo_close("^GSPC", "1990-01-01")
    for trough_thresh in (-0.50, -0.80):
        for steep_thresh in (15, 40):
            events = _steepening_short_events(curve, spx, trough_thresh * 100, steep_thresh)
            rets = [e["spx_3m"] for e in events if e.get("spx_3m") is not None]
            f4_grid.append(
                {
                    "trough_bps": trough_thresh * 100,
                    "steepen_4wk_bps": steep_thresh,
                    "n": len(events),
                    "spx_3m": summarize_returns(rets, bullish=False),
                    "spx_3m_pw": probability_weighted_summary(
                        rets, bullish=False, horizon="spx_3m"
                    ),
                    "instances": [
                        {
                            "date": e["date"],
                            "spx_3m": e.get("spx_3m"),
                        }
                        for e in events
                    ],
                }
            )
    payload = {
        "F1_oct2022": oct22,
        "F1_tightening_late": oct22.get("tightening_late_f1"),
        "F4_steepening_short_grid": f4_grid,
        "F4_mechanism_analogs": ["2000", "2007", "2022-23 failure (fiscal/AI offset)"],
    }
    _write("F_quant_regime", payload)
    return payload


def _steepening_short_events(
    curve: pd.Series,
    spx: pd.Series,
    trough_bps: float,
    steep_bps: float,
) -> list[dict]:
    weekly = curve.resample("W-FRI").last().dropna()
    events = []
    in_inverted = False
    trough = 0.0
    for i in range(4, len(weekly)):
        window = weekly.iloc[i - 4 : i + 1]
        if (window < 0).all():
            in_inverted = True
            trough = min(trough, float(window.min()))
        if not in_inverted:
            continue
        if trough * 100 > trough_bps:
            continue
        chg = (float(window.iloc[-1]) - float(window.iloc[0])) * 100
        if chg >= steep_bps:
            dt = weekly.index[i]
            ret = forward_return_pct(spx, dt, 63)
            events.append({"date": dt.strftime("%Y-%m-%d"), "spx_3m": ret})
            in_inverted = False
            trough = 0.0
    return events


def run_part_g() -> dict[str, Any]:
    _log("Part G: persistence...")
    spx_w = spx_with_50wma()
    grind_dates = []
    for i in range(7, len(spx_w)):
        rets = spx_w["weekly_ret_pct"].iloc[i - 7 : i]
        if (rets > 0.5).all():
            grind_dates.append(spx_w.index[i])
    spx = fetch_yahoo_close("^GSPC", "1990-01-01")
    grind_6m = [forward_return_pct(spx, d, 126) for d in grind_dates]
    grind_6m = [r for r in grind_6m if r is not None]

    vix = fetch_yahoo_close("^VIX", "1990-01-01")
    vix_supp = []
    for i in range(10, len(vix)):
        if (vix.iloc[i - 10 : i] < 15).all():
            vix_supp.append(vix.index[i])
    lead_days = []
    for d in vix_supp:
        future = vix.loc[d : d + pd.Timedelta(days=60)]
        hit = future[future > 25]
        if not hit.empty:
            lead_days.append((hit.index[0] - d).days)
    payload = {
        "G1_seven_week_grind": {
            "n": len(grind_dates),
            "spx_6m": summarize_returns(grind_6m),
            "standalone_short_ok": (summarize_returns(grind_6m).get("hit_rate") or 0) > 0.5,
        },
        "G2_vix_suppressed": {
            "n": len(vix_supp),
            "median_days_to_vix25": float(pd.Series(lead_days).median()) if lead_days else None,
            "lead_rate": len(lead_days) / len(vix_supp) if vix_supp else None,
        },
    }
    _write("G_persistence", payload)
    return payload


def run_named_combo_regime_slices() -> dict[str, Any]:
    out = {}
    with get_connection() as conn:
        for combo in ("A", "B", "C", "D", "E", "F", "G"):
            rows = conn.execute(
                """
                SELECT cf.macro_regime, fr.spx_3m
                FROM combo_fires cf
                JOIN forward_returns fr ON cf.combo_id = fr.combo_id
                WHERE cf.runic_combo = ? AND fr.spx_3m IS NOT NULL
                """,
                (combo,),
            ).fetchall()
            bullish = combo in ("B", "F")
            rets = [r["spx_3m"] for r in rows]
            by_fed: dict[str, list] = {}
            for r in rows:
                reg = json.loads(r["macro_regime"] or "{}")
                fc = reg.get("fed_cycle", "UNK")
                by_fed.setdefault(fc, []).append(r["spx_3m"])
            out[combo] = {
                "overall_3m": summarize_returns(rets, bullish=bullish),
                "by_fed_cycle_legacy": {k: summarize_returns(v, bullish=bullish) for k, v in by_fed.items()},
            }
    _write("X_COMBO_regime_slices", out)
    return out


def run_part_d_hmm() -> dict[str, Any]:
    from src.macro_intelligence.analysis.regime_experiments.hmm_prototype import run_hmm_prototype
    from src.macro_intelligence.analysis.regime_experiments.regime_backtest import run_regime_backtest

    payload = run_hmm_prototype()
    payload["regime_backtest"] = run_regime_backtest()
    _write("D_hmm_prototype", payload)
    return payload


def run_all_experiments() -> dict[str, Any]:
    clear_regime_v2_caches()
    manifest = {
        "run_date": pd.Timestamp.now().strftime("%Y-%m-%d"),
        "artifacts": {},
    }
    manifest["part_a"] = run_part_a()
    manifest["part_b"] = run_part_b()
    manifest["part_c"] = run_part_c()
    manifest["part_e"] = run_part_e()
    manifest["part_f"] = run_part_f()
    manifest["part_g"] = run_part_g()
    _log("X-FM track...")
    manifest["xfm"] = run_xfm_experiments()
    _log("Named combo regime slices...")
    manifest["combo_regime_slices"] = run_named_combo_regime_slices()
    _log("Part D HMM prototype...")
    manifest["part_d"] = run_part_d_hmm()
    _write("X-FM_all", manifest["xfm"])
    path = _write("experiment_manifest", manifest)
    manifest["manifest_path"] = str(path)
    return manifest
