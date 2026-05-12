"""
Deterministic trading math for chatbot prompts (MTM, holding days).

Injected into HYBRID synthesis so the model cites server-computed numbers instead of
re-deriving Arithmetic from mixed CSV strings.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd


def _load_mtm_pricing():
    """Load mtm_pricing by path so importing ``src.utils`` package (Streamlit, etc.) is avoided."""
    root = Path(__file__).resolve().parents[2]
    path = root / "src" / "utils" / "mtm_pricing.py"
    spec = importlib.util.spec_from_file_location("_mtm_pricing_chatbot_tool", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


_mtm = _load_mtm_pricing()
TODAY_PRICE_COLUMN = _mtm.TODAY_PRICE_COLUMN
MTM_HOLDING_COLUMN = _mtm.MTM_HOLDING_COLUMN
calculate_holding_period = _mtm.calculate_holding_period
calculate_mark_to_market = _mtm.calculate_mark_to_market
parse_symbol_signal_column = _mtm.parse_symbol_signal_column
parse_today_trading_price = _mtm.parse_today_trading_price
parse_mtm_holding_cell = _mtm.parse_mtm_holding_cell
resolve_signal_basis = _mtm.resolve_signal_basis

COMPOUND_COL = "Symbol, Signal, Signal Date/Price[$]"
_TODAY_LEGACY = _mtm.TODAY_PRICE_COLUMN_LEGACY

_MAX_TOOL_LINES = 48


def compute_position_mtm_breakdown(
    entry_price: float,
    current_price: float,
    side: str,
) -> Dict[str, Any]:
    """
    Programmatic MTM summary for tools/tests.

    Returns:
        dict with mtm_percent_display (e.g. '-29.67%'), raw_price_change_pct before Short flip.
    """
    sp = float(entry_price)
    cp = float(current_price)
    raw = ((cp - sp) / sp) * 100 if sp else 0.0
    mtm_str = calculate_mark_to_market(cp, sp, side)
    return {
        "entry": sp,
        "current": cp,
        "side": str(side).strip() or "Long",
        "raw_price_change_pct": raw,
        "mtm_percent_display": mtm_str,
    }


def compute_row_metrics(row: pd.Series) -> Optional[Dict[str, Any]]:
    """
    One consolidated CSV row → MTM and holding for prompts.

    **Authoritative source:** When ``Current Mark to Market and Holding Period`` is present
    and parseable (outstanding-signals / entry.csv pipeline), its MTM % and **days** are
    used exactly — they match the consolidated report the UI shows.

    Falls back to recomputation from ``Today Trading Date/Price...`` + entry basis when
    that column is missing or empty.
    """
    compound = row.get(COMPOUND_COL)
    if compound is None or pd.isna(compound):
        return None

    open_cell = row.get("Signal Open Price")
    signal_price, sig_type, sig_date = resolve_signal_basis(open_cell, compound)
    if signal_price is None or float(signal_price) <= 0:
        return None

    symbol, _, _, _ = parse_symbol_signal_column(compound)
    fn = row.get("Function", "")
    if pd.isna(fn):
        fn = ""

    side = (sig_type or "Long").strip()

    report_mtm: Optional[str] = None
    report_days: Optional[int] = None
    if MTM_HOLDING_COLUMN in row.index:
        raw_mtm = row.get(MTM_HOLDING_COLUMN)
        report_mtm, report_days = parse_mtm_holding_cell(raw_mtm)

    today_raw = row.get(TODAY_PRICE_COLUMN)
    if (today_raw is None or pd.isna(today_raw)) and _TODAY_LEGACY in row.index:
        today_raw = row.get(_TODAY_LEGACY)

    as_of: Optional[str] = ""
    cur_px: Optional[float] = None
    if today_raw is not None and not pd.isna(today_raw):
        as_of, cur_px = parse_today_trading_price(today_raw)

    use_report_mtm = report_mtm is not None and report_days is not None

    if not use_report_mtm:
        if cur_px is None:
            return None
        mtm_str = calculate_mark_to_market(cur_px, signal_price, side)
        hold_days = 0
        if sig_date and as_of:
            hold_days = calculate_holding_period(sig_date, as_of)
    else:
        mtm_str = report_mtm
        hold_days = int(report_days)

    out_current: Optional[float] = float(cur_px) if cur_px is not None else None

    return {
        "symbol": symbol or "?",
        "function": str(fn).strip() or "?",
        "side": side,
        "entry": float(signal_price),
        "current": out_current,
        "as_of": as_of or "",
        "mtm_pct": mtm_str,
        "holding_days": hold_days,
        "mtm_from_report": use_report_mtm,
    }


def build_calculator_tool_block(signal_data: Optional[Dict[str, pd.DataFrame]]) -> str:
    """
    Format a prompt section listing deterministic metrics per row (bounded).

    Empty string if nothing parseable.
    """
    if not signal_data:
        return ""

    lines_out: List[str] = []
    n = 0
    for sig_type, df in signal_data.items():
        if df is None or getattr(df, "empty", True):
            continue
        for _, row in df.iterrows():
            if n >= _MAX_TOOL_LINES:
                break
            m = compute_row_metrics(row)
            if not m:
                continue
            cur_disp = f"{m['current']:.6g}" if m.get("current") is not None else "n/a"
            src = "report" if m.get("mtm_from_report") else "computed"
            lines_out.append(
                f"- [{sig_type}] symbol={m['symbol']} function={m['function']} "
                f"side={m['side']} entry={m['entry']:.6g} current={cur_disp} "
                f"as_of={m['as_of']} MTM={m['mtm_pct']} holding_days={m['holding_days']} "
                f"(MTM/holding_source={src})"
            )
            n += 1
        if n >= _MAX_TOOL_LINES:
            break

    if not lines_out:
        return ""

    header = (
        "=== CALCULATOR TOOL OUTPUT (aligned with consolidated outstanding-signals / entry.csv) ===\n"
        f'MTM %% and holding_days use **"{MTM_HOLDING_COLUMN}"** from SOURCE A when present '
        f'(same values as the Outstanding Signals report). Otherwise they are computed from entry basis '
        f'(Signal Open Price if present, else compound column) and "{TODAY_PRICE_COLUMN}". '
        "Current price comes from the Today column when available."
    )
    footer = (
        'Prefer **report-sourced** MTM/holding (MTM/holding_source=report) over manual math. '
        "If SOURCE A JSON shows different prose-only MTM text, trust this block and the MTM/Holding column."
    )
    return "\n".join([header, "", *lines_out, "", footer])


def metrics_as_json(rows: List[Dict[str, Any]]) -> str:
    """Serialize computed metrics for logging or APIs."""
    return json.dumps(rows, indent=2, default=str)
