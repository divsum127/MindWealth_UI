"""Tests for scripts/set_manual_pe_history.py, including a round trip through
daily_update() and calculate_valuation_tax_components() to confirm a manually-entered
P/E series drives the PE-percentile valuation tax component exactly like an
auto-fetched (yfinance/FMP) series would.
"""

from __future__ import annotations

import csv
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_SCRIPT_PATH = _ROOT / "scripts" / "set_manual_pe_history.py"
_spec = importlib.util.spec_from_file_location("set_manual_pe_history", _SCRIPT_PATH)
set_manual_pe_history = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(set_manual_pe_history)

from src.conviction_engine.engine import daily_update  # noqa: E402
from src.conviction_engine.scoring import calculate_valuation_tax_components  # noqa: E402
from src.conviction_engine.store import load_record  # noqa: E402


def _write_csv(path: Path, rows: list[tuple[str, float]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["date", "pe"])
        for date_str, pe in rows:
            writer.writerow([date_str, pe])


class TestParsePeHistoryCsv(unittest.TestCase):
    def test_parses_and_sorts(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "pe.csv"
            _write_csv(csv_path, [("2020-06-30", 20.0), ("2020-01-31", 15.0)])
            rows = set_manual_pe_history.parse_pe_history_csv(csv_path)
            self.assertEqual(rows, [("2020-01-31", 15.0), ("2020-06-30", 20.0)])

    def test_missing_columns_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "bad.csv"
            csv_path.write_text("foo,bar\n1,2\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                set_manual_pe_history.parse_pe_history_csv(csv_path)

    def test_invalid_date_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "bad.csv"
            _write_csv(csv_path, [("not-a-date", 15.0)])
            with self.assertRaises(ValueError):
                set_manual_pe_history.parse_pe_history_csv(csv_path)

    def test_out_of_range_pe_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "bad.csv"
            _write_csv(csv_path, [("2020-01-31", 9999.0)])
            with self.assertRaises(ValueError):
                set_manual_pe_history.parse_pe_history_csv(csv_path)


class TestBuildManualPeBundle(unittest.TestCase):
    def test_insufficient_when_span_short(self):
        bundle = set_manual_pe_history.build_manual_pe_bundle([("2023-01-31", 20.0), ("2023-06-30", 22.0)])
        self.assertTrue(bundle["meta"]["insufficient_20y"])
        self.assertEqual(bundle["meta"]["source"], "manual")

    def test_sufficient_when_span_long(self):
        rows = [(f"{year}-06-30", 15.0 + year % 5) for year in range(2000, 2025)]
        bundle = set_manual_pe_history.build_manual_pe_bundle(rows)
        self.assertFalse(bundle["meta"]["insufficient_20y"])
        self.assertGreaterEqual(bundle["meta"]["years_available"], 20.0)


class TestManualEntryRoundTrip(unittest.TestCase):
    """Full pipeline: CSV -> script -> conviction_store JSON -> daily_update ->
    calculate_valuation_tax_components, for a non-US ticker (INFY.NS)."""

    def test_round_trip_drives_pe_hist_percentile(self):
        with tempfile.TemporaryDirectory() as tmp:
            store_dir = Path(tmp) / "conviction_store"
            csv_path = Path(tmp) / "infy_pe.csv"

            # 26 years of monthly PE values, low->high, so a near-max pe_ttm lands
            # near the 100th percentile deterministically.
            rows: list[tuple[str, float]] = []
            for year in range(1999, 2025):
                for month in (6, 12):
                    day = 30 if month in (6, 9, 11) else 31
                    rows.append((f"{year}-{month:02d}-{day:02d}", 10.0 + (year - 1999) * 1.0))
            _write_csv(csv_path, rows)

            exit_code = set_manual_pe_history.main(
                ["INFY.NS", "--csv", str(csv_path), "--store-dir", str(store_dir)]
            )
            self.assertEqual(exit_code, 0)

            record = load_record("INFY.NS", store_dir)
            self.assertIsNotNone(record)
            self.assertEqual(record["pe_history_meta"]["source"], "manual")
            self.assertFalse(record["pe_history_meta"]["insufficient_20y"])

            # Simulate a price/EPS update that puts current PE near the top of the
            # manually-entered history (max stored value is ~10 + 25*1.0 = 35).
            record["eps_ttm"] = 1.0
            record["price"] = 34.5

            updated = daily_update("INFY.NS", record=record, store_dir=store_dir, save=False)

            self.assertIsNotNone(updated["pe_percentile_20y"])
            self.assertGreaterEqual(updated["pe_percentile_20y"], 85.0)
            self.assertFalse(updated.get("pe_history_insufficient"))

            updated["business_type"] = "compounder"
            components = calculate_valuation_tax_components(updated)
            self.assertEqual(components["pe_hist_percentile"], -3.0)

    def test_round_trip_neutral_when_still_insufficient(self):
        """Manual entry that's still short of 20y should behave exactly like the
        existing insufficient-history safety net: pe_hist_percentile stays neutral."""
        with tempfile.TemporaryDirectory() as tmp:
            store_dir = Path(tmp) / "conviction_store"
            csv_path = Path(tmp) / "thin.csv"
            _write_csv(csv_path, [("2022-01-31", 30.0), ("2023-01-31", 32.0), ("2024-01-31", 34.0)])

            exit_code = set_manual_pe_history.main(
                ["THIN.NS", "--csv", str(csv_path), "--store-dir", str(store_dir)]
            )
            self.assertEqual(exit_code, 0)

            record = load_record("THIN.NS", store_dir)
            record["eps_ttm"] = 1.0
            record["price"] = 34.0

            updated = daily_update("THIN.NS", record=record, store_dir=store_dir, save=False)
            self.assertIsNone(updated["pe_percentile_20y"])
            self.assertTrue(updated.get("pe_history_insufficient"))

            updated["business_type"] = "compounder"
            components = calculate_valuation_tax_components(updated)
            self.assertEqual(components["pe_hist_percentile"], 0.0)


if __name__ == "__main__":
    unittest.main()
