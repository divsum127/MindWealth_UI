"""Staleness caps and carried-forward weight penalties for SSI inputs."""

from __future__ import annotations

import pandas as pd

from src.sentiment_superindex.config import SSI_INPUT_CADENCE, staleness_policy, weight_penalty_for


def input_cadence(series_key: str) -> str:
    return SSI_INPUT_CADENCE.get(series_key, "weekly")


def calendar_stale_days(as_of: pd.Timestamp, last_obs: pd.Timestamp) -> int:
    return (as_of.normalize() - pd.Timestamp(last_obs).normalize()).days


def observation_as_of(
    series: pd.Series | None,
    as_of: pd.Timestamp,
    *,
    series_key: str,
    max_stale_days: dict[str, int] | None = None,
    stale_weight_penalty: float | None = None,
) -> tuple[float | None, int | None, float]:
    """Last observation ≤ as_of with cadence-aware drop + carry-forward weight penalty.

    Returns (raw_value, stale_days, weight_multiplier).
    weight_multiplier is 0 when dropped (beyond max_stale_days or no data),
    1.0 on the print date, else stale_weight_penalty.
    """
    if max_stale_days is None:
        max_stale_days, _, _ = staleness_policy()
    if stale_weight_penalty is None:
        stale_weight_penalty = weight_penalty_for(series_key)

    if series is None or series.empty:
        return None, None, 0.0

    sl = series.loc[:as_of].dropna()
    if sl.empty:
        return None, None, 0.0

    last_ts = sl.index[-1]
    raw = float(sl.iloc[-1])
    stale_days = calendar_stale_days(as_of, last_ts)
    cadence = input_cadence(series_key)
    max_days = int(max_stale_days.get(cadence, max_stale_days["weekly"]))

    if stale_days > max_days:
        return None, stale_days, 0.0

    weight_mult = 1.0 if stale_days == 0 else float(stale_weight_penalty)
    return raw, stale_days, weight_mult


def effective_input_weights(
    input_keys: list[str],
    components: dict[str, dict],
    nominal_weights: dict[str, float],
) -> dict[str, float]:
    """Apply stale penalties then renormalize surviving inputs to sum to 1.0."""
    penalized: dict[str, float] = {}
    for key in input_keys:
        comp = components.get(key, {})
        if comp.get("raw") is None:
            continue
        nominal = nominal_weights.get(key, 0.0)
        if nominal <= 0:
            continue
        mult = float(comp.get("weight_multiplier", 1.0))
        if mult <= 0:
            continue
        penalized[key] = nominal * mult

    total = sum(penalized.values())
    if total <= 0:
        return {key: 0.0 for key in input_keys}
    return {key: (penalized[key] / total if key in penalized else 0.0) for key in input_keys}
