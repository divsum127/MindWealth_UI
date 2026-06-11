"""Test 17: TrendPulse sentiment deterioration sweep (PDF Part 7).

Detects episodes where SSI falls at >= threshold/week for 2+ consecutive weeks
in the bearish direction, then measures SPX forward returns.

Sweep: 60th / 70th / 80th percentile of |weekly SSI delta| distribution.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.sentiment_superindex.analysis.forward_metrics import load_spx, returns_at_horizons, summarize_returns
from src.sentiment_superindex.analysis.report_utils import metrics_table, save_artifact, write_md_snippet
from src.sentiment_superindex.analysis.ssi_history import build_ssi_history_frame


def _weekly_deltas(ssi: pd.Series) -> pd.Series:
    """Resample to Friday closes and compute week-on-week changes."""
    weekly = ssi.resample("W-FRI").last().dropna()
    return weekly.diff().dropna()


def _find_deterioration_episodes(
    weekly_deltas: pd.Series,
    threshold: float,
) -> pd.DatetimeIndex:
    """Return dates of the first week in each 2+-week consecutive deterioration episode.

    Deterioration week: delta <= -threshold (falling by at least threshold/week).
    Consecutive: 2 or more such weeks back-to-back.
    """
    is_det = weekly_deltas <= -threshold
    episode_starts = []
    in_episode = False
    run_length = 0
    for dt, flag in zip(weekly_deltas.index, is_det):
        if flag:
            run_length += 1
            if run_length == 2:
                # start of a confirmed 2-week deterioration episode
                episode_starts.append(dt)
        else:
            run_length = 0
            in_episode = False
    return pd.DatetimeIndex(episode_starts)


def run_and_report(start: str = "2010-01-01") -> dict[str, Any]:
    hist = build_ssi_history_frame(start)
    score_col = "ssi_level" if "ssi_level" in hist.columns else "ssi_score"
    if score_col not in hist.columns:
        raise ValueError(f"ssi_history missing expected score column; found: {list(hist.columns)}")

    ssi = hist[score_col].dropna()
    spx = load_spx(start)
    deltas = _weekly_deltas(ssi)

    # Sweep 60th / 70th / 80th percentile of |weekly change| magnitudes
    abs_deltas = deltas.abs()
    pctile_thresholds = {
        "p60": float(np.percentile(abs_deltas, 60)),
        "p70": float(np.percentile(abs_deltas, 70)),
        "p80": float(np.percentile(abs_deltas, 80)),
    }

    results: list[dict[str, Any]] = []
    for label, thr in pctile_thresholds.items():
        episodes = _find_deterioration_episodes(deltas, thr)
        ret_rows = returns_at_horizons(spx, episodes)
        m = summarize_returns(ret_rows, long_side=True)
        results.append(
            {
                "label": label,
                "threshold": round(thr, 4),
                "n_episodes": len(episodes),
                "metrics": m,
                "episode_dates": [str(d.date()) for d in episodes],
            }
        )

    payload = {
        "test_id": "17_trendpulse",
        "start": start,
        "weekly_delta_stats": {
            "n": len(deltas),
            "mean": round(float(deltas.mean()), 4),
            "std": round(float(deltas.std()), 4),
            "p60": round(pctile_thresholds["p60"], 4),
            "p70": round(pctile_thresholds["p70"], 4),
            "p80": round(pctile_thresholds["p80"], 4),
        },
        "results": results,
    }
    save_artifact("17_trendpulse", payload)

    md = "# Test 17: TrendPulse sentiment deterioration (PDF Part 7)\n\n"
    md += "**Definition:** Episode starts when weekly SSI falls ≥ threshold for 2+ consecutive weeks.\n\n"
    md += "## Weekly SSI delta distribution\n\n"
    stats = payload["weekly_delta_stats"]
    md += f"n={stats['n']}, mean={stats['mean']}, std={stats['std']}\n\n"
    md += f"| Percentile | Threshold |\n|---|---|\n"
    for k in ("p60", "p70", "p80"):
        md += f"| {k} | {stats[k]} |\n"
    md += "\n"
    for r in results:
        md += f"\n## {r['label']} (threshold={r['threshold']}, n={r['n_episodes']})\n\n"
        md += metrics_table(r["metrics"]) + "\n"
    write_md_snippet("17_trendpulse", md)
    return payload
