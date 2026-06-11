"""Test 7: DBMF 21d beta threshold study with percentile ranking and regression."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.sentiment_superindex.analysis.forward_metrics import load_spx, returns_at_horizons, summarize_returns
from src.sentiment_superindex.analysis.report_utils import metrics_table, save_artifact, write_md_snippet
from src.sentiment_superindex.data.yahoo_inputs import dbmf_beta_vs_spy


def _rolling_pctile_3yr(series: pd.Series, window_weeks: int = 156) -> pd.Series:
    """3-year rolling percentile rank for each observation."""
    out = {}
    for dt in series.index:
        cutoff = dt - pd.DateOffset(weeks=window_weeks)
        window = series.loc[cutoff:dt].dropna()
        if len(window) < 10:
            continue
        val = float(series.loc[dt])
        pctile = float((window < val).sum() / len(window) * 100)
        out[dt] = round(pctile, 1)
    return pd.Series(out).sort_index()


def _ols_regression(beta: pd.Series, fwd_returns: pd.Series) -> dict[str, Any]:
    """OLS regression of beta vs forward returns. Returns R², p-value, slope."""
    aligned = pd.DataFrame({"beta": beta, "fwd": fwd_returns}).dropna()
    if len(aligned) < 30:
        return {"n": len(aligned), "r2": None, "p_value": None, "slope": None}
    try:
        from scipy.stats import linregress
        slope, intercept, r, p, se = linregress(aligned["beta"], aligned["fwd"])
        return {"n": len(aligned), "r2": round(r**2, 4), "p_value": round(p, 4),
                "slope": round(slope, 4), "intercept": round(intercept, 4)}
    except ImportError:
        # Fallback: manual OLS
        x = aligned["beta"].values
        y = aligned["fwd"].values
        x_mean, y_mean = x.mean(), y.mean()
        ss_xy = ((x - x_mean) * (y - y_mean)).sum()
        ss_xx = ((x - x_mean) ** 2).sum()
        ss_yy = ((y - y_mean) ** 2).sum()
        slope = ss_xy / ss_xx if ss_xx > 1e-12 else 0
        r2 = (ss_xy ** 2) / (ss_xx * ss_yy) if ss_xx * ss_yy > 1e-12 else 0
        return {"n": len(aligned), "r2": round(r2, 4), "p_value": None, "slope": round(slope, 4)}


def run_and_report(start: str = "2019-01-01") -> dict[str, Any]:
    beta = dbmf_beta_vs_spy(21, start)
    spx = load_spx(start)
    thresholds = [-0.05, -0.10, -0.15, -0.20]
    rows: list[dict[str, Any]] = []
    prev = beta.shift(1)

    # 3-year rolling percentile of beta (low pctile = beta very negative = CTAs short equities)
    beta_pctile = _rolling_pctile_3yr(beta)

    # Cross-threshold entry analysis
    _h = {"1w": 5, "2w": 10, "4w": 20, "8w": 40}
    for thr in thresholds:
        mask = (beta < thr) & (prev >= thr)
        dates = beta.index[mask.fillna(False)]
        ret_rows = returns_at_horizons(spx, dates, horizons=_h)
        metrics = summarize_returns(ret_rows, horizons=_h)
        # Percentile rank at each fire date
        pctiles_at_fire = beta_pctile.reindex(dates, method="nearest").dropna()
        avg_pctile = round(float(pctiles_at_fire.mean()), 1) if not pctiles_at_fire.empty else None
        direction = "SHORT_EQUITIES" if thr < 0 else "NEUTRAL"
        rows.append({
            "beta_threshold": thr,
            "n_crossings": len(dates),
            "direction": direction,
            "avg_pctile_3yr_at_fire": avg_pctile,
            "metrics": metrics,
        })

    # OLS regression: beta vs SPX forward returns at each horizon
    regression = {}
    for label, days in _h.items():
        fwd = spx.pct_change(days).shift(-days) * 100
        fwd.index = pd.to_datetime(fwd.index).tz_localize(None)
        beta_aligned = beta.copy()
        beta_aligned.index = pd.to_datetime(beta_aligned.index).tz_localize(None)
        regression[label] = _ols_regression(beta_aligned, fwd)

    # Granger causality test
    granger_p = None
    try:
        from statsmodels.tsa.stattools import grangercausalitytests
        aligned = pd.DataFrame({"beta": beta, "spy_ret": spx.pct_change()}).dropna().loc[start:]
        if len(aligned) > 100:
            gc = grangercausalitytests(aligned[["spy_ret", "beta"]], maxlag=4, verbose=False)
            granger_p = {f"lag_{k}": round(gc[k + 1][0]["ssr_ftest"][1], 4) for k in range(4)}
    except Exception:
        granger_p = {"note": "statsmodels unavailable or insufficient data"}

    # Current beta and its percentile
    current_beta = round(float(beta.iloc[-1]), 4) if not beta.empty else None
    current_pctile = round(float(beta_pctile.iloc[-1]), 1) if not beta_pctile.empty else None

    payload = {
        "test_id": "07_dbmf_beta",
        "rows": rows,
        "regression": regression,
        "granger_p": granger_p,
        "current_state": {
            "beta": current_beta,
            "pctile_3yr": current_pctile,
            "direction": "SHORT_EQUITIES" if (current_beta or 0) < -0.10 else
                         "MILD_SHORT" if (current_beta or 0) < -0.05 else "NEUTRAL",
        },
    }
    save_artifact("07_dbmf_beta", payload)

    md = "# Test 7: DBMF 21-day Rolling Beta\n\n"
    md += f"## Current State\n- Beta: {current_beta}  |  3yr Percentile: {current_pctile}th\n"
    md += f"- Direction: {payload['current_state']['direction']}\n\n"
    md += "## Cross-Threshold Analysis\n"
    for r in rows:
        md += (f"\n### Beta crosses below {r['beta_threshold']} "
               f"(n={r['n_crossings']}, avg 3yr pctile at fire: {r['avg_pctile_3yr_at_fire']}th)\n")
        md += metrics_table(r["metrics"])
    md += "\n## OLS Regression: Beta → SPX Forward Return\n"
    md += "| Horizon | n | R² | p-value | Slope |\n|---|---|---|---|---|\n"
    for horizon, res in regression.items():
        md += f"| {horizon} | {res['n']} | {res['r2']} | {res['p_value']} | {res['slope']} |\n"
    if granger_p:
        md += f"\n## Granger Causality (beta → SPX)\n`{granger_p}`\n"
    write_md_snippet("07_dbmf_beta", md)
    return payload
