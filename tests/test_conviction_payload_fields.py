"""CE-10: payload fields and the fundamental anomaly flag reach the overlay row."""

from __future__ import annotations

import tempfile
from pathlib import Path

from src.conviction_engine.engine import full_recalculation, modify_signal
from src.conviction_engine.scoring import fundamental_anomaly_flags


def test_anomaly_bands():
    assert fundamental_anomaly_flags({"pe_ttm": 4.0}) == ["pe_below_5"]
    assert fundamental_anomaly_flags({"pe_ttm": 120.0}) == ["pe_above_80"]
    assert fundamental_anomaly_flags({"pe_ttm": 20.0, "stockholders_equity": -5e9}) == ["negative_book_value"]
    assert fundamental_anomaly_flags({"net_margin": 1.4}) == ["net_income_implausible_vs_revenue"]
    assert fundamental_anomaly_flags({"pe_ttm": 20.0, "net_margin": 0.25, "tangible_book_value": -1e9}) == []
    assert fundamental_anomaly_flags({"pe_ttm": -12.0}) == []  # loss-making: no P/E band


def test_overlay_row_carries_payload_fields():
    with tempfile.TemporaryDirectory() as tmp:
        full_recalculation(
            "ZZZ",
            info={"quoteType": "EQUITY", "sector": "Technology", "industry": "Software - Application"},
            fundamentals={"price": 100.0, "market_cap": 10_000_000_000, "eps_ttm": 1.0},
            store_dir=Path(tmp),
        )
        row = modify_signal("ZZZ", "BUY", "long", store_dir=Path(tmp), persist=False).to_dict()
    assert row["market_cap"] == 10_000_000_000
    assert row["pe_ttm"] == 100.0
    assert row["fundamental_anomaly_flag"] is True
    assert row["fundamental_anomaly_reasons"] == "pe_above_80"
