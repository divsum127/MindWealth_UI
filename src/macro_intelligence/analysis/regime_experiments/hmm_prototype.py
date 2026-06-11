"""Part D — research-only HMM prototype on backfilled emission vectors."""

from __future__ import annotations

from typing import Any

import numpy as np

from src.macro_intelligence.analysis.regime_experiments.metrics import summarize_returns
from src.macro_intelligence.db.connection import get_connection


def run_hmm_prototype(n_states: int = 3, max_rows: int = 500) -> dict[str, Any]:
    """
    Simple Gaussian HMM-style clustering on mean daily percentile vector.
    Labels: Risk-On, Risk-Off, Transition (by cluster sort).
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT date, AVG(unconditional_pctile) AS mean_pctile
            FROM emission_vectors
            WHERE unconditional_pctile IS NOT NULL
            GROUP BY date
            ORDER BY date DESC
            LIMIT ?
            """,
            (max_rows,),
        ).fetchall()
    if len(rows) < 30:
        return {"status": "DEFERRED", "reason": "insufficient emission_vectors rows"}

    dates = [r["date"] for r in reversed(rows)]
    obs = np.array([float(r["mean_pctile"]) for r in reversed(rows)]).reshape(-1, 1)

    # K-means init for 3 states
    centroids = np.percentile(obs, [20, 50, 80]).reshape(3, 1)
    labels = np.argmin(np.abs(obs - centroids.T), axis=1)
    state_names = ["Risk-Off", "Transition", "Risk-On"]
    order = np.argsort(centroids.flatten())
    remap = {old: state_names[i] for i, old in enumerate(order)}

    posteriors = []
    for i, lab in enumerate(labels):
        counts = np.bincount(labels[max(0, i - 20) : i + 1], minlength=3)
        p = counts / max(counts.sum(), 1)
        posteriors.append(
            {
                "date": dates[i],
                "state": remap[int(lab)],
                "posterior": {state_names[j]: float(p[j]) for j in range(3)},
            }
        )

    # Simple backtest proxy: high mean_pctile weeks vs SPX
    from src.macro_intelligence.data.yahoo_pull import fetch_yahoo_close
    from src.macro_intelligence.engine.forward_returns import forward_return_pct
    import pandas as pd

    spx = fetch_yahoo_close("^GSPC", "2010-01-01")
    risk_off_rets = []
    risk_on_rets = []
    for row in posteriors[::4]:
        st = row["state"]
        ret = forward_return_pct(spx, pd.Timestamp(row["date"]), 63)
        if ret is None:
            continue
        if st == "Risk-Off":
            risk_off_rets.append(ret)
        elif st == "Risk-On":
            risk_on_rets.append(ret)

    return {
        "status": "RESEARCH_PROTOTYPE",
        "n_obs": len(obs),
        "risk_off_3m": summarize_returns(risk_off_rets),
        "risk_on_3m": summarize_returns(risk_on_rets),
        "note": "Production HMM deferred until 6mo live emission_vectors",
        "sample_posteriors": posteriors[-5:],
        "state_by_date": {p["date"]: p["state"] for p in posteriors},
    }
