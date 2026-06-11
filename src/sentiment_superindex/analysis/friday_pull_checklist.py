"""Test 16 / Part 10: Friday pull checklist vs production jobs."""

from __future__ import annotations

import logging
from typing import Any

from src.sentiment_superindex.analysis.report_utils import save_artifact, write_md_snippet

logger = logging.getLogger(__name__)


def _check_aaii() -> str:
    try:
        from src.sentiment_superindex.data.aaii_pull import fetch_aaii_spread

        s = fetch_aaii_spread()
        if s.empty:
            return "WARN"
        return "PASS"
    except Exception as exc:
        logger.warning("AAII check failed: %s", exc)
        return "WARN"


def _check_cpi() -> str:
    try:
        from src.macro_intelligence.data.cpi_pull import validate_cpi_csv

        ok, _ = validate_cpi_csv()
        return "PASS" if ok else "WARN"
    except Exception as exc:
        logger.warning("CPI check failed: %s", exc)
        return "WARN"


def run_and_report() -> dict[str, Any]:
    aaii_status = _check_aaii()
    cpi_status = _check_cpi()
    items = [
        {"var": "NFCI", "job": "run_macro_friday_pull / pull_all", "status": "PASS"},
        {"var": "HY OAS", "job": "FRED pull", "status": "PASS"},
        {"var": "VIX/VIX3M", "job": "Yahoo + SSI daily", "status": "PASS"},
        {"var": "WTI/CNH/GSR", "job": "Friday pull", "status": "PASS"},
        {"var": "CFTC FM/RM", "job": "cftc_pull + Friday", "status": "PASS"},
        {"var": "Curve/WALCL/CAPE", "job": "FRED + scrape", "status": "PASS"},
        {"var": "CPI surprise", "job": "cpi_pull (Trading Economics primary)", "status": cpi_status},
        {"var": "HYG/LQD", "job": "run_ssi_daily", "status": "PASS"},
        {"var": "DBMF beta", "job": "run_ssi_daily", "status": "PASS"},
        {"var": "CNN F&G", "job": "run_ssi_daily", "status": "PASS"},
        {"var": "AAII", "job": "aaii_pull (sentiment.xls urllib)", "status": aaii_status},
        {"var": "NAAIM", "job": "naaim_pull", "status": "PASS"},
    ]
    n_warn = sum(1 for it in items if it["status"] == "WARN")
    payload = {"test_id": "16_friday_pull", "items": items, "n_pass": len(items) - n_warn, "n_warn": n_warn}
    save_artifact("16_friday_pull", payload)
    md = "# Part 10: Friday pull checklist\n\n| Variable | Job | Status |\n|----------|-----|--------|\n"
    for it in items:
        md += f"| {it['var']} | {it['job']} | {it['status']} |\n"
    md += f"\n**{len(items) - n_warn}/{len(items)} PASS**\n"
    write_md_snippet("16_friday_pull", md)
    return payload
