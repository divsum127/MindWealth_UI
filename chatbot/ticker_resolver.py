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

import logging
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)


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

    # 2. Bare symbol → unique suffixed match, e.g. "MFT" → "MFT.NZ".
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
