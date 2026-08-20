"""
Regression tests for the "no signals in a buy/replace answer" bug.

The NZ replacement question routed to WEB_RAG, which answers purely from web
text and never touches the signal pipeline. Three defects combined:

1. the router left needs_internal_signal_data=false (no rule covered
   recommendation wording),
2. bare "FPH"/"MFT" could not match the stored "FPH.NZ"/"MFT.NZ",
3. entry fetches forced open-signals-only, excluding the very names the user
   said they had sold.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from chatbot.agents.llm_router import (  # noqa: E402
    apply_internal_level_override,
    apply_recommendation_internal_override,
)
from chatbot.smart_data_fetcher import _mentions_closed_position  # noqa: E402
from chatbot.ticker_resolver import resolve_ticker, resolve_tickers  # noqa: E402

# The two messages that actually failed in the UI.
NZ_REPLACEMENT_QUERY = (
    "what new zealand stocks do i buy to replace fph and mft that i sold recently ? why?"
)
SIGNAL_QUALITY_QUERY = (
    "based on signals from our model what should we buy (new buy signals or exit sell "
    "signals ) ... consider also fundamentals and give me a signal quality score"
)

UNIVERSE = ["AAPL", "AIA.NZ", "FPH.NZ", "MFT.NZ", "SPK.NZ", "FRW.NZ", "WPM", "WPM.TO"]


# ── router override ──────────────────────────────────────────────────────────

def test_nz_replacement_query_forces_internal_and_keeps_web():
    """Must land on HYBRID: internal signals primary, web supplementary."""
    internal, web, queries, reasoning = apply_recommendation_internal_override(
        NZ_REPLACEMENT_QUERY, internal=False, web=True, queries=["nzx stocks"], reasoning="web only"
    )
    assert internal is True
    assert web is True, "web must stay on so the route is HYBRID, not INTERNAL"
    assert queries == ["nzx stocks"]
    assert "override" in reasoning


def test_signal_quality_query_forces_internal():
    internal, web, _queries, _reasoning = apply_recommendation_internal_override(
        SIGNAL_QUALITY_QUERY, internal=False, web=True, queries=None, reasoning=""
    )
    assert internal is True
    assert web is True


def test_conversational_and_news_queries_are_untouched():
    for query in (
        "what does TRENDPULSE mean",
        "summarize our chat",
        "what happened to the fed yesterday",
        "show me breadth for last week",
    ):
        internal, web, _q, _r = apply_recommendation_internal_override(
            query, internal=False, web=True, queries=None, reasoning=""
        )
        assert internal is False, f"should not have fired for: {query}"


def test_level_override_still_wins_and_suppresses_web():
    """A level/ladder query must stay internal-only (web off), per ROUTER_SYSTEM rule 8."""
    query = "what is the resistance level on FPH"
    internal, web, queries, reasoning = apply_internal_level_override(
        query, internal=False, web=True, queries=["fph resistance"], reasoning=""
    )
    internal, web, queries, reasoning = apply_recommendation_internal_override(
        query, internal, web, queries, reasoning
    )
    assert internal is True
    assert web is False, "recommendation override must not re-enable web search"


# ── ticker resolution ────────────────────────────────────────────────────────

def test_bare_nz_tickers_resolve_to_suffixed_symbols():
    assert resolve_ticker("FPH", UNIVERSE) == "FPH.NZ"
    assert resolve_ticker("MFT", UNIVERSE) == "MFT.NZ"
    assert resolve_ticker("mft", UNIVERSE) == "MFT.NZ"


def test_already_canonical_symbol_passes_through():
    assert resolve_ticker("FPH.NZ", UNIVERSE) == "FPH.NZ"
    assert resolve_ticker("AAPL", UNIVERSE) == "AAPL"


def test_ambiguous_base_is_left_unresolved():
    """WPM exists both bare (US) and as WPM.TO — never guess."""
    assert resolve_ticker("WPM", UNIVERSE) == "WPM"  # exact match wins
    assert resolve_ticker("XYZ", UNIVERSE) is None


def test_unknown_symbol_reported_not_silently_dropped():
    """FRE does not exist in the universe (Freightways is FRW.NZ)."""
    resolved, unresolved = resolve_tickers(["FPH", "MFT", "FRE"], UNIVERSE)
    assert resolved == ["FPH.NZ", "MFT.NZ"]
    assert unresolved == ["FRE"]


def test_resolution_is_deduplicated():
    resolved, _unresolved = resolve_tickers(["FPH", "FPH.NZ", "fph"], UNIVERSE)
    assert resolved == ["FPH.NZ"]


# ── sold-position handling ───────────────────────────────────────────────────

def test_sold_and_replace_wording_relaxes_open_only_filter():
    assert _mentions_closed_position(NZ_REPLACEMENT_QUERY) is True
    for query in (
        "what should i replace MFT with",
        "i sold FPH last week, now what",
        "no longer hold SPK",
    ):
        assert _mentions_closed_position(query) is True


def test_plain_buy_question_keeps_open_only_filter():
    for query in (
        "what are my open entry signals",
        "show me signals from last month",
    ):
        assert _mentions_closed_position(query) is False
