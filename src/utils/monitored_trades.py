"""
Utility module for managing monitored trades
Stores and updates personal portfolio trades
"""

import pandas as pd
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import re

from src.utils.mtm_pricing import (
    batch_latest_prices,
    calculate_holding_period,
    calculate_mark_to_market,
    calculate_price_change_percentage,
    get_latest_price_from_stock_data,
    normalize_symbol,
)


MONITORED_TRADES_FILE = "monitored_trades.json"


def get_monitored_trades_path() -> Path:
    """Get the path to the monitored trades storage file"""
    project_root = Path(__file__).resolve().parent.parent.parent
    return project_root / MONITORED_TRADES_FILE


def generate_trade_id(symbol: str, signal_date: str, interval: str, signal_type: str, function: str) -> str:
    """Generate a unique ID for a trade based on its identifying characteristics"""
    # Normalize values
    symbol = str(symbol).strip().upper()
    signal_date = str(signal_date).strip()
    interval = str(interval).strip()
    signal_type = str(signal_type).strip()
    function = str(function).strip()
    
    # Create a unique identifier
    trade_id = f"{symbol}_{signal_date}_{interval}_{signal_type}_{function}"
    # Replace any problematic characters
    trade_id = re.sub(r'[^a-zA-Z0-9_\-]', '_', trade_id)
    return trade_id


def load_monitored_trades() -> pd.DataFrame:
    """Load monitored trades from JSON file"""
    file_path = get_monitored_trades_path()
    
    if not file_path.exists():
        return pd.DataFrame()
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        if not data or 'trades' not in data:
            return pd.DataFrame()
        
        # Convert list of dicts to DataFrame
        df = pd.DataFrame(data['trades'])
        return df
    except Exception as e:
        print(f"Error loading monitored trades: {e}")
        return pd.DataFrame()


def save_monitored_trades(df: pd.DataFrame) -> bool:
    """Save monitored trades to JSON file"""
    file_path = get_monitored_trades_path()
    
    try:
        # Convert DataFrame to list of dicts
        trades = df.to_dict('records') if not df.empty else []
        
        data = {
            'last_updated': datetime.now().isoformat(),
            'trades': trades
        }
        
        # Ensure directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        return True
    except Exception as e:
        print(f"Error saving monitored trades: {e}")
        return False


def add_trade_to_monitored(trade_data: Dict) -> bool:
    """Add a new trade to monitored trades"""
    df = load_monitored_trades()
    
    # Generate unique ID
    trade_id = generate_trade_id(
        trade_data.get('Symbol', ''),
        trade_data.get('Signal_Date', ''),
        trade_data.get('Interval', ''),
        trade_data.get('Signal_Type', ''),
        trade_data.get('Function', '')
    )
    
    # Check if trade already exists
    if not df.empty and 'Trade_ID' in df.columns:
        if trade_id in df['Trade_ID'].values:
            return False  # Trade already exists
    
    # Add trade ID and metadata
    trade_data['Trade_ID'] = trade_id
    trade_data['Added_Date'] = datetime.now().isoformat()
    trade_data['Last_Updated'] = datetime.now().isoformat()
    
    # Initialize exit fields if not present
    if 'Exit_Date' not in trade_data:
        trade_data['Exit_Date'] = None
    if 'Exit_Price' not in trade_data:
        trade_data['Exit_Price'] = None
    if 'Current_Price' not in trade_data:
        trade_data['Current_Price'] = None
    if 'Current_Date' not in trade_data:
        trade_data['Current_Date'] = None
    
    # Add to DataFrame
    new_row = pd.DataFrame([trade_data])
    if df.empty:
        df = new_row
    else:
        df = pd.concat([df, new_row], ignore_index=True)
    
    return save_monitored_trades(df)


def remove_trade_from_monitored(trade_id: str) -> bool:
    """Remove a trade from monitored trades"""
    df = load_monitored_trades()
    
    if df.empty or 'Trade_ID' not in df.columns:
        return False
    
    # Filter out the trade
    df = df[df['Trade_ID'] != trade_id]
    
    return save_monitored_trades(df)


def update_monitored_trades_prices() -> bool:
    """Update today prices for all monitored trades and update Raw_Data"""
    df = load_monitored_trades()
    
    if df.empty:
        return True
    
    row_symbols = []
    for _, row in df.iterrows():
        s = row.get("Symbol", "")
        if s:
            row_symbols.append(normalize_symbol(s))
    price_map = batch_latest_prices(row_symbols, None)

    updated = False
    for idx, row in df.iterrows():
        symbol = normalize_symbol(row.get("Symbol", ""))
        if not symbol:
            continue

        latest = price_map.get(symbol)
        if latest is None:
            continue
        current_price, current_date = latest
        if current_price is None or current_date is None:
            continue

        df.at[idx, 'Current_Price'] = current_price
        df.at[idx, 'Current_Date'] = current_date
        df.at[idx, 'Last_Updated'] = datetime.now().isoformat()

        # Update Raw_Data if it exists
        if 'Raw_Data' in row and pd.notna(row.get('Raw_Data')):
            raw_data = row['Raw_Data']

            # Parse Raw_Data if it's a string
            if isinstance(raw_data, str):
                try:
                    import json
                    raw_data = json.loads(raw_data)
                except Exception:
                    raw_data = {}

            if isinstance(raw_data, dict):
                # Get signal price and type for calculations
                signal_price = row.get('Signal_Price', 0)
                signal_type = row.get('Signal_Type', 'Long')
                signal_date = row.get('Signal_Date', '')

                # Calculate price change percentage
                price_change_str = calculate_price_change_percentage(current_price, signal_price, signal_type)

                # Update "Today Trading Date/Price[$], Today Price vs Signal" column
                current_price_col = "Today Trading Date/Price[$], Today Price vs Signal"
                raw_data[current_price_col] = f"{current_date} (Price: {current_price:.4f}), {price_change_str}"

                # Calculate holding period
                holding_days = calculate_holding_period(signal_date, current_date)

                # Calculate mark to market
                mtm_pct = calculate_mark_to_market(current_price, signal_price, signal_type)

                # Update "Current Mark to Market and Holding Period" column
                mtm_col = "Current Mark to Market and Holding Period"
                raw_data[mtm_col] = f"{mtm_pct}, {holding_days} days"

                # Update "Trading Days between Signal and Today Date" column
                trading_days_col = "Trading Days between Signal and Today Date"
                raw_data[trading_days_col] = f"{holding_days} days"

                # Save updated Raw_Data back
                df.at[idx, 'Raw_Data'] = raw_data

        updated = True
    
    if updated:
        return save_monitored_trades(df)
    
    return True


def check_exit_signals_in_outstanding(df: pd.DataFrame, outstanding_df: pd.DataFrame) -> pd.DataFrame:
    """
    Check for exit signals in outstanding signals for monitored trades.
    Updates Exit_Date and Exit_Price if exit signal is found.
    
    Args:
        df: Monitored trades DataFrame
        outstanding_df: Outstanding signals DataFrame
    
    Returns:
        Updated monitored trades DataFrame
    """
    if df.empty or outstanding_df.empty:
        return df
    
    # Ensure required columns exist
    required_cols = ['Symbol', 'Signal_Date', 'Interval', 'Signal_Type', 'Function']
    if not all(col in df.columns for col in required_cols):
        return df
    
    if 'Symbol' not in outstanding_df.columns:
        return df
    
    # Parse exit signal column from outstanding signals
    exit_col = 'Exit Signal Date/Price[$]'
    if exit_col not in outstanding_df.columns:
        return df
    
    for idx, monitored_row in df.iterrows():
        # Skip if already has exit
        if pd.notna(monitored_row.get('Exit_Date')) and monitored_row.get('Exit_Date'):
            continue
        
        # Match criteria
        symbol = str(monitored_row['Symbol']).strip().upper()
        signal_date = str(monitored_row['Signal_Date']).strip()
        interval = str(monitored_row['Interval']).strip()
        signal_type = str(monitored_row['Signal_Type']).strip()
        function = str(monitored_row['Function']).strip()
        
        # Find matching signal in outstanding - match on symbol and function first
        matches = outstanding_df[
            (outstanding_df['Symbol'].str.strip().str.upper() == symbol) &
            (outstanding_df['Function'].str.strip() == function)
        ]
        
        if matches.empty:
            continue
        
        # Check each match for exit signal and verify it's the same trade
        for _, match_row in matches.iterrows():
            # Verify this is the same signal by checking signal date and type
            signal_info = str(match_row.get('Symbol, Signal, Signal Date/Price[$]', ''))
            
            # Check if signal date matches
            if signal_date not in signal_info:
                continue
            
            # Check if signal type matches (Long/Short)
            if signal_type.upper() not in signal_info.upper():
                continue
            
            # Check interval if available in outstanding data
            if 'Interval' in match_row.index:
                match_interval = str(match_row['Interval']).strip()
                if interval and match_interval and interval.lower() not in match_interval.lower() and match_interval.lower() not in interval.lower():
                    continue
            
            # Now check for exit signal
            exit_info = str(match_row.get(exit_col, ''))
            
            # Check if exit exists
            if 'No Exit Yet' in exit_info or not exit_info or exit_info.lower() in ['nan', 'none', '']:
                continue
            
            # Extract exit date and price
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', exit_info)
            price_match = re.search(r'Price:\s*([\d.]+)', exit_info)
            
            if date_match and price_match:
                exit_date = date_match.group(1)
                try:
                    exit_price = float(price_match.group(1))
                    
                    # Update exit information
                    df.at[idx, 'Exit_Date'] = exit_date
                    df.at[idx, 'Exit_Price'] = exit_price
                    df.at[idx, 'Last_Updated'] = datetime.now().isoformat()
                    
                    # Update Raw_Data if it exists (use df.at to get current row data)
                    if 'Raw_Data' in df.columns and pd.notna(df.at[idx, 'Raw_Data']):
                        raw_data = df.at[idx, 'Raw_Data']
                        
                        # Parse Raw_Data if it's a string
                        if isinstance(raw_data, str):
                            try:
                                import json
                                raw_data = json.loads(raw_data)
                            except:
                                raw_data = {}
                        
                        if isinstance(raw_data, dict):
                            # Update "Exit Signal Date/Price[$]" column
                            exit_col = "Exit Signal Date/Price[$]"
                            raw_data[exit_col] = f"{exit_date} (Price: {exit_price:.4f})"
                            
                            # Update today price to exit price for closed trades
                            signal_price = df.at[idx, 'Signal_Price'] if 'Signal_Price' in df.columns else monitored_row.get('Signal_Price', 0)
                            signal_type = df.at[idx, 'Signal_Type'] if 'Signal_Type' in df.columns else monitored_row.get('Signal_Type', 'Long')
                            signal_date = df.at[idx, 'Signal_Date'] if 'Signal_Date' in df.columns else monitored_row.get('Signal_Date', '')
                            
                            # Calculate final mark to market
                            mtm_pct = calculate_mark_to_market(exit_price, signal_price, signal_type)
                            
                            # Calculate holding period (from signal date to exit date)
                            holding_days = calculate_holding_period(signal_date, exit_date)
                            
                            # Update "Current Mark to Market and Holding Period" column
                            mtm_col = "Current Mark to Market and Holding Period"
                            raw_data[mtm_col] = f"{mtm_pct}, {holding_days} days"
                            
                            # Update "Current Trading Date/Price[$], Current Price vs Signal" to exit info
                            price_change_str = calculate_price_change_percentage(exit_price, signal_price, signal_type)
                            current_price_col = "Current Trading Date/Price[$], Current Price vs Signal"
                            raw_data[current_price_col] = f"{exit_date} (Price: {exit_price:.4f}), {price_change_str}"
                            
                            # Update "Trading Days between Signal and Today Date" column (use exit date as current)
                            trading_days_col = "Trading Days between Signal and Today Date"
                            raw_data[trading_days_col] = f"{holding_days} days"
                            
                            # Save updated Raw_Data back
                            df.at[idx, 'Raw_Data'] = raw_data
                    
                    break
                except:
                    continue
    
    return df


def update_monitored_trades_with_outstanding(outstanding_df: pd.DataFrame) -> bool:
    """Update monitored trades with exit signals from outstanding signals"""
    df = load_monitored_trades()
    
    if df.empty:
        return True
    
    # Update prices first
    update_monitored_trades_prices()
    df = load_monitored_trades()  # Reload after price update
    
    # Check for exit signals
    df = check_exit_signals_in_outstanding(df, outstanding_df)
    
    return save_monitored_trades(df)

