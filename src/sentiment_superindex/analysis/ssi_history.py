"""SSI level + 5-year percentile history for validation sweeps."""

from __future__ import annotations

import pandas as pd

from src.sentiment_superindex.config import load_config
from src.sentiment_superindex.engine.ssi_score import build_ssi_history

_HIST_CACHE: dict[str, pd.DataFrame] = {}


def build_ssi_history_frame(start: str = "2010-01-01") -> pd.DataFrame:
    if start in _HIST_CACHE:
        return _HIST_CACHE[start]
    levels = build_ssi_history(start)
    if levels.empty:
        frame = pd.DataFrame(columns=["ssi_level", "ssi_pctile_5y"])
        _HIST_CACHE[start] = frame
        return frame
    years = load_config().get("ssi_score", {}).get("history_years", 5)
    pctiles: list[float] = []
    for dt in levels.index:
        hist = levels.loc[dt - pd.DateOffset(years=years) : dt]
        if len(hist) < 10:
            hist = levels.loc[:dt]
        if len(hist) >= 10:
            pctiles.append(float((hist <= levels.loc[dt]).sum() / len(hist) * 100))
        else:
            pctiles.append(float("nan"))
    frame = pd.DataFrame({"ssi_level": levels.values, "ssi_pctile_5y": pctiles}, index=levels.index)
    _HIST_CACHE[start] = frame
    return frame
