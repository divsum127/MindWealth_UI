"""Tests for degradation cache performance."""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.services import degradation_cache as cache
from api.services import degradation_service as ds
from tests.api_test_helpers import disable_rate_limits


class TestDegradationCache(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        disable_rate_limits()

    def test_cached_read_under_one_second(self) -> None:
        ds.warm_degradation_cache()
        start = time.perf_counter()
        result = ds.check_degradation()
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 1.0, f"cached check_degradation took {elapsed:.2f}s")
        self.assertIn("alert_count", result)

    def test_manifest_roundtrip(self) -> None:
        m1 = cache.scan_fwd_manifest()
        self.assertIn("csv_count", m1)
        self.assertGreater(m1["csv_count"], 0)


class TestIntegrationHealthStore(unittest.TestCase):
    def test_tavily_marker_roundtrip(self) -> None:
        from api.services import integration_health_store as ihs

        with patch.object(ihs, "TAVILY_MARKER", Path("/tmp/test_tavily_marker.json")):
            ihs.record_tavily_search(latency_ms=120, success=True, query="SPX")
            info = ihs.tavily_health_info()
            self.assertEqual(info["name"], "Tavily")
            self.assertEqual(info["status"], "ok")


if __name__ == "__main__":
    unittest.main()
