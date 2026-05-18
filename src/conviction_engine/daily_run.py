"""Daily conviction pipeline: fundamentals refresh + signal overlays + dated archives."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from ..utils.atomic_io import write_dataframe_csv_atomic_guarded
from .engine import apply_to_signal_file, generate_daily_report, run_daily_universe
from .formatting import CONVICTION_COLUMNS, summarize_overlay
from .fundamentals import discover_universe, update_universe_fundamentals
from .models import utc_now_iso
from .signals import (
    COMPOUND_SIGNAL_COLUMN,
    PRIMARY_DAILY_REPORT,
    discover_daily_signal_files,
    resolve_report_date,
)
from .store import (
    daily_overlay_path,
    daily_snapshot_dir,
    list_records,
    overlay_path,
    sanitize_ticker,
)


def conviction_score_sheet(overlay_df: pd.DataFrame) -> pd.DataFrame:
    """Compact per-signal conviction columns for daily score sheets."""
    if overlay_df.empty:
        return overlay_df
    signal_col = COMPOUND_SIGNAL_COLUMN if COMPOUND_SIGNAL_COLUMN in overlay_df.columns else None
    prefix = ["Function", signal_col] if signal_col else ["Function"]
    cols = [c for c in prefix + CONVICTION_COLUMNS if c in overlay_df.columns]
    return overlay_df[cols].copy()


def run_daily_conviction_pipeline(
    *,
    report_date: str | None = None,
    trade_store_dir: Path | None = None,
    store_dir: Path | None = None,
    fundamentals_mode: str = "daily",
    skip_fundamentals: bool = False,
    skip_overlays: bool = False,
    dry_run: bool = False,
    fail_fast: bool = False,
    limit: int | None = None,
    overlay_reports: list[str] | None = None,
) -> dict[str, Any]:
    """
    1. Refresh conviction_store fundamentals (default: daily price-sensitive).
    2. Overlay conviction scores onto daily New Signals report (default) and archive.
    3. Archive full overlays + compact score sheets under conviction_store/daily/YYYY-MM-DD/.
    4. Refresh conviction_store/overlays/* for latest UI consumption.
    """
    if overlay_reports is None:
        overlay_reports = [PRIMARY_DAILY_REPORT]

    resolved_date = resolve_report_date(trade_store_dir, report_date)
    if not resolved_date:
        return {"status": "error", "error": "Could not resolve report date from trade_store"}

    signal_files = discover_daily_signal_files(resolved_date, trade_store_dir, overlay_reports)
    if not signal_files:
        return {
            "status": "error",
            "report_date": resolved_date,
            "error": "No daily signal report CSVs found for this date",
        }

    tickers = discover_universe(
        trade_store_dir=trade_store_dir,
        include_existing_records=True,
        include_signal_sources=True,
    )
    if limit is not None:
        tickers = tickers[:limit]

    fundamentals_result: list[dict[str, Any]] = []
    if not skip_fundamentals and tickers:
        fundamentals_result = update_universe_fundamentals(
            tickers,
            mode=fundamentals_mode,
            store_dir=store_dir,
            dry_run=dry_run,
            fail_fast=fail_fast,
        )

    snapshot_dir = daily_snapshot_dir(resolved_date, store_dir)
    report_entries: list[dict[str, Any]] = []
    overlay_errors: list[str] = []

    if not skip_overlays and not dry_run:
        for label, source_path in signal_files.items():
            try:
                overlay_df = apply_to_signal_file(
                    source_path,
                    store_dir=store_dir,
                    save_output=False,
                    update_layers=False,
                )
                if overlay_df.empty:
                    report_entries.append(
                        {
                            "label": label,
                            "source_file": str(source_path),
                            "rows": 0,
                            "status": "empty",
                        }
                    )
                    continue

                summary = summarize_overlay(overlay_df)
                full_latest = overlay_path(source_path)
                full_daily = daily_overlay_path(source_path, resolved_date, store_dir)
                scores_latest = full_latest.parent / f"{source_path.stem}_conviction_scores.csv"
                scores_daily = snapshot_dir / f"{source_path.stem}_conviction_scores.csv"

                write_dataframe_csv_atomic_guarded(overlay_df, full_latest)
                write_dataframe_csv_atomic_guarded(overlay_df, full_daily)
                score_df = conviction_score_sheet(overlay_df)
                write_dataframe_csv_atomic_guarded(score_df, scores_latest)
                write_dataframe_csv_atomic_guarded(score_df, scores_daily)

                report_entries.append(
                    {
                        "label": label,
                        "source_file": str(source_path),
                        "overlay_file": str(full_daily),
                        "conviction_scores_file": str(scores_daily),
                        "latest_overlay_file": str(full_latest),
                        "rows": int(len(overlay_df)),
                        "summary": summary,
                        "status": "ok",
                    }
                )
            except Exception as exc:
                msg = f"{label}: {exc}"
                overlay_errors.append(msg)
                report_entries.append(
                    {
                        "label": label,
                        "source_file": str(source_path),
                        "status": "error",
                        "error": str(exc),
                    }
                )
                if fail_fast:
                    raise

    records = list_records(store_dir)
    if not skip_fundamentals and tickers:
        alert_map = run_daily_universe([sanitize_ticker(t) for t in tickers], store_dir=store_dir)
    else:
        alert_map = {}
        for record in records:
            flags: list[str] = []
            if record.get("yield_trap_warning"):
                flags.append("yield_trap")
            if record.get("fs_class") in {"weak", "moderate_low"}:
                flags.append(f"fs_{record.get('fs_class')}")
            if (record.get("conviction_score") or 0) < 2:
                flags.append("low_conviction")
            ticker = record.get("ticker")
            if flags and ticker:
                alert_map[sanitize_ticker(str(ticker))] = flags
    daily_report_text = generate_daily_report(alert_map, records)

    manifest: dict[str, Any] = {
        "report_date": resolved_date,
        "generated_at": utc_now_iso(),
        "fundamentals_mode": fundamentals_mode,
        "skip_fundamentals": skip_fundamentals,
        "dry_run": dry_run,
        "tickers_in_universe": len(tickers),
        "fundamentals_updated": sum(1 for r in fundamentals_result if r.get("status") == "updated"),
        "fundamentals_errors": sum(1 for r in fundamentals_result if r.get("status") == "error"),
        "signal_reports": report_entries,
        "overlay_errors": overlay_errors,
        "overlay_reports": overlay_reports,
        "snapshot_dir": str(snapshot_dir),
        "daily_report": daily_report_text,
    }

    if not dry_run:
        manifest_path = snapshot_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, default=str) + "\n", encoding="utf-8")
        (snapshot_dir / "daily_report.txt").write_text(daily_report_text + "\n", encoding="utf-8")

    status = "completed"
    if overlay_errors:
        status = "completed_with_overlay_errors"
    if any(r.get("status") == "error" for r in fundamentals_result):
        status = "completed_with_errors" if status == "completed" else status

    return {
        "status": status,
        **manifest,
        "fundamentals_results": fundamentals_result,
    }
