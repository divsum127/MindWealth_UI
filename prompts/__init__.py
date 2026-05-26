"""
Centralized prompt templates for MindWealth UI and chatbot engine.
"""

from .engine import (
    SYSTEM_PROMPT,
    format_batch_aggregation_prompt,
    format_batch_synthesis_prompt,
    format_memory_extraction_prompt,
    format_unified_extractor_prompt,
    load_chatbot_system_prompt,
)
from .ui_buttons import (
    ANALYZE_ASSET_PROMPT_LEGACY_TEMPLATE,
    ANALYZE_ASSET_PROMPT_TEMPLATE,
    format_analyze_asset_prompt,
    format_analyze_asset_prompt_legacy,
    format_breadth_analysis_prompt,
    format_signal_insights_prompt,
)

__all__ = [
    "ANALYZE_ASSET_PROMPT_LEGACY_TEMPLATE",
    "ANALYZE_ASSET_PROMPT_TEMPLATE",
    "SYSTEM_PROMPT",
    "format_analyze_asset_prompt",
    "format_analyze_asset_prompt_legacy",
    "format_batch_aggregation_prompt",
    "format_batch_synthesis_prompt",
    "format_breadth_analysis_prompt",
    "format_memory_extraction_prompt",
    "format_signal_insights_prompt",
    "format_unified_extractor_prompt",
    "load_chatbot_system_prompt",
]
