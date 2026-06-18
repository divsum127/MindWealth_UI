#!/usr/bin/env python3
"""Per-variable threshold sweep (Rohit v2 §1d) — isolation, not combos.

For each of 12 variables, fire on first crossing into percentile bands
(0-100 scale) and measure SPX forward returns with PW columns.
"""

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
from src.macro_intelligence.config import load_config  # noqa: E402
from src.macro_intelligence.data.yahoo_pull import fetch_yahoo_close  # noqa: E402
from src.macro_intelligence.db.connection import get_connection, init_db  # noqa: E402
from src.macro_intelligence.engine.forward_returns import forward_return_pct  # noqa: E402

def _norm_pctile(p: float | None) -> float | None:
    """Legacy rows stored 0-1; current pipeline uses 0-100."""
    if p is None:
        return None
    val = float(p)
    if 0 < val <= 1.0:
        return val * 100.0
    return val


# var_id -> list of (label, low_pctile_inclusive, high_pctile_inclusive), bullish
SWEEP_BANDS: dict[str, list[tuple[str, float, float, bool]]] = {
    "VIX": [("high_70_79", 70, 79, False), ("high_80_plus", 80, 100, False)],
    "HY": [("high_75_84", 75, 84, False), ("high_85_plus", 85, 100, False)],
    "VXTS": [("high_75_84", 75, 84, False), ("high_85_plus", 85, 100, False)],
    "NFCI": [("tight_70_79", 70, 79, False), ("tight_80_plus", 80, 100, False)],
    "WALCL": [("high_75_84", 75, 84, True), ("high_85_plus", 85, 100, True)],
    "CNH": [("high_75_84", 75, 84, False), ("high_85_plus", 85, 100, False)],
    "WTI": [("high_75_84", 75, 84, False), ("high_85_plus", 85, 100, False)],
    "CFTC": [("low_5_14", 5, 14, True), ("low_below_5", 0, 5, True)],
    "CAPE": [("high_85_94", 85, 94, False), ("high_95_plus", 95, 100, False)],
    "CPI": [("high_75_84", 75, 84, False), ("high_85_plus", 85, 100, False)],
    "GSR": [("high_75_84", 75, 84, False), ("high_85_plus", 85, 100, False)],
    "CURVE": [
        ("inverted_70_79", 70, 79, False),
        ("inverted_80_plus", 80, 100, False),
    ],
}

HORIZONS = [
    ("spx_1m", 21),
    ("spx_3m", 63),
    ("spx_6m", 126),
    ("spx_9m", 189),
    ("spx_12m", 252),
]


def _first_cross_events(
    var_id: str,
    lo: float,
    hi: float,
    spx: pd.Series,
    start: str = "2010-01-01",
) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT date, raw_value, unconditional_pctile
            FROM daily_readings
            WHERE var_id = ? AND date >= ? AND unconditional_pctile IS NOT NULL
            ORDER BY date
            """,
            (var_id, start),
        ).fetchall()
    events: list[dict[str, Any]] = []
    prev_in = False
    for r in rows:
        p = _norm_pctile(r["unconditional_pctile"])
        if p is None:
            prev_in = False
            continue
        in_band = lo <= p <= hi
        if in_band and not prev_in:
            dt = pd.Timestamp(r["date"])
            rets = {
                h: forward_return_pct(spx, dt, days) for h, days in HORIZONS
            }
            events.append(
                {
                    "date": r["date"],
                    "raw_value": r["raw_value"],
                    "pctile": p,
                    "returns": rets,
                }
            )
        prev_in = in_band
    return events


def run_sweep(start: str = "2010-01-01") -> dict[str, Any]:
    init_db()
    spx = fetch_yahoo_close("^GSPC", start)
    cfg_vars = {v["id"]: v for v in load_config().get("variables", [])}
    out: dict[str, Any] = {"start": start, "variables": {}}
    for var_id, bands in SWEEP_BANDS.items():
        var_out: list[dict[str, Any]] = []
        for label, lo, hi, bullish in bands:
            events = _first_cross_events(var_id, lo, hi, spx, start=start)
            horizons: dict[str, Any] = {}
            for h, _ in HORIZONS:
                rets = [e["returns"].get(h) for e in events if e["returns"].get(h) is not None]
                horizons[h] = probability_weighted_summary(
                    rets, bullish=bullish, horizon=h
                )
            var_out.append(
                {
                    "band": label,
                    "pctile_range": [lo, hi],
                    "bullish": bullish,
                    "n_events": len(events),
                    "horizons": horizons,
                    "instances": events[:25],
                }
            )
        out["variables"][var_id] = {
            "config": cfg_vars.get(var_id, {}),
            "bands": var_out,
        }
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2010-01-01")
    parser.add_argument(
        "--out",
        default="macro_intelligence/analysis/regime_v2_experiments/F_per_variable_sweep_v2.json",
    )
    args = parser.parse_args()
    payload = run_sweep(args.start)
    out_path = ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"written": str(out_path), "n_vars": len(payload["variables"])}, indent=2))


if __name__ == "__main__":
    main()
