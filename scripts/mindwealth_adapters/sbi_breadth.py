#!/usr/bin/env python3
"""Test 15: SBI breadth short entries from MindWealth compute module."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal
import yfinance as yf


@contextlib.contextmanager
def _mindwealth_quiet():
    """MindWealth breadth prints progress to stdout; keep stdout for final JSON only."""
    saved = sys.stdout
    sys.stdout = sys.stderr
    try:
        yield
    finally:
        sys.stdout = saved

MW = Path(os.environ.get("MINDWEALTH_ROOT", "/home/ubuntu/MindWealth"))
if str(MW) not in sys.path:
    sys.path.insert(0, str(MW))

UI = Path(__file__).resolve().parents[2]


def _load_spx(start: str) -> pd.Series:
    data = yf.download("^GSPC", start=start, progress=False, auto_adjust=True)
    if data.empty:
        return pd.Series(dtype=float)
    close = data["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    close.index = pd.to_datetime(close.index).tz_localize(None)
    return close.dropna().astype(float)


def _nyse_sessions() -> pd.DatetimeIndex:
    cal = mcal.get_calendar("NYSE")
    schedule = cal.schedule(start_date="1990-01-01", end_date=pd.Timestamp.now() + pd.Timedelta(days=400))
    return schedule.index.tz_localize(None)


def _forward_return_pct(
    spx: pd.Series,
    fire_date: pd.Timestamp,
    trading_days: int,
    sessions: pd.DatetimeIndex,
) -> float | None:
    fire_date = pd.Timestamp(fire_date).tz_localize(None)
    idx = sessions.searchsorted(fire_date, side="left")
    if idx >= len(sessions) or sessions[idx] < fire_date:
        idx += 1
    if idx + trading_days >= len(sessions):
        return None
    end_date = sessions[idx + trading_days]
    spx = spx.sort_index()
    spx.index = pd.to_datetime(spx.index).tz_localize(None)
    if spx.empty or end_date > spx.index[-1]:
        return None
    start_slice = spx.loc[:fire_date]
    if start_slice.empty:
        return None
    start_px = float(start_slice.iloc[-1])
    end_slice = spx.loc[end_date:end_date]
    if end_slice.empty:
        end_slice = spx.loc[:end_date]
    if end_slice.empty:
        return None
    end_px = float(end_slice.iloc[-1])
    return float((end_px - start_px) / start_px * 100)


def _summarize_returns(
    return_rows: list[dict[str, float | None]],
    *,
    long_side: bool,
    horizons: dict[str, int],
) -> dict[str, Any]:
    out: dict[str, Any] = {"n_events": len(return_rows)}
    for label, days in horizons.items():
        key = f"ret_{label}"
        vals = [r[key] for r in return_rows if r.get(key) is not None]
        if not vals:
            out[label] = {"n": 0, "avg": None, "median": None, "win_pct": None, "worst": None, "sharpe": None}
            continue
        arr = np.array(vals, dtype=float)
        wins = (arr > 0).sum() if long_side else (arr < 0).sum()
        std = float(arr.std())
        sharpe = float(arr.mean() / std * np.sqrt(252 / days)) if std > 1e-9 else None
        out[label] = {
            "n": len(vals),
            "avg": round(float(arr.mean()), 4),
            "median": round(float(np.median(arr)), 4),
            "win_pct": round(wins / len(vals) * 100, 2),
            "worst": round(float(arr.min() if long_side else arr.max()), 4),
            "sharpe": round(sharpe, 4) if sharpe is not None else None,
        }
    return out


def _patch_mw_breadth_quiet() -> None:
    """Skip plotly/kaleido PNG writes and trade_store CSV churn during batch scans."""
    from helper_functions import trade_arrival_analysis

    _orig = trade_arrival_analysis.analyze_trade_arrival_for_function

    def _quiet(*args, **kwargs):
        kwargs["save_plots"] = False
        kwargs["save_artifacts"] = False
        return _orig(*args, **kwargs)

    trade_arrival_analysis.analyze_trade_arrival_for_function = _quiet


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2015-01-01")
    parser.add_argument("--end", default="", help="Inclusive end date YYYY-MM-DD (default: today)")
    parser.add_argument(
        "--freq",
        default="BMS",
        help="Date frequency: B=daily, BMS=business month-start (default, ~10x faster), W-FRI=weekly",
    )
    parser.add_argument(
        "--dates-cache",
        default="",
        help="JSON file to read/write short entry dates (skip MW scan when reading)",
    )
    args = parser.parse_args()
    cache_path = Path(args.dates_cache) if args.dates_cache else None
    short_dates: list[str] = []
    resume_after: str | None = None

    cached: dict[str, Any] = {}
    if cache_path and cache_path.is_file():
        cached = json.loads(cache_path.read_text())
        short_dates = list(cached.get("short_dates", []))
        resume_after = cached.get("last_done")

    if not cached.get("scan_complete"):
        try:
            import data as _mw_data

            _saved_argv = sys.argv[:]
            sys.argv = sys.argv[:1]  # hide --start flag from MindWealth argparse
            try:
                _mw_data.initialise_arguments()
            finally:
                sys.argv = _saved_argv
            _mw_data.online = False  # use cached sp500_stake.csv; skip per-month dashboard refresh
            _patch_mw_breadth_quiet()
            from compute import calculate_trade_arrival_stats_for_breadth
            from constant import BREADTH_INDICATOR_SBI_PERCENTILE_TRIGGER

            trigger = BREADTH_INDICATOR_SBI_PERCENTILE_TRIGGER
            end = pd.Timestamp(args.end) if args.end else pd.Timestamp.now()
            dates = pd.date_range(args.start, end, freq=args.freq)
            with _mindwealth_quiet():
                for i, dt in enumerate(dates, 1):
                    d = dt.strftime("%Y-%m-%d")
                    if resume_after and d <= resume_after:
                        continue
                    print(f"[SBI] {i}/{len(dates)} {d}", file=sys.stderr)
                    try:
                        _tl, _ts, _tlo, _tsh, lp, sp = calculate_trade_arrival_stats_for_breadth(
                            "COMBINED_STRATEGY", "Daily", d, use_sp500=True
                        )
                        sp_val = float(str(sp).replace("%", "")) if sp not in (None, "", "NA") else None
                        if sp_val is not None and sp_val <= trigger:
                            short_dates.append(d)
                    except Exception:
                        continue
                    if cache_path:
                        cache_path.write_text(
                            json.dumps({"short_dates": short_dates, "last_done": d, "scan_complete": False})
                        )
        except ImportError as e:
            print(json.dumps({"test_id": "15_sbi_short", "error": str(e)}))
            return

        if cache_path:
            cache_path.write_text(
                json.dumps({"short_dates": short_dates, "last_done": None, "scan_complete": True})
            )

    horizons = {"1w": 5, "4w": 20, "8w": 40}
    sessions = _nyse_sessions()
    spx = _load_spx(args.start)
    ret_rows: list[dict[str, float | None]] = []
    for d in short_dates:
        row: dict[str, float | None] = {"date": d}
        for label, days in horizons.items():
            row[f"ret_{label}"] = _forward_return_pct(spx, pd.Timestamp(d), days, sessions)
        ret_rows.append(row)
    metrics = _summarize_returns(ret_rows, long_side=False, horizons=horizons)
    print(
        json.dumps(
            {
                "test_id": "15_sbi_short",
                "freq": args.freq,
                "n_short_entries": len(short_dates),
                "metrics": metrics,
                "sample_dates": short_dates[-10:],
            }
        )
    )


if __name__ == "__main__":
    main()
