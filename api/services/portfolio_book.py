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
        elif book_id == "brokerage":
            self.detail = "book_id=brokerage is not available yet. IBKR integration is pending product spec (Phase 8)."
        elif book_id == "personal":
            self.detail = (
                "book_id=personal is only available on /portfolio/nav and /portfolio/holdings "
                "(it has no Sizer/Risk concept — those are MODEL-book-only pages)."
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
    allow_all_model_books: bool = False,
    allow_personal: bool = False,
) -> tuple[str, str | None]:
    """Validate book_id (and optional MODEL valuation book).

    Returns (book_id, book) where book is set only for model.
    Raises ValueError for bad params, BookUnavailableError for unsupported combos.

    ``allow_all_model_books=True`` — used by ``/portfolio/nav`` when NAV history provider
    can serve base/ssi/cv/enhanced (workbook proxy or nav_engine).
    ``allow_personal=True`` — NAV/Holdings only (Phase 7); personal has no base/ssi/cv/enhanced
    concept (it's a flat user-entered book), so ``book`` stays None for it. Brokerage remains
    unavailable everywhere (IBKR integration deferred — Phase 8).
    """
    bid = normalize_book_id(book_id)
    if bid == "brokerage":
        raise BookUnavailableError(bid)
    if bid == "personal":
        if not allow_personal:
            raise BookUnavailableError(bid)
        return bid, None
    if require_model_book and not book:
        raise ValueError("book is required when book_id=model (base | ssi | cv | enhanced)")
    if book:
        bk = normalize_model_book(book)
        supported = MODEL_VALUATION_BOOKS if allow_all_model_books else _SUPPORTED_MODEL_BOOKS
        if bk not in supported:
            raise BookUnavailableError(bid, bk)
        return bid, bk
    return bid, None


def validate_nav_book_access(book_id: str, book: str | None) -> tuple[str, str | None]:
    """MODEL valuation books allowed on /portfolio/nav when history source is wired.

    ``personal`` is also allowed here (Phase 7) — ``book`` is ignored/None for it.
    """
    bid = normalize_book_id(book_id)
    if bid == "personal":
        return bid, None
    bid, bk = validate_book_access(
        book_id,
        book=book,
        require_model_book=True,
        allow_all_model_books=True,
    )
    assert bk is not None
    return bid, bk


def validate_holdings_book_access(book_id: str, book: str | None) -> tuple[str, str | None]:
    """MODEL valuation books (currently enhanced-only) OR personal (Phase 7) for /portfolio/holdings."""
    bid = normalize_book_id(book_id)
    if bid == "personal":
        return bid, None
    return validate_book_access(book_id, book=book, require_model_book=True)


def validate_model_only(book_id: str = "model") -> str:
    """MODEL-only endpoints (sizer, risk) — book_id must be model."""
    bid = normalize_book_id(book_id)
    if bid != "model":
        raise BookUnavailableError(bid)
    return bid
