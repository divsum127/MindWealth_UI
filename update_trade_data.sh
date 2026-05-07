#!/bin/bash

# Script to copy trade data files and push to GitHub
# V2 - targets /home/ubuntu/uiv2/MindWealth_UI/trade_store

set -e  # Exit on any error

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🔄 Starting trade data update process (v2)..."
echo "📁 Working directory: $SCRIPT_DIR"

# Define source directories (shared data from MindWealth engine)
CACHE_US_DIR="/home/ubuntu/MindWealth/cache/US"
SOURCE_TRADE_DIR="/home/ubuntu/MindWealth/trade_store/US"
SOURCE_VIRTUAL_TRADING_DIR="/home/ubuntu/MindWealth/trade_store"

# Define target directories (inside this uiv2 app)
TARGET_STOCK_DATA_DIR="$SCRIPT_DIR/trade_store/stock_data"
TARGET_TRADE_DIR="$SCRIPT_DIR/trade_store/US"

# Validate source directories
if [ ! -d "$CACHE_US_DIR" ]; then
    echo "❌ Error: Cache US directory $CACHE_US_DIR does not exist!"
    exit 1
fi

if [ ! -d "$SOURCE_TRADE_DIR" ]; then
    echo "❌ Error: Trade store directory $SOURCE_TRADE_DIR does not exist!"
    exit 1
fi

# Validate target directories
if [ ! -d "$TARGET_STOCK_DATA_DIR" ]; then
    echo "❌ Error: Target stock data directory $TARGET_STOCK_DATA_DIR does not exist!"
    exit 1
fi

if [ ! -d "$TARGET_TRADE_DIR" ]; then
    echo "❌ Error: Target trade directory $TARGET_TRADE_DIR does not exist!"
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

# Sync stock data CSV files from cache/US to stock_data (delete then copy)
echo "📊 Syncing stock data CSV files from cache/US to trade_store/stock_data..."

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

        [ -f "$dest_file" ] && rm -f "$dest_file"

        cp "$src_file" "$dest_file"
        copied_count=$((copied_count + 1))
    done
    echo "✅ Synced $copied_count stock CSV file(s)"
fi
shopt -u nullglob

# Copy trade signal CSV files (skip legacy ones)
echo "📊 Copying trade signal CSV files..."
for file in "$SOURCE_TRADE_DIR"/*.csv; do
    if [ -f "$file" ]; then
        filename=$(basename "$file")
        if should_skip_trade_csv "$filename"; then
            echo "⏭️  Skipping legacy UI CSV: $filename"
            continue
        fi
        cp "$file" "$TARGET_TRADE_DIR/"
    fi
done

# Remove legacy standalone UI CSVs from target if present from older syncs
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

# Copy trade signal TXT files
echo "📄 Copying trade signal TXT files..."
cp "$SOURCE_TRADE_DIR"/*.txt "$TARGET_TRADE_DIR/" 2>/dev/null || echo "⚠️  No TXT files found in trade_store/US"

# Copy data_fetch_datetime.json
echo "📅 Copying data fetch datetime JSON file..."
if [ -f "$SOURCE_TRADE_DIR/data_fetch_datetime.json" ]; then
    cp "$SOURCE_TRADE_DIR/data_fetch_datetime.json" "$TARGET_TRADE_DIR/data_fetch_datetime.json"
    echo "✅ Copied data_fetch_datetime.json"
else
    echo "⚠️  data_fetch_datetime.json not found in $SOURCE_TRADE_DIR"
fi

# Clean up old dated CSV files — keep only the latest for each base name
echo "🧹 Cleaning up old dated CSV files (keeping only latest for each base name)..."
cd "$TARGET_TRADE_DIR" || { echo "❌ Error: Cannot cd to $TARGET_TRADE_DIR"; exit 1; }

files_before=$(find . -maxdepth 1 -type f -name "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_*.csv" 2>/dev/null | wc -l | tr -d ' ')

while IFS= read -r base_name; do
    [ -z "$base_name" ] && continue
    matching_files=$(find . -maxdepth 1 -type f -name "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_${base_name}" 2>/dev/null)
    if [ -n "$matching_files" ]; then
        latest_file=$(echo "$matching_files" | sed 's|^\./||' | sort -r | head -1)
        if [ -n "$latest_file" ] && [ -f "$latest_file" ]; then
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

files_after=$(find . -maxdepth 1 -type f -name "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_*.csv" 2>/dev/null | wc -l | tr -d ' ')
deleted_count=$((files_before - files_after))
if [ $deleted_count -gt 0 ]; then
    echo "✅ Deleted $deleted_count old dated CSV file(s)"
else
    echo "ℹ️  No old dated CSV files to delete"
fi

# Clean up old dated TXT files — keep only the latest for each base name
txt_files_before=$(find . -maxdepth 1 -type f -name "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_*.txt" 2>/dev/null | wc -l | tr -d ' ')

while IFS= read -r base_name; do
    [ -z "$base_name" ] && continue
    matching_files=$(find . -maxdepth 1 -type f -name "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_${base_name}" 2>/dev/null)
    if [ -n "$matching_files" ]; then
        latest_file=$(echo "$matching_files" | sed 's|^\./||' | sort -r | head -1)
        if [ -n "$latest_file" ] && [ -f "$latest_file" ]; then
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

txt_files_after=$(find . -maxdepth 1 -type f -name "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_*.txt" 2>/dev/null | wc -l | tr -d ' ')
deleted_txt_count=$((txt_files_before - txt_files_after))
if [ $deleted_txt_count -gt 0 ]; then
    echo "✅ Deleted $deleted_txt_count old dated TXT file(s)"
fi

cd "$SCRIPT_DIR"

# Copy virtual trading CSV files (from trade_store root, not US subfolder)
echo "📊 Copying virtual trading CSV files..."
for vt_file in virtual_trading_long.csv virtual_trading_short.csv breadth_us.csv; do
    if [ -f "$SOURCE_VIRTUAL_TRADING_DIR/$vt_file" ]; then
        cp "$SOURCE_VIRTUAL_TRADING_DIR/$vt_file" "$TARGET_TRADE_DIR/$vt_file"
        echo "✅ Copied $vt_file"
    else
        echo "⚠️  $vt_file not found in $SOURCE_VIRTUAL_TRADING_DIR"
    fi
done

# Convert signals to chatbot data structure using uiv2 venv
echo "🔄 Converting signals to chatbot data structure..."
echo "🐍 Activating virtual environment (.venv)..."
source "$SCRIPT_DIR/.venv/bin/activate"
python3 "$SCRIPT_DIR/chatbot/convert_signals_to_data_structure.py"

# Update monitored trades with latest prices and exit conditions
echo "⭐ Updating monitored trades with latest prices and exit conditions..."
python3 -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR')
from src.utils.monitored_trades import update_monitored_trades_prices, update_monitored_trades_with_outstanding
from src.utils.data_loader import load_data_from_file
import os
import glob

print('  📊 Updating current prices from stock data...')
update_monitored_trades_prices()

print('  🔍 Checking for exit signals in outstanding signals...')
outstanding_files = sorted(glob.glob('$SCRIPT_DIR/trade_store/US/*_outstanding_signal.csv'))
if outstanding_files:
    latest_file = outstanding_files[-1]
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

# Git operations
echo "🔄 Adding files to git..."
git -C "$SCRIPT_DIR" add .

echo "💾 Committing changes..."
git -C "$SCRIPT_DIR" commit -m "Update trade data: CSV files from cache and trade_store/US"

echo "🚀 Pushing to GitHub..."
git -C "$SCRIPT_DIR" push origin main

echo "✅ All done! Data updated and pushed to GitHub."
