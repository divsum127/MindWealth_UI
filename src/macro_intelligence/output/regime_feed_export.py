"""Maintained, versioned export of the 5-dimension regime feed.

Promotes the one-off `testing/5_regime_uplift/run_regime_sharpe_uplift.py::load_regime_fridays` /
`regime_daily` logic into a supported module (macro regime system fix-to-spec plan, work item 3,
action 2), so `GET /macro/regime/history` (`api/routers/macro.py`) and any other consumer share
one source of truth for the daily 5-dimension regime series, instead of each re-implementing the
Friday-eval + forward-fill logic independently.

Source of truth: `macro_regime_log_v2` (SQLite table, `regime_json` column) — the real
5-dimension shadow regime (`fed_cycle_v2`, `curve_regime_v2`, `val_regime`, `geo_overlay_v2`,
`liquidity_v2`), Friday cadence since 1990-01-05. Designating this table as the *production*
regime source of truth (superseding the legacy `runic_output.json` regime block) is a pending
product decision — see `docs/plans/regime_source_of_truth_decision_2026-07-29.md`. This module
does not itself make that call; it exports whatever `macro_regime_log_v2` contains.

Point-in-time discipline: `macro_regime_log_v2` rows are evaluated as of each Friday close. Daily
rows here forward-fill the most recent Friday's classification (`is_forward_filled=True` on
Mon-Thu, `False` on the evaluation Friday itself), following the same house pattern as
`testing/macro_th_exp/run_d1_regime_bucket_feed.py`. No lookahead is introduced by the export
itself. Any consumer that trades or backtests off this feed is responsible for its own execution
lag (e.g. `shift(1)` before applying a same-day multiplier to next-day returns) -- this module
exports the raw point-in-time regime state, not a pre-lagged trading signal.

Multiplier caveat: the per-dimension multiplier table below is the same v1 "illustrative economic
priors" table documented in `testing/5_regime_uplift/regime_dimension_multipliers_v1_unsigned.md` -- explicitly **not
production-signed**. It is exposed here for convenience/continuity with Test 5, tagged
`multiplier_version=MULTIPLIER_VERSION` (currently `v1_illustrative_unsigned_geo_off`) so
nothing downstream can mistake it for an approved production table. See
`docs/plans/multiplier_signoff_request_2026-07-29.md` for the pending sign-off.

Geo overlay: switched OFF 2026-08-17 on Rohit's 6 Aug instruction — every geo state maps to
1.00 because the backfill has geo at 97.6% NEUTRAL with only 25 ELEVATED_RISK and 21 CRISIS
observations. The tag change makes the switch visible to any consumer comparing feeds.

Schema version: SCHEMA_VERSION below. Bump on any breaking column change so consumers (e.g.
Ahil's backtest engine) can detect drift.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import numpy as np
import pandas as pd

from src.macro_intelligence.db.connection import get_connection

logger = logging.getLogger("macro.regime_feed")

SCHEMA_VERSION = "v1"
MULTIPLIER_VERSION = "v1_illustrative_unsigned_geo_off"
REGIME_SOURCE = "macro_regime_log_v2"

# NOTE ON THE WORD "DIMENSIONS" (Rohit 6 Aug): the FIVE here are the macro regime grid —
# fed cycle, curve, valuation, geo, liquidity. The FOUR on the signals side are asset,
# function, interval, direction. Two different objects; always qualify which is meant.

MIN_MULT = 0.40
MAX_MULT = 1.00
DEFAULT_DIM_MULT = 0.95

# The clip is ONE-SIDED: regime can only shrink the book (max 1.00) while the VIX and SSI
# overlays both reach 1.20. That asymmetry fell out of where the clip was set rather than
# being decided, and is left unchanged pending Rohit's call — see the answers doc.

# v1 economic priors -- illustrative, NOT production-signed (see module docstring).
FED_MULT = {"TIGHTENING": 0.82, "PIVOTING": 0.92, "EASING": 1.00, "EASY": 1.00}
CURVE_MULT = {"INVERTED": 0.78, "FLAT": 0.90, "NORMAL": 1.00, "STEEPENING": 0.95}
VAL_MULT = {"EXTREME_CAPE": 0.85, "ELEVATED_CAPE": 0.92, "NORMAL": 1.00, "CHEAP_CAPE": 1.00}
# GEO SWITCHED OFF 2026-08-17 (Rohit 6 Aug): the backfill has geo at 97.6% NEUTRAL with only
# 25 ELEVATED_RISK and 21 CRISIS observations, and most slices under 10 — nothing to
# calibrate against. Better to switch it off and say so than carry a number we can't defend.
# Previous values were CRISIS 0.70 / ELEVATED_RISK 0.85.
GEO_MULT = {"CRISIS": 1.00, "ELEVATED_RISK": 1.00, "NEUTRAL": 1.00}
GEO_MULT_DISABLED_REASON = (
    "geo overlay off pending data: 97.6% NEUTRAL, n=25 ELEVATED_RISK, n=21 CRISIS"
)
LIQ_LEVEL_MULT = {"TIGHT": 0.80, "NEUTRAL": 0.95, "EASY": 1.00}

DIMENSION_COLUMNS = ["fed_cycle_v2", "curve_regime_v2", "val_regime", "geo_overlay_v2", "liquidity_v2"]


def _liquidity_level(liq_v2: str | None) -> str:
    if not liq_v2:
        return "NEUTRAL"
    u = liq_v2.upper()
    if u.startswith("TIGHT"):
        return "TIGHT"
    if u.startswith("EASY"):
        return "EASY"
    return "NEUTRAL"


def _dimension_multipliers(reg: dict[str, Any]) -> dict[str, Any]:
    fed = str(reg.get("fed_cycle_v2") or "EASY").upper()
    curve = str(reg.get("curve_regime_v2") or "NORMAL").upper()
    val = str(reg.get("val_regime") or "NORMAL").upper()
    geo = str(reg.get("geo_overlay_v2") or reg.get("geo_overlay") or "NEUTRAL").upper()
    liq_raw = reg.get("liquidity_v2")
    liq = _liquidity_level(liq_raw)

    m_fed = FED_MULT.get(fed, DEFAULT_DIM_MULT)
    m_curve = CURVE_MULT.get(curve, DEFAULT_DIM_MULT)
    m_val = VAL_MULT.get(val, DEFAULT_DIM_MULT)
    # Geo is pinned at 1.00 for every state, so no unknown state should get a 0.95 haircut
    # from DEFAULT_DIM_MULT while the overlay is switched off.
    m_geo = GEO_MULT.get(geo, 1.00)
    m_liq = LIQ_LEVEL_MULT.get(liq, DEFAULT_DIM_MULT)
    gross_mult = float(np.clip(m_fed * m_curve * m_val * m_geo * m_liq, MIN_MULT, MAX_MULT))

    return {
        "fed_cycle_v2": fed,
        "curve_regime_v2": curve,
        "val_regime": val,
        "geo_overlay_v2": geo,
        "liquidity_v2": str(liq_raw or ""),
        "m_fed": m_fed,
        "m_curve": m_curve,
        "m_val": m_val,
        "m_geo": m_geo,
        "m_liq": m_liq,
        "gross_mult": gross_mult,
        "multiplier_version": MULTIPLIER_VERSION,
        "geo_overlay_enabled": False,
    }


def load_regime_fridays(start: str | None = None, end: str | None = None) -> pd.DataFrame:
    """One row per evaluated Friday from macro_regime_log_v2, with dimension states + multipliers."""
    query = "SELECT date, regime_json FROM macro_regime_log_v2"
    clauses = []
    params: list[str] = []
    if start:
        clauses.append("date >= ?")
        params.append(start)
    if end:
        clauses.append("date <= ?")
        params.append(end)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY date"

    rows: list[dict[str, Any]] = []
    with get_connection() as conn:
        for r in conn.execute(query, tuple(params)).fetchall():
            try:
                reg = json.loads(r["regime_json"] or "{}")
            except json.JSONDecodeError:
                continue
            parts = _dimension_multipliers(reg)
            rows.append({"date": pd.Timestamp(r["date"]), "evaluation_date": r["date"], **parts})
    if not rows:
        return pd.DataFrame(columns=["evaluation_date", *DIMENSION_COLUMNS, "gross_mult"])
    return pd.DataFrame(rows).set_index("date").sort_index()


# Columns joined from the ceiling chain. Kept separate from the five regime dimensions above:
# those are the macro grid, these are the market overlays the live sizing path also applies.
OVERLAY_COLUMNS = ["vix_mult", "trend_mult", "hy_mult", "chain_mult"]


def _attach_overlay_multipliers(daily: pd.DataFrame) -> pd.DataFrame:
    """Join the daily VIX / SPX-trend / HY multiplier history onto the regime feed.

    The 5-dimension grid answers "what macro regime was this", but a backtest sizing a book
    also needs the market overlays. Those are computed by
    ``portfolio_nav.four_book_engine.load_full_ceiling_chain_series``, which mirrors
    ``portfolio_service._compute_ceiling``'s live thresholds -- so the history and the live
    path agree by construction rather than by a second implementation.

    Coverage differs from the grid and is reported rather than hidden: the dimensions run from
    1990, while these overlays start 1996-12-31 (HY OAS, the shortest leg). Rows before that
    carry nulls, and ``overlay_history_start`` in the feed metadata names the boundary, so a
    caller cannot mistake "no overlay yet" for "overlay of 1.0".
    """
    try:
        from src.portfolio_nav.four_book_engine import load_full_ceiling_chain_series

        chain = load_full_ceiling_chain_series()
    except Exception as exc:  # never take the regime feed down for an overlay
        logger.warning("ceiling-chain overlays unavailable for regime feed: %s", exc)
        for col in OVERLAY_COLUMNS:
            daily[col] = np.nan
        return daily

    if chain.empty:
        for col in OVERLAY_COLUMNS:
            daily[col] = np.nan
        return daily

    # Forward-fill onto the regime feed's calendar: the chain is trading-day indexed, the feed
    # is calendar-day, and a weekend must carry Friday's overlay rather than go null.
    joined = chain[OVERLAY_COLUMNS].reindex(
        daily.index.union(chain.index).sort_values(), method="ffill"
    ).reindex(daily.index)
    # Do not fabricate an overlay before the first real observation.
    joined.loc[daily.index < chain.index.min()] = np.nan
    for col in OVERLAY_COLUMNS:
        daily[col] = joined[col]
    return daily


def overlay_history_start() -> str | None:
    """First date for which the VIX/trend/HY overlays exist (None if unavailable)."""
    try:
        from src.portfolio_nav.four_book_engine import load_full_ceiling_chain_series

        chain = load_full_ceiling_chain_series()
    except Exception:
        return None
    if chain.empty:
        return None
    return chain.index.min().strftime("%Y-%m-%d")


def get_regime_feed(
    start: str | None = None,
    end: str | None = None,
    *,
    calendar_index: pd.DatetimeIndex | None = None,
) -> pd.DataFrame:
    """Daily regime feed: Friday evaluations forward-filled to a daily calendar.

    Parameters
    ----------
    start, end: optional ISO date bounds on the underlying Friday evaluations.
    calendar_index: optional daily index to forward-fill onto. Defaults to a calendar-day
        range spanning the Friday evaluations (callers needing a trading-day calendar, e.g. to
        align with SPY/ETF prices, should pass their own index).

    Returns a DataFrame indexed by date with columns:
        evaluation_date   -- the Friday this row's classification was evaluated on (str, ISO)
        is_forward_filled -- True for Mon-Thu rows carrying forward the prior Friday's state
        fed_cycle_v2, curve_regime_v2, val_regime, geo_overlay_v2, liquidity_v2 -- dimension states
        m_fed, m_curve, m_val, m_geo, m_liq -- per-dimension multipliers (v1 illustrative)
        gross_mult         -- clipped product of the 5 multipliers, MIN_MULT..MAX_MULT
        schema_version, regime_source, multiplier_version -- provenance metadata (constant per row)
    """
    fridays = load_regime_fridays(start, end)
    if fridays.empty:
        return fridays

    idx = calendar_index
    if idx is None:
        # Calendar-day index (freq="D"). Forward-fill is UNLIMITED (limit=None): each Friday
        # classification carries through Sat/Sun/Mon–Thu until the next evaluation Friday.
        # Do not pass a row limit here without renaming the constant — limit counts calendar-day
        # rows, not business days (see src/sentiment_superindex/data/alignment.py).
        idx = pd.date_range(fridays.index.min(), fridays.index.max(), freq="D")

    daily = fridays.reindex(idx, method="ffill")  # limit=None → unlimited calendar-day ffill
    daily["is_forward_filled"] = ~daily.index.isin(fridays.index)
    daily = _attach_overlay_multipliers(daily)
    daily["schema_version"] = SCHEMA_VERSION
    daily["regime_source"] = REGIME_SOURCE
    daily["multiplier_version"] = MULTIPLIER_VERSION
    daily.index.name = "date"
    return daily


def regime_feed_as_records(
    start: str | None = None,
    end: str | None = None,
    *,
    calendar_index: pd.DatetimeIndex | None = None,
) -> list[dict[str, Any]]:
    """JSON/API-friendly row list -- used by GET /macro/regime/history."""
    df = get_regime_feed(start, end, calendar_index=calendar_index)
    if df.empty:
        return []
    out = df.reset_index()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    return out.to_dict(orient="records")
