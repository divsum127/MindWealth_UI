#!/usr/bin/env python3
"""Fetch AAII sentiment.xls / sent_results for GitHub Actions (non-datacenter IP).

Writes macro_intelligence/data/aaii_sentiment.xls and aaii_sentiment.csv.
Exits 0 when at least one row is parsed; 1 when all fetch paths fail.
"""

from __future__ import annotations

import argparse
import io
import logging
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from src.config_paths import MACRO_INTEL_DATA_DIR
from src.sentiment_superindex.data.aaii_pull import (
    AAII_RESULTS_URL,
    AAII_URL,
    CACHE_CSV,
    CACHE_XLS,
    _download_xls,
    _fetch_aaii_bytes,
    _parse_sent_results_html,
    _read_aaii_excel,
    _scrape_sent_results_live,
)
from src.sentiment_superindex.data.scraper_utils import is_excel_content, save_cached_series

logger = logging.getLogger(__name__)

BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _urllib_get(url: str, *, referer: str | None = None, timeout: int = 45) -> bytes | None:
    req = urllib.request.Request(url)
    for k, v in BROWSER.items():
        req.add_header(k, v)
    if referer:
        req.add_header("Referer", referer)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as exc:
        logger.warning("urllib fetch failed %s: %s", url, exc)
        return None


def _fetch_xls_urllib() -> tuple[pd.Series, str]:
    content = _urllib_get(AAII_URL, referer=AAII_RESULTS_URL)
    if not content or not is_excel_content(content):
        return pd.Series(dtype=float), "aaii_urllib_xls_fail"
    series = _read_aaii_excel(io.BytesIO(content))
    if series.empty:
        return series, "aaii_urllib_xls_invalid"
    CACHE_XLS.parent.mkdir(parents=True, exist_ok=True)
    CACHE_XLS.write_bytes(content)
    return series, "aaii_urllib_xls"


def _fetch_sent_results_urllib() -> tuple[pd.Series, str]:
    content = _urllib_get(AAII_RESULTS_URL, referer=AAII_URL)
    if not content:
        return pd.Series(dtype=float), "aaii_urllib_html_fail"
    series = _parse_sent_results_html(content.decode("utf-8", errors="replace"))
    return series, "aaii_urllib_html" if not series.empty else "aaii_urllib_html_empty"


def _fetch_survey_datachart() -> tuple[pd.Series, str]:
    """Parse dataChart5 from sentimentsurvey page (52-week history)."""
    content = _urllib_get("https://www.aaii.com/sentimentsurvey", referer="https://www.aaii.com/")
    if not content:
        return pd.Series(dtype=float), "aaii_datachart_fail"
    html = content.decode("utf-8", errors="replace")
    match = re.search(r"var\s+dataChart5\s*=\s*(\[[\s\S]*?\]);", html)
    if not match:
        return pd.Series(dtype=float), "aaii_datachart_missing"
    try:
        import json

        rows = json.loads(match.group(1))
    except json.JSONDecodeError:
        return pd.Series(dtype=float), "aaii_datachart_invalid"
    points: list[tuple[pd.Timestamp, float]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        try:
            dt = pd.to_datetime(item.get("date_") or item.get("date"))
            bull = float(item.get("bullish", 0))
            bear = float(item.get("bearish", 0))
            spread = float(item.get("spread", bull - bear))
            if spread <= 1.5 and abs(spread) <= 1.5:
                spread *= 100.0
            points.append((dt, spread))
        except (TypeError, ValueError):
            continue
    if not points:
        return pd.Series(dtype=float), "aaii_datachart_empty"
    s = pd.Series({d: v for d, v in points}).sort_index()
    s.name = "aaii_spread"
    return s.astype(float), "aaii_datachart"


def collect_aaii_series() -> tuple[pd.Series, str]:
    """Try all free fetch paths; prefer full-history XLS."""
    from src.sentiment_superindex.data.scraper_utils import merge_series

    merged = pd.Series(dtype=float)
    source = "aaii_none"

    for fetcher, label in (
        (_download_xls, "curl"),
        (_fetch_xls_urllib, "urllib_xls"),
        (_scrape_sent_results_live, "curl_html"),
        (_fetch_sent_results_urllib, "urllib_html"),
        (_fetch_survey_datachart, "datachart"),
    ):
        try:
            series, tag = fetcher()
        except Exception as exc:
            logger.warning("%s failed: %s", label, exc)
            continue
        merged = merge_series(merged, series)
        if not series.empty and (merged.empty or len(series) >= len(merged) * 0.5):
            source = tag
        logger.info("%s -> %s rows (tag=%s)", label, len(series), tag)

    if merged.empty:
        content, _ = _fetch_aaii_bytes(AAII_URL)
        if content and is_excel_content(content):
            merged = _read_aaii_excel(io.BytesIO(content))
            source = "aaii_bytes_xls"
    return merged, source


def write_outputs(series: pd.Series) -> None:
    MACRO_INTEL_DATA_DIR.mkdir(parents=True, exist_ok=True)
    save_cached_series(series, CACHE_CSV, value_col="spread")
    if CACHE_XLS.exists():
        logger.info("XLS cache: %s (%s bytes)", CACHE_XLS, CACHE_XLS.stat().st_size)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Sync AAII sentiment to macro_intelligence/data/")
    parser.add_argument("--dry-run", action="store_true", help="Fetch only; do not write files")
    args = parser.parse_args()

    series, source = collect_aaii_series()
    if series.empty:
        logger.error("AAII sync failed: no data from any source")
        return 1

    latest = series.index[-1]
    logger.info(
        "AAII sync OK: %s rows, source=%s, latest=%s spread=%.2f",
        len(series),
        source,
        latest.date() if hasattr(latest, "date") else latest,
        float(series.iloc[-1]),
    )
    if not args.dry_run:
        write_outputs(series)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
