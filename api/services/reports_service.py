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


def load_report_records(report_name: str, report_date: str | None = None) -> dict[str, Any]:
    path = resolve_report_path(report_name, report_date)
    if path is None:
        raise FileNotFoundError(f"Report not found: {report_name!r} date={report_date!r}")
    df = _read_csv(path)
    if report_name.lower().replace("-", "_") in ("claude_shortlist", "claude_signals_report", "claude-shortlist"):
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
    return {
        "report_name": report_name,
        "source_file": str(path),
        "report_date": _report_date_from_path(path),
        "format": "csv",
        "row_count": int(len(df)),
        "records": dataframe_to_records(df),
    }


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


def get_shortlist_report() -> dict[str, Any]:
    txt_path = _find_latest_claude_txt()
    csv_path = resolve_report_path("claude-shortlist")
    csv_df = _read_csv(csv_path) if csv_path else pd.DataFrame()
    return {
        "report_date": _report_date_from_path(txt_path) if txt_path else None,
        "text_file": str(txt_path) if txt_path else None,
        "csv_file": str(csv_path) if csv_path else None,
        "markdown": txt_path.read_text(encoding="utf-8") if txt_path and txt_path.exists() else "",
        "row_count": int(len(csv_df)),
        "records": dataframe_to_records(csv_df),
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


def performance_summary() -> dict[str, Any]:
    path = resolve_report_path("combined-performance")
    df = _read_csv(path) if path else pd.DataFrame()
    summary: dict[str, Any] = {"source_file": str(path) if path else None, "row_count": int(len(df))}
    if not df.empty and "Win_Percentage" in df.columns:
        summary["avg_win_rate"] = float(df["Win_Percentage"].mean())
        summary["total_trades"] = int(df["Total_Trades"].sum()) if "Total_Trades" in df.columns else None
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


def sentiment_layers() -> dict[str, Any]:
    positioning = load_positioning() if SSI_POSITIONING_JSON.exists() else {}
    signals = latest_sentiment_signals()
    return {
        "positioning": positioning,
        "composite": {
            "ssi_level": positioning.get("ssi_level"),
            "ssi_percentile_5y": positioning.get("ssi_percentile_5y"),
            "layer2_status": positioning.get("layer2_status"),
            "ssi_multiplier": positioning.get("ssi_multiplier"),
        },
        "layer_inputs": positioning.get("inputs", {}),
        "layer2_votes": (positioning.get("inputs") or {}).get("layer2_votes", []),
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
