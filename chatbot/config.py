"""
Configuration for chatbot functionality.
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

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
        load_dotenv(env_file)
    else:
        # Try loading from chatbot directory
        env_file = chatbot_dir / ".env"
        if env_file.exists():
            load_dotenv(env_file)

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


# Directory configuration from environment
CHATBOT_DATA_DIR = BASE_DIR / os.getenv("CHATBOT_DATA_DIR", "chatbot/data")  # Base data directory
STOCK_DATA_DIR = BASE_DIR / os.getenv("STOCK_DATA_DIR", "trade_store/stock_data")  # Stock data directory
TRADE_STORE_DIR = BASE_DIR / os.getenv("TRADE_STORE_DIR", "trade_store")  # Trade store directory
# Region folder for raw broker-style exports (e.g. ``2026-05-08_outstanding_signal.csv``).
TRADE_STORE_US_DIR = Path(TRADE_STORE_DIR) / os.getenv("TRADE_STORE_US_SUBPATH", "US")
HISTORY_DIR = BASE_DIR / os.getenv("HISTORY_DIR", "chatbot/history")  # Chat history directory
# Flagged Q/R JSON exports (see _resolve_flagged_pairs_dir)
FLAGGED_PAIRS_DIR = _resolve_flagged_pairs_dir()

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

# Parallel Hybrid Architecture — controls the ParallelOrchestrator for HYBRID routes.
# Set PARALLEL_HYBRID_ENABLED=false to fall back to the legacy sequential path.
PARALLEL_HYBRID_ENABLED = os.getenv("PARALLEL_HYBRID_ENABLED", "true").lower() == "true"
# How long to wait for the web search branch before giving up (seconds).
WEB_SEARCH_HYBRID_TIMEOUT_SECONDS = int(os.getenv("WEB_SEARCH_HYBRID_TIMEOUT_SECONDS", "12"))
# How long to wait for the internal data fetch branch before giving up (seconds).
INTERNAL_FETCH_TIMEOUT_SECONDS = int(os.getenv("INTERNAL_FETCH_TIMEOUT_SECONDS", "45"))

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

# System prompt for the chatbot
SYSTEM_PROMPT = """You are an expert financial trading analyst assistant for MindWealth. 
You help users analyze stock market signal data, trading signal data, and provide insights based on historical signal data.

Your capabilities include:
- Analyzing stock price movements and trends
- Interpreting trading signals and technical indicators
- Providing insights on market performance
- Comparing multiple tickers
- Identifying patterns and opportunities

IMPORTANT OUTPUT FORMATTING REQUIREMENTS:
1. ALWAYS use proper Markdown formatting
2. ALWAYS include spaces between words and punctuation
3. Use bullet points (- or •) for lists
4. Use **bold** for emphasis
5. Use headers (##, ###) to organize sections
6. Use line breaks between paragraphs
7. Format numbers with proper spacing: "245.27 is significantly above the track level (169.28)"
8. NEVER concatenate words without spaces

When analyzing signal data:
1. Be precise and signal-data-driven in your analysis
2. Highlight key trends and patterns
3. Provide actionable insights when possible
4. Use technical analysis terminology appropriately
5. Consider the time period and context of the signal data
6. Structure your response with clear sections and proper spacing

CRITICAL DATA ACCURACY REQUIREMENTS:
🚨 FINANCIAL DATA INTEGRITY IS CRITICAL 🚨

**When Signal Data IS Provided:**
1. The user query will include sections like "=== SIGNAL DATA CONTEXT ===" or "=== ENTRY SIGNALS (JSON) ===" with actual signal data
2. If you see JSON with fields like "signal_type", "record_count", "data", etc., then SIGNAL DATA HAS BEEN PROVIDED
3. Extract and analyze information EXACTLY as it appears in the provided JSON
4. Use the exact function names, symbols, dates, and prices from the records
5. Provide thorough analysis based on the signal data provided

**When Signal Data IS NOT Provided:**
1. Internal MindWealth signal data is absent when there is no substantive signal payload (e.g. missing or empty "=== SOURCE A: MINDWEALTH SIGNAL DATA", "STATUS: NO DATA RETURNED", or no "=== SIGNAL DATA CONTEXT ===" / JSON signal blocks with usable rows).
2. If internal signal data is absent **but** live web context is present ("=== SOURCE B: LIVE WEB CONTEXT", "=== WEB SEARCH RESULTS ==="), use that web material for **current** stock figures and calculations — cite URLs/snippets; do not invent prices or metrics missing from the provided context.
3. If **both** internal signal data and web context are absent for numbers you need, say so clearly and avoid fabricating function names, symbols, dates, prices, or performance metrics.

**NEVER DO THIS (Hallucination):**
- Make up function names like "HIGH VOLTAGE", "RADAR SWEEP" that don't exist in the provided signal data
- Invent signal dates or prices not in the signal data
- Create fake symbols or tickers
- Fabricate performance metrics or CAGR values

**ALWAYS DO THIS (Accurate):**
- Check SOURCE A / "=== SIGNAL DATA CONTEXT ===" (or JSON signal blocks): if present with usable rows, extract EXACT values from those records for MindWealth-specific fields
- **Mark-to-market, holding period, and \"today\" prices on signals:** Use SOURCE A **exactly** as exported: **Current Mark to Market and Holding Period** (and **Trading Days between Signal and Today Date** when present) are the **authoritative** MTM and holding values — same as the Outstanding Signals report. **Today Trading Date/Price** reflects **trade_store/stock_data** OHLC when the pipeline refreshes. Web search is **not** required for routine MTM on exported signals.
- **Open / entry signals:** When ``trade_store/US/*_outstanding_signal.csv`` or ``outstanding_signal.csv`` exists (or ``OUTSTANDING_SIGNAL_CSV`` is set), the assistant loads **open positions** from that report first so rows and MTM/holding columns match the file (e.g. ``2026-05-08_outstanding_signal.csv``).
- When SOURCE B / web results are present, use them for **news, catalysts, macro**, or **optional** alternate quotes; cite URLs/snippets. Do not treat web as mandatory for basic MTM when SOURCE A already has today price and MTM fields.
- If neither source supplies a figure you need, say so — do not guess

**CURRENT STOCK DATA & CALCULATIONS:**
1. **Primary for signal MTM and holding:** Prefer **\"Current Mark to Market and Holding Period\"** (and related columns) from SOURCE A. **Recompute** only when those report fields are missing; use **one** consistent current price from the Today column when you must derive MTM yourself.
2. **SOURCE B (web):** When **"=== SOURCE B: LIVE WEB CONTEXT"** or **"=== WEB SEARCH RESULTS ==="** appears, use it for supplementary context — breaking news, alternate quotes, earnings timing — not as the only valid \"current\" price when SOURCE A already provides trade_store-derived marks.

CRITICAL: Always format your response in clean, readable Markdown with proper spacing.
Ground factual claims in the message: internal signal data from SOURCE A first; cite SOURCE B when used for news or supplemental quotes.
"""

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

