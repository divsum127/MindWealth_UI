"""Operating-segment revenue mix and the mixed-business tie-break (CE-06).

Rohit, 21 Sep 2026 (msg 1a0c341380f3954b): the dominant operating segment is the tie-break
for a name that spans two business-type buckets, with documented overrides ("yes to the
first part of. your q in general"). His examples were Infratil and Spark.

US filers: segment revenue comes from the latest 10-K's XBRL instance (facts reported on
``us-gaap:StatementBusinessSegmentsAxis``); SEC's companyfacts API omits dimensional facts,
so the instance document is read directly. Non-US names have no SEC filing, so their
segment figures can only come from a documented override in
``config/conviction_business_type_overrides.json`` (``segments`` + ``segment_types``).

Which business type a named segment belongs to is a judgement, so the tie-break applies
only where an override maps segments to types. Without one, the mix is recorded for
transparency and the sector-based classification stands.
"""

from __future__ import annotations

import json
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any

from .pe_history_sec import SEC_CACHE_DIR, _get_with_backoff, get_cik_for_ticker

SEGMENT_AXIS = "us-gaap:StatementBusinessSegmentsAxis"
REVENUE_CONCEPTS = ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax")
# Below this share of revenue the largest segment does not dominate, so the name counts
# as mixed and the tie-break (where an override exists) decides the type.
DOMINANT_SHARE = 0.60
SEGMENT_CACHE_MAX_AGE_DAYS = 80  # same refresh cadence as the SEC EPS cache
_XBRLI = "http://www.xbrl.org/2003/instance"
_XBRLDI = "http://xbrl.org/2006/xbrldi"


def parse_segment_revenue(instance_xml: bytes) -> dict[str, Any] | None:
    """Revenue by business segment for the latest annual period in an XBRL instance."""
    root = ET.fromstring(instance_xml)
    contexts: dict[str, tuple[str, str, dict[str, str]]] = {}
    for ctx in root.findall(f"{{{_XBRLI}}}context"):
        period = ctx.find(f"{{{_XBRLI}}}period")
        start = period.find(f"{{{_XBRLI}}}startDate") if period is not None else None
        end = period.find(f"{{{_XBRLI}}}endDate") if period is not None else None
        if start is None or end is None:
            continue
        dims = {m.get("dimension"): (m.text or "") for m in ctx.iter(f"{{{_XBRLDI}}}explicitMember")}
        contexts[ctx.get("id") or ""] = (start.text or "", end.text or "", dims)

    by_period: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    for element in root:
        concept = element.tag.split("}", 1)[-1]
        if concept not in REVENUE_CONCEPTS:
            continue
        context = contexts.get(element.get("contextRef") or "")
        if not context:
            continue
        start, end, dims = context
        # Only facts broken down by segment alone; a second axis (product, geography)
        # would double count.
        if list(dims) != [SEGMENT_AXIS]:
            continue
        try:
            value = float(element.text or "")
        except ValueError:
            continue
        member = dims[SEGMENT_AXIS]
        # Keep the larger of the two revenue concepts if both are reported.
        by_period[(start, end)][member] = max(value, by_period[(start, end)].get(member, 0.0))

    annual = {k: v for k, v in by_period.items() if _days(k[0], k[1]) >= 330}
    if not annual:
        return None
    period = max(annual, key=lambda k: k[1])
    return mix_from_revenue(annual[period], source="sec_10k_xbrl", period_end=period[1])


def mix_from_revenue(revenue: dict[str, float], *, source: str, period_end: str | None = None) -> dict[str, Any] | None:
    positive = {k: v for k, v in revenue.items() if v and v > 0}
    total = sum(positive.values())
    if total <= 0:
        return None
    segments = sorted(
        ({"segment": k, "revenue": v, "share": round(v / total, 4)} for k, v in positive.items()),
        key=lambda s: -s["revenue"],
    )
    dominant = segments[0]
    return {
        "segments": segments,
        "dominant_segment": dominant["segment"],
        "dominant_share": dominant["share"],
        "multi_segment": dominant["share"] < DOMINANT_SHARE and len(segments) > 1,
        "source": source,
        "period_end": period_end,
    }


def _days(start: str, end: str) -> int:
    from datetime import date

    try:
        return (date.fromisoformat(end) - date.fromisoformat(start)).days
    except ValueError:
        return 0


def fetch_segment_mix_sec(ticker: str, cache_dir: Path | None = None) -> dict[str, Any] | None:
    """Segment mix from the latest 10-K, cached; None for non-filers or single-segment names."""
    directory = cache_dir if cache_dir is not None else SEC_CACHE_DIR
    cache = directory / f"{ticker.upper()}_segments.json"
    if cache.exists():
        try:
            payload = json.loads(cache.read_text(encoding="utf-8"))
            if (time.time() - float(payload.get("fetched_at", 0))) / 86400.0 <= SEGMENT_CACHE_MAX_AGE_DAYS:
                return payload.get("mix")
        except (OSError, ValueError):
            pass
    mix = _fetch_uncached(ticker)
    try:
        directory.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"fetched_at": time.time(), "mix": mix}), encoding="utf-8")
    except OSError:
        pass
    return mix


def _fetch_uncached(ticker: str) -> dict[str, Any] | None:
    cik = get_cik_for_ticker(ticker)
    if not cik:
        return None
    resp = _get_with_backoff(f"https://data.sec.gov/submissions/CIK{cik}.json")
    if resp is None or resp.status_code != 200:
        return None
    recent = resp.json().get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    try:
        i = forms.index("10-K")
    except ValueError:
        return None
    accession = str(recent["accessionNumber"][i]).replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}"
    index = _get_with_backoff(f"{base}/index.json")
    if index is None or index.status_code != 200:
        return None
    names = [item.get("name", "") for item in index.json().get("directory", {}).get("item", [])]
    instance = next((n for n in names if n.endswith("_htm.xml")), None)
    if not instance:
        return None
    doc = _get_with_backoff(f"{base}/{instance}", timeout=60)
    if doc is None or doc.status_code != 200:
        return None
    try:
        return parse_segment_revenue(doc.content)
    except ET.ParseError:
        return None


def resolve_segment_mix(ticker: str, override: dict[str, Any] | None, *, us_filer: bool) -> dict[str, Any] | None:
    """Documented override first (any listing), then SEC for US filers."""
    if override and isinstance(override.get("segments"), dict):
        return mix_from_revenue(
            {k: float(v) for k, v in override["segments"].items()},
            source=f"override: {override.get('segments_source') or 'documented'}",
            period_end=override.get("segments_period_end"),
        )
    return fetch_segment_mix_sec(ticker) if us_filer else None


def segment_tiebreak_type(mix: dict[str, Any] | None, override: dict[str, Any] | None) -> str | None:
    """Business type of the dominant segment, when an override maps segments to types."""
    if not mix or not override or not isinstance(override.get("segment_types"), dict):
        return None
    return override["segment_types"].get(mix["dominant_segment"])
