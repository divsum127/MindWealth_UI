"""CE-01 / CE-05 / CE-07: reviewed business_type overrides and uncovered telco/utility types."""

from __future__ import annotations

import json

from src.conviction_engine import scoring
from src.conviction_engine.models import BusinessType, threshold_profile
from src.conviction_engine.scoring import (
    EV_REV_TIERS,
    detect_business_type,
    is_coverage_incomplete,
    load_business_type_overrides,
)

SBUX_INFO = {
    "quoteType": "EQUITY",
    "sector": "Consumer Cyclical",
    "industry": "Restaurants",
    "dividendYield": 0.031,
    "payoutRatio": 0.72,
}


def test_dividend_rule_alone_would_make_sbux_income():
    assert detect_business_type(SBUX_INFO, {}) == (BusinessType.INCOME.value, "auto")


def test_config_override_keeps_sbux_compounder():
    assert detect_business_type(SBUX_INFO, {}, ticker="SBUX") == (BusinessType.COMPOUNDER.value, "config_override")
    assert detect_business_type(SBUX_INFO, {}, ticker="sbux")[1] == "config_override"


def test_record_manual_override_beats_config():
    assert detect_business_type(SBUX_INFO, {"business_type": "income"}, ticker="SBUX") == ("income", "manual")


def test_sftby_is_holding_company_and_uncovered():
    info = {"quoteType": "EQUITY", "sector": "Communication Services", "industry": "Telecom Services"}
    business_type, source = detect_business_type(info, {}, ticker="SFTBY")
    assert (business_type, source) == (BusinessType.HOLDING_COMPANY.value, "config_override")
    assert is_coverage_incomplete(business_type)


def test_telcos_gate_as_coverage_incomplete():
    info = {"quoteType": "EQUITY", "sector": "Communication Services", "industry": "Telecom Services"}
    business_type, source = detect_business_type(info, {}, ticker="CNU.NZ")
    assert (business_type, source) == (BusinessType.TELCO.value, "auto_coverage_incomplete")
    assert is_coverage_incomplete(business_type)


def test_regulated_utility_gates_but_renewables_stay_income():
    regulated = {"quoteType": "EQUITY", "sector": "Utilities", "industry": "Utilities - Regulated Gas"}
    renewable = {"quoteType": "EQUITY", "sector": "Utilities", "industry": "Utilities - Renewable", "dividendYield": 0.05, "payoutRatio": 0.9}
    assert detect_business_type(regulated, {}, ticker="BIPC.TO")[0] == BusinessType.REGULATED_UTILITY.value
    assert detect_business_type(renewable, {}, ticker="MCY.NZ")[0] == BusinessType.INCOME.value


def test_uncovered_types_keep_their_previous_threshold_profile():
    assert threshold_profile("telco") == "income"
    assert threshold_profile("regulated_utility") == "income"
    assert threshold_profile("holding_company") == "compounder"
    assert threshold_profile("saas") == "saas"
    assert EV_REV_TIERS.get(threshold_profile("telco")) == EV_REV_TIERS["income"]


def test_override_file_is_valid_and_documented():
    overrides = load_business_type_overrides()
    assert {"SBUX", "SFTBY"} <= set(overrides)
    for entry in overrides.values():
        assert entry["decided_by"] and entry["decided_on"] and entry["source"]


def test_missing_override_file_means_no_overrides(tmp_path):
    assert load_business_type_overrides(tmp_path / "absent.json") == {}
    path = tmp_path / "o.json"
    path.write_text(json.dumps({"_comment": "x", "AAA": {"business_type": "saas"}, "BBB": {}}))
    assert set(load_business_type_overrides(path)) == {"AAA"}


def test_detect_without_ticker_ignores_config(monkeypatch):
    monkeypatch.setattr(scoring, "business_type_override_for", lambda ticker: {"business_type": "saas"} if ticker else None)
    assert detect_business_type(SBUX_INFO, {})[0] == BusinessType.INCOME.value
