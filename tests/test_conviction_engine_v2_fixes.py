"""Tests for Conviction Engine Fixes v2 (after Rohit's 30 July + follow-up answers).

Covers: bank detection + P/TBV-vs-ROE valuation + efficiency-ratio margin substitution;
high_margin_hardware detection at the 40% boundary + EV/EBITDA tax tiers + floor
exemption; the corrected universal 4x floor and growth-multiple-fragility conditions
(regression, not just new behavior); the coverage_incomplete hard gate;
buyback-suspension/dividend-cut tiered flags + the -4 combined cap; the rebuilt FS-score
slice tables (including the CRM worked example from the follow-up doc); the
classification-only universe diff pass; explicit-undefined yield-trap thresholds for
KR/JP/CN; adjusted-EPS tax-rate handling; and the Tier-2 non-US PE-history reconstruction.

See `instruction_docs/conviction_engine_issues/conviction_fixes_decisions.md` for the
full rationale behind each of these.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.conviction_engine.adjusted_eps import compute_adjusted_eps_bundle, compute_effective_tax_rate
from src.conviction_engine.bank_valuation import (
    bank_fs_valuation_slice,
    bank_ptbv_valuation_tax,
    compute_efficiency_ratio,
    fair_ptbv,
    score_bank_balance_sheet,
    score_bank_margin_quality,
)
from src.conviction_engine.bq_scoring import score_deal_delay_risk
from src.conviction_engine.capital_allocation import (
    combined_capital_return_penalty,
    detect_buyback_suspension,
    detect_dividend_cut,
)
from src.conviction_engine.engine import modify_signal
from src.conviction_engine.fundamentals import classify_universe_diff
from src.conviction_engine.models import default_record
from src.conviction_engine.pe_history_core import compute_pe_history, reconstruct_quarterly_eps_from_net_income
from src.conviction_engine.scoring import (
    calculate_valuation_tax_components,
    detect_business_type,
    fs_score_breakdown,
    is_coverage_incomplete,
    is_yield_trap,
    market_yield_threshold,
    verdict_for_buy,
    verdict_for_sell,
    yield_trap_breakdown,
)
from src.conviction_engine.store import save_record


class TestBankDetectionAndValuation(unittest.TestCase):
    def test_bank_sector_and_industry_detected_as_bank(self):
        business_type, source = detect_business_type(
            {"quoteType": "EQUITY", "sector": "Financial Services", "industry": "Banks - Regional"}
        )
        self.assertEqual(business_type, "bank")
        self.assertEqual(source, "auto")

    def test_insurer_gets_coverage_incomplete_not_bank(self):
        business_type, source = detect_business_type(
            {"quoteType": "EQUITY", "sector": "Financial Services", "industry": "Insurance - Life"}
        )
        self.assertNotEqual(business_type, "bank")
        self.assertTrue(is_coverage_incomplete(business_type))
        self.assertEqual(source, "auto_coverage_incomplete")

    def test_asset_manager_in_financial_services_not_misclassified_as_bank(self):
        business_type, _ = detect_business_type(
            {"quoteType": "EQUITY", "sector": "Financial Services", "industry": "Asset Management"}
        )
        self.assertNotEqual(business_type, "bank")

    def test_bank_margin_quality_efficiency_ratio_tiers(self):
        strong = score_bank_margin_quality(
            {"noninterest_expense_ttm": 50.0, "net_interest_income_ttm": 100.0, "noninterest_income_ttm": 0.0}
        )
        mid = score_bank_margin_quality(
            {"noninterest_expense_ttm": 60.0, "net_interest_income_ttm": 100.0, "noninterest_income_ttm": 0.0}
        )
        weak = score_bank_margin_quality(
            {"noninterest_expense_ttm": 70.0, "net_interest_income_ttm": 100.0, "noninterest_income_ttm": 0.0}
        )
        self.assertEqual(strong, 2.0)  # 50% < 55% strong
        self.assertEqual(mid, 0.0)  # 60% in 55-65% band
        self.assertEqual(weak, -2.0)  # 70% > 65% weak
        ratio = compute_efficiency_ratio(
            {"noninterest_expense_ttm": 50.0, "net_interest_income_ttm": 100.0, "noninterest_income_ttm": 0.0}
        )
        self.assertAlmostEqual(ratio, 0.5)

    def test_bank_balance_sheet_equity_assets_tiers(self):
        well, well_label = score_bank_balance_sheet({"stockholders_equity": 12.0, "total_assets": 100.0})
        adequate, _ = score_bank_balance_sheet({"stockholders_equity": 8.0, "total_assets": 100.0})
        thin, thin_label = score_bank_balance_sheet({"stockholders_equity": 4.0, "total_assets": 100.0})
        self.assertEqual(well, 1.0)
        self.assertEqual(well_label, "bank_well_capitalized")
        self.assertEqual(adequate, 0.0)
        self.assertEqual(thin, -2.0)
        self.assertEqual(thin_label, "bank_thinly_capitalized")

    def test_fair_ptbv_matches_gordon_growth_formula(self):
        # (ROE - g) / (CoE - g), CoE=9%, g=3% by default
        result = fair_ptbv(0.15)
        self.assertAlmostEqual(result, (0.15 - 0.03) / (0.09 - 0.03))

    def test_bank_ptbv_valuation_tax_supersedes_flat_pb_table(self):
        # Actual = fair * 1.6 -> ratio 1.6 -> falls in the >=1.5 tier -> -2.0, NOT the
        # flat Price/Book table from the 30 July reply (which this supersedes, see
        # conviction_fixes_decisions.md Section 2).
        record = {
            "market_cap": 1.6 * ((0.15 - 0.03) / (0.09 - 0.03)) * 100.0,
            "tangible_book_value": 100.0,
            "roic_5y_avg": 0.15,
        }
        points, breakdown = bank_ptbv_valuation_tax(record)
        self.assertAlmostEqual(points, -2.0)
        self.assertAlmostEqual(breakdown["ratio"], 1.6, places=2)

    def test_bank_fs_valuation_slice_cheap_bank_gets_positive_points(self):
        # actual/fair = 0.6 -> cheap bank -> +10 (symmetric slice, not penalty-only)
        record = {
            "market_cap": 0.6 * ((0.15 - 0.03) / (0.09 - 0.03)) * 100.0,
            "tangible_book_value": 100.0,
            "roic_5y_avg": 0.15,
        }
        points, _ = bank_fs_valuation_slice(record)
        self.assertEqual(points, 10.0)

    def test_bank_yield_trap_threshold_gets_2pp_addon(self):
        base = market_yield_threshold("XYZ", business_type=None)
        bank = market_yield_threshold("XYZ", business_type="bank")
        self.assertAlmostEqual(bank - base, 0.02, places=4)


class TestHighMarginHardware(unittest.TestCase):
    def test_above_40pct_margin_is_high_margin_hardware(self):
        business_type, _ = detect_business_type(
            {"quoteType": "EQUITY", "sector": "Technology", "industry": "Semiconductors", "profitMargins": 0.45}
        )
        self.assertEqual(business_type, "high_margin_hardware")

    def test_below_40pct_margin_stays_cyclical(self):
        business_type, _ = detect_business_type(
            {"quoteType": "EQUITY", "sector": "Technology", "industry": "Semiconductors", "profitMargins": 0.25}
        )
        self.assertEqual(business_type, "cyclical")

    def test_exactly_40pct_margin_qualifies(self):
        business_type, _ = detect_business_type(
            {"quoteType": "EQUITY", "sector": "Technology", "industry": "Semiconductors", "profitMargins": 0.40}
        )
        self.assertEqual(business_type, "high_margin_hardware")

    def test_ev_ebitda_tax_tiers(self):
        below_tier1 = calculate_valuation_tax_components(
            {"business_type": "high_margin_hardware", "ev_fwd_ebitda": 8.0}
        )
        tier2 = calculate_valuation_tax_components(
            {"business_type": "high_margin_hardware", "ev_fwd_ebitda": 16.0}
        )
        tier4 = calculate_valuation_tax_components(
            {"business_type": "high_margin_hardware", "ev_fwd_ebitda": 30.0}
        )
        self.assertEqual(below_tier1["entry_multiple"], 0.0)
        self.assertEqual(tier2["entry_multiple"], -2.0)
        self.assertEqual(tier4["entry_multiple"], -4.0)

    def test_hardware_exempt_from_universal_floor(self):
        # Even with a huge EV/EBITDA multiple, hardware's `entry_multiple` never gets the
        # universal -5 floor applied (that floor only checks `ev_fwd_rev`, which hardware
        # doesn't use for its `entry_multiple` component at all).
        components = calculate_valuation_tax_components(
            {"business_type": "high_margin_hardware", "ev_fwd_ebitda": 30.0, "ev_fwd_rev": 20.0}
        )
        self.assertEqual(components["entry_multiple"], -4.0)
        self.assertGreater(components["entry_multiple"], -5.0)


class TestValuationTaxBugfixes(unittest.TestCase):
    """Regression tests for the two bug fixes (item 2), not just the new behavior."""

    def test_growth_multiple_fragility_fires_on_high_growth_not_low(self):
        # Corrected rule: ev_rev >= 4x AND revenue_growth >= 15% -> -2.0 (fast growth
        # priced in makes deceleration the risk). The OLD buggy condition fired on
        # revenue_growth < 5% instead -- assert the new, correct direction.
        high_growth = calculate_valuation_tax_components(
            {"business_type": "compounder", "ev_fwd_rev": 5.0, "revenue_growth": 0.20}
        )
        self.assertEqual(high_growth["growth_multiple_fragility"], -2.0)

        low_growth = calculate_valuation_tax_components(
            {"business_type": "compounder", "ev_fwd_rev": 5.0, "revenue_growth": 0.02}
        )
        self.assertEqual(low_growth["growth_multiple_fragility"], 0.0)

    def test_universal_4x_floor_applies_regardless_of_business_type(self):
        # cyclical had NO per-type floor trigger under the old per-type list -- the
        # universal rule must still floor it at -5 once ev_rev >= 4x.
        components = calculate_valuation_tax_components(
            {"business_type": "cyclical", "ev_fwd_rev": 4.5, "revenue_growth": 0.0}
        )
        self.assertLessEqual(components["entry_multiple"], -5.0)

    def test_universal_floor_does_not_fire_below_4x(self):
        components = calculate_valuation_tax_components(
            {"business_type": "cyclical", "ev_fwd_rev": 3.9, "revenue_growth": 0.0}
        )
        self.assertGreater(components["entry_multiple"], -5.0)


class TestCoverageIncompleteGate(unittest.TestCase):
    def test_verdict_for_buy_coverage_incomplete_distinct_from_cancel_buy(self):
        verdict, sizing = verdict_for_buy(9.0, coverage_incomplete=True)
        self.assertEqual(verdict, "COVERAGE INCOMPLETE")
        self.assertEqual(sizing, 0.0)

    def test_verdict_for_buy_yield_trap_still_cancel_buy(self):
        verdict, _ = verdict_for_buy(9.0, yield_trap=True, coverage_incomplete=False)
        self.assertEqual(verdict, "CANCEL BUY")

    def test_verdict_for_sell_coverage_incomplete(self):
        verdict, sizing = verdict_for_sell(9.0, "long", coverage_incomplete=True)
        self.assertEqual(verdict, "COVERAGE INCOMPLETE")
        self.assertEqual(sizing, 0.0)

    def test_modify_signal_uncalibrated_business_type_gets_coverage_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = default_record("UNMAPPED1")
            record.update(
                {
                    "asset_type": "EQUITY",
                    "business_type": "unknown",
                    "bq_raw": 9,
                    "valuation_tax": 0,
                    "conviction_score": 9,
                    "fs_score": 80,
                    "fs_class": "strong",
                }
            )
            save_record(record, Path(tmp))
            mod = modify_signal("UNMAPPED1", "BUY", "long", store_dir=Path(tmp), persist=False)
            self.assertEqual(mod.verdict, "COVERAGE INCOMPLETE")
            self.assertEqual(mod.sizing_pct, 0.0)
            self.assertTrue(mod.coverage_incomplete)


class TestBuybackDividendFlags(unittest.TestCase):
    def test_buyback_suspension_tiers(self):
        no_trigger = detect_buyback_suspension({"buyback_spend_ttm": 90_000_000.0, "buyback_spend_prior_year": 105_000_000.0})
        tier1 = detect_buyback_suspension({"buyback_spend_ttm": 60_000_000.0, "buyback_spend_prior_year": 100_000_000.0})
        tier2 = detect_buyback_suspension({"buyback_spend_ttm": 40_000_000.0, "buyback_spend_prior_year": 100_000_000.0})
        tier3 = detect_buyback_suspension({"buyback_spend_ttm": 10_000_000.0, "buyback_spend_prior_year": 100_000_000.0})
        self.assertFalse(no_trigger["triggered"])
        self.assertEqual(tier1["penalty"], -1.0)
        self.assertEqual(tier2["penalty"], -2.0)
        self.assertEqual(tier3["penalty"], -3.0)

    def test_buyback_suspension_requires_prior_spend_over_100m(self):
        below_threshold = detect_buyback_suspension({"buyback_spend_ttm": 0.0, "buyback_spend_prior_year": 50_000_000.0})
        self.assertFalse(below_threshold["triggered"])
        self.assertEqual(below_threshold["penalty"], 0.0)

    def test_dividend_cut_tiers(self):
        tier3 = detect_dividend_cut({"annual_div_declared_current": 0.0, "annual_div_declared_prior": 2.0})
        self.assertEqual(tier3["penalty"], -3.0)
        self.assertTrue(tier3["triggered"])

    def test_combined_penalty_capped_at_negative_4(self):
        buyback = {"penalty": -3.0}
        dividend = {"penalty": -3.0}
        self.assertEqual(combined_capital_return_penalty(buyback, dividend), -4.0)

    def test_combined_penalty_below_cap_stays_uncapped(self):
        buyback = {"penalty": -1.0}
        dividend = {"penalty": -2.0}
        self.assertEqual(combined_capital_return_penalty(buyback, dividend), -3.0)


class TestFsScoreSlice(unittest.TestCase):
    def test_pe_percentile_points_table(self):
        below20 = fs_score_breakdown({"business_type": "compounder", "bq_raw": 0.0, "pe_percentile_20y": 10})
        p20_40 = fs_score_breakdown({"business_type": "compounder", "bq_raw": 0.0, "pe_percentile_20y": 30})
        p40_60 = fs_score_breakdown({"business_type": "compounder", "bq_raw": 0.0, "pe_percentile_20y": 50})
        p60_80 = fs_score_breakdown({"business_type": "compounder", "bq_raw": 0.0, "pe_percentile_20y": 70})
        above80 = fs_score_breakdown({"business_type": "compounder", "bq_raw": 0.0, "pe_percentile_20y": 90})
        self.assertEqual(below20["components"]["pe_percentile"], 10.0)
        self.assertEqual(p20_40["components"]["pe_percentile"], 5.0)
        self.assertEqual(p40_60["components"]["pe_percentile"], 0.0)
        self.assertEqual(p60_80["components"]["pe_percentile"], -5.0)
        self.assertEqual(above80["components"]["pe_percentile"], -10.0)

    def test_oey_points_table_saas_thresholds(self):
        # saas strong=5%, expensive=1%
        very_strong = fs_score_breakdown({"business_type": "saas", "bq_raw": 0.0, "owner_earnings_yield": 0.08})
        strong = fs_score_breakdown({"business_type": "saas", "bq_raw": 0.0, "owner_earnings_yield": 0.05})
        neutral = fs_score_breakdown({"business_type": "saas", "bq_raw": 0.0, "owner_earnings_yield": 0.02})
        expensive = fs_score_breakdown({"business_type": "saas", "bq_raw": 0.0, "owner_earnings_yield": 0.008})
        very_expensive = fs_score_breakdown({"business_type": "saas", "bq_raw": 0.0, "owner_earnings_yield": 0.002})
        self.assertEqual(very_strong["components"]["oey"], 10.0)
        self.assertEqual(strong["components"]["oey"], 5.0)
        self.assertEqual(neutral["components"]["oey"], 0.0)
        self.assertEqual(expensive["components"]["oey"], -5.0)
        self.assertEqual(very_expensive["components"]["oey"], -10.0)

    def test_slice_is_symmetric_not_penalty_only(self):
        cheap = fs_score_breakdown(
            {"business_type": "compounder", "bq_raw": 0.0, "pe_percentile_20y": 5, "owner_earnings_yield": 0.08, "ev_fwd_rev": 0.5}
        )
        self.assertGreater(cheap["total"], cheap["components"]["base"])

    def test_crm_worked_example_from_followup_doc(self):
        """Pinned regression case (conviction_fixes_decisions.md Section 4/5): BQ +8,
        PE 91st pctile, OEY 1.8% (saas, between strong=5%/expensive=1%), EV/rev 9.2x
        (saas Tier 3) -> fs_score 55 -> moderate_high -> NO cap -> conviction stays +3
        -> REDUCED BUY. This is the exact case behind the CRM live-dashboard bug."""
        record = {
            "business_type": "saas",
            "bq_raw": 8.0,
            "pe_percentile_20y": 91,
            "owner_earnings_yield": 0.018,
            "ev_fwd_rev": 9.2,
        }
        breakdown = fs_score_breakdown(record)
        self.assertEqual(breakdown["components"]["base"], 70.0)  # 50 + 8*2.5
        self.assertEqual(breakdown["components"]["pe_percentile"], -10.0)
        self.assertEqual(breakdown["components"]["oey"], 0.0)
        self.assertEqual(breakdown["components"]["ev_fwd_rev"], -5.0)
        self.assertEqual(breakdown["total"], 55.0)

        from src.conviction_engine.scoring import apply_fs_cap, classify_fs

        fs_class = classify_fs(breakdown["total"])
        self.assertEqual(fs_class, "moderate_high")
        conviction_raw = 8.0 + (-5.0)  # BQ + valuation tax, from the live bug report
        final_score, cap_reason = apply_fs_cap(conviction_raw, fs_class, "long")
        self.assertEqual(final_score, 3.0)
        self.assertIsNone(cap_reason)
        verdict, sizing = verdict_for_buy(final_score)
        self.assertEqual(verdict, "REDUCED BUY")
        self.assertEqual(sizing, 40.0)

    def test_fs_score_and_fs_class_are_always_derived_from_the_same_breakdown(self):
        """Item 15 / structural CRM-bug fix: fs_score is never a separately-cached
        number that could drift from fs_cap_breakdown's own total."""
        record = {
            "business_type": "saas",
            "bq_raw": 8.0,
            "pe_percentile_20y": 91,
            "owner_earnings_yield": 0.018,
            "ev_fwd_rev": 9.2,
        }
        breakdown = fs_score_breakdown(record)
        from src.conviction_engine.scoring import calculate_fs_score

        self.assertEqual(calculate_fs_score(record), breakdown["total"])


class TestYieldTrapUndefinedMarkets(unittest.TestCase):
    def test_kr_threshold_is_undefined(self):
        self.assertIsNone(market_yield_threshold("005930.KS"))

    def test_jp_hk_cn_thresholds_are_undefined(self):
        for suffix in (".KQ", ".T", ".HK", ".SS", ".SZ"):
            self.assertIsNone(market_yield_threshold(f"TICKER{suffix}"), f"suffix {suffix} should be undefined")

    def test_us_threshold_still_defined(self):
        self.assertIsNotNone(market_yield_threshold("AAPL"))

    def test_yield_trap_never_fires_for_undefined_market(self):
        record = {"dividend_yield_zscore": 5.0, "dividend_yield_current": 0.15}
        self.assertFalse(is_yield_trap(record, "005930.KS"))

    def test_yield_trap_breakdown_reports_threshold_undefined(self):
        record = {"dividend_yield_zscore": 5.0, "dividend_yield_current": 0.15}
        breakdown = yield_trap_breakdown(record, "005930.KS")
        self.assertFalse(breakdown["market_threshold_defined"])
        self.assertFalse(breakdown["fired"])


class TestUniverseClassificationPass(unittest.TestCase):
    def test_flip_into_bank_is_queued(self):
        def fake_fetch(ticker: str) -> dict:
            return {"sector": "Financial Services", "industry": "Banks - Diversified"}

        with tempfile.TemporaryDirectory() as tmp:
            record = default_record("FAKEBANK")
            record["business_type"] = "compounder"
            save_record(record, Path(tmp))
            result = classify_universe_diff(["FAKEBANK"], store_dir=Path(tmp), fetch_info=fake_fetch)
            self.assertIn("FAKEBANK", result["flipped_tickers"])
            self.assertEqual(result["results"][0]["new_business_type"], "bank")

    def test_unrelated_flip_not_queued(self):
        def fake_fetch(ticker: str) -> dict:
            return {"sector": "Energy", "industry": "Oil & Gas E&P"}

        with tempfile.TemporaryDirectory() as tmp:
            record = default_record("FAKECOMP")
            record["business_type"] = "compounder"
            save_record(record, Path(tmp))
            result = classify_universe_diff(["FAKECOMP"], store_dir=Path(tmp), fetch_info=fake_fetch)
            self.assertNotIn("FAKECOMP", result["flipped_tickers"])
            self.assertTrue(result["results"][0]["flipped"])  # reclassified, but not a queue-worthy flip

    def test_already_coverage_incomplete_ticker_not_reflagged(self):
        def fake_fetch(ticker: str) -> dict:
            return {}

        with tempfile.TemporaryDirectory() as tmp:
            record = default_record("ALREADYUNK")
            record["business_type"] = "unknown"
            save_record(record, Path(tmp))
            result = classify_universe_diff(["ALREADYUNK"], store_dir=Path(tmp), fetch_info=fake_fetch)
            self.assertNotIn("ALREADYUNK", result["flipped_tickers"])


class TestAdjustedEpsTaxRate(unittest.TestCase):
    def test_effective_tax_rate_computed_from_quarterly_statement(self):
        dates = pd.date_range("2025-03-31", periods=4, freq="QE")
        q_inc = pd.DataFrame(
            {d: {"Tax Provision": 20.0, "Pretax Income": 100.0} for d in dates}
        )
        rate, is_fallback = compute_effective_tax_rate(q_inc)
        self.assertAlmostEqual(rate, 0.20)
        self.assertFalse(is_fallback)

    def test_flat_fallback_when_pretax_income_negative(self):
        dates = pd.date_range("2025-03-31", periods=4, freq="QE")
        q_inc = pd.DataFrame(
            {d: {"Tax Provision": 5.0, "Pretax Income": -10.0} for d in dates}
        )
        rate, is_fallback = compute_effective_tax_rate(q_inc)
        self.assertEqual(rate, 0.21)
        self.assertTrue(is_fallback)

    def test_materiality_gate_blocks_small_one_offs(self):
        fundamentals = {"net_income_ttm": 1000.0, "shares_outstanding_now": 100.0, "price": 50.0}
        dates = pd.date_range("2025-03-31", periods=4, freq="QE")
        q_inc = pd.DataFrame(
            {d: {"Tax Provision": 20.0, "Pretax Income": 100.0, "Total Unusual Items": -1.0} for d in dates}
        )
        result = compute_adjusted_eps_bundle(fundamentals, q_inc)
        self.assertNotIn("pe_ttm_adjusted", result)

    def test_materiality_gate_fires_for_large_one_offs(self):
        fundamentals = {"net_income_ttm": 1000.0, "shares_outstanding_now": 100.0, "price": 50.0}
        dates = pd.date_range("2025-03-31", periods=4, freq="QE")
        q_inc = pd.DataFrame(
            {d: {"Tax Provision": 20.0, "Pretax Income": 100.0, "Total Unusual Items": -500.0} for d in dates}
        )
        result = compute_adjusted_eps_bundle(fundamentals, q_inc)
        self.assertIn("pe_ttm_adjusted", result)
        self.assertGreater(result["one_off_pct_of_ni"], 0.05)


class TestNonUsPeHistoryReconstruction(unittest.TestCase):
    def test_reconstructs_eps_from_net_income_and_shares(self):
        dates = pd.date_range("2020-03-31", periods=8, freq="QE")
        q_inc = pd.DataFrame(
            {d: {"Net Income": 100_000_000.0, "Diluted Average Shares": 50_000_000.0} for d in dates}
        )
        eps = reconstruct_quarterly_eps_from_net_income(q_inc)
        self.assertEqual(len(eps), 8)
        self.assertAlmostEqual(eps.iloc[0], 2.0)

    def test_returns_empty_when_no_usable_rows(self):
        q_inc = pd.DataFrame({pd.Timestamp("2020-03-31"): {"Some Other Row": 1.0}})
        eps = reconstruct_quarterly_eps_from_net_income(q_inc)
        self.assertTrue(eps.empty)

    def test_reconstructed_series_feeds_compute_pe_history(self):
        dates = pd.date_range("2020-03-31", periods=8, freq="QE")
        q_inc = pd.DataFrame(
            {d: {"Net Income": 100_000_000.0 + i * 2_000_000, "Diluted Average Shares": 50_000_000.0} for i, d in enumerate(dates)}
        )
        eps = reconstruct_quarterly_eps_from_net_income(q_inc)
        price_dates = pd.date_range("2020-01-01", "2022-06-30", freq="D")
        prices = pd.Series([100.0] * len(price_dates), index=price_dates)
        bundle = compute_pe_history(prices, eps)
        self.assertTrue(bundle["values"])
        self.assertGreater(bundle["meta"]["point_count"], 0)


class TestDealDelayAgentScoring(unittest.TestCase):
    def test_prefers_live_agent_score_over_legacy_flag(self):
        overrides = {"deal_delay_detail": {"signal": "deal_delay", "score": -2}, "deal_delay_flag": False}
        self.assertEqual(score_deal_delay_risk(overrides), -2.0)

    def test_supply_constraint_signal_never_negative(self):
        overrides = {"deal_delay_detail": {"signal": "supply_constraint", "score": 0}}
        self.assertEqual(score_deal_delay_risk(overrides), 0.0)

    def test_falls_back_to_legacy_binary_flag_when_no_agent_detail(self):
        self.assertEqual(score_deal_delay_risk({"deal_delay_flag": True}), -1.0)
        self.assertEqual(score_deal_delay_risk({}), 0.0)


if __name__ == "__main__":
    unittest.main()
