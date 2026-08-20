"""
Resolve user-typed tickers to the canonical symbols stored in the signal CSVs.

Users type ``FPH`` and ``MFT``; the signal store holds ``FPH.NZ`` and
``MFT.NZ``. Filtering is an exact ``isin`` match (see
``smart_data_fetcher._filter_df_by_assets``), so an unresolved bare symbol
silently returns zero rows and the answer degrades to "no data" — or, worse,
to a web-only answer that looks fine but never consulted the model.

Suffixes in the live universe: ``.NZ .TO .NS .KS .HK .SI .PA .F``, plus FX
(``=X``), crypto (``-USD``) and index (``^``) forms that have no base/suffix
split at all.
"""

import json
import logging
import os
import re
from functools import lru_cache
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

_ALIAS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config",
    "ticker_aliases.json",
)


def _normalize_alias(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace — must match the generator."""
    out = re.sub(r"[^a-z0-9\s]", " ", str(text).lower())
    return re.sub(r"\s+", " ", out).strip()


@lru_cache(maxsize=1)
def _alias_index() -> Dict[str, str]:
    """
    Normalized company name / alias -> canonical symbol.

    Built from ``config/ticker_aliases.json`` (regenerate with
    ``scripts/update_ticker_aliases.py``). The generator already drops any alias
    owned by more than one symbol, so a hit here is unambiguous by construction.

    A missing or unreadable file is not fatal: resolution degrades to the
    symbol-only behaviour that predates the map. It must never degrade to a
    guess — that is the failure this map exists to remove ("tlk" -> TLT).
    """
    try:
        with open(_ALIAS_FILE, encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(f"Ticker alias map unavailable ({exc}); symbol-only resolution")
        return {}

    index: Dict[str, str] = {}
    for symbol, entry in (payload.get("symbols") or {}).items():
        if not isinstance(entry, dict):
            continue
        for alias in entry.get("aliases") or []:
            key = _normalize_alias(alias)
            if key:
                index.setdefault(key, symbol)
        name = entry.get("name")
        if name:
            index.setdefault(_normalize_alias(name), symbol)
    return index


def _base_symbol(ticker: str) -> str:
    """``FPH.NZ`` → ``FPH``. Symbols without a dot are returned unchanged."""
    return ticker.split(".", 1)[0]


def _build_index(available: Iterable[str]) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
    """Map upper-cased exact symbols and base symbols to canonical spellings."""
    exact: Dict[str, str] = {}
    by_base: Dict[str, List[str]] = {}
    for symbol in available or []:
        if not symbol:
            continue
        canonical = str(symbol).strip()
        if not canonical:
            continue
        exact.setdefault(canonical.upper(), canonical)
        by_base.setdefault(_base_symbol(canonical.upper()), []).append(canonical)
    return exact, by_base


def resolve_ticker(raw: str, available: Sequence[str]) -> Optional[str]:
    """
    Resolve one user-typed ticker to its canonical symbol.

    Returns ``None`` when the symbol is unknown or ambiguous (the same base
    listed on two exchanges), so callers can tell the user instead of silently
    filtering to nothing.
    """
    exact, by_base = _build_index(available)
    return _resolve_one(raw, exact, by_base)


def _resolve_one(
    raw: str,
    exact: Dict[str, str],
    by_base: Dict[str, List[str]],
) -> Optional[str]:
    if raw is None:
        return None
    candidate = str(raw).strip().upper()
    if not candidate:
        return None

    # 1. Exact match (case-insensitive) — already canonical, e.g. "FPH.NZ".
    if candidate in exact:
        return exact[candidate]

    # 2. Company name or curated alias, e.g. "google" → "GOOG", "brkb" → "BRK-B".
    #    Exact lookups only — no fuzzy or nearest-match matching, because that is
    #    precisely how "tlk" became "TLT" (a different asset) in the first place.
    alias_hit = _alias_index().get(_normalize_alias(raw))
    if alias_hit and alias_hit.upper() in exact:
        return exact[alias_hit.upper()]

    # 3. Adjacent-transposition typo, e.g. "mhci" → "MCHI", "brbk" → "BRK-B".
    #    Deliberately transposition-ONLY: swapping two neighbouring characters is
    #    a slip of the fingers, while substituting one character turns a ticker
    #    into a different company. "tlk" -> "tlt" is a substitution and must stay
    #    unresolved; it was exactly that guess which answered a Telkom question
    #    with 20-year Treasury data.
    transposed = _transposition_match(candidate, exact, by_base)
    if transposed:
        return transposed

    # 4. Bare symbol → unique suffixed match, e.g. "MFT" → "MFT.NZ".
    if "." not in candidate:
        matches = by_base.get(candidate, [])
        unique = sorted(set(matches))
        if len(unique) == 1:
            return unique[0]
        if len(unique) > 1:
            logger.info(
                f"Ticker '{candidate}' is ambiguous across exchanges {unique} — "
                "leaving unresolved"
            )
            return None

    return None


def resolve_tickers(
    tickers: Sequence[str],
    available: Sequence[str],
) -> Tuple[List[str], List[str]]:
    """
    Resolve a list of user-typed tickers.

    Returns ``(resolved, unresolved)``. ``resolved`` is de-duplicated and holds
    canonical symbols; ``unresolved`` holds the original spellings that are not
    in the MindWealth universe (e.g. ``FRE``, which does not exist — the real
    Freightways symbol is ``FRW.NZ``) or that are ambiguous. Callers should
    surface ``unresolved`` to the user rather than dropping it.
    """
    if not tickers:
        return [], []
    if not available:
        # No universe loaded — pass through upper-cased so behaviour matches the
        # previous code path rather than filtering everything out.
        return [str(t).strip().upper() for t in tickers if t], []

    exact, by_base = _build_index(available)
    resolved: List[str] = []
    unresolved: List[str] = []
    for raw in tickers:
        if not raw:
            continue
        match = _resolve_one(raw, exact, by_base)
        if match is None:
            unresolved.append(str(raw).strip().upper())
        elif match not in resolved:
            resolved.append(match)

    if unresolved:
        logger.warning(f"Unresolved tickers (not in MindWealth universe): {unresolved}")
    return resolved, unresolved


def _message_tokens(user_message: str) -> List[str]:
    """Candidate ticker-ish tokens and 1-3 word phrases from the raw question."""
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9.\-^=]*", str(user_message or ""))
    tokens = list(words)
    lowered = [w.lower() for w in words]
    for size in (2, 3):
        for i in range(len(lowered) - size + 1):
            tokens.append(" ".join(lowered[i : i + size]))
    return tokens


def verify_extracted_symbols(
    user_message: str,
    symbols: Sequence[str],
    available: Sequence[str],
) -> Tuple[List[str], List[str]]:
    """
    Keep only symbols the question actually justifies; return the rest as guesses.

    The extractor is an LLM and will "correct" a symbol it does not recognise.
    "mhci, tlk and brbk" came back as ``[MCHI, TLT, BRK-B]`` — and because ``TLT``
    is a real universe symbol, a membership check alone happily lets it through.
    Provenance is the test that catches it: a symbol survives only when the
    message contains the symbol itself (or its base), or a token/phrase that the
    committed alias map maps to exactly that symbol.

    So ``"google"`` keeps ``GOOG`` (alias hit) while ``"tlk"`` drops ``TLT``
    (nothing in the message points there). Dropped symbols are returned so the
    caller can tell the user the ticker is not tracked, rather than answering
    about a different company.
    """
    if not symbols:
        return [], []
    if not user_message:
        return list(symbols), []

    haystack = str(user_message).lower()
    alias_index = _alias_index()
    exact, by_base = _build_index(available)
    token_symbols = set()
    for token in _message_tokens(user_message):
        hit = alias_index.get(_normalize_alias(token))
        if hit:
            token_symbols.add(hit.upper())
            continue
        # Also accept what the resolver itself would reach from this token —
        # suffix completion ("mft" -> MFT.NZ) and adjacent-transposition typos
        # ("mhci" -> MCHI). Without this the resolver and the provenance check
        # disagree and a correctly-recovered typo gets thrown away.
        resolved = _resolve_one(token, exact, by_base)
        if resolved:
            token_symbols.add(resolved.upper())

    kept: List[str] = []
    guessed: List[str] = []
    for symbol in symbols:
        if not symbol:
            continue
        upper = str(symbol).upper()
        literal = re.search(
            rf"(?<![a-z0-9]){re.escape(upper.lower())}(?![a-z0-9])", haystack
        ) or re.search(
            rf"(?<![a-z0-9]){re.escape(_base_symbol(upper).lower())}(?![a-z0-9])", haystack
        )
        if literal or upper in token_symbols:
            kept.append(symbol)
        else:
            guessed.append(symbol)

    if guessed:
        logger.warning(
            f"Dropped extracted symbol(s) with no support in the question: {guessed}"
        )
    return kept, guessed


def _transposition_match(
    candidate: str,
    exact: Dict[str, str],
    by_base: Dict[str, List[str]],
) -> Optional[str]:
    """
    Resolve a symbol typed with two adjacent characters swapped.

    Only adjacent swaps are considered, and only when exactly one universe symbol
    is reached — anything ambiguous stays unresolved. Punctuation is ignored on
    both sides so "brbk" can reach "BRK-B".

    Substitutions, insertions and deletions are NOT handled on purpose: they are
    how a real ticker becomes a different real ticker.
    """
    plain = re.sub(r"[^A-Z0-9]", "", str(candidate).upper())
    if len(plain) < 4:  # too short to distinguish a slip from a different symbol
        return None

    lookup: Dict[str, set] = {}
    for key, canonical in exact.items():
        lookup.setdefault(re.sub(r"[^A-Z0-9]", "", key), set()).add(canonical)
    for base, canonicals in by_base.items():
        lookup.setdefault(re.sub(r"[^A-Z0-9]", "", base), set()).update(canonicals)

    hits: set = set()
    for i in range(len(plain) - 1):
        swapped = plain[:i] + plain[i + 1] + plain[i] + plain[i + 2:]
        if swapped == plain:
            continue
        hits.update(lookup.get(swapped, set()))

    if len(hits) == 1:
        match = next(iter(hits))
        logger.info(f"Ticker '{candidate}' resolved to '{match}' via adjacent transposition")
        return match
    if len(hits) > 1:
        logger.info(f"Transposition of '{candidate}' is ambiguous {sorted(hits)} — unresolved")
    return None
