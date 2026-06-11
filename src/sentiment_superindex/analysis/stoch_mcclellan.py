"""Test 13: Stochastic <20 turning up + McClellan positive."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.sentiment_superindex.analysis.forward_metrics import load_spx, returns_at_horizons, summarize_returns
from src.sentiment_superindex.analysis.report_utils import metrics_table, save_artifact, write_md_snippet
from src.sentiment_superindex.data.mcclellan_pull import fetch_mcclellan_oscillator


def _stoch_k(close: pd.Series, period: int = 14) -> pd.Series:
    low = close.rolling(period).min()
    high = close.rolling(period).max()
    return 100 * (close - low) / (high - low).replace(0, pd.NA)


def run_and_report(start: str = "2010-01-01") -> dict[str, Any]:
    spx = load_spx(start)
    k = _stoch_k(spx)
    mcc = fetch_mcclellan_oscillator(start)
    mcc_z = (mcc - mcc.rolling(252).mean()) / mcc.rolling(252).std()
    idx = spx.index.intersection(mcc_z.dropna().index)
    stoch_alone = []
    mcc_alone = []
    combo = []
    for i in range(1, len(idx)):
        dt = idx[i]
        if k.loc[dt] < 20 and k.loc[idx[i - 1]] >= 20:
            stoch_alone.append(dt)
        if mcc_z.loc[dt] > 0 and mcc_z.loc[idx[i - 1]] <= 0:
            mcc_alone.append(dt)
        if k.loc[dt] < 20 and k.loc[idx[i - 1]] >= 20 and mcc_z.loc[dt] > 0:
            combo.append(dt)
    horizons = {"1w": 5, "2w": 10, "4w": 20}
    payload = {
        "test_id": "13_stoch_mcclellan",
        "stoch_only": summarize_returns(returns_at_horizons(spx, stoch_alone, horizons=horizons)),
        "mcclellan_only": summarize_returns(returns_at_horizons(spx, mcc_alone, horizons=horizons)),
        "combo": summarize_returns(returns_at_horizons(spx, combo, horizons=horizons)),
        "n_stoch": len(stoch_alone),
        "n_mcc": len(mcc_alone),
        "n_combo": len(combo),
    }
    save_artifact("13_stoch_mcclellan", payload)
    md = "# Test 13: Stochastic + McClellan\n\n"
    counts = {"stoch_only": payload["n_stoch"], "mcclellan_only": payload["n_mcc"], "combo": payload["n_combo"]}
    for label in ("stoch_only", "mcclellan_only", "combo"):
        md += f"\n## {label} (n={counts[label]})\n{metrics_table(payload[label])}\n"
    write_md_snippet("13_stoch_mcclellan", md)
    return payload
