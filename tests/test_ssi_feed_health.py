"""Guards for the SSI data-feed failures found in the 2026-08-18 reply audit.

Each test names the specific regression it prevents. The failures these cover were all silent:
the job exited 0, the log held only pandas warnings, and the page published a confident number
built on a fraction of its inputs.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.data import cftc_pull
from src.macro_intelligence.data.retry_cache import _is_empty
from src.sentiment_superindex.config import coverage_policy
from src.sentiment_superindex.engine.superindex import _layer_signal_coverage


def _component(raw: float | None, norm: float = 0.1) -> dict:
    return {"raw": raw, "norm": norm, "stale_days": 0, "weight_multiplier": 1.0}


LAYER1_WEIGHTS = {
    "aaii_spread": 0.30,
    "naaim_exposure": 0.35,
    "put_call_ema": 0.20,
    "cnn_fg": 0.15,
}
LAYER2_KEYS = [
    "mcclellan",
    "nh_nl_ratio",
    "hyg_lqd",
    "skew",
    "vix_ratio",
    "pct_above_200dma",
]
LAYER3_KEYS = ["dbmf_beta", "cftc_fm_net", "cftc_rm_net", "gross_net"]


class TestCoverageGate(unittest.TestCase):
    """The gate that stops a degraded layer from publishing a confident score."""

    def test_layer2_two_of_six_is_unreliable(self) -> None:
        """The 2026-08-18 outage: a dead ^VIX3M feed took Layer 2 to 2 of 6 and the page
        still printed 'UNCONFIRMED, 0.80x size' as though the market had moved."""
        weights = {k: 1 / 6 for k in LAYER2_KEYS}
        components = {k: _component(None) for k in LAYER2_KEYS}
        components["mcclellan"] = _component(1.0)
        components["pct_above_200dma"] = _component(1.0)
        cov = _layer_signal_coverage(LAYER2_KEYS, components, weights, layer_key="layer2")
        self.assertFalse(cov["reliable"])
        self.assertIn("2 of 6", cov["unreliable_reason"])

    def test_layer3_dbmf_only_is_unreliable(self) -> None:
        """Rohit's SSI CRITICAL (sheet row 45): when COT drops out, Layer 3 renormalised to
        DBMF at 100% weight and kept its full 0.25 layer weight."""
        weights = {k: 0.25 for k in LAYER3_KEYS}
        components = {k: _component(None) for k in LAYER3_KEYS}
        components["dbmf_beta"] = _component(1.0)
        cov = _layer_signal_coverage(LAYER3_KEYS, components, weights, layer_key="layer3")
        self.assertFalse(cov["reliable"])

    def test_layer1_survives_losing_its_smallest_signal(self) -> None:
        """Losing NAAIM (0.35) alone must stay scoreable -- the gate is not a tripwire."""
        components = {k: _component(1.0) for k in LAYER1_WEIGHTS}
        components["naaim_exposure"] = _component(None)
        cov = _layer_signal_coverage(
            list(LAYER1_WEIGHTS), components, LAYER1_WEIGHTS, layer_key="layer1"
        )
        self.assertTrue(cov["reliable"])
        self.assertAlmostEqual(cov["nominal_weight_retained"], 0.65)

    def test_gate_is_weight_aware_not_just_count_aware(self) -> None:
        """Three of four inputs can still be too little when the missing one is the heaviest."""
        weights = {"a": 0.70, "b": 0.10, "c": 0.10, "d": 0.10}
        components = {k: _component(1.0) for k in weights}
        components["a"] = _component(None)
        cov = _layer_signal_coverage(list(weights), components, weights, layer_key="layer1")
        self.assertEqual(cov["available_count"], 3)
        self.assertFalse(cov["reliable"])
        self.assertIn("nominal weight", cov["unreliable_reason"])

    def test_reason_is_empty_only_when_reliable(self) -> None:
        """The label and the decision must come from one place so they cannot disagree."""
        components = {k: _component(1.0) for k in LAYER1_WEIGHTS}
        cov = _layer_signal_coverage(
            list(LAYER1_WEIGHTS), components, LAYER1_WEIGHTS, layer_key="layer1"
        )
        self.assertTrue(cov["reliable"])
        self.assertIsNone(cov["unreliable_reason"])

    def test_thresholds_come_from_config(self) -> None:
        min_counts, min_weight = coverage_policy()
        self.assertIn("layer1", min_counts)
        self.assertGreater(min_weight, 0)


class TestCftcHistoryCompleteness(unittest.TestCase):
    """The prod defect: a partial zip cache silently shortened the percentile window."""

    def test_expected_specs_cover_bulk_plus_every_year(self) -> None:
        specs = cftc_pull._expected_zip_specs(2006)
        names = [p.name for p, _ in specs]
        self.assertIn("fin_fut_txt_2006_2016.zip", names)
        current_year = pd.Timestamp.now().year
        self.assertIn(f"fut_fin_txt_{current_year}.zip", names)
        # One bulk file + one per year from 2017 to now.
        self.assertEqual(len(names), 1 + (current_year - 2017 + 1))

    def test_percentile_refuses_a_short_window(self) -> None:
        """Prod ranked the same fm_net 87.1st against ~31 weeks where dev said 52.9th against
        156. A rank is only meaningful against the window it claims to use."""
        idx = pd.date_range("2026-01-06", periods=31, freq="W-TUE")
        short = pd.Series(range(31), index=idx, dtype=float)
        self.assertIsNone(cftc_pull._rolling_pctile(short, idx[-1]))

    def test_percentile_published_for_a_full_window(self) -> None:
        idx = pd.date_range("2023-09-05", periods=156, freq="W-TUE")
        full = pd.Series(range(156), index=idx, dtype=float)
        self.assertAlmostEqual(cftc_pull._rolling_pctile(full, idx[-1]), 100.0)

    def test_raw_cache_is_keyed_by_start_year(self) -> None:
        """A single global served the first caller's window to every later caller for the life
        of the process -- a real hazard in the long-lived API server."""
        self.assertIsInstance(cftc_pull._TFF_RAW_CACHE, dict)

    def test_next_release_is_never_in_the_past(self) -> None:
        """The tile advertised 'next release Fri 14 Aug' on 18 Aug."""
        from src.sentiment_superindex.data.cftc_patterns import evaluate_cftc_positioning

        out = evaluate_cftc_positioning(76.0, 64.0, "2026-08-18", fm_net=-1.0, rm_net=1.0)
        if out.get("next_release"):
            self.assertGreater(pd.Timestamp(out["next_release"]), pd.Timestamp("2026-08-18"))


class TestPullFailuresAreVisible(unittest.TestCase):
    def test_empty_series_counts_as_a_failed_pull(self) -> None:
        """pull_with_cache treated only None as failure, so a dead source logged OK with zero
        rows and could overwrite a good cached value."""
        self.assertTrue(_is_empty(pd.Series(dtype=float)))
        self.assertTrue(_is_empty(pd.DataFrame()))
        self.assertFalse(_is_empty(pd.Series([1.0])))
        # A scalar zero is a value, not an absence.
        self.assertFalse(_is_empty(0.0))

    def test_yahoo_cache_serves_history_when_the_fetch_dies(self) -> None:
        """A failed fetch must return the cached series, not an empty one."""
        from src.sentiment_superindex.data import yahoo_cache

        cached = pd.Series([1.0, 2.0], index=pd.to_datetime(["2026-01-01", "2026-01-02"]))
        with patch.object(
            yahoo_cache, "load_cached_series", return_value=(cached, pd.Series(dtype=object))
        ), patch.object(
            yahoo_cache.cboe_indices, "fetch_for_ticker", return_value=pd.Series(dtype=float)
        ), patch.object(
            yahoo_cache, "fetch_yahoo_close", side_effect=RuntimeError("yahoo down")
        ):
            out = yahoo_cache.cached_yahoo_close("HYG")
        self.assertEqual(len(out), 2)

    def test_truncated_live_tail_does_not_shorten_the_series(self) -> None:
        """The ^VIX3M failure: a live response ending a month early must not delete history."""
        from src.sentiment_superindex.data import yahoo_cache

        idx = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"])
        cached = pd.Series([1.0, 2.0, 3.0], index=idx)
        truncated = pd.Series([1.0], index=idx[:1])
        with patch.object(
            yahoo_cache, "load_cached_series", return_value=(cached, pd.Series(dtype=object))
        ), patch.object(
            yahoo_cache.cboe_indices, "fetch_for_ticker", return_value=pd.Series(dtype=float)
        ), patch.object(
            yahoo_cache, "fetch_yahoo_close", return_value=truncated
        ), patch.object(yahoo_cache, "save_cached_series"):
            out = yahoo_cache.cached_yahoo_close("^VIX3M")
        self.assertEqual(out.index.max(), idx[-1])
        self.assertEqual(len(out), 3)


if __name__ == "__main__":
    unittest.main()
