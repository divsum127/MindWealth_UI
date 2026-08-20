"""Regression: sentiment/layers must expose all six Layer-2 gate votes."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi.testclient import TestClient

from api.main import app
from api.services.reports_service import _ensure_layer2_gate_votes, sentiment_layers
from tests.api_test_helpers import disable_rate_limits


class TestSentimentLayersGateVotes(unittest.TestCase):
    def test_backfills_gate_votes_from_layer2_components(self) -> None:
        inputs = {
            "layer2_votes": [
                {"input": "hyg_lqd", "raw": 0.75, "vote": True, "signal": "risk_on"},
                {"input": "vix_ratio", "raw": 1.09, "vote": True, "signal": "stress"},
            ],
            "layer2_components": {
                "mcclellan": {"raw": -12.0, "norm": -0.6},
                "nh_nl_ratio": {"raw": 0.73, "norm": -0.1},
                "hyg_lqd": {"raw": 0.75, "norm": 1.2},
                "skew": {"raw": 150.0, "norm": -0.8},
                "vix_ratio": {"raw": 1.09, "norm": -0.2},
                "pct_above_200dma": {"raw": 66.0, "norm": 0.3},
            },
        }
        out = _ensure_layer2_gate_votes(inputs)
        gate_inputs = [g["input"] for g in out["layer2_gate_votes"]]
        self.assertEqual(
            gate_inputs,
            [
                "mcclellan",
                "nh_nl_ratio",
                "hyg_lqd",
                "skew",
                "vix_ratio",
                "pct_above_200dma",
            ],
        )
        nh_nl = next(g for g in out["layer2_gate_votes"] if g["input"] == "nh_nl_ratio")
        self.assertIn("vote", nh_nl)
        self.assertIn("signal", nh_nl)
        self.assertIsInstance(out["layer2_gate_confirmed_count"], int)
        self.assertEqual(out["layer2_gate_conf_long"], 1)
        self.assertEqual(out["layer2_gate_conf_short"], 3)
        self.assertEqual(out["layer2_gate_direction"], "SHORT_CONFIRMED")
        self.assertIn("1 long / 3 short of 6", out["layer2_gate_label"])

    def test_enriches_existing_gate_votes_with_directional_counts(self) -> None:
        existing = [{"input": "nh_nl_ratio", "vote": False, "signal": "neutral"}]
        inputs = {"layer2_gate_votes": existing, "layer2_components": {"nh_nl_ratio": {"norm": 0.1}}}
        out = _ensure_layer2_gate_votes(inputs)
        self.assertEqual(len(out["layer2_gate_votes"]), 6)
        self.assertEqual(out["layer2_gate_conf_long"], 0)
        self.assertEqual(out["layer2_gate_conf_short"], 0)
        self.assertEqual(out["layer2_gate_direction"], "UNCONFIRMED")
        self.assertIn("no direction confirmed", out["layer2_gate_label"])

    def test_sentiment_layers_includes_skew_gate_vote(self) -> None:
        """Live/stale positioning.json must still expose skew in layer2_gate_votes."""
        body = sentiment_layers()
        gate_votes = body.get("layer2_gate_votes") or (body.get("layer_inputs") or {}).get(
            "layer2_gate_votes", []
        )
        inputs = [v.get("input") for v in gate_votes]
        self.assertIn("skew", inputs)
        skew = next(v for v in gate_votes if v.get("input") == "skew")
        self.assertIn("vote", skew)
        self.assertIn("signal", skew)
        self.assertIsInstance(body.get("layer2_gate_confirmed_count"), int)
        self.assertIsNotNone(body.get("layer2_gate_label"))
        self.assertIn(body.get("layer2_gate_direction"), {
            "LONG_CONFIRMED",
            "SHORT_CONFIRMED",
            "CONTESTED",
            "UNCONFIRMED",
        })


class TestSentimentLayersHTTP(unittest.TestCase):
    def setUp(self) -> None:
        disable_rate_limits()
        self.client = TestClient(app)
        self._api_patch = patch.dict("os.environ", {"API_KEY": ""}, clear=False)
        self._key_patch = patch("api.dependencies.API_KEY", "")
        self._api_patch.start()
        self._key_patch.start()

    def tearDown(self) -> None:
        self._key_patch.stop()
        self._api_patch.stop()

    def test_http_sentiment_layers_gate_votes(self) -> None:
        r = self.client.get("/api/v1/analytics/sentiment/layers")
        self.assertEqual(r.status_code, 200, r.text[:500])
        body = r.json()
        gate_votes = body.get("layer2_gate_votes") or (body.get("layer_inputs") or {}).get(
            "layer2_gate_votes", []
        )
        self.assertEqual(len(gate_votes), 6, [v.get("input") for v in gate_votes])
        inputs = [v.get("input") for v in gate_votes]
        self.assertIn("skew", inputs)
        self.assertIn("mcclellan", inputs)
        skew = next(v for v in gate_votes if v.get("input") == "skew")
        self.assertIn("vote", skew)
        self.assertIn("signal", skew)
        self.assertIsInstance(body.get("layer2_gate_confirmed_count"), int)
        self.assertIsNotNone(body.get("layer2_gate_label"))
        self.assertIn(body.get("layer2_gate_direction"), {
            "LONG_CONFIRMED",
            "SHORT_CONFIRMED",
            "CONTESTED",
            "UNCONFIRMED",
        })


if __name__ == "__main__":
    unittest.main()
