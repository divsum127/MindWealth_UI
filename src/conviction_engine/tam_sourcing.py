"""TAM / Dim 15 (reinvestment runway) three-tier sourcing (item 20, carried forward from
the 28 July note's Section 12.1).

Rohit's follow-up on Dim 15 split what the original spec treated as one "agentic
dimension" into three sourcing tiers with genuinely different mechanics:

1. **Structured, no search** — revenue backlog (``RevenueRemainingPerformanceObligation``)
   is a tagged XBRL fact filed every 10-Q, same tier as the buyback/adjusted-EPS pulls
   (``capital_allocation.py``, ``adjusted_eps.py``) — a straight SEC EDGAR API call, zero
   agentic component. Built here.
2. **Text extraction from transcript** — a company-stated TAM figure (e.g. "$3-4T AI
   infrastructure spend by 2030") is spoken management commentary, not a filed number —
   there's no XBRL tag for it. Requires a light NLP/web-search step. Built in
   ``agent_dims.compute_reinvestment_runway_agent`` (Claude web search).
3. **Web search + fetch of a public press release** — an independent third-party market
   estimate (IDC/Gartner/Synergy Research/SIA-Deloitte-style headline numbers, published
   free specifically to be cited) is ordinary search-then-fetch, same method that
   unblocked Gartner/G2 once the search-first sequence was used. Built in the same
   ``compute_reinvestment_runway_agent`` call (asked for alongside the company figure).

Tier 1 is mechanical and belongs in this module; tiers 2-3 are agentic and live in
``agent_dims.py`` — this module's ``fetch_revenue_backlog_xbrl`` is called first and its
result is threaded into the Tier-2/3 prompt as context (so the agent can use the backlog
as the demand proxy for companies that don't publish a TAM number, e.g. GOOGL per the
note's own worked example) and merged into the final bundle in ``run_agent_dimensions``.
"""

from __future__ import annotations

import logging
from typing import Any

from .pe_history_fmp import is_us_ticker
from .pe_history_sec import SEC_BASE_URL, _get_with_backoff, get_cik_for_ticker  # noqa: SLF001 (internal reuse, same package)

logger = logging.getLogger(__name__)

# Tagged under us-gaap; reported in a plain currency unit (USD), not USD/shares like the
# EPS concepts pe_history_sec.py reads — hence this module's own small fetch helper
# rather than reusing `_fetch_concept_facts` (which assumes a `.../shares` unit).
BACKLOG_CONCEPT = "RevenueRemainingPerformanceObligation"


def fetch_revenue_backlog_xbrl(ticker: str) -> dict[str, Any] | None:
    """Tier 1: most-recent ``RevenueRemainingPerformanceObligation`` XBRL fact for a US
    ticker — the company's total remaining performance obligation ("backlog") as of its
    latest 10-Q, straight from SEC EDGAR. Returns ``None`` when the ticker isn't a US
    filer, isn't in SEC's ticker->CIK map, or simply doesn't tag this concept (common for
    non-subscription/non-contract-revenue businesses — this is a real "not applicable"
    result, not a fetch failure)."""
    if not ticker or not is_us_ticker(ticker):
        return None
    cik = get_cik_for_ticker(ticker)
    if not cik:
        return None

    url = f"{SEC_BASE_URL}/api/xbrl/companyconcept/CIK{cik}/us-gaap/{BACKLOG_CONCEPT}.json"
    resp = _get_with_backoff(url)
    if resp is None or resp.status_code != 200:
        return None
    try:
        data = resp.json()
    except Exception:
        return None

    units = (data or {}).get("units") if isinstance(data, dict) else None
    facts = (units or {}).get("USD")
    if not facts:
        return None

    # Point-in-time facts (no start/end duration, just an instantaneous `end` snapshot) —
    # take the single most-recently-filed value, not a TTM/duration reconstruction.
    latest = max(facts, key=lambda f: (str(f.get("end") or ""), str(f.get("filed") or "")))
    value = latest.get("val")
    if value is None:
        return None
    return {
        "backlog_usd": float(value),
        "as_of": latest.get("end"),
        "filed": latest.get("filed"),
        "form": latest.get("form"),
        "source": "sec_xbrl_RevenueRemainingPerformanceObligation",
    }
