"""Tests for macro calendar helpers."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.data.macro_calendar import (
    MacroReleaseRow,
    _dedupe_macro_rows,
    _is_event_match,
    hours_since_event,
)


class TestMacroCalendar(unittest.TestCase):
    def test_fomc_event_name_match(self) -> None:
        self.assertTrue(_is_event_match("Fed Interest Rate Decision", ("fed interest rate decision",)))
        self.assertFalse(_is_event_match("Core CPI MoM", ("fed interest rate decision",)))

    def test_nfp_event_name_match(self) -> None:
        self.assertTrue(_is_event_match("Nonfarm Payrolls", ("nonfarm payrolls",)))
        self.assertTrue(_is_event_match("Non-Farm Payrolls", ("non-farm payrolls",)))

    def test_dedupe_prefers_investing(self) -> None:
        rows = _dedupe_macro_rows(
            [
                MacroReleaseRow("FOMC", "2026-06-18", source="fred_release_calendar"),
                MacroReleaseRow(
                    "FOMC",
                    "2026-06-18",
                    consensus=0.25,
                    source="investing.com",
                    event_name="Fed Interest Rate Decision",
                ),
            ]
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].source, "investing.com")

    def test_hours_since_event_fomc(self) -> None:
        hrs = hours_since_event("FOMC", "2026-06-17", "2026-06-18")
        self.assertGreater(hrs, 0)
        self.assertLessEqual(hrs, 30)

    @patch("src.macro_intelligence.data.macro_calendar.requests.get")
    def test_fetch_fred_release_dates(self, mock_get) -> None:
        from src.macro_intelligence.data.macro_calendar import fetch_fred_release_dates

        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "release_dates": [{"date": "2026-07-04"}, {"date": "2026-06-06"}]
        }
        with patch.dict("os.environ", {"FRED_API_KEY": "test-key"}):
            dates = fetch_fred_release_dates("NFP", limit=10)
        self.assertEqual(dates, ["2026-06-06", "2026-07-04"])


if __name__ == "__main__":
    unittest.main()
