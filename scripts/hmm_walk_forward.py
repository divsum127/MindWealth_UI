#!/usr/bin/env python3
"""HMM walk-forward validation scaffold (Rohit v2 §2).

AHIL HANDOFF — how to run after 6 months live vectors:
  1. Ensure `emission_vectors` has daily rows (cron: run_emission_vectors_daily.py).
  2. Run: `.venv/bin/python scripts/hmm_walk_forward.py --from-year 2015 --to-year 2025`
  3. Inspect JSON: transition matrix stability + Risk-Off/Risk-On lead times.
  4. Label states via anchor dates (ANCHORS below) — remap clusters each window.
  5. Wire posteriors into classifier prompt (Part D2) once validated.

Uses hmmlearn GaussianHMM (diag covariance), expanding train window from 1990.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.db.connection import get_connection, init_db  # noqa: E402

ANCHORS: dict[str, list[str]] = {
    "Risk-Off": [
        "1998-08-01",
        "2002-10-01",
        "2008-10-01",
        "2009-03-01",
        "2011-08-01",
        "2020-03-01",
    ],
    "Risk-On": [
        "1995-01-01",
        "2003-03-01",
        "2009-07-01",
        "2011-10-01",
        "2013-03-01",
        "2018-01-01",
        "2020-06-01",
    ],
    "Transition": [
        "2007-07-01",
        "2018-12-01",
        "2022-10-01",
        "2025-04-01",
    ],
}

RISK_OFF_COMBOS = ("C", "D", "E", "G")
RISK_ON_COMBOS = ("B", "F")


def _load_weekly_vectors(start: str, end: str) -> tuple[list[str], np.ndarray]:
    """Weekly mean percentile vector (14 vars) from emission_vectors."""
    init_db()
    with get_connection() as conn:
        var_rows = conn.execute(
            "SELECT DISTINCT var_id FROM emission_vectors ORDER BY var_id"
        ).fetchall()
        vars_ = [r["var_id"] for r in var_rows if r["var_id"] != "SPX_W"]
        rows = conn.execute(
            """
            SELECT date, var_id, unconditional_pctile
            FROM emission_vectors
            WHERE date >= ? AND date <= ? AND unconditional_pctile IS NOT NULL
            ORDER BY date
            """,
            (start, end),
        ).fetchall()
    if not rows:
        return [], np.empty((0, 0))
    df = pd.DataFrame([dict(r) for r in rows])
    df["date"] = pd.to_datetime(df["date"])
    weekly = (
        df.groupby([pd.Grouper(key="date", freq="W-FRI"), "var_id"])["unconditional_pctile"]
        .mean()
        .unstack(fill_value=np.nan)
    )
    for v in vars_:
        if v not in weekly.columns:
            weekly[v] = np.nan
    weekly = weekly[vars_].dropna(how="all")
    # Neutral fill for sparse vars (CPI etc.) — required for stable HMM fit
    weekly = weekly.ffill().bfill().fillna(0.5)
    dates = [d.strftime("%Y-%m-%d") for d in weekly.index]
    return dates, weekly.values.astype(float)


def _remap_by_anchors(model, X: np.ndarray, dates: list[str]) -> dict[int, str]:
    """Assign economic labels to HMM states using anchor dates in training window."""
    labels = model.predict(X)
    state_scores: dict[int, dict[str, int]] = {i: {s: 0 for s in ANCHORS} for i in range(3)}
    for i, d in enumerate(dates):
        st = int(labels[i])
        dt = pd.Timestamp(d)
        for name, anchors in ANCHORS.items():
            for a in anchors:
                if abs((dt - pd.Timestamp(a)).days) <= 14:
                    state_scores[st][name] += 1
    mapping: dict[int, str] = {}
    used: set[str] = set()
    for st in range(3):
        best = max(state_scores[st], key=lambda k: state_scores[st][k])
        if state_scores[st][best] > 0 and best not in used:
            mapping[st] = best
            used.add(best)
    # Fill unmapped from mean ordering
    order = np.argsort(model.means_.mean(axis=1))
    defaults = ["Risk-Off", "Transition", "Risk-On"]
    for st in range(3):
        if st not in mapping:
            for dname in defaults:
                if dname not in mapping.values():
                    mapping[st] = dname
                    break
    return mapping


def _combo_fires(start: str, end: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT cf.date, cf.runic_combo, cf.macro_regime
            FROM combo_fires cf
            WHERE cf.date >= ? AND cf.date <= ?
              AND cf.runic_combo IS NOT NULL
            ORDER BY cf.date
            """,
            (start, end),
        ).fetchall()
    return [dict(r) for r in rows]


def _lead_times(
    fires: list[dict],
    posterior_by_date: dict[str, dict[str, float]],
    target_state: str,
    weeks_lookback: int = 8,
) -> list[int]:
    lags: list[int] = []
    for f in fires:
        fd = pd.Timestamp(f["date"])
        found = 0
        for w in range(1, weeks_lookback + 1):
            check = (fd - pd.Timedelta(weeks=w)).strftime("%Y-%m-%d")
            post = posterior_by_date.get(check, {})
            if post.get(target_state, 0) >= 0.5:
                found = w
                break
        lags.append(found)
    return lags


def run_walk_forward(
    train_end_year: int = 2014,
    test_from: int = 2015,
    test_to: int = 2025,
) -> dict[str, Any]:
    try:
        from hmmlearn.hmm import GaussianHMM
    except ImportError as e:
        return {
            "status": "BLOCKED",
            "error": "pip install hmmlearn",
            "detail": str(e),
        }

    results: list[dict[str, Any]] = []
    for test_year in range(test_from, test_to + 1):
        train_end = f"{train_end_year}-12-31"
        test_start = f"{test_year}-01-01"
        test_end = f"{test_year}-12-31"
        train_dates, X_train = _load_weekly_vectors("1990-01-01", train_end)
        test_dates, X_test = _load_weekly_vectors(test_start, test_end)
        if len(train_dates) < 100 or len(test_dates) < 4:
            results.append({"test_year": test_year, "status": "SKIP", "reason": "thin data"})
            train_end_year = test_year
            continue
        model = GaussianHMM(
            n_components=3,
            covariance_type="diag",
            n_iter=200,
            random_state=42,
        )
        model.fit(X_train)
        mapping = _remap_by_anchors(model, X_train, train_dates)
        inv_map = {v: k for k, v in mapping.items()}
        risk_off_idx = inv_map.get("Risk-Off", 0)
        risk_on_idx = inv_map.get("Risk-On", 2)

        posteriors = model.predict_proba(X_test)
        post_by_date: dict[str, dict[str, float]] = {}
        for i, d in enumerate(test_dates):
            post_by_date[d] = {
                mapping[j]: float(posteriors[i, j]) for j in range(3)
            }

        fires = _combo_fires(test_start, test_end)
        risk_off_fires = [
            f
            for f in fires
            if f["runic_combo"] in RISK_OFF_COMBOS
            or (
                f["runic_combo"] == "A"
                and "TIGHT" in str(f.get("macro_regime", "")).upper()
            )
        ]
        risk_on_fires = [
            f
            for f in fires
            if f["runic_combo"] in RISK_ON_COMBOS
            or (
                f["runic_combo"] == "A"
                and "EASY" in str(f.get("macro_regime", "")).upper()
            )
        ]
        off_lags = _lead_times(risk_off_fires, post_by_date, "Risk-Off")
        on_lags = _lead_times(risk_on_fires, post_by_date, "Risk-On")

        def _stats(lags: list[int]) -> dict[str, Any]:
            if not lags:
                return {"n": 0, "note": "blank year"}
            positive = [x for x in lags if x > 0]
            return {
                "n": len(lags),
                "median_weeks": float(np.median(lags)),
                "min_weeks": int(min(lags)),
                "max_weeks": int(max(lags)),
                "pct_any_lead": len(positive) / len(lags) if lags else 0,
            }

        trans = model.transmat_.tolist()
        results.append(
            {
                "test_year": test_year,
                "train_through": train_end,
                "status": "OK",
                "state_mapping": mapping,
                "transition_matrix": trans,
                "risk_off_track": _stats(off_lags),
                "risk_on_track": _stats(on_lags),
                "n_train_weeks": len(train_dates),
            }
        )
        train_end_year = test_year

    return {"status": "OK", "windows": results, "anchors": ANCHORS}


def main() -> None:
    parser = argparse.ArgumentParser(description="HMM walk-forward validation")
    parser.add_argument("--from-year", type=int, default=2015)
    parser.add_argument("--to-year", type=int, default=2025)
    parser.add_argument(
        "--out",
        default="macro_intelligence/analysis/regime_v2_experiments/D_hmm_walk_forward.json",
    )
    args = parser.parse_args()
    payload = run_walk_forward(test_from=args.from_year, test_to=args.to_year)
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"written": str(out), "status": payload.get("status")}, indent=2))


if __name__ == "__main__":
    main()
