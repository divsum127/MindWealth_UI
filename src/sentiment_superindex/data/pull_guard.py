"""Observability for SSI data pulls.

Every SSI input is fetched by a function that returns an empty ``pd.Series`` when its source
is unreachable, unparseable, or has silently changed shape. That is deliberate -- a layer
should degrade rather than crash the nightly job -- but until now those failures were also
*invisible*: ``macro_intelligence/logs/ssi_daily.log`` contained nothing but pandas
``UserWarning``s while NAAIM and ^VIX3M had both been dead for weeks (audit 2026-08-18).

This module does not change any control flow. It only makes the failure legible, in two
places at once:

* ``logging`` -- so the failure lands in ``ssi_daily.log`` where an operator looks first.
* ``data_pull_log`` -- the existing table behind ``retry_cache.log_pull`` /
  ``scripts/export_data_validation.py`` / ``GET /macro/data/freshness``, so a dead feed is
  visible on the site and not only in a log file.

Use ``log_pull_failure`` for an exception and ``log_pull_empty`` for the quieter and more
dangerous case: a request that succeeded but returned nothing usable (HTTP 200 with the
table removed, a delisted ticker, an endpoint that started paginating).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("ssi.pull")


def _record(source_id: str, status: str, error: str) -> None:
    """Write to data_pull_log, never letting bookkeeping break the caller's pull."""
    try:
        from src.macro_intelligence.data.retry_cache import log_pull

        log_pull(source_id, status, error=error)
    except Exception:  # pragma: no cover - the DB must never take a pull down
        logger.debug("could not record %s status for %s", status, source_id, exc_info=True)


def log_pull_failure(source_id: str, exc: BaseException, *, note: str | None = None) -> None:
    """An SSI pull raised. Log it and record an ERROR row."""
    detail = f"{type(exc).__name__}: {exc}"
    if note:
        detail = f"{detail} ({note})"
    logger.warning("SSI pull failed: %s -- %s", source_id, detail)
    _record(source_id, "ERROR", detail)


def log_pull_empty(source_id: str, *, note: str) -> None:
    """An SSI pull succeeded but returned nothing usable -- the silent-death case."""
    logger.warning("SSI pull returned no data: %s -- %s", source_id, note)
    _record(source_id, "EMPTY", note)


def log_pull_ok(source_id: str, rows: int, last_date: Any = None) -> None:
    """An SSI pull returned data. Debug-level: the interesting events are the two above."""
    logger.debug("SSI pull ok: %s rows=%s last=%s", source_id, rows, last_date)
