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
        }
    verdicts = df.get("verdict", pd.Series(dtype=str)).astype(str)
    return {
        "total_signals": int(len(df)),
        "applicable": int((verdicts != "NOT_APPLICABLE").sum()),
        "cancel_buy": int((verdicts == "CANCEL BUY").sum()),
        "max_conviction": int((verdicts == "MAX CONVICTION").sum()),
        "yield_traps": int(df.get("yield_trap_warning", pd.Series(dtype=bool)).fillna(False).sum()),
    }
