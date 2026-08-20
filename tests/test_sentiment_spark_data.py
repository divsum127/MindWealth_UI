"""Spark data helper for sentiment layers API."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from api.services.reports_service import _build_spark_data


class TestSentimentSparkData(unittest.TestCase):
    def test_build_spark_data_empty_when_no_db(self) -> None:
        with patch("src.config_paths.SSI_DB") as mock_path:
            mock_path.exists.return_value = False
            out = _build_spark_data(days=10)
        self.assertEqual(out["days_available"], 0)
        self.assertEqual(out["layer1"], [])


if __name__ == "__main__":
    unittest.main()
