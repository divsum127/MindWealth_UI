"""
Guards for the three code-level defects found in the sheet-driven bug sweep:
raw provider errors reaching users, silent ticker substitution, and silent
omission of a requested ticker.
"""

import logging
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd  # noqa: E402

from chatbot.asset_coverage import (  # noqa: E402
    build_ticker_mapping_note,
    coverage_note,
    inferred_assets,
    uncovered_assets,
)
from chatbot.error_messages import (  # noqa: E402
    GENERIC,
    safe_error_metadata,
    user_facing_error,
)
from chatbot.smart_data_fetcher import _drop_exact_duplicate_rows  # noqa: E402

logging.disable(logging.ERROR)

# The verbatim text a user was shown, from the todo sheet.
_REAL_BILLING_ERROR = (
    "Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', "
    "'message': 'Your credit balance is too low to access the Anthropic API. Please go "
    "to Plans & Billing to upgrade or purchase credits.'}, 'request_id': 'req_011CdZXHhfEZa88x6hcfgeoA'}"
)


class TestErrorSanitisation(unittest.TestCase):
    def test_billing_error_leaks_nothing(self) -> None:
        out = user_facing_error(Exception(_REAL_BILLING_ERROR))
        for leak in ("Anthropic", "req_011", "credit balance", "Plans & Billing", "400"):
            self.assertNotIn(leak, out, f"leaked: {leak}")
        self.assertIn("quota", out.lower())

    def test_classification(self) -> None:
        cases = [
            (Exception("Error code: 429 rate_limit_error"), "too many requests"),
            (TimeoutError("read timed out"), "longer than the time available"),
            (Exception("401 invalid_api_key"), "authenticate"),
            (FileNotFoundError("no such file: entry.csv"), "could not be read"),
        ]
        for exc, expected in cases:
            self.assertIn(expected, user_facing_error(exc), str(exc))

    def test_unknown_error_falls_back_to_generic(self) -> None:
        self.assertEqual(user_facing_error(ValueError("weird internal thing")), GENERIC)

    def test_no_exception_text_survives_any_branch(self) -> None:
        """A partial regex match must not splice provider text into the output."""
        secret = "SUPERSECRET-TOKEN-abc123"
        for exc in (Exception(f"rate limit hit {secret}"), Exception(f"unmatched {secret}")):
            self.assertNotIn(secret, user_facing_error(exc))

    def test_metadata_keeps_detail_but_display_is_safe(self) -> None:
        md = safe_error_metadata(Exception(_REAL_BILLING_ERROR))
        self.assertNotIn("req_011", md["error"])
        self.assertIn("credit balance", md["error_detail"])

    def test_non_ascii_and_empty_messages_do_not_crash(self) -> None:
        for exc in (Exception(""), Exception("エラー"), RuntimeError(None)):
            self.assertTrue(user_facing_error(exc))


class TestInferredTickers(unittest.TestCase):
    def test_literal_symbols_are_not_flagged(self) -> None:
        self.assertEqual(inferred_assets("latest AAPL and NVDA signals", ["AAPL", "NVDA"]), [])

    def test_case_insensitive(self) -> None:
        self.assertEqual(inferred_assets("latest aapl signals", ["AAPL"]), [])

    def test_suffix_symbol_matched_by_base(self) -> None:
        """"replace fph and mft" must not flag FPH.NZ as invented."""
        self.assertEqual(inferred_assets("replace fph and mft", ["FPH.NZ", "MFT.NZ"]), [])

    def test_company_name_and_typo_are_flagged(self) -> None:
        self.assertEqual(inferred_assets("levels for google and nvda", ["GOOG", "NVDA"]), ["GOOG"])
        self.assertIn("TLT", inferred_assets("mhci, tlk and brbk", ["MCHI", "TLT", "BRK-B"]))

    def test_note_mentions_every_inferred_symbol(self) -> None:
        note = build_ticker_mapping_note("mhci, tlk and brbk", ["MCHI", "TLT", "BRK-B"])
        assert note is not None
        for sym in ("MCHI", "TLT", "BRK-B"):
            self.assertIn(sym, note)
        self.assertIn("different company", note)

    def test_no_note_when_nothing_inferred(self) -> None:
        self.assertIsNone(build_ticker_mapping_note("AAPL please", ["AAPL"]))
        self.assertIsNone(build_ticker_mapping_note("", None))


class TestCoverageGuard(unittest.TestCase):
    def test_flags_the_real_goog_omission(self) -> None:
        answer = "# NVDA analysis\nNVIDIA exit signals ..."
        self.assertEqual(uncovered_assets(answer, ["GOOG", "NVDA"], {"GOOG": 15, "NVDA": 2}), ["GOOG"])

    def test_no_flag_when_symbol_is_discussed_even_as_absent(self) -> None:
        answer = "GOOG: no rows returned in this window. NVDA: 3 signals."
        self.assertEqual(uncovered_assets(answer, ["GOOG", "NVDA"], {"GOOG": 15, "NVDA": 3}), [])

    def test_zero_row_symbols_are_not_flagged(self) -> None:
        self.assertEqual(uncovered_assets("NVDA only", ["GOOG", "NVDA"], {"GOOG": 0, "NVDA": 1}), [])

    def test_inferred_symbols_are_skipped(self) -> None:
        """An answer that correctly ignores a wrong guess must not be flagged."""
        answer = "MCHI: -2.6%. BRK-B: no signal. TLK is not tracked."
        self.assertEqual(
            uncovered_assets(answer, ["MCHI", "TLT", "BRK-B"], None, skip=["TLT"]), []
        )

    def test_region_filters_are_skipped(self) -> None:
        self.assertEqual(uncovered_assets("no NZ names", [".NZ"], None), [])

    def test_punctuation_heavy_symbols(self) -> None:
        self.assertEqual(uncovered_assets("^TNX rallied; BRK-B flat", ["^TNX", "BRK-B"], None), [])
        self.assertEqual(uncovered_assets("nothing here", ["000660.KS"], None), ["000660.KS"])

    def test_substring_does_not_count_as_coverage(self) -> None:
        self.assertEqual(uncovered_assets("AAPLE pie", ["AAPL"], None), ["AAPL"])

    def test_empty_inputs_are_safe(self) -> None:
        self.assertEqual(uncovered_assets("", ["AAPL"], None), [])
        self.assertEqual(uncovered_assets("text", None, None), [])

    def test_note_is_readable_for_one_and_many(self) -> None:
        self.assertIn("GOOG", coverage_note(["GOOG"]))
        self.assertIn("was", coverage_note(["GOOG"]))
        self.assertIn("were", coverage_note(["GOOG", "MSFT"]))


class TestExactDuplicateDedupe(unittest.TestCase):
    def test_identical_rows_collapse(self) -> None:
        df = pd.DataFrame({"a": [1, 1, 2], "b": ["x", "x", "y"]})
        self.assertEqual(len(_drop_exact_duplicate_rows(df)), 2)

    def test_rows_differing_in_one_column_are_kept(self) -> None:
        """Two real signals sharing a symbol must both survive."""
        df = pd.DataFrame({"sym": ["AAPL", "AAPL"], "fn": ["TRENDPULSE", "FRACTAL TRACK"]})
        self.assertEqual(len(_drop_exact_duplicate_rows(df)), 2)

    def test_order_and_first_occurrence_preserved(self) -> None:
        df = pd.DataFrame({"a": [3, 1, 3, 2]})
        self.assertEqual(list(_drop_exact_duplicate_rows(df)["a"]), [3, 1, 2])

    def test_empty_and_none_are_safe(self) -> None:
        self.assertTrue(_drop_exact_duplicate_rows(pd.DataFrame()).empty)
        self.assertIsNone(_drop_exact_duplicate_rows(None))

    def test_nan_rows_are_treated_as_duplicates(self) -> None:
        df = pd.DataFrame({"a": [None, None], "b": [1, 1]})
        self.assertEqual(len(_drop_exact_duplicate_rows(df)), 1)


class TestPromptRules(unittest.TestCase):
    def test_reporting_rules_present(self) -> None:
        from prompts.engine import SYSTEM_PROMPT

        for rule in (
            "Name the price MTM is measured from",
            "Copy the stored MTM character-for-character",
            "sample size",
            "Date every web quote",
            "Cover every symbol",
        ):
            self.assertIn(rule, SYSTEM_PROMPT, rule)


class TestEngineCoverageGuardIntegration(unittest.TestCase):
    def test_guard_appends_note_and_records_metadata(self) -> None:
        from chatbot.chatbot_engine import ChatbotEngine

        engine = ChatbotEngine.__new__(ChatbotEngine)  # no __init__: no CSV load
        meta = {"rows_by_asset": {"GOOG": 15, "NVDA": 2}}
        out, md = ChatbotEngine._apply_coverage_guard(
            engine, "levels for GOOG and NVDA", "NVDA only analysis", meta, ["GOOG", "NVDA"]
        )
        self.assertIn("Coverage note", out)
        self.assertEqual(md["assets_not_covered"], ["GOOG"])

    def test_guard_is_a_no_op_when_everything_covered(self) -> None:
        from chatbot.chatbot_engine import ChatbotEngine

        engine = ChatbotEngine.__new__(ChatbotEngine)
        out, md = ChatbotEngine._apply_coverage_guard(
            engine, "GOOG and NVDA", "GOOG and NVDA both covered", {}, ["GOOG", "NVDA"]
        )
        self.assertNotIn("Coverage note", out)
        self.assertNotIn("assets_not_covered", md)

    def test_guard_never_raises(self) -> None:
        from chatbot.chatbot_engine import ChatbotEngine

        engine = ChatbotEngine.__new__(ChatbotEngine)
        with patch("chatbot.chatbot_engine.uncovered_assets", side_effect=RuntimeError("boom")):
            out, md = ChatbotEngine._apply_coverage_guard(
                engine, "GOOG", "answer", {}, ["GOOG"]
            )
        self.assertEqual(out, "answer")


if __name__ == "__main__":
    unittest.main()
