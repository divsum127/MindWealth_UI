"""Tests for the Conviction Engine overlay."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.conviction_engine.data_coverage import CRITICAL_FIELDS, assess_data_coverage, missing_fields_list
from src.conviction_engine.engine import apply_to_signal_file, full_recalculation, modify_signal
from src.conviction_engine.fundamentals import (
    discover_universe,
    map_yfinance_fundamentals,
    update_ticker_fundamentals,
)
from src.conviction_engine.models import default_record
from src.conviction_engine.dividend_yield import compute_dividend_yield_stats
from src.conviction_engine.bq_scoring import classify_debt_purpose, score_balance_sheet_v6
from src.conviction_engine.fd_votes import compute_fd_votes
from src.conviction_engine.fundamentals_enriched import compute_bq_components_auto
from src.conviction_engine.scoring import (
    calculate_valuation_tax,
    detect_business_type,
    is_yield_trap,
    score_manual,
    verdict_for_buy,
)
from src.conviction_engine.signals import normalize_signal_row, signal_timeframe_from_interval
from src.conviction_engine.store import load_record, save_record


class TestBacktestParsing(unittest.TestCase):
    def test_parse_vs_signal_pct(self):
        from src.conviction_engine.backtest import parse_vs_signal_pct

        self.assertAlmostEqual(parse_vs_signal_pct("2026-05-11 (Price: 100), 4.55% above"), 4.55)
        self.assertAlmostEqual(parse_vs_signal_pct("2026-05-11 (Price: 100), 2.4% below"), -2.4)

    def test_parse_mtm_first_pct(self):
        from src.conviction_engine.backtest import parse_mtm_first_pct

        self.assertAlmostEqual(parse_mtm_first_pct("4.55%, 15 days"), 4.55)
        self.assertIsNone(parse_mtm_first_pct("No Exit Yet"))

    def test_signal_key_stable(self):
        from src.conviction_engine.backtest import build_signal_key
        from src.conviction_engine.signals import COMPOUND_SIGNAL_COLUMN

        row = pd.Series(
            {
                "Function": "TRENDPULSE",
                COMPOUND_SIGNAL_COLUMN: "AAPL, Long, 2026-04-01 (Price: 200)",
            }
        )
        k1 = build_signal_key(row)
        row2 = pd.Series(
            {
                "Function": "TRENDPULSE",
                COMPOUND_SIGNAL_COLUMN: "AAPL, Long, 2026-04-01 (Price: 200)",
            }
        )
        self.assertEqual(k1, build_signal_key(row2))


class TestSummarizeOverlay(unittest.TestCase):
    def test_max_conviction_uses_conviction_raw_not_only_verdict(self):
        from src.conviction_engine.formatting import summarize_overlay

        df = pd.DataFrame(
            {
                "verdict": ["REDUCED BUY", "MAX CONVICTION", "NOT_APPLICABLE"],
                "original_signal": ["BUY", "BUY", "BUY"],
                "asset_type": ["EQUITY", "EQUITY", "ETF"],
                "conviction_raw": [8.5, 3.0, 9.0],
                "conviction_score": [2.0, 3.0, 1.0],
                "yield_trap_warning": [False, False, False],
                "rationale": ["", "", ""],
            }
        )
        s = summarize_overlay(df)
        # Row 0: raw>=8 BUY equity applicable -> max tier even though verdict is not MAX
        # Row 1: verdict MAX CONVICTION
        # Row 2: ETF not equity -> excluded from max tier mask
        self.assertEqual(s["max_conviction"], 2)

    def test_yield_trap_coerces_string_false(self):
        from src.conviction_engine.formatting import summarize_overlay

        df = pd.DataFrame(
            {
                "verdict": ["CANCEL BUY", "CANCEL BUY"],
                "original_signal": ["BUY", "BUY"],
                "asset_type": ["EQUITY", "EQUITY"],
                "conviction_raw": [0.0, 0.0],
                "conviction_score": [0.0, 0.0],
                "yield_trap_warning": ["False", "True"],
                "rationale": ["Yield trap hard gate fired", ""],
            }
        )
        s = summarize_overlay(df)
        self.assertEqual(s["yield_traps"], 2)


class TestSignalParsing(unittest.TestCase):
    def test_parse_outstanding_signal_shape(self):
        row = pd.Series(
            {
                "Function": "TRENDPULSE",
                "Symbol, Signal, Signal Date/Price[$]": "KXS.TO, Long, 2026-05-10 (Price: 158.73)",
                "Win Rate [%], History Tested, Number of Trades": "91.67%, Past 10 years, 12",
                "Interval, Confirmation Status": "Weekly, is CONFIRMED on 2026-05-08",
                "Exit Signal Date/Price[$]": "No Exit Yet",
            }
        )
        signal = normalize_signal_row(row, source_file="source.csv", source_row=3)
        self.assertEqual(signal.symbol, "KXS.TO")
        self.assertEqual(signal.technical_signal, "BUY")
        self.assertEqual(signal.signal_timeframe, "short")
        self.assertAlmostEqual(signal.signal_strength, 0.9167, places=4)
        self.assertEqual(signal.status, "Open")

    def test_interval_mapping(self):
        self.assertEqual(signal_timeframe_from_interval("Daily"), "short")
        self.assertEqual(signal_timeframe_from_interval("Weekly"), "short")
        self.assertEqual(signal_timeframe_from_interval("Monthly"), "long")
        self.assertEqual(signal_timeframe_from_interval("Quarterly"), "long")


class TestScoringAndVerdicts(unittest.TestCase):
    def test_business_type_avoids_software_infrastructure_as_income(self):
        info = {"quoteType": "EQUITY", "sector": "Technology", "industry": "Software - Infrastructure", "dividendYield": 0.008}
        business_type, _ = detect_business_type(info)
        self.assertNotEqual(business_type, "income")

    def test_auto_bq_insider_ownership_percent_scale(self):
        from src.conviction_engine.fundamentals_enriched import compute_bq_components_auto

        mid = compute_bq_components_auto({"insider_pct": 8.0}, "compounder", {})
        self.assertEqual(mid["insider_ownership"], 0.0)
        high = compute_bq_components_auto({"insider_pct": 18.0}, "compounder", {})
        self.assertEqual(high["insider_ownership"], 2.0)
        low = compute_bq_components_auto({"insider_pct": 0.5}, "compounder", {})
        self.assertEqual(low["insider_ownership"], -1.0)

    def test_business_type_avoids_low_yield_compounder_as_income(self):
        business_type, source = detect_business_type(
            {
                "quoteType": "EQUITY",
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "dividendYield": 0.37,
                "payoutRatio": 0.15,
            }
        )
        self.assertEqual(source, "auto")
        self.assertEqual(business_type, "compounder")

    def test_business_type_keeps_income_sector_and_high_yield_income(self):
        telecom_type, _ = detect_business_type(
            {
                "quoteType": "EQUITY",
                "sector": "Communication Services",
                "industry": "Telecom Services",
                "dividendYield": 7.3,
                "payoutRatio": 2.2,
            }
        )
        high_yield_type, _ = detect_business_type(
            {
                "quoteType": "EQUITY",
                "sector": "Industrials",
                "industry": "Diversified",
                "dividendYield": 0.06,
                "payoutRatio": 0.6,
            }
        )
        self.assertEqual(telecom_type, "income")
        self.assertEqual(high_yield_type, "income")

    def test_business_type_skips_non_equities(self):
        business_type, _ = detect_business_type({"quoteType": "ETF", "dividendYield": 1.2})
        self.assertEqual(business_type, "unknown")

    def test_telus_style_yield_trap(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = full_recalculation(
                "T.TO",
                info={
                    "quoteType": "EQUITY",
                    "sector": "Communication Services",
                    "industry": "Telecom Services",
                    "dividendYield": 0.073,
                    "payoutRatio": 2.2,
                },
                fundamentals={
                    "price": 22.05,
                    "market_cap": 25_000_000_000,
                    "fcf_ttm": 1_600_000_000,
                    "net_debt_stored": 27_500_000_000,
                    "fwd_revenue_stored": 20_400_000_000,
                    "annual_div_per_share_stored": 1.61,
                    "dividend_yield_5y_mean": 0.05,
                    "dividend_yield_5y_std": 0.0115,
                    "eps_ttm": 0.65,
                    "pe_20y_array": [12, 14, 18, 22, 25, 30, 35],
                },
                overrides={"bq_raw": -5},
                store_dir=Path(tmp),
            )
            self.assertEqual(record["business_type"], "income")
            self.assertTrue(record["yield_trap_warning"])
            mod = modify_signal("T.TO", "BUY", "long", record=record, store_dir=Path(tmp), persist=False)
            self.assertEqual(mod.verdict, "CANCEL BUY")

    def test_sell_yield_trap_hard_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = full_recalculation(
                "T.TO",
                info={"quoteType": "EQUITY", "sector": "Communication Services", "industry": "Telecom Services"},
                fundamentals={
                    "price": 22.05,
                    "market_cap": 25_000_000_000,
                    "annual_div_per_share_stored": 1.61,
                    "dividend_yield_5y_mean": 0.05,
                    "dividend_yield_5y_std": 0.0115,
                    "eps_ttm": 0.65,
                    "pe_20y_array": [12, 14, 18, 22, 25, 30, 35],
                },
                overrides={"bq_raw": 9},
                store_dir=Path(tmp),
            )
            self.assertTrue(record["yield_trap_warning"])
            layers_before = record.get("position_layers") or {}
            if not layers_before.get("core_fraction"):
                record["position_layers"] = {
                    "core_fraction": 0.8,
                    "tactical_fraction": 0.2,
                    "core_model": None,
                    "tactical_model": None,
                    "core_signal_date": None,
                    "tactical_signal_date": None,
                }
                save_record(record, Path(tmp))
            mod = modify_signal("T.TO", "SELL", "long", record=record, store_dir=Path(tmp), persist=False)
            self.assertEqual(mod.verdict, "HARD EXIT")
            self.assertEqual(mod.sizing_pct, 0.0)
            self.assertTrue(mod.yield_trap_warning)
            self.assertEqual(mod.position_layers.core_fraction, 0.0)
            self.assertEqual(mod.position_layers.tactical_fraction, 0.0)
            self.assertTrue(any("yield trap" in r.lower() for r in mod.rationale))

    def test_yield_trap_missing_zscore_false(self):
        record = default_record("T.TO")
        record.update(
            {
                "dividend_yield_current": 0.099,
                "dividend_yield_zscore": None,
                "dividend_yield_5y_mean": None,
                "dividend_yield_5y_std": None,
                "yield_trap_warning": True,
            }
        )
        self.assertFalse(is_yield_trap(record, "T.TO"))

    def test_compute_dividend_yield_stats_aligns_dividend_dates(self):
        """Dividend rows are timestamped 09:30 while closes are midnight; the stats
        must still line up. A constant dividend at a constant price is a zero-
        dispersion series -- the old 365-day rolling sum printed dispersion here
        purely because the window flipped between two and three payments."""
        import pandas as pd

        # Three years of semi-annual payments: the month-end series needs a full year of
        # complete trailing windows before it will report a distribution at all.
        idx = pd.date_range("2020-01-01", periods=1200, freq="D")
        close = pd.Series(20.0, index=idx)
        div_idx = pd.to_datetime([
            "2020-06-15 09:30:00", "2020-12-15 09:30:00",
            "2021-06-15 09:30:00", "2021-12-15 09:30:00",
            "2022-06-15 09:30:00", "2022-12-15 09:30:00",
            "2023-06-15 09:30:00",
        ])
        divs = pd.Series([0.5] * 7, index=div_idx)
        stats = compute_dividend_yield_stats(pd.DataFrame({"Close": close}), divs)
        self.assertIn("dividend_yield_5y_mean", stats)
        self.assertIn("dividend_yield_5y_std", stats)
        # Two payments of 0.5 a year against a flat 20.00 price = a flat 5% yield.
        self.assertAlmostEqual(stats["dividend_yield_5y_mean"], 0.05, places=4)
        self.assertEqual(stats["dividend_yield_5y_std"], 0.0)

    def test_compute_dividend_yield_stats_moves_when_the_dividend_moves(self):
        import pandas as pd

        idx = pd.date_range("2020-01-01", periods=1400, freq="D")
        close = pd.Series(20.0, index=idx)
        div_idx = pd.to_datetime(
            [
                "2020-06-15 09:30:00", "2020-12-15 09:30:00",
                "2021-06-15 09:30:00", "2021-12-15 09:30:00",
                "2022-06-15 09:30:00", "2022-12-15 09:30:00",
                "2023-06-15 09:30:00", "2023-12-15 09:30:00",
            ]
        )
        divs = pd.Series([0.5, 0.5, 0.5, 0.5, 0.7, 0.7, 0.7, 0.7], index=div_idx)
        stats = compute_dividend_yield_stats(pd.DataFrame({"Close": close}), divs)
        self.assertGreater(stats["dividend_yield_5y_std"], 0)

    def test_buy_verdict_and_position_layer(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = default_record("KXS.TO")
            record.update(
                {
                    "asset_type": "EQUITY",
                    "business_type": "saas",
                    "bq_raw": 9,
                    "valuation_tax": 0,
                    "conviction_score": 9,
                    "fs_score": 80,
                    "fs_class": "strong",
                    "fd_direction": "positive",
                }
            )
            save_record(record, Path(tmp))
            mod = modify_signal("KXS.TO", "BUY", "long", quant_model_name="DELTADRIFT_Monthly", store_dir=Path(tmp))
            self.assertEqual(mod.verdict, "MAX CONVICTION")
            self.assertEqual(mod.position_layers.core_fraction, 1.0)

    def test_fs_cap_differs_by_timeframe(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = default_record("WEAK")
            record.update(
                {
                    "asset_type": "EQUITY",
                    "business_type": "compounder",
                    "bq_raw": 8,
                    "fs_quality_base": 20,
                    "valuation_tax": 0,
                    "conviction_score": 8,
                    "fs_score": 20,
                    "fs_class": "weak",
                }
            )
            save_record(record, Path(tmp))
            long_mod = modify_signal("WEAK", "BUY", "long", store_dir=Path(tmp), persist=False)
            short_mod = modify_signal("WEAK", "BUY", "short", store_dir=Path(tmp), persist=False)
            self.assertEqual(long_mod.conviction_score, 1.0)
            self.assertEqual(long_mod.verdict, "CANCEL BUY")
            self.assertEqual(short_mod.conviction_score, 2.0)
            self.assertEqual(short_mod.verdict, "REDUCED BUY")

    def test_non_equity_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            mod = modify_signal("QQQ", "BUY", "short", store_dir=Path(tmp), persist=False)
            self.assertEqual(mod.verdict, "NOT_APPLICABLE")
            self.assertEqual(mod.asset_type, "ETF")

    def test_non_equity_full_recalc_has_no_conviction_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = full_recalculation(
                "QQQ",
                info={"quoteType": "ETF", "dividendYield": 1.2},
                fundamentals={"price": 700.0, "annual_div_per_share_stored": 1.7},
                store_dir=Path(tmp),
            )
            self.assertEqual(record["asset_type"], "ETF")
            self.assertIsNone(record["conviction_score"])
            self.assertIsNone(record["valuation_tax"])

    def test_missing_equity_record_needs_recalculation(self):
        with tempfile.TemporaryDirectory() as tmp:
            mod = modify_signal("KXS.TO", "BUY", "short", store_dir=Path(tmp), persist=False)
            self.assertEqual(mod.verdict, "NEEDS_FULL_RECALCULATION")
            self.assertIsNone(mod.conviction_score)

    def test_oey_does_not_improve_valuation_tax(self):
        record = {
            "business_type": "compounder",
            "ev_fwd_rev": 0.8,
            "pe_percentile_20y": 75,
            "owner_earnings_yield": 0.08,
        }
        self.assertEqual(calculate_valuation_tax(record), -2.0)

    def test_batch_overlay_preserves_source_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "signals.csv"
            pd.DataFrame(
                [
                    {
                        "Function": "TRENDPULSE",
                        "Symbol, Signal, Signal Date/Price[$]": "KXS.TO, Long, 2026-05-10 (Price: 158.73)",
                        "Interval, Confirmation Status": "Weekly, is CONFIRMED on 2026-05-08",
                    }
                ]
            ).to_csv(source, index=False)
            result = apply_to_signal_file(source, store_dir=Path(tmp))
            self.assertIn("Function", result.columns)
            self.assertIn("conviction_score", result.columns)
            self.assertIn("verdict", result.columns)

    def test_store_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = default_record("ABC")
            record["bq_raw"] = 4
            save_record(record, Path(tmp))
            loaded = load_record("ABC", Path(tmp))
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded["bq_raw"], 4)


class TestFundamentalsUpdate(unittest.TestCase):
    def test_map_yfinance_fundamentals_keeps_zero_values(self):
        mapped = map_yfinance_fundamentals(
            {
                "quoteType": "EQUITY",
                "currentPrice": 10.0,
                "marketCap": 1000.0,
                "trailingEps": 2.0,
                "totalRevenue": 500.0,
                "freeCashflow": 50.0,
                "totalDebt": 0.0,
                "totalCash": 0.0,
                "ebitda": 100.0,
                "dividendRate": 0.0,
                "sharesOutstanding": 100.0,
            }
        )
        self.assertEqual(mapped["quote_type"], "EQUITY")
        self.assertEqual(mapped["net_debt_stored"], 0.0)
        self.assertEqual(mapped["fcf_ttm"], 50.0)
        self.assertEqual(mapped["fcf_margin"], 0.1)

    def test_update_ticker_fundamentals_creates_record_without_network(self):
        def fake_fetcher(_ticker):
            return {
                "info": {
                    "quoteType": "EQUITY",
                    "sector": "Technology",
                    "industry": "Software",
                    "currentPrice": 100.0,
                    "marketCap": 1_000_000.0,
                    "trailingEps": 5.0,
                },
                "fundamentals": {
                    "price": 100.0,
                    "market_cap": 1_000_000.0,
                    "eps_ttm": 5.0,
                    "fcf_ttm": 80_000.0,
                    "net_debt_stored": 0.0,
                    "fwd_revenue_stored": 500_000.0,
                    "revenue_growth": 0.2,
                    "fcf_margin": 0.16,
                    "gross_margin": 0.7,
                },
            }

        with tempfile.TemporaryDirectory() as tmp:
            result = update_ticker_fundamentals("KXS.TO", mode="auto", fetcher=fake_fetcher, store_dir=Path(tmp))
            self.assertEqual(result["status"], "updated")
            record = load_record("KXS.TO", Path(tmp))
            self.assertIsNotNone(record)
            assert record is not None
            self.assertEqual(record["asset_type"], "EQUITY")
            self.assertIsNotNone(record["conviction_score"])
            self.assertIn("data_coverage", record)
            self.assertIn("missing_fields", record)

    def test_discover_universe_from_signal_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            signal_file = Path(tmp) / "2026-05-11_all_signal.csv"
            pd.DataFrame(
                [
                    {
                        "Function": "TRENDPULSE",
                        "Symbol, Signal, Signal Date/Price[$]": "KXS.TO, Long, 2026-05-10 (Price: 158.73)",
                        "Interval, Confirmation Status": "Weekly, is CONFIRMED on 2026-05-08",
                    }
                ]
            ).to_csv(signal_file, index=False)
            self.assertEqual(discover_universe(trade_store_dir=Path(tmp)), ["KXS.TO"])
            self.assertEqual(
                discover_universe(trade_store_dir=Path(tmp), extra_tickers=["AAPL"], include_signal_sources=False),
                ["AAPL"],
            )


class TestDataCoverage(unittest.TestCase):
  FULL_FUNDAMENTALS = {
      "price": 100.0,
      "market_cap": 1_000_000.0,
      "eps_ttm": 5.0,
      "eps_fwd": 6.0,
      "fcf_ttm": 80_000.0,
      "net_debt_stored": 10_000.0,
      "fwd_revenue_stored": 500_000.0,
      "annual_div_per_share_stored": 2.0,
      "revenue_growth": 0.12,
      "fcf_margin": 0.16,
      "gross_margin": 0.7,
      "net_debt_ebitda": 0.5,
      "distribution_coverage_ratio": 2.0,
      "gross_margin_trend": 0.01,
      "roic_proxy": 0.15,
      "pe_20y_array": [15.0, 18.0, 20.0, 22.0],
      "dividend_yield_5y_mean": 0.02,
      "dividend_yield_5y_std": 0.003,
      "revenue_accelerating": True,
      "insider_pct": 12.0,
  }

  def test_sparse_fundamentals_reports_missing_and_low_confidence(self):
      fundamentals = {"price": 50.0, "eps_ttm": 2.0, "market_cap": 1000.0}
      record = {
          "pe_ttm": 25.0,
          "ev_fwd_rev": 3.0,
          "owner_earnings_yield": 0.05,
          "bq_components": {"revenue_quality": 0.0, "growth_trajectory": 0.0},
      }
      coverage = assess_data_coverage(fundamentals, {"info": {}}, record, record["bq_components"])
      self.assertLess(coverage["coverage_ratio"], 1.0)
      self.assertIn("fcf_ttm", coverage["fields_missing"])
      self.assertTrue(coverage["low_data_confidence"])

  def test_full_fundamentals_high_coverage(self):
      fundamentals = dict(self.FULL_FUNDAMENTALS)
      record = {
          "pe_ttm": 20.0,
          "pe_percentile_20y": 0.4,
          "ev_fwd_rev": 2.5,
          "owner_earnings_yield": 0.08,
          "bq_components": {"revenue_quality": 2.0, "balance_sheet": 1.0},
      }
      raw = {
          "info": {"quoteType": "EQUITY", "sector": "Technology"},
          "quarterly_income": pd.DataFrame({"Total Revenue": [1, 2, 3, 4]}),
          "quarterly_balance": pd.DataFrame({"Total Debt": [1]}),
          "quarterly_cashflow": pd.DataFrame({"Operating Cash Flow": [1]}),
      }
      coverage = assess_data_coverage(fundamentals, raw, record, record["bq_components"], info=raw["info"])
      self.assertGreaterEqual(coverage["coverage_ratio"], 0.9)
      self.assertFalse(coverage["low_data_confidence"])
      self.assertTrue(coverage["statements"]["income"])

  def test_valuation_inputs_flag_missing_pe_percentile(self):
      fundamentals = {"price": 100.0, "eps_ttm": 5.0, "market_cap": 1_000_000.0, "fwd_revenue_stored": 400_000.0}
      record = {
          "pe_ttm": 20.0,
          "pe_percentile_20y": None,
          "ev_fwd_rev": 2.5,
          "owner_earnings_yield": 0.08,
          "bq_components": {},
      }
      coverage = assess_data_coverage(fundamentals, {"info": {"quoteType": "EQUITY"}}, record)
      self.assertFalse(coverage["valuation_inputs"]["pe_percentile_20y"])
      self.assertIn("valuation:pe_percentile_20y", missing_fields_list(coverage))

  def test_full_recalculation_persists_data_coverage(self):
      with tempfile.TemporaryDirectory() as tmp:
          fundamentals = {
              "price": 100.0,
              "market_cap": 1_000_000.0,
              "eps_ttm": 5.0,
              "fcf_ttm": 80_000.0,
              "fwd_revenue_stored": 500_000.0,
              "revenue_growth": 0.2,
              "fcf_margin": 0.16,
              "gross_margin": 0.7,
              "net_debt_stored": 0.0,
          }
          raw_fetch = {
              "info": {"quoteType": "EQUITY", "sector": "Technology"},
              "quarterly_income": pd.DataFrame({"Total Revenue": [1, 2, 3, 4]}),
          }
          record = full_recalculation(
              "COVTEST",
              fundamentals=fundamentals,
              info=raw_fetch["info"],
              raw_fetch=raw_fetch,
              store_dir=Path(tmp),
          )
          self.assertIn("data_coverage", record)
          self.assertIn("missing_fields", record)
          self.assertIsInstance(record["data_coverage"]["coverage_ratio"], float)
          self.assertLessEqual(len(record["missing_fields"]), len(CRITICAL_FIELDS) + 10)


class TestDailyConvictionPipeline(unittest.TestCase):
    def test_resolve_report_date_from_dated_filename(self):
        from src.conviction_engine.signals import resolve_report_date

        with tempfile.TemporaryDirectory() as tmp:
            trade_dir = Path(tmp)
            (trade_dir / "2026-05-15_new_signal.csv").write_text("Function\n", encoding="utf-8")
            self.assertEqual(resolve_report_date(trade_dir), "2026-05-15")

    def test_discover_daily_signal_files_default_new_signal_only(self):
        from src.conviction_engine.signals import PRIMARY_DAILY_REPORT_LABEL, discover_daily_signal_files

        with tempfile.TemporaryDirectory() as tmp:
            trade_dir = Path(tmp)
            (trade_dir / "2026-05-15_all_signal.csv").write_text("Function\n", encoding="utf-8")
            (trade_dir / "2026-05-15_new_signal.csv").write_text("Function\n", encoding="utf-8")
            (trade_dir / "2026-05-15_outstanding_signal.csv").write_text("Function\n", encoding="utf-8")
            found = discover_daily_signal_files("2026-05-15", trade_dir)
            self.assertEqual(list(found.keys()), [PRIMARY_DAILY_REPORT_LABEL])

    def test_discover_daily_signal_files_multi_when_requested(self):
        from src.conviction_engine.signals import discover_daily_signal_files

        with tempfile.TemporaryDirectory() as tmp:
            trade_dir = Path(tmp)
            (trade_dir / "2026-05-15_all_signal.csv").write_text("Function\n", encoding="utf-8")
            (trade_dir / "2026-05-15_new_signal.csv").write_text("Function\n", encoding="utf-8")
            found = discover_daily_signal_files(
                "2026-05-15",
                trade_dir,
                overlay_reports=["all_signal.csv", "new_signal.csv"],
            )
            self.assertIn("All Signal Report", found)
            self.assertIn("New Signals", found)

    def test_daily_snapshot_store_helpers(self):
        from src.conviction_engine.store import (
            daily_new_signal_overlay_path,
            list_daily_snapshot_dates,
            load_daily_new_signal_overlay,
        )

        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp)
            day_dir = store / "daily" / "2026-05-15"
            day_dir.mkdir(parents=True)
            overlay = day_dir / "2026-05-15_new_signal_conviction.csv"
            overlay.write_text(
                "Function,ticker,conviction_score\nTRENDPULSE,AAPL,5.0\n",
                encoding="utf-8",
            )
            self.assertEqual(list_daily_snapshot_dates(store), ["2026-05-15"])
            self.assertEqual(daily_new_signal_overlay_path("2026-05-15", store), overlay)
            df = load_daily_new_signal_overlay("2026-05-15", store)
            self.assertEqual(len(df), 1)
            self.assertAlmostEqual(float(df.iloc[0]["conviction_score"]), 5.0)

    def test_conviction_score_sheet_columns(self):
        from src.conviction_engine.daily_run import conviction_score_sheet

        df = pd.DataFrame(
            {
                "Function": ["TRENDPULSE"],
                "Symbol, Signal, Signal Date/Price[$]": ["AAPL, Long, 2026-05-01 (Price: 100)"],
                "ticker": ["AAPL"],
                "conviction_score": [5.5],
                "verdict": ["BUY"],
                "rationale": ["ok"],
                "extra_col": [1],
            }
        )
        sheet = conviction_score_sheet(df)
        self.assertIn("conviction_score", sheet.columns)
        self.assertNotIn("extra_col", sheet.columns)


class TestPeHistory(unittest.TestCase):
    def test_uses_historical_price_and_point_in_time_eps(self):
        from src.conviction_engine.fundamentals_enriched import compute_pe_history

        quarter_ends = pd.to_datetime(
            ["2019-03-31", "2019-06-30", "2019-09-30", "2019-12-31", "2020-03-31", "2020-06-30"]
        )
        quarterly_eps = pd.Series([1.0, 1.0, 1.0, 1.0, 2.0, 2.0], index=quarter_ends)
        price_dates = pd.to_datetime(["2020-01-15", "2020-04-15", "2020-07-15", "2020-10-15"])
        prices = pd.Series([10.0, 20.0, 30.0, 40.0], index=price_dates)
        pe_bundle = compute_pe_history(prices, quarterly_eps)
        pe_hist = pe_bundle["values"]
        self.assertTrue(pe_hist)
        # Jan 2020: last report 2019-12-31, TTM EPS = 4.0 → PE = 10/4 = 2.5
        self.assertAlmostEqual(pe_hist[0], 2.5, places=3)
        # Oct 2020: last report 2020-06-30, TTM EPS = 1+1+2+2 = 6 → PE = 40/6
        self.assertAlmostEqual(pe_hist[-1], 40.0 / 6.0, places=3)
        self.assertTrue(pe_bundle["meta"]["insufficient_20y"])

    def test_not_flat_when_only_today_price_would_be_used(self):
        from src.conviction_engine.fundamentals_enriched import compute_pe_history

        quarter_ends = pd.to_datetime(
            ["2020-03-31", "2020-06-30", "2020-09-30", "2020-12-31", "2021-03-31", "2021-06-30"]
        )
        quarterly_eps = pd.Series([2.0, 2.0, 2.0, 2.0, 2.0, 2.0], index=quarter_ends)
        prices = pd.Series(
            [20.0, 40.0],
            index=pd.to_datetime(["2021-01-15", "2021-08-15"]),
        )
        pe_bundle = compute_pe_history(prices, quarterly_eps)
        pe_hist = pe_bundle["values"]
        self.assertEqual(len(pe_hist), 2)
        self.assertNotAlmostEqual(pe_hist[0], pe_hist[1], places=3)


class TestPeHistoryWithLegacyAnnual(unittest.TestCase):
    """compute_pe_history_with_legacy_annual — the merge point for pe_history_sec_legacy.py's
    pre-2009 annual EPS extension (see that module's docstring for the EX-27/Selected
    Financial Data sourcing)."""

    def _modern_quarterly_eps(self) -> pd.Series:
        dates = pd.date_range("2019-03-31", periods=32, freq="QE")  # 2019-2026, stays current
        return pd.Series([1.0 + 0.02 * i for i in range(32)], index=dates)

    def _long_price_series(self) -> pd.Series:
        return pd.Series(
            [10.0 + i * 0.05 for i in range(320)],
            index=pd.date_range("2001-01-31", periods=320, freq="ME"),
        )

    def test_extends_years_available_and_flips_insufficient_flag(self):
        from src.conviction_engine.pe_history_core import compute_pe_history, compute_pe_history_with_legacy_annual

        modern_eps = self._modern_quarterly_eps()
        prices = self._long_price_series()
        legacy_eps = pd.Series(
            [0.2 + 0.02 * i for i in range(18)],
            index=pd.date_range("2000-12-31", periods=18, freq="YE"),
        )

        plain = compute_pe_history(prices, modern_eps)
        extended = compute_pe_history_with_legacy_annual(prices, modern_eps, legacy_eps)

        self.assertTrue(plain["meta"]["insufficient_20y"])
        self.assertFalse(extended["meta"]["insufficient_20y"])
        self.assertGreater(extended["meta"]["years_available"], plain["meta"]["years_available"])
        self.assertEqual(extended["meta"]["start_date"], "2001-01-31")

    def test_empty_or_none_legacy_series_matches_plain_compute(self):
        from src.conviction_engine.pe_history_core import compute_pe_history, compute_pe_history_with_legacy_annual

        modern_eps = self._modern_quarterly_eps()
        prices = self._long_price_series()
        plain = compute_pe_history(prices, modern_eps)

        self.assertEqual(compute_pe_history_with_legacy_annual(prices, modern_eps, pd.Series(dtype=float)), plain)
        self.assertEqual(compute_pe_history_with_legacy_annual(prices, modern_eps, None), plain)

    def test_legacy_points_overlapping_modern_coverage_are_dropped(self):
        """A legacy point landing on/after the modern series' earliest TTM date must
        never override or duplicate it — only strictly-older legacy points are used."""
        from src.conviction_engine.pe_history_core import compute_pe_history_with_legacy_annual

        modern_eps = self._modern_quarterly_eps()
        prices = self._long_price_series()
        legacy_eps = pd.Series(
            [0.2, 0.25, 99.0],  # last point deliberately overlaps modern coverage
            index=[pd.Timestamp("2010-12-31"), pd.Timestamp("2011-12-31"), modern_eps.index[3]],
        )
        bundle = compute_pe_history_with_legacy_annual(prices, modern_eps, legacy_eps)
        # earliest *usable* legacy point is 2010-12-31 (the 99.0 point is dropped as an
        # overlap, so it can't push coverage back to an earlier or corrupted start)
        self.assertEqual(bundle["meta"]["start_date"], "2010-12-31")
        # and the modern-era point that 99.0 tried to duplicate keeps its correct value
        without_overlap = compute_pe_history_with_legacy_annual(
            prices, modern_eps, legacy_eps.iloc[:2]  # same series minus the overlapping point
        )
        self.assertEqual(bundle["values"], without_overlap["values"])

    def test_price_series_none_returns_empty_bundle(self):
        from src.conviction_engine.pe_history_core import compute_pe_history_with_legacy_annual

        bundle = compute_pe_history_with_legacy_annual(None, self._modern_quarterly_eps(), pd.Series([0.5], index=[pd.Timestamp("2005-01-01")]))
        self.assertEqual(bundle["values"], [])
        self.assertTrue(bundle["meta"]["insufficient_20y"])


class TestPeHistoryDistribution(unittest.TestCase):
    def test_summarize_pe_history_distribution_buckets(self):
        from src.conviction_engine.data_coverage import summarize_pe_history_distribution

        records = [
            {
                "ticker": "OLD",
                "asset_type": "EQUITY",
                "conviction_score": 3.0,
                "pe_history_meta": {"years_available": 22.0, "insufficient_20y": False},
                "pe_20y_array": [1.0, 2.0],
            },
            {
                "ticker": "IPO",
                "asset_type": "EQUITY",
                "conviction_score": 1.0,
                "pe_history_meta": {"years_available": 3.5, "insufficient_20y": True},
                "pe_20y_array": [1.0],
            },
        ]
        summary = summarize_pe_history_distribution(records)
        self.assertEqual(summary["total_equity_records"], 2)
        self.assertEqual(summary["insufficient_20y_count"], 1)
        buckets = {row["bucket"]: row["count"] for row in summary["years_distribution"]}
        self.assertEqual(buckets.get("20+"), 1)
        self.assertEqual(buckets.get("2-5"), 1)


class TestV6Scoring(unittest.TestCase):
    def test_score_manual_ceo_quality_four(self):
        self.assertEqual(score_manual("ceo_quality_score", {"ceo_quality_score": 4}), 0.0)
        self.assertEqual(score_manual("ceo_quality_score", {"ceo_quality_score": 2}), -1.0)
        self.assertEqual(score_manual("ceo_quality_score", {"ceo_quality_score": 8}), 2.0)

    def test_debt_purpose_financial_engineering(self):
        purpose = classify_debt_purpose(
            {"net_debt_stored": -50_000_000_000, "cash_and_equivalents": 100e9, "total_debt": 50e9}
        )
        self.assertEqual(purpose, "financial_engineering")
        score, p = score_balance_sheet_v6(
            {"net_debt_stored": -50e9, "cash_and_equivalents": 100e9, "total_debt": 50e9},
            "compounder",
            {},
        )
        self.assertEqual(p, "financial_engineering")
        self.assertEqual(score, 2.0)

    def test_fd_votes_no_majority_stable(self):
        bundle = compute_fd_votes(
            {
                "revenue_accelerating": True,
                "gross_margin_trend": 0.02,
                "fcf_growth_yoy": -0.1,
                "shares_outstanding_change_pct": 0.02,
            }
        )
        self.assertEqual(bundle["fd_direction"], "stable")
        self.assertEqual(bundle["positive_count"], 2)
        self.assertEqual(bundle["negative_count"], 2)

    def test_yield_trap_at_threshold(self):
        record = {
            "dividend_yield_zscore": 2.0,
            "dividend_yield_current": 0.07,
        }
        self.assertTrue(is_yield_trap(record, "T.TO"))

    def test_bq_auto_uses_manual_mapping(self):
        comps = compute_bq_components_auto(
            {},
            "compounder",
            {"ceo_quality_score": 2, "mgmt_alloc_score": 6, "competitive_moat_score": 9},
        )
        self.assertEqual(comps["ceo_quality"], -1.0)
        self.assertEqual(comps["mgmt_capital_allocation"], 1.0)
        self.assertEqual(comps["competitive_moat"], 2.0)


class TestJuly2026FundamentalUpdates(unittest.TestCase):
    def test_reinvestment_runway_threshold_ten_x(self):
        from src.conviction_engine.scoring import _score_reinvestment

        self.assertEqual(_score_reinvestment(11), 1.0)
        self.assertEqual(_score_reinvestment(10), 0.0)
        self.assertEqual(_score_reinvestment(2), -1.0)

    def test_capital_allocation_buyback_scoring(self):
        from src.conviction_engine.capital_allocation import score_capital_allocation

        score, detail = score_capital_allocation({"shares_outstanding_change_pct": -0.071})
        self.assertEqual(score, 2.0)
        self.assertGreater(detail.get("buyback_pct", 0), 0.05)

    def test_divergence_persistence_counter(self):
        from src.conviction_engine.divergence import detect_divergence_signal, update_divergence_state

        record: dict = {}
        update_divergence_state(record, current_price=50.0, fifty_two_week_high=100.0, as_of=__import__("datetime").date(2026, 1, 1))
        self.assertEqual(record["days_below_high"], 1)
        update_divergence_state(record, current_price=50.0, fifty_two_week_high=100.0, as_of=__import__("datetime").date(2026, 3, 1))
        self.assertEqual(record["days_below_high"], 2)
        self.assertTrue(
            detect_divergence_signal(
                current_price=50.0,
                fifty_two_week_high=100.0,
                days_below_high=65,
                fd_direction="positive",
            )
        )

    def test_pe_percentile_neutral_when_eps_missing(self):
        from src.conviction_engine.engine import daily_update

        with tempfile.TemporaryDirectory() as tmp:
            record = default_record("NOPETEST")
            record.update(
                {
                    "asset_type": "EQUITY",
                    "quote_type": "EQUITY",
                    "bq_raw": 4.0,
                    "eps_ttm": None,
                    "pe_20y_array": [10.0, 12.0, 15.0],
                    "market_cap": 1_000_000.0,
                    "fcf_ttm": 100_000.0,
                    "fwd_revenue_stored": 500_000.0,
                }
            )
            out = daily_update("NOPETEST", record=record, market_data={"price": 100.0}, store_dir=Path(tmp), save=False)
            self.assertIsNone(out.get("pe_ttm"))
            self.assertIsNone(out.get("pe_percentile_20y"))
            components = (out.get("valuation_tax_breakdown") or {}).get("components", {})
            self.assertEqual(components.get("pe_hist_percentile"), 0.0)

    def test_fd_sizing_in_verdict_not_multiplier(self):
        verdict, sizing = verdict_for_buy(6.0, "positive")
        self.assertEqual(verdict, "TACTICAL BUY")
        self.assertEqual(sizing, 85.0)
        verdict_neg, sizing_neg = verdict_for_buy(6.0, "negative")
        self.assertEqual(sizing_neg, 60.0)

    def test_ceo_transition_penalty(self):
        from src.conviction_engine.ceo_quality import compute_ceo_quality_score

        score, detail = compute_ceo_quality_score(
            {"ticker": "PYPL"},
            {"ceo_start_date": "2026-03-01"},
        )
        self.assertEqual(score, -1.0)
        self.assertLess(detail.get("ceo_tenure_months", 99), 12)

    def test_revenue_acceleration_yoy_quarterly(self):
        import pandas as pd
        from src.conviction_engine.fundamentals_enriched import build_fundamentals_from_raw

        dates = pd.date_range("2023-01-01", periods=8, freq="QE")
        rev = pd.Series([100, 110, 120, 130, 140, 155, 170, 190], index=dates)
        q_inc = pd.DataFrame([rev.values], index=["Total Revenue"], columns=rev.index)
        raw = {
            "ticker": "TEST",
            "info": {"quoteType": "EQUITY"},
            "fast_info": {},
            "quarterly_income": q_inc,
            "errors": [],
        }
        out = build_fundamentals_from_raw(raw)
        self.assertTrue(out.get("revenue_accelerating"))

    def test_ttm_and_balance_sheet_fields_use_latest_quarter_not_oldest(self):
        """Regression: _df_row / _df_ttm_sum must sort ascending before slicing — yfinance
        quarterly columns are newest-first, and iloc[-1]/iloc[-periods:] on the raw (unsorted)
        columns silently returns the OLDEST quarter/quarters instead of the latest (same bug
        class fixed for revenue_growth_yoy on 2026-07-22)."""
        import pandas as pd
        from src.conviction_engine.fundamentals_enriched import build_fundamentals_from_raw

        # 8 quarters, newest-first column order (Q8..Q1) — matches real yfinance output.
        dates_desc = pd.date_range("2023-01-01", periods=8, freq="QE")[::-1]
        revenue = [170, 160, 150, 140, 130, 120, 110, 100]  # Q8..Q1
        debt = [64, 62, 60, 58, 56, 54, 52, 50]
        cash = [17, 16, 15, 14, 13, 12, 11, 10]
        ocf = [40, 38, 36, 34, 32, 30, 28, 26]
        capex = [-5, -5, -5, -5, -4, -4, -4, -4]

        q_inc = pd.DataFrame([revenue], index=["Total Revenue"], columns=dates_desc)
        q_bal = pd.DataFrame(
            [debt, cash], index=["Total Debt", "Cash And Cash Equivalents"], columns=dates_desc,
        )
        q_cf = pd.DataFrame(
            [ocf, capex], index=["Operating Cash Flow", "Capital Expenditure"], columns=dates_desc,
        )

        raw = {
            "ticker": "TEST3",
            "info": {"quoteType": "EQUITY"},
            "fast_info": {},
            "quarterly_income": q_inc,
            "quarterly_balance": q_bal,
            "quarterly_cashflow": q_cf,
            "errors": [],
        }
        out = build_fundamentals_from_raw(raw)

        # Latest chronological quarter (Q8) must win, not the DataFrame's first column.
        self.assertEqual(out["total_debt"], 64)
        self.assertEqual(out["cash_and_equivalents"], 17)
        self.assertEqual(out["net_debt_stored"], 64 - 17)

        # TTM = sum of the 4 most recent quarters (Q5-Q8: 140+150+160+170), not the 4 oldest.
        self.assertEqual(out["revenue_ttm"], 140 + 150 + 160 + 170)
        self.assertEqual(out["fcf_ttm"], (34 + 36 + 38 + 40) + (-5 - 5 - 5 - 5))

        # Prior-year (Q1-Q4) FCF must use the quarters before the current TTM window.
        self.assertEqual(out["fcf_prior_year"], (26 + 28 + 30 + 32) + (-4 - 4 - 4 - 4))


if __name__ == "__main__":
    unittest.main()
