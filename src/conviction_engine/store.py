"""JSON persistence for Conviction Engine records."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from ..config_paths import CONVICTION_OUTPUT_DIR, CONVICTION_STORE_DIR
from .models import default_record, utc_now_iso


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
