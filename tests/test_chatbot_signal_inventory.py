from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chatbot.chatbot_engine import ChatbotEngine, _row_limit_for_query
from chatbot.config import MAX_ROWS_TO_INCLUDE


INVENTORY_QUERY = (
    "Using current internal data only, give total outstanding signals, "
    "long/short split, new-today count, and the five highest forward win-rate rows."
)


def test_complete_inventory_and_ranking_queries_bypass_the_generic_row_cap() -> None:
    assert _row_limit_for_query(None, None, INVENTORY_QUERY) is None
    assert _row_limit_for_query(None, None, "Show recent AAPL signals") == MAX_ROWS_TO_INCLUDE


def test_internal_fetch_returns_all_rows_above_100_for_inventory_query() -> None:
    rows = pd.DataFrame(
        {
            "Symbol": [f"SYM{i:03d}" for i in range(104)],
            "Position": ["Long"] * 96 + ["Short"] * 8,
            "Forward Win Rate": [85.94] * 5 + [80.34] * 99,
        }
    )
    seen_limits: list[int | None] = []

    def fetch_data(**kwargs):
        limit = kwargs["limit_rows"]
        seen_limits.append(limit)
        return {"entry": rows if limit is None else rows.head(limit)}

    engine = object.__new__(ChatbotEngine)
    engine.history_manager = SimpleNamespace(get_messages_for_api=lambda **_: [])
    engine.unified_extractor = MagicMock()
    engine.unified_extractor.extract_all.return_value = {
        "success": True,
        "signal_types": ["entry"],
        "columns": {
            "entry": {
                "column_names": ["Symbol", "Position", "Forward Win Rate"],
                "reasoning": "Inventory, side split and ranking",
                "column_indices": [],
            }
        },
        "functions": None,
        "tickers": None,
    }
    engine.smart_data_fetcher = SimpleNamespace(fetch_data=fetch_data)

    fetched, metadata = engine._fetch_signal_data(
        INVENTORY_QUERY,
        ["entry"],
        auto_extract_tickers=True,
    )

    assert seen_limits == [None]
    assert metadata["rows_fetched"] == 104
    assert len(fetched["entry"]) == 104
    assert fetched["entry"]["Position"].value_counts().to_dict() == {
        "Long": 96,
        "Short": 8,
    }
    assert fetched["entry"].nlargest(5, "Forward Win Rate")["Symbol"].tolist() == [
        "SYM000",
        "SYM001",
        "SYM002",
        "SYM003",
        "SYM004",
    ]
