"""
Text file page for displaying Claude output
"""

import streamlit as st
import pandas as pd
import os
import glob
from datetime import datetime

from constant import (
    GPT_SIGNALS_REPORT_TXT_PATH_US,
    GPT_SIGNALS_REPORT_CSV_PATH_US,
)
from ..components.cards import create_summary_cards, create_strategy_cards
from ..components.quality_bubble_chart import render_quality_bubble_chart
from ..utils.file_discovery import extract_date_from_filename
from ..utils.surface_json_parser import parse_surface_json
from ..utils.signal_quality import quality_rows_from_parsed_df


def find_latest_gpt_file(base_path, extension='txt'):
    """
    Find the most recent Claude report file (dated or non-dated).
    Returns the file path and extracted date if found.
    """
    # Get directory and base filename
    dir_path = os.path.dirname(base_path)
    base_name = os.path.basename(base_path)
    
    # Pattern to match: YYYY-MM-DD_claude_signals_report.ext or claude_signals_report.ext
    pattern_txt = os.path.join(dir_path, f"*_claude_signals_report.{extension}")
    pattern_base = os.path.join(dir_path, f"claude_signals_report.{extension}")
    
    # Find all matching files
    dated_files = glob.glob(pattern_txt)
    base_files = glob.glob(pattern_base)
    
    all_files = dated_files + base_files
    
    if not all_files:
        return None, None
    
    # Sort files by date (most recent first)
    def get_file_date(file_path):
        filename = os.path.basename(file_path)
        date_obj = extract_date_from_filename(filename)
        return date_obj if date_obj else datetime.min
    
    # Get the most recent file
    latest_file = max(all_files, key=get_file_date)
    file_date = extract_date_from_filename(os.path.basename(latest_file))
    
    return latest_file, file_date


def create_text_file_page():
    """Create a page to display Claude Signals report: text first, then cards + table"""
    # Info button at the top
    if st.button("ℹ️ Info About Page", key="info_text_file", help="Click to learn about this page"):
        st.session_state['show_info_text_file'] = not st.session_state.get('show_info_text_file', False)
    
    if st.session_state.get('show_info_text_file', False):
        with st.expander("📖 Claude Signals Report Information", expanded=True):
            st.markdown("""
            ### What is this page?
            The Claude Signals Report page displays AI-generated analysis of trading signal data using Claude AI, showing both textual analysis and structured signal data.
            
            ### Why is it used?
            - **AI Insights**: Get Claude AI's analysis and recommendations on trading signal data
            - **Comprehensive Reports**: View both narrative text reports and structured CSV signals
            - **Signal Summary**: See a consolidated view of important signals analyzed by AI
            - **Quick Reference**: Access Claude's latest market analysis and trading suggestions
            
            ### How to use?
            1. **Read Text Analysis**: Start with the text report section for Claude's narrative analysis
            2. **Review Cards**: Scroll through strategy cards for quick signal overview
            3. **Check Table**: Examine the detailed signal data table at the bottom
            4. **Filter Signals**: Use sidebar filters to focus on specific strategies or symbols
            5. **Compare Signals**: Cross-reference Claude's insights with your own analysis
            
            ### Key Features:
            - AI-powered signal analysis from Claude
            - Dual format: Text report + structured signal data
            - Automated date-stamped reports
            - Integration with signal cards and tables
            - Historical report access
            """)
    
    st.title("🤖 Claude Signals Report")
    
    # Display data fetch datetime at top of page (from JSON file)
    from ..utils.helpers import display_data_fetch_info
    display_data_fetch_info(location="header")
    
    # Find the latest Claude files
    txt_file, txt_date = find_latest_gpt_file(GPT_SIGNALS_REPORT_TXT_PATH_US, 'txt')
    csv_file, csv_date = find_latest_gpt_file(GPT_SIGNALS_REPORT_CSV_PATH_US, 'csv')
    
    st.markdown("---")
    
    # 1) Text output
    st.markdown("### 📝 Claude Analysis (Text)")
    txt_path = txt_file if txt_file else GPT_SIGNALS_REPORT_TXT_PATH_US
    try:
        with open(txt_path, 'r', encoding='utf-8') as file:
            content = file.read()
            st.text_area("Report Text:", content, height=600, key="claude_signals_text")
    except FileNotFoundError:
        st.warning(f"Text report not found: {txt_path}")
    except Exception as e:
        st.error(f"Error reading text report: {str(e)}")
    
    st.markdown("---")
    
    # 2) CSV output: show strategy cards first, then table
    st.markdown("### 📊 Claude Signals (Cards + Table)")
    csv_path = csv_file if csv_file else GPT_SIGNALS_REPORT_CSV_PATH_US
    
    if not os.path.exists(csv_path):
        st.info("No signal data available - Claude signals CSV file not found.")
        return
    
    try:
        # Read raw CSV first
        raw_df = pd.read_csv(csv_path)
        
        if raw_df.empty:
            st.info("No signal data available in Claude signals CSV.")
            return
        
        # Claude Signals CSV has the same structure as outstanding_signal.csv
        # Use parse_detailed_signal_csv parser directly
        from ..parsers.base_parsers import parse_detailed_signal_csv
        parsed_df = parse_detailed_signal_csv(raw_df)
        
        if parsed_df.empty:
            st.info("No signal data could be parsed from Claude signals CSV.")
            return
        
        # Sidebar Filters
        st.sidebar.markdown("### 📊 Filters")
        min_win_rate = st.sidebar.slider(
            "Min Win Rate (%)",
            min_value=0,
            max_value=100,
            value=70,
            step=1,
            key="win_rate_slider_claude_signals"
        )
        min_sharpe_ratio = st.sidebar.slider(
            "Min Sharpe Ratio",
            min_value=-5.0,
            max_value=5.0,
            value=0.5,
            step=0.1,
            key="sharpe_ratio_slider_claude_signals"
        )
        
        # Apply filters
        if 'Win_Rate' in parsed_df.columns:
            parsed_df = parsed_df[parsed_df['Win_Rate'].fillna(0) >= min_win_rate]
        if 'Strategy_Sharpe' in parsed_df.columns:
            parsed_df = parsed_df[parsed_df['Strategy_Sharpe'].fillna(-999) >= min_sharpe_ratio]
        
        if parsed_df.empty:
            st.info("No signal data matches the current filter criteria.")
            return
        
        # Strategy cards - use parsed data which has Raw_Data column
        # Summary cards if possible
        required_summary_cols = {'Win_Rate', 'Num_Trades', 'Strategy_CAGR', 'Strategy_Sharpe'}
        has_summary_cols = required_summary_cols.issubset(set(parsed_df.columns))
        
        if has_summary_cols:
            create_summary_cards(parsed_df)
            st.markdown("---")

        # Bubble chart: prefer surface_json from Claude text; fallback to computed fields
        bubble_rows = []
        try:
            with open(txt_path, "r", encoding="utf-8") as _tf:
                bubble_rows = parse_surface_json(_tf.read())
        except Exception:
            bubble_rows = []
        if not bubble_rows:
            bubble_rows = quality_rows_from_parsed_df(parsed_df)
        if bubble_rows:
            st.markdown("### 📊 Signal Quality Composite vs Lifecycle")
            render_quality_bubble_chart(
                bubble_rows,
                title="Claude Signals: Quality Composite vs Lifecycle",
            )
            st.markdown("---")
        
        # Strategy cards with function-specific column logic (with search)
        search_filtered_parsed_df = create_strategy_cards(parsed_df, page_name="Claude Signals", tab_context="claude_signals")
        st.markdown("---")
        
        # Detail table - exclude function-specific columns (uses search-filtered data)
        st.markdown("### 📋 Detailed Signal Data Table (Original CSV Format)")
        
        # Build table from search-filtered parsed data's Raw_Data
        csv_data = []
        for _, row in search_filtered_parsed_df.iterrows():
            if 'Raw_Data' in row and pd.notna(row.get('Raw_Data')):
                raw_data = row['Raw_Data']
                csv_data.append(raw_data if isinstance(raw_data, dict) else {})
            else:
                csv_data.append({})
        original_df = pd.DataFrame(csv_data) if csv_data else pd.DataFrame()
        
        # Columns to exclude from detail table (only show in strategy cards if not "No Information")
        # Signal Open Price: backend deduplication only - never display
        columns_to_exclude = [
            'Signal Open Price',
            'Sigmashell, Success Rate of Past Analysis [%]',
            'Divergence observed with, Signal Type',
            'Maxima Broken Date/Price[$]',
            'Track Level/Price($), Price on Latest Trading day vs Track Level, Signal Type',
            'Reference Upmove or Downmove start Date/Price($), end Date/Price($)',
            '% Change in Price on Latest Trading day vs Price on Trendpulse Breakout day/Earliest Unconfirmed Signal day/Confirmed Signal day'
        ]
        
        # Remove excluded columns if they exist
        columns_to_display = [col for col in original_df.columns if col not in columns_to_exclude]
        filtered_raw_df = original_df[columns_to_display] if not original_df.empty else pd.DataFrame()
        
        if filtered_raw_df.empty:
            st.info("No signal data to display for the current search.")
        else:
            # Reorder columns: Symbol/Signal first, Exit Signal second, Function third
            from ..utils.helpers import reorder_dataframe_columns, find_column_by_keywords
            filtered_raw_df = reorder_dataframe_columns(filtered_raw_df)
            
            # Find Symbol and Exit Signal columns for pinning
            symbol_col = find_column_by_keywords(filtered_raw_df.columns, ['Symbol, Signal', 'Symbol'])
            if not symbol_col:
                for col in filtered_raw_df.columns:
                    if 'Symbol' in col and 'Signal' in col and 'Exit' not in col:
                        symbol_col = col
                        break
            exit_col = find_column_by_keywords(filtered_raw_df.columns, ['Exit Signal Date', 'Exit Signal', 'Exit'])
            
            # Display with better formatting and autosize for ALL columns
            column_config = {}
            for col in filtered_raw_df.columns:
                column_config[col] = st.column_config.TextColumn(
                    col,
                    help=f"Original CSV column: {col}"
                    # No width parameter = autosize
                )
            
            st.dataframe(
                filtered_raw_df,
                use_container_width=True,
                height=600,
                column_config=column_config
            )
    except pd.errors.EmptyDataError:
        st.info("No signal data available in Claude signals CSV.")
    except Exception as e:
        st.error(f"Error reading CSV report: {str(e)}")
        import traceback
        st.code(traceback.format_exc())