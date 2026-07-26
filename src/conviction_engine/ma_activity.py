"""M&A activity detection and persistence (weekly cron, July 2026 spec)."""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta
from typing import Any

from .db.connection import get_connection
from .store import load_record, save_record, sanitize_ticker

logger = logging.getLogger(__name__)

_ACTIVE_RESPONSES = {"pending", "rejected", "accepted", "lapsed"}


def upsert_ma_activity(
    *,
    ticker: str,
    bidder: str | None,
    bid_price: float | None,
    bid_date: str,
    board_response: str = "pending",
    note: str | None = None,
    active: bool = True,
) -> None:
    symbol = sanitize_ticker(ticker)
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO ma_activity (ticker, bidder, bid_price, bid_date, board_response, note, last_updated, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker, bid_date) DO UPDATE SET
                bidder=excluded.bidder,
                bid_price=excluded.bid_price,
                board_response=excluded.board_response,
                note=excluded.note,
                last_updated=excluded.last_updated,
                active=excluded.active
            """,
            (symbol, bidder, bid_price, bid_date, board_response, note, now, int(active)),
        )
        conn.commit()


def get_active_ma(ticker: str) -> dict[str, Any] | None:
    symbol = sanitize_ticker(ticker)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM ma_activity WHERE ticker=? AND active=1 ORDER BY bid_date DESC LIMIT 1",
            (symbol,),
        ).fetchone()
    return dict(row) if row else None


def deactivate_stale_offers(max_idle_days: int = 90) -> int:
    cutoff = (date.today() - timedelta(days=max_idle_days)).isoformat()
    with get_connection() as conn:
        cur = conn.execute(
            """
            UPDATE ma_activity SET active=0
            WHERE active=1 AND date(last_updated) < date(?)
              AND board_response NOT IN ('accepted', 'lapsed')
            """,
            (cutoff,),
        )
        conn.commit()
        return cur.rowcount


def get_ma_flags(ticker: str) -> dict[str, Any]:
    """Return M&A fields for conviction record without saving."""
    active = get_active_ma(ticker)
    if not active:
        return {"m_and_a_activity": False}
    return {
        "m_and_a_activity": True,
        "m_and_a_bid_price": active.get("bid_price"),
        "m_and_a_note": active.get("note") or f"{active.get('bidder', 'Unknown')} bid",
        "m_and_a_board_response": active.get("board_response"),
    }


def _search_ma_with_agent(ticker: str, company_name: str) -> dict[str, Any] | None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    from .agent_dims import _call_claude_web_search, _apply_confidence_rules

    year = date.today().year
    system = """Search for active takeover/M&A bids. Respond ONLY JSON:
{"found": <bool>, "bidder": "<name>", "bid_price": <float|null>, "bid_date": "YYYY-MM-DD",
 "board_response": "pending|rejected|accepted|lapsed", "note": "<120 chars>",
 "sources": ["url"], "confidence": <0-1>}"""
    user = f'"{company_name} {ticker} takeover bid acquisition offer M&A {year}"'
    try:
        result = _call_claude_web_search(system=system, user=user, max_tokens=400)
        result = _apply_confidence_rules(result, default_score=0)
        if not result.get("found") or float(result.get("confidence", 0)) < 0.7:
            return None
        return result
    except Exception as exc:
        logger.warning("[ma_activity] agent search failed for %s: %s", ticker, exc)
        return None


def scan_ticker_ma(ticker: str, company_name: str | None = None) -> dict[str, Any]:
    symbol = sanitize_ticker(ticker)
    record = load_record(symbol) or {}
    name = company_name or record.get("company_name") or symbol
    hit = _search_ma_with_agent(symbol, str(name))
    if hit:
        bid_date = str(hit.get("bid_date") or date.today().isoformat())[:10]
        board = str(hit.get("board_response") or "pending").lower()
        if board not in _ACTIVE_RESPONSES:
            board = "pending"
        upsert_ma_activity(
            ticker=symbol,
            bidder=str(hit.get("bidder") or ""),
            bid_price=hit.get("bid_price"),
            bid_date=bid_date,
            board_response=board,
            note=str(hit.get("note") or ""),
            active=board not in ("accepted", "lapsed"),
        )
    sync_ma_to_conviction_store(symbol)
    return {"ticker": symbol, "found": bool(hit), "active": get_active_ma(symbol)}


def sync_ma_to_conviction_store(ticker: str) -> dict[str, Any] | None:
    """Write active M&A flags into conviction_store JSON."""
    symbol = sanitize_ticker(ticker)
    record = load_record(symbol)
    if record is None:
        return None
    record.update(get_ma_flags(symbol))
    if not record.get("m_and_a_activity"):
        record.pop("m_and_a_bid_price", None)
        record.pop("m_and_a_note", None)
        record.pop("m_and_a_board_response", None)
    save_record(record)
    return record


def run_weekly_ma_scan(tickers: list[str] | None = None) -> list[dict[str, Any]]:
    from .fundamentals import discover_universe

    universe = tickers or discover_universe(include_existing_records=True, include_signal_sources=True)
    deactivated = deactivate_stale_offers()
    logger.info("[ma_activity] deactivated %s stale offers", deactivated)
    results: list[dict[str, Any]] = []
    for ticker in universe:
        try:
            results.append(scan_ticker_ma(ticker))
        except Exception as exc:
            results.append({"ticker": ticker, "error": str(exc)})
    return results
