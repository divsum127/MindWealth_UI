"""SEC EDGAR XBRL PE-history fallback — primary deep-history source for US tickers.

Supersedes FMP as the first fallback tried (2026-07-24, per explicit user direction
after confirming FMP's free tier caps history at 5 years — see ``pe_history_fmp.py``).
``data.sec.gov``'s XBRL API is the SEC's own official, permanently free, unlimited
(no API key, no daily cap — only a fair-use ~10 req/sec guideline and a required
``User-Agent`` contact header) source for every US-GAAP fact a company has ever filed.
Live-verified 2026-07-24: AAPL and MSFT EPS both go back to fiscal 2007 (~19 years),
NVDA to fiscal 2008 (~18y), PYPL to 2013 (~12y, limited by its 2015 eBay spinoff) — a
real ceiling around the 2009 XBRL mandate, but categorically deeper than FMP's free-tier
5-year cap and yfinance's typical ~0.5-2 year quarterly-statement depth.

Design (per explicit user decisions, 2026-07-24):
1. **Quarterly reconstruction, not annual-only.** SEC filings report EPS for discrete
   fiscal quarters via 10-Qs (Q1-Q3) and for the full fiscal year via 10-Ks, but never
   file a standalone "Q4" report. Q4 is reconstructed as ``FY_EPS - (Q1+Q2+Q3)`` — the
   standard "Q4 plug" technique — so ``compute_pe_history()`` (shared with the
   yfinance/FMP paths, see ``pe_history_core.py``) gets a normal 4-quarters-per-year
   series and can build the same rolling-TTM monthly P/E history it always has.
2. **First-filed value per (start, end) period**, to approximate point-in-time data and
   avoid look-ahead bias from later restatements (discontinued-ops reclassification,
   segment changes, etc.) — the same period's EPS can appear in multiple filings (its
   own quarter's 10-Q/10-K, plus as a prior-year comparative in next year's filing);
   the earliest-``filed`` value is kept.
3. Foreign private issuers (20-F/40-F/6-K filers) are out of scope for the general
   ``is_us_ticker()``-gated path — they don't report US-GAAP
   ``EarningsPerShareDiluted``/``EarningsPerShareBasic`` and won't be found in SEC's
   ticker→CIK map under their local-exchange ticker with usable facts; ``fetch_pe_history_sec``
   returns ``None`` for them (same non-US routing to ``scripts/set_manual_pe_history.py``
   as the FMP path) **unless** explicitly listed in ``FOREIGN_PRIVATE_ISSUER_ALIASES``
   below (2026-07-29 addendum, see that dict's docstring) — a small, manually-verified
   allowlist for large-cap Canadian names that are dual-listed on a US exchange and file
   ``40-F``/``6-K`` under the MJDS regime with real ``ifrs-full``-taxonomy EPS data.

Known caveat (shared with the yfinance path, not new here): EPS values are **not**
retroactively split-adjusted the way yfinance's split-adjusted close prices are, since
"first-filed" intentionally does not pick up a later filing's restated/split-adjusted
comparative figures. A stock split will show as a step-change discontinuity in the P/E
series around the split date. Documented as a known gap, not solved in this pass.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from src.config_paths import CONVICTION_STORE_DIR

from .pe_history_core import compute_pe_history, compute_pe_history_with_legacy_annual
from .pe_history_fmp import is_us_ticker

logger = logging.getLogger(__name__)

SEC_BASE_URL = "https://data.sec.gov"
SEC_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
# SEC requires a descriptive User-Agent identifying the app + a contact (its own Fair
# Access policy, not a paid-key requirement). Override via env for production so SEC
# can reach a real contact if this integration ever needs throttling/investigation.
DEFAULT_USER_AGENT = "MindWealth-ConvictionEngine/1.0 (contact: research@mindwealth.internal)"

SEC_CACHE_DIR = CONVICTION_STORE_DIR / "pe_history_cache"
SEC_CACHE_MAX_AGE_DAYS = 80  # ~quarterly refresh cadence, matches pe_history_fmp.py
SEC_TICKER_MAP_MAX_AGE_DAYS = 30  # SEC's bulk ticker->CIK file changes slowly

# Diluted preferred (matches conventional trailing-P/E convention); fall back to basic
# for companies/periods that don't report diluted EPS (e.g. simple capital structures).
EPS_CONCEPTS: tuple[str, ...] = ("EarningsPerShareDiluted", "EarningsPerShareBasic")

_VALID_FORMS = {"10-K", "10-Q", "10-K/A", "10-Q/A"}
_QUARTER_DAYS_RANGE = (80, 100)
_ANNUAL_DAYS_RANGE = (340, 380)

# Added 2026-07-29: a small, **manually verified** allowlist of large-cap Canadian
# tickers that are dual-listed on a US exchange under a different (bare) ticker symbol
# and file annual reports with the SEC via the MJDS regime (form 40-F, quarterly updates
# via 6-K) rather than a 10-K/10-Q — and report EPS under the ``ifrs-full`` XBRL
# taxonomy (``DilutedEarningsLossPerShare``/``BasicEarningsLossPerShare``), not
# ``us-gaap``. Deliberately NOT a generic "any bare foreign ticker" rule: SEC's
# ticker->CIK map has real collisions with unrelated shell companies for some Canadian
# tickers (e.g. bare "NA" and "SJ" resolve to unrelated OTC issuers, not National Bank
# of Canada / Stella-Jones) — every entry here was individually confirmed via a live
# ``companyconcept`` fetch before being added, not inferred from a suffix pattern.
#
# ``currency`` is the XBRL unit (e.g. ``"CAD/shares"``) to require — this ticker's own
# ``conviction_store`` price series must be denominated in that same currency, or the
# resulting "P/E" would silently divide a price in one currency by EPS in another. This
# is why only the ``.TO`` (CAD-priced, TSX) listing is aliased for TD/RY/BNS/CNQ even
# though a bare US-listed (USD-priced) ticker also exists for some of them (e.g. "TD")
# — their EPS is CAD-only, so only the CAD-priced ``.TO`` listing can use it correctly.
# TRI.TO and BN.TO were investigated and explicitly excluded: both report EPS in
# USD/shares only (confirmed via live ``companyconcept`` check), but trade in CAD on the
# TSX — using their USD EPS against a CAD price needs an FX conversion step that does
# not exist yet; left as a documented follow-up rather than risking a wrong ratio.
#
# ``annual_only=True`` (CNQ) means the concept has zero quarter-duration (~80-100 day)
# facts at all — only annual (40-F) totals, no 6-K interim updates carry this concept for
# that filer — so there is nothing to run through the normal Q4-plug reconstruction.
# These are instead treated as already-TTM values (one per fiscal year end), reusing
# ``compute_pe_history_with_legacy_annual``'s existing "annual points are already TTM"
# handling (see ``_fetch_foreign_private_issuer`` below) rather than duplicating that
# logic here.
FOREIGN_PRIVATE_ISSUER_ALIASES: dict[str, dict[str, Any]] = {
    "TD.TO": {"sec_ticker": "TD", "currency": "CAD"},
    "RY.TO": {"sec_ticker": "RY", "currency": "CAD"},
    "BNS.TO": {"sec_ticker": "BNS", "currency": "CAD"},
    "CNQ.TO": {"sec_ticker": "CNQ", "currency": "CAD", "annual_only": True},
}

_FPI_VALID_FORMS = {"40-F", "40-F/A", "6-K"}
_FPI_EPS_TAXONOMY_CONCEPTS: tuple[tuple[str, str], ...] = (
    ("ifrs-full", "DilutedEarningsLossPerShare"),
    ("ifrs-full", "BasicEarningsLossPerShare"),
)


def _user_agent() -> str:
    return os.environ.get("SEC_EDGAR_USER_AGENT") or DEFAULT_USER_AGENT


def _get_with_backoff(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    max_attempts: int = 2,
    timeout: int = 20,
) -> requests.Response | None:
    delay = 2.0
    resp: requests.Response | None = None
    headers = {"User-Agent": _user_agent()}
    for _ in range(max_attempts):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=timeout)
        except Exception:
            resp = None
        if resp is not None and resp.status_code == 200:
            return resp
        if resp is not None and resp.status_code in (429, 500, 502, 503):
            time.sleep(delay)
            delay = min(delay * 2, 20.0)
            continue
        break
    return resp


def _ticker_map_cache_path(cache_dir: Path) -> Path:
    return cache_dir / "sec_company_tickers.json"


def _load_ticker_map(cache_dir: Path) -> dict[str, str] | None:
    path = _ticker_map_cache_path(cache_dir)
    if path.exists():
        try:
            payload = json.loads(path.read_text())
            fetched_at = payload.get("fetched_at")
            if isinstance(fetched_at, (int, float)) and (time.time() - fetched_at) / 86400.0 <= SEC_TICKER_MAP_MAX_AGE_DAYS:
                mapping = payload.get("map")
                if isinstance(mapping, dict) and mapping:
                    return mapping
        except Exception:
            pass

    resp = _get_with_backoff(SEC_TICKER_MAP_URL)
    if resp is None or resp.status_code != 200:
        return None
    try:
        raw = resp.json()
    except Exception:
        return None

    mapping: dict[str, str] = {}
    values = raw.values() if isinstance(raw, dict) else raw if isinstance(raw, list) else []
    for entry in values:
        try:
            mapping[str(entry["ticker"]).upper()] = str(entry["cik_str"]).zfill(10)
        except (KeyError, TypeError):
            continue
    if not mapping:
        return None

    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"fetched_at": time.time(), "map": mapping}))
    except Exception:
        logger.debug("pe_history_sec: failed to write ticker-map cache", exc_info=True)
    return mapping


def get_cik_for_ticker(ticker: str, cache_dir: Path | None = None) -> str | None:
    """Resolve a ticker to its 10-digit zero-padded SEC CIK via the cached bulk map."""
    if not ticker:
        return None
    resolved_dir = cache_dir if cache_dir is not None else SEC_CACHE_DIR
    mapping = _load_ticker_map(resolved_dir)
    if not mapping:
        return None
    return mapping.get(ticker.upper().strip())


def _dedupe_first_filed(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the earliest-``filed`` fact per unique (start, end) period — approximates
    point-in-time data, avoiding look-ahead bias from later restatements."""
    best: dict[tuple[str, str], dict[str, Any]] = {}
    for fact in facts:
        key = (fact.get("start"), fact.get("end"))
        if key[0] is None or key[1] is None:
            continue
        existing = best.get(key)
        if existing is None or str(fact.get("filed") or "") < str(existing.get("filed") or ""):
            best[key] = fact
    return list(best.values())


def _duration_days(fact: dict[str, Any]) -> int | None:
    try:
        start = date.fromisoformat(fact["start"])
        end = date.fromisoformat(fact["end"])
    except (KeyError, ValueError, TypeError):
        return None
    return (end - start).days


def _plug_quarterly_series(facts: list[dict[str, Any]]) -> dict[str, float]:
    """Classify facts into discrete quarters (~80-100 day spans, direct from 10-Qs) and
    annual totals (~340-380 day spans, from 10-Ks), then reconstruct each fiscal year's
    Q4 as ``FY - (Q1+Q2+Q3)`` when exactly 3 quarters are found inside that FY's span.
    Years where fewer than 3 quarters are found are left with a gap (no Q4 plugged) —
    safe: ``compute_pe_history``'s rolling-4-quarter TTM simply produces fewer usable
    points for that stretch rather than a corrupted value. Returns {end_date: eps}.
    """
    quarters: list[tuple[str, float]] = []
    annuals: list[tuple[str, str, float]] = []
    for fact in facts:
        days = _duration_days(fact)
        val = fact.get("val")
        end = fact.get("end")
        start = fact.get("start")
        if days is None or val is None or end is None or start is None:
            continue
        try:
            val_f = float(val)
        except (TypeError, ValueError):
            continue
        if _QUARTER_DAYS_RANGE[0] <= days <= _QUARTER_DAYS_RANGE[1]:
            quarters.append((end, val_f))
        elif _ANNUAL_DAYS_RANGE[0] <= days <= _ANNUAL_DAYS_RANGE[1]:
            annuals.append((start, end, val_f))

    result: dict[str, float] = dict(quarters)

    for fy_start, fy_end, annual_val in annuals:
        try:
            start_d = date.fromisoformat(fy_start)
            end_d = date.fromisoformat(fy_end)
        except ValueError:
            continue
        contained = [
            (qend, qval)
            for qend, qval in quarters
            if qend != fy_end and start_d <= date.fromisoformat(qend) <= end_d
        ]
        if len(contained) == 3:
            q4_val = annual_val - sum(v for _, v in contained)
            result[fy_end] = q4_val
        # else: <3 found -> can't reliably plug Q4, leave a gap for this FY;
        #       4 found -> already fully tiled by discrete quarters, nothing to add.

    return result


def build_quarterly_eps_series(facts: list[dict[str, Any]], *, valid_forms: set[str] | None = None) -> pd.Series:
    """SEC XBRL facts (one company-concept's ``units[currency + '/shares']`` array) -> a
    quarterly EPS ``pd.Series`` indexed by quarter-end date, ready for
    ``compute_pe_history()``. Empty series when nothing usable is found.

    ``valid_forms`` defaults to the standard US 10-K/10-Q set; the foreign-private-issuer
    path passes ``_FPI_VALID_FORMS`` (40-F/6-K) instead — see ``FOREIGN_PRIVATE_ISSUER_ALIASES``.
    """
    forms = valid_forms if valid_forms is not None else _VALID_FORMS
    filtered = [
        f
        for f in facts
        if isinstance(f, dict) and str(f.get("form") or "").upper() in forms and f.get("val") is not None
    ]
    deduped = _dedupe_first_filed(filtered)
    quarter_map = _plug_quarterly_series(deduped)
    if not quarter_map:
        return pd.Series(dtype=float)
    dates = [pd.Timestamp(d) for d in quarter_map]
    values = list(quarter_map.values())
    return pd.Series(values, index=pd.DatetimeIndex(dates)).sort_index()


def _build_annual_only_eps_series(facts: list[dict[str, Any]], *, valid_forms: set[str]) -> pd.Series:
    """For filers with **no** quarter-duration facts at all (e.g. CNQ's IFRS EPS concept
    only ever carries annual 40-F totals, never a 6-K interim update) — build a plain
    annual series directly, skipping the Q4-plug machinery entirely since there are no
    discrete quarters to reconstruct around. Each value is already a full-year (i.e.
    already-TTM-as-of-fiscal-year-end) figure, meant for
    ``compute_pe_history_with_legacy_annual``'s ``legacy_annual_eps`` parameter.
    """
    filtered = [
        f
        for f in facts
        if isinstance(f, dict) and str(f.get("form") or "").upper() in valid_forms and f.get("val") is not None
    ]
    deduped = _dedupe_first_filed(filtered)
    annual_map: dict[str, float] = {}
    for fact in deduped:
        days = _duration_days(fact)
        end = fact.get("end")
        val = fact.get("val")
        if days is None or end is None or val is None:
            continue
        if _ANNUAL_DAYS_RANGE[0] <= days <= _ANNUAL_DAYS_RANGE[1]:
            try:
                annual_map[end] = float(val)
            except (TypeError, ValueError):
                continue
    if not annual_map:
        return pd.Series(dtype=float)
    dates = [pd.Timestamp(d) for d in annual_map]
    values = list(annual_map.values())
    return pd.Series(values, index=pd.DatetimeIndex(dates)).sort_index()


def _fetch_concept_facts(
    cik: str,
    concept: str,
    *,
    taxonomy: str = "us-gaap",
    currency: str = "USD",
) -> list[dict[str, Any]] | None:
    url = f"{SEC_BASE_URL}/api/xbrl/companyconcept/CIK{cik}/{taxonomy}/{concept}.json"
    resp = _get_with_backoff(url)
    if resp is None or resp.status_code != 200:
        return None
    try:
        data = resp.json()
    except Exception:
        return None
    units = data.get("units") if isinstance(data, dict) else None
    facts = (units or {}).get(f"{currency}/shares")
    if not facts:
        return None
    return facts


def _bundle_cache_path(ticker: str, cache_dir: Path) -> Path:
    return cache_dir / f"{ticker.upper()}_sec.json"


def _load_bundle_cache(ticker: str, cache_dir: Path) -> dict[str, Any] | None:
    path = _bundle_cache_path(ticker, cache_dir)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text())
    except Exception:
        return None
    fetched_at = payload.get("fetched_at")
    if not isinstance(fetched_at, (int, float)):
        return None
    age_days = (time.time() - fetched_at) / 86400.0
    if age_days > SEC_CACHE_MAX_AGE_DAYS:
        return None
    bundle = payload.get("bundle")
    if not isinstance(bundle, dict) or not bundle.get("values"):
        return None
    return bundle


def _save_bundle_cache(ticker: str, bundle: dict[str, Any], cache_dir: Path) -> None:
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        _bundle_cache_path(ticker, cache_dir).write_text(
            json.dumps({"fetched_at": time.time(), "bundle": bundle})
        )
    except Exception:
        logger.debug("pe_history_sec: failed to write cache for %s", ticker, exc_info=True)


def fetch_pe_history_sec(
    ticker: str,
    price_series: pd.Series | None,
    *,
    cache_dir: Path | None = None,
    cik: str | None = None,
) -> dict[str, Any] | None:
    """Fetch + reconstruct quarterly EPS from SEC EDGAR XBRL for a US ticker, then run
    it through the shared ``compute_pe_history()`` (same TTM/monthly-sampling logic as
    the yfinance and FMP paths) using the given historical price series.

    Returns ``None`` (never raises) when: the ticker isn't US-style, no price history is
    given, the ticker isn't found in SEC's CIK map (foreign private issuer, ETF, etc.),
    or SEC has no usable EPS facts for it — callers should fall back to FMP (or the
    existing yfinance bundle) in that case. A successful result is cached on disk for
    ``SEC_CACHE_MAX_AGE_DAYS`` since fundamentals only change quarterly.

    Checks ``FOREIGN_PRIVATE_ISSUER_ALIASES`` first (2026-07-29 addendum) — a handful of
    dual-listed Canadian tickers that would otherwise fail the ``is_us_ticker()`` gate
    below (they carry a ``.TO`` suffix) but have real, currency-matched IFRS EPS data on
    SEC via MJDS ``40-F``/``6-K`` filings.
    """
    if price_series is None or getattr(price_series, "empty", True):
        return None

    if ticker.upper() in FOREIGN_PRIVATE_ISSUER_ALIASES:
        return _fetch_foreign_private_issuer(ticker, price_series, cache_dir=cache_dir, cik=cik)

    if not is_us_ticker(ticker):
        return None

    resolved_cache_dir = cache_dir if cache_dir is not None else SEC_CACHE_DIR
    cached = _load_bundle_cache(ticker, resolved_cache_dir)
    if cached is not None:
        return cached

    resolved_cik = cik if cik is not None else get_cik_for_ticker(ticker, resolved_cache_dir)
    if not resolved_cik:
        return None

    facts: list[dict[str, Any]] | None = None
    for concept in EPS_CONCEPTS:
        facts = _fetch_concept_facts(resolved_cik, concept)
        if facts:
            break
    if not facts:
        return None

    quarterly_eps = build_quarterly_eps_series(facts)
    if quarterly_eps.empty:
        return None

    bundle = compute_pe_history(price_series, quarterly_eps)
    if not bundle.get("values"):
        return None

    bundle["meta"]["source"] = "sec_edgar"

    if bundle["meta"].get("insufficient_20y"):
        extended = _try_legacy_extension(ticker, resolved_cik, price_series, quarterly_eps, bundle)
        if extended is not None:
            bundle = extended

    _save_bundle_cache(ticker, bundle, resolved_cache_dir)
    return bundle


def _fetch_foreign_private_issuer(
    ticker: str,
    price_series: pd.Series,
    *,
    cache_dir: Path | None = None,
    cik: str | None = None,
) -> dict[str, Any] | None:
    """Handles the ``FOREIGN_PRIVATE_ISSUER_ALIASES`` allowlist path — resolves the CIK
    under the *aliased* SEC-registered ticker (e.g. ``"TD"`` for ``"TD.TO"``), fetches
    ``ifrs-full`` EPS facts restricted to the currency this specific ticker's price
    series is denominated in, and accepts ``40-F``/``6-K`` forms instead of 10-K/10-Q.
    """
    alias = FOREIGN_PRIVATE_ISSUER_ALIASES[ticker.upper()]
    sec_ticker = alias["sec_ticker"]
    currency = alias["currency"]
    annual_only = bool(alias.get("annual_only"))

    resolved_cache_dir = cache_dir if cache_dir is not None else SEC_CACHE_DIR
    cached = _load_bundle_cache(ticker, resolved_cache_dir)
    if cached is not None:
        return cached

    resolved_cik = cik if cik is not None else get_cik_for_ticker(sec_ticker, resolved_cache_dir)
    if not resolved_cik:
        return None

    facts: list[dict[str, Any]] | None = None
    for taxonomy, concept in _FPI_EPS_TAXONOMY_CONCEPTS:
        facts = _fetch_concept_facts(resolved_cik, concept, taxonomy=taxonomy, currency=currency)
        if facts:
            break
    if not facts:
        return None

    if annual_only:
        annual_eps = _build_annual_only_eps_series(facts, valid_forms=_FPI_VALID_FORMS)
        if annual_eps.empty:
            return None
        bundle = compute_pe_history_with_legacy_annual(price_series, pd.Series(dtype=float), annual_eps)
    else:
        quarterly_eps = build_quarterly_eps_series(facts, valid_forms=_FPI_VALID_FORMS)
        if quarterly_eps.empty:
            return None
        bundle = compute_pe_history(price_series, quarterly_eps)

    if not bundle.get("values"):
        return None

    bundle["meta"]["source"] = "sec_edgar_40f"
    _save_bundle_cache(ticker, bundle, resolved_cache_dir)
    return bundle


def _try_legacy_extension(
    ticker: str,
    cik: str,
    price_series: pd.Series,
    quarterly_eps: pd.Series,
    xbrl_bundle: dict[str, Any],
) -> dict[str, Any] | None:
    """Only reached when the XBRL-only bundle is still ``insufficient_20y`` — attempts
    the pre-2009 EX-27 / Selected-Financial-Data extension (``pe_history_sec_legacy.py``).
    Deliberately isolated + defensive (broad except) so a legacy-filing parsing issue for
    one ticker can never break the (already-working) XBRL-only bundle for it — worst case
    is falling back to ``xbrl_bundle`` unchanged, never a crash or corrupted PE series.
    """
    try:
        from .pe_history_sec_legacy import fetch_legacy_annual_eps

        legacy_eps = fetch_legacy_annual_eps(ticker, cik, quarterly_eps.index.min())
        if legacy_eps.empty:
            return None
        extended = compute_pe_history_with_legacy_annual(price_series, quarterly_eps, legacy_eps)
        if not extended.get("values") or extended["meta"]["point_count"] <= xbrl_bundle["meta"]["point_count"]:
            return None
        extended["meta"]["source"] = "sec_edgar+legacy"
        return extended
    except Exception:
        logger.debug("pe_history_sec: legacy extension failed for %s", ticker, exc_info=True)
        return None
