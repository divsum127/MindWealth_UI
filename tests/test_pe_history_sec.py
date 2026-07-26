"""Tests for the SEC EDGAR PE-history fallback module (pe_history_sec.py).

All SEC HTTP calls are mocked — no real network access is exercised here. (A live,
manual smoke test against the real data.sec.gov API was run separately during
development and is documented in the job-status docs, not part of the automated suite.)
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.conviction_engine.pe_history_sec import (
    _dedupe_first_filed,
    _plug_quarterly_series,
    build_quarterly_eps_series,
    fetch_pe_history_sec,
    get_cik_for_ticker,
)


def _fact(start: str, end: str, val: float, *, form: str = "10-Q", filed: str = "2020-01-01", fy: int = 2020) -> dict:
    return {"start": start, "end": end, "val": val, "form": form, "filed": filed, "fy": fy, "accn": "0001-20-000001"}


class TestDedupeFirstFiled(unittest.TestCase):
    def test_keeps_earliest_filed_per_period(self):
        facts = [
            _fact("2019-01-01", "2019-03-31", 1.0, filed="2019-05-01"),
            _fact("2019-01-01", "2019-03-31", 1.05, filed="2019-04-15"),  # earlier filing wins
            _fact("2019-04-01", "2019-06-30", 1.1, filed="2019-08-01"),
        ]
        result = _dedupe_first_filed(facts)
        by_end = {f["end"]: f["val"] for f in result}
        self.assertEqual(by_end["2019-03-31"], 1.05)
        self.assertEqual(by_end["2019-06-30"], 1.1)

    def test_skips_facts_missing_period(self):
        facts = [{"val": 1.0, "form": "10-Q", "filed": "2020-01-01"}]
        self.assertEqual(_dedupe_first_filed(facts), [])


class TestPlugQuarterlySeries(unittest.TestCase):
    def test_q4_plugged_from_three_quarters_and_annual(self):
        facts = [
            _fact("2019-01-01", "2019-03-31", 1.0),
            _fact("2019-04-01", "2019-06-30", 1.1),
            _fact("2019-07-01", "2019-09-30", 1.2),
            _fact("2019-01-01", "2019-12-31", 4.6, form="10-K"),
        ]
        result = _plug_quarterly_series(facts)
        self.assertAlmostEqual(result["2019-03-31"], 1.0)
        self.assertAlmostEqual(result["2019-06-30"], 1.1)
        self.assertAlmostEqual(result["2019-09-30"], 1.2)
        self.assertAlmostEqual(result["2019-12-31"], 4.6 - (1.0 + 1.1 + 1.2), places=6)

    def test_two_fiscal_years_both_plugged(self):
        facts = [
            _fact("2019-01-01", "2019-03-31", 1.0),
            _fact("2019-04-01", "2019-06-30", 1.1),
            _fact("2019-07-01", "2019-09-30", 1.2),
            _fact("2019-01-01", "2019-12-31", 4.6, form="10-K"),
            _fact("2020-01-01", "2020-03-31", 1.4),
            _fact("2020-04-01", "2020-06-30", 1.5),
            _fact("2020-07-01", "2020-09-30", 1.6),
            _fact("2020-01-01", "2020-12-31", 6.4, form="10-K"),
        ]
        result = _plug_quarterly_series(facts)
        self.assertEqual(len(result), 8)  # 2 years x 4 quarters
        self.assertAlmostEqual(result["2019-12-31"], 1.3, places=6)
        self.assertAlmostEqual(result["2020-12-31"], 1.9, places=6)

    def test_gap_left_when_fewer_than_three_quarters_found(self):
        """Only 2 of 3 quarters present for the FY -> Q4 can't be reliably plugged;
        leaves a gap rather than guessing (safe: fewer usable TTM points, not corrupt)."""
        facts = [
            _fact("2019-01-01", "2019-03-31", 1.0),
            _fact("2019-04-01", "2019-06-30", 1.1),
            # Q3 missing
            _fact("2019-01-01", "2019-12-31", 4.6, form="10-K"),
        ]
        result = _plug_quarterly_series(facts)
        self.assertIn("2019-03-31", result)
        self.assertIn("2019-06-30", result)
        self.assertNotIn("2019-12-31", result)

    def test_ignores_out_of_range_durations(self):
        facts = [
            _fact("2019-01-01", "2019-02-15", 0.5),  # ~45 days, not a quarter
            _fact("2019-01-01", "2019-06-30", 2.0),  # ~180 days, half-year, not annual
        ]
        result = _plug_quarterly_series(facts)
        self.assertEqual(result, {})


class TestBuildQuarterlyEpsSeries(unittest.TestCase):
    def test_filters_non_periodic_forms(self):
        facts = [
            _fact("2019-01-01", "2019-03-31", 1.0, form="10-Q"),
            _fact("2019-04-01", "2019-06-30", 99.0, form="8-K"),  # excluded
        ]
        series = build_quarterly_eps_series(facts)
        self.assertEqual(len(series), 1)
        self.assertAlmostEqual(series.iloc[0], 1.0)

    def test_empty_facts_returns_empty_series(self):
        series = build_quarterly_eps_series([])
        self.assertTrue(series.empty)

    def test_full_reconstruction_sorted_by_date(self):
        facts = [
            _fact("2019-07-01", "2019-09-30", 1.2),
            _fact("2019-01-01", "2019-03-31", 1.0),
            _fact("2019-04-01", "2019-06-30", 1.1),
            _fact("2019-01-01", "2019-12-31", 4.6, form="10-K"),
        ]
        series = build_quarterly_eps_series(facts)
        self.assertEqual(len(series), 4)
        self.assertTrue(series.index.is_monotonic_increasing)


class TestGetCikForTicker(unittest.TestCase):
    def test_resolves_and_caches(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
                "1": {"cik_str": 1633917, "ticker": "PYPL", "title": "PayPal Holdings"},
            }
            with patch("src.conviction_engine.pe_history_sec.requests.get", return_value=mock_resp) as mock_get:
                cik = get_cik_for_ticker("PYPL", cache_dir=cache_dir)
            self.assertEqual(cik, "0001633917")
            self.assertEqual(mock_get.call_count, 1)

            # second call hits the on-disk cache, no network
            with patch("src.conviction_engine.pe_history_sec.requests.get") as mock_get2:
                cik2 = get_cik_for_ticker("AAPL", cache_dir=cache_dir)
            mock_get2.assert_not_called()
            self.assertEqual(cik2, "0000320193")

    def test_unknown_ticker_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
            with patch("src.conviction_engine.pe_history_sec.requests.get", return_value=mock_resp):
                cik = get_cik_for_ticker("NOPE", cache_dir=Path(tmp))
            self.assertIsNone(cik)

    def test_network_failure_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("src.conviction_engine.pe_history_sec.requests.get", side_effect=ConnectionError("boom")):
                cik = get_cik_for_ticker("AAPL", cache_dir=Path(tmp))
            self.assertIsNone(cik)


def _price_series() -> pd.Series:
    dates = pd.date_range("2019-01-31", "2020-12-31", freq="ME")
    return pd.Series([10.0 + 0.5 * i for i in range(len(dates))], index=dates)


class TestFetchPeHistorySec(unittest.TestCase):
    def test_non_us_ticker_returns_none_without_network(self):
        with patch("src.conviction_engine.pe_history_sec.requests.get") as mock_get:
            result = fetch_pe_history_sec("SHOP.TO", _price_series())
        self.assertIsNone(result)
        mock_get.assert_not_called()

    def test_empty_price_series_returns_none(self):
        result = fetch_pe_history_sec("PYPL", pd.Series(dtype=float), cik="0001633917")
        self.assertIsNone(result)

    def test_none_price_series_returns_none(self):
        result = fetch_pe_history_sec("PYPL", None, cik="0001633917")
        self.assertIsNone(result)

    def test_no_cik_found_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("src.conviction_engine.pe_history_sec.get_cik_for_ticker", return_value=None):
                result = fetch_pe_history_sec("ZZZZ", _price_series(), cache_dir=Path(tmp))
            self.assertIsNone(result)

    def test_successful_fetch_builds_bundle_and_caches(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            facts_resp = MagicMock()
            facts_resp.status_code = 200
            facts_resp.json.return_value = {
                "units": {
                    "USD/shares": [
                        _fact("2019-01-01", "2019-03-31", 1.0),
                        _fact("2019-04-01", "2019-06-30", 1.1),
                        _fact("2019-07-01", "2019-09-30", 1.2),
                        _fact("2019-01-01", "2019-12-31", 4.6, form="10-K"),
                        _fact("2020-01-01", "2020-03-31", 1.4),
                        _fact("2020-04-01", "2020-06-30", 1.5),
                        _fact("2020-07-01", "2020-09-30", 1.6),
                        _fact("2020-01-01", "2020-12-31", 6.4, form="10-K"),
                    ]
                }
            }
            with patch("src.conviction_engine.pe_history_sec.requests.get", return_value=facts_resp) as mock_get:
                bundle = fetch_pe_history_sec("PYPL", _price_series(), cache_dir=cache_dir, cik="0001633917")
            self.assertIsNotNone(bundle)
            self.assertEqual(bundle["meta"]["source"], "sec_edgar")
            self.assertGreaterEqual(mock_get.call_count, 1)
            self.assertTrue((cache_dir / "PYPL_sec.json").exists())

            # second call hits cache, no network
            with patch("src.conviction_engine.pe_history_sec.requests.get") as mock_get2:
                bundle2 = fetch_pe_history_sec("PYPL", _price_series(), cache_dir=cache_dir, cik="0001633917")
            mock_get2.assert_not_called()
            self.assertEqual(bundle2["values"], bundle["values"])

    def test_falls_back_to_basic_eps_when_diluted_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            diluted_resp = MagicMock()
            diluted_resp.status_code = 404
            basic_resp = MagicMock()
            basic_resp.status_code = 200
            basic_resp.json.return_value = {
                "units": {
                    "USD/shares": [
                        _fact("2019-01-01", "2019-03-31", 1.0),
                        _fact("2019-04-01", "2019-06-30", 1.1),
                        _fact("2019-07-01", "2019-09-30", 1.2),
                        _fact("2019-01-01", "2019-12-31", 4.6, form="10-K"),
                    ]
                }
            }
            with patch(
                "src.conviction_engine.pe_history_sec.requests.get",
                side_effect=[diluted_resp, basic_resp],
            ):
                bundle = fetch_pe_history_sec("PYPL", _price_series(), cache_dir=Path(tmp), cik="0001633917")
            self.assertIsNotNone(bundle)

    def test_no_facts_at_all_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            not_found = MagicMock()
            not_found.status_code = 404
            with patch("src.conviction_engine.pe_history_sec.requests.get", return_value=not_found):
                bundle = fetch_pe_history_sec("PYPL", _price_series(), cache_dir=Path(tmp), cik="0001633917")
            self.assertIsNone(bundle)

    def test_malformed_json_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad_resp = MagicMock()
            bad_resp.status_code = 200
            bad_resp.json.side_effect = ValueError("bad json")
            with patch("src.conviction_engine.pe_history_sec.requests.get", return_value=bad_resp):
                bundle = fetch_pe_history_sec("PYPL", _price_series(), cache_dir=Path(tmp), cik="0001633917")
            self.assertIsNone(bundle)


if __name__ == "__main__":
    unittest.main()
