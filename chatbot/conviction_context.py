"""
Build the "SOURCE C" prompt block: MindWealth's own ranked buy/exit lists,
per-signal quality scores, conviction scores and fundamentals.

The chatbot's CSV pipeline never had access to any of this, so recommendation
questions ("what should I buy to replace FPH and MFT", "give me a signal quality
score") were answered from web text alone — or from prose the model invented —
even though the numbers exist, are computed nightly, and are served over HTTP.

Data comes from our own API (see ``chatbot/tools/mindwealth_api_client.py``):

    GET /signals/entries?book_id=model            ranked buy candidates
    GET /signals/exits?book_id=model              exit / sell candidates
    GET /signals/surface?report=outstanding-signals   Signal Quality Composite Score + tier
    GET /conviction/overlays/dates → …/{date}/score-sheet   conviction per signal
    GET /conviction/tickers/{ticker}              fundamentals snapshot

Every fetch degrades to "section omitted" rather than raising: this is
enrichment inside a job worker thread, not a hard dependency.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Sequence

from .config import (
    CONVICTION_CONTEXT_MAX_ROWS,
    CONVICTION_CONTEXT_TIMEOUT_SECONDS,
    CONVICTION_BOOK_ID,
    ENABLE_CONVICTION_CONTEXT,
    MINDWEALTH_API_BASE_URL,
)
from .tools.mindwealth_api_client import MindWealthAPIClient

logger = logging.getLogger(__name__)

# Questions for which this context is worth the extra HTTP latency. Mirrors
# ROUTER_SYSTEM rule 9 / ``llm_router._RECOMMENDATION_QUERY_RE``: recommendation,
# screening, replacement, quality-score and fundamentals asks.
_CONVICTION_RELEVANT_RE = re.compile(
    r"\b(buy|sell|add|exit|replace|replacement|recommend|recommendation|candidates?|"
    r"shortlist|screen(ing)?|alternatives?|substitutes?|swap|rotate|allocate|"
    r"conviction|fundamental(s|ly)?|quality\s+score|signal\s+quality|valuation|"
    r"pe\s+ratio|p/e|dividend|yield|roic|verdict|sizing|worth\s+(buying|adding|holding))\b",
    re.I,
)

# Terminology the model must not paraphrase or invent.
_SCORE_LEGEND = (
    "Field notes (use these numbers verbatim; do NOT invent a quality score):\n"
    "- 'Signal Quality Composite Score' (composite_score) is MindWealth's own signal "
    "quality metric, range approx -41 to +83 (NOT 0-100). Higher is better; negative "
    "scores are poor-quality signals.\n"
    "- 'tier' is a separate label. Two tier vocabularies exist in the pipeline "
    "(best/tA/ok/watch and tierc/exit); report the tier string exactly as given and do "
    "not translate it into a rating of your own.\n"
    "- 'conviction_score' = bq_raw (business quality) + valuation_tax, FS-capped. "
    "'verdict' and 'sizing_pct' come from the conviction engine.\n"
    "- forward_win_rate_pct is the forward-tested win rate; Gate A2b requires >= 60%.\n"
    "- For non-US tickers (.NZ, .AX, .NS, ...) 20-year P/E history is unavailable, so "
    "pe_percentile_20y is null and the FS/conviction score is computed WITHOUT the P/E "
    "percentile component. Say so when comparing a non-US name against a US name; do "
    "not present the two conviction scores as directly comparable."
)


def is_conviction_relevant(user_message: Optional[str]) -> bool:
    """True when the query is a recommendation / quality / fundamentals ask."""
    if not user_message or not str(user_message).strip():
        return False
    return bool(_CONVICTION_RELEVANT_RE.search(str(user_message)))


def _fmt(value: Any, digits: int = 2) -> str:
    """Compact scalar formatting; ``None`` becomes ``n/a``."""
    if value is None or value == "":
        return "n/a"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        return f"{value:.{digits}f}".rstrip("0").rstrip(".") if isinstance(value, float) else str(value)
    return str(value)


def _symbol_of(row: Dict[str, Any]) -> str:
    """Ticker from either the flat field or the compound signal column."""
    ticker = row.get("ticker")
    if ticker:
        return str(ticker)
    compound = row.get("Symbol, Signal, Signal Date/Price[$]") or ""
    return str(compound).split(",")[0].strip()


class ConvictionContextBuilder:
    """Assembles the SOURCE C text block from the local MindWealth API."""

    def __init__(self, client: Optional[MindWealthAPIClient] = None):
        self.client = client or MindWealthAPIClient(
            base_url=MINDWEALTH_API_BASE_URL or None,
            timeout=CONVICTION_CONTEXT_TIMEOUT_SECONDS,
        )
        self.book_id = CONVICTION_BOOK_ID

    # ── sections ────────────────────────────────────────────────────────────

    def _buy_candidates(self) -> Optional[str]:
        data = self.client.get("/signals/entries", {"book_id": self.book_id})
        rows = (data or {}).get("entries") or []
        if not rows:
            return None
        lines = [
            f"Ranked BUY candidates from the MindWealth model "
            f"(book={self.book_id}, as_of={(data or {}).get('as_of')}):"
        ]
        for row in rows[:CONVICTION_CONTEXT_MAX_ROWS]:
            lines.append(
                f"- rank {_fmt(row.get('rank'))}: {_symbol_of(row)} | "
                f"{row.get('function')} {row.get('interval')} {row.get('direction')} | "
                f"signal_date={row.get('signal_date')} | "
                f"Signal Quality Composite Score={_fmt(row.get('score'))} | "
                f"forward_win_rate={_fmt(row.get('forward_win_rate_pct'))}%"
            )
        return "\n".join(lines)

    def _exit_candidates(self) -> Optional[str]:
        data = self.client.get("/signals/exits", {"book_id": self.book_id})
        rows = (data or {}).get("exits") or []
        if not rows:
            return None
        lines = [
            f"EXIT / SELL candidates from the MindWealth model "
            f"(book={self.book_id}, as_of={(data or {}).get('as_of')}):"
        ]
        for row in rows[:CONVICTION_CONTEXT_MAX_ROWS]:
            lines.append(
                f"- rank {_fmt(row.get('rank'))}: {_symbol_of(row)} | "
                f"{row.get('function')} {row.get('interval')} {row.get('direction')} | "
                f"signal_date={row.get('signal_date')} | exit_type={row.get('exit_type')} | "
                f"closed_pnl={_fmt(row.get('closed_pnl_pct'))}% | "
                f"Signal Quality Composite Score={_fmt(row.get('score'))}"
            )
        return "\n".join(lines)

    def _conviction_score_sheet(self, assets: Optional[Sequence[str]]) -> Optional[str]:
        dates = self.client.get("/conviction/overlays/dates")
        if not dates:
            return None
        latest = dates[-1] if isinstance(dates, list) else None
        if not latest:
            return None
        data = self.client.get(f"/conviction/overlays/{latest}/score-sheet")
        rows = (data or {}).get("records") or []
        if not rows:
            return None

        wanted = {str(a).strip().upper() for a in (assets or []) if a}
        if wanted:
            focused = [r for r in rows if _symbol_of(r).upper() in wanted]
            rows = focused or rows

        lines = [f"Conviction engine score sheet (overlay date {latest}):"]
        for row in rows[:CONVICTION_CONTEXT_MAX_ROWS]:
            lines.append(
                f"- {_symbol_of(row)} | {row.get('Function')} | "
                f"business_type={row.get('business_type')} | "
                f"bq_raw={_fmt(row.get('bq_raw'))} | "
                f"valuation_tax={_fmt(row.get('valuation_tax'))} | "
                f"conviction_score={_fmt(row.get('conviction_score'))} | "
                f"fs_class={row.get('fs_class')} | "
                f"yield_trap={_fmt(row.get('yield_trap_warning'))} | "
                f"verdict={row.get('verdict')} | sizing_pct={_fmt(row.get('sizing_pct'))}"
            )
        return "\n".join(lines)

    def _signal_quality(self, assets: Optional[Sequence[str]]) -> Optional[str]:
        data = self.client.get("/signals/surface", {"report": "outstanding-signals"})
        rows = (data or {}).get("records") or []
        if not rows:
            return None

        wanted = {str(a).strip().upper() for a in (assets or []) if a}
        if wanted:
            rows = [r for r in rows if _symbol_of(r).upper() in wanted] or rows

        scored = [r for r in rows if r.get("composite_score") is not None]
        scored.sort(key=lambda r: r.get("composite_score") or 0, reverse=True)
        if not scored:
            return None

        lines = [
            f"Signal Quality Composite Scores on open signals "
            f"(report_date {(data or {}).get('report_date')}, top {CONVICTION_CONTEXT_MAX_ROWS} by score):"
        ]
        for row in scored[:CONVICTION_CONTEXT_MAX_ROWS]:
            lines.append(
                f"- {_symbol_of(row)} | {row.get('function')} | "
                f"composite_score={_fmt(row.get('composite_score'))} | tier={row.get('tier')} | "
                f"mtm={_fmt(row.get('mtm_pct'))}% | er_annualized={_fmt(row.get('er_annualized'))} | "
                f"conviction_bq={_fmt(row.get('conviction_bq_score'))} | "
                f"fs_class={row.get('conviction_fs_class')}"
            )
        return "\n".join(lines)

    def _fundamentals(self, assets: Optional[Sequence[str]]) -> Optional[str]:
        if not assets:
            return None
        lines: List[str] = []
        for asset in list(assets)[:8]:
            record = self.client.get(f"/conviction/tickers/{asset}", {"fields": "full"})
            if not isinstance(record, dict) or not record:
                continue
            coverage = record.get("data_coverage") or {}
            lines.append(
                f"- {asset} | sector={record.get('sector')} | "
                f"business_type={record.get('business_type')} | "
                f"pe_ttm={_fmt(record.get('pe_ttm'))} | "
                f"pe_percentile_20y={_fmt(record.get('pe_percentile_20y'))} | "
                f"roic_5y_avg={_fmt(record.get('roic_5y_avg'))} | "
                f"owner_earnings_yield={_fmt(record.get('owner_earnings_yield'))} | "
                f"dividend_yield={_fmt(record.get('dividend_yield_current'))} | "
                f"market_cap={_fmt(record.get('market_cap'), 0)} | "
                f"bq_raw={_fmt(record.get('bq_raw'))} | "
                f"conviction_score={_fmt(record.get('conviction_score'))} | "
                f"data_coverage={_fmt(coverage.get('coverage_ratio'))}"
            )
        if not lines:
            return None
        return "Fundamentals snapshot (conviction engine):\n" + "\n".join(lines)

    # ── entry point ─────────────────────────────────────────────────────────

    def build(
        self,
        user_message: str,
        assets: Optional[Sequence[str]] = None,
    ) -> Optional[str]:
        """
        Return the SOURCE C block, or ``None`` when disabled, irrelevant, or when
        every section failed to fetch.
        """
        if not ENABLE_CONVICTION_CONTEXT:
            return None
        if not is_conviction_relevant(user_message):
            return None

        sections: List[str] = []
        for name, builder in (
            ("buy_candidates", lambda: self._buy_candidates()),
            ("exit_candidates", lambda: self._exit_candidates()),
            ("signal_quality", lambda: self._signal_quality(assets)),
            ("conviction_score_sheet", lambda: self._conviction_score_sheet(assets)),
            ("fundamentals", lambda: self._fundamentals(assets)),
        ):
            try:
                block = builder()
            except Exception as exc:  # never break the answer over enrichment
                logger.warning(f"Conviction context section '{name}' failed: {exc}")
                continue
            if block:
                sections.append(block)

        if not sections:
            logger.info("Conviction context: no sections available")
            return None

        logger.info(f"Conviction context: built {len(sections)} section(s)")
        return (
            "=== SOURCE C — MINDWEALTH CONVICTION & SIGNAL QUALITY (INTERNAL) ===\n"
            + "\n\n".join(sections)
            + "\n\n"
            + _SCORE_LEGEND
        )


def build_conviction_context(
    user_message: str,
    assets: Optional[Sequence[str]] = None,
) -> Optional[str]:
    """Module-level convenience wrapper around :class:`ConvictionContextBuilder`."""
    try:
        return ConvictionContextBuilder().build(user_message, assets=assets)
    except Exception as exc:
        logger.warning(f"Conviction context unavailable: {exc}")
        return None
