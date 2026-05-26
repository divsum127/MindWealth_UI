"""
Streamlit chatbot sidebar one-click button prompts.
"""

from __future__ import annotations

ANALYZE_ASSET_PROMPT_TEMPLATE = """Please run a deep dive on {asset} covering all signals recorded for the analysis window. Use the specified entry and / or exit-date range as the filter.

Date range: {start_date} to {end_date}

## Data to use (already loaded in this message)

The app has **already merged** outstanding, entry, all_signal, and virtual_trading rows for {asset} into the JSON blocks below. **Do not** try to open files on disk or treat `trade_store/US` paths as something you must read yourself.

**Primary sources (use these only):**
1. **=== ENTRY SIGNALS (JSON) ===** — all open positions (`record_count` rows). Every row is a distinct signal unless Function, Interval, Direction, and entry date are identical.
2. **=== EXIT SIGNALS (JSON) ===** — closed trades for the window.

**Column usage (from each JSON row):**
- **MTM / holding / today:** cite **Current Mark to Market and Holding Period**, **Today Trading Date/Price[$], Today Price vs Signal**, and **Trading Days between Signal and Today Date** exactly as exported — do not recompute when present.
- **Take profit / stop loss:** from the **Targets (...)** and **Stop Loss (...)** columns on the **same row** as entry (Pivot | Avg | Func | Horizontal | F-Stack 1 | F-Stack 2 | EMA 200, etc.). Dollar values only; skip slots marked "No target", "No Horizontal", "No stop loss", etc.

**Completeness (mandatory):**
- Retrieve and list **all** open signals present in ENTRY JSON — including rows with NaN Targets/Stop or Virtual Trading notes (e.g. FRACTAL TRACK daily 2026-04-28, PULSEGAUGE 2026-04-23, TRENDPULSE 2026-04-14).
- Start with: **Open signal inventory: N rows** (N = ENTRY `record_count`).
- Do not omit a row because Targets/Stop are missing; show Entry + MTM and state ladders are not in export.

## Open signals (tabular — mandatory)

Present **all** ENTRY JSON rows in **Markdown tables** only (no bullet lists for signal rows). Sort rows: entry dates inside [{start_date}, {end_date}] first (newest first), then older still-open rows.

**Table 1 — Open signal summary** (one row per distinct signal):

| Function | Interval | Direction | Entry Date | Entry $ | MTM | Days Held | Today $ | Status |
|----------|----------|-------------|------------|---------|-----|-----------|---------|--------|

- **MTM**, **Days Held**, **Today $:** from **Current Mark to Market and Holding Period**, **Trading Days between Signal and Today Date**, **Today Trading Date/Price[$]** (same row).
- **Status:** Early | Approaching avg | Late | Beyond max (use Backtested Holding Period Max/Min/Avg when available).
- Include every ENTRY JSON row; use `—` for missing cells. Never drop a row because Targets/Stop are NaN.

**Table 2 — Open signal take profit & stop loss** (same rows, same order as Table 1; values from the **same** JSON row):

| Function | Interval | Entry Date | TP Pivot | TP Avg | TP Func | TP Horiz | TP FS1 | TP FS2 | TP EMA200 | SL Extrema | SL Horiz | SL FS1 | SL FS2 | SL FT1 | SL FT2 | SL EMA200 |
|----------|----------|------------|----------|--------|--------|----------|-------|-------|-----------|------------|----------|-------|-------|-------|-------|-----------|

- Dollar values only; use `—` for empty / "No target" / "No stop loss" slots.
- Note breached stops in Table 1 **Status** or a brief footnote if SIGNAL LEVEL VALIDATION is present.
- If the entire Targets/Stop row is NaN: still list the row in both tables; put `—` in level columns.

## Exited signals (tabular — mandatory)

Present **all** EXIT JSON rows in one **Markdown table** (one row per exit):

| Function | Interval | Direction | Entry Date | Entry $ | Exit Date | Exit $ | Result % | Held Days |
|----------|----------|-------------|------------|---------|-----------|--------|----------|-----------|

- **Result %** and **Held Days:** from **Current Mark to Market and Holding Period** and exit fields on the same row.
- Use `—` only when a field is truly absent in JSON.

## Analysis (concise — written once, not per signal)

1. **Contradictions** — genuine conflicts only (e.g. monthly short vs daily longs); one sentence each.
2. **Timeframe alignment** — one short paragraph (daily / weekly / monthly).
3. **Stance** — **BUY** / **HOLD** / **SELL** with at most 3 bullet rationale.
4. **Key risks & triggers** — at most 5 bullets (late holds, stops to watch, levels that change stance).

## Rules

- Use only signals verifiable from ENTRY/EXIT JSON (and Streamlit-loaded exports represented there). Do not fabricate rows.
- Do not repeat full signal ladders in the Analysis section — reference by function + interval + entry date.
- Row binding: Entry, take-profit, and stop-loss for one position must come from the **same** JSON row (same signal date and Signal Open Price).
- Use clean Markdown (`##`, tables, bullets only in Analysis). Do **not** use box-drawing lines (────) or excessive emoji.
- Open and exited signal details must be **tables**, not prose paragraphs or one-line summaries per signal.
- Long: active stops should be below today price; Short: above today price (see SIGNAL LEVEL VALIDATION when provided).

Date Range: {start_date} to {end_date}"""

ANALYZE_ASSET_PROMPT_LEGACY_TEMPLATE = """Please run a deep dive on {asset} covering all signals recorded over the past few weeks. Use the specified entry and / or exit-date range as the filter.

For **open / outstanding entry signals**, use the latest **Outstanding Signal report** CSV under ``trade_store/US`` (e.g. dated ``*_outstanding_signal.csv``) as loaded by the app: cite **Current Mark to Market and Holding Period**, **Today Trading Date/Price**, and **Trading Days between Signal and Today Date** exactly as in that export — do not recompute MTM or holding when those columns are present.

Retrieve and list all signals for this period, showing each function, timeframe, and direction (long/short).

Identify contradictions, such as:

Short signals that have already hit targets or registered exits while higher-interval (e.g., monthly-candle) functions are still showing active longs.

Overlaps between exit dates on short-term signals and open longer-term entries.

Assess alignment between short-term and medium-term outlooks based strictly on the verified signals in the Streamlit reports.

Determine stance — whether the current setup indicates a Buy, Hold, or Sell — using only the pre-computed signal data and the historically observed holding periods for each function.

Important:

Do not fabricate or infer new signals. Use only signals verifiable from the existing Streamlit reports and outstanding-signal export.

Date Range: {start_date} to {end_date}"""

SIGNAL_INSIGHTS_PROMPT_TEMPLATE = """Please analyze all ENTRY signals across all assets and functions for the date range {start_date} to {end_date}.

Focus on identifying high-quality signals that meet the following criteria:

1. **High Sharpe Ratio**: Strategy Sharpe Ratio > 1.5
2. **High Win Rate (Full History)**: Win Rate > 80% based on full historical testing
3. **Latest Performance Win Rate**: Win Rate > 85% for past 4 years
4. **Forward Testing Win Rate**: Win Rate > 65% from forward testing signal data

For each qualifying signal, provide:
- Asset symbol
- Function name
- Timeframe/Interval
- Signal direction (Long/Short)
- Signal date
- Strategy Sharpe Ratio
- Win Rate (full history, latest performance, and forward testing if available)
- Any other relevant performance metrics

Organize the results by:
1. Highest Sharpe Ratio signals first
2. Then by highest Win Rate
3. Highlight any signals with high Forward Testing Win Rate (>65%)

Important:
- Only analyze ENTRY signals (signals that are still open, no exit yet)
- Use only signals verifiable from the existing Streamlit reports
- Do not fabricate or infer new signals
- Focus on signals that meet ALL or MOST of the quality criteria above

Date Range: {start_date} to {end_date}"""

BREADTH_ANALYSIS_PROMPT_TEMPLATE = """Please analyze Signal Breadth Indicator (SBI) trade-arrival data for the date range {start_date} to {end_date}.

Use the BREADTH SIGNALS JSON block. Primary metrics (S&P 500 universe):
- Total New Long Signal / Total New Short Signal
- Last 6 Month Top 10 Percentile No of Long/Short Signal (6-month busy-day thresholds)
- Today Long Signal Percentile From Top (Last 6 Month)
- Today Short Signal Percentile From Top (Last 6 Month)

For market-wide analysis, prioritize Function = "Combined (TrendPulse + DeltaDrift + BandMatrix)"; also break down TRENDPULSE, DELTADRIFT, and BAND MATRIX.

Percentile semantics: "Today ... Percentile From Top" = how close today is to the busiest signal day in the last 6 months (10 ≈ top 10% activity; low values ≈ quiet days).

Focus on:

1. **Extreme SBI days (Combined row)**:
   - Days in the **bottom 10%** of the date range by Today Long Signal Percentile From Top (quiet long-signal days)
   - Days in the **top 10%** by that metric (busy long-signal days)
   - Same for Today Short Signal Percentile From Top where relevant
   - Show signal counts vs 6-month top-10% thresholds for those days

2. **Per-function SBI patterns**:
   - Compare TRENDPULSE, DELTADRIFT, BAND MATRIX, and Combined
   - Note divergences (e.g. one strategy busy while Combined is quiet)

3. **Low-activity / reversal context**:
   - List days where long percentile is in the bottom decile of the selected range
   - Explain what low long-signal percentile may indicate (reduced bullish participation; possible consolidation)

4. **Summary**:
   - Total days with data in range
   - Count of bottom/top decile days (long and short percentiles)
   - Average Total New Long/Short Signal (Combined row) for the period
   - Trends across the range

For each highlighted day provide: Date, Function, Total New Long/Short Signal, both percentile columns, 6-month thresholds, and brief interpretation.

Important:
- Use only data from the provided BREADTH SIGNALS JSON (and sbi_schema_note if present)
- Do not fabricate values; if a column is missing for a date, say so
- Do not use legacy Bullish Asset/Signal % columns unless populated

Date Range: {start_date} to {end_date}"""


def format_analyze_asset_prompt(asset: str, start_date: str, end_date: str) -> str:
    return ANALYZE_ASSET_PROMPT_TEMPLATE.format(
        asset=asset, start_date=start_date, end_date=end_date
    )


def format_analyze_asset_prompt_legacy(asset: str, start_date: str, end_date: str) -> str:
    return ANALYZE_ASSET_PROMPT_LEGACY_TEMPLATE.format(
        asset=asset, start_date=start_date, end_date=end_date
    )


def format_signal_insights_prompt(start_date: str, end_date: str) -> str:
    return SIGNAL_INSIGHTS_PROMPT_TEMPLATE.format(
        start_date=start_date, end_date=end_date
    )


def format_breadth_analysis_prompt(start_date: str, end_date: str) -> str:
    return BREADTH_ANALYSIS_PROMPT_TEMPLATE.format(
        start_date=start_date, end_date=end_date
    )
