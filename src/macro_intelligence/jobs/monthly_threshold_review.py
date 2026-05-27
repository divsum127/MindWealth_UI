"""Monthly automated threshold review scaffold (addendum A5)."""

from __future__ import annotations

import json
from datetime import datetime

from src.macro_intelligence.db.connection import get_connection


def run_monthly_review() -> list[dict]:
    """Flag combos with poor or sparse recent performance."""
    findings: list[dict] = []
    with get_connection() as conn:
        loose = conn.execute(
            """
            SELECT runic_combo, COUNT(*) AS n
            FROM combo_fires
            WHERE date >= date('now', '-12 months') AND runic_combo IS NOT NULL
            GROUP BY runic_combo HAVING n >= 10
            """
        ).fetchall()
        for row in loose:
            findings.append({"combo": row["runic_combo"], "issue": "high_frequency", "n": row["n"]})

    with get_connection() as conn:
        for f in findings:
            conn.execute(
                """
                INSERT INTO threshold_review_log (review_date, combo_key, suggestion_json, status)
                VALUES (?, ?, ?, 'PENDING')
                """,
                (
                    datetime.now().strftime("%Y-%m-%d"),
                    f.get("combo"),
                    json.dumps(f),
                ),
            )
    return findings
