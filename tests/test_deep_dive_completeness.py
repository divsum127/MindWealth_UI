"""Integration tests: deep-dive entry fetch covers all open all_signal rows per asset."""

import unittest
from pathlib import Path

import pandas as pd

from chatbot.outstanding_paths import resolve_all_signal_path
from chatbot.smart_data_fetcher import (
    SmartDataFetcher,
    SYMBOL_SIGNAL_COMPOUND_COL,
    compute_missing_open_entry_keys,
)


def _open_keys_from_all_signal(asset: str) -> set:
    path = resolve_all_signal_path()
    if path is None or not path.is_file():
        return set()
    adf = pd.read_csv(path)
    adf = SmartDataFetcher._filter_outstanding_open_rows(adf)
    adf = SmartDataFetcher._filter_df_by_assets(adf, [asset])
    adf = SmartDataFetcher._filter_confirmed_rows(adf)
    return {SmartDataFetcher._entry_signal_identity_key(row) for _, row in adf.iterrows()}


class TestDeepDiveCompleteness(unittest.TestCase):
    """Parametrized completeness against repo trade_store data."""

    ASSETS = ["BYDDY", "MSFT", "TSLA"]

    def test_open_all_signal_keys_present_in_entry_fetch(self):
        path = resolve_all_signal_path()
        if path is None or not path.is_file():
            self.skipTest("No all_signal report in trade_store")

        fetcher = SmartDataFetcher()
        for asset in self.ASSETS:
            with self.subTest(asset=asset):
                expected = _open_keys_from_all_signal(asset)
                if not expected:
                    self.skipTest(f"No open confirmed rows for {asset} in {path.name}")

                result = fetcher.fetch_data(
                    signal_types=["entry"],
                    required_columns=None,
                    assets=[asset],
                    from_date="2026-01-01",
                    to_date="2026-12-31",
                    date_filter_mode="entry_or_exit",
                )
                entry_df = result.get("entry")
                self.assertIsNotNone(entry_df)

                missing = compute_missing_open_entry_keys(asset, entry_df)
                self.assertEqual(
                    missing,
                    [],
                    msg=f"{asset}: missing keys {missing[:5]} (of {len(missing)})",
                )

                loaded = {
                    SmartDataFetcher._entry_signal_identity_key(row)
                    for _, row in entry_df.iterrows()
                }
                for key in expected:
                    self.assertIn(
                        key,
                        loaded,
                        msg=f"{asset}: expected open key {key} not in fetch",
                    )


if __name__ == "__main__":
  unittest.main()
