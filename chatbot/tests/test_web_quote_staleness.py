"""
Guards for web-quote dating.

The incident: an NVDA quote dated 2026-07-18 was printed beside a live internal
price. The pipeline carried no date field at all — the only temporal signal was
"Retrieved at: <now>", which is when we fetched the page, not when it was written.
"""

import logging
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from chatbot.agents.web_search_agent import (  # noqa: E402
    SearchResult,
    WebSearchAgent,
    _describe_publication,
    _is_stale_for_prices,
    _parse_date_like,
    _resolve_published_date,
    annotate_result_ages,
)

logging.disable(logging.WARNING)


class TestDateParsing(unittest.TestCase):
    def test_formats_these_sources_actually_use(self) -> None:
        cases = {
            "2026-07-18": "2026-07-18",
            "Fri, 18 Jul 2026 10:00:00 GMT": "2026-07-18",
            "https://www.fool.com/2026/07/18/nvda-news/": "2026-07-18",
            "https://site.com/20260718/story": "2026-07-18",
        }
        for raw, expected in cases.items():
            self.assertEqual(_parse_date_like(raw), expected, raw)

    def test_junk_returns_none(self) -> None:
        for raw in ("", None, "garbage", "https://example.com/page", "2026-13-45"):
            self.assertIsNone(_parse_date_like(raw), repr(raw))

    def test_resolution_precedence(self) -> None:
        """Tavily's own field wins over a date in the URL."""
        self.assertEqual(
            _resolve_published_date(
                {"published_date": "2026-08-01"}, "https://x.com/2026/07/18/a", ""
            ),
            "2026-08-01",
        )

    def test_url_used_when_field_absent(self) -> None:
        self.assertEqual(
            _resolve_published_date({}, "https://x.com/2026/07/18/a", ""), "2026-07-18"
        )

    def test_content_used_as_last_resort(self) -> None:
        self.assertEqual(
            _resolve_published_date({}, "https://x.com/a", "posted 18 July 2026 by staff"),
            "2026-07-18",
        )

    def test_nothing_anywhere_is_none(self) -> None:
        self.assertIsNone(_resolve_published_date({}, "https://x.com/a", "no dates"))


class TestAgeing(unittest.TestCase):
    def test_age_measured_against_our_as_of(self) -> None:
        results = [SearchResult("t", "u", "c", 0.5, published_date="2026-07-18")]
        annotate_result_ages(results, "2026-08-17")
        self.assertEqual(results[0].age_days, 30)

    def test_future_dates_clamp_to_zero(self) -> None:
        results = [SearchResult("t", "u", "c", 0.5, published_date="2026-09-01")]
        annotate_result_ages(results, "2026-08-17")
        self.assertEqual(results[0].age_days, 0)

    def test_undated_results_stay_none(self) -> None:
        results = [SearchResult("t", "u", "c", 0.5)]
        annotate_result_ages(results, "2026-08-17")
        self.assertIsNone(results[0].age_days)

    def test_missing_as_of_falls_back_to_wall_clock(self) -> None:
        """Without a fallback every source would read stale and all prices vanish."""
        results = [SearchResult("t", "u", "c", 0.5, published_date="2020-01-01")]
        annotate_result_ages(results, None)
        self.assertIsNotNone(results[0].age_days)
        self.assertGreater(results[0].age_days, 300)


class TestStalenessGate(unittest.TestCase):
    def test_fresh_is_usable(self) -> None:
        r = SearchResult("t", "u", "c", 0.5, published_date="2026-08-17", age_days=0)
        self.assertFalse(_is_stale_for_prices(r))

    def test_old_is_stale(self) -> None:
        r = SearchResult("t", "u", "c", 0.5, published_date="2026-07-18", age_days=30)
        self.assertTrue(_is_stale_for_prices(r))

    def test_unknown_date_is_stale(self) -> None:
        """Guessing freshness is what caused the bug; unknown must not be optimistic."""
        self.assertTrue(_is_stale_for_prices(SearchResult("t", "u", "c", 0.5)))

    def test_threshold_is_configurable(self) -> None:
        r = SearchResult("t", "u", "c", 0.5, published_date="2026-08-10", age_days=7)
        with patch("chatbot.config.WEB_QUOTE_MAX_AGE_DAYS", 30):
            self.assertFalse(_is_stale_for_prices(r))

    def test_description_wording(self) -> None:
        self.assertIn("unknown", _describe_publication(SearchResult("t", "u", "c", 0.5)))
        self.assertIn(
            "same day",
            _describe_publication(
                SearchResult("t", "u", "c", 0.5, published_date="2026-08-17", age_days=0)
            ),
        )
        self.assertIn(
            "30 days before",
            _describe_publication(
                SearchResult("t", "u", "c", 0.5, published_date="2026-07-18", age_days=30)
            ),
        )


class TestFormatter(unittest.TestCase):
    def _block(self):
        results = [
            SearchResult("Fresh", "u1", "body A", 0.9, published_date="2026-08-17"),
            SearchResult("Old", "u2", "body B", 0.8, published_date="2026-07-18"),
            SearchResult("Undated", "u3", "body C", 0.7),
        ]
        annotate_result_ages(results, "2026-08-17")
        return WebSearchAgent._format_for_claude("tsla vs nvda price", results)

    def test_every_source_carries_a_published_line(self) -> None:
        block = self._block()
        self.assertEqual(block.count("Published:"), 3)

    def test_stale_sources_are_marked_and_summarised(self) -> None:
        block = self._block()
        self.assertIn("PRICE USE: STALE", block)
        self.assertIn("STALE FOR PRICES: Source 2, Source 3", block)

    def test_fresh_source_is_not_marked(self) -> None:
        block = self._block()
        fresh_section = block.split("[Source 2]")[0]
        self.assertNotIn("PRICE USE: STALE", fresh_section)

    def test_content_and_citation_rule_still_present(self) -> None:
        block = self._block()
        for expected in ("body A", "body B", "[Source N]", "=== END WEB SEARCH RESULTS ==="):
            self.assertIn(expected, block)

    def test_empty_results_do_not_crash(self) -> None:
        block = WebSearchAgent._format_for_claude("q", [])
        self.assertIn("=== WEB SEARCH RESULTS ===", block)
        self.assertNotIn("STALE FOR PRICES", block)


if __name__ == "__main__":
    unittest.main()
