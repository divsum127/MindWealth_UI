"""CE-02: P/E history confidence tiers (Rohit 21 Sep 2026)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from src.conviction_engine.engine import full_recalculation
from src.conviction_engine.pe_history_core import pe_history_confidence
from src.conviction_engine.scoring import fs_score_breakdown, valuation_tax_breakdown


@pytest.mark.parametrize(
    "years, has_series, expected",
    [
        (32.0, True, "full"),
        (20.0, True, "full"),
        (19.9, True, "provisional"),
        (10.0, True, "provisional"),
        (9.99, True, "neutral"),
        (0.0, True, "neutral"),
        (25.0, False, "neutral"),
        (None, True, "neutral"),
    ],
)
def test_confidence_tiers(years, has_series, expected):
    assert pe_history_confidence(years, has_series) == expected


def _record(pe_pct, insufficient):
    return {"business_type": "compounder", "pe_percentile_20y": pe_pct, "pe_history_insufficient": insufficient}


def test_provisional_history_is_scored_with_the_same_point_table():
    # Same percentile, same points, whether the history is full or provisional.
    full = {**_record(90, False), "pe_history_confidence": "full"}
    provisional = {**_record(90, False), "pe_history_confidence": "provisional"}
    assert valuation_tax_breakdown(provisional)["components"]["pe_hist_percentile"] == -3.0
    assert valuation_tax_breakdown(full)["components"] == valuation_tax_breakdown(provisional)["components"]
    assert fs_score_breakdown(full)["components"] == fs_score_breakdown(provisional)["components"]


def test_neutral_history_contributes_nothing():
    assert valuation_tax_breakdown(_record(90, True))["components"]["pe_hist_percentile"] == 0.0


def _recalc(years: float):
    pe = [10 + i * 0.5 for i in range(60)]
    with tempfile.TemporaryDirectory() as tmp:
        return full_recalculation(
            "ZZZ",
            info={"quoteType": "EQUITY", "sector": "Technology", "industry": "Software - Application"},
            fundamentals={
                "price": 100.0,
                "market_cap": 10_000_000_000,
                "eps_ttm": 2.0,
                "pe_20y_array": pe,
                "pe_history_meta": {"years_available": years, "point_count": len(pe), "source": "sec_edgar"},
            },
            store_dir=Path(tmp),
        )


def test_recalc_labels_fifteen_years_provisional_and_keeps_percentile():
    record = _recalc(15.0)
    assert record["pe_history_confidence"] == "provisional"
    assert record["pe_history_insufficient"] is False
    assert record["pe_percentile_20y"] is not None
    assert record["pe_history_source"] == "sec_edgar"


def test_recalc_neutralises_under_ten_years():
    record = _recalc(6.0)
    assert record["pe_history_confidence"] == "neutral"
    assert record["pe_history_insufficient"] is True
    assert record["pe_percentile_20y"] is None


def test_recalc_full_history():
    record = _recalc(25.0)
    assert record["pe_history_confidence"] == "full"
    assert record["pe_history_insufficient"] is False


def test_recalc_without_history_metadata_is_neutral():
    with tempfile.TemporaryDirectory() as tmp:
        record = full_recalculation(
            "SONY",
            info={"quoteType": "EQUITY", "sector": "Technology", "industry": "Consumer Electronics"},
            fundamentals={"price": 100.0, "market_cap": 10_000_000_000, "eps_ttm": 2.0, "pe_20y_array": [10, 12, 14]},
            store_dir=Path(tmp),
        )
    assert record["pe_history_confidence"] == "neutral"
    assert record["pe_percentile_20y"] is None
    assert valuation_tax_breakdown(record)["components"]["pe_hist_percentile"] == 0.0
