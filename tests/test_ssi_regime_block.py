"""Tests for Layer 4 regime block in positioning.json."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from src.sentiment_superindex.engine.regime_block import build_regime_block


class TestRegimeBlock(unittest.TestCase):
    def test_build_regime_block_shape(self) -> None:
        with patch(
            "src.sentiment_superindex.engine.regime_block._var_map_from_runic",
            return_value={
                "VIX": {"pctile_3yr": 25.0},
                "HY": {"current": 2.5},
            },
        ), patch(
            "src.sentiment_superindex.engine.regime_block._trend_regime_label",
            return_value=("ABOVE_MA200", {"above_ma200": True}),
        ):
            block = build_regime_block(1.2)
        self.assertEqual(block["vix_regime"], "LOW_VOL")
        self.assertEqual(block["trend_regime"], "ABOVE_MA200")
        self.assertEqual(block["credit_regime"], "BENIGN")
        self.assertEqual(block["size_mult"], 1.2)


if __name__ == "__main__":
    unittest.main()
