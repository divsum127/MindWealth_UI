"""Regression tests for the SSI display-rounding policy.

Rule (per 2026-07-23 bug report on SKEW/McClellan/NH-NL showing raw floats
with 12+ decimals): every indicator (oscillators, ratios, betas, spreads,
breadth %, CFTC net positions) rounds to 2 decimals at display time. 4
decimals is reserved for actual currency pairs (e.g. USDCNH) - none of the
current SSI inputs are FX, so today every field rounds to 2dp.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.sentiment_superindex.engine.positioning import (
    _display_decimals,
    _round_display,
)


def _flat_series(value: float, days: int = 400) -> pd.Series:
    idx = pd.bdate_range("2020-01-01", periods=days)
    return pd.Series([value] * days, index=idx, dtype=float)


class TestRoundDisplayHelper(unittest.TestCase):
    def test_default_rounds_to_two_decimals(self):
        self.assertEqual(_round_display(147.27999877929688), 147.28)
        self.assertEqual(_round_display(217.09514599086106), 217.1)
        self.assertEqual(_round_display(0.9787234042553191), 0.98)
        self.assertEqual(_round_display(0.7423256097837936, key="hyg_lqd"), 0.74)
        self.assertEqual(_round_display(1.165570862734967, key="vix_ratio"), 1.17)
        self.assertEqual(_round_display(0.5566, key="dbmf_beta"), 0.56)

    def test_none_passes_through(self):
        self.assertIsNone(_round_display(None))
        self.assertIsNone(_round_display(None, key="skew"))

    def test_currency_pair_key_gets_four_decimals(self):
        """Future-proofing: if an FX series (e.g. usdcnh) is ever added, it
        should keep 4dp instead of silently defaulting to 2dp."""
        self.assertEqual(_display_decimals("usdcnh"), 4)
        self.assertEqual(_display_decimals("USDCNH"), 4)
        self.assertEqual(_round_display(6.912345, key="usdcnh"), 6.9123)

    def test_non_currency_keys_get_two_decimals(self):
        for key in ("skew", "mcclellan", "nh_nl_ratio", "hyg_lqd", "vix_ratio", "dbmf_beta", "cftc_fm_net"):
            self.assertEqual(_display_decimals(key), 2, f"{key} should round to 2dp, not a currency pair")

    def test_explicit_decimals_override_wins(self):
        self.assertEqual(_round_display(1.23456, decimals=3), 1.235)


class TestPositioningPayloadRounding(unittest.TestCase):
    @patch("src.sentiment_superindex.engine.positioning.values_as_of")
    @patch("src.sentiment_superindex.engine.positioning.load_all_series")
    @patch("src.sentiment_superindex.engine.positioning.layer3_for_date")
    @patch("src.sentiment_superindex.engine.positioning.evaluate_layer2")
    @patch("src.sentiment_superindex.engine.positioning.compute_ssi_at_date")
    @patch("src.sentiment_superindex.engine.positioning.build_superindex")
    def test_no_field_leaks_more_than_two_decimals(
        self, mock_build_si, mock_compute, mock_layer2, mock_layer3, mock_load_all, mock_values_as_of
    ):
        from src.sentiment_superindex.engine.positioning import build_positioning_payload

        mock_build_si.return_value = {
            "ssi_level": 0.2173,
            "layers": {
                "layer1": {"score": 0.58, "weight": 0.4, "components": {}},
                "layer2": {
                    "score": -0.04,
                    "weight": 0.35,
                    "components": {
                        "hyg_lqd": {"raw": 0.7423256097837936, "norm": 0.1},
                        "vix_ratio": {"raw": 1.165570862734967, "norm": -0.2},
                    },
                },
                "layer3": {
                    "score": -0.006,
                    "weight": 0.25,
                    "components": {"dbmf_beta": {"raw": 0.5566123456, "norm": 0.05}},
                },
            },
        }
        mock_compute.return_value = (0.2173, 55.0, {})
        mock_layer2.return_value = ("CONFIRMED", 3, [], 1.2)
        mock_layer3.return_value = {}
        mock_load_all.return_value = {}
        mock_values_as_of.return_value = {
            "mcclellan": 217.09514599086106,
            "nh_nl_ratio": 0.9787234042553191,
            "hyg_lqd": 0.7423256097837936,
            "skew": 147.27999877929688,
            "vix_ratio": 1.165570862734967,
            "aaii_spread": 12.041234,
            "naaim_exposure": 95.635912,
            "cnn_fg": 43.234567,
            "pct_above_200dma": 66.071234,
        }

        payload = build_positioning_payload("2026-07-16")
        layer2_display = payload["inputs"]["layer2"]
        layer1_display = payload["inputs"]["layer1"]

        for key, value in {**layer1_display, **layer2_display}.items():
            if value is None:
                continue
            decimals = len(str(value).split(".")[-1]) if "." in str(value) else 0
            self.assertLessEqual(decimals, 2, f"{key}={value} has more than 2 decimal places")

        self.assertEqual(layer2_display["mcclellan"], 217.1)
        self.assertEqual(layer2_display["nh_nl_ratio"], 0.98)
        self.assertEqual(layer2_display["skew"], 147.28)
        self.assertEqual(layer2_display["pct_above_200dma"], 66.07)
        self.assertNotIn("pct_above_200dma", layer1_display)

    @patch("src.sentiment_superindex.engine.positioning.values_as_of")
    @patch("src.sentiment_superindex.engine.positioning.load_all_series")
    @patch("src.sentiment_superindex.engine.positioning.layer3_for_date")
    @patch("src.sentiment_superindex.engine.positioning.evaluate_layer2")
    @patch("src.sentiment_superindex.engine.positioning.compute_ssi_at_date")
    @patch("src.sentiment_superindex.engine.positioning.build_superindex")
    def test_layer1_inputs_meta_includes_aaii_weekly_as_of(
        self, mock_build_si, mock_compute, mock_layer2, mock_layer3, mock_load_all, mock_values_as_of
    ):
        from src.sentiment_superindex.engine.positioning import build_positioning_payload

        mock_build_si.return_value = {"ssi_level": 0.1, "layers": {}}
        mock_compute.return_value = (0.1, 50.0, {})
        mock_layer2.return_value = ("UNCONFIRMED", 0, [], 1.0)
        mock_layer3.return_value = {}
        idx = pd.to_datetime(["2026-07-23", "2026-07-30"])
        mock_load_all.return_value = {
            "aaii_spread": pd.Series([-12.75, -11.11], index=idx),
            "naaim_exposure": pd.Series([90.0, 91.0], index=idx),
            "cnn_fg": pd.Series([40.0, 41.0], index=idx),
            "pct_above_200dma": pd.Series([60.0, 61.0], index=idx),
        }
        mock_values_as_of.return_value = {
            "aaii_spread": -11.11,
            "naaim_exposure": 91.0,
            "cnn_fg": 41.0,
            "pct_above_200dma": 61.0,
        }

        payload = build_positioning_payload("2026-08-02")
        aaii_meta = payload["inputs_meta"]["layer1"]["aaii_spread"]
        self.assertEqual(aaii_meta["cadence"], "weekly")
        self.assertEqual(aaii_meta["as_of"], "2026-07-30")
        self.assertEqual(aaii_meta["schedule_et"], "Thu")
        self.assertEqual(aaii_meta["stale_days"], 3)


if __name__ == "__main__":
    unittest.main()
