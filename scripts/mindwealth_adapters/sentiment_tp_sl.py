#!/usr/bin/env python3
"""Test 5 adapter: TP/SL grid using MindWealth sentiment vol logic on SPY."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
UI_ROOT = Path(__file__).resolve().parents[2]
if str(UI_ROOT) not in sys.path:
    sys.path.insert(0, str(UI_ROOT))


def _load_spy() -> pd.DataFrame:
    try:
        import yfinance as yf

        df = yf.download("^GSPC", start="2010-01-01", progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.rename(columns=str.title)
        df.index = pd.to_datetime(df.index).tz_localize(None)
        return df
    except Exception:
        from src.macro_intelligence.data.yahoo_pull import fetch_yahoo_close

        s = fetch_yahoo_close("^GSPC", "2010-01-01")
        return pd.DataFrame({"Close": s, "High": s, "Low": s})


def _simulate(df: pd.DataFrame, tp_mult: float, sl_mult: float) -> dict:
    daily_vol = df["Close"].pct_change().std() * 100
    if pd.isna(daily_vol) or daily_vol < 0.01:
        daily_vol = 2.0
    tp_pct = daily_vol * tp_mult
    sl_pct = daily_vol * sl_mult
    rets = []
    for i in range(100, len(df) - 60, 5):
        entry = float(df["Close"].iloc[i])
        for j in range(i + 1, min(i + 60, len(df))):
            hi = float(df["High"].iloc[j])
            lo = float(df["Low"].iloc[j])
            if (hi - entry) / entry * 100 >= tp_pct:
                rets.append(tp_pct)
                break
            if (entry - lo) / entry * 100 >= sl_pct:
                rets.append(-sl_pct)
                break
        else:
            continue
    if not rets:
        return {"tp_mult": tp_mult, "sl_mult": sl_mult, "n": 0, "sharpe": None, "win_pct": None}
    arr = np.array(rets)
    sharpe = float(arr.mean() / arr.std() * np.sqrt(252 / 21)) if arr.std() > 1e-9 else None
    return {
        "tp_mult": tp_mult,
        "sl_mult": sl_mult,
        "n": len(arr),
        "sharpe": round(sharpe, 4) if sharpe else None,
        "win_pct": round((arr > 0).mean() * 100, 2),
        "avg_return": round(float(arr.mean()), 4),
    }


def main() -> None:
    df = _load_spy()
    rows = []
    for tp in range(5, 21):
        for sl in range(8, 26):
            rows.append(_simulate(df, float(tp), float(sl)))
    best = max((r for r in rows if r.get("n", 0) > 10 and r.get("sharpe")), key=lambda x: x["sharpe"], default=None)
    print(json.dumps({"test_id": "05_tp_sl", "rows": rows, "best": best}))


if __name__ == "__main__":
    main()
