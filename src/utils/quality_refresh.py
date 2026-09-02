"""Recompute price-dependent quality columns after a price refresh.

The consolidated chatbot CSVs (``chatbot/data/*.csv``) get their Today price, MTM
and trading-day columns rewritten every run, but the quality columns derived from
that same price -- R:R, timeliness, reward remaining, tier, target and stop
ladders -- used to stay frozen at whatever day the row was first written. A
signal from June therefore showed a June R:R next to an August price, and the two
could not be reconciled by anyone reading the card.

Everything here recomputes those columns from the refreshed row, and stamps
``quality_as_of`` so a stale vintage is visible instead of silent.
"""

from __future__ import annotations

import sys
from functools import lru_cache
from typing import Any

import pandas as pd

from src.config_paths import MINDWEALTH_ROOT

QUALITY_AS_OF_COLUMN = "quality_as_of"

# CSV header -> enriched field. Only price-dependent columns belong here; static
# backtest columns (win rate, Sharpe, CAGR) do not move with price.
REPORT_COLUMN_TO_FIELD: dict[str, str] = {
    "R:R Static": "rr_static",
    "R:R Dynamic": "rr_dynamic",
    "R:R Original": "rr_original",
    "Timeliness Score": "timeliness_score",
    "Reward Remaining [%]": "reward_remaining_pct",
    "Signal Quality Composite Score": "composite_score",
    "Expected Return E[R] [%]": "er",
    "Signal Alpha Per Trade [%]": "signal_alpha_per_trade",
    "Theoretical Entry Price [$]": "theoretical_entry_price",
}

# Audit legs behind every R:R. Always written, even into a frame that never had
# them: a ratio a reader cannot reproduce from the same card is the defect these
# columns exist to close.
AUDIT_FIELDS = (
    "nearest_support_stop",
    "nearest_support_stop_type",
    "risk_to_nearest_stop",
    "proposed_reward",
    "bt_avg_exit_price",
    "bt_avg_exit_basis",
    "stop_distance_pct",
    "rr_null_reason",
)

# Snake-case columns the enrich pipeline writes straight through when present.
PASSTHROUGH_FIELDS = (
    "rr_static",
    "rr_dynamic",
    "rr_original",
    "timeliness_score",
    "reward_remaining_pct",
    "composite_score",
    "window_remaining_pct",
    "tier",
    "er",
    "er_annualized",
    "signal_alpha_per_trade",
    "signal_alpha_annualized",
    "days_elapsed",
    "nearest_support_stop",
    "nearest_support_stop_type",
    "risk_to_nearest_stop",
    "proposed_reward",
    "bt_avg_exit_price",
    "bt_avg_exit_basis",
    "stop_distance_pct",
    "rr_null_reason",
)

# Values formatted as percentage strings in the report CSVs.
PERCENT_STRING_COLUMNS = {
    "Reward Remaining [%]",
    "Expected Return E[R] [%]",
    "Signal Alpha Per Trade [%]",
}


@lru_cache(maxsize=1)
def _enrich_signal_dict():
    """Import the core enricher without leaving its root on ``sys.path``.

    The core repo ships its own top-level ``config`` module, and the chatbot does
    ``from config import CHATBOT_ENTRY_DIR``. Leaving MINDWEALTH_ROOT on the path
    means whichever of the two is imported second resolves ``config`` to the wrong
    file. The root is needed only long enough to resolve ``helper_functions``, so
    it is added for the import and removed again.
    """
    root = str(MINDWEALTH_ROOT)
    added = root not in sys.path
    if added:
        sys.path.insert(0, root)
    try:
        from helper_functions.claude_lateness_metrics import enrich_signal_dict  # noqa: WPS433
    finally:
        if added:
            try:
                sys.path.remove(root)
            except ValueError:
                pass

    return enrich_signal_dict


def _format_for_column(column: str, value: Any) -> Any:
    if value is None:
        return None
    if column in PERCENT_STRING_COLUMNS:
        return f"{value:.2f}%" if isinstance(value, (int, float)) else value
    return value


def refresh_quality_columns(
    df: pd.DataFrame,
    as_of: str | None = None,
) -> pd.DataFrame:
    """Recompute quality columns row by row and stamp ``quality_as_of``.

    Columns absent from ``df`` are not created, except ``quality_as_of``: writing
    new quality columns into a report that never carried them would change that
    report's schema. Rows that fail to enrich keep their previous values and are
    left without a fresh stamp, so staleness stays visible.
    """
    if df is None or df.empty:
        return df

    enrich = _enrich_signal_dict()
    out = df.copy()

    if QUALITY_AS_OF_COLUMN not in out.columns:
        out[QUALITY_AS_OF_COLUMN] = None

    present_report_cols = {
        column: field
        for column, field in REPORT_COLUMN_TO_FIELD.items()
        if column in out.columns
    }
    present_passthrough = [f for f in PASSTHROUGH_FIELDS if f in out.columns]
    for field in AUDIT_FIELDS:
        if field not in out.columns:
            out[field] = None

    for idx, row in out.iterrows():
        raw = row.to_dict()
        if "Function" not in raw and "function" in raw:
            raw["Function"] = raw["function"]
        symbol_field = raw.get("Symbol, Signal, Signal Date/Price[$]", "")
        if symbol_field and not raw.get("Symbol"):
            raw["Symbol"] = str(symbol_field).split(",")[0].strip()
        try:
            enriched = enrich(raw)
        except Exception:  # noqa: BLE001 - one bad row must not void the refresh
            continue

        for column, field in present_report_cols.items():
            out.at[idx, column] = _format_for_column(column, enriched.get(field))
        for field in present_passthrough:
            out.at[idx, field] = enriched.get(field)
        for field in AUDIT_FIELDS:
            out.at[idx, field] = enriched.get(field)

        as_of_value = as_of or _row_price_date(raw)
        if as_of_value:
            out.at[idx, QUALITY_AS_OF_COLUMN] = as_of_value

    return out


def _row_price_date(row: dict[str, Any]) -> str | None:
    """Trading date the refreshed price belongs to, used as the quality vintage."""
    for key in (
        "Today Trading Date/Price[$], Today Price vs Signal",
        "Today Trading Date/Price[$], Today price vs Signal",
    ):
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if len(text) >= 10 and text[:4].isdigit():
            return text[:10]
    return None
