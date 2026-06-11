"""CPI surprise data — manual CSV cache or FRED CPIAUCSL proxy."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config_paths import MACRO_INTEL_DATA_DIR

CPI_CACHE = MACRO_INTEL_DATA_DIR / "cpi_surprises.csv"
REQUIRED_COLUMNS = {"date", "surprise_pp"}


def load_cpi_surprises() -> pd.Series:
    """Actual minus consensus in percentage points. Seed file optional."""
    if CPI_CACHE.exists():
        df = pd.read_csv(CPI_CACHE, parse_dates=["date"])
        df = df.set_index("date")["surprise_pp"].sort_index()
        return df.astype(float)
    return pd.Series(dtype=float)


def validate_cpi_csv(path: Path | None = None) -> tuple[bool, str]:
    """Validate CPI surprises file schema."""
    path = path or CPI_CACHE
    if not path.exists():
        return False, f"missing file: {path}"
    try:
        df = pd.read_csv(path)
    except Exception as e:
        return False, str(e)
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        return False, f"missing columns: {missing}"
    if df.empty:
        return False, "empty file"
    if df["surprise_pp"].isna().all():
        return False, "all surprise_pp null"
    return True, "ok"


def save_cpi_surprise(
    date: str,
    surprise_pp: float,
    actual: float | None = None,
    consensus: float | None = None,
) -> None:
    CPI_CACHE.parent.mkdir(parents=True, exist_ok=True)
    row: dict = {"date": date, "surprise_pp": surprise_pp}
    if actual is not None:
        row["actual"] = actual
    if consensus is not None:
        row["consensus"] = consensus
    new = pd.DataFrame([row])
    if CPI_CACHE.exists():
        existing = pd.read_csv(CPI_CACHE)
        existing = existing[existing["date"].astype(str) != date]
        new = pd.concat([existing, new], ignore_index=True)
    new.to_csv(CPI_CACHE, index=False)


def ingest_release(date: str, actual: float, consensus: float) -> float:
    """Compute surprise_pp = actual - consensus and persist."""
    from src.macro_intelligence.data.bls_pull import ingest_cpi_release

    surprise = ingest_cpi_release(date, actual, consensus, source="manual")
    save_cpi_surprise(date, surprise, actual=actual, consensus=consensus)
    return surprise
