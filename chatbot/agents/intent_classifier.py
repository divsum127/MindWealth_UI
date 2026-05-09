"""
Intent Classification Agent for MindWealth Trading Chatbot.

Two-stage classification:
  Stage 1 – Fast rule-based pre-check   (zero API cost, ~0 ms)
  Stage 2 – LLM disambiguation via gpt-4o-mini for ambiguous queries
"""

import re
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .llm_router import (
    mtm_margin_calculation_needs_live_prices,
    query_implies_portfolio_or_signals,
)

logger = logging.getLogger(__name__)

# ── Intent constants ────────────────────────────────────────────────────────────
INTENT_SNAPSHOT           = "SNAPSHOT"
INTENT_PERFORMANCE_REVIEW = "PERFORMANCE_REVIEW"
INTENT_SIGNAL_LOOKUP      = "SIGNAL_LOOKUP"
INTENT_COMPARISON         = "COMPARISON"
INTENT_DIAGNOSTICS        = "DIAGNOSTICS"
INTENT_MARKET_OVERVIEW    = "MARKET_OVERVIEW"
INTENT_TARGET_TRACKING    = "TARGET_TRACKING"
INTENT_CONVERSATIONAL     = "CONVERSATIONAL"
INTENT_RESEARCH           = "RESEARCH"
INTENT_WEB_QUERY          = "WEB_QUERY"

ALL_INTENTS = [
    INTENT_SNAPSHOT, INTENT_PERFORMANCE_REVIEW, INTENT_SIGNAL_LOOKUP,
    INTENT_COMPARISON, INTENT_DIAGNOSTICS, INTENT_MARKET_OVERVIEW,
    INTENT_TARGET_TRACKING, INTENT_CONVERSATIONAL, INTENT_RESEARCH,
    INTENT_WEB_QUERY,
]

# Intent badge labels and colours used by the UI
INTENT_LABELS: Dict[str, str] = {
    INTENT_SNAPSHOT:           "Snapshot",
    INTENT_PERFORMANCE_REVIEW: "Performance Review",
    INTENT_SIGNAL_LOOKUP:      "Signal Lookup",
    INTENT_COMPARISON:         "Comparison",
    INTENT_DIAGNOSTICS:        "Diagnostics",
    INTENT_MARKET_OVERVIEW:    "Market Overview",
    INTENT_TARGET_TRACKING:    "Target Tracking",
    INTENT_CONVERSATIONAL:     "Conversational",
    INTENT_RESEARCH:           "Research",
    INTENT_WEB_QUERY:          "Web Search",
}

# ── High-confidence keyword patterns (compiled once) ───────────────────────────
_RAW_RULES: Dict[str, List[str]] = {
    INTENT_CONVERSATIONAL: [
        r"\bwhat (is|are|does)\b",
        r"\bhow (does|do|is|are)\b",
        r"\bexplain\b",
        r"\bdefine\b",
        r"\bcan you (tell|explain|clarify|summarize)\b",
        r"\bwhat'?s? the difference between\b",
        r"\bwhat does .{1,30} mean\b",
    ],
    INTENT_WEB_QUERY: [
        r"\b(latest news|breaking news|news on|news about|news for)\b",
        r"\b(recent news|current news|today.s news)\b",
        r"\bearnings (report|call|announcement|this week|today|season)\b",
        r"\b(announced|IPO|macro|inflation|recession|gdp|cpi|ppi)\b",
        r"\b(Fed|Federal Reserve|interest rate|rate cut|rate hike)\b",
        r"\blive (price|stock price|market)\b",
        r"\bwhat happened (to|with)\b",
        r"\btoday.s (market|price|news)\b(?!.*signal)",
        r"\bany (news|updates|developments|announcements)\b",
    ],
    INTENT_TARGET_TRACKING: [
        r"\b(F-Stack|f stack|fstack)\b",
        r"\btargets? (achieved|hit|reached|met)\b",
        r"\bremaining (potential |exit )?target\b",
        r"\bdistance to target\b",
        r"\bportfolio target\b",
        r"\bacquired target\b",
    ],
    INTENT_MARKET_OVERVIEW: [
        r"\bmarket breadth\b",
        r"\boverall market\b",
        r"\bbullish (vs|versus|ratio|asset|signal)\b",
        r"\bbearish (vs|versus|ratio|asset|signal)\b",
        r"\bmarket (regime|conditions|overview|health|sentiment)\b",
        r"\bhow is the (market|overall market)\b",
    ],
    INTENT_COMPARISON: [
        r"\bvs\.?\b",
        r"\bversus\b",
        r"\bcompare\b",
        r"\bcontrast\b",
        r"\bwhich is better\b",
        r"\bbetter performing\b",
        r"\bside.by.side\b",
    ],
    INTENT_RESEARCH: [
        r"\bcomprehensive\b",
        r"\bfull analysis\b",
        r"\bdeep dive\b",
        r"\bdeep-dive\b",
        r"\binvestigate\b",
        r"\bthorough\b",
        r"\bcomplete picture\b",
        r"\bend.to.end analysis\b",
    ],
    INTENT_PERFORMANCE_REVIEW: [
        r"\bwin rate\b",
        r"\bCAGR\b",
        r"\bsharpe\b",
        r"\bbacktest",
        r"\brealized return\b",
        r"\bhistorical performance\b",
        r"\bhow has .{1,40} perform",
        r"\btrack record\b",
        r"\bstrategy performance\b",
    ],
    INTENT_SIGNAL_LOOKUP: [
        r"\bfind (all )?signals?\b",
        r"\bshow (me )?(all |entry |exit |breadth )?(signals?|positions?) for\b",
        r"\blist (all )?signals?\b",
        r"\bfetch signals?\b",
        r"\bget (me )?(all )?(signals?|positions?|entries|exits)\b",
        r"\bsignals? (from|for|in) .{1,40}(date|week|month|year)\b",
        r"\bwhich signals? fired\b",
        r"\bshow (entry|exit|breadth) signals?\b",
    ],
}

_COMPILED_RULES: Dict[str, List[re.Pattern]] = {
    intent: [re.compile(pat, re.IGNORECASE) for pat in patterns]
    for intent, patterns in _RAW_RULES.items()
}

_KNOWN_FUNCTIONS = [
    "ALTITUDE ALPHA", "BAND MATRIX", "BASELINEDIVERGENCE",
    "FRACTAL TRACK", "OSCILLATOR DELTA", "PULSEGAUGE",
    "SIGMASHELL", "TRENDPULSE",
]
_KNOWN_SIGNAL_TYPES = ["entry", "exit", "portfolio_target_achieved", "breadth", "claude_report"]

_TICKER_STOPWORDS = {
    "I", "AI", "US", "NZ", "TO", "OK", "ML", "API", "LLM", "CAGR", "MTM",
    "SBI", "ROI", "PE", "EPS", "ETF", "IPO", "YTD", "ATH",
}


# ── Data classes ────────────────────────────────────────────────────────────────

@dataclass
class DataScopeHint:
    tickers_mentioned: List[str] = field(default_factory=list)
    functions_mentioned: List[str] = field(default_factory=list)
    date_range_mentioned: Optional[Tuple[str, str]] = None
    signal_types_mentioned: List[str] = field(default_factory=list)


@dataclass
class IntentResult:
    primary_intent: str
    confidence: float
    is_hybrid: bool
    secondary_intent: Optional[str]
    reasoning: str
    data_scope_hint: DataScopeHint
    classified_by: str                        # "rules" | "llm" | "fallback"
    web_search_queries: Optional[List[str]] = None

    @property
    def label(self) -> str:
        return INTENT_LABELS.get(self.primary_intent, self.primary_intent)


# ── Classifier ──────────────────────────────────────────────────────────────────

class IntentClassifier:
    """
    Two-stage intent classifier.

    Stage 1: Rule-based pattern matching — returns immediately with no API call
             when a pattern fires with high confidence.
    Stage 2: gpt-4o-mini disambiguation — only called when rules are ambiguous
             or produce no match.
    """

    _CLASSIFICATION_PROMPT = """You are classifying a trading chatbot query for MindWealth.
The chatbot works with internal trading signal data (entry/exit signals, portfolio targets, market breadth)
and can also search the web for live financial information.

AVAILABLE INTENTS:
- SNAPSHOT           : Current state / today's data / open positions right now
- PERFORMANCE_REVIEW : Historical stats, win rates, CAGR, Sharpe, backtests
- SIGNAL_LOOKUP      : Find specific signals for a ticker, function, or date range
- COMPARISON         : Compare 2+ entities — strategies, tickers, time periods
- DIAGNOSTICS        : Why/how questions, root cause, explain anomalies
- MARKET_OVERVIEW    : Market breadth, overall market health, bullish/bearish ratios
- TARGET_TRACKING    : Portfolio targets, F-Stack levels, achieved/remaining targets
- CONVERSATIONAL     : Educational, definitional questions — NO data needed
- RESEARCH           : Multi-step comprehensive analysis, deep dives
- WEB_QUERY          : News, live prices, earnings, external financial data

CONVERSATION CONTEXT (last 2 turns, may be empty):
{context}

CURRENT USER QUERY:
{query}

Return ONLY a valid JSON object — no extra text, no markdown fences:
{{
  "primary_intent": "INTENT_NAME",
  "confidence": 0.85,
  "is_hybrid": false,
  "secondary_intent": null,
  "reasoning": "one concise sentence",
  "web_search_queries": null,
  "data_scope_hint": {{
    "tickers_mentioned": [],
    "functions_mentioned": [],
    "signal_types_mentioned": []
  }}
}}

Rules:
- If is_hybrid is true, set secondary_intent (e.g. primary=SIGNAL_LOOKUP + secondary=WEB_QUERY)
- If primary_intent is WEB_QUERY, populate web_search_queries with 1-3 targeted search strings
  including the current year (2026) where relevant
- web_search_queries must be null for non-WEB_QUERY intents
- confidence should reflect how certain you are (0.0 – 1.0)
- Mark-to-market (MTM) margin or margin requirements based on **current** marks need live prices:
  use WEB_QUERY alone if only external/public numbers apply; use HYBRID (SIGNAL_LOOKUP + WEB_QUERY)
  if the user ties it to their signals, positions, or portfolio."""

    def __init__(self, api_key: Optional[str] = None, openai_model: str = "gpt-4o-mini"):
        self._api_key = api_key
        self._model = openai_model
        self._client = None

        if api_key:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=api_key)
                logger.info("IntentClassifier: OpenAI client ready")
            except Exception as exc:
                logger.warning(f"IntentClassifier: OpenAI init failed: {exc}")

    # ── Public API ──────────────────────────────────────────────────────────────

    def classify(
        self,
        query: str,
        last_two_turns: Optional[List[Dict]] = None,
    ) -> IntentResult:
        """
        Classify user intent. Rule-based first; LLM fallback for ambiguous queries.
        """
        query = (query or "").strip()

        if mtm_margin_calculation_needs_live_prices(query):
            hint = self._extract_scope_hint(query)
            ticks = hint.tickers_mentioned
            if ticks:
                web_qs = [f"{t} stock price quote live today 2026" for t in ticks[:2]]
            else:
                web_qs = [query[:200]]
            web_qs = web_qs[:3]
            if query_implies_portfolio_or_signals(query):
                return IntentResult(
                    primary_intent=INTENT_SIGNAL_LOOKUP,
                    confidence=0.92,
                    is_hybrid=True,
                    secondary_intent=INTENT_WEB_QUERY,
                    reasoning=(
                        "MTM/margin calculation requires live marks — hybrid web + signal data"
                    ),
                    data_scope_hint=hint,
                    classified_by="rules",
                    web_search_queries=web_qs,
                )
            return IntentResult(
                primary_intent=INTENT_WEB_QUERY,
                confidence=0.90,
                is_hybrid=False,
                secondary_intent=None,
                reasoning="MTM/margin calculation requires live prices from web",
                data_scope_hint=hint,
                classified_by="rules",
                web_search_queries=web_qs,
            )

        rule_result = self._apply_rules(query)
        if rule_result is not None:
            intent, confidence = rule_result
            logger.info(f"[INTENT/rules] {intent} ({confidence:.2f}): {query[:80]}")
            return IntentResult(
                primary_intent=intent,
                confidence=confidence,
                is_hybrid=False,
                secondary_intent=None,
                reasoning=f"Matched keyword pattern for {intent}",
                data_scope_hint=self._extract_scope_hint(query),
                classified_by="rules",
                web_search_queries=(
                    self._default_web_queries(query) if intent == INTENT_WEB_QUERY else None
                ),
            )

        return self._classify_with_llm(query, last_two_turns or [])

    # ── Stage 1 — Rule-based ────────────────────────────────────────────────────

    def _apply_rules(self, query: str) -> Optional[Tuple[str, float]]:
        """Return (intent, confidence) if a clear rule matches, else None."""
        matches: Dict[str, int] = {}
        for intent, patterns in _COMPILED_RULES.items():
            for pat in patterns:
                if pat.search(query):
                    matches[intent] = matches.get(intent, 0) + 1

        if not matches:
            return None

        if len(matches) == 1:
            return next(iter(matches)), 0.90

        sorted_m = sorted(matches.items(), key=lambda x: x[1], reverse=True)
        top_intent, top_count = sorted_m[0]
        _, second_count = sorted_m[1]

        if top_count > second_count:
            return top_intent, 0.82

        return None  # Tied — fall through to LLM

    # ── Stage 2 — LLM disambiguation ───────────────────────────────────────────

    def _classify_with_llm(
        self,
        query: str,
        last_two_turns: List[Dict],
    ) -> IntentResult:
        if not self._client:
            logger.warning("IntentClassifier: no OpenAI client — defaulting to SIGNAL_LOOKUP")
            return self._fallback(query, "No OpenAI client available")

        context_parts = []
        for msg in last_two_turns[-4:]:
            role = msg.get("role", "")
            content = str(msg.get("content", ""))[:300]
            if role in ("user", "assistant"):
                context_parts.append(f"{role.upper()}: {content}")
        context = "\n".join(context_parts) or "(none)"

        prompt = self._CLASSIFICATION_PROMPT.format(query=query, context=context)

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_completion_tokens=350,
                temperature=0,
            )
            raw = response.choices[0].message.content.strip()
            if "```" in raw:
                raw = re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()
            data = json.loads(raw)
        except Exception as exc:
            logger.error(f"IntentClassifier LLM call failed: {exc}")
            return self._fallback(query, f"LLM error: {exc}")

        intent = data.get("primary_intent", INTENT_SIGNAL_LOOKUP)
        if intent not in ALL_INTENTS:
            intent = INTENT_SIGNAL_LOOKUP

        scope_raw = data.get("data_scope_hint", {}) or {}
        scope = DataScopeHint(
            tickers_mentioned=scope_raw.get("tickers_mentioned", []),
            functions_mentioned=scope_raw.get("functions_mentioned", []),
            signal_types_mentioned=scope_raw.get("signal_types_mentioned", []),
        )

        result = IntentResult(
            primary_intent=intent,
            confidence=float(data.get("confidence", 0.70)),
            is_hybrid=bool(data.get("is_hybrid", False)),
            secondary_intent=data.get("secondary_intent"),
            reasoning=data.get("reasoning", ""),
            data_scope_hint=scope,
            classified_by="llm",
            web_search_queries=data.get("web_search_queries"),
        )
        logger.info(
            f"[INTENT/llm] {result.primary_intent} ({result.confidence:.2f})"
            f" hybrid={result.is_hybrid}: {query[:80]}"
        )
        return result

    # ── Helpers ─────────────────────────────────────────────────────────────────

    def _fallback(self, query: str, reason: str) -> IntentResult:
        return IntentResult(
            primary_intent=INTENT_SIGNAL_LOOKUP,
            confidence=0.50,
            is_hybrid=False,
            secondary_intent=None,
            reasoning=f"Fallback: {reason}",
            data_scope_hint=self._extract_scope_hint(query),
            classified_by="fallback",
        )

    def _extract_scope_hint(self, query: str) -> DataScopeHint:
        tickers = re.findall(r'\b([A-Z]{2,5})(?:\.[A-Z]{2})?\b', query)
        tickers = [t for t in tickers if t not in _TICKER_STOPWORDS]
        functions = [f for f in _KNOWN_FUNCTIONS if f.lower() in query.lower()]
        signals = [s for s in _KNOWN_SIGNAL_TYPES if s.lower() in query.lower()]
        return DataScopeHint(
            tickers_mentioned=tickers[:10],
            functions_mentioned=functions,
            signal_types_mentioned=signals,
        )

    @staticmethod
    def _default_web_queries(query: str) -> List[str]:
        return [query.strip()]
