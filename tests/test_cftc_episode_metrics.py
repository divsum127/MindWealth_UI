"""CFTC episode distribution metrics — worked examples and ranking spec."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.sentiment_superindex.analysis.cftc_episode_metrics import (
    analyze_par_row,
    build_market_benchmark,
    summarize_episode_horizon,
)
from src.sentiment_superindex.analysis.cftc_report_format import (
    WORKED_EXAMPLE_A,
    WORKED_EXAMPLE_B,
    rank_cells_by_gap,
)


class TestCftcEpisodeMetrics(unittest.TestCase):
    def test_worked_example_a_tail_driven(self):
        m = summarize_episode_horizon(WORKED_EXAMPLE_A, benchmark=None, long_side=True)
        self.assertEqual(m["n"], 9)
        self.assertAlmostEqual(m["mean"], 5.8889, places=3)
        self.assertAlmostEqual(m["median"], 2.0, places=3)
        self.assertAlmostEqual(m["mean_median_gap"], 3.8889, places=3)
        self.assertAlmostEqual(m["hit_pct"], 66.67, places=1)
        self.assertAlmostEqual(m["worst"], -4.0, places=3)
        self.assertAlmostEqual(m["best"], 22.0, places=3)

    def test_worked_example_b_market_beta(self):
        m = summarize_episode_horizon(WORKED_EXAMPLE_B, benchmark=None, long_side=True)
        self.assertEqual(m["n"], 9)
        self.assertAlmostEqual(m["mean"], 2.3333, places=3)
        self.assertAlmostEqual(m["median"], 3.0, places=3)
        self.assertAlmostEqual(m["mean_median_gap"], -0.6667, places=3)
        self.assertAlmostEqual(m["hit_pct"], 77.78, places=1)
        self.assertAlmostEqual(m["worst"], -2.0, places=3)

    def test_example_a_ranks_above_b_on_gap(self):
        a = summarize_episode_horizon(WORKED_EXAMPLE_A, benchmark=None, long_side=True)
        b = summarize_episode_horizon(WORKED_EXAMPLE_B, benchmark=None, long_side=True)
        self.assertGreater(a["mean_median_gap"], b["mean_median_gap"])
        rows = [
            {"pattern": "SQUEEZE", "n_episodes": 9, "metrics": {"12w": a}},
            {"pattern": "SQUEEZE", "n_episodes": 9, "metrics": {"12w": b}},
        ]
        ranked = rank_cells_by_gap(rows, "12w", squeeze_only=True)
        self.assertEqual(ranked[0]["metrics"]["12w"]["mean"], a["mean"])

    def test_required_distribution_fields_present(self):
        m = summarize_episode_horizon(WORKED_EXAMPLE_A, benchmark=None, long_side=True)
        for key in ("n", "mean", "median", "mean_median_gap", "hit_pct", "best", "worst"):
            self.assertIn(key, m)
            self.assertIsNotNone(m[key])

    def test_excess_metrics_long_side(self):
        m = summarize_episode_horizon([5.0, 3.0, 1.0], benchmark=2.0, long_side=True)
        self.assertAlmostEqual(m["mean_excess"], 1.0, places=3)
        self.assertAlmostEqual(m["hit_excess_pct"], 66.67, places=1)

    def test_excess_metrics_short_side(self):
        m = summarize_episode_horizon([-3.0, -1.0, 1.0], benchmark=0.0, long_side=False)
        self.assertAlmostEqual(m["hit_excess_pct"], 66.67, places=1)

    def test_par_row_uses_all_weeks_no_collapse(self):
        import numpy as np
        import pandas as pd

        weeks = pd.DatetimeIndex(
            [pd.Timestamp("2020-01-07") + pd.Timedelta(days=7 * i) for i in range(4)]
        )
        spx = pd.Series(
            [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0],
            index=pd.date_range("2020-01-01", periods=8, freq="B"),
        )
        bench = build_market_benchmark(spx, weeks, horizons={"4w": 4})
        par = analyze_par_row(weeks, spx, benchmark=bench, horizons={"4w": 4})
        self.assertEqual(par["n_weeks"], 4)
        self.assertEqual(par["n_episodes"], 4)

    def test_subsample_stability_twelve_offsets(self):
        import numpy as np
        import pandas as pd

        from src.sentiment_superindex.analysis.cftc_episode_metrics import subsample_stability_weekly

        weeks = pd.date_range("2020-01-07", periods=24, freq="7D")
        qual = weeks[[0, 1, 12, 13]]
        spx = pd.Series(
            np.linspace(3000, 3200, len(weeks) * 5),
            index=pd.date_range(weeks[0], periods=len(weeks) * 5, freq="B"),
        )
        out = subsample_stability_weekly(
            pd.DatetimeIndex(qual),
            pd.DatetimeIndex(weeks),
            spx,
            benchmark={"12w": 2.0},
            horizon_label="12w",
            stride=12,
        )
        self.assertEqual(len(out["offsets"]), 12)
        self.assertEqual(out["stride"], 12)


if __name__ == "__main__":
    unittest.main()
