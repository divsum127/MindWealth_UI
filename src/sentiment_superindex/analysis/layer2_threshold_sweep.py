"""Test 10: Layer 2 confirmation threshold sweep (min_confirmed votes)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.sentiment_superindex.analysis.forward_metrics import load_spx, returns_at_horizons, summarize_returns
from src.sentiment_superindex.analysis.report_utils import metrics_table, save_artifact, write_md_snippet
from src.sentiment_superindex.analysis.ssi_history import build_ssi_history_frame
from src.sentiment_superindex.data.pull_all import load_all_series, values_as_of
from src.sentiment_superindex.engine.layer2 import _pctile_in_history


def _count_votes(as_of: pd.Timestamp, series: dict, votes_cfg: dict) -> int:
    vals = values_as_of(series, as_of)
    n = 0
    hyg = vals.get("hyg_lqd")
    if hyg is not None:
        pct = _pctile_in_history(hyg, series["hyg_lqd"].loc[:as_of])
        if pct >= votes_cfg.get("hyg_lqd", {}).get("risk_on_pctile_min", 70) or pct <= votes_cfg.get("hyg_lqd", {}).get("risk_off_pctile_max", 30):
            n += 1
    beta = vals.get("dbmf_beta")
    if beta is not None:
        if beta <= votes_cfg.get("dbmf_beta", {}).get("low_beta_max", 0.5) or beta >= votes_cfg.get("dbmf_beta", {}).get("high_beta_min", 1.2):
            n += 1
    fg = vals.get("cnn_fg")
    if fg is not None:
        if fg <= votes_cfg.get("cnn_fg", {}).get("fear_max", 25) or fg >= votes_cfg.get("cnn_fg", {}).get("greed_min", 75):
            n += 1
    vr = vals.get("vix_ratio")
    if vr is not None:
        if vr >= votes_cfg.get("vix_ratio", {}).get("stress_min", 1.05) or vr <= votes_cfg.get("vix_ratio", {}).get("complacency_max", 0.95):
            n += 1
    return n


def run_and_report(start: str = "2015-01-01") -> dict[str, Any]:
    from src.sentiment_superindex.config import load_config

    cfg = load_config()
    votes_cfg = cfg.get("layer2", {}).get("votes", {})
    series = load_all_series()
    hist = build_ssi_history_frame(start)
    spx = load_spx(start)
    long_gate = hist["ssi_pctile_5y"] <= float(cfg.get("thresholds", {}).get("long_entry_pctile", 20))
    rows: list[dict[str, Any]] = []
    for min_votes in range(0, 5):
        dates = []
        for dt in hist.index:
            if not long_gate.loc[dt]:
                continue
            if _count_votes(dt, series, votes_cfg) >= min_votes:
                dates.append(dt)
        ret_rows = returns_at_horizons(spx, dates)
        rows.append({"min_votes": min_votes, "n_long_with_gate": len(dates), "metrics": summarize_returns(ret_rows)})
    payload = {"test_id": "10_layer2_sweep", "rows": rows}
    save_artifact("10_layer2_sweep", payload)
    md = "# Test 10: Layer 2 vote count vs long quality\n\n"
    for r in rows:
        md += f"\n## min_votes >= {r['min_votes']} (n={r['n_long_with_gate']})\n{metrics_table(r['metrics'])}\n"
    write_md_snippet("10_layer2_sweep", md)
    return payload
