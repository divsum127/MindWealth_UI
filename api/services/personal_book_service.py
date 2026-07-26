"""Personal book (book_id=personal) — user-entered holdings, CRUD + live snapshot (Phase 7).

Scope (per the always-applied repo rules and 21July_review_specs.md): personal is a manual
holdings tracker, not a NAV-engine valuation book. There is no historical daily NAV series for
it (we don't know what the user held on any past date) — ``get_personal_nav_payload()`` returns
a single **live snapshot** and discloses that boundary via ``data_status``, never a fabricated
history. Storage is a small JSON file (same pattern as ``manual_overrides_service.py``), not
committed to git (see .gitignore).
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from typing import Any

from src.config_paths import PERSONAL_HOLDINGS_JSON

_lock = threading.Lock()


def _load() -> dict[str, Any]:
    if not PERSONAL_HOLDINGS_JSON.is_file():
        return {"holdings": {}, "cash_usd": 0.0}
    try:
        raw = json.loads(PERSONAL_HOLDINGS_JSON.read_text())
        if not isinstance(raw, dict):
            return {"holdings": {}, "cash_usd": 0.0}
        raw.setdefault("holdings", {})
        raw.setdefault("cash_usd", 0.0)
        return raw
    except (json.JSONDecodeError, OSError):
        return {"holdings": {}, "cash_usd": 0.0}


def _save(data: dict[str, Any]) -> None:
    PERSONAL_HOLDINGS_JSON.parent.mkdir(parents=True, exist_ok=True)
    PERSONAL_HOLDINGS_JSON.write_text(json.dumps(data, indent=2))


def list_holdings() -> list[dict[str, Any]]:
    return list(_load()["holdings"].values())


def upsert_holding(
    *,
    ticker: str,
    shares: float,
    cost_basis: float,
    entry_date: str | None = None,
    currency: str = "USD",
    notes: str | None = None,
) -> dict[str, Any]:
    if shares <= 0:
        raise ValueError("shares must be > 0")
    if cost_basis < 0:
        raise ValueError("cost_basis must be >= 0")
    with _lock:
        data = _load()
        ticker = str(ticker or "").upper().strip()
        if not ticker:
            raise ValueError("ticker is required")
        entry = {
            "ticker": ticker,
            "shares": float(shares),
            "cost_basis": float(cost_basis),
            "entry_date": entry_date,
            "currency": currency or "USD",
            "notes": notes,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        data["holdings"][ticker] = entry
        _save(data)
        return entry


def remove_holding(ticker: str) -> bool:
    with _lock:
        data = _load()
        ticker = str(ticker or "").upper().strip()
        if ticker not in data["holdings"]:
            return False
        del data["holdings"][ticker]
        _save(data)
        return True


def get_cash() -> float:
    return float(_load().get("cash_usd") or 0.0)


def set_cash(cash_usd: float) -> float:
    if cash_usd < 0:
        raise ValueError("cash_usd must be >= 0")
    with _lock:
        data = _load()
        data["cash_usd"] = float(cash_usd)
        _save(data)
        return data["cash_usd"]


def _live_price(ticker: str) -> float | None:
    from api.services.portfolio_service import _fetch_price_safe

    return _fetch_price_safe(ticker)


def _ticker_name(ticker: str) -> str:
    try:
        from api.services.portfolio_service import _refresh_ticker_names_cache

        return _refresh_ticker_names_cache({ticker}, max_fetch=1).get(ticker, ticker)
    except Exception:
        return ticker


def get_personal_snapshot() -> dict[str, Any]:
    """Enriched holdings + cash + totals, priced live. No history — single point in time."""
    data = _load()
    cash_usd = float(data.get("cash_usd") or 0.0)
    rows: list[dict[str, Any]] = []
    total_market_value = cash_usd
    total_cost_basis = cash_usd
    for h in data["holdings"].values():
        ticker = h["ticker"]
        shares = float(h["shares"])
        cost_basis = float(h["cost_basis"])
        price = _live_price(ticker)
        market_value = round(shares * price, 2) if price else None
        cost_value = round(shares * cost_basis, 2)
        pnl_usd = round(market_value - cost_value, 2) if market_value is not None else None
        pnl_pct = round((pnl_usd / cost_value) * 100, 2) if pnl_usd is not None and cost_value else None
        rows.append({
            "ticker": ticker,
            "name": _ticker_name(ticker),
            "shares": shares,
            "entry_price": cost_basis,
            "current_price": price,
            "entry_date": h.get("entry_date"),
            "currency": h.get("currency", "USD"),
            "notes": h.get("notes"),
            "market_value": market_value,
            "cost_value": cost_value,
            "pnl_usd": pnl_usd,
            "mtm_pct": pnl_pct,
            "status": "Open",
        })
        if market_value is not None:
            total_market_value += market_value
        total_cost_basis += cost_value

    total_pnl_usd = round(total_market_value - total_cost_basis, 2)
    total_pnl_pct = round((total_pnl_usd / total_cost_basis) * 100, 2) if total_cost_basis else None

    return {
        "holdings": rows,
        "cash_usd": cash_usd,
        "position_count": len(rows),
        "total_market_value_usd": round(total_market_value, 2),
        "total_cost_basis_usd": round(total_cost_basis, 2),
        "total_pnl_usd": total_pnl_usd,
        "total_pnl_pct": total_pnl_pct,
        "as_of": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }


def get_personal_nav_history() -> list[dict[str, Any]]:
    """Daily NAV series accumulated by ``scripts/run_personal_book_snapshot_daily.py`` — empty
    until that job has run at least once. No backfill before its first run date; see
    ``src/portfolio_nav/book_snapshot_store.py``'s ``personal_book_snapshot_daily`` table."""
    from src.portfolio_nav import book_snapshot_store as store

    rows = store.read_personal_book_series()
    return [
        {
            "date": r.get("snapshot_date"),
            "nav": r.get("nav_usd"),
            "cash_usd": r.get("cash_usd"),
            "position_count": r.get("position_count"),
            "total_pnl_usd": r.get("total_pnl_usd"),
            "total_pnl_pct": r.get("total_pnl_pct"),
        }
        for r in rows
    ]


def get_personal_holdings_payload(book_id: str = "personal") -> dict[str, Any]:
    snap = get_personal_snapshot()
    return {
        "book_id": book_id,
        "book": None,
        "as_of": snap["as_of"],
        "holdings": snap["holdings"],
    }


def get_personal_nav_payload(book_id: str = "personal") -> dict[str, Any]:
    """Live snapshot NAV point, plus whatever daily history the snapshot job has accumulated
    since it first ran (never backfilled before that date)."""
    snap = get_personal_snapshot()
    nav = snap["total_market_value_usd"]
    history = get_personal_nav_history()

    if history:
        earliest = history[0]["date"]
        note = (
            f"Personal book NAV history starts {earliest} — the day the daily snapshot job "
            "first ran. No data before that date exists or is fabricated; holdings are "
            "user-entered so there is no way to know what was held on earlier dates."
        )
        data_status = {"status": "live_from_snapshot_start", "earliest_date": earliest, "note": note}
        mtm_daily = [{"date": h["date"], "nav": h["nav"]} for h in history if h.get("nav") is not None]
    else:
        note = (
            "Personal book has no historical NAV series yet — holdings are user-entered with no "
            "known past valuation dates, and the daily snapshot job has not run yet. This is a "
            "single live snapshot, not a replayed history."
        )
        data_status = {"status": "live_snapshot_only", "note": note}
        mtm_daily = []

    return {
        "book_id": book_id,
        "book": None,
        "as_of": snap["as_of"],
        "nav": nav,
        "cash_usd": snap["cash_usd"],
        "position_count": snap["position_count"],
        # Unrealized P&L since each position's entry — NOT a daily change (no prior-day price
        # is stored for a user-entered book). Deliberately not named day_mtm_* to avoid implying
        # otherwise.
        "total_pnl_usd": snap["total_pnl_usd"],
        "total_pnl_pct": snap["total_pnl_pct"],
        "holdings": snap["holdings"],
        "mtm": mtm_daily,
        "mtm_daily": mtm_daily,
        "monthly_returns": [],
        "attribution": [],
        "data_status": data_status,
        "nav_history_note": note,
    }
