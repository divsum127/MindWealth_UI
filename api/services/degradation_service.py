"""Signal degradation detection service — Layer 1 Degradation Alerts (AI Analyst spec)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import pandas as pd

from api.services import degradation_cache as deg_cache
from src.config_paths import VIRTUAL_TRADING_LONG_CSV, VIRTUAL_TRADING_SHORT_CSV

FWD_WR_FLOOR = 60.0
_MTM_LOSS_THRESHOLD = -10.0
_MIN_EXITS_FOR_ANALYSIS = 3
_BORDER_COLOR = "#ff4d6d"
_LABEL_WATCH = "AI ANALYST · OVERWATCH AUTO-TRIGGERED · DEGRADATION WATCH"
_LABEL_BREACH = "AI ANALYST · OVERWATCH AUTO-TRIGGERED · DEGRADATION BREACH"
_LABEL_PORTFOLIO = "AI ANALYST · OVERWATCH AUTO-TRIGGERED · DEGRADATION BREACH"


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


def _is_declining_toward_floor(rates: list[float], floor: float = FWD_WR_FLOOR) -> bool:
    if len(rates) < 2:
        return False
    current = rates[-1]
    if current < floor:
        return False
    tail = rates[-4:] if len(rates) >= 4 else rates
    declines = sum(1 for i in range(1, len(tail)) if tail[i] < tail[i - 1])
    return declines >= 1 and current >= floor


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


def _format_degradation_message(
    function: str,
    direction: str,
    interval: str,
    fwd_rate: float,
    floor: float,
    severity: Literal["watch", "breach"],
    weekly_trend: list[float],
    recommendation: str,
) -> str:
    floor_word = "approaching" if severity == "watch" else ("above" if fwd_rate >= floor else "below")
    trend_str = " → ".join(f"{v:.1f}" for v in weekly_trend) if weekly_trend else "n/a"
    return (
        f"{function} / {direction} / {interval}: FWD win rate {fwd_rate:.1f}% — "
        f"{floor_word} {floor:.0f}% floor.<br>"
        f"Trend: {trend_str} (last 4 weeks).<br>"
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
            if not weekly_rates:
                continue

            current_fwd_rate = weekly_rates[-1]
            severity: Literal["watch", "breach"] | None = None

            if current_fwd_rate < floor_pct:
                severity = "breach"
            elif _is_declining_toward_floor(weekly_rates, floor_pct):
                severity = "watch"
            else:
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
            label = _LABEL_WATCH if severity == "watch" else _LABEL_BREACH
            recommendation = pattern_info["recommendation"]
            message = _format_degradation_message(
                function, direction, interval, current_fwd_rate, floor_pct,
                severity, fwd_trend, recommendation,
            )

            signal_alerts.append({
                "trigger_type": "fwd_degradation",
                "severity": severity,
                "strategy": function,
                "combo": {
                    "asset": symbol,
                    "function": function,
                    "interval": interval,
                    "direction": direction,
                },
                "bt_rate": round(bt_rate, 1) if bt_rate is not None else None,
                "fwd_rate": round(current_fwd_rate, 1),
                "weekly_trend": fwd_trend,
                "monthly_trend": [round(r, 1) for r in _monthly_win_rates(group)[-6:]],
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
