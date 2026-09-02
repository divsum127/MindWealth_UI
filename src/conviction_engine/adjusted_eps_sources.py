"""Sourcing paths for adjusted earnings (Rohit 1 Sep, section B).

The 28 July note §6 specifies SEC XBRL Company Facts as the sourcing path. That is
US-only. NZX issuers have no XBRL mandate, which is how SPK.NZ ended up adjusted off a
catch-all bucket and reported at 25.87c against the 11.9c Spark publishes itself.

Two real sources live here:

``B1 company_disclosed``
    The issuer's own reported-to-adjusted reconciliation. There is no feed for this —
    it comes from the results announcement — so it is held in a small reviewed store
    keyed by ticker and fiscal period. Nearly every NZX issuer publishes one, so this
    is the primary path for the non-US side of the universe rather than a special case.

``B2 xbrl_tagged``
    SEC XBRL Company Facts, reusing the CIK resolution and backoff client already built
    for the P/E history work. Uses the tagged one-off concepts rather than yfinance's
    ``Total Unusual Items`` catch-all, which on GOOGL sums to $148.8B against $244.2B of
    trailing net income and cannot be taken at face value.

``B3`` (individually named lines) and ``B4`` (raw, flagged) are applied in
``adjusted_eps.py``, since they read the statement already fetched there.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.config_paths import CONVICTION_STORE_DIR

logger = logging.getLogger(__name__)

# Reviewed store of issuer-published adjusted earnings. Written by a human or by the
# results-ingest step; never guessed by the engine. Values are the company's own
# adjusted figures exactly as reported, with the citation kept alongside so any number
# reaching a screen can be traced back to the announcement it came from.
# Kept in a `reference/` subfolder, not beside the per-ticker records: everything at the
# top level of conviction_store is globbed as `<TICKER>.json`, so a reference file there
# is read back as a ticker called "disclosed_adjusted_earnings".
DISCLOSED_ADJUSTED_PATH = Path(CONVICTION_STORE_DIR) / "reference" / "disclosed_adjusted_earnings.json"

# SEC XBRL concepts that tag genuine one-off items. Each names a specific event, unlike
# the aggregate buckets this whole exercise exists to avoid.
XBRL_ONE_OFF_CONCEPTS = (
    "GainLossOnSaleOfBusiness",
    "GainLossOnDispositionOfAssets",
    "GainLossOnDispositionOfBusiness",
    "RestructuringCharges",
    "AssetImpairmentCharges",
    "GoodwillImpairmentLoss",
    "BusinessCombinationAcquisitionRelatedCosts",
)


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_disclosed_store() -> dict[str, Any]:
    """Read the reviewed store of issuer-published adjusted earnings."""
    if not DISCLOSED_ADJUSTED_PATH.exists():
        return {}
    try:
        return json.loads(DISCLOSED_ADJUSTED_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("[adjusted_eps] cannot read disclosed store: %s", exc)
        return {}


def save_disclosed_entry(ticker: str, entry: dict[str, Any]) -> None:
    """Upsert one issuer-disclosed reconciliation. Callers supply the citation."""
    store = load_disclosed_store()
    store[ticker.upper()] = entry
    DISCLOSED_ADJUSTED_PATH.parent.mkdir(parents=True, exist_ok=True)
    DISCLOSED_ADJUSTED_PATH.write_text(json.dumps(store, indent=2, sort_keys=True), encoding="utf-8")


def company_disclosed_adjusted(
    ticker: str,
    shares_outstanding: float | None,
    price: float | None,
) -> dict[str, Any] | None:
    """B1 — the issuer's own adjusted earnings, where we hold a reviewed entry.

    Accepts either an adjusted EPS or an adjusted net income plus a share count, so an
    announcement that publishes only one of the two is still usable.
    """
    entry = load_disclosed_store().get(str(ticker).upper())
    if not isinstance(entry, dict):
        return None

    adjusted_eps = _float_or_none(entry.get("adjusted_eps"))
    if adjusted_eps is None:
        adjusted_net_income = _float_or_none(entry.get("adjusted_net_income"))
        shares = _float_or_none(entry.get("shares_outstanding")) or _float_or_none(shares_outstanding)
        if adjusted_net_income is None or not shares:
            return None
        adjusted_eps = adjusted_net_income / shares

    result: dict[str, Any] = {
        "adjusted_eps_ttm": round(adjusted_eps, 4),
        "adjusted_eps_source": "company_disclosed",
        "adjusted_eps_basis": entry.get("basis") or "annual_fy",
        "adjusted_eps_period": entry.get("period"),
        "adjusted_eps_citation": entry.get("citation"),
        "one_off_review_needed": False,
    }
    if price and adjusted_eps > 0:
        result["pe_ttm_adjusted"] = round(price / adjusted_eps, 4)
    return result


def xbrl_tagged_one_offs(ticker: str) -> dict[str, Any] | None:
    """B2 — pre-tax one-off total from SEC XBRL tagged concepts, US filers.

    Returns ``None`` when the ticker is not a US filer, is absent from SEC's ticker
    map, or tags none of the concepts — all of which are ordinary, not errors.
    """
    try:
        from .pe_history_sec import SEC_BASE_URL, _get_with_backoff, get_cik_for_ticker
    except Exception as exc:  # pragma: no cover - import guard
        logger.debug("[adjusted_eps] SEC client unavailable: %s", exc)
        return None

    cik = get_cik_for_ticker(ticker)
    if not cik:
        return None

    total = 0.0
    matched: list[str] = []
    for concept in XBRL_ONE_OFF_CONCEPTS:
        url = f"{SEC_BASE_URL}/api/xbrl/companyconcept/CIK{cik}/us-gaap/{concept}.json"
        try:
            response = _get_with_backoff(url)
        except Exception:
            continue
        if response is None or getattr(response, "status_code", 200) != 200:
            continue
        try:
            payload = response.json()
        except ValueError:
            continue
        value = _latest_annual_value(payload)
        if value is not None:
            total += value
            matched.append(concept)

    if not matched:
        return None
    return {
        "one_off_items_pretax": round(total, 2),
        "adjusted_eps_source": "xbrl_tagged",
        "xbrl_concepts_matched": matched,
    }


def _latest_annual_value(payload: dict[str, Any]) -> float | None:
    """Most recent full-year (FY) figure from an XBRL companyconcept payload."""
    units = (payload or {}).get("units") or {}
    entries = units.get("USD") or []
    annual = [e for e in entries if e.get("form", "").startswith("10-K") and e.get("fp") == "FY"]
    pool = annual or [e for e in entries if e.get("fp") == "FY"]
    if not pool:
        return None
    latest = max(pool, key=lambda e: str(e.get("end", "")))
    return _float_or_none(latest.get("val"))
