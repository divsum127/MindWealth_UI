"""Live and fixture tests for macro/SSI scraper pipelines."""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

FIXTURES = Path(__file__).parent / "fixtures" / "scrapers"


class TestCapeScrape(unittest.TestCase):
    def test_load_cape_has_history(self) -> None:
        from src.macro_intelligence.data.cape_scrape import load_cape_series

        s = load_cape_series()
        self.assertGreater(len(s), 100)
        self.assertGreater(float(s.iloc[-1]), 10.0)


class TestCnnFearGreed(unittest.TestCase):
    def test_parse_fixture_json(self) -> None:
        from src.sentiment_superindex.data.scraper_utils import parse_cnn_historical_points

        data = json.loads((FIXTURES / "cnn_fear_greed_sample.json").read_text())
        hist = parse_cnn_historical_points(data["fear_and_greed_historical"])
        self.assertEqual(len(hist), 2)
        self.assertTrue((hist <= 100).all() and (hist >= 0).all())

    @patch("src.sentiment_superindex.data.cnn_fear_greed.http_get")
    def test_fetch_uses_api_scores(self, mock_get) -> None:
        from src.sentiment_superindex.data.cnn_fear_greed import fetch_cnn_history

        class Resp:
            def raise_for_status(self):
                return None

            def json(self):
                return json.loads((FIXTURES / "cnn_fear_greed_sample.json").read_text())

        mock_get.return_value = Resp()
        s = fetch_cnn_history()
        self.assertGreaterEqual(len(s), 2)
        self.assertLessEqual(float(s.iloc[-1]), 100.0)

    def test_live_cnn_in_valid_range(self) -> None:
        from src.sentiment_superindex.data.cnn_fear_greed import fetch_cnn_history

        s = fetch_cnn_history()
        if s.empty:
            self.skipTest("CNN API unavailable")
        last = float(s.iloc[-1])
        self.assertGreaterEqual(last, 0.0)
        self.assertLessEqual(last, 100.0)


class TestAaiiPull(unittest.TestCase):
    def test_ingest_fixture_csv(self) -> None:
        from src.sentiment_superindex.data.aaii_pull import ingest_aaii_csv

        s = ingest_aaii_csv(FIXTURES / "aaii_sentiment.csv")
        self.assertEqual(len(s), 5)
        self.assertAlmostEqual(float(s.iloc[-1]), 42.5 - 29.0, places=1)

    def test_github_sync_csv(self) -> None:
        from unittest.mock import MagicMock, patch

        from src.sentiment_superindex.data.aaii_pull import _fetch_github_synced

        csv_bytes = (FIXTURES / "aaii_sentiment.csv").read_bytes()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = csv_bytes
        with patch(
            "src.sentiment_superindex.data.aaii_pull._github_sync_urls",
            return_value=[("https://example.test/aaii_sentiment.csv", "aaii_github_csv")],
        ), patch("src.sentiment_superindex.data.aaii_pull.requests.get", return_value=mock_resp):
            series, tag = _fetch_github_synced()
        self.assertEqual(len(series), 5)
        self.assertEqual(tag, "aaii_github_csv")

    def test_scrape_sent_results_live(self) -> None:
        from src.sentiment_superindex.data.aaii_pull import _scrape_sent_results_table

        s = _scrape_sent_results_table()
        if s.empty:
            self.skipTest("AAII sent_results unavailable")
        self.assertGreaterEqual(len(s), 10)


class TestNaaimPull(unittest.TestCase):
    def test_live_naaim_has_rows(self) -> None:
        from src.sentiment_superindex.data.naaim_pull import fetch_naaim_exposure

        s = fetch_naaim_exposure()
        if s.empty:
            self.skipTest("NAAIM scrape unavailable")
        self.assertGreater(len(s), 3)
        self.assertGreater(float(s.iloc[-1]), -200.0)


class TestBreadthSp500(unittest.TestCase):
    def test_sp500_universe_loads(self) -> None:
        from src.sentiment_superindex.data.sp500_universe import load_sp500_tickers

        t = load_sp500_tickers()
        self.assertGreaterEqual(len(t), 400)

    def test_breadth_stats_columns(self) -> None:
        from src.sentiment_superindex.data.sp500_breadth import compute_daily_breadth_stats
        import pandas as pd
        import numpy as np

        idx = pd.date_range("2023-01-01", periods=260, freq="B")
        close = pd.DataFrame(
            {f"S{i}": 100 + np.arange(260) * 0.1 for i in range(25)},
            index=idx,
        )
        df = compute_daily_breadth_stats(close)
        self.assertIn("nh_nl_ratio", df.columns)
        self.assertIn("pct_above_200dma", df.columns)
        self.assertIn("net_advances", df.columns)


class TestInvestingCpiConsensus(unittest.TestCase):
    def test_parse_fixture_html(self) -> None:
        from src.macro_intelligence.data.investing_cpi_consensus import _parse_calendar_html

        html = (FIXTURES / "investing_cpi_calendar.html").read_text()
        rows = _parse_calendar_html(html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].consensus, 0.1)
        self.assertEqual(rows[0].actual, 0.2)

    def test_te_consensus_when_post_release_equals_actual(self) -> None:
        from src.macro_intelligence.data.investing_cpi_consensus import _te_consensus_from_cells

        # TE often copies Actual into Consensus; Previous holds pre-release consensus.
        tds = ["2026-04-10", "12:30 PM", "Inflation Rate MoM", "Mar", "0.9%", "0.3%", "0.9%", "0.8%"]
        consensus = _te_consensus_from_cells(tds, actual=0.9, prior_release_actual=None)
        self.assertEqual(consensus, 0.3)

    def test_parse_tradingeconomics_fixture(self) -> None:
        from src.macro_intelligence.data.investing_cpi_consensus import _parse_tradingeconomics_html

        html = (FIXTURES / "tradingeconomics_cpi_mom.html").read_text()
        rows = _parse_tradingeconomics_html(html, series="headline")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].release_date, "2026-05-12")
        self.assertEqual(rows[0].consensus, 0.6)
        self.assertEqual(rows[0].actual, 0.6)
        self.assertEqual(rows[1].release_date, "2026-06-10")
        self.assertEqual(rows[1].consensus, 0.4)
        self.assertIsNone(rows[1].actual)
        self.assertEqual(rows[1].source, "tradingeconomics.com")

    def test_fetch_cpi_consensus_te_primary_without_investing_proxy(self) -> None:
        from src.macro_intelligence.data import investing_cpi_consensus as mod

        te_row = mod.CpiReleaseRow(
            release_date="2026-06-10",
            consensus=0.4,
            actual=None,
            previous=0.6,
            event_name="Inflation Rate MoM",
            source="tradingeconomics.com",
        )
        with patch.dict("os.environ", {}, clear=False):
            os.environ.pop("INVESTING_HTTP_PROXY", None)
            with patch.object(mod, "fetch_tradingeconomics_cpi_calendar", return_value=[te_row]):
                with patch.object(mod, "fetch_investing_cpi_calendar") as mock_inv:
                    with patch.object(mod, "fetch_fred_cpi_release_dates", return_value=[]):
                        rows = mod.fetch_cpi_consensus_calendar()
        mock_inv.assert_not_called()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].source, "tradingeconomics.com")

    def test_merge_cpi_rows_prefers_primary(self) -> None:
        from src.macro_intelligence.data.investing_cpi_consensus import CpiReleaseRow, _merge_cpi_rows

        secondary = [
            CpiReleaseRow("2026-06-10", 0.3, None, None, "Inflation Rate MoM", "investing.com"),
        ]
        primary = [
            CpiReleaseRow("2026-06-10", 0.4, None, 0.6, "Inflation Rate MoM", "tradingeconomics.com"),
        ]
        merged = _merge_cpi_rows(primary, secondary)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].consensus, 0.4)
        self.assertEqual(merged[0].source, "tradingeconomics.com")

    def test_calendar_post_payloads_include_custom_range(self) -> None:
        from src.macro_intelligence.data.investing_cpi_consensus import _calendar_post_payloads

        payloads = _calendar_post_payloads(weeks_back=8)
        tabs = [p["currentTab"] for p in payloads]
        self.assertIn("thisWeek", tabs)
        self.assertIn("nextWeek", tabs)
        self.assertIn("custom", tabs)
        custom = next(p for p in payloads if p["currentTab"] == "custom")
        self.assertIn("dateFrom", custom)
        self.assertIn("dateTo", custom)


class TestPct200Dma(unittest.TestCase):
    def test_live_or_cached_pct(self) -> None:
        from src.sentiment_superindex.data.pct_200dma_pull import fetch_pct_above_200dma

        s = fetch_pct_above_200dma("2020-01-01")
        if s.empty:
            self.skipTest("200DMA computation unavailable (yfinance)")
        self.assertGreaterEqual(float(s.iloc[-1]), 0.0)
        self.assertLessEqual(float(s.iloc[-1]), 100.0)


class TestCftcSnapshotGuard(unittest.TestCase):
    def test_persist_returns_none_before_cftc_era(self) -> None:
        from src.macro_intelligence.data.cftc_pull import persist_cftc_snapshot

        snap = persist_cftc_snapshot("1990-01-01")
        self.assertIsNone(snap)


if __name__ == "__main__":
    unittest.main()
