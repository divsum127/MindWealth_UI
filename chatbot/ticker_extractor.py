"""
Ticker/Asset Extractor using GPT-5.2.
Automatically identifies asset symbols from user queries.
"""

import os
import json
import logging
from typing import List, Optional
from openai import OpenAI
from .config import OPENAI_API_KEY, TEMPERATURE, OPENAI_MODEL, MAX_TOKENS
from prompts.engine import TICKER_EXTRACTOR_SYSTEM, format_ticker_extraction_prompt

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TickerExtractor:
    """Extract ticker symbols from user queries using configured GPT model."""
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize TickerExtractor.
        
        Args:
            api_key: OpenAI API key (optional, uses env var if not provided)
            model: Model to use for extraction (optional, uses config default if not provided)
        """
        self.api_key = api_key or OPENAI_API_KEY
        if not self.api_key:
            raise ValueError("OpenAI API key not provided for TickerExtractor.")
        
        self.model = model or OPENAI_MODEL
        self.client = OpenAI(api_key=self.api_key)
        self.available_tickers = []  # Populated by chatbot engine
    
    def set_available_tickers(self, tickers: List[str]):
        """
        Set the list of available tickers for extraction.
        
        Args:
            tickers: List of available ticker symbols
        """
        self.available_tickers = [t.upper() for t in tickers]
        logger.info(f"Set {len(self.available_tickers)} available tickers for extraction")
    
    def extract_tickers(self, user_query: str) -> List[str]:
        """
        Extract ticker symbols from user query using GPT-5.2.
        
        Args:
            user_query: User's natural language query
            
        Returns:
            List of extracted ticker symbols
        """
        if not self.available_tickers:
            logger.warning("No available tickers set for extraction. Returning empty list.")
            return []
        
        ticker_list = ', '.join(self.available_tickers)
        prompt = format_ticker_extraction_prompt(ticker_list, user_query)

        try:
            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,  # Use GPT-5.2 for intelligent extraction
                messages=[
                    {"role": "system", "content": TICKER_EXTRACTOR_SYSTEM},
                    {"role": "user", "content": prompt}
                ],
                temperature=TEMPERATURE,  # Use configured temperature
                max_completion_tokens=150,  # Short response for ticker list
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            extracted_data = json.loads(content)
            extracted_result = extracted_data.get("tickers", [])
            
            logger.info(f"Extraction result: {extracted_result}")
            
            # Handle different response types
            if extracted_result == "ALL":
                # Return empty list to signal "use all tickers"
                logger.info("No specific tickers mentioned - will use ALL available tickers")
                return []  # Empty list = ALL tickers
            
            if isinstance(extracted_result, str):
                extracted_result = [extracted_result]
            
            if not isinstance(extracted_result, list):
                logger.warning(f"Unexpected result type: {type(extracted_result)}")
                return []
            
            # Handle region filters (e.g., [".NZ"], [".TO"])
            if extracted_result and extracted_result[0].startswith("."):
                suffix = extracted_result[0]
                matched_tickers = [t for t in self.available_tickers if t.endswith(suffix)]
                logger.info(f"Region filter '{suffix}' matched {len(matched_tickers)} tickers")
                return matched_tickers
            
            # Filter and normalize extracted tickers against available ones
            valid_tickers = []
            for ticker in extracted_result:
                ticker_upper = ticker.upper()
                if ticker_upper in self.available_tickers:
                    valid_tickers.append(ticker_upper)
                else:
                    # Try fuzzy matching (case-insensitive)
                    for available in self.available_tickers:
                        if available.upper() == ticker_upper:
                            valid_tickers.append(available)
                            break
            
            if valid_tickers:
                logger.info(f"Extracted {len(valid_tickers)} specific tickers: {valid_tickers}")
                return list(set(valid_tickers))  # Return unique valid tickers
            else:
                # No valid tickers found, return empty (= ALL)
                logger.info("No valid tickers extracted - will use ALL available tickers")
                return []
            
        except Exception as e:
            logger.error(f"Error extracting tickers with {self.model}: {e}")
            return []

