#!/usr/bin/env python3
"""
Regenerate ``config/ticker_aliases.json`` — the committed company-name/alias map.

Why this file exists: the chatbot's LLM extractor used to "correct" symbols it did
not recognise. A user asking about "mhci, tlk and brbk" got ``[MCHI, TLT, BRK-B]``
back — and ``TLT`` (20-year Treasuries) is not a typo of ``TLK`` (Telkom
Indonesia), it is a different asset that then resolved cleanly and was queried.
A committed lookup table replaces that guess with a deterministic answer, and
anything not in the table is reported as not-in-universe rather than swapped.

The generated file is authoritative at runtime; nothing here runs during a chat
turn. Re-run this script when the traded universe changes.

Sources, in precedence order:
  1. hand-curated seeds (``chatbot/tools/market_price_tool.NZ_TICKER_ALIASES``)
  2. SEC ``company_tickers.json`` — keyless, covers US registrants
  3. yfinance ``longName``/``shortName`` — the only wired source covering
     ``.TO/.NZ/.NS/.KS/.HK`` and ETFs

Usage:
    .venv/bin/python scripts/update_ticker_aliases.py [--dry-run] [--offline]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

OUTPUT_PATH = _ROOT / "config" / "ticker_aliases.json"
SEC_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"

# Symbols that are not companies — indices, FX pairs, crypto. They get a symbol
# entry with no name so the resolver still knows they are real.
_NON_COMPANY_RE = re.compile(r"^\^|=X$|-USD$")

# Stripped when deriving aliases: "Alphabet Inc." -> "alphabet".
_CORPORATE_SUFFIXES = (
    "incorporated", "inc", "corporation", "corp", "company", "co",
    "limited", "ltd", "plc", "holdings", "holding", "group", "sa", "nv",
    "ag", "se", "spa", "ab", "asa", "oyj", "class a", "class b", "class c",
    "the", "trust", "fund", "etf",
)


# Common usage that no official name yields. "Alphabet Inc." never produces
# "google"; "BERKSHIRE HATHAWAY INC" never produces "brkb". Keep this list short
# and obvious — it is a vocabulary aid, not a place to guess at typos.
_CURATED_ALIASES: Dict[str, List[str]] = {
    "GOOG": ["google", "googl"],
    "BRK-B": ["brkb", "brk b", "brk.b"],
    "META": ["facebook"],
    "^GSPC": ["s&p", "s&p 500", "sp500", "spx"],
    "^NDX": ["nasdaq 100", "ndx"],
    "^DJI": ["dow", "dow jones"],
    "^VIX": ["vix"],
    "BTC-USD": ["bitcoin", "btc"],
    "ETH-USD": ["ethereum", "eth"],
}


def _normalize(text: str) -> str:
    """Lowercase, drop punctuation, collapse whitespace. Used for alias keys."""
    out = re.sub(r"[^a-z0-9\s]", " ", str(text).lower())
    return re.sub(r"\s+", " ", out).strip()


def _derive_aliases(symbol: str, name: Optional[str]) -> List[str]:
    """Aliases a person would plausibly type, derived from the official name."""
    aliases: set[str] = set()
    base = symbol.split(".")[0].lower()
    if base and base != symbol.lower():
        aliases.add(base)  # "FPH" for "FPH.NZ"
    if not name:
        return sorted(aliases)

    norm = _normalize(name)
    if norm:
        aliases.add(norm)
    words = norm.split()
    while words and words[-1] in _CORPORATE_SUFFIXES:
        words.pop()
    trimmed = " ".join(words)
    if trimmed and trimmed != norm:
        aliases.add(trimmed)
    # First word only, when it is distinctive enough to stand alone ("berkshire").
    if words and len(words[0]) >= 5 and words[0] not in _CORPORATE_SUFFIXES:
        aliases.add(words[0])
    return sorted(a for a in aliases if a)


def _load_universe() -> List[str]:
    from chatbot.data_processor import DataProcessor

    return sorted(DataProcessor().get_available_tickers())


def _seed_aliases() -> Dict[str, List[str]]:
    """Hand-curated NZ names already used by Deep Research — keep both paths in step."""
    try:
        from chatbot.tools.market_price_tool import NZ_TICKER_ALIASES

        out: Dict[str, List[str]] = {}
        for alias, symbol in NZ_TICKER_ALIASES.items():
            out.setdefault(str(symbol).upper(), []).append(_normalize(alias))
        return out
    except Exception as exc:  # pragma: no cover - seeds are a nicety, not required
        print(f"  ! could not load NZ seeds: {exc}")
        return {}


def _fetch_sec_names() -> Dict[str, str]:
    """SEC ticker -> official title. Keyless; US registrants only."""
    import requests

    headers = {"User-Agent": "MindWealth research contact@mindwealth.co"}
    try:
        resp = requests.get(SEC_TICKER_MAP_URL, headers=headers, timeout=30)
        resp.raise_for_status()
        raw = resp.json()
    except Exception as exc:
        print(f"  ! SEC fetch failed: {exc}")
        return {}
    values = raw.values() if isinstance(raw, dict) else raw
    out: Dict[str, str] = {}
    for entry in values:
        try:
            out[str(entry["ticker"]).upper()] = str(entry["title"]).strip()
        except (KeyError, TypeError):
            continue
    return out


def _fetch_yfinance_names(symbols: List[str], batch: int = 20) -> Dict[str, str]:
    """yfinance longName/shortName. Covers suffixed symbols and ETFs."""
    try:
        import yfinance as yf
    except Exception as exc:
        print(f"  ! yfinance unavailable: {exc}")
        return {}

    out: Dict[str, str] = {}
    for i in range(0, len(symbols), batch):
        chunk = symbols[i : i + batch]
        try:
            tickers = yf.Tickers(" ".join(chunk))
            for sym in chunk:
                try:
                    info = tickers.tickers[sym].info or {}
                    name = info.get("longName") or info.get("shortName")
                    if name:
                        out[sym] = str(name).strip()
                except Exception:
                    continue
        except Exception as exc:
            print(f"  ! yfinance batch {i // batch} failed: {exc}")
        time.sleep(0.5)  # be polite; this script is not latency-sensitive
    return out


def build_map(offline: bool = False) -> dict:
    universe = _load_universe()
    print(f"universe: {len(universe)} symbols")

    seeds = _seed_aliases()
    print(f"seeded aliases for {len(seeds)} symbol(s) from NZ_TICKER_ALIASES")

    names: Dict[str, str] = {}
    if not offline:
        sec = _fetch_sec_names()
        names.update({s: sec[s] for s in universe if s in sec})
        print(f"SEC names: {len(names)}/{len(universe)}")

        missing = [
            s for s in universe
            if s not in names and not _NON_COMPANY_RE.search(s)
        ]
        yf_names = _fetch_yfinance_names(missing)
        names.update(yf_names)
        print(f"yfinance names: {len(yf_names)} (of {len(missing)} still missing)")

    symbols: Dict[str, dict] = {}
    for sym in universe:
        name = names.get(sym)
        aliases = set(_derive_aliases(sym, name)) | set(seeds.get(sym, []))
        entry: dict = {"aliases": sorted(aliases)}
        if name:
            entry["name"] = name
        if _NON_COMPANY_RE.search(sym):
            entry["kind"] = "non_company"
        symbols[sym] = entry

    for sym, extra in _CURATED_ALIASES.items():
        if sym in symbols:
            merged = set(symbols[sym]["aliases"]) | {_normalize(a) for a in extra}
            symbols[sym]["aliases"] = sorted(a for a in merged if a)

    # An alias that points at more than one symbol is worse than no alias: it is
    # exactly the guess this map exists to remove. "ishares" matches every iShares
    # ETF in the universe, so it is dropped from all of them.
    owners: Dict[str, List[str]] = {}
    for sym, entry in symbols.items():
        for alias in entry["aliases"]:
            owners.setdefault(alias, []).append(sym)
    ambiguous = {a for a, owner_list in owners.items() if len(owner_list) > 1}
    if ambiguous:
        for entry in symbols.values():
            entry["aliases"] = [a for a in entry["aliases"] if a not in ambiguous]
        print(f"dropped {len(ambiguous)} ambiguous alias(es): {sorted(ambiguous)[:8]}")

    named = sum(1 for e in symbols.values() if e.get("name"))
    print(f"named: {named}/{len(symbols)}")
    return {
        "as_of": date.today().isoformat(),
        "generated_by": "scripts/update_ticker_aliases.py",
        "symbol_count": len(symbols),
        "named_count": named,
        "symbols": symbols,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="print summary, do not write")
    parser.add_argument("--offline", action="store_true", help="skip network; derive aliases from symbols only")
    args = parser.parse_args()

    payload = build_map(offline=args.offline)

    # Never let a failed fetch shrink a good committed map.
    if OUTPUT_PATH.exists():
        try:
            existing = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
            if payload["named_count"] < existing.get("named_count", 0) * 0.9:
                print(
                    f"REFUSING to write: named_count would drop "
                    f"{existing.get('named_count')} -> {payload['named_count']}. "
                    "Re-run when the network is healthy."
                )
                return 1
        except (OSError, json.JSONDecodeError):
            pass

    if args.dry_run:
        print(json.dumps({k: v for k, v in payload.items() if k != "symbols"}, indent=2))
        return 0

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT_PATH} ({payload['symbol_count']} symbols, {payload['named_count']} named)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
