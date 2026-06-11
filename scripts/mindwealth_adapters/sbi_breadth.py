#!/usr/bin/env python3
"""Test 15: SBI breadth short entries from MindWealth compute module."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd

MW = Path(os.environ.get("MINDWEALTH_ROOT", "/home/ubuntu/MindWealth"))
if str(MW) not in sys.path:
    sys.path.insert(0, str(MW))

UI = Path(__file__).resolve().parents[2]
if str(UI) not in sys.path:
    sys.path.insert(0, str(UI))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2015-01-01")
    args = parser.parse_args()
    short_dates = []
    try:
        import data as _mw_data

        _saved_argv = sys.argv[:]
        sys.argv = sys.argv[:1]  # hide --start flag from MindWealth argparse
        try:
            _mw_data.initialise_arguments()
        finally:
            sys.argv = _saved_argv
        from compute import calculate_trade_arrival_stats_for_breadth
        from constant import BREADTH_INDICATOR_SBI_PERCENTILE_TRIGGER

        trigger = BREADTH_INDICATOR_SBI_PERCENTILE_TRIGGER
        dates = pd.date_range(args.start, pd.Timestamp.now(), freq="B")
        for dt in dates:
            d = dt.strftime("%Y-%m-%d")
            try:
                _tl, _ts, _tlo, _tsh, lp, sp = calculate_trade_arrival_stats_for_breadth(
                    "COMBINED_STRATEGY", "Daily", d, use_sp500=True
                )
                sp_val = float(str(sp).replace("%", "")) if sp not in (None, "", "NA") else None
                if sp_val is not None and sp_val <= trigger:
                    short_dates.append(d)
            except Exception:
                continue
    except ImportError as e:
        print(json.dumps({"test_id": "15_sbi_short", "error": str(e)}))
        return

    from src.sentiment_superindex.analysis.forward_metrics import load_spx, returns_at_horizons, summarize_returns

    spx = load_spx(args.start)
    ret_rows = returns_at_horizons(spx, [pd.Timestamp(d) for d in short_dates], horizons={"1w": 5, "4w": 20, "8w": 40})
    metrics = summarize_returns(ret_rows, long_side=False)
    print(
        json.dumps(
            {
                "test_id": "15_sbi_short",
                "n_short_entries": len(short_dates),
                "metrics": metrics,
                "sample_dates": short_dates[-10:],
            }
        )
    )


if __name__ == "__main__":
    main()
