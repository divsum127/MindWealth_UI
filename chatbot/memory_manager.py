"""
Rolling memory log for cross-session stateful memory.

Maintains a compact, rolling log of key facts and user preferences
extracted from past conversations, bridging the "amnesia gap" across days.

Architecture
------------
- chatbot/memory/rolling_log.json  — the persisted store
- RollingMemoryLog                 — manages add / prune / inject
- extract_memory_from_conversation — LLM call that summarises one session
"""

import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from prompts.engine import format_memory_extraction_prompt

logger = logging.getLogger(__name__)

_CHATBOT_DIR = Path(__file__).resolve().parent
MEMORY_DIR = _CHATBOT_DIR / "memory"
MEMORY_LOG_FILE = MEMORY_DIR / "rolling_log.json"

# Configurable defaults
DEFAULT_MAX_AGE_DAYS: int = 30
DEFAULT_MAX_ENTRIES: int = 50
DEFAULT_MAX_CONTEXT_ENTRIES: int = 8  # injected per new session


class RollingMemoryLog:
    """
    A size-bounded, time-pruned log of cross-session memories.

    Each entry is a compact summary of one conversation session, carrying
    extracted tickers, topics, user preferences, and key facts.
    Entries older than *max_age_days* are pruned transparently on every
    load and save, so the store never grows unboundedly.

    Typical lifecycle
    -----------------
    1. Instantiate on engine start-up (loads and prunes automatically).
    2. Call ``build_memory_context()`` to get text for the system prompt.
    3. After a session ends, call ``add_entry(...)`` with extracted facts.
    """

    def __init__(
        self,
        max_age_days: int = DEFAULT_MAX_AGE_DAYS,
        max_entries: int = DEFAULT_MAX_ENTRIES,
    ) -> None:
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        self.max_age_days = max_age_days
        self.max_entries = max_entries
        self.entries: List[Dict[str, Any]] = []
        self._load()

    # ── persistence ────────────────────────────────────────────────────────

    def _load(self) -> None:
        if MEMORY_LOG_FILE.exists():
            try:
                with open(MEMORY_LOG_FILE, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                self.entries = data.get("entries", [])
            except Exception as exc:
                logger.error(f"Failed to load memory log: {exc}")
                self.entries = []
        self._prune()

    def _save(self) -> None:
        self._prune()
        try:
            with open(MEMORY_LOG_FILE, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "version": "1.0",
                        "last_updated": datetime.now().isoformat(),
                        "entries": self.entries,
                    },
                    fh,
                    indent=2,
                    ensure_ascii=False,
                )
        except Exception as exc:
            logger.error(f"Failed to save memory log: {exc}")

    def _prune(self) -> None:
        """Drop entries older than max_age_days and enforce the hard cap."""
        cutoff = datetime.now() - timedelta(days=self.max_age_days)
        self.entries = [
            e
            for e in self.entries
            if datetime.fromisoformat(e.get("timestamp", "2000-01-01T00:00:00")) >= cutoff
        ]
        # Keep only the newest N entries
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries :]

    # ── write ──────────────────────────────────────────────────────────────

    def add_entry(
        self,
        session_id: str,
        summary: str,
        key_facts: List[str],
        tickers: Optional[List[str]] = None,
        topics: Optional[List[str]] = None,
        conversation_turns: int = 0,
    ) -> Dict[str, Any]:
        """Persist a memory entry for the completed *session_id*."""
        entry: Dict[str, Any] = {
            "id": str(uuid4()),
            "session_id": session_id,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "timestamp": datetime.now().isoformat(),
            "summary": summary,
            "key_facts": key_facts or [],
            "tickers": tickers or [],
            "topics": topics or [],
            "conversation_turns": conversation_turns,
        }
        self.entries.append(entry)
        self._save()
        logger.info(f"Memory entry added for session {session_id}")
        return entry

    # ── read ───────────────────────────────────────────────────────────────

    def get_recent_entries(self, n: int = DEFAULT_MAX_CONTEXT_ENTRIES) -> List[Dict[str, Any]]:
        """Return the *n* most recent entries, oldest first."""
        return self.entries[-n:] if len(self.entries) >= n else list(self.entries)

    def build_memory_context(self, max_entries: int = DEFAULT_MAX_CONTEXT_ENTRIES) -> str:
        """
        Build a compact memory block suitable for appending to the system prompt.

        Returns an empty string when there are no memories, so callers can
        safely do ``system_prompt + memory.build_memory_context()`` without
        adding noise on fresh installs.
        """
        recent = self.get_recent_entries(max_entries)
        if not recent:
            return ""

        lines: List[str] = [
            "\n\n=== MEMORY FROM PREVIOUS SESSIONS ===",
            "Use these remembered facts to provide continuity across conversations.",
        ]
        for entry in recent:
            date = entry.get("date", "unknown date")
            summary = entry.get("summary", "")
            key_facts = entry.get("key_facts", [])
            tickers = entry.get("tickers", [])

            lines.append(f"\n[{date}]")
            if summary:
                lines.append(f"  Summary: {summary}")
            if tickers:
                lines.append(f"  Tickers discussed: {', '.join(tickers)}")
            for fact in key_facts:
                lines.append(f"  • {fact}")

        lines.append("\n=== END OF MEMORY ===")
        return "\n".join(lines)

    def stats(self) -> Dict[str, Any]:
        """Return a quick overview of the current memory store."""
        return {
            "total_entries": len(self.entries),
            "oldest_date": self.entries[0]["date"] if self.entries else None,
            "newest_date": self.entries[-1]["date"] if self.entries else None,
            "max_age_days": self.max_age_days,
            "max_entries": self.max_entries,
        }


# ── LLM-based extraction ───────────────────────────────────────────────────


def extract_memory_from_conversation(
    conversation: List[Dict[str, Any]],
    session_id: str,
    claude_client: Any,
    claude_model: str,
) -> Optional[Dict[str, Any]]:
    """
    Use Claude to extract a compact memory summary from a completed conversation.

    Only runs for sessions with at least 2 user turns (lightweight guard).
    Large data payloads are stripped before sending to keep token cost minimal.

    Returns a dict ready for ``RollingMemoryLog.add_entry(**result)``,
    or *None* on failure / insufficient conversation length.
    """
    user_turns = [m for m in conversation if m.get("role") == "user"]
    if len(user_turns) < 2:
        return None

    # Build a stripped, token-efficient transcript
    transcript_parts: List[str] = []
    for msg in conversation:
        role = msg.get("role", "")
        if role == "system":
            continue
        content = msg.get("content", "")
        # Remove heavy data sections (JSON dumps, CSV blobs, etc.)
        content = re.sub(
            r"===\s*[A-Z _()]+\s*===[\s\S]*?(?====|\Z)", "", content, flags=re.IGNORECASE
        )
        content = content.strip()[:600]
        if content:
            transcript_parts.append(f"{role.upper()}: {content}")

    if not transcript_parts:
        return None

    transcript = "\n".join(transcript_parts[:30])  # cap at 30 messages

    extraction_prompt = format_memory_extraction_prompt(transcript)

    try:
        response = claude_client.messages.create(
            model=claude_model,
            max_tokens=300,
            temperature=0.0,
            messages=[{"role": "user", "content": extraction_prompt}],
        )
        raw = response.content[0].text.strip()
        # Strip accidental markdown fences
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        data = json.loads(raw)

        return {
            "session_id": session_id,
            "summary": str(data.get("summary", ""))[:120],
            "key_facts": [str(f)[:80] for f in data.get("key_facts", [])[:4]],
            "tickers": data.get("tickers", []),
            "topics": data.get("topics", []),
            "conversation_turns": len(user_turns),
        }
    except Exception as exc:
        logger.warning(f"Memory extraction failed for session {session_id}: {exc}")
        return None
