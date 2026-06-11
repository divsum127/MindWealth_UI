"""SSI positioning.json schema and atomic write."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.sentiment_superindex.output.json_writer import read_positioning_json, write_positioning_json


class TestSSIPositioningJson(unittest.TestCase):
    def test_write_and_read_schema_keys(self):
        payload = {
            "date": "2026-05-27",
            "ssi_level": -0.42,
            "ssi_percentile_5y": 18.2,
            "layer2_status": "CONFIRMED",
            "layer2_confirmed_count": 3,
            "ssi_multiplier": 1.2,
            "signals": {
                "long": {"size_mult": 1.2, "entry_threshold": -0.6, "active": True},
                "short": {"size_mult": 0.8, "entry_threshold": 0.85, "active": False},
            },
            "inputs": {"layer2_votes": []},
            "validation": {},
        }
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "positioning.json"
            write_positioning_json(payload, path)
            self.assertTrue(path.exists())
            data = read_positioning_json(path)
            assert data is not None
            self.assertIn("signals", data)
            self.assertEqual(data["signals"]["long"]["size_mult"], 1.2)
            raw = path.read_text(encoding="utf-8")
            self.assertNotIn(".tmp", raw)


if __name__ == "__main__":
    unittest.main()
