"""Unit tests for the Portfolio Backend Remaining Build engines (Phases 0-7):

  - api/services/policy_service.py       (Phase 0)
  - src/portfolio_nav/book_snapshot_store.py (Phase 1)
  - api/services/sizing_engine.py        (Phase 2)
  - src/portfolio_nav/eviction_engine.py  (Phase 3)
  - src/portfolio_nav/four_book_engine.py (Phase 5, pure helpers)
  - api/services/manual_overrides_service.py (Phase 6)
  - api/services/personal_book_service.py    (Phase 7)
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd

from api.services import policy_service, sizing_engine
from src.portfolio_nav import eviction_engine, four_book_engine


# ─────────────────────────────────────────────────────────────────────────────
# Phase 0 — policy_service
# ─────────────────────────────────────────────────────────────────────────────

class TestPolicyService(unittest.TestCase):

    def setUp(self) -> None:
        for key in (
            "PORTFOLIO_NOTIONAL", "PORTFOLIO_USE_RESEARCH_NOTIONAL", "PORTFOLIO_N_SLOTS",
            "PORTFOLIO_REBALANCE_MODE", "PORTFOLIO_EVICTION_MARGIN_M",
        ):
            os.environ.pop(key, None)

    def tearDown(self) -> None:
        self.setUp()

    def test_default_notional_is_100m(self) -> None:
        notional, source = policy_service.get_notional()
        self.assertEqual(notional, 100_000_000)
        self.assertEqual(source, "default")

    def test_research_notional_flag(self) -> None:
        os.environ["PORTFOLIO_USE_RESEARCH_NOTIONAL"] = "1"
        notional, source = policy_service.get_notional()
        self.assertEqual(notional, 10_000_000)
        self.assertEqual(source, "research")

    def test_env_notional_overrides_everything(self) -> None:
        os.environ["PORTFOLIO_USE_RESEARCH_NOTIONAL"] = "1"
        os.environ["PORTFOLIO_NOTIONAL"] = "55000000"
        notional, source = policy_service.get_notional()
        self.assertEqual(notional, 55_000_000)
        self.assertEqual(source, "env")

    def test_default_n_slots_is_60(self) -> None:
        n, _source = policy_service.get_n_slots()
        self.assertEqual(n, 60)

    def test_n_slots_env_override(self) -> None:
        os.environ["PORTFOLIO_N_SLOTS"] = "80"
        n, source = policy_service.get_n_slots()
        self.assertEqual(n, 80)
        self.assertEqual(source, "env")

    def test_default_rebalance_mode_is_hold_original(self) -> None:
        mode, _source = policy_service.get_rebalance_mode()
        self.assertEqual(mode, "hold_original")

    def test_rebalance_mode_env_override(self) -> None:
        os.environ["PORTFOLIO_REBALANCE_MODE"] = "legacy_rebalance"
        mode, source = policy_service.get_rebalance_mode()
        self.assertEqual(mode, "legacy_rebalance")
        self.assertEqual(source, "env")

    def test_default_eviction_margin_is_zero(self) -> None:
        margin, _source = policy_service.get_eviction_margin_m()
        self.assertEqual(margin, 0.0)

    def test_sleeves_sum_close_to_100(self) -> None:
        sleeves = policy_service.get_sleeves()
        self.assertGreater(len(sleeves), 0)
        total = sum(s["ceiling_pct"] for s in sleeves)
        self.assertAlmostEqual(total, 100.0, delta=1.0)

    def test_policy_meta_has_all_keys(self) -> None:
        meta = policy_service.policy_meta()
        for key in (
            "notional", "n_slots", "rebalance_mode", "eviction_margin_m", "sleeves",
            "same_asset_siblings", "auto_scenario_thresholds",
        ):
            self.assertIn(key, meta)

    def test_auto_scenario_thresholds_default_from_yaml(self) -> None:
        thresholds = policy_service.get_auto_scenario_thresholds()
        self.assertEqual(thresholds["vix_pctile_stress"], 70.0)
        self.assertEqual(thresholds["hy_pct_stress"], 4.0)
        self.assertEqual(thresholds["ssi_multiplier_stress_below"], 0.9)
        self.assertEqual(thresholds["vix_pctile_lowvol"], 30.0)
        self.assertEqual(thresholds["ssi_multiplier_lowvol_at_least"], 1.0)

    def test_auto_scenario_status_is_interim(self) -> None:
        self.assertEqual(policy_service.get_auto_scenario_status(), "interim")


class TestResolveAutoScenario(unittest.TestCase):
    """resolve_auto_scenario() (D4 AUTO) — now driven by policy_service.get_auto_scenario_thresholds(),
    not hardcoded (see config/portfolio_policy.yaml auto_scenario block)."""

    @staticmethod
    def _runic(vix_pctile: float | None = None, hy_pct: float | None = None) -> dict:
        variables = []
        if vix_pctile is not None:
            variables.append({"variable": "VIX", "pctile_3yr": vix_pctile})
        if hy_pct is not None:
            variables.append({"variable": "HY", "current": hy_pct})
        return {"variables_dashboard": variables}

    def test_high_vix_pctile_resolves_stress(self) -> None:
        from api.services import portfolio_service

        scenario, reason = portfolio_service.resolve_auto_scenario(
            self._runic(vix_pctile=85.0), {"ssi_multiplier": 1.0},
        )
        self.assertEqual(scenario, "stress")
        self.assertIn("stress", reason)

    def test_low_vix_and_high_ssi_resolves_lowvol(self) -> None:
        from api.services import portfolio_service

        scenario, _reason = portfolio_service.resolve_auto_scenario(
            self._runic(vix_pctile=15.0), {"ssi_multiplier": 1.05},
        )
        self.assertEqual(scenario, "lowvol")

    def test_middling_signals_resolve_normal(self) -> None:
        from api.services import portfolio_service

        scenario, _reason = portfolio_service.resolve_auto_scenario(
            self._runic(vix_pctile=50.0), {"ssi_multiplier": 1.0},
        )
        self.assertEqual(scenario, "normal")

    def test_thresholds_are_read_from_policy_not_hardcoded(self) -> None:
        """Regression: tightening vix_pctile_stress in policy must change the outcome for the
        same inputs — proves resolve_auto_scenario() no longer hardcodes 70/4.0/0.9/30/1.0."""
        from api.services import portfolio_service

        runic = self._runic(vix_pctile=50.0)
        ssi = {"ssi_multiplier": 1.0}
        baseline, _ = portfolio_service.resolve_auto_scenario(runic, ssi)
        self.assertEqual(baseline, "normal")

        tightened = {
            "vix_pctile_stress": 40.0, "hy_pct_stress": 4.0,
            "ssi_multiplier_stress_below": 0.9, "vix_pctile_lowvol": 30.0,
            "ssi_multiplier_lowvol_at_least": 1.0,
        }
        with patch.object(policy_service, "get_auto_scenario_thresholds", return_value=tightened):
            scenario, reason = portfolio_service.resolve_auto_scenario(runic, ssi)
        self.assertEqual(scenario, "stress")
        self.assertIn("stress", reason)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1 — book_snapshot_store
# ─────────────────────────────────────────────────────────────────────────────

class TestBookSnapshotStore(unittest.TestCase):

    def setUp(self) -> None:
        from src.portfolio_nav import book_snapshot_store as store

        self.store = store
        self._tmpdir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmpdir.name) / "test_snapshots.db"
        self._patch = patch.object(store, "BOOK_SNAPSHOTS_DB", self._db_path)
        self._patch.start()

    def tearDown(self) -> None:
        self._patch.stop()
        self._tmpdir.cleanup()

    def test_write_and_read_position_snapshots(self) -> None:
        rows = [
            {"ticker": "AAPL", "function": "MOM", "interval": "D", "direction": "Long",
             "sleeve_id": "us_tech", "true_weight_pct": 1.5, "size_usd": 150000},
            {"ticker": "MSFT", "function": "MOM", "interval": "D", "direction": "Long",
             "sleeve_id": "us_tech", "true_weight_pct": 1.2, "size_usd": 120000},
        ]
        written = self.store.write_position_snapshots("2026-07-22", rows, scenario="normal")
        self.assertEqual(written, 2)
        read_back = self.store.read_position_snapshots("2026-07-22", scenario="normal")
        self.assertEqual(len(read_back), 2)
        self.assertEqual({r["ticker"] for r in read_back}, {"AAPL", "MSFT"})

    def test_duplicate_ticker_same_day_does_not_collide(self) -> None:
        """Regression: PK used to be (date,ticker,function,interval,direction,scenario)."""
        rows = [
            {"ticker": "SPOT", "function": "TRENDPULSE", "interval": "Daily", "direction": "Long"},
            {"ticker": "SPOT", "function": "TRENDPULSE", "interval": "Daily", "direction": "Long"},
        ]
        written = self.store.write_position_snapshots("2026-07-22", rows, scenario="normal")
        self.assertEqual(written, 2)

    def test_rerunning_same_date_replaces_rows(self) -> None:
        self.store.write_position_snapshots("2026-07-22", [{"ticker": "AAPL"}], scenario="normal")
        self.store.write_position_snapshots("2026-07-22", [{"ticker": "MSFT"}], scenario="normal")
        read_back = self.store.read_position_snapshots("2026-07-22", scenario="normal")
        self.assertEqual(len(read_back), 1)
        self.assertEqual(read_back[0]["ticker"], "MSFT")

    def test_regime_bucket_upsert(self) -> None:
        self.store.write_regime_bucket("2026-07-22", scenario="normal", regime_bucket="normal", final_ceiling_pct=80.0)
        self.store.write_regime_bucket("2026-07-22", scenario="normal", regime_bucket="stress", final_ceiling_pct=65.0)
        series = self.store.read_regime_bucket_series(scenario="normal")
        self.assertEqual(len(series), 1)
        self.assertEqual(series[0]["regime_bucket"], "stress")

    def test_eviction_log_write_and_read(self) -> None:
        self.store.write_eviction(
            "2026-07-22", evicted_ticker="XYZ", evicted_function="MOM", evicted_interval="D",
            challenger_ticker="ABC", challenger_score=9.0, weakest_score=2.0, margin_m=0, mode="1c",
        )
        rows = self.store.read_evictions()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["evicted_ticker"], "XYZ")
        self.assertEqual(rows[0]["challenger_ticker"], "ABC")

    def test_snapshot_status_empty_store(self) -> None:
        status = self.store.snapshot_status()
        self.assertIsNone(status["earliest_snapshot_date"])
        self.assertEqual(status["days_captured"], 0)

    def test_snapshot_status_after_write(self) -> None:
        self.store.write_position_snapshots("2026-07-22", [{"ticker": "AAPL"}], scenario="normal")
        status = self.store.snapshot_status()
        self.assertEqual(status["earliest_snapshot_date"], "2026-07-22")
        self.assertEqual(status["days_captured"], 1)

    def test_personal_book_snapshot_write_and_read(self) -> None:
        self.store.write_personal_book_snapshot(
            "2026-07-22", nav_usd=12345.0, cash_usd=1000.0, position_count=2,
            total_pnl_usd=345.0, total_pnl_pct=2.87,
            holdings=[{"ticker": "AAPL", "shares": 10}],
        )
        rows = self.store.read_personal_book_series()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["snapshot_date"], "2026-07-22")
        self.assertEqual(rows[0]["nav_usd"], 12345.0)
        self.assertEqual(rows[0]["holdings"], [{"ticker": "AAPL", "shares": 10}])

    def test_personal_book_snapshot_rerun_same_date_overwrites(self) -> None:
        self.store.write_personal_book_snapshot(
            "2026-07-22", nav_usd=100.0, cash_usd=0.0, position_count=0,
            total_pnl_usd=0.0, total_pnl_pct=0.0,
        )
        self.store.write_personal_book_snapshot(
            "2026-07-22", nav_usd=200.0, cash_usd=0.0, position_count=1,
            total_pnl_usd=0.0, total_pnl_pct=0.0,
        )
        rows = self.store.read_personal_book_series()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["nav_usd"], 200.0)

    def test_personal_book_series_date_filters(self) -> None:
        for d, nav in (("2026-07-20", 100.0), ("2026-07-21", 110.0), ("2026-07-22", 120.0)):
            self.store.write_personal_book_snapshot(
                d, nav_usd=nav, cash_usd=0.0, position_count=0, total_pnl_usd=0.0, total_pnl_pct=0.0,
            )
        rows = self.store.read_personal_book_series(start_date="2026-07-21")
        self.assertEqual([r["snapshot_date"] for r in rows], ["2026-07-21", "2026-07-22"])

    def test_earliest_personal_snapshot_date_empty_store(self) -> None:
        self.assertIsNone(self.store.earliest_personal_snapshot_date())

    def test_earliest_personal_snapshot_date_after_write(self) -> None:
        self.store.write_personal_book_snapshot(
            "2026-07-22", nav_usd=100.0, cash_usd=0.0, position_count=0, total_pnl_usd=0.0, total_pnl_pct=0.0,
        )
        self.assertEqual(self.store.earliest_personal_snapshot_date(), "2026-07-22")


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2 — sizing_engine (D1 NAV/N slots)
# ─────────────────────────────────────────────────────────────────────────────

class TestSizingEngine(unittest.TestCase):

    def test_max_slots_for_sleeve(self) -> None:
        # D1 worked example: US Tech 12% ceiling, N=60 -> floor(12*60/100) = 7
        self.assertEqual(sizing_engine.max_slots_for_sleeve(12.0, 60), 7)

    def test_max_slots_zero_n(self) -> None:
        self.assertEqual(sizing_engine.max_slots_for_sleeve(12.0, 0), 0)

    def _pending_row(self, ticker: str, bq: float, adj_share: float = 1.0, blocked: bool = False) -> dict:
        return {
            "ticker": ticker, "bq": bq, "verdict": "OK", "not_applicable": False,
            "tier_label": "MAX", "adj_share": adj_share, "flags": [], "direction": "Long",
            "blocked": blocked, "rank_weight": adj_share, "row": {},
        }

    def test_sleeve_full_marks_excess_as_waiting(self) -> None:
        sleeves = [{"id": "us_tech", "label": "US Tech", "ceiling_pct": 12.0}]
        pending = {
            "us_tech": [self._pending_row(f"T{i}", bq=10 - i) for i in range(9)],
        }
        sleeve_map, sized_rows = sizing_engine.compute_d1_sizing(
            pending, notional=10_000_000, final_ceiling_pct=100.0, n_slots=60, sleeves=sleeves,
        )
        self.assertEqual(sleeve_map["us_tech"]["slots_max"], 7)
        admitted = [r for r in sized_rows if not r["_d1_waiting"]]
        waiting = [r for r in sized_rows if r["_d1_waiting"]]
        self.assertEqual(len(admitted), 7)
        self.assertEqual(len(waiting), 2)
        for r in waiting:
            self.assertEqual(r["_d1_wait_reason"], "sleeve_full")

    def test_conviction_multiplier_scales_allocation(self) -> None:
        sleeves = [{"id": "us_tech", "label": "US Tech", "ceiling_pct": 100.0}]
        pending = {"us_tech": [self._pending_row("AAPL", bq=10.0, adj_share=0.5)]}
        _sleeve_map, sized_rows = sizing_engine.compute_d1_sizing(
            pending, notional=6_000_000, final_ceiling_pct=100.0, n_slots=60, sleeves=sleeves,
        )
        # slot_dollars = 6,000,000/60 = 100,000; * adj_share 0.5 * ceiling_fraction 1.0 = 50,000
        self.assertEqual(sized_rows[0]["_d1_allocation_usd"], 50_000)

    def test_blocked_rows_never_consume_slot(self) -> None:
        sleeves = [{"id": "us_tech", "label": "US Tech", "ceiling_pct": 100.0}]
        pending = {"us_tech": [
            self._pending_row("AAPL", bq=10.0, blocked=True),
            self._pending_row("MSFT", bq=8.0),
        ]}
        sleeve_map, sized_rows = sizing_engine.compute_d1_sizing(
            pending, notional=6_000_000, final_ceiling_pct=100.0, n_slots=60, sleeves=sleeves,
        )
        self.assertEqual(sleeve_map["us_tech"]["slots_used"], 1)
        blocked_row = next(r for r in sized_rows if r["ticker"] == "AAPL")
        self.assertEqual(blocked_row["_d1_allocation_usd"], 0)
        self.assertFalse(blocked_row["_d1_waiting"])

    def test_sizing_engine_version_defaults_to_legacy(self) -> None:
        os.environ.pop("SIZING_ENGINE_VERSION", None)
        self.assertEqual(sizing_engine.sizing_engine_version(), "legacy")

    def test_sizing_engine_version_flag(self) -> None:
        os.environ["SIZING_ENGINE_VERSION"] = "d1_slots"
        try:
            self.assertEqual(sizing_engine.sizing_engine_version(), "d1_slots")
        finally:
            os.environ.pop("SIZING_ENGINE_VERSION", None)

    def test_clamp_display_pct(self) -> None:
        self.assertEqual(sizing_engine.clamp_display_pct(350.0), 100.0)
        self.assertEqual(sizing_engine.clamp_display_pct(-5.0), 0.0)
        self.assertEqual(sizing_engine.clamp_display_pct(42.0), 42.0)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3 — eviction_engine (1C / A2 / A3)
# ─────────────────────────────────────────────────────────────────────────────

class TestEvictionEngine(unittest.TestCase):

    def _cand(self, ticker: str, score: float | None) -> eviction_engine.Candidate:
        return eviction_engine.Candidate(key=(ticker, "MOM", "D", "Long"), ticker=ticker, score=score)

    def test_admits_into_free_slots_without_eviction(self) -> None:
        held = [self._cand("A", 5.0)]
        candidates = [self._cand("B", 8.0)]
        decision = eviction_engine.decide_admissions(held=held, candidates=candidates, n_max=5)
        self.assertEqual([c.ticker for c in decision.admitted], ["B"])
        self.assertEqual(decision.evicted, [])

    def test_1c_evicts_weakest_when_full_and_challenger_stronger(self) -> None:
        held = [self._cand("WEAK", 1.0), self._cand("STRONG", 9.0)]
        candidates = [self._cand("CHALLENGER", 5.0)]
        decision = eviction_engine.decide_admissions(held=held, candidates=candidates, n_max=2, margin_m=0)
        self.assertEqual([c.ticker for c in decision.evicted], ["WEAK"])
        self.assertEqual([c.ticker for c in decision.admitted], ["CHALLENGER"])
        self.assertEqual(len(decision.evictions), 1)
        self.assertEqual(decision.evictions[0].evicted.ticker, "WEAK")
        self.assertEqual(decision.evictions[0].challenger.ticker, "CHALLENGER")

    def test_a2_margin_softener_blocks_marginal_eviction(self) -> None:
        held = [self._cand("WEAK", 5.0), self._cand("STRONG", 9.0)]
        candidates = [self._cand("CHALLENGER", 8.0)]  # beats WEAK by 3, but M=10 blocks it
        decision = eviction_engine.decide_admissions(held=held, candidates=candidates, n_max=2, margin_m=10)
        self.assertEqual(decision.evicted, [])
        self.assertEqual([c.ticker for c in decision.waiting], ["CHALLENGER"])

    def test_a2_margin_softener_allows_when_gap_exceeds_margin(self) -> None:
        held = [self._cand("WEAK", 1.0), self._cand("STRONG", 9.0)]
        candidates = [self._cand("CHALLENGER", 8.0)]  # beats WEAK by 7, M=5 allows it
        decision = eviction_engine.decide_admissions(held=held, candidates=candidates, n_max=2, margin_m=5)
        self.assertEqual([c.ticker for c in decision.evicted], ["WEAK"])

    def test_a3_freeze_at_n_never_evicts(self) -> None:
        held = [self._cand("WEAK", 1.0), self._cand("STRONG", 9.0)]
        candidates = [self._cand("CHALLENGER", 100.0)]
        decision = eviction_engine.decide_admissions(
            held=held, candidates=candidates, n_max=2, freeze_at_n=True,
        )
        self.assertEqual(decision.evicted, [])
        self.assertEqual(decision.admitted, [])
        self.assertEqual([c.ticker for c in decision.waiting], ["CHALLENGER"])
        self.assertEqual(decision.mode, "f5_freeze")

    def test_a3_freeze_at_n_admits_into_naturally_freed_slots(self) -> None:
        held = [self._cand("A", 5.0)]  # only 1 of 2 slots held
        candidates = [self._cand("B", 3.0)]
        decision = eviction_engine.decide_admissions(
            held=held, candidates=candidates, n_max=2, freeze_at_n=True,
        )
        self.assertEqual([c.ticker for c in decision.admitted], ["B"])

    def test_eviction_margin_helper(self) -> None:
        self.assertEqual(eviction_engine.eviction_margin(8.0, 2.0), 6.0)
        self.assertIsNone(eviction_engine.eviction_margin(None, 2.0))


# ─────────────────────────────────────────────────────────────────────────────
# Phase 5 — four_book_engine pure helpers
# ─────────────────────────────────────────────────────────────────────────────

class TestFourBookEngineHelpers(unittest.TestCase):

    def test_bq_multiplier_tiers(self) -> None:
        self.assertEqual(four_book_engine._bq_multiplier(9.0, "OK"), 1.00)
        self.assertEqual(four_book_engine._bq_multiplier(6.0, "OK"), 0.75)
        self.assertEqual(four_book_engine._bq_multiplier(3.0, "OK"), 0.40)
        self.assertEqual(four_book_engine._bq_multiplier(-1.0, "OK"), 0.00)

    def test_bq_multiplier_not_applicable_never_blocked(self) -> None:
        self.assertEqual(four_book_engine._bq_multiplier(None, "NOT_APPLICABLE"), 1.0)
        self.assertEqual(four_book_engine._bq_multiplier(-5.0, "not_applicable"), 1.0)

    def test_bq_multiplier_unscored_defaults_reduced(self) -> None:
        self.assertEqual(four_book_engine._bq_multiplier(None, "OK"), 0.40)

    def test_apply_ssi_overlay_scales_down_on_ceiling_drop(self) -> None:
        dates = pd.date_range("2026-01-01", periods=5, freq="D")
        base = pd.DataFrame({"NAV": [10_000_000, 10_100_000, 10_200_000, 10_300_000, 10_400_000],
                              "N_active": [10] * 5}, index=dates)
        ssi_series = pd.Series([0.5] * 5, index=dates)  # heavy ceiling haircut
        out = four_book_engine.apply_ssi_overlay(base, ssi_series, start_nav=10_000_000)
        # With ceiling=0.5, NAV growth should be materially less than the un-haircut base
        self.assertLess(out["NAV"].iloc[-1], base["NAV"].iloc[-1])
        self.assertEqual(list(out["ceiling_fraction"]), [0.5] * 5)

    def test_apply_ssi_overlay_noop_when_ceiling_is_1(self) -> None:
        dates = pd.date_range("2026-01-01", periods=3, freq="D")
        base = pd.DataFrame({"NAV": [10_000_000, 10_100_000, 10_050_000], "N_active": [5, 5, 5]}, index=dates)
        ssi_series = pd.Series([1.0, 1.0, 1.0], index=dates)
        out = four_book_engine.apply_ssi_overlay(base, ssi_series, start_nav=10_000_000)
        for a, b in zip(out["NAV"], base["NAV"]):
            self.assertAlmostEqual(a, b, places=6)

    def test_conviction_daily_archive_multiplier_lookup(self) -> None:
        d1 = pd.Timestamp("2026-05-15")
        d2 = pd.Timestamp("2026-06-01")
        archive = four_book_engine.ConvictionDailyArchive(
            dates=[d1, d2],
            by_date={d1: {"AAPL": (9.0, "OK")}, d2: {"AAPL": (2.0, "OK")}},
        )
        self.assertEqual(archive.earliest_date(), d1)
        # Nearest snapshot <= date
        self.assertEqual(archive.multiplier_at_or_before(pd.Timestamp("2026-05-20"), "AAPL"), 1.0)
        self.assertEqual(archive.multiplier_at_or_before(pd.Timestamp("2026-06-15"), "AAPL"), 0.40)
        self.assertIsNone(archive.multiplier_at_or_before(pd.Timestamp("2026-01-01"), "AAPL"))

    def test_decompose_attribution_no_conviction_book(self) -> None:
        dates = pd.date_range("2026-01-01", periods=3, freq="D")
        base = pd.DataFrame({"NAV": [10_000_000, 10_500_000, 11_000_000], "N_active": [5] * 3}, index=dates)
        ssi = pd.DataFrame({"NAV": [10_000_000, 10_300_000, 10_600_000], "N_active": [5] * 3}, index=dates)
        result = four_book_engine.decompose_attribution(base, ssi, None, None, start_nav=10_000_000)
        self.assertIsNotNone(result["base_cum_return_pct"])
        self.assertIsNotNone(result["ssi_effect_pp"])
        self.assertLess(result["ssi_effect_pp"], 0)  # SSI haircut book trails base here
        self.assertIsNone(result["conviction_effect_pp"])
        self.assertFalse(result["residual_flag"])

    def test_decompose_attribution_residual_closes_to_zero(self) -> None:
        dates = pd.date_range("2026-05-15", periods=10, freq="D")
        base = pd.DataFrame({"NAV": [10_000_000 * (1.001 ** i) for i in range(10)], "N_active": [5] * 10}, index=dates)
        ssi = pd.DataFrame({"NAV": [10_000_000 * (1.0009 ** i) for i in range(10)], "N_active": [5] * 10}, index=dates)
        cv = pd.DataFrame({"NAV": [10_000_000 * (0.999 ** i) for i in range(10)], "N_active": [5] * 10}, index=dates)
        enhanced = pd.DataFrame({"NAV": [10_000_000 * (0.9985 ** i) for i in range(10)], "N_active": [5] * 10}, index=dates)
        result = four_book_engine.decompose_attribution(base, ssi, cv, enhanced, start_nav=10_000_000)
        self.assertEqual(result["residual_pp"], 0.0)
        self.assertFalse(result["residual_flag"])


# ─────────────────────────────────────────────────────────────────────────────
# Phase 6 — manual_overrides_service
# ─────────────────────────────────────────────────────────────────────────────

class TestManualOverridesService(unittest.TestCase):

    def setUp(self) -> None:
        from api.services import manual_overrides_service as svc

        self.svc = svc
        self._tmpdir = tempfile.TemporaryDirectory()
        self._path = Path(self._tmpdir.name) / "overrides.json"
        self._patch = patch.object(svc, "_STORE_PATH", self._path)
        self._patch.start()

    def tearDown(self) -> None:
        self._patch.stop()
        self._tmpdir.cleanup()

    def test_set_and_list_override(self) -> None:
        self.svc.set_override(ticker="aapl", allocation_usd=500_000, function="MOM", interval="D")
        overrides = self.svc.list_overrides()
        self.assertEqual(len(overrides), 1)
        self.assertEqual(overrides[0]["ticker"], "AAPL")
        self.assertEqual(overrides[0]["allocation_usd"], 500_000)

    def test_negative_allocation_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.svc.set_override(ticker="AAPL", allocation_usd=-100)

    def test_remove_override(self) -> None:
        self.svc.set_override(ticker="AAPL", allocation_usd=100, function="MOM", interval="D")
        self.assertTrue(self.svc.remove_override(ticker="AAPL", function="MOM", interval="D"))
        self.assertFalse(self.svc.remove_override(ticker="AAPL", function="MOM", interval="D"))

    def test_apply_manual_overrides_recomputes_shares(self) -> None:
        self.svc.set_override(ticker="AAPL", allocation_usd=100_000, function="MOM", interval="D", direction="Long")
        rows = [{"ticker": "AAPL", "function": "MOM", "interval": "D", "direction": "Long",
                 "entry_price": 100.0, "today_price": 110.0, "allocation_usd": 5000,
                 "blocked": True, "blocked_reason": "x"}]
        applied = self.svc.apply_manual_overrides(rows)
        self.assertEqual(applied, 1)
        row = rows[0]
        self.assertEqual(row["allocation_usd"], 100_000)
        self.assertTrue(row["manual_override"])
        self.assertFalse(row["blocked"])
        self.assertEqual(row["shares"], 1000.0)
        self.assertEqual(row["market_value_usd"], 110_000.0)
        self.assertEqual(row["pnl_usd"], 10_000.0)

    def test_apply_manual_overrides_no_match_is_noop(self) -> None:
        rows = [{"ticker": "MSFT", "function": "MOM", "interval": "D", "direction": "Long", "allocation_usd": 5000}]
        applied = self.svc.apply_manual_overrides(rows)
        self.assertEqual(applied, 0)
        self.assertEqual(rows[0]["allocation_usd"], 5000)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 7 — personal_book_service
# ─────────────────────────────────────────────────────────────────────────────

class TestPersonalBookService(unittest.TestCase):

    def setUp(self) -> None:
        from api.services import personal_book_service as svc
        from src.portfolio_nav import book_snapshot_store as store

        self.svc = svc
        self.store = store
        self._tmpdir = tempfile.TemporaryDirectory()
        self._path = Path(self._tmpdir.name) / "personal_holdings.json"
        self._db_path = Path(self._tmpdir.name) / "test_snapshots.db"
        self._patch = patch.object(svc, "PERSONAL_HOLDINGS_JSON", self._path)
        self._patch.start()
        self._db_patch = patch.object(store, "BOOK_SNAPSHOTS_DB", self._db_path)
        self._db_patch.start()
        self._price_patch = patch.object(svc, "_live_price", return_value=200.0)
        self._price_patch.start()
        self._name_patch = patch.object(svc, "_ticker_name", return_value="Apple Inc.")
        self._name_patch.start()

    def tearDown(self) -> None:
        self._price_patch.stop()
        self._name_patch.stop()
        self._db_patch.stop()
        self._patch.stop()
        self._tmpdir.cleanup()

    def test_upsert_and_list_holding(self) -> None:
        self.svc.upsert_holding(ticker="aapl", shares=10, cost_basis=150.0)
        holdings = self.svc.list_holdings()
        self.assertEqual(len(holdings), 1)
        self.assertEqual(holdings[0]["ticker"], "AAPL")

    def test_upsert_rejects_non_positive_shares(self) -> None:
        with self.assertRaises(ValueError):
            self.svc.upsert_holding(ticker="AAPL", shares=0, cost_basis=150.0)

    def test_remove_holding(self) -> None:
        self.svc.upsert_holding(ticker="AAPL", shares=10, cost_basis=150.0)
        self.assertTrue(self.svc.remove_holding("AAPL"))
        self.assertFalse(self.svc.remove_holding("AAPL"))

    def test_cash_roundtrip(self) -> None:
        self.svc.set_cash(5000.0)
        self.assertEqual(self.svc.get_cash(), 5000.0)

    def test_cash_rejects_negative(self) -> None:
        with self.assertRaises(ValueError):
            self.svc.set_cash(-1.0)

    def test_snapshot_computes_pnl_with_mocked_price(self) -> None:
        self.svc.upsert_holding(ticker="AAPL", shares=10, cost_basis=150.0)
        self.svc.set_cash(1000.0)
        snap = self.svc.get_personal_snapshot()
        self.assertEqual(snap["position_count"], 1)
        row = snap["holdings"][0]
        self.assertEqual(row["market_value"], 2000.0)  # 10 * 200.0
        self.assertEqual(row["cost_value"], 1500.0)  # 10 * 150.0
        self.assertEqual(row["pnl_usd"], 500.0)
        self.assertEqual(snap["total_market_value_usd"], 3000.0)  # 2000 + 1000 cash
        self.assertEqual(snap["cash_usd"], 1000.0)

    def test_nav_payload_has_no_history_data_status(self) -> None:
        self.svc.upsert_holding(ticker="AAPL", shares=10, cost_basis=150.0)
        payload = self.svc.get_personal_nav_payload()
        self.assertEqual(payload["mtm"], [])
        self.assertEqual(payload["mtm_daily"], [])
        self.assertEqual(payload["data_status"]["status"], "live_snapshot_only")

    def test_nav_payload_serves_accumulated_history_once_snapshot_job_has_run(self) -> None:
        """Regression for the personal-book daily snapshot job (run_personal_book_snapshot_daily.py):
        once at least one day is in the store, the NAV payload must serve it instead of staying
        permanently empty, while still disclosing the no-backfill boundary."""
        self.store.write_personal_book_snapshot(
            "2026-07-21", nav_usd=10_000.0, cash_usd=1000.0, position_count=1,
            total_pnl_usd=100.0, total_pnl_pct=1.0,
        )
        self.store.write_personal_book_snapshot(
            "2026-07-22", nav_usd=10_500.0, cash_usd=1000.0, position_count=1,
            total_pnl_usd=150.0, total_pnl_pct=1.5,
        )
        payload = self.svc.get_personal_nav_payload()
        self.assertEqual(len(payload["mtm_daily"]), 2)
        self.assertEqual(payload["mtm_daily"][0], {"date": "2026-07-21", "nav": 10_000.0})
        self.assertEqual(payload["data_status"]["status"], "live_from_snapshot_start")
        self.assertEqual(payload["data_status"]["earliest_date"], "2026-07-21")

    def test_get_personal_nav_history_empty_when_job_never_ran(self) -> None:
        self.assertEqual(self.svc.get_personal_nav_history(), [])


if __name__ == "__main__":
    unittest.main()
