"""
Parsers for advanced signal CSV files (outstanding, new signals, breadth, etc.)
"""

import pandas as pd
import re
from .base_parsers import parse_detailed_signal_csv


def _to_float(value, default=0.0):
    try:
        if isinstance(value, str):
            value = value.replace('%', '').replace(',', '').strip()
        return float(value)
    except Exception:
        return default


def _to_int(value, default=0):
    try:
        if isinstance(value, str):
            value = value.replace(',', '').strip()
        return int(float(value))
    except Exception:
        return default


def _parse_date_price_field(value):
    value_str = str(value)
    match = re.search(r'([0-9]{4}-[0-9]{2}-[0-9]{2})\s*\(Price:\s*([^)]+)\)', value_str)
    if match:
        date_part = match.group(1).strip()
        price_part = match.group(2).strip()
        try:
            price_value = float(price_part.replace(',', ''))
        except Exception:
            price_value = 0
        return date_part, price_value
    return "Unknown", 0


def parse_outstanding_signal(df):
    """Parse outstanding_signal.csv"""
    return parse_detailed_signal_csv(df)


def parse_new_signal(df):
    """Parse new_signal.csv"""
    return parse_detailed_signal_csv(df)


def parse_breadth(df):
    """Parse breadth.csv"""
    processed_data = []
    
    for _, row in df.iterrows():
        # Extract function name
        function = row.get('Function', 'Unknown')
        
        # Extract bullish asset percentage
        bullish_asset_str = str(row.get('Bullish Asset vs Total Asset (%)', '0%')).replace('%', '')
        try:
            bullish_asset_pct = float(bullish_asset_str)
        except:
            bullish_asset_pct = 0
        
        # Extract bullish signal percentage
        bullish_signal_str = str(row.get('Bullish Signal vs Total Signal (%)', '0%')).replace('%', '')
        try:
            bullish_signal_pct = float(bullish_signal_str)
        except:
            bullish_signal_pct = 0
        
        processed_data.append({
            'Function': function,
            'Bullish_Asset_Percentage': bullish_asset_pct,
            'Bullish_Signal_Percentage': bullish_signal_pct,
            'Raw_Data': row.to_dict()
        })
    
    return pd.DataFrame(processed_data)


def parse_target_signals(df, page_name="Unknown"):
    """Parse target signals CSV (target_signal.csv) - Different column structure"""
    processed_data = []

    for idx, row in df.iterrows():
        try:
            # Signal Price: ALWAYS from Symbol, Signal, Signal Date/Price[$] (Price: X)
            # Signal Open Price is for backend deduplication only - never used for display
            signal_price = 0

            # Target Signal CSV has different structure with combined fields
            symbol_info = str(row.get('Symbol, Signal, Signal Date/Price[$]', '')).strip()

            symbol = "Unknown"
            signal_type = "Unknown"
            signal_date = "Unknown"

            if symbol_info:
                parts = [part.strip() for part in symbol_info.split(',')]
                if parts:
                    symbol = parts[0]
                if len(parts) >= 2:
                    signal_type = parts[1].title()

                date_match = re.search(r'([0-9]{4}-[0-9]{2}-[0-9]{2})\s*\(Price:\s*([^)]+)\)', symbol_info)
                if date_match:
                    signal_date = date_match.group(1).strip()
                    try:
                        signal_price = float(date_match.group(2).strip())
                    except:
                        signal_price = 0

            # Get function and interval from separate columns
            function = str(row['Function']) if 'Function' in row.index else 'Unknown'
            interval = str(row['Interval']) if 'Interval' in row.index else 'Unknown'

            # If entry column exists, prefer its date/price for historical accuracy
            entry_info = row.get('Entry Signal Date/Price[$]', '')
            entry_match = re.search(r'([^(]+)\(Price:\s*([^)]+)\)', str(entry_info))
            if entry_match:
                signal_date = entry_match.group(1).strip()
                try:
                    signal_price = float(entry_match.group(2).strip())
                except:
                    pass  # Keep existing signal_price
            
            if not signal_type or signal_type == "Unknown":
                signal_type = "Long"
            
            # Parse current trading date and price
            current_date, current_price = _parse_date_price_field(row.get('Current Trading Date/Price[$]', ''))
            
            # Parse win rate and number of trades
            win_rate = 0
            num_trades = 0
            win_rate_info = None
            if 'Win Rate [%], History Tested, Number of Trades' in row.index:
                win_rate_info = row['Win Rate [%], History Tested, Number of Trades']
            elif 'Number of Trades/Historic Win Rate [%]' in row.index:
                win_rate_info = row['Number of Trades/Historic Win Rate [%]']
            
            if win_rate_info:
                info_str = str(win_rate_info)
                percent_match = re.search(r'([0-9.]+)\s*%', info_str)
                if percent_match:
                    try:
                        win_rate = float(percent_match.group(1))
                    except:
                        win_rate = 0
                
                parts = [p.strip() for p in info_str.split(',')]
                if parts:
                    # Fallback: check for pattern trades/win rate (e.g., "22/95.45%")
                    slash_match = re.search(r'([0-9]+)\s*/\s*([0-9.]+)%', info_str)
                    if slash_match:
                        try:
                            num_trades = int(slash_match.group(1))
                            win_rate = float(slash_match.group(2))
                        except:
                            pass
                    elif len(parts) >= 3:
                        # Last part should be number of trades
                        trades_candidate = parts[-1]
                        trades_match = re.search(r'([0-9]+)', trades_candidate)
                        if trades_match:
                            try:
                                num_trades = int(trades_match.group(1))
                            except:
                                num_trades = 0
                    elif not num_trades:
                        trades_match = re.search(r'([0-9]+)\s+trades', info_str, re.IGNORECASE)
                        if trades_match:
                            try:
                                num_trades = int(trades_match.group(1))
                            except:
                                num_trades = 0
            
            # Parse gain and holding period
            gain_info = row.get('% Gain, Holding Period (days)', '')
            
            # Import extract_days_from_formatted_string to handle new day formats
            from ..utils.helpers import extract_days_from_formatted_string
            
            gain_match = re.search(r'([0-9.]+)%,\s*([^,]+)', str(gain_info))
            
            if gain_match:
                try:
                    gain_pct = float(gain_match.group(1))
                    holding_period_str = gain_match.group(2).strip()
                    holding_days = extract_days_from_formatted_string(holding_period_str)
                except:
                    gain_pct, holding_days = 0, 0
            else:
                gain_pct, holding_days = 0, 0
            
            # Parse backtested returns
            returns_info = row.get('Backtested Returns(Win Trades) [%] (Max/Min/Avg)', '')
            returns_match = re.search(r'([0-9.]+)%/([0-9.]+)%/([0-9.]+)%', str(returns_info))
            
            if returns_match:
                try:
                    best_return = float(returns_match.group(1))
                    worst_return = float(returns_match.group(2))
                    avg_return = float(returns_match.group(3))
                except:
                    best_return, worst_return, avg_return = 0, 0, 0
            else:
                best_return, worst_return, avg_return = 0, 0, 0
            
            # Parse target information
            target_info = row.get('Target for which Price has achieved over 90 percent of gain %', '')
            target_price = 0
            target_type = "Unknown"
            
            if '(' in str(target_info) and ')' in str(target_info):
                # Extract price and type from format like "0.8118 (Historic Rise or Fall to Pivot)"
                target_match = re.search(r'([0-9.]+)\s*\(([^)]+)\)', str(target_info))
                if target_match:
                    try:
                        target_price = float(target_match.group(1))
                        target_type = target_match.group(2).strip()
                    except:
                        target_price, target_type = 0, "Unknown"
            
            # Parse next targets
            next_targets = row.get('Next Two Target % from Latest Trading Price', 'N/A')
            
            # Parse remaining potential exit prices
            exit_prices = row.get('Remaining Potential Exit Prices [$]', 'N/A')
            
            # Performance metrics
            strategy_cagr = _to_float(row.get('Backtested Strategy CAGR [%]', 0))
            buy_hold_cagr = _to_float(row.get('CAGR of Buy and Hold [%]', 0))
            strategy_sharpe = _to_float(row.get('Backtested Strategy Sharpe Ratio', 0))
            buy_hold_sharpe = _to_float(row.get('Sharpe Ratio of Buy and Hold', 0))
            
            processed_data.append({
                'Symbol': symbol,
                'Function': function,
                'Signal_Type': signal_type,
                'Signal_Date': signal_date,
                'Signal_Price': signal_price,
                'Current_Date': current_date,
                'Current_Price': current_price,
                'Gain_Percentage': gain_pct,
                'Holding_Days': holding_days,
                'Win_Rate': win_rate,
                'Num_Trades': num_trades,
                'Best_Return': best_return,
                'Worst_Return': worst_return,
                'Avg_Return': avg_return,
                'Target_Price': target_price,
                'Target_Type': target_type,
                'Next_Targets': next_targets,
                'Exit_Prices': exit_prices,
                'Interval': interval,
                'Strategy_CAGR': strategy_cagr,
                'Buy_Hold_CAGR': buy_hold_cagr,
                'Strategy_Sharpe': strategy_sharpe,
                'Buy_Hold_Sharpe': buy_hold_sharpe,
                'Raw_Data': row.to_dict()
            })
        except Exception as e:
            # Log error but still add the row with default values to ensure no data is lost
            import sys
            print(f"Warning: Error parsing target signal row {idx}: {e}", file=sys.stderr)
            # Try to extract symbol from the row
            symbol_info = str(row.get('Symbol, Signal, Signal Date/Price[$]', '')).strip()
            symbol = "Unknown"
            if symbol_info and ',' in symbol_info:
                symbol = symbol_info.split(',')[0].strip()
            processed_data.append({
                'Symbol': symbol,
                'Function': row.get('Function', 'Unknown'),
                'Signal_Type': 'Long',
                'Signal_Date': 'Unknown',
                'Signal_Price': 0,
                'Current_Date': 'Unknown',
                'Current_Price': 0,
                'Gain_Percentage': 0,
                'Holding_Days': 0,
                'Win_Rate': 0,
                'Num_Trades': 0,
                'Best_Return': 0,
                'Worst_Return': 0,
                'Avg_Return': 0,
                'Target_Price': 0,
                'Target_Type': 'Unknown',
                'Next_Targets': 'N/A',
                'Exit_Prices': 'N/A',
                'Interval': row.get('Interval', 'Unknown'),
                'Strategy_CAGR': 0,
                'Buy_Hold_CAGR': 0,
                'Strategy_Sharpe': 0,
                'Buy_Hold_Sharpe': 0,
            'Raw_Data': row.to_dict()
        })
    
    return pd.DataFrame(processed_data)


def parse_f_stack_analyzer(df, page_name="F-Stack"):
    """Parse F-Stack Analyzer CSV files."""
    processed_data = []
    
    for _, row in df.iterrows():
        symbol = str(row.get('Symbol', 'Unknown')).strip()
        signal = str(row.get('Signal', 'Unknown')).title()
        
        signal_date, signal_price = _parse_date_price_field(row.get('Signal Date/Price($)', ''))
        latest_date, latest_price = _parse_date_price_field(row.get('Latest Trading Date/Price($)', ''))
        
        current_extension = _to_float(row.get('Current Extension Level($)', 0))
        current_band_range = str(row.get('Current Band Price Range($)', 'N/A'))
        current_band_width = _to_float(row.get('Width of Current Band(%)', 0))
        band_composition = str(row.get('Band Composition (Extension Level(%) of Low($)-High($) & ..)', 'N/A'))
        
        trading_days = _to_int(row.get('Trading Days between signal date and Latest Trading date', 0))
        price_vs_signal = str(row.get('Price on Latest Trading day vs signal date', 'N/A'))
        
        next_band_level = _to_float(row.get('Next Band Price Level($)', 0))
        next_band_range = str(row.get('Next Band Price Range($)', 'N/A'))
        next_fib_ret = str(row.get('Next Fib Ret [%] (Price Level [$]/Retracement Level [%]/Upmove [$])', 'N/A'))
        next_fib_vs_price = str(row.get('Next Fib Ret [%] Price Level vs Price on Latest Trading day', 'N/A'))
        next_band_vs_price = str(row.get('Next Band Price Level vs Price on Latest Trading day', 'N/A'))
        
        processed_data.append({
            'Symbol': symbol,
            'Signal': signal,
            'Signal_Date': signal_date,
            'Signal_Price': signal_price,
            'Latest_Date': latest_date,
            'Latest_Price': latest_price,
            'Interval': str(row.get('Interval', 'Unknown')),
            'Current_Extension_Level': current_extension,
            'Current_Band_Range': current_band_range,
            'Current_Band_Width': current_band_width,
            'Band_Composition': band_composition,
            'Trading_Days': trading_days,
            'Price_vs_Signal': price_vs_signal,
            'Next_Band_Level': next_band_level,
            'Next_Band_Range': next_band_range,
            'Next_Fib_Ret': next_fib_ret,
            'Next_Fib_vs_Price': next_fib_vs_price,
            'Next_Band_vs_Price': next_band_vs_price,
            'Raw_Data': row.to_dict()
        })
    
    return pd.DataFrame(processed_data)

