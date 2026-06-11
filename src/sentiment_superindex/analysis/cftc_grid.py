"""Tests 3–4: SQUEEZE and LIQUIDITY EXIT CFTC FM/RM grids."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.macro_intelligence.data.cftc_pull import fetch_cftc_asset_manager_net, fetch_cftc_fast_money_net
from src.macro_intelligence.engine.percentiles import percentile_rank
from src.sentiment_superindex.analysis.forward_metrics import load_spx, returns_at_horizons, summarize_returns
from src.sentiment_superindex.analysis.report_utils import save_artifact, write_md_snippet


def _weekly_pctile_series(net: pd.Series, weeks: int = 156) -> pd.Series:
    out = []
    for dt in net.index:
        window = net.loc[:dt].dropna().tail(weeks)
        if len(window) < 20:
            continue
        out.append((dt, percentile_rank(float(net.loc[dt]), window)))
    return pd.Series(dict(out)).sort_index()


def run_squeeze_grid(start: str = "2006-01-01") -> dict[str, Any]:
    fm = fetch_cftc_fast_money_net()
    rm = fetch_cftc_asset_manager_net()
    spx = load_spx(start)
    rows = []
    fm_pct = _weekly_pctile_series(fm)
    rm_pct = _weekly_pctile_series(rm)
    idx = fm_pct.index.intersection(rm_pct.index)
    idx = idx[idx >= pd.Timestamp(start)]
    for fm_thr in range(15, 45, 5):
        for rm_thr in range(40, 70, 5):
            mask = (fm_pct.loc[idx] < fm_thr) & (rm_pct.loc[idx] > rm_thr)
            dates = idx[mask]
            if len(dates) < 3:
                rows.append({"fm_max": fm_thr, "rm_min": rm_thr, "n": len(dates), "metrics": {}})
                continue
            _h = {"4w": 20, "8w": 40, "12w": 60}
            ret_rows = returns_at_horizons(spx, dates, horizons=_h)
            rows.append({"fm_max": fm_thr, "rm_min": rm_thr, "n": len(dates), "metrics": summarize_returns(ret_rows, horizons=_h)})
    return {"test_id": "03_squeeze_grid", "rows": rows}


def run_liquidity_exit_grid(start: str = "2006-01-01") -> dict[str, Any]:
    fm = fetch_cftc_fast_money_net()
    rm = fetch_cftc_asset_manager_net()
    spx = load_spx(start)
    rows = []
    fm_pct = _weekly_pctile_series(fm)
    rm_pct = _weekly_pctile_series(rm)
    idx = fm_pct.index.intersection(rm_pct.index)
    idx = idx[idx >= pd.Timestamp(start)]
    for rm_thr in range(15, 45, 5):
        for fm_thr in range(45, 80, 5):
            mask = (rm_pct.loc[idx] < rm_thr) & (fm_pct.loc[idx] > fm_thr)
            dates = idx[mask]
            if len(dates) < 3:
                rows.append({"rm_max": rm_thr, "fm_min": fm_thr, "n": len(dates), "metrics": {}})
                continue
            _h = {"4w": 20, "8w": 40, "12w": 60}
            ret_rows = returns_at_horizons(spx, dates, horizons=_h)
            m = summarize_returns(ret_rows, long_side=False, horizons=_h)
            dds = [min(r.get("ret_4w") or 0, r.get("ret_8w") or 0, r.get("ret_12w") or 0) for r in ret_rows]
            m["median_drawdown"] = round(float(np.median(dds)), 4) if dds else None
            rows.append({"rm_max": rm_thr, "fm_min": fm_thr, "n": len(dates), "metrics": m})
    return {"test_id": "04_liquidity_exit_grid", "rows": rows}


def _cell_12w(r: dict) -> str:
    m = r.get("metrics", {}).get("12w", {})
    if not m or not m.get("n"):
        return "—"
    return f"{m.get('avg')}% / {m.get('win_pct')}% win / Sh{m.get('sharpe')}"


def run_and_report(start: str = "2006-01-01") -> dict[str, Any]:
    squeeze = run_squeeze_grid(start)
    liq = run_liquidity_exit_grid(start)
    save_artifact("03_squeeze_grid", squeeze)
    save_artifact("04_liquidity_exit_grid", liq)
    md = "# Tests 3–4: CFTC grids\n\n## SQUEEZE heatmap (12w avg SPX % / win % / Sharpe)\n\n"
    md += "| FM < | RM > 40 | RM > 45 | RM > 50 | RM > 55 | RM > 60 | RM > 65 |\n"
    md += "|------|-----------|-----------|-----------|-----------|-----------|----------|\n"
    for fm in range(15, 45, 5):
        cells = []
        for rm in range(40, 70, 5):
            row = next((x for x in squeeze["rows"] if x["fm_max"] == fm and x["rm_min"] == rm), None)
            cells.append(_cell_12w(row) if row else "—")
        md += f"| {fm} | " + " | ".join(cells) + " |\n"
    best = max(
        (r for r in squeeze["rows"] if r.get("n", 0) >= 50 and r.get("metrics", {}).get("12w")),
        key=lambda x: (x["metrics"]["12w"].get("sharpe") or 0),
        default=None,
    )
    if best:
        md += (
            f"\n**Recommended SQUEEZE cell:** FM<{best['fm_max']}, RM>{best['rm_min']} "
            f"(n={best['n']}, 12w avg {best['metrics']['12w'].get('avg')}%, "
            f"Sharpe {best['metrics']['12w'].get('sharpe')})\n"
        )
    md += "\n## LIQUIDITY EXIT (top cells by n)\n"
    for r in sorted(liq["rows"], key=lambda x: -x.get("n", 0))[:10]:
        m4 = r.get("metrics", {}).get("4w", {})
        md += (
            f"- RM<{r['rm_max']} FM>{r['fm_min']}: n={r['n']}, "
            f"4w SPX down {m4.get('win_pct')}% (median DD {r.get('metrics', {}).get('median_drawdown')})\n"
        )
    write_md_snippet("03_04_cftc_grid", md)
    return {"squeeze": squeeze, "liquidity": liq}
