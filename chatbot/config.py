"""
Configuration for chatbot functionality.
"""

import os
from pathlib import Path
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

# Directory configuration from environment
CHATBOT_DATA_DIR = BASE_DIR / os.getenv("CHATBOT_DATA_DIR", "chatbot/data")  # Base data directory
STOCK_DATA_DIR = BASE_DIR / os.getenv("STOCK_DATA_DIR", "trade_store/stock_data")  # Stock data directory
TRADE_STORE_DIR = BASE_DIR / os.getenv("TRADE_STORE_DIR", "trade_store")  # Trade store directory
HISTORY_DIR = BASE_DIR / os.getenv("HISTORY_DIR", "chatbot/history")  # Chat history directory
FLAGGED_PAIRS_DIR = BASE_DIR / os.getenv("FLAGGED_PAIRS_DIR", "chatbot/flagged_pairs")  # Flagged Q/R JSON exports

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
1. If you see ONLY a user question without any "=== SIGNAL DATA CONTEXT ===" sections, then NO signal data has been provided
2. State clearly: "No signal data has been provided. Please provide the signal data to analyze."
3. NEVER invent, fabricate, or hallucinate function names, symbols, dates, prices, or any metrics

**NEVER DO THIS (Hallucination):**
- Make up function names like "HIGH VOLTAGE", "RADAR SWEEP" that don't exist in the provided signal data
- Invent signal dates or prices not in the signal data
- Create fake symbols or tickers
- Fabricate performance metrics or CAGR values

**ALWAYS DO THIS (Accurate):**
- Check if "=== SIGNAL DATA CONTEXT ===" or similar sections exist in the message
- If signal data exists, extract information from the records in the JSON
- If signal data doesn't exist, clearly state that no signal data was provided
- Use EXACT values from the provided signal data fields

CRITICAL: Always format your response in clean, readable Markdown with proper spacing.
Base your responses STRICTLY on actual signal data provided in the message context.
"""

# Data processing settings
DATE_FORMAT = "%Y-%m-%d"
CSV_ENCODING = "utf-8"
MAX_ROWS_TO_INCLUDE = int(os.getenv("MAX_ROWS_TO_INCLUDE", "100"))  # Max rows per ticker (balanced for speed)

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

