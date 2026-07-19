"""FM positioning events and X-FM experiments."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from src.macro_intelligence.analysis.regime_experiments.metrics import (
    HORIZONS,
    evidence_tag,
    slice_by_regime,
    summarize_returns,
)
from src.macro_intelligence.db.connection import get_connection
from src.macro_intelligence.engine.forward_returns import compute_forward_returns_for_combo
from src.macro_intelligence.data.yahoo_pull import fetch_yahoo_close


def load_cftc_history() -> pd.DataFrame:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT date, fm_pctile, rm_pctile, fm_net, status FROM cftc_positioning ORDER BY date"
        ).fetchall()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame([dict(r) for r in rows])
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").sort_index()


def load_regime_v2_map() -> dict[str, dict[str, Any]]:
    """Load shadow v2 regimes (populated by backfill_regime_v2)."""
    with get_connection() as conn:
        try:
            rows = conn.execute("SELECT date, regime_json FROM macro_regime_log_v2").fetchall()
        except Exception:
            return {}
    return {r["date"]: json.loads(r["regime_json"]) for r in rows}


def regime_at(reg_map: dict[str, dict[str, Any]], dt: pd.Timestamp) -> dict[str, Any]:
    ds = dt.strftime("%Y-%m-%d")
    if ds in reg_map:
        return reg_map[ds]
    for i in range(1, 8):
        key = (dt - pd.Timedelta(days=i)).strftime("%Y-%m-%d")
        if key in reg_map:
            return reg_map[key]
    return {}


def extract_fm_band_events(
    band: str,
    spx: pd.Series | None = None,
    regime_map: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """band: extreme_short | extreme_long | moderate"""
    df = load_cftc_history()
    if df.empty:
        return []
    if spx is None:
        spx = fetch_yahoo_close("^GSPC", "1990-01-01")
    if regime_map is None:
        regime_map = load_regime_v2_map()

    events: list[dict[str, Any]] = []
    prev_in = False
    for dt, row in df.iterrows():
        fm = row.get("fm_pctile")
        if fm is None or pd.isna(fm):
            continue
        if band == "extreme_short":
            in_band = fm < 15
        elif band == "extreme_long":
            in_band = fm > 85
        else:
            in_band = 25 <= fm <= 75
        if in_band and not prev_in:
            ds = dt.strftime("%Y-%m-%d")
            rets = {}
            for col, days in [
                ("spx_1w", 5),
                ("spx_2w", 10),
                ("spx_1m", 21),
                ("spx_3m", 63),
                ("spx_6m", 126),
            ]:
                from src.macro_intelligence.engine.forward_returns import forward_return_pct

                rets[col] = forward_return_pct(spx, dt, days)
            regime = regime_at(regime_map, dt)
            events.append(
                {
                    "date": ds,
                    "fm_pctile": float(fm),
                    "band": band,
                    "returns": rets,
                    "regime": regime,
                }
            )
        prev_in = in_band
    return events


def run_xfm_experiments() -> dict[str, Any]:
    """X-FM-1 through X-FM-5."""
    out: dict[str, Any] = {"experiments": {}}
    regime_map = load_regime_v2_map()
    spx = fetch_yahoo_close("^GSPC", "1990-01-01")

    for band in ("extreme_short", "extreme_long", "moderate"):
        events = extract_fm_band_events(band, spx=spx, regime_map=regime_map)
        bullish = band != "extreme_long"
        by_horizon = {
            h: summarize_returns([e["returns"].get(h) for e in events], bullish=bullish)
            for h in ["spx_1w", "spx_1m", "spx_3m", "spx_6m"]
        }
        regime_slices = {}
        for key in (
            "fed_cycle_v2",
            "curve_regime_v2",
            "liquidity_v2",
            "val_regime",
            "geo_overlay_v2",
        ):
            regime_slices[key] = slice_by_regime(events, key, "spx_3m", bullish=bullish)
        out["experiments"][f"X-FM-1_{band}"] = {
            "n_crossings": len(events),
            "by_horizon": by_horizon,
            "regime_slices_3m": regime_slices,
            "evidence_tag": evidence_tag(by_horizon.get("spx_3m", {}).get("n") or 0),
            "interpretation": _fm_interpretation(band, by_horizon),
        }

    out["experiments"]["X-FM-2_combo_b"] = _combo_b_instances()
    out["experiments"]["X-FM-3_combo_d"] = _combo_d_instances()
    out["experiments"]["X-FM-5_fm_rm_divergence"] = _fm_rm_divergence(regime_map=regime_map, spx=spx)
    return out


def _fm_interpretation(band: str, by_horizon: dict) -> str:
    h3 = by_horizon.get("spx_3m", {})
    n = h3.get("n") or 0
    hr = h3.get("hit_rate")
    if band == "extreme_short" and n >= 5 and hr and hr > 0.7:
        return "FM extreme short: SPX tends higher at 3m — contrary indicator (supports Combo B washout)."
    if band == "extreme_long" and n >= 5:
        h1 = by_horizon.get("spx_1w", {})
        return f"FM extreme long: 1w SPX down rate {h1.get('hit_rate')}; 3m may degrade."
    if band == "moderate":
        return "Moderate FM band: no strong contrary/trend edge assumed — verify with n."
    return "Insufficient n or mixed results."


def _combo_b_instances() -> dict[str, Any]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT cf.date, cf.status, cf.macro_regime, fr.spx_1w, fr.spx_3m, fr.spx_6m
            FROM combo_fires cf
            JOIN forward_returns fr ON cf.combo_id = fr.combo_id
            WHERE cf.runic_combo = 'B'
            ORDER BY cf.date
            """
        ).fetchall()
    instances = []
    spx_up_3m = 0
    n_3m = 0
    for r in rows:
        reg = json.loads(r["macro_regime"] or "{}")
        up = r["spx_3m"] is not None and r["spx_3m"] > 0
        if r["spx_3m"] is not None:
            n_3m += 1
            spx_up_3m += int(up)
        instances.append(
            {
                "date": r["date"],
                "status": r["status"],
                "spx_3m": r["spx_3m"],
                "fed_cycle_v2": collapse_from_json(reg),
            }
        )
    return {
        "n_fires": len(instances),
        "spx_up_3m_pct": spx_up_3m / n_3m if n_3m else None,
        "n_with_3m": n_3m,
        "instances": instances[:50],
        "evidence_tag": evidence_tag(n_3m, mechanism=True),
    }


def collapse_from_json(reg: dict) -> str:
    from src.macro_intelligence.engine.regime_v2_shadow import (
        collapse_fed_cycle_v2,
        fed_cycle_v2_analytics,
    )

    stored = reg.get("fed_cycle_v2") or collapse_fed_cycle_v2(reg.get("fed_cycle", ""))
    return fed_cycle_v2_analytics(str(stored))


def _combo_d_instances() -> dict[str, Any]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT cf.date, fr.spx_1w, fr.spx_2w, fr.spx_1m, fr.spx_3m
            FROM combo_fires cf
            JOIN forward_returns fr ON cf.combo_id = fr.combo_id
            WHERE cf.runic_combo = 'D'
            ORDER BY cf.date
            """
        ).fetchall()
    rets_1w = [r["spx_1w"] for r in rows if r["spx_1w"] is not None]
    rets_3m = [r["spx_3m"] for r in rows if r["spx_3m"] is not None]
    return {
        "n_fires": len(rows),
        "short_horizon_1w": summarize_returns(rets_1w, bullish=False),
        "long_horizon_3m": summarize_returns(rets_3m, bullish=False),
    }


def _fm_rm_divergence(
    regime_map: dict[str, dict[str, Any]] | None = None,
    spx: pd.Series | None = None,
) -> dict[str, Any]:
    df = load_cftc_history()
    if df.empty:
        return {}
    if spx is None:
        spx = fetch_yahoo_close("^GSPC", "1990-01-01")
    if regime_map is None:
        regime_map = load_regime_v2_map()
    squeeze: list[dict] = []
    liq_exit: list[dict] = []
    for dt, row in df.iterrows():
        fm, rm = row.get("fm_pctile"), row.get("rm_pctile")
        if fm is None or rm is None:
            continue
        ds = dt.strftime("%Y-%m-%d")
        from src.macro_intelligence.engine.forward_returns import forward_return_pct

        ret3 = forward_return_pct(spx, dt, 63)
        reg = regime_at(regime_map, dt)
        if fm < 30 and rm > 50:
            squeeze.append({"date": ds, "spx_3m": ret3, "regime": reg})
        if rm < 30 and fm > 60:
            liq_exit.append({"date": ds, "spx_3m": ret3, "regime": reg})
    return {
        "SQUEEZE_fm_low_rm_high": {
            "n": len(squeeze),
            "overall_3m": summarize_returns([x["spx_3m"] for x in squeeze]),
            "by_fed_cycle_v2": slice_by_regime(squeeze, "fed_cycle_v2"),
        },
        "LIQUIDITY_EXIT_rm_low_fm_high": {
            "n": len(liq_exit),
            "overall_3m": summarize_returns([x["spx_3m"] for x in liq_exit]),
            "by_fed_cycle_v2": slice_by_regime(liq_exit, "fed_cycle_v2"),
        },
    }
