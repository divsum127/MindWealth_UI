"""
History manager for maintaining conversation context.
"""

import json
import logging
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Optional
from uuid import uuid4

from .config import HISTORY_DIR, MAX_HISTORY_LENGTH

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HistoryManager:
    """Manages conversation history and context for chatbot sessions."""
    
    def __init__(self, session_id: Optional[str] = None, session_title: Optional[str] = None):
        """
        Initialize history manager.
        
        Args:
            session_id: Unique session identifier. If None, creates new session.
            session_title: Optional title for the session.
        """
        self.session_id = session_id or str(uuid4())
        self.history_file = HISTORY_DIR / f"{self.session_id}.json"
        self.conversation_history: List[Dict[str, str]] = []
        self.metadata: Dict = {
            "session_id": self.session_id,
            "title": session_title or "New Chat",
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "message_count": 0
        }
        
        # Load existing history if available
        if self.history_file.exists():
            self.load_history()
        else:
            # Create new session file immediately to ensure persistence
            self.save_history()
            logger.info(f"Created new session file for {self.session_id}")
    
    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None):
        """
        Add a message to conversation history.
        
        Args:
            role: Message role ('user', 'assistant', 'system')
            content: Message content
            metadata: Optional metadata for the message
        """
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        if metadata:
            message["metadata"] = metadata
        
        self.conversation_history.append(message)
        self.metadata["last_updated"] = datetime.now().isoformat()
        self.metadata["message_count"] = len(self.conversation_history)
        
        # Auto-generate title from first user message if title is still "New Chat"
        if role == "user" and self.metadata.get("title") == "New Chat":
            self.update_session_title_from_message(content)

        # Create summary once after first user+assistant pair, then keep it stable.
        if not self.metadata.get("summary"):
            has_user = any(m.get("role") == "user" for m in self.conversation_history)
            has_assistant = any(m.get("role") == "assistant" for m in self.conversation_history)
            if has_user and has_assistant:
                self.metadata["summary"] = self._generate_session_summary()
        
        # Trim history if it exceeds max length
        if len(self.conversation_history) > MAX_HISTORY_LENGTH * 2:  # *2 for user+assistant pairs
            self.conversation_history = self.conversation_history[-(MAX_HISTORY_LENGTH * 2):]
        
        # Auto-save after each message
        self.save_history()
        
        logger.info(f"Added {role} message to session {self.session_id}")

    @staticmethod
    def _extract_clean_prompt(message: Dict) -> str:
        """Extract a user-friendly prompt from stored message content/metadata."""
        message_metadata = message.get("metadata") or {}
        preview_text = message_metadata.get("display_prompt") or message.get("content", "")

        if "FOLLOW-UP QUESTION:" in preview_text:
            preview_text = preview_text.split("FOLLOW-UP QUESTION:", 1)[1].strip()
        elif "User Query:" in preview_text:
            preview_text = preview_text.split("User Query:", 1)[1].strip()

        if "CURRENT QUESTION:" in preview_text and "CONVERSATION CONTEXT (for reference):" in preview_text:
            preview_text = preview_text.split("CURRENT QUESTION:", 1)[1].strip()

        if "===" in preview_text:
            preview_text = preview_text.split("===", 1)[0].strip()

        preview_text = re.sub(r"\s+", " ", preview_text).strip()
        return preview_text

    @staticmethod
    def _extract_assets_from_messages(messages: List[Dict]) -> List[str]:
        """Extract likely ticker symbols from a list of user messages."""
        tickers = []
        seen = set()
        pattern = re.compile(r"\b[A-Z]{2,5}\b")
        ignore_tokens = {
            "DATE", "DATES", "FROM", "TO", "JSON", "DATA", "NOTE", "USER",
            "QUERY", "WITH", "AND", "FOR", "THE", "ALL", "LONG", "SHORT",
            "OPEN", "CLOSE", "EXIT", "ENTRY", "SBI", "AI",
        }

        for message in messages:
            text = HistoryManager._extract_clean_prompt(message)
            for token in pattern.findall(text):
                if token not in ignore_tokens and token not in seen:
                    seen.add(token)
                    tickers.append(token)
                if len(tickers) >= 2:
                    return tickers
        return tickers

    def _generate_session_summary(self, max_length: int = 90) -> str:
        """Generate a concise one-line summary from the first exchange only."""
        user_messages = [m for m in self.conversation_history if m.get("role") == "user"]
        if not user_messages:
            return "New chat"

        first_prompt = self._extract_clean_prompt(user_messages[0])
        first_assistant = next(
            (m for m in self.conversation_history if m.get("role") == "assistant"),
            None
        )
        first_meta = (first_assistant or {}).get("metadata") or {}

        intent = str(first_meta.get("intent") or "").strip()
        selected_signal_types = first_meta.get("selected_signal_types") or []
        assets = self._extract_assets_from_messages([user_messages[0]])

        # Pipeline: intent-aware label -> signal context -> assets -> query gist
        intent_label_map = {
            "SIGNAL_LOOKUP": "Signal lookup",
            "MARKET_BREADTH": "Market breadth",
            "PERFORMANCE_ANALYSIS": "Performance analysis",
            "RISK_ANALYSIS": "Risk analysis",
            "TRADE_REVIEW": "Trade review",
            "GENERAL_QA": "General Q&A",
        }
        base = intent_label_map.get(intent, "Trading analysis")

        if selected_signal_types:
            signal_text = ", ".join(str(s).replace("_", " ") for s in selected_signal_types[:2])
            base = f"{base} ({signal_text})"

        if assets:
            asset_text = ", ".join(assets)
            summary = f"{base} for {asset_text}"
        else:
            summary = base

        if first_prompt:
            short_prompt = first_prompt[:50].strip()
            if len(first_prompt) > 50:
                short_prompt += "..."
            summary = f"{summary}: {short_prompt}"

        summary = re.sub(r"\s+", " ", summary).strip(" -:")
        if len(summary) > max_length:
            summary = summary[: max_length - 3].rstrip() + "..."
        return summary or "Trading analysis"
    
    def get_messages_for_api(self, max_pairs: Optional[int] = None, strip_data: bool = True) -> List[Dict[str, str]]:
        """
        Get conversation history formatted for OpenAI API.
        
        Args:
            max_pairs: Optional maximum number of user-assistant message pairs to include.
                      If specified, returns the last N pairs plus the system message.
                      If None, returns all messages.
            strip_data: If True, removes large data payloads from user messages (recommended for token efficiency).
                       Default is True to prevent sending massive data tables in conversation history.
                       NOTE: ALWAYS keeps data in the LAST (current) message - only strips HISTORICAL messages.
        
        Returns:
            List of message dictionaries with 'role' and 'content' keys
        """
        import re
        
        def _strip_data_payload(text: str) -> str:
            """Remove data sections from message text to reduce token usage"""
            if not text:
                return text
            
            # Remove everything from === DATA CONTEXT === onwards
            # This captures all data sections in one go
            patterns = [
                r"===\s*COLUMN SELECTION BY SIGNAL TYPE\s*===[\s\S]*$",  # From column selection to end
                r"===\s*DATA CONTEXT\s*===[\s\S]*$",  # From data context to end
                r"===\s*TRADING DATA[\s\S]*$",  # From trading data to end
                r"===\s*NEW DATA FETCHED[\s\S]*$",  # From new data to end
                r"===\s*NEW COLUMNS ADDED[\s\S]*$",  # From new columns to end
                r"===\s*PROVIDED DATA\s*===[\s\S]*$",  # From provided data to end
                r"===\s*ENTRY SIGNALS \(JSON\)[\s\S]*$",  # From entry signals to end
                r"===\s*EXIT SIGNALS \(JSON\)[\s\S]*$",  # From exit signals to end
                r"===\s*PORTFOLIO_TARGET_ACHIEVED SIGNALS \(JSON\)[\s\S]*$",  # From target signals to end
                r"===\s*BREADTH SIGNALS \(JSON\)[\s\S]*$",  # From breadth signals to end
                r"===\s*ADDITIONAL CONTEXT\s*===[\s\S]*$",  # From additional context to end
            ]
            
            cleaned = text
            for pat in patterns:
                cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE | re.DOTALL)
            
            # Clean up prefixes
            cleaned = re.sub(r"User Query:\s*", "", cleaned)
            cleaned = re.sub(r"FOLLOW-UP QUESTION:\s*", "", cleaned)
            cleaned = re.sub(r"CONVERSATION CONTEXT \(for reference\):[\s\S]*?CURRENT QUESTION:\s*", "", cleaned)
            cleaned = re.sub(r"NOTE:.*?$", "", cleaned, flags=re.IGNORECASE | re.MULTILINE)
            
            # Clean up excessive whitespace
            cleaned = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned)
            cleaned = cleaned.strip()
            
            return cleaned
        
        messages = []
        total_messages = len(self.conversation_history)
        
        for idx, msg in enumerate(self.conversation_history):
            role = msg["role"]
            content = msg["content"]
            
            # CRITICAL: Only strip data from HISTORICAL messages, NOT the last (current) message
            # The last user message should ALWAYS include its data context
            is_last_message = (idx == total_messages - 1)
            
            if strip_data and role == "user" and not is_last_message:
                content = _strip_data_payload(content)
            
            messages.append({"role": role, "content": content})
        
        if max_pairs is None:
            return messages
        
        # Separate system message from conversation
        system_messages = [msg for msg in messages if msg["role"] == "system"]
        conversation_messages = [msg for msg in messages if msg["role"] != "system"]
        
        # Get last N pairs (each pair is user + assistant = 2 messages)
        num_messages_to_keep = max_pairs * 2
        last_messages = conversation_messages[-num_messages_to_keep:] if len(conversation_messages) > num_messages_to_keep else conversation_messages
        
        # Combine: system message + last N pairs
        return system_messages + last_messages
    
    def get_full_history(self) -> List[Dict[str, str]]:
        """
        Get complete conversation history with all metadata.
        
        Returns:
            List of all message dictionaries
        """
        return self.conversation_history.copy()
    
    def save_history(self):
        """Save conversation history to file."""
        try:
            # Prepare conversation history for serialization
            serializable_conversation = []
            for message in self.conversation_history:
                serializable_message = message.copy()
                
                # Convert DataFrames in metadata to serializable format
                if 'metadata' in serializable_message and serializable_message['metadata']:
                    metadata = serializable_message['metadata'].copy()
                    
                    # Handle full_signal_tables DataFrames
                    if 'full_signal_tables' in metadata:
                        metadata['full_signal_tables'] = {
                            signal_type: df.to_dict('records') if hasattr(df, 'to_dict') else df
                            for signal_type, df in metadata['full_signal_tables'].items()
                        }
                    
                    # Handle any other DataFrames in metadata
                    for key, value in metadata.items():
                        if hasattr(value, 'to_dict'):  # Check if it's a DataFrame
                            metadata[key] = value.to_dict('records')
                    
                    serializable_message['metadata'] = metadata
                
                serializable_conversation.append(serializable_message)
            
            # Also handle DataFrames in session metadata
            serializable_metadata = self.metadata.copy()
            for key, value in serializable_metadata.items():
                if hasattr(value, 'to_dict'):  # Check if it's a DataFrame
                    serializable_metadata[key] = value.to_dict('records')
            
            data = {
                "metadata": serializable_metadata,
                "conversation": serializable_conversation
            }
            
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved history for session {self.session_id}")
            
        except Exception as e:
            logger.error(f"Error saving history: {e}")
    
    def load_history(self):
        """Load conversation history from file."""
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Load metadata and reconstruct any DataFrames
            self.metadata = data.get("metadata", {})
            
            # Convert serialized DataFrames back to DataFrames in session metadata
            import pandas as pd
            for key, value in self.metadata.items():
                if isinstance(value, list) and value and isinstance(value[0], dict):
                    # This looks like serialized DataFrame data
                    try:
                        self.metadata[key] = pd.DataFrame(value)
                    except:
                        # Keep as-is if conversion fails
                        pass
            
            # Load conversation history and convert serialized DataFrames back
            self.conversation_history = []
            for message in data.get("conversation", []):
                loaded_message = message.copy()
                
                # Convert serialized data back to DataFrames for internal use
                if 'metadata' in loaded_message and loaded_message['metadata']:
                    metadata = loaded_message['metadata'].copy()
                    
                    # Handle full_signal_tables - convert back to DataFrames
                    if 'full_signal_tables' in metadata:
                        import pandas as pd
                        converted_tables = {}
                        for signal_type, table_data in metadata['full_signal_tables'].items():
                            if isinstance(table_data, list) and table_data:
                                # Convert list of records back to DataFrame
                                converted_tables[signal_type] = pd.DataFrame(table_data)
                            else:
                                # Keep as-is if not in expected format
                                converted_tables[signal_type] = table_data
                        metadata['full_signal_tables'] = converted_tables
                    
                    loaded_message['metadata'] = metadata
                
                self.conversation_history.append(loaded_message)
            
            logger.info(f"Loaded history for session {self.session_id} with {len(self.conversation_history)} messages")
            
        except Exception as e:
            logger.error(f"Error loading history: {e}")
            self.conversation_history = []
    
    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []
        self.metadata["last_updated"] = datetime.now().isoformat()
        self.save_history()
        logger.info(f"Cleared history for session {self.session_id}")
    
    def delete_session(self):
        """Delete session history file."""
        try:
            if self.history_file.exists():
                self.history_file.unlink()
                logger.info(f"Deleted session {self.session_id}")
        except Exception as e:
            logger.error(f"Error deleting session: {e}")
    
    def get_session_summary(self) -> Dict:
        """
        Get summary of current session.
        
        Returns:
            Dictionary with session metadata and statistics
        """
        return {
            "session_id": self.session_id,
            "title": self.metadata.get("title", "New Chat"),
            "created_at": self.metadata.get("created_at"),
            "last_updated": self.metadata.get("last_updated"),
            "message_count": len(self.conversation_history),
            "user_messages": len([m for m in self.conversation_history if m["role"] == "user"]),
            "assistant_messages": len([m for m in self.conversation_history if m["role"] == "assistant"])
        }
    
    def update_session_title(self, new_title: str):
        """
        Update the session title.
        
        Args:
            new_title: New title for the session
        """
        self.metadata["title"] = new_title
        self.metadata["last_updated"] = datetime.now().isoformat()
        self.save_history()
        logger.info(f"Updated title for session {self.session_id}: {new_title}")
    
    def update_session_title_from_message(self, message: str, max_length: int = 50):
        """
        Auto-generate and update session title from a message.
        
        Args:
            message: Message content to generate title from
            max_length: Maximum length for the title
        """
        if not message:
            return
        
        # Clean up the message
        title = message.strip()
        
        # Truncate if too long
        if len(title) > max_length:
            title = title[:max_length].rsplit(' ', 1)[0] + "..."
        
        self.update_session_title(title)
    
    @staticmethod
    def list_all_sessions() -> List[str]:
        """
        List all available session IDs.
        
        Returns:
            List of session ID strings
        """
        try:
            session_files = list(HISTORY_DIR.glob("*.json"))
            return [f.stem for f in session_files]
        except Exception as e:
            logger.error(f"Error listing sessions: {e}")
            return []
    
    @staticmethod
    def load_session(session_id: str) -> Optional['HistoryManager']:
        """
        Load an existing session by ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            HistoryManager instance or None if session doesn't exist
        """
        session_file = HISTORY_DIR / f"{session_id}.json"
        if session_file.exists():
            return HistoryManager(session_id=session_id)
        return None

