"""
MindWealth Trading Strategy Analysis - Main Application
Modular version with organized code structure
"""

import streamlit as st

from constant import *
from src.pages import (
    create_top_signals_dashboard,
    create_analysis_page,
    create_text_file_page,
    create_virtual_trading_page,
    render_chatbot_page,
    create_trade_details_page,
    create_f_stack_page,
    create_all_data_page,
    create_levels_altitude_page
)
from src.pages.monitored_trades_page import create_monitored_trades_page
from src.pages.horizontal_page import create_horizontal_page
from src.utils import discover_csv_files, get_latest_csv_file
from chatbot import SessionManager

# Set page config
st.set_page_config(
    page_title="Trading Strategy Analysis",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        margin: 0.5rem 0;
        cursor: pointer;
        transition: transform 0.2s;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    .metric-value {
        font-size: 2rem;
        font-weight: bold;
        margin: 0;
    }
    .metric-label {
        font-size: 0.9rem;
        opacity: 0.9;
        margin: 0;
    }
    .strategy-card {
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
        background: white;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        cursor: pointer;
        transition: all 0.3s ease;
    }
    .strategy-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        transform: translateY(-2px);
    }
    .positive {
        color: #00C851;
        font-weight: bold;
    }
    .negative {
        color: #ff4444;
        font-weight: bold;
    }
    .neutral {
        color: #ffbb33;
        font-weight: bold;
    }
    
    /* Enable text wrapping in dataframe cells */
    .stDataFrame,
    [data-testid="stDataFrame"] {
        word-wrap: break-word;
        overflow-wrap: break-word;
    }
    
    .stDataFrame td,
    [data-testid="stDataFrame"] td,
    .stDataFrame th,
    [data-testid="stDataFrame"] th {
        white-space: normal !important;
        word-wrap: break-word !important;
        overflow-wrap: break-word !important;
        max-width: 500px;
    }
    
    /* AG Grid specific styling for text wrapping */
    .ag-cell,
    .ag-cell-value {
        white-space: normal !important;
        word-wrap: break-word !important;
        overflow-wrap: break-word !important;
        line-height: 1.5 !important;
    }
    
    /* Ensure cells can expand vertically */
    .ag-row {
        min-height: auto !important;
    }
    
    .ag-cell-wrapper {
        height: auto !important;
        min-height: 30px;
    }
    
    /* Wider default sidebar width */
    [data-testid="stSidebar"] {
        min-width: 250px !important;
        max-width: 400px !important;
    }

    /* Sidebar typography controls */
    [data-testid="stSidebar"] .stMarkdown,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stTextInput label,
    [data-testid="stSidebar"] .stDateInput label,
    [data-testid="stSidebar"] .stToggle label {
        font-size: 0.90rem !important;
    }

    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        font-size: 1.00rem !important;
    }

    [data-testid="stSidebar"] .stButton button p {
        font-size: 0.85rem !important;
        line-height: 1.15 !important;
    }

    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
        font-size: 0.78rem !important;
    }

    /* Reduce vertical spacing between sidebar sections/widgets */
    [data-testid="stSidebar"] hr {
        margin-top: 0.35rem !important;
        margin-bottom: 0.35rem !important;
    }

    [data-testid="stSidebar"] .stMarkdown {
        margin-bottom: 0.15rem !important;
    }

    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        margin-top: 0.25rem !important;
        margin-bottom: 0.25rem !important;
    }

    [data-testid="stSidebar"] .stButton,
    [data-testid="stSidebar"] .stSelectbox,
    [data-testid="stSidebar"] .stTextInput,
    [data-testid="stSidebar"] .stDateInput,
    [data-testid="stSidebar"] .stToggle,
    [data-testid="stSidebar"] .stCaptionContainer,
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] > div {
        margin-top: 0.15rem !important;
        margin-bottom: 0.15rem !important;
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }
</style>
""", unsafe_allow_html=True)


def main():
    """Main application entry point"""
    horizontal_new_high_file = None

    # Add refresh button at the top
    col1, col2 = st.columns([10, 1])
    with col1:
        st.title("📈 Trading Strategy Analysis")
    with col2:
        if st.button("🔄 Refresh", help="Refresh data and reload page"):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.rerun()
    
    # Sidebar Navigation
    st.sidebar.title("Navigation")

    # Add Chat History at the top for chatbot page
    # Check if we're on the chatbot page
    try:
        # We need to peek at what page will be selected
        # Get the current page from session state or default to first option
        csv_files = discover_csv_files()
        page_options = {
            "Dashboard": None,
            "AI Chatbot": "chatbot",
            "Monitored Trades": "monitored_trades",
            "Virtual Trading": "virtual_trading",
            "All Historical Report Signals": "all_data",
            "Claude Shortlisted Signal": "text_files",
            "Trade Details": "trade_details",
        }
        horizontal_new_high_file = get_latest_csv_file("horizontal_new_high_report.csv")
        if horizontal_new_high_file:
            page_options["Horizontal & New High Report"] = "levels_new_high_report"
        page_options.update(csv_files)

        # Get current page selection (default to first option if not set)
        current_page_key = st.sidebar.selectbox(
            "**Select Page**",
            list(page_options.keys()),
            key="page_selector"
        )

        # Keep New Chat action directly under page dropdown on chatbot page.
        if current_page_key == "AI Chatbot":
            if st.sidebar.button("➕ New Chat", use_container_width=True, type="primary"):
                new_session_id = SessionManager.create_new_session()
                st.session_state.current_session_id = new_session_id
                st.session_state.chatbot_engine = None
                st.session_state.chat_history = []
                st.session_state.last_settings = None
                st.rerun()

    except Exception as e:
        # Fallback if there's an issue
        st.sidebar.error(f"Error loading navigation: {e}")
        # Set default page on error
        current_page_key = "Dashboard"
        page_options = {
            "Dashboard": None,
            "AI Chatbot": "chatbot",
            "Monitored Trades": "monitored_trades",
            "Virtual Trading": "virtual_trading",
            "All Historical Report Signals": "all_data",
            "Claude Shortlisted Signal": "text_files",
            "Trade Details": "trade_details",
        }

    st.sidebar.markdown("---")

    # Page selection (keep this for backward compatibility)
    page = current_page_key
    
    # Display selected page
    if page == "Dashboard":
        create_top_signals_dashboard()
    elif page == "AI Chatbot":
        render_chatbot_page()
    elif page == "Monitored Trades":
        create_monitored_trades_page()
    elif page == "Virtual Trading":
        create_virtual_trading_page()
    elif page == "All Historical Report Signals":
        create_all_data_page()
    elif page == "Claude Shortlisted Signal":
        create_text_file_page()
    elif page == "Trade Details":
        create_trade_details_page()
    elif page == "Horizontal & New High Report":
        create_levels_altitude_page(horizontal_new_high_file, page)
    else:
        # Create analysis page for CSV files
        if page in page_options:
            csv_file = page_options[page]
            if csv_file and csv_file not in ["text_files", "virtual_trading", "chatbot"]:
                if page == 'F-Stack':
                    create_f_stack_page(csv_file, page)
                else:
                    create_analysis_page(csv_file, page)
            else:
                st.error(f"No data file found for {page}")
        else:
            st.error(f"Page '{page}' not found in navigation options")


if __name__ == "__main__":
    main()

