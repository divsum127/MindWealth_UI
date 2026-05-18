"""
Smart data fetcher that retrieves only the required columns from CSV files.
Fetches data based on asset name, function, date, and selected columns.
"""

import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional, Union
import logging
import re
from datetime import datetime

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import (
    CHATBOT_ENTRY_DIR,
    CHATBOT_EXIT_DIR,
    CHATBOT_TARGET_DIR,
    CHATBOT_BREADTH_DIR,
    CHATBOT_ENTRY_CSV,
    CHATBOT_EXIT_CSV,
    CHATBOT_TARGET_CSV,
    CHATBOT_BREADTH_CSV,
    CSV_ENCODING,
    DATE_FORMAT,
)

try:
    from .outstanding_paths import (
        resolve_all_signal_path,
        resolve_outstanding_signal_path,
        trade_store_us_dir,
    )
    from .breadth_context import BREADTH_SBI_COLUMNS, BREADTH_NUMERIC_COLUMNS
    from .signal_confirm import INTERVAL_CONFIRMATION_COL, is_confirmed_signal
except ImportError:  # pragma: no cover — script-style import when ``chatbot`` is not a package
    from outstanding_paths import (  # type: ignore
        resolve_all_signal_path,
        resolve_outstanding_signal_path,
        trade_store_us_dir,
    )
    from breadth_context import BREADTH_SBI_COLUMNS, BREADTH_NUMERIC_COLUMNS
    from signal_confirm import INTERVAL_CONFIRMATION_COL, is_confirmed_signal  # type: ignore

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
from src.utils.mtm_pricing import normalize_today_price_column_names

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Compound column in consolidated CSVs: "SYMBOL, Long|Short, YYYY-MM-DD (Price: ...)"
SYMBOL_SIGNAL_COMPOUND_COL = "Symbol, Signal, Signal Date/Price[$]"
BREADTH_REQUIRED_COLUMNS = BREADTH_SBI_COLUMNS

# Outstanding-signals → consolidated CSV columns (see ``src.utils.mtm_pricing``). Always merged into
# entry / exit / portfolio_target fetches so MTM and holding period are never dropped when the LLM
# picks a narrow column index list.
CONSOLIDATED_MTM_REPORT_COLUMN_NAMES = (
    "Symbol, Signal, Signal Date/Price[$]",
    "Signal Open Price",
    "Today Trading Date/Price[$], Today Price vs Signal",
    "Current Mark to Market and Holding Period",
    "Trading Days between Signal and Today Date",
)


def _merge_mtm_report_columns(
    signal_type: str,
    df: pd.DataFrame,
    columns_to_keep: List[str],
) -> List[str]:
    if signal_type not in ("entry", "exit", "portfolio_target_achieved"):
        return columns_to_keep
    seen = set(columns_to_keep)
    out = list(columns_to_keep)
    for col in CONSOLIDATED_MTM_REPORT_COLUMN_NAMES:
        if col in df.columns and col not in seen:
            out.append(col)
            seen.add(col)
    return out


def normalize_position_side(raw: Optional[str]) -> Optional[str]:
    """Return 'short', 'long', or None."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    s = str(raw).strip().lower()
    if s in ("short", "long"):
        return s
    return None


def infer_position_side_from_query(text: str) -> Optional[str]:
    """
    Detect Short vs Long intent from natural language (short selling vs long).
    Avoid matching unrelated phrases like 'short term' by requiring signal/position wording.
    """
    for side in ("short", "long"):
        if is_explicit_position_side_request(text, side):
            return side
    return None


def is_explicit_position_side_request(text: str, side: Optional[str] = None) -> bool:
    """
    Return True only when the query explicitly asks to filter by a side.
    This avoids false positives from comparative prompts that mention both
    long and short (e.g. "identify contradictions between short and long").
    """
    if not text or not str(text).strip():
        return False

    low = text.lower()

    def _mentioned(s: str) -> bool:
        return bool(
            re.search(rf"\b{s}\s+(signals?|positions?|trades?|setups?)\b", low)
            or re.search(rf"\b{s}\b", low)
        )

    mentioned_short = _mentioned("short")
    mentioned_long = _mentioned("long")

    # If both directions are discussed, default to no direction filter.
    if mentioned_short and mentioned_long:
        return False

    sides_to_check = [normalize_position_side(side)] if side else ["short", "long"]

    exclusivity = bool(re.search(r"\b(only|just|exclusively|specifically|strictly)\b", low))
    filter_verbs = r"(show|list|retrieve|find|get|analy[sz]e|filter)"
    instruments = r"(signals?|positions?|trades?|setups?)"

    for s in [x for x in sides_to_check if x]:
        if not _mentioned(s):
            continue
        if exclusivity:
            return True
        if re.search(rf"\b{filter_verbs}\b[\s\S]{{0,40}}\b{s}\s+{instruments}\b", low):
            return True

    return False


EXIT_DATE_COL = "Exit Signal Date/Price[$]"
SOURCE_COL = "_mw_signal_source"
# Lower number = higher priority when deduplicating the same signal identity.
ENTRY_SOURCE_PRIORITY = {
    "outstanding": 0,
    "all_signal": 1,
    "entry_csv": 2,
    "virtual_trading": 3,
}


def infer_date_filter_mode(user_message: Optional[str]) -> str:
    """
    Return ``entry_or_exit`` for deep-dive / OR-style range queries, else ``primary``.

    Deep dives ask for signals whose entry **or** exit falls in the window, and open
    positions that were still active during the window (even if entered earlier).
    """
    if not user_message or not str(user_message).strip():
        return "primary"
    low = str(user_message).lower()
    if re.search(r"\bdeep[- ]?dive\b", low):
        return "entry_or_exit"
    if re.search(r"entry\s+and\s*/?\s*or\s+exit[- ]?date", low):
        return "entry_or_exit"
    return "primary"


def _is_open_exit_value(value) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return True
    s = str(value).strip().lower()
    if not s or s == "nan":
        return True
    return "no exit" in s


class SmartDataFetcher:
    """
    Fetches only the required columns from data files based on:
    - Signal type (entry/exit/portfolio_target_achieved/breadth)
    - Asset name (ticker)
    - Function name (trading strategy)
    - Date
    - Required columns

    Supports both folder-based (legacy) and consolidated CSV (new) data structures.
    """

    def __init__(self, use_consolidated_csvs=True):
        """Initialize the smart data fetcher."""
        self.use_consolidated_csvs = use_consolidated_csvs

        # Legacy folder-based paths
        self.entry_dir = Path(CHATBOT_ENTRY_DIR)
        self.exit_dir = Path(CHATBOT_EXIT_DIR)
        self.target_dir = Path(CHATBOT_TARGET_DIR)
        self.breadth_dir = Path(CHATBOT_BREADTH_DIR)

        # New consolidated CSV paths
        self.entry_csv = Path(CHATBOT_ENTRY_CSV)
        self.exit_csv = Path(CHATBOT_EXIT_CSV)
        self.target_csv = Path(CHATBOT_TARGET_CSV)
        self.breadth_csv = Path(CHATBOT_BREADTH_CSV)

    @staticmethod
    def _filter_outstanding_open_rows(df: pd.DataFrame) -> pd.DataFrame:
        """Keep only rows with no exit yet (outstanding report semantics)."""
        if EXIT_DATE_COL not in df.columns:
            return df
        return df[df[EXIT_DATE_COL].apply(_is_open_exit_value)].copy()

    @staticmethod
    def _filter_df_by_assets(df: pd.DataFrame, assets: Optional[List[str]]) -> pd.DataFrame:
        if not assets or SYMBOL_SIGNAL_COMPOUND_COL not in df.columns:
            return df
        out = df.copy()
        out["_extracted_symbol"] = (
            out[SYMBOL_SIGNAL_COMPOUND_COL].astype(str).str.split(",").str[0].str.strip()
        )
        out = out[out["_extracted_symbol"].isin(assets)]
        return out.drop(columns=["_extracted_symbol"])

    def _read_consolidated_signal_csv(self, signal_type: str) -> pd.DataFrame:
        csv_path = self._get_consolidated_csv_path(signal_type)
        if not csv_path.exists():
            logger.warning(f"Consolidated CSV does not exist: {csv_path}")
            return pd.DataFrame()
        try:
            return pd.read_csv(csv_path, encoding=CSV_ENCODING)
        except Exception as exc:
            logger.error("Error reading consolidated CSV %s: %s", csv_path, exc)
            return pd.DataFrame()

    @staticmethod
    def _tag_signal_source(df: pd.DataFrame, source: str) -> pd.DataFrame:
        if df.empty:
            return df
        out = df.copy()
        out[SOURCE_COL] = source
        return out

    @staticmethod
    def _filter_confirmed_rows(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or INTERVAL_CONFIRMATION_COL not in df.columns:
            return df
        mask = df[INTERVAL_CONFIRMATION_COL].apply(is_confirmed_signal)
        return df[mask].copy()

    @staticmethod
    def _entry_signal_identity_key(row: pd.Series) -> tuple:
        """Stable key: symbol × function × entry date × direction × interval."""
        sym_col = str(row.get(SYMBOL_SIGNAL_COMPOUND_COL, "")).strip()
        symbol = sym_col.split(",")[0].strip() if sym_col else ""
        func = str(row.get("Function", "")).strip()
        m = re.search(r"(\d{4}-\d{2}-\d{2})", sym_col)
        entry_date = m.group(1) if m else ""
        if ", Long," in sym_col:
            side = "Long"
        elif ", Short," in sym_col:
            side = "Short"
        else:
            side = ""
        interval = ""
        if INTERVAL_CONFIRMATION_COL in row.index and pd.notna(row.get(INTERVAL_CONFIRMATION_COL)):
            interval = str(row[INTERVAL_CONFIRMATION_COL]).split(",")[0].strip()
        return (symbol, func, entry_date, side, interval)

    @classmethod
    def _merge_entry_frames_by_identity(
        cls,
        base: pd.DataFrame,
        incoming: pd.DataFrame,
    ) -> pd.DataFrame:
        """Union rows; on duplicate identity keep the row with better source priority."""
        if incoming.empty:
            return base
        if base.empty:
            return incoming.copy()

        combined = pd.concat([base, incoming], ignore_index=True)
        if SOURCE_COL not in combined.columns:
            return combined.drop_duplicates(
                subset=[c for c in [SYMBOL_SIGNAL_COMPOUND_COL, "Function"] if c in combined.columns],
                keep="first",
            )

        combined["_prio"] = combined[SOURCE_COL].map(
            lambda s: ENTRY_SOURCE_PRIORITY.get(str(s), 99)
        )
        combined["_idkey"] = combined.apply(cls._entry_signal_identity_key, axis=1)
        combined = combined.sort_values("_prio", ascending=True)
        combined = combined.drop_duplicates(subset=["_idkey"], keep="first")
        return combined.drop(columns=["_prio", "_idkey"], errors="ignore")

    @classmethod
    def dedupe_single_asset_signals(cls, df: pd.DataFrame) -> pd.DataFrame:
        """Collapse duplicate identities for single-ticker fetches (keeps best MTM source)."""
        if df.empty:
            return df
        out = cls._merge_entry_frames_by_identity(pd.DataFrame(), df)
        if SOURCE_COL in out.columns:
            out = out.drop(columns=[SOURCE_COL], errors="ignore")
        return out

    def _prepare_open_entry_frame(
        self,
        df: pd.DataFrame,
        assets: Optional[List[str]],
        prefer_open_only: bool,
        prefer_confirmed_only: bool,
    ) -> pd.DataFrame:
        if df.empty:
            return df
        df = normalize_today_price_column_names(df)
        if prefer_open_only:
            df = self._filter_outstanding_open_rows(df)
        df = self._filter_df_by_assets(df, assets)
        if prefer_confirmed_only:
            df = self._filter_confirmed_rows(df)
        if not df.empty and "SignalType" not in df.columns:
            df = df.copy()
            df["SignalType"] = "entry"
        return df

    def _load_entry_source_dataframe(
        self,
        assets: Optional[List[str]] = None,
        prefer_open_only: bool = True,
        prefer_confirmed_only: bool = True,
    ) -> pd.DataFrame:
        """
        Load open entry rows from outstanding + entry.csv, then always supplement from
        all_signal and (when assets are set) virtual_trading. Never returns before supplements.
        """
        df = pd.DataFrame()
        outstanding_path = resolve_outstanding_signal_path()

        if outstanding_path is not None and outstanding_path.is_file():
            try:
                odf = pd.read_csv(outstanding_path, encoding=CSV_ENCODING)
                odf = self._prepare_open_entry_frame(
                    odf, assets, prefer_open_only, prefer_confirmed_only
                )
                if not odf.empty:
                    df = self._merge_entry_frames_by_identity(
                        df, self._tag_signal_source(odf, "outstanding")
                    )
                    logger.info(
                        "Entry from outstanding report %s (%s rows for filter)",
                        outstanding_path.name,
                        len(odf),
                    )
            except Exception as exc:
                logger.error(
                    "Failed to read outstanding signal report %s: %s",
                    outstanding_path,
                    exc,
                )

        edf = self._read_consolidated_signal_csv("entry")
        edf = self._prepare_open_entry_frame(
            edf, assets, prefer_open_only, prefer_confirmed_only
        )
        if not edf.empty:
            df = self._merge_entry_frames_by_identity(
                df, self._tag_signal_source(edf, "entry_csv")
            )
            logger.info("Merged entry.csv (%s rows for filter)", len(edf))

        df = self._supplement_entry_from_all_signal(df, assets, prefer_confirmed_only)
        if assets:
            df = self._supplement_entry_from_virtual_trading(df, assets)

        if SOURCE_COL in df.columns:
            n_out = int((df[SOURCE_COL] == "outstanding").sum()) if not df.empty else 0
            n_all = int((df[SOURCE_COL] == "all_signal").sum()) if not df.empty else 0
            logger.info(
                "Unified entry load: %s total rows (outstanding=%s, all_signal supplement=%s)",
                len(df),
                n_out,
                n_all,
            )
        return df

    def _supplement_entry_from_all_signal(
        self,
        df: pd.DataFrame,
        assets: Optional[List[str]],
    ) -> pd.DataFrame:
        """
        Merge open rows from the latest All Signal report that are missing from
        ``entry.csv`` / outstanding (e.g. PULSEGAUGE entries not in outstanding export).
        """
        path = resolve_all_signal_path()
        if path is None or not path.is_file():
            return df

        try:
            adf = pd.read_csv(path, encoding=CSV_ENCODING)
            adf = normalize_today_price_column_names(adf)
            adf = self._filter_outstanding_open_rows(adf)
            adf = self._filter_df_by_assets(adf, assets)
        except Exception as exc:
            logger.warning("Could not supplement entry from all_signal %s: %s", path, exc)
            return df

        if adf.empty:
            return df

        keys = {self._entry_signal_identity_key(row) for _, row in df.iterrows()} if not df.empty else set()
        extra_rows = []
        for _, row in adf.iterrows():
            key = self._entry_signal_identity_key(row)
            if key not in keys:
                extra_rows.append(row)
                keys.add(key)

        if not extra_rows:
            return df

        extra_df = pd.DataFrame(extra_rows)
        if "SignalType" not in extra_df.columns:
            extra_df = extra_df.copy()
            extra_df["SignalType"] = "entry"
        logger.info(
            "Supplemented %s open entry row(s) from all_signal report: %s",
            len(extra_df),
            path.name,
        )
        if df.empty:
            return extra_df
        return pd.concat([df, extra_df], ignore_index=True)

    def _supplement_entry_from_virtual_trading(
        self,
        df: pd.DataFrame,
        assets: List[str],
    ) -> pd.DataFrame:
        """
        For single-asset queries, add open Virtual Trading rows not present in consolidated
        entry data (e.g. FRACTAL TRACK daily long confirmed on 2026-04-28).
        """
        us = trade_store_us_dir()
        if not us.is_dir():
            return df

        keys = {self._entry_signal_identity_key(row) for _, row in df.iterrows()} if not df.empty else set()
        extra_rows = []

        for vt_name, default_side in (
            ("virtual_trading_long.csv", "Long"),
            ("virtual_trading_short.csv", "Short"),
        ):
            vt_path = us / vt_name
            if not vt_path.is_file():
                continue
            try:
                vdf = pd.read_csv(vt_path, encoding=CSV_ENCODING)
            except Exception as exc:
                logger.warning("Could not read %s: %s", vt_path, exc)
                continue

            if vdf.empty:
                continue

            sym_col = "Symbol"
            if sym_col not in vdf.columns:
                continue
            vdf = vdf[vdf[sym_col].astype(str).str.strip().isin(assets)]
            if "Status" in vdf.columns:
                vdf = vdf[vdf["Status"].astype(str).str.strip().str.lower() == "open"]
            if vdf.empty:
                continue

            for _, row in vdf.iterrows():
                symbol = str(row.get("Symbol", "")).strip()
                side = str(row.get("Signal", default_side)).strip() or default_side
                entry_date = str(row.get("Entry Date", "")).strip()
                if not symbol or not entry_date or entry_date.lower() == "nan":
                    continue
                try:
                    entry_price = float(row.get("Entry Price"))
                    price_str = f"{entry_price:g}"
                except (TypeError, ValueError):
                    price_str = str(row.get("Entry Price", "")).strip()

                interval = str(row.get("Interval", "Daily")).strip() or "Daily"
                compound = f"{symbol}, {side}, {entry_date} (Price: {price_str})"
                mtm = str(row.get("Realised/Unrealised Profit", "") or "").strip()
                today_px = row.get("Today price", "")
                try:
                    today_str = f"{float(today_px):g}"
                except (TypeError, ValueError):
                    today_str = str(today_px).strip()

                synthetic = {
                    "Function": row.get("Function", ""),
                    SYMBOL_SIGNAL_COMPOUND_COL: compound,
                    EXIT_DATE_COL: "No Exit Yet",
                    "Current Mark to Market and Holding Period": mtm or "No Information",
                    "Interval, Confirmation Status": (
                        f"{interval}, is CONFIRMED on {entry_date}"
                    ),
                    "Today Trading Date/Price[$], Today Price vs Signal": (
                        f"(Price: {today_str}), Virtual Trading export"
                        if today_str
                        else "No Information"
                    ),
                    "SignalType": "entry",
                    "Signal Open Price": price_str,
                }
                key = self._entry_signal_identity_key(pd.Series(synthetic))
                if key in keys:
                    continue
                extra_rows.append(synthetic)
                keys.add(key)

        if not extra_rows:
            return df

        extra_df = pd.DataFrame(extra_rows)
        logger.info(
            "Supplemented %s open entry row(s) from virtual_trading for assets %s",
            len(extra_df),
            assets,
        )
        if df.empty:
            return extra_df
        return pd.concat([df, extra_df], ignore_index=True)

    def _consolidated_source_ready(self, signal_type: str) -> bool:
        """True if we can serve this signal type from the consolidated / report path."""
        if signal_type == "entry":
            op = resolve_outstanding_signal_path()
            if op is not None and op.is_file():
                return True
            return self.entry_csv.is_file()
        try:
            return self._get_consolidated_csv_path(signal_type).is_file()
        except ValueError:
            return False
    
    def fetch_data(
        self,
        signal_types: List[str],
        required_columns: Optional[List[str]],
        assets: Optional[List[str]] = None,
        functions: Optional[List[str]] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit_rows: Optional[int] = None,
        column_indices: Optional[Dict[str, List[int]]] = None,
        position_side: Optional[str] = None,
        date_filter_mode: Optional[str] = None,
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch data from specified signal types with the required columns or ALL columns.

        Uses consolidated CSV files if available, falls back to folder-based approach.

        Args:
            signal_types: List of signal types to fetch from (entry, exit, portfolio_target_achieved, breadth)
            required_columns: List of column names to fetch, or None to fetch ALL columns (preserves CSV structure)
            assets: Optional list of asset/ticker names to filter by
            functions: Optional list of function names to filter by
            from_date: Optional start date (YYYY-MM-DD)
            to_date: Optional end date (YYYY-MM-DD)
            limit_rows: Optional limit on number of rows per signal type
            column_indices: Optional dict mapping signal_type to list of column indices for precise selection
            position_side: Optional 'short' or 'long' — filter rows by position in the compound symbol column
            date_filter_mode: ``primary`` (single date column) or ``entry_or_exit`` (OR + active overlap)

        Returns:
            Dictionary mapping signal_type to DataFrame with fetched data
            {
                "entry": DataFrame with required/all columns,
                "exit": DataFrame with required/all columns,
                ...
            }
        """
        # Use consolidated CSVs if enabled and available, otherwise fall back to folder-based
        if self.use_consolidated_csvs:
            consolidated_available = all(
                self._consolidated_source_ready(signal_type) for signal_type in signal_types
            )

            if consolidated_available:
                logger.info("🔄 Using consolidated CSV files for data fetching")
                return self.fetch_data_consolidated(
                    signal_types=signal_types,
                    required_columns=required_columns,
                    assets=assets,
                    functions=functions,
                    from_date=from_date,
                    to_date=to_date,
                    limit_rows=limit_rows,
                    column_indices=column_indices,
                    position_side=position_side,
                    date_filter_mode=date_filter_mode,
                )

        # Fall back to folder-based approach
        logger.info("🔄 Using folder-based data fetching (fallback)")
        result = {}

        for signal_type in signal_types:
            try:
                if signal_type == "breadth":
                    df = self._fetch_breadth_data(
                        required_columns=required_columns,
                        from_date=from_date,
                        to_date=to_date,
                        limit_rows=limit_rows
                    )
                else:
                    df = self._fetch_signal_type_data(
                        signal_type=signal_type,
                        required_columns=required_columns,
                        assets=assets,
                        functions=functions,
                        from_date=from_date,
                        to_date=to_date,
                        limit_rows=limit_rows
                    )

                if not df.empty:
                    result[signal_type] = df
                    logger.info(f"✅ Fetched {len(df)} rows from {signal_type} with columns: {list(df.columns)}")
                    # Show sample data for debugging
                    if len(df) > 0:
                        logger.info(f"📊 Sample data preview from {signal_type}:")
                        for col in df.columns:
                            sample_val = df[col].iloc[0] if not df[col].empty else "N/A"
                            logger.info(f"   {col}: {sample_val}")
                else:
                    logger.warning(f"❌ No data fetched from {signal_type}")
                    logger.warning(f"   Requested columns: {required_columns}")
                    logger.warning(f"   Assets filter: {assets}")
                    logger.warning(f"   Functions filter: {functions}")
                    logger.warning(f"   Date range: {from_date} to {to_date}")

            except Exception as e:
                logger.error(f"Error fetching data from {signal_type}: {e}")

        return result
    
    def _fetch_signal_type_data(
        self,
        signal_type: str,
        required_columns: Optional[List[str]],
        assets: Optional[List[str]] = None,
        functions: Optional[List[str]] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit_rows: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Fetch data from a signal type (entry/exit/portfolio_target_achieved).
        
        Args:
            signal_type: One of "entry", "exit", "portfolio_target_achieved"
            required_columns: List of column names to fetch, or None to fetch ALL columns
            assets: Optional list of assets to filter by
            functions: Optional list of functions to filter by
            from_date: Optional start date
            to_date: Optional end date
            limit_rows: Optional row limit
            
        Returns:
            DataFrame with fetched data
        """
        # Get base directory for signal type
        base_dir = self._get_signal_type_dir(signal_type)
        if not base_dir.exists():
            logger.warning(f"Directory does not exist: {base_dir}")
            return pd.DataFrame()
        
        all_data = []
        
        # Iterate through asset directories
        for asset_dir in base_dir.iterdir():
            if not asset_dir.is_dir():
                continue
            
            asset_name = asset_dir.name
            
            # Filter by assets if specified
            if assets and asset_name not in assets:
                continue
            
            # Iterate through function directories
            for function_dir in asset_dir.iterdir():
                if not function_dir.is_dir():
                    continue
                
                function_name = function_dir.name
                
                # Filter by functions if specified
                if functions and function_name not in functions:
                    continue
                
                # Get CSV files in date range
                csv_files = self._get_csv_files_in_range(
                    function_dir,
                    from_date,
                    to_date
                )
                
                # Read data from CSV files
                for csv_file in csv_files:
                    try:
                        df = self._read_csv_with_columns(csv_file, required_columns)
                        
                        if not df.empty:
                            # Add metadata columns
                            df['_signal_type'] = signal_type
                            df['_asset'] = asset_name
                            df['_function'] = function_name
                            df['_date'] = csv_file.stem  # filename is the date
                            
                            all_data.append(df)
                    
                    except Exception as e:
                        logger.error(f"Error reading {csv_file}: {e}")
        
        # Combine all data
        if not all_data:
            return pd.DataFrame()
        
        combined_df = pd.concat(all_data, ignore_index=True)

        for pct_col in [
            "Bullish Asset vs Total Asset (%)",
            "Bullish Signal vs Total Signal (%)",
        ]:
            if pct_col in combined_df.columns:
                combined_df[f"{pct_col} [numeric]"] = pd.to_numeric(
                    combined_df[pct_col].astype(str).str.replace("%", "", regex=False).str.strip(),
                    errors="coerce",
                )
        
        # Apply row limit if specified
        if limit_rows and len(combined_df) > limit_rows:
            combined_df = combined_df.head(limit_rows)
        
        return combined_df

    def fetch_data_consolidated(
        self,
        signal_types: List[str],
        required_columns: Optional[List[str]],
        assets: Optional[List[str]] = None,
        functions: Optional[List[str]] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit_rows: Optional[int] = None,
        column_indices: Optional[Dict[str, List[int]]] = None,
        position_side: Optional[str] = None,
        date_filter_mode: Optional[str] = None,
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch data from consolidated CSV files.

        Args:
            signal_types: List of signal types to fetch from (entry, exit, portfolio_target_achieved, breadth)
            required_columns: List of column names to fetch, or None to fetch ALL columns
            assets: Optional list of asset/ticker names to filter by
            functions: Optional list of function names to filter by
            from_date: Optional start date (YYYY-MM-DD)
            to_date: Optional end date (YYYY-MM-DD)
            limit_rows: Optional limit on number of rows per signal type
            date_filter_mode: ``primary`` or ``entry_or_exit``

        Returns:
            Dictionary mapping signal_type to DataFrame with fetched data
        """
        mode = date_filter_mode or "primary"
        result = {}

        for signal_type in signal_types:
            try:
                if signal_type == "breadth":
                    df = self._fetch_breadth_data_consolidated(
                        required_columns=required_columns,
                        from_date=from_date,
                        to_date=to_date,
                        limit_rows=limit_rows
                    )
                else:
                    # Get column indices for this signal type if available
                    signal_col_indices = column_indices.get(signal_type) if column_indices else None
                    
                    df = self._fetch_signal_type_data_consolidated(
                        signal_type=signal_type,
                        required_columns=required_columns,
                        assets=assets,
                        functions=functions,
                        from_date=from_date,
                        to_date=to_date,
                        limit_rows=limit_rows,
                        column_indices=signal_col_indices,
                        position_side=position_side,
                        date_filter_mode=mode,
                    )

                if not df.empty:
                    result[signal_type] = df
                    logger.info(f"✅ Fetched {len(df)} rows from {signal_type} (consolidated) with columns: {list(df.columns)}")

            except Exception as e:
                logger.error(f"Error fetching data from {signal_type} (consolidated): {e}")

        return result

    def _fetch_signal_type_data_consolidated(
        self,
        signal_type: str,
        required_columns: Optional[List[str]],
        assets: Optional[List[str]] = None,
        functions: Optional[List[str]] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit_rows: Optional[int] = None,
        column_indices: Optional[List[int]] = None,
        position_side: Optional[str] = None,
        date_filter_mode: str = "primary",
    ) -> pd.DataFrame:
        """
        Fetch data from consolidated CSV for a signal type (entry/exit/target).

        Args:
            signal_type: One of "entry", "exit", "portfolio_target_achieved"
            required_columns: List of column names to fetch, or None to fetch ALL columns
            assets: Optional list of assets to filter by
            functions: Optional list of functions to filter by
            from_date: Optional start date
            to_date: Optional end date
            limit_rows: Optional row limit
            date_filter_mode: ``primary`` or ``entry_or_exit``

        Returns:
            DataFrame with fetched data
        """
        column_indices = list(column_indices) if column_indices else column_indices
        df: Optional[pd.DataFrame] = None

        if signal_type == "entry":
            df = self._load_entry_source_dataframe(assets=assets, prefer_open_only=True)
            # Column indices refer to chatbot/data/entry.csv layout; outstanding export order differs.
            column_indices = None

        if df is None:
            df = self._read_consolidated_signal_csv(signal_type)

        try:
            if df.empty:
                return pd.DataFrame()

            symbol_col = SYMBOL_SIGNAL_COMPOUND_COL
            if signal_type != "entry":
                df = self._filter_df_by_assets(df, assets)

            # Filter by Function column
            if 'Function' in df.columns and functions:
                df = df[df['Function'].isin(functions)]

            if from_date or to_date:
                logger.info(
                    "Filtering %s by date range: %s to %s (mode=%s)",
                    signal_type,
                    from_date,
                    to_date,
                    date_filter_mode,
                )
                logger.info("DataFrame shape before date filtering: %s", df.shape)
                df = self._filter_dataframe_by_date_range(
                    df,
                    signal_type,
                    from_date,
                    to_date,
                    date_filter_mode,
                )
                logger.info("DataFrame shape after date filtering: %s", df.shape)

            ps = normalize_position_side(position_side)
            if ps and symbol_col in df.columns:
                marker = f", {ps.title()}, "
                before_ps = len(df)
                df = df[df[symbol_col].astype(str).str.contains(marker, na=False, regex=False)]
                logger.info(f"Position filter ({ps}): {before_ps} -> {len(df)} rows")

            if "_extracted_date" in df.columns:
                df = df.sort_values("_extracted_date", ascending=False, na_position="last")
                df = df.drop(columns=["_extracted_date"])

            # Apply column selection - use indices if provided for 100% accuracy
            if column_indices and len(column_indices) > 0:
                # Use column indices for precise selection
                logger.info(f"Using column indices for {signal_type}: {column_indices}")
                all_columns = df.columns.tolist()
                columns_to_keep = []
                for idx in column_indices:
                    if 0 <= idx < len(all_columns):
                        columns_to_keep.append(all_columns[idx])
                        logger.info(f"  Index {idx} -> Column: {all_columns[idx]}")
                    else:
                        logger.warning(f"  Index {idx} out of range (0-{len(all_columns)-1})")
                
                if columns_to_keep:
                    logger.info(f"Keeping {len(columns_to_keep)} columns by index")
                    columns_to_keep = _merge_mtm_report_columns(
                        signal_type, df, columns_to_keep
                    )
                    df = df[columns_to_keep]
                else:
                    logger.warning(f"No valid column indices for {signal_type}")
                    return pd.DataFrame()
            elif required_columns:
                # Fallback to column names (old behavior)
                available_columns = df.columns.tolist()
                logger.info(f"Required columns for {signal_type}: {required_columns}")
                logger.info(f"Available columns in CSV: {available_columns[:10]}...")  # Show first 10
                columns_to_keep = [col for col in required_columns if col in available_columns]
                missing_columns = [col for col in required_columns if col not in available_columns]
                if missing_columns:
                    logger.warning(f"Missing columns in {signal_type}: {missing_columns}")
                if columns_to_keep:
                    logger.info(f"Keeping {len(columns_to_keep)} columns: {columns_to_keep}")
                    columns_to_keep = _merge_mtm_report_columns(
                        signal_type, df, columns_to_keep
                    )
                    df = df[columns_to_keep]
                else:
                    logger.warning(f"None of the required columns found in {signal_type} consolidated CSV")
                    logger.warning(f"Requested: {required_columns}")
                    logger.warning(f"Available: {available_columns}")
                    return pd.DataFrame()
            # If required_columns is None, keep all columns

            # Apply row limit
            if limit_rows and len(df) > limit_rows:
                df = df.head(limit_rows)

            return df

        except Exception as e:
            logger.error("Error processing consolidated data for %s: %s", signal_type, e)
            return pd.DataFrame()

    def _get_date_source_column(self, signal_type: str, columns: List[str]) -> Optional[str]:
        """
        Choose the best source column for date filtering by signal type.

        Priority:
        - entry: signal date column
        - exit: exit date column
        - portfolio_target_achieved: target exit date, then exit date, then signal date
        """
        if signal_type == "entry":
            candidates = [
                "Symbol, Signal, Signal Date/Price[$]",
            ]
        elif signal_type == "exit":
            candidates = [
                "Exit Signal Date/Price[$]",
                "Symbol, Signal, Signal Date/Price[$]",
            ]
        elif signal_type == "portfolio_target_achieved":
            candidates = [
                "Backtested Target Exit Date",
                "Exit Signal Date/Price[$]",
                "Symbol, Signal, Signal Date/Price[$]",
            ]
        else:
            candidates = [
                "Symbol, Signal, Signal Date/Price[$]",
            ]

        for candidate in candidates:
            if candidate in columns:
                return candidate
        return None

    def _extract_date_series(self, series: pd.Series, source_column: str) -> pd.Series:
        """
        Extract YYYY-MM-DD date strings from date-bearing text columns.
        """
        if source_column == "Backtested Target Exit Date":
            # This column may already be a plain date or contain text; regex works for both.
            return series.astype(str).str.extract(r'(\d{4}-\d{2}-\d{2})', expand=False)

        return series.astype(str).str.extract(r'(\d{4}-\d{2}-\d{2})', expand=False)

    def _entry_and_exit_dates_for_row(
        self,
        row: pd.Series,
        signal_type: str,
        columns: List[str],
    ) -> tuple:
        """Return (entry_date, exit_date) as Timestamps or NaT for one row."""
        symbol_col = SYMBOL_SIGNAL_COMPOUND_COL
        entry_dt = exit_dt = pd.NaT

        if symbol_col in columns:
            entry_parsed = self._extract_date_series(
                pd.Series([row[symbol_col]]), symbol_col
            ).iloc[0]
            if entry_parsed is not None and str(entry_parsed).strip():
                entry_dt = pd.to_datetime(entry_parsed, errors="coerce")

        exit_col = EXIT_DATE_COL
        if exit_col in columns:
            exit_raw = row[exit_col]
            if not _is_open_exit_value(exit_raw):
                parsed = self._extract_date_series(pd.Series([exit_raw]), exit_col).iloc[0]
                if parsed is not None and str(parsed).strip():
                    exit_dt = pd.to_datetime(parsed, errors="coerce")

        if signal_type == "portfolio_target_achieved" and pd.isna(exit_dt):
            target_col = "Backtested Target Exit Date"
            if target_col in columns:
                parsed = self._extract_date_series(
                    pd.Series([row[target_col]]), target_col
                ).iloc[0]
                if parsed is not None and str(parsed).strip():
                    exit_dt = pd.to_datetime(parsed, errors="coerce")

        return entry_dt, exit_dt

    @staticmethod
    def _row_in_entry_or_exit_window(
        entry_dt,
        exit_dt,
        from_dt,
        to_dt,
        signal_type: str,
    ) -> bool:
        """
        Match deep-dive semantics: entry OR exit in range, or still open and overlapping window.
        """

        def _in_closed_range(dt) -> bool:
            if pd.isna(dt):
                return False
            if from_dt is not None and pd.notna(from_dt) and dt < from_dt:
                return False
            if to_dt is not None and pd.notna(to_dt) and dt > to_dt:
                return False
            return True

        if _in_closed_range(entry_dt) or _in_closed_range(exit_dt):
            return True

        if pd.isna(entry_dt):
            return False

        if to_dt is not None and pd.notna(to_dt) and entry_dt > to_dt:
            return False

        is_open = pd.isna(exit_dt)
        if not is_open and from_dt is not None and pd.notna(from_dt) and exit_dt < from_dt:
            return False

        # Still open, or closed on/after window start while entered before window end
        return is_open or (
            from_dt is None
            or pd.isna(from_dt)
            or (pd.notna(exit_dt) and exit_dt >= from_dt)
        )

    def _filter_dataframe_by_date_range(
        self,
        df: pd.DataFrame,
        signal_type: str,
        from_date: Optional[str],
        to_date: Optional[str],
        date_filter_mode: str,
    ) -> pd.DataFrame:
        if df.empty:
            return df

        from_dt = pd.to_datetime(from_date, errors="coerce") if from_date else None
        to_dt = pd.to_datetime(to_date, errors="coerce") if to_date else None
        if from_dt is None and to_dt is None:
            return df

        columns = df.columns.tolist()
        mode = (date_filter_mode or "primary").lower()

        if mode == "entry_or_exit":
            keep = []
            sort_dates = []
            for idx, row in df.iterrows():
                entry_dt, exit_dt = self._entry_and_exit_dates_for_row(
                    row, signal_type, columns
                )
                if self._row_in_entry_or_exit_window(
                    entry_dt, exit_dt, from_dt, to_dt, signal_type
                ):
                    keep.append(idx)
                    sort_dates.append(
                        exit_dt if pd.notna(exit_dt) else entry_dt
                    )
            if not keep:
                return df.iloc[0:0].copy()
            out = df.loc[keep].copy()
            out["_extracted_date"] = pd.to_datetime(sort_dates, errors="coerce")
            return out

        date_source = self._get_date_source_column(signal_type, columns)
        if not date_source:
            logger.warning(
                "No suitable date source column found for %s; skipping date filter",
                signal_type,
            )
            return df

        logger.info("Using date source column for %s: %s", signal_type, date_source)
        out = df.copy()
        out["_extracted_date"] = pd.to_datetime(
            self._extract_date_series(out[date_source], date_source), errors="coerce"
        )
        if from_dt is not None and pd.notna(from_dt):
            out = out[out["_extracted_date"] >= from_dt]
        if to_dt is not None and pd.notna(to_dt):
            out = out[out["_extracted_date"] <= to_dt]
        return out

    def _fetch_breadth_data_consolidated(
        self,
        required_columns: Optional[List[str]],
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit_rows: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Fetch breadth data from consolidated CSV.

        Args:
            required_columns: List of column names to fetch, or None to fetch ALL columns
            from_date: Optional start date
            to_date: Optional end date
            limit_rows: Optional row limit

        Returns:
            DataFrame with fetched data
        """
        if not self.breadth_csv.exists():
            logger.warning(f"Breadth consolidated CSV does not exist: {self.breadth_csv}")
            return pd.DataFrame()

        try:
            # Read the consolidated CSV
            df = pd.read_csv(self.breadth_csv, encoding=CSV_ENCODING)

            if df.empty:
                return pd.DataFrame()

            # Apply date filters - breadth CSV uses "Date" column (capitalized)
            if from_date or to_date:
                date_col = 'Date'
                if date_col in df.columns:
                    # Convert date to datetime for filtering
                    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')

                    if from_date:
                        from_date_obj = pd.to_datetime(from_date)
                        df = df[df[date_col] >= from_date_obj]

                    if to_date:
                        to_date_obj = pd.to_datetime(to_date)
                        df = df[df[date_col] <= to_date_obj]

            # Apply column selection
            if required_columns:
                available_columns = df.columns.tolist()
                merged_required = []
                seen = set()
                for col in [*required_columns, *BREADTH_REQUIRED_COLUMNS]:
                    if col and col not in seen:
                        merged_required.append(col)
                        seen.add(col)
                columns_to_keep = [col for col in merged_required if col in available_columns]
                if columns_to_keep:
                    df = df[columns_to_keep]
                else:
                    logger.warning("None of the required columns found in breadth consolidated CSV")
                    return pd.DataFrame()
            # If required_columns is None, keep all columns

            # Normalize SBI trade-arrival columns to numeric for percentile analysis.
            for num_col in BREADTH_NUMERIC_COLUMNS:
                if num_col in df.columns:
                    series = df[num_col].astype(str).str.replace("%", "", regex=False).str.strip()
                    series = series.replace({"N/A": "", "Not Applicable": "", "nan": ""})
                    df[f"{num_col} [numeric]"] = pd.to_numeric(series, errors="coerce")

            # Apply row limit
            if limit_rows and len(df) > limit_rows:
                df = df.head(limit_rows)

            return df

        except Exception as e:
            logger.error(f"Error reading breadth consolidated CSV {self.breadth_csv}: {e}")
            return pd.DataFrame()

    def _get_consolidated_csv_path(self, signal_type: str) -> Path:
        """Get the consolidated CSV path for a signal type."""
        if signal_type == "entry":
            return self.entry_csv
        elif signal_type == "exit":
            return self.exit_csv
        elif signal_type == "portfolio_target_achieved":
            return self.target_csv
        elif signal_type == "breadth":
            return self.breadth_csv
        else:
            raise ValueError(f"Invalid signal type: {signal_type}")

    def _fetch_breadth_data(
        self,
        required_columns: Optional[List[str]],
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit_rows: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Fetch breadth data (no assets/functions, just date-based files).
        
        Args:
            required_columns: List of column names to fetch, or None to fetch ALL columns
            from_date: Optional start date
            to_date: Optional end date
            limit_rows: Optional row limit
            
        Returns:
            DataFrame with fetched data
        """
        if not self.breadth_dir.exists():
            logger.warning(f"Breadth directory does not exist: {self.breadth_dir}")
            return pd.DataFrame()
        
        # Get CSV files in date range
        csv_files = self._get_csv_files_in_range(
            self.breadth_dir,
            from_date,
            to_date
        )
        
        all_data = []
        
        for csv_file in csv_files:
            try:
                df = self._read_csv_with_columns(csv_file, required_columns)
                
                if not df.empty:
                    # Add metadata
                    df['_signal_type'] = 'breadth'
                    df['_date'] = csv_file.stem
                    all_data.append(df)
            
            except Exception as e:
                logger.error(f"Error reading {csv_file}: {e}")
        
        # Combine all data
        if not all_data:
            return pd.DataFrame()
        
        combined_df = pd.concat(all_data, ignore_index=True)
        
        # Apply row limit if specified
        if limit_rows and len(combined_df) > limit_rows:
            combined_df = combined_df.head(limit_rows)
        
        return combined_df
    
    def _get_signal_type_dir(self, signal_type: str) -> Path:
        """Get the base directory for a signal type."""
        if signal_type == "entry":
            return self.entry_dir
        elif signal_type == "exit":
            return self.exit_dir
        elif signal_type == "portfolio_target_achieved":
            return self.target_dir
        elif signal_type == "breadth":
            return self.breadth_dir
        else:
            raise ValueError(f"Invalid signal type: {signal_type}")
    
    def _get_csv_files_in_range(
        self,
        directory: Path,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> List[Path]:
        """
        Get CSV files in a directory within the specified date range.
        
        Args:
            directory: Directory to search
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            
        Returns:
            List of CSV file paths
        """
        csv_files = sorted(list(directory.glob("*.csv")))
        
        if not from_date and not to_date:
            return csv_files
        
        # Filter by date range
        filtered_files = []
        
        for csv_file in csv_files:
            file_date_str = csv_file.stem
            
            # Try to parse the date from filename
            try:
                file_date = datetime.strptime(file_date_str, DATE_FORMAT)
                
                # Check if within range
                if from_date:
                    from_date_obj = datetime.strptime(from_date, DATE_FORMAT)
                    if file_date < from_date_obj:
                        continue
                
                if to_date:
                    to_date_obj = datetime.strptime(to_date, DATE_FORMAT)
                    if file_date > to_date_obj:
                        continue
                
                filtered_files.append(csv_file)
            
            except ValueError:
                # If filename is not a date, skip it
                logger.warning(f"Could not parse date from filename: {csv_file.name}")
                continue
        
        return filtered_files
    
    def _read_csv_with_columns(
        self,
        csv_file: Path,
        required_columns: Optional[List[str]]
    ) -> pd.DataFrame:
        """
        Read a CSV file and return the required columns or ALL columns if None specified.
        Uses flexible matching: exact match, partial match, or semantic match.
        
        Args:
            csv_file: Path to CSV file
            required_columns: List of column names to read, or None to fetch ALL columns
            
        Returns:
            DataFrame with the required columns or ALL columns (preserving original CSV structure)
        """
        try:
            # First read just the header to see what columns are available
            df_header = pd.read_csv(csv_file, nrows=0, encoding=CSV_ENCODING)
            available_columns = df_header.columns.tolist()
            
            logger.info(f"📁 Reading {csv_file.name}")
            logger.info(f"📊 Available columns ({len(available_columns)}): {available_columns}")
            
            # If no specific columns requested, return ALL columns to preserve original CSV structure
            if required_columns is None:
                logger.info(f"🎯 Fetching ALL columns to preserve original CSV structure")
                df = pd.read_csv(csv_file, encoding=CSV_ENCODING)
                logger.info(f"📈 Loaded {len(df)} rows with {len(df.columns)} columns from {csv_file.name}")
                return df
            
            # Find which required columns exist in this file using flexible matching
            logger.info(f"🎯 Required columns ({len(required_columns)}): {required_columns}")
            columns_to_read = self._match_columns_flexibly(required_columns, available_columns)
            
            logger.info(f"✅ Matched columns ({len(columns_to_read)}): {columns_to_read}")
            
            if not columns_to_read:
                logger.warning(f"❌ None of the required columns found in {csv_file.name}")
                logger.warning(f"   Required: {required_columns}")
                logger.warning(f"   Available: {available_columns}")
                return pd.DataFrame()
            
            # Read only the required columns
            df = pd.read_csv(csv_file, usecols=columns_to_read, encoding=CSV_ENCODING)
            
            logger.info(f"📈 Loaded {len(df)} rows with {len(df.columns)} columns from {csv_file.name}")
            
            return df
        
        except Exception as e:
            logger.error(f"Error reading CSV {csv_file}: {e}")
            return pd.DataFrame()
    
    def _match_columns_flexibly(
        self,
        required_columns: List[str],
        available_columns: List[str]
    ) -> List[str]:
        """
        Match required columns to available columns using flexible matching.
        
        Matching strategies:
        1. Exact match (case-insensitive)
        2. Partial match (column contains required keyword)
        3. Semantic match (e.g., "target" matches "target_1", "target_price", etc.)
        
        Args:
            required_columns: List of column names requested
            available_columns: List of column names in the CSV
            
        Returns:
            List of actual column names to read from CSV
        """
        matched_columns = []
        
        for req_col in required_columns:
            req_col_lower = req_col.lower().strip()
            
            # Strategy 1: Exact match (case-insensitive)
            found_exact = False
            for avail_col in available_columns:
                if avail_col.lower().strip() == req_col_lower:
                    if avail_col not in matched_columns:
                        matched_columns.append(avail_col)
                    found_exact = True
                    break
            
            if not found_exact:
                # Strategy 2: Smart partial matching with preference for better matches
                best_match = None
                best_score = 0
                
                for avail_col in available_columns:
                    if avail_col in matched_columns:
                        continue  # Skip already matched columns
                        
                    avail_col_lower = avail_col.lower().strip()
                    
                    # Calculate match score
                    score = 0
                    
                    # High score for exact substring match
                    if req_col_lower in avail_col_lower:
                        score += 100
                    
                    # Medium score for containing key words
                    req_words = set(req_col_lower.replace('[', ' ').replace(']', ' ').replace('(', ' ').replace(')', ' ').replace(',', ' ').split())
                    avail_words = set(avail_col_lower.replace('[', ' ').replace(']', ' ').replace('(', ' ').replace(')', ' ').replace(',', ' ').split())
                    
                    common_words = req_words & avail_words
                    if common_words:
                        score += len(common_words) * 10
                    
                    # Bonus for semantic relationships
                    if self._are_semantically_related(req_col_lower, avail_col_lower):
                        score += 5
                    
                    # Update best match
                    if score > best_score and score > 10:  # Minimum threshold
                        best_score = score
                        best_match = avail_col
                
                if best_match:
                    matched_columns.append(best_match)
                    logger.info(f"✅ Matched '{req_col}' to '{best_match}' (score: {best_score})")
                else:
                    logger.warning(f"❌ Could not match required column '{req_col}' to any available columns")
                    logger.warning(f"   Available columns: {available_columns}")
        
        logger.info(f"🔗 Final column matching: {dict(zip(required_columns, matched_columns))}")
        return matched_columns
    
    def _are_semantically_related(self, col1: str, col2: str) -> bool:
        """
        Check if two column names are semantically related.
        
        Examples:
        - "target" matches "target_1", "target_price", "target_reached"
        - "entry" matches "entry_date", "entry_price", "entry_signal"
        - "performance" matches "current_performance", "performance_pct"
        
        Args:
            col1: First column name (lowercase)
            col2: Second column name (lowercase)
            
        Returns:
            True if semantically related
        """
        # Define keyword groups that are semantically related
        related_groups = [
            {'target', 'target_1', 'target_2', 'target_3', 'target_price', 'target_reached', 'target_hit'},
            {'entry', 'entry_date', 'entry_price', 'entry_signal', 'entry_time'},
            {'exit', 'exit_date', 'exit_price', 'exit_signal', 'exit_time'},
            {'performance', 'current_performance', 'performance_pct', 'perf', 'pnl'},
            {'price', 'current_price', 'close_price', 'open_price', 'close', 'open'},
            {'date', 'signal_date', 'entry_date', 'exit_date', 'timestamp'},
            {'signal', 'signal_type', 'signal_date', 'signal_strength'},
            {'volume', 'vol', 'avg_volume', 'volume_ratio'},
            {'rsi', 'rsi_14', 'rsi_value'},
            {'macd', 'macd_line', 'macd_signal', 'macd_hist'},
            {'bollinger', 'bb_upper', 'bb_lower', 'bb_mid', 'bb_width'},
            {'stochastic', 'stoch', 'stoch_k', 'stoch_d'},
            {'divergence', 'div', 'bullish_div', 'bearish_div'},
            {'trend', 'trendline', 'uptrend', 'downtrend'},
        ]
        
        # Check if both columns belong to the same semantic group
        for group in related_groups:
            # Check if any word from col1 or col2 is in this group
            col1_words = set(col1.replace('_', ' ').split())
            col2_words = set(col2.replace('_', ' ').split())
            
            if (any(word in group for word in col1_words) and 
                any(word in group for word in col2_words)):
                return True
        
        return False
    
    def get_data_summary(
        self,
        signal_type: str,
        asset: Optional[str] = None,
        function: Optional[str] = None
    ) -> Dict:
        """
        Get summary information about available data.
        
        Args:
            signal_type: One of "entry", "exit", "portfolio_target_achieved", "breadth"
            asset: Optional asset name
            function: Optional function name
            
        Returns:
            Dictionary with summary info (available dates, row counts, etc.)
        """
        base_dir = self._get_signal_type_dir(signal_type)
        
        if signal_type == "breadth":
            csv_files = list(base_dir.glob("*.csv"))
            return {
                "signal_type": signal_type,
                "num_files": len(csv_files),
                "dates": [f.stem for f in sorted(csv_files)]
            }
        
        # For entry/exit/portfolio_target_achieved
        if asset and function:
            function_dir = base_dir / asset / function
            if function_dir.exists():
                csv_files = list(function_dir.glob("*.csv"))
                return {
                    "signal_type": signal_type,
                    "asset": asset,
                    "function": function,
                    "num_files": len(csv_files),
                    "dates": [f.stem for f in sorted(csv_files)]
                }
        
        return {"signal_type": signal_type, "error": "Invalid parameters"}

    def add_data_to_consolidated_csv(
        self,
        signal_type: str,
        new_data: pd.DataFrame,
        deduplicate: bool = True
    ) -> bool:
        """
        Add new data to a consolidated CSV file with optional deduplication.

        Args:
            signal_type: One of "entry", "exit", "portfolio_target_achieved", "breadth"
            new_data: DataFrame with new data to add
            deduplicate: Whether to deduplicate based on unique keys

        Returns:
            True if successful, False otherwise
        """
        csv_path = self._get_consolidated_csv_path(signal_type)

        try:
            # Read existing data if file exists
            if csv_path.exists():
                existing_data = pd.read_csv(csv_path, encoding=CSV_ENCODING)
            else:
                existing_data = pd.DataFrame()

            # Add metadata columns if needed
            if signal_type != "breadth":
                # For entry/exit/portfolio_target_achieved, add metadata if not present
                if 'symbol' not in new_data.columns and 'symbol' in existing_data.columns:
                    # Try to extract symbol from existing data patterns
                    pass  # Will be handled by calling code
            else:
                # For breadth, add date metadata if not present
                if 'date' not in new_data.columns and 'date' in existing_data.columns:
                    pass  # Will be handled by calling code

            # Combine existing and new data
            combined_data = pd.concat([existing_data, new_data], ignore_index=True)

            if deduplicate and not combined_data.empty:
                combined_data = self._deduplicate_data_preserve_origination(combined_data, signal_type)

            # Remove metadata columns before saving (they're only used for deduplication)
            if signal_type == "breadth":
                # For breadth data, remove date and signal_type_meta
                metadata_columns = ['date', 'signal_type_meta']
            else:
                # For other signal types, remove standard metadata columns
                metadata_columns = ['symbol', 'function', 'signal_date', 'signal_type', 'interval', 'asset_name', 'signal_type_meta']

            columns_to_drop = [col for col in metadata_columns if col in combined_data.columns]
            if columns_to_drop:
                combined_data = combined_data.drop(columns=columns_to_drop)

            # Save back to CSV
            combined_data.to_csv(csv_path, index=False, encoding=CSV_ENCODING)
            logger.info(f"✅ Added {len(new_data)} rows to {signal_type} consolidated CSV (total: {len(combined_data)} rows)")

            return True

        except Exception as e:
            logger.error(f"Error adding data to {signal_type} consolidated CSV: {e}")
            return False

    def _deduplicate_data_preserve_origination(self, data: pd.DataFrame, signal_type: str) -> pd.DataFrame:
        """
        Deduplicate data based on unique keys for each signal type.

        Args:
            data: DataFrame to deduplicate
            signal_type: Signal type to determine deduplication key

        Returns:
            Deduplicated DataFrame
        """
        if data.empty:
            return data

        # Create unique keys
        if signal_type == "breadth":
            # For breadth: date + function
            if 'date' in data.columns and 'Function' in data.columns:
                data['unique_key'] = data.apply(
                    lambda row: f"{row['date']}|{row.get('Function', 'Unknown')}",
                    axis=1
                )
            else:
                logger.warning("Cannot deduplicate breadth data: missing date or Function columns")
                return data
        else:
            # For entry/exit/portfolio_target_achieved: symbol + signal_type + asset_name + function + interval + Signal Open Price
            required_cols = ['symbol', 'signal_type', 'asset_name', 'function', 'interval', 'Signal Open Price']
            if all(col in data.columns for col in required_cols):
                data['unique_key'] = data.apply(
                    lambda row: f"{row['symbol']}|{row['signal_type']}|{row['asset_name']}|{row['function']}|{row['interval']}|{row['Signal Open Price']}",
                    axis=1
                )
            else:
                logger.warning(f"Cannot deduplicate {signal_type} data: missing required columns {required_cols}")
                return data

        # Remove duplicates, keeping the last (most recent) occurrence
        original_count = len(data)
        data = data.drop_duplicates(subset=['unique_key'], keep='last')
        
        removed_count = original_count - len(data)
        if removed_count > 0:
            logger.info(f"🗑️ Removed {removed_count} duplicate rows from {signal_type} data")
            removed_count = original_count - len(data)
            if removed_count > 0:
                logger.info(f"🗑️ Removed {removed_count} duplicate rows from {signal_type} data")

        data = data.drop(columns=['unique_key'])

        return data

    def _deduplicate_data(self, data: pd.DataFrame, signal_type: str) -> pd.DataFrame:
        """
        Deduplicate data based on unique keys for each signal type.

        Args:
            data: DataFrame to deduplicate
            signal_type: Signal type to determine deduplication key

        Returns:
            Deduplicated DataFrame
        """
        if data.empty:
            return data

        if signal_type == "breadth":
            # For breadth: date + function
            if 'date' in data.columns and 'Function' in data.columns:
                data['unique_key'] = data.apply(
                    lambda row: f"{row['date']}|{row.get('Function', 'Unknown')}",
                    axis=1
                )
            else:
                logger.warning("Cannot deduplicate breadth data: missing date or Function columns")
                return data
        else:
            # For entry/exit/portfolio_target_achieved: symbol + signal_type + asset_name + function + interval + Signal Open Price
            required_cols = ['symbol', 'signal_type', 'asset_name', 'function', 'interval', 'Signal Open Price']
            if all(col in data.columns for col in required_cols):
                data['unique_key'] = data.apply(
                    lambda row: f"{row['symbol']}|{row['signal_type']}|{row['asset_name']}|{row['function']}|{row['interval']}|{row['Signal Open Price']}",
                    axis=1
                )
            else:
                logger.warning(f"Cannot deduplicate {signal_type} data: missing required columns {required_cols}")
                return data

        # Remove duplicates, keeping the last (most recent) occurrence
        original_count = len(data)
        data = data.drop_duplicates(subset=['unique_key'], keep='last')
        data = data.drop(columns=['unique_key'])

        removed_count = original_count - len(data)
        if removed_count > 0:
            logger.info(f"🗑️ Removed {removed_count} duplicate rows from {signal_type} data")

        return data


if __name__ == "__main__":
    # Test the data fetcher
    fetcher = SmartDataFetcher()
    
    # Test 1: Fetch entry data for TSM
    print("\n" + "="*60)
    print("TEST 1: Fetch entry data for TSM")
    print("="*60)
    
    result = fetcher.fetch_data(
        signal_types=["entry"],
        required_columns=["Symbol", "Signal", "Current Mark to Market and Holding Period"],
        assets=["TSM"],
        from_date="2025-10-14",
        to_date="2025-10-14"
    )
    
    if "entry" in result:
        print(f"\nFetched {len(result['entry'])} rows")
        print(result['entry'].head())
    
    # Test 2: Fetch breadth data
    print("\n" + "="*60)
    print("TEST 2: Fetch breadth data")
    print("="*60)
    
    result = fetcher.fetch_data(
        signal_types=["breadth"],
        required_columns=["Function", "Bullish Asset vs Total Asset (%)", "Date"],
        from_date="2025-10-14"
    )
    
    if "breadth" in result:
        print(f"\nFetched {len(result['breadth'])} rows")
        print(result['breadth'].head())
