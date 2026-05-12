"""Unit tests for src.utils.mtm_pricing (MTM, latest price, batch consistency)."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from src.utils.mtm_pricing import (
    batch_latest_prices,
    calculate_mark_to_market,
    get_latest_price_from_stock_data,
    parse_mtm_holding_cell,
    parse_symbol_signal_column,
    resolve_signal_basis,
)


class TestLatestPriceFromCsv(unittest.TestCase):
    def test_unsorted_dates_picks_latest_calendar_row(self):
        with TemporaryDirectory() as td:
            stock_dir = Path(td)
            csv_path = stock_dir / "ZZZ.csv"
            df = pd.DataFrame(
                {
                    "Date": ["2025-01-02", "2025-01-10", "2025-01-05"],
                    "Close": [10.0, 99.0, 50.0],
                }
            )
            df.to_csv(csv_path, index=False)

            price, d = get_latest_price_from_stock_data("ZZZ", stock_dir)
            self.assertEqual(d, "2025-01-10")
            self.assertAlmostEqual(price, 99.0, places=5)


class TestParseMtmHoldingCell(unittest.TestCase):
    def test_positive_mtm_and_days(self):
        m, d = parse_mtm_holding_cell("12.34%, 5 days")
        self.assertEqual(m, "12.34%")
        self.assertEqual(d, 5)

    def test_negative_mtm(self):
        m, d = parse_mtm_holding_cell("-3.00%, 10 days")
        self.assertEqual(m, "-3.00%")
        self.assertEqual(d, 10)

    def test_invalid_returns_none(self):
        self.assertEqual(parse_mtm_holding_cell(""), (None, None))
        self.assertEqual(parse_mtm_holding_cell(None), (None, None))


class TestShortMtm(unittest.TestCase):
    def test_short_inverts_mtm(self):
        long_m = calculate_mark_to_market(90.0, 100.0, "Long")
        short_m = calculate_mark_to_market(90.0, 100.0, "SHORT")
        self.assertEqual(long_m, "-10.00%")
        self.assertEqual(short_m, "10.00%")


class TestResolveSignalBasis(unittest.TestCase):
    def test_prefers_signal_open_price_when_valid(self):
        compound = "FOO, Long, 2025-01-01 (Price: 100.0)"
        p, sig_type, sig_date = resolve_signal_basis("95.5", compound)
        self.assertAlmostEqual(p, 95.5, places=4)
        self.assertEqual(sig_type, "Long")
        self.assertEqual(sig_date, "2025-01-01")

    def test_falls_back_to_compound_price(self):
        compound = "FOO, Long, 2025-01-01 (Price: 100.0)"
        p, _, _ = resolve_signal_basis("", compound)
        self.assertAlmostEqual(p, 100.0, places=4)


class TestBatchLatestPrices(unittest.TestCase):
    def test_same_snapshot_for_repeated_symbol(self):
        with TemporaryDirectory() as td:
            stock_dir = Path(td)
            csv_path = stock_dir / "BAT.csv"
            pd.DataFrame({"Date": ["2025-06-01"], "Close": [42.0]}).to_csv(csv_path, index=False)

            mp = batch_latest_prices(["BAT", "BAT", "BAT"], stock_dir)
            self.assertEqual(len(mp), 1)
            p, d = mp["BAT"]
            self.assertAlmostEqual(p, 42.0, places=5)
            self.assertEqual(d, "2025-06-01")


class TestParseSymbolSignal(unittest.TestCase):
    def test_parse_basic(self):
        s, dt, st, pr = parse_symbol_signal_column(
            "ETH-USD, Long, 2025-10-10 (Price: 4369.1436)"
        )
        self.assertEqual(s, "ETH-USD")
        self.assertEqual(dt, "2025-10-10")
        self.assertEqual(st, "Long")
        self.assertAlmostEqual(pr, 4369.1436, places=4)


if __name__ == "__main__":
    unittest.main()
