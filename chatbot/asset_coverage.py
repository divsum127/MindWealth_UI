"""
Guards for two ways a ticker can go wrong between the question and the answer.

**Substitution** — the extractor is an LLM and will happily "correct" a symbol
it does not recognise. A real case: "mhci, tlk and brbk" came back as
``[MCHI, TLT, BRK-B]``. ``TLK`` is not in the universe and ``TLT`` is an
unrelated asset (20-year Treasuries, not Telkom Indonesia). The answer happened
to keep them apart, but nothing forced it to.

**Omission** — twice now the model has been handed rows for a symbol and simply
not mentioned it. "recent exit levels and entry levels for google and nvda"
fetched both (``assets: [GOOG, NVDA]``, 17 rows) and answered about NVDA only,
stating there were no GOOG signals when GOOG had 15 open entries. A second,
identical run covered both. Silent and intermittent, which is worse than an
error: the user cannot tell the answer is incomplete.

Neither guard drops or edits data. One adds an instruction, the other appends a
factual note when a symbol was retrieved but never discussed.
"""

import logging
import re
from typing import Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)


def _base_symbol(symbol: str) -> str:
    """``FPH.NZ`` → ``FPH``; ``BRK-B`` → ``BRK-B`` (only exchange suffixes split)."""
    return str(symbol).split(".")[0].strip()


def _mentions(text: str, symbol: str) -> bool:
    """
    Whether ``text`` refers to ``symbol``.

    Matches the full symbol or its base as a standalone token, case-insensitively.
    ``re.escape`` matters: real symbols contain ``.``, ``-`` and ``^`` (``BRK-B``,
    ``^TNX``, ``000660.KS``), all of which are regex metacharacters.
    """
    if not text or not symbol:
        return False
    haystack = text.lower()
    for candidate in {str(symbol).lower(), _base_symbol(symbol).lower()}:
        if not candidate:
            continue
        # \b is unreliable next to '.', '-' and '^', so bound on non-alphanumerics.
        if re.search(rf"(?<![a-z0-9]){re.escape(candidate)}(?![a-z0-9])", haystack):
            return True
    return False


def inferred_assets(user_message: str, assets: Optional[Sequence[str]]) -> List[str]:
    """
    Symbols the pipeline produced that the user did not literally type.

    Covers both legitimate inference ("google" → ``GOOG``, "brbk" → ``BRK-B``)
    and unwanted substitution ("tlk" → ``TLT``). The two are indistinguishable
    here, so nothing is dropped — the caller asks the model to state the mapping
    and to flag anything it cannot map.
    """
    if not assets or not user_message:
        return []
    return [a for a in assets if a and not _mentions(user_message, a)]


def _pair_tokens_to_symbols(
    user_message: str,
    symbols: Sequence[str],
    available: Optional[Sequence[str]] = None,
) -> Dict[str, str]:
    """
    Which word in the question produced each symbol, e.g. ``{"brbk": "BRK-B"}``.

    Without the pairing the model was told only that ``BRK-B`` was "inferred" and
    had to guess where it came from — it decided the user's ``brbk`` was a
    separate, untracked ticker and reported it as such alongside BRK-B's own data.
    """
    pairs: Dict[str, str] = {}
    if not user_message or not symbols:
        return pairs
    try:
        from .ticker_resolver import _message_tokens, resolve_ticker
    except Exception:  # pragma: no cover - pairing is a nicety, never fatal
        return pairs

    wanted = {str(s).upper(): str(s) for s in symbols if s}
    universe = list(available) if available else list(wanted.values())
    for token in _message_tokens(user_message):
        try:
            hit = resolve_ticker(token, universe)
        except Exception:
            continue
        if hit and hit.upper() in wanted and token.lower() != hit.lower():
            pairs.setdefault(token.lower(), wanted[hit.upper()])
    return pairs


def build_ticker_mapping_note(
    user_message: str,
    assets: Optional[Sequence[str]],
    available: Optional[Sequence[str]] = None,
) -> Optional[str]:
    """Prompt fragment telling the model to be explicit about inferred symbols."""
    inferred = inferred_assets(user_message, assets)
    if not inferred:
        return None

    pairs = _pair_tokens_to_symbols(user_message, inferred, available)
    lines = [
        "=== TICKER RESOLUTION NOTICE ===",
        f"These symbols were inferred from the question rather than typed verbatim: "
        f"{', '.join(inferred)}.",
    ]
    if pairs:
        lines.append(
            "Resolved from the user's own wording: "
            + ", ".join(f"\"{token}\" → {symbol}" for token, symbol in sorted(pairs.items()))
            + ". Treat these as the SAME asset — do not also report the user's spelling "
            "as a separate untracked ticker."
        )
    lines += [
        "- State the mapping explicitly the first time you use one "
        "(e.g. \"brbk → BRK-B\", \"google → GOOG\").",
        "- If a symbol the user typed is NOT in the MindWealth universe, say so "
        "plainly and do NOT present another symbol's rows under that name. A "
        "near-miss on a ticker is a different company, not a typo to be fixed "
        "silently.",
    ]
    return "\n".join(lines)


def uncovered_assets(
    answer: str,
    assets: Optional[Sequence[str]],
    rows_by_asset: Optional[Dict[str, int]] = None,
    skip: Optional[Sequence[str]] = None,
) -> List[str]:
    """
    Requested symbols that never appear in the answer.

    ``skip`` excludes inferred symbols: if the user typed "tlk" and the
    extractor guessed ``TLT``, an answer that correctly ignores ``TLT`` must not
    be flagged for omitting it. ``rows_by_asset``, when given, restricts the
    check to symbols that actually had data — a symbol with zero rows is
    legitimately absent.
    """
    if not assets or not answer:
        return []
    skip_set = {str(s).upper() for s in (skip or [])}
    missing: List[str] = []
    for asset in assets:
        if not asset or str(asset).startswith("."):  # region filters like ".NZ"
            continue
        if str(asset).upper() in skip_set:
            continue
        if rows_by_asset is not None and rows_by_asset.get(asset, 0) <= 0:
            continue
        if not _mentions(answer, asset):
            missing.append(asset)
    return missing


def coverage_note(missing: Sequence[str]) -> str:
    """Advisory appended to an answer that silently dropped a requested symbol."""
    symbols = ", ".join(missing)
    plural = "s were" if len(missing) > 1 else " was"
    return (
        f"\n\n---\n\n> **Coverage note:** {symbols} — this symbol{plural} part of your "
        "question and present in the retrieved signal data, but not covered above. "
        "Ask again naming it directly to get the detail."
    )


def build_unresolved_ticker_note(unresolved: Sequence[str]) -> Optional[str]:
    """
    Prompt fragment naming symbols the user asked about that we do not track.

    ``unified_extractor`` has always produced this list and nothing ever read it,
    so an untracked ticker was simply absent from the answer — or, worse, quietly
    replaced by whatever the model thought the user meant. Stating it plainly is
    the whole point: "TLK is not in the MindWealth universe" is a useful answer,
    "here are TLT's numbers" is a wrong one.
    """
    symbols = [str(s).strip() for s in (unresolved or []) if str(s).strip()]
    if not symbols:
        return None
    return (
        "=== TICKERS NOT IN THE MINDWEALTH UNIVERSE ===\n"
        f"{', '.join(symbols)}\n"
        "- Say plainly that we do not track these, giving each its own line.\n"
        "- Do NOT substitute a similarly spelled symbol, and do NOT present another "
        "asset's rows under one of these names. A near-miss ticker is a different "
        "company, not a typo to be corrected.\n"
        "- Answer normally for every other symbol in the question."
    )
