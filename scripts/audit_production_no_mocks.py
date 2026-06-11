#!/usr/bin/env python3
"""Fail if production macro/SSI code references mocks, fixtures, or open TODO deferrals."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN = [
    ROOT / "src" / "macro_intelligence",
    ROOT / "src" / "sentiment_superindex",
    ROOT / "scripts",
]
SKIP = {
    "scripts/audit_production_no_mocks.py",
    "scripts/run_full_v3_verification.py",
    "scripts/export_v3_traceability_matrix.py",
}
PATTERN = re.compile(
    r"unittest\.mock|from tests\.fixtures|TODO|FIXME|not implemented",
    re.I,
)
ALLOW = ("heuristic_regime", "heuristic_geo", "pending backfill", "monthly review")


def main() -> int:
    hits: list[str] = []
    for base in SCAN:
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            if "test" in path.parts:
                continue
            rel = str(path.relative_to(ROOT))
            if rel in SKIP:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for i, line in enumerate(text.splitlines(), 1):
                if not PATTERN.search(line):
                    continue
                if any(a in line for a in ALLOW):
                    continue
                hits.append(f"{path.relative_to(ROOT)}:{i}:{line.strip()}")
    if hits:
        print("FAIL: mock/TODO patterns in production paths:")
        for h in hits[:30]:
            print(h)
        if len(hits) > 30:
            print(f"... and {len(hits) - 30} more")
        return 1
    print("OK: no mock/fixture/TODO patterns in production macro/SSI paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
