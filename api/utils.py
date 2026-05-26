"""Shared API helpers."""

from __future__ import annotations

from typing import Any

import pandas as pd


def dataframe_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    clean = df.where(pd.notnull(df), None)
    return clean.to_dict(orient="records")
