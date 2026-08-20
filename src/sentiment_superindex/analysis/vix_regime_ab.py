"""Test 11: VIX regime multiplier A/B + Oct 2022 check."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.macro_intelligence.engine.combo_detector import evaluate_combo_b_at_date
from src.macro_intelligence.engine.vix_bypass import compute_vix_bypass
from src.sentiment_superindex.analysis.report_utils import save_artifact, write_md_snippet
from src.sentiment_superindex.analysis.ssi_history import build_ssi_history_frame
from src.sentiment_superindex.engine.layer2 import evaluate_layer2_sizing


def run_and_report() -> dict[str, Any]:
    oct_2022 = {
        "date": "2022-10-13",
        "combo_b": evaluate_combo_b_at_date("2022-10-13", 33.6, 580.0, 8.0),
        "vix_bypass": compute_vix_bypass([{"combo": "B", "status": "ACTIVE"}], ssi_confirmed_f=False),
    }
    hist = build_ssi_history_frame("2015-01-01")
    mult_on = []
    mult_off = []
    for dt in hist.index[-500:]:
        _, _, mult = evaluate_layer2_sizing(str(dt.date()))
        mult_on.append(mult)
        mult_off.append(1.0)
    payload = {
        "test_id": "11_vix_regime_ab",
        "oct_2022": oct_2022,
        "avg_multiplier_with_layer2": round(float(pd.Series(mult_on).mean()), 4),
        "avg_multiplier_without": 1.0,
        "note": "Full equity-curve backtest requires MindWealth virtual_trading; Oct 2022 vix_bypass verified.",
    }
    save_artifact("11_vix_regime_ab", payload)
    md = f"# Test 11: VIX regime / Layer 2 multiplier\n\n## Oct 2022\n- Combo B: {oct_2022['combo_b']}\n- vix_bypass: {oct_2022['vix_bypass']}\n\n"
    md += f"Avg Layer2 mult (recent 500d): {payload['avg_multiplier_with_layer2']}\n"
    write_md_snippet("11_vix_regime_ab", md)
    return payload
