"""Tests for smart data fetcher date filtering and outstanding fallback."""

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd

from chatbot.smart_data_fetcher import (
    SmartDataFetcher,
    infer_date_filter_mode,
    _is_open_exit_value,
    SYMBOL_SIGNAL_COMPOUND_COL,
    EXIT_DATE_COL,
)


class TestInferDateFilterMode(unittest.TestCase):
    def test_deep_dive(self):
        self.assertEqual(
            infer_date_filter_mode("Please run a deep dive on MSFT"),
            "entry_or_exit",
        )

    def test_entry_or_exit_phrase(self):
        self.assertEqual(
            infer_date_filter_mode("Use entry and / or exit-date range as the filter"),
            "entry_or_exit",
        )

    def test_default_primary(self):
        self.assertEqual(infer_date_filter_mode("show AAPL signals"), "primary")


class TestEntryOrExitWindow(unittest.TestCase):
    def test_open_before_window_counts(self):
        from_dt = pd.Timestamp("2026-04-01")
        to_dt = pd.Timestamp("2026-05-16")
        entry = pd.Timestamp("2026-03-11")
        self.assertTrue(
            SmartDataFetcher._row_in_entry_or_exit_window(
                entry, pd.NaT, from_dt, to_dt, "entry"
            )
        )

    def test_exit_before_window_excluded(self):
        from_dt = pd.Timestamp("2026-04-01")
        to_dt = pd.Timestamp("2026-05-16")
        entry = pd.Timestamp("2026-02-06")
        exit_dt = pd.Timestamp("2026-03-24")
        self.assertFalse(
            SmartDataFetcher._row_in_entry_or_exit_window(
                entry, exit_dt, from_dt, to_dt, "exit"
            )
        )

    def test_entry_inside_window(self):
        from_dt = pd.Timestamp("2026-04-01")
        to_dt = pd.Timestamp("2026-05-16")
        entry = pd.Timestamp("2026-04-10")
        self.assertTrue(
            SmartDataFetcher._row_in_entry_or_exit_window(
                entry, pd.NaT, from_dt, to_dt, "entry"
            )
        )


class TestOutstandingFallback(unittest.TestCase):
    def test_falls_back_to_entry_csv_when_asset_missing_from_outstanding(self):
        with TemporaryDirectory() as td:
            us = Path(td) / "US"
            us.mkdir(parents=True)
            outstanding = us / "2026-05-15_outstanding_signal.csv"
            header = (
                f'Function,"{SYMBOL_SIGNAL_COMPOUND_COL}",{EXIT_DATE_COL}\n'
            )
            outstanding.write_text(
                header
                + 'FRACTAL TRACK,"AAPL, Long, 2026-05-15 (Price: 100.0)",No Exit Yet\n',
                encoding="utf-8",
            )

            entry_csv = Path(td) / "entry.csv"
            entry_csv.write_text(
                header
                + 'TRENDPULSE,"MSFT, Long, 2026-03-11 (Price: 400.0)",No Exit Yet\n'
                + 'TRENDPULSE,"MSFT, Long, 2026-01-01 (Price: 380.0)",2026-02-01 (Price: 390.0)\n',
                encoding="utf-8",
            )

            fetcher = SmartDataFetcher(use_consolidated_csvs=True)
            with patch(
                "chatbot.smart_data_fetcher.resolve_outstanding_signal_path",
                return_value=outstanding,
            ), patch(
                "chatbot.smart_data_fetcher.resolve_all_signal_path",
                return_value=None,
            ), patch(
                "chatbot.smart_data_fetcher.trade_store_us_dir",
                return_value=us,
            ), patch.object(fetcher, "entry_csv", entry_csv), patch.object(
                fetcher, "_get_consolidated_csv_path", lambda st: entry_csv if st == "entry" else Path()
            ):
                df = fetcher._load_entry_source_dataframe(assets=["MSFT"])
            self.assertEqual(len(df), 1)
            self.assertIn("MSFT", df[SYMBOL_SIGNAL_COMPOUND_COL].iloc[0])


class TestAllSignalSupplement(unittest.TestCase):
    def test_byddy_gets_pulsegauge_apr_23_from_all_signal(self):
        fetcher = SmartDataFetcher()
        r = fetcher.fetch_data(
            signal_types=["entry"],
            required_columns=None,
            assets=["BYDDY"],
            from_date="2026-04-01",
            to_date="2026-05-18",
            date_filter_mode="entry_or_exit",
        )
        df = r.get("entry")
        self.assertIsNotNone(df)
        self.assertGreater(len(df), 0)
        mask_423 = df[SYMBOL_SIGNAL_COMPOUND_COL].astype(str).str.contains("2026-04-23")
        self.assertTrue(mask_423.any(), "Expected 2026-04-23 entry in fetch")
        funcs = df.loc[mask_423, "Function"].astype(str).tolist()
        self.assertIn("PULSEGAUGE", funcs, f"Expected PULSEGAUGE on 2026-04-23; got {funcs}")

    def test_byddy_gets_fractal_apr_28_from_virtual_trading(self):
        fetcher = SmartDataFetcher()
        r = fetcher.fetch_data(
            signal_types=["entry"],
            required_columns=None,
            assets=["BYDDY"],
            from_date="2026-04-01",
            to_date="2026-05-18",
            date_filter_mode="entry_or_exit",
        )
        df = r.get("entry")
        compounds = df[SYMBOL_SIGNAL_COMPOUND_COL].astype(str).tolist()
        self.assertTrue(
            any("2026-04-28" in c for c in compounds),
            msg=f"Expected FRACTAL 2026-04-28 from virtual_trading; got keys: {compounds}",
        )


class TestIsOpenExitValue(unittest.TestCase):
    def test_no_exit_yet(self):
        self.assertTrue(_is_open_exit_value("No Exit Yet"))

    def test_closed(self):
        self.assertFalse(_is_open_exit_value("2026-03-24 (Price: 372.74)"))


if __name__ == "__main__":
    unittest.main()
