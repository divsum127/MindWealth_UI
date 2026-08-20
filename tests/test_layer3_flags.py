"""Layer 3 CFTC flag enrichment for sentiment/layers API."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.services.reports_service import _layer3_flags, sentiment_layers


class TestLayer3Flags(unittest.TestCase):
    def test_layer3_flags_liquidity_exit(self):
        flags = _layer3_flags({
            "fm_pctile": 93.0,
            "rm_pctile": 28.0,
            "squeeze_setup": False,
            "liquidity_exit": True,
            "positioning_pattern": "liquidity_exit",
            "pattern_label": "Liquidity Exit",
            "plain_english": "Real money exiting; fast money still crowded long",
        })
        self.assertTrue(flags["liquidity_exit"])
        self.assertFalse(flags["squeeze_setup"])
        self.assertEqual(flags["positioning_pattern"], "liquidity_exit")

    @patch("api.services.reports_service.load_positioning")
    @patch("api.services.reports_service.latest_sentiment_signals")
    def test_sentiment_layers_exposes_layer3_flags(self, mock_signals, mock_pos):
        mock_signals.return_value = {"records": [], "report_date": "2026-08-07"}
        mock_pos.return_value = {
            "ssi_level": 0.4,
            "layers": {},
            "inputs": {
                "layer3_cftc": {
                    "fm_pctile": 93.0,
                    "rm_pctile": 28.0,
                    "squeeze_setup": False,
                    "liquidity_exit": True,
                    "positioning_pattern": "liquidity_exit",
                    "pattern_label": "Liquidity Exit",
                },
            },
        }
        out = sentiment_layers()
        self.assertTrue(out["layer3_flags"]["liquidity_exit"])
        self.assertEqual(out["layer3_flags"]["fm_pctile"], 93.0)


if __name__ == "__main__":
    unittest.main()
