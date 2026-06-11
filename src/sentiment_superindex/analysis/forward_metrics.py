"""Standard SPX forward-return metrics for SSI validation studies."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.macro_intelligence.data.yahoo_pull import fetch_yahoo_close
from src.macro_intelligence.engine.forward_returns import _nyse_sessions, forward_return_pct

DEFAULT_HORIZONS: dict[str, int] = {
    "1w": 5,
    "2w": 10,
    "1m": 21,
    "3m": 63,
    "6m": 126,
    "12m": 252,
}


def load_spx(start: str = "2010-01-01") -> pd.Series:
    return fetch_yahoo_close("^GSPC", start)


def returns_at_horizons(
    spx: pd.Series,
    fire_dates: pd.DatetimeIndex | list[pd.Timestamp],
    horizons: dict[str, int] | None = None,
) -> list[dict[str, float | None]]:
    horizons = horizons or DEFAULT_HORIZONS
    sessions = _nyse_sessions()
    rows: list[dict[str, float | None]] = []
    for dt in fire_dates:
        row: dict[str, float | None] = {"date": str(pd.Timestamp(dt).date())}
        for label, days in horizons.items():
            row[f"ret_{label}"] = forward_return_pct(spx, pd.Timestamp(dt), days, sessions=sessions)
        rows.append(row)
    return rows


def summarize_returns(
    return_rows: list[dict[str, float | None]],
    *,
    long_side: bool = True,
    horizons: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Aggregate n, avg, median, win%, worst, Sharpe per horizon."""
    horizons = horizons or DEFAULT_HORIZONS
    out: dict[str, Any] = {"n_events": len(return_rows)}
    for label in horizons:
        key = f"ret_{label}"
        vals = [r[key] for r in return_rows if r.get(key) is not None]
        if not vals:
            out[label] = {"n": 0, "avg": None, "median": None, "win_pct": None, "worst": None, "sharpe": None}
            continue
        arr = np.array(vals, dtype=float)
        if long_side:
            wins = (arr > 0).sum()
        else:
            wins = (arr < 0).sum()
        std = float(arr.std())
        sharpe = float(arr.mean() / std * np.sqrt(252 / horizons[label])) if std > 1e-9 else None
        out[label] = {
            "n": len(vals),
            "avg": round(float(arr.mean()), 4),
            "median": round(float(np.median(arr)), 4),
            "win_pct": round(wins / len(vals) * 100, 2),
            "worst": round(float(arr.min() if long_side else arr.max()), 4),
            "sharpe": round(sharpe, 4) if sharpe is not None else None,
        }
    return out
