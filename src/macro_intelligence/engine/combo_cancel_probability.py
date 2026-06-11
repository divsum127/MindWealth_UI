"""Part E — combo cancel probability (Monte Carlo digital barrier)."""

from __future__ import annotations

import math
from typing import Any

import numpy as np


def digital_barrier_prob(
    spot: float,
    strike: float,
    vol_annual: float,
    weeks_to_expiry: float,
) -> float:
    """P(S_T < K) under GBM, T in years."""
    if spot <= 0 or strike <= 0 or weeks_to_expiry <= 0:
        return 0.0
    T = weeks_to_expiry / 52.0
    sigma = vol_annual
    if T <= 0 or sigma <= 0:
        return 1.0 if spot < strike else 0.0
    d2 = (math.log(spot / strike) + (-0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    # Standard normal CDF without scipy
    return 0.5 * (1.0 + math.erf(-d2 / math.sqrt(2.0)))


def combo_cancel_probability_wti(
    current_wti: float,
    strike_mult: float = 1.05,
    vol_annual: float = 0.35,
    n_fridays: int = 4,
    correlation: float = 0.75,
    n_sim: int = 10000,
    seed: int = 42,
) -> dict[str, Any]:
    """
    Monte Carlo: 4 consecutive Fridays each need WTI 4wk return < +5%.
    Overlapping windows → correlated GBM paths.
    """
    rng = np.random.default_rng(seed)
    dt = 1 / 52
    strikes = [current_wti / strike_mult] * n_fridays
    passes = 0
    for _ in range(n_sim):
        s = current_wti
        ok = True
        for week in range(n_fridays):
            z = rng.standard_normal()
            s = s * math.exp((-0.5 * vol_annual**2) * dt + vol_annual * math.sqrt(dt) * z)
            if s >= strikes[week]:
                ok = False
                break
        if ok:
            passes += 1
    mc_prob = passes / n_sim
    marginal = digital_barrier_prob(current_wti, strikes[0], vol_annual, 1.0)
    return {
        "monte_carlo_prob_all_4": mc_prob,
        "marginal_week1_prob": marginal,
        "current_wti": current_wti,
        "strike": strikes[0],
        "vol_annual": vol_annual,
        "n_sim": n_sim,
    }


def combo_cancel_probability_cpi(historical_not_hot_rate: float, consecutive: int = 2) -> float:
    return float(historical_not_hot_rate**consecutive)


def combo_c_total_cancel_prob(
    wti_result: dict[str, Any],
    cpi_not_hot_rate: float = 0.55,
) -> dict[str, Any]:
    cpi_p = combo_cancel_probability_cpi(cpi_not_hot_rate)
    wti_p = wti_result.get("monte_carlo_prob_all_4", 0)
    return {
        "wti_leg": wti_result,
        "cpi_leg_prob": cpi_p,
        "combined_cancel_prob": wti_p * cpi_p,
    }
