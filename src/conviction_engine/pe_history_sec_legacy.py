"""Pre-2009 SEC filing extension for PE history — closes the gap SEC EDGAR's XBRL API
can't reach (its ``companyconcept`` endpoint only has data from each company's own start
of XBRL tagging, ~2007-2011 depending on the filer). Only invoked for tickers still
``insufficient_20y`` after the normal XBRL pass (``pe_history_sec.py``) — this is a
deliberately gated, extra-cost extension, not a routine per-ticker fetch.

Two structured (not scraped-HTML-table-guessing) sources, chosen after live research
against real filings (2026-07-29, see job-status docs for the validation record):

1. **EX-27 "Financial Data Schedule"** (mandatory SEC exhibit on 10-Ks/10-Qs for fiscal
   periods ending before ~2001-06-15, when the SEC eliminated the requirement). This is
   a plain-text, tag-delimited mini-schema — ``<EPS-DILUTED>2.63`` — filed inside every
   annual/quarterly report of that era regardless of industry (Article 5 = commercial/
   industrial, Article 9 = bank holding companies, etc. all carry the same
   ``EPS-PRIMARY``/``EPS-DILUTED`` tag names). Live-verified against MSFT's FY1997 10-K
   (``EPS-DILUTED=2.63``, matches Microsoft's own contemporaneous press release and
   investor-relations "financial highlights" page exactly) and Chase Manhattan's (JPM's
   predecessor CIK) FY1997 10-K (Article 9 bank schedule, same tag names). This is by far
   the most reliable of the two sources — annual-only in this implementation (10-Q/
   quarterly EX-27 parsing, which would need the same Q4-plug technique as
   ``pe_history_sec.py``, is a documented future extension, not built here).

2. **"Selected Financial Data" (Item 6) table**, for the ~2001-2009 dead zone between
   EX-27's phase-out and each company's XBRL start. SEC-mandated for that entire era: a
   single 10-K's Item 6 table reports 5 fiscal years of comparative annual EPS in one
   place, so *one* well-chosen filing per ticker typically bridges the whole gap. Parsed
   from the plain text of the filing (HTML tags stripped) via a "Diluted earnings per
   share" line-match that explicitly excludes "before/after/excluding/from ..." adjusted
   variants (those sit on an adjacent line in the same table and must not be confused
   with the GAAP figure) — live-verified against MSFT's FY2002 10-K, which returns
   exactly the 5 values for FY1998-FY2002 matching the known-published figures.

Both sources are **not** retroactively split-adjusted (same documented caveat as
``pe_history_sec.py``'s XBRL path) — figures reflect only splits that had already
happened *as of that filing*, so a P/E series spanning multiple sources across the
legacy/modern boundary or across the EX-27/Item-6 boundary can show a step-change
discontinuity at split dates. Not solved here; flagged as a known gap.
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from src.config_paths import CONVICTION_STORE_DIR

from .pe_history_sec import SEC_BASE_URL, _get_with_backoff

logger = logging.getLogger(__name__)

LEGACY_CACHE_DIR = CONVICTION_STORE_DIR / "pe_history_cache"
LEGACY_CACHE_MAX_AGE_DAYS = 365  # pre-2009 filings never change; cache aggressively

_TENK_FORMS = {"10-K", "10-K405", "10-K/A", "10-K405/A"}
_EX27_CUTOFF = date(2001, 9, 1)  # SEC eliminated the FDS requirement for periods ending after 2001-06-15; a small buffer covers filings straddling that date
_MAX_LEGACY_FILINGS_PER_TICKER = 12  # bounds worst-case network cost for one ticker's backfill

_MONTH_ABBR = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

_NUM_TOKEN = r"\(?-?\$?\s?[\d,]+\.\d{2}\)?"
_DILUTED_EPS_LINE = re.compile(
    r"Diluted (?:net income |earnings )per (?:common )?share"
    r"(?!\s+(?:before|after|excluding|from))\s*"
    r"((?:" + _NUM_TOKEN + r"\s*){2,8})",
    re.IGNORECASE,
)
_BASIC_EPS_LINE = re.compile(
    r"Basic (?:net income |earnings )per (?:common )?share"
    r"(?!\s+(?:before|after|excluding|from))\s*"
    r"((?:" + _NUM_TOKEN + r"\s*){2,8})",
    re.IGNORECASE,
)
_YEAR_HEADER = re.compile(r"Year Ended \w+ \d{1,2},?\s+((?:\d{4}(?:\s*\(\d+\))?\s*){2,8})")
_SELECTED_FIN_DATA_HEADING = re.compile(r"SELECTED\s+FINANCIAL\s+DATA", re.IGNORECASE)


def _parse_sec_date(raw: str) -> date | None:
    """Parse SEC's ``MMM-DD-YYYY`` EX-27 date format (e.g. ``JUN-30-1997``)."""
    try:
        month_s, day_s, year_s = raw.strip().upper().split("-")
        month = _MONTH_ABBR.get(month_s)
        if month is None:
            return None
        return date(int(year_s), month, int(day_s))
    except (ValueError, AttributeError):
        return None


def _clean_number(token: str) -> float | None:
    cleaned = token.strip().replace("$", "").replace(",", "").replace(" ", "")
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    cleaned = cleaned.strip("()")
    try:
        val = float(cleaned)
    except ValueError:
        return None
    return -val if negative else val


def _submission_txt_url(cik: str, accession: str) -> str:
    """Full-submission ``.txt`` URL — unlike the per-document folder path (which strips
    dashes from the accession number), this flat legacy form keeps them."""
    cik_int = str(int(cik))
    return f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession}.txt"


def _fetch_submission_text(cik: str, accession: str) -> str | None:
    resp = _get_with_backoff(_submission_txt_url(cik, accession), timeout=30)
    if resp is None or resp.status_code != 200:
        return None
    return resp.text


def _extract_sgml_document(submission_text: str, type_prefix: str) -> str | None:
    """Pull one ``<DOCUMENT>``'s ``<TEXT>...</TEXT>`` body out of a full SGML submission
    ``.txt`` file, matched by its ``<TYPE>`` (e.g. ``EX-27``, ``10-K``) — tolerant of a
    trailing ``.1``/``405`` suffix (``EX-27.1``, ``10-K405``)."""
    pattern = re.compile(
        r"<TYPE>" + re.escape(type_prefix) + r"[^\n<]*\n.*?<TEXT>(.*?)</TEXT>",
        re.DOTALL | re.IGNORECASE,
    )
    m = pattern.search(submission_text)
    return m.group(1) if m else None


def parse_ex27_annual_eps(ex27_text: str) -> tuple[date, float] | None:
    """Extract one annual (``PERIOD-TYPE`` YEAR/12-MOS) EPS point from an EX-27 Financial
    Data Schedule body. Prefers ``EPS-DILUTED``, falls back to ``EPS-PRIMARY``. Returns
    ``None`` when the schedule isn't annual, has no usable EPS tag, or fails to parse."""
    period_type_m = re.search(r"<PERIOD-TYPE>\s*([^\n<]+)", ex27_text, re.IGNORECASE)
    if not period_type_m:
        return None
    period_type = period_type_m.group(1).strip().upper()
    if period_type not in ("YEAR", "12-MOS"):
        return None

    period_end_m = re.search(r"<PERIOD-END>\s*([^\n<]+)", ex27_text, re.IGNORECASE)
    if not period_end_m:
        return None
    period_end = _parse_sec_date(period_end_m.group(1))
    if period_end is None:
        return None

    # Pre-SFAS-128 (1997) schedules often leave EPS-DILUTED as a literal unpopulated "0"
    # when the filer didn't compute a separate fully-diluted figure (simple capital
    # structure) — treat an exact 0.0 as "not reported" and fall through to EPS-PRIMARY
    # rather than silently dropping a perfectly good primary-EPS data point.
    fallback: float | None = None
    for tag in ("EPS-DILUTED", "EPS-PRIMARY"):
        m = re.search(r"<" + tag + r">\s*([^\n<]+)", ex27_text, re.IGNORECASE)
        if not m:
            continue
        val = _clean_number(m.group(1))
        if val is None or not (-500.0 < val < 500.0):
            continue
        if val == 0.0:
            fallback = fallback if fallback is not None else val
            continue
        return period_end, val
    if fallback is not None:
        return period_end, fallback
    return None


def parse_selected_financial_data(document_text: str, anchor_report_date: date) -> dict[date, float]:
    """Extract the Item 6 "Selected Financial Data" 5(ish)-year annual-EPS table from a
    10-K's plain document text (HTML or SGML — tags are stripped here). ``anchor_report_date``
    is the filing's *own* fiscal year end (from SEC's ``reportDate``), used to map each
    table column to a specific fiscal year end date (rightmost/newest column = the anchor
    year, each column left of it = one fiscal year earlier) — more robust than trying to
    parse the (inconsistently worded) "Year Ended <month> <day>" header for the actual
    calendar mapping. Returns ``{fiscal_year_end: diluted_or_basic_eps}``, possibly empty
    if no real Selected Financial Data section (as opposed to a table-of-contents link)
    with a parseable per-share row is found.
    """
    text = re.sub(r"<[^>]+>", " ", document_text)
    text = re.sub(r"&nbsp;|&#160;", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)

    results: dict[date, float] = {}
    for heading_m in _SELECTED_FIN_DATA_HEADING.finditer(text):
        window = text[heading_m.end() : heading_m.end() + 6000]
        eps_m = _DILUTED_EPS_LINE.search(window) or _BASIC_EPS_LINE.search(window)
        if not eps_m:
            continue  # likely a table-of-contents hit, not the real section
        values = [v for v in (_clean_number(tok) for tok in re.findall(_NUM_TOKEN, eps_m.group(1))) if v is not None]
        if len(values) < 2:
            continue
        # Rightmost (newest) column = anchor_report_date; each column left of it is one
        # fiscal year earlier. Same month/day as the anchor, year decremented.
        n = len(values)
        for offset, val in enumerate(reversed(values)):
            fy_end = date(anchor_report_date.year - offset, anchor_report_date.month, anchor_report_date.day)
            if -500.0 < val < 500.0:
                results[fy_end] = val
        if results:
            break  # first section with a parseable EPS row wins; don't scan further hits
    return results


def _list_all_10k_filings(cik: str) -> list[dict[str, Any]]:
    """All 10-K/10-K405(+/A) filings for a CIK across the ``recent`` block and every
    paginated ``filings.files`` page, sorted ascending by ``reportDate``. One extra
    network call per additional page of filing history (most large/old filers have 1-3).
    """
    filings: list[dict[str, Any]] = []

    def _collect(payload: dict[str, Any]) -> None:
        forms = payload.get("form") or []
        dates = payload.get("reportDate") or []
        filing_dates = payload.get("filingDate") or []
        accns = payload.get("accessionNumber") or []
        for i, form in enumerate(forms):
            if str(form).upper() not in _TENK_FORMS:
                continue
            report_date = dates[i] if i < len(dates) else None
            if not report_date:
                continue
            filings.append(
                {
                    "form": form,
                    "reportDate": report_date,
                    "filingDate": filing_dates[i] if i < len(filing_dates) else None,
                    "accessionNumber": accns[i] if i < len(accns) else None,
                }
            )

    resp = _get_with_backoff(f"{SEC_BASE_URL}/submissions/CIK{cik}.json")
    if resp is None or resp.status_code != 200:
        return []
    try:
        payload = resp.json()
    except Exception:
        return []
    _collect(payload.get("filings", {}).get("recent", {}))

    for file_ref in payload.get("filings", {}).get("files", []) or []:
        name = file_ref.get("name")
        if not name:
            continue
        page_resp = _get_with_backoff(f"{SEC_BASE_URL}/submissions/{name}")
        if page_resp is None or page_resp.status_code != 200:
            continue
        try:
            page_payload = page_resp.json()
        except Exception:
            continue
        _collect(page_payload)

    filings.sort(key=lambda f: f["reportDate"])
    return filings


def fetch_legacy_annual_eps(
    ticker: str,
    cik: str,
    existing_earliest_date: pd.Timestamp | None,
    *,
    cache_dir: Path | None = None,
) -> pd.Series:
    """Fetch + parse pre-``existing_earliest_date`` annual EPS from old 10-Ks (EX-27
    Financial Data Schedules for filings before the ~2001 cutoff, one "Selected Financial
    Data" table lookup to bridge from there up to ``existing_earliest_date``).

    Returns a ``pd.Series`` indexed by fiscal-year-end date (already trailing-twelve-
    months values, ready for ``pe_history_core.compute_pe_history_with_legacy_annual``),
    restricted to dates strictly before ``existing_earliest_date`` — never raises, never
    overlaps with modern-era coverage. Empty series on any failure (no filings found, no
    parseable EX-27/Item-6 data, network errors).
    """
    resolved_cache_dir = cache_dir if cache_dir is not None else LEGACY_CACHE_DIR
    cutoff = pd.Timestamp(existing_earliest_date) if existing_earliest_date is not None else None

    cached = _load_legacy_cache(ticker, resolved_cache_dir)
    if cached is not None:
        series = pd.Series(cached, dtype=float)
        series.index = pd.DatetimeIndex(series.index)
        if cutoff is not None:
            series = series[series.index < cutoff]
        return series.sort_index()

    all_filings = _list_all_10k_filings(cik)
    if not all_filings:
        return pd.Series(dtype=float)

    if cutoff is not None:
        candidates = [f for f in all_filings if pd.Timestamp(f["reportDate"]) < cutoff]
    else:
        candidates = list(all_filings)
    if not candidates:
        return pd.Series(dtype=float)

    points: dict[date, float] = {}

    ex27_candidates = [f for f in candidates if date.fromisoformat(f["reportDate"]) <= _EX27_CUTOFF]
    for filing in ex27_candidates[-_MAX_LEGACY_FILINGS_PER_TICKER:]:
        text = _fetch_submission_text(cik, filing["accessionNumber"])
        if not text:
            continue
        ex27_body = _extract_sgml_document(text, "EX-27")
        if not ex27_body:
            continue
        parsed = parse_ex27_annual_eps(ex27_body)
        if parsed:
            fy_end, val = parsed
            points.setdefault(fy_end, val)

    # Bridge whatever gap remains (post-EX27-cutoff up to existing_earliest_date) with
    # one Selected Financial Data table lookup, picked so its ~5y lookback covers the gap.
    bridge_candidates = [f for f in candidates if date.fromisoformat(f["reportDate"]) > _EX27_CUTOFF]
    if bridge_candidates:
        bridge_filing = bridge_candidates[-1]  # latest pre-cutoff filing: widest lookback toward existing coverage
        text = _fetch_submission_text(cik, bridge_filing["accessionNumber"])
        if text:
            tenk_body = _extract_sgml_document(text, "10-K") or text
            anchor = date.fromisoformat(bridge_filing["reportDate"])
            bridged = parse_selected_financial_data(tenk_body, anchor)
            for fy_end, val in bridged.items():
                points.setdefault(fy_end, val)

    if not points:
        _save_legacy_cache(ticker, {}, resolved_cache_dir)
        return pd.Series(dtype=float)

    series = pd.Series(points).sort_index()
    series.index = pd.DatetimeIndex(series.index)
    _save_legacy_cache(ticker, {d.strftime("%Y-%m-%d"): v for d, v in series.items()}, resolved_cache_dir)

    if cutoff is not None:
        series = series[series.index < cutoff]
    return series


def _legacy_cache_path(ticker: str, cache_dir: Path) -> Path:
    return cache_dir / f"{ticker.upper()}_sec_legacy.json"


def _load_legacy_cache(ticker: str, cache_dir: Path) -> dict[str, float] | None:
    path = _legacy_cache_path(ticker, cache_dir)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text())
    except Exception:
        return None
    fetched_at = payload.get("fetched_at")
    if not isinstance(fetched_at, (int, float)):
        return None
    if (time.time() - fetched_at) / 86400.0 > LEGACY_CACHE_MAX_AGE_DAYS:
        return None
    points = payload.get("points")
    return points if isinstance(points, dict) else None


def _save_legacy_cache(ticker: str, points: dict[str, float], cache_dir: Path) -> None:
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        _legacy_cache_path(ticker, cache_dir).write_text(json.dumps({"fetched_at": time.time(), "points": points}))
    except Exception:
        logger.debug("pe_history_sec_legacy: failed to write cache for %s", ticker, exc_info=True)
