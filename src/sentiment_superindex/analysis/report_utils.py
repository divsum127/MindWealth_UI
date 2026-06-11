"""Write validation artifacts and markdown snippets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.config_paths import BASE_DIR, SSI_ANALYSIS_DIR

GENERATED_DOCS = BASE_DIR / "docs" / "ssi_validation" / "_generated"


def stamp() -> str:
    return pd.Timestamp.now().strftime("%Y%m%d")


def save_artifact(test_id: str, payload: dict[str, Any], *, suffix: str = "json") -> Path:
    SSI_ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    path = SSI_ANALYSIS_DIR / f"{test_id}_{stamp()}.{suffix}"
    if suffix == "json":
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    elif suffix == "csv" and "rows" in payload:
        pd.DataFrame(payload["rows"]).to_csv(path, index=False)
    return path


def metrics_table(metrics: dict[str, Any], title: str = "") -> str:
    lines = [f"### {title}" if title else "", "| Horizon | n | Avg % | Median % | Win % | Worst % | Sharpe |", "|---------|---|-------|----------|-------|---------|--------|"]
    for label, m in metrics.items():
        if label == "n_events" or not isinstance(m, dict):
            continue
        lines.append(
            f"| {label} | {m.get('n', 0)} | {m.get('avg', '—')} | {m.get('median', '—')} | "
            f"{m.get('win_pct', '—')} | {m.get('worst', '—')} | {m.get('sharpe', '—')} |"
        )
    return "\n".join(lines) + "\n"


def write_md_snippet(test_id: str, body: str) -> Path:
    GENERATED_DOCS.mkdir(parents=True, exist_ok=True)
    path = GENERATED_DOCS / f"{test_id}_{stamp()}.md"
    path.write_text(body, encoding="utf-8")
    return path
