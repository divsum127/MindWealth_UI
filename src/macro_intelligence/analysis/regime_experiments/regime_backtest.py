"""Part D2 — research-only backtest: named combos vs HMM state overlay."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from src.macro_intelligence.analysis.regime_experiments.hmm_prototype import run_hmm_prototype
from src.macro_intelligence.analysis.regime_experiments.metrics import summarize_returns
from src.macro_intelligence.db.connection import get_connection


def run_regime_backtest() -> dict[str, Any]:
    hmm = run_hmm_prototype()
    if hmm.get("status") != "RESEARCH_PROTOTYPE":
        return {"status": "DEFERRED", "reason": hmm.get("reason", "HMM prototype unavailable")}

    state_by_date = hmm.get("state_by_date") or {}
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT cf.runic_combo, cf.date, fr.spx_3m
            FROM combo_fires cf
            JOIN forward_returns fr ON cf.combo_id = fr.combo_id
            WHERE cf.runic_combo IN ('B', 'D') AND fr.spx_3m IS NOT NULL
            """
        ).fetchall()

    results: dict[str, Any] = {}
    for combo in ("B", "D"):
        bullish = combo == "B"
        all_rets = [r["spx_3m"] for r in rows if r["runic_combo"] == combo]
        overlay_rets = []
        for r in rows:
            if r["runic_combo"] != combo:
                continue
            st = state_by_date.get(r["date"])
            if st == "Risk-Off":
                overlay_rets.append(r["spx_3m"])
        results[combo] = {
            "overall_3m": summarize_returns(all_rets, bullish=bullish),
            "hmm_risk_off_only_3m": summarize_returns(overlay_rets, bullish=bullish),
            "note": "Research prototype — production HMM deferred 6mo",
        }

    return {"status": "RESEARCH", "comparisons": results, "hmm_n_obs": hmm.get("n_obs")}
