"""Part E — combo cancel probability (Monte Carlo digital barrier).

Rebuilt 2026-08-17 after Rohit's 6 Aug audit. Four defects were fixed:

1. `vol_annual` was a hardcoded 0.35 — neither realised nor option-implied, just a
   constant. Sigma now comes from OVX (CBOE Crude Oil VIX, the market's own implied vol
   for WTI options), falling back to trailing realised vol, and the payload always says
   which one was used.
2. Fridays already banked never reduced the barrier count — every run rebuilt all four
   strikes from today's spot. With 1 of 4 banked the model now simulates 3 barriers, so
   P(cancel) rises as the legs actually bank instead of standing still.
3. The CPI leg rate was hardcoded at the call site. It is now derived from the CPI print
   history, reported with its sample size.
4. Nothing in the output said what sigma or how many weeks remained, so a wrong number
   was indistinguishable from a right one.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np

DEFAULT_VOL_ANNUAL = 0.35
OVX_TICKER = "^OVX"
WTI_TICKER = "CL=F"
REALISED_WINDOW_DAYS = 60
MAX_SIGMA_STALE_DAYS = 7


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


def wti_sigma(as_of: str | None = None) -> dict[str, Any]:
    """Annualised WTI vol for the cancel model, option-implied where available.

    Preference order:
      1. `ovx_implied`  — prior-day OVX close / 100. OVX is the implied vol of WTI options,
         so this is the market's own probability rather than one inferred from the past.
      2. `realised_60d` — trailing 60-day annualised vol of WTI futures closes.
      3. `config_default` — last resort, and flagged as such so it is never mistaken for
         a measured value.
    """
    cutoff = None
    if as_of:
        try:
            cutoff = datetime.strptime(str(as_of)[:10], "%Y-%m-%d").date()
        except ValueError:
            cutoff = None

    try:
        from src.macro_intelligence.data.yahoo_pull import fetch_yahoo_close
    except Exception:
        return {
            "sigma": DEFAULT_VOL_ANNUAL,
            "sigma_source": "config_default",
            "sigma_as_of": None,
            "sigma_note": "yahoo feed unavailable",
        }

    # 1. Option-implied (OVX)
    try:
        ovx = fetch_yahoo_close(OVX_TICKER, start="2007-01-01").dropna()
        if cutoff is not None:
            ovx = ovx[ovx.index.date < cutoff]
        if not ovx.empty:
            last_date = ovx.index[-1].date()
            reference = cutoff or datetime.now(UTC).date()
            if (reference - last_date) <= timedelta(days=MAX_SIGMA_STALE_DAYS):
                sigma = float(ovx.iloc[-1]) / 100.0
                if 0.0 < sigma < 5.0:
                    return {
                        "sigma": round(sigma, 4),
                        "sigma_source": "ovx_implied",
                        "sigma_as_of": last_date.isoformat(),
                        "sigma_note": "prior-day OVX close (WTI option-implied vol)",
                    }
    except Exception:
        pass

    # 2. Trailing realised
    try:
        wti = fetch_yahoo_close(WTI_TICKER, start="2000-01-01").dropna()
        if cutoff is not None:
            wti = wti[wti.index.date < cutoff]
        if len(wti) > REALISED_WINDOW_DAYS:
            log_returns = np.log(wti / wti.shift(1)).dropna().tail(REALISED_WINDOW_DAYS)
            sigma = float(log_returns.std() * math.sqrt(252))
            if 0.0 < sigma < 5.0:
                return {
                    "sigma": round(sigma, 4),
                    "sigma_source": "realised_60d",
                    "sigma_as_of": wti.index[-1].date().isoformat(),
                    "sigma_note": (
                        "OVX unavailable; trailing 60d realised vol. Realised understates "
                        "tails relative to option-implied."
                    ),
                }
    except Exception:
        pass

    return {
        "sigma": DEFAULT_VOL_ANNUAL,
        "sigma_source": "config_default",
        "sigma_as_of": None,
        "sigma_note": "neither OVX nor WTI closes available",
    }


def cpi_not_hot_rate() -> dict[str, Any]:
    """Empirical rate of CPI prints coming in at or below consensus, with sample size."""
    try:
        from src.macro_intelligence.db.connection import get_connection

        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS n,
                       SUM(CASE WHEN actual <= consensus THEN 1 ELSE 0 END) AS not_hot
                FROM pending_releases
                WHERE release_type='CPI' AND actual IS NOT NULL AND consensus IS NOT NULL
                """
            ).fetchone()
        n = int(row["n"] or 0)
        not_hot = int(row["not_hot"] or 0)
        if n >= 12:
            return {"rate": round(not_hot / n, 4), "n_obs": n, "source": "cpi_print_history"}
        return {"rate": 0.5, "n_obs": n, "source": "insufficient_history_50pct_prior"}
    except Exception:
        return {"rate": 0.5, "n_obs": 0, "source": "unavailable_50pct_prior"}


def wti_weekly_history(weeks: int = 5, as_of: str | None = None) -> list[float]:
    """Most recent weekly WTI closes, oldest first — the trailing leg of the 4wk window."""
    try:
        from src.macro_intelligence.data.yahoo_pull import fetch_yahoo_close

        series = fetch_yahoo_close(WTI_TICKER, start="2015-01-01").dropna()
        if as_of:
            try:
                cutoff = datetime.strptime(str(as_of)[:10], "%Y-%m-%d").date()
                series = series[series.index.date <= cutoff]
            except ValueError:
                pass
        weekly = series.resample("W-FRI").last().dropna()
        return [float(v) for v in weekly.tail(weeks)]
    except Exception:
        return []


def combo_cancel_probability_wti(
    current_wti: float,
    strike_mult: float = 1.05,
    vol_annual: float | None = None,
    n_fridays: int = 4,
    weeks_banked: int = 0,
    correlation: float = 0.75,
    n_sim: int = 10000,
    seed: int = 42,
    as_of: str | None = None,
    weekly_history: list[float] | None = None,
    roc_weeks: int = 4,
) -> dict[str, Any]:
    """
    Monte Carlo: each REMAINING Friday needs the WTI **4-week return** below +5%.

    Two corrections over the original model, both from Rohit's 6 Aug audit:

    * `weeks_banked` (`wti_potential_week` in combo_c_cancel) removes already-satisfied
      Fridays from the simulation. With 3 of 4 banked the cancel is one clean week away.
    * The barrier is the rule the cancel actually uses — the trailing 4-week rate of
      change — not the spot price against today × 1.05. Those differ sharply: the old
      form required the price to stay under a FIXED level for the whole run, so a market
      sitting flat after a past rally scored as near-impossible even while the real 4wk
      leg was comfortably passing. The trailing side of each early window is known
      history, so only the forward part is simulated.
    """
    sigma_info = (
        {"sigma": float(vol_annual), "sigma_source": "explicit_argument", "sigma_as_of": None,
         "sigma_note": "caller-supplied sigma"}
        if vol_annual is not None
        else wti_sigma(as_of)
    )
    sigma = float(sigma_info["sigma"])

    weeks_banked = max(0, min(int(weeks_banked), n_fridays))
    weeks_remaining = max(0, n_fridays - weeks_banked)

    if weeks_remaining == 0:
        return {
            "monte_carlo_prob_all_4": 1.0,
            "marginal_week1_prob": 1.0,
            "current_wti": current_wti,
            "strike": current_wti / strike_mult,
            "weeks_banked": weeks_banked,
            "weeks_remaining": 0,
            "n_fridays_required": n_fridays,
            "n_sim": n_sim,
            **sigma_info,
        }

    gate = strike_mult - 1.0  # +5% by default
    if weekly_history is None:
        weekly_history = wti_weekly_history(weeks=roc_weeks + 1, as_of=as_of)

    # path[0] is now; negative indices reach back into known weekly closes.
    history = list(weekly_history[:-1]) if weekly_history else []
    rng = np.random.default_rng(seed)
    dt = 1 / 52
    drift = -0.5 * sigma**2 * dt
    shock = sigma * math.sqrt(dt)

    passes = 0
    for _ in range(n_sim):
        path = [current_wti]
        ok = True
        for week in range(1, weeks_remaining + 1):
            path.append(path[-1] * math.exp(drift + shock * rng.standard_normal()))
            lag_index = week - roc_weeks
            if lag_index >= 0:
                base = path[lag_index]
            elif history:
                # Trailing side still in the past — use the actual close.
                base = history[max(0, len(history) + lag_index)]
            else:
                base = current_wti
            if base <= 0:
                continue
            if (path[-1] / base - 1.0) >= gate:
                ok = False
                break
        if ok:
            passes += 1

    mc_prob = passes / n_sim
    strike = current_wti / strike_mult
    marginal = digital_barrier_prob(current_wti, strike, sigma, 1.0)
    return {
        "monte_carlo_prob_all_4": mc_prob,
        "marginal_week1_prob": marginal,
        "current_wti": current_wti,
        "strike": strike,
        "gate_pct": round(gate * 100, 2),
        "roc_weeks": roc_weeks,
        "weeks_banked": weeks_banked,
        "weeks_remaining": weeks_remaining,
        "n_fridays_required": n_fridays,
        "n_sim": n_sim,
        "barrier_basis": "trailing_4wk_roc",
        "history_weeks_used": len(history),
        **sigma_info,
    }


def combo_cancel_probability_cpi(historical_not_hot_rate: float, consecutive: int = 2) -> float:
    return float(historical_not_hot_rate**consecutive)


def cpi_prints_in_window(weeks_remaining: int) -> int:
    """CPI prints expected before the cancel completes (one release per calendar month)."""
    if weeks_remaining <= 0:
        return 0
    return max(1, math.ceil(weeks_remaining / 4.345))


def combo_c_total_cancel_prob(
    wti_mc: dict[str, Any],
    cpi_not_hot_rate: float | None = None,
    consecutive_cpi: int | None = None,
    cpi_leg_currently_ok: bool | None = None,
) -> dict[str, Any]:
    """Joint cancel probability across the WTI and CPI legs.

    `consecutive_cpi` used to default to 2, which assumed two independent future prints
    regardless of how long the cancel actually had left. CPI releases monthly, so a cancel
    three Fridays from completion faces ONE print, not two — squaring the rate pushed the
    headline probability down by a factor of two for no modelled reason (Rohit 6 Aug).
    """
    cpi_info = {"rate": cpi_not_hot_rate, "n_obs": None, "source": "explicit_argument"}
    if cpi_not_hot_rate is None:
        cpi_info = cpi_not_hot_rate_lookup()
    rate = float(cpi_info["rate"])

    weeks_remaining = int(wti_mc.get("weeks_remaining") or 0)
    if consecutive_cpi is None:
        consecutive_cpi = cpi_prints_in_window(weeks_remaining)
    cpi_prob = combo_cancel_probability_cpi(rate, consecutive=consecutive_cpi)
    # A governing print that already passes covers every Friday until the next release.
    if cpi_leg_currently_ok and consecutive_cpi == 0:
        cpi_prob = 1.0
    wti_prob = float(wti_mc.get("monte_carlo_prob_all_4") or 0.0)
    return {
        # `wti_leg` and `combined_cancel_prob` keep the original contract — nightly_run,
        # the briefing renderer and the experiments runner all read those keys.
        "wti_leg": wti_mc,
        "combined_cancel_prob": wti_prob * cpi_prob,
        "wti_leg_prob": wti_prob,
        "cpi_leg_prob": cpi_prob,
        "total_prob": wti_prob * cpi_prob,
        "cpi_not_hot_rate": rate,
        "cpi_n_obs": cpi_info.get("n_obs"),
        "cpi_rate_source": cpi_info.get("source"),
        "cpi_prints_in_window": consecutive_cpi,
        "cpi_leg_currently_ok": cpi_leg_currently_ok,
        "weeks_banked": wti_mc.get("weeks_banked"),
        "weeks_remaining": wti_mc.get("weeks_remaining"),
        "sigma": wti_mc.get("sigma"),
        "sigma_source": wti_mc.get("sigma_source"),
        "sigma_as_of": wti_mc.get("sigma_as_of"),
    }


# Named separately so combo_c_total_cancel_prob can default its CPI rate without
# shadowing the parameter of the same name.
cpi_not_hot_rate_lookup = cpi_not_hot_rate
