"""SSI 3-layer superindex tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.sentiment_superindex.engine.superindex import (
    build_layer1,
    build_layer2,
    build_layer3,
    build_superindex,
)


def _flat_series(value: float, days: int = 400) -> pd.Series:
    idx = pd.bdate_range("2020-01-01", periods=days)
    return pd.Series([value] * days, index=idx, dtype=float)


class TestSSISuperindex(unittest.TestCase):
    @patch("src.sentiment_superindex.engine.superindex.load_all_series")
    def test_superindex_equals_weighted_layer_scores(self, mock_load):
        mock_load.return_value = {
            "aaii_spread": _flat_series(10.0),
            "naaim_exposure": _flat_series(80.0),
            "cnn_fg": _flat_series(50.0),
            "pct_above_200dma": _flat_series(55.0),
            "mcclellan": _flat_series(5.0),
            "nh_nl_ratio": _flat_series(0.6),
            "hyg_lqd": _flat_series(0.72),
            "skew": _flat_series(130.0),
            "vix_ratio": _flat_series(1.0),
            "dbmf_beta": _flat_series(0.4),
            "cftc_fm_net": _flat_series(100_000.0),
            "cftc_rm_net": _flat_series(200_000.0),
            "gross_net": _flat_series(300_000.0),
        }

        result = build_superindex("2021-06-01")
        layers = result["layers"]
        expected = (
            0.40 * layers["layer1"]["score"]
            + 0.35 * layers["layer2"]["score"]
            + 0.25 * layers["layer3"]["score"]
        )
        self.assertAlmostEqual(result["ssi_level"], expected, places=6)

    @patch("src.sentiment_superindex.engine.superindex.load_all_series")
    def test_layer_builders_return_zscore_components(self, mock_load):
        mock_load.return_value = {
            "aaii_spread": _flat_series(12.0),
            "naaim_exposure": _flat_series(75.0),
            "cnn_fg": _flat_series(40.0),
            "pct_above_200dma": _flat_series(60.0),
            "mcclellan": _flat_series(8.0),
            "nh_nl_ratio": _flat_series(0.7),
            "hyg_lqd": _flat_series(0.71),
            "skew": _flat_series(125.0),
            "vix_ratio": _flat_series(0.98),
            "dbmf_beta": _flat_series(0.35),
            "cftc_fm_net": _flat_series(90_000.0),
            "cftc_rm_net": _flat_series(180_000.0),
            "gross_net": _flat_series(270_000.0),
        }

        l1 = build_layer1("2021-06-01")
        self.assertIsNotNone(l1["score"])
        for comp in l1["components"].values():
            self.assertIn("norm", comp)
            self.assertIn("raw", comp)

    @patch("src.sentiment_superindex.engine.superindex.load_all_series")
    def test_composite_uses_norm_not_raw(self, mock_load):
        """Layer scores must come from normalized values, not raw inputs."""
        idx = pd.bdate_range("2020-01-01", periods=400)
        hyg = pd.Series(np.linspace(0.65, 0.80, len(idx)), index=idx)
        mock_load.return_value = {
            "aaii_spread": _flat_series(5.0),
            "naaim_exposure": _flat_series(70.0),
            "cnn_fg": _flat_series(45.0),
            "pct_above_200dma": _flat_series(50.0),
            "mcclellan": _flat_series(3.0),
            "nh_nl_ratio": _flat_series(0.55),
            "hyg_lqd": hyg,
            "skew": _flat_series(128.0),
            "vix_ratio": _flat_series(1.02),
            "dbmf_beta": _flat_series(0.5),
            "cftc_fm_net": _flat_series(80_000.0),
            "cftc_rm_net": _flat_series(160_000.0),
            "gross_net": _flat_series(240_000.0),
        }

        result = build_superindex("2021-06-01")
        hyg_norm = result["layers"]["layer2"]["components"]["hyg_lqd"]["norm"]
        hyg_raw = result["layers"]["layer2"]["components"]["hyg_lqd"]["raw"]
        self.assertNotAlmostEqual(hyg_norm, hyg_raw, places=2)


if __name__ == "__main__":
    unittest.main()
