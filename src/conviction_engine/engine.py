"""Public Conviction Engine API."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from ..utils.atomic_io import write_dataframe_csv_atomic_guarded
from .models import PositionLayers, QuantSignal, SignalModification, default_record, utc_now_iso
from .fundamentals_enriched import compute_bq_components_auto, compute_fd_direction
from .scoring import (
    apply_fs_cap,
    calculate_bq_raw,
    calculate_fs_score,
    calculate_valuation_tax,
    classify_fs,
    compute_bq_components,
    detect_business_type,
    is_equity_asset,
    is_yield_trap,
    verdict_for_buy,
    verdict_for_sell,
)
from .signals import load_signal_file, normalize_signal_dataframe, normalize_signal_row
from .store import load_or_create_record, load_record, overlay_path, save_record, sanitize_ticker


def _try_yfinance_ticker(ticker: str) -> Any | None:
    try:
        import yfinance as yf  # type: ignore

        return yf.Ticker(ticker)
    except Exception:
        return None


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _percentile_rank(values: list[float], current: float | None) -> float | None:
    if current is None or not values:
        return None
    clean = [float(value) for value in values if value is not None]
    if not clean:
        return None
    count = sum(1 for value in clean if value <= current)
    return round((count / len(clean)) * 100, 2)


def _copy_known_fields(record: dict[str, Any], values: dict[str, Any]) -> None:
    for key, value in values.items():
        if value is not None:
            record[key] = value


def _first_not_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def full_recalculation(
    ticker: str,
    overrides: dict[str, Any] | None = None,
    trigger: str = "manual",
    fundamentals: dict[str, Any] | None = None,
    info: dict[str, Any] | None = None,
    store_dir: Path | None = None,
) -> dict[str, Any]:
    """Create or refresh the static fundamentals record for a ticker."""
    symbol = sanitize_ticker(ticker)
    overrides = overrides or {}
    fundamentals = fundamentals or {}
    info = info or {}

    if not info:
        yf_ticker = _try_yfinance_ticker(ticker)
        if yf_ticker is not None:
            try:
                info = dict(yf_ticker.info or {})
            except Exception:
                info = {}

    existing = load_record(symbol, store_dir) or default_record(symbol)
    record = {**existing, "ticker": symbol}
    record["manual_overrides"] = {**record.get("manual_overrides", {}), **overrides}
    record["quote_type"] = info.get("quoteType") or fundamentals.get("quote_type") or record.get("quote_type")
    quote_type = str(record.get("quote_type") or "").upper()
    record["asset_type"] = quote_type if quote_type else record.get("asset_type", "UNKNOWN")

    business_type, source = detect_business_type(info, record.get("manual_overrides"))
    record["business_type"] = business_type
    record["business_type_source"] = source

    bq_inputs = {**fundamentals, "roic": fundamentals.get("roic_proxy")}
    bq_components = compute_bq_components_auto(bq_inputs, business_type, record.get("manual_overrides"))
    if not any(bq_components.values()):
        bq_components = compute_bq_components(fundamentals, record.get("manual_overrides"))
    record["bq_components"] = bq_components
    record["bq_raw"] = float(overrides.get("bq_raw", calculate_bq_raw(bq_components)))
    record["fs_quality_base"] = round(50 + (record["bq_raw"] * 2.5), 2)

    fd_direction = compute_fd_direction(
        _safe_float(fundamentals.get("revenue_growth")),
        None,
        _safe_float(fundamentals.get("gross_margin_trend")),
    )
    record["fd_direction"] = overrides.get("fd_direction", fd_direction)

    _copy_known_fields(
        record,
        {
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "roic_5y_avg": _first_not_none(fundamentals.get("roic_proxy"), fundamentals.get("roic_5y_avg"), overrides.get("roic_5y_avg")),
            "pe_20y_array": _first_not_none(fundamentals.get("pe_20y_array"), overrides.get("pe_20y_array")),
            "eps_ttm": _first_not_none(fundamentals.get("eps_ttm"), info.get("trailingEps"), overrides.get("eps_ttm")),
            "eps_fwd": _first_not_none(fundamentals.get("eps_fwd"), info.get("forwardEps"), overrides.get("eps_fwd")),
            "fcf_ttm": _first_not_none(fundamentals.get("fcf_ttm"), overrides.get("fcf_ttm")),
            "net_debt_stored": _first_not_none(fundamentals.get("net_debt_stored"), overrides.get("net_debt_stored")),
            "fwd_revenue_stored": _first_not_none(fundamentals.get("fwd_revenue_stored"), overrides.get("fwd_revenue_stored")),
            "annual_div_per_share_stored": _first_not_none(
                fundamentals.get("annual_div_per_share_stored"), overrides.get("annual_div_per_share_stored")
            ),
            "fd_votes": overrides.get("fd_votes"),
            "fd_direction": overrides.get("fd_direction", record.get("fd_direction")),
            "dividend_yield_5y_mean": _first_not_none(
                fundamentals.get("dividend_yield_5y_mean"), overrides.get("dividend_yield_5y_mean")
            ),
            "dividend_yield_5y_std": _first_not_none(
                fundamentals.get("dividend_yield_5y_std"), overrides.get("dividend_yield_5y_std")
            ),
        },
    )

    if fundamentals.get("fetch_errors") is not None:
        record["fetch_errors"] = fundamentals.get("fetch_errors")
    record["last_full_calc"] = utc_now_iso()
    record["full_recalc_trigger"] = trigger
    record = daily_update(symbol, record=record, market_data={**info, **fundamentals, **overrides}, store_dir=store_dir, save=False)
    save_record(record, store_dir)
    return record


def daily_update(
    ticker: str,
    record: dict[str, Any] | None = None,
    force: bool = False,
    market_data: dict[str, Any] | None = None,
    store_dir: Path | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """Refresh price-sensitive valuation and FS fields."""
    symbol = sanitize_ticker(ticker)
    record = record or load_or_create_record(symbol, store_dir)
    market_data = market_data or {}

    if not market_data and force:
        yf_ticker = _try_yfinance_ticker(ticker)
        if yf_ticker is not None:
            try:
                fast_info = getattr(yf_ticker, "fast_info", {}) or {}
                market_data = {
                    "price": fast_info.get("last_price") or fast_info.get("lastPrice"),
                    "market_cap": fast_info.get("market_cap") or fast_info.get("marketCap"),
                }
            except Exception:
                market_data = {}

    price = _safe_float(market_data.get("price") or market_data.get("currentPrice") or market_data.get("regularMarketPrice"))
    market_cap = _safe_float(market_data.get("market_cap") or market_data.get("marketCap"))
    if price is not None:
        record["price"] = price
    if market_cap is not None:
        record["market_cap"] = market_cap

    equity, asset_type, reason = is_equity_asset(record, symbol)
    record["asset_type"] = asset_type
    if not equity:
        record["business_type"] = "unknown"
        record["business_type_source"] = record.get("business_type_source", "auto")
        record["valuation_tax"] = None
        record["conviction_score"] = None
        record["fs_score"] = None
        record["fs_class"] = None
        record["yield_trap_warning"] = False
        record["not_applicable_reason"] = reason or "Conviction Engine applies only to individual equities"
        record["last_daily_update"] = utc_now_iso()
        if save:
            save_record(record, store_dir)
        return record

    eps_ttm = _safe_float(record.get("eps_ttm"))
    stored_price = _safe_float(record.get("price"))
    if stored_price is not None and eps_ttm and eps_ttm > 0:
        record["pe_ttm"] = round(stored_price / eps_ttm, 4)

    pe_history = record.get("pe_20y_array") or []
    if isinstance(pe_history, list):
        record["pe_percentile_20y"] = _percentile_rank(pe_history, _safe_float(record.get("pe_ttm")))

    mcap = _safe_float(record.get("market_cap"))
    net_debt = _safe_float(record.get("net_debt_stored")) or 0.0
    fwd_revenue = _safe_float(record.get("fwd_revenue_stored"))
    if mcap is not None:
        record["enterprise_value"] = mcap + net_debt
        fcf = _safe_float(record.get("fcf_ttm"))
        if fcf is not None and mcap > 0:
            record["owner_earnings_yield"] = round(fcf / mcap, 6)
    if mcap is not None and fwd_revenue and fwd_revenue > 0:
        record["ev_fwd_rev"] = round((mcap + net_debt) / fwd_revenue, 4)

    annual_div = _safe_float(record.get("annual_div_per_share_stored"))
    if annual_div is not None and stored_price and stored_price > 0:
        record["dividend_yield_current"] = round(annual_div / stored_price, 6)
        mean = _safe_float(record.get("dividend_yield_5y_mean"))
        std = _safe_float(record.get("dividend_yield_5y_std"))
        if mean is not None and std and std > 0:
            record["dividend_yield_zscore"] = round((record["dividend_yield_current"] - mean) / std, 4)

    record["valuation_tax"] = calculate_valuation_tax(record)
    record["conviction_score"] = round((_safe_float(record.get("bq_raw")) or 0.0) + record["valuation_tax"], 2)
    record["fs_score"] = calculate_fs_score(record)
    record["fs_class"] = classify_fs(record["fs_score"])
    record["yield_trap_warning"] = is_yield_trap(record, symbol)
    record["last_daily_update"] = utc_now_iso()

    if save:
        save_record(record, store_dir)
    return record


def modify_signal(
    ticker: str,
    technical_signal: str,
    signal_timeframe: str,
    signal_strength: float = 0.75,
    quant_model_name: str | None = None,
    long_position_near_stop: bool = False,
    signal_date: str | None = None,
    record: dict[str, Any] | None = None,
    store_dir: Path | None = None,
    persist: bool = True,
    update_layers: bool = True,
) -> SignalModification:
    symbol = sanitize_ticker(ticker)
    if record is None:
        record = load_record(symbol, store_dir)
    if record is None:
        placeholder = default_record(symbol)
        equity, asset_type, reason = is_equity_asset(placeholder, symbol)
        layers = PositionLayers()
        if not equity:
            return SignalModification(
                ticker=symbol,
                original_signal=technical_signal,
                signal_timeframe=signal_timeframe,
                verdict="NOT_APPLICABLE",
                sizing_pct=0.0,
                conviction_score=None,
                conviction_raw=None,
                fs_score=None,
                fs_class=None,
                yield_trap_warning=False,
                asset_type=asset_type,
                position_layers=layers,
                not_applicable_reason=reason,
                rationale=[reason or "Conviction Engine applies only to individual equities"],
            )
        return SignalModification(
            ticker=symbol,
            original_signal=str(technical_signal or "").upper(),
            signal_timeframe=signal_timeframe,
            verdict="NEEDS_FULL_RECALCULATION",
            sizing_pct=0.0,
            conviction_score=None,
            conviction_raw=None,
            fs_score=None,
            fs_class=None,
            yield_trap_warning=False,
            asset_type=asset_type,
            position_layers=layers,
            not_applicable_reason="No conviction record found",
            rationale=[f'Run full_recalculation("{symbol}") before scoring this signal'],
        )
    equity, asset_type, reason = is_equity_asset(record, symbol)
    layers = PositionLayers.from_dict(record.get("position_layers"))

    if not equity:
        return SignalModification(
            ticker=symbol,
            original_signal=technical_signal,
            signal_timeframe=signal_timeframe,
            verdict="NOT_APPLICABLE",
            sizing_pct=0.0,
            conviction_score=None,
            conviction_raw=None,
            fs_score=None,
            fs_class=None,
            yield_trap_warning=False,
            asset_type=asset_type,
            position_layers=layers,
            not_applicable_reason=reason,
            rationale=[reason or "Conviction Engine applies only to individual equities"],
        )

    record = daily_update(symbol, record=record, store_dir=store_dir, save=False)
    raw_score = float(record.get("conviction_score", 0.0) or 0.0)
    fs_class = str(record.get("fs_class") or classify_fs(record.get("fs_score")))
    final_score, cap_reason = apply_fs_cap(raw_score, fs_class, signal_timeframe)
    yield_trap = bool(record.get("yield_trap_warning"))
    rationale = [
        f"BQ {record.get('bq_raw', 0)} + valuation tax {record.get('valuation_tax', 0)} = {raw_score}",
        f"FS class {fs_class}",
    ]
    if cap_reason:
        rationale.append(cap_reason)

    technical_signal = str(technical_signal or "").upper()
    if technical_signal == "BUY" and signal_timeframe == "short" and long_position_near_stop:
        verdict, sizing = "CANCEL BUY", 0.0
        rationale.append("TRAILING_STOP_WARNING: long position near stop")
    elif technical_signal == "BUY":
        verdict, sizing = verdict_for_buy(final_score, record.get("fd_direction"), yield_trap)
    elif technical_signal == "SELL":
        verdict, sizing = verdict_for_sell(final_score, signal_timeframe, yield_trap)
    else:
        verdict, sizing = "NOT_APPLICABLE", 0.0
        rationale.append("Unknown technical signal")

    if yield_trap:
        rationale.append("Yield trap hard gate fired")

    if update_layers:
        _update_position_layers(layers, verdict, sizing, technical_signal, signal_timeframe, quant_model_name, signal_date)
        record["position_layers"] = layers.to_dict()

    if persist:
        save_record(record, store_dir)

    return SignalModification(
        ticker=symbol,
        original_signal=technical_signal,
        signal_timeframe=signal_timeframe,
        verdict=verdict,
        sizing_pct=sizing,
        conviction_score=round(final_score, 2),
        conviction_raw=round(raw_score, 2),
        fs_score=record.get("fs_score"),
        fs_class=fs_class,
        yield_trap_warning=yield_trap,
        business_type=record.get("business_type"),
        bq_raw=record.get("bq_raw"),
        valuation_tax=record.get("valuation_tax"),
        asset_type=asset_type,
        rationale=rationale,
        position_layers=layers,
    )


def _update_position_layers(
    layers: PositionLayers,
    verdict: str,
    sizing_pct: float,
    technical_signal: str,
    signal_timeframe: str,
    quant_model_name: str | None,
    signal_date: str | None,
) -> None:
    if technical_signal == "BUY" and verdict != "CANCEL BUY":
        target_fraction = max(0.0, min(1.0, sizing_pct / 100.0))
        if signal_timeframe == "long":
            layers.core_fraction = target_fraction
            layers.core_model = quant_model_name
            layers.core_signal_date = signal_date
        else:
            layers.tactical_fraction = max(0.0, min(target_fraction, 1.0 - layers.core_fraction))
            layers.tactical_model = quant_model_name
            layers.tactical_signal_date = signal_date
        return

    if technical_signal == "SELL":
        if verdict == "HARD EXIT":
            layers.core_fraction = 0.0
            layers.tactical_fraction = 0.0
            return
        if signal_timeframe == "short":
            layers.tactical_fraction = 0.0
            return
        if verdict == "PAUSE SELL":
            layers.core_fraction *= 0.70
        elif verdict == "PARTIAL EXIT":
            layers.core_fraction *= 0.50
        elif verdict == "FULL EXIT":
            layers.core_fraction = 0.0
            layers.tactical_fraction = 0.0


def apply_to_signal(
    signal: QuantSignal | pd.Series | dict[str, Any],
    store_dir: Path | None = None,
    persist: bool = False,
    update_layers: bool = False,
) -> dict[str, Any]:
    quant_signal = signal if isinstance(signal, QuantSignal) else normalize_signal_row(signal)
    modification = modify_signal(
        ticker=quant_signal.symbol,
        technical_signal=quant_signal.technical_signal,
        signal_timeframe=quant_signal.signal_timeframe,
        signal_strength=quant_signal.signal_strength,
        quant_model_name=f"{quant_signal.function_name}_{quant_signal.interval}",
        signal_date=quant_signal.signal_date,
        store_dir=store_dir,
        persist=persist,
        update_layers=update_layers and str(quant_signal.status).lower() == "open",
    )
    return modification.to_dict()


def apply_to_signal_file(
    file_path: Path | str,
    store_dir: Path | None = None,
    save_output: bool = False,
    update_layers: bool = False,
) -> pd.DataFrame:
    path = Path(file_path)
    df = load_signal_file(path)
    if df.empty:
        return df

    signals = normalize_signal_dataframe(df, source_file=path)
    overlays = [
        apply_to_signal(signal, store_dir=store_dir, persist=update_layers, update_layers=update_layers)
        for signal in signals
    ]
    overlay_df = pd.DataFrame(overlays)
    result = pd.concat([df.reset_index(drop=True), overlay_df.reset_index(drop=True)], axis=1)

    if save_output:
        write_dataframe_csv_atomic_guarded(result, overlay_path(path))
    return result


def run_daily_universe(tickers: list[str], store_dir: Path | None = None) -> dict[str, list[str]]:
    alert_map: dict[str, list[str]] = {}
    for ticker in tickers:
        record = daily_update(ticker, store_dir=store_dir)
        flags: list[str] = []
        if record.get("yield_trap_warning"):
            flags.append("yield_trap")
        if record.get("fs_class") in {"weak", "moderate_low"}:
            flags.append(f"fs_{record.get('fs_class')}")
        if (record.get("conviction_score") or 0) < 2:
            flags.append("low_conviction")
        if flags:
            alert_map[sanitize_ticker(ticker)] = flags
    return alert_map


def generate_daily_report(alert_map: dict[str, list[str]] | None = None, records: list[dict[str, Any]] | None = None) -> str:
    alert_map = alert_map or {}
    records = records or []
    lines = ["Conviction Engine Daily Report", ""]
    if records:
        scored_records = [record for record in records if record.get("conviction_score") is not None]
        strong = sum(1 for record in scored_records if record.get("conviction_score", 0) >= 5)
        weak = sum(1 for record in scored_records if record.get("conviction_score", 0) < 2)
        lines.append(f"Universe size: {len(records)}")
        lines.append(f"Scored equities: {len(scored_records)}")
        lines.append(f"Strong conviction names: {strong}")
        lines.append(f"Weak / cancel-buy names: {weak}")
        lines.append("")
    if not alert_map:
        lines.append("No fundamental alerts.")
    else:
        lines.append("Alerts:")
        for ticker, flags in sorted(alert_map.items()):
            lines.append(f"- {ticker}: {', '.join(flags)}")
    return "\n".join(lines)


def update_overrides(
    ticker: str,
    updates: dict[str, Any],
    recompute: bool = True,
    store_dir: Path | None = None,
) -> dict[str, Any]:
    record = load_or_create_record(ticker, store_dir)
    record["manual_overrides"] = {**record.get("manual_overrides", {}), **updates}
    if recompute:
        components = compute_bq_components(record, record["manual_overrides"])
        record["bq_components"] = components
        record["bq_raw"] = float(record["manual_overrides"].get("bq_raw", calculate_bq_raw(components)))
        record["fs_quality_base"] = round(50 + (record["bq_raw"] * 2.5), 2)
        record = daily_update(ticker, record=record, store_dir=store_dir, save=False)
    save_record(record, store_dir)
    return record
