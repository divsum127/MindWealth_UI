"""Positioning payload CFTC meta tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.sentiment_superindex.engine.layer2 import Layer2GateSummary


class TestPositioningCftcMeta(unittest.TestCase):
    @patch("src.sentiment_superindex.engine.positioning.derive_layer2_sizing")
    @patch("src.sentiment_superindex.engine.positioning.evaluate_layer2_gates")
    @patch("src.sentiment_superindex.engine.positioning.hyg_vix_legacy_votes")
    @patch("src.sentiment_superindex.engine.positioning.values_as_of")
    @patch("src.sentiment_superindex.engine.positioning.load_all_series")
    @patch("src.sentiment_superindex.engine.positioning.layer3_for_date")
    @patch("src.sentiment_superindex.engine.positioning.compute_ssi_at_date")
    @patch("src.sentiment_superindex.engine.positioning.build_superindex")
    def test_layer3_cftc_meta_fields(
        self,
        mock_build_si,
        mock_compute,
        mock_layer3,
        mock_load_all,
        mock_values_as_of,
        mock_hyg_vix,
        mock_gates,
        mock_sizing,
    ):
        from src.sentiment_superindex.engine.positioning import build_positioning_payload

        mock_build_si.return_value = {"ssi_level": 0.1, "layers": {}}
        mock_compute.return_value = (0.1, 50.0, {})
        mock_hyg_vix.return_value = []
        mock_gates.return_value = Layer2GateSummary(
            confirmed_count=0,
            conf_long=0,
            conf_short=0,
            gate_total=6,
            direction="UNCONFIRMED",
            label="test",
            votes=[],
        )
        mock_sizing.return_value = ("UNCONFIRMED", 0, 0.8)
        mock_layer3.return_value = {
            "position_date": "2026-07-29",
            "expected_release": "2026-07-29",
            "next_release": "2026-08-01",
            "data_freshness": "waiting_for_friday_release",
            "stale": True,
            "positioning_pattern": None,
            "pattern_label": "None",
        }
        mock_load_all.return_value = {}
        mock_values_as_of.return_value = {}

        payload = build_positioning_payload("2026-08-04")
        meta = payload["inputs_meta"]["layer3_cftc"]
        self.assertEqual(meta["position_date"], "2026-07-29")
        self.assertEqual(meta["data_freshness"], "waiting_for_friday_release")
        self.assertTrue(meta["stale"])
        self.assertEqual(meta["stale_days"], 6)
        self.assertEqual(meta["max_stale_days"], 8)
        self.assertEqual(meta["release_date"], "2026-08-01")


if __name__ == "__main__":
    unittest.main()
