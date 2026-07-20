"""Disk cache for forward-testing scans and degradation results."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import pandas as pd

from src.config_paths import (
    DATA_FETCH_DATETIME_JSON,
    MINDWEALTH_TRADE_STORE,
    VIRTUAL_TRADING_LONG_CSV,
    VIRTUAL_TRADING_SHORT_CSV,
)

OVERWATCH_STORE = Path(os.getenv("OVERWATCH_STORE_DIR", "overwatch_store"))
FWD_PARQUET = OVERWATCH_STORE / "fwd_trades.parquet"
FWD_MANIFEST = OVERWATCH_STORE / "fwd_trades_manifest.json"
DEGRADATION_RESULT_CACHE = OVERWATCH_STORE / "degradation_result_cache.json"
_FWD_ROOT = MINDWEALTH_TRADE_STORE / "forward_testing"

_USECOLS = [
    "Function",
    "Symbol",
    "Signal",
    "Interval",
    "Entry Date",
    "Exit Date",
    "Profit [%]",
    "Backtested Win Rate [%]",
]


def _read_csv_safe(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path, usecols=lambda c: c in _USECOLS)
    except ValueError:
        try:
            return pd.read_csv(path)
        except Exception:
            return pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def scan_fwd_manifest() -> dict[str, Any]:
    """Fast manifest: count + max mtime without reading CSV contents."""
    max_mtime = 0.0
    count = 0
    if _FWD_ROOT.exists():
        for csv_file in _FWD_ROOT.rglob("*.csv"):
            count += 1
            max_mtime = max(max_mtime, csv_file.stat().st_mtime)
    return {
        "csv_count": count,
        "max_csv_mtime": max_mtime,
        "data_fetch_mtime": DATA_FETCH_DATETIME_JSON.stat().st_mtime
        if DATA_FETCH_DATETIME_JSON.exists()
        else 0.0,
        "vt_long_mtime": VIRTUAL_TRADING_LONG_CSV.stat().st_mtime
        if VIRTUAL_TRADING_LONG_CSV.exists()
        else 0.0,
        "vt_short_mtime": VIRTUAL_TRADING_SHORT_CSV.stat().st_mtime
        if VIRTUAL_TRADING_SHORT_CSV.exists()
        else 0.0,
    }


def manifest_fingerprint(manifest: dict[str, Any]) -> str:
    return json.dumps(manifest, sort_keys=True)


def _manifest_matches(stored: dict[str, Any] | None, current: dict[str, Any]) -> bool:
    if not stored:
        return False
    return manifest_fingerprint(stored) == manifest_fingerprint(current)


def load_fwd_trades_df(*, force_rebuild: bool = False) -> pd.DataFrame:
    """Load concatenated forward-testing trades, using parquet cache when fresh."""
    OVERWATCH_STORE.mkdir(parents=True, exist_ok=True)
    manifest = scan_fwd_manifest()
    stored_manifest: dict[str, Any] | None = None
    if FWD_MANIFEST.exists():
        try:
            stored_manifest = json.loads(FWD_MANIFEST.read_text(encoding="utf-8"))
        except Exception:
            stored_manifest = None

    if (
        not force_rebuild
        and FWD_PARQUET.exists()
        and _manifest_matches(stored_manifest, manifest)
    ):
        try:
            return pd.read_parquet(FWD_PARQUET)
        except Exception:
            pass

    if not _FWD_ROOT.exists():
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []
    for fn_dir in _FWD_ROOT.iterdir():
        if not fn_dir.is_dir():
            continue
        function = fn_dir.name.replace("_", " ")
        for asset_dir in fn_dir.iterdir():
            if not asset_dir.is_dir():
                continue
            symbol = asset_dir.name
            for csv_file in asset_dir.glob("*.csv"):
                df = _read_csv_safe(csv_file)
                if df.empty:
                    continue
                if "Function" not in df.columns:
                    df["Function"] = function
                if "Symbol" not in df.columns:
                    df["Symbol"] = symbol
                frames.append(df)

    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not combined.empty:
        combined.to_parquet(FWD_PARQUET, index=False)
    FWD_MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return combined


def load_cached_degradation_result() -> dict[str, Any] | None:
    if not DEGRADATION_RESULT_CACHE.exists():
        return None
    try:
        payload = json.loads(DEGRADATION_RESULT_CACHE.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not _manifest_matches(payload.get("manifest"), scan_fwd_manifest()):
        return None
    return payload.get("result")


def save_degradation_result(result: dict[str, Any]) -> None:
    OVERWATCH_STORE.mkdir(parents=True, exist_ok=True)
    payload = {
        "manifest": scan_fwd_manifest(),
        "cached_at": time.time(),
        "result": result,
    }
    DEGRADATION_RESULT_CACHE.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
