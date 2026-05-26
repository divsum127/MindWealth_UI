"""
Column selector using GPT to identify required columns for user queries.
Combines chatbot.txt prompt with user query and available column metadata.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from openai import OpenAI

from .column_metadata_extractor import ColumnMetadataExtractor
from .config import OPENAI_API_KEY, OPENAI_MODEL, TEMPERATURE, MAX_TOKENS
from prompts.engine import load_chatbot_system_prompt

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ColumnSelector:
    """
    Uses GPT with chatbot.txt prompt to identify which columns are needed
    for a given user query.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the column selector.
        
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
    
    def _build_column_context(self, selected_signal_types: Optional[List[str]] = None) -> str:
        """
        Build context about available columns with INDEX numbers for the GPT prompt.
        
        Args:
            selected_signal_types: List of signal types user has selected (entry, exit, portfolio_target_achieved, breadth)
            
        Returns:
            Formatted string with column information including indices
        """
        metadata = self.metadata_extractor.extract_all_metadata()
        
        # If no signal types specified, include all
        if not selected_signal_types:
            selected_signal_types = ["entry", "exit", "portfolio_target_achieved", "breadth"]
        
        context_parts = ["\n=== AVAILABLE COLUMNS (with INDEX numbers) ===\n"]
        context_parts.append("IMPORTANT: Always specify both column INDEX (number) and column NAME for 100% accuracy.\n")
        
        for signal_type in selected_signal_types:
            if signal_type not in metadata:
                continue
            
            context_parts.append(f"\n{signal_type.upper()} SIGNALS:")
            
            if signal_type == "breadth":
                # Breadth has no functions
                columns = metadata["breadth"]
                context_parts.append(f"  Available columns ({len(columns)} total):")
                for idx, col in enumerate(columns):
                    context_parts.append(f"    [{idx}] {col}")
            else:
                # Entry/exit/target have functions
                for function_name, columns in metadata[signal_type].items():
                    context_parts.append(f"\n  Function: {function_name}")
                    context_parts.append(f"    Available columns ({len(columns)} total):")
                    for idx, col in enumerate(columns):
                        context_parts.append(f"      [{idx}] {col}")
        
        context_parts.append("\n=== END AVAILABLE COLUMNS ===\n")
        
        return "\n".join(context_parts)
    
    def select_columns(
        self,
        user_query: str,
        selected_signal_types: Optional[List[str]] = None,
        additional_context: Optional[str] = None
    ) -> Dict:
        """
        Select required columns for a user query using GPT.
        
        Args:
            user_query: The user's question/request
            selected_signal_types: List of signal types user has selected (checkboxes)
            additional_context: Optional additional context about the query
            
        Returns:
            Dictionary with structure:
            {
                "entry": {
                    "required_columns": [...],
                    "reasoning": "..."
                },
                "exit": {
                    "required_columns": [...],
                    "reasoning": "..."
                },
                ... (only includes selected signal types)
                "success": True/False,
                "error": "Error message if success=False"
            }
        """
        try:
            # Build the column context
            column_context = self._build_column_context(selected_signal_types)
            
            # Build the user message
            user_message_parts = [
                "User query:",
                user_query,
                column_context
            ]
            
            if selected_signal_types:
                user_message_parts.append(
                    f"\nUser has selected the following signal types (via checkboxes): {', '.join(selected_signal_types)}"
                )
                user_message_parts.append(
                    "\nIMPORTANT: Only return column selections for the signal types the user selected above."
                )
            
            if additional_context:
                user_message_parts.append(f"\nAdditional context: {additional_context}")
            
            user_message_parts.append(
                "\nMANDATORY COLUMNS that MUST always be included:\n"
                "- For entry/exit/portfolio_target_achieved signals:\n"
                "  * [0] Function - REQUIRED to identify the trading strategy\n"
                "  * [1] Symbol, Signal, Signal Date/Price[$] - REQUIRED to identify the asset and signal\n"
                "\n"
                "Respond with a JSON object containing the required columns for EACH selected signal type. "
                "For EACH column, specify BOTH the column INDEX (number) AND column name for 100% accuracy. "
                "Format:\n"
                "{\n"
                "  \"signal_type\": {\n"
                "    \"required_columns\": [{\"index\": 0, \"name\": \"Column Name\"}, ...],\n"
                "    \"reasoning\": \"Brief explanation\"\n"
                "  }\n"
                "}\n"
                "IMPORTANT: ALWAYS include the mandatory columns (Function and Symbol) in your selection.\n"
                "ONLY return valid JSON, no other text."
            )
            
            user_message = "\n".join(user_message_parts)
            
            # Call GPT
            logger.info(f"Calling GPT to select columns for query: {user_query[:100]}...")
            
            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,  # Use GPT-5.2 for intelligent column selection
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=TEMPERATURE,  # Use config value
                max_completion_tokens=1000  # Enough for column list and reasoning
            )
            
            # Extract and parse the response
            response_text = response.choices[0].message.content.strip()
            logger.info(f"GPT response: {response_text[:200]}...")
            
            # Try to extract JSON from the response
            result = self._extract_json_from_response(response_text)
            
            if result and self._validate_signal_type_response(result, selected_signal_types):
                # Convert new format (with indices) to include both formats
                result = self._normalize_column_format(result)
                
                # Validate that selected columns exist in available columns
                metadata = self.metadata_extractor.extract_all_metadata()
                validation_result = self._validate_column_names(result, metadata, selected_signal_types)
                
                if not validation_result["valid"]:
                    logger.warning(f"Column validation warnings: {validation_result['warnings']}")
                    # Log warnings but don't fail - the flexible matcher will handle it
                    for warning in validation_result['warnings']:
                        logger.warning(f"  - {warning}")
                
                result["success"] = True
                result["column_validation_warnings"] = validation_result.get("warnings", [])
                total_columns = sum(
                    len(sig_data.get('required_columns', [])) 
                    for sig_data in result.values() 
                    if isinstance(sig_data, dict) and 'required_columns' in sig_data
                )
                logger.info(f"Successfully selected {total_columns} columns across {len([k for k in result if k not in ['success', 'error', 'column_validation_warnings']])} signal types")
                return result
            else:
                logger.error("Failed to parse or validate JSON from GPT response")
                return {
                    "success": False,
                    "error": "Could not parse or validate JSON from GPT response"
                }
        
        except Exception as e:
            logger.error(f"Error selecting columns: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _normalize_column_format(self, result: Dict) -> Dict:
        """
        Normalize column format to support both old (list of strings) and new (list of dicts with index+name).
        Converts to consistent format: list of strings for column names, with separate indices list.
        Also ensures mandatory columns (Function, Symbol) are always included.
        
        Args:
            result: GPT response with column selections
            
        Returns:
            Normalized result with both column names and indices
        """
        # Define mandatory columns for each signal type
        MANDATORY_COLUMNS = {
            'entry': [
                {'index': 0, 'name': 'Function'},
                {'index': 1, 'name': 'Symbol, Signal, Signal Date/Price[$]'}
            ],
            'exit': [
                {'index': 0, 'name': 'Function'},
                {'index': 1, 'name': 'Symbol, Signal, Signal Date/Price[$]'}
            ],
            'portfolio_target_achieved': [
                {'index': 0, 'name': 'Function'},
                {'index': 1, 'name': 'Symbol, Signal, Signal Date/Price[$]'}
            ]
        }
        
        for signal_type, signal_data in result.items():
            if not isinstance(signal_data, dict) or 'required_columns' not in signal_data:
                continue
            
            columns = signal_data['required_columns']
            
            # Check if new format (list of dicts with index+name)
            if columns and isinstance(columns[0], dict):
                # Extract names and indices
                column_names = []
                column_indices = []
                
                # Add mandatory columns first if this signal type has them
                if signal_type in MANDATORY_COLUMNS:
                    for mandatory_col in MANDATORY_COLUMNS[signal_type]:
                        # Check if mandatory column is already in the list
                        if not any(col.get('index') == mandatory_col['index'] for col in columns if isinstance(col, dict)):
                            logger.info(f"{signal_type}: Adding mandatory column [{mandatory_col['index']}] {mandatory_col['name']}")
                            column_indices.insert(0, mandatory_col['index'])
                            column_names.insert(0, mandatory_col['name'])
                
                for col_info in columns:
                    if isinstance(col_info, dict):
                        idx = col_info.get('index', -1)
                        name = col_info.get('name', '')
                        # Avoid duplicates
                        if idx not in column_indices:
                            column_indices.append(idx)
                            column_names.append(name)
                    else:
                        # Fallback for mixed format
                        column_names.append(str(col_info))
                        column_indices.append(-1)
                
                signal_data['required_columns'] = column_names
                signal_data['column_indices'] = column_indices
                logger.info(f"{signal_type}: Using column indices {column_indices} for precise selection")
            # else: old format (list of strings) - keep as is
        
        return result
    
    def _validate_signal_type_response(
        self, 
        result: Dict, 
        selected_signal_types: Optional[List[str]]
    ) -> bool:
        """
        Validate that the response has the correct structure for selected signal types.
        
        Args:
            result: Parsed JSON response from GPT
            selected_signal_types: Signal types user selected
            
        Returns:
            True if valid, False otherwise
        """
        if not selected_signal_types:
            return True
        
        # Check if at least one selected signal type is in the response
        has_valid_signal = False
        for signal_type in selected_signal_types:
            if signal_type in result:
                signal_data = result[signal_type]
                # Validate structure: must have required_columns and reasoning
                if isinstance(signal_data, dict) and 'required_columns' in signal_data:
                    has_valid_signal = True
                    break
        
        return has_valid_signal
    
    def _validate_column_names(
        self,
        result: Dict,
        metadata: Dict,
        selected_signal_types: Optional[List[str]]
    ) -> Dict:
        """
        Validate that selected column names actually exist in the available columns.
        
        Args:
            result: Parsed JSON response from GPT with selected columns
            metadata: Column metadata from metadata_extractor
            selected_signal_types: Signal types user selected
            
        Returns:
            Dictionary with validation results:
            {
                "valid": True/False,
                "warnings": ["warning message 1", "warning message 2", ...]
            }
        """
        warnings = []
        
        if not selected_signal_types:
            return {"valid": True, "warnings": []}
        
        for signal_type in selected_signal_types:
            if signal_type not in result:
                continue
            
            signal_data = result[signal_type]
            if not isinstance(signal_data, dict) or 'required_columns' not in signal_data:
                continue
            
            selected_columns = signal_data['required_columns']
            
            # Get available columns for this signal type
            if signal_type == "breadth":
                available_columns = metadata.get("breadth", [])
            else:
                # For entry/exit/target, collect all columns across all functions
                available_columns = []
                signal_metadata = metadata.get(signal_type, {})
                for function_name, columns in signal_metadata.items():
                    available_columns.extend(columns)
                # Remove duplicates while preserving order
                available_columns = list(dict.fromkeys(available_columns))
            
            # Check each selected column
            for col in selected_columns:
                if col not in available_columns:
                    # Check if it's a close match (for helpful warnings)
                    close_matches = [ac for ac in available_columns if col.lower() in ac.lower() or ac.lower() in col.lower()]
                    if close_matches:
                        warnings.append(
                            f"{signal_type.upper()}: Column '{col}' not found. Did you mean one of: {', '.join(close_matches[:3])}?"
                        )
                    else:
                        warnings.append(
                            f"{signal_type.upper()}: Column '{col}' does not exist in available columns. It will be matched flexibly."
                        )
        
        return {
            "valid": len(warnings) == 0,
            "warnings": warnings
        }
    
    def _extract_json_from_response(self, response_text: str) -> Optional[Dict]:
        """
        Extract JSON from GPT response, handling various formats.
        
        Args:
            response_text: The response text from GPT
            
        Returns:
            Parsed JSON dict or None if parsing failed
        """
        # Try direct parsing first
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass
        
        # Try to find JSON within code blocks
        import re
        
        # Look for JSON in code blocks
        json_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        matches = re.findall(json_pattern, response_text, re.DOTALL)
        
        if matches:
            try:
                return json.loads(matches[0])
            except json.JSONDecodeError:
                pass
        
        # Try to find any JSON-like structure
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(json_pattern, response_text, re.DOTALL)
        
        for match in matches:
            try:
                result = json.loads(match)
                # Validate it has signal type keys with required structure
                if any(key in ['entry', 'exit', 'portfolio_target_achieved', 'breadth'] for key in result.keys()):
                    return result
            except json.JSONDecodeError:
                continue
        
        return None
    
    def validate_columns_exist(
        self,
        column_selection_result: Dict,
        selected_signal_types: List[str]
    ) -> Dict[str, Tuple[List[str], List[str]]]:
        """
        Validate that the required columns actually exist in the specified signal types.
        
        Args:
            column_selection_result: Result from select_columns() with per-signal-type columns
            selected_signal_types: List of signal types to check
            
        Returns:
            Dictionary mapping signal_type to (valid_columns, invalid_columns) tuple
            {
                "entry": ([valid_cols], [invalid_cols]),
                "exit": ([valid_cols], [invalid_cols]),
                ...
            }
        """
        metadata = self.metadata_extractor.extract_all_metadata()
        validation_results = {}
        
        for signal_type in selected_signal_types:
            if signal_type not in column_selection_result:
                continue
            
            signal_data = column_selection_result[signal_type]
            if not isinstance(signal_data, dict) or 'required_columns' not in signal_data:
                continue
            
            required_columns = signal_data['required_columns']
            
            # Collect all available columns for this signal type
            available_columns = set()
            
            if signal_type == "breadth":
                available_columns.update(metadata["breadth"])
            elif signal_type in metadata:
                for function_name, columns in metadata[signal_type].items():
                    available_columns.update(columns)
            
            # Validate each required column
            valid_columns = []
            invalid_columns = []
            
            for col in required_columns:
                if col in available_columns:
                    valid_columns.append(col)
                else:
                    invalid_columns.append(col)
            
            if invalid_columns:
                logger.warning(f"Invalid columns for {signal_type}: {invalid_columns}")
            
            validation_results[signal_type] = (valid_columns, invalid_columns)
        
        return validation_results
    
    def get_column_suggestions(self, partial_query: str, top_k: int = 10) -> List[str]:
        """
        Get column suggestions based on a partial query (for autocomplete features).
        
        Args:
            partial_query: Partial user query
            top_k: Number of suggestions to return
            
        Returns:
            List of suggested column names
        """
        all_columns = self.metadata_extractor.get_all_unique_columns()
        
        # Simple keyword matching (could be enhanced with more sophisticated matching)
        query_lower = partial_query.lower()
        keywords = query_lower.split()
        
        scored_columns = []
        for col in all_columns:
            col_lower = col.lower()
            score = 0
            
            # Score based on keyword matches
            for keyword in keywords:
                if keyword in col_lower:
                    score += 10
                if col_lower.startswith(keyword):
                    score += 5
            
            if score > 0:
                scored_columns.append((col, score))
        
        # Sort by score and return top_k
        scored_columns.sort(key=lambda x: x[1], reverse=True)
        return [col for col, score in scored_columns[:top_k]]


if __name__ == "__main__":
    # Test the column selector
    import sys
    
    # Check if API key is available
    if not OPENAI_API_KEY:
        print("Error: OPENAI_API_KEY not found in environment")
        sys.exit(1)
    
    selector = ColumnSelector()
    
    # Test queries
    test_queries = [
        "Show me the current performance of TSM",
        "What are the targets for my open positions?",
        "Show me breadth indicators for today",
        "What's the win rate and holding period for all my trades?"
    ]
    
    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print('='*60)
        
        result = selector.select_columns(
            query,
            selected_signal_types=["entry", "exit", "portfolio_target_achieved", "breadth"]
        )
        
        print(f"\nSuccess: {result.get('success', False)}")
        
        if result.get('success'):
            for signal_type in ["entry", "exit", "portfolio_target_achieved", "breadth"]:
                if signal_type in result:
                    signal_data = result[signal_type]
                    cols = signal_data.get('required_columns', [])
                    reasoning = signal_data.get('reasoning', '')
                    print(f"\n{signal_type.upper()}:")
                    print(f"  Columns ({len(cols)}): {cols[:3]}{'...' if len(cols) > 3 else ''}")
                    print(f"  Reasoning: {reasoning[:100]}{'...' if len(reasoning) > 100 else ''}")
        else:
            print(f"Error: {result.get('error', '')}")
