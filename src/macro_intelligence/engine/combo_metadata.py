"""Per-combo hit-rate horizons, direction, and display metadata."""

from __future__ import annotations

from typing import Any

from src.macro_intelligence.config import load_config
from src.macro_intelligence.engine.hit_rates import raw_hit_rate

_HORIZON_LABELS = {
    "spx_1w": "5D",
    "spx_2w": "2W",
    "spx_1m": "1M",
    "spx_3m": "3M",
    "spx_6m": "6M",
    "spx_9m": "9M",
    "spx_12m": "12M",
}


def _combo_cfg(letter: str) -> dict[str, Any]:
    cfg = load_config().get("combo_hit_rates", {})
    return cfg.get(letter.upper(), {})


def combo_bullish(letter: str) -> bool | None:
    """True = SPX up is success; False = SPX down is success; None = no return HR."""
    direction = _combo_cfg(letter).get("direction")
    if direction == "bullish":
        return True
    if direction == "bearish":
        return False
    return None


def combo_show_hit_rate(letter: str) -> bool:
    return bool(_combo_cfg(letter).get("show_hit_rate", True))


def combo_primary_horizon(letter: str) -> str | None:
    return _combo_cfg(letter).get("primary_horizon")


def combo_secondary_horizon(letter: str) -> str | None:
    return _combo_cfg(letter).get("secondary_horizon")


def horizon_display_label(horizon_col: str | None) -> str:
    if not horizon_col:
        return "—"
    return _HORIZON_LABELS.get(horizon_col, horizon_col.upper().replace("SPX_", ""))


def combo_hit_rate_stats(letter: str) -> dict[str, Any]:
    """Primary (and optional secondary) hit rate from historical combo fires."""
    if not combo_show_hit_rate(letter):
        return {
            "show_hit_rate": False,
            "primary_horizon": None,
            "primary_label": "N/A",
            "hit_rate_primary": None,
            "avg_return_primary": None,
            "hit_rate_secondary": None,
            "avg_return_secondary": None,
            "secondary_label": None,
        }
    bullish = combo_bullish(letter)
    if bullish is None:
        bullish = True
    primary = combo_primary_horizon(letter) or "spx_3m"
    secondary = combo_secondary_horizon(letter)
    primary_stats = raw_hit_rate(letter, horizon=primary, bullish=bullish)
    secondary_stats = (
        raw_hit_rate(letter, horizon=secondary, bullish=bullish) if secondary else None
    )
    return {
        "show_hit_rate": True,
        "primary_horizon": primary,
        "primary_label": horizon_display_label(primary),
        "hit_rate_primary": primary_stats.get("hit_rate"),
        "avg_return_primary": primary_stats.get("avg_return"),
        "n_obs_primary": primary_stats.get("n_obs"),
        "hit_rate_secondary": secondary_stats.get("hit_rate") if secondary_stats else None,
        "avg_return_secondary": secondary_stats.get("avg_return") if secondary_stats else None,
        "secondary_label": horizon_display_label(secondary) if secondary else None,
        "n_obs_secondary": secondary_stats.get("n_obs") if secondary_stats else None,
    }


def format_hit_rate_display(stats: dict[str, Any]) -> tuple[str, str]:
    """Return (hit_rate_cell, avg_return_cell) for briefing table."""
    if not stats.get("show_hit_rate"):
        return "N/A", "N/A"
    hr = stats.get("hit_rate_primary")
    avg = stats.get("avg_return_primary")
    label = stats.get("primary_label", "3M")
    hr_txt = f"{hr * 100:.1f}% ({label})" if hr is not None else "—"
    if avg is not None:
        avg_txt = f"{avg:+.1f}% ({label})"
    else:
        avg_txt = "—"
    return hr_txt, avg_txt


def posture_display(raw: str | None) -> str:
    """Map internal posture codes to briefing labels."""
    if not raw:
        return "NEUTRAL"
    mapping = {
        "TACTICAL_BRAVE": "TACTICAL EASY MONEY",
        "TACTICAL_EASY_MONEY": "TACTICAL EASY MONEY",
        "STRATEGIC_BRAVE": "STRATEGIC EASY MONEY",
        "STRATEGIC_EASY_MONEY": "STRATEGIC EASY MONEY",
        "TACTICAL_FEARFUL_STRATEGIC_BRAVE": "TACTICAL TIGHT MONEY / STRATEGIC EASY MONEY",
        "TACTICAL_FEARFUL_STRATEGIC_EASY_MONEY": "TACTICAL TIGHT MONEY / STRATEGIC EASY MONEY",
        "TACTICAL_TIGHT_MONEY": "TACTICAL TIGHT MONEY",
        "TACTICAL_TIGHT_MONEY_STRATEGIC_EASY_MONEY": "TACTICAL TIGHT MONEY / STRATEGIC EASY MONEY",
        "TACTICAL_EASY_MONEY_STRATEGIC_TIGHT_MONEY": "TACTICAL EASY MONEY / STRATEGIC TIGHT MONEY",
        "STRATEGIC_TIGHT_MONEY": "STRATEGIC TIGHT MONEY",
        "TACTICAL_FEARFUL": "TACTICAL TIGHT MONEY",
    }
    return mapping.get(raw, raw.replace("_", " "))
