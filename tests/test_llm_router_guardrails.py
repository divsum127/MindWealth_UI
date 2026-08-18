"""Tests for the deterministic internal-only override in LLMRouter.

Covers the fix for Rohit's flagged issue: entry/exit/target/stop/resistance
queries about MindWealth signals must never be routed to web search, even if
the underlying LLM classification call mis-labels them as needing web data.
"""

import unittest
from unittest.mock import MagicMock, patch

from chatbot.agents.llm_router import (
    LLMRouter,
    _INTERNAL_LEVEL_QUERY_RE,
    _WEB_ONLY_SIGNAL_RE,
    apply_internal_level_override,
)
from chatbot.chatbot_engine import _TARGETS_STOP_QUERY_RE as ENGINE_TARGETS_STOP_RE
from chatbot.smart_data_fetcher import _TARGETS_STOP_QUERY_RE as FETCHER_TARGETS_STOP_RE


ROHIT_QUERY = "recent exit levels and entry levels for Google and NVDA"


class TestApplyInternalLevelOverride(unittest.TestCase):
    def test_overrides_web_for_level_query(self):
        internal, web, queries, reasoning = apply_internal_level_override(
            ROHIT_QUERY,
            internal=True,
            web=True,
            queries=["GOOG NVDA exit levels"],
            reasoning="User wants recent levels",
        )
        self.assertTrue(internal)
        self.assertFalse(web)
        self.assertIsNone(queries)
        self.assertIn("override", reasoning.lower())

    def test_overrides_resistance_query(self):
        internal, web, queries, reasoning = apply_internal_level_override(
            "what is the resistance level for NVDA",
            internal=False,
            web=True,
            queries=["NVDA resistance level"],
            reasoning="Needs web technical analysis",
        )
        self.assertTrue(internal)
        self.assertFalse(web)
        self.assertIsNone(queries)

    def test_does_not_override_when_web_already_false(self):
        internal, web, queries, reasoning = apply_internal_level_override(
            ROHIT_QUERY,
            internal=True,
            web=False,
            queries=None,
            reasoning="Internal only",
        )
        self.assertTrue(internal)
        self.assertFalse(web)
        self.assertIsNone(queries)
        self.assertEqual(reasoning, "Internal only")

    def test_does_not_override_pure_web_query(self):
        internal, web, queries, reasoning = apply_internal_level_override(
            "what's the latest news on NVDA earnings",
            internal=False,
            web=True,
            queries=["NVDA earnings news"],
            reasoning="News query",
        )
        self.assertFalse(internal)
        self.assertTrue(web)
        self.assertEqual(queries, ["NVDA earnings news"])
        self.assertEqual(reasoning, "News query")

    def test_does_not_override_genuine_hybrid_query(self):
        # Level wording AND explicit web-only wording (news) present ->
        # genuine hybrid ask should still be allowed to hit the web.
        internal, web, queries, reasoning = apply_internal_level_override(
            "compare my TSM entry level with today's TSM earnings news",
            internal=True,
            web=True,
            queries=["TSM earnings news"],
            reasoning="Hybrid",
        )
        self.assertTrue(internal)
        self.assertTrue(web)
        self.assertEqual(queries, ["TSM earnings news"])
        self.assertEqual(reasoning, "Hybrid")

    def test_matches_take_profit_and_stop_loss_wording(self):
        for phrase in (
            "what's my take profit for AAPL",
            "show me stop loss for MSFT",
            "what are the pivot and f-stack targets for TSLA",
        ):
            with self.subTest(phrase=phrase):
                self.assertTrue(_INTERNAL_LEVEL_QUERY_RE.search(phrase))

    def test_web_only_regex_matches_news_wording(self):
        for phrase in (
            "any breaking news on NVDA",
            "NVDA earnings report",
            "Fed rate decision impact",
        ):
            with self.subTest(phrase=phrase):
                self.assertTrue(_WEB_ONLY_SIGNAL_RE.search(phrase))


class TestLLMRouterRouteOverride(unittest.TestCase):
    """End-to-end test through LLMRouter.route() with a mocked OpenAI client."""

    def _make_router_with_response(self, payload: dict) -> LLMRouter:
        router = LLMRouter(api_key=None)  # skip real OpenAI init
        mock_client = MagicMock()
        mock_message = MagicMock()
        import json

        mock_message.content = json.dumps(payload)
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=mock_message)]
        mock_client.chat.completions.create.return_value = mock_response
        router._client = mock_client
        return router

    def test_route_forces_internal_only_for_level_query(self):
        router = self._make_router_with_response(
            {
                "conversational_only": False,
                "needs_internal_signal_data": True,
                "needs_web_search": True,
                "search_queries": ["GOOG NVDA resistance level"],
                "reasoning": "User wants resistance and exit levels",
            }
        )
        result = router.route(ROHIT_QUERY)
        self.assertTrue(result.needs_internal_signal_data)
        self.assertFalse(result.needs_web_search)
        self.assertIsNone(result.search_queries)
        self.assertIn("override", result.reasoning.lower())

    def test_route_keeps_web_for_pure_news_query(self):
        router = self._make_router_with_response(
            {
                "conversational_only": False,
                "needs_internal_signal_data": False,
                "needs_web_search": True,
                "search_queries": ["NVDA earnings news 2026"],
                "reasoning": "News query about earnings",
            }
        )
        result = router.route("what's the latest news on NVDA earnings")
        self.assertTrue(result.needs_web_search)
        self.assertEqual(result.search_queries, ["NVDA earnings news 2026"])


class TestTargetsStopQueryRegexWidened(unittest.TestCase):
    """Both copies of _TARGETS_STOP_QUERY_RE must match Rohit's exact phrasing
    so the column-picker guardrail pulls Targets/Stop Loss columns."""

    def test_engine_regex_matches_rohit_query(self):
        self.assertTrue(ENGINE_TARGETS_STOP_RE.search(ROHIT_QUERY))

    def test_fetcher_regex_matches_rohit_query(self):
        self.assertTrue(FETCHER_TARGETS_STOP_RE.search(ROHIT_QUERY))

    def test_engine_regex_matches_resistance_wording(self):
        self.assertTrue(
            ENGINE_TARGETS_STOP_RE.search("what is the resistance level for NVDA")
        )

    def test_fetcher_regex_matches_resistance_wording(self):
        self.assertTrue(
            FETCHER_TARGETS_STOP_RE.search("what is the resistance level for NVDA")
        )


if __name__ == "__main__":
    unittest.main()
