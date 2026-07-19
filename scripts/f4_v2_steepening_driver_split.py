#!/usr/bin/env python3
"""F4 v2 — split steepening-of-inversion by yield driver (D3 spec).

Classifies −50/+15 steepening episodes by DGS2/DGS10 4-week yield moves,
tags HY OAS widening and ICSA claims momentum at fire date, and reports
SPX 3m/6m vs unconditional rolling-window benchmark.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from src.macro_intelligence.analysis.regime_experiments.metrics import (
    probability_weighted_summary,
    summarize_returns,
)
from src.macro_intelligence.data.fred_pull import fetch_dgs10, fetch_dgs2, fetch_fred_series
from src.macro_intelligence.data.yahoo_pull import fetch_yahoo_close
from src.macro_intelligence.engine.forward_returns import forward_return_pct

OUTPUT = Path("macro_intelligence/analysis/regime_v2_experiments/F4_v2_steepening_driver_split.json")
TROUGH_BPS = -50.0
STEEPEN_BPS = 15.0


def _weekly_fri(series: pd.Series) -> pd.Series:
    return series.sort_index().resample("W-FRI").last().dropna()


def _yield_4wk_change_pp(yields: pd.Series, end_date: pd.Timestamp) -> float | None:
    """4-week yield change in percentage points on weekly Friday grid."""
    weekly = _weekly_fri(yields)
    end_date = pd.Timestamp(end_date)
    loc = weekly.index.searchsorted(end_date, side="right") - 1
    if loc < 4 or loc < 0:
        return None
    return float(weekly.iloc[loc] - weekly.iloc[loc - 4])


def _series_4wk_change(series: pd.Series, end_date: pd.Timestamp) -> float | None:
    weekly = _weekly_fri(series)
    end_date = pd.Timestamp(end_date)
    loc = weekly.index.searchsorted(end_date, side="right") - 1
    if loc < 4 or loc < 0:
        return None
    return float(weekly.iloc[loc] - weekly.iloc[loc - 4])


def classify_steepening_driver(dgs2_chg: float, dgs10_chg: float) -> str:
    if dgs2_chg < 0 and dgs10_chg < 0:
        return "BULL"
    if dgs2_chg > 0 and dgs10_chg > 0:
        return "BEAR"
    if dgs2_chg < 0 and dgs10_chg > 0:
        return "TWIST"
    return "OTHER"


def steepening_short_events(
    curve: pd.Series,
    spx: pd.Series,
    trough_bps: float,
    steep_bps: float,
) -> list[dict[str, Any]]:
    weekly = curve.resample("W-FRI").last().dropna()
    events: list[dict[str, Any]] = []
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
            events.append(
                {
                    "date": dt.strftime("%Y-%m-%d"),
                    "trough_bps": round(trough * 100, 2),
                    "steepen_4wk_bps": round(chg, 2),
                    "spx_3m": forward_return_pct(spx, dt, 63),
                    "spx_6m": forward_return_pct(spx, dt, 126),
                }
            )
            in_inverted = False
            trough = 0.0
    return events


def unconditional_down_rate(
    spx: pd.Series,
    trading_days: int,
    start: str = "1990-01-01",
) -> dict[str, Any]:
    """% of all weekly Fridays with negative SPX forward return (edge-vs-baseline)."""
    spx = spx.sort_index()
    spx = spx[spx.index >= pd.Timestamp(start)]
    weekly_dates = spx.resample("W-FRI").last().dropna().index
    rets: list[float] = []
    for dt in weekly_dates:
        r = forward_return_pct(spx, dt, trading_days)
        if r is not None:
            rets.append(r)
    if not rets:
        return {"n": 0, "pct_spx_down": None, "avg_return": None}
    down = sum(1 for r in rets if r < 0)
    return {
        "n": len(rets),
        "pct_spx_down": down / len(rets),
        "avg_return": float(sum(rets) / len(rets)),
    }


def _horizon_block(
    rets: list[float],
    bullish: bool,
    horizon_key: str,
    unconditional_down_pct: float | None,
) -> dict[str, Any]:
    summary = summarize_returns(rets, bullish=bullish)
    pw = probability_weighted_summary(rets, bullish=bullish, horizon=horizon_key)
    hit = summary.get("hit_rate")
    return {
        **summary,
        "pw": pw,
        "unconditional_pct_spx_down": unconditional_down_pct,
        "edge_vs_baseline_pp": (
            (hit - unconditional_down_pct) * 100 if hit is not None and unconditional_down_pct is not None else None
        ),
    }


def enrich_episode(
    event: dict[str, Any],
    dgs2: pd.Series,
    dgs10: pd.Series,
    hy: pd.Series,
    icsa: pd.Series,
) -> dict[str, Any]:
    dt = pd.Timestamp(event["date"])
    d2 = _yield_4wk_change_pp(dgs2, dt)
    d10 = _yield_4wk_change_pp(dgs10, dt)
    driver = classify_steepening_driver(d2, d10) if d2 is not None and d10 is not None else "UNKNOWN"
    hy_chg = _series_4wk_change(hy, dt)
    icsa_chg = _series_4wk_change(icsa, dt)
    hy_widening = hy_chg > 0 if hy_chg is not None else None
    claims_rising = icsa_chg > 0 if icsa_chg is not None else None
    return {
        **event,
        "driver": driver,
        "dgs2_4wk_chg_pp": d2,
        "dgs10_4wk_chg_pp": d10,
        "hy_oas_4wk_chg_bps": round(hy_chg * 100, 2) if hy_chg is not None else None,
        "hy_widening": hy_widening,
        "icsa_4wk_chg": round(icsa_chg, 1) if icsa_chg is not None else None,
        "claims_rising": claims_rising,
        "bearish_bucket": driver == "BULL" and hy_widening is True,
    }


def run_f4_v2() -> dict[str, Any]:
    curve = fetch_fred_series("T10Y2Y", "1990-01-01")
    spx = fetch_yahoo_close("^GSPC", "1990-01-01")
    dgs2 = fetch_dgs2("1990-01-01")
    dgs10 = fetch_dgs10("1990-01-01")
    hy = fetch_fred_series("BAMLH0A0HYM2", "1996-01-01")
    icsa = fetch_fred_series("ICSA", "1990-01-01")

    events = steepening_short_events(curve, spx, TROUGH_BPS, STEEPEN_BPS)
    enriched = [enrich_episode(e, dgs2, dgs10, hy, icsa) for e in events]

    bench_3m = unconditional_down_rate(spx, 63)
    bench_6m = unconditional_down_rate(spx, 126)

    by_driver: dict[str, list[dict]] = {}
    for ep in enriched:
        by_driver.setdefault(ep["driver"], []).append(ep)

    bearish_eps = [e for e in enriched if e["bearish_bucket"]]
    other_eps = [e for e in enriched if not e["bearish_bucket"]]

    def bucket_stats(eps: list[dict], horizon: str, days: int) -> dict[str, Any]:
        key = f"spx_{horizon}"
        rets = [e[key] for e in eps if e.get(key) is not None]
        bench = bench_3m if horizon == "3m" else bench_6m
        return _horizon_block(rets, bullish=False, horizon_key=f"spx_{horizon}", unconditional_down_pct=bench["pct_spx_down"])

    payload: dict[str, Any] = {
        "spec": "D3 F4 v2 — steepening driver split (−50/+15 cell)",
        "cell": {"trough_bps": TROUGH_BPS, "steepen_4wk_bps": STEEPEN_BPS},
        "n_episodes": len(enriched),
        "unconditional_benchmark": {
            "spx_3m": bench_3m,
            "spx_6m": bench_6m,
        },
        "episodes": enriched,
        "by_driver": {
            driver: {
                "n": len(eps),
                "episodes": [e["date"] for e in eps],
                "spx_3m": bucket_stats(eps, "3m", 63),
                "spx_6m": bucket_stats(eps, "6m", 126),
            }
            for driver, eps in sorted(by_driver.items())
        },
        "hypothesis_buckets": {
            "bull_steepening_plus_hy_widening": {
                "label": "BULL steepening + HY widening (2000/2007-type)",
                "n": len(bearish_eps),
                "dates": [e["date"] for e in bearish_eps],
                "spx_3m": bucket_stats(bearish_eps, "3m", 63),
                "spx_6m": bucket_stats(bearish_eps, "6m", 126),
            },
            "everything_else": {
                "n": len(other_eps),
                "spx_3m": bucket_stats(other_eps, "3m", 63),
                "spx_6m": bucket_stats(other_eps, "6m", 126),
            },
        },
        "verdict": None,
    }

    bear = payload["hypothesis_buckets"]["bull_steepening_plus_hy_widening"]
    rest = payload["hypothesis_buckets"]["everything_else"]
    bear_hr = (bear["spx_3m"] or {}).get("hit_rate")
    rest_hr = (rest["spx_3m"] or {}).get("hit_rate")
    if bear["n"] < 3:
        payload["verdict"] = "INSUFFICIENT_N — mechanism+analog only; split inconclusive for statistical gate"
    elif bear_hr is not None and rest_hr is not None and bear_hr > rest_hr + 0.15:
        payload["verdict"] = "SPLIT_WORKS — bearish bucket separates from rest at 3m"
    elif bear_hr is not None and rest_hr is not None and bear_hr <= rest_hr:
        payload["verdict"] = "PARK_F4 — split does not separate cleanly; steepening short gate = NO"
    else:
        payload["verdict"] = "INCONCLUSIVE — review episode table"

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return payload


def main() -> int:
    payload = run_f4_v2()
    print(json.dumps(payload, indent=2, default=str))
    print(f"\nWrote {OUTPUT}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
