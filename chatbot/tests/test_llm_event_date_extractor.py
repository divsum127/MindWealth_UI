"""Tests for LLM event date extraction (mocked)."""

from unittest.mock import MagicMock, patch

from chatbot.tools.llm_event_date_extractor import (
    EventDateExtractionResult,
    LlmEventDateExtractor,
    extract_event_date_from_web,
)


def test_extract_event_date_llm_high_confidence():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content='{"event_date": "2015-10-01", "announcement_date": "2015-10-01", '
                '"settlement_date": "2015-10-06", "seller_name": "Infratil", '
                '"seller_ticker": "IFT.NZ", "sold_name": "Z Energy", "sold_ticker": "ZEL.NZ", '
                '"seller_is_listed": true, "confidence": 0.92, '
                '"reasoning": "Block trade announced 1 October 2015"}'
            )
        )
    ]
    mock_client.chat.completions.create.return_value = mock_response

    sources = [
        {
            "title": "Infratil sells Z Energy",
            "url": "https://infratil.com/news/z-energy",
            "content": "1 October 2015 block trade book build 29 September 2015",
        }
    ]
    def _stub_init(self, **kwargs):
        self._client = mock_client
        self._model = "gpt-4o-mini"
        self._api_key = "test"

    with patch.object(LlmEventDateExtractor, "__init__", _stub_init):
        ext = LlmEventDateExtractor()
        with patch(
            "chatbot.tools.llm_event_date_extractor.get_llm_event_date_extractor",
            return_value=ext,
        ):
            result = extract_event_date_from_web(
                question="Z Energy block sale date",
                sources=sources,
                precedent_name="Z Energy / Infratil 2015",
                seller_ticker="IFT.NZ",
                sold_ticker="ZEL.NZ",
                use_llm=True,
            )

    assert result.event_date == "2015-10-01"
    assert result.source == "llm"
    assert result.confidence >= 0.55


def test_extract_falls_back_to_heuristic_when_llm_low_confidence():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content='{"event_date": null, "confidence": 0.2, "reasoning": "unclear"}'
            )
        )
    ]
    mock_client.chat.completions.create.return_value = mock_response

    text = "Infratil Limited 1 October 2015 agreed to sell 20% Z Energy block trade"

    def _stub_init(self, **kwargs):
        self._client = mock_client
        self._model = "gpt-4o-mini"
        self._api_key = "test"

    with patch.object(LlmEventDateExtractor, "__init__", _stub_init):
        ext = LlmEventDateExtractor()
        with patch(
            "chatbot.tools.llm_event_date_extractor.get_llm_event_date_extractor",
            return_value=ext,
        ):
            result = extract_event_date_from_web(
                question="Z Energy date",
                sources=[{"title": "x", "url": "", "content": text}],
                text_blob=text,
                precedent_name="Z Energy",
                use_llm=True,
            )

    assert result.event_date == "2015-10-01"
    assert result.source == "heuristic"


def test_air_nz_crown_unlisted_from_llm():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content='{"event_date": "2013-11-17", "seller_name": "NZ Government", '
                '"seller_ticker": null, "sold_ticker": "AIR.NZ", "seller_is_listed": false, '
                '"confidence": 0.9, "reasoning": "Government sell-down 17 Nov 2013"}'
            )
        )
    ]
    mock_client.chat.completions.create.return_value = mock_response

    def _stub_init_air(self, **kwargs):
        self._client = mock_client
        self._model = "gpt-4o-mini"
        self._api_key = "test"

    with patch.object(LlmEventDateExtractor, "__init__", _stub_init_air):
        ext = LlmEventDateExtractor()
        with patch(
            "chatbot.tools.llm_event_date_extractor.get_llm_event_date_extractor",
            return_value=ext,
        ):
            result = extract_event_date_from_web(
                question="Air NZ block sale 2013",
                sources=[
                    {
                        "title": "Air NZ asset sale",
                        "content": "Nov 17, 2013 Government sell 20% stake",
                    }
                ],
                precedent_name="Air New Zealand 2013",
                use_llm=True,
            )

    assert result.event_date == "2013-11-17"
    assert result.seller_ticker is None
    assert result.sold_ticker == "AIR.NZ"
    assert result.seller_is_listed is False
