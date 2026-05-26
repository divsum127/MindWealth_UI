"""Planner and refinement validation for precedent + price_data pipeline."""

from chatbot.agents.research_planner import ResearchPlanner
from chatbot.agents.research_query_analyzer import ResearchQueryAnalysis
from chatbot.agents.research_types import is_valid_subtask_question


IFT_CEN_QUERY = (
    "Infratil is selling its Contact Energy stake via a block sale. "
    "What happened in similar NZ block sales in years gone by — "
    "how did the seller stock and the block stock perform 1, 3, and 6 months after?"
)


def test_rule_based_query_analysis_historical_precedents():
    from chatbot.agents.research_query_analyzer import ResearchQueryAnalyzer

    analysis = ResearchQueryAnalyzer(None).analyze(IFT_CEN_QUERY)
    assert analysis.comparison_type == "historical_precedents"
    assert analysis.measure_forward_returns_for_reference is False
    assert len(analysis.suggested_precedents) >= 1
    assert "Origin" in analysis.suggested_precedents[0]


def test_fallback_z_energy_query_uses_2015():
    from chatbot.agents.research_query_analyzer import ResearchQueryAnalyzer

    analysis = ResearchQueryAnalyzer(None).analyze(IFT_CEN_QUERY)
    planner = ResearchPlanner(api_key=None, max_subtasks=10)
    plan = planner._fallback_plan(IFT_CEN_QUERY, analysis)
    z_web = [st for st in plan.subtasks if st.precedent_name and "Z Energy" in st.precedent_name and st.retrieval_mode == "web"]
    assert z_web
    joined = " ".join(z_web[0].web_queries).lower()
    assert "2015" in joined
    assert "2019" not in joined


def test_fallback_plan_has_precedent_pairs_not_forward_cen():
    analysis = ResearchQueryAnalysis(
        comparison_type="historical_precedents",
        reference_event={
            "seller_ticker": "IFT.NZ",
            "sold_ticker": "CEN.NZ",
            "status": "in_progress",
        },
        measure_forward_returns_for_reference=False,
        suggested_precedents=["Z Energy", "Trustpower", "Genesis Energy"],
    )
    planner = ResearchPlanner(api_key=None, max_subtasks=10)
    plan = planner._fallback_plan(IFT_CEN_QUERY, analysis)

    modes = [st.retrieval_mode for st in plan.subtasks]
    assert "price_data" in modes
    assert "web" in modes

    bad_forward = [
        st
        for st in plan.subtasks
        if "1 month after" in st.question.lower()
        and "cen" in st.question.lower()
        and "2026" in st.question.lower()
    ]
    assert len(bad_forward) == 0

    for st in plan.subtasks:
        assert is_valid_subtask_question(st.question)


def test_parse_subtask_rejects_placeholder():
    planner = ResearchPlanner(api_key=None)
    assert planner._parse_subtask({"question": "Research subtask", "retrieval_mode": "web"}, "st1") is None
    assert planner._parse_subtask({"question": "", "retrieval_mode": "web"}, "st1") is None

    valid = planner._parse_subtask(
        {
            "question": "Find Z Energy block sale event date for Infratil divestment",
            "retrieval_mode": "price_data",
            "seller_ticker": "IFT.NZ",
            "sold_ticker": "ZEL.NZ",
            "depends_on": ["st1"],
        },
        "st2",
    )
    assert valid is not None
    assert valid.retrieval_mode == "price_data"


def test_parse_refinement_skips_invalid():
    planner = ResearchPlanner(api_key=None)
    refinements = planner.parse_refinement_subtasks(
        {
            "refinement_subtasks": [
                {"question": "Research subtask", "retrieval_mode": "web"},
                {
                    "question": "Compute T+3m prices after Trustpower divestment date",
                    "retrieval_mode": "price_data",
                    "seller_ticker": "IFT.NZ",
                    "sold_ticker": "TPW.NZ",
                },
            ]
        },
        IFT_CEN_QUERY,
    )
    assert len(refinements) == 1
    assert refinements[0].retrieval_mode == "price_data"
