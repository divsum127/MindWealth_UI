"""Model-approved (Function, Interval, Signal) combos — FWD >= 60% gate membership."""

from __future__ import annotations

HIGH_WIN_RATE_COMBOS: frozenset[tuple[str, str, str]] = frozenset({
    ("ALTITUDE ALPHA", "YEARLY", "LONG"),
    ("ALTITUDE ALPHA", "WEEKLY", "LONG"),
    ("BAND MATRIX", "DAILY", "LONG"),
    ("BAND MATRIX", "WEEKLY", "LONG"),
    ("BAND MATRIX", "MONTHLY", "LONG"),
    ("BASELINEDIVERGENCE", "WEEKLY", "LONG"),
    ("DELTADRIFT", "DAILY", "LONG"),
    ("DELTADRIFT", "WEEKLY", "LONG"),
    ("DELTADRIFT", "MONTHLY", "LONG"),
    ("DELTADRIFT", "WEEKLY", "SHORT"),
    ("FRACTAL TRACK", "WEEKLY", "LONG"),
    ("FRACTAL TRACK", "MONTHLY", "SHORT"),
    ("FRACTAL TRACK", "WEEKLY", "SHORT"),
    ("OSCILLATOR DELTA", "DAILY", "LONG"),
    ("OSCILLATOR DELTA", "DAILY", "SHORT"),
    ("PULSEGAUGE", "WEEKLY", "LONG"),
    ("PULSEGAUGE", "WEEKLY", "SHORT"),
    ("SIGMASHELL", "DAILY", "LONG"),
    ("TRENDPULSE", "DAILY", "LONG"),
    ("TRENDPULSE", "WEEKLY", "LONG"),
    ("TRENDPULSE", "MONTHLY", "LONG"),
})


def normalize_combo_key(function: str, interval: str, signal: str) -> tuple[str, str, str]:
    return (
        str(function or "").strip().upper(),
        str(interval or "").strip().upper(),
        str(signal or "").strip().upper(),
    )
