"""Tests for the FMP PE-history fallback module.

All FMP HTTP calls are mocked — no real network access is exercised here.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.conviction_engine.pe_history_fmp import (
    fetch_pe_history_fmp,
    is_us_ticker,
    _parse_fmp_ratios_response,
)


class TestIsUsTicker(unittest.TestCase):
    def test_bare_ticker_is_us(self):
        self.assertTrue(is_us_ticker("PYPL"))
        self.assertTrue(is_us_ticker("AAPL"))

    def test_non_us_suffixes(self):
        for suffix in (".TO", ".NS", ".NZ", ".HK", ".KS", ".SI", ".PA", ".F"):
            ticker = f"XYZ{suffix}"
            self.assertFalse(is_us_ticker(ticker), f"expected {ticker} to be non-US")

    def test_empty_ticker(self):
        self.assertFalse(is_us_ticker(""))
        self.assertFalse(is_us_ticker(None))  # type: ignore[arg-type]

    def test_case_insensitive(self):
        self.assertFalse(is_us_ticker("shop.to"))


class TestFetchPeHistoryFmpNoKey(unittest.TestCase):
    def test_returns_none_and_never_calls_network_when_key_unset(self):
        with patch("src.conviction_engine.pe_history_fmp.requests.get") as mock_get:
            result = fetch_pe_history_fmp("PYPL", api_key=None)
        self.assertIsNone(result)
        mock_get.assert_not_called()

    def test_returns_none_for_non_us_ticker_even_with_key(self):
        with patch("src.conviction_engine.pe_history_fmp.requests.get") as mock_get:
            result = fetch_pe_history_fmp("SHOP.TO", api_key="fake-key")
        self.assertIsNone(result)
        mock_get.assert_not_called()


_SAMPLE_ROWS = [
    {"symbol": "PYPL", "date": "2021-03-31", "period": "Q1", "priceToEarningsRatio": 45.2},
    {"symbol": "PYPL", "date": "2021-06-30", "period": "Q2", "priceToEarningsRatio": 40.1},
    {"symbol": "PYPL", "date": "2021-09-30", "period": "Q3", "priceToEarningsRatio": 38.7},
    {"symbol": "PYPL", "date": "2021-12-31", "period": "Q4", "priceToEarningsRatio": 35.0},
    {"symbol": "PYPL", "date": "2022-03-31", "period": "Q1", "priceToEarningsRatio": 20.4},
]


class TestParseFmpRatiosResponse(unittest.TestCase):
    def test_parses_realistic_response(self):
        bundle = _parse_fmp_ratios_response(_SAMPLE_ROWS, target_years=20)
        self.assertIsNotNone(bundle)
        self.assertEqual(bundle["meta"]["point_count"], 5)
        self.assertEqual(bundle["meta"]["source"], "fmp")
        self.assertEqual(bundle["meta"]["start_date"], "2021-03-31")
        self.assertEqual(bundle["meta"]["end_date"], "2022-03-31")
        self.assertTrue(bundle["meta"]["insufficient_20y"])  # only ~1 year of data
        self.assertAlmostEqual(bundle["values"][0], 45.2)
        self.assertAlmostEqual(bundle["values"][-1], 20.4)

    def test_alternate_field_name(self):
        rows = [{"date": "2020-01-01", "priceEarningsRatio": 15.0}, {"date": "2020-06-01", "peRatio": 16.0}]
        bundle = _parse_fmp_ratios_response(rows, target_years=20)
        self.assertIsNotNone(bundle)
        self.assertEqual(bundle["values"], [15.0, 16.0])

    def test_empty_rows_returns_none(self):
        self.assertIsNone(_parse_fmp_ratios_response([], target_years=20))

    def test_rows_with_no_usable_pe_returns_none(self):
        rows = [{"date": "2020-01-01"}, {"date": "2020-06-01", "priceToEarningsRatio": None}]
        self.assertIsNone(_parse_fmp_ratios_response(rows, target_years=20))

    def test_out_of_range_pe_filtered_out(self):
        rows = [{"date": "2020-01-01", "priceToEarningsRatio": 5000.0}, {"date": "2020-06-01", "priceToEarningsRatio": -1.0}]
        self.assertIsNone(_parse_fmp_ratios_response(rows, target_years=20))


class TestFetchPeHistoryFmpSuccess(unittest.TestCase):
    def test_mocked_success_parses_and_caches(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = _SAMPLE_ROWS
            with patch("src.conviction_engine.pe_history_fmp.requests.get", return_value=mock_resp) as mock_get:
                bundle = fetch_pe_history_fmp("PYPL", api_key="fake-key", cache_dir=cache_dir)
            self.assertIsNotNone(bundle)
            self.assertEqual(bundle["meta"]["source"], "fmp")
            self.assertEqual(mock_get.call_count, 1)
            self.assertTrue((cache_dir / "PYPL.json").exists())

            # Second call should hit the on-disk cache, not the network again.
            with patch("src.conviction_engine.pe_history_fmp.requests.get") as mock_get2:
                bundle2 = fetch_pe_history_fmp("PYPL", api_key="fake-key", cache_dir=cache_dir)
            mock_get2.assert_not_called()
            self.assertEqual(bundle2["values"], bundle["values"])

    def test_non_200_response_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            mock_resp = MagicMock()
            mock_resp.status_code = 403
            with patch("src.conviction_engine.pe_history_fmp.requests.get", return_value=mock_resp):
                bundle = fetch_pe_history_fmp("PYPL", api_key="fake-key", cache_dir=Path(tmp))
            self.assertIsNone(bundle)

    def test_malformed_json_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.side_effect = ValueError("bad json")
            with patch("src.conviction_engine.pe_history_fmp.requests.get", return_value=mock_resp):
                bundle = fetch_pe_history_fmp("PYPL", api_key="fake-key", cache_dir=Path(tmp))
            self.assertIsNone(bundle)

    def test_empty_list_response_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = []
            with patch("src.conviction_engine.pe_history_fmp.requests.get", return_value=mock_resp):
                bundle = fetch_pe_history_fmp("PYPL", api_key="fake-key", cache_dir=Path(tmp))
            self.assertIsNone(bundle)

    def test_network_exception_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("src.conviction_engine.pe_history_fmp.requests.get", side_effect=ConnectionError("boom")):
                bundle = fetch_pe_history_fmp("PYPL", api_key="fake-key", cache_dir=Path(tmp))
            self.assertIsNone(bundle)


def _make_raw(ticker: str, *, thin: bool) -> dict:
    """Build a minimal ``raw`` payload for build_fundamentals_from_raw with either a
    thin (~1y, insufficient_20y=True) or long (~22y, insufficient_20y=False) PE history.
    """
    import pandas as pd

    if thin:
        # 5 EPS quarters so the rolling 4Q TTM is valid from 2020-12-31 onward;
        # price dates all fall after that so every price point yields a PE value.
        quarter_ends = pd.to_datetime(
            ["2020-03-31", "2020-06-30", "2020-09-30", "2020-12-31", "2021-03-31"]
        )
        eps_values = [1.0, 1.0, 1.0, 1.0, 1.0]
        price_dates = pd.to_datetime(["2021-01-15", "2021-04-15", "2021-07-15", "2021-10-15"])
        price_values = [10.0, 20.0, 30.0, 40.0]
    else:
        quarter_ends = pd.date_range("2000-03-31", periods=92, freq="QE")
        eps_values = [1.0 + 0.01 * i for i in range(92)]
        price_dates = pd.date_range("2000-01-15", periods=92, freq="QE")
        price_values = [10.0 + 0.1 * i for i in range(92)]

    q_inc = pd.DataFrame([eps_values], index=["Diluted EPS"], columns=quarter_ends)
    price_hist = pd.Series(price_values, index=price_dates)
    return {
        "ticker": ticker,
        "info": {},
        "fast_info": {},
        "quarterly_income": q_inc,
        "quarterly_balance": None,
        "quarterly_cashflow": None,
        "price_history": price_hist,
        "dividends": None,
        "errors": [],
    }


class TestFundamentalsEnrichedWireIn(unittest.TestCase):
    """Confirm the SEC-EDGAR-first / FMP-fallback ordering (2026-07-24 pivot):
    - Neither is called unless insufficient_20y=True AND ticker is US-style.
    - SEC EDGAR is tried first; FMP is only tried when SEC returns None outright
      (not merely when SEC's result is itself still insufficient_20y).
    - The richer of (existing bundle, fetched bundle) always wins by point_count.
    """

    def test_sec_called_and_used_when_thin_and_us_fmp_never_called(self):
        from src.conviction_engine.fundamentals_enriched import build_fundamentals_from_raw

        rich_sec_bundle = {
            "values": [10.0] * 68,
            "meta": {
                "years_available": 17.0,
                "point_count": 68,
                "stored_point_count": 68,
                "insufficient_20y": True,
                "target_years": 20,
                "source": "sec_edgar",
                "start_date": "2009-01-01",
                "end_date": "2026-01-01",
            },
        }
        raw = _make_raw("PYPL", thin=True)
        with patch(
            "src.conviction_engine.fundamentals_enriched.fetch_pe_history_sec",
            return_value=rich_sec_bundle,
        ) as mock_sec, patch(
            "src.conviction_engine.fundamentals_enriched.fetch_pe_history_fmp"
        ) as mock_fmp:
            fundamentals = build_fundamentals_from_raw(raw)
        mock_sec.assert_called_once()
        mock_fmp.assert_not_called()  # SEC returned data (even if still <20y) -> FMP skipped
        self.assertEqual(fundamentals["pe_history_meta"]["source"], "sec_edgar")
        self.assertEqual(fundamentals["pe_20y_array"], rich_sec_bundle["values"])

    def test_fmp_called_only_when_sec_returns_none(self):
        from src.conviction_engine.fundamentals_enriched import build_fundamentals_from_raw

        rich_fmp_bundle = {
            "values": [10.0] * 25,
            "meta": {
                "years_available": 6.0,
                "point_count": 25,
                "stored_point_count": 25,
                "insufficient_20y": True,
                "target_years": 20,
                "source": "fmp",
                "start_date": "2018-01-01",
                "end_date": "2024-01-01",
            },
        }
        raw = _make_raw("PYPL", thin=True)
        with patch(
            "src.conviction_engine.fundamentals_enriched.fetch_pe_history_sec",
            return_value=None,
        ) as mock_sec, patch(
            "src.conviction_engine.fundamentals_enriched.fetch_pe_history_fmp",
            return_value=rich_fmp_bundle,
        ) as mock_fmp:
            fundamentals = build_fundamentals_from_raw(raw)
        mock_sec.assert_called_once()
        mock_fmp.assert_called_once()
        self.assertEqual(fundamentals["pe_history_meta"]["source"], "fmp")
        self.assertEqual(fundamentals["pe_20y_array"], rich_fmp_bundle["values"])

    def test_neither_called_when_already_sufficient(self):
        from src.conviction_engine.fundamentals_enriched import build_fundamentals_from_raw

        raw = _make_raw("PYPL", thin=False)
        with patch(
            "src.conviction_engine.fundamentals_enriched.fetch_pe_history_sec"
        ) as mock_sec, patch(
            "src.conviction_engine.fundamentals_enriched.fetch_pe_history_fmp"
        ) as mock_fmp:
            fundamentals = build_fundamentals_from_raw(raw)
        mock_sec.assert_not_called()
        mock_fmp.assert_not_called()
        self.assertFalse(fundamentals["pe_history_meta"]["insufficient_20y"])
        self.assertEqual(fundamentals["pe_history_meta"]["source"], "yfinance")

    def test_neither_called_for_non_us_ticker_even_when_thin(self):
        from src.conviction_engine.fundamentals_enriched import build_fundamentals_from_raw

        raw = _make_raw("SHOP.TO", thin=True)
        with patch(
            "src.conviction_engine.fundamentals_enriched.fetch_pe_history_sec"
        ) as mock_sec, patch(
            "src.conviction_engine.fundamentals_enriched.fetch_pe_history_fmp"
        ) as mock_fmp:
            fundamentals = build_fundamentals_from_raw(raw)
        mock_sec.assert_not_called()
        mock_fmp.assert_not_called()
        self.assertTrue(fundamentals["pe_history_meta"]["insufficient_20y"])
        self.assertEqual(fundamentals["pe_history_meta"]["source"], "yfinance")

    def test_sec_thinner_result_ignored_but_fmp_still_skipped(self):
        """SEC returning a series no richer than yfinance's own should not override it
        -- but since SEC returned *something* (not None), FMP must still be skipped
        entirely per the 'FMP only if SEC has no data' rule."""
        from src.conviction_engine.fundamentals_enriched import build_fundamentals_from_raw

        thin_sec_bundle = {
            "values": [10.0],
            "meta": {
                "years_available": 0.1,
                "point_count": 1,
                "stored_point_count": 1,
                "insufficient_20y": True,
                "target_years": 20,
                "source": "sec_edgar",
                "start_date": "2024-01-01",
                "end_date": "2024-02-01",
            },
        }
        raw = _make_raw("PYPL", thin=True)
        with patch(
            "src.conviction_engine.fundamentals_enriched.fetch_pe_history_sec",
            return_value=thin_sec_bundle,
        ) as mock_sec, patch(
            "src.conviction_engine.fundamentals_enriched.fetch_pe_history_fmp"
        ) as mock_fmp:
            fundamentals = build_fundamentals_from_raw(raw)
        mock_sec.assert_called_once()
        mock_fmp.assert_not_called()
        self.assertEqual(fundamentals["pe_history_meta"]["source"], "yfinance")

    def test_fmp_thinner_result_ignored_keeps_yfinance(self):
        """FMP returning a series no richer than the existing yfinance one (after SEC
        returned None) should not override it."""
        from src.conviction_engine.fundamentals_enriched import build_fundamentals_from_raw

        thin_fmp_bundle = {
            "values": [10.0],
            "meta": {
                "years_available": 0.1,
                "point_count": 1,
                "stored_point_count": 1,
                "insufficient_20y": True,
                "target_years": 20,
                "source": "fmp",
                "start_date": "2024-01-01",
                "end_date": "2024-02-01",
            },
        }
        raw = _make_raw("PYPL", thin=True)
        with patch(
            "src.conviction_engine.fundamentals_enriched.fetch_pe_history_sec",
            return_value=None,
        ), patch(
            "src.conviction_engine.fundamentals_enriched.fetch_pe_history_fmp",
            return_value=thin_fmp_bundle,
        ) as mock_fmp:
            fundamentals = build_fundamentals_from_raw(raw)
        mock_fmp.assert_called_once()
        self.assertEqual(fundamentals["pe_history_meta"]["source"], "yfinance")


if __name__ == "__main__":
    unittest.main()
