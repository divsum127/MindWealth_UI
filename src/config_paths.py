"""
Shared configuration paths for the entire application.
This module provides consistent paths that can be imported by both chatbot and src modules.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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
CONVICTION_UNIVERSE_FILE = BASE_DIR / os.getenv("CONVICTION_UNIVERSE_FILE", "conviction_universe.txt")

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