"""Three-layer SSI superindex: z-scored layer aggregates weighted 40/35/25."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from src.sentiment_superindex.config import (
    coverage_policy,
    load_config,
    staleness_policy,
    weight_penalty_for,
)
from src.sentiment_superindex.data.pull_all import load_all_series
from src.sentiment_superindex.data.staleness import (
    effective_input_weights,
    input_cadence,
    observation_as_of,
)

logger = logging.getLogger("ssi.superindex")

DEFAULT_LAYER_WEIGHTS = {"layer1": 0.40, "layer2": 0.35, "layer3": 0.25}

DEFAULT_LAYER_INPUTS = {
    "layer1": ["aaii_spread", "naaim_exposure", "put_call_ema", "cnn_fg"],
    "layer2": ["mcclellan", "nh_nl_ratio", "hyg_lqd", "skew", "vix_ratio", "pct_above_200dma"],
    "layer3": ["dbmf_beta", "cftc_fm_net", "cftc_rm_net", "gross_net"],
}

DEFAULT_LAYER1_INPUT_WEIGHTS = {
    "aaii_spread": 0.30,
    "naaim_exposure": 0.35,
    "put_call_ema": 0.20,
    "cnn_fg": 0.15,
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
    if key in ("skew", "put_call_ema"):
        # High put/call = fear; invert so fear lowers risk-on layer score.
        return -z
    return z


def _layer_config(
    cfg: dict[str, Any],
) -> tuple[dict[str, float], dict[str, list[str]], dict[str, float], float, int]:
    score_cfg = cfg.get("ssi_score", {})
    weights = score_cfg.get("layer_weights", DEFAULT_LAYER_WEIGHTS)
    inputs = score_cfg.get("layers", DEFAULT_LAYER_INPUTS)
    layer1_input_weights = {
        key: float(value)
        for key, value in score_cfg.get("layer1_input_weights", DEFAULT_LAYER1_INPUT_WEIGHTS).items()
    }
    clip = float(score_cfg.get("zscore_clip", 3.0))
    years = int(score_cfg.get("history_years", 5))
    return weights, inputs, layer1_input_weights, clip, years


def _input_weights_for_layer(
    layer_key: str,
    input_keys: list[str],
    layer1_input_weights: dict[str, float],
) -> dict[str, float]:
    if layer_key == "layer1":
        return {key: layer1_input_weights.get(key, 0.0) for key in input_keys}
    equal = 1.0 / len(input_keys) if input_keys else 0.0
    return {key: equal for key in input_keys}


def _value_as_of(series: pd.Series, as_of: pd.Timestamp, *, series_key: str) -> float | None:
    """Cadence-aware last observation with max-stale drop (see observation_as_of)."""
    raw, _, _ = observation_as_of(series, as_of, series_key=series_key)
    return raw


def _history_window(series: pd.Series, as_of: pd.Timestamp, years: int) -> pd.Series:
    return series.loc[as_of - pd.DateOffset(years=years) : as_of]


def _exclusion_reason(
    series_key: str, stale_days: int | None, max_stale_days: dict[str, int]
) -> str:
    """Plain-words why an input was dropped, for the API payload and the page."""
    if stale_days is None:
        return "unavailable - no observation on or before this date"
    cadence = input_cadence(series_key)
    cap = int(max_stale_days.get(cadence, max_stale_days["weekly"]))
    return f"expired - last print {stale_days}d old, {cadence} carry cap {cap}d"


def _layer_signal_coverage(
    input_keys: list[str],
    components: dict[str, Any],
    input_weights: dict[str, float],
    *,
    layer_key: str | None = None,
) -> dict[str, Any]:
    """Unavailable / expired signals dropped; stale carries weight_penalty then renormalize.

    Also decides whether what survived is still enough to score. ``reliable`` is consumed by
    ``_build_layer`` (to suppress the score) and by the API/UI (to label the layer), so the
    number shown and the number used can never disagree -- the same rule the combo dominance
    code follows for ``insufficient_episodes``.
    """
    configured_count = len(input_keys)
    available_keys = [
        key for key in input_keys if components.get(key, {}).get("raw") is not None
    ]
    available_count = len(available_keys)
    configured_weight_sum = sum(input_weights.get(key, 0.0) for key in input_keys)
    effective_weights = {
        key: round(weight, 4)
        for key, weight in effective_input_weights(input_keys, components, input_weights).items()
    }
    stale_keys = [
        key
        for key in available_keys
        if int(components.get(key, {}).get("stale_days") or 0) > 0
    ]
    expired_keys = [
        key
        for key in input_keys
        if components.get(key, {}).get("stale_days") is not None
        and components.get(key, {}).get("raw") is None
    ]
    min_counts, min_weight_retained = coverage_policy()
    nominal_weight_retained = (
        sum(input_weights.get(key, 0.0) for key in available_keys) / configured_weight_sum
        if configured_weight_sum > 0
        else 0.0
    )
    min_count = min_counts.get(layer_key or "", 0)
    reasons: list[str] = []
    if available_count < min_count:
        reasons.append(
            f"only {available_count} of {configured_count} inputs available "
            f"(minimum {min_count})"
        )
    if nominal_weight_retained < min_weight_retained:
        reasons.append(
            f"only {nominal_weight_retained:.0%} of nominal weight present "
            f"(minimum {min_weight_retained:.0%})"
        )
    reliable = not reasons

    return {
        "configured_count": configured_count,
        "available_count": available_count,
        "reliable": reliable,
        "unreliable_reason": "; ".join(reasons) if reasons else None,
        "nominal_weight_retained": round(nominal_weight_retained, 4),
        "min_available_count": min_count,
        "min_nominal_weight_retained": min_weight_retained,
        "weights_renormalized": available_count < configured_count or bool(stale_keys),
        "nominal_weights": {
            key: round(input_weights.get(key, 0.0), 4) for key in input_keys
        },
        "configured_weight_sum": round(configured_weight_sum, 4),
        "effective_weights": effective_weights,
        "missing": [key for key in input_keys if key not in available_keys],
        "stale": stale_keys,
        "expired": expired_keys,
    }


def _effective_weight_sum(effective_weights: dict[str, float]) -> float:
    return sum(weight for weight in effective_weights.values() if weight > 0)


def _attach_component_contributions(
    input_keys: list[str],
    components: dict[str, Any],
    input_weights: dict[str, float],
) -> None:
    """Per-signal share of the within-layer weighted mean (weight * norm / sum(weights))."""
    effective_weights = effective_input_weights(input_keys, components, input_weights)
    weight_sum = _effective_weight_sum(effective_weights)
    for key in input_keys:
        comp = components.get(key, {})
        norm = comp.get("norm")
        weight = effective_weights.get(key, 0.0)
        if norm is None or weight <= 0 or weight_sum <= 0:
            comp["contribution"] = None
            comp["effective_weight"] = round(weight, 4) if weight > 0 else 0.0
            continue
        comp["effective_weight"] = round(weight, 4)
        comp["contribution"] = round(weight * float(norm) / weight_sum, 4)


def _weighted_layer_score(
    input_keys: list[str],
    components: dict[str, Any],
    input_weights: dict[str, float],
) -> float | None:
    effective_weights = effective_input_weights(input_keys, components, input_weights)
    weighted_sum = 0.0
    weight_sum = 0.0
    for key in input_keys:
        norm = components.get(key, {}).get("norm")
        if norm is None:
            continue
        weight = effective_weights.get(key, 0.0)
        if weight <= 0:
            continue
        weighted_sum += weight * float(norm)
        weight_sum += weight
    return weighted_sum / weight_sum if weight_sum > 0 else None


def _build_layer(
    layer_key: str,
    input_keys: list[str],
    as_of: pd.Timestamp,
    series: dict[str, pd.Series],
    clip: float,
    years: int,
    *,
    layer1_input_weights: dict[str, float],
) -> dict[str, Any]:
    max_stale_days, _, _ = staleness_policy()
    components: dict[str, Any] = {}
    input_weights = _input_weights_for_layer(layer_key, input_keys, layer1_input_weights)
    for key in input_keys:
        s = series.get(key)
        raw, stale_days, weight_mult = observation_as_of(
            s,
            as_of,
            series_key=key,
            max_stale_days=max_stale_days,
            stale_weight_penalty=weight_penalty_for(key),
        )
        if raw is None:
            components[key] = {
                "raw": None,
                "norm": None,
                "stale_days": stale_days,
                "weight_multiplier": 0.0,
                # Why this input scored nothing, said once here rather than left for each
                # consumer to infer from a null. The Sentiment page was printing the carried
                # net figure with no hint it contributed 0 (audit 2026-08-20).
                "excluded_from_score": True,
                "excluded_reason": _exclusion_reason(key, stale_days, max_stale_days),
            }
            continue
        hist = _history_window(s, as_of, years)
        norm = normalize_component(key, raw, hist, clip)
        components[key] = {
            "raw": raw,
            "norm": norm,
            "stale_days": stale_days,
            "weight_multiplier": weight_mult,
            "excluded_from_score": False,
            "excluded_reason": None,
        }
    _attach_component_contributions(input_keys, components, input_weights)
    score = _weighted_layer_score(input_keys, components, input_weights)
    coverage = _layer_signal_coverage(
        input_keys, components, input_weights, layer_key=layer_key
    )
    # The score over whatever survived, kept even when the gate suppresses `score`. Without it
    # a client that still has to render something has nothing true to render -- the Nuxt page
    # was falling back to the SSI composite and displaying it as the Layer 3 score.
    partial_score = float(score) if score is not None else None
    if not coverage["reliable"]:
        # Suppressing the score (rather than publishing a number built on a fraction of the
        # inputs) makes build_superindex drop the layer from the weighted mean via the path it
        # already uses for a fully-empty layer. The components stay in the payload so the page
        # can still show what was and was not received.
        # DEBUG, not ERROR: _build_layer runs once per date while build_ssi_history walks
        # several thousand historical dates, most of which predate a given input entirely.
        # The authoritative, once-per-run report is jobs.daily_run.log_coverage; shouting here
        # produced 510 ERROR lines in a single job and would have rebuilt the very log-noise
        # problem this gate was added to solve.
        logger.debug(
            "SSI %s marked UNRELIABLE: %s", layer_key, coverage["unreliable_reason"]
        )
        score = None
    return {
        "score": float(score) if score is not None else None,
        "partial_score": partial_score if score is None else None,
        "components": components,
        "signal_coverage": coverage,
    }


def build_layer1(
    as_of: str | pd.Timestamp,
    *,
    series: dict[str, pd.Series] | None = None,
) -> dict[str, Any]:
    as_of_ts = pd.Timestamp(as_of)
    cfg = load_config()
    _, inputs, layer1_input_weights, clip, years = _layer_config(cfg)
    series = series or load_all_series()
    return _build_layer(
        "layer1",
        inputs.get("layer1", DEFAULT_LAYER_INPUTS["layer1"]),
        as_of_ts,
        series,
        clip,
        years,
        layer1_input_weights=layer1_input_weights,
    )


def build_layer2(
    as_of: str | pd.Timestamp,
    *,
    series: dict[str, pd.Series] | None = None,
) -> dict[str, Any]:
    as_of_ts = pd.Timestamp(as_of)
    cfg = load_config()
    _, inputs, layer1_input_weights, clip, years = _layer_config(cfg)
    series = series or load_all_series()
    return _build_layer(
        "layer2",
        inputs.get("layer2", DEFAULT_LAYER_INPUTS["layer2"]),
        as_of_ts,
        series,
        clip,
        years,
        layer1_input_weights=layer1_input_weights,
    )


def build_layer3(
    as_of: str | pd.Timestamp,
    *,
    series: dict[str, pd.Series] | None = None,
) -> dict[str, Any]:
    as_of_ts = pd.Timestamp(as_of)
    cfg = load_config()
    _, inputs, layer1_input_weights, clip, years = _layer_config(cfg)
    series = series or load_all_series()
    return _build_layer(
        "layer3",
        inputs.get("layer3", DEFAULT_LAYER_INPUTS["layer3"]),
        as_of_ts,
        series,
        clip,
        years,
        layer1_input_weights=layer1_input_weights,
    )


def build_superindex(
    as_of: str | pd.Timestamp,
    *,
    series: dict[str, pd.Series] | None = None,
) -> dict[str, Any]:
    """Weighted composite from z-scored layer means (not display-rounded values)."""
    as_of_ts = pd.Timestamp(as_of)
    cfg = load_config()
    weights, _, _, _, _ = _layer_config(cfg)
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
