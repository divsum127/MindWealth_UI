"""Fundamentals fetch/update helpers for daily Conviction Engine maintenance."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import pandas as pd

from ..config_paths import CONVICTION_UNIVERSE_FILE, TRADE_STORE_US_DIR
from .engine import daily_update, full_recalculation
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


def compute_dividend_yield_stats(history: pd.DataFrame | None, dividends: pd.Series | None) -> dict[str, float]:
    """Compute 5Y dividend-yield mean/std from daily close and dividend series."""
    if history is None or dividends is None or history.empty or dividends.empty or "Close" not in history.columns:
        return {}

    close = history["Close"].dropna()
    if close.empty:
        return {}

    dividends = dividends.dropna()
    if dividends.empty:
        return {}

    if close.index.tz is not None:
        close.index = close.index.tz_localize(None)
    if dividends.index.tz is not None:
        dividends.index = dividends.index.tz_localize(None)

    daily_dividends = dividends.reindex(close.index, fill_value=0.0)
    annual_dividends = daily_dividends.rolling(window=365, min_periods=1).sum()
    dividend_yield = (annual_dividends / close).replace([float("inf"), float("-inf")], pd.NA).dropna()
    dividend_yield = dividend_yield[dividend_yield > 0]
    if len(dividend_yield) < 20:
        return {}

    return {
        "dividend_yield_5y_mean": round(float(dividend_yield.mean()), 6),
        "dividend_yield_5y_std": round(float(dividend_yield.std(ddof=0)), 6),
    }


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

    dividend_rate = _safe_float(_first_not_none(info.get("dividendRate"), info.get("trailingAnnualDividendRate")))
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
    payload = fetcher(symbol)
    info = payload.get("info", {})
    raw_fetch = payload.get("raw_fetch") or {}
    fundamentals = dict(payload.get("fundamentals", {}))
    fetch_errors = list(payload.get("fetch_errors") or fundamentals.pop("fetch_errors", None) or [])
    if fetch_errors:
        fundamentals["fetch_errors"] = fetch_errors
    existing = load_record(symbol, store_dir)

    selected_mode = mode
    if mode == "auto":
        selected_mode = "full" if existing is None else "daily"

    if dry_run:
        return {
            "ticker": symbol,
            "status": "dry_run",
            "mode": selected_mode,
            "quote_type": info.get("quoteType") or fundamentals.get("quote_type"),
            "fields": sorted(fundamentals.keys()),
        }

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
