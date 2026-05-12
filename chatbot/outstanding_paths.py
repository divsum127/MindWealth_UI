"""
Path resolution for outstanding-signal (open position) CSV exports.

Kept separate from ``chatbot.config`` so imports cannot fail if ``config`` is trimmed
or load order changes; ``config`` re-exports :func:`resolve_outstanding_signal_path`.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def trade_store_us_dir() -> Path:
    """``{TRADE_STORE_DIR}/{TRADE_STORE_US_SUBPATH}`` under the project root (default ``trade_store/US``)."""
    root = _project_root()
    trade_store = root / os.getenv("TRADE_STORE_DIR", "trade_store")
    return Path(trade_store) / os.getenv("TRADE_STORE_US_SUBPATH", "US")


def resolve_outstanding_signal_path() -> Optional[Path]:
    """
    Path to the outstanding-signal CSV used as the primary entry source when the file exists.

    1. ``OUTSTANDING_SIGNAL_CSV`` — absolute or relative to project root, if set and exists.
    2. ``{trade_store_us_dir()}/outstanding_signal.csv``
    3. Newest ``*_outstanding_signal.csv`` in that directory by mtime.
    """
    raw = os.getenv("OUTSTANDING_SIGNAL_CSV", "").strip()
    base = _project_root()
    if raw:
        p = Path(raw).expanduser()
        if not p.is_absolute():
            p = base / p
        return p if p.is_file() else None

    us = trade_store_us_dir()
    if not us.is_dir():
        return None

    exact = us / "outstanding_signal.csv"
    if exact.is_file():
        return exact

    dated = [f for f in us.glob("*_outstanding_signal.csv") if f.is_file()]
    if not dated:
        return None

    dated.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return dated[0]
