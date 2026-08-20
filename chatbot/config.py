"""
Configuration for chatbot functionality.
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from prompts.engine import SYSTEM_PROMPT as _SYSTEM_PROMPT_BASE, TARGET_STOP_ROW_BINDING_RULES

SYSTEM_PROMPT = _SYSTEM_PROMPT_BASE + "\n\n" + TARGET_STOP_ROW_BINDING_RULES

# Try loading from Streamlit secrets first (for deployed apps)
try:
    import streamlit as st
    USING_STREAMLIT_SECRETS = hasattr(st, 'secrets') and len(st.secrets) > 0
except (ImportError, AttributeError, FileNotFoundError):
    USING_STREAMLIT_SECRETS = False

# Load environment variables from .env file (fallback if not using Streamlit secrets)
project_root = Path(__file__).resolve().parent.parent
chatbot_dir = Path(__file__).resolve().parent

if not USING_STREAMLIT_SECRETS:
    # Try loading from project root first
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=False)
    else:
        # Try loading from chatbot directory
        env_file = chatbot_dir / ".env"
        if env_file.exists():
            load_dotenv(env_file, override=False)

# Base directories
BASE_DIR = project_root


def _resolve_flagged_pairs_dir() -> Path:
    """
    Where flagged user/assistant JSON files are written (Streamlit "Flag this exchange").

    Resolution order when Streamlit secrets exist: ``[paths] FLAGGED_PAIRS_DIR`` or top-level
    ``FLAGGED_PAIRS_DIR`` in secrets.toml, then ``$FLAGGED_PAIRS_DIR``, then default
    ``chatbot/flagged_pairs`` under the project root.

    Set an absolute path on EC2 (e.g. ``/home/ubuntu/uiv2/MindWealth_UI/chatbot/flagged_pairs``)
    via systemd ``Environment=`` or secrets so deploys do not depend on cwd.
    """
    raw: Optional[str] = None
    if USING_STREAMLIT_SECRETS:
        try:
            import streamlit as st

            if "paths" in st.secrets and "FLAGGED_PAIRS_DIR" in st.secrets["paths"]:
                raw = str(st.secrets["paths"]["FLAGGED_PAIRS_DIR"]).strip()
            elif "FLAGGED_PAIRS_DIR" in st.secrets:
                raw = str(st.secrets["FLAGGED_PAIRS_DIR"]).strip()
        except Exception:
            pass
    if not raw:
        raw = os.getenv("FLAGGED_PAIRS_DIR", "chatbot/flagged_pairs")
    p = Path(raw).expanduser()
    if p.is_absolute():
        return p
    return BASE_DIR / p


def _resolve_deep_research_logs_dir() -> Path:
    """Per-query Deep Research audit logs: ``dprsh_<uuid>.json``."""
    raw: Optional[str] = None
    if USING_STREAMLIT_SECRETS:
        try:
            import streamlit as st

            if "paths" in st.secrets and "DEEP_RESEARCH_LOGS_DIR" in st.secrets["paths"]:
                raw = str(st.secrets["paths"]["DEEP_RESEARCH_LOGS_DIR"]).strip()
            elif "DEEP_RESEARCH_LOGS_DIR" in st.secrets:
                raw = str(st.secrets["DEEP_RESEARCH_LOGS_DIR"]).strip()
        except Exception:
            pass
    if not raw:
        raw = os.getenv("DEEP_RESEARCH_LOGS_DIR", "chatbot/deep_research_logs")
    p = Path(raw).expanduser()
    if p.is_absolute():
        return p
    return BASE_DIR / p


# Directory configuration from environment
CHATBOT_DATA_DIR = BASE_DIR / os.getenv("CHATBOT_DATA_DIR", "chatbot/data")  # Base data directory
STOCK_DATA_DIR = BASE_DIR / os.getenv("STOCK_DATA_DIR", "trade_store/stock_data")  # Stock data directory
TRADE_STORE_DIR = BASE_DIR / os.getenv("TRADE_STORE_DIR", "trade_store")  # Trade store directory
# Region folder for raw broker-style exports (e.g. ``2026-05-08_outstanding_signal.csv``).
TRADE_STORE_US_DIR = Path(TRADE_STORE_DIR) / os.getenv("TRADE_STORE_US_SUBPATH", "US")
HISTORY_DIR = BASE_DIR / os.getenv("HISTORY_DIR", "chatbot/history")  # Chat history directory
# Flagged Q/R JSON exports (see _resolve_flagged_pairs_dir)
FLAGGED_PAIRS_DIR = _resolve_flagged_pairs_dir()
DEEP_RESEARCH_LOGS_DIR = _resolve_deep_research_logs_dir()

# Data file names from environment
ENTRY_CSV_NAME = os.getenv("ENTRY_CSV_NAME", "entry.csv")
EXIT_CSV_NAME = os.getenv("EXIT_CSV_NAME", "exit.csv")
TARGET_CSV_NAME = os.getenv("TARGET_CSV_NAME", "portfolio_target_achieved.csv")
BREADTH_CSV_NAME = os.getenv("BREADTH_CSV_NAME", "breadth.csv")

# Directory structure
CHATBOT_ENTRY_DIR = CHATBOT_DATA_DIR / "entry"  # Entry signals (open positions)
CHATBOT_EXIT_DIR = CHATBOT_DATA_DIR / "exit"  # Exit signals (completed trades)
CHATBOT_TARGET_DIR = CHATBOT_DATA_DIR / "portfolio_target_achieved"  # Portfolio target achieved signals
CHATBOT_BREADTH_DIR = CHATBOT_DATA_DIR / "breadth"  # Breadth reports (market-wide)
TARGET_MASTER_CSV = CHATBOT_TARGET_DIR / "all_targets.csv"  # Master portfolio target file for dedup

# Consolidated CSV files (new system)
CHATBOT_ENTRY_CSV = CHATBOT_DATA_DIR / ENTRY_CSV_NAME  # Consolidated entry data
CHATBOT_EXIT_CSV = CHATBOT_DATA_DIR / EXIT_CSV_NAME  # Consolidated exit data
CHATBOT_TARGET_CSV = CHATBOT_DATA_DIR / TARGET_CSV_NAME  # Consolidated portfolio target data
CHATBOT_BREADTH_CSV = CHATBOT_DATA_DIR / BREADTH_CSV_NAME  # Consolidated breadth data

# Create necessary directories if they don't exist
HISTORY_DIR.mkdir(parents=True, exist_ok=True)
FLAGGED_PAIRS_DIR.mkdir(parents=True, exist_ok=True)
DEEP_RESEARCH_LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Outstanding-signal CSV (see ``outstanding_paths``). Use absolute import because some modules
# load this file as top-level ``config`` (``from config import …``), where relative imports fail.
try:
    from chatbot.outstanding_paths import resolve_outstanding_signal_path
except ImportError:  # noqa: E402
    from outstanding_paths import resolve_outstanding_signal_path  # type: ignore

# Max lines of Python logging attached to response metadata per request (flagged JSON export)
ENGINE_LOG_LINES_CAP = int(os.getenv("ENGINE_LOG_LINES_CAP", "1500"))


# Helper function to get API key from Streamlit secrets (DEPRECATED - using Claude now)
def get_api_key() -> str:
    """Get OpenAI API key from Streamlit secrets or environment variables. DEPRECATED - kept for backward compatibility."""
    if USING_STREAMLIT_SECRETS:
        try:
            import streamlit as st
            # Try openai section first, then root level
            if "openai" in st.secrets and "OPENAI_API_KEY" in st.secrets["openai"]:
                return st.secrets["openai"]["OPENAI_API_KEY"]
            elif "OPENAI_API_KEY" in st.secrets:
                return st.secrets["OPENAI_API_KEY"]
        except Exception:
            pass
    # Fallback to environment variable
    return os.getenv("OPENAI_API_KEY", "")

# OpenAI Configuration (DEPRECATED - using Claude for all operations now)
# API Key from Streamlit secrets (secure)
OPENAI_API_KEY = get_api_key()

# Claude Configuration (for all chatbot operations - extraction AND responses)
def get_claude_api_key() -> str:
    """Get Claude API key from Streamlit secrets or environment variables."""
    if USING_STREAMLIT_SECRETS:
        try:
            import streamlit as st
            if "anthropic" in st.secrets and "CLAUDE_API_KEY" in st.secrets["anthropic"]:
                return st.secrets["anthropic"]["CLAUDE_API_KEY"]
            elif "CLAUDE_API_KEY" in st.secrets:
                return st.secrets["CLAUDE_API_KEY"]
        except Exception:
            pass
    return os.getenv("CLAUDE_API_KEY", "")

CLAUDE_API_KEY = get_claude_api_key()
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")

# Tavily Web Search Configuration
def get_tavily_api_key() -> str:
    """Get Tavily API key from Streamlit secrets or environment variables."""
    if USING_STREAMLIT_SECRETS:
        try:
            import streamlit as st
            if "tavily" in st.secrets and "TAVILY_API_KEY" in st.secrets["tavily"]:
                return st.secrets["tavily"]["TAVILY_API_KEY"]
            elif "TAVILY_API_KEY" in st.secrets:
                return st.secrets["TAVILY_API_KEY"]
        except Exception:
            pass
    return os.getenv("TAVILY_API_KEY", "")

TAVILY_API_KEY = get_tavily_api_key()
ENABLE_WEB_SEARCH = os.getenv("ENABLE_WEB_SEARCH", "true").lower() == "true"
WEB_SEARCH_MAX_RESULTS = int(os.getenv("WEB_SEARCH_MAX_RESULTS", "3"))
WEB_SEARCH_MAX_CHARS_PER_RESULT = int(os.getenv("WEB_SEARCH_MAX_CHARS_PER_RESULT", "1500"))
# Lower default — Tavily scores vary; WebSearchAgent falls back to top-N if none pass threshold
WEB_SEARCH_MIN_RELEVANCE_SCORE = float(os.getenv("WEB_SEARCH_MIN_RELEVANCE_SCORE", "0.15"))
# A web quote older than this many days (measured against MindWealth's own data
# as-of date, not wall clock) may not be used for prices. An NVDA quote dated
# 2026-07-18 once sat beside a live internal price with nothing marking it stale.
# Sources beyond the limit stay in the prompt for narrative context.
WEB_QUOTE_MAX_AGE_DAYS = int(os.getenv("WEB_QUOTE_MAX_AGE_DAYS", "2"))

# Parallel Hybrid Architecture — controls the ParallelOrchestrator for HYBRID routes.
# Set PARALLEL_HYBRID_ENABLED=false to fall back to the legacy sequential path.
PARALLEL_HYBRID_ENABLED = os.getenv("PARALLEL_HYBRID_ENABLED", "true").lower() == "true"
# How long to wait for the web search branch before giving up (seconds).
WEB_SEARCH_HYBRID_TIMEOUT_SECONDS = int(os.getenv("WEB_SEARCH_HYBRID_TIMEOUT_SECONDS", "12"))
# How long to wait for the internal data fetch branch before giving up (seconds).
INTERNAL_FETCH_TIMEOUT_SECONDS = int(os.getenv("INTERNAL_FETCH_TIMEOUT_SECONDS", "45"))

# Deep Research — multi-step plan → subtask execution → gap refinement → synthesis
ENABLE_DEEP_RESEARCH = os.getenv("ENABLE_DEEP_RESEARCH", "true").lower() == "true"
DEEP_RESEARCH_MAX_SUBTASKS = int(os.getenv("DEEP_RESEARCH_MAX_SUBTASKS", "8"))
DEEP_RESEARCH_MAX_ROUNDS = int(os.getenv("DEEP_RESEARCH_MAX_ROUNDS", "2"))
DEEP_RESEARCH_WEB_TIMEOUT_SECONDS = int(os.getenv("DEEP_RESEARCH_WEB_TIMEOUT_SECONDS", "45"))
DEEP_RESEARCH_INTERNAL_TIMEOUT_SECONDS = int(os.getenv("DEEP_RESEARCH_INTERNAL_TIMEOUT_SECONDS", "60"))
DEEP_RESEARCH_WEB_MAX_RESULTS = int(os.getenv("DEEP_RESEARCH_WEB_MAX_RESULTS", "8"))
DEEP_RESEARCH_WEB_MAX_QUERIES_PER_SUBTASK = int(os.getenv("DEEP_RESEARCH_WEB_MAX_QUERIES_PER_SUBTASK", "4"))
DEEP_RESEARCH_MAX_WEB_CHARS = int(os.getenv("DEEP_RESEARCH_MAX_WEB_CHARS", "12000"))
# Also the client's job-poll budget: the UI reads this from /chatbot/config and
# polls for (value + 30)s. At 120 a legitimate 147s answer was completed, then
# discarded — the UI gave up 3s early and showed "Could not reach the analyst".
# 300 → ~330s budget, comfortably clear of the UI's 30s poll granularity.
DEEP_RESEARCH_TOTAL_TIMEOUT_SECONDS = int(os.getenv("DEEP_RESEARCH_TOTAL_TIMEOUT_SECONDS", "300"))
DEEP_RESEARCH_PLANNER_MODEL = os.getenv("DEEP_RESEARCH_PLANNER_MODEL", "gpt-4o-mini")
ENABLE_DEEP_RESEARCH_LOGGING = os.getenv("ENABLE_DEEP_RESEARCH_LOGGING", "true").lower() == "true"
DEEP_RESEARCH_LOG_MAX_CONTENT_CHARS = int(os.getenv("DEEP_RESEARCH_LOG_MAX_CONTENT_CHARS", "2000"))
ENABLE_DEEP_RESEARCH_PRICE_DATA = os.getenv("ENABLE_DEEP_RESEARCH_PRICE_DATA", "true").lower() == "true"
DEEP_RESEARCH_PRICE_DATA_SOURCE = os.getenv("DEEP_RESEARCH_PRICE_DATA_SOURCE", "yfinance")
DEEP_RESEARCH_MIN_PRECEDENTS = int(os.getenv("DEEP_RESEARCH_MIN_PRECEDENTS", "3"))
ENABLE_LLM_EVENT_DATE_EXTRACTION = (
    os.getenv("ENABLE_LLM_EVENT_DATE_EXTRACTION", "true").lower() == "true"
)

# NZ OHLC fallbacks when yfinance has no delisted NZ history (Stooq / NZXplorer / NZX API)
ENABLE_STOOQ_OHLC_FALLBACK = os.getenv("ENABLE_STOOQ_OHLC_FALLBACK", "true").lower() == "true"
ENABLE_NZX_OHLC_FALLBACK = os.getenv("ENABLE_NZX_OHLC_FALLBACK", "true").lower() == "true"
STOOQ_API_KEY = os.getenv("STOOQ_API_KEY", "").strip() or None
NZXPLORER_API_KEY = os.getenv("NZXPLORER_API_KEY", "").strip() or None
NZX_API_KEY = os.getenv("NZX_API_KEY", "").strip() or None
STOOQ_REQUEST_TIMEOUT_SECONDS = float(os.getenv("STOOQ_REQUEST_TIMEOUT_SECONDS", "12"))
NZX_PRICE_REQUEST_TIMEOUT_SECONDS = float(os.getenv("NZX_PRICE_REQUEST_TIMEOUT_SECONDS", "15"))
CACHE_NZ_OHLC_TO_TRADE_STORE = os.getenv("CACHE_NZ_OHLC_TO_TRADE_STORE", "true").lower() == "true"

# Conviction & signal-quality context (SOURCE C) — see chatbot/conviction_context.py.
# Pulls ranked buy/exit lists, Signal Quality Composite Scores, conviction scores
# and fundamentals from our own REST API. Only fetched for recommendation /
# screening / quality questions, so ordinary turns take no extra latency.
ENABLE_CONVICTION_CONTEXT = os.getenv("ENABLE_CONVICTION_CONTEXT", "true").lower() == "true"
# Empty → derived from API_PORT at call time (chatbot/tools/mindwealth_api_client.py).
MINDWEALTH_API_BASE_URL = os.getenv("MINDWEALTH_API_BASE_URL", "").strip()
CONVICTION_CONTEXT_TIMEOUT_SECONDS = float(os.getenv("CONVICTION_CONTEXT_TIMEOUT_SECONDS", "8"))
CONVICTION_CONTEXT_MAX_ROWS = int(os.getenv("CONVICTION_CONTEXT_MAX_ROWS", "25"))
# Only the model book exposes Sizer/Risk entries and exits; brokerage is pending
# IBKR integration and personal has no Sizer concept.
CONVICTION_BOOK_ID = os.getenv("CONVICTION_BOOK_ID", "model").strip() or "model"

# Macro regime & sentiment context (SOURCE D) — see chatbot/macro_context.py.
# Pulls the Runic nightly regime, SSI summary and portfolio risk posture from our
# own REST API. Without it, macro questions were answered from web search and
# contradicted the engine's own regime call. Gated on macro wording, so ordinary
# turns take no extra latency.
ENABLE_MACRO_CONTEXT = os.getenv("ENABLE_MACRO_CONTEXT", "true").lower() == "true"
MACRO_CONTEXT_BOOK_ID = os.getenv("MACRO_CONTEXT_BOOK_ID", "model").strip() or "model"

# Platform capability context (SOURCE E) — see chatbot/platform_context.py.
# A static description of our own signal types plus the live function list, so
# "what signal types exist" and "summarise the claude report" are answered from
# our taxonomy instead of generic textbook definitions.
ENABLE_PLATFORM_CONTEXT = os.getenv("ENABLE_PLATFORM_CONTEXT", "true").lower() == "true"

# LLM Router — decides web vs internal vs conversational (gpt-4o-mini JSON)
LLM_ROUTER_ENABLED = os.getenv("LLM_ROUTER_ENABLED", "true").lower() == "true"
LLM_ROUTER_MODEL = os.getenv("LLM_ROUTER_MODEL", "gpt-4o-mini")
CLAUDE_MAX_TOKENS = int(os.getenv("CLAUDE_MAX_TOKENS", "6000"))
CLAUDE_TEMPERATURE = float(os.getenv("CLAUDE_TEMPERATURE", "0.2"))
CLAUDE_INPUT_TRUNCATION_TARGET_RATIO = float(os.getenv("CLAUDE_INPUT_TRUNCATION_TARGET_RATIO", "0.75"))

# All other config from .env file (DEPRECATED OpenAI settings kept for backward compatibility)
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.2")  # DEPRECATED - using Claude now
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "8000"))  # Output tokens (response length)
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.1"))  # DEPRECATED - using CLAUDE_TEMPERATURE now

# Token limits - Smart batch processing automatically handles any data size
MAX_INPUT_TOKENS_PER_CALL = int(os.getenv("MAX_INPUT_TOKENS_PER_CALL", "60000"))  # Token limit per batch
MAX_SEQUENTIAL_BATCHES = int(os.getenv("MAX_SEQUENTIAL_BATCHES", "999"))  # NO LIMIT - Process as many batches as needed
BATCH_DELAY_SECONDS = float(os.getenv("BATCH_DELAY_SECONDS", "5.0"))  # Delay between batches to avoid rate limits
ESTIMATED_CHARS_PER_TOKEN = 4  # Rough estimate: 1 token ≈ 4 characters
MIN_HISTORY_MESSAGES = 2  # Minimum messages to keep in history
ENABLE_BATCH_PROCESSING = True  # Smart batch processing always enabled for optimal performance

# Smart Filtering Settings
# When smart filtering is enabled, the system automatically determines which tickers to process:
# - If function(s) specified: ALL tickers with that function (no limit)
# - If ticker(s) specified: Only those tickers
# - If both specified: Intersection of tickers that have the function
# - Batch processing automatically handles any number of tickers efficiently

# Data processing settings
DATE_FORMAT = "%Y-%m-%d"
CSV_ENCODING = "utf-8"
MAX_ROWS_TO_INCLUDE = int(os.getenv("MAX_ROWS_TO_INCLUDE", "100"))  # Max rows per ticker (balanced for speed)
# Single-asset deep dive: higher cap (0 = unlimited after date filter + dedupe)
MAX_ROWS_DEEP_DIVE = int(os.getenv("MAX_ROWS_DEEP_DIVE", "500"))

# Conversation settings
MAX_HISTORY_LENGTH = int(os.getenv("MAX_HISTORY_LENGTH", "15"))  # Max conversation turns to keep
MAX_EXTRACTION_HISTORY_LENGTH = int(os.getenv("MAX_EXTRACTION_HISTORY_LENGTH", "5"))  # Max history for extraction calls (lighter)

# Chat History UI Settings
MAX_CHATS_DISPLAY = int(os.getenv("MAX_CHATS_DISPLAY", "10"))  # Max number of chats to show in sidebar (default: 10)

# ── Rolling Memory Log ────────────────────────────────────────────────────────
# Cross-session stateful memory that bridges the "amnesia gap" across days.
# Memory entries are extracted from completed sessions and injected into the
# system prompt of new sessions.
MEMORY_MAX_AGE_DAYS = int(os.getenv("MEMORY_MAX_AGE_DAYS", "30"))       # Drop entries older than N days
MEMORY_MAX_ENTRIES = int(os.getenv("MEMORY_MAX_ENTRIES", "50"))          # Hard cap on stored entries
MEMORY_MAX_CONTEXT_ENTRIES = int(os.getenv("MEMORY_MAX_CONTEXT_ENTRIES", "8"))  # Entries injected per session
MEMORY_MIN_TURNS_TO_SAVE = int(os.getenv("MEMORY_MIN_TURNS_TO_SAVE", "2"))  # Min user turns before saving memory

# ── Prompt Changelog ──────────────────────────────────────────────────────────
# Lightweight versioning of all named prompts.  On each engine start-up the
# current prompt content is compared against the last recorded hash; if changed,
# a new version entry (with reason) is appended automatically.
PROMPT_CHANGELOG_ENABLED = os.getenv("PROMPT_CHANGELOG_ENABLED", "true").lower() == "true"

# Data deduplication settings
DEDUP_COLUMNS = os.getenv("DEDUP_COLUMNS", "Function,Symbol,Interval,Signal,Signal Open Price").split(",")  # Columns to use for deduplication
BREADTH_DEDUP_COLUMNS = os.getenv("BREADTH_DEDUP_COLUMNS", "Function,Date").split(",")  # Columns to use for breadth deduplication

