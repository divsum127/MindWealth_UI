"""
UI Card Components for displaying trading strategy information
"""

import streamlit as st
import pandas as pd

from .charts import create_interactive_chart, create_outstanding_signal_chart
from ..utils.helpers import format_days


def create_summary_cards(df):
    """Create summary metric cards"""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        avg_win_rate = df['Win_Rate'].mean()
        st.markdown(f"""
        <div class="metric-card">
            <p class="metric-value">{avg_win_rate:.1f}%</p>
            <p class="metric-label">Average Win Rate</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        total_trades = len(df['Num_Trades'])
        st.markdown(f"""
        <div class="metric-card">
            <p class="metric-value">{total_trades}</p>
            <p class="metric-label">Total Trades</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        avg_cagr = df['Strategy_CAGR'].mean()
        color_class = "positive" if avg_cagr > 0 else "negative"
        st.markdown(f"""
        <div class="metric-card">
            <p class="metric-value {color_class}">{avg_cagr:.1f}%</p>
            <p class="metric-label">Average Strategy CAGR</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        avg_sharpe = df['Strategy_Sharpe'].mean()
        st.markdown(f"""
        <div class="metric-card">
            <p class="metric-value">{avg_sharpe:.2f}</p>
            <p class="metric-label">Average Sharpe Ratio</p>
        </div>
        """, unsafe_allow_html=True)


def _filter_df_by_asset_search(df, search_query):
    """Filter dataframe by asset/symbol name. Returns filtered df."""
    if not search_query or not search_query.strip():
        return df
    search_lower = search_query.strip().lower()
    if 'Symbol' in df.columns:
        mask = df['Symbol'].astype(str).str.lower().str.contains(search_lower, na=False)
        return df[mask].copy()
    if 'Symbol, Signal, Signal Date/Price[$]' in df.columns:
        def _extract_symbol(val):
            if pd.isna(val): return ""
            s = str(val).strip()
            return s.split(',')[0].strip().lower() if ',' in s else s.lower()
        mask = df['Symbol, Signal, Signal Date/Price[$]'].apply(
            lambda x: search_lower in _extract_symbol(x)
        )
        return df[mask].copy()
    return df


def create_strategy_cards(df, page_name="Unknown", tab_context=""):
    """Create individual strategy cards with pagination for large datasets. Returns filtered df for use in detail table."""
    # Search box - filter by asset name
    search_key = f"asset_search_{page_name}_{tab_context}".replace(" ", "_")
    search_query = st.text_input(
        "🔍 Search by asset name",
        key=search_key,
        placeholder="Type asset symbol to filter cards and table...",
        help="Filter strategy cards and detail table by asset/symbol name"
    )
    filtered_df = _filter_df_by_asset_search(df, search_query)

    st.markdown("### 📊 Strategy Performance Cards")
    st.markdown("Click on any card to see important trade details")
    
    total_signals = len(filtered_df)
    
    if total_signals == 0:
        st.warning("No signal data matches the current filters.")
        return filtered_df
    # Display total count
    st.markdown(f"**Total Signals: {total_signals}**")
    
    # Pagination settings for strategy cards - 30 per tab for Signal Analysis
    cards_per_page = 30
    total_pages = (total_signals + cards_per_page - 1) // cards_per_page
    
    # Create tabs for pagination - always use tabs instead of dropdown
    if total_signals <= cards_per_page:
        # If all signals fit in one page, just display them
        display_strategy_cards_page(filtered_df, page_name, tab_context)
    else:
        # Generate tab labels
        tab_labels = []
        for i in range(total_pages):
            start_idx = i * cards_per_page + 1
            end_idx = min((i + 1) * cards_per_page, total_signals)
            tab_labels.append(f"#{start_idx}-{end_idx}")
        
        
        # Create tabs for all pages
        tabs = st.tabs(tab_labels)
        for i, tab in enumerate(tabs):
            with tab:
                start_idx = i * cards_per_page
                end_idx = min((i + 1) * cards_per_page, total_signals)
                page_df = filtered_df.iloc[start_idx:end_idx]
                st.markdown(f"**Showing signals {start_idx + 1} to {end_idx} of {total_signals}**")
                # Add pagination context to make keys unique across pagination tabs
                pagination_context = f"{tab_context}_page{i}"

                display_strategy_cards_page(page_df, page_name, pagination_context)

    return filtered_df


def display_strategy_cards_page(df, page_name="Unknown", tab_context=""):
    """Display strategy cards for a given page with scrollable container"""
    if len(df) == 0:
        st.warning("No data to display on this page.")
        return

    # Add custom CSS for scrollable container
    st.markdown("""
    <style>
    /* Custom scrollbar styling for strategy cards */
    .stContainer {
        max-height: 70vh;
        overflow-y: auto;
        overflow-x: hidden;
    }
    .stContainer::-webkit-scrollbar {
        width: 12px;
    }
    .stContainer::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 10px;
        margin: 5px;
    }
    .stContainer::-webkit-scrollbar-thumb {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 10px;
    }
    .stContainer::-webkit-scrollbar-thumb:hover {
        background: linear-gradient(135deg, #764ba2 0%, #667eea 100%);
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Create scrollable container for cards
    with st.container(height=1000, border=True):
        # Display strategy cards in scrollable area
        for card_num, (idx, row) in enumerate(df.iterrows()):
            # Get raw data for extracting expander info
            # Handle missing Raw_Data (for monitored trades that might not have it)
            if 'Raw_Data' in row and pd.notna(row.get('Raw_Data')):
                raw_data = row['Raw_Data']
                if isinstance(raw_data, str):
                    # Try to parse if it's a string
                    import json
                    try:
                        raw_data = json.loads(raw_data)
                    except:
                        raw_data = {}
                elif not isinstance(raw_data, dict):
                    raw_data = {}
            else:
                # Create a fallback raw_data dict from available row data
                raw_data = {}
                # Populate with available data
                if 'Symbol' in row:
                    raw_data['Symbol, Signal, Signal Date/Price[$]'] = f"{row.get('Symbol', '')}, {row.get('Signal_Type', '')}, {row.get('Signal_Date', '')} (Price: {row.get('Signal_Price', 0)})"
                if 'Interval' in row:
                    raw_data['Interval, Confirmation Status'] = row.get('Interval', 'Unknown')
                if 'Exit_Date' in row and pd.notna(row.get('Exit_Date')):
                    raw_data['Exit Signal Date/Price[$]'] = f"{row.get('Exit_Date', '')} (Price: {row.get('Exit_Price', 0)})"
                else:
                    raw_data['Exit Signal Date/Price[$]'] = 'No Exit Yet'

            # Extract interval
            interval_display = "Unknown"
            if 'Interval' in row and row['Interval'] != 'Unknown':
                interval_display = row['Interval']
                if interval_display == 'Unknown':
                    interval_display = raw_data.get("Interval", "Unknown")

            else:
                interval_info = raw_data.get('Interval, Confirmation Status', 'Unknown')
                if ',' in str(interval_info):
                    interval_display = str(interval_info).split(',')[0].strip()
                else:
                    interval_display = str(interval_info).strip()

            
            # Extract signal type (Long/Short)
            signal_type_display = "Unknown"
            if 'Signal_Type' in row and row['Signal_Type'] != 'Unknown':
                signal_type_display = row['Signal_Type']
            else:
                signal_info = raw_data.get('Symbol, Signal, Signal Date/Price[$]', '')
                if 'Long' in str(signal_info):
                    signal_type_display = 'Long'
                elif 'Short' in str(signal_info):
                    signal_type_display = 'Short'
            
            # Extract signal date
            signal_date_display = "Unknown"
            if 'Signal_Date' in row and row['Signal_Date'] != 'Unknown':
                signal_date_display = row['Signal_Date']
            else:
                signal_info = raw_data.get('Symbol, Signal, Signal Date/Price[$]', '')
                if 'Price:' in str(signal_info):
                    parts = str(signal_info).split(',')
                    if len(parts) >= 3:
                        date_part = parts[2].strip().split('(')[0].strip()
                        signal_date_display = date_part
            
            # Create expandable card with new title format
            expander_title = f"🔍 {row['Function']} - {row['Symbol']} | {interval_display} | {signal_type_display} | {signal_date_display}"
            
            with st.expander(expander_title, expanded=False):
                st.markdown("**📋 Key Trade Information**")

                # Add interactive chart button for all strategy pages with functions
                show_chart = False
                # List of pages that should have charts
                chart_enabled_pages = [
                    "All Signal Report", "Outstanding Signals", "New Signals", "Claude Signals", "New High"
                ]
                
                # Create unique identifier for buttons (needed for both chart and add to monitored)
                import hashlib
                unique_str = f"{page_name}_{tab_context}_{card_num}_{row['Symbol']}_{signal_date_display}_{interval_display}_{signal_type_display}_{idx}"
                unique_hash = hashlib.md5(unique_str.encode()).hexdigest()[:8]
                
                # Create button row - show chart button if charts are enabled, and add/remove buttons
                show_chart = False
                if page_name in chart_enabled_pages:
                    show_chart = True
                elif 'Function' in row and row['Function'] == 'FRACTAL TRACK':
                    show_chart = True
                
                show_add_monitored = (page_name in ['Outstanding Signals'])
                show_remove_monitored = (page_name == 'Monitored Trades')
                
                # Only create button row if at least one button should be shown
                if show_chart or show_add_monitored or show_remove_monitored:
                    # Determine number of columns needed
                    num_buttons = sum([show_chart, show_add_monitored, show_remove_monitored])
                    if num_buttons == 1:
                        button_col1 = st.container()
                        button_col2 = None
                        button_col3 = None
                    elif num_buttons == 2:
                        button_col1, button_col2 = st.columns([1, 1])
                        button_col3 = None
                    else:
                        button_col1, button_col2, button_col3 = st.columns([1, 1, 1])
                    
                    # Create a session state key for tracking which chart to show
                    chart_key = f"chart_{unique_hash}_{card_num}"
                    chart_state_key = f"show_chart_{unique_hash}_{card_num}"
                    
                    with button_col1:
                        if show_chart:
                            if st.button(f"📊 View Interactive Chart", key=chart_key):
                                # Toggle chart visibility
                                st.session_state[chart_state_key] = not st.session_state.get(chart_state_key, False)
                    
                    # Add "Add to Monitored" button for Outstanding Signals page
                    if show_add_monitored:
                        button_container = button_col2 if button_col2 else button_col1
                        with button_container:
                            add_monitored_key = f"add_monitored_{unique_hash}_{card_num}"
                            if st.button("⭐ Add to Monitored", key=add_monitored_key):
                                # Import here to avoid circular imports
                                from ..utils.monitored_trades import add_trade_to_monitored, generate_trade_id
                                
                                # Prepare trade data
                                trade_data = {
                                    'Symbol': row.get('Symbol', ''),
                                    'Function': row.get('Function', ''),
                                    'Signal_Type': row.get('Signal_Type', ''),
                                    'Signal_Date': row.get('Signal_Date', ''),
                                    'Signal_Price': row.get('Signal_Price', 0),
                                    'Interval': row.get('Interval', 'Unknown'),
                                    'Win_Rate': row.get('Win_Rate', 0),
                                    'Strategy_CAGR': row.get('Strategy_CAGR', 0),
                                    'Buy_Hold_CAGR': row.get('Buy_Hold_CAGR', 0),
                                    'Strategy_Sharpe': row.get('Strategy_Sharpe', 0),
                                    'Buy_Hold_Sharpe': row.get('Buy_Hold_Sharpe', 0),
                                    'Raw_Data': raw_data,  # Store original CSV data
                                }
                                
                                # Extract interval from raw data if not available
                                if trade_data['Interval'] == 'Unknown':
                                    interval_info = raw_data.get('Interval, Confirmation Status', 'Unknown')
                                    if ',' in str(interval_info):
                                        trade_data['Interval'] = str(interval_info).split(',')[0].strip()
                                    else:
                                        trade_data['Interval'] = str(interval_info).strip()
                                
                                # Check if already exists
                                trade_id = generate_trade_id(
                                    trade_data['Symbol'],
                                    trade_data['Signal_Date'],
                                    trade_data['Interval'],
                                    trade_data['Signal_Type'],
                                    trade_data['Function']
                                )
                                
                                # Try to add
                                if add_trade_to_monitored(trade_data):
                                    st.success(f"✅ Added {trade_data['Symbol']} to Monitored Trades!")
                                else:
                                    st.warning(f"⚠️ {trade_data['Symbol']} is already in Monitored Trades")
                                st.rerun()
                    
                    # Add "Remove from Monitored" button for Monitored Trades page
                    if show_remove_monitored:
                        button_container = button_col3 if button_col3 else (button_col2 if button_col2 else button_col1)
                        with button_container:
                            remove_monitored_key = f"remove_monitored_{unique_hash}_{card_num}"
                            if st.button("🗑️ Remove from Monitored", key=remove_monitored_key, type="secondary"):
                                # Import here to avoid circular imports
                                from ..utils.monitored_trades import remove_trade_from_monitored
                                
                                # Get trade ID from row
                                trade_id = row.get('Trade_ID', '')
                                if trade_id:
                                    if remove_trade_from_monitored(trade_id):
                                        st.success(f"✅ Removed {row.get('Symbol', 'trade')} from Monitored Trades!")
                                        st.rerun()
                                    else:
                                        st.error(f"❌ Failed to remove trade")
                                else:
                                    st.warning("⚠️ Trade ID not found")
                
                # Display chart if toggle is active (full width, outside columns)
                if show_chart and st.session_state.get(chart_state_key, False):
                    st.markdown("---")
                    # Route to appropriate chart based on page type
                    if page_name in ['All Signal Report', 'Outstanding Signals', 'New Signals', 'Claude Signals']:
                        # For mixed detailed-signal pages, fetch original data from function CSVs
                        create_outstanding_signal_chart(row, raw_data)
                    else:
                        # Simple candlestick chart with buy/sell marker for all other pages
                        create_interactive_chart(row, raw_data)
                    st.markdown("---")
                
                # Create three columns for better layout
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.markdown("**🎯 Trade Details**")
                    st.write(f"**Symbol:** {row['Symbol']}")
                    st.write(f"**Function:** {row['Function']}")
                    
                    # Handle different data structures
                    if 'Interval' in row and row['Interval'] != 'Unknown':
                        st.write(f"**Interval:** {row['Interval']}")
                    else:
                        # Fallback to raw data parsing
                        interval_info = raw_data.get('Interval, Confirmation Status', 'N/A')
                        if ',' in str(interval_info):
                            st.write(f"**Interval:** {str(interval_info).split(',')[0]}")
                        else:
                            st.write(f"**Interval:** {interval_info}")
                
                    # Handle signal information - check if we have parsed data or need to parse raw data
                    if 'Signal_Type' in row and row['Signal_Type'] != 'Unknown':
                        st.write(f"**Signal:** {row['Signal_Type']}")
                        if 'Signal_Date' in row and row['Signal_Date'] != 'Unknown':
                            st.write(f"**Signal Date:** {row['Signal_Date']}")
                        if 'Signal_Price' in row and pd.notna(row.get('Signal_Price')) and row['Signal_Price'] != 0:
                            st.write(f"**Signal Price:** ${row['Signal_Price']:.4f}")
                    else:
                        # Fallback to raw data parsing
                        signal_info = raw_data.get('Symbol, Signal, Signal Date/Price[$]', 'N/A')
                        if 'Price:' in str(signal_info):
                            parts = str(signal_info).split(',')
                            if len(parts) >= 3:
                                signal_type = parts[1].strip()
                                date_part = parts[2].strip().split('(')[0].strip()
                                price_part = str(signal_info).split('(Price:')[1].replace(')', '').strip()
                                st.write(f"**Signal:** {signal_type}")
                                st.write(f"**Signal Date:** {date_part}")
                                st.write(f"**Signal Price:** ${price_part}")
                            else:
                                st.write(f"**Signal Date & Price:** {signal_info}")
                        else:
                            st.write(f"**Signal Date & Price:** {signal_info}")
                    # Handle exit information
                    if 'Entry_Date' in row and row['Entry_Date'] != 'Unknown':
                        st.write(f"**Entry Date:** {row['Entry_Date']}")
                        if 'Entry_Price' in row and pd.notna(row.get('Entry_Price')) and row['Entry_Price'] != 0:
                            st.write(f"**Entry Price:** ${row['Entry_Price']:.4f}")
                    else:
                        st.write(f"**Exit Date & Price:** {raw_data.get('Exit Signal Date/Price[$]', 'N/A')}")
                    
                    # Show divergence details for mixed detailed-signal pages when available
                    if page_name in ['All Signal Report', 'Outstanding Signals']:
                        divergence_info = raw_data.get('Divergence Start/End (Date and Price [$])', '')
                        if divergence_info and '/' in str(divergence_info):
                            try:
                                parts = str(divergence_info).split('/')
                                if len(parts) >= 2:
                                    start_part = parts[0].strip()
                                    end_part = parts[1].strip()
                                    
                                    # Extract start date and price
                                    if '(' in start_part and ')' in start_part:
                                        start_date = start_part.split('(')[0].strip()
                                        start_price = start_part.split('(')[1].split(')')[0].replace('Price: ', '')
                                        st.write(f"**Divergence Start:** {start_date} (${start_price})")
                                    
                                    # Extract end date and price
                                    if '(' in end_part and ')' in end_part:
                                        end_date = end_part.split('(')[0].strip()
                                        end_price = end_part.split('(')[1].split(')')[0].replace('Price: ', '')
                                        st.write(f"**Divergence End:** {end_date} (${end_price})")
                            except:
                                pass
                    
                    if 'Win_Rate' in row and pd.notna(row.get('Win_Rate')):
                        st.write(f"**Win Rate:** {row['Win_Rate']:.1f}%")
                    else:
                        st.write(f"**Win Rate:** N/A")
                        
                with col2:
                    st.markdown("**📊 Status & Performance**")
                    
                    # Skip Confirmation Status and Current MTM for portfolio/target pages
                    is_portfolio_page = 'portfolio' in page_name.lower() or 'target' in page_name.lower()
                    
                    # Handle confirmation status (skip for portfolio pages)
                    if not is_portfolio_page:
                        if 'Interval, Confirmation Status' in raw_data:
                            conf_status = raw_data.get('Interval, Confirmation Status', 'N/A')
                            if ',' in str(conf_status):
                                st.write(f"**Confirmation Status:** {str(conf_status).split(',')[1].strip()}")
                            else:
                                st.write(f"**Confirmation Status:** N/A")
                        else:
                            st.write(f"**Confirmation Status:** N/A")
                    
                    # Handle current status (skip Current MTM for portfolio pages)
                    if 'Current_Date' in row and row['Current_Date'] != 'Unknown':
                        st.write(f"**Today Date:** {row['Current_Date']}")
                        if 'Current_Price' in row and pd.notna(row.get('Current_Price')) and row['Current_Price'] != 0:
                            st.write(f"**Today Price:** ${row['Current_Price']:.4f}")
                    else:
                        if not is_portfolio_page:
                            st.write(f"**Current MTM:** {raw_data.get('Current Mark to Market and Holding Period', 'N/A')}")
                    
                    # Handle performance metrics
                    if 'Strategy_CAGR' in row and pd.notna(row.get('Strategy_CAGR')):
                        st.write(f"**Strategy CAGR:** {row['Strategy_CAGR']:.2f}%")
                    if 'Buy_Hold_CAGR' in row and pd.notna(row.get('Buy_Hold_CAGR')):
                        st.write(f"**Buy & Hold CAGR:** {row['Buy_Hold_CAGR']:.2f}%")
                    if 'Strategy_Sharpe' in row and pd.notna(row.get('Strategy_Sharpe')):
                        st.write(f"**Strategy Sharpe:** {row['Strategy_Sharpe']:.2f}")
                    if 'Buy_Hold_Sharpe' in row and pd.notna(row.get('Buy_Hold_Sharpe')):
                        st.write(f"**Buy & Hold Sharpe:** {row['Buy_Hold_Sharpe']:.2f}")
                        
                    # Handle gain information for target signals
                    if 'Gain_Percentage' in row and pd.notna(row.get('Gain_Percentage')) and row['Gain_Percentage'] != 0:
                        st.write(f"**Gain:** {row['Gain_Percentage']:.2f}%")
                    if 'Holding_Days' in row and pd.notna(row.get('Holding_Days')) and row['Holding_Days'] != 0:
                        st.write(f"**Holding Days:** {format_days(str(int(row['Holding_Days'])))}")
                        
                with col3:
                    st.markdown("**⚠️ Risk & Timing**")
                    
                    # Skip Cancellation Level/Date for portfolio pages (is_portfolio_page already defined in col2)
                    if not is_portfolio_page:
                        st.write(f"**Cancellation Level/Date:** {raw_data.get('Cancellation Level/Date', 'N/A')}")
                        
                    # Handle target information for target signals
                    if 'Target_Price' in row and pd.notna(row.get('Target_Price')) and row['Target_Price'] != 0:
                        st.write(f"**Target Price:** ${row['Target_Price']:.4f}")
                        if 'Target_Type' in row and row['Target_Type'] != 'Unknown':
                            st.write(f"**Target Type:** {row['Target_Type']}")
                    
                    if 'Next_Targets' in row and row['Next_Targets'] != 'N/A':
                        st.write(f"**Next Targets:** {row['Next_Targets']}")
                        
                        # Extract average holding period from the complex string
                        holding_period_info = raw_data.get('Backtested Holding Period(Win Trades) (days) (Max./Min./Avg.)', 'N/A')
                        if '/' in str(holding_period_info):
                            avg_holding = str(holding_period_info).split('/')[-1].strip()
                            st.write(f"**Avg Holding Period:** {format_days(avg_holding)}")
                        else:
                            st.write(f"**Avg Holding Period:** N/A")
                        
                        # Extract average backtested return
                        returns_info = raw_data.get('Backtested Returns(Win Trades) [%] (Max/Min/Avg)', 'N/A')
                        if '/' in str(returns_info):
                            avg_return = str(returns_info).split('/')[-1].strip()
                            st.write(f"**Avg Backtested Return:** {avg_return}")
                        else:
                            st.write(f"**Avg Backtested Return:** N/A")

                    # Handle exit prices for target signals
                    if 'Exit_Prices' in row and row['Exit_Prices'] != 'N/A':
                        st.write(f"**Exit Prices:** {row['Exit_Prices']}")
                    
                    # Function-specific information - get function name first
                    function_name = str(row.get('Function', '')).upper()
                    
                    # FRACTAL TRACK specific: Reference Upmove/Downmove and Track Level/Price
                    if 'FRACTAL' in function_name or 'TRACK' in function_name:
                        # Handle reference upmove/downmove for fractal track - use exact column name
                        reference_upmove = raw_data.get('Reference Upmove or Downmove start Date/Price($), end Date/Price($)', 'N/A')
                        if reference_upmove and reference_upmove != 'N/A' and reference_upmove != 'No Information':
                            st.write(f"**Reference Upmove or Downmove start Date/Price($), end Date/Price($):** {reference_upmove}")
                        
                        # Handle track level/price for fractal track - use exact column name
                        track_level_full = raw_data.get('Track Level/Price($), Price on Latest Trading day vs Track Level, Signal Type', 'N/A')
                        
                        if track_level_full and track_level_full != 'N/A' and track_level_full != 'No Information':
                            st.write(f"**Track Level/Price($), Price on Latest Trading day vs Track Level, Signal Type:** {track_level_full}")
                    
                    # Get function name for function-specific display
                    function_name = str(row.get('Function', '')).upper()
                    
                    # Handle separate signal type field if it exists (only if not already shown in Track Level)
                    signal_type_separate = raw_data.get('Signal Type', 'N/A')
                    if signal_type_separate and signal_type_separate != 'N/A' and signal_type_separate != 'No Information':
                        # Check if track_level_full exists and doesn't already contain Signal Type
                        track_level_full_check = raw_data.get('Track Level/Price($), Price on Latest Trading day vs Track Level, Signal Type', 'N/A')
                        if 'Signal Type' not in str(track_level_full_check):  # Only show if not already displayed
                            st.write(f"**Signal Type:** {signal_type_separate}")
                    
                    # Function-specific information display based on function type
                    # (function_name is already defined above for FRACTAL TRACK)
                    
                    # SIGMA/SIGMASHELL specific: Sigmashell, Success Rate of Past Analysis [%]
                    if 'SIGMA' in function_name or 'SIGMASHELL' in function_name:
                        sigmashell = raw_data.get('Sigmashell, Success Rate of Past Analysis [%]', 'N/A')
                        if sigmashell and sigmashell != 'N/A' and sigmashell != 'No Information':
                            st.write(f"**Sigmashell, Success Rate of Past Analysis [%]:** {sigmashell}")
                    
                    # BASELINE DIVERGENCE specific: Divergence observed with, Signal Type
                    if 'BASELINE' in function_name or 'DIVERGENCE' in function_name:
                        divergence_observed = raw_data.get('Divergence observed with, Signal Type', 'N/A')
                        if divergence_observed and divergence_observed != 'N/A' and divergence_observed != 'No Information':
                            st.write(f"**Divergence observed with, Signal Type:** {divergence_observed}")
                    
                    # ALTITUDE ALPHA specific: Maxima Broken Date/Price[$]
                    if 'ALTITUDE' in function_name or 'ALPHA' in function_name:
                        maxima_broken = raw_data.get('Maxima Broken Date/Price[$]', 'N/A')
                        if maxima_broken and maxima_broken != 'N/A' and maxima_broken != 'No Information':
                            st.write(f"**Maxima Broken Date/Price[$]:** {maxima_broken}")
                    
                    # TRENDPULSE specific: TrendPulse Start/End and % Change in Price
                    if 'TRENDPULSE' in function_name:
                        # For TrendPulse, check Reference Upmove/Downmove column first (same as Fractal Track approach)
                        # TrendPulse data is typically stored in the Reference Upmove/Downmove column
                        reference_upmove_trendpulse = raw_data.get('Reference Upmove or Downmove start Date/Price($), end Date/Price($)', 'N/A')
                        if reference_upmove_trendpulse and reference_upmove_trendpulse != 'N/A' and reference_upmove_trendpulse != 'No Information':
                            st.write(f"**Reference Upmove or Downmove start Date/Price($), end Date/Price($):** {reference_upmove_trendpulse}")
                        else:
                            # Fallback to dedicated TrendPulse column if Reference Upmove/Downmove doesn't have data
                            trendpulse_val = raw_data.get('TrendPulse Start/End (Date and Price($))', 'N/A')
                            if trendpulse_val and trendpulse_val != 'N/A' and trendpulse_val != 'No Information':
                                st.write(f"**TrendPulse Start/End (Date and Price($)):** {trendpulse_val}")
                        
                        # Price Change Analysis - use exact column name
                        price_change = raw_data.get('% Change in Price on Latest Trading day vs Price on Trendpulse Breakout day/Earliest Unconfirmed Signal day/Confirmed Signal day', 'N/A')
                        if price_change and price_change != 'N/A' and price_change != 'No Information':
                            st.write(f"**% Change in Price on Latest Trading day vs Price on Trendpulse Breakout day/Earliest Unconfirmed Signal day/Confirmed Signal day:** {price_change}")
                    


def create_performance_summary_cards(df):
    """Create summary metric cards for performance data"""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        avg_win_rate = df['Win_Percentage'].mean()
        st.markdown(f"""
        <div class="metric-card">
            <p class="metric-value">{avg_win_rate:.1f}%</p>
            <p class="metric-label">Average Win Rate</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        total_trades = df['Total_Trades'].sum()
        st.markdown(f"""
        <div class="metric-card">
            <p class="metric-value">{total_trades}</p>
            <p class="metric-label">Total Trades</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        avg_profit = df['Avg_Profit'].mean()
        color_class = "positive" if avg_profit > 0 else "negative"
        st.markdown(f"""
        <div class="metric-card">
            <p class="metric-value {color_class}">{avg_profit:.1f}%</p>
            <p class="metric-label">Average Profit</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        avg_holding = df['Avg_Holding_Days'].mean()
        formatted_avg_holding = format_days(f"{avg_holding:.0f}") if pd.notna(avg_holding) else "N/A"
        st.markdown(f"""
        <div class="metric-card">
            <p class="metric-value">{formatted_avg_holding}</p>
            <p class="metric-label">Avg Holding Days</p>
        </div>
        """, unsafe_allow_html=True)


def create_performance_cards(df):
    """Create individual performance cards with pagination for large datasets"""
    st.markdown("### 📊 Performance Analysis Cards")
    st.markdown("Click on any card to see detailed performance metrics")
    
    total_records = len(df)
    
    if total_records == 0:
        st.warning("No performance data matches the current filters.")
        return
    
    # Display total count
    st.markdown(f"**Total Records: {total_records}**")
    
    # Pagination settings for performance cards - 30 per tab
    cards_per_page = 30
    total_pages = (total_records + cards_per_page - 1) // cards_per_page
    
    # Create pagination if there are many records
    if total_records <= cards_per_page:
        # If 30 or fewer records, show all in one view
        display_performance_cards_page(df)
    else:
        # Create tabs for pagination
        # Generate tab labels
        tab_labels = []
        for i in range(total_pages):
            start_idx = i * cards_per_page + 1
            end_idx = min((i + 1) * cards_per_page, total_records)
            tab_labels.append(f"#{start_idx}-{end_idx}")
        
        # Create tabs dynamically
        if total_pages <= 8:  # Limit to 8 tabs to avoid overcrowding
            # If 8 or fewer pages, create all tabs at once
            tabs = st.tabs(tab_labels)
            for i, tab in enumerate(tabs):
                with tab:
                    start_idx = i * cards_per_page
                    end_idx = min((i + 1) * cards_per_page, total_records)
                    page_df = df.iloc[start_idx:end_idx]
                    display_performance_cards_page(page_df)
        else:
            # If more than 8 pages, use selectbox for navigation
            st.markdown("**Navigate to page:**")
            selected_page = st.selectbox(
                "Choose page:",
                options=list(range(1, total_pages + 1)),
                format_func=lambda x: f"Page {x} (#{(x-1)*cards_per_page + 1}-{min(x*cards_per_page, total_records)})",
                key="performance_cards_page_selector"
            )
            
            # Display selected page
            start_idx = (selected_page - 1) * cards_per_page
            end_idx = min(selected_page * cards_per_page, total_records)
            page_df = df.iloc[start_idx:end_idx]
            
            st.markdown(f"**Showing records {start_idx + 1} to {end_idx} of {total_records}**")
            display_performance_cards_page(page_df)


def display_performance_cards_page(df):
    """Display performance cards for a given page"""
    if len(df) == 0:
        st.warning("No data to display on this page.")
        return
    
    # Use Streamlit's container with height parameter for scrolling
    with st.container(height=600):  # Fixed height container that will scroll
        for idx, row in df.iterrows():
            # Create expandable card
            win_pct = row.get('Win_Percentage', 0) if pd.notna(row.get('Win_Percentage')) else 0
            with st.expander(f"📊 {row['Strategy']} - {row['Interval']} ({win_pct:.1f}% Win Rate)", expanded=False):
                st.markdown("**📋 Performance Metrics**")
                
                # Create three columns for better layout
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.markdown("**🎯 Strategy Details**")
                    st.write(f"**Strategy:** {row['Strategy']}")
                    st.write(f"**Interval:** {row['Interval']}")
                    st.write(f"**Signal Type:** {row['Signal_Type']}")
                    st.write(f"**Total Trades:** {row['Total_Trades']}")
                    if 'Win_Percentage' in row and pd.notna(row.get('Win_Percentage')):
                        st.write(f"**Win Percentage:** {row['Win_Percentage']:.1f}%")
                    
                with col2:
                    st.markdown("**📊 Profit Analysis**")
                    if 'Best_Profit' in row and pd.notna(row.get('Best_Profit')):
                        st.write(f"**Best Profit:** {row['Best_Profit']:.1f}%")
                    if 'Worst_Profit' in row and pd.notna(row.get('Worst_Profit')):
                        st.write(f"**Worst Profit:** {row['Worst_Profit']:.1f}%")
                    if 'Avg_Profit' in row and pd.notna(row.get('Avg_Profit')):
                        st.write(f"**Average Profit:** {row['Avg_Profit']:.1f}%")
                    if 'Avg_Backtested_Win_Rate' in row and pd.notna(row.get('Avg_Backtested_Win_Rate')):
                        st.write(f"**Avg Backtested Win Rate:** {row['Avg_Backtested_Win_Rate']:.1f}%")
                    
                with col3:
                    st.markdown("**⏱️ Holding Period Analysis**")
                    st.write(f"**Max Holding Days:** {format_days(f'{row['Max_Holding_Days']:.0f}')}")
                    st.write(f"**Min Holding Days:** {format_days(f'{row['Min_Holding_Days']:.0f}')}")
                    st.write(f"**Avg Holding Days:** {format_days(f'{row['Avg_Holding_Days']:.0f}')}")
                    st.write(f"**Avg Backtested Holding:** {format_days(f'{row['Avg_Backtested_Holding_Days']:.0f}')}")


_COMBINED_FUNCTION_NAMES = (
    'Combined (TrendPulse + DeltaDrift + BandMatrix)',
    'All Function Combined',
)


def _breadth_uses_sbi_ui(df):
    """True when parsed df has trade-arrival SBI metrics to display."""
    if 'Schema' in df.columns and (df['Schema'] == 'sbi').any():
        return True
    if 'Today_Long_Percentile' not in df.columns:
        return False
    long_pct = df['Today_Long_Percentile'].fillna(0)
    short_pct = df.get('Today_Short_Percentile', pd.Series(0, index=df.index)).fillna(0)
    long_cnt = df.get('Total_New_Long', pd.Series(0, index=df.index)).fillna(0)
    short_cnt = df.get('Total_New_Short', pd.Series(0, index=df.index)).fillna(0)
    return bool(
        (long_pct > 0).any()
        or (short_pct > 0).any()
        or (long_cnt > 0).any()
        or (short_cnt > 0).any()
    )


def _breadth_combined_row(df):
    """Market-wide combined row for summary cards."""
    for name in _COMBINED_FUNCTION_NAMES:
        matches = df[df['Function'] == name]
        if not matches.empty:
            return matches.iloc[-1]
    return df.iloc[-1] if not df.empty else None


def create_breadth_summary_cards(df):
    """Create summary metric cards for breadth data (SBI or legacy)."""
    if _breadth_uses_sbi_ui(df):
        combined = _breadth_combined_row(df)
        if combined is None:
            st.info("No breadth data available for summary.")
            return
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <h3>Total New Long</h3>
                <h2>{combined.get('Total_New_Long', 0):.0f}</h2>
                <p>{combined['Function']}</p>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <h3>Total New Short</h3>
                <h2>{combined.get('Total_New_Short', 0):.0f}</h2>
                <p>{combined['Function']}</p>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <h3>Long Percentile (Top)</h3>
                <h2>{combined.get('Today_Long_Percentile', 0):.1f}%</h2>
                <p>vs last 6 months</p>
            </div>
            """, unsafe_allow_html=True)
        with col4:
            st.markdown(f"""
            <div class="metric-card">
                <h3>Short Percentile (Top)</h3>
                <h2>{combined.get('Today_Short_Percentile', 0):.1f}%</h2>
                <p>vs last 6 months</p>
            </div>
            """, unsafe_allow_html=True)
        return

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        avg_bullish_assets = df['Bullish_Asset_Percentage'].mean()
        st.markdown(f"""
        <div class="metric-card">
            <h3>Avg Bullish Assets</h3>
            <h2>{avg_bullish_assets:.1f}%</h2>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        avg_bullish_signals = df['Bullish_Signal_Percentage'].mean()
        st.markdown(f"""
        <div class="metric-card">
            <h3>Avg Bullish Signals</h3>
            <h2>{avg_bullish_signals:.1f}%</h2>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <h3>Total Strategies</h3>
            <h2>{len(df)}</h2>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        best_asset_strategy = df.loc[df['Bullish_Asset_Percentage'].idxmax(), 'Function']
        best_asset_pct = df['Bullish_Asset_Percentage'].max()
        st.markdown(f"""
        <div class="metric-card">
            <h3>Best Asset Breadth</h3>
            <h2>{best_asset_pct:.1f}%</h2>
            <p>{best_asset_strategy}</p>
        </div>
        """, unsafe_allow_html=True)


def create_breadth_cards(df):
    """Create individual breadth analysis cards (SBI trade-arrival or legacy)."""
    cols = st.columns(2)
    use_sbi = _breadth_uses_sbi_ui(df)

    for idx, (_, row) in enumerate(df.iterrows()):
        with cols[idx % 2]:
            with st.expander(f"📊 {row['Function']}", expanded=False):
                if use_sbi:
                    c1, c2 = st.columns(2)
                    with c1:
                        st.metric(
                            "Total New Long",
                            f"{row.get('Total_New_Long', 0):.0f}",
                            help="New long signals today (S&P 500 universe)",
                        )
                        st.metric(
                            "Long Percentile (Top)",
                            f"{row.get('Today_Long_Percentile', 0):.1f}%",
                            help="Today's long count vs last 6 months (top-percentile; lower = quieter day)",
                        )
                    with c2:
                        st.metric(
                            "Total New Short",
                            f"{row.get('Total_New_Short', 0):.0f}",
                            help="New short signals today (S&P 500 universe)",
                        )
                        st.metric(
                            "Short Percentile (Top)",
                            f"{row.get('Today_Short_Percentile', 0):.1f}%",
                            help="Today's short count vs last 6 months (top-percentile)",
                        )
                    st.caption(
                        f"6-month top-10% thresholds — Long: {row.get('Top10_Long_Threshold', 0):.0f}, "
                        f"Short: {row.get('Top10_Short_Threshold', 0):.0f}"
                    )
                    long_p = row.get('Today_Long_Percentile', 0) or 0
                    short_p = row.get('Today_Short_Percentile', 0) or 0
                    avg_p = (long_p + short_p) / 2
                    if avg_p >= 70:
                        status, color = "🟢 High activity", "green"
                    elif avg_p >= 40:
                        status, color = "🟡 Moderate", "orange"
                    else:
                        status, color = "🔵 Quiet day", "steelblue"
                    st.markdown(f"""
                    <div style="text-align: center; margin-top: 10px;">
                        <h4 style="color: {color};">{status}</h4>
                        <p>Avg top-percentile: {avg_p:.1f}%</p>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    c1, c2 = st.columns(2)
                    with c1:
                        st.metric(
                            "Bullish Assets",
                            f"{row['Bullish_Asset_Percentage']:.1f}%",
                            help="Percentage of bullish assets vs total assets",
                        )
                    with c2:
                        st.metric(
                            "Bullish Signals",
                            f"{row['Bullish_Signal_Percentage']:.1f}%",
                            help="Percentage of bullish signals vs total signals",
                        )
                    avg_breadth = (
                        row['Bullish_Asset_Percentage'] + row['Bullish_Signal_Percentage']
                    ) / 2
                    if avg_breadth >= 70:
                        breadth_status, breadth_color = "🟢 Strong", "green"
                    elif avg_breadth >= 40:
                        breadth_status, breadth_color = "🟡 Moderate", "orange"
                    else:
                        breadth_status, breadth_color = "🔴 Weak", "red"
                    st.markdown(f"""
                    <div style="text-align: center; margin-top: 10px;">
                        <h4 style="color: {breadth_color};">{breadth_status}</h4>
                        <p>Average Breadth: {avg_breadth:.1f}%</p>
                    </div>
                    """, unsafe_allow_html=True)


