"""Tests for centralized prompt templates."""

import unittest

from chatbot.smart_data_fetcher import infer_date_filter_mode
from prompts.engine import SYSTEM_PROMPT, format_unified_extractor_prompt
from prompts.ui_buttons import (
    ANALYZE_ASSET_PROMPT_LEGACY_TEMPLATE,
    format_analyze_asset_prompt,
    format_analyze_asset_prompt_legacy,
    format_breadth_analysis_prompt,
    format_signal_insights_prompt,
)


class TestUiButtonPrompts(unittest.TestCase):
    def test_analyze_asset_prompt_substitution(self):
        prompt = format_analyze_asset_prompt("MSFT", "2026-04-01", "2026-05-16")
        self.assertIn("MSFT", prompt)
        self.assertIn("2026-04-01", prompt)
        self.assertIn("2026-05-16", prompt)
        self.assertIn("Please run a deep dive", prompt)
        self.assertIn("entry and / or exit-date range", prompt)
        self.assertIn("=== ENTRY SIGNALS (JSON) ===", prompt)
        self.assertIn("list **all** open signals", prompt)
        self.assertIn("Markdown table", prompt)
        self.assertIn("Table 1 — Open signal summary", prompt)
        self.assertIn("Exited signals (tabular", prompt)
        self.assertIn("Date Range: 2026-04-01 to 2026-05-16", prompt)
        self.assertNotIn("────────────────", prompt)
        self.assertEqual(
            infer_date_filter_mode(prompt),
            "entry_or_exit",
        )

    def test_legacy_analyze_asset_prompt(self):
        prompt = format_analyze_asset_prompt_legacy("BYDDY", "2026-04-01", "2026-05-16")
        self.assertIn("Please run a deep dive on BYDDY", prompt)
        self.assertIn("Date Range: 2026-04-01 to 2026-05-16", prompt)

    def test_legacy_template_non_empty(self):
        self.assertGreater(len(ANALYZE_ASSET_PROMPT_LEGACY_TEMPLATE), 200)

    def test_signal_insights_prompt(self):
        prompt = format_signal_insights_prompt("2026-01-01", "2026-01-31")
        self.assertIn("ENTRY signals", prompt)
        self.assertIn("2026-01-01", prompt)

    def test_breadth_analysis_prompt(self):
        prompt = format_breadth_analysis_prompt("2026-05-01", "2026-05-18")
        self.assertIn("Signal Breadth Indicator", prompt)
        self.assertIn("2026-05-18", prompt)


class TestEnginePrompts(unittest.TestCase):
    def test_system_prompt_loaded(self):
        self.assertGreater(len(SYSTEM_PROMPT), 500)
        self.assertIn("MindWealth", SYSTEM_PROMPT)

    def test_unified_extractor_prompt(self):
        prompt = format_unified_extractor_prompt(
            user_query="signals for AAPL",
            available_functions="TRENDPULSE, FRACTAL TRACK",
            ticker_list="AAPL, MSFT",
            column_context="=== columns ===",
        )
        self.assertIn("signals for AAPL", prompt)
        self.assertIn("TRENDPULSE", prompt)
        self.assertIn("=== columns ===", prompt)


if __name__ == "__main__":
    unittest.main()
