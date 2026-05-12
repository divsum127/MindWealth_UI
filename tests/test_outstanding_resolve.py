"""Tests for outstanding-signal report path resolution."""

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import chatbot.outstanding_paths as op


class TestResolveOutstandingSignalPath(unittest.TestCase):
    def test_exact_name_beats_dated(self):
        with TemporaryDirectory() as td:
            us = Path(td) / "US"
            us.mkdir(parents=True, exist_ok=True)
            exact = us / "outstanding_signal.csv"
            dated = us / "2026-05-08_outstanding_signal.csv"
            exact.write_text("Function\nX")
            dated.write_text("Function\nY")
            with patch.object(op, "trade_store_us_dir", return_value=us):
                p = op.resolve_outstanding_signal_path()
            self.assertEqual(p.resolve(), exact.resolve())

    def test_newest_dated_by_mtime(self):
        with TemporaryDirectory() as td:
            us = Path(td) / "US"
            us.mkdir(parents=True, exist_ok=True)
            older = us / "2026-01-01_outstanding_signal.csv"
            newer = us / "2026-05-08_outstanding_signal.csv"
            older.write_text("a")
            os.utime(older, (1, 1))
            newer.write_text("b")
            os.utime(newer, (999999999, 999999999))
            with patch.object(op, "trade_store_us_dir", return_value=us):
                p = op.resolve_outstanding_signal_path()
            self.assertEqual(p.resolve(), newer.resolve())

    def test_reexported_from_config(self):
        from chatbot.config import resolve_outstanding_signal_path as from_cfg

        self.assertIs(from_cfg, op.resolve_outstanding_signal_path)


if __name__ == "__main__":
    unittest.main()
