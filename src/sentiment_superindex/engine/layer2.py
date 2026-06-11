"""Layer 2 confirmation — 4 inputs, CONFIRMED / PARTIAL / UNCONFIRMED."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.sentiment_superindex.config import load_config
from src.sentiment_superindex.data.pull_all import load_all_series, values_as_of


def _pctile_in_history(value: float, history: pd.Series) -> float:
    h = history.dropna()
    if h.empty:
        return 50.0
    return float((h <= value).sum() / len(h) * 100)


def evaluate_layer2(as_of: str) -> tuple[str, int, list[dict[str, Any]], float]:
    cfg = load_config()
    l2 = cfg.get("layer2", {})
    mult_map = l2.get("multipliers", {})
    votes_cfg = l2.get("votes", {})
    min_conf = l2.get("min_confirmed", 2)

    as_of_ts = pd.Timestamp(as_of)
    series = load_all_series()
    vals = values_as_of(series, as_of_ts)

    vote_details: list[dict[str, Any]] = []
    confirmed = 0

    hyg = vals.get("hyg_lqd")
    if hyg is not None:
        pct = _pctile_in_history(hyg, series["hyg_lqd"].loc[:as_of_ts])
        risk_on = pct >= votes_cfg.get("hyg_lqd", {}).get("risk_on_pctile_min", 70)
        risk_off = pct <= votes_cfg.get("hyg_lqd", {}).get("risk_off_pctile_max", 30)
        active = risk_on or risk_off
        if active:
            confirmed += 1
        vote_details.append({"input": "hyg_lqd", "raw": hyg, "pctile": pct, "vote": active, "signal": "risk_on" if risk_on else "risk_off" if risk_off else "neutral"})

    beta = vals.get("dbmf_beta")
    if beta is not None:
        low = beta <= votes_cfg.get("dbmf_beta", {}).get("low_beta_max", 0.5)
        high = beta >= votes_cfg.get("dbmf_beta", {}).get("high_beta_min", 1.2)
        active = low or high
        if active:
            confirmed += 1
        vote_details.append({"input": "dbmf_beta", "raw": beta, "vote": active, "signal": "low_beta" if low else "high_beta" if high else "neutral"})

    fg = vals.get("cnn_fg")
    if fg is not None:
        fear = fg <= votes_cfg.get("cnn_fg", {}).get("fear_max", 25)
        greed = fg >= votes_cfg.get("cnn_fg", {}).get("greed_min", 75)
        active = fear or greed
        if active:
            confirmed += 1
        vote_details.append({"input": "cnn_fg", "raw": fg, "vote": active, "signal": "fear" if fear else "greed" if greed else "neutral"})

    vr = vals.get("vix_ratio")
    if vr is not None:
        stress = vr >= votes_cfg.get("vix_ratio", {}).get("stress_min", 1.05)
        complacency = vr <= votes_cfg.get("vix_ratio", {}).get("complacency_max", 0.95)
        active = stress or complacency
        if active:
            confirmed += 1
        vote_details.append({"input": "vix_ratio", "raw": vr, "vote": active, "signal": "stress" if stress else "complacency" if complacency else "neutral"})

    if confirmed >= min_conf:
        status = "CONFIRMED"
        mult = float(mult_map.get("CONFIRMED", 1.2))
    elif confirmed == 1:
        status = "PARTIAL"
        mult = float(mult_map.get("PARTIAL", 1.0))
    else:
        status = "UNCONFIRMED"
        mult = float(mult_map.get("UNCONFIRMED", 0.8))

    return status, confirmed, vote_details, mult
