"""Shared report CSV/JSON loading for REST APIs."""

from __future__ import annotations

import glob
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from constant import GPT_SIGNALS_REPORT_TXT_PATH_US
from src.config_paths import (
    MACRO_INTEL_JSON_PATH,
    SSI_POSITIONING_JSON,
    TRADE_STORE_US_DIR,
    VIRTUAL_TRADING_LONG_CSV,
    VIRTUAL_TRADING_SHORT_CSV,
)
from src.utils.file_discovery import discover_csv_files, extract_date_from_filename, get_latest_csv_file, get_base_filename
from src.utils.monitored_trades import (
    add_trade_to_monitored,
    load_monitored_trades,
    remove_trade_from_monitored,
    update_monitored_trades_prices,
)

from api.utils import dataframe_to_records

_SYMBOL_SIGNAL_KEY = "Symbol, Signal, Signal Date/Price[$]"
_INTERVAL_KEY = "Interval, Confirmation Status"
_FWD_WR_KEY = (
    "Forward Testing Win Rate[%]/No. of Analysed Trades/Avg Holding Period "
    "(days) (Across ALL Assets)"
)
_WIN_RATE_KEY = "Win Rate [%], History Tested, Number of Trades"
_OUTSTANDING_SLUGS = frozenset({"outstanding_signals", "outstanding_signal"})

# API slug -> trade_store base filename
REPORT_SLUGS: dict[str, str] = {
    "all-signal": "all_signal.csv",
    "all_signal": "all_signal.csv",
    "breadth": "breadth.csv",
    "sbi": "breadth.csv",
    "outstanding-signals": "outstanding_signal.csv",
    "outstanding_signal": "outstanding_signal.csv",
    "new-signals": "new_signal.csv",
    "new_signal": "new_signal.csv",
    "target-signals": "target_signal.csv",
    "target_signal": "target_signal.csv",
    "portfolio-risk": "target_signal.csv",
    "combined-performance": "combined_performance_report.csv",
    "combined_performance_report": "combined_performance_report.csv",
    "sentiment": "sentiment.csv",
    "sigma": "sigma.csv",
    "horizontal-new-high": "horizontal_new_high_report.csv",
    "horizontal_new_high_report": "horizontal_new_high_report.csv",
    "claude-shortlist": "claude_signals_report.csv",
    "claude_signals_report": "claude_signals_report.csv",
    "f-stack": "F-Stack-Analyzer.csv",
}


def _parse_signal_date_from_record(record: dict[str, Any]) -> str | None:
    import re

    field = record.get(_SYMBOL_SIGNAL_KEY, "")
    match = re.search(r"(\d{4}-\d{2}-\d{2})", str(field))
    return match.group(1) if match else None


def _sort_outstanding_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Supplementary §2: freshest signal_date first."""
    return sorted(
        records,
        key=lambda row: _parse_signal_date_from_record(row) or "",
        reverse=True,
    )


def _parse_forward_test_field(record: dict[str, Any]) -> tuple[float | None, int | None]:
    raw = record.get(_FWD_WR_KEY, "")
    if not raw or str(raw).strip() in ("N/A", ""):
        return None, None
    parts = str(raw).split("/")
    try:
        fwd_wr = float(parts[0].strip().rstrip("%").strip())
    except (ValueError, IndexError):
        fwd_wr = None
    trades: int | None = None
    if len(parts) >= 2:
        try:
            trades = int(float(parts[1].strip()))
        except ValueError:
            trades = None
    return fwd_wr, trades


def _parse_win_rate_from_record(record: dict[str, Any]) -> float | None:
    raw = record.get(_WIN_RATE_KEY, "")
    if not raw or str(raw).strip() in ("N/A", ""):
        return None
    try:
        return float(str(raw).split(",")[0].strip().rstrip("%").strip())
    except (ValueError, IndexError):
        return None


_GATE_A2B_FLOOR = 60.0  # Gate A2b: fwd WR below this → disapprove


def _gate_a2b_label(fwd_wr: float | None) -> str | None:
    if fwd_wr is None:
        return None
    if fwd_wr >= 63:
        return "PASS"
    if fwd_wr >= _GATE_A2B_FLOOR:
        return "PASS (cusp)"
    return "FAIL"


def _gate_a2b_verdict(fwd_wr: float | None) -> str:
    """Return approve/disapprove per Gate A2b (missing fwd_wr does not exclude)."""
    if fwd_wr is None or fwd_wr >= _GATE_A2B_FLOOR:
        return "approve"
    return "disapprove"


def _strategy_health_status(fwd_wr: float | None) -> str | None:
    if fwd_wr is None:
        return None
    return "healthy" if fwd_wr >= 62 else "monitor"


def build_strategy_health(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate forward-test stats per function/interval (Supplementary §6)."""
    from collections import defaultdict

    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        function = str(record.get("Function", "")).strip()
        interval_field = record.get(_INTERVAL_KEY, "")
        interval = str(interval_field).split(",")[0].strip() if interval_field else ""
        if function and interval:
            groups[(function, interval)].append(record)

    rows: list[dict[str, Any]] = []
    for (function, interval), group_rows in sorted(groups.items()):
        fwd_wr, trades = _parse_forward_test_field(group_rows[0])
        win_rates = [
            wr
            for wr in (_parse_win_rate_from_record(row) for row in group_rows)
            if wr is not None
        ]
        bt_wr = round(sum(win_rates) / len(win_rates), 2) if win_rates else None
        delta_vs_bt = (
            round(fwd_wr - bt_wr, 2) if fwd_wr is not None and bt_wr is not None else None
        )
        rows.append(
            {
                "strategy": function,
                "interval": interval,
                "fwd_wr": fwd_wr,
                "bt_wr": bt_wr,
                "delta_vs_bt": delta_vs_bt,
                "trades": trades,
                "gate_a2b": _gate_a2b_label(fwd_wr),
                "status": _strategy_health_status(fwd_wr),
            }
        )
    return rows


def strategy_health_report(report_date: str | None = None) -> dict[str, Any]:
    """Latest all-signal report aggregated to strategy_health[]."""
    payload = load_report_records("all-signal", report_date=report_date)
    records = payload.get("records", [])
    return {
        "report_date": payload.get("report_date"),
        "source_file": payload.get("source_file"),
        "strategy_health": build_strategy_health(records),
    }


def build_gate_a2b_gating(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Gate A2b verdict per function/interval/direction from all-signal rows."""
    from collections import defaultdict

    from api.services.signal_enrichment_service import _get_direction

    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        function = str(record.get("Function", "")).strip()
        interval_field = record.get(_INTERVAL_KEY, "")
        interval = str(interval_field).split(",")[0].strip() if interval_field else ""
        direction = _get_direction(record)
        if function and interval:
            groups[(function, interval, direction)].append(record)

    rows: list[dict[str, Any]] = []
    for (function, interval, direction), group_rows in sorted(groups.items()):
        fwd_wr, trades = _parse_forward_test_field(group_rows[0])
        verdict = _gate_a2b_verdict(fwd_wr)
        rows.append(
            {
                "function": function,
                "interval": interval,
                "direction": direction,
                "fwd_wr": fwd_wr,
                "trades": trades,
                "verdict": verdict,
                "approved": verdict == "approve",
            }
        )
    return rows


def gate_a2b_gating_report(report_date: str | None = None) -> dict[str, Any]:
    """Gate A2b approve/disapprove for every function/interval/direction combo."""
    payload = load_report_records("all-signal", report_date=report_date)
    records = payload.get("records", [])
    gates = build_gate_a2b_gating(records)
    approved_count = sum(1 for row in gates if row["approved"])
    return {
        "report_date": payload.get("report_date"),
        "source_file": payload.get("source_file"),
        "floor_pct": _GATE_A2B_FLOOR,
        "gates": gates,
        "row_count": len(gates),
        "approved_count": approved_count,
        "disapproved_count": len(gates) - approved_count,
    }


def _read_csv(path: Path | str) -> pd.DataFrame:
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
        return df if not df.empty else pd.DataFrame()
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _report_date_from_path(path: Path) -> str | None:
    dt = extract_date_from_filename(path.name)
    return dt.strftime("%Y-%m-%d") if dt else None


def list_available_reports() -> list[dict[str, Any]]:
    """Catalog of discoverable trade-store reports."""
    discovered = discover_csv_files()
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for page_name, file_path in discovered.items():
        base = get_base_filename(os.path.basename(file_path))
        seen.add(base)
        entries.append(
            {
                "page_name": page_name,
                "base_filename": base,
                "path": file_path,
                "report_date": _report_date_from_path(Path(file_path)),
            }
        )
    for slug, base in REPORT_SLUGS.items():
        if base in seen:
            continue
        latest = get_latest_csv_file(base, str(TRADE_STORE_US_DIR))
        if latest:
            seen.add(base)
            entries.append(
                {
                    "page_name": slug,
                    "base_filename": base,
                    "path": latest,
                    "report_date": _report_date_from_path(Path(latest)),
                }
            )
    return entries


def resolve_report_path(report_name: str, report_date: str | None = None) -> Path | None:
    slug = report_name.strip().lower().replace(".csv", "").replace("_", "-")
    base = REPORT_SLUGS.get(slug) or REPORT_SLUGS.get(report_name) or (
        report_name if report_name.endswith(".csv") else f"{report_name}.csv"
    )
    if report_date:
        dated = TRADE_STORE_US_DIR / f"{report_date}_{base}"
        if dated.exists() and dated.stat().st_size > 0:
            return dated
    latest = get_latest_csv_file(base, str(TRADE_STORE_US_DIR))
    return Path(latest) if latest else None


_ENRICH_SLUGS = frozenset({
    "outstanding_signals", "outstanding_signal",
    "new_signals", "new_signal",
    "all_signal", "all-signal",
    "target_signals", "target_signal", "portfolio_risk", "portfolio-risk",
})

_CROSS_FUNCTION_REPORT_SLUGS = frozenset({
    "outstanding_signals", "outstanding_signal",
    "target_signals", "target_signal", "portfolio_risk", "portfolio-risk",
})


def _load_cross_function_conflicts() -> dict[str, Any]:
    """Load latest cross_function_conflicts.json from trade_store."""
    latest = TRADE_STORE_US_DIR / "cross_function_conflicts.json"
    if latest.exists() and latest.stat().st_size > 0:
        try:
            return json.loads(latest.read_text(encoding="utf-8"))
        except Exception:
            pass
    pattern = str(TRADE_STORE_US_DIR / "*_cross_function_conflicts.json")
    files = glob.glob(pattern)
    if not files:
        return {"conflict_count": 0, "conflicts": []}

    def key(p: str) -> datetime:
        d = extract_date_from_filename(os.path.basename(p))
        return d if d else datetime.min

    path = max(files, key=key)
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {"conflict_count": 0, "conflicts": []}


def _normalize_cross_function_fields(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for row in records:
        triggered = row.get("cross_function_exit_triggered")
        display = row.get("Cross-Function Exit") or row.get("cross_function_exit_display") or ""
        if triggered is None:
            triggered = bool(str(display).strip())
        elif isinstance(triggered, str):
            triggered = triggered.strip().lower() in ("true", "1", "yes")
        else:
            triggered = bool(triggered)
        row["cross_function_exit_triggered"] = triggered
        row["conflict"] = triggered
        if display:
            row["cross_function_exit_display"] = str(display).strip()
    return records


def load_report_records(
    report_name: str,
    report_date: str | None = None,
    enrich: bool = True,
) -> dict[str, Any]:
    path = resolve_report_path(report_name, report_date)
    if path is None:
        raise FileNotFoundError(f"Report not found: {report_name!r} date={report_date!r}")
    df = _read_csv(path)
    slug = report_name.lower().replace("-", "_").replace(".csv", "")
    if slug in ("claude_shortlist", "claude_signals_report", "claude-shortlist"):
        if df.empty:
            txt_path = _find_latest_claude_txt()
            return {
                "report_name": report_name,
                "source_file": str(txt_path) if txt_path else str(path),
                "report_date": _report_date_from_path(txt_path) if txt_path else _report_date_from_path(path),
                "format": "markdown",
                "row_count": 0,
                "content": txt_path.read_text(encoding="utf-8") if txt_path and txt_path.exists() else "",
                "records": [],
                "csv_empty": True,
            }
    raw_records = (
        _sort_outstanding_records(dataframe_to_records(df))
        if slug in _OUTSTANDING_SLUGS
        else dataframe_to_records(df)
    )
    if enrich and slug in _ENRICH_SLUGS:
        from api.services.signal_enrichment_service import enrich_records
        raw_records = enrich_records(raw_records)
    raw_records = _normalize_cross_function_fields(raw_records)
    payload: dict[str, Any] = {
        "report_name": report_name,
        "source_file": str(path),
        "report_date": _report_date_from_path(path),
        "format": "csv",
        "row_count": int(len(df)),
        "records": raw_records,
    }
    if slug in _CROSS_FUNCTION_REPORT_SLUGS:
        conflicts_blob = _load_cross_function_conflicts()
        payload["cross_function_conflicts"] = conflicts_blob.get("conflicts", [])
        payload["cross_function_conflict_count"] = conflicts_blob.get(
            "conflict_count", len(payload["cross_function_conflicts"])
        )
    return payload


def _find_latest_claude_txt() -> Path | None:
    dir_path = Path(GPT_SIGNALS_REPORT_TXT_PATH_US).parent
    pattern = str(dir_path / "*_claude_signals_report.txt")
    files = glob.glob(pattern) + glob.glob(str(dir_path / "claude_signals_report.txt"))
    if not files:
        fallback = Path(GPT_SIGNALS_REPORT_TXT_PATH_US)
        return fallback if fallback.exists() else None

    def key(p: str) -> datetime:
        d = extract_date_from_filename(os.path.basename(p))
        return d if d else datetime.min

    return Path(max(files, key=key))


def _extract_surface_json_records(text: str) -> list[dict[str, Any]]:
    """Extract structured rows from <surface_json> block embedded in Claude txt report."""
    import re as _re
    import json as _json

    pattern = r"<surface_json>(.*?)</surface_json>"
    m = _re.search(pattern, text, _re.DOTALL)
    if not m:
        return []
    try:
        blob = _json.loads(m.group(1).strip())
        return blob.get("surface_data", [])
    except Exception:
        return []


def _parse_shortlist_structured_records(markdown: str) -> list[dict[str, Any]]:
    """
    Extract structured signal rows from Claude shortlist markdown text.
    Prefers <surface_json> embedded block; falls back to regex parsing.
    """
    # Prefer the authoritative surface_json block
    surface_rows = _extract_surface_json_records(markdown)
    if surface_rows:
        return surface_rows

    import re as _re

    records: list[dict[str, Any]] = []
    seen: set[str] = set()

    # Table row pattern: | SYMBOL | FUNCTION | DIRECTION | INTERVAL |
    table_row_pat = _re.compile(
        r"\|\s*([A-Z0-9.\-/]{1,12})\s*\|\s*([A-Z_\s]+?)\s*\|\s*(Long|Short|LONG|SHORT)\s*\|\s*([A-Za-z]+)\s*\|",
        _re.IGNORECASE,
    )
    symbol_line_pat = _re.compile(
        r"\*\*([A-Z0-9.\-/]{1,12})\*\*.*?(Long|Short|LONG|SHORT)",
        _re.IGNORECASE,
    )

    for line in markdown.splitlines():
        m = table_row_pat.search(line)
        if m:
            sym, fn, direction, interval = m.group(1), m.group(2).strip(), m.group(3).strip(), m.group(4).strip()
            key = f"{sym}|{fn}|{direction}|{interval}".upper()
            if key not in seen:
                seen.add(key)
                records.append({"symbol": sym, "function": fn, "direction": direction.title(), "interval": interval.title()})
            continue
        m = symbol_line_pat.search(line)
        if m:
            sym, direction = m.group(1), m.group(2)
            fn_match = _re.search(
                r"(TRENDPULSE|DELTADRIFT|OSCILLATOR[_\s]DELTA|SIGMASHELL|BASELINE[_\s]DIVERGENCE|FRACTAL[_\s]TRACK|PULSEGAUGE|BAND[_\s]MATRIX)",
                line, _re.IGNORECASE,
            )
            fn = fn_match.group(1).replace(" ", "_").upper() if fn_match else "UNKNOWN"
            interval_match = _re.search(r"\b(Daily|Weekly|Monthly|Yearly)\b", line, _re.IGNORECASE)
            interval = interval_match.group(1).title() if interval_match else "Daily"
            key = f"{sym}|{fn}|{direction}|{interval}".upper()
            if key not in seen:
                seen.add(key)
                records.append({"symbol": sym, "function": fn, "direction": direction.title(), "interval": interval})
    return records


def get_shortlist_report() -> dict[str, Any]:
    txt_path = _find_latest_claude_txt()
    csv_path = resolve_report_path("claude-shortlist")
    csv_df = _read_csv(csv_path) if csv_path else pd.DataFrame()

    markdown_text = ""
    if txt_path and txt_path.exists():
        try:
            markdown_text = txt_path.read_text(encoding="utf-8")
        except Exception:
            markdown_text = ""

    # Build structured records: prefer csv rows; fall back to txt parsing
    if not csv_df.empty:
        from api.services.signal_enrichment_service import enrich_records
        from src.utils.mtm_pricing import refresh_dataframe_current_prices

        csv_df = refresh_dataframe_current_prices(csv_df)
        structured_records = enrich_records(dataframe_to_records(csv_df))
    else:
        structured_records = _parse_shortlist_structured_records(markdown_text)

    return {
        "report_date": _report_date_from_path(txt_path) if txt_path else None,
        "text_file": str(txt_path) if txt_path else None,
        "csv_file": str(csv_path) if csv_path else None,
        "markdown": markdown_text,
        "row_count": len(structured_records),
        "records": structured_records,
    }


def load_virtual_trading(side: str) -> dict[str, Any]:
    side = side.lower()
    if side == "long":
        path = get_latest_csv_file("virtual_trading_long.csv", str(TRADE_STORE_US_DIR)) or str(VIRTUAL_TRADING_LONG_CSV)
    elif side == "short":
        path = get_latest_csv_file("virtual_trading_short.csv", str(TRADE_STORE_US_DIR)) or str(VIRTUAL_TRADING_SHORT_CSV)
    else:
        raise ValueError("side must be 'long' or 'short'")
    df = _read_csv(path)
    return {
        "side": side,
        "source_file": path,
        "row_count": int(len(df)),
        "records": dataframe_to_records(df),
    }


def portfolio_summary() -> dict[str, Any]:
    long_df = _read_csv(get_latest_csv_file("virtual_trading_long.csv", str(TRADE_STORE_US_DIR)) or VIRTUAL_TRADING_LONG_CSV)
    short_df = _read_csv(get_latest_csv_file("virtual_trading_short.csv", str(TRADE_STORE_US_DIR)) or VIRTUAL_TRADING_SHORT_CSV)

    def _open_count(df: pd.DataFrame) -> int:
        if df.empty or "Status" not in df.columns:
            return int(len(df))
        return int((df["Status"].astype(str).str.lower() == "open").sum())

    return {
        "long": {"row_count": int(len(long_df)), "open_count": _open_count(long_df)},
        "short": {"row_count": int(len(short_df)), "open_count": _open_count(short_df)},
        "combined_open": _open_count(long_df) + _open_count(short_df),
    }


def forced_portfolio_ytd() -> dict[str, Any]:
    """YTD unrealized+realized P&L proxy from virtual trading open positions entered this year."""
    year = datetime.now().year
    long_path = get_latest_csv_file("virtual_trading_long.csv", str(TRADE_STORE_US_DIR)) or str(VIRTUAL_TRADING_LONG_CSV)
    df = _read_csv(long_path)
    if df.empty:
        return {"forced_portfolio_ytd": 0.0, "year": year, "position_count": 0}
    profit_col = "Realised/Unrealised Profit"
    date_col = "Entry Date"
    if profit_col not in df.columns:
        return {"forced_portfolio_ytd": 0.0, "year": year, "position_count": int(len(df))}
    ytd_mask = df[date_col].astype(str).str.startswith(str(year)) if date_col in df.columns else pd.Series([True] * len(df))
    subset = df[ytd_mask]
    total = 0.0
    for val in subset[profit_col].astype(str):
        try:
            total += float(val.replace("%", "").strip())
        except ValueError:
            continue
    return {
        "forced_portfolio_ytd": round(total, 4),
        "year": year,
        "position_count": int(len(subset)),
    }


def latest_sigma() -> dict[str, Any]:
    path = resolve_report_path("sigma")
    df = _read_csv(path) if path else pd.DataFrame()
    return {
        "source_file": str(path) if path else None,
        "report_date": _report_date_from_path(path) if path else None,
        "row_count": int(len(df)),
        "records": dataframe_to_records(df),
    }


def latest_sentiment_signals() -> dict[str, Any]:
    path = resolve_report_path("sentiment")
    df = _read_csv(path) if path else pd.DataFrame()
    return {
        "source_file": str(path) if path else None,
        "report_date": _report_date_from_path(path) if path else None,
        "row_count": int(len(df)),
        "records": dataframe_to_records(df),
    }


def _mean_win_pct(df: pd.DataFrame) -> float | None:
    """Parse 'Win Percentage' column (e.g. '80.18%') and return mean."""
    if df.empty or "Win Percentage" not in df.columns:
        return None
    pct = pd.to_numeric(
        df["Win Percentage"].astype(str).str.rstrip("%").str.strip(),
        errors="coerce",
    )
    valid = pct.dropna()
    return round(float(valid.mean()), 2) if not valid.empty else None


def performance_summary() -> dict[str, Any]:
    path = resolve_report_path("combined-performance")
    df = _read_csv(path) if path else pd.DataFrame()
    summary: dict[str, Any] = {"source_file": str(path) if path else None, "row_count": int(len(df))}
    if not df.empty and "Win Percentage" in df.columns and "Function" in df.columns:
        # Dashboard KPI "Avg Fwd win rate" — Latest Performance section (~6mo rolling).
        latest_df = df[df["Function"] == "Latest Performance"]
        fwd_df = df[df["Function"] == "Forward Testing"]
        avg_latest = _mean_win_pct(latest_df)
        if avg_latest is not None:
            summary["avg_win_rate"] = avg_latest
        avg_fwd = _mean_win_pct(fwd_df)
        if avg_fwd is not None:
            summary["avg_fwd_testing_win_rate"] = avg_fwd
        bt_col = "Avg Backtested Win Rate [%]"
        if not latest_df.empty and bt_col in latest_df.columns:
            bt = pd.to_numeric(
                latest_df[bt_col].astype(str).str.rstrip("%").str.strip(),
                errors="coerce",
            ).dropna()
            if not bt.empty:
                summary["avg_backtest_win_rate"] = round(float(bt.mean()), 2)
        if "Total Analysed Trades" in df.columns and not latest_df.empty:
            summary["total_trades"] = int(latest_df["Total Analysed Trades"].sum())
    summary["records"] = dataframe_to_records(df)
    return summary


def load_runic_nightly() -> dict[str, Any]:
    if not MACRO_INTEL_JSON_PATH.exists():
        raise FileNotFoundError(f"Runic output not found: {MACRO_INTEL_JSON_PATH}")
    return json.loads(MACRO_INTEL_JSON_PATH.read_text(encoding="utf-8"))


def load_positioning() -> dict[str, Any]:
    if not SSI_POSITIONING_JSON.exists():
        raise FileNotFoundError(f"SSI positioning not found: {SSI_POSITIONING_JSON}")
    return json.loads(SSI_POSITIONING_JSON.read_text(encoding="utf-8"))


def _ensure_layer2_gate_votes(inputs: dict[str, Any]) -> dict[str, Any]:
    """Backfill six-gate vote rows when positioning.json predates layer2_gate_votes."""
    if not inputs or inputs.get("layer2_gate_votes"):
        return inputs
    layer2_components = inputs.get("layer2_components") or {}
    if not layer2_components:
        return inputs
    from src.sentiment_superindex.engine.layer2 import evaluate_layer2_gates

    legacy_votes = inputs.get("layer2_votes") or []
    confirmed, gate_votes = evaluate_layer2_gates(layer2_components, legacy_votes=legacy_votes)
    enriched = dict(inputs)
    enriched["layer2_gate_votes"] = gate_votes
    enriched["layer2_gate_confirmed_count"] = confirmed
    return enriched


def sentiment_layers() -> dict[str, Any]:
    positioning = load_positioning() if SSI_POSITIONING_JSON.exists() else {}
    signals = latest_sentiment_signals()
    layers = positioning.get("layers", {})
    composite = {
        "ssi_level": positioning.get("ssi_level"),
        "ssi_percentile_5y": positioning.get("ssi_percentile_5y"),
        "layer2_status": positioning.get("layer2_status"),
        "ssi_multiplier": positioning.get("ssi_multiplier"),
        "layers": layers,
    }
    layer_inputs = _ensure_layer2_gate_votes(positioning.get("inputs", {}) or {})
    return {
        "positioning": positioning,
        "composite": composite,
        "layer_inputs": layer_inputs,
        "layer2_votes": layer_inputs.get("layer2_votes", []),
        "layer2_gate_votes": layer_inputs.get("layer2_gate_votes", []),
        "layer2_gate_confirmed_count": layer_inputs.get("layer2_gate_confirmed_count"),
        "signal_rows": signals.get("records", []),
        "signal_report_date": signals.get("report_date"),
    }


def list_monitored_trades(*, refresh_prices: bool = False) -> list[dict[str, Any]]:
    if refresh_prices:
        update_monitored_trades_prices()
    df = load_monitored_trades()
    if df.empty:
        return []
    return dataframe_to_records(df)


def create_monitored_trade(trade: dict[str, Any]) -> dict[str, Any]:
    ok = add_trade_to_monitored(trade)
    if not ok:
        raise ValueError("Trade already exists or could not be saved")
    return trade


def delete_monitored_trade(trade_id: str) -> bool:
    return remove_trade_from_monitored(trade_id)
