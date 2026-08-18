"""Test 15: SBI breadth short signal validation via MindWealth."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from src.config_paths import BASE_DIR


def run_via_adapter(start: str = "2015-01-01") -> dict[str, Any]:
    import json

    out_file = Path("/tmp/sbi_full_out.json")
    if out_file.is_file() and out_file.stat().st_size > 20:
        try:
            return json.loads(out_file.read_text().strip().split("\n")[-1])
        except Exception:
            pass

    mw = Path(os.getenv("MINDWEALTH_ROOT", "/home/ubuntu/MindWealth"))
    if not mw.is_dir():
        return {"test_id": "15_sbi_short", "error": "MINDWEALTH_ROOT not set"}
    script = BASE_DIR / "scripts" / "mindwealth_adapters" / "sbi_breadth.py"
    py = mw / ".venv" / "bin" / "python"
    if not py.exists():
        py = Path(sys.executable)
    dates_cache = Path("/tmp/sbi_short_dates.json")
    proc = subprocess.run(
        [
            str(py),
            str(script),
            "--start",
            start,
            "--freq",
            "BMS",
            "--dates-cache",
            str(dates_cache),
        ],
        cwd=str(mw),
        env={**os.environ, "MINDWEALTH_ROOT": str(mw), "PYTHONPATH": str(mw)},
        capture_output=True,
        text=True,
        timeout=14400,
    )
    import json

    if proc.returncode != 0:
        return {"test_id": "15_sbi_short", "error": proc.stderr or proc.stdout}
    try:
        return json.loads(proc.stdout.strip().split("\n")[-1])
    except Exception:
        return {"test_id": "15_sbi_short", "raw": proc.stdout}


def run_and_report(start: str = "2015-01-01") -> dict[str, Any]:
    from src.sentiment_superindex.analysis.report_utils import save_artifact, write_md_snippet

    result = run_via_adapter(start)
    save_artifact("15_sbi_short", result)
    md = "# Test 15: SBI short signal\n\n"
    if result.get("error"):
        md += f"Error: {result['error']}\n"
    else:
        md += f"Short entry days: {result.get('n_short_entries', 0)}\nMetrics: {result.get('metrics', {})}\n"
    write_md_snippet("15_sbi_short", md)
    return result
