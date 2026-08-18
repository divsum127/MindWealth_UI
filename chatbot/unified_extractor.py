"""
Unified Extractor - Combines signal type, function, ticker, and column extraction in ONE GPT-5.2 API call.
This reduces API calls from 4 to 1, improving performance and reducing costs.
"""

import json
import logging
from typing import Dict, List, Optional, Tuple
from openai import OpenAI
from pathlib import Path

from .column_metadata_extractor import ColumnMetadataExtractor
from .config import OPENAI_API_KEY, OPENAI_MODEL, MAX_TOKENS, TEMPERATURE
from .ticker_resolver import resolve_tickers, verify_extracted_symbols
from prompts.engine import format_unified_extractor_prompt, load_chatbot_system_prompt

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


ALLOWED_SIGNAL_TYPES = ["entry", "exit", "portfolio_target_achieved", "breadth", "claude_report"]
DEFAULT_SIGNAL_TYPES = ["entry", "exit", "portfolio_target_achieved"]

AVAILABLE_FUNCTIONS = [
    "ALTITUDE ALPHA",
    "BAND MATRIX",
    "BASELINEDIVERGENCE",
    "FRACTAL TRACK",
    "OSCILLATOR DELTA",
    "PULSEGAUGE",
    "SIGMASHELL",
    "TRENDPULSE"
]


class UnifiedExtractor:
    """
    Extracts all query components in a single GPT-5.2 call:
    1. Signal types (entry, exit, portfolio_target_achieved, breadth)
    2. Functions (TRENDPULSE, FRACTAL TRACK, etc.)
    3. Tickers/Assets (AAPL, MSFT, etc.)
    4. Required columns for each signal type
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the unified extractor.
        
        Args:
            api_key: Optional OpenAI API key (uses env var if not provided)
        """
        self.api_key = api_key or OPENAI_API_KEY
        
        if not self.api_key:
            raise ValueError("OpenAI API key not provided")
        
        try:
            self.client = OpenAI(api_key=self.api_key)
        except Exception as e:
            raise ValueError(f"Failed to initialize OpenAI client: {e}")
        
        self.metadata_extractor = ColumnMetadataExtractor()
        self.system_prompt = load_chatbot_system_prompt()
        self.available_tickers = []
    
    def set_available_tickers(self, tickers: List[str]):
        """Set the list of available tickers for extraction."""
        self.available_tickers = [t.upper() for t in tickers]
        logger.info(f"Set {len(self.available_tickers)} available tickers for unified extraction")
    
    def _build_column_context(self, signal_types: List[str]) -> str:
        """Build context about available columns with INDEX numbers."""
        metadata = self.metadata_extractor.extract_all_metadata()
        
        context_parts = ["\n=== AVAILABLE COLUMNS (with INDEX numbers) ===\n"]
        context_parts.append("IMPORTANT: Always specify both column INDEX (number) and column NAME for 100% accuracy.\n")
        
        for signal_type in signal_types:
            if signal_type not in metadata:
                continue
            
            context_parts.append(f"\n{signal_type.upper()} SIGNALS:")
            
            if signal_type == "breadth":
                columns = metadata["breadth"]
                context_parts.append(f"  Available columns ({len(columns)} total):")
                for idx, col in enumerate(columns):
                    context_parts.append(f"    [{idx}] {col}")
            else:
                for function_name, columns in metadata[signal_type].items():
                    context_parts.append(f"\n  Function: {function_name}")
                    context_parts.append(f"    Available columns ({len(columns)} total):")
                    for idx, col in enumerate(columns):
                        context_parts.append(f"      [{idx}] {col}")
        
        context_parts.append("\n=== END AVAILABLE COLUMNS ===\n")
        return "\n".join(context_parts)
    
    def extract_all(self, user_query: str, conversation_history: Optional[List[Dict]] = None) -> Dict:
        """
        Extract all query components in a single GPT call.
        
        Args:
            user_query: The user's question/request
            conversation_history: Optional list of previous conversation messages for context
            
        Returns:
            Dictionary with structure:
            {
                "signal_types": ["entry", "exit", ...],
                "signal_types_reasoning": "...",
                "functions": ["TRENDPULSE", ...] or None,
                "tickers": ["AAPL", "MSFT", ...] or None (None means ALL),
                "columns": {
                    "entry": {
                        "required_columns": [...],
                        "column_indices": [...],
                        "reasoning": "..."
                    },
                    "exit": {...},
                    ...
                },
                "success": True/False,
                "error": "Error message if success=False"
            }
        """
        try:
            # Build comprehensive prompt
            # Send the FULL universe. Truncating at 100 hid every symbol past
            # that index — e.g. MFT.NZ sits at ~111, so the model could not learn
            # its ".NZ" suffix and emitted a bare "MFT" that matched no rows.
            # The universe is ~200 symbols; the token cost is negligible.
            ticker_list = ', '.join(self.available_tickers) if self.available_tickers else "No tickers available"
            
            # Start with default signal types for column context
            default_signals = DEFAULT_SIGNAL_TYPES.copy()
            column_context = self._build_column_context(default_signals)
            
            unified_prompt = format_unified_extractor_prompt(
                user_query=user_query,
                available_functions=", ".join(AVAILABLE_FUNCTIONS),
                ticker_list=ticker_list,
                column_context=column_context,
            )

            logger.info(f"Calling unified extractor (GPT-5.2) for query: {user_query[:100]}...")
            
            # Build messages with conversation history for context
            from .config import MAX_EXTRACTION_HISTORY_LENGTH, MAX_INPUT_TOKENS_PER_CALL, ESTIMATED_CHARS_PER_TOKEN
            
            messages = []
            
            # Add system message
            messages.append({"role": "system", "content": self.system_prompt})
            
            # Add conversation history if provided (for follow-up context)
            if conversation_history:
                # Limit history to MAX_EXTRACTION_HISTORY_LENGTH exchanges (5 by default, lighter than main chat)
                history_to_use = conversation_history[-MAX_EXTRACTION_HISTORY_LENGTH*2:] if len(conversation_history) > MAX_EXTRACTION_HISTORY_LENGTH*2 else conversation_history
                
                # Filter out system messages (already added above)
                history_to_use = [msg for msg in history_to_use if msg.get('role') != 'system']
                
                # Estimate tokens to avoid exceeding MAX_INPUT_TOKENS_PER_CALL
                total_chars = len(self.system_prompt) + len(unified_prompt)
                for msg in history_to_use:
                    total_chars += len(str(msg.get('content', '')))
                
                estimated_tokens = total_chars // ESTIMATED_CHARS_PER_TOKEN
                
                # If we're approaching token limit, reduce history
                while estimated_tokens > (MAX_INPUT_TOKENS_PER_CALL - 5000) and len(history_to_use) > 2:
                    # Remove oldest messages but keep at least 2 (1 exchange)
                    history_to_use = history_to_use[2:]
                    total_chars = len(self.system_prompt) + len(unified_prompt)
                    for msg in history_to_use:
                        total_chars += len(str(msg.get('content', '')))
                    estimated_tokens = total_chars // ESTIMATED_CHARS_PER_TOKEN
                
                if history_to_use:  # Only extend if there are non-system messages
                    messages.extend(history_to_use)
                    logger.info(f"Including {len(history_to_use)} history messages (~{estimated_tokens} tokens)")
            
            messages.append({"role": "user", "content": unified_prompt})
            
            # Call OpenAI GPT-5.2 API
            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                max_completion_tokens=MAX_TOKENS,
                temperature=TEMPERATURE
            )
            
            response_text = response.choices[0].message.content.strip()
            logger.info(f"Unified extractor response: {response_text[:300]}...")
            
            # Parse JSON response
            result = self._extract_json_from_response(response_text)
            
            if not result:
                logger.error("Failed to parse JSON from unified extractor response")
                return {
                    "success": False,
                    "error": "Could not parse JSON from GPT-5.2 response"
                }
            
            # Validate and normalize the result
            result = self._validate_and_normalize(
                result, user_query=user_query, conversation_history=conversation_history
            )
            result["success"] = True
            
            logger.info(f"✅ Unified extraction complete:")
            logger.info(f"  - Signal types: {result.get('signal_types', [])}")
            logger.info(f"  - Functions: {result.get('functions', 'ALL')}")
            logger.info(f"  - Tickers: {result.get('tickers', 'ALL')}")
            logger.info(f"  - Columns extracted for {len(result.get('columns', {}))} signal types")
            
            return result
        
        except Exception as e:
            logger.error(f"Error in unified extraction: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    def _extract_json_from_response(self, response_text: str) -> Optional[Dict]:
        """Extract JSON from GPT-5.2 response, handling markdown code blocks."""
        # Remove markdown code blocks if present
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            response_text = response_text[start:end].strip()
        elif "```" in response_text:
            start = response_text.find("```") + 3
            end = response_text.find("```", start)
            response_text = response_text[start:end].strip()
        
        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            logger.error(f"Response text: {response_text}")
            return None
    
    def _validate_and_normalize(
        self,
        result: Dict,
        user_query: str = "",
        conversation_history: Optional[List[Dict]] = None,
    ) -> Dict:
        """Validate and normalize the extraction result."""
        # Ensure signal_types is valid
        signal_types = result.get("signal_types", [])
        if not signal_types:
            logger.warning("No signal types extracted, using defaults")
            signal_types = DEFAULT_SIGNAL_TYPES.copy()
        
        # Filter to valid signal types only
        signal_types = [st for st in signal_types if st in ALLOWED_SIGNAL_TYPES]
        result["signal_types"] = signal_types
        
        # Normalize functions (null → None)
        functions = result.get("functions")
        if functions == [] or functions == "null":
            functions = None
        result["functions"] = functions
        
        # Normalize tickers (null → None)
        tickers = result.get("tickers")
        if tickers == [] or tickers == "null":
            tickers = None
        # Handle region filters (e.g., [".NZ"])
        elif isinstance(tickers, list) and len(tickers) > 0:
            if tickers[0].startswith("."):
                # Region filter - expand to matching tickers
                suffix = tickers[0]
                tickers = [t for t in self.available_tickers if t.endswith(suffix)]
                logger.info(f"Expanded region filter '{suffix}' to {len(tickers)} tickers")
            else:
                # Resolve bare symbols to the canonical stored spelling
                # ("MFT" → "MFT.NZ"). Filtering downstream is an exact match, so
                # an unresolved bare symbol silently yields zero rows.
                resolved, unresolved = resolve_tickers(tickers, self.available_tickers)

                # Drop symbols the question does not justify. The model will
                # "correct" an unknown ticker to a real one — "tlk" came back as
                # TLT, a different asset that passes every membership check — so
                # each surviving symbol must be traceable to the wording, either
                # literally or through the committed alias map. History is part
                # of the haystack because follow-ups ("the mtm for those") name
                # their ticker in an earlier turn.
                haystack = " ".join(
                    [str(user_query or "")]
                    + [
                        str(msg.get("content", ""))
                        for msg in (conversation_history or [])
                        if isinstance(msg, dict)
                    ]
                )
                resolved, guessed = verify_extracted_symbols(
                    haystack, resolved, self.available_tickers
                )
                if guessed:
                    logger.warning(f"Discarded unsupported extracted symbols: {guessed}")

                if unresolved or guessed:
                    result["unresolved_tickers"] = unresolved + guessed
                # Keep unresolved symbols in the filter list so the caller can
                # report "not in the universe" rather than answering as if the
                # user had asked about nothing in particular.
                tickers = resolved + unresolved
        result["tickers"] = tickers

        # position_side: short / long (short selling vs long); null when not specified
        ps = result.get("position_side")
        if ps is None or ps == "null" or (isinstance(ps, str) and not ps.strip()):
            result["position_side"] = None
        else:
            ps_l = str(ps).strip().lower()
            result["position_side"] = ps_l if ps_l in ("short", "long") else None
        
        # Normalize columns - add indices list
        # For claude_report signal type, columns might be None or empty
        columns = result.get("columns", {})
        if columns is None:
            columns = {}
        
        for signal_type, signal_data in columns.items():
            if "required_columns" in signal_data:
                # Extract indices separately for easier access
                indices = []
                names = []
                for col in signal_data["required_columns"]:
                    if isinstance(col, dict):
                        indices.append(col.get("index"))
                        names.append(col.get("name"))
                    else:
                        names.append(col)
                
                signal_data["column_indices"] = indices
                signal_data["column_names"] = names
        
        result["columns"] = columns
        
        return result
