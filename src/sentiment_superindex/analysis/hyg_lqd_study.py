"""Test 8: HYG/LQD 4-week change thresholds."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.macro_intelligence.data.yahoo_pull import fetch_yahoo_close
from src.sentiment_superindex.analysis.forward_metrics import load_spx, returns_at_horizons, summarize_returns
from src.sentiment_superindex.analysis.report_utils import metrics_table, save_artifact, write_md_snippet
from src.sentiment_superindex.data.yahoo_inputs import hyg_lqd_ratio


def run_and_report(start: str = "2010-01-01") -> dict[str, Any]:
    ratio = hyg_lqd_ratio(start)
    chg4w = ratio.pct_change(28) * 100
    spx = load_spx(start)
    vix = fetch_yahoo_close("^VIX", start)
    thresholds = [-1.0, -1.5, -2.0, -3.0]
    rows: list[dict[str, Any]] = []
    prev = chg4w.shift(1)
    for thr in thresholds:
        mask = (chg4w < thr) & (prev >= thr)
        dates = chg4w.index[mask.fillna(False)]
        _h = {"1w": 5, "4w": 20, "8w": 40}
        ret_rows = returns_at_horizons(spx, dates, horizons=_h)
        lead_days: list[int] = []
        for dt in dates[:200]:
            vix_slice = vix.loc[dt : dt + pd.Timedelta(days=60)]
            if len(vix_slice) < 2:
                continue
            spike = vix_slice[vix_slice > 25]
            if not spike.empty:
                lead_days.append((spike.index[0] - dt).days)
        rows.append({
            "threshold_pct": thr,
            "n_crossings": len(dates),
            "metrics": summarize_returns(ret_rows, horizons=_h),
            "median_days_to_vix25": int(pd.Series(lead_days).median()) if lead_days else None,
        })
    payload = {"test_id": "08_hyg_lqd", "rows": rows}
    save_artifact("08_hyg_lqd", payload)
    md = "# Test 8: HYG/LQD widening\n\n"
    for r in rows:
        md += f"\n## 4w change < {r['threshold_pct']}% (n={r['n_crossings']}, median days to VIX>25: {r.get('median_days_to_vix25')})\n"
        md += metrics_table(r["metrics"])
    write_md_snippet("08_hyg_lqd", md)
    return payload
