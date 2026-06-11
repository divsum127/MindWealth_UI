"""Test 6: CNN Fear & Greed forward returns."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.sentiment_superindex.analysis.forward_metrics import load_spx, returns_at_horizons, summarize_returns
from src.sentiment_superindex.analysis.report_utils import metrics_table, save_artifact, write_md_snippet
from src.sentiment_superindex.data.cnn_fear_greed import load_cnn_series


def _crossings(series: pd.Series, op: str, level: float) -> pd.DatetimeIndex:
    prev = series.shift(1)
    if op == "lt":
        mask = (series < level) & (prev >= level)
    elif op == "gt":
        mask = (series > level) & (prev <= level)
    else:
        mask = series < level
    return series.index[mask.fillna(False)]


def run_and_report(start: str = "2011-01-01") -> dict[str, Any]:
    cnn = load_cnn_series()
    cnn = cnn.loc[cnn.index >= pd.Timestamp(start)]
    spx = load_spx(start)
    rules = [
        ("fear_20", "lt", 20),
        ("fear_10", "lt", 10),
        ("greed_80", "gt", 80),
        ("greed_90", "gt", 90),
    ]
    results: list[dict[str, Any]] = []
    for name, op, level in rules:
        dates = _crossings(cnn, op, level)
        ret_rows = returns_at_horizons(spx, dates)
        results.append({"rule": name, "level": level, "n_crossings": len(dates), "metrics": summarize_returns(ret_rows)})
    payload = {"test_id": "06_cnn_fear_greed", "start": start, "rules": results}
    save_artifact("06_cnn_fear_greed", payload)
    md = "# Test 6: CNN Fear & Greed\n\n"
    for r in results:
        md += f"\n## {r['rule']} (n={r['n_crossings']})\n{metrics_table(r['metrics'])}\n"
    write_md_snippet("06_cnn_fear_greed", md)
    return payload
