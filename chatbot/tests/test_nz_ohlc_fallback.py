"""Tests for Stooq / NZX OHLC fallbacks."""

from unittest.mock import MagicMock, patch

import pandas as pd

from chatbot.tools.market_price_tool import fetch_ohlc_series
from chatbot.tools.nz_ohlc_fallback import (
    _parse_stooq_csv,
    load_nzxplorer_ohlc,
    load_stooq_ohlc,
    to_stooq_symbol,
)


STOOQ_CSV = """Date,Open,High,Low,Close,Volume
2015-09-28,5.8,6.0,5.7,5.9,1000000
2015-09-29,5.9,6.1,5.8,6.0,1200000
2015-09-30,6.0,6.2,5.9,6.0,900000
2015-10-01,6.0,6.1,5.95,6.0,800000
"""


def test_to_stooq_symbol():
    assert to_stooq_symbol("ZEL.NZ") == "zel.nz"
    assert to_stooq_symbol("IFT.NZ") == "ift.nz"


def test_parse_stooq_csv():
    df = _parse_stooq_csv(STOOQ_CSV)
    assert df is not None
    assert len(df) == 4
    assert float(df.iloc[-1]["Close"]) == 6.0


@patch("chatbot.tools.nz_ohlc_fallback.requests.get")
def test_load_stooq_ohlc(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = STOOQ_CSV
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    df, src = load_stooq_ohlc("ZEL.NZ")
    assert src == "stooq"
    assert df is not None
    assert len(df) >= 4


@patch("chatbot.tools.nz_ohlc_fallback.requests.get")
def test_load_nzxplorer_ohlc(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": {
            "prices": [
                {"date": "2015-09-30", "close": 6.0},
                {"date": "2015-10-01", "close": 6.05},
            ]
        }
    }
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    df, src = load_nzxplorer_ohlc("ZEL.NZ", api_key="test-key")
    assert src == "nzxplorer"
    assert len(df) == 2


@patch("chatbot.tools.market_price_tool._load_yfinance_ohlc", return_value=None)
@patch("chatbot.tools.market_price_tool._load_trade_store_ohlc", return_value=None)
@patch("chatbot.tools.nz_ohlc_fallback.load_stooq_ohlc")
def test_fetch_ohlc_series_stooq_fallback(mock_stooq, _mock_ts, _mock_yf):
    dates = pd.date_range("2015-09-01", periods=200, freq="B")
    df = pd.DataFrame({"Close": [6.0] * len(dates)}, index=dates)
    mock_stooq.return_value = (df, "stooq")

    series, src = fetch_ohlc_series("ZEL.NZ", stock_data_dir=None)
    assert src == "stooq"
    assert series is not None
    assert len(series) == 200
