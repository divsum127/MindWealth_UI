"""Live gross/net divergence flag (Test 14 — display/alert only)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.macro_intelligence.data.cftc_pull import fetch_cftc_asset_manager_net, fetch_cftc_fast_money_net
from src.macro_intelligence.engine.percentiles import percentile_rank
from src.sentiment_superindex.data.yahoo_inputs import hyg_lqd_ratio


def evaluate_gross_net_divergence(as_of: str) -> dict[str, Any]:
    """3-condition rule: gross >75th pctile, RM net falling, HYG/LQD 4w chg < −1%."""
    inactive = {"gross_net_divergence_active": False, "gross_net_divergence_label": "None"}
    ts = pd.Timestamp(as_of)
    fm = fetch_cftc_fast_money_net()
    rm = fetch_cftc_asset_manager_net()
    if fm.empty or rm.empty:
        return inactive
    gross = fm + rm
    g_slice = gross.loc[:ts].dropna()
    if g_slice.empty:
        return inactive
    g_now = float(g_slice.iloc[-1])
    g_win = g_slice.tail(156)
    if len(g_win) < 30:
        return inactive
    g_pct = percentile_rank(g_now, g_win)
    if g_pct < 75:
        return {**inactive, "gross_pctile": round(g_pct, 1)}
    rm_slice = rm.loc[:ts].dropna()
    if len(rm_slice) < 4:
        return inactive
    rm_now = float(rm_slice.iloc[-1])
    rm_prev = float(rm_slice.iloc[-4])
    if rm_now >= rm_prev:
        return {**inactive, "gross_pctile": round(g_pct, 1)}
    ratio = hyg_lqd_ratio(str(ts.date() - pd.Timedelta(days=400)))
    chg4w = ratio.pct_change(28) * 100
    chg_slice = chg4w.loc[:ts].dropna()
    if chg_slice.empty:
        return inactive
    hyg_chg = float(chg_slice.iloc[-1])
    if hyg_chg >= -1.0:
        return {
            **inactive,
            "gross_pctile": round(g_pct, 1),
            "hyg_lqd_4w_pct": round(hyg_chg, 2),
        }
    return {
        "gross_net_divergence_active": True,
        "gross_net_divergence_label": "Gross/Net Divergence",
        "gross_pctile": round(g_pct, 1),
        "hyg_lqd_4w_pct": round(hyg_chg, 2),
        "gross_net_divergence_plain_english": "Gross positioning elevated; real money net falling; credit widening",
    }