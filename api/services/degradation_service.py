"""Signal degradation detection service — Layer 1 Degradation Alerts.

Trigger conditions (all three are independently evaluated):
  1. Live forward win rate for any (asset/function/interval/direction) combo
     drops below 61% AND >=2 consecutive months of successively lower FWD rate.
  2. Any booked loss on a portfolio position (virtual trading, status != Open).
  3. Any live MTM on a position exceeds -10%.

On trigger, pattern analysis classifies:
  - asset-specific (losses cluster on one symbol across functions)
  - function degradation (losses cluster on one function across assets)
  - combo issue (both dimensions contribute equally)

Message format:
  '[Strategy] gap: BT X% vs FWD Y%. [Above/Below] 60% floor.
   [Pattern]. Recommend: [action].'
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.config_paths import (
    MINDWEALTH_TRADE_STORE,
    VIRTUAL_TRADING_LONG_CSV,
    VIRTUAL_TRADING_SHORT_CSV,
)

# ── Constants ──────────────────────────────────────────────────────────────────
_FWD_WR_FLOOR = 61.0           # FWD win rate must be below this to trigger
_MTM_LOSS_THRESHOLD = -10.0    # live MTM threshold (%)
_MIN_EXITS_FOR_ANALYSIS = 3    # minimum closed trades per combo to analyse
_CONSEC_MONTHS_REQUIRED = 2    # consecutive months of declining rate to trigger
_ALERT_LABEL = "AI ANALYST · AUTO-TRIGGERED · DEGRADATION ALERT"
_BORDER_COLOR = "#ff4d6d"

_FWD_TESTING_ROOT = MINDWEALTH_TRADE_STORE / "forward_testing"


# ── CSV helpers ────────────────────────────────────────────────────────────────

def _read_csv_safe(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _parse_profit(val: Any) -> float | None:
    """Parse profit values like '1.6%', '-5.43%', '1.6', or float."""
    if val is None:
        return None
    if isinstance(val, float):
        import math
        return None if math.isnan(val) else val
    s = str(val).strip().rstrip("%").strip()
    if s in ("", "N/A", "nan", "None", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


# ── Forward testing data loader ────────────────────────────────────────────────

def _load_all_fwd_trades() -> pd.DataFrame:
    """
    Walk {MINDWEALTH_TRADE_STORE}/forward_testing/{FUNCTION}/{SYMBOL}/{INTERVAL}.csv
    and return concatenated DataFrame of all closed trade records.

    Result columns: Function, Symbol, Signal (direction), Interval,
    Entry Date, Exit Date, Profit [%], Backtested Win Rate [%]
    """
    root = _FWD_TESTING_ROOT
    if not root.exists():
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []
    for fn_dir in root.iterdir():
        if not fn_dir.is_dir():
            continue
        function = fn_dir.name.replace("_", " ")
        for asset_dir in fn_dir.iterdir():
            if not asset_dir.is_dir():
                continue
            symbol = asset_dir.name
            for csv_file in asset_dir.glob("*.csv"):
                df = _read_csv_safe(csv_file)
                if df.empty:
                    continue
                # Normalise Function and Symbol in case CSV values differ from directory names
                if "Function" not in df.columns:
                    df["Function"] = function
                if "Symbol" not in df.columns:
                    df["Symbol"] = symbol
                frames.append(df)

    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)
    return combined


# ── Monthly win-rate trend ─────────────────────────────────────────────────────

def _monthly_win_rates(group_df: pd.DataFrame) -> list[float]:
    """
    Compute monthly FWD win rate from closed trades in chronological order.
    Only months that have at least 1 exited trade are included.
    """
    closed = group_df[
        group_df["Exit Date"].notna()
        & (group_df["Exit Date"].astype(str).str.strip().str.lower() != "")
    ].copy()
    if closed.empty:
        return []

    try:
        closed["exit_month"] = pd.to_datetime(closed["Exit Date"], errors="coerce").dt.to_period("M")
    except Exception:
        return []

    closed = closed.dropna(subset=["exit_month"])
    if closed.empty:
        return []

    closed["_profit"] = closed["Profit [%]"].apply(_parse_profit)
    # Drop rows where profit couldn't be parsed
    closed = closed.dropna(subset=["_profit"])
    if closed.empty:
        return []

    monthly = (
        closed.groupby("exit_month")["_profit"]
        .agg(lambda x: float((x > 0).sum()) / max(len(x), 1) * 100)
        .sort_index()
    )
    return [float(v) for v in monthly.values]


def _has_consecutive_decline(rates: list[float]) -> bool:
    """
    True when there are >= _CONSEC_MONTHS_REQUIRED consecutive step-down months.

    Example: _CONSEC_MONTHS_REQUIRED=2 means we need [m1 > m2 > m3] — two
    successive declines — which requires at least 3 data points.
    """
    n = _CONSEC_MONTHS_REQUIRED
    # n consecutive declines need n+1 data points
    if len(rates) < n + 1:
        return False
    tail = rates[-(n + 1):]
    return all(tail[i] > tail[i + 1] for i in range(n))


def _trailing_decline_count(rates: list[float]) -> int:
    """Count how many consecutive trailing months show a strict decline."""
    if len(rates) < 2:
        return 0
    count = 0
    for i in range(len(rates) - 1, 0, -1):
        if rates[i] < rates[i - 1]:
            count += 1
        else:
            break
    return count


# ── Pattern classifier ─────────────────────────────────────────────────────────

def _classify_loss_pattern(
    symbol: str,
    function: str,
    full_df: pd.DataFrame,
) -> dict[str, str]:
    """
    Determine whether losses concentrate in asset, function, or the combo.

    Logic mirrors the user specification:
      asset_loss_count > func_loss_count  → asset story
      func_loss_count > asset_loss_count  → function degradation
      equal                               → combo issue
    """
    def _loss_count(mask_df: pd.DataFrame) -> int:
        profits = mask_df["Profit [%]"].apply(_parse_profit)
        return int((profits < 0).sum())

    asset_losses = _loss_count(full_df[full_df["Symbol"] == symbol])
    func_losses = _loss_count(full_df[full_df["Function"] == function])

    if asset_losses > func_losses:
        return {
            "pattern": f"Asset-specific: review {symbol} fundamentals",
            "recommendation": f"Review {symbol} fundamentals and macro context; consider pausing signals on this asset.",
        }
    if func_losses > asset_losses:
        return {
            "pattern": f"Function degradation: {function} underperforming across assets",
            "recommendation": f"Recalibrate {function} parameters; review model assumptions across all assets.",
        }
    return {
        "pattern": f"Combo issue: {symbol}/{function} — review model params",
        "recommendation": f"Audit {symbol}/{function} combo; check for structural break or data staleness.",
    }


# ── Portfolio trigger checks ───────────────────────────────────────────────────

def _check_portfolio_triggers() -> list[dict[str, Any]]:
    """
    Check virtual trading positions for:
      - Booked losses (closed trades with profit < 0%)
      - Live MTM exceeding -10%
    """
    alerts: list[dict[str, Any]] = []

    sources = [("long", VIRTUAL_TRADING_LONG_CSV), ("short", VIRTUAL_TRADING_SHORT_CSV)]
    for side, csv_path in sources:
        df = _read_csv_safe(Path(csv_path))
        if df.empty:
            continue
        profit_col = "Realised/Unrealised Profit"
        if profit_col not in df.columns:
            continue

        df = df.copy()
        df["_profit"] = df[profit_col].apply(_parse_profit)
        status_col = "Status" if "Status" in df.columns else None
        df["_status"] = (
            df[status_col].astype(str).str.strip().str.lower()
            if status_col
            else "open"
        )

        # Booked losses: closed position with negative realised profit
        closed_loss = df[(df["_status"] != "open") & (df["_profit"].notna()) & (df["_profit"] < 0)]
        for _, row in closed_loss.iterrows():
            alerts.append({
                "trigger_type": "booked_loss",
                "side": side,
                "symbol": str(row.get("Symbol", "")),
                "function": str(row.get("Function", "")),
                "interval": str(row.get("Interval", "")),
                "direction": side.title(),
                "profit_pct": round(float(row["_profit"]), 2),
                "status": str(row.get("Status", "closed")),
                "message": (
                    f"Booked loss on {side} position: "
                    f"{row.get('Symbol', '')} "
                    f"({row.get('Function', '')}/{row.get('Interval', '')}). "
                    f"Realised P&L: {row['_profit']:.2f}%."
                ),
                "label": _ALERT_LABEL,
                "border_color": _BORDER_COLOR,
            })

        # Live MTM breach: open position with current P&L below -10%
        live_breach = df[
            (df["_status"] == "open")
            & (df["_profit"].notna())
            & (df["_profit"] < _MTM_LOSS_THRESHOLD)
        ]
        for _, row in live_breach.iterrows():
            alerts.append({
                "trigger_type": "live_mtm_breach",
                "side": side,
                "symbol": str(row.get("Symbol", "")),
                "function": str(row.get("Function", "")),
                "interval": str(row.get("Interval", "")),
                "direction": side.title(),
                "profit_pct": round(float(row["_profit"]), 2),
                "status": "open",
                "message": (
                    f"Live MTM breach on {side} position: "
                    f"{row.get('Symbol', '')} "
                    f"({row.get('Function', '')}/{row.get('Interval', '')}). "
                    f"MTM: {row['_profit']:.2f}% (floor: {_MTM_LOSS_THRESHOLD}%)."
                ),
                "label": _ALERT_LABEL,
                "border_color": _BORDER_COLOR,
            })

    return alerts


# ── Main degradation check ─────────────────────────────────────────────────────

def check_degradation() -> dict[str, Any]:
    """
    Run full Layer 1 degradation analysis across all (asset/function/interval/direction) combos.

    Returns:
        triggered         bool    — True if at least one alert fired
        alerts            list    — signal-level degradation alerts (fwd_degradation)
        portfolio_alerts  list    — portfolio position alerts (booked_loss | live_mtm_breach)
        checked_combos    int     — number of combos analysed
        alert_count       int     — total alerts across both lists
        label             str     — UI panel label
        border_color      str     — panel left border colour
    """
    fwd_df = _load_all_fwd_trades()
    signal_alerts: list[dict[str, Any]] = []
    checked_combos = 0

    if not fwd_df.empty and "Profit [%]" in fwd_df.columns:
        # Normalise direction from Signal column (Long / Short)
        if "Signal" in fwd_df.columns:
            fwd_df["_direction"] = fwd_df["Signal"].astype(str).str.strip().str.title()
        else:
            fwd_df["_direction"] = "Long"

        fwd_df["Function"] = fwd_df["Function"].astype(str).str.strip()

        group_keys = ["Symbol", "Function", "Interval", "_direction"]
        for combo_key, group in fwd_df.groupby(group_keys):
            symbol, function, interval, direction = combo_key

            # Require sufficient closed trades for statistical validity
            closed = group[
                group["Exit Date"].notna()
                & (group["Exit Date"].astype(str).str.strip().str.lower() != "")
            ]
            if len(closed) < _MIN_EXITS_FOR_ANALYSIS:
                continue

            checked_combos += 1

            # Compute chronological monthly win rates
            monthly_rates = _monthly_win_rates(group)
            if not monthly_rates:
                continue

            current_fwd_rate = monthly_rates[-1]

            # Gate 1: current FWD win rate below 61% floor
            if current_fwd_rate >= _FWD_WR_FLOOR:
                continue

            # Gate 2: >= 2 consecutive months of successively lower win rates
            if not _has_consecutive_decline(monthly_rates):
                continue

            # BT win rate: use first available value (static per combo)
            bt_rate: float | None = None
            bt_col = "Backtested Win Rate [%]"
            if bt_col in group.columns:
                bt_vals = group[bt_col].dropna()
                if not bt_vals.empty:
                    try:
                        bt_rate = float(bt_vals.iloc[0])
                    except (ValueError, TypeError):
                        bt_rate = None

            floor_rel = "Above" if current_fwd_rate >= 60.0 else "Below"
            pattern_info = _classify_loss_pattern(symbol, function, fwd_df)
            strategy_label = f"{function} {interval}"
            bt_str = f"{bt_rate:.1f}" if bt_rate is not None else "N/A"

            signal_alerts.append({
                "trigger_type": "fwd_degradation",
                "strategy": strategy_label,
                "combo": {
                    "asset": symbol,
                    "function": function,
                    "interval": interval,
                    "direction": direction,
                },
                "bt_rate": round(bt_rate, 1) if bt_rate is not None else None,
                "fwd_rate": round(current_fwd_rate, 1),
                "monthly_trend": [round(r, 1) for r in monthly_rates[-6:]],
                "consecutive_decline_months": _trailing_decline_count(monthly_rates),
                "pattern": pattern_info["pattern"],
                "recommendation": pattern_info["recommendation"],
                "message": (
                    f"{strategy_label} gap: BT {bt_str}% vs FWD {current_fwd_rate:.1f}%. "
                    f"{floor_rel} 60% floor.\n"
                    f"{pattern_info['pattern']}. Recommend: {pattern_info['recommendation']}."
                ),
                "label": _ALERT_LABEL,
                "border_color": _BORDER_COLOR,
            })

    portfolio_alerts = _check_portfolio_triggers()

    return {
        "triggered": bool(signal_alerts or portfolio_alerts),
        "alerts": signal_alerts,
        "portfolio_alerts": portfolio_alerts,
        "checked_combos": checked_combos,
        "alert_count": len(signal_alerts) + len(portfolio_alerts),
        "label": _ALERT_LABEL,
        "border_color": _BORDER_COLOR,
    }
