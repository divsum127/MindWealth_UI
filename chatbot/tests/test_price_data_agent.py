"""Tests for PriceDataAgent event date inference from web evidence."""

from unittest.mock import patch

import pandas as pd

from chatbot.agents.price_data_agent import PriceDataAgent
from chatbot.agents.research_planner import ResearchPlan
from chatbot.agents.research_types import EvidenceStore, ResearchSubTask, SubTaskEvidence


def test_price_data_infers_date_from_web_snippet():
    plan = ResearchPlan(user_question="q", summary="s", subtasks=[], reasoning="")
    store = EvidenceStore(plan=plan)
    store.add(
        SubTaskEvidence(
            subtask_id="st1",
            question="Z Energy block date",
            retrieval_mode="web",
            success=True,
            formatted_context=(
                "Infratil Limited announces 1 October 2015 sell 20% Z Energy block trade"
            ),
            inferred_event_date="2015-10-01",
        )
    )
    subtask = ResearchSubTask(
        id="st2",
        question="Compute T+1m/3m/6m after Z Energy block sale",
        retrieval_mode="price_data",
        rationale="",
        success_criteria="",
        depends_on=["st1"],
        precedent_name="Z Energy / Infratil 2015",
        seller_ticker="IFT.NZ",
        sold_ticker="ZEL.NZ",
    )

    dates = pd.date_range("2015-09-01", periods=300, freq="B")
    df = pd.DataFrame({"Close": [5.0 + i * 0.01 for i in range(len(dates))]}, index=dates)

    with patch("chatbot.tools.market_price_tool.fetch_ohlc_series", return_value=(df, "yfinance")):
        evidence, detail = PriceDataAgent().run(subtask, store)

    assert evidence.inferred_event_date == "2015-10-01"
    assert detail.get("inferred_event_date") == "2015-10-01"
    assert evidence.success is True


def test_price_data_prefers_web_date_over_planner_hallucination():
    plan = ResearchPlan(user_question="q", summary="s", subtasks=[], reasoning="")
    store = EvidenceStore(plan=plan)
    store.add(
        SubTaskEvidence(
            subtask_id="st1",
            question="Z Energy block date",
            retrieval_mode="web",
            success=True,
            formatted_context="block trade 1 October 2015",
            inferred_event_date="2015-10-01",
            inferred_seller_ticker="IFT.NZ",
            inferred_sold_ticker="ZEL.AX",
        )
    )
    subtask = ResearchSubTask(
        id="st2",
        question="Compute prices",
        retrieval_mode="price_data",
        rationale="",
        success_criteria="",
        depends_on=["st1"],
        precedent_name="Z Energy / Infratil 2015",
        seller_ticker="IFT.NZ",
        sold_ticker="ZEL.AX",
        event_date="2015-06-12",
    )

    dates = pd.date_range("2015-09-01", periods=300, freq="B")
    df = pd.DataFrame({"Close": [5.0 + i * 0.01 for i in range(len(dates))]}, index=dates)

    with patch("chatbot.tools.market_price_tool.fetch_ohlc_series", return_value=(df, "yfinance")):
        evidence, _ = PriceDataAgent().run(subtask, store)

    assert evidence.inferred_event_date == "2015-10-01"
