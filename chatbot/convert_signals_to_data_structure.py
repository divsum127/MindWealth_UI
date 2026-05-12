#!/usr/bin/env python3
"""
Convert trading signal CSV files to chatbot data structure.
Creates consolidated CSV files for efficient data access:
chatbot/data/entry.csv, exit.csv, portfolio_target_achieved.csv, breadth.csv

Features:
- Automatic deduplication based on signal type and keys from .env
- Prevents duplicate rows when appending to existing files
- Folder structure creation disabled - uses consolidated CSVs only
"""

import pandas as pd
import re
import os
import threading
from pathlib import Path
from datetime import datetime, timedelta
import sys
from typing import Dict, List

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.utils.atomic_io import read_csv_optional_locked, write_dataframe_csv_atomic_guarded
from src.utils.mtm_pricing import (
    MTM_HOLDING_COLUMN,
    TODAY_PRICE_COLUMN,
    TODAY_PRICE_COLUMN_LEGACY,
    TRADING_DAYS_COLUMN,
    batch_latest_prices,
    enrich_row_current_prices,
    normalize_symbol,
    normalize_today_price_column_names,
    parse_symbol_signal_column,
)

# Import configuration
from config import (
    STOCK_DATA_DIR,
    CHATBOT_DATA_DIR, 
    DEDUP_COLUMNS,
    BREADTH_DEDUP_COLUMNS,
    ENTRY_CSV_NAME,
    EXIT_CSV_NAME,
    TARGET_CSV_NAME,
    BREADTH_CSV_NAME
)

# Cache for stock data to avoid repeated file reads
_stock_data_cache = {}
_stock_data_cache_lock = threading.Lock()

def normalize_today_price_columns(df):
    """Backward-compatible name for :func:`normalize_today_price_column_names`."""
    return normalize_today_price_column_names(df)


def parse_exit_signal_column(value):
    """
    Parse the "Exit Signal Date/Price[$]" column.
    
    Examples:
        "No Exit Yet" -> (None, None)
        "2025-10-10 (Price: 5.98) (Today)" -> ("2025-10-10", 5.98)
    
    Returns: (exit_date, exit_price) or (None, None) if no exit
    """
    try:
        # Handle NaN, None, or empty values
        if value is None or pd.isna(value):
            return None, None
        
        # Convert to string to handle any numeric types
        value_str = str(value).strip()
        
        if not value_str or value_str.lower() in ['nan', 'none', '']:
            return None, None
        
        # Check if no exit (case-insensitive)
        if "no exit yet" in value_str.lower():
            return None, None
        
        # Extract date using regex
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', value_str)
        exit_date = date_match.group(1) if date_match else None
        
        # Extract price using regex (handle negative values and thousand separators)
        price_match = re.search(r'Price:\s*([-]?\d+(?:\.\d+)?(?:,\d{3})*)', value_str)
        if price_match:
            price_str = price_match.group(1).replace(',', '')
            exit_price = float(price_str)
        else:
            exit_price = None
        
        return exit_date, exit_price
        
    except Exception as e:
        print(f"Error parsing exit: {value} - {e}")
        return None, None


def parse_interval_from_status(value):
    """
    Parse the interval from "Interval, Confirmation Status" column.
    
    Example: "Daily, is CONFIRMED on 2025-11-18" -> "Daily"
    Example: "Weekly, Nullified" -> "Weekly"
    
    Args:
        value: Value from "Interval, Confirmation Status" column
    
    Returns:
        Interval string (e.g., "Daily", "Weekly") or None
    """
    try:
        if not value or pd.isna(value):
            return None
        
        # Split by comma and take the first part (interval)
        parts = str(value).split(',')
        if parts:
            interval = parts[0].strip()
            return interval if interval else None
        
        return None
        
    except Exception as e:
        print(f"  ⚠ Error parsing interval: {e}")
        return None


def get_interval_based_open_price(symbol, signal_date, interval, stock_data_dir=None):
    """
    Get the correct open price based on the interval type.
    
    For Daily: Returns open price on the signal date
    For Weekly: Returns open price on the Monday of that week
    For Monthly: Returns open price on the first trading day of that month
    For Quarterly: Returns open price on the first trading day of that quarter
    
    Args:
        symbol: Stock symbol
        signal_date: Signal date (YYYY-MM-DD string)
        interval: Interval type (Daily, Weekly, Monthly, Quarterly)
        stock_data_dir: Directory containing stock data CSVs (uses config default if None)
    
    Returns:
        Open price as float with 4 decimal places, or None if not found
    """
    if stock_data_dir is None:
        stock_data_dir = str(STOCK_DATA_DIR)
    """
    Get the correct open price based on the interval type.
    
    For Daily: Returns open price on the signal date
    For Weekly: Returns open price on the Monday of that week
    For Monthly: Returns open price on the first trading day of that month
    For Quarterly: Returns open price on the first trading day of that quarter
    
    Args:
        symbol: Stock symbol
        signal_date: Signal date (YYYY-MM-DD string)
        interval: Interval type (Daily, Weekly, Monthly, Quarterly)
        stock_data_dir: Directory containing stock data CSVs
    
    Returns:
        Open price as float with 4 decimal places, or None if not found
    """
    global _stock_data_cache
    
    try:
        # Parse signal date
        signal_dt = datetime.strptime(signal_date, '%Y-%m-%d')
        
        with _stock_data_cache_lock:
            if symbol not in _stock_data_cache:
                stock_file = Path(stock_data_dir) / f"{symbol}.csv"
                if not stock_file.exists():
                    return None
                
                stock_data = pd.read_csv(stock_file)
                if stock_data.empty:
                    return None
                
                stock_data['Date'] = pd.to_datetime(stock_data['Date'])
                stock_data = stock_data.sort_values('Date')
                _stock_data_cache[symbol] = stock_data
            
            stock_data = _stock_data_cache[symbol]
        
        # Get open price based on interval
        if interval == 'Daily':
            # Find exact date match
            date_matches = stock_data[stock_data['Date'].dt.date == signal_dt.date()]
            if not date_matches.empty:
                return float(f"{date_matches.iloc[0]['Open']:.4f}")
        
        elif interval == 'Weekly':
            # Find the week containing the signal date
            week_start = signal_dt - timedelta(days=signal_dt.weekday())  # Monday
            week_end = week_start + timedelta(days=6)  # Sunday
            
            week_data = stock_data[
                (stock_data['Date'].dt.date >= week_start.date()) &
                (stock_data['Date'].dt.date <= week_end.date())
            ]
            
            if not week_data.empty:
                return float(f"{week_data.iloc[0]['Open']:.4f}")
        
        elif interval == 'Monthly':
            # Find data for the target month
            month_data = stock_data[
                (stock_data['Date'].dt.year == signal_dt.year) &
                (stock_data['Date'].dt.month == signal_dt.month)
            ]
            
            if not month_data.empty:
                return float(f"{month_data.iloc[0]['Open']:.4f}")
        
        elif interval == 'Quarterly':
            # Find data for the target quarter
            target_quarter = (signal_dt.month - 1) // 3 + 1
            
            quarter_data = stock_data[
                (stock_data['Date'].dt.year == signal_dt.year) &
                (((stock_data['Date'].dt.month - 1) // 3 + 1) == target_quarter)
            ]
            
            if not quarter_data.empty:
                return float(f"{quarter_data.iloc[0]['Open']:.4f}")
        
        return None
        
    except Exception as e:
        print(f"  ⚠ Error getting interval-based open price for {symbol}: {e}")
        return None


def is_confirmed_signal(confirmation_status_value):
    """
    Check if the confirmation status indicates the signal is or was confirmed.
    
    Only accepts:
    - "is CONFIRMED" (current confirmed status)
    - "was CONFIRMED" (previously confirmed status)
    
    Rejects:
    - "will be confirmed"
    - "nullified"
    - Any other status
    
    Args:
        confirmation_status_value: Value from "Interval, Confirmation Status" column
            Example: "Daily, is CONFIRMED on 2025-11-18"
    
    Returns:
        True if signal is confirmed, False otherwise
    """
    try:
        if not confirmation_status_value or pd.isna(confirmation_status_value):
            return False
        
        status_str = str(confirmation_status_value).strip()
        
        # Check for "is CONFIRMED" or "was CONFIRMED" (case-insensitive)
        # Using regex to match these patterns
        confirmed_pattern = re.search(r'\b(is|was)\s+CONFIRMED\b', status_str, re.IGNORECASE)
        
        if confirmed_pattern:
            return True
        
        return False
        
    except Exception as e:
        print(f"  ⚠ Error checking confirmation status: {e}")
        return False


def get_dedup_columns(signal_type="entry"):
    """
    Get deduplication columns from configuration.
    Uses DEDUP_COLUMNS for most types, BREADTH_DEDUP_COLUMNS for breadth data.

    Args:
        signal_type: Type of signal ('entry', 'exit', 'portfolio_target_achieved', 'breadth')

    Returns:
        List of column names to use for deduplication
    """
    if signal_type == "breadth":
        dedup_cols = BREADTH_DEDUP_COLUMNS.copy()
    else:
        dedup_cols = DEDUP_COLUMNS.copy()
    
    return dedup_cols


def deduplicate_dataframe(df, dedup_columns=None, signal_type="entry"):
    """
    Remove duplicates from dataframe based on specified columns.
    
    Args:
        df: DataFrame to deduplicate
        dedup_columns: List of column names to check for duplicates (if None, uses signal_type to get defaults)
        signal_type: Type of signal ('entry', 'exit', 'portfolio_target_achieved', 'breadth') - used if dedup_columns is None
        
    Returns:
        Deduplicated DataFrame
    """
    if dedup_columns is None:
        dedup_columns = get_dedup_columns(signal_type)
    
    # Only use columns that exist in the dataframe
    available_cols = [col for col in dedup_columns if col in df.columns]
    
    if available_cols:
        original_count = len(df)
        df = df.drop_duplicates(subset=available_cols, keep='first')
        removed_count = original_count - len(df)
        
        if removed_count > 0:
            print(f"  ℹ Removed {removed_count} duplicate rows based on: {', '.join(available_cols)}")
    
    return df


def check_target_duplicate(row, master_csv_path):
    """
    Check if target signal already exists in master CSV based on key columns.
    
    Args:
        row: DataFrame row to check (should be enriched with Symbol, Signal Date, etc.)
        master_csv_path: Path to all_targets.csv
        
    Returns:
        True if duplicate found, False otherwise
    """
    import pandas as pd
    from pathlib import Path
    
    # Get deduplication columns from configuration
    dedup_cols = get_dedup_columns(signal_type="portfolio_target_achieved")
    
    master_file = Path(master_csv_path)
    
    # If master file doesn't exist, not a duplicate
    if not master_file.exists():
        return False
    
    try:
        master_df = pd.read_csv(master_file)
        
        # Check which columns exist in both row and master
        available_cols = [col for col in dedup_cols if col in master_df.columns and col in row.index]
        
        if not available_cols:
            print(f"  ⚠ Warning: No dedup columns found for comparison")
            return False
        
        # Check for exact match on ALL three columns
        for _, existing_row in master_df.iterrows():
            match = True
            for col in available_cols:
                # Convert to string for comparison to handle different data types
                existing_val = str(existing_row[col]).strip()
                new_val = str(row[col]).strip()
                
                if existing_val != new_val:
                    match = False
                    break
            
            if match:
                # Found exact duplicate
                print(f"  🚫 Duplicate found: {row.get('Symbol', 'N/A')} - {row.get('Signal Date', 'N/A')}")
                return True
        
        return False
        
    except Exception as e:
        print(f"  ⚠ Error checking duplicate: {e}")
        return False


def convert_signal_file_to_data_structure(
    input_file,
    signal_type="signal",
    output_base_dir=None,
    overwrite=False,
    dedup_columns=None
):
    """
    Convert a trading signal/target CSV file to the data folder structure.
    Automatically deduplicates data based on DEDUP_COLUMNS from .env.
    
    For signals: Splits into entry/ and exit/ folders based on exit date:
        - If exit date exists → exit/ folder (completed trades)
        - If no exit yet → entry/ folder (open positions)
        - Only entry signals with "is CONFIRMED" or "was CONFIRMED" status are processed
        - Exit signals are always processed (they're completed trades)
    
    For targets: Checks against master CSV before storing.
    
    Args:
        input_file: Path to input CSV file (e.g., outstanding_signal.csv, target_signal.csv)
        signal_type: 'signal' or 'portfolio_target_achieved'
        output_base_dir: Base directory for output (default: chatbot/data)
        overwrite: Whether to overwrite existing files
        dedup_columns: List of columns for deduplication (uses .env if None)
    """
    # Set default output directory if not provided
    if output_base_dir is None:
        output_base_dir = str(CHATBOT_DATA_DIR)
    
    # Note: dedup_columns parameter is now handled per-row based on signal type (entry/exit/target/breadth)
    # Each signal type uses different deduplication keys
    print("\n" + "="*80)
    print(f"CONVERTING: {input_file}")
    print("="*80 + "\n")
    
    # Read the CSV file
    try:
        df = pd.read_csv(input_file)
        print(f"✓ Loaded {len(df)} rows from {input_file}")
    except Exception as e:
        print(f"✗ Error reading file: {e}")
        return
    
    # Get the column names
    symbol_column = df.columns[1]  # "Symbol, Signal, Signal Date/Price[$]"
    exit_column = df.columns[2] if len(df.columns) > 2 else None  # "Exit Signal Date/Price[$]"
    
    print(f"✓ Parsing column: '{symbol_column}'")
    if exit_column and signal_type != "portfolio_target_achieved":
        print(f"✓ Exit column: '{exit_column}'")
    
    # Parse each row and append to consolidated CSVs only
    # Note: No folder structure is created - all data goes to consolidated CSV files
    processed = 0
    skipped = 0
    duplicates_rejected = 0
    unconfirmed_skipped = 0
    created_symbols = set()
    created_functions = set()
    signals_with_exit = 0
    signals_no_exit = 0
    
    # Handle different column structures for signal vs portfolio_target_achieved
    if signal_type == "portfolio_target_achieved":
        # For target_signal.csv column order:
        # col 0: Function
        # col 1: "Symbol, Signal, Signal Date/Price[$]"
        # col 2: Interval
        # col 3: Exit Signal Date/Price[$]
        # col 4: Target for which Price has achieved over 90 percent of gain %
        # col 5: Backtested Target Exit Date
        # col 6+: Other columns...
        function_column = df.columns[0]  # "Function"
        symbol_column = df.columns[1]  # "Symbol, Signal, Signal Date/Price[$]"
        exit_column = None  # Exit Signal Date/Price[$] is in column 3, but handled separately in target parsing section
        confirmation_column = None  # No confirmation column for targets
        use_current_date = True  # Use current date for targets
    else:
        # For signal files, function is first column, symbol is in column 1
        function_column = df.columns[0]  # Function name
        symbol_column = df.columns[1]
        exit_column = df.columns[2] if len(df.columns) > 2 else None
        # Find "Interval, Confirmation Status" column (usually column 5)
        confirmation_column = None
        for col in df.columns:
            if "Confirmation Status" in col or "confirmation" in col.lower():
                confirmation_column = col
                break
        use_current_date = False
        
        if confirmation_column:
            print(f"✓ Confirmation column found: '{confirmation_column}'")
        else:
            print(f"⚠ Warning: Confirmation Status column not found. All signals will be processed.")
    
    for idx, row in df.iterrows():
        # Get function name
        function_name = row[function_column]
        if pd.isna(function_name) or not function_name:
            function_name = "UNKNOWN"
        
        # Parse symbol based on file type
        if signal_type == "portfolio_target_achieved":
            # For portfolio_target_achieved, parse the compound column "Symbol, Signal, Signal Date/Price[$]"
            symbol_data = row[symbol_column]
            if pd.notna(symbol_data):
                symbol, signal_date, sig_type, price = parse_symbol_signal_column(symbol_data)
            else:
                symbol, signal_date, sig_type, price = None, None, None, None
            
            if not symbol or not signal_date:
                # Fallback: try to get symbol directly if parsing fails
                if pd.notna(row[symbol_column]):
                    symbol = str(row[symbol_column]).strip()
                    # Try to extract symbol from the beginning if it's a compound field
                    if ',' in symbol:
                        symbol = symbol.split(',')[0].strip()
                else:
                    symbol = ""
                signal_date = datetime.now().strftime("%Y-%m-%d")
                sig_type = ""
            
            # For targets, keep ALL columns from source as-is
            # Note: Symbol, Signal, Signal Date are already in "Symbol, Signal, Signal Date/Price[$]" column
            # No need to create separate columns - dedup key extraction handles parsing directly
            
            # Ensure Interval column is properly named (it should already be there from source)
            if 'Interval' not in row.index and len(df.columns) > 2:
                interval_column = df.columns[2]
                if interval_column in row.index:
                    row['Interval'] = str(row[interval_column]).strip() if pd.notna(row[interval_column]) else ""

            # Ensure Exit Signal Date/Price[$] column is properly named
            if 'Exit Signal Date/Price[$]' not in row.index and len(df.columns) > 3:
                exit_signal_column = df.columns[3]
                if exit_signal_column in row.index:
                    row['Exit Signal Date/Price[$]'] = str(row[exit_signal_column]).strip() if pd.notna(row[exit_signal_column]) else ""

            # Ensure Target column is properly named
            if 'Target for which Price has achieved over 90 percent of gain %' not in row.index and len(df.columns) > 4:
                target_column = df.columns[4]
                if target_column in row.index:
                    row['Target for which Price has achieved over 90 percent of gain %'] = str(row[target_column]).strip() if pd.notna(row[target_column]) else ""

            # Ensure Backtested Target Exit Date column is properly named
            if 'Backtested Target Exit Date' not in row.index and len(df.columns) > 5:
                backtested_exit_column = df.columns[5]
                if backtested_exit_column in row.index:
                    row['Backtested Target Exit Date'] = str(row[backtested_exit_column]).strip() if pd.notna(row[backtested_exit_column]) else ""
            
            # Note: Target signals are now handled like entry/exit signals
            # No master CSV duplicate checking needed - they append to portfolio_target_achieved.csv
        else:
            # For signals, parse the compound column
            symbol_data = row[symbol_column]
            if pd.notna(symbol_data):
                symbol, signal_date, sig_type, price = parse_symbol_signal_column(symbol_data)
            else:
                symbol, signal_date, sig_type, price = None, None, None, None
        
        if not symbol or not signal_date:
            skipped += 1
            continue
        
        # Check for exit date (only for signals, not targets)
        exit_date = None
        exit_price = None
        
        if signal_type != "portfolio_target_achieved" and exit_column and exit_column in row.index:
            exit_data = row[exit_column]
            if pd.notna(exit_data):
                exit_date, exit_price = parse_exit_signal_column(exit_data)
            else:
                exit_date, exit_price = None, None
        
        # For entry signals (signals without exit), check confirmation status
        # Exit signals are always processed (they're completed trades)
        if signal_type == "signal" and not exit_date and confirmation_column and confirmation_column in row.index:
            confirmation_status = row[confirmation_column]
            if pd.notna(confirmation_status) and not is_confirmed_signal(confirmation_status):
                unconfirmed_skipped += 1
                skipped += 1
                continue  # Skip unconfirmed entry signals
            elif pd.isna(confirmation_status):
                # If confirmation status is NaN, skip the signal (can't verify it's confirmed)
                unconfirmed_skipped += 1
                skipped += 1
                continue
        
        # Determine which folder and date to use based on signal type and exit date
        # Determine signal type and date to use
        if signal_type == "portfolio_target_achieved":
            # For portfolio_target_achieved, always use current date
            date_to_use = datetime.now().strftime("%Y-%m-%d")
            row_signal_type = "portfolio_target_achieved"
        elif exit_date:
            # For signals with exit, use exit date (completed trade)
            date_to_use = exit_date
            signals_with_exit += 1
            row_signal_type = "exit"
        else:
            # For signals without exit, use signal date (open position)
            date_to_use = signal_date
            signals_no_exit += 1
            row_signal_type = "entry"
        
        # Note: We do NOT add Interval, Signal, Symbol, Date columns to the row
        # These are extracted from existing columns for deduplication only
        # The original columns already contain this information:
        # - Interval is in "Interval, Confirmation Status"
        # - Signal (Long/Short) is in "Symbol, Signal, Signal Date/Price[$]"
        # - Symbol is in "Symbol, Signal, Signal Date/Price[$]"
        # - Date is in "Symbol, Signal, Signal Date/Price[$]"
        
        # Add SignalType column to the row (this is the only new column we add)
        row['SignalType'] = row_signal_type
        
        # Signal Open Price handling:
        # 1. If trade_store data has 'Signal Open Price' column with value, keep it
        # 2. Otherwise, use signal text price as fallback
        if signal_type != "breadth":
            if 'Signal Open Price' not in row.index or pd.isna(row.get('Signal Open Price')) or row.get('Signal Open Price') == '':
                # No Signal Open Price in trade_store data, use fallback
                if price is not None:
                    row['Signal Open Price'] = f"{price:.4f}"
                else:
                    row['Signal Open Price'] = ""
            else:
                # Signal Open Price exists in trade_store, format it to 4 decimals
                try:
                    existing_price = float(row['Signal Open Price'])
                    row['Signal Open Price'] = f"{existing_price:.4f}"
                except (ValueError, TypeError):
                    # Invalid value, use fallback
                    if price is not None:
                        row['Signal Open Price'] = f"{price:.4f}"
                    else:
                        row['Signal Open Price'] = ""
        
        # Track symbols and functions for summary
        created_symbols.add(symbol)
        created_functions.add(function_name)
        
        # ONLY append to consolidated CSV (no individual files)
        try:
            append_to_consolidated_csv(row, row_signal_type, output_base_dir)
            processed += 1
        except Exception as e:
            print(f"  ⚠ Error appending to consolidated CSV: {e}")
            skipped += 1
    
    print("\n" + "-"*80)
    print("CONVERSION SUMMARY")
    print("-"*80)
    print(f"Signal Type: {signal_type.upper()}")
    print(f"✓ Total rows processed: {processed}")
    print(f"⚠ Rows skipped: {skipped}")
    if signal_type == "portfolio_target_achieved":
        print(f"🚫 Duplicates rejected: {duplicates_rejected}")
        print(f"   → Deduplication keys: Function, Symbol, Signal Type, Interval, Signal Open Price")
    if signal_type == "signal" and unconfirmed_skipped > 0:
        print(f"🚫 Unconfirmed entry signals skipped: {unconfirmed_skipped} (only 'is CONFIRMED' or 'was CONFIRMED' are processed)")
    print(f"✓ Unique assets: {len(created_symbols)}")
    print(f"✓ Unique functions: {len(created_functions)}")
    if signal_type != "portfolio_target_achieved":
        print(f"\n� Signal Distribution:")
        print(f"   ✓ EXIT signals (completed trades): {signals_with_exit}")
        print(f"      → Appended to: chatbot/data/exit.csv")
        print(f"      → Deduplication keys: Function, Symbol, Signal Type, Interval, Signal Date, Signal Open Price")
        print(f"   ✓ ENTRY signals (confirmed open positions): {signals_no_exit}")
        print(f"      → Appended to: chatbot/data/entry.csv")
        print(f"      → Deduplication keys: Function, Symbol, Signal Type, Interval, Signal Open Price")
        if unconfirmed_skipped > 0:
            print(f"   ⚠ Unconfirmed entry signals filtered out: {unconfirmed_skipped}")
    print(f"\n✓ Functions: {', '.join(sorted(list(created_functions)))}")
    print(f"\n✓ Assets (sample): {', '.join(sorted(list(created_symbols)[:10]))}")
    if len(created_symbols) > 10:
        print(f"  ... and {len(created_symbols) - 10} more")
    
    if signal_type == "portfolio_target_achieved":
        print(f"\n✓ Consolidated CSV: chatbot/data/portfolio_target_achieved.csv (updated)")
    else:
        print(f"\n✓ Consolidated CSVs:")
        print(f"   - chatbot/data/entry.csv (updated)")
        print(f"   - chatbot/data/exit.csv (updated)")
    print("="*80 + "\n")
    
    return processed, skipped, created_symbols


def parse_current_price_column(value):
    """
    Parse the "Today Trading Date/Price[$], Today Price vs Signal" column.
    
    Example: "2025-11-18 (Price: 401.25), 0.0% below"
    Returns: (date, price, percentage_change) or (None, None, None)
    """
    try:
        if not value or pd.isna(value):
            return None, None, None
        
        value_str = str(value).strip()
        
        # Extract date
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', value_str)
        date = date_match.group(1) if date_match else None
        
        # Extract price (handle negative values and thousand separators)
        price_match = re.search(r'Price:\s*([-]?\d+(?:\.\d+)?(?:,\d{3})*)', value_str)
        if price_match:
            price_str = price_match.group(1).replace(',', '')
            price = float(price_str)
        else:
            price = None
        
        # Extract percentage change (optional)
        pct_match = re.search(r'([\d.]+)%\s*(above|below)', value_str)
        percentage = None
        if pct_match:
            pct_value = float(pct_match.group(1))
            direction = pct_match.group(2)
            percentage = pct_value if direction == 'above' else -pct_value
        
        return date, price, percentage
        
    except Exception as e:
        print(f"  ⚠ Error parsing today price: {value} - {e}")
        return None, None, None


def append_to_consolidated_csv(row, signal_type, data_base_dir=None):
    """
    Update or insert signal row in consolidated CSV file.
    
    CRITICAL LOGIC:
    1. Reads data from trade_store CSV files
    2. Checks deduplication key for each row
    3. If key exists → UPDATE existing row with new data from trade_store
    4. If key is new → INSERT new row from trade_store
    5. Signal Open Price comes from trade_store (already in row data)
    
    Consolidated files:
    - chatbot/data/entry.csv (open positions)
    - chatbot/data/exit.csv (completed trades)
    - chatbot/data/portfolio_target_achieved.csv (target achievements)
    - chatbot/data/breadth.csv (market breadth)
    
    Args:
        row: Pandas Series with signal data (from trade_store)
        signal_type: 'entry', 'exit', 'portfolio_target_achieved', or 'breadth'
        data_base_dir: Base directory for data (default: chatbot/data)
    """
    try:
        # Set default data directory if not provided
        if data_base_dir is None:
            data_base_dir = str(CHATBOT_DATA_DIR)
            
        # Determine consolidated CSV path based on signal type
        csv_path = Path(data_base_dir) / f"{signal_type}.csv"
        
        # Prepare new row DataFrame
        new_row_df = pd.DataFrame([row])
        new_row_df = normalize_today_price_columns(new_row_df)
        
        # Helper: Extract dedup key based on signal type
        def get_dedup_key(row_data, sig_type):
            """Extract deduplication key columns based on signal type"""
            signal_col = row_data.get("Symbol, Signal, Signal Date/Price[$]", "")
            interval_col = row_data.get("Interval, Confirmation Status", "")
            
            if sig_type == "entry":
                # Key: Function + Symbol + Signal Type + Interval + Signal Open Price
                function = str(row_data.get("Function", "")).strip()
                match_signal = re.search(r'^([^,]+),\s*([^,]+),', str(signal_col))
                match_interval = re.search(r'^([^,]+)', str(interval_col))
                symbol = match_signal.group(1).strip() if match_signal else ""
                signal_type_val = match_signal.group(2).strip() if match_signal else ""
                interval = match_interval.group(1).strip() if match_interval else ""
                signal_open_price = str(row_data.get("Signal Open Price", "")).strip()
                return (function, symbol, signal_type_val, interval, signal_open_price)
                
            elif sig_type == "exit":
                # Key: Function + Symbol + Signal Type + Interval + Signal Date + Signal Open Price
                function = str(row_data.get("Function", "")).strip()
                match_signal = re.search(r'^([^,]+),\s*([^,]+),\s*(\d{4}-\d{2}-\d{2})', str(signal_col))
                match_interval = re.search(r'^([^,]+)', str(interval_col))
                symbol = match_signal.group(1).strip() if match_signal else ""
                signal_type_val = match_signal.group(2).strip() if match_signal else ""
                signal_date = match_signal.group(3).strip() if match_signal else ""
                interval = match_interval.group(1).strip() if match_interval else ""
                signal_open_price = str(row_data.get("Signal Open Price", "")).strip()
                return (function, symbol, signal_type_val, interval, signal_date, signal_open_price)
                
            elif sig_type == "portfolio_target_achieved":
                # Key: Function + Symbol + Signal Type + Interval + Signal Open Price
                function = str(row_data.get("Function", "")).strip()
                match_signal = re.search(r'^([^,]+),\s*([^,]+),', str(signal_col))
                match_interval = re.search(r'^([^,]+)', str(interval_col))
                symbol = match_signal.group(1).strip() if match_signal else ""
                signal_type_val = match_signal.group(2).strip() if match_signal else ""
                interval = match_interval.group(1).strip() if match_interval else ""
                signal_open_price = str(row_data.get("Signal Open Price", "")).strip()
                return (function, symbol, signal_type_val, interval, signal_open_price)

            elif sig_type == "breadth":
                # Key: Function + Date
                function = str(row_data.get("Function", "")).strip()
                date_col = row_data.get("Date", "")
                match = re.search(r'(\d{4}-\d{2}-\d{2})', str(date_col))
                date_val = match.group(1) if match else ""
                return (function, date_val)

            return None
        
        # Get dedup key for new row
        new_key = get_dedup_key(row, signal_type)
        
        # Read existing CSV if it exists (optional shared lock)
        if csv_path.exists():
            existing_df = read_csv_optional_locked(csv_path)
            existing_df = normalize_today_price_columns(existing_df)
            
            # Find if key already exists
            key_exists = False
            existing_row_idx = None
            
            for idx, existing_row in existing_df.iterrows():
                existing_key = get_dedup_key(existing_row, signal_type)
                if existing_key == new_key:
                    key_exists = True
                    existing_row_idx = idx
                    break
            
            if key_exists:
                # UPDATE: Key exists → replace entire row with new data
                # Drop the old row and append the new one
                existing_df = existing_df.drop(existing_row_idx)
                combined_df = pd.concat([existing_df, new_row_df], ignore_index=True)
            else:
                # INSERT: New key → append new row
                combined_df = pd.concat([existing_df, new_row_df], ignore_index=True)
        else:
            # File doesn't exist yet → INSERT new row
            
            combined_df = new_row_df

        combined_df = normalize_today_price_columns(combined_df)
        # Ensure legacy duplicate column is never written (defense in depth)
        if TODAY_PRICE_COLUMN_LEGACY in combined_df.columns:
            combined_df = combined_df.drop(columns=[TODAY_PRICE_COLUMN_LEGACY])
        
        # Note: NO additional deduplication needed here
        # Deduplication is already handled by the key matching logic above
        # which uses the proper dedup key based on signal type:
        # - entry: Function + Symbol + Signal Type + Interval + Signal Open Price
        # - exit: Function + Symbol + Signal Type + Interval + Signal Date + Signal Open Price
        # - portfolio_target_achieved: Function + Symbol + Signal Type + Interval + Signal Open Price
        # - breadth: Function + Date
        
        # Write back to consolidated CSV (atomic replace + lock)
        write_dataframe_csv_atomic_guarded(combined_df, csv_path)
        
    except Exception as e:
        import traceback
        print(f"  ⚠ Error updating consolidated CSV {csv_path}: {e}")
        print(f"  ⚠ Traceback: {traceback.format_exc()}")


def update_current_prices_in_data_files(data_base_dir=None, stock_data_dir=None):
    """
    Update today prices in consolidated CSV files using live prices from stock_data.
    
    This function:
    1. Reads consolidated CSV files (entry.csv, exit.csv, portfolio_target_achieved.csv)
    2. For each file, extracts symbols and updates "Today Trading Date/Price[$], Today Price vs Signal" column
    3. Uses the latest price from stock_data CSV files
    
    Args:
        data_base_dir: Base directory for chatbot data (uses config default if None)
        stock_data_dir: Directory containing stock_data CSV files (uses config default if None)
    """
    if data_base_dir is None:
        data_base_dir = str(CHATBOT_DATA_DIR)
    if stock_data_dir is None:
        stock_data_dir = str(STOCK_DATA_DIR)
    
    print("\n" + "="*80)
    print("UPDATING TODAY PRICES FROM LIVE STOCK DATA")
    print("="*80 + "\n")
    
    data_base = Path(data_base_dir)
    stock_data_base = Path(stock_data_dir)
    
    if not data_base.exists():
        print(f"✗ Data directory not found: {data_base_dir}")
        return
    
    if not stock_data_base.exists():
        print(f"✗ Stock data directory not found: {stock_data_dir}")
        return
    
    # Define consolidated CSV files to process
    csv_files = {
        'entry': (data_base / 'entry.csv', 'Entry Signals (Open Positions)'),
        'exit': (data_base / 'exit.csv', 'Exit Signals (Completed Trades)'),
        'portfolio_target_achieved': (data_base / 'portfolio_target_achieved.csv', 'Portfolio Target Achieved')
    }
    
    # Canonical column name for today price
    current_price_column = TODAY_PRICE_COLUMN
    
    updated_count = 0
    skipped_count = 0
    price_not_found_count = 0
    total_rows_updated = 0
    
    # Process each consolidated CSV file
    for signal_type, (csv_path, description) in csv_files.items():
        if not csv_path.exists():
            print(f"⚠ {description} file not found: {csv_path}")
            continue
        
        print(f"\n📂 Processing {description}...")
        
        try:
            df = read_csv_optional_locked(csv_path)
            df = normalize_today_price_columns(df)
            
            if df.empty:
                print(f"  ℹ File is empty, skipping")
                continue
            
            if current_price_column not in df.columns:
                print(f"  ⚠ Today price column not found, skipping")
                skipped_count += 1
                continue
            
            rows_updated_in_file = 0
            
            symbol_col = "Symbol, Signal, Signal Date/Price[$]"
            row_symbols: List[str] = []
            sym_by_idx: Dict[int, str] = {}
            for idx, row in df.iterrows():
                if symbol_col not in row.index:
                    continue
                symbol_data = row[symbol_col]
                if pd.notna(symbol_data):
                    parsed_symbol, _, _, _ = parse_symbol_signal_column(symbol_data)
                    if parsed_symbol:
                        ns = normalize_symbol(parsed_symbol)
                        sym_by_idx[idx] = ns
                        row_symbols.append(ns)
            
            price_map = batch_latest_prices(row_symbols, Path(stock_data_dir) if stock_data_dir else None)
            
            for idx, row in df.iterrows():
                sym = sym_by_idx.get(idx)
                if not sym:
                    continue
                latest = price_map.get(sym)
                if latest is None:
                    price_not_found_count += 1
                    continue
                latest_price, latest_date = latest
                if latest_price is None or latest_date is None:
                    price_not_found_count += 1
                    continue
                
                today_cell, mtm_cell, td_cell = enrich_row_current_prices(row, latest_price, latest_date)
                df.at[idx, current_price_column] = today_cell
                if MTM_HOLDING_COLUMN in df.columns:
                    df.at[idx, MTM_HOLDING_COLUMN] = mtm_cell
                if TRADING_DAYS_COLUMN in df.columns:
                    df.at[idx, TRADING_DAYS_COLUMN] = td_cell
                rows_updated_in_file += 1
            
            # Save updated file if changes were made (ensure legacy column is never written)
            if rows_updated_in_file > 0:
                if TODAY_PRICE_COLUMN_LEGACY in df.columns:
                    df = df.drop(columns=[TODAY_PRICE_COLUMN_LEGACY])
                write_dataframe_csv_atomic_guarded(df, csv_path)
                updated_count += 1
                total_rows_updated += rows_updated_in_file
                print(f"  ✓ Updated {rows_updated_in_file} rows")
            else:
                print(f"  ℹ No rows updated")
                
        except Exception as e:
            print(f"  ⚠ Error updating {csv_path}: {e}")
            skipped_count += 1
    
    print("\n" + "-"*80)
    print("PRICE UPDATE SUMMARY")
    print("-"*80)
    print(f"✓ Total files updated: {updated_count}")
    print(f"✓ Total rows updated: {total_rows_updated}")
    print(f"⚠ Files skipped: {skipped_count}")
    print(f"⚠ Symbols with no price data: {price_not_found_count}")
    print("="*80 + "\n")


def convert_breadth_report(
    input_file,
    output_base_dir=None
):
    """
    Convert breadth report to data folder structure.
    Breadth is market-wide, so structure is: chatbot/data/breadth/YYYY-MM-DD.csv
    
    Args:
        input_file: Path to breadth.csv file
        output_base_dir: Base directory for output (uses config default if None)
    """
    if output_base_dir is None:
        output_base_dir = str(CHATBOT_DATA_DIR)
    print("\n" + "="*80)
    print(f"CONVERTING BREADTH REPORT: {input_file}")
    print("="*80 + "\n")
    
    # Read the breadth CSV file
    try:
        df = pd.read_csv(input_file)
        print(f"✓ Loaded {len(df)} rows from {input_file}")
    except Exception as e:
        print(f"✗ Error reading file: {e}")
        return 0, 0
    
    # Use current date for Date column
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    # Add Date column to the dataframe
    df['Date'] = current_date
    
    # ONLY append to consolidated breadth.csv (no individual files)
    try:
        print(f"✓ Functions in report: {len(df)}")
        print(f"✓ Columns: {', '.join(df.columns.tolist())}")
        
        # Append each row to consolidated breadth.csv
        for _, row in df.iterrows():
            append_to_consolidated_csv(row, "breadth", output_base_dir)
        
        processed = 1
        skipped = 0
    except Exception as e:
        print(f"✗ Error appending to consolidated breadth.csv: {e}")
        processed = 0
        skipped = 1
    
    print("\n" + "-"*80)
    print("BREADTH CONVERSION SUMMARY")
    print("-"*80)
    print(f"✓ Date: {current_date}")
    print(f"✓ Total functions: {len(df)}")
    print(f"✓ Consolidated CSV: chatbot/data/breadth.csv (updated)")
    print("="*80 + "\n")
    
    return processed, skipped


def main():
    """Main function with examples."""
    
    print("\n" + "="*80)
    print("TRADING SIGNAL, TARGET & BREADTH DATA CONVERTER")
    print("="*80 + "\n")
    
    print("This script converts trading CSV files to the chatbot data structure.")
    print("Structure (Consolidated CSV Approach):")
    print("  - chatbot/data/entry.csv (all open positions)")
    print("  - chatbot/data/exit.csv (all completed trades)")
    print("  - chatbot/data/portfolio_target_achieved.csv (all portfolio target achieved)")
    print("  - chatbot/data/breadth.csv (all market breadth data)")
    print("Note: Folder structure creation is disabled - using consolidated CSVs only.\n")
    
    # Convert outstanding_signal.csv (signals)
    # Handle both naming conventions: outstanding_signal.csv and YYYY-MM-DD_outstanding_signal.csv
    print("-" * 80)
    print("Converting SIGNAL data (outstanding_signal.csv)")
    print("-" * 80)
    
    # Try to find the most recent outstanding_signal file
    signal_file = None
    
    # Use trade store directory from config
    trade_store_us = Path(str(CHATBOT_DATA_DIR).replace("chatbot/data", "trade_store/US"))
    
    # First try exact match
    signal_file_exact = trade_store_us / "outstanding_signal.csv"
    if signal_file_exact.exists():
        signal_file = signal_file_exact
    else:
        # Try pattern matching for date_name.csv format
        signal_pattern_files = list(trade_store_us.glob("*_outstanding_signal.csv"))
        if signal_pattern_files:
            # Sort by modification time and get the most recent
            signal_pattern_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            signal_file = signal_pattern_files[0]
            print(f"ℹ Found dated file: {signal_file.name}")
    
    if signal_file and signal_file.exists():
        convert_signal_file_to_data_structure(
            input_file=signal_file,
            signal_type="signal",
            output_base_dir=str(CHATBOT_DATA_DIR),
            overwrite=False
        )
    else:
        print(f"⚠ File not found: outstanding_signal.csv (tried exact match and date_name.csv pattern)")
    
    # Convert target_signal.csv (targets)
    # Handle both naming conventions: target_signal.csv and YYYY-MM-DD_target_signal.csv
    print("\n" + "-" * 80)
    print("Converting TARGET data (target_signal.csv)")
    print("-" * 80)
    
    # Try to find the most recent target_signal file
    target_file = None
    
    # First try exact match
    target_file_exact = trade_store_us / "target_signal.csv"
    if target_file_exact.exists():
        target_file = target_file_exact
    else:
        # Try pattern matching for date_name.csv format
        target_pattern_files = list(trade_store_us.glob("*_target_signal.csv"))
        if target_pattern_files:
            # Sort by modification time and get the most recent
            target_pattern_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            target_file = target_pattern_files[0]
            print(f"ℹ Found dated file: {target_file.name}")
    
    if target_file and target_file.exists():
        convert_signal_file_to_data_structure(
            input_file=target_file,
            signal_type="portfolio_target_achieved",
            output_base_dir=str(CHATBOT_DATA_DIR),
            overwrite=False
        )
    else:
        print(f"⚠ File not found: target_signal.csv (tried exact match and date_name.csv pattern)")
    
    # Convert breadth.csv (market-wide breadth report)
    # Handle both naming conventions: breadth.csv and YYYY-MM-DD_breadth.csv
    print("\n" + "-" * 80)
    print("Converting BREADTH data (breadth.csv)")
    print("-" * 80)
    
    # Try to find the most recent breadth file
    breadth_file = None
    
    # First try exact match
    breadth_file_exact = trade_store_us / "breadth.csv"
    if breadth_file_exact.exists():
        breadth_file = breadth_file_exact
    else:
        # Try pattern matching for date_name.csv format (excluding breadth_us.csv)
        breadth_pattern_files = [f for f in trade_store_us.glob("*_breadth.csv") 
                                if "breadth_us" not in f.name]
        if breadth_pattern_files:
            # Sort by modification time and get the most recent
            breadth_pattern_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            breadth_file = breadth_pattern_files[0]
            print(f"ℹ Found dated file: {breadth_file.name}")
    
    if breadth_file and breadth_file.exists():
        convert_breadth_report(
            input_file=breadth_file,
            output_base_dir=str(CHATBOT_DATA_DIR)
        )
    else:
        print(f"⚠ File not found: breadth.csv (tried exact match and date_name.csv pattern)")
    
    # Copy Claude report to chatbot data folder
    print("\n" + "-" * 80)
    print("Copying CLAUDE REPORT to chatbot data folder")
    print("-" * 80)
    
    # Look for the most recent Claude report
    claude_report_files = list(trade_store_us.glob("*_claude_signals_report.txt"))
    if claude_report_files:
        # Sort by modification time and get the most recent
        claude_report_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        latest_claude_report = claude_report_files[0]
        print(f"ℹ Found Claude report: {latest_claude_report.name}")
        
        # Copy to chatbot data folder
        destination = CHATBOT_DATA_DIR / "claude_report.txt"
        import shutil
        shutil.copy2(latest_claude_report, destination)
        print(f"✓ Copied to: {destination}")
    else:
        print(f"⚠ No Claude report files found (pattern: *_claude_signals_report.txt)")
    
    # Update today prices in all chatbot data files using live prices from stock_data
    print("\n" + "-" * 80)
    print("Updating today prices from live stock data")
    print("-" * 80)
    update_current_prices_in_data_files(
        data_base_dir=str(CHATBOT_DATA_DIR),
        stock_data_dir=str(STOCK_DATA_DIR)
    )
    
    print("\n" + "="*80)
    print("✓ Conversion Complete!")
    print("="*80)
    print("\nConsolidated CSV files updated:")
    print("  - chatbot/data/entry.csv (open positions)")
    print("  - chatbot/data/exit.csv (completed trades)")
    print("  - chatbot/data/portfolio_target_achieved.csv (target achievements)")
    print("  - chatbot/data/breadth.csv (market breadth)")
    print("  - chatbot/data/claude_report.txt (Claude signals analysis)")
    print("\n✓ Today prices updated from live stock data")
    print()


if __name__ == "__main__":
    main()