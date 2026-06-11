"""BTIG briefing HTML/PDF smoke tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.output.briefing_renderer import (
    build_briefing_sections,
    render_html,
    write_briefing,
)


def _sample_payload() -> dict:
    return {
        "date": "2026-05-26",
        "dominant_signal": "C",
        "dominant_reason": "Combo C active week 11. Energy shock dominates near-term risk.",
        "brave_fearful": "TACTICAL_FEARFUL",
        "regime": {
            "fed_cycle": "CUTTING_EARLY",
            "curve_regime": "STEEPENING",
            "geo_overlay": "REGIONAL_WAR",
            "val_regime": "EXTREME",
            "liquidity": "GLOBAL_EASY",
        },
        "active_combos": [
            {
                "combo": "C",
                "status": "ACTIVE",
                "duration_weeks": 11,
                "duration_bucket": "MEDIUM",
                "hit_rate_3m": 0.83,
                "avg_return_3m": -3.2,
            },
            {
                "combo": "F",
                "status": "ACTIVE",
                "duration_weeks": 8,
                "duration_bucket": "MEDIUM",
                "hit_rate_3m": 0.78,
                "avg_return_3m": 9.5,
            },
        ],
        "watch_combos": ["D"],
        "variables_dashboard": [
            {
                "num": 1,
                "variable": "NFCI",
                "current": -0.523,
                "tier": "NORMAL",
                "pctile_3yr": 30,
                "direction": "Loosening",
            },
            {
                "num": 12,
                "variable": "CAPE",
                "current": 42.04,
                "tier": "EXTREME",
                "pctile_3yr": 97,
                "direction": "Elevated",
            },
        ],
        "narrative": "The dominant macro signal is Combo C, which outweighs competing signals because energy shocks persist.",
        "ssi_multiplier": 1.0,
        "ssi_layer2_status": "PARTIAL",
        "combo_c_cancel": {"active": True, "wti_potential_week": 2},
        "pending_cpi_release": True,
    }


class TestBriefingRenderer(unittest.TestCase):
    def test_sections_contain_spec_blocks(self) -> None:
        sections = build_briefing_sections(_sample_payload())
        self.assertEqual(len(sections["combo_rows"]), 7)
        self.assertEqual(sections["dominant_signal"], "C")
        self.assertIn("Stagflation", sections["dominant_label"])
        self.assertTrue(sections["system_recommendation"])

    def test_render_contains_sections(self) -> None:
        payload = _sample_payload()
        html = render_html(payload)
        self.assertIn("DOMINANT SIGNAL", html)
        self.assertIn("Combo Status", html)
        self.assertIn("System Recommendation", html)
        self.assertIn("Variable Dashboard", html)

    def test_write_briefing_html_and_pdf(self) -> None:
        import tempfile

        payload = _sample_payload()
        with tempfile.TemporaryDirectory() as tmp:
            paths = write_briefing(payload, out_dir=Path(tmp))
            self.assertIn("html", paths)
            self.assertTrue(paths["html"].exists())
            self.assertIn("pdf", paths)
            self.assertTrue(paths["pdf"].exists())
            self.assertGreater(paths["pdf"].stat().st_size, 4000,
                               "PDF must be >4 KB — empty stub detected")
            html_text = paths["html"].read_text(encoding="utf-8")
            self.assertIn("DOMINANT SIGNAL", html_text)
            self.assertIn("System Recommendation", html_text)

    def test_html_colour_palette(self) -> None:
        """Verify navy header, coloured combo rows, amber EXTREME var row."""
        html = render_html(_sample_payload())
        # Navy header present
        self.assertIn(_NAVY := "#0A1628", html)
        # Active combo rows are green-highlighted
        self.assertIn("#1A5C38", html)
        # WATCH combo row is amber
        self.assertIn("#7D5200", html)
        # EXTREME var row uses amber
        self.assertIn("#7D5200", html)
        # Recommendation box uses navy
        self.assertIn("#0A1628", html)

    def test_pdf_long_combo_duration(self) -> None:
        """PDF combo table should render long duration strings without error."""
        import tempfile

        from src.macro_intelligence.output.briefing_renderer import render_pdf

        payload = _sample_payload()
        payload["active_combos"] = [
            {
                "combo": "F",
                "status": "ACTIVE",
                "duration_weeks": 10,
                "duration_bucket": "MEDIUM",
                "episode_start": "2026-04-03",
                "hit_rate_3m": 0.788,
                "avg_return_3m": 5.5,
            },
            {
                "combo": "E",
                "status": "CONFIRMED",
                "confirmed_legs": ["CAPE", "NFCI"],
                "hit_rate_3m": 0.189,
                "avg_return_3m": 10.9,
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = Path(tmp) / "long_duration.pdf"
            render_pdf(payload, pdf_path)
            self.assertTrue(pdf_path.exists())
            self.assertGreater(pdf_path.stat().st_size, 4000)


if __name__ == "__main__":
    unittest.main()
