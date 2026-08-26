"""Part 1: VIX>35 washout — FM percentile distribution and return inflection."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.macro_intelligence.data.cftc_pull import fetch_cftc_fast_money_net
from src.macro_intelligence.data.yahoo_pull import fetch_yahoo_close
from src.macro_intelligence.engine.percentiles import percentile_rank
from src.sentiment_superindex.analysis.cftc_episode_metrics import weekly_pctile_series
from src.sentiment_superindex.analysis.forward_metrics import load_spx, returns_at_horizons, summarize_returns
from src.sentiment_superindex.analysis.report_utils import save_artifact, write_md_snippet


def _weekly_pctile_series(net: pd.Series, weeks: int = 156) -> pd.Series:
    """Delegates to the shared helper, which refuses to rank a partial window.

    This module carried its own copy with a 20-observation minimum, so it began ranking ~136 weeks
    before a 156-week window could exist and published those partial ranks as 3-year percentiles
    (Rohit, 24 Aug 2026). Kept as a thin wrapper rather than deleted so the call sites read the same.
    """
    return weekly_pctile_series(net, weeks=weeks)


def _fm_pctile_asof(fm_pct: pd.Series, dt: pd.Timestamp) -> float | None:
    prior = fm_pct.loc[:dt].dropna()
    if prior.empty:
        return None
    return float(prior.iloc[-1])


def run_and_report(start: str = "2010-01-01") -> dict[str, Any]:
    vix = fetch_yahoo_close("^VIX", start=start)
    fm = fetch_cftc_fast_money_net()
    fm_pct = _weekly_pctile_series(fm)
    spx = load_spx(start)

    vix_high = vix[vix >= 35].index
    episodes: list[dict[str, Any]] = []
    for dt in vix_high:
        fp = _fm_pctile_asof(fm_pct, dt)
        if fp is None:
            continue
        episodes.append({"date": str(dt.date()), "vix": float(vix.loc[dt]), "fm_pctile": fp})

    fm_vals = [e["fm_pctile"] for e in episodes]
    dist = {
        "n_vix_ge_35": len(episodes),
        "fm_pctile_median": round(float(np.median(fm_vals)), 2) if fm_vals else None,
        "fm_pctile_mean": round(float(np.mean(fm_vals)), 2) if fm_vals else None,
        "pct_below_15": round(sum(1 for v in fm_vals if v < 15) / len(fm_vals) * 100, 2) if fm_vals else None,
        "pct_below_30": round(sum(1 for v in fm_vals if v < 30) / len(fm_vals) * 100, 2) if fm_vals else None,
    }

    bins = [(0, 15), (15, 30), (30, 50), (50, 100)]
    bin_rows: list[dict[str, Any]] = []
    for lo, hi in bins:
        dates = [pd.Timestamp(e["date"]) for e in episodes if lo <= e["fm_pctile"] < hi]
        ret_rows = returns_at_horizons(spx, dates)
        bin_rows.append(
            {
                "fm_pctile_bin": f"{lo}–{hi}",
                "n": len(dates),
                "metrics": summarize_returns(ret_rows),
            }
        )

    sweep_rows: list[dict[str, Any]] = []
    for thr in range(5, 50, 5):
        dates = [pd.Timestamp(e["date"]) for e in episodes if e["fm_pctile"] < thr]
        ret_rows = returns_at_horizons(spx, dates)
        m = summarize_returns(ret_rows)
        sweep_rows.append({"fm_pctile_max": thr, "n": len(dates), "metrics": m})

    payload = {
        "test_id": "19_vix_fm_washout",
        "start": start,
        "distribution": dist,
        "episodes": episodes,
        "bins": bin_rows,
        "fm_threshold_sweep": sweep_rows,
    }
    save_artifact("19_vix_fm_washout", payload)

    md = "# Part 1: VIX ≥ 35 — FM percentile distribution\n\n"
    md += f"- Episodes (VIX≥35 with FM data): **{dist['n_vix_ge_35']}**\n"
    md += f"- FM pctile median: **{dist['fm_pctile_median']}**, mean: **{dist['fm_pctile_mean']}**\n"
    md += f"- Share with FM < 15th: **{dist['pct_below_15']}%**; FM < 30th: **{dist['pct_below_30']}%**\n\n"
    md += "## Returns by FM percentile bin (on VIX≥35 dates)\n\n"
    md += "| FM bin | n | 3m avg % | 3m win % | 6m avg % |\n|--------|---|----------|----------|----------|\n"
    for r in bin_rows:
        m = r["metrics"]
        md += (
            f"| {r['fm_pctile_bin']} | {r['n']} | {m.get('3m', {}).get('avg', '—')} | "
            f"{m.get('3m', {}).get('win_pct', '—')} | {m.get('6m', {}).get('avg', '—')} |\n"
        )
    md += "\n## FM threshold sweep (VIX≥35 subset, FM < X)\n\n"
    md += "| FM max pctile | n | 3m avg % | 3m win % |\n|---------------|---|----------|----------|\n"
    for r in sweep_rows:
        m = r["metrics"]
        md += f"| < {r['fm_pctile_max']} | {r['n']} | {m.get('3m', {}).get('avg', '—')} | {m.get('3m', {}).get('win_pct', '—')} |\n"
    write_md_snippet("19_vix_fm_washout", md)
    return payload
