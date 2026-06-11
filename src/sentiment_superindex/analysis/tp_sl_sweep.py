"""Test 5: TP/SL vol multiplier grid (SPY long entries)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from src.config_paths import BASE_DIR


def _mindwealth_root() -> Path | None:
    root = os.getenv("MINDWEALTH_ROOT", "/home/ubuntu/MindWealth")
    p = Path(root)
    return p if p.is_dir() else None


def run_via_adapter(entry_dates: list[str] | None = None) -> dict[str, Any]:
    mw = _mindwealth_root()
    if mw is None:
        return {"test_id": "05_tp_sl", "error": "MINDWEALTH_ROOT not set", "rows": []}
    script = BASE_DIR / "scripts" / "mindwealth_adapters" / "sentiment_tp_sl.py"
    py = mw / ".venv" / "bin" / "python"
    if not py.exists():
        py = Path(sys.executable)
    proc = subprocess.run(
        [str(py), str(script)],
        cwd=str(mw),
        env={**os.environ, "MINDWEALTH_ROOT": str(mw), "PYTHONPATH": str(BASE_DIR)},
        capture_output=True,
        text=True,
        timeout=600,
    )
    if proc.returncode != 0:
        return {"test_id": "05_tp_sl", "error": proc.stderr or proc.stdout, "rows": []}
    import json

    try:
        return json.loads(proc.stdout.strip().split("\n")[-1])
    except Exception:
        return {"test_id": "05_tp_sl", "raw": proc.stdout, "stderr": proc.stderr}


def run_and_report() -> dict[str, Any]:
    from src.sentiment_superindex.analysis.report_utils import save_artifact, write_md_snippet

    result = run_via_adapter()
    save_artifact("05_tp_sl", result)
    md = "# Test 5: TP/SL optimization\n\n"
    if result.get("error"):
        md += f"Error: {result['error']}\n"
    else:
        rows = sorted(result.get("rows", []), key=lambda x: -(x.get("sharpe") or 0))
        md += "## Top 10 by Sharpe\n\n| TP× | SL× | n | Sharpe | Win% | Avg return% |\n|-----|-----|---|--------|------|-------------|\n"
        for r in rows[:10]:
            md += (
                f"| {r.get('tp_mult')} | {r.get('sl_mult')} | {r.get('n')} | "
                f"{r.get('sharpe')} | {r.get('win_pct')} | {r.get('avg_return')} |\n"
            )
        legacy = next((r for r in rows if r.get("tp_mult") == 10 and r.get("sl_mult") == 15), None)
        best = rows[0] if rows else None
        if legacy and best:
            md += (
                f"\n**Legacy TP×10 / SL×15:** Sharpe {legacy.get('sharpe')}, win {legacy.get('win_pct')}%\n"
                f"**Best TP×{best.get('tp_mult')} / SL×{best.get('sl_mult')}:** Sharpe {best.get('sharpe')}, win {best.get('win_pct')}%\n"
            )
    write_md_snippet("05_tp_sl", md)
    return result
