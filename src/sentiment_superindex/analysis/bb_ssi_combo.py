"""Test 12: Bollinger lower touch + SSI long gate."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.sentiment_superindex.analysis.forward_metrics import load_spx, returns_at_horizons, summarize_returns
from src.sentiment_superindex.analysis.report_utils import metrics_table, save_artifact, write_md_snippet
from src.sentiment_superindex.analysis.ssi_history import build_ssi_history_frame


def _bb_lower_touches(close: pd.Series, period: int = 20, std: float = 2.0) -> pd.DatetimeIndex:
    sma = close.rolling(period).mean()
    sd = close.rolling(period).std()
    lower = sma - std * sd
    touch = close <= lower
    prev = touch.shift(1).fillna(False)
    return close.index[touch & ~prev]


def run_and_report(start: str = "2010-01-01") -> dict[str, Any]:
    spx = load_spx(start)
    hist = build_ssi_history_frame(start)
    long_pct = float(hist["ssi_pctile_5y"].median())  # use 20 from config
    from src.sentiment_superindex.config import load_config

    long_pct = float(load_config().get("thresholds", {}).get("long_entry_pctile", 20))
    bb_dates = _bb_lower_touches(spx)
    combo_dates = bb_dates.intersection(hist.index[hist["ssi_pctile_5y"] <= long_pct])
    bb_only = returns_at_horizons(spx, bb_dates)
    combo = returns_at_horizons(spx, combo_dates)
    payload = {
        "test_id": "12_bollinger_ssi",
        "n_bb_only": len(bb_dates),
        "n_combo": len(combo_dates),
        "bb_only_metrics": summarize_returns(bb_only),
        "combo_metrics": summarize_returns(combo),
    }
    save_artifact("12_bollinger_ssi", payload)
    md = "# Test 12: Bollinger + SSI\n\n"
    md += f"BB only n={payload['n_bb_only']}\n{metrics_table(payload['bb_only_metrics'])}\n"
    md += f"\nBB + SSI pctile<={long_pct} n={payload['n_combo']}\n{metrics_table(payload['combo_metrics'])}\n"
    write_md_snippet("12_bollinger_ssi", md)
    return payload
