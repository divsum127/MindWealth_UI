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


_AUDITED_AGENT_DIMENSIONS = ("ceo_quality", "competitive_moat")
_AGENT_CONFIDENCE_THRESHOLD = 0.70


def _bq_component_score(record: dict[str, Any], dimension: str) -> float | None:
    components = record.get("bq_components")
    value: Any = None
    if isinstance(components, dict):
        value = components.get(dimension)
    elif isinstance(components, list):
        for component in components:
            if not isinstance(component, dict):
                continue
            raw_name = str(component.get("name") or "").strip().lower().replace(" ", "_")
            if raw_name == dimension:
                value = component.get("score")
                break
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _statement_status(record: dict[str, Any], key: str, *, inverted: bool = False) -> str:
    asset_type = str(record.get("asset_type") or record.get("quote_type") or "").upper()
    if asset_type and asset_type not in {"EQUITY", "UNKNOWN"}:
        return "not_applicable"
    coverage = record.get("statement_coverage")
    if not isinstance(coverage, dict) or key not in coverage:
        return "not_recorded"
    available = bool(coverage.get(key))
    if inverted:
        available = not available
    return "available" if available else "unavailable"


def _pe_history_band(years: float, has_series: bool) -> str:
    if not has_series:
        return "no_series"
    if years >= 20:
        return "20_plus"
    if years >= 10:
        return "10_to_20"
    return "under_10"


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
            # Raw vs adjusted earnings multiple. A feed-read P/E prices SPK.NZ at 8.3x
            # when the business is on 18.4x, so both travel together and the caller can
            # see which one it is holding (Rohit 26 Aug, conviction spec gap 1).
            "pe_ttm": r.get("pe_ttm"),
            "pe_ttm_adjusted": r.get("pe_ttm_adjusted"),
            "adjusted_eps_ttm": r.get("adjusted_eps_ttm"),
            "adjusted_eps_basis": r.get("adjusted_eps_basis"),
            "one_off_pct_of_ni": r.get("one_off_pct_of_ni"),
            "one_off_review_needed": r.get("one_off_review_needed"),
            # Which of the four sourcing paths produced the adjusted figure, so a
            # screen can show whether it came from the issuer or from a statement row
            # (Rohit 1 Sep, section B).
            "adjusted_eps_source": r.get("adjusted_eps_source"),
            "one_off_sizing_cap_pct": r.get("one_off_sizing_cap_pct"),
            # Whether the agentic dimensions actually ran for this name. A 0 on an
            # agentic line means nothing without this (E1).
            "agent_dims_status": r.get("agent_dims_status"),
            # Whether a valuation module exists for this business type at all (section F).
            "framework_coverage": r.get("framework_coverage"),
            "sell_reason_code": r.get("sell_reason_code"),
            "last_daily_update": r.get("last_daily_update"),
        }
        for r in filtered
    ]


def get_ticker_record(ticker: str) -> dict[str, Any] | None:
    return load_record(ticker)


def recalculate_ticker(ticker: str) -> dict[str, Any]:
    from src.conviction_engine.fundamentals import update_ticker_fundamentals

    result = update_ticker_fundamentals(ticker, mode="full")
    record = load_record(ticker)
    return record if record is not None else result


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


def get_engine_audit() -> dict[str, Any]:
    """Expose the live safety and provenance state used by the dev verification UI."""
    records = list_records()
    pe_coverage = summarize_pe_history_distribution(records)
    pe_by_ticker = {
        str(row.get("ticker") or "").upper(): row
        for row in pe_coverage.get("tickers", [])
        if isinstance(row, dict)
    }

    rows: list[dict[str, Any]] = []
    for record in records:
        ticker = str(record.get("ticker") or "").upper()
        if not ticker:
            continue

        dividend_flag = record.get("dividend_cut_flag")
        dividend_triggered = bool(
            isinstance(dividend_flag, dict) and dividend_flag.get("triggered")
        )
        dividend_gate_recorded = (
            "dividend_cut_penalty_applied" in record
            or "dividend_cut_penalty_pending_approval" in record
        )
        if not dividend_gate_recorded:
            dividend_status = "not_recorded"
        elif record.get("dividend_cut_penalty_applied") is True:
            dividend_status = "applied"
        elif record.get("dividend_cut_penalty_pending_approval") is True:
            dividend_status = "pending_approval"
        else:
            dividend_status = "clear"

        provenance = record.get("agent_dim_provenance")
        provenance = provenance if isinstance(provenance, dict) else {}
        low_confidence_answers: list[str] = []
        low_confidence_neutralized: list[str] = []
        low_confidence_needs_recalc: list[str] = []
        for dimension in _AUDITED_AGENT_DIMENSIONS:
            detail = provenance.get(dimension)
            if not isinstance(detail, dict):
                continue
            try:
                confidence = float(detail.get("confidence"))
            except (TypeError, ValueError):
                continue
            if confidence >= _AGENT_CONFIDENCE_THRESHOLD:
                continue
            low_confidence_answers.append(dimension)
            score = _bq_component_score(record, dimension)
            if score == 0:
                low_confidence_neutralized.append(dimension)
            else:
                low_confidence_needs_recalc.append(dimension)

        framework_coverage = record.get("framework_coverage")
        if framework_coverage is True:
            framework_status = "covered"
        elif framework_coverage is False:
            framework_status = "coverage_incomplete"
        else:
            framework_status = "not_recorded"

        pe_row = pe_by_ticker.get(ticker, {})
        years_available = float(pe_row.get("years_available") or 0.0)
        has_pe_series = bool(pe_row.get("has_pe_series"))

        usage = record.get("agent_run_usage")
        usage = usage if isinstance(usage, dict) else None
        statement_coverage = record.get("statement_coverage")
        statement_coverage = statement_coverage if isinstance(statement_coverage, dict) else {}

        rows.append(
            {
                "ticker": ticker,
                "asset_type": record.get("asset_type") or record.get("quote_type"),
                "business_type": record.get("business_type"),
                "last_full_calc": record.get("last_full_calc"),
                "dividend_status": dividend_status,
                "dividend_triggered": dividend_triggered,
                "dividend_decline_pct": (
                    dividend_flag.get("decline_pct")
                    if isinstance(dividend_flag, dict)
                    else None
                ),
                "low_confidence_answers": low_confidence_answers,
                "low_confidence_neutralized": low_confidence_neutralized,
                "low_confidence_needs_recalc": low_confidence_needs_recalc,
                "agent_dims_status": record.get("agent_dims_status") or "not_recorded",
                "agent_run_usage": usage,
                "framework_status": framework_status,
                "framework_coverage_capped": record.get("framework_coverage_capped"),
                "pe_history_years": years_available,
                "pe_history_band": _pe_history_band(years_available, has_pe_series),
                "pe_has_series": has_pe_series,
                "quarterly_income_status": _statement_status(
                    record, "quarterly_income_empty", inverted=True
                ),
                "prior_year_cashflow_status": _statement_status(
                    record, "cashflow_prior_year_available"
                ),
                "statement_fetch_errors": list(record.get("fetch_errors") or []),
                "adjusted_eps_source": record.get("adjusted_eps_source"),
                "adjusted_eps_basis": record.get("adjusted_eps_basis"),
                "one_off_review_needed": bool(record.get("one_off_review_needed")),
                "one_off_sizing_cap_pct": record.get("one_off_sizing_cap_pct"),
                "statement_coverage_recorded": bool(statement_coverage),
            }
        )

    rows.sort(key=lambda row: row["ticker"])
    equity_rows = [
        row
        for row in rows
        if str(row.get("asset_type") or "").upper() in {"", "EQUITY", "UNKNOWN"}
    ]

    return {
        "policies": {
            "dividend_penalty_requires_explicit_approval": True,
            "dividend_hard_exit_requires_approved_penalty": True,
            "agent_confidence_threshold": _AGENT_CONFIDENCE_THRESHOLD,
            "pe_full_confidence_years": int(pe_coverage.get("target_years") or 20),
            "short_history_pe_policy": "pending_rohit_decision_strict_20y_active",
        },
        "summary": {
            "total_records": len(rows),
            "equity_records": len(equity_rows),
            "dividend_pending_approval": sum(
                row["dividend_status"] == "pending_approval" for row in rows
            ),
            "dividend_penalty_applied": sum(
                row["dividend_status"] == "applied" for row in rows
            ),
            "dividend_gate_not_recorded": sum(
                row["dividend_status"] == "not_recorded" for row in rows
            ),
            "low_confidence_answers": sum(
                len(row["low_confidence_answers"]) for row in rows
            ),
            "low_confidence_neutralized": sum(
                len(row["low_confidence_neutralized"]) for row in rows
            ),
            "low_confidence_needs_recalc": sum(
                len(row["low_confidence_needs_recalc"]) for row in rows
            ),
            "framework_incomplete": sum(
                row["framework_status"] == "coverage_incomplete" for row in rows
            ),
            "framework_not_recorded": sum(
                row["framework_status"] == "not_recorded" for row in rows
            ),
            "framework_capped": sum(
                row["framework_coverage_capped"] is True for row in rows
            ),
            "agent_runs_metered": sum(row["agent_run_usage"] is not None for row in rows),
            "statement_coverage_recorded": sum(
                row["statement_coverage_recorded"] for row in rows
            ),
            "pe_20_plus": sum(row["pe_history_band"] == "20_plus" for row in rows),
            "pe_10_to_20": sum(row["pe_history_band"] == "10_to_20" for row in rows),
            "pe_under_10": sum(row["pe_history_band"] == "under_10" for row in rows),
            "pe_no_series": sum(row["pe_history_band"] == "no_series" for row in rows),
        },
        "records": rows,
    }


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
