"""CBOE SKEW index via Yahoo."""

from __future__ import annotations

import pandas as pd

from src.sentiment_superindex.data.yahoo_inputs import fetch_close


def fetch_skew(start: str = "1990-01-01") -> pd.Series:
    return fetch_close("^SKEW", start)
