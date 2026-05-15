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

from src.conviction_engine.engine import apply_to_signal_file, full_recalculation, modify_signal
from src.conviction_engine.fundamentals import (
    discover_universe,
    map_yfinance_fundamentals,
    update_ticker_fundamentals,
)
from src.conviction_engine.models import default_record
from src.conviction_engine.scoring import calculate_valuation_tax, detect_business_type
from src.conviction_engine.signals import normalize_signal_row, signal_timeframe_from_interval
from src.conviction_engine.store import load_record, save_record


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


if __name__ == "__main__":
    unittest.main()
