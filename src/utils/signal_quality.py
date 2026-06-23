"""Compute MasterSpec signal-quality fields for Streamlit bubble charts."""

from __future__ import annotations

import sys
from functools import lru_cache
from typing import Any

import pandas as pd

from src.config_paths import MINDWEALTH_ROOT


@lru_cache(maxsize=1)
def _enrich_signal_dict():
    """Import MindWealth enrich_signal_dict once (cached)."""
    root = str(MINDWEALTH_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    from helper_functions.claude_lateness_metrics import enrich_signal_dict  # noqa: WPS433

    return enrich_signal_dict


def enrich_raw_signal_row(raw_row: dict[str, Any]) -> dict[str, Any]:
    """Return quality fields for one CSV row dict."""
    row = dict(raw_row)
    if "Function" not in row and "function" in row:
        row["Function"] = row["function"]
    symbol_field = row.get("Symbol, Signal, Signal Date/Price[$]", "")
    if symbol_field and "Symbol" not in row:
        row["Symbol"] = str(symbol_field).split(",")[0].strip()
    try:
        enriched = _enrich_signal_dict()(row)
    except Exception:
        return {}
    return {
        "symbol": enriched.get("Symbol") or row.get("Symbol"),
        "function": enriched.get("Function") or row.get("Function"),
        "interval": _parse_interval(enriched),
        "direction": _parse_direction(enriched),
        "asset_class": enriched.get("asset_class"),
        "er": enriched.get("er"),
        "er_annualized": enriched.get("er_annualized"),
        "signal_alpha_per_trade": enriched.get("signal_alpha_per_trade"),
        "signal_alpha_annualized": enriched.get("signal_alpha_annualized"),
        "composite_score": enriched.get("composite_score"),
        "timeliness_score": enriched.get("timeliness_score"),
        "window_remaining_pct": enriched.get("window_remaining_pct"),
        "reward_remaining_pct": enriched.get("reward_remaining_pct"),
        "intrinsic_lag_days": enriched.get("intrinsic_lag_days"),
        "rr_dynamic": enriched.get("rr_dynamic"),
        "rr_static": enriched.get("rr_static"),
        "tier": enriched.get("tier"),
        "exit_fired": enriched.get("exit_fired"),
        "alpha_interpretation": enriched.get("alpha_interpretation"),
        "days_elapsed": _parse_days_elapsed(enriched),
    }


def quality_rows_from_parsed_df(parsed_df: pd.DataFrame) -> list[dict[str, Any]]:
    """Build bubble-chart rows from analysis-page parsed_df (needs Raw_Data)."""
    if parsed_df is None or parsed_df.empty or "Raw_Data" not in parsed_df.columns:
        return []
    rows: list[dict[str, Any]] = []
    for _, series_row in parsed_df.iterrows():
        raw = series_row.get("Raw_Data")
        if not isinstance(raw, dict):
            continue
        quality = enrich_raw_signal_row(raw)
        if quality.get("composite_score") is None and quality.get("timeliness_score") is None:
            continue
        rows.append(quality)
    return rows


def _parse_interval(row: dict[str, Any]) -> str | None:
    interval_field = row.get("Interval, Confirmation Status", "")
    if interval_field:
        return str(interval_field).split(",")[0].strip()
    return row.get("interval")


def _parse_direction(row: dict[str, Any]) -> str | None:
    symbol_field = row.get("Symbol, Signal, Signal Date/Price[$]", "")
    if symbol_field:
        parts = str(symbol_field).split(", ")
        if len(parts) >= 2:
            return parts[1].strip()
    return row.get("direction")


def _parse_days_elapsed(row: dict[str, Any]) -> int | None:
    raw = row.get("Trading Days between Signal and Today Date")
    if raw is None:
        return row.get("days_elapsed")
    text = str(raw).strip().lower().replace("days", "").strip()
    try:
        return int(float(text))
    except ValueError:
        return None
