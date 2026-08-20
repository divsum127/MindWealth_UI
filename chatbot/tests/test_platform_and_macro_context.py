"""
Guards for the three audit gaps: the assistant not knowing its own vocabulary,
platform-meta questions answered from general knowledge, and macro questions
falling through to web search.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from chatbot.agents.llm_router import (  # noqa: E402
    apply_macro_internal_override,
    apply_platform_vocab_internal_override,
    apply_recommendation_internal_override,
)
from chatbot.macro_context import MacroContextBuilder, is_macro_relevant  # noqa: E402
from chatbot.platform_context import (  # noqa: E402
    build_platform_context,
    is_platform_question,
)


class TestPlatformVocabRouting(unittest.TestCase):
    """"give me a short summary about claude report" used to ask if Claude was a ticker."""

    def test_claude_report_forces_internal(self) -> None:
        internal, web, _, reason = apply_platform_vocab_internal_override(
            "give me a short summry about claude report", False, False, None, "web only"
        )
        self.assertTrue(internal)
        self.assertIn("override", reason)

    def test_signal_types_question_forces_internal(self) -> None:
        internal, *_ = apply_platform_vocab_internal_override(
            "What signal types exist?", False, True, [], ""
        )
        self.assertTrue(internal)

    def test_function_name_forces_internal(self) -> None:
        for q in ("what is trendpulse", "explain the FRACTAL TRACK function", "deltadrift signals"):
            internal, *_ = apply_platform_vocab_internal_override(q, False, True, [], "")
            self.assertTrue(internal, q)

    def test_web_flag_is_left_alone(self) -> None:
        """The override only ever turns internal ON, so genuine hybrids survive."""
        _, web, queries, _ = apply_platform_vocab_internal_override(
            "mindwealth view on AAPL vs today's news", False, True, ["aapl news"], ""
        )
        self.assertTrue(web)
        self.assertEqual(queries, ["aapl news"])

    def test_ordinary_market_question_untouched(self) -> None:
        internal, *_ = apply_platform_vocab_internal_override(
            "what is the price of gold", False, True, [], ""
        )
        self.assertFalse(internal)


class TestMacroRouting(unittest.TestCase):
    """The macro half of the same defect class as the original NZ complaint."""

    def test_regime_and_combo_question_forces_internal(self) -> None:
        internal, web, _, reason = apply_macro_internal_override(
            "what is the current macro regime and which combo is dominant?",
            False, True, ["macro regime 2026"], "needs current market info",
        )
        self.assertTrue(internal)
        self.assertTrue(web, "web must stay on so the route lands on HYBRID")
        self.assertIn("macro", reason.lower())

    def test_ssi_and_sizing_questions(self) -> None:
        for q in ("what is the ssi multiplier", "how is position sizing set today",
                  "current market breadth", "is the yield curve steepening"):
            internal, *_ = apply_macro_internal_override(q, False, True, [], "")
            self.assertTrue(internal, q)

    def test_already_internal_is_a_no_op(self) -> None:
        internal, web, queries, reason = apply_macro_internal_override(
            "current regime", True, False, None, "unchanged"
        )
        self.assertEqual((internal, web, queries, reason), (True, False, None, "unchanged"))

    def test_recommendation_override_still_wins_independently(self) -> None:
        """Composition check — the four overrides must not cancel each other."""
        internal, web, queries, reason = apply_recommendation_internal_override(
            "what should i buy", False, True, ["x"], "r"
        )
        internal, web, queries, reason = apply_macro_internal_override(
            "what should i buy", internal, web, queries, reason
        )
        self.assertTrue(internal)
        self.assertTrue(web)


class TestMacroContextBuilder(unittest.TestCase):
    def test_relevance_gate(self) -> None:
        self.assertTrue(is_macro_relevant("which combo is dominant?"))
        self.assertTrue(is_macro_relevant("what is the ssi layer 2 status"))
        self.assertFalse(is_macro_relevant("latest aapl signals"))
        self.assertFalse(is_macro_relevant(""))

    def test_every_section_failing_yields_none(self) -> None:
        """Enrichment must degrade to nothing, never raise into a job thread."""
        builder = MacroContextBuilder()
        with patch.object(builder.client, "get", return_value=None):
            self.assertIsNone(builder.build("what is the current macro regime?"))

    def test_section_exception_is_swallowed(self) -> None:
        builder = MacroContextBuilder()
        with patch.object(builder.client, "get", side_effect=RuntimeError("boom")):
            self.assertIsNone(builder.build("which combo is dominant?"))

    def test_irrelevant_query_skips_all_http(self) -> None:
        builder = MacroContextBuilder()
        with patch.object(builder.client, "get") as mock_get:
            self.assertIsNone(builder.build("latest aapl signals"))
            mock_get.assert_not_called()

    def test_block_reports_regime_and_combos(self) -> None:
        payloads = {
            "/macro/runic/nightly": {
                "date": "2026-08-17",
                "dominant_signal": "F",
                "dominant_reason": "Combo F active",
                "regime": {"fed_cycle": "PAUSING"},
                "brave_fearful_display": "TACTICAL EASY MONEY",
                "ssi_multiplier": 1.2,
                "ssi_layer2_status": "CONFIRMED",
                "vix_bypass": True,
                "active_combos": [{"combo": "F", "status": "ACTIVE"}],
                "watch_combos": [{"combo": "D", "status": "WATCH"}],
            },
        }
        builder = MacroContextBuilder()
        with patch.object(builder.client, "get", side_effect=lambda p, q=None: payloads.get(p)):
            block = builder.build("what is the current macro regime and which combo is dominant?")
        assert block is not None
        self.assertIn("SOURCE D", block)
        self.assertIn("dominant_signal: F", block)
        self.assertIn("Combo D", block)
        self.assertIn("NOT firing", block, "WATCH combos must be labelled as not firing")
        self.assertIn("vix_bypass: yes", block)


class TestPlatformContext(unittest.TestCase):
    def test_relevance_gate(self) -> None:
        self.assertTrue(is_platform_question("give me a short summry about claude report"))
        self.assertTrue(is_platform_question("What signal types exist?"))
        self.assertFalse(is_platform_question("should i buy meta?"))

    def test_block_lists_our_taxonomy_not_generic_terms(self) -> None:
        block = build_platform_context("What signal types exist?")
        assert block is not None
        for key in ("entry", "exit", "portfolio_target_achieved", "breadth", "claude_report"):
            self.assertIn(f"`{key}`", block)
        self.assertIn("SOURCE E", block)
        self.assertIn("not public indicators", block)

    def test_irrelevant_question_returns_none(self) -> None:
        self.assertIsNone(build_platform_context("what is aapl doing"))


if __name__ == "__main__":
    unittest.main()
