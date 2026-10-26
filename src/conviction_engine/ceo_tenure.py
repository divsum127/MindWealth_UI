"""CEO start dates from the proxy statement's Pay-versus-Performance table (CE-24).

`ceo_start_date` drives CEO quality: with tenure of 12 months or more it scores TSR against
SPY since the start date; under 12 months it applies the transition penalty. It was never
populated, so the dimension always fell back to neutral.

Source: the latest DEF 14A's XBRL instance. Since 2023 the SEC's Pay-versus-Performance rule
tags, for each of the last three to five fiscal years, who the principal executive officer
(PEO, normally the CEO) was: either `ecd:PeoName` per year (Disney style), or PEO pay tagged
per person on `ecd:IndividualAxis` per year (Starbucks style). A filer with one long-serving
CEO often tags no name at all.

Only a CEO change *inside* the window gives a start date. The date is the first day of the
first fiscal year the current CEO is listed for, or the end of that year when it was a
handover year shared with the predecessor, so it errs late, never crediting the predecessor. When the same CEO covers the whole window the start is only known to be no
later than the window's first year; that is stored as `ceo_tenure_at_least_since` and is not
used for scoring, because TSR measured from a lower bound would cover the wrong period.
"""

from __future__ import annotations

import json
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any

from .pe_history_sec import SEC_CACHE_DIR, _get_with_backoff, get_cik_for_ticker

_X = "http://www.xbrl.org/2003/instance"
_D = "http://xbrl.org/2006/xbrldi"
INDIVIDUAL_AXIS = "ecd:IndividualAxis"
CACHE_MAX_AGE_DAYS = 80


def parse_peo_history(instance_xml: bytes) -> list[dict[str, Any]]:
    """[{start, end, peos}] per fiscal year, oldest first; peos are names where tagged."""
    root = ET.fromstring(instance_xml)
    contexts: dict[str, tuple[str | None, str | None, dict[str, str]]] = {}
    for ctx in root.findall(f"{{{_X}}}context"):
        period = ctx.find(f"{{{_X}}}period")
        start = period.find(f"{{{_X}}}startDate") if period is not None else None
        end = period.find(f"{{{_X}}}endDate") if period is not None else None
        dims = {m.get("dimension"): (m.text or "") for m in ctx.iter(f"{{{_D}}}explicitMember")}
        contexts[ctx.get("id") or ""] = (
            start.text if start is not None else None,
            end.text if end is not None else None,
            dims,
        )

    member_names: dict[str, str] = {}
    names_by_year: dict[tuple[str, str], set[str]] = defaultdict(set)
    paid_by_year: dict[tuple[str, str], set[str]] = defaultdict(set)
    unnamed_years: set[tuple[str, str]] = set()
    for element in root:
        concept = element.tag.split("}", 1)[-1]
        context = contexts.get(element.get("contextRef") or "")
        if not context or not context[0] or not context[1]:
            continue
        start, end, dims = context
        year = (start, end)
        member = dims.get(INDIVIDUAL_AXIS)
        if concept == "PeoName" and element.text:
            name = element.text.strip()
            if member:
                member_names[member] = name
            else:
                names_by_year[year].add(name)
        elif concept == "PeoTotalCompAmt":
            if member:
                try:
                    if float(element.text or 0) != 0:
                        paid_by_year[year].add(member)
                except ValueError:
                    continue
            else:
                unnamed_years.add(year)

    # Members tagged on IndividualAxis without their own PeoName (Disney: "dis:MrChapekMember")
    # are matched to a tagged name by their letters ("Mr. Chapek").
    all_names = {n for names in names_by_year.values() for n in names} | set(member_names.values())

    def person(member: str) -> str:
        if member in member_names:
            return member_names[member]
        key = _letters(member.split(":", 1)[-1].removesuffix("Member"))
        return next((n for n in all_names if _letters(n) == key), member)

    years = set(names_by_year) | set(paid_by_year) | unnamed_years
    history = []
    for year in sorted(years, key=lambda y: y[1]):
        peos = set(names_by_year.get(year, set()))
        peos |= {person(m) for m in paid_by_year.get(year, set())}
        history.append({"start": year[0], "end": year[1], "peos": sorted(peos)})
    return [h for h in history if _days(h["start"], h["end"]) >= 330]


def derive_ceo_start(history: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Start of the current CEO's run, or a lower bound when no change is in the window."""
    if not history:
        return None
    latest = history[-1]["peos"]
    if len(latest) > 1:
        # Two PEOs in the latest year means a mid-year handover: the new one is whoever
        # was not there the year before.
        previous = history[-2]["peos"] if len(history) > 1 else []
        newcomers = [p for p in latest if not any(_same_person(p, q) for q in previous)]
        current = newcomers[0] if len(newcomers) == 1 else None
    else:
        current = latest[0] if latest else None

    if current is None:
        # Unnamed throughout (single PEO, no names tagged) or ambiguous handover.
        if all(not h["peos"] for h in history):
            return {"ceo_name": None, "precision": "lower_bound", "at_least_since": history[0]["start"]}
        return None

    first_index = len(history) - 1
    while first_index > 0 and any(_same_person(current, p) for p in history[first_index - 1]["peos"]):
        first_index -= 1
    # A change is evidenced only when the year before names a *different* PEO. An unnamed
    # year (AMD, Palantir and Robinhood tag a name only for the latest year) says nothing.
    if first_index > 0 and not history[first_index - 1]["peos"]:
        return {"ceo_name": current, "precision": "lower_bound", "at_least_since": history[0]["start"]}
    if first_index == 0 and len(history[0]["peos"]) == 1:
        return {"ceo_name": current, "precision": "lower_bound", "at_least_since": history[0]["start"]}
    first_year = history[first_index]
    if len(first_year["peos"]) > 1:
        # Handover year: the appointment fell somewhere inside it. Its end is used, so TSR
        # never credits the predecessor (Niccol started 9 Sep 2024, FY2024 ended 29 Sep).
        return {"ceo_name": current, "precision": "handover_year_end", "ceo_start_date": first_year["end"]}
    return {"ceo_name": current, "precision": "fiscal_year", "ceo_start_date": first_year["start"]}


def _same_person(a: str, b: str) -> bool:
    """Same PEO under two spellings ("Dr. Su" / "Lisa Su"): compare surnames."""
    last = lambda n: _letters((n.replace(".", " ").split() or [""])[-1])  # noqa: E731
    return _letters(a) == _letters(b) or (bool(last(a)) and last(a) == last(b))


def _letters(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())


def _days(start: str, end: str) -> int:
    from datetime import date

    try:
        return (date.fromisoformat(end) - date.fromisoformat(start)).days
    except ValueError:
        return 0


def fetch_ceo_tenure_sec(ticker: str, cache_dir: Path | None = None) -> dict[str, Any] | None:
    directory = cache_dir if cache_dir is not None else SEC_CACHE_DIR
    cache = directory / f"{ticker.upper()}_ceo_tenure.json"
    if cache.exists():
        try:
            payload = json.loads(cache.read_text(encoding="utf-8"))
            if (time.time() - float(payload.get("fetched_at", 0))) / 86400.0 <= CACHE_MAX_AGE_DAYS:
                return payload.get("tenure")
        except (OSError, ValueError):
            pass
    tenure = _fetch_uncached(ticker)
    try:
        directory.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"fetched_at": time.time(), "tenure": tenure}), encoding="utf-8")
    except OSError:
        pass
    return tenure


def _fetch_uncached(ticker: str) -> dict[str, Any] | None:
    cik = get_cik_for_ticker(ticker)
    if not cik:
        return None
    resp = _get_with_backoff(f"https://data.sec.gov/submissions/CIK{cik}.json")
    if resp is None or resp.status_code != 200:
        return None
    recent = resp.json().get("filings", {}).get("recent", {})
    try:
        i = recent.get("form", []).index("DEF 14A")
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
        derived = derive_ceo_start(parse_peo_history(doc.content))
    except ET.ParseError:
        return None
    if derived:
        derived["source"] = f"DEF 14A pay-versus-performance, filed {recent['filingDate'][i]}"
    return derived
