"""CPI surprise data — manual CSV cache or FRED CPIAUCSL proxy."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config_paths import MACRO_INTEL_DATA_DIR

CPI_CACHE = MACRO_INTEL_DATA_DIR / "cpi_surprises.csv"


def load_cpi_surprises() -> pd.Series:
    """Actual minus consensus in percentage points. Seed file optional."""
    if CPI_CACHE.exists():
        df = pd.read_csv(CPI_CACHE, parse_dates=["date"])
        df = df.set_index("date")["surprise_pp"].sort_index()
        return df.astype(float)
    return pd.Series(dtype=float)


def save_cpi_surprise(date: str, surprise_pp: float) -> None:
    CPI_CACHE.parent.mkdir(parents=True, exist_ok=True)
    row = pd.DataFrame([{"date": date, "surprise_pp": surprise_pp}])
    if CPI_CACHE.exists():
        existing = pd.read_csv(CPI_CACHE)
        existing = existing[existing["date"] != date]
        row = pd.concat([existing, row], ignore_index=True)
    row.to_csv(CPI_CACHE, index=False)
