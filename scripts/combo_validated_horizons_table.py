#!/usr/bin/env python3
"""Regenerate validated-horizon PW table for named combos (§1 feedback)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.analysis.regime_experiments.metrics import (  # noqa: E402
    probability_weighted_summary,
)
from src.macro_intelligence.config import load_config
from src.macro_intelligence.data.yahoo_pull import fetch_yahoo_close
from src.macro_intelligence.db.connection import get_connection
from src.macro_intelligence.engine.forward_returns import (  # noqa: E402
    _nyse_sessions,
    forward_return_pct,
)

# horizon label, trading days, benchmark %, bullish
COMBO_ROWS = [
    ("B", "3M", 63, 2.5, True),
    ("C", "6M", 126, 5.0, False),
    ("C", "3M", 63, 2.5, False),
    ("D", "5D", 5, 0.5, False),
    ("E", "12M", 252, 10.0, False),
    ("F", "6M", 126, 5.0, True),
    ("F", "3M", 63, 2.5, True),
    ("A", "6M", 126, 5.0, False),
    ("A", "3M", 63, 2.5, False),
]


def load_unique_fires(combo: str) -> list[str]:
    """Distinct fire dates per combo (dedupe duplicate combo_id rows)."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT date FROM combo_fires
            WHERE runic_combo = ?
            ORDER BY date
            """,
            (combo,),
        ).fetchall()
    return [r["date"] for r in rows]


def returns_for_dates(
    dates: list[str],
    trading_days: int,
    spx: pd.Series,
    sessions: pd.DatetimeIndex,
) -> list[float]:
    out: list[float] = []
    for ds in dates:
        ret = forward_return_pct(spx, pd.Timestamp(ds), trading_days, sessions=sessions)
        if ret is not None:
            out.append(ret)
    return out


def fmt_pct(v: float | None, *, signed: bool = True) -> str:
    if v is None:
        return "—"
    if signed:
        return f"{v:+.2f}" if v != 0 else "0.00"
    return f"{v:.1f}"


def row_stats(
    combo: str,
    horizon_label: str,
    dates: list[str],
    trading_days: int,
    benchmark: float,
    bullish: bool,
    spx: pd.Series,
    sessions: pd.DatetimeIndex,
) -> dict[str, Any]:
    rets = returns_for_dates(dates, trading_days, spx, sessions)
    n_total = len(dates)
    n_mature = len(rets)
    if not rets:
        return {
            "combo": combo,
            "horizon_label": horizon_label,
            "n_total": n_total,
            "n_mature": 0,
            "hit_pct": None,
            "avg_win": None,
            "avg_loss": None,
            "pw_expected": None,
            "benchmark": benchmark,
            "excess": None,
            "direction": "bullish" if bullish else "bearish",
        }
    pw = probability_weighted_summary(
        rets, bullish=bullish, benchmark_pct=benchmark, horizon=f"spx_{horizon_label.lower()}"
    )
    hit = pw["hit_rate"]
    return {
        "combo": combo,
        "horizon_label": horizon_label,
        "n_total": n_total,
        "n_mature": n_mature,
        "hit_pct": round(hit * 100, 1) if hit is not None else None,
        "avg_win": round(pw["avg_win"], 2) if pw.get("avg_win") is not None else None,
        "avg_loss": round(pw["avg_loss"], 2) if pw.get("avg_loss") is not None else None,
        "pw_expected": round(pw["pw_expected"], 2) if pw.get("pw_expected") is not None else None,
        "benchmark": benchmark,
        "excess": round(pw["excess_pct"], 2) if pw.get("excess_pct") is not None else None,
        "direction": "bullish" if bullish else "bearish",
    }


def markdown_table(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| Combo | Primary horizon | n_total | n_mature | Hit % | Avg win % | Avg loss % | "
        "PW expected % | Benchmark % | Excess % |",
        "|-------|-----------------|---------|----------|-------|-----------|------------|"
        "---------------|-------------|----------|",
    ]
    labels = {
        ("B", "3M"): "**B** (bullish)",
        ("C", "6M"): "**C** (bearish)",
        ("C", "3M"): "**C** (bearish)",
        ("D", "5D"): "**D** (bearish)",
        ("E", "12M"): "**E** (bearish)",
        ("F", "6M"): "**F** (bullish)",
        ("F", "3M"): "**F** (bullish)",
        ("A", "6M"): "**A** (TIGHT/bearish)",
        ("A", "3M"): "**A** (TIGHT/bearish)",
    }
    primary = {
        ("C", "6M"): "6M primary",
        ("C", "3M"): "3M secondary",
        ("F", "6M"): "6M primary",
        ("F", "3M"): "3M secondary",
        ("B", "3M"): "3M",
        ("D", "5D"): "5D primary",
        ("E", "12M"): "12M primary",
        ("A", "6M"): "6M",
        ("A", "3M"): "3M",
    }
    for r in rows:
        key = (r["combo"], r["horizon_label"])
        combo_cell = labels.get(key, r["combo"])
        hz = primary.get(key, r["horizon_label"])
        if r["n_mature"] == 0:
            lines.append(
                f"| {combo_cell} | {hz} | {r['n_total']} | 0 | — | — | — | — | "
                f"+{r['benchmark']:.1f} | — |"
            )
        else:
            lines.append(
                f"| {combo_cell} | {hz} | {r['n_total']} | {r['n_mature']} | "
                f"{r['hit_pct']:.1f} | {fmt_pct(r['avg_win'])} | {fmt_pct(r['avg_loss'])} | "
                f"{fmt_pct(r['pw_expected'])} | +{r['benchmark']:.1f} | "
                f"**{fmt_pct(r['excess'])}** |"
            )
    lines.append(
        "| **G** | — | 0 | — | — | — | — | — | — | No return table |"
    )
    return "\n".join(lines)


def run_sweep() -> dict[str, Any]:
    cfg = load_config()
    _ = cfg  # ensure config loads
    spx = fetch_yahoo_close("^GSPC", "1990-01-01")
    sessions = _nyse_sessions()
    cache: dict[str, list[str]] = {}
    rows: list[dict[str, Any]] = []
    for combo, hz, days, bench, bullish in COMBO_ROWS:
        if combo not in cache:
            cache[combo] = load_unique_fires(combo)
        rows.append(
            row_stats(combo, hz, cache[combo], days, bench, bullish, spx, sessions)
        )
    return {"rows": rows, "markdown_table": markdown_table(rows)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT
        / "macro_intelligence/analysis/regime_v2_experiments/COMBO_validated_horizons_pw.json",
    )
    args = parser.parse_args()
    payload = run_sweep()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(payload["markdown_table"])
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
