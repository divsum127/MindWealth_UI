"""Per-combo hit-rate horizons, direction, and display metadata."""

from __future__ import annotations

from typing import Any

from src.macro_intelligence.config import load_config
from src.macro_intelligence.engine.hit_rates import raw_hit_rate

MIN_EPISODES_HIT_RATE_DEFAULT = 5

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


def min_episodes_for_hit_rate(letter: str) -> int:
    """Minimum mature episodes before briefing shows an actionable hit rate (D6: Combo C n=4)."""
    cfg = _combo_cfg(letter)
    raw = cfg.get("min_episodes_for_hit_rate", MIN_EPISODES_HIT_RATE_DEFAULT)
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return MIN_EPISODES_HIT_RATE_DEFAULT


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
    n_primary = int(primary_stats.get("n_obs") or 0)
    min_n = min_episodes_for_hit_rate(letter)
    insufficient = n_primary < min_n
    if insufficient:
        return {
            "show_hit_rate": True,
            "insufficient_episodes": True,
            "min_episodes_required": min_n,
            "primary_horizon": primary,
            "primary_label": horizon_display_label(primary),
            "hit_rate_primary": None,
            "avg_return_primary": None,
            "n_obs_primary": n_primary,
            "hit_rate_secondary": None,
            "avg_return_secondary": None,
            "secondary_label": horizon_display_label(secondary) if secondary else None,
            "n_obs_secondary": secondary_stats.get("n_obs") if secondary_stats else None,
        }
    return {
        "show_hit_rate": True,
        "insufficient_episodes": False,
        "min_episodes_required": min_n,
        "primary_horizon": primary,
        "primary_label": horizon_display_label(primary),
        "hit_rate_primary": primary_stats.get("hit_rate"),
        "avg_return_primary": primary_stats.get("avg_return"),
        "n_obs_primary": n_primary,
        "hit_rate_secondary": secondary_stats.get("hit_rate") if secondary_stats else None,
        "avg_return_secondary": secondary_stats.get("avg_return") if secondary_stats else None,
        "secondary_label": horizon_display_label(secondary) if secondary else None,
        "n_obs_secondary": secondary_stats.get("n_obs") if secondary_stats else None,
    }


def hit_rate_reason_clause(stats: dict[str, Any]) -> str:
    """Full hit-rate phrase for dominant_reason (neutral, numeric)."""
    if not stats.get("show_hit_rate"):
        return "Timing signal only (no validated hit rate)."
    if stats.get("insufficient_episodes"):
        n_obs = stats.get("n_obs_primary") or 0
        min_n = stats.get("min_episodes_required", MIN_EPISODES_HIT_RATE_DEFAULT)
        return f"Insufficient episodes for validated hit rate (n={n_obs}, need ≥{min_n})."
    hr = stats.get("hit_rate_primary")
    n_obs = stats.get("n_obs_primary") or 0
    label = stats.get("primary_label", "3M")
    if hr is None or n_obs == 0:
        return f"No mature hit-rate data at {label} horizon."
    return f"{hr * 100:.0f}% {label} hit rate."


def hit_rate_reason_short(stats: dict[str, Any]) -> str | None:
    """Compact hit-rate for outrank parens; None when not displayable."""
    if not stats.get("show_hit_rate"):
        return None
    if stats.get("insufficient_episodes"):
        return "insufficient episodes"
    hr = stats.get("hit_rate_primary")
    n_obs = stats.get("n_obs_primary") or 0
    if hr is None or n_obs == 0:
        return None
    label = stats.get("primary_label", "3M")
    return f"{hr * 100:.0f}% {label}"


def format_reason_hit_rate(letter: str) -> str:
    return hit_rate_reason_clause(combo_hit_rate_stats(letter))


def format_reason_hit_rate_short(letter: str) -> str | None:
    return hit_rate_reason_short(combo_hit_rate_stats(letter))


def combo_fed_cycle_slice_stats(letter: str) -> dict[str, Any] | None:
    """Fed-cycle slice table for combos with validated D5-style breakdown (e.g. Combo D)."""
    slice_cfg = _combo_cfg(letter).get("fed_cycle_slices")
    if not slice_cfg:
        return None
    min_n = int(slice_cfg.get("min_episodes", 10))
    regimes = slice_cfg.get("regimes") or []
    validated = slice_cfg.get("validated") or {}
    primary = combo_primary_horizon(letter) or "spx_3m"
    secondary = combo_secondary_horizon(letter)
    horizons = [h for h in (primary, secondary) if h]

    slices: list[dict[str, Any]] = []
    for regime in regimes:
        reg_data = validated.get(regime, {})
        horizon_stats: dict[str, Any] = {}
        for horizon in horizons:
            hdata = reg_data.get(horizon, {})
            n = int(hdata.get("n") or 0)
            horizon_stats[horizon] = {
                "label": horizon_display_label(horizon),
                "n": n,
                "hit_rate": hdata.get("hit_rate"),
                "avg_return": hdata.get("avg_return"),
                "verdict": "USE" if n >= min_n else "CANNOT USE",
            }
        primary_n = int((reg_data.get(primary) or {}).get("n") or 0)
        slices.append(
            {
                "fed_cycle": regime,
                "verdict": "USE" if primary_n >= min_n else "CANNOT USE",
                "horizons": horizon_stats,
            }
        )

    return {
        "min_episodes": min_n,
        "validated_source": slice_cfg.get("validated_source"),
        "validated_config_id": slice_cfg.get("validated_config_id"),
        "slices": slices,
    }


def format_hit_rate_display(stats: dict[str, Any]) -> tuple[str, str]:
    """Return (hit_rate_cell, avg_return_cell) for briefing table."""
    if not stats.get("show_hit_rate"):
        return "N/A", "N/A"
    if stats.get("insufficient_episodes"):
        return "insufficient episodes", "—"
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
