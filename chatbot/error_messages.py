"""
User-facing error text for chat failures.

The engine used to render ``f"Error processing query: {str(e)}"`` straight into
the chat, so an Anthropic billing failure reached the user verbatim —
provider name, plan wording and the ``request_id`` included:

    Error processing query: Error code: 400 - {'type': 'error', 'error':
    {'type': 'invalid_request_error', 'message': 'Your credit balance is too
    low to access the Anthropic API...'}, 'request_id': 'req_011CdZ...'}

That leaks vendor and account detail to whoever is using the terminal, and it
tells them nothing they can act on. The full exception is still logged and
still stored on the job record for debugging; only the chat bubble changes.
"""

import logging
import re
from typing import Tuple

logger = logging.getLogger(__name__)

GENERIC = (
    "Something went wrong while preparing this answer. The details have been "
    "logged. Please try again — if it keeps happening, flag it to the team."
)

_QUOTA = (
    "The analyst is temporarily unavailable because the language-model service "
    "quota has been exhausted. This is an account-level issue, not a problem "
    "with your question — the team has been notified."
)
_RATE_LIMIT = (
    "The analyst is handling too many requests right now. Please wait a few "
    "seconds and try again."
)
_TIMEOUT = (
    "This answer took longer than the time available. Try narrowing the "
    "question — a specific ticker or a shorter date range usually helps."
)
_AUTH = (
    "The analyst could not authenticate with an upstream service. This is a "
    "configuration issue on our side; the team has been notified."
)
_DATA = (
    "The signal data needed for this question could not be read. The team has "
    "been notified."
)

# Ordered most-specific first: a credit/quota failure is also a 400, and an
# auth failure also mentions "key", so the first match must win.
_PATTERNS: Tuple[Tuple[str, str], ...] = (
    (r"credit balance|insufficient[_ ]quota|quota.*exceed|billing|plans? & billing", _QUOTA),
    (r"rate.?limit|429|too many requests|overloaded|529", _RATE_LIMIT),
    (r"timeout|timed out|deadline exceeded|read timed out", _TIMEOUT),
    (r"authentication|unauthorized|invalid[_ ]api[_ ]key|permission denied|401|403", _AUTH),
    (r"no such file|filenotfound|parsererror|emptydataerror|could not read", _DATA),
)


def user_facing_error(exc: BaseException, *, context: str = "") -> str:
    """
    Map an exception to a message that is safe and useful to show a user.

    The raw exception is logged with a stack trace at ERROR. Nothing from the
    exception text reaches the return value — matching is done on a lowercased
    copy, and every branch returns a fixed string, so a provider message can
    never leak through a partial match.
    """
    detail = f"{type(exc).__name__}: {exc}"
    logger.error(f"Chat failure{f' during {context}' if context else ''}: {detail}", exc_info=True)

    haystack = detail.lower()
    for pattern, message in _PATTERNS:
        if re.search(pattern, haystack):
            return message
    return GENERIC


def safe_error_metadata(exc: BaseException) -> dict:
    """
    Error fields for the job record: sanitized for display, raw for debugging.

    ``error`` is what the UI shows (the Nuxt client renders ``job.error``
    directly), so it must be the safe string. ``error_detail`` keeps the real
    exception for the job JSON on disk and for support.
    """
    return {
        "error": user_facing_error(exc),
        "error_detail": f"{type(exc).__name__}: {exc}",
    }
