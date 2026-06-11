"""Yahoo pulls for SSI inputs (reuse Runic yahoo helpers)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.macro_intelligence.data.yahoo_pull import fetch_yahoo_close


def fetch_close(ticker: str, start: str = "2010-01-01") -> pd.Series:
    return fetch_yahoo_close(ticker, start=start)


def hyg_lqd_ratio(start: str = "2010-01-01") -> pd.Series:
    hyg = fetch_yahoo_close("HYG", start=start)
    lqd = fetch_yahoo_close("LQD", start=start)
    df = pd.DataFrame({"hyg": hyg, "lqd": lqd}).dropna()
    return (df["hyg"] / df["lqd"]).rename("hyg_lqd")


def vix_ratio_series(start: str = "2007-01-01") -> pd.Series:
    vix = fetch_yahoo_close("^VIX", start=start)
    vix3m = fetch_yahoo_close("^VIX3M", start=start)
    df = pd.DataFrame({"vix": vix, "vix3m": vix3m}).dropna()
    return (df["vix3m"] / df["vix"]).rename("vix_ratio")


def dbmf_beta_vs_spy(window: int = 21, start: str = "2015-01-01") -> pd.Series:
    dbmf = fetch_yahoo_close("DBMF", start=start)
    spy = fetch_yahoo_close("SPY", start=start)
    dbmf_ret = dbmf.pct_change()
    spy_ret = spy.pct_change()
    aligned = pd.DataFrame({"dbmf": dbmf_ret, "spy": spy_ret}).dropna()
    cov = aligned["dbmf"].rolling(window).cov(aligned["spy"])
    var = aligned["spy"].rolling(window).var()
    beta = cov / var.replace(0, np.nan)
    return beta.rename("dbmf_beta")
