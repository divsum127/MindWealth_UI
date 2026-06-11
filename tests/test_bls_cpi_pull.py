"""BLS CPI ingest and not-hot cancel leg."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.data.bls_pull import cpi_not_hot_for_week, ingest_cpi_release
from src.macro_intelligence.db.connection import init_db


class TestBlsCpiPull(unittest.TestCase):
    def setUp(self) -> None:
        init_db()

    def test_cpi_not_hot_when_actual_below_consensus(self) -> None:
        ingest_cpi_release("2024-01-10", 0.2, 0.3)
        self.assertTrue(cpi_not_hot_for_week("2024-01-10"))

    def test_cpi_hot_when_above_consensus(self) -> None:
        ingest_cpi_release("2024-02-10", 0.4, 0.2)
        self.assertFalse(cpi_not_hot_for_week("2024-02-10"))

    def test_no_release_passes(self) -> None:
        self.assertTrue(cpi_not_hot_for_week(None))


if __name__ == "__main__":
    unittest.main()
