"""Monthly Part H combo discovery pipeline (replaces threshold sweep scaffold)."""

from __future__ import annotations

import json
from datetime import datetime

from src.macro_intelligence.analysis.combo_discovery_pipeline import (
    run_combo_discovery_pipeline,
    write_pipeline_artifacts,
)
from src.macro_intelligence.db.connection import get_connection
from src.macro_intelligence.db.migrate import migrate_db
from src.macro_intelligence.engine.forward_returns import backfill_extended_returns, backfill_forward_returns


def run_monthly_review(*, use_claude: bool = False, write_report: bool = True) -> dict:
    """Run full 298-combo discovery pipeline and log results."""
    migrate_db()
    backfill_forward_returns(log_every=0)
    backfill_extended_returns(log_every=0)

    payload = run_combo_discovery_pipeline(use_claude=use_claude)
    json_path, md_path = write_pipeline_artifacts(payload, write_report=write_report)

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO threshold_review_log (review_date, combo_key, suggestion_json, status)
            VALUES (?, ?, ?, 'COMPLETE')
            """,
            (
                datetime.now().strftime("%Y-%m-%d"),
                "combo_discovery_pipeline",
                json.dumps(
                    {
                        "summary": payload["summary"],
                        "json_path": str(json_path),
                        "report_path": str(md_path) if md_path else None,
                    }
                ),
            ),
        )

    return {
        "summary": payload["summary"],
        "json_path": str(json_path),
        "report_path": str(md_path) if md_path else None,
        "survivors": payload["survivors"],
        "promotion_candidates": payload["promotion_candidates"],
    }
