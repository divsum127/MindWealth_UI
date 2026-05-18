"""JSON persistence for Conviction Engine records."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

from ..config_paths import CONVICTION_OUTPUT_DIR, CONVICTION_STORE_DIR
from .models import default_record, utc_now_iso
from .signals import PRIMARY_DAILY_REPORT

_DATE_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def sanitize_ticker(ticker: str) -> str:
    return str(ticker).strip().upper().replace("/", "_").replace("\\", "_")


def record_path(ticker: str, store_dir: Path | None = None) -> Path:
    base_dir = Path(store_dir) if store_dir else CONVICTION_STORE_DIR
    return base_dir / f"{sanitize_ticker(ticker)}.json"


def load_record(ticker: str, store_dir: Path | None = None) -> dict[str, Any] | None:
    path = record_path(ticker, store_dir)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_or_create_record(ticker: str, store_dir: Path | None = None) -> dict[str, Any]:
    return load_record(ticker, store_dir) or default_record(sanitize_ticker(ticker))


def save_record(record: dict[str, Any], store_dir: Path | None = None) -> Path:
    ticker = record.get("ticker")
    if not ticker:
        raise ValueError("record must include a ticker")

    path = record_path(str(ticker), store_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    record["updated_at"] = utc_now_iso()

    fd, tmp = tempfile.mkstemp(prefix=".tmp_", suffix=".json", dir=path.parent)
    os.close(fd)
    tmp_path = Path(tmp)
    try:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(record, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp_path, path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    return path


def list_records(store_dir: Path | None = None) -> list[dict[str, Any]]:
    base_dir = Path(store_dir) if store_dir else CONVICTION_STORE_DIR
    if not base_dir.exists():
        return []

    records: list[dict[str, Any]] = []
    for path in sorted(base_dir.glob("*.json")):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                records.append(json.load(fh))
        except (OSError, json.JSONDecodeError):
            continue
    return records


def overlay_path(source_file: Path | str) -> Path:
    source_path = Path(source_file)
    CONVICTION_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return CONVICTION_OUTPUT_DIR / f"{source_path.stem}_conviction.csv"


def daily_snapshot_dir(report_date: str, store_dir: Path | None = None) -> Path:
    """Dated folder for archived conviction overlays (YYYY-MM-DD)."""
    base = Path(store_dir) if store_dir else CONVICTION_STORE_DIR
    path = base / "daily" / str(report_date).strip()
    path.mkdir(parents=True, exist_ok=True)
    return path


def daily_overlay_path(source_file: Path | str, report_date: str, store_dir: Path | None = None) -> Path:
    source_path = Path(source_file)
    return daily_snapshot_dir(report_date, store_dir) / f"{source_path.stem}_conviction.csv"


def _daily_root(store_dir: Path | None = None) -> Path:
    base = Path(store_dir) if store_dir else CONVICTION_STORE_DIR
    return base / "daily"


def list_daily_snapshot_dates(store_dir: Path | None = None) -> list[str]:
    """Sorted YYYY-MM-DD dates with archived daily conviction snapshots."""
    daily_root = _daily_root(store_dir)
    if not daily_root.exists():
        return []
    dates = [p.name for p in daily_root.iterdir() if p.is_dir() and _DATE_DIR_RE.match(p.name)]
    return sorted(dates)


def daily_new_signal_overlay_path(report_date: str, store_dir: Path | None = None) -> Path | None:
    """Path to archived New Signals full overlay CSV for a report date."""
    snapshot = daily_snapshot_dir(report_date, store_dir)
    manifest_path = snapshot / "manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for entry in manifest.get("signal_reports") or []:
                overlay_file = entry.get("overlay_file")
                if overlay_file and Path(overlay_file).exists():
                    return Path(overlay_file)
        except (OSError, json.JSONDecodeError, TypeError):
            pass

    candidates = [
        snapshot / f"{report_date}_new_signal_conviction.csv",
        snapshot / f"{report_date}_{PRIMARY_DAILY_REPORT.replace('.csv', '')}_conviction.csv",
    ]
    for path in candidates:
        if path.exists():
            return path
    matches = sorted(snapshot.glob("*new_signal*_conviction.csv"))
    return matches[0] if matches else None


def load_daily_new_signal_overlay(report_date: str, store_dir: Path | None = None) -> pd.DataFrame:
    """Load archived New Signals conviction overlay for a report date."""
    path = daily_new_signal_overlay_path(report_date, store_dir)
    if path is None or not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (OSError, pd.errors.EmptyDataError):
        return pd.DataFrame()
