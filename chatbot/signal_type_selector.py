"""
Signal type selector that uses configured GPT model to determine which data categories are needed.
"""

import json
import logging
from typing import List, Optional, Tuple

from openai import OpenAI

from .config import OPENAI_API_KEY, OPENAI_MODEL, MAX_TOKENS, TEMPERATURE
from prompts.engine import (
    SIGNAL_TYPE_SELECTOR_SYSTEM,
    format_signal_type_selector_prompt,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


ALLOWED_SIGNAL_TYPES = ["entry", "exit", "portfolio_target_achieved", "breadth", "claude_report"]
DEFAULT_SIGNAL_TYPES = ["entry", "exit", "portfolio_target_achieved"]

SIGNAL_TYPE_DESCRIPTIONS = {
    "entry": (
        "Entry Signals",
        "Fresh trading ideas that have triggered but are still open (no exit yet). "
        "Useful when the user wants current opportunities or new setups."
    ),
    "exit": (
        "Exit Signals",
        "Trades that have completed with recorded exits. "
        "Relevant for reviewing performance, closed trades, or outcomes."
    ),
    "portfolio_target_achieved": (
        "Portfolio Target Achieved",
        "Signals that capture portfolio positions where targets have been hit and next risk actions are defined. "
        "Use when the user wants to understand realized targets, remaining upside, or protective moves for their portfolio."
    ),
    "breadth": (
        "Market Breadth",
        "Market-wide sentiment metrics (e.g., bull/bear breadth). "
        "Apply when the user asks about overall market health or breadth indicators."
    ),
    "claude_report": (
        "Claude Comprehensive Analysis Report",
        "Detailed comprehensive analysis report by Claude covering signal synthesis, insights, recommendations, and filtered signals. "
        "Use when the user asks about Claude's analysis, comprehensive reports, signal recommendations, or high-quality actionable signals."
    ),
}


class SignalTypeSelector:
    """Determine which signal types are needed for a user prompt."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or OPENAI_API_KEY
        if not self.api_key:
            raise ValueError("OpenAI API key not provided for SignalTypeSelector.")

        self.client = OpenAI(api_key=self.api_key)
        self.model = model or OPENAI_MODEL

    def select_signal_types(self, user_query: str) -> Tuple[List[str], str]:
        """
        Analyze the user query and decide which signal types to include.

        Returns:
            Tuple[List[str], str]: (selected signal type identifiers, reasoning string)
        """
        if not user_query or not user_query.strip():
            return (
                DEFAULT_SIGNAL_TYPES.copy(),
                "No specific request detected; using default entry/exit/portfolio_target_achieved signals."
            )

        options_text = "\n".join(
            [
                f"- {name} ({title}): {description}"
                for name, (title, description) in SIGNAL_TYPE_DESCRIPTIONS.items()
            ]
        )

        prompt = format_signal_type_selector_prompt(options_text, user_query)

        try:
            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,  # Use GPT-5.2 for intelligent extraction
                messages=[
                    {
                        "role": "system",
                        "content": SIGNAL_TYPE_SELECTOR_SYSTEM,
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=TEMPERATURE,  # Use configured temperature
                max_completion_tokens=200,  # Short response for signal type selection
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            data = json.loads(content)
            raw_selection = data.get("signal_types", [])
            reasoning = data.get("reasoning", "").strip()

            if isinstance(raw_selection, str):
                raw_selection = [raw_selection]

            selection_set = {item.lower() for item in raw_selection if isinstance(item, str)}

            ordered_selection = [
                signal_type for signal_type in ALLOWED_SIGNAL_TYPES if signal_type in selection_set
            ]

            if not ordered_selection:
                logger.info("Signal type selector returned empty or invalid selection; using defaults.")
                ordered_selection = DEFAULT_SIGNAL_TYPES.copy()
                if not reasoning:
                    reasoning = "Defaulted to entry/exit/portfolio_target_achieved due to unclear selection."

            logger.info(f"Signal type selection: {ordered_selection} | Reason: {reasoning}")
            return ordered_selection, reasoning or "Auto-selected signal types based on the query."

        except Exception as exc:
            logger.error(f"Failed to select signal types via OpenAI: {exc}")
            return (
                DEFAULT_SIGNAL_TYPES.copy(),
                "Fallback to default entry/exit/portfolio_target_achieved due to selection error."
            )

