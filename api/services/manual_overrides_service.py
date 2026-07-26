"""MANUAL sizing scenario — user-set size overrides, persisted (D4 / spec_15July.md).

"MANUAL stays exactly as it works today": the user sets an explicit $ size for a position;
REFRESH SIZES recomputes shares/market-value/pnl against the latest prices while keeping the
user's $ allocation fixed, until they change or remove the override. Overrides persist in a
small JSON store (same pattern as ``api/services/personal_book_service.py``) — not committed
to git (runtime artifact, see .gitignore).
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from typing import Any

from src.config_paths import BASE_DIR

_STORE_PATH = BASE_DIR / "config" / "manual_sizing_overrides.json"
_lock = threading.Lock()


def _key(ticker: str, function: str | None, interval: str | None, direction: str | None) -> str:
    return "|".join([
        str(ticker or "").upper(),
        str(function or "").upper(),
        str(interval or ""),
        str(direction or "Long"),
    ])


def _load() -> dict[str, dict[str, Any]]:
    if not _STORE_PATH.is_file():
        return {}
    try:
        raw = json.loads(_STORE_PATH.read_text())
        return raw.get("overrides", {}) if isinstance(raw, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save(overrides: dict[str, dict[str, Any]]) -> None:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STORE_PATH.write_text(json.dumps({"overrides": overrides}, indent=2))


def list_overrides() -> list[dict[str, Any]]:
    return list(_load().values())


def set_override(
    *,
    ticker: str,
    allocation_usd: float,
    function: str | None = None,
    interval: str | None = None,
    direction: str | None = "Long",
) -> dict[str, Any]:
    if allocation_usd < 0:
        raise ValueError("allocation_usd must be >= 0")
    with _lock:
        overrides = _load()
        key = _key(ticker, function, interval, direction)
        entry = {
            "ticker": str(ticker or "").upper(),
            "function": function,
            "interval": interval,
            "direction": direction or "Long",
            "allocation_usd": float(allocation_usd),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        overrides[key] = entry
        _save(overrides)
        return entry


def remove_override(
    *,
    ticker: str,
    function: str | None = None,
    interval: str | None = None,
    direction: str | None = "Long",
) -> bool:
    with _lock:
        overrides = _load()
        key = _key(ticker, function, interval, direction)
        if key not in overrides:
            return False
        del overrides[key]
        _save(overrides)
        return True


def override_for(ticker: str, function: str | None, interval: str | None, direction: str | None) -> float | None:
    overrides = _load()
    key = _key(ticker, function, interval, direction)
    entry = overrides.get(key)
    return float(entry["allocation_usd"]) if entry else None


def apply_manual_overrides(sized_rows: list[dict[str, Any]]) -> int:
    """Mutate ``allocation_usd``/``allocation_pct`` in place for rows with a persisted override.

    Recomputes shares/market_value/pnl from the override $ against each row's already-resolved
    live price — "REFRESH SIZES recomputes against them" (spec_15July.md).
    """
    overrides = _load()
    if not overrides:
        return 0
    applied = 0
    for row in sized_rows:
        key = _key(row.get("ticker"), row.get("function"), row.get("interval"), row.get("direction"))
        entry = overrides.get(key)
        if entry is None:
            continue
        allocation_usd = float(entry["allocation_usd"])
        row["allocation_usd"] = allocation_usd
        row["manual_override"] = True
        row["blocked"] = False
        row["blocked_reason"] = None
        row["waiting"] = False
        row["wait_reason"] = None
        entry_price = row.get("entry_price")
        today_price = row.get("today_price")
        shares = round(allocation_usd / entry_price, 4) if entry_price and entry_price > 0 else None
        row["shares"] = shares
        if shares is not None and today_price is not None:
            market_value = round(shares * today_price, 2)
            row["market_value_usd"] = market_value
            row["pnl_usd"] = round(market_value - allocation_usd, 2)
        applied += 1
    return applied
