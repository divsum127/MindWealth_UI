"""Tests for chatbot.agents.synthesis_agent hybrid MTM prompt blocks."""

import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
_SPECPATH = _ROOT / "chatbot" / "agents" / "synthesis_agent.py"
_spec = importlib.util.spec_from_file_location("synthesis_agent_standalone", _SPECPATH)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)
SynthesisAgent = _mod.SynthesisAgent


class TestSynthesisHybridRules(unittest.TestCase):
    def test_build_prompt_includes_hybrid_block_when_both_sources_ok(self):
        agent = SynthesisAgent()
        signal_data = {
            "entry": pd.DataFrame(
                [
                    {
                        "Function": "TRENDPULSE",
                        "Symbol, Signal, Signal Date/Price[$]": "SOXX, Long, 2026-02-28 (Price: 352.29)",
                        "Signal Open Price": "352.29",
                        "Today Trading Date/Price[$], Today Price vs Signal": "2026-05-08 (Price: 400.0000), 13.5% above",
                    }
                ]
            )
        }
        web_result = SimpleNamespace(success=True, results=[{"url": "https://example.com"}])

        prompt = agent.build_prompt(
            user_message="SOXX MTM",
            web_result=web_result,
            signal_data=signal_data,
            signal_metadata={},
            web_failed=False,
            internal_failed=False,
        )

        self.assertIn("=== HYBRID CALCULATION RULES ===", prompt)
        self.assertIn("recompute", prompt.lower())
        self.assertIn("SOURCE A", prompt)
        self.assertIn("SOURCE B", prompt)
        self.assertIn("latest signal date", prompt.lower())
        self.assertIn(
            "If multiple rows list the same Symbol",
            prompt,
        )
        self.assertIn("trade_store/stock_data", prompt)
        self.assertIn("CALCULATOR TOOL OUTPUT", prompt)

    def test_build_prompt_omits_hybrid_block_when_web_failed(self):
        agent = SynthesisAgent()
        signal_data = {"entry": pd.DataFrame([{"Function": "X"}])}
        web_result = SimpleNamespace(success=True)

        prompt = agent.build_prompt(
            user_message="test",
            web_result=web_result,
            signal_data=signal_data,
            signal_metadata={},
            web_failed=True,
            internal_failed=False,
        )

        self.assertNotIn("=== HYBRID CALCULATION RULES ===", prompt)

    def test_should_include_hybrid_false_when_empty_signal_data(self):
        self.assertFalse(
            SynthesisAgent._should_include_hybrid_mtm_rules(
                None,
                SimpleNamespace(success=True),
                web_failed=False,
                internal_failed=False,
            )
        )


if __name__ == "__main__":
    unittest.main()
