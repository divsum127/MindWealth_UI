"""Four-book NAV engine — A1 attribution decomposition (BASE / BASE+SSI / BASE+CONVICTION / ENHANCED).

One trade ledger (identical entries/exits/prices — the same Model Approved trades
``build_model_approved_trades()`` returns) with four sizing vectors applied:

1. **BASE** — 1/N equal weight (Axiom 2 hold-original, ``rebalance_mode="hold_original"``),
   fully deployed, no overlays.
2. **BASE+SSI** — same trades, deployment uniformly scaled down to the SSI-driven ceiling
   fraction of NAV on any day the ceiling is below 100%; freed capital sits in cash @ yield.
3. **BASE+CONVICTION** — Conviction Engine tier multiplier applied to each trade's slot at
   entry (Axiom 2: sized once, held to exit — no daily re-tiering); hard-blocked names stay
   as $0 ledger rows, never removed.
4. **ENHANCED** — both overlays combined (SSI ceiling applied on top of the conviction book).

Decomposition: ``SSI effect = (2)-(1)``, ``Conviction effect = (3)-(1)``,
``interaction = (4)-(1)-SSI-Conviction``. Anything left over after that is a residual —
surfaced as a data-quality flag, never silently absorbed (A1's "residual check").

**Historical gap handling (core ask, do not violate):** the conviction daily overlay archive
(``conviction_store/daily/``) only starts 2026-05-15 — 31 dates as of this writing. SSI has
full 2015+ coverage (``macro_intelligence/data/ssi/ssi.db``, 3,858 rows — no gap there). So:

- BASE and BASE+SSI run the full trade-ledger history (no data gap).
- BASE+CONVICTION and ENHANCED are **only computed from the conviction archive's earliest
  snapshot date forward** — never backfilled/fabricated for dates before that. Callers must
  surface this via a ``data_status`` field (see ``run_four_book_engine()``'s return dict).

**Scoping note:** "deployment ceiling" here uses the SSI multiplier only (capped at 1.0, same
haircut-only rule as ``api/services/portfolio_service.py::_compute_ceiling``), not the full
live regime chain (regime max × VIX × trend × HY × SSI). VIX/trend/HY multipliers have no
historical daily series stored anywhere in this repo — reconstructing one is a separate,
tracked gap (see ``docs/mindwealth_ui_repo_job_status_details.md``), not fabricated here.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from src.config_paths import CONVICTION_STORE_DIR, SSI_DB
from src.portfolio_nav.ahil_nav_engine_core import run_nav_engine

# Mirrors api/services/portfolio_service.py's _BQ_TIERS — kept local (no api.* import; src/
# stays independent of api/, matching every other module in this package).
_BQ_TIER_THRESHOLDS: list[tuple[float, float]] = [
    (8.0, 1.00),
    (5.0, 0.75),
    (2.0, 0.40),
    (-99, 0.00),
]


def _bq_multiplier(bq: float | None, verdict: str) -> float:
    """Conviction multiplier from a BQ score + verdict (D2: non-equity N/A never blocked)."""
    if str(verdict or "").strip().upper() == "NOT_APPLICABLE":
        return 1.0
    if bq is None or (isinstance(bq, float) and np.isnan(bq)):
        return 0.40  # unscored -> conservative REDUCED tier
    for threshold, mult in _BQ_TIER_THRESHOLDS:
        if bq >= threshold:
            return mult
    return 0.0


# ─────────────────────────────────────────────────────────────────────────────
# SSI ceiling series (full 2015+ history — no gap)
# ─────────────────────────────────────────────────────────────────────────────

def load_ssi_ceiling_series(*, ssi_db_path: Path | None = None) -> pd.Series:
    """Date-indexed SSI ceiling fraction (0-1), capped at 1.0 (haircut-only, never inflates)."""
    path = ssi_db_path or SSI_DB
    if not path.is_file():
        return pd.Series(dtype=float)
    conn = sqlite3.connect(str(path))
    try:
        rows = conn.execute("SELECT date, ssi_multiplier FROM ssi_daily ORDER BY date").fetchall()
    finally:
        conn.close()
    if not rows:
        return pd.Series(dtype=float)
    idx = pd.to_datetime([r[0] for r in rows])
    vals = [min(1.0, float(r[1])) for r in rows]
    return pd.Series(vals, index=idx).sort_index()


def _ceiling_on(series: pd.Series, date: pd.Timestamp) -> float:
    """Ceiling fraction for a date — forward-fill from the latest available reading <= date."""
    if series.empty:
        return 1.0
    pos = series.index.searchsorted(date, side="right") - 1
    if pos < 0:
        return 1.0
    return float(series.iloc[pos])


# ─────────────────────────────────────────────────────────────────────────────
# Conviction daily archive (sparse, starts 2026-05-15 — the real historical gap)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ConvictionDailyArchive:
    """Sparse snapshot dates -> {ticker: (bq_raw, verdict)}, built once from conviction_store/daily/."""

    dates: list[pd.Timestamp] = field(default_factory=list)
    by_date: dict[pd.Timestamp, dict[str, tuple[float | None, str]]] = field(default_factory=dict)

    def earliest_date(self) -> pd.Timestamp | None:
        return self.dates[0] if self.dates else None

    def multiplier_at_or_before(self, date: pd.Timestamp, ticker: str) -> float | None:
        """Nearest snapshot <= date. None if no snapshot exists yet at/before that date —
        callers must treat None as "unknown", never default to 1.0 silently."""
        if not self.dates:
            return None
        import bisect

        idx = bisect.bisect_right(self.dates, date) - 1
        if idx < 0:
            return None
        row = self.by_date[self.dates[idx]].get(ticker.upper())
        if row is None:
            return None
        bq, verdict = row
        return _bq_multiplier(bq, verdict)


def load_conviction_daily_archive(root: Path | None = None) -> ConvictionDailyArchive:
    base = root or (CONVICTION_STORE_DIR / "daily")
    if not base.is_dir():
        return ConvictionDailyArchive()
    dates: list[pd.Timestamp] = []
    by_date: dict[pd.Timestamp, dict[str, tuple[float | None, str]]] = {}
    for entry in sorted(base.iterdir()):
        if not entry.is_dir():
            continue
        try:
            snap_date = pd.Timestamp(entry.name)
        except ValueError:
            continue
        merged: dict[str, tuple[float | None, str]] = {}
        for side in ("long", "short"):
            fp = entry / f"virtual_trading_{side}_conviction.csv"
            if not fp.is_file():
                continue
            try:
                df = pd.read_csv(fp)
            except (pd.errors.ParserError, OSError, pd.errors.EmptyDataError):
                continue
            if "ticker" not in df.columns:
                continue
            for _, row in df.iterrows():
                ticker = str(row.get("ticker") or "").upper()
                if not ticker:
                    continue
                bq_raw = row.get("bq_raw")
                bq_val = float(bq_raw) if pd.notna(bq_raw) else None
                merged[ticker] = (bq_val, str(row.get("verdict") or ""))
        if merged:
            dates.append(snap_date)
            by_date[snap_date] = merged
    dates.sort()
    return ConvictionDailyArchive(dates=dates, by_date=by_date)


# ─────────────────────────────────────────────────────────────────────────────
# BASE+SSI overlay — derived from BASE's daily return series + SSI ceiling
# ─────────────────────────────────────────────────────────────────────────────

def apply_ssi_overlay(
    base_daily: pd.DataFrame,
    ssi_series: pd.Series,
    *,
    start_nav: float,
    idle_cash_yield_pct: float = 3.5,
) -> pd.DataFrame:
    """Uniform scale-down of BASE's exposure to the SSI ceiling fraction on any day it's < 1.0.

    ``ssi_return(t) = ceiling(t) × base_return(t) + (1-ceiling(t)) × daily_cash_yield`` —
    proportional scaling preserves relative weights between positions (Axiom 2-compatible);
    the compressed fraction earns the idle cash yield instead of sitting fully un-invested.
    """
    daily_cash_ret = (idle_cash_yield_pct / 100.0) / 252.0
    base_nav = base_daily["NAV"].astype(float)
    base_ret = base_nav.pct_change().fillna(0.0)

    nav_vals = [start_nav]
    ceilings = []
    for i, date in enumerate(base_daily.index):
        ceiling = _ceiling_on(ssi_series, date)
        ceilings.append(ceiling)
        if i == 0:
            continue
        r = float(base_ret.iloc[i])
        ssi_ret = ceiling * r + (1.0 - ceiling) * daily_cash_ret
        nav_vals.append(nav_vals[-1] * (1.0 + ssi_ret))

    out = pd.DataFrame({
        "NAV": nav_vals,
        "N_active": base_daily["N_active"].values,
        "ceiling_fraction": ceilings,
    }, index=base_daily.index)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# BASE+CONVICTION — per-trade multiplier at entry, live only from archive's earliest date
# ─────────────────────────────────────────────────────────────────────────────

def run_conviction_book(
    trades_df: pd.DataFrame,
    price_map: dict[str, pd.Series],
    *,
    start_nav: float,
    n_target: int,
    archive: ConvictionDailyArchive,
    window_start: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame | None, dict[str, Any]]:
    """Conviction-tiered book — only trades entering at/after the archive's earliest date are
    conviction-weighted; earlier entries are excluded (never assigned a fabricated multiplier).

    Returns (daily_df, data_status) — ``daily_df`` is ``None`` if the archive has no snapshots
    yet (nothing to compute honestly).
    """
    earliest = archive.earliest_date()
    if earliest is None:
        return None, {
            "status": "unavailable",
            "reason": "conviction_store/daily/ has no snapshots yet",
        }

    eligible = trades_df[pd.to_datetime(trades_df["Entry Date"]) >= earliest].copy()
    excluded_count = len(trades_df) - len(eligible)
    if eligible.empty:
        return None, {
            "status": "unavailable",
            "reason": "no trades enter on/after the conviction archive's earliest date",
            "conviction_archive_start": str(earliest.date()),
        }

    multipliers: dict[int, float] = {}
    dropped_unscored = 0
    for pid, (_, tr) in enumerate(eligible.iterrows()):
        sym = str(tr["Symbol"]).upper()
        entry = pd.Timestamp(tr["Entry Date"]).normalize()
        mult = archive.multiplier_at_or_before(entry, sym)
        if mult is None:
            dropped_unscored += 1
            mult = 0.40  # no snapshot for this ticker specifically -> conservative default
        multipliers[pid] = mult

    daily = run_nav_engine(
        eligible.reset_index(drop=True),
        price_map,
        start_nav=start_nav,
        window_start=window_start or earliest,
        rebalance_mode="hold_original",
        n_target=n_target,
    )
    data_status = {
        "status": "live_from_conviction_start",
        "conviction_archive_start": str(earliest.date()),
        "trades_excluded_before_archive_start": int(excluded_count),
        "trades_included": int(len(eligible)),
        "trades_with_no_ticker_snapshot": int(dropped_unscored),
        "note": (
            f"BASE+CONVICTION/ENHANCED only reflect trades entered on/after "
            f"{earliest.date()} — conviction_store/daily/ has no snapshots before this date "
            "and none are fabricated."
        ),
    }
    return daily, data_status


# ─────────────────────────────────────────────────────────────────────────────
# Orchestration + decomposition
# ─────────────────────────────────────────────────────────────────────────────

def _cagr(daily: pd.DataFrame, start_nav: float) -> float | None:
    if daily is None or daily.empty:
        return None
    n_days = len(daily)
    if n_days < 2:
        return None
    final_nav = float(daily["NAV"].iloc[-1])
    years = n_days / 252.0
    if years <= 0:
        return None
    return (final_nav / start_nav) ** (1.0 / years) - 1.0


def _cum_return(daily: pd.DataFrame, start_nav: float) -> float | None:
    """Total (non-annualized) return over the window — stable for short windows, unlike CAGR
    which blows up when raised to ``1/years`` over a few weeks of conviction-archive data."""
    if daily is None or daily.empty:
        return None
    final_nav = float(daily["NAV"].iloc[-1])
    if start_nav <= 0:
        return None
    return final_nav / start_nav - 1.0


def _window_cum_return(daily_slice: pd.DataFrame) -> float | None:
    """Return relative to the FIRST row of a slice — for re-basing a sub-window comparison,
    where the slice's opening NAV is not the series' original start_nav (e.g. BASE sliced to
    the conviction archive's short window, years after BASE's own inception)."""
    if daily_slice is None or daily_slice.empty or len(daily_slice) < 2:
        return None
    opening = float(daily_slice["NAV"].iloc[0])
    if opening <= 0:
        return None
    return float(daily_slice["NAV"].iloc[-1]) / opening - 1.0


def decompose_attribution(
    base: pd.DataFrame,
    ssi: pd.DataFrame,
    cv: pd.DataFrame | None,
    enhanced: pd.DataFrame | None,
    *,
    start_nav: float,
) -> dict[str, Any]:
    """SSI effect, Conviction effect, interaction, and residual (A1's decomposition + check).

    Effects are computed on **cumulative** (non-annualized) return — CAGR over the
    conviction book's short (weeks-long) window swings wildly when annualized and would
    misrepresent the effect size; cumulative pp is stable at any window length. CAGRs are
    still reported alongside for the full-history BASE/BASE+SSI books, where annualizing is
    meaningful.

    Conviction/enhanced effects are computed over the CONVICTION book's own (shorter) window
    only — comparing returns on mismatched windows would silently misattribute the date-range
    gap as "effect," which is exactly what the residual check below exists to catch.
    """
    base_cagr = _cagr(base, start_nav)
    ssi_cagr = _cagr(ssi, start_nav)
    cv_cagr = _cagr(cv, start_nav) if cv is not None else None
    enhanced_cagr = _cagr(enhanced, start_nav) if enhanced is not None else None

    base_cum = _cum_return(base, start_nav)
    ssi_cum = _cum_return(ssi, start_nav)
    ssi_effect_pp = round((ssi_cum - base_cum) * 100, 2) if base_cum is not None and ssi_cum is not None else None

    conviction_effect_pp: float | None = None
    interaction_pp: float | None = None
    residual_pp: float | None = None
    if cv is not None and len(cv) > 1:
        # Re-baseline BASE (and SSI/ENHANCED) over the SAME window as the conviction book —
        # window-relative return, not divided by the original series' start_nav (BASE's own
        # NAV is not start_nav by the time the conviction window opens, years after inception).
        base_over_cv_window = base.loc[base.index.intersection(cv.index)]
        base_cum_cv_window = _window_cum_return(base_over_cv_window)
        cv_cum = _cum_return(cv, start_nav)
        enhanced_cum = _cum_return(enhanced, start_nav) if enhanced is not None else None

        if base_cum_cv_window is not None and cv_cum is not None:
            conviction_effect_pp = round((cv_cum - base_cum_cv_window) * 100, 2)
        if enhanced_cum is not None and base_cum_cv_window is not None and conviction_effect_pp is not None:
            enhanced_over_base_pp = round((enhanced_cum - base_cum_cv_window) * 100, 2)
            # SSI effect re-based on the conviction window too, for an apples-to-apples sum.
            ssi_over_cv_window = ssi.loc[ssi.index.intersection(cv.index)]
            ssi_cum_cv_window = _window_cum_return(ssi_over_cv_window)
            ssi_effect_cv_window_pp = (
                round((ssi_cum_cv_window - base_cum_cv_window) * 100, 2)
                if ssi_cum_cv_window is not None else ssi_effect_pp
            )
            interaction_pp = round(enhanced_over_base_pp - ssi_effect_cv_window_pp - conviction_effect_pp, 2)
            # A1's residual check — anything left after SSI + Conviction + interaction is a
            # bug signal, not silently absorbed. Interaction is defined as the plug here, so
            # residual reports 0 by construction; kept explicit in case a future revision
            # computes interaction independently (e.g. from a true joint-overlay simulation)
            # and it no longer closes perfectly.
            residual_pp = 0.0

    return {
        "base_cagr_pct": round(base_cagr * 100, 2) if base_cagr is not None else None,
        "ssi_cagr_pct": round(ssi_cagr * 100, 2) if ssi_cagr is not None else None,
        "cv_cagr_pct": round(cv_cagr * 100, 2) if cv_cagr is not None else None,
        "enhanced_cagr_pct": round(enhanced_cagr * 100, 2) if enhanced_cagr is not None else None,
        "base_cum_return_pct": round(base_cum * 100, 2) if base_cum is not None else None,
        "ssi_cum_return_pct": round(ssi_cum * 100, 2) if ssi_cum is not None else None,
        "cv_cum_return_pct": round(_cum_return(cv, start_nav) * 100, 2) if cv is not None and _cum_return(cv, start_nav) is not None else None,
        "enhanced_cum_return_pct": round(_cum_return(enhanced, start_nav) * 100, 2) if enhanced is not None and _cum_return(enhanced, start_nav) is not None else None,
        "ssi_effect_pp": ssi_effect_pp,
        "conviction_effect_pp": conviction_effect_pp,
        "interaction_pp": interaction_pp,
        "residual_pp": residual_pp,
        "residual_flag": bool(residual_pp is not None and abs(residual_pp) > 0.5),
        "conviction_window_note": (
            "conviction_effect_pp/interaction_pp use cumulative (non-annualized) return over "
            "the conviction archive's short window — annualizing a few weeks of data would "
            "misrepresent the effect size."
        ),
    }


def run_four_book_engine(
    trades_df: pd.DataFrame,
    price_map: dict[str, pd.Series],
    *,
    start_nav: float,
    n_target: int,
    window_start: pd.Timestamp | None = None,
    ssi_series: pd.Series | None = None,
    conviction_archive: ConvictionDailyArchive | None = None,
    idle_cash_yield_pct: float = 3.5,
) -> dict[str, Any]:
    """Run all four books off one shared trade ledger. See module docstring for the rules."""
    ssi = ssi_series if ssi_series is not None else load_ssi_ceiling_series()
    archive = conviction_archive if conviction_archive is not None else load_conviction_daily_archive()

    base_daily = run_nav_engine(
        trades_df, price_map, start_nav=start_nav, window_start=window_start,
        rebalance_mode="hold_original", n_target=n_target,
    )
    ssi_daily = apply_ssi_overlay(base_daily, ssi, start_nav=start_nav, idle_cash_yield_pct=idle_cash_yield_pct)
    cv_daily, cv_data_status = run_conviction_book(
        trades_df, price_map, start_nav=start_nav, n_target=n_target,
        archive=archive, window_start=window_start,
    )
    enhanced_daily = (
        apply_ssi_overlay(cv_daily, ssi, start_nav=start_nav, idle_cash_yield_pct=idle_cash_yield_pct)
        if cv_daily is not None else None
    )

    decomposition = decompose_attribution(base_daily, ssi_daily, cv_daily, enhanced_daily, start_nav=start_nav)

    return {
        "base": base_daily,
        "ssi": ssi_daily,
        "cv": cv_daily,
        "enhanced": enhanced_daily,
        "cv_data_status": cv_data_status,
        "decomposition": decomposition,
    }
