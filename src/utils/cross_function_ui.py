"""UI helpers for cross-function exit conflicts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from ..config_paths import TRADE_STORE_US_DIR


def load_cross_function_conflicts() -> dict[str, Any]:
    path = Path(TRADE_STORE_US_DIR) / "cross_function_conflicts.json"
    if not path.exists():
        return {"conflict_count": 0, "conflicts": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"conflict_count": 0, "conflicts": []}


def _row_triggered(raw: dict[str, Any]) -> bool:
    triggered = raw.get("cross_function_exit_triggered")
    if triggered is not None:
        if isinstance(triggered, str):
            return triggered.strip().lower() in ("true", "1", "yes")
        return bool(triggered)
    display = str(raw.get("Cross-Function Exit", "") or "").strip()
    return bool(display)


def filter_cross_function_conflicts(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    mask = df.apply(
        lambda row: _row_triggered(row.get("Raw_Data", {}) if isinstance(row.get("Raw_Data"), dict) else {}),
        axis=1,
    )
    return df[mask].copy()


def filter_recent_exits(df: pd.DataFrame) -> pd.DataFrame:
    """Rows with a real exit date (not No Exit Yet)."""
    if df.empty:
        return df

    def has_exit(row: pd.Series) -> bool:
        raw = row.get("Raw_Data", {})
        if not isinstance(raw, dict):
            return False
        exit_info = str(raw.get("Exit Signal Date/Price[$]", "") or "").strip()
        if not exit_info or exit_info in ("No Exit Yet", "N/A", "nan"):
            return False
        return bool(__import__("re").search(r"\d{4}-\d{2}-\d{2}", exit_info))

    return df[df.apply(has_exit, axis=1)].copy()


def render_cross_function_conflict_banner(conflicts: list[dict[str, Any]], *, page_label: str) -> None:
    if not conflicts:
        return

    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, #7f1d1d 0%, #991b1b 100%);
            color: white;
            padding: 1rem 1.25rem;
            border-radius: 8px;
            margin-bottom: 1rem;
            border-left: 6px solid #fbbf24;
        ">
            <strong>⚠ Cross-Function Exit Conflicts — {page_label}</strong><br/>
            {len(conflicts)} asset(s) have an exit signal from one function while other function(s) still hold an open position.
            Review the conflict list below before acting on individual signals.
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_cross_function_conflict_table(conflicts: list[dict[str, Any]]) -> None:
    if not conflicts:
        return

    st.markdown("### ⚠ Cross-Function Conflict List")
    rows: list[dict[str, str]] = []
    for item in conflicts:
        symbol = item.get("symbol", "")
        direction = item.get("direction", "")
        asset_class = item.get("asset_class", "")
        triggers = item.get("triggering_exits") or []
        opens = item.get("open_positions") or []
        trigger_txt = "; ".join(
            f"{t.get('function')} @ ${t.get('exit_price', '—')} ({t.get('exit_date', '')})"
            for t in triggers
        )
        open_txt = "; ".join(
            (
                f"{p.get('function')} ({p.get('interval', '')}) "
                f"MTM {p.get('mtm_pct'):+.2f}%"
                if p.get("mtm_pct") is not None
                else f"{p.get('function')} ({p.get('interval', '')})"
            )
            for p in opens
        )
        rows.append(
            {
                "Symbol": symbol,
                "Direction": direction,
                "Asset Class": asset_class,
                "Triggering Exit(s)": trigger_txt,
                "Open Position(s) + MTM": open_txt,
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def is_cross_function_conflict_row(row: pd.Series) -> bool:
    raw = row.get("Raw_Data", {})
    if not isinstance(raw, dict):
        return False
    return _row_triggered(raw)


def cross_function_display_for_row(row: pd.Series) -> str:
    raw = row.get("Raw_Data", {})
    if not isinstance(raw, dict):
        return ""
    return str(raw.get("Cross-Function Exit") or raw.get("cross_function_exit_display") or "").strip()
