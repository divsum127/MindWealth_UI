"""CFTC TFF report parsing for net spec positioning."""

from __future__ import annotations

import io
import zipfile
from datetime import datetime

import pandas as pd
import requests

CFTC_HIST_URL = "https://www.cftc.gov/files/dea/history/deacot{year}.zip"


def _year_urls(year: int) -> str:
    return CFTC_HIST_URL.format(year=year)


def fetch_cftc_fast_money_net(start_year: int = 2006) -> pd.Series:
    """Net spec from Leveraged Money positions on E-mini S&P futures."""
    frames: list[pd.DataFrame] = []
    current_year = datetime.now().year
    for year in range(start_year, current_year + 1):
        url = _year_urls(year)
        try:
            resp = requests.get(url, timeout=60)
            if resp.status_code != 200:
                continue
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                for name in zf.namelist():
                    if not name.endswith(".txt"):
                        continue
                    with zf.open(name) as f:
                        try:
                            df = pd.read_csv(f, low_memory=False)
                        except Exception:
                            continue
                        frames.append(df)
        except Exception:
            continue

    if not frames:
        return pd.Series(dtype=float)

    df = pd.concat(frames, ignore_index=True)
    # TFF: filter S&P 500 futures, Lev Money
    market_col = _find_col(df, ["Market_and_Exchange_Names", "Market and Exchange Names"])
    cat_col = _find_col(df, ["Traders_Classification", "Trader Classification", "Traders Classification"])
    if market_col is None:
        return pd.Series(dtype=float)

    mask = df[market_col].astype(str).str.contains("S&P 500", case=False, na=False)
    if cat_col:
        mask &= df[cat_col].astype(str).str.contains("Lev Money|Leveraged Funds", case=False, na=False)

    sub = df.loc[mask].copy()
    date_col = _find_col(sub, ["Report_Date_as_YYYY-MM-DD", "Report_Date", "As of Date in Form YYYY-MM-DD"])
    long_col = _find_col(sub, ["Lev_Money_Positions_Long_All", "Lev Money Positions-Long-All"])
    short_col = _find_col(sub, ["Lev_Money_Positions_Short_All", "Lev Money Positions-Short-All"])

    if date_col is None or long_col is None or short_col is None:
        return pd.Series(dtype=float)

    sub[date_col] = pd.to_datetime(sub[date_col], errors="coerce")
    sub["net"] = pd.to_numeric(sub[long_col], errors="coerce") - pd.to_numeric(sub[short_col], errors="coerce")
    out = sub.groupby(date_col)["net"].sum().sort_index()
    out.index = pd.to_datetime(out.index)
    return out.dropna()


def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    cols = {c.strip(): c for c in df.columns}
    for cand in candidates:
        for col in df.columns:
            if col.strip() == cand or cand.lower() in col.lower():
                return col
    return None
