"""
Session Manager for handling multiple chat sessions.
Provides functionality to list, create, load, delete, and rename chat sessions.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from uuid import uuid4

from .config import HISTORY_DIR
from .history_manager import HistoryManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SessionManager:
    """Manages multiple chat sessions for the chatbot."""
    
    @staticmethod
    def create_new_session(title: Optional[str] = None) -> str:
        """
        Create a new chat session.
        
        Args:
            title: Optional title for the session. If None, uses "New Chat"
            
        Returns:
            New session ID
        """
        session_id = str(uuid4())
        session_file = HISTORY_DIR / f"{session_id}.json"
        
        # Create initial session data
        session_data = {
            "metadata": {
                "session_id": session_id,
                "title": title or "New Chat",
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "message_count": 0
            },
            "conversation": []
        }
        
        # Save the session
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Created new session: {session_id}")
        return session_id
    
    @staticmethod
    def list_all_sessions(sort_by: str = 'last_updated') -> List[Dict]:
        """
        List all available chat sessions with their metadata.
        
        Args:
            sort_by: Field to sort by ('last_updated', 'created_at', 'title')
            
        Returns:
            List of session dictionaries with metadata
        """
        try:
            session_files = list(HISTORY_DIR.glob("*.json"))
            sessions = []
            
            for session_file in session_files:
                try:
                    with open(session_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    metadata = data.get("metadata", {})
                    conversation = data.get("conversation", [])
                    
                    def _extract_preview(message: Dict) -> str:
                        metadata = message.get("metadata") or {}
                        preview_text = metadata.get("display_prompt") or message.get("content", "")
                        if 'FOLLOW-UP QUESTION:' in preview_text:
                            preview_text = preview_text.split('FOLLOW-UP QUESTION:', 1)[1].strip()
                        elif 'User Query:' in preview_text:
                            preview_text = preview_text.split('User Query:', 1)[1].strip()
                        if '===' in preview_text:
                            preview_text = preview_text.split('===', 1)[0].strip()
                        return preview_text.strip()
                    
                    first_user_msg = ""
                    for msg in conversation:
                        if msg.get("role") == "user":
                            first_user_msg = _extract_preview(msg)
                            break

                    if len(first_user_msg) > 240:
                        first_user_msg = first_user_msg[:237] + "..."

                    summary = (metadata.get("summary") or "").strip()
                    if not summary and conversation:
                        # Backfill summary for older sessions that predate summary metadata.
                        try:
                            history = HistoryManager(session_id=metadata.get("session_id", session_file.stem))
                            summary = history._generate_session_summary()
                            history.metadata["summary"] = summary
                            history.save_history()
                        except Exception:
                            summary = first_user_msg
                    elif not summary:
                        summary = first_user_msg or "New chat"
                    
                    # Count messages
                    user_messages = len([m for m in conversation if m.get("role") == "user"])
                    assistant_messages = len([m for m in conversation if m.get("role") == "assistant"])
                    
                    sessions.append({
                        "session_id": metadata.get("session_id", session_file.stem),
                        "title": metadata.get("title", "Untitled Chat"),
                        "created_at": metadata.get("created_at", ""),
                        "last_updated": metadata.get("last_updated", ""),
                        "message_count": len(conversation),
                        "user_messages": user_messages,
                        "assistant_messages": assistant_messages,
                        "preview": summary
                    })
                    
                except Exception as e:
                    logger.error(f"Error reading session {session_file.name}: {e}")
                    continue
            
            # Sort sessions
            if sort_by in ['last_updated', 'created_at']:
                sessions.sort(key=lambda x: x.get(sort_by, ''), reverse=True)
            elif sort_by == 'title':
                sessions.sort(key=lambda x: x.get('title', '').lower())
            
            return sessions
            
        except Exception as e:
            logger.error(f"Error listing sessions: {e}")
            return []
    
    @staticmethod
    def get_session_metadata(session_id: str) -> Optional[Dict]:
        """
        Get metadata for a specific session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session metadata dictionary or None if not found
        """
        try:
            session_file = HISTORY_DIR / f"{session_id}.json"
            if not session_file.exists():
                return None
            
            with open(session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            return data.get("metadata", {})
            
        except Exception as e:
            logger.error(f"Error getting session metadata: {e}")
            return None
    
    @staticmethod
    def update_session_title(session_id: str, new_title: str) -> bool:
        """
        Update the title of a session.
        
        Args:
            session_id: Session identifier
            new_title: New title for the session
            
        Returns:
            True if successful, False otherwise
        """
        try:
            session_file = HISTORY_DIR / f"{session_id}.json"
            if not session_file.exists():
                return False
            
            with open(session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            data["metadata"]["title"] = new_title
            data["metadata"]["last_updated"] = datetime.now().isoformat()
            
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Updated title for session {session_id}: {new_title}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating session title: {e}")
            return False
    
    @staticmethod
    def delete_session(session_id: str) -> bool:
        """
        Delete a chat session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            session_file = HISTORY_DIR / f"{session_id}.json"
            if session_file.exists():
                session_file.unlink()
                logger.info(f"Deleted session: {session_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error deleting session: {e}")
            return False
    
    @staticmethod
    def session_exists(session_id: str) -> bool:
        """
        Check if a session exists.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if session exists, False otherwise
        """
        session_file = HISTORY_DIR / f"{session_id}.json"
        return session_file.exists()
    
    @staticmethod
    def auto_generate_title_from_message(message: str, max_length: int = 50) -> str:
        """
        Generate a session title from the first user message.
        
        Args:
            message: User message content
            max_length: Maximum length for the title
            
        Returns:
            Generated title
        """
        if not message:
            return "New Chat"
        
        # Clean up the message
        title = message.strip()
        
        # Truncate if too long
        if len(title) > max_length:
            title = title[:max_length].rsplit(' ', 1)[0] + "..."
        
        return title
    
    @staticmethod
    def get_session_count() -> int:
        """
        Get the total number of sessions.
        
        Returns:
            Number of sessions
        """
        try:
            session_files = list(HISTORY_DIR.glob("*.json"))
            return len(session_files)
        except Exception as e:
            logger.error(f"Error counting sessions: {e}")
            return 0
    
    @staticmethod
    def get_recent_sessions(limit: int = 10) -> List[Dict]:
        """
        Get the most recent chat sessions.
        
        Args:
            limit: Maximum number of sessions to return
            
        Returns:
            List of recent session dictionaries
        """
        all_sessions = SessionManager.list_all_sessions(sort_by='last_updated')
        return all_sessions[:limit]
    
    @staticmethod
    def search_sessions(query: str) -> List[Dict]:
        """
        Search sessions by title or content.
        
        Args:
            query: Search query
            
        Returns:
            List of matching session dictionaries
        """
        all_sessions = SessionManager.list_all_sessions()
        query_lower = query.lower()
        
        matching_sessions = []
        for session in all_sessions:
            title_match = query_lower in session.get("title", "").lower()
            preview_match = query_lower in session.get("preview", "").lower()
            
            if title_match or preview_match:
                matching_sessions.append(session)
        
        return matching_sessions
