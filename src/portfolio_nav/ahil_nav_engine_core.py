"""Ahil position-level NAV engine (Version B MTM + Version A closed)."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from src.portfolio_nav import portfolio_sharpe_analysis as psa
from src.portfolio_nav.combos import normalize_combo_key

WINDOW_START = pd.Timestamp("2024-01-01")
BT_MIN = 70


def apply_bt_gate(df: pd.DataFrame, bt_min: int = BT_MIN) -> pd.DataFrame:
    bt = pd.to_numeric(df.get("Backtested Win Rate [%]"), errors="coerce")
    return df[bt >= bt_min].copy()


def build_model_approved_trades(
    *,
    forward_testing_root: Path | str | None = None,
    version: str = "b",
    window_start: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Dual-gated trades (BT>=70, FWD combo membership, stake universe)."""
    trades = psa.load_all_strategy_trades(forward_testing_root)
    stake = psa.load_stake_symbols()
    filtered = psa.filter_trades_by_win_rate_combos(psa.filter_trades_by_symbols(trades, stake))
    filtered = apply_bt_gate(filtered)
    closed, full_b = psa.split_versions(filtered)
    start = window_start or WINDOW_START
    frame = closed if version.lower() == "a" else full_b
    frame = frame[frame["Entry Date"] >= start].copy()
    if frame.empty:
        raise ValueError(f"No Model Approved trades with Entry Date >= {start.date()}.")
    return frame


def run_nav_engine(
    trades_df: pd.DataFrame,
    price_map: dict[str, pd.Series],
    *,
    start_nav: float = 10_000_000.0,
    window_start: pd.Timestamp | None = None,
    rebalance_mode: str = "legacy_rebalance",
    n_target: int | None = None,
) -> pd.DataFrame:
    """Daily NAV + active position count (Ahil nav_engine.run_nav_engine).

    ``rebalance_mode`` (Phase 4 / Ask 2, OPEN_QUESTIONS_FOR_ROHIT.md):

    - ``"legacy_rebalance"`` (default here for back-compat): resets ALL active positions to
      1/N of NAV on every new entry, and redistributes an exiting position's value pro-rata
      to survivors. This is Ahil's original ``nav_engine.py`` behavior — kept for side-by-side
      comparison against the pre-Axiom-2 workbooks.
    - ``"hold_original"`` (Axiom 2 — 14July_axioms_and_specs.md, resolved research direction):
      never touches an existing position's value because someone else entered or exited.
      A new position takes a fixed slot (``NAV-at-entry / n_target``) out of cash; an exiting
      position's value returns to cash and sits idle until the next admitted signal takes the
      freed slot. ``api/services/policy_service.py`` decides which mode the live API requests
      (default ``hold_original``) — this function itself defaults conservatively so any other
      direct caller/test keeps today's behavior unless it opts in.
    """
    if rebalance_mode not in ("legacy_rebalance", "hold_original"):
        raise ValueError(f"Invalid rebalance_mode '{rebalance_mode}'. Use: legacy_rebalance, hold_original")
    window = window_start or WINDOW_START
    rets_by_symbol: dict[str, dict[pd.Timestamp, float]] = {}
    for sym, close in price_map.items():
        s = close.sort_index()
        s = s[~s.index.duplicated(keep="last")]
        rets_by_symbol[sym] = s.pct_change().to_dict()

    end_date = trades_df["Exit Date"].max().normalize()
    all_dates: set[pd.Timestamp] = set()
    for close in price_map.values():
        all_dates.update(d.normalize() for d in close.index)
    calendar = np.array(sorted(d for d in all_dates if window <= d <= end_date))
    if len(calendar) == 0:
        raise ValueError("Empty trading calendar.")

    entries_by_day: dict[pd.Timestamp, list[int]] = defaultdict(list)
    exits_by_day: dict[pd.Timestamp, list[int]] = defaultdict(list)
    positions: dict[int, dict] = {}
    skipped = 0
    for pid, (_, tr) in enumerate(trades_df.iterrows()):
        sym = str(tr["Symbol"]).upper()
        if sym not in price_map:
            skipped += 1
            continue
        entry = pd.Timestamp(tr["Entry Date"]).normalize()
        exit_ = pd.Timestamp(tr["Exit Date"]).normalize()
        ei = int(np.searchsorted(calendar, entry, side="left"))
        xi = int(np.searchsorted(calendar, exit_, side="left"))
        if ei >= len(calendar):
            skipped += 1
            continue
        xi = min(xi, len(calendar) - 1)
        if xi <= ei:
            skipped += 1
            continue
        positions[pid] = {
            "symbol": sym,
            "is_short": str(tr["Signal"]).lower() == "short",
            "entry_day": calendar[ei],
            "exit_day": calendar[xi],
            "value": 0.0,
        }
        entries_by_day[calendar[ei]].append(pid)
        exits_by_day[calendar[xi]].append(pid)

    open_ids: set[int] = set()
    cash = start_nav
    rows = []
    for t in calendar:
        for pid in open_ids:
            pos = positions[pid]
            ret = rets_by_symbol[pos["symbol"]].get(t, 0.0)
            if ret is None or (isinstance(ret, float) and np.isnan(ret)):
                ret = 0.0
            pos["value"] *= (1.0 - ret) if pos["is_short"] else (1.0 + ret)

        exiting = [pid for pid in exits_by_day.get(t, []) if pid in open_ids]
        pool = 0.0
        for pid in exiting:
            pool += positions[pid]["value"]
            open_ids.discard(pid)
        if pool:
            if rebalance_mode == "hold_original":
                # Axiom 2: no spreading a closed position's money across survivors —
                # freed cash sits idle until the next admitted signal takes the slot.
                cash += pool
            else:
                remaining_val = sum(positions[pid]["value"] for pid in open_ids)
                if open_ids and remaining_val > 0:
                    for pid in open_ids:
                        positions[pid]["value"] += pool * (positions[pid]["value"] / remaining_val)
                else:
                    cash += pool

        entering = entries_by_day.get(t, [])
        if entering:
            if rebalance_mode == "hold_original":
                # Axiom 2: no reset-to-1/N on entry — existing positions are untouched; each
                # new position takes a fixed NAV/N slot out of cash only.
                nav_now = cash + sum(positions[pid]["value"] for pid in open_ids)
                n_slot = n_target or max(len(open_ids) + len(entering), 1)
                slot_value = nav_now / n_slot
                for pid in entering:
                    alloc = min(cash, slot_value)
                    positions[pid]["value"] = alloc
                    cash -= alloc
                    open_ids.add(pid)
            else:
                for pid in entering:
                    positions[pid]["value"] = 0.0
                    open_ids.add(pid)
                nav_now = cash + sum(positions[pid]["value"] for pid in open_ids)
                per = nav_now / len(open_ids)
                for pid in open_ids:
                    positions[pid]["value"] = per
                cash = 0.0

        nav_t = cash + sum(positions[pid]["value"] for pid in open_ids)
        rows.append({"Date": t, "NAV": nav_t, "N_active": len(open_ids)})

    return pd.DataFrame(rows).set_index("Date")


def monthly_from_daily(daily: pd.DataFrame, *, start_nav: float = 10_000_000.0) -> pd.DataFrame:
    month_end = daily.groupby(daily.index.to_period("M")).tail(1).copy()
    month_end["Period"] = month_end.index.to_period("M")
    month_end = month_end.set_index("Period")

    closing = month_end["NAV"]
    opening = closing.shift(1)
    opening.iloc[0] = start_nav
    monthly_ret = closing / opening - 1.0
    cumulative = closing / start_nav - 1.0
    peak = pd.concat([pd.Series([start_nav]), closing]).cummax().iloc[1:]
    peak.index = closing.index
    drawdown = closing / peak - 1.0

    return pd.DataFrame({
        "Month": [p.strftime("%b-%y") for p in closing.index],
        "Opening_NAV": opening.values,
        "Closing_NAV": closing.values,
        "Monthly_Return": monthly_ret.values,
        "Cumulative_Return": cumulative.values,
        "Drawdown": drawdown.values,
    })


def compute_stats(monthly: pd.DataFrame, *, start_nav: float = 10_000_000.0) -> dict:
    r = monthly["Monthly_Return"].dropna().astype(float)
    n = len(monthly)
    final_nav = float(monthly["Closing_NAV"].iloc[-1])
    cagr = (final_nav / start_nav) ** (12.0 / n) - 1.0 if n else float("nan")
    vol = float(r.std(ddof=1) * np.sqrt(12)) if len(r) > 1 else float("nan")
    sharpe = float(r.mean() * 12 / vol) if vol not in (0.0, float("nan")) and vol else float("nan")
    max_dd = float(monthly["Drawdown"].min())
    return {
        "months": n,
        "final_nav": final_nav,
        "cumulative_return": final_nav / start_nav - 1.0,
        "cagr": cagr,
        "ann_vol": vol,
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "pct_positive": float((r > 0).mean()),
        "best_month": float(r.max()),
        "worst_month": float(r.min()),
        "avg_month": float(r.mean()),
        "calmar": cagr / abs(max_dd) if max_dd else float("nan"),
    }
