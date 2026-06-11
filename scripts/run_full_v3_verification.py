#!/usr/bin/env python3
"""
Full v3 verification gate: unittest + production validator + traceability matrix + mock audit.

Exit 0 when all strict checks pass. Use --allow-warn to pass with production WARNs (e.g. AAII ingest).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV_PY = ROOT / ".venv" / "bin" / "python"


def _run(cmd: list[str], label: str) -> int:
    print(f"\n=== {label} ===")
    proc = subprocess.run(cmd, cwd=ROOT)
    return proc.returncode


def _write_go_no_go(
    *,
    tests_rc: int,
    prod_rc: int,
    matrix_rc: int,
    audit_rc: int,
    allow_warn: bool,
) -> Path:
    out = ROOT / "macro_intelligence" / "output" / "v3_go_no_go.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    strict_ok = tests_rc == 0 and audit_rc == 0 and matrix_rc == 0 and prod_rc == 0
    warn_ok = tests_rc == 0 and audit_rc == 0 and matrix_rc == 0 and prod_rc in (0, 1) and allow_warn
    verdict = "GO" if strict_ok else ("GO_WITH_WARNS" if warn_ok else "NO_GO")
    body = f"""# Runic v3 Go / No-Go

Generated: {datetime.now().isoformat()}

| Check | Exit code | Pass |
|-------|-----------|------|
| unittest (macro/SSI) | {tests_rc} | {'yes' if tests_rc == 0 else 'no'} |
| production data sources | {prod_rc} | {'yes' if prod_rc == 0 else 'warn/fail'} |
| traceability matrix | {matrix_rc} | {'yes' if matrix_rc == 0 else 'no'} |
| production no-mock audit | {audit_rc} | {'yes' if audit_rc == 0 else 'no'} |

**Verdict:** {verdict}

## Commands

```bash
.venv/bin/python scripts/run_full_v3_verification.py
.venv/bin/python scripts/validate_production_data_sources.py
.venv/bin/python scripts/run_macro_nightly.py
```

## Rohit sign-off

Complete `docs/plans/macro_intelligence_rohit_signoff.md` before production trading.
"""
    out.write_text(body, encoding="utf-8")
    print(f"Wrote {out}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Full v3 verification")
    parser.add_argument("--allow-warn", action="store_true", help="Allow production WARNs (not FAILs)")
    parser.add_argument("--skip-live", action="store_true", help="Skip live production validator")
    parser.add_argument("--ssi-validation-smoke", action="store_true", help="Run SSI validation unit smoke only")
    args = parser.parse_args()
    py = str(VENV_PY if VENV_PY.exists() else "python3")

    if args.ssi_validation_smoke:
        return _run([py, "-m", "unittest", "-q", "tests.test_ssi_validation_smoke"], "SSI validation smoke")

    test_modules = [
        "tests.test_macro_percentiles",
        "tests.test_hit_rates",
        "tests.test_backfill_hit_rates",
        "tests.test_combo_a_vote",
        "tests.test_combo_b_oct_2022",
        "tests.test_combo_c_cancel",
        "tests.test_combo_f_jun_2020",
        "tests.test_combo_g",
        "tests.test_cftc_parser",
        "tests.test_cftc_column_manifest",
        "tests.test_dominant_priority",
        "tests.test_runic_output_schema",
        "tests.test_briefing_renderer",
        "tests.test_friday_pull_integration",
        "tests.test_bls_cpi_pull",
        "tests.test_cpi_pull",
        "tests.test_ssi_layer2",
        "tests.test_ssi_positioning_json",
        "tests.test_scraper_pipelines",
    ]
    tests_rc = _run([py, "-m", "unittest", "-q", *test_modules], "Layer 2: unittest")

    audit_rc = _run([py, "scripts/audit_production_no_mocks.py"], "Layer 2b: no-mock audit")

    matrix_rc = _run([py, "scripts/export_v3_traceability_matrix.py"], "Layer 1: traceability matrix")

    prod_rc = 0
    if not args.skip_live:
        prod_rc = _run([py, "scripts/validate_production_data_sources.py"], "Layer 3: live production")

    _write_go_no_go(
        tests_rc=tests_rc,
        prod_rc=prod_rc,
        matrix_rc=matrix_rc,
        audit_rc=audit_rc,
        allow_warn=args.allow_warn,
    )

    if tests_rc != 0 or audit_rc != 0 or matrix_rc != 0:
        return 1
    if prod_rc != 0 and not args.allow_warn:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
