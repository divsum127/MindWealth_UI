"""Three-layer SSI superindex: z-scored layer aggregates weighted 40/35/25."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.sentiment_superindex.config import load_config
from src.sentiment_superindex.data.pull_all import load_all_series

DEFAULT_LAYER_WEIGHTS = {"layer1": 0.40, "layer2": 0.35, "layer3": 0.25}

DEFAULT_LAYER_INPUTS = {
    "layer1": ["aaii_spread", "naaim_exposure", "cnn_fg", "pct_above_200dma"],
    "layer2": ["mcclellan", "nh_nl_ratio", "hyg_lqd", "skew", "vix_ratio"],
    "layer3": ["dbmf_beta", "cftc_fm_net", "cftc_rm_net", "gross_net"],
}


def _zscore(value: float, history: pd.Series, clip: float) -> float:
    h = history.dropna()
    if len(h) < 30:
        return 0.0
    mu, sigma = float(h.mean()), float(h.std())
    if sigma < 1e-9:
        return 0.0
    z = (value - mu) / sigma
    return float(np.clip(z, -clip, clip))


def normalize_component(key: str, value: float, history: pd.Series, clip: float) -> float:
    """Map to roughly [-1, 1] risk-off (negative) vs risk-on (positive)."""
    z = _zscore(value, history, clip)
    if key == "hyg_lqd":
        return z
    if key == "dbmf_beta":
        return -z
    if key == "cnn_fg":
        if value <= 25:
            return 0.8
        if value >= 75:
            return -0.8
        return (50 - value) / 50
    if key == "vix_ratio":
        if value >= 1.1:
            return -0.7
        if value <= 0.95:
            return 0.5
        return (1.0 - value) * 2
    if key == "skew":
        return -z
    return z


def _layer_config(cfg: dict[str, Any]) -> tuple[dict[str, float], dict[str, list[str]], float, int]:
    score_cfg = cfg.get("ssi_score", {})
    weights = score_cfg.get("layer_weights", DEFAULT_LAYER_WEIGHTS)
    inputs = score_cfg.get("layers", DEFAULT_LAYER_INPUTS)
    clip = float(score_cfg.get("zscore_clip", 3.0))
    years = int(score_cfg.get("history_years", 5))
    return weights, inputs, clip, years


def _value_as_of(series: pd.Series, as_of: pd.Timestamp) -> float | None:
    if series is None or series.empty:
        return None
    sl = series.loc[:as_of].dropna()
    return float(sl.iloc[-1]) if not sl.empty else None


def _history_window(series: pd.Series, as_of: pd.Timestamp, years: int) -> pd.Series:
    return series.loc[as_of - pd.DateOffset(years=years) : as_of]


def _build_layer(
    layer_key: str,
    input_keys: list[str],
    as_of: pd.Timestamp,
    series: dict[str, pd.Series],
    clip: float,
    years: int,
) -> dict[str, Any]:
    components: dict[str, Any] = {}
    norms: list[float] = []
    for key in input_keys:
        s = series.get(key)
        raw = _value_as_of(s, as_of) if s is not None else None
        if raw is None:
            components[key] = {"raw": None, "norm": None}
            continue
        hist = _history_window(s, as_of, years)
        norm = normalize_component(key, raw, hist, clip)
        components[key] = {"raw": raw, "norm": norm}
        norms.append(norm)
    score = float(np.mean(norms)) if norms else None
    return {"score": score, "components": components}


def build_layer1(
    as_of: str | pd.Timestamp,
    *,
    series: dict[str, pd.Series] | None = None,
) -> dict[str, Any]:
    as_of_ts = pd.Timestamp(as_of)
    cfg = load_config()
    _, inputs, clip, years = _layer_config(cfg)
    series = series or load_all_series()
    return _build_layer("layer1", inputs.get("layer1", DEFAULT_LAYER_INPUTS["layer1"]), as_of_ts, series, clip, years)


def build_layer2(
    as_of: str | pd.Timestamp,
    *,
    series: dict[str, pd.Series] | None = None,
) -> dict[str, Any]:
    as_of_ts = pd.Timestamp(as_of)
    cfg = load_config()
    _, inputs, clip, years = _layer_config(cfg)
    series = series or load_all_series()
    return _build_layer("layer2", inputs.get("layer2", DEFAULT_LAYER_INPUTS["layer2"]), as_of_ts, series, clip, years)


def build_layer3(
    as_of: str | pd.Timestamp,
    *,
    series: dict[str, pd.Series] | None = None,
) -> dict[str, Any]:
    as_of_ts = pd.Timestamp(as_of)
    cfg = load_config()
    _, inputs, clip, years = _layer_config(cfg)
    series = series or load_all_series()
    return _build_layer("layer3", inputs.get("layer3", DEFAULT_LAYER_INPUTS["layer3"]), as_of_ts, series, clip, years)


def build_superindex(
    as_of: str | pd.Timestamp,
    *,
    series: dict[str, pd.Series] | None = None,
) -> dict[str, Any]:
    """Weighted composite from z-scored layer means (not display-rounded values)."""
    as_of_ts = pd.Timestamp(as_of)
    cfg = load_config()
    weights, _, _, _ = _layer_config(cfg)
    series = series or load_all_series()

    layers = {
        "layer1": build_layer1(as_of_ts, series=series),
        "layer2": build_layer2(as_of_ts, series=series),
        "layer3": build_layer3(as_of_ts, series=series),
    }

    level = 0.0
    wsum = 0.0
    for layer_key, layer in layers.items():
        score = layer.get("score")
        weight = float(weights.get(layer_key, 0.0))
        layer["weight"] = weight
        if score is None or weight <= 0:
            continue
        level += weight * float(score)
        wsum += weight

    ssi_level = level / wsum if wsum > 0 else 0.0
    return {"ssi_level": ssi_level, "layers": layers, "weights": weights}
