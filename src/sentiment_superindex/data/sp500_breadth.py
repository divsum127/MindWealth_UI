"""NYSE-style breadth from full S&P 500 universe (yfinance)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import yfinance as yf

from src.sentiment_superindex.data.sp500_universe import load_sp500_tickers
from src.sentiment_superindex.data.pull_guard import log_pull_empty, log_pull_failure

MIN_HISTORY_DAYS = 220
CHUNK_SIZE = 40


def _download_closes(tickers: list[str], period: str = "5y", start: str | None = None) -> pd.DataFrame:
    frames: list[pd.Series] = []
    for i in range(0, len(tickers), CHUNK_SIZE):
        chunk = tickers[i : i + CHUNK_SIZE]
        try:
            kwargs: dict = dict(
                interval="1d",
                group_by="ticker",
                auto_adjust=True,
                progress=False,
                threads=True,
            )
            if start:
                kwargs["start"] = start
            else:
                kwargs["period"] = period
            data = yf.download(chunk, **kwargs)
        except Exception as exc:
            log_pull_failure(
                "ssi_sp500_breadth",
                exc,
                note=f"chunk of {len(chunk)} tickers skipped; breadth will undercount",
            )
            continue
        if data is None or data.empty:
            continue
        if isinstance(data.columns, pd.MultiIndex):
            if "Close" in data.columns.get_level_values(0):
                close = data["Close"]
            else:
                close = data.xs("Close", level="Price", axis=1) if "Price" in data.columns.names else None
            if close is None:
                continue
            for sym in chunk:
                if sym in close.columns:
                    frames.append(close[sym].rename(sym))
        elif "Close" in data.columns and len(chunk) == 1:
            frames.append(data["Close"].rename(chunk[0]))

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, axis=1).sort_index()


def compute_daily_breadth_stats(close: pd.DataFrame) -> pd.DataFrame:
    """Per date: pct above 200DMA, 52w high count, 52w low count, advancers, decliners."""
    if close.empty:
        return pd.DataFrame()

    dates = close.index
    n = len(dates)
    # Use zeros + per-row valid counters so NaN warmup periods don't contaminate the totals.
    pct_above_200 = np.zeros(n)
    pct_valid_count = np.zeros(n)    # stocks with valid MA200 per row
    nh_count = np.zeros(n)
    nl_count = np.zeros(n)
    hl_valid_count = np.zeros(n)     # stocks with valid 52w high/low per row
    advancers = np.zeros(n)
    decliners = np.zeros(n)
    ret_valid_count = np.zeros(n)
    valid_syms = [c for c in close.columns if close[c].notna().sum() >= MIN_HISTORY_DAYS]

    for sym in valid_syms:
        s = close[sym].dropna()
        ma200 = s.rolling(200, min_periods=200).mean()
        high52 = s.rolling(252, min_periods=252).max()
        low52 = s.rolling(252, min_periods=252).min()
        ret = s.pct_change()

        # Use the rolling series itself (NaN when not enough data) to track validity
        ma200_reindexed = ma200.reindex(dates)
        high52_reindexed = high52.reindex(dates)
        low52_reindexed = low52.reindex(dates)
        s_reindexed = s.reindex(dates)
        ret_reindexed = ret.reindex(dates)

        # mask_200: True only when MA200 has enough data (not NaN)
        mask_200 = ma200_reindexed.notna().values
        above_200_vals = (s_reindexed > ma200_reindexed).fillna(False).astype(float).values
        pct_above_200 += np.where(mask_200, above_200_vals, 0)
        pct_valid_count += mask_200.astype(float)

        mask_hl = high52_reindexed.notna().values
        at_high_vals = (s_reindexed >= high52_reindexed).fillna(False).astype(float).values
        at_low_vals = (s_reindexed <= low52_reindexed).fillna(False).astype(float).values
        nh_count += np.where(mask_hl, at_high_vals, 0)
        nl_count += np.where(mask_hl, at_low_vals, 0)
        hl_valid_count += mask_hl.astype(float)

        mask_ret = ret_reindexed.notna().values
        up_vals = (ret_reindexed > 0).fillna(False).astype(float).values
        down_vals = (ret_reindexed < 0).fillna(False).astype(float).values
        advancers += np.where(mask_ret, up_vals, 0)
        decliners += np.where(mask_ret, down_vals, 0)
        ret_valid_count += mask_ret.astype(float)

    MIN_STOCKS = max(10, len(valid_syms) // 10)  # require at least 10% of stocks to have valid data
    pct_denom = np.where(pct_valid_count >= MIN_STOCKS, pct_valid_count, np.nan)
    hl_denom = np.where(hl_valid_count >= MIN_STOCKS, hl_valid_count, np.nan)

    out = pd.DataFrame(
        {
            "pct_above_200dma": 100.0 * pct_above_200 / pct_denom,
            "new_highs": np.where(hl_valid_count >= MIN_STOCKS, nh_count, np.nan),
            "new_lows": np.where(hl_valid_count >= MIN_STOCKS, nl_count, np.nan),
            "advancers": advancers,
            "decliners": decliners,
        },
        index=dates,
    )
    nh_nl_denom = out["new_highs"] + out["new_lows"]
    out["nh_nl_ratio"] = np.where(nh_nl_denom > 0, out["new_highs"] / nh_nl_denom, np.nan)
    out["net_advances"] = out["advancers"] - out["decliners"]
    return out.dropna(how="all")


def load_breadth_frame(*, force: bool = False, start: str | None = None) -> pd.DataFrame:
    global _BREADTH_CACHE
    if not force and start is None and _BREADTH_CACHE is not None and not _BREADTH_CACHE.empty:
        return _BREADTH_CACHE
    tickers = load_sp500_tickers()
    close = _download_closes(tickers, start=start)
    _BREADTH_CACHE = compute_daily_breadth_stats(close)
    return _BREADTH_CACHE


_BREADTH_CACHE: pd.DataFrame | None = None


def series_from_breadth(column: str, start: str | None = None) -> pd.Series:
    df = load_breadth_frame()
    if df.empty or column not in df.columns:
        return pd.Series(dtype=float)
    s = df[column].dropna().astype(float)
    if start:
        s = s.loc[s.index >= pd.Timestamp(start)]
    return s
