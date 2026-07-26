"""Forward win-rate drift alerts — Layer 1 DRIFT ALERT (AI Analyst / email spec 5D)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import pandas as pd

from api.services import degradation_cache as deg_cache
from src.config_paths import VIRTUAL_TRADING_LONG_CSV, VIRTUAL_TRADING_SHORT_CSV

FWD_WR_FLOOR = 60.0
DRIFT_WATCH_CEILING = 61.0
DRIFT_BREACH_CEILING = 60.0
DRIFT_WATCH_FALLING_MONTHS = 2
DRIFT_BREACH_FALLING_MONTHS = 3
_MTM_LOSS_THRESHOLD = -10.0
_MIN_EXITS_FOR_ANALYSIS = 3
_BORDER_COLOR = "#ff4d6d"
_LABEL_WATCH = "AI ANALYST · OVERWATCH AUTO-TRIGGERED · DRIFT ALERT WATCH"
_LABEL_BREACH = "AI ANALYST · OVERWATCH AUTO-TRIGGERED · DRIFT ALERT BREACH"
_LABEL_PORTFOLIO = "AI ANALYST · OVERWATCH AUTO-TRIGGERED · DRIFT ALERT BREACH"


def _parse_profit(val: Any) -> float | None:
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


def _weekly_win_rates(group_df: pd.DataFrame) -> list[float]:
    closed = group_df[
        group_df["Exit Date"].notna()
        & (group_df["Exit Date"].astype(str).str.strip().str.lower() != "")
    ].copy()
    if closed.empty:
        return []

    try:
        closed["exit_week"] = pd.to_datetime(closed["Exit Date"], errors="coerce").dt.to_period("W")
    except Exception:
        return []

    closed = closed.dropna(subset=["exit_week"])
    if closed.empty:
        return []

    closed["_profit"] = closed["Profit [%]"].apply(_parse_profit)
    closed = closed.dropna(subset=["_profit"])
    if closed.empty:
        return []

    weekly = (
        closed.groupby("exit_week")["_profit"]
        .agg(lambda x: float((x > 0).sum()) / max(len(x), 1) * 100)
        .sort_index()
    )
    return [float(v) for v in weekly.values]


def _monthly_win_rates(group_df: pd.DataFrame) -> list[float]:
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
    closed = closed.dropna(subset=["_profit"])
    if closed.empty:
        return []

    monthly = (
        closed.groupby("exit_month")["_profit"]
        .agg(lambda x: float((x > 0).sum()) / max(len(x), 1) * 100)
        .sort_index()
    )
    return [float(v) for v in monthly.values]


def _cumulative_fwd_win_rate(group_df: pd.DataFrame) -> float | None:
    """Overall forward win rate across all closed trades (not a single week/month)."""
    closed = group_df[
        group_df["Exit Date"].notna()
        & (group_df["Exit Date"].astype(str).str.strip().str.lower() != "")
    ]
    if closed.empty or "Profit [%]" not in closed.columns:
        return None
    profits = closed["Profit [%]"].apply(_parse_profit).dropna()
    if profits.empty:
        return None
    return float((profits > 0).sum()) / len(profits) * 100


def _is_falling_streak(rates: list[float], months: int) -> bool:
    """True when win rate fell month-over-month for `months` consecutive months."""
    if months < 1 or len(rates) < months + 1:
        return False
    tail = rates[-(months + 1) :]
    return all(tail[i] < tail[i - 1] for i in range(1, len(tail)))


def _classify_drift_severity(
    cumulative_fwd_rate: float,
    monthly_rates: list[float],
) -> Literal["watch", "breach"] | None:
    """
    DRIFT ALERT rules (email spec 5D):
    - Orange: FWD win rate below 61% AND falling 2 months in a row.
    - Red: FWD win rate below 60% AND falling 3 months in a row.
    BT vs FWD gap is irrelevant — only live forward rate and its monthly trend matter.
    """
    if cumulative_fwd_rate >= DRIFT_WATCH_CEILING:
        return None
    if (
        cumulative_fwd_rate < DRIFT_BREACH_CEILING
        and _is_falling_streak(monthly_rates, DRIFT_BREACH_FALLING_MONTHS)
    ):
        return "breach"
    if (
        cumulative_fwd_rate < DRIFT_WATCH_CEILING
        and _is_falling_streak(monthly_rates, DRIFT_WATCH_FALLING_MONTHS)
    ):
        return "watch"
    return None


def _last_n_weekly(rates: list[float], n: int = 4) -> list[float]:
    if not rates:
        return []
    tail = rates[-n:]
    while len(tail) < n and tail:
        tail = [tail[0]] + tail
    return [round(v, 1) for v in tail[-n:]]


def _classify_loss_pattern(symbol: str, function: str, full_df: pd.DataFrame) -> dict[str, str]:
    def _loss_count(mask_df: pd.DataFrame) -> int:
        if mask_df.empty or "Profit [%]" not in mask_df.columns:
            return 0
        profits = mask_df["Profit [%]"].apply(_parse_profit)
        return int((profits < 0).sum())

    asset_losses = _loss_count(full_df[full_df["Symbol"] == symbol])
    func_losses = _loss_count(full_df[full_df["Function"] == function])

    if asset_losses > func_losses:
        return {
            "pattern": f"Asset-specific: review {symbol} fundamentals",
            "recommendation": (
                f"Review {symbol} fundamentals and macro context; "
                f"consider pausing signals on this asset."
            ),
        }
    if func_losses > asset_losses:
        return {
            "pattern": f"Function degradation: {function} underperforming across assets",
            "recommendation": (
                f"Recalibrate {function} parameters; review model assumptions across all assets."
            ),
        }
    return {
        "pattern": f"Combo issue: {symbol}/{function} — review model params",
        "recommendation": (
            f"Audit {symbol}/{function} combo; check for structural break or data staleness."
        ),
    }


def _format_drift_message(
    function: str,
    direction: str,
    interval: str,
    fwd_rate: float,
    severity: Literal["watch", "breach"],
    weekly_trend: list[float],
    monthly_trend: list[float],
    recommendation: str,
) -> str:
    ceiling = DRIFT_WATCH_CEILING if severity == "watch" else DRIFT_BREACH_CEILING
    falling_months = (
        DRIFT_WATCH_FALLING_MONTHS
        if severity == "watch"
        else DRIFT_BREACH_FALLING_MONTHS
    )
    weekly_str = " → ".join(f"{v:.1f}" for v in weekly_trend) if weekly_trend else "n/a"
    monthly_str = " → ".join(f"{v:.1f}" for v in monthly_trend) if monthly_trend else "n/a"
    return (
        f"{function} / {direction} / {interval}: FWD win rate {fwd_rate:.1f}% — "
        f"below {ceiling:.0f}% with {falling_months} consecutive monthly declines.<br>"
        f"Weekly trend: {weekly_str} (last 4 weeks).<br>"
        f"Monthly trend: {monthly_str}.<br>"
        f"Recommend: {recommendation}."
    )


def _read_csv_safe(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _check_portfolio_triggers(fwd_df: pd.DataFrame) -> list[dict[str, Any]]:
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
            df[status_col].astype(str).str.strip().str.lower() if status_col else "open"
        )

        closed_loss = df[(df["_status"] != "open") & (df["_profit"].notna()) & (df["_profit"] < 0)]
        for _, row in closed_loss.iterrows():
            symbol = str(row.get("Symbol", ""))
            function = str(row.get("Function", ""))
            interval = str(row.get("Interval", ""))
            pattern_info = _classify_loss_pattern(symbol, function, fwd_df)
            alerts.append({
                "trigger_type": "booked_loss",
                "severity": "breach",
                "side": side,
                "symbol": symbol,
                "function": function,
                "interval": interval,
                "direction": side.title(),
                "profit_pct": round(float(row["_profit"]), 2),
                "pattern": pattern_info["pattern"],
                "recommendation": pattern_info["recommendation"],
                "message": (
                    f"Booked loss on {side} position: {symbol} ({function}/{interval}). "
                    f"Realised P&L: {row['_profit']:.2f}%."
                ),
                "label": _LABEL_PORTFOLIO,
                "border_color": _BORDER_COLOR,
            })

        live_breach = df[
            (df["_status"] == "open")
            & (df["_profit"].notna())
            & (df["_profit"] < _MTM_LOSS_THRESHOLD)
        ]
        for _, row in live_breach.iterrows():
            alerts.append({
                "trigger_type": "live_mtm_breach",
                "severity": "breach",
                "side": side,
                "symbol": str(row.get("Symbol", "")),
                "function": str(row.get("Function", "")),
                "interval": str(row.get("Interval", "")),
                "direction": side.title(),
                "profit_pct": round(float(row["_profit"]), 2),
                "message": (
                    f"Live MTM breach on {side} position: "
                    f"{row.get('Symbol', '')} ({row.get('Function', '')}/{row.get('Interval', '')}). "
                    f"MTM: {row['_profit']:.2f}% (floor: {_MTM_LOSS_THRESHOLD}%)."
                ),
                "recommendation": "Review stop levels and position sizing; consider reducing exposure.",
                "label": _LABEL_PORTFOLIO,
                "border_color": _BORDER_COLOR,
            })

    return alerts


def _compute_degradation(fwd_df: pd.DataFrame, floor_pct: float) -> dict[str, Any]:
    signal_alerts: list[dict[str, Any]] = []
    checked_combos = 0

    if not fwd_df.empty and "Profit [%]" in fwd_df.columns:
        if "Signal" in fwd_df.columns:
            fwd_df = fwd_df.copy()
            fwd_df["_direction"] = fwd_df["Signal"].astype(str).str.strip().str.title()
        else:
            fwd_df = fwd_df.copy()
            fwd_df["_direction"] = "Long"

        fwd_df["Function"] = fwd_df["Function"].astype(str).str.strip()

        group_keys = ["Symbol", "Function", "Interval", "_direction"]
        for combo_key, group in fwd_df.groupby(group_keys):
            symbol, function, interval, direction = combo_key

            closed = group[
                group["Exit Date"].notna()
                & (group["Exit Date"].astype(str).str.strip().str.lower() != "")
            ]
            if len(closed) < _MIN_EXITS_FOR_ANALYSIS:
                continue

            checked_combos += 1
            weekly_rates = _weekly_win_rates(group)
            monthly_rates = _monthly_win_rates(group)
            cumulative_fwd_rate = _cumulative_fwd_win_rate(group)
            if cumulative_fwd_rate is None:
                continue

            severity = _classify_drift_severity(cumulative_fwd_rate, monthly_rates)
            if severity is None:
                continue

            bt_rate: float | None = None
            bt_col = "Backtested Win Rate [%]"
            if bt_col in group.columns:
                bt_vals = group[bt_col].dropna()
                if not bt_vals.empty:
                    try:
                        bt_rate = float(bt_vals.iloc[0])
                    except (ValueError, TypeError):
                        bt_rate = None

            pattern_info = _classify_loss_pattern(symbol, function, fwd_df)
            fwd_trend = _last_n_weekly(weekly_rates, 4)
            monthly_trend = [round(r, 1) for r in monthly_rates[-6:]]
            label = _LABEL_WATCH if severity == "watch" else _LABEL_BREACH
            recommendation = pattern_info["recommendation"]
            message = _format_drift_message(
                function,
                direction,
                interval,
                cumulative_fwd_rate,
                severity,
                fwd_trend,
                monthly_trend,
                recommendation,
            )

            signal_alerts.append({
                "trigger_type": "fwd_drift",
                "severity": severity,
                "strategy": function,
                "combo": {
                    "asset": symbol,
                    "function": function,
                    "interval": interval,
                    "direction": direction,
                },
                "bt_rate": round(bt_rate, 1) if bt_rate is not None else None,
                "fwd_rate": round(cumulative_fwd_rate, 1),
                "weekly_trend": fwd_trend,
                "monthly_trend": monthly_trend,
                "pattern": pattern_info["pattern"],
                "recommendation": recommendation,
                "message": message,
                "label": label,
                "border_color": _BORDER_COLOR,
            })

    portfolio_alerts = _check_portfolio_triggers(fwd_df)

    return {
        "triggered": bool(signal_alerts or portfolio_alerts),
        "alerts": signal_alerts,
        "portfolio_alerts": portfolio_alerts,
        "checked_combos": checked_combos,
        "alert_count": len(signal_alerts) + len(portfolio_alerts),
        "floor_pct": floor_pct,
        "label": _LABEL_BREACH if (signal_alerts or portfolio_alerts) else _LABEL_WATCH,
        "border_color": _BORDER_COLOR,
    }


def check_degradation(floor_pct: float = FWD_WR_FLOOR, *, use_cache: bool = True) -> dict[str, Any]:
    """Run Layer 1 degradation analysis with parquet + result disk cache."""
    if use_cache:
        cached = deg_cache.load_cached_degradation_result()
        if cached is not None:
            return cached

    fwd_df = deg_cache.load_fwd_trades_df()
    result = _compute_degradation(fwd_df, floor_pct)
    if use_cache:
        deg_cache.save_degradation_result(result)
    return result


def warm_degradation_cache(floor_pct: float = FWD_WR_FLOOR) -> dict[str, Any]:
    """Force rebuild — used by cron pre-warm."""
    deg_cache.load_fwd_trades_df(force_rebuild=True)
    result = _compute_degradation(deg_cache.load_fwd_trades_df(), floor_pct)
    deg_cache.save_degradation_result(result)
    return result
