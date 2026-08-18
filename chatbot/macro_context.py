"""
Build the "SOURCE D" prompt block: MindWealth's own macro regime, Runic combos,
SSI sentiment layers and portfolio risk posture.

The chatbot could reach signals and conviction but had no macro feed at all, so
"what is the current macro regime and which combo is dominant?" was answered
from web search — and the web answer ("transitional, mixed signals") directly
contradicted our own nightly output (Combo F dominant, week 20 of 26, TACTICAL
EASY MONEY). Every number here is computed nightly and served over HTTP; none of
it was reachable from a chat turn.

Data comes from our own API (see ``chatbot/tools/mindwealth_api_client.py``):

    GET /macro/runic/nightly    regime, dominant signal, active/watch combos
    GET /macro/ssi/summary      SSI level, percentile, multiplier, Layer 2 state
    GET /portfolio/risk         cluster weights, breaches, conviction summary

Every fetch degrades to "section omitted" rather than raising: this is
enrichment inside a job worker thread, not a hard dependency.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from .config import (
    CONVICTION_CONTEXT_TIMEOUT_SECONDS,
    ENABLE_MACRO_CONTEXT,
    MACRO_CONTEXT_BOOK_ID,
    MINDWEALTH_API_BASE_URL,
)
from .tools.mindwealth_api_client import MindWealthAPIClient

logger = logging.getLogger(__name__)

# Mirrors ``llm_router._MACRO_QUERY_RE``. Kept as its own copy so the context
# builder stays usable when the router is bypassed (presets, direct calls).
_MACRO_RELEVANT_RE = re.compile(
    r"\b(macro\s+(regime|backdrop|picture|view)|current\s+regime|regime\b)"
    r"|\bcombo\s*[a-g]?\b|\brunic\b"
    r"|\b(ssi|super\s*sentiment|sentiment\s+(index|layer|regime))\b"
    r"|\b(fear\s*(and|&|/)?\s*greed|naaim|aaii|put[- ]?call)\b"
    r"|\b(market\s+breadth|breadth)\b"
    r"|\b(vix|vxts|cape|nfci|walcl|liquidity\s+(regime|conditions))\b"
    r"|\b(fed\s+cycle|yield\s+curve|steepening|inversion)\b"
    r"|\b(position\s+sizing|sizing\s+multiplier|portfolio\s+(nav|risk|exposure|allocation)|"
    r"cluster\s+weight|drawdown)\b"
    r"|\bsystem\s+posture\b|\bdominant\s+signal\b"
    r"|\bmarket\s+(outlook|conditions|environment)\b",
    re.I,
)

_MACRO_LEGEND = (
    "Field notes (quote these values verbatim; do NOT substitute web commentary "
    "for MindWealth's own regime call):\n"
    "- 'dominant_signal' is the Runic combo the engine ranks highest today; "
    "combos are lettered A-G and each has its own validated hit rate and horizon.\n"
    "- A combo in WATCH is not firing; it has met some legs and not others. Do "
    "not present a WATCH combo as an active signal.\n"
    "- 'ssi_multiplier' scales position sizing. Layer 2 CONFIRMED means the "
    "sentiment gate passed; it is not a directional view on its own.\n"
    "- 'vix_bypass' true means the SSI multiplier is being discarded for sizing "
    "that day — say so explicitly if it is set.\n"
    "- If the web (SOURCE B) describes a different regime, MindWealth's regime "
    "here is the answer; surface the disagreement rather than adopting the web's."
)


def is_macro_relevant(user_message: Optional[str]) -> bool:
    """True when the query is a macro / regime / sentiment / portfolio ask."""
    if not user_message or not str(user_message).strip():
        return False
    return bool(_MACRO_RELEVANT_RE.search(str(user_message)))


def _fmt(value: Any) -> str:
    if value is None or value == "":
        return "n/a"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value)


def _combo_line(combo: Dict[str, Any]) -> str:
    name = combo.get("combo") or combo.get("runic_combo") or combo.get("id") or "?"
    bits = [f"Combo {name}"]
    for key, label in (
        ("label", ""),
        ("status", "status"),
        ("week", "week"),
        ("weeks_total", "of"),
        ("direction", ""),
        ("hit_rate", "hit_rate"),
        ("horizon", "horizon"),
    ):
        val = combo.get(key)
        if val in (None, ""):
            continue
        bits.append(f"{label}={_fmt(val)}" if label else _fmt(val))
    return "- " + " | ".join(bits)


class MacroContextBuilder:
    """Assembles the SOURCE D text block from the local MindWealth API."""

    def __init__(self, client: Optional[MindWealthAPIClient] = None):
        self.client = client or MindWealthAPIClient(
            base_url=MINDWEALTH_API_BASE_URL or None,
            timeout=CONVICTION_CONTEXT_TIMEOUT_SECONDS,
        )
        self.book_id = MACRO_CONTEXT_BOOK_ID

    def _regime(self) -> Optional[str]:
        data = self.client.get("/macro/runic/nightly")
        if not data:
            return None
        lines = [
            f"MindWealth macro regime (Runic nightly, as_of={_fmt(data.get('date'))}):",
            f"- dominant_signal: {_fmt(data.get('dominant_signal'))} "
            f"({_fmt(data.get('dominant_reason'))})",
            f"- regime: {_fmt(data.get('regime'))}",
            f"- brave_fearful: {_fmt(data.get('brave_fearful_display') or data.get('brave_fearful'))}",
            f"- system_recommendation: {_fmt(data.get('system_recommendation'))}",
            f"- ssi_multiplier: {_fmt(data.get('ssi_multiplier'))} | "
            f"layer2: {_fmt(data.get('ssi_layer2_status'))} | "
            f"vix_bypass: {_fmt(data.get('vix_bypass'))}",
        ]
        active = data.get("active_combos") or []
        watch = data.get("watch_combos") or []
        if active:
            lines.append("ACTIVE combos:")
            lines += [_combo_line(c) for c in active if isinstance(c, dict)]
        if watch:
            lines.append("WATCH combos (legs partially met — NOT firing):")
            lines += [_combo_line(c) for c in watch if isinstance(c, dict)]
        narrative = data.get("narrative")
        if narrative:
            lines.append(f"Nightly narrative (first 1200 chars):\n{str(narrative)[:1200]}")
        return "\n".join(lines)

    def _ssi(self) -> Optional[str]:
        data = self.client.get("/macro/ssi/summary")
        if not data:
            return None
        return "\n".join([
            f"Super Sentiment Index (as_of={_fmt(data.get('date'))}):",
            f"- ssi_level: {_fmt(data.get('ssi_level'))} | "
            f"5y percentile: {_fmt(data.get('ssi_percentile_5y'))}",
            f"- multiplier: {_fmt(data.get('ssi_multiplier'))} "
            f"({_fmt(data.get('ssi_multiplier_label'))}), raw {_fmt(data.get('ssi_multiplier_raw'))}",
            f"- ceiling term: {_fmt(data.get('ssi_ceiling_term_label') or data.get('ssi_ceiling_term'))}",
            f"- layer2: {_fmt(data.get('layer2_status'))} "
            f"({_fmt(data.get('layer2_confirmed_count'))}/{_fmt(data.get('layer2_required'))} confirmed)",
        ])

    def _portfolio_risk(self) -> Optional[str]:
        data = self.client.get("/portfolio/risk", {"book_id": self.book_id})
        if not data:
            return None
        lines = [f"Portfolio risk posture (book={self.book_id}, as_of={_fmt(data.get('date'))}):"]
        weights = data.get("cluster_weights") or {}
        if isinstance(weights, dict) and weights:
            top = sorted(
                ((k, v) for k, v in weights.items() if isinstance(v, (int, float))),
                key=lambda kv: kv[1],
                reverse=True,
            )[:6]
            lines.append("- largest cluster weights: " + ", ".join(f"{k} {_fmt(v)}" for k, v in top))
        breaches = data.get("breaches") or []
        lines.append(f"- breaches: {len(breaches)}")
        for b in breaches[:5]:
            if isinstance(b, dict):
                lines.append(f"  · {_fmt(b.get('label') or b.get('cluster'))}: {_fmt(b.get('detail') or b.get('weight'))}")
        summary = data.get("conviction_summary")
        if isinstance(summary, dict) and summary:
            lines.append("- conviction summary: " + ", ".join(f"{k}={_fmt(v)}" for k, v in list(summary.items())[:8]))
        return "\n".join(lines)

    def build(self, user_message: str) -> Optional[str]:
        """Return the SOURCE D block, or ``None`` when disabled/irrelevant/empty."""
        if not ENABLE_MACRO_CONTEXT:
            return None
        if not is_macro_relevant(user_message):
            return None

        sections: List[str] = []
        for name, builder in (
            ("regime", self._regime),
            ("ssi", self._ssi),
            ("portfolio_risk", self._portfolio_risk),
        ):
            try:
                block = builder()
            except Exception as exc:  # never break the answer over enrichment
                logger.warning(f"Macro context section '{name}' failed: {exc}")
                block = None
            if block:
                sections.append(block)

        if not sections:
            logger.warning("Macro context: every section failed or was empty")
            return None

        logger.info(f"Macro context: built {len(sections)} section(s)")
        return (
            "=== SOURCE D — MINDWEALTH MACRO REGIME & SENTIMENT (INTERNAL) ===\n"
            + "\n\n".join(sections)
            + "\n\n"
            + _MACRO_LEGEND
        )


def build_macro_context(user_message: str) -> Optional[str]:
    """Module-level convenience wrapper around :class:`MacroContextBuilder`."""
    try:
        return MacroContextBuilder().build(user_message)
    except Exception as exc:
        logger.warning(f"Macro context unavailable: {exc}")
        return None
