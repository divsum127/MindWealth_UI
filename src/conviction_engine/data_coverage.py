"""Data coverage and missing-field reporting for conviction fundamentals."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .fundamentals_enriched import PE_HISTORY_TARGET_YEARS

CRITICAL_FIELDS: tuple[str, ...] = (
    "price",
    "market_cap",
    "eps_ttm",
    "eps_fwd",
    "fcf_ttm",
    "net_debt_stored",
    "fwd_revenue_stored",
    "annual_div_per_share_stored",
    "revenue_growth",
    "fcf_margin",
    "gross_margin",
    "net_debt_ebitda",
    "distribution_coverage_ratio",
    "gross_margin_trend",
    "roic_proxy",
    "pe_20y_array",
    "dividend_yield_5y_mean",
    "dividend_yield_5y_std",
    "revenue_accelerating",
    "insider_pct",
)

# BQ auto dimensions: required fundamental keys to treat dimension as data-backed (not neutral-only).
BQ_DIMENSION_INPUTS: dict[str, tuple[str, ...]] = {
    "revenue_quality": ("gross_margin", "fcf_margin"),
    "growth_trajectory": ("revenue_growth",),
    "margin_quality": ("revenue_growth", "fcf_margin", "distribution_coverage_ratio", "gross_margin"),
    "balance_sheet": ("net_debt_ebitda",),
    "roic_wacc_spread": ("roic_proxy", "roic"),
    "gross_margin_trend": ("gross_margin_trend",),
    "debt_maturity_risk": (),  # override-only unless explicitly set
    "ceo_quality": (),  # manual override
    "mgmt_capital_allocation": (),
    "competitive_moat": (),
    "macro_tailwind": (),
    "divergence_signal": (),
    "deal_delay_risk": (),
    "insider_ownership": ("insider_pct",),
    "reinvestment_runway": (),
}

LOW_COVERAGE_THRESHOLD = 0.45

PE_HISTORY_YEAR_BUCKETS: tuple[tuple[str, float, float | None], ...] = (
    ("0", 0.0, 0.0),
    ("0-2", 0.0, 2.0),
    ("2-5", 2.0, 5.0),
    ("5-10", 5.0, 10.0),
    ("10-15", 10.0, 15.0),
    ("15-20", 15.0, 20.0),
    ("20+", 20.0, None),
)


def _pe_history_meta(record: dict[str, Any], fundamentals: dict[str, Any] | None = None) -> dict[str, Any]:
    meta = dict(
        (fundamentals or {}).get("pe_history_meta")
        or record.get("pe_history_meta")
        or (record.get("data_coverage") or {}).get("pe_history")
        or {}
    )
    if not meta and not _is_present(record.get("pe_20y_array")):
        return {
            "years_available": 0.0,
            "target_years": PE_HISTORY_TARGET_YEARS,
            "insufficient_20y": True,
            "has_pe_series": False,
        }
    if not meta and _is_present(record.get("pe_20y_array")):
        stored = len(record.get("pe_20y_array") or [])
        return {
            "years_available": 0.0,
            "target_years": PE_HISTORY_TARGET_YEARS,
            "insufficient_20y": True,
            "has_pe_series": True,
            "legacy_no_meta": True,
            "stored_point_count": stored,
        }
    years = float(meta.get("years_available") or 0.0)
    return {
        **meta,
        "years_available": years,
        "target_years": int(meta.get("target_years") or PE_HISTORY_TARGET_YEARS),
        "insufficient_20y": bool(meta.get("insufficient_20y", years < PE_HISTORY_TARGET_YEARS)),
        "has_pe_series": _is_present(record.get("pe_20y_array")) or bool(meta.get("point_count")),
    }


def _years_bucket(years: float) -> str:
    if years <= 0:
        return "0"
    if years <= 2:
        return "0-2"
    if years <= 5:
        return "2-5"
    if years <= 10:
        return "5-10"
    if years <= 15:
        return "10-15"
    if years <= 20:
        return "15-20"
    return "20+"


def summarize_pe_history_distribution(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate P/E history span across conviction_store records (equities with scores)."""
    rows: list[dict[str, Any]] = []
    for record in records:
        ticker = str(record.get("ticker") or "").upper()
        if not ticker:
            continue
        asset = str(record.get("asset_type") or record.get("quote_type") or "").upper()
        if asset and asset not in {"EQUITY", "UNKNOWN", ""}:
            continue
        if record.get("conviction_score") is None:
            continue
        pe = _pe_history_meta(record)
        years = float(pe.get("years_available") or 0.0)
        rows.append(
            {
                "ticker": ticker,
                "years_available": years,
                "insufficient_20y": bool(pe.get("insufficient_20y", years < PE_HISTORY_TARGET_YEARS)),
                "has_pe_series": bool(pe.get("has_pe_series")),
                "start_date": pe.get("start_date"),
                "end_date": pe.get("end_date"),
            }
        )

    total = len(rows)
    with_series = sum(1 for r in rows if r["has_pe_series"])
    insufficient = sum(1 for r in rows if r["insufficient_20y"])
    bucket_counts = Counter(_years_bucket(r["years_available"]) for r in rows)
    distribution = [
        {"bucket": label, "count": bucket_counts.get(label, 0)}
        for label, _, _ in PE_HISTORY_YEAR_BUCKETS
    ]

    return {
        "target_years": PE_HISTORY_TARGET_YEARS,
        "total_equity_records": total,
        "with_pe_series": with_series,
        "without_pe_series": total - with_series,
        "insufficient_20y_count": insufficient,
        "insufficient_20y_pct": round((insufficient / total) * 100, 1) if total else 0.0,
        "sufficient_20y_count": total - insufficient,
        "years_distribution": distribution,
        "tickers": sorted(rows, key=lambda r: r["years_available"]),
    }


def _is_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return True
    if isinstance(value, (list, tuple, dict)):
        return len(value) > 0
    if isinstance(value, str):
        return bool(value.strip()) and value.strip().lower() not in ("nan", "none")
    try:
        if isinstance(value, float) and value != value:  # NaN
            return False
    except TypeError:
        pass
    return True


def _statement_flags(raw_fetch: dict[str, Any] | None) -> dict[str, bool]:
    raw_fetch = raw_fetch or {}
    return {
        "income": _is_present(raw_fetch.get("quarterly_income")),
        "balance": _is_present(raw_fetch.get("quarterly_balance")),
        "cashflow": _is_present(raw_fetch.get("quarterly_cashflow")),
    }


def _field_sources(fundamentals: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    """Merged view of stored fundamentals and post-daily record fields."""
    merged: dict[str, Any] = dict(fundamentals or {})
    for key in (
        "price",
        "market_cap",
        "eps_ttm",
        "pe_ttm",
        "pe_percentile_20y",
        "ev_fwd_rev",
        "owner_earnings_yield",
        "pe_20y_array",
        "dividend_yield_5y_mean",
        "dividend_yield_5y_std",
    ):
        if key in record and record[key] is not None:
            merged[key] = record[key]
    return merged


def _bq_dimension_status(
    name: str,
    score: float,
    merged: dict[str, Any],
    overrides: dict[str, Any] | None,
) -> dict[str, Any]:
    overrides = overrides or {}
    required = BQ_DIMENSION_INPUTS.get(name, ())
    available: list[str] = []
    missing: list[str] = []
    for key in required:
        val = merged.get(key)
        if _is_present(val):
            available.append(key)
        else:
            missing.append(key)

    manual_keys = {
        "ceo_quality": "ceo_quality_score",
        "mgmt_capital_allocation": "mgmt_alloc_score",
        "competitive_moat": "competitive_moat_score",
        "debt_maturity_risk": "debt_maturity_risk",
        "macro_tailwind": "macro_tailwind",
        "divergence_signal": "divergence_signal",
        "deal_delay_risk": "deal_delay_risk",
        "reinvestment_runway": "reinvestment_runway",
    }
    source = "auto"
    if name in manual_keys and overrides.get(manual_keys[name]) is not None:
        source = "override"
    elif not required:
        source = "manual_or_default"
    elif missing and not available:
        source = "neutral_missing_inputs"
    elif missing:
        source = "partial_inputs"

    return {
        "score": float(score),
        "inputs_available": available,
        "inputs_missing": missing,
        "source": source,
    }


def assess_data_coverage(
    fundamentals: dict[str, Any] | None,
    raw_fetch: dict[str, Any] | None,
    record: dict[str, Any],
    bq_components: dict[str, float] | None = None,
    info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build structured coverage report for a conviction record.

    Does not rescale conviction_score; only reports what was available vs missing.
    """
    fundamentals = fundamentals or {}
    raw_fetch = raw_fetch or {}
    info = info or raw_fetch.get("info") or {}
    bq_components = bq_components or record.get("bq_components") or {}
    overrides = record.get("manual_overrides") or {}

    fetch_errors = list(
        fundamentals.get("fetch_errors")
        or record.get("fetch_errors")
        or raw_fetch.get("errors")
        or []
    )

    merged = _field_sources(fundamentals, record)
    fields_present = [f for f in CRITICAL_FIELDS if _is_present(merged.get(f))]
    fields_missing = [f for f in CRITICAL_FIELDS if f not in fields_present]

    coverage_ratio = round(len(fields_present) / len(CRITICAL_FIELDS), 4) if CRITICAL_FIELDS else 0.0

    valuation_inputs = {
        "pe_ttm": _is_present(record.get("pe_ttm")),
        "pe_percentile_20y": _is_present(record.get("pe_percentile_20y")),
        "ev_fwd_rev": _is_present(record.get("ev_fwd_rev")),
        "owner_earnings_yield": _is_present(record.get("owner_earnings_yield")),
        "dividend_yield_zscore": _is_present(record.get("dividend_yield_zscore")),
        "dividend_yield_5y_stats": _is_present(record.get("dividend_yield_5y_mean"))
        and _is_present(record.get("dividend_yield_5y_std")),
    }

    bq_auto: dict[str, Any] = {}
    for name, score in bq_components.items():
        bq_auto[name] = _bq_dimension_status(name, float(score), merged, overrides)

    info_ok = bool(info) and len(info) >= 2 and info.get("quoteType") is not None
    pe_history = _pe_history_meta(record, fundamentals)

    low_data_confidence = bool(
        fetch_errors
        or not info_ok
        or coverage_ratio < LOW_COVERAGE_THRESHOLD
        or not valuation_inputs.get("ev_fwd_rev")
    )

    return {
        "fetch_errors": fetch_errors,
        "statements": _statement_flags(raw_fetch),
        "info_available": info_ok,
        "fields_present": fields_present,
        "fields_missing": fields_missing,
        "valuation_inputs": valuation_inputs,
        "pe_history": pe_history,
        "bq_auto_dimensions": bq_auto,
        "coverage_ratio": coverage_ratio,
        "low_data_confidence": low_data_confidence,
        "low_coverage_threshold": LOW_COVERAGE_THRESHOLD,
        "neutral_zero_policy": (
            "Missing BQ inputs contribute 0 to bq_raw; conviction_score is not re-scaled by coverage."
        ),
    }


def fundamentals_snapshot(
    record: dict[str, Any],
    fundamentals: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge explicit fundamentals with fields persisted on the conviction record."""
    merged: dict[str, Any] = {}
    if fundamentals:
        merged.update(fundamentals)
    for key in CRITICAL_FIELDS:
        if key in record and record[key] is not None:
            merged[key] = record[key]
    if record.get("fetch_errors") is not None:
        merged["fetch_errors"] = record["fetch_errors"]
    return merged


def _carry_raw_fetch(record: dict[str, Any], raw_fetch: dict[str, Any] | None) -> dict[str, Any]:
    """Preserve statement flags on daily-only updates when raw payloads are not re-fetched."""
    if raw_fetch:
        return raw_fetch
    prev = (record.get("data_coverage") or {}).get("statements")
    if not prev:
        return {}
    return {
        "quarterly_income": prev.get("income"),
        "quarterly_balance": prev.get("balance"),
        "quarterly_cashflow": prev.get("cashflow"),
    }


def apply_coverage_to_record(
    record: dict[str, Any],
    fundamentals: dict[str, Any] | None = None,
    raw_fetch: dict[str, Any] | None = None,
    info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Attach data_coverage and missing_fields to a conviction record."""
    snap = fundamentals_snapshot(record, fundamentals)
    coverage = assess_data_coverage(
        snap,
        _carry_raw_fetch(record, raw_fetch),
        record,
        record.get("bq_components"),
        info,
    )
    record["data_coverage"] = coverage
    record["missing_fields"] = missing_fields_list(coverage)
    return record


def missing_fields_list(coverage: dict[str, Any]) -> list[str]:
    """Flat sorted list for record.missing_fields and UI."""
    missing = list(coverage.get("fields_missing") or [])
    for err in coverage.get("fetch_errors") or []:
        missing.append(f"fetch:{err}")
    if not coverage.get("info_available", True):
        missing.append("info:empty")
    vi = coverage.get("valuation_inputs") or {}
    for key, ok in vi.items():
        if not ok:
            missing.append(f"valuation:{key}")
    pe_hist = coverage.get("pe_history") or {}
    if pe_hist.get("insufficient_20y"):
        years = pe_hist.get("years_available", 0)
        missing.append(f"pe_history:insufficient_20y ({years}y)")
    elif not pe_hist.get("has_pe_series"):
        missing.append("pe_history:no_series")
    return sorted(set(missing))
