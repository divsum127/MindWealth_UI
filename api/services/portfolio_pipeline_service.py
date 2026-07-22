"""Portfolio pipeline adapters — entries, exits, holdings, portfolio-risk (HANDOFF)."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from api.services import portfolio_book as book_svc
from api.services import portfolio_service as portfolio_svc
from api.services import reports_service
from api.services.portfolio_book import BookUnavailableError, validate_book_access

_SYM_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
_SYM_PRICE_RE = re.compile(r"Price:\s*([\d.]+)")


def _as_of_iso(report_date: str | None = None) -> str:
    if report_date:
        return f"{report_date}T16:00:00Z"
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-") or "unknown"


def _pos_key(
    symbol: str,
    function: str | None,
    interval: str | None,
    direction: str | None,
) -> tuple[str, str, str, str]:
    return (
        str(symbol or "").upper(),
        str(function or "").upper(),
        str(interval or ""),
        str(direction or "Long"),
    )


def _parse_signal_meta(row: dict[str, Any]) -> dict[str, Any]:
    sym_field = str(
        row.get("Symbol, Signal, Signal Date/Price[$]")
        or row.get("symbol")
        or ""
    )
    parts = [p.strip() for p in sym_field.split(",")]
    symbol = (row.get("symbol") or (parts[0] if parts else "")).strip().upper()
    direction = (row.get("direction") or (parts[1] if len(parts) > 1 else "Long")).strip()
    signal_date = None
    entry_price = None
    if len(parts) > 2:
        date_part = parts[2]
        m_date = _SYM_DATE_RE.search(date_part)
        if m_date:
            signal_date = m_date.group(1)
        m_price = _SYM_PRICE_RE.search(date_part)
        if m_price:
            entry_price = float(m_price.group(1))

    interval_field = str(row.get("Interval, Confirmation Status") or row.get("interval") or "")
    interval = interval_field.split(",")[0].strip() if interval_field else str(row.get("interval") or "")

    function = str(row.get("Function") or row.get("function") or "").strip()
    return {
        "symbol": symbol,
        "function": function,
        "interval": interval,
        "direction": direction,
        "signal_date": signal_date or row.get("Entry Date") or row.get("entry_date"),
        "entry_price": entry_price or _safe_float(row.get("Signal Open Price") or row.get("entry_price")),
    }


def _safe_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return float(str(val).replace("%", "").strip())
    except (ValueError, TypeError):
        return None


def _score(row: dict[str, Any]) -> float | None:
    return _safe_float(
        row.get("composite_score")
        or row.get("Signal Quality Composite Score")
    )


def _fwd_wr(row: dict[str, Any]) -> float | None:
    return _safe_float(row.get("fwd_wr"))


def _rr_dynamic(row: dict[str, Any]) -> float | None:
    return _safe_float(row.get("rr_dynamic") or row.get("R:R Dynamic"))


def _hold_time_used_pct(row: dict[str, Any]) -> float | None:
    days = row.get("days_elapsed")
    avg_hold = row.get("avg_hold_days")
    if days is None or not avg_hold:
        return None
    try:
        return round(float(days) / float(avg_hold) * 100, 1)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _implied_natural_exit_date(signal_date: str | None, avg_hold_days: int | None) -> str | None:
    if not signal_date or not avg_hold_days:
        return None
    try:
        start = datetime.strptime(str(signal_date)[:10], "%Y-%m-%d")
        return (start + timedelta(days=int(avg_hold_days))).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def _build_exit_ref(row: dict[str, Any]) -> str | None:
    display = row.get("cross_function_exit_display") or row.get("Cross-Function Exit")
    if display and str(display).strip():
        return str(display).strip()
    xf_fn = row.get("cross_function_exit_function")
    xf_date = row.get("cross_function_exit_date")
    xf_price = row.get("cross_function_exit_price")
    if xf_fn:
        parts = [f"Cross-function exit via {xf_fn}"]
        if xf_date:
            parts.append(f"({xf_date})")
        if xf_price:
            parts.append(f"@ {xf_price}")
        return " ".join(parts)
    rr = _rr_dynamic(row)
    if rr is not None and rr < 0:
        return "Reward exhausted — dynamic R:R negative (past average exit horizon)"
    return None


def _conviction_tier_from_size_tier(size_tier: str | None) -> str | None:
    if not size_tier:
        return None
    label = str(size_tier).split()[0].upper()
    if label == "BLOCKED":
        return "BLOCKED"
    return label


def _build_allocation_index(sizer: dict[str, Any]) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    index: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for cluster in sizer.get("clusters", []):
        sleeve = cluster.get("label") or cluster.get("id")
        for pos in cluster.get("positions", []):
            key = _pos_key(
                pos.get("ticker", ""),
                pos.get("function"),
                pos.get("interval"),
                pos.get("direction"),
            )
            pos_copy = dict(pos)
            pos_copy["sleeve"] = sleeve
            index[key] = pos_copy
    return index


def _build_sibling_index(
    outstanding: list[dict[str, Any]],
    new_rows: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], set[tuple[str, str, str, str]], set[tuple[str, str, str, str]]]:
    held_keys = {
        _pos_key(
            _parse_signal_meta(r)["symbol"],
            _parse_signal_meta(r)["function"],
            _parse_signal_meta(r)["interval"],
            _parse_signal_meta(r)["direction"],
        )
        for r in outstanding
    }
    new_keys = {
        _pos_key(
            _parse_signal_meta(r)["symbol"],
            _parse_signal_meta(r)["function"],
            _parse_signal_meta(r)["interval"],
            _parse_signal_meta(r)["direction"],
        )
        for r in new_rows
    }
    by_symbol: dict[str, list[dict[str, Any]]] = {}
    for row in outstanding + new_rows:
        sym = _parse_signal_meta(row)["symbol"]
        if sym:
            by_symbol.setdefault(sym, []).append(row)
    return by_symbol, held_keys, new_keys


def _same_asset_siblings(
    row: dict[str, Any],
    sibling_rows: list[dict[str, Any]],
    *,
    held_keys: set,
    new_keys: set,
) -> list[dict[str, Any]]:
    meta = _parse_signal_meta(row)
    self_key = _pos_key(meta["symbol"], meta["function"], meta["interval"], meta["direction"])
    out: list[dict[str, Any]] = []
    for other in sibling_rows:
        ometa = _parse_signal_meta(other)
        okey = _pos_key(ometa["symbol"], ometa["function"], ometa["interval"], ometa["direction"])
        if okey == self_key:
            continue
        rel = "already_held" if okey in held_keys else "new_signal" if okey in new_keys else "new_signal"
        out.append({
            "symbol": ometa["symbol"],
            "function": ometa["function"],
            "interval": ometa["interval"],
            "direction": ometa["direction"],
            "signal_date": ometa["signal_date"],
            "relationship": rel,
            "forward_win_rate_pct": _fwd_wr(other),
            "rr_dynamic": _rr_dynamic(other),
            "avg_hold_days": other.get("avg_hold_days"),
            "days_elapsed": other.get("days_elapsed"),
        })
    return out


def _multi_sig(row: dict[str, Any], sibling_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    meta = _parse_signal_meta(row)
    self_key = _pos_key(meta["symbol"], meta["function"], meta["interval"], meta["direction"])
    direction = meta["direction"]
    out: list[dict[str, Any]] = []
    for other in sibling_rows:
        ometa = _parse_signal_meta(other)
        okey = _pos_key(ometa["symbol"], ometa["function"], ometa["interval"], ometa["direction"])
        if okey == self_key or ometa["direction"] != direction:
            continue
        out.append({
            "function": ometa["function"],
            "interval": ometa["interval"],
            "direction": ometa["direction"],
            "signal_date": ometa["signal_date"],
            "forward_win_rate_pct": _fwd_wr(other),
        })
    return out


def _lookup_hold_days(
    symbol: str,
    function: str,
    interval: str,
    outstanding_index: dict[tuple[str, str, str, str], dict[str, Any]],
) -> int | None:
    for key, row in outstanding_index.items():
        if key[0] == symbol.upper() and key[1] == function.upper() and key[2] == interval:
            avg = row.get("avg_hold_days")
            if avg is not None:
                try:
                    return int(avg)
                except (TypeError, ValueError):
                    return None
    return None


def get_signal_entries(book_id: str) -> dict[str, Any]:
    book_svc.validate_book_access(book_id)
    payload = reports_service.load_report_records("new-signals", enrich=True)
    records = payload.get("records", [])
    ranked = sorted(
        records,
        key=lambda r: (_score(r) is not None, _score(r) or -1e9),
        reverse=True,
    )
    entries: list[dict[str, Any]] = []
    for rank, row in enumerate(ranked, start=1):
        meta = _parse_signal_meta(row)
        sc = _score(row)
        entries.append({
            "id": f"entry-{_slug(meta['symbol'])}-{_slug(meta['function'])}-{_slug(meta['interval'])}-{meta['signal_date']}",
            "ticker": meta["symbol"],
            "function": meta["function"],
            "interval": meta["interval"],
            "direction": meta["direction"],
            "signal_date": meta["signal_date"],
            "score": sc,
            "rank": rank,
            "forward_win_rate_pct": _fwd_wr(row),
            "detail": "Eligible for model admission",
        })
    return {
        "book_id": book_id,
        "as_of": _as_of_iso(payload.get("report_date")),
        "entries": entries,
    }


def _classify_exit_type(row: dict[str, Any]) -> str:
    exit_field = str(row.get("Exit Signal Date/Price[$]") or "")
    if row.get("exit_fired") or (
        exit_field and exit_field.strip().lower() not in ("", "no exit yet")
    ):
        return "signal"
    rr = _rr_dynamic(row)
    if rr is not None and rr < 0:
        return "rr"
    return "signal"


def _parse_exit_price(row: dict[str, Any]) -> float | None:
    xf_price = row.get("cross_function_exit_price")
    if xf_price is not None:
        p = _safe_float(xf_price)
        if p is not None:
            return p
    exit_field = str(row.get("Exit Signal Date/Price[$]") or "")
    m = _SYM_PRICE_RE.search(exit_field)
    if m:
        return float(m.group(1))
    return None


def _closed_pnl_pct(row: dict[str, Any]) -> float | None:
    return _safe_float(row.get("mtm_pct")) or _parse_mtm_from_field(row)


def _parse_mtm_from_field(row: dict[str, Any]) -> float | None:
    raw = row.get("Current Mark to Market and Holding Period")
    if raw is None:
        return None
    m = re.search(r"([+\-]?\d+\.?\d*)\s*%", str(raw))
    return float(m.group(1)) if m else None


def get_signal_exits(book_id: str) -> dict[str, Any]:
    book_svc.validate_book_access(book_id)
    payload = reports_service.load_report_records("target-signals", enrich=True)
    records = payload.get("records", [])
    # Exit candidates: fired exits, cross-function conflicts, or negative R:R
    candidates = [
        r for r in records
        if r.get("exit_fired")
        or r.get("cross_function_exit_triggered")
        or r.get("conflict")
        or (_rr_dynamic(r) is not None and _rr_dynamic(r) < 0)
        or str(r.get("Exit Signal Date/Price[$]", "")).strip().lower() not in ("", "no exit yet")
    ]
    ranked = sorted(
        candidates,
        key=lambda r: (_score(r) is not None, _score(r) if _score(r) is not None else 1e9),
    )
    exits: list[dict[str, Any]] = []
    for rank, row in enumerate(ranked, start=1):
        meta = _parse_signal_meta(row)
        sc = _score(row)
        exits.append({
            "id": f"exit-{_slug(meta['symbol'])}-{_slug(meta['function'])}-{_slug(meta['interval'])}-{meta['signal_date']}",
            "ticker": meta["symbol"],
            "function": meta["function"],
            "interval": meta["interval"],
            "direction": meta["direction"],
            "signal_date": meta["signal_date"],
            "score": sc,
            "rank": rank,
            "forward_win_rate_pct": _fwd_wr(row),
            "detail": (
                "Cross-function exit conflict"
                if row.get("cross_function_exit_triggered")
                else "Risk/reward exit triggered"
                if _classify_exit_type(row) == "rr"
                else "Signal exit triggered"
            ),
            "exit_type": _classify_exit_type(row),
            "exit_price": _parse_exit_price(row),
            "closed_pnl_pct": _closed_pnl_pct(row),
            "conflict": bool(row.get("cross_function_exit_triggered") or row.get("conflict")),
        })
    return {
        "book_id": book_id,
        "as_of": _as_of_iso(payload.get("report_date")),
        "exits": exits,
    }


def get_portfolio_risk_report(book_id: str) -> dict[str, Any]:
    book_svc.validate_book_access(book_id)
    payload = reports_service.load_report_records("portfolio-risk", enrich=True)
    outstanding = payload.get("records", [])
    hold_index: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in outstanding:
        meta = _parse_signal_meta(row)
        key = _pos_key(meta["symbol"], meta["function"], meta["interval"], meta["direction"])
        hold_index[key] = row

    conflicts_out: list[dict[str, Any]] = []
    for conflict in payload.get("cross_function_conflicts", []):
        open_positions: list[dict[str, Any]] = []
        for op in conflict.get("open_positions", []):
            fn = str(op.get("function") or "")
            interval = str(op.get("interval") or "")
            sym = str(conflict.get("symbol") or "").upper()
            avg_hold = _lookup_hold_days(sym, fn, interval, hold_index)
            signal_date = op.get("signal_date")
            open_positions.append({
                "function": fn,
                "interval": interval,
                "mtm_pct": op.get("mtm_pct"),
                "signal_date": signal_date,
                "implied_natural_exit_date": _implied_natural_exit_date(signal_date, avg_hold),
            })
        conflicts_out.append({
            "symbol": conflict.get("symbol"),
            "direction": conflict.get("direction"),
            "asset_class": conflict.get("asset_class"),
            "conflict": bool(conflict.get("conflict", True)),
            "triggering_exits": conflict.get("triggering_exits", []),
            "open_positions": open_positions,
        })
    return {
        "book_id": book_id,
        "report_date": payload.get("report_date"),
        "cross_function_conflict_count": payload.get(
            "cross_function_conflict_count", len(conflicts_out),
        ),
        "cross_function_conflicts": conflicts_out,
    }


def get_portfolio_holdings(
    book_id: str,
    book: str,
    *,
    scenario: str = "normal",
) -> dict[str, Any]:
    validate_book_access(book_id, book=book, require_model_book=True)
    outstanding_payload = reports_service.load_report_records("outstanding-signals", enrich=True)
    new_payload = reports_service.load_report_records("new-signals", enrich=True)
    outstanding = outstanding_payload.get("records", [])
    new_rows = new_payload.get("records", [])

    sizer = portfolio_svc.get_portfolio_sizer(scenario=scenario)
    alloc_index = _build_allocation_index(sizer)

    sibling_by_symbol, held_keys, new_keys = _build_sibling_index(outstanding, new_rows)

    scored = sorted(
        outstanding,
        key=lambda r: (_score(r) is not None, _score(r) or -1e9),
        reverse=True,
    )

    holdings: list[dict[str, Any]] = []
    for rank, row in enumerate(scored, start=1):
        meta = _parse_signal_meta(row)
        key = _pos_key(meta["symbol"], meta["function"], meta["interval"], meta["direction"])
        alloc = alloc_index.get(key, {})
        sym = meta["symbol"]
        siblings_raw = sibling_by_symbol.get(sym, [])
        size_usd = alloc.get("allocation_usd") or 0
        shares = alloc.get("shares")
        market_value = alloc.get("market_value_usd")
        pnl_usd = alloc.get("pnl_usd")
        entry_price = alloc.get("entry_price") or meta["entry_price"]
        current_price = alloc.get("today_price") or entry_price
        mtm_pct = alloc.get("pnl_pct") or _parse_mtm_from_field(row)

        holdings.append({
            "id": f"{book_id}-{_slug(sym)}-{_slug(meta['function'])}-{_slug(meta['interval'])}",
            "ticker": sym,
            "name": alloc.get("name") or sym,
            "function": meta["function"],
            "interval": meta["interval"],
            "direction": meta["direction"],
            "entry_date": meta["signal_date"],
            "entry_price": entry_price,
            "current_price": current_price,
            "entry_currency": "USD",
            "shares": shares,
            "market_value": market_value,
            "pnl_usd": pnl_usd,
            "mtm_pct": mtm_pct,
            "score": _score(row),
            "rank": rank,
            "rr_dynamic": _rr_dynamic(row),
            "hold_time_used_pct": _hold_time_used_pct(row),
            "size_usd": size_usd,
            "conviction_tier": _conviction_tier_from_size_tier(alloc.get("size_tier")),
            "sleeve": alloc.get("sleeve") or alloc.get("investment_type"),
            "pnl_contribution_bps": None,
            "same_asset_siblings": _same_asset_siblings(
                row, siblings_raw, held_keys=held_keys, new_keys=new_keys,
            ),
            "multi_sig": _multi_sig(row, siblings_raw),
            "exit_ref": _build_exit_ref(row),
            "cross_function_exit": bool(row.get("cross_function_exit_triggered")),
            "asset_class": str(row.get("asset_class") or row.get("Asset Class") or "Equity").title(),
            "status": "Open",
            "backtested_win_rate_pct": _safe_float(row.get("backtested_win_rate_pct") or row.get("win_rate")),
            "next_out": False,
        })

    return {
        "book_id": book_id,
        "book": book,
        "as_of": _as_of_iso(outstanding_payload.get("report_date")),
        "holdings": holdings,
    }


def _contrib_row(holding: dict[str, Any], nav: float) -> dict[str, Any]:
    pnl = holding.get("pnl_usd") or 0
    bps = round(float(pnl) / nav * 10000, 1) if nav else None
    return {
        "ticker": holding.get("ticker"),
        "function": holding.get("function"),
        "interval": holding.get("interval"),
        "pnl_contribution_bps": bps,
    }


def _risk_chips_from_breaches(breaches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chips: list[dict[str, Any]] = []
    for idx, breach in enumerate(breaches[:5]):
        labels = breach.get("pair_labels") or breach.get("pair") or []
        pair_text = " / ".join(str(x) for x in labels) if labels else "cluster pair"
        level = str(breach.get("level") or "watch")
        chips.append({
            "id": f"correlation-breach-{idx}",
            "icon": "⚠",
            "title": f"Correlation breach ({level})",
            "body": breach.get("recommendation")
            or f"{pair_text} ρ={breach.get('rho')}",
            "target_view": "risk",
            "action_label": "VIEW RISK",
        })
    return chips


def get_portfolio_nav(
    book_id: str,
    book: str,
    *,
    scenario: str = "normal",
) -> dict[str, Any]:
    """Overview NAV payload (HANDOFF §3) — MODEL enhanced book from sizer + holdings pipeline."""
    validate_book_access(book_id, book=book, require_model_book=True)

    sizer = portfolio_svc.get_portfolio_sizer(scenario=scenario)
    holdings_payload = get_portfolio_holdings(book_id, book, scenario=scenario)
    entries_payload = get_signal_entries(book_id)
    exits_payload = get_signal_exits(book_id)
    risk_payload = portfolio_svc.get_portfolio_risk(scenario=scenario)

    summary = sizer.get("summary") or {}
    ceiling = sizer.get("ceiling") or {}
    notional = float(ceiling.get("portfolio_notional") or portfolio_svc.PORTFOLIO_NOTIONAL)
    nav = notional
    pnl_rows = sizer.get("pnl_rows") or []

    day_mtm_usd = round(sum(float(r.get("pnl_usd") or 0) for r in pnl_rows), 2)
    day_mtm_pct = round(day_mtm_usd / nav * 100, 2) if nav else None

    long_rows = [r for r in pnl_rows if str(r.get("direction") or "Long").lower() == "long"]
    short_rows = [r for r in pnl_rows if str(r.get("direction") or "").lower() == "short"]
    long_mv = sum(float(r.get("market_value_usd") or 0) for r in long_rows)
    short_mv = sum(float(r.get("market_value_usd") or 0) for r in short_rows)
    gross_exposure_pct = round((long_mv + short_mv) / nav * 100, 1) if nav else None
    net_exposure_pct = round((long_mv - short_mv) / nav * 100, 1) if nav else None

    as_of = holdings_payload.get("as_of") or _as_of_iso(sizer.get("date"))
    series_date = str(sizer.get("date") or (as_of or "")[:10])

    holdings = holdings_payload.get("holdings") or []
    ranked_pnl = sorted(
        [h for h in holdings if h.get("pnl_usd") is not None],
        key=lambda h: float(h.get("pnl_usd") or 0),
        reverse=True,
    )
    top_contributors = [
        _contrib_row(h, nav) for h in ranked_pnl[:5] if float(h.get("pnl_usd") or 0) > 0
    ]
    top_detractors = [
        _contrib_row(h, nav) for h in sorted(ranked_pnl, key=lambda h: float(h.get("pnl_usd") or 0))[:5]
        if float(h.get("pnl_usd") or 0) < 0
    ]

    waterfall_steps: list[dict[str, Any]] = []
    for step in ceiling.get("steps") or []:
        waterfall_steps.append({
            "label": step.get("label"),
            "value": step.get("value"),
            "tone": step.get("tone", "default"),
            "final": bool(step.get("final")),
        })
    final_ceiling = ceiling.get("final_ceiling_pct")
    if final_ceiling is not None and not any(s.get("final") for s in waterfall_steps):
        waterfall_steps.append({
            "label": "Final ceiling",
            "value": f"{final_ceiling}%",
            "tone": "gold",
            "final": True,
        })

    macro = sizer.get("macro_override") or {}
    stance_detail = None
    if macro.get("active") and macro.get("reasons"):
        stance_detail = "; ".join(str(r) for r in macro["reasons"][:2])
    elif sizer.get("constraints"):
        stance_detail = str(sizer["constraints"][0].get("body") or "")

    next_in = None
    if entries_payload.get("entries"):
        e = entries_payload["entries"][0]
        next_in = {
            "ticker": e.get("ticker"),
            "function": e.get("function"),
            "interval": e.get("interval"),
            "direction": e.get("direction"),
            "signal_or_entry_date": e.get("signal_date"),
            "score": e.get("score"),
            "forward_win_rate_pct": e.get("forward_win_rate_pct"),
            "er_alpha_pct": None,
            "rr_dynamic": None,
            "hold_time_used_pct": 0,
            "detail": e.get("detail"),
        }

    next_out = None
    if exits_payload.get("exits"):
        x = exits_payload["exits"][0]
        next_out = {
            "ticker": x.get("ticker"),
            "function": x.get("function"),
            "interval": x.get("interval"),
            "direction": x.get("direction"),
            "signal_or_entry_date": x.get("signal_date"),
            "score": x.get("score"),
            "forward_win_rate_pct": x.get("forward_win_rate_pct"),
            "exit_type": x.get("exit_type"),
            "detail": x.get("detail"),
        }

    eviction_margin = None
    eviction_note = "Challenger score minus weakest holding score"
    entry_scores = [e.get("score") for e in entries_payload.get("entries", []) if e.get("score") is not None]
    hold_scores = [h.get("score") for h in holdings if h.get("score") is not None]
    if entry_scores and hold_scores:
        eviction_margin = round(float(max(entry_scores)) - float(min(hold_scores)), 1)

    return {
        "book_id": book_id,
        "book": book,
        "as_of": as_of,
        "currency": "USD",
        "nav": nav,
        "day_mtm_usd": day_mtm_usd if day_mtm_usd else None,
        "day_mtm_pct": day_mtm_pct,
        "since_go_live_pct": None,
        "position_count": len(holdings),
        "position_limit": None,
        "deployed_pct": summary.get("deployed_pct"),
        "cash_pct": summary.get("cash_pct"),
        "long_count": len(long_rows),
        "short_count": len(short_rows),
        "net_exposure_pct": net_exposure_pct,
        "gross_exposure_pct": gross_exposure_pct,
        "realized_vol_pct": None,
        "beta_sp500": None,
        "best_month_pct": None,
        "worst_month_pct": None,
        "mtm": [{
            "date": series_date,
            "value": nav,
            "drawdown_pct": 0.0,
            "high_water_mark": nav,
        }],
        "closed": [],
        "base_mtm": [],
        "base_closed": [],
        "benchmark": [],
        "monthly_returns": [],
        "attribution": [],
        "waterfall_steps": waterfall_steps,
        "ceiling_marker_pct": final_ceiling,
        "stance": {
            "label": "CAUTIOUSLY DEPLOYED" if macro.get("active") else "DEPLOYED",
            "detail": stance_detail,
        },
        "conviction_summary": portfolio_svc.build_conviction_summary(sizer),
        "risk_chips": _risk_chips_from_breaches(risk_payload.get("breaches") or []),
        "top_contributors": top_contributors,
        "top_detractors": top_detractors,
        "next_in": next_in,
        "next_out": next_out,
        "eviction_margin": eviction_margin,
        "eviction_margin_note": eviction_note,
        "nav_history_note": (
            "Daily NAV history and benchmark attribution require Ahil A1 four-book replay; "
            "mtm currently exposes a single as-of snapshot."
        ),
    }
