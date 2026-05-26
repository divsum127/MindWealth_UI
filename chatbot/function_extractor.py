"""
Function extractor using GPT-5.2 to identify trading functions from user prompts.
"""

import logging
import json
from typing import List, Optional
from openai import OpenAI

from .config import OPENAI_API_KEY, OPENAI_MODEL, MAX_TOKENS, TEMPERATURE
from prompts.engine import FUNCTION_EXTRACTION_PROMPT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FunctionExtractor:
    """Extracts trading function names from user prompts using GPT-5.2."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize function extractor.
        
        Args:
            api_key: Optional OpenAI API key (uses env var if not provided)
        """
        self.api_key = api_key or OPENAI_API_KEY
        
        if not self.api_key:
            raise ValueError(
                "OpenAI API key not provided. Set OPENAI_API_KEY environment variable."
            )
        
        self.client = OpenAI(api_key=self.api_key)
        
        # Available function names for validation
        self.available_functions = [
            "ALTITUDE ALPHA",
            "BAND MATRIX",
            "BASELINEDIVERGENCE",
            "FRACTAL TRACK",
            "OSCILLATOR DELTA",
            "PULSEGAUGE",
            "SIGMASHELL",
            "TRENDPULSE"
        ]
    
    def extract_functions(self, user_query: str) -> List[str]:
        """
        Extract function names from user query using GPT-5.2.
        
        Args:
            user_query: User's question/prompt
            
        Returns:
            List of function names mentioned in the query
        """
        try:
            # Build the prompt
            messages = [
                {"role": "system", "content": FUNCTION_EXTRACTION_PROMPT},
                {"role": "user", "content": user_query}
            ]
            
            # Call GPT-5.2 for extraction
            logger.info(f"Extracting functions from user query using {OPENAI_MODEL}...")
            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,  # Use GPT-5.2 for intelligent extraction
                messages=messages,
                max_completion_tokens=100,  # Short response for function names
                temperature=TEMPERATURE  # Use configured temperature
            )
            
            # Parse response
            response_text = response.choices[0].message.content.strip()
            logger.info(f"Function extraction response: {response_text}")
            
            # Parse JSON response
            try:
                functions = json.loads(response_text)
                
                if not isinstance(functions, list):
                    logger.warning(f"Response is not a list: {response_text}")
                    return []
                
                # Validate extracted functions
                valid_functions = []
                for func in functions:
                    if func in self.available_functions:
                        valid_functions.append(func)
                    else:
                        logger.warning(f"Invalid function extracted: {func}")
                
                logger.info(f"Extracted {len(valid_functions)} valid functions: {valid_functions}")
                return valid_functions
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {response_text}")
                # Try to extract functions manually as fallback
                return self._fallback_extraction(user_query)
        
        except Exception as e:
            logger.error(f"Error extracting functions: {e}")
            return []
    
    def _fallback_extraction(self, user_query: str) -> List[str]:
        """
        Fallback method using simple string matching.
        
        Args:
            user_query: User's question
            
        Returns:
            List of function names found in query
        """
        logger.info("Using fallback extraction method")
        
        query_upper = user_query.upper()
        found_functions = []
        
        for func in self.available_functions:
            # Check for exact match or close variations
            if func.upper() in query_upper:
                found_functions.append(func)
            # Check for variations without spaces
            elif func.upper().replace(" ", "") in query_upper.replace(" ", ""):
                found_functions.append(func)
        
        return found_functions
    
    def get_available_functions(self) -> List[str]:
        """Get list of available function names."""
        return self.available_functions.copy()

