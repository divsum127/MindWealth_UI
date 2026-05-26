"""Tests for entry target/stop validation and cited-entry hint parsing."""

from chatbot.signal_level_validator import validate_entry_record
from chatbot.smart_data_fetcher import SmartDataFetcher

SYMBOL_COL = "Symbol, Signal, Signal Date/Price[$]"
TODAY_COL = "Today Trading Date/Price[$], Today Price vs Signal"
STOP_COL = (
    "Stop Loss (Recent Extrema/Horizontal/F-Stack 1/F-Stack 2/F-Track 1/F-Track 2/EMA 200) [$]"
)
TARGET_COL = (
    "Targets (Historic Rise or Fall to Pivot/Avg % Gain of Historic Winning trades/"
    "Function Specific Target/Horizontal/F-Stack 1/F-Stack 2/EMA 200) [$]"
)


def test_long_stop_above_today_warns():
    record = {
        SYMBOL_COL: "FXI, Long, 2026-01-04 (Price: 39.82)",
        TODAY_COL: "2026-05-19 (Price: 36.2800), 5.23% below",
        STOP_COL: "38.6/20.865/No F-Stack Support/No F-Stack Support/No F-Track Level/No F-Track Level/37.78",
        TARGET_COL: "41.2296/45.6815/52.5/42.665/90.5742/95.3274/No EMA 200 Target",
    }
    warnings = validate_entry_record(record)
    assert any("Long signal" in w and "stale" in w.lower() or "above" in w for w in warnings)


def test_april_fxi_row_no_long_stop_warning():
    record = {
        SYMBOL_COL: "FXI, Long, 2026-04-12 (Price: 36.25)",
        TODAY_COL: "2026-05-19 (Price: 36.2800), 2.66% above",
        STOP_COL: "34.85/20.865/No F-Stack Support/No F-Stack Support/No F-Track Level/No F-Track Level/No EMA 200 Stop Loss",
        TARGET_COL: "37.5622/41.6766/48.93/42.105/90.5742/95.3274/38.66",
    }
    warnings = validate_entry_record(record)
    assert not any("Long signal" in w and "34.85" in w for w in warnings)
    assert any("EMA 200" in w and "Targets" in w for w in warnings)


def test_parse_cited_entry_hints():
    text = "FRACTAL TRACK Weekly (Entry: $35.34 on 2026-04-12)"
    hints = SmartDataFetcher.parse_cited_entry_hints(text)
    assert ("2026-04-12", 35.34) in hints
