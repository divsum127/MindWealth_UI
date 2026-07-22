"""Portfolio book_id / valuation-book validation (HANDOFF §2)."""

from __future__ import annotations

BOOK_IDS: frozenset[str] = frozenset({"model", "brokerage", "personal"})
MODEL_VALUATION_BOOKS: frozenset[str] = frozenset({"base", "ssi", "cv", "enhanced"})

# Only enhanced is wired until Ahil A1 four-book replay ships.
_SUPPORTED_MODEL_BOOKS: frozenset[str] = frozenset({"enhanced"})


class BookUnavailableError(Exception):
    """Valid book_id/book combo that is not yet implemented."""

    def __init__(self, book_id: str, book: str | None = None, detail: str | None = None) -> None:
        self.book_id = book_id
        self.book = book
        if detail:
            self.detail = detail
        elif book_id in ("brokerage", "personal"):
            self.detail = (
                f"book_id={book_id} is not available yet. "
                f"{'IBKR integration' if book_id == 'brokerage' else 'Personal holdings persistence'} "
                "is pending product spec."
            )
        elif book:
            self.detail = (
                f"book={book} is not available yet. Four-book attribution (Ahil A1) "
                "must complete before base/ssi/cv variants are served."
            )
        else:
            self.detail = f"book_id={book_id} is not available."
        super().__init__(self.detail)


def normalize_book_id(book_id: str) -> str:
    bid = (book_id or "").strip().lower()
    if bid not in BOOK_IDS:
        raise ValueError(
            f"Invalid book_id '{book_id}'. Must be one of: model | brokerage | personal"
        )
    return bid


def normalize_model_book(book: str) -> str:
    bk = (book or "").strip().lower()
    if bk not in MODEL_VALUATION_BOOKS:
        raise ValueError(
            f"Invalid book '{book}'. Must be one of: base | ssi | cv | enhanced"
        )
    return bk


def validate_book_access(
    book_id: str,
    *,
    book: str | None = None,
    require_model_book: bool = False,
) -> tuple[str, str | None]:
    """Validate book_id (and optional MODEL valuation book).

    Returns (book_id, book) where book is set only for model.
    Raises ValueError for bad params, BookUnavailableError for unsupported combos.
    """
    bid = normalize_book_id(book_id)
    if bid in ("brokerage", "personal"):
        raise BookUnavailableError(bid)
    if require_model_book and not book:
        raise ValueError("book is required when book_id=model (base | ssi | cv | enhanced)")
    if book:
        bk = normalize_model_book(book)
        if bk not in _SUPPORTED_MODEL_BOOKS:
            raise BookUnavailableError(bid, bk)
        return bid, bk
    return bid, None


def validate_model_only(book_id: str = "model") -> str:
    """MODEL-only endpoints (sizer, risk) — book_id must be model."""
    bid = normalize_book_id(book_id)
    if bid != "model":
        raise BookUnavailableError(bid)
    return bid
