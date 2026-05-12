"""
Data processor for loading and filtering CSV data based on user parameters.
CSV-Only Structure: Uses consolidated CSV files (entry.csv, exit.csv, portfolio_target_achieved.csv, breadth.csv)
instead of hierarchical folder structure.
"""

import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Set
import logging

from .config import (
    CHATBOT_DATA_DIR,
    CHATBOT_ENTRY_DIR,
    CHATBOT_EXIT_DIR,
    CHATBOT_TARGET_DIR,
    CHATBOT_BREADTH_DIR,
    STOCK_DATA_DIR,
    DATE_FORMAT,
    CSV_ENCODING,
    MAX_ROWS_TO_INCLUDE,
    DEDUP_COLUMNS,
    BREADTH_DEDUP_COLUMNS,
    MAX_INPUT_TOKENS_PER_CALL,
    ESTIMATED_CHARS_PER_TOKEN,
)
from .outstanding_paths import resolve_outstanding_signal_path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataProcessor:
    """Handles loading and processing of CSV data for chatbot queries using consolidated CSV files."""

    def __init__(self, use_new_structure: bool = True):
        """
        Initialize DataProcessor.

        Args:
            use_new_structure: If True, uses consolidated CSV files in chatbot/data/ (entry.csv, exit.csv, portfolio_target_achieved.csv, breadth.csv).
                             If False, uses legacy trade_store/stock_data structure.
        """
        self.use_new_structure = use_new_structure
        self.chatbot_data_dir = Path(CHATBOT_DATA_DIR)
        self.stock_data_dir = Path(STOCK_DATA_DIR)

        # Cache for consolidated CSV files to avoid repeated loading
        self._csv_cache = {}
        self._cache_timestamp = {}

        # Consolidated CSV file paths
        self.entry_csv = self.chatbot_data_dir / "entry.csv"
        self.exit_csv = self.chatbot_data_dir / "exit.csv"
        self.portfolio_csv = self.chatbot_data_dir / "portfolio_target_achieved.csv"
        self.breadth_csv = self.chatbot_data_dir / "breadth.csv"

    def _load_csv_cached(self, csv_path: Path) -> Optional[pd.DataFrame]:
        """
        Load CSV file with caching to improve performance.
        Automatically reloads if file has been modified since last cache.

        Args:
            csv_path: Path to CSV file

        Returns:
            DataFrame or None if file doesn't exist or can't be loaded
        """
        if not csv_path.exists():
            return None

        # Check if file has been modified since last cache
        current_mtime = csv_path.stat().st_mtime
        cache_key = str(csv_path)

        if (cache_key in self._csv_cache and
            cache_key in self._cache_timestamp and
            self._cache_timestamp[cache_key] >= current_mtime):
            # Use cached version
            return self._csv_cache[cache_key]

        # Load and cache the file
        try:
            df = pd.read_csv(csv_path, encoding=CSV_ENCODING)
            self._csv_cache[cache_key] = df
            self._cache_timestamp[cache_key] = current_mtime
            logger.debug(f"Loaded and cached {csv_path.name}: {len(df)} rows")
            return df
        except Exception as e:
            logger.error(f"Error loading CSV {csv_path}: {e}")
            return None

    def _extract_symbol_from_compound_column(self, compound_value: str) -> Optional[str]:
        """
        Extract symbol from compound column like "AAPL, Long, 2026-01-16 (Price: 193.89)"

        Args:
            compound_value: Compound column value

        Returns:
            Symbol string or None if parsing fails
        """
        if not compound_value or pd.isna(compound_value):
            return None

        try:
            # Split by comma and take first part
            parts = str(compound_value).split(',')
            if parts:
                return parts[0].strip()
        except Exception as e:
            logger.warning(f"Error parsing symbol from compound column '{compound_value}': {e}")

        return None

    def _filter_dataframe_by_ticker(self, df: pd.DataFrame, ticker: str) -> pd.DataFrame:
        """
        Filter DataFrame to include only rows for the specified ticker.

        Args:
            df: DataFrame to filter
            ticker: Ticker symbol to filter by

        Returns:
            Filtered DataFrame
        """
        if df is None or df.empty:
            return pd.DataFrame()

        # Try Symbol column first
        if 'Symbol' in df.columns:
            return df[df['Symbol'] == ticker]
        # Fall back to compound column
        elif "Symbol, Signal, Signal Date/Price[$]" in df.columns:
            return df[df["Symbol, Signal, Signal Date/Price[$]"].apply(
                lambda x: self._extract_symbol_from_compound_column(x) == ticker
            )]
        else:
            # No way to filter by ticker
            logger.warning(f"No Symbol column found in DataFrame, cannot filter by ticker {ticker}")
            return pd.DataFrame()

    def _filter_dataframe_by_functions(self, df: pd.DataFrame, functions: List[str]) -> pd.DataFrame:
        """
        Filter DataFrame to include only rows for the specified functions.

        Args:
            df: DataFrame to filter
            functions: List of function names to filter by

        Returns:
            Filtered DataFrame
        """
        if df is None or df.empty or not functions:
            return df

        if 'Function' in df.columns:
            return df[df['Function'].isin(functions)]
        else:
            logger.warning("No Function column found in DataFrame, cannot filter by functions")
            return df

    def _filter_dataframe_by_date_range(self, df: pd.DataFrame, from_date: Optional[str], to_date: Optional[str]) -> pd.DataFrame:
        """
        Filter DataFrame to include only rows within the specified date range.

        Args:
            df: DataFrame to filter
            from_date: Start date in YYYY-MM-DD format (optional)
            to_date: End date in YYYY-MM-DD format (optional)

        Returns:
            Filtered DataFrame
        """
        if df is None or df.empty or (not from_date and not to_date):
            return df

        # Try different date columns
        date_columns = ['Date']

        for date_col in date_columns:
            if date_col in df.columns:
                # Convert to datetime if not already
                if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
                    df = df.copy()
                    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')

                # Apply date filters
                filtered_df = df.copy()

                if from_date:
                    from_dt = pd.to_datetime(from_date)
                    filtered_df = filtered_df[filtered_df[date_col] >= from_dt]

                if to_date:
                    to_dt = pd.to_datetime(to_date)
                    filtered_df = filtered_df[filtered_df[date_col] <= to_dt]

                return filtered_df

        # No date column found
        logger.warning("No date column found in DataFrame, cannot filter by date range")
        return df

    def get_available_tickers(self) -> List[str]:
        """
        Get list of available ticker/asset symbols from consolidated CSV files.

        Returns:
            List of ticker symbols
        """
        try:
            if self.use_new_structure:
                # Get unique symbols from consolidated CSV files
                tickers = set()

                # Load entry.csv and extract symbols
                entry_df = self._load_csv_cached(self.entry_csv)
                if entry_df is not None and not entry_df.empty:
                    if 'Symbol' in entry_df.columns:
                        symbols = entry_df['Symbol'].dropna().unique()
                        tickers.update(symbols)
                    # Also check compound column if Symbol column not available
                    elif "Symbol, Signal, Signal Date/Price[$]" in entry_df.columns:
                        compound_symbols = entry_df["Symbol, Signal, Signal Date/Price[$]"].dropna().apply(self._extract_symbol_from_compound_column)
                        valid_symbols = compound_symbols.dropna().unique()
                        tickers.update(valid_symbols)

                # Outstanding-signal report (trade_store/US) — primary open-position source for the chatbot
                out_path = resolve_outstanding_signal_path()
                if out_path is not None and out_path.is_file():
                    try:
                        odf = pd.read_csv(out_path, encoding=CSV_ENCODING)
                        col = "Symbol, Signal, Signal Date/Price[$]"
                        if odf is not None and not odf.empty and col in odf.columns:
                            compound_symbols = (
                                odf[col].dropna().apply(self._extract_symbol_from_compound_column)
                            )
                            tickers.update(compound_symbols.dropna().unique())
                    except Exception as exc:
                        logger.warning("Could not load tickers from outstanding report %s: %s", out_path, exc)

                # Load exit.csv and extract symbols
                exit_df = self._load_csv_cached(self.exit_csv)
                if exit_df is not None and not exit_df.empty:
                    if 'Symbol' in exit_df.columns:
                        symbols = exit_df['Symbol'].dropna().unique()
                        tickers.update(symbols)
                    # Also check compound column if Symbol column not available
                    elif "Symbol, Signal, Signal Date/Price[$]" in exit_df.columns:
                        compound_symbols = exit_df["Symbol, Signal, Signal Date/Price[$]"].dropna().apply(self._extract_symbol_from_compound_column)
                        valid_symbols = compound_symbols.dropna().unique()
                        tickers.update(valid_symbols)

                # Load portfolio_target_achieved.csv and extract symbols
                portfolio_df = self._load_csv_cached(self.portfolio_csv)
                if portfolio_df is not None and not portfolio_df.empty:
                    if 'Symbol' in portfolio_df.columns:
                        symbols = portfolio_df['Symbol'].dropna().unique()
                        tickers.update(symbols)
                    # Also check compound column if Symbol column not available
                    elif "Symbol, Signal, Signal Date/Price[$]" in portfolio_df.columns:
                        compound_symbols = portfolio_df["Symbol, Signal, Signal Date/Price[$]"].dropna().apply(self._extract_symbol_from_compound_column)
                        valid_symbols = compound_symbols.dropna().unique()
                        tickers.update(valid_symbols)

                return sorted(list(tickers))
            else:
                # Legacy: Get CSV files from trade_store/stock_data/
                csv_files = list(self.stock_data_dir.glob("*.csv"))
                tickers = [f.stem for f in csv_files if f.stem != "today_date"]
                return sorted(tickers)
        except Exception as e:
            logger.error(f"Error getting available tickers: {e}")
            return []
    
    def get_available_functions(self, ticker: Optional[str] = None) -> List[str]:
        """
        Get list of available function names from consolidated CSV files.

        Args:
            ticker: Optional ticker to get functions for. If None, gets all unique functions.

        Returns:
            List of function names
        """
        try:
            if not self.use_new_structure:
                return []

            functions = set()

            # Helper function to extract functions from a dataframe
            def extract_functions_from_df(df: pd.DataFrame, ticker_filter: Optional[str] = None) -> Set[str]:
                if df is None or df.empty:
                    return set()

                funcs = set()

                # Filter by ticker if specified
                if ticker_filter:
                    if 'Symbol' in df.columns:
                        filtered_df = df[df['Symbol'] == ticker_filter]
                    elif "Symbol, Signal, Signal Date/Price[$]" in df.columns:
                        # Filter by compound column
                        filtered_df = df[df["Symbol, Signal, Signal Date/Price[$]"].apply(
                            lambda x: self._extract_symbol_from_compound_column(x) == ticker_filter
                        )]
                    else:
                        return set()
                else:
                    filtered_df = df

                # Extract unique functions
                if 'Function' in filtered_df.columns:
                    unique_funcs = filtered_df['Function'].dropna().unique()
                    funcs.update(unique_funcs)

                return funcs

            # Get functions from all relevant CSV files
            csv_files = [self.entry_csv, self.exit_csv, self.portfolio_csv]

            for csv_file in csv_files:
                df = self._load_csv_cached(csv_file)
                funcs_from_file = extract_functions_from_df(df, ticker)
                functions.update(funcs_from_file)

            return sorted(list(functions))
        except Exception as e:
            logger.error(f"Error getting available functions: {e}")
            return []
    
    def get_available_dates_for_ticker(
        self,
        ticker: str,
        function: Optional[str] = None
    ) -> List[str]:
        """
        Get list of available dates for a specific ticker and function from consolidated CSV files.

        Args:
            ticker: Ticker/asset symbol
            function: Function name (optional). If None, gets dates across all functions.

        Returns:
            List of date strings in YYYY-MM-DD format
        """
        try:
            dates = set()

            # Helper function to extract dates from a dataframe
            def extract_dates_from_df(df: pd.DataFrame, ticker_filter: str, function_filter: Optional[str] = None) -> Set[str]:
                if df is None or df.empty:
                    return set()

                extracted_dates = set()

                # Filter by ticker
                if 'Symbol' in df.columns:
                    ticker_filtered_df = df[df['Symbol'] == ticker_filter]
                elif "Symbol, Signal, Signal Date/Price[$]" in df.columns:
                    # Filter by compound column
                    ticker_filtered_df = df[df["Symbol, Signal, Signal Date/Price[$]"].apply(
                        lambda x: self._extract_symbol_from_compound_column(x) == ticker_filter
                    )]
                else:
                    return set()

                # Filter by function if specified
                if function_filter and 'Function' in ticker_filtered_df.columns:
                    filtered_df = ticker_filtered_df[ticker_filtered_df['Function'] == function_filter]
                else:
                    filtered_df = ticker_filtered_df

                # Extract dates from "Date" column
                if 'Date' in filtered_df.columns:
                    date_values = filtered_df['Date'].dropna().unique()
                    for date_val in date_values:
                        try:
                            # Ensure it's a valid date string
                            if isinstance(date_val, str):
                                datetime.strptime(str(date_val), DATE_FORMAT)
                                extracted_dates.add(str(date_val))
                            elif hasattr(date_val, 'strftime'):  # datetime object
                                extracted_dates.add(date_val.strftime(DATE_FORMAT))
                        except (ValueError, AttributeError):
                            continue

                return extracted_dates

            # Get dates from all relevant CSV files
            csv_files = [self.entry_csv, self.exit_csv, self.portfolio_csv]

            for csv_file in csv_files:
                df = self._load_csv_cached(csv_file)
                dates_from_file = extract_dates_from_df(df, ticker, function)
                dates.update(dates_from_file)

            return sorted(list(dates))
        except Exception as e:
            logger.error(f"Error getting available dates for {ticker}: {e}")
            return []
    
    def get_date_range(self, from_date: str, to_date: str) -> List[str]:
        """
        Generate list of dates between from_date and to_date.
        
        Args:
            from_date: Start date in YYYY-MM-DD format
            to_date: End date in YYYY-MM-DD format
            
        Returns:
            List of date strings
        """
        try:
            start = datetime.strptime(from_date, DATE_FORMAT)
            end = datetime.strptime(to_date, DATE_FORMAT)
            
            dates = []
            current = start
            while current <= end:
                dates.append(current.strftime(DATE_FORMAT))
                current += timedelta(days=1)
            
            return dates
        except Exception as e:
            logger.error(f"Error generating date range: {e}")
            return []
    
    def load_stock_data_new_structure(
        self,
        tickers: List[str],
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        dedup_columns: Optional[List[str]] = None,
        functions: Optional[List[str]] = None,
        signal_types: Optional[List[str]] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Load stock data from consolidated CSV files: entry.csv, exit.csv, portfolio_target_achieved.csv
        Filters data based on tickers, date range, functions, and signal types.

        Args:
            tickers: List of ticker/asset symbols
            from_date: Start date in YYYY-MM-DD format
            to_date: End date in YYYY-MM-DD format
            dedup_columns: Columns to use for deduplication (placeholder)
            functions: List of function names to filter (None = all functions)
            signal_types: List of signal types - controls which CSV files to load from:
                         - ['entry'] → load from entry.csv only
                         - ['exit'] → load from exit.csv only
                         - ['portfolio_target_achieved'] → load from portfolio_target_achieved.csv only
                         - None or [] → load from all CSV files (fallback)

        Returns:
            Dictionary mapping ticker to combined DataFrame
        """
        if dedup_columns is None:
            # Use appropriate dedup columns - breadth uses different columns than regular signals
            dedup_columns = DEDUP_COLUMNS

        result = {}

        for ticker in tickers:
            try:
                logger.info(f"Loading data for ticker: {ticker}")

                # Determine which CSV files to load from based on signal_types
                csv_files_to_load = []
                if signal_types:
                    if 'entry' in signal_types or 'entry_exit' in signal_types:
                        csv_files_to_load.append(('entry', self.entry_csv))
                    if 'exit' in signal_types or 'entry_exit' in signal_types:
                        csv_files_to_load.append(('exit', self.exit_csv))
                    if 'portfolio_target_achieved' in signal_types:
                        csv_files_to_load.append(('portfolio_target_achieved', self.portfolio_csv))
                    logger.info(f"Loading based on signal_types {signal_types}: {[name for name, _ in csv_files_to_load]}")
                else:
                    # No signal_types specified - load from all CSV files (fallback)
                    csv_files_to_load = [
                        ('entry', self.entry_csv),
                        ('exit', self.exit_csv),
                        ('portfolio_target_achieved', self.portfolio_csv)
                    ]
                    logger.info("No signal_types specified - loading from entry, exit, and portfolio_target_achieved CSV files")

                all_dfs = []

                # Load and filter data from each CSV file
                for data_type, csv_file in csv_files_to_load:
                    df = self._load_csv_cached(csv_file)
                    if df is None or df.empty:
                        logger.debug(f"CSV file {csv_file.name} not found or empty")
                        continue

                    # Filter by ticker
                    filtered_df = self._filter_dataframe_by_ticker(df, ticker)
                    if filtered_df.empty:
                        logger.debug(f"No data found for ticker {ticker} in {csv_file.name}")
                        continue

                    # Filter by functions if specified
                    if functions:
                        filtered_df = self._filter_dataframe_by_functions(filtered_df, functions)
                        if filtered_df.empty:
                            logger.debug(f"No data found for functions {functions} in {csv_file.name}")
                            continue

                    # Filter by date range
                    filtered_df = self._filter_dataframe_by_date_range(filtered_df, from_date, to_date)
                    if filtered_df.empty:
                        logger.debug(f"No data found in date range {from_date} to {to_date} in {csv_file.name}")
                        continue

                    # Add data type column
                    filtered_df = filtered_df.copy()  # Avoid SettingWithCopyWarning
                    filtered_df['DataType'] = data_type

                    # Ensure Symbol column exists (extract from compound column if needed)
                    if 'Symbol' not in filtered_df.columns:
                        if "Symbol, Signal, Signal Date/Price[$]" in filtered_df.columns:
                            filtered_df['Symbol'] = filtered_df["Symbol, Signal, Signal Date/Price[$]"].apply(
                                self._extract_symbol_from_compound_column
                            )
                        else:
                            filtered_df['Symbol'] = ticker

                    # Ensure all string columns are properly encoded
                    for col in filtered_df.columns:
                        if filtered_df[col].dtype == 'object':
                            filtered_df[col] = filtered_df[col].astype(str).replace('nan', pd.NA)

                    all_dfs.append(filtered_df)
                    logger.debug(f"Loaded {len(filtered_df)} rows for {ticker} from {csv_file.name}")

                if not all_dfs:
                    logger.warning(f"No valid data loaded for ticker: {ticker}")
                    continue

                # Combine all dataframes
                combined_df = pd.concat(all_dfs, ignore_index=True)

                # Convert Date column to datetime if present
                if 'Date' in combined_df.columns:
                    combined_df['Date'] = pd.to_datetime(combined_df['Date'], errors='coerce')

                # Remove duplicates based on specified columns
                available_dedup_cols = [col for col in dedup_columns if col in combined_df.columns]

                if available_dedup_cols:
                    original_count = len(combined_df)
                    combined_df = combined_df.drop_duplicates(subset=available_dedup_cols, keep='first')
                    removed_count = original_count - len(combined_df)

                    if removed_count > 0:
                        logger.info(f"Removed {removed_count} duplicate rows for {ticker} based on columns: {available_dedup_cols}")
                else:
                    logger.warning(f"No deduplication columns found for {ticker}. Available columns: {combined_df.columns.tolist()}")

                # Sort by date if Date column exists (LATEST FIRST)
                if 'Date' in combined_df.columns:
                    combined_df = combined_df.sort_values('Date', ascending=False)

                # Limit rows if too many - KEEP LATEST DATA
                if len(combined_df) > MAX_ROWS_TO_INCLUDE:
                    logger.info(f"Limiting {ticker} data from {len(combined_df)} to {MAX_ROWS_TO_INCLUDE} rows (keeping latest)")
                    combined_df = combined_df.head(MAX_ROWS_TO_INCLUDE)

                result[ticker] = combined_df
                logger.info(f"Successfully loaded {len(combined_df)} rows for {ticker}")

            except Exception as e:
                logger.error(f"Error loading data for {ticker}: {e}")
                import traceback
                traceback.print_exc()
                continue

        return result
    
    def load_stock_data_legacy(
        self,
        tickers: List[str],
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Load stock data from legacy structure: trade_store/stock_data/{ticker}.csv
        
        Args:
            tickers: List of ticker symbols
            from_date: Start date in YYYY-MM-DD format
            to_date: End date in YYYY-MM-DD format
            
        Returns:
            Dictionary mapping ticker to filtered DataFrame
        """
        result = {}
        
        for ticker in tickers:
            try:
                file_path = self.stock_data_dir / f"{ticker}.csv"
                
                if not file_path.exists():
                    logger.warning(f"Data file not found for ticker: {ticker}")
                    continue
                
                df = pd.read_csv(file_path, encoding=CSV_ENCODING)
                
                # Ensure Date column exists
                if 'Date' not in df.columns:
                    logger.warning(f"No 'Date' column in {ticker} data")
                    continue
                
                # Convert Date column to datetime
                df['Date'] = pd.to_datetime(df['Date'])
                
                # Filter by date range if provided
                if from_date:
                    from_dt = pd.to_datetime(from_date)
                    df = df[df['Date'] >= from_dt]
                
                if to_date:
                    to_dt = pd.to_datetime(to_date)
                    df = df[df['Date'] <= to_dt]
                
                # Sort by date
                df = df.sort_values('Date')
                
                # Limit rows if too many
                if len(df) > MAX_ROWS_TO_INCLUDE:
                    logger.info(f"Limiting {ticker} data from {len(df)} to {MAX_ROWS_TO_INCLUDE} rows")
                    step = len(df) // MAX_ROWS_TO_INCLUDE
                    df = df.iloc[::step][:MAX_ROWS_TO_INCLUDE]
                
                result[ticker] = df
                logger.info(f"Loaded {len(df)} rows for {ticker}")
                
            except Exception as e:
                logger.error(f"Error loading data for {ticker}: {e}")
                continue
        
        return result
    
    def load_stock_data(
        self,
        tickers: List[str],
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        dedup_columns: Optional[List[str]] = None,
        functions: Optional[List[str]] = None,
        signal_types: Optional[List[str]] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Load stock data for specified tickers, functions, and date range.
        Loads from signal and/or portfolio_target_achieved folders based on signal_types.
        Uses new structure if available, falls back to legacy.
        
        Args:
            tickers: List of ticker/asset symbols
            from_date: Start date in YYYY-MM-DD format
            to_date: End date in YYYY-MM-DD format
            dedup_columns: Columns to use for deduplication
            functions: List of function names to filter (None = all functions)
            signal_types: List of signal types - controls which folders to load from:
                         - ['entry_exit'] → load from entry/exit folders
                        - ['portfolio_target_achieved'] → load from portfolio_target_achieved/ folder only
                         - ['entry_exit', 'portfolio_target_achieved'] → load from both
            
        Returns:
            Dictionary mapping ticker to DataFrame (includes DataType column: 'signal' or 'portfolio_target_achieved')
        """
        if self.use_new_structure:
            return self.load_stock_data_new_structure(
                tickers, from_date, to_date, dedup_columns, functions, signal_types
            )
        else:
            return self.load_stock_data_legacy(tickers, from_date, to_date)
    
    def load_breadth_data(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> Optional[pd.DataFrame]:
        """
        Load breadth report data for the specified date range from breadth.csv.
        Breadth data is market-wide (not asset-specific).

        Args:
            from_date: Start date in YYYY-MM-DD format
            to_date: End date in YYYY-MM-DD format

        Returns:
            Filtered DataFrame with breadth data in the date range, or None if no data found
        """
        # Load the breadth CSV file
        df = self._load_csv_cached(self.breadth_csv)
        if df is None or df.empty:
            logger.warning(f"Breadth CSV file not found or empty: {self.breadth_csv}")
            return None

        # Filter by date range using the Date column
        filtered_df = self._filter_dataframe_by_date_range(df, from_date, to_date)

        if filtered_df.empty:
            logger.info(f"No breadth reports found in date range {from_date} to {to_date}")
            return None

        # Ensure DataType column is set
        filtered_df = filtered_df.copy()
        filtered_df['DataType'] = 'breadth'

        # Convert Date column to datetime if present
        if 'Date' in filtered_df.columns:
            filtered_df['Date'] = pd.to_datetime(filtered_df['Date'], errors='coerce')

        # Sort by date (oldest first to show chronological progression)
        if 'Date' in filtered_df.columns:
            filtered_df = filtered_df.sort_values('Date', ascending=True)

        # Limit rows if too many - but keep all dates in range
        if len(filtered_df) > MAX_ROWS_TO_INCLUDE:
            logger.info(f"Breadth data has {len(filtered_df)} rows (limit: {MAX_ROWS_TO_INCLUDE}), but keeping all dates in range")
            # Still apply limit but try to keep representative data across all dates
            if 'Date' in filtered_df.columns:
                # Group by date and sample if needed
                dates = filtered_df['Date'].unique()
                rows_per_date = MAX_ROWS_TO_INCLUDE // len(dates) if len(dates) > 0 else MAX_ROWS_TO_INCLUDE
                sampled_dfs = []
                for date in dates:
                    date_df = filtered_df[filtered_df['Date'] == date]
                    if len(date_df) > rows_per_date:
                        # Sample rows for this date
                        sampled_df = date_df.sample(n=rows_per_date, random_state=42)
                        sampled_dfs.append(sampled_df)
                    else:
                        sampled_dfs.append(date_df)
                filtered_df = pd.concat(sampled_dfs, ignore_index=True)
            else:
                # No date column, just take first MAX_ROWS_TO_INCLUDE
                filtered_df = filtered_df.head(MAX_ROWS_TO_INCLUDE)

        logger.info(f"Loaded breadth data: {len(filtered_df)} rows from date range {from_date} to {to_date}")
        if 'Date' in filtered_df.columns and not filtered_df['Date'].empty:
            logger.info(f"Date range in results: {filtered_df['Date'].min()} to {filtered_df['Date'].max()}")

        # Apply breadth-specific deduplication
        if len(filtered_df) > 0:
            available_dedup_cols = [col for col in BREADTH_DEDUP_COLUMNS if col in filtered_df.columns]
            if available_dedup_cols:
                original_count = len(filtered_df)
                filtered_df = filtered_df.drop_duplicates(subset=available_dedup_cols, keep='first')
                removed_count = original_count - len(filtered_df)
                if removed_count > 0:
                    logger.info(f"Removed {removed_count} duplicate breadth rows based on: {', '.join(available_dedup_cols)}")

        return filtered_df
    
    def estimate_token_count(self, text: str) -> int:
        """
        Estimate token count from text.
        
        Args:
            text: Text to estimate tokens for
            
        Returns:
            Estimated token count
        """
        return len(text) // ESTIMATED_CHARS_PER_TOKEN
    
    def format_data_for_prompt(
        self,
        stock_data: Dict[str, pd.DataFrame],
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Format stock data as JSON for inclusion in GPT prompt.
        Automatically limits data to fit within token constraints.
        
        Args:
            stock_data: Dictionary mapping ticker to DataFrame
            max_tokens: Maximum tokens allowed (default from config)
            
        Returns:
            Formatted JSON string for prompt (limited to max_tokens)
        """
        if not stock_data:
            return ""
        
        if max_tokens is None:
            max_tokens = MAX_INPUT_TOKENS_PER_CALL
        
        import json
        
        formatted_parts = ["=== TRADING DATA (JSON Format) ===\n"]
        current_tokens = 0
        tickers_included = []
        
        # NO TOKEN LIMITS - Include ALL tickers
        # Smart batch processing will handle splitting across multiple API calls
        for ticker, df in stock_data.items():
            if df.empty:
                continue
            
            # Convert DataFrame to list of dictionaries (each row as key-value pairs)
            records = df.to_dict('records')
            
            # Create JSON structure for this ticker
            ticker_data = {
                "asset": ticker,
                "record_count": len(records),
                "data": records
            }
            
            # Convert to JSON string (pretty printed for readability)
            ticker_json = json.dumps(ticker_data, indent=2, default=str)
            
            ticker_token_estimate = self.estimate_token_count(ticker_json)
            
            # Add ALL ticker data - no skipping
            formatted_parts.append(f"\n{ticker_json}")
            current_tokens += ticker_token_estimate
            tickers_included.append(ticker)
        
        result = "\n".join(formatted_parts)
        logger.info(f"Formatted ALL data as JSON: ~{current_tokens} tokens, {len(tickers_included)} assets included (NO LIMITS)")
        
        return result
    
    def validate_date_format(self, date_str: str) -> bool:
        """
        Validate date string format.
        
        Args:
            date_str: Date string to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            datetime.strptime(date_str, DATE_FORMAT)
            return True
        except ValueError:
            return False
    
    def get_data_summary(
        self,
        tickers: List[str],
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        dedup_columns: Optional[List[str]] = None,
        functions: Optional[List[str]] = None
    ) -> Tuple[Dict[str, pd.DataFrame], str]:
        """
        Complete data loading and formatting pipeline.
        Loads from BOTH signal and portfolio_target_achieved folders.
        
        Args:
            tickers: List of ticker/asset symbols
            from_date: Start date
            to_date: End date
            dedup_columns: Columns for deduplication
            functions: List of function names to filter
            
        Returns:
            Tuple of (stock_data_dict, formatted_text)
        """
        # Load stock data (from both signal and portfolio_target_achieved)
        stock_data = self.load_stock_data(
            tickers, from_date, to_date, dedup_columns, functions
        )
        
        # Format for prompt
        formatted_text = self.format_data_for_prompt(stock_data)
        
        return stock_data, formatted_text
    
    def load_claude_report(self) -> Optional[str]:
        """
        Load Claude comprehensive analysis report from claude_report.txt.
        
        Returns:
            Report text as string, or None if file doesn't exist or can't be loaded
        """
        claude_report_path = self.chatbot_data_dir / "claude_report.txt"
        
        if not claude_report_path.exists():
            logger.warning(f"Claude report file not found: {claude_report_path}")
            return None
        
        try:
            with open(claude_report_path, 'r', encoding='utf-8') as f:
                report_text = f.read()
            
            logger.info(f"Loaded Claude report: {len(report_text)} characters")
            return report_text
        except Exception as e:
            logger.error(f"Error loading Claude report {claude_report_path}: {e}")
            return None
