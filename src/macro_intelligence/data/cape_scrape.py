"""CAPE / Shiller P/E from multpl.com or local cache."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

from src.config_paths import MACRO_INTEL_DATA_DIR

CAPE_CACHE = MACRO_INTEL_DATA_DIR / "cape_history.csv"
MULTPL_URL = "https://www.multpl.com/shiller-pe/table/by-month"


def load_cape_series() -> pd.Series:
    if CAPE_CACHE.exists():
        df = pd.read_csv(CAPE_CACHE, parse_dates=["date"])
        return df.set_index("date")["cape"].sort_index().astype(float)
    return fetch_cape_history()


def fetch_cape_history() -> pd.Series:
    try:
        resp = requests.get(MULTPL_URL, timeout=30, headers={"User-Agent": "MindWealth-Runic/2.2"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        table = soup.find("table")
        if table is None:
            return _fallback_cape()
        rows = []
        for tr in table.find_all("tr")[1:]:
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(cells) < 2:
                continue
            date_str, val_str = cells[0], cells[1]
            val = re.sub(r"[^\d.]", "", val_str)
            if not val:
                continue
            try:
                rows.append({"date": pd.to_datetime(date_str), "cape": float(val)})
            except Exception:
                continue
        if not rows:
            return _fallback_cape()
        df = pd.DataFrame(rows).set_index("date").sort_index()
        CAPE_CACHE.parent.mkdir(parents=True, exist_ok=True)
        df.reset_index().to_csv(CAPE_CACHE, index=False)
        return df["cape"]
    except Exception:
        return _fallback_cape()


def _fallback_cape() -> pd.Series:
    """FRED does not host CAPE; return empty if scrape fails."""
    if CAPE_CACHE.exists():
        df = pd.read_csv(CAPE_CACHE, parse_dates=["date"])
        return df.set_index("date")["cape"].sort_index().astype(float)
    return pd.Series(dtype=float)
