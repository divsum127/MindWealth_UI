"""
Guards for the committed ticker/alias map and the provenance check that replaced
the extractor's guessing.

The incident: "mhci, tlk and brbk" was extracted as [MCHI, TLT, BRK-B]. TLK is not
in the universe and TLT is a 20-year Treasury ETF, not Telkom Indonesia. Because
TLT *is* a real universe symbol, a membership check alone lets it through — only
provenance catches it.
"""

import json
import logging
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from chatbot.asset_coverage import build_unresolved_ticker_note  # noqa: E402
from chatbot.ticker_resolver import (  # noqa: E402
    _alias_index,
    resolve_ticker,
    resolve_tickers,
    verify_extracted_symbols,
)

logging.disable(logging.WARNING)

_MAP_PATH = _ROOT / "config" / "ticker_aliases.json"


def _universe():
    return sorted(json.loads(_MAP_PATH.read_text(encoding="utf-8"))["symbols"])


class TestAliasMapFile(unittest.TestCase):
    def test_map_exists_and_is_populated(self) -> None:
        payload = json.loads(_MAP_PATH.read_text(encoding="utf-8"))
        self.assertGreaterEqual(payload["symbol_count"], 150)
        self.assertGreaterEqual(payload["named_count"], 100)

    def test_no_alias_is_owned_by_two_symbols(self) -> None:
        """An ambiguous alias is a guess in disguise; the generator must prune them."""
        payload = json.loads(_MAP_PATH.read_text(encoding="utf-8"))
        owners: dict[str, list[str]] = {}
        for symbol, entry in payload["symbols"].items():
            for alias in entry.get("aliases", []):
                owners.setdefault(alias, []).append(symbol)
        self.assertEqual({a: o for a, o in owners.items() if len(o) > 1}, {})

    def test_untracked_symbols_absent(self) -> None:
        payload = json.loads(_MAP_PATH.read_text(encoding="utf-8"))
        for absent in ("TLK", "BRBK", "MHCI"):
            self.assertNotIn(absent, payload["symbols"])


class TestAliasResolution(unittest.TestCase):
    def setUp(self) -> None:
        self.universe = _universe()

    def test_company_names_resolve(self) -> None:
        for word, expected in (
            ("google", "GOOG"),
            ("berkshire", "BRK-B"),
            ("mainfreight", "MFT.NZ"),
            ("apple", "AAPL"),
        ):
            self.assertEqual(resolve_ticker(word, self.universe), expected, word)

    def test_symbols_still_resolve_as_before(self) -> None:
        self.assertEqual(resolve_ticker("AAPL", self.universe), "AAPL")
        self.assertEqual(resolve_ticker("mft", self.universe), "MFT.NZ")

    def test_untracked_and_ambiguous_stay_unresolved(self) -> None:
        resolved, unresolved = resolve_tickers(["TLK", "ishares"], self.universe)
        self.assertEqual(resolved, [])
        self.assertEqual(sorted(unresolved), ["ISHARES", "TLK"])

    def test_adjacent_transposition_typos_recover(self) -> None:
        """Finger slips are recoverable; "mhci" plainly means MCHI."""
        resolved, unresolved = resolve_tickers(["mhci", "brbk"], self.universe)
        self.assertEqual(sorted(resolved), ["BRK-B", "MCHI"])
        self.assertEqual(unresolved, [])

    def test_substitutions_are_not_recovered(self) -> None:
        """
        The whole point: "tlk" differs from "tlt" by a substitution, and TLT is a
        different asset. Only adjacent swaps are forgiven.
        """
        self.assertIsNone(resolve_ticker("tlk", self.universe))
        self.assertIsNone(resolve_ticker("appl", self.universe))

    def test_directly_typed_symbols_are_untouched(self) -> None:
        self.assertEqual(resolve_ticker("TLT", self.universe), "TLT")

    def test_short_tokens_are_not_transposed(self) -> None:
        """Three characters is too little signal to call a swap a typo."""
        self.assertIsNone(resolve_ticker("mft.", self.universe.copy() and ["MFTX", "XMFT"]))

    def test_missing_map_degrades_to_symbol_only(self) -> None:
        """A broken map must not break resolution, and must never cause a guess."""
        _alias_index.cache_clear()
        with patch("chatbot.ticker_resolver._ALIAS_FILE", "/nonexistent/aliases.json"):
            self.assertEqual(resolve_ticker("mft", self.universe), "MFT.NZ")
            self.assertIsNone(resolve_ticker("google", self.universe))
        _alias_index.cache_clear()


class TestProvenanceVerification(unittest.TestCase):
    def setUp(self) -> None:
        self.universe = _universe()

    def test_the_real_incident(self) -> None:
        """TLT is dropped; the two recoverable typos survive."""
        kept, guessed = verify_extracted_symbols(
            "what is the mark to market for mhci, tlk and brbk latest signals?",
            ["MCHI", "TLT", "BRK-B"],
            self.universe,
        )
        self.assertEqual(guessed, ["TLT"])
        self.assertEqual(sorted(kept), ["BRK-B", "MCHI"])

    def test_alias_backed_symbols_survive(self) -> None:
        kept, guessed = verify_extracted_symbols(
            "recent exit levels for google and nvda", ["GOOG", "NVDA"], self.universe
        )
        self.assertEqual(sorted(kept), ["GOOG", "NVDA"])
        self.assertEqual(guessed, [])

    def test_base_symbol_counts_as_literal(self) -> None:
        kept, _ = verify_extracted_symbols(
            "replace fph and mft that i sold", ["FPH.NZ", "MFT.NZ"], self.universe
        )
        self.assertEqual(sorted(kept), ["FPH.NZ", "MFT.NZ"])

    def test_history_supplies_provenance_for_followups(self) -> None:
        """"now calculate the mtm for those" must not lose the ticker from turn 1."""
        haystack = "show me the latest entry and exit signals for aapl\nnow calculate the mtm according to the last trade"
        kept, guessed = verify_extracted_symbols(haystack, ["AAPL"], self.universe)
        self.assertEqual(kept, ["AAPL"])
        self.assertEqual(guessed, [])

    def test_unsupported_symbol_is_dropped(self) -> None:
        kept, guessed = verify_extracted_symbols("show me signals", ["AAPL"], self.universe)
        self.assertEqual(kept, [])
        self.assertEqual(guessed, ["AAPL"])

    def test_empty_inputs_are_safe(self) -> None:
        self.assertEqual(verify_extracted_symbols("", ["AAPL"], self.universe), (["AAPL"], []))
        self.assertEqual(verify_extracted_symbols("text", [], self.universe), ([], []))


class TestUnresolvedNote(unittest.TestCase):
    def test_note_names_symbols_and_forbids_substitution(self) -> None:
        note = build_unresolved_ticker_note(["TLK", "BRBK"])
        assert note is not None
        self.assertIn("TLK", note)
        self.assertIn("different company", note)

    def test_no_note_when_empty(self) -> None:
        self.assertIsNone(build_unresolved_ticker_note([]))


if __name__ == "__main__":
    unittest.main()
