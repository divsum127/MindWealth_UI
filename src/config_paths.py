"""
Shared configuration paths for the entire application.
This module provides consistent paths that can be imported by both chatbot and src modules.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Macro Claude client uses ANTHROPIC_API_KEY; accept CLAUDE_API_KEY alias from Streamlit secrets.
if not os.getenv("ANTHROPIC_API_KEY") and os.getenv("CLAUDE_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = os.environ["CLAUDE_API_KEY"]

# Base directory
BASE_DIR = Path(__file__).parent.parent.resolve()

# Directory configuration from environment
CHATBOT_DATA_DIR = BASE_DIR / os.getenv("CHATBOT_DATA_DIR", "chatbot/data")
STOCK_DATA_DIR = BASE_DIR / os.getenv("STOCK_DATA_DIR", "trade_store/stock_data")
TRADE_STORE_DIR = BASE_DIR / os.getenv("TRADE_STORE_DIR", "trade_store")
TRADE_STORE_US_DIR = TRADE_STORE_DIR / "US"  # US specific trade store
HISTORY_DIR = BASE_DIR / os.getenv("HISTORY_DIR", "chatbot/history")
CONVICTION_STORE_DIR = BASE_DIR / os.getenv("CONVICTION_STORE_DIR", "conviction_store")
CONVICTION_OUTPUT_DIR = CONVICTION_STORE_DIR / os.getenv("CONVICTION_OUTPUT_SUBDIR", "overlays")
CONVICTION_DAILY_DIR = CONVICTION_STORE_DIR / os.getenv("CONVICTION_DAILY_SUBDIR", "daily")
CONVICTION_UNIVERSE_FILE = BASE_DIR / os.getenv("CONVICTION_UNIVERSE_FILE", "conviction_universe.txt")

# Macro Intelligence (Runic Agent)
MACRO_INTEL_DIR = BASE_DIR / os.getenv("MACRO_INTEL_DIR", "macro_intelligence")
MACRO_INTEL_DATA_DIR = MACRO_INTEL_DIR / "data"
MACRO_INTEL_OUTPUT_DIR = MACRO_INTEL_DIR / "output"
MACRO_INTEL_DB = Path(os.getenv("MACRO_INTEL_DB", str(MACRO_INTEL_DATA_DIR / "runic.db")))
MACRO_INTEL_JSON_PATH = Path(
    os.getenv("MACRO_INTEL_JSON_PATH", str(MACRO_INTEL_OUTPUT_DIR / "runic_output.json"))
)
MACRO_INTEL_CONFIG = MACRO_INTEL_DIR / "CONFIG.yaml"
SSI_CONFIG = MACRO_INTEL_DIR / "SSI_CONFIG.yaml"
SSI_DATA_DIR = MACRO_INTEL_DATA_DIR / "ssi"
SSI_POSITIONING_JSON = Path(
    os.getenv("SSI_POSITIONING_JSON", str(MACRO_INTEL_OUTPUT_DIR / "positioning.json"))
)
SSI_DB = Path(os.getenv("SSI_DB", str(SSI_DATA_DIR / "ssi.db")))
SSI_ANALYSIS_DIR = MACRO_INTEL_DIR / "analysis" / "ssi_validation"
MINDWEALTH_ROOT = Path(os.getenv("MINDWEALTH_ROOT", "/home/ubuntu/MindWealth"))
MINDWEALTH_TRADE_STORE = Path(
    os.getenv("MINDWEALTH_TRADE_STORE", str(MINDWEALTH_ROOT / "trade_store" / "US"))
)

# Additional data paths
DATA_FETCH_DATETIME_JSON = TRADE_STORE_US_DIR / "data_fetch_datetime.json"
VIRTUAL_TRADING_LONG_CSV = TRADE_STORE_US_DIR / "virtual_trading_long.csv"  
VIRTUAL_TRADING_SHORT_CSV = TRADE_STORE_US_DIR / "virtual_trading_short.csv"

# Data file names from environment
ENTRY_CSV_NAME = os.getenv("ENTRY_CSV_NAME", "entry.csv")
EXIT_CSV_NAME = os.getenv("EXIT_CSV_NAME", "exit.csv")
TARGET_CSV_NAME = os.getenv("TARGET_CSV_NAME", "portfolio_target_achieved.csv")
BREADTH_CSV_NAME = os.getenv("BREADTH_CSV_NAME", "breadth.csv")

# Full paths to consolidated CSV files
CHATBOT_ENTRY_CSV = CHATBOT_DATA_DIR / ENTRY_CSV_NAME
CHATBOT_EXIT_CSV = CHATBOT_DATA_DIR / EXIT_CSV_NAME
CHATBOT_TARGET_CSV = CHATBOT_DATA_DIR / TARGET_CSV_NAME
CHATBOT_BREADTH_CSV = CHATBOT_DATA_DIR / BREADTH_CSV_NAME

# Create necessary directories if they don't exist
HISTORY_DIR.mkdir(parents=True, exist_ok=True)
CHATBOT_DATA_DIR.mkdir(parents=True, exist_ok=True)
CONVICTION_STORE_DIR.mkdir(parents=True, exist_ok=True)
CONVICTION_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CONVICTION_DAILY_DIR.mkdir(parents=True, exist_ok=True)
MACRO_INTEL_DIR.mkdir(parents=True, exist_ok=True)
MACRO_INTEL_DATA_DIR.mkdir(parents=True, exist_ok=True)
MACRO_INTEL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SSI_DATA_DIR.mkdir(parents=True, exist_ok=True)
SSI_ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)