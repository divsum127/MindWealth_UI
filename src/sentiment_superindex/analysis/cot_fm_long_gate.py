"""Part 1: COT Fast Money percentile sweep as long-gate confirmation (15th–45th)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.macro_intelligence.data.cftc_pull import fetch_cftc_fast_money_net
from src.macro_intelligence.engine.percentiles import percentile_rank
from src.sentiment_superindex.analysis.forward_metrics import load_spx, returns_at_horizons, summarize_returns
from src.sentiment_superindex.analysis.report_utils import metrics_table, save_artifact, write_md_snippet


def _weekly_pctile_series(net: pd.Series, weeks: int = 156) -> pd.Series:
    out: list[tuple[pd.Timestamp, float]] = []
    for dt in net.index:
        window = net.loc[:dt].dropna().tail(weeks)
        if len(window) < 20:
            continue
        out.append((dt, percentile_rank(float(net.loc[dt]), window)))
    return pd.Series(dict(out)).sort_index()


def run_and_report(start: str = "2010-01-01") -> dict[str, Any]:
    fm = fetch_cftc_fast_money_net()
    spx = load_spx(start)
    fm_pct = _weekly_pctile_series(fm)
    idx = fm_pct.index[fm_pct.index >= pd.Timestamp(start)]
    rows: list[dict[str, Any]] = []
    for thr in range(15, 50, 5):
        dates = idx[fm_pct.loc[idx] < thr]
        ret_rows = returns_at_horizons(spx, dates)
        rows.append(
            {
                "fm_pctile_max": thr,
                "n_crossings": len(dates),
                "metrics": summarize_returns(ret_rows),
            }
        )
    payload = {"test_id": "18_cot_fm_long_gate", "start": start, "rows": rows}
    save_artifact("18_cot_fm_long_gate", payload)
    md = "# Part 1: COT FM long gate — percentile sweep (FM < X)\n\n"
    md += "| FM pctile max | n | 1m avg % | 1m win % | 3m avg % | 3m win % | 6m avg % |\n"
    md += "|---------------|---|----------|----------|----------|----------|----------|\n"
    for r in rows:
        m = r["metrics"]
        md += (
            f"| < {r['fm_pctile_max']} | {r['n_crossings']} | "
            f"{m.get('1m', {}).get('avg', '—')} | {m.get('1m', {}).get('win_pct', '—')} | "
            f"{m.get('3m', {}).get('avg', '—')} | {m.get('3m', {}).get('win_pct', '—')} | "
            f"{m.get('6m', {}).get('avg', '—')} |\n"
        )
    md += "\n## Full metrics\n"
    for r in rows:
        md += f"\n### FM < {r['fm_pctile_max']}th pctile (n={r['n_crossings']})\n"
        md += metrics_table(r["metrics"])
    write_md_snippet("18_cot_fm_long_gate", md)
    return payload
