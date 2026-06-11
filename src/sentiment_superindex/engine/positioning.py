"""Build positioning.json payload."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from src.sentiment_superindex.config import load_config
from src.sentiment_superindex.engine.layer2 import evaluate_layer2
from src.sentiment_superindex.data.pull_all import layer3_for_date, load_all_series, values_as_of
from src.sentiment_superindex.engine.ssi_score import compute_ssi_at_date


def build_positioning_payload(as_of: str | None = None) -> dict[str, Any]:
    as_of = as_of or datetime.now().strftime("%Y-%m-%d")
    cfg = load_config()
    th = cfg.get("thresholds", {})

    level, pctile, components = compute_ssi_at_date(as_of)
    layer2_status, layer2_count, votes, ssi_mult = evaluate_layer2(as_of)
    layer1 = values_as_of(load_all_series(), pd.Timestamp(as_of))

    long_th = float(th.get("long_entry", -0.6))
    short_th = float(th.get("short_entry", 0.85))
    long_pct_th = float(th.get("long_entry_pctile", 20))
    short_pct_th = float(th.get("short_entry_pctile", 85))

    long_active = (pctile is not None and pctile <= long_pct_th) or level <= long_th
    short_active = (pctile is not None and pctile >= short_pct_th) or level >= short_th

    long_mult = ssi_mult if long_active else 1.0
    short_mult = ssi_mult if short_active else (0.8 if layer2_status == "UNCONFIRMED" else 1.0)

    return {
        "date": as_of,
        "ssi_level": round(level, 4),
        "ssi_percentile_5y": round(pctile, 2) if pctile is not None else None,
        "layer2_status": layer2_status,
        "layer2_confirmed_count": layer2_count,
        "ssi_multiplier": ssi_mult,
        "signals": {
            "long": {
                "size_mult": long_mult,
                "entry_threshold": long_th,
                "active": long_active,
            },
            "short": {
                "size_mult": short_mult,
                "entry_threshold": short_th,
                "active": short_active,
            },
        },
        "inputs": {
            "hyg_lqd": components.get("hyg_lqd", {}),
            "dbmf_beta": components.get("dbmf_beta", {}),
            "cnn_fg": components.get("cnn_fg", {}),
            "vix_ratio": components.get("vix_ratio", {}),
            "layer2_votes": votes,
            "layer3_cftc": layer3_for_date(as_of),
            "layer1": {
                "aaii_spread": layer1.get("aaii_spread"),
                "naaim_exposure": layer1.get("naaim_exposure"),
                "cnn_fg_raw": layer1.get("cnn_fg"),
                "pct_above_200dma": layer1.get("pct_above_200dma"),
                "mcclellan": layer1.get("mcclellan"),
                "nh_nl_ratio": layer1.get("nh_nl_ratio"),
                "skew": layer1.get("skew"),
            },
        },
        "validation": {
            "threshold_source": "SSI_CONFIG.yaml",
            "design_percentile": cfg.get("ssi_score", {}).get("design_percentile", 20),
            "notes": "Empirical sweep: run scripts/run_ssi_threshold_sweep.py",
        },
    }
