"""Shared confirmation-status checks for signal CSV rows."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

INTERVAL_CONFIRMATION_COL = "Interval, Confirmation Status"


def is_confirmed_signal(confirmation_status_value: Any) -> bool:
    """
    True when status is or was CONFIRMED (matches convert_signals_to_data_structure).
    """
    if confirmation_status_value is None or (
        isinstance(confirmation_status_value, float) and pd.isna(confirmation_status_value)
    ):
        return False
    status_str = str(confirmation_status_value).strip()
    if not status_str or status_str.lower() == "nan":
        return False
    return bool(re.search(r"\b(is|was)\s+CONFIRMED\b", status_str, re.IGNORECASE))
