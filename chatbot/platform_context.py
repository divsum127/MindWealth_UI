"""
Build the "SOURCE E" prompt block: what MindWealth itself holds — our signal
types, our strategy functions, and the freshness of each backing file.

Without this the assistant answered questions about its own platform from
general knowledge. Two observed failures:

* "give me a short summary about claude report" — the model asked whether
  "Claude" was a stock ticker, while ``claude_report`` is a first-class signal
  type backed by ``chatbot/data/claude_report.txt``, refreshed daily.
* "what signal types exist?" — returned a textbook LONG/SHORT/entry/exit answer
  instead of our taxonomy (entry, exit, portfolio_target_achieved, breadth,
  claude_report) or any of our function names.

The block is cheap: signal types are static, and the function list is read once
from the entry CSV and cached for the process lifetime.
"""

import logging
import os
import re
from datetime import datetime, timezone
from typing import List, Optional

from .config import CSV_ENCODING, ENABLE_PLATFORM_CONTEXT
from .signal_type_selector import ALLOWED_SIGNAL_TYPES, SIGNAL_TYPE_DESCRIPTIONS

logger = logging.getLogger(__name__)

# Mirrors ``llm_router._PLATFORM_VOCAB_RE`` — questions phrased in our own nouns.
_PLATFORM_RELEVANT_RE = re.compile(
    r"\b(claude\s+(\w+\s+)?(report|analysis|shortlist(ed)?( signals?)?)|"
    r"claude.s\s+(report|analysis|shortlist)|comprehensive\s+(analysis\s+)?report|"
    r"shortlist(ed)?\s+signals?)\b"
    r"|\bsignal\s+types?\b"
    r"|\b(which|what)\s+(functions?|strategies|models?|signals?)\b.{0,30}\b(exist|available|have|use|run)\b"
    r"|\bportfolio\s+target\s+achieved\b"
    r"|\bmindwealth\b"
    r"|\bwhat\s+(data|reports?|signals?)\s+(do\s+)?(you|we)\s+(have|hold|track|cover)\b"
    r"|\bwhat\s+can\s+you\s+(do|answer|access)\b",
    re.I,
)

_FUNCTIONS_CACHE: Optional[List[str]] = None


def is_platform_question(user_message: Optional[str]) -> bool:
    """True when the user is asking about the platform itself, not the market."""
    if not user_message or not str(user_message).strip():
        return False
    return bool(_PLATFORM_RELEVANT_RE.search(str(user_message)))


def _data_dir() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def known_functions() -> List[str]:
    """
    Distinct strategy function names, read once from the entry CSV.

    Reads only the ``Function`` column: the full file is ~22 MB and this runs
    inside a chat turn.
    """
    global _FUNCTIONS_CACHE
    if _FUNCTIONS_CACHE is not None:
        return _FUNCTIONS_CACHE
    path = os.path.join(_data_dir(), "entry.csv")
    try:
        import pandas as pd

        col = pd.read_csv(path, usecols=["Function"], encoding=CSV_ENCODING)
        _FUNCTIONS_CACHE = sorted({str(v).strip() for v in col["Function"].dropna() if str(v).strip()})
    except Exception as exc:
        logger.warning(f"Platform context: could not read function list: {exc}")
        _FUNCTIONS_CACHE = []
    return _FUNCTIONS_CACHE


def _file_freshness(filename: str) -> str:
    path = os.path.join(_data_dir(), filename)
    try:
        stamp = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
    except OSError:
        return "not available"
    age_h = (datetime.now(timezone.utc) - stamp).total_seconds() / 3600
    return f"updated {stamp.strftime('%Y-%m-%d %H:%M UTC')} ({age_h:.1f}h ago)"


def build_platform_context(user_message: str) -> Optional[str]:
    """Return the SOURCE E block, or ``None`` when disabled or irrelevant."""
    if not ENABLE_PLATFORM_CONTEXT:
        return None
    if not is_platform_question(user_message):
        return None

    lines = [
        "=== SOURCE E — MINDWEALTH PLATFORM CAPABILITIES (INTERNAL) ===",
        "These are the data categories this assistant can retrieve. Answer "
        "questions about what the platform holds from THIS list — never from "
        "general knowledge, and never guess that a MindWealth term is a stock "
        "ticker.",
        "",
        "Signal types (the exact identifiers used by the system):",
    ]
    files = {
        "entry": "entry.csv",
        "exit": "exit.csv",
        "portfolio_target_achieved": "portfolio_target_achieved.csv",
        "breadth": "breadth.csv",
        "claude_report": "claude_report.txt",
    }
    for key in ALLOWED_SIGNAL_TYPES:
        title, desc = SIGNAL_TYPE_DESCRIPTIONS.get(key, (key, ""))
        lines.append(f"- `{key}` — {title}: {desc.strip()}")
        source = files.get(key)
        if source:
            lines.append(f"    source: chatbot/data/{source} — {_file_freshness(source)}")

    functions = known_functions()
    if functions:
        lines += [
            "",
            f"Strategy functions currently present in the signal data ({len(functions)}):",
            ", ".join(functions),
            "",
            "A 'function' is a MindWealth strategy that generates signals. These "
            "names are ours; they are not public indicators and cannot be looked "
            "up on the web.",
        ]

    lines += [
        "",
        "Also reachable on request: conviction scores and fundamentals (SOURCE C), "
        "macro regime, Runic combos, SSI sentiment and portfolio risk (SOURCE D).",
    ]
    return "\n".join(lines)
