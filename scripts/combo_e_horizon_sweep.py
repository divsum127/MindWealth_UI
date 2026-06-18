#!/usr/bin/env python3
"""Combo E horizon sweep: SPX outcomes at 6M–18M in 3M steps."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.analysis.regime_experiments.metrics import (  # noqa: E402
    probability_weighted_summary,
)
from src.macro_intelligence.data.yahoo_pull import fetch_yahoo_close  # noqa: E402
from src.macro_intelligence.db.connection import get_connection  # noqa: E402
from src.macro_intelligence.engine.forward_returns import (  # noqa: E402
    _nyse_sessions,
    forward_return_pct,
)

HORIZONS = [
    ("6M", "spx_6m", 126, 5.0),
    ("9M", "spx_9m", 189, 7.5),
    ("12M", "spx_12m", 252, 10.0),
    ("15M", "spx_15m", 315, 12.5),
    ("18M", "spx_18m", 378, 15.0),
]

DEFAULT_OUT = (
    ROOT
    / "macro_intelligence/analysis/regime_v2_experiments/COMBO_E_horizon_sweep_6_18m.json"
)


def load_combo_e_fires() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT cf.combo_id, cf.date, cf.status,
                   fr.spx_6m, fr.spx_9m, fr.spx_12m
            FROM combo_fires cf
            LEFT JOIN forward_returns fr ON cf.combo_id = fr.combo_id
            WHERE cf.runic_combo = 'E'
            ORDER BY cf.date
            """
        ).fetchall()
    return [dict(r) for r in rows]


def compute_returns(
    fires: list[dict[str, Any]],
    spx: pd.Series,
    sessions: pd.DatetimeIndex,
) -> dict[str, list[float]]:
    """Forward returns per horizon; prefer DB cols for 6/9/12 when present."""
    db_col = {"spx_6m": "spx_6m", "spx_9m": "spx_9m", "spx_12m": "spx_12m"}
    out: dict[str, list[float]] = {h[1]: [] for h in HORIZONS}
    for row in fires:
        fire_ts = pd.Timestamp(row["date"])
        for _label, col, days, _bench in HORIZONS:
            ret: float | None = None
            if col in db_col and row.get(db_col[col]) is not None:
                ret = float(row[db_col[col]])
            else:
                ret = forward_return_pct(spx, fire_ts, days, sessions=sessions)
            if ret is not None:
                out[col].append(ret)
    return out


def horizon_row(
    label: str,
    col: str,
    benchmark: float,
    returns: list[float],
) -> dict[str, Any]:
    bear = probability_weighted_summary(
        returns, bullish=False, benchmark_pct=benchmark, horizon=col
    )
    bull = probability_weighted_summary(
        returns, bullish=True, benchmark_pct=benchmark, horizon=col
    )
    return {
        "horizon_label": label,
        "horizon_col": col,
        "benchmark_pct": benchmark,
        "n_mature": bear["n"],
        "bear_hit_pct": round(bear["hit_rate"] * 100, 1) if bear["hit_rate"] is not None else None,
        "bull_up_pct": round(bull["hit_rate"] * 100, 1) if bull["hit_rate"] is not None else None,
        "avg_return_pct": round(bull["avg"], 2) if bull.get("avg") is not None else None,
        "bear_avg_win_pct": round(bear["avg_win"], 2) if bear["avg_win"] is not None else None,
        "bear_avg_loss_pct": round(bear["avg_loss"], 2) if bear["avg_loss"] is not None else None,
        "bear_pw_expected_pct": round(bear["pw_expected"], 2) if bear["pw_expected"] is not None else None,
        "bear_excess_pct": round(bear["excess_pct"], 2) if bear["excess_pct"] is not None else None,
        "bull_pw_expected_pct": round(bull["pw_expected"], 2) if bull["pw_expected"] is not None else None,
        "bull_excess_pct": round(bull["excess_pct"], 2) if bull["excess_pct"] is not None else None,
    }


def pick_recommended(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Heuristic: prefer 12M unless another horizon has clearly higher bear hit with n≥30."""
    eligible = [r for r in rows if (r.get("n_mature") or 0) >= 30]
    if not eligible:
        eligible = rows
    by_bear = sorted(eligible, key=lambda r: (r.get("bear_hit_pct") or 0), reverse=True)
    best_bear = by_bear[0] if by_bear else None
    row_12 = next((r for r in rows if r["horizon_label"] == "12M"), None)
    return {
        "config_primary": "12M",
        "highest_bear_hit_horizon": best_bear["horizon_label"] if best_bear else None,
        "highest_bear_hit_pct": best_bear.get("bear_hit_pct") if best_bear else None,
        "note": (
            "Combo E is structural bearish; low bear hit at all horizons is expected. "
            "Keep 12M primary unless Rohit prefers horizon with best bear hit + n_mature."
        ),
        "12M_bear_hit_pct": row_12.get("bear_hit_pct") if row_12 else None,
        "12M_n_mature": row_12.get("n_mature") if row_12 else None,
    }


def markdown_table(rows: list[dict[str, Any]], n_total: int) -> str:
    lines = [
        "*Combo E horizon sweep — computed via `scripts/combo_e_horizon_sweep.py` "
        f"({datetime.now().strftime('%Y-%m-%d')}). n_total fires = {n_total}. "
        "Bear hit = % SPX down. PW bear uses down moves as wins. "
        "15M/18M computed from Yahoo ^GSPC (not stored in `forward_returns` yet).*",
        "",
        "**Overall Combo E — bearish framing (validated direction):**",
        "",
        "| Horizon | n_mature | Bear Hit% ↓ | Avg Return% | Bear Avg Win% | Bear Avg Loss% | PW Bear% | Benchmark | Bear Excess |",
        "|---------|----------|-------------|-------------|---------------|----------------|----------|-----------|-------------|",
    ]
    for r in rows:
        lines.append(
            f"| {r['horizon_label']} | {r['n_mature']} | {r['bear_hit_pct']}% | "
            f"{r['avg_return_pct']:+.2f}% | {r['bear_avg_win_pct']:+.2f}% | "
            f"{r['bear_avg_loss_pct']:+.2f}% | {r['bear_pw_expected_pct']:+.2f}% | "
            f"{r['benchmark_pct']}% | {r['bear_excess_pct']:+.2f}pp |"
        )
    lines.extend(
        [
            "",
            "**SPX Up% (diagnostic — Combo E fires often coincide with positive drift):**",
            "",
            "| Horizon | n_mature | SPX Up% | PW Bull% | Bull Excess |",
            "|---------|----------|---------|----------|-------------|",
        ]
    )
    for r in rows:
        lines.append(
            f"| {r['horizon_label']} | {r['n_mature']} | {r['bull_up_pct']}% | "
            f"{r['bull_pw_expected_pct']:+.2f}% | {r['bull_excess_pct']:+.2f}pp |"
        )
    return "\n".join(lines)


def run_sweep(*, out_path: Path) -> dict[str, Any]:
    fires = load_combo_e_fires()
    spx = fetch_yahoo_close("^GSPC", "1990-01-01")
    sessions = _nyse_sessions()
    returns_by_h = compute_returns(fires, spx, sessions)
    rows = [
        horizon_row(label, col, bench, returns_by_h[col])
        for label, col, _days, bench in HORIZONS
    ]
    payload = {
        "combo": "E",
        "direction": "bearish",
        "n_total_fires": len(fires),
        "run_date": datetime.now().strftime("%Y-%m-%d"),
        "horizons_trading_days": {h[0]: h[2] for h in HORIZONS},
        "horizons": rows,
        "recommendation": pick_recommended(rows),
        "markdown_table": markdown_table(rows, len(fires)),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    print(f"\nWrote {out_path}", flush=True)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Combo E 6M–18M horizon sweep")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    run_sweep(out_path=args.out)


if __name__ == "__main__":
    main()
