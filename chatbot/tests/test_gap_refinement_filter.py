"""Tests for gap analyzer refinement filtering."""

from chatbot.agents.research_gap_analyzer import ResearchGapAnalyzer
from chatbot.agents.research_planner import ResearchPlan, ResearchSubTask
from chatbot.agents.research_types import EvidenceStore


def test_filter_drops_cen_2026_forward_refinement():
    analyzer = ResearchGapAnalyzer(api_key=None)
    refinements = [
        ResearchSubTask(
            id="ref1",
            question=(
                "What were the share prices of Contact Energy 1 month, 3 months, and 6 months "
                "after Infratil's block sale on May 25, 2026?"
            ),
            retrieval_mode="web",
            rationale="x",
            success_criteria="x",
        ),
    ]
    qa = {"measure_forward_returns_for_reference": False}
    out = analyzer._filter_refinements(refinements, qa, EvidenceStore(plan=_empty_plan()))
    assert len(out) == 0


def test_upgrade_dated_zel_to_price_data():
    analyzer = ResearchGapAnalyzer(api_key=None)
    refinements = [
        ResearchSubTask(
            id="ref2",
            question=(
                "What were the share prices of Z Energy 1 month, 3 months, and 6 months "
                "after Infratil's block sale on October 1, 2015?"
            ),
            retrieval_mode="web",
            rationale="x",
            success_criteria="x",
            seller_ticker="IFT.NZ",
            sold_ticker="ZEL.NZ",
            precedent_name="Z Energy",
        ),
    ]
    qa = {"measure_forward_returns_for_reference": False}
    out = analyzer._filter_refinements(refinements, qa, EvidenceStore(plan=_empty_plan()))
    assert len(out) == 1
    assert out[0].retrieval_mode == "price_data"
    assert out[0].event_date == "2015-10-01"


def _empty_plan() -> ResearchPlan:
    return ResearchPlan(
        user_question="test",
        summary="test",
        subtasks=[],
        reasoning="",
    )
