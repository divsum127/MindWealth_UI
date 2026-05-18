#!/bin/bash

# Script to copy trade data files and push to GitHub
# Copies from the MindWealth engine tree into this repo's trade_store/

set -e  # Exit on any error

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🔄 Starting trade data update process..."
echo "📁 Working directory: $SCRIPT_DIR"

# MindWealth data sources (absolute — uiv2/MindWealth_UI is not beside ../MindWealth)
MINDWEALTH_ROOT="${MINDWEALTH_ROOT:-/home/ubuntu/MindWealth}"
CACHE_US_DIR="$MINDWEALTH_ROOT/cache/US"
TARGET_STOCK_DATA_DIR="trade_store/stock_data"
SOURCE_TRADE_DIR="$MINDWEALTH_ROOT/trade_store/US"
SOURCE_VIRTUAL_TRADING_DIR="$MINDWEALTH_ROOT/trade_store"
TARGET_TRADE_DIR="trade_store/US"

# Check if cache US directory exists (source for stock_data)
if [ ! -d "$CACHE_US_DIR" ]; then
    echo "❌ Error: Cache US directory $CACHE_US_DIR does not exist!"
    exit 1
fi

# Check if trade store source directory exists
if [ ! -d "$SOURCE_TRADE_DIR" ]; then
    echo "❌ Error: Trade store directory $SOURCE_TRADE_DIR does not exist!"
    exit 1
fi

should_skip_trade_csv() {
    local filename="$1"

    # Legacy standalone UI CSVs replaced by combined reports
    if [[ $filename =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}_(forward_testing|latest_performance|forward_backtesting|Horizontal)\.csv$ ]]; then
        return 0
    fi

    case "$filename" in
        forward_testing.csv|latest_performance.csv|forward_backtesting.csv|Horizontal.csv)
            return 0
            ;;
    esac

    return 1
}

# Sync stock data CSV files from cache/US to stock_data (file-by-file).
# For each CSV in cache/US: delete the destination file (if present), then copy.
echo "📊 Syncing stock data CSV files from cache/US to trade_store/stock_data..."
if [ ! -d "$TARGET_STOCK_DATA_DIR" ]; then
    echo "❌ Error: Target stock data directory $TARGET_STOCK_DATA_DIR does not exist!"
    exit 1
fi

shopt -s nullglob
cache_csv_files=("$CACHE_US_DIR"/*.csv)
if [ ${#cache_csv_files[@]} -eq 0 ]; then
    echo "⚠️  No CSV files found in $CACHE_US_DIR"
else
    copied_count=0
    for src_file in "${cache_csv_files[@]}"; do
        [ -f "$src_file" ] || continue
        base_name="$(basename "$src_file")"
        dest_file="$TARGET_STOCK_DATA_DIR/$base_name"

        if [ -f "$dest_file" ]; then
            rm -f "$dest_file"
        fi

        cp "$src_file" "$dest_file"
        copied_count=$((copied_count + 1))
    done
    echo "✅ Synced $copied_count stock CSV file(s) (delete then copy)"
fi
shopt -u nullglob

# Copy all CSV files from trade_store/US
# Skip legacy standalone UI CSVs that are now replaced by combined reports
echo "📊 Copying trade signal CSV files..."
for file in "$SOURCE_TRADE_DIR"/*.csv; do
    if [ -f "$file" ]; then
        filename=$(basename "$file")
        if should_skip_trade_csv "$filename"; then
            echo "⏭️  Skipping legacy UI CSV: $filename (covered by combined report flow)"
            continue
        fi
        cp "$file" "$TARGET_TRADE_DIR"/
    fi
done

# Remove legacy standalone UI CSVs from target if they already exist from older syncs
echo "🧹 Removing legacy standalone UI CSV files from target..."
shopt -s nullglob
legacy_ui_files=(
    "$TARGET_TRADE_DIR"/forward_testing.csv
    "$TARGET_TRADE_DIR"/latest_performance.csv
    "$TARGET_TRADE_DIR"/forward_backtesting.csv
    "$TARGET_TRADE_DIR"/Horizontal.csv
    "$TARGET_TRADE_DIR"/[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_forward_testing.csv
    "$TARGET_TRADE_DIR"/[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_latest_performance.csv
    "$TARGET_TRADE_DIR"/[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_forward_backtesting.csv
    "$TARGET_TRADE_DIR"/[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_Horizontal.csv
)
removed_legacy_count=0
for legacy_file in "${legacy_ui_files[@]}"; do
    [ -e "$legacy_file" ] || continue
    rm -f "$legacy_file"
    echo "  🗑️  Removed legacy UI CSV: $(basename "$legacy_file")"
    removed_legacy_count=$((removed_legacy_count + 1))
done
if [ $removed_legacy_count -eq 0 ]; then
    echo "ℹ️  No legacy standalone UI CSV files found in target"
else
    echo "✅ Removed $removed_legacy_count legacy standalone UI CSV file(s)"
fi
shopt -u nullglob

# Copy all TXT files from trade_store/US
echo "📄 Copying trade signal TXT files..."
cp "$SOURCE_TRADE_DIR"/*.txt "$TARGET_TRADE_DIR"/ 2>/dev/null || echo "⚠️  No TXT files found in trade_store/US"

# Copy data_fetch_datetime.json file
echo "📅 Copying data fetch datetime JSON file..."
if [ -f "$SOURCE_TRADE_DIR/data_fetch_datetime.json" ]; then
    cp "$SOURCE_TRADE_DIR/data_fetch_datetime.json" "$TARGET_TRADE_DIR/data_fetch_datetime.json"
    echo "✅ Copied data_fetch_datetime.json"
else
    echo "⚠️  data_fetch_datetime.json not found in $SOURCE_TRADE_DIR"
fi

# Clean up old dated CSV and TXT files after copying new ones
# This ensures we keep only the latest dated file for each base name
echo "🧹 Cleaning up old dated files (keeping only latest for each base name)..."
if [ -d "$TARGET_TRADE_DIR" ]; then
    cd "$TARGET_TRADE_DIR" || { echo "❌ Error: Cannot cd to $TARGET_TRADE_DIR"; exit 1; }
    
    # Process CSV files: Find latest file for each base name and delete older ones
    # Count files before cleanup
    files_before=$(find . -maxdepth 1 -type f -name "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_*.csv" 2>/dev/null | wc -l | tr -d ' ')
    
    # Get all unique base names from dated CSV files
    # Use process substitution to avoid subshell issues
    while IFS= read -r base_name; do
        # Skip empty lines
        [ -z "$base_name" ] && continue

        # Find all files for this base name using find (more reliable than glob)
        matching_files=$(find . -maxdepth 1 -type f -name "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_${base_name}" 2>/dev/null)
                
        if [ -n "$matching_files" ]; then
            # Get the latest file (first when sorted descending by filename)
            latest_file=$(echo "$matching_files" | sed 's|^\./||' | sort -r | head -1)
            
            if [ -n "$latest_file" ] && [ -f "$latest_file" ]; then
                # Delete all other files with the same base name
                echo "$matching_files" | sed 's|^\./||' | while IFS= read -r file; do
                    [ -z "$file" ] && continue
                    if [ -f "$file" ] && [ "$file" != "$latest_file" ]; then
                        rm -f "$file" && echo "  🗑️  Deleted old file: $file (keeping $latest_file)"
                    fi
                done
            fi
        fi
    done < <(find . -maxdepth 1 -type f -name "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_*.csv" 2>/dev/null | \
        sed 's|^\./||' | \
        sed 's/^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_//' | \
        sort -u)
    
    # Count files after cleanup
    files_after=$(find . -maxdepth 1 -type f -name "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_*.csv" 2>/dev/null | wc -l | tr -d ' ')
    deleted_count=$((files_before - files_after))
    
    if [ $deleted_count -gt 0 ]; then
        echo "✅ Deleted $deleted_count old dated CSV file(s) (kept latest for each base name)"
    else
        echo "ℹ️  No old dated CSV files to delete (all files are already the latest)"
    fi
    
    # Process TXT files the same way
    # Count files before cleanup
    txt_files_before=$(find . -maxdepth 1 -type f -name "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_*.txt" 2>/dev/null | wc -l | tr -d ' ')
    
    # Get all unique base names from dated TXT files
    while IFS= read -r base_name; do
        # Skip empty lines
        [ -z "$base_name" ] && continue
        
        # Find all files for this base name using find (more reliable than glob)
        matching_files=$(find . -maxdepth 1 -type f -name "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_${base_name}" 2>/dev/null)
                
        if [ -n "$matching_files" ]; then
            # Get the latest file (first when sorted descending by filename)
            latest_file=$(echo "$matching_files" | sed 's|^\./||' | sort -r | head -1)
            
            if [ -n "$latest_file" ] && [ -f "$latest_file" ]; then
                # Delete all other files with the same base name
                echo "$matching_files" | sed 's|^\./||' | while IFS= read -r file; do
                    [ -z "$file" ] && continue
                    if [ -f "$file" ] && [ "$file" != "$latest_file" ]; then
                        rm -f "$file" && echo "  🗑️  Deleted old file: $file (keeping $latest_file)"
                    fi
                done
            fi
        fi
    done < <(find . -maxdepth 1 -type f -name "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_*.txt" 2>/dev/null | \
        sed 's|^\./||' | \
        sed 's/^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_//' | \
        sort -u)
    
    # Count files after cleanup
    txt_files_after=$(find . -maxdepth 1 -type f -name "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_*.txt" 2>/dev/null | wc -l | tr -d ' ')
    deleted_txt_count=$((txt_files_before - txt_files_after))
    
    if [ $deleted_txt_count -gt 0 ]; then
        echo "✅ Deleted $deleted_txt_count old dated TXT file(s) (kept latest for each base name)"
    fi
    
    cd "$SCRIPT_DIR" || true
else
    echo "⚠️  Warning: Target trade directory $TARGET_TRADE_DIR does not exist, skipping cleanup"
fi

# Copy virtual trading CSV files specifically (from trade_store root, not US subfolder)
echo "📊 Copying virtual trading CSV files..."
if [ -f "$SOURCE_VIRTUAL_TRADING_DIR/virtual_trading_long.csv" ]; then
    cp "$SOURCE_VIRTUAL_TRADING_DIR/virtual_trading_long.csv" "$TARGET_TRADE_DIR/virtual_trading_long.csv"
    echo "✅ Copied virtual_trading_long.csv → virtual_trading_long.csv"
else
    echo "⚠️  virtual_trading_long.csv not found in $SOURCE_VIRTUAL_TRADING_DIR"
fi

if [ -f "$SOURCE_VIRTUAL_TRADING_DIR/virtual_trading_short.csv" ]; then
    cp "$SOURCE_VIRTUAL_TRADING_DIR/virtual_trading_short.csv" "$TARGET_TRADE_DIR/virtual_trading_short.csv"
    echo "✅ Copied virtual_trading_short.csv → virtual_trading_short.csv"
else
    echo "⚠️  virtual_trading_short.csv not found in $SOURCE_VIRTUAL_TRADING_DIR"
fi

# Copy breadth_us.csv from trade_store to trade_store/US
echo "📊 Copying breadth_us.csv..."
if [ -f "$SOURCE_VIRTUAL_TRADING_DIR/breadth_us.csv" ]; then
    cp "$SOURCE_VIRTUAL_TRADING_DIR/breadth_us.csv" "$TARGET_TRADE_DIR/breadth_us.csv"
    echo "✅ Copied breadth_us.csv → breadth_us.csv"
else
    echo "⚠️  breadth_us.csv not found in $SOURCE_VIRTUAL_TRADING_DIR"
fi


# Convert signals to data structure
echo "🔄 Converting signals to chatbot data structure..."
echo "🐍 Activating virtual environment..."
if [ -f "$SCRIPT_DIR/.venv/bin/activate" ]; then
    source "$SCRIPT_DIR/.venv/bin/activate"
elif [ -f "$SCRIPT_DIR/venv/bin/activate" ]; then
    source "$SCRIPT_DIR/venv/bin/activate"
else
    echo "❌ Error: No .venv or venv found in $SCRIPT_DIR"
    exit 1
fi
python3 chatbot/convert_signals_to_data_structure.py

# Update monitored trades with latest prices and exit conditions
echo "⭐ Updating monitored trades with latest prices and exit conditions..."
python3 -c "
import sys
sys.path.insert(0, '.')
from src.utils.monitored_trades import update_monitored_trades_prices, update_monitored_trades_with_outstanding
from src.utils.data_loader import load_data_from_file
import os
import glob

# Update prices from stock data
print('  📊 Updating current prices from stock data...')
update_monitored_trades_prices()

# Update exit conditions from outstanding signals
print('  🔍 Checking for exit signals in outstanding signals...')
# Find the latest outstanding signal file with date prefix
outstanding_files = sorted(glob.glob('./trade_store/US/*_outstanding_signal.csv'))
if outstanding_files:
    latest_file = outstanding_files[-1]  # Get the latest dated file
    print(f'  📁 Using file: {os.path.basename(latest_file)}')
    outstanding_df = load_data_from_file(latest_file, 'Outstanding Signals')
    if not outstanding_df.empty:
        update_monitored_trades_with_outstanding(outstanding_df)
        print('  ✅ Monitored trades updated successfully!')
    else:
        print('  ⚠️  Outstanding signals file is empty')
else:
    print('  ⚠️  Outstanding signals file not found')
"

# Conviction Engine: fundamentals + conviction on daily signal reports + dated archive
echo "📈 Running Conviction Engine daily pipeline..."
python3 scripts/run_conviction_engine_daily.py --fundamentals-mode daily
echo "✅ Conviction Engine daily pipeline completed (see conviction_store/daily/)"

# Git operations
echo "🔄 Adding files to git..."
git add .

# Commit changes
echo "💾 Committing changes..."
git commit -m "Update trade data: CSV files from cache and trade_store/US"

# Push to GitHub
echo "🚀 Pushing to GitHub..."
git push origin main

echo "✅ All done! Data updated and pushed to GitHub."