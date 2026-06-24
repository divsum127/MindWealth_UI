"""Dominant reason string generation — all combos and pairings."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.engine.dominant import determine_dominant_combo, resolve_dominant

FAKE_STATS: dict[str, dict] = {
    "A": {
        "show_hit_rate": True,
        "primary_label": "6M",
        "hit_rate_primary": 0.833,
        "n_obs_primary": 174,
    },
    "B": {
        "show_hit_rate": True,
        "primary_label": "3M",
        "hit_rate_primary": 0.798,
        "n_obs_primary": 89,
    },
    "C": {
        "show_hit_rate": True,
        "primary_label": "6M",
        "hit_rate_primary": 0.83,
        "n_obs_primary": 12,
    },
    "C_immature": {
        "show_hit_rate": True,
        "primary_label": "6M",
        "hit_rate_primary": None,
        "n_obs_primary": 0,
    },
    "D": {
        "show_hit_rate": True,
        "primary_label": "5D",
        "hit_rate_primary": 0.385,
        "n_obs_primary": 452,
    },
    "E": {
        "show_hit_rate": True,
        "primary_label": "12M",
        "hit_rate_primary": 0.189,
        "n_obs_primary": 507,
    },
    "F": {
        "show_hit_rate": True,
        "primary_label": "6M",
        "hit_rate_primary": 0.788,
        "n_obs_primary": 704,
    },
    "G": {
        "show_hit_rate": False,
        "primary_label": "N/A",
        "hit_rate_primary": None,
        "n_obs_primary": 0,
    },
}


def _fake_stats(letter: str) -> dict:
    return dict(FAKE_STATS.get(letter, FAKE_STATS["F"]))


def _patch_stats(test_func):
    """Patch combo_hit_rate_stats used by format_reason_hit_rate."""

    def wrapper(self, mock_stats):
        mock_stats.side_effect = lambda letter: _fake_stats(letter)
        return test_func(self, mock_stats)

    return patch(
        "src.macro_intelligence.engine.combo_metadata.combo_hit_rate_stats",
        side_effect=lambda letter: _fake_stats(letter),
    )(wrapper)


class TestDominantReasonSoleCombo(unittest.TestCase):
    @_patch_stats
    def test_f_with_duration(self, _mock) -> None:
        active = [
            {
                "combo": "F",
                "status": "ACTIVE",
                "duration_weeks": 12,
                "duration_bucket": "MEDIUM",
                "episode_start": "2026-04-03",
            }
        ]
        _, reason, _ = determine_dominant_combo(active)
        self.assertIn("Combo F active (week 12, MEDIUM · started 2026-04-03)", reason)
        self.assertIn("79% 6M hit rate", reason)
        self.assertNotIn("Outranks", reason)
        self.assertNotIn("horizon fit", reason)

    @_patch_stats
    def test_e_confirmed_no_duration(self, _mock) -> None:
        active = [
            {
                "combo": "E",
                "status": "CONFIRMED",
                "duration_weeks": None,
                "duration_bucket": None,
                "confirmed_legs": ["CAPE", "NFCI"],
            }
        ]
        _, reason, _ = determine_dominant_combo(active)
        self.assertIn("Combo E confirmed (2/3)", reason)
        self.assertNotIn("week None", reason)
        self.assertNotIn("week ?", reason)
        self.assertIn("19% 12M hit rate", reason)
        self.assertIn("Legs: CAPE, NFCI.", reason)

    @_patch_stats
    def test_e_confirmed_3_of_3(self, _mock) -> None:
        active = [{"combo": "E", "status": "CONFIRMED_3_OF_3", "confirmed_legs": ["CAPE", "NFCI", "CFTC"]}]
        _, reason, _ = determine_dominant_combo(active)
        self.assertIn("confirmed (3/3)", reason)

    @_patch_stats
    def test_b_active_no_duration(self, _mock) -> None:
        active = [{"combo": "B", "status": "ACTIVE"}]
        _, reason, _ = determine_dominant_combo(active)
        self.assertIn("Combo B active.", reason)
        self.assertIn("80% 3M hit rate", reason)
        self.assertNotIn("week", reason)

    @_patch_stats
    def test_g_timing_only(self, _mock) -> None:
        active = [{"combo": "G", "status": "ACTIVE"}]
        _, reason, _ = determine_dominant_combo(active)
        self.assertIn("Timing signal only (no validated hit rate)", reason)

    @_patch_stats
    def test_c_immature_hit_rate(self, _mock) -> None:
        with patch(
            "src.macro_intelligence.engine.combo_metadata.combo_hit_rate_stats",
            side_effect=lambda letter: dict(FAKE_STATS["C_immature"]),
        ):
            active = [
                {
                    "combo": "C",
                    "status": "ACTIVE",
                    "duration_weeks": 11,
                    "duration_bucket": "MEDIUM",
                    "episode_start": "2026-03-10",
                }
            ]
            _, reason, _ = determine_dominant_combo(active)
        self.assertIn("No mature hit-rate data at 6M horizon", reason)
        self.assertNotIn("0% 6M", reason)


class TestDominantReasonPairs(unittest.TestCase):
    @_patch_stats
    def test_f_beats_e_prod_like(self, _mock) -> None:
        active = [
            {
                "combo": "F",
                "status": "ACTIVE",
                "duration_weeks": 12,
                "duration_bucket": "MEDIUM",
                "episode_start": "2026-04-03",
            },
            {
                "combo": "E",
                "status": "CONFIRMED",
                "duration_weeks": None,
                "confirmed_legs": ["CAPE", "NFCI"],
            },
        ]
        dom, reason, _ = determine_dominant_combo(active)
        self.assertEqual(dom, "F")
        self.assertIn("Outranks Combo E (19% 12M) on configured priority rank.", reason)
        self.assertNotIn("horizon fit", reason)

    @_patch_stats
    def test_c_beats_f_with_suffix(self, _mock) -> None:
        active = [
            {"combo": "F", "status": "ACTIVE", "duration_weeks": 8, "duration_bucket": "MEDIUM"},
            {
                "combo": "C",
                "status": "ACTIVE",
                "duration_weeks": 11,
                "duration_bucket": "MEDIUM",
                "episode_start": "2026-03-10",
            },
        ]
        dom, reason, _ = determine_dominant_combo(active)
        self.assertEqual(dom, "C")
        self.assertIn("Outranks Combo F (79% 6M) on configured priority rank.", reason)
        self.assertIn("Bearish medium-duration energy shock", reason)

    @_patch_stats
    def test_f_beats_a_higher_hr(self, _mock) -> None:
        active = [
            {"combo": "A", "status": "ACTIVE"},
            {
                "combo": "F",
                "status": "ACTIVE",
                "duration_weeks": 5,
                "duration_bucket": "SHORT",
            },
        ]
        dom, reason, _ = determine_dominant_combo(active)
        self.assertEqual(dom, "F")
        self.assertIn("Outranks Combo A (83% 6M) on configured priority rank.", reason)
        self.assertNotIn("horizon fit", reason)

    @_patch_stats
    def test_d_beats_g_no_hr_parens(self, _mock) -> None:
        active = [
            {"combo": "G", "status": "ACTIVE"},
            {"combo": "D", "status": "ACTIVE"},
        ]
        dom, reason, _ = determine_dominant_combo(active)
        self.assertEqual(dom, "D")
        self.assertIn("Outranks Combo G on configured priority rank.", reason)
        self.assertNotIn("(0%", reason)


class TestDominantReasonParametrize(unittest.TestCase):
    @_patch_stats
    def test_each_letter_sole_dominant(self, _mock) -> None:
        cases = {
            "A": ("Combo A active.", "83% 6M"),
            "B": ("Combo B active.", "80% 3M"),
            "C": ("Combo C active (week 10", "83% 6M"),
            "D": ("Combo D active.", "38% 5D"),
            "E": ("Combo E confirmed (2/3)", "19% 12M"),
            "F": ("Combo F active (week 10", "79% 6M"),
            "G": ("Combo G active.", "Timing signal only"),
        }
        status_map = {
            "A": "ACTIVE",
            "B": "ACTIVE",
            "C": "ACTIVE",
            "D": "ACTIVE",
            "E": "CONFIRMED",
            "F": "ACTIVE",
            "G": "ACTIVE",
        }
        for letter, (prefix, hr_part) in cases.items():
            combo = {"combo": letter, "status": status_map[letter]}
            if letter in ("C", "F"):
                combo.update(
                    duration_weeks=10,
                    duration_bucket="MEDIUM",
                    episode_start="2026-04-03",
                )
            if letter == "E":
                combo["confirmed_legs"] = ["CAPE", "NFCI"]
            _, reason, _ = determine_dominant_combo([combo])
            self.assertIn(prefix, reason, msg=f"letter={letter}")
            self.assertIn(hr_part, reason, msg=f"letter={letter}")


class TestDominantReasonDbIntegration(unittest.TestCase):
    """Smoke against live DB after backfill — skipped when DB missing."""

    @classmethod
    def setUpClass(cls) -> None:
        from src.config_paths import MACRO_INTEL_DB

        if not MACRO_INTEL_DB.exists():
            raise unittest.SkipTest("runic.db not present")

    def test_c_mature_6m_observations_exist(self) -> None:
        from src.macro_intelligence.engine.hit_rates import raw_hit_rate

        hr = raw_hit_rate("C", horizon="spx_6m", bullish=False)
        self.assertGreater(hr.get("n_obs") or 0, 0, "Combo C should have mature 6M forward returns after backfill")

    def test_live_f_e_reason_contract(self) -> None:
        import json
        from pathlib import Path

        from src.macro_intelligence.engine.dominant import resolve_dominant

        path = Path("macro_intelligence/output/runic_output.json")
        if not path.exists():
            self.skipTest("runic_output.json missing")
        data = json.loads(path.read_text())
        active = data.get("active_combos", [])
        if not active:
            self.skipTest("no active combos in fixture")
        _, reason, _ = resolve_dominant(active)
        self.assertNotIn("week None", reason)
        self.assertNotIn("horizon fit", reason)
        self.assertIn("configured priority rank", reason)


if __name__ == "__main__":
    unittest.main()
