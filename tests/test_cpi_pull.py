"""CPI surprise validation and ingest."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.data import cpi_pull


class TestCPIPull(unittest.TestCase):
    def test_ingest_and_validate(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "cpi_surprises.csv"
            cpi_pull.CPI_CACHE = path
            surprise = cpi_pull.ingest_release("2024-01-11", actual=3.4, consensus=3.1)
            self.assertAlmostEqual(surprise, 0.3)
            ok, msg = cpi_pull.validate_cpi_csv(path)
            self.assertTrue(ok, msg)
            s = cpi_pull.load_cpi_surprises()
            self.assertFalse(s.empty)


if __name__ == "__main__":
    unittest.main()
