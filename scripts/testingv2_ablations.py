#!/usr/bin/env python3
"""Testing v2 ablations: Combo B confirmed-only + Combo A TWY/GSR legs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.analysis.regime_experiments.metrics import (  # noqa: E402
    probability_weighted_summary,
)
from src.macro_intelligence.db.connection import get_connection, init_db  # noqa: E402
from src.macro_intelligence.engine.regime_v2_shadow import twy_roc_at_date  # noqa: E402


def combo_b_confirmed_only() -> dict[str, Any]:
    """Combo B with status ACTIVE or CONFIRMED (3/3 legs), 3M bullish."""
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT fr.spx_3m, cf.status, cf.date
            FROM combo_fires cf
            JOIN forward_returns fr ON cf.combo_id = fr.combo_id
            WHERE cf.runic_combo = 'B' AND fr.spx_3m IS NOT NULL
            ORDER BY cf.date
            """
        ).fetchall()
    all_rets = [r["spx_3m"] for r in rows]
    confirmed = [
        r["spx_3m"]
        for r in rows
        if (r["status"] or "").upper() in ("ACTIVE", "CONFIRMED", "CONFIRMED_3_OF_3")
    ]
    watch = [r["spx_3m"] for r in rows if (r["status"] or "").upper() == "WATCH"]
    return {
        "all_fires": probability_weighted_summary(all_rets, bullish=True, horizon="spx_3m"),
        "confirmed_only": probability_weighted_summary(
            confirmed, bullish=True, horizon="spx_3m"
        ),
        "watch_only": probability_weighted_summary(watch, bullish=True, horizon="spx_3m"),
        "n_all": len(all_rets),
        "n_confirmed": len(confirmed),
        "n_watch": len(watch),
    }


def combo_a_twy_gsr_ablation() -> dict[str, Any]:
    """Test whether TWY_ROC or GSR rare legs sharpen Combo A."""
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT cf.date, cf.status, fr.spx_3m, fr.spx_6m, cf.macro_regime
            FROM combo_fires cf
            JOIN forward_returns fr ON cf.combo_id = fr.combo_id
            WHERE cf.runic_combo = 'A'
            ORDER BY cf.date
            """
        ).fetchall()
        gsr_rows = conn.execute(
            """
            SELECT date, unconditional_pctile, raw_value
            FROM daily_readings WHERE var_id = 'GSR'
            """
        ).fetchall()
    gsr_by_date = {r["date"]: dict(r) for r in gsr_rows}
    base_3m: list[float] = []
    twy_dovish_3m: list[float] = []
    twy_hawkish_3m: list[float] = []
    gsr_rare_3m: list[float] = []
    for r in rows:
        r3 = r["spx_3m"]
        if r3 is None:
            continue
        base_3m.append(r3)
        twy = twy_roc_at_date(r["date"])
        d = twy.get("direction")
        if d == "DOVISH":
            twy_dovish_3m.append(r3)
        elif d == "HAWKISH":
            twy_hawkish_3m.append(r3)
        gsr = gsr_by_date.get(r["date"])
        if gsr and gsr.get("unconditional_pctile") is not None:
            if float(gsr["unconditional_pctile"]) >= 0.80:
                gsr_rare_3m.append(r3)
    return {
        "baseline_combo_a_3m": probability_weighted_summary(
            base_3m, bullish=False, horizon="spx_3m"
        ),
        "subset_twy_dovish_3m": probability_weighted_summary(
            twy_dovish_3m, bullish=False, horizon="spx_3m"
        ),
        "subset_twy_hawkish_3m": probability_weighted_summary(
            twy_hawkish_3m, bullish=False, horizon="spx_3m"
        ),
        "subset_gsr_pctile_80plus_3m": probability_weighted_summary(
            gsr_rare_3m, bullish=False, horizon="spx_3m"
        ),
        "note": "Post-hoc slice on existing Combo A fires — not a re-fired combo rule.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        default="macro_intelligence/analysis/regime_v2_experiments/X_testingv2_ablations.json",
    )
    args = parser.parse_args()
    payload = {
        "combo_b_confirmed_only": combo_b_confirmed_only(),
        "combo_a_twy_gsr_ablation": combo_a_twy_gsr_ablation(),
    }
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
