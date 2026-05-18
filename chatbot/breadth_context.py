"""
Signal Breadth Indicator (SBI) schema and AI context helpers.

Trade-arrival SBI metrics from MindWealth breadth reports (S&P 500 universe).
"""

from typing import List

# Market-wide combined row in breadth reports
COMBINED_FUNCTION_NAME = "Combined (TrendPulse + DeltaDrift + BandMatrix)"

# Core SBI columns (current schema from get_enhanced_breadth_signal)
BREADTH_SBI_COLUMNS: List[str] = [
    "Date",
    "Function",
    "Total New Long Signal",
    "Last 6 Month Top 10 Percentile No of Long Signal",
    "Today Long Signal Percentile From Top (Last 6 Month)",
    "Total New Short Signal",
    "Last 6 Month Top 10 Percentile No of Short Signal",
    "Today Short Signal Percentile From Top (Last 6 Month)",
]

BREADTH_MANDATORY_COLUMNS = BREADTH_SBI_COLUMNS

BREADTH_NUMERIC_COLUMNS = [
    "Total New Long Signal",
    "Last 6 Month Top 10 Percentile No of Long Signal",
    "Today Long Signal Percentile From Top (Last 6 Month)",
    "Total New Short Signal",
    "Last 6 Month Top 10 Percentile No of Short Signal",
    "Today Short Signal Percentile From Top (Last 6 Month)",
]

BREADTH_COLUMN_DESCRIPTIONS = {
    "Date": "Trading date for SBI metrics (S&P 500 universe).",
    "Function": "Strategy name (TRENDPULSE, DELTADRIFT, BAND MATRIX) or Combined row.",
    "Total New Long Signal": "Count of new long signals today.",
    "Total New Short Signal": "Count of new short signals today.",
    "Last 6 Month Top 10 Percentile No of Long Signal": "90th-percentile threshold of daily long signal counts over last 6 months.",
    "Last 6 Month Top 10 Percentile No of Short Signal": "90th-percentile threshold of daily short signal counts over last 6 months.",
    "Today Long Signal Percentile From Top (Last 6 Month)": (
        "Where today's long count ranks vs last 6 months (top-percentile). "
        "Example: 10 = today is in the top 10% of long-signal days; low values = quiet long-signal day."
    ),
    "Today Short Signal Percentile From Top (Last 6 Month)": (
        "Where today's short count ranks vs last 6 months (top-percentile). "
        "Example: 10 = today is in the top 10% of short-signal days."
    ),
}


def build_breadth_schema_note() -> str:
    """Short schema note for LLM breadth analysis."""
    lines = [
        "SIGNAL BREADTH INDICATOR (SBI) — trade-arrival metrics on S&P 500 stocks.",
        f"For market-wide analysis, prioritize Function = '{COMBINED_FUNCTION_NAME}'.",
        "Percentile semantics: 'Today ... Percentile From Top' = distance from the busiest day in the last 6 months.",
        "  - High value (e.g. >= 90): extreme activity (top ~10% of days).",
        "  - Low value (e.g. <= 10): quiet day (bottom ~10% vs 6-month history).",
        "Bottom/top 10% in the selected date range: rank percentile columns across days in range; "
        "bottom decile = lowest percentiles, top decile = highest.",
        "Column definitions:",
    ]
    for col in BREADTH_SBI_COLUMNS:
        if col in ("Date", "Function"):
            continue
        desc = BREADTH_COLUMN_DESCRIPTIONS.get(col, "")
        if desc:
            lines.append(f"  - {col}: {desc}")
    return "\n".join(lines)
