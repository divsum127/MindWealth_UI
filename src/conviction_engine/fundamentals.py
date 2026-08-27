"""Fundamentals fetch/update helpers for daily Conviction Engine maintenance."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import pandas as pd

from ..config_paths import CONVICTION_UNIVERSE_FILE, TRADE_STORE_US_DIR
from .dividend_yield import compute_dividend_yield_stats
from .engine import daily_update, full_recalculation
from .scoring import BusinessType, detect_business_type, is_coverage_incomplete
from .signals import discover_signal_sources, load_signal_file, normalize_signal_dataframe
from .store import list_records, load_record, sanitize_ticker

FundamentalsPayload = dict[str, dict[str, Any]]
FundamentalsFetcher = Callable[[str], FundamentalsPayload]


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_dict(value: Any) -> dict[str, Any]:
    if not value:
        return {}
    try:
        return dict(value)
    except Exception:
        return {}


def _first_not_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _series_value(series: pd.Series, key: str) -> Any:
    if key not in series.index:
        return None
    value = series.get(key)
    if pd.isna(value):
        return None
    return value


def map_yfinance_fundamentals(
    info: dict[str, Any],
    fast_info: dict[str, Any] | None = None,
    dividend_stats: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Map yfinance fields into the engine's fundamentals schema."""
    fast_info = fast_info or {}
    dividend_stats = dividend_stats or {}

    price = _safe_float(
        _first_not_none(
            fast_info.get("last_price"),
            fast_info.get("lastPrice"),
            info.get("currentPrice"),
            info.get("regularMarketPrice"),
            info.get("previousClose"),
        )
    )
    market_cap = _safe_float(_first_not_none(fast_info.get("market_cap"), fast_info.get("marketCap"), info.get("marketCap")))
    total_revenue = _safe_float(info.get("totalRevenue"))
    fcf = _safe_float(_first_not_none(info.get("freeCashflow"), info.get("freeCashFlow")))
    if fcf is None:
        operating_cf = _safe_float(info.get("operatingCashflow"))
        capex = _safe_float(info.get("capitalExpenditures"))
        if operating_cf is not None and capex is not None:
            fcf = operating_cf + capex

    total_debt = _safe_float(info.get("totalDebt"))
    total_cash = _safe_float(info.get("totalCash"))
    net_debt = None
    if total_debt is not None or total_cash is not None:
        net_debt = (total_debt or 0.0) - (total_cash or 0.0)

    ebitda = _safe_float(info.get("ebitda"))
    net_debt_ebitda = None
    if net_debt is not None and ebitda and ebitda > 0:
        net_debt_ebitda = round(net_debt / ebitda, 4)

    # Dividend basis (Rohit 26 Aug, conviction spec gap 4). `dividendRate` is the
    # forward annual rate implied by the latest declaration; `trailingAnnualDividendRate`
    # is what was actually paid over the last twelve months. They diverge exactly when a
    # cut or a raise has been announced -- the SPK.NZ case -- which is when the yield-trap
    # answer flips. Keep both, and record which one `annual_div_per_share_stored` used.
    dividend_rate_forward = _safe_float(info.get("dividendRate"))
    dividend_rate_trailing = _safe_float(info.get("trailingAnnualDividendRate"))
    dividend_rate = _first_not_none(dividend_rate_forward, dividend_rate_trailing)
    shares = _safe_float(info.get("sharesOutstanding"))
    distribution_coverage = None
    if fcf is not None and dividend_rate is not None and shares and shares > 0:
        annual_obligation = dividend_rate * shares
        if annual_obligation > 0:
            distribution_coverage = round(fcf / annual_obligation, 4)

    mapped = {
        "quote_type": info.get("quoteType"),
        "price": price,
        "market_cap": market_cap,
        "eps_ttm": _safe_float(info.get("trailingEps")),
        "eps_fwd": _safe_float(info.get("forwardEps")),
        "fcf_ttm": fcf,
        "net_debt_stored": net_debt,
        "fwd_revenue_stored": _safe_float(_first_not_none(info.get("revenueEstimate"), info.get("totalRevenue"))),
        "annual_div_per_share_stored": dividend_rate,
        "annual_div_per_share_forward": dividend_rate_forward,
        "annual_div_per_share_trailing": dividend_rate_trailing,
        "dividend_basis": (
            "forward_declared" if dividend_rate_forward is not None
            else ("trailing_12m" if dividend_rate_trailing is not None else None)
        ),
        "revenue_growth": _safe_float(info.get("revenueGrowth")),
        "fcf_margin": round(fcf / total_revenue, 6) if fcf is not None and total_revenue and total_revenue > 0 else None,
        "gross_margin": _safe_float(info.get("grossMargins")),
        "net_debt_ebitda": net_debt_ebitda,
        "distribution_coverage_ratio": distribution_coverage,
        **dividend_stats,
    }
    return {key: value for key, value in mapped.items() if value is not None}


def fetch_yfinance_fundamentals(ticker: str) -> FundamentalsPayload:
    """Fetch yfinance fundamentals via enriched statement pipeline."""
    from .fundamentals_enriched import fetch_and_compute_fundamentals

    payload = fetch_and_compute_fundamentals(ticker)
    fundamentals = dict(payload.get("fundamentals", {}))
    fetch_errors = fundamentals.pop("fetch_errors", [])
    return {
        "info": payload.get("info", {}),
        "fundamentals": fundamentals,
        "fetch_errors": fetch_errors,
        "raw_fetch": payload.get("raw", {}),
    }


def discover_universe(
    trade_store_dir: Path | None = None,
    universe_file: Path | None = None,
    extra_tickers: list[str] | None = None,
    include_existing_records: bool = False,
    include_signal_sources: bool = True,
) -> list[str]:
    """Discover tickers from latest signal files, optional universe file, and explicit inputs."""
    tickers: set[str] = set()
    base_dir = trade_store_dir or TRADE_STORE_US_DIR

    if include_signal_sources:
        for source_path in discover_signal_sources(base_dir).values():
            df = load_signal_file(source_path)
            for signal in normalize_signal_dataframe(df, source_file=source_path):
                if signal.symbol:
                    tickers.add(sanitize_ticker(signal.symbol))

    file_path = universe_file if universe_file is not None else CONVICTION_UNIVERSE_FILE
    if file_path and Path(file_path).exists():
        with open(file_path, "r", encoding="utf-8") as fh:
            for line in fh:
                symbol = line.strip()
                if symbol and not symbol.startswith("#"):
                    tickers.add(sanitize_ticker(symbol))

    for symbol in extra_tickers or []:
        if symbol:
            tickers.add(sanitize_ticker(symbol))

    if include_existing_records:
        for record in list_records():
            if record.get("ticker"):
                tickers.add(sanitize_ticker(str(record["ticker"])))

    return sorted(tickers)


def update_ticker_fundamentals(
    ticker: str,
    mode: str = "auto",
    fetcher: FundamentalsFetcher = fetch_yfinance_fundamentals,
    store_dir: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Fetch fundamentals for one ticker and update the conviction JSON store."""
    symbol = sanitize_ticker(ticker)
    existing = load_record(symbol, store_dir)

    selected_mode = mode
    if mode == "auto":
        selected_mode = "full" if existing is None else "daily"

    if dry_run:
        return {
            "ticker": symbol,
            "status": "dry_run",
            "mode": selected_mode,
            "quote_type": (existing or {}).get("quote_type") or (existing or {}).get("asset_type"),
            "fields": sorted((existing or {}).keys()),
        }

    payload = fetcher(symbol)
    info = payload.get("info", {})
    raw_fetch = payload.get("raw_fetch") or {}
    fundamentals = dict(payload.get("fundamentals", {}))
    fetch_errors = list(payload.get("fetch_errors") or fundamentals.pop("fetch_errors", None) or [])
    if fetch_errors:
        fundamentals["fetch_errors"] = fetch_errors

    if selected_mode == "full":
        record = full_recalculation(
            symbol,
            trigger="daily_fundamentals_script",
            fundamentals=fundamentals,
            info=info,
            raw_fetch=raw_fetch,
            store_dir=store_dir,
        )
    elif selected_mode == "daily":
        record = existing or full_recalculation(
            symbol,
            trigger="daily_fundamentals_script",
            fundamentals=fundamentals,
            info=info,
            raw_fetch=raw_fetch,
            store_dir=store_dir,
        )
        market = {**fundamentals, "_raw_fetch": raw_fetch}
        record = daily_update(symbol, record=record, market_data=market, info=info, store_dir=store_dir, save=True)
    else:
        raise ValueError("mode must be one of: auto, daily, full")

    return {
        "ticker": symbol,
        "status": "updated",
        "mode": selected_mode,
        "asset_type": record.get("asset_type"),
        "business_type": record.get("business_type"),
        "bq_raw": record.get("bq_raw"),
        "valuation_tax": record.get("valuation_tax"),
        "conviction_score": record.get("conviction_score"),
        "fs_class": record.get("fs_class"),
        "yield_trap_warning": record.get("yield_trap_warning"),
        "not_applicable_reason": record.get("not_applicable_reason"),
        "fetch_errors": fetch_errors,
    }


def update_universe_fundamentals(
    tickers: list[str],
    mode: str = "auto",
    fetcher: FundamentalsFetcher = fetch_yfinance_fundamentals,
    store_dir: Path | None = None,
    dry_run: bool = False,
    fail_fast: bool = False,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for ticker in tickers:
        try:
            results.append(update_ticker_fundamentals(ticker, mode=mode, fetcher=fetcher, store_dir=store_dir, dry_run=dry_run))
        except Exception as exc:
            if fail_fast:
                raise
            results.append({"ticker": sanitize_ticker(ticker), "status": "error", "error": str(exc)})
    return results


# --- Item 12: cheap classification-only universe rollout ---------------------------
#
# Rohit's Q11 answer replaces the earlier "just run full_recalculation on everyone"
# plan with a two-step approach: (1) a lightweight `.info`-only classification pass
# across the whole ~193-ticker universe (same cost profile as the existing daily
# runner — one yfinance `.info` call per ticker, no quarterly statements/price
# history pull), (2) diff against each ticker's currently-stored `business_type` and
# only queue tickers that actually *flip* into one of the 3 new/changed buckets this
# v2 pass introduces (`bank`, `high_margin_hardware`, `coverage_incomplete`) for a
# full `full_recalculation()`. Everything that classifies the same stays on its
# normal schedule — same migration discipline already used for the PE-history
# rollout (`scripts/report_pe_history_coverage.py` / `set_manual_pe_history.py`).

FLIP_WORTH_RECALCULATING = frozenset(
    {BusinessType.BANK.value, BusinessType.HIGH_MARGIN_HARDWARE.value, "coverage_incomplete"}
)


def fetch_classification_info(ticker: str, max_attempts: int = 2) -> dict[str, Any]:
    """Fetch only ``yfinance`` ``.info`` for a ticker — no statements, no price history.

    Deliberately the cheapest possible call: this is the entire point of the
    classification-only pass (item 12) versus a full `fetch_and_compute_fundamentals()`.
    """
    import time as _time

    import yfinance as yf

    symbol = sanitize_ticker(ticker)
    last_exc: str | None = None
    for attempt in range(max_attempts):
        try:
            info = _safe_dict(getattr(yf.Ticker(symbol), "info", {}) or {})
            if info:
                return info
        except Exception as exc:
            last_exc = str(exc)
        _time.sleep(0.4 * (attempt + 1))
    if last_exc:
        return {"_fetch_error": last_exc}
    return {}


def classify_universe_diff(
    tickers: list[str] | None = None,
    store_dir: Path | None = None,
    fetch_info: Callable[[str], dict[str, Any]] = fetch_classification_info,
) -> dict[str, Any]:
    """Classification-only diff pass (item 12, step 1+2): returns per-ticker
    old-vs-new `business_type` plus the subset that actually needs a full
    `full_recalculation()` (flips into bank/high_margin_hardware/coverage_incomplete).

    Never fetches financial statements or writes to the store — purely a cheap read
    + diff so it's safe to run against the whole universe on a schedule without the
    cost of a full daily/quarterly fundamentals pull.
    """
    tickers = tickers if tickers is not None else [r.get("ticker") for r in list_records(store_dir) if r.get("ticker")]
    results: list[dict[str, Any]] = []
    flipped: list[str] = []
    for raw_ticker in tickers:
        if not raw_ticker:
            continue
        symbol = sanitize_ticker(str(raw_ticker))
        existing = load_record(symbol, store_dir) or {}
        old_business_type = str(existing.get("business_type") or BusinessType.UNKNOWN.value)

        info = fetch_info(symbol)
        if info.get("_fetch_error"):
            results.append({"ticker": symbol, "status": "error", "error": info["_fetch_error"], "old_business_type": old_business_type})
            continue

        new_business_type, source = detect_business_type(info, existing.get("manual_overrides"))
        new_coverage_incomplete = is_coverage_incomplete(new_business_type)
        old_coverage_incomplete = is_coverage_incomplete(old_business_type)
        # "Flip" (per Rohit's Q11 answer) means landing in one of the 3 buckets this
        # v2 pass newly calibrates/introduces, having not been there before — not
        # every reclassification (e.g. compounder<->cyclical) warrants a full recalc.
        new_bucket = "coverage_incomplete" if new_coverage_incomplete else new_business_type
        old_bucket = "coverage_incomplete" if old_coverage_incomplete else old_business_type
        needs_recalc = new_bucket != old_bucket and new_bucket in FLIP_WORTH_RECALCULATING

        results.append(
            {
                "ticker": symbol,
                "status": "classified",
                "old_business_type": old_business_type,
                "new_business_type": new_business_type,
                "business_type_source": source,
                "coverage_incomplete": new_coverage_incomplete,
                "flipped": new_bucket != old_bucket,
                "needs_full_recalculation": needs_recalc,
            }
        )
        if needs_recalc:
            flipped.append(symbol)

    return {
        "universe_size": len(results),
        "flipped_tickers": flipped,
        "flipped_count": len(flipped),
        "results": results,
    }


def run_universe_classification_pass(
    tickers: list[str] | None = None,
    store_dir: Path | None = None,
    fetch_info: Callable[[str], dict[str, Any]] = fetch_classification_info,
    auto_recalculate: bool = True,
    fetcher: FundamentalsFetcher = fetch_yfinance_fundamentals,
    fail_fast: bool = False,
) -> dict[str, Any]:
    """Run `classify_universe_diff()` and, by default, immediately queue the flipped
    subset for a full `full_recalculation()` via the normal `mode="full"` path — the
    expensive step only ever runs on the (expected-to-be-small) flipped subset, never
    the whole universe."""
    diff = classify_universe_diff(tickers, store_dir=store_dir, fetch_info=fetch_info)
    diff["auto_recalculated"] = False
    diff["recalculation_results"] = []
    if auto_recalculate and diff["flipped_tickers"]:
        diff["recalculation_results"] = update_universe_fundamentals(
            diff["flipped_tickers"],
            mode="full",
            fetcher=fetcher,
            store_dir=store_dir,
            fail_fast=fail_fast,
        )
        diff["auto_recalculated"] = True
    return diff
