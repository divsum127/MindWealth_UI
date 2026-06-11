"""Test 14: Gross/net divergence revised 3-condition rule."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.macro_intelligence.data.cftc_pull import fetch_cftc_asset_manager_net, fetch_cftc_fast_money_net
from src.macro_intelligence.engine.percentiles import percentile_rank
from src.sentiment_superindex.analysis.forward_metrics import load_spx, returns_at_horizons, summarize_returns
from src.sentiment_superindex.analysis.report_utils import metrics_table, save_artifact, write_md_snippet
from src.sentiment_superindex.data.yahoo_inputs import hyg_lqd_ratio


def run_and_report(start: str = "2010-01-01") -> dict[str, Any]:
    fm = fetch_cftc_fast_money_net()
    rm = fetch_cftc_asset_manager_net()
    gross = fm + rm
    ratio = hyg_lqd_ratio(start)
    chg4w = ratio.pct_change(28) * 100
    spx = load_spx(start)
    idx = gross.index.intersection(chg4w.dropna().index)
    idx = idx[idx >= pd.Timestamp(start)]
    events = []
    for dt in idx[100:]:
        gwin = gross.loc[:dt].dropna().tail(156)
        if len(gwin) < 30:
            continue
        g_pct = percentile_rank(float(gross.loc[dt]), gwin)
        if g_pct < 75:
            continue
        rm_prev = float(rm.loc[:dt].iloc[-4]) if len(rm.loc[:dt]) >= 4 else float(rm.loc[dt])
        rm_now = float(rm.loc[dt])
        if rm_now >= rm_prev:
            continue
        if float(chg4w.loc[dt]) >= -1.0:
            continue
        events.append(dt)
    _horizons = {"4w": 20, "8w": 40, "12w": 60}
    ret_rows = returns_at_horizons(spx, events, horizons=_horizons)
    metrics = summarize_returns(ret_rows, long_side=False, horizons=_horizons)
    payload = {"test_id": "14_gross_net", "n_events": len(events), "metrics": metrics, "instances": [str(d.date()) for d in events[-20:]]}
    save_artifact("14_gross_net", payload)
    md = f"# Test 14: Gross/net divergence (n={len(events)})\n\n{metrics_table(metrics)}\n"
    write_md_snippet("14_gross_net", md)
    return payload
