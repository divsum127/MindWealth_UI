"""Thin adapters over src.conviction_engine."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.config_paths import CONVICTION_STORE_DIR, TRADE_STORE_US_DIR
from src.conviction_engine import (
    apply_to_signal_file,
    daily_update,
    full_recalculation,
    generate_daily_report,
    modify_signal,
    run_daily_conviction_pipeline,
    run_daily_universe,
    update_overrides,
)
from src.conviction_engine.daily_run import conviction_score_sheet
from src.conviction_engine.data_coverage import summarize_pe_history_distribution
from src.conviction_engine.formatting import summarize_overlay
from src.conviction_engine.fundamentals import discover_universe
from src.conviction_engine.signals import resolve_report_date, signal_file_for_report_date
from src.conviction_engine.store import (
    daily_new_signal_overlay_path,
    list_daily_snapshot_dates,
    list_records,
    load_daily_new_signal_overlay,
    load_record,
    sanitize_ticker,
)

from api.utils import dataframe_to_records


def _filter_records(
    records: list[dict[str, Any]],
    *,
    fs_class: str | None,
    yield_trap: bool | None,
    limit: int | None,
    offset: int,
) -> list[dict[str, Any]]:
    filtered = records
    if fs_class:
        filtered = [r for r in filtered if str(r.get("fs_class") or "").lower() == fs_class.lower()]
    if yield_trap is not None:
        filtered = [r for r in filtered if bool(r.get("yield_trap_warning")) == yield_trap]
    if offset:
        filtered = filtered[offset:]
    if limit is not None:
        filtered = filtered[:limit]
    return filtered


def list_ticker_records(
    *,
    fs_class: str | None = None,
    yield_trap: bool | None = None,
    limit: int | None = None,
    offset: int = 0,
    fields: str | None = "summary",
) -> list[dict[str, Any]]:
    records = list_records()
    filtered = _filter_records(records, fs_class=fs_class, yield_trap=yield_trap, limit=limit, offset=offset)
    if fields == "full":
        return filtered
    return [
        {
            "ticker": r.get("ticker"),
            "asset_type": r.get("asset_type"),
            "business_type": r.get("business_type"),
            "bq_raw": r.get("bq_raw"),
            "conviction_score": r.get("conviction_score"),
            "fs_class": r.get("fs_class"),
            "yield_trap_warning": r.get("yield_trap_warning"),
            "last_daily_update": r.get("last_daily_update"),
        }
        for r in filtered
    ]


def get_ticker_record(ticker: str) -> dict[str, Any] | None:
    return load_record(ticker)


def recalculate_ticker(ticker: str) -> dict[str, Any]:
    return full_recalculation(ticker)


def daily_refresh_ticker(ticker: str) -> dict[str, Any]:
    return daily_update(ticker)


def patch_ticker_overrides(ticker: str, overrides: dict[str, Any], *, recompute: bool = True) -> dict[str, Any]:
    return update_overrides(ticker, overrides, recompute=recompute)


def evaluate_signal(**kwargs: Any) -> dict[str, Any]:
    mod = modify_signal(**kwargs)
    return mod.to_dict()


def overlay_signal_file(
    *,
    report_date: str | None,
    report_name: str,
    save_output: bool,
    update_layers: bool,
) -> dict[str, Any]:
    resolved_date = report_date or resolve_report_date(TRADE_STORE_US_DIR) or ""
    path = signal_file_for_report_date(report_name, resolved_date, TRADE_STORE_US_DIR)
    if path is None or not path.exists():
        raise FileNotFoundError(f"No signal file found for report_name={report_name!r}, date={report_date!r}")
    df = apply_to_signal_file(
        path,
        save_output=save_output,
        update_layers=update_layers,
    )
    if df.empty and "claude" in report_name.lower():
        from api.services import reports_service as reports

        shortlist = reports.get_shortlist_report()
        return {
            "source_file": str(path),
            "row_count": 0,
            "summary": summarize_overlay(df),
            "records": [],
            "csv_empty": True,
            "shortlist": shortlist,
        }
    return {
        "source_file": str(path),
        "row_count": int(len(df)),
        "summary": summarize_overlay(df),
        "records": dataframe_to_records(df),
    }


def get_overlay_dates() -> list[str]:
    return list_daily_snapshot_dates()


def get_new_signals_overlay(report_date: str) -> dict[str, Any]:
    df = load_daily_new_signal_overlay(report_date)
    path = daily_new_signal_overlay_path(report_date)
    return {
        "report_date": report_date,
        "overlay_file": str(path) if path else None,
        "row_count": int(len(df)),
        "records": dataframe_to_records(df),
    }


def get_overlay_summary(report_date: str) -> dict[str, Any]:
    df = load_daily_new_signal_overlay(report_date)
    if df.empty:
        return summarize_overlay(df)
    return summarize_overlay(df)


def get_score_sheet(report_date: str) -> dict[str, Any]:
    df = load_daily_new_signal_overlay(report_date)
    sheet = conviction_score_sheet(df)
    return {
        "report_date": report_date,
        "row_count": int(len(sheet)),
        "records": dataframe_to_records(sheet),
    }


def get_universe() -> list[str]:
    return discover_universe(include_existing_records=True, include_signal_sources=True)


def get_pe_history_coverage() -> dict[str, Any]:
    return summarize_pe_history_distribution(list_records())


def run_pipeline(**kwargs: Any) -> dict[str, Any]:
    return run_daily_conviction_pipeline(**kwargs)


def get_daily_alerts() -> dict[str, Any]:
    records = list_records()
    tickers = [sanitize_ticker(str(r.get("ticker"))) for r in records if r.get("ticker")]
    alert_map = run_daily_universe(tickers)
    report_text = generate_daily_report(alert_map, records)
    return {"alerts": alert_map, "report": report_text, "universe_size": len(records)}


def conviction_store_writable() -> bool:
    try:
        CONVICTION_STORE_DIR.mkdir(parents=True, exist_ok=True)
        test = CONVICTION_STORE_DIR / ".api_write_test"
        test.write_text("", encoding="utf-8")
        test.unlink(missing_ok=True)
        return True
    except OSError:
        return False
