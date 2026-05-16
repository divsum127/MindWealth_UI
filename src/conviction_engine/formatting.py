"""Presentation helpers for Conviction Engine outputs."""

from __future__ import annotations

from typing import Any

import pandas as pd


CONVICTION_COLUMNS = [
    "ticker",
    "asset_type",
    "business_type",
    "signal_timeframe",
    "bq_raw",
    "valuation_tax",
    "conviction_raw",
    "conviction_score",
    "fs_score",
    "fs_class",
    "yield_trap_warning",
    "verdict",
    "sizing_pct",
    "rationale",
]


def display_columns(df: pd.DataFrame) -> list[str]:
    preferred = [
        "Function",
        "Symbol",
        "Signal",
        "Interval",
        "Symbol, Signal, Signal Date/Price[$]",
        "Current Mark to Market and Holding Period",
        "Backtested Win Rate [%]",
        "ticker",
        "signal_timeframe",
        "conviction_score",
        "fs_class",
        "yield_trap_warning",
        "verdict",
        "sizing_pct",
        "rationale",
    ]
    return [column for column in preferred if column in df.columns] + [
        column for column in df.columns if column not in preferred
    ]


def summarize_overlay(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {
            "total_signals": 0,
            "applicable": 0,
            "cancel_buy": 0,
            "max_conviction": 0,
            "yield_traps": 0,
            "tactical_plus": 0,
        }

    verdicts = df.get("verdict", pd.Series("", index=df.index, dtype=str)).astype(str).str.strip()
    verdicts_uc = verdicts.str.upper().replace({"NAN": ""})

    applicable_mask = verdicts_uc != "NOT_APPLICABLE"

    buy_mask = df.get("original_signal", pd.Series("", index=df.index, dtype=str)).astype(str).str.upper().str.strip() == "BUY"
    equity_mask = df.get("asset_type", pd.Series("", index=df.index, dtype=str)).astype(str).str.upper().str.strip() == "EQUITY"

    raw = pd.to_numeric(df.get("conviction_raw"), errors="coerce")
    # Verdict uses FS-capped score, so "MAX CONVICTION" is rare; count fundamental max tier by raw score.
    max_tier_mask = (raw >= 8.0) & buy_mask & equity_mask & applicable_mask
    verdict_max_mask = verdicts_uc == "MAX CONVICTION"
    max_conviction_mask = max_tier_mask | verdict_max_mask

    tactical_plus_mask = (raw >= 5.0) & buy_mask & equity_mask & applicable_mask

    yt_col = df.get("yield_trap_warning")
    if yt_col is None:
        yield_trap_mask = pd.Series(False, index=df.index)
    else:
        s = yt_col if isinstance(yt_col, pd.Series) else pd.Series(yt_col, index=df.index)
        yield_trap_mask = _coerce_bool_series(s.reindex(df.index))

    rationale = df.get("rationale", pd.Series("", index=df.index, dtype=str)).astype(str)
    rationale_yield = rationale.str.contains("yield trap", case=False, na=False)
    yield_trap_mask = yield_trap_mask | (rationale_yield & equity_mask)

    return {
        "total_signals": int(len(df)),
        "applicable": int(applicable_mask.sum()),
        "cancel_buy": int((verdicts_uc == "CANCEL BUY").sum()),
        "max_conviction": int(max_conviction_mask.sum()),
        "yield_traps": int(yield_trap_mask.sum()),
        "tactical_plus": int(tactical_plus_mask.sum()),
    }


def _coerce_bool_series(series: pd.Series) -> pd.Series:
    """Robust bool for overlay columns (may be bool, 0/1, or 'True'/'False' strings from CSV)."""
    result: list[bool] = []
    for v in series.tolist():
        if pd.isna(v):
            result.append(False)
        elif isinstance(v, bool):
            result.append(v)
        elif isinstance(v, (int, float)):
            result.append(v != 0)
        else:
            t = str(v).strip().lower()
            if t in ("false", "0", "", "no", "nan"):
                result.append(False)
            elif t in ("true", "1", "yes"):
                result.append(True)
            else:
                result.append(False)
    return pd.Series(result, index=series.index)
