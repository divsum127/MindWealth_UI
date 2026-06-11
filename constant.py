# Sidebar page feature flags — set False to hide a page from the navigation dropdown.
# Keys must match the exact labels shown in the "Select Page" dropdown.
PAGE_FEATURE_FLAGS = {
    "Dashboard": True,
    "AI Chatbot": True,
    "Conviction Engine": True,
    "Runic Macro Intelligence": True,
    "Monitored Trades": True,
    "Virtual Trading": True,
    "All Historical Report Signals": True,
    "Claude Shortlisted Signal": True,
    "Trade Details": True,
    "Horizontal & New High Report": True,
    # CSV-backed report pages (from trade_store/US discovery)
    "All Signal Report": True,
    "Signal Breadth Indicator (SBI)": True,
    "Outstanding Signals": True,
    "Portfolio Risk Management": True,
    "New Signals": True,
    "Combined Performance Report": True,
    "F-Stack": True,
}


def filter_pages_by_feature_flags(page_options: dict) -> dict:
    """Keep only pages enabled in PAGE_FEATURE_FLAGS (unknown keys default to visible)."""
    return {
        name: path
        for name, path in page_options.items()
        if PAGE_FEATURE_FLAGS.get(name, True)
    }


# AI Chatbot and sidebar UI element visibility — set False to hide a control.
UI_FEATURE_FLAGS = {
    # app.py — shown when "AI Chatbot" page is selected
    "new_chat_button": True,
    # chatbot_page.py — sidebar
    "date_range_picker": True,
    "deep_dive_section": True,
    "analyze_asset_button": True,
    "signal_insights_button": True,
    "breadth_analysis_button": True,
    "signal_types_section": True,
    "web_search_toggle": False,
    "llm_router_toggle": False,
    "deep_research_toggle": True,
    "chat_history_sidebar": True,
    "clear_current_chat_button": True,
    # chatbot_page.py — main area
    "info_about_page_button": True,
    "flag_exchange_panel": True,
    "chat_input": True,
}

# Values used when the matching toggle is hidden (engine + session state).
UI_FEATURE_DEFAULTS = {
    "web_search_enabled": True,
    "llm_router_enabled": True,
    "deep_research_enabled": False,
}


def ui_feature_enabled(key: str) -> bool:
    """Return True if a UI element flag is enabled (unknown keys default to visible)."""
    return UI_FEATURE_FLAGS.get(key, True)


OUTSTANDING_SIGNAL_CSV_PATH_US = "./trade_store/US/outstanding_signal.csv"

BREADTH_CSV_PATH_US = "./trade_store/US/breadth.csv"
# Breadth SBI consolidated CSV (trade-arrival history for chart)
BREADTH_SIGNAL_STORE_CSV_PATH_US = "./chatbot/data/breadth.csv"
# Deprecated legacy breadth store (Bullish % only)
BREADTH_LEGACY_STORE_CSV_PATH_US = "./trade_store/US/breadth_us.csv"

TARGET_SIGNAL_CSV_PATH_US = "./trade_store/US/target_signal.csv"

NEW_SIGNAL_CSV_PATH_US = "./trade_store/US/new_signal.csv"

# CSV PATHS for India-specific reports
F_STACK_ANALYZER_REPORT_CSV_PATH_INDIA = "./trade_store/INDIA/F-Stack-Analyzer.csv"

# Claude REPORT PATHS
GPT_SIGNALS_REPORT_TXT_PATH_US = "./trade_store/US/claude_signals_report.txt"
GPT_SIGNALS_REPORT_CSV_PATH_US = "./trade_store/US/claude_signals_report.csv"

