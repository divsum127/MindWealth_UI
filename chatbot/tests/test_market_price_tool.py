"""Unit tests for market_price_tool."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from chatbot.tools.market_price_tool import (
    _normalize_ohlc_index,
    compute_post_event_returns,
    fetch_close_on_or_near,
    to_yfinance_symbol,
)


def test_to_yfinance_symbol_nz_aliases():
    assert to_yfinance_symbol("CEN.NZ") == "CEN.NZ"
    assert to_yfinance_symbol("z energy") == "ZEL.NZ"
    assert to_yfinance_symbol("IFT") == "IFT.NZ"
    assert to_yfinance_symbol("Contact Energy") == "CEN.NZ"


@patch("chatbot.tools.market_price_tool.fetch_ohlc_series")
def test_compute_post_event_returns(mock_fetch):
    dates = pd.date_range("2019-06-01", periods=200, freq="B")
    prices = [5.0 + i * 0.01 for i in range(len(dates))]
    df = pd.DataFrame({"Close": prices}, index=dates)

    mock_fetch.return_value = (df, "yfinance")

    result = compute_post_event_returns(
        seller_ticker="IFT.NZ",
        sold_ticker="ZEL.NZ",
        event_date="2019-06-12",
        months=(1, 3, 6),
        stock_data_dir=None,
    )

    assert result["event_date"] == "2019-06-12"
    assert result["seller"] is not None
    assert result["seller"]["T0"] is not None
    assert result["data_source"] == "yfinance"


def test_normalize_ohlc_index_strips_timezone():
    dates = pd.date_range("2015-08-01", periods=10, freq="B", tz="Pacific/Auckland")
    df = pd.DataFrame({"Close": range(10)}, index=dates)
    norm = _normalize_ohlc_index(df)
    assert norm.index.tz is None
    target = pd.Timestamp("2015-08-04").tz_localize(None)
    assert (norm.index >= target).any()


@patch("chatbot.tools.market_price_tool.fetch_ohlc_series")
def test_fetch_close_on_or_near_tz_aware_yfinance(mock_fetch):
    dates = pd.date_range("2015-08-01", periods=30, freq="B", tz="Pacific/Auckland")
    df = pd.DataFrame({"Close": [9.0 + i * 0.05 for i in range(30)]}, index=dates)
    mock_fetch.return_value = (df, "yfinance")

    price, actual, source = fetch_close_on_or_near("CEN.NZ", "2015-08-20", None)
    assert price is not None
    assert actual is not None
    assert source == "yfinance"


def test_is_valid_subtask_question():
    from chatbot.agents.research_types import is_valid_subtask_question

    assert not is_valid_subtask_question("Research subtask")
    assert not is_valid_subtask_question("")
    assert is_valid_subtask_question("Find Z Energy block sale date in 2019")
