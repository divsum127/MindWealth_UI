#!/usr/bin/env python3
"""Flatten SSI validation JSON artifacts into per-test CSVs plus an INDEX.

Every numbered test (1-22) stores its results as JSON in
``macro_intelligence/analysis/ssi_validation/``. Only Tests 3, 4, 18 and 22 ever
got CSV exports, and those were built ad hoc by
``scripts/export_cftc_rohit_share_package.py`` (Tests 3/4/18) or by hand
(Test 22). This script gives every test a CSV so any number quoted in
``testing/ssi_th_exp/SSI_THRESHOLD_EXPERIMENTS_ANALYSIS.md`` can be traced to a
file.

It reads only the newest artifact per test and never re-runs an experiment.

Usage::

    python3 scripts/export_ssi_validation_csvs.py
    python3 scripts/export_ssi_validation_csvs.py --out /tmp/ssi_csv
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ART = ROOT / "macro_intelligence" / "analysis" / "ssi_validation"
DEFAULT_OUT = ART / "csv"

DATED = re.compile(r"^(?P<stem>.+?)_(?P<date>\d{8})\.json$")

# Freshness is taken from docs/ssi_validation/STALE_BACKTESTS_AFTER_CNN_HY_FIXES.md
# (2026-08-17). CURRENT = artifact post-dates the 2026-08-02 CNN/HY fixes and the
# test's inputs actually moved. STALE = newest artifact predates the fixes and the
# test scores the SSI composite (which carries cnn_fg at weight 0.25).
# See the analysis doc for the two places that list disagrees with the artifacts.
TESTS: list[dict[str, Any]] = [
    {"stem": "01_02_threshold_sweep", "test": "01-02", "part": "1", "label": "SSI long/short threshold sweep", "freshness": "STALE"},
    {"stem": "03_squeeze_grid_v2", "test": "03", "part": "1", "label": "CFTC SQUEEZE grid (v2)", "freshness": "CURRENT"},
    {"stem": "04_liquidity_exit_grid_v2", "test": "04", "part": "1", "label": "CFTC LIQUIDITY EXIT grid (v2)", "freshness": "CURRENT"},
    {"stem": "05_tp_sl", "test": "05", "part": "1", "label": "TP/SL optimization", "freshness": "STALE"},
    {"stem": "06_cnn_fear_greed", "test": "06", "part": "1,2", "label": "CNN Fear & Greed thresholds", "freshness": "STALE"},
    {"stem": "07_dbmf_beta", "test": "07", "part": "2", "label": "DBMF beta threshold", "freshness": "UNAFFECTED"},
    {"stem": "08_hyg_lqd", "test": "08", "part": "2", "label": "HYG/LQD widening", "freshness": "UNAFFECTED"},
    {"stem": "09_zscore_vs_percentile", "test": "09", "part": "1", "label": "Z-score vs percentile composite", "freshness": "STALE"},
    {"stem": "10_layer2_sweep", "test": "10", "part": "1", "label": "Layer 2 vote-count sweep", "freshness": "STALE"},
    {"stem": "11_vix_regime_ab", "test": "11", "part": "5", "label": "VIX regime multiplier A/B", "freshness": "UNAFFECTED"},
    {"stem": "12_bollinger_ssi", "test": "12", "part": "9", "label": "Bollinger + SSI overlay", "freshness": "STALE"},
    {"stem": "13_stoch_mcclellan", "test": "13", "part": "9", "label": "Stochastic + McClellan", "freshness": "UNAFFECTED"},
    {"stem": "14_gross_net", "test": "14", "part": "4", "label": "Gross/net divergence", "freshness": "STALE"},
    {"stem": "15_sbi_short", "test": "15", "part": "6", "label": "SBI short signal", "freshness": "VOID"},
    {"stem": "16_friday_pull", "test": "16", "part": "10", "label": "Friday pull checklist", "freshness": "CURRENT"},
    {"stem": "17_trendpulse", "test": "17", "part": "7", "label": "TrendPulse deterioration", "freshness": "UNAFFECTED"},
    {"stem": "18_cot_fm_long_gate", "test": "18", "part": "1", "label": "COT FM long gate sweep", "freshness": "CURRENT"},
    {"stem": "19_vix_fm_washout", "test": "19", "part": "1", "label": "VIX>=35 + FM distribution", "freshness": "UNAFFECTED"},
    {"stem": "20_layer2_zscore_sweep", "test": "20", "part": "1", "label": "Layer 2 z-score sweep", "freshness": "STALE"},
    {"stem": "21_staleness_decay", "test": "21", "part": "beyond", "label": "Staleness decay calibration", "freshness": "CURRENT"},
    {"stem": "22_layer2_gate_grid", "test": "22", "part": "1", "label": "Layer 2 gate 2-D grid", "freshness": "CURRENT"},
    {"stem": "cftc_robustness_subsample", "test": "03-04-sup", "part": "1", "label": "CFTC 12-offset subsample robustness", "freshness": "CURRENT"},
    {"stem": "cftc_fm_pctile_regression", "test": "18-sup", "part": "1", "label": "CFTC FM pctile regression", "freshness": "CURRENT"},
]

# CSVs that already exist elsewhere and are NOT regenerated here.
EXISTING_BUNDLES: list[dict[str, str]] = [
    {"test": "03", "path": "docs/ssi_validation/CFTC_ROHIT_SHARE_20260811/csv/squeeze_grid_12w.csv"},
    {"test": "03", "path": "docs/ssi_validation/CFTC_ROHIT_SHARE_20260811/csv/squeeze_grid_all_horizons.csv"},
    {"test": "03", "path": "docs/ssi_validation/CFTC_ROHIT_SHARE_20260811/csv/squeeze_absolute_cuts.csv"},
    {"test": "04", "path": "docs/ssi_validation/CFTC_ROHIT_SHARE_20260811/csv/liquidity_exit_grid_4w.csv"},
    {"test": "04", "path": "docs/ssi_validation/CFTC_ROHIT_SHARE_20260811/csv/liquidity_exit_grid_all_horizons.csv"},
    {"test": "03-04", "path": "docs/ssi_validation/CFTC_ROHIT_SHARE_20260811/csv/episode_dates_top_cells.csv"},
    {"test": "03-04", "path": "docs/ssi_validation/CFTC_ROHIT_SHARE_20260811/csv/par_row.csv"},
    {"test": "03-04", "path": "docs/ssi_validation/CFTC_ROHIT_SHARE_20260811/csv/robustness_subsample.csv"},
    {"test": "03-04", "path": "docs/ssi_validation/CFTC_ROHIT_SHARE_20260811/csv/sample_diagnostics.csv"},
    {"test": "18", "path": "docs/ssi_validation/CFTC_ROHIT_SHARE_20260811/csv/fm_pctile_regression.csv"},
    {"test": "18", "path": "docs/ssi_validation/CFTC_ROHIT_SHARE_20260811/csv/fm_net_distribution.csv"},
    {"test": "22", "path": "docs/ssi_validation/LAYER2_GATE_GRID_ROHIT_SHARE_20260812/csv/22_layer2_gate_grid_summary.csv"},
    {"test": "22", "path": "docs/ssi_validation/LAYER2_GATE_GRID_ROHIT_SHARE_20260812/csv/22_layer2_gate_grid_forward_returns.csv"},
    {"test": "01-02", "path": "macro_intelligence/analysis/ssi_validation/ssi_threshold_sweep_20260604.csv"},
]


def newest(stem: str) -> tuple[Path, str] | None:
    """Newest dated artifact for a stem. Exact stem match, so ``03_squeeze_grid``
    never picks up ``03_squeeze_grid_v2``."""
    best: tuple[Path, str] | None = None
    for path in ART.glob(f"{stem}_*.json"):
        m = DATED.match(path.name)
        if not m or m.group("stem") != stem:
            continue
        if best is None or m.group("date") > best[1]:
            best = (path, m.group("date"))
    return best


def _is_row_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(v, dict) for v in value)


def _rows_to_frame(rows: list[dict]) -> tuple[pd.DataFrame, dict[str, list[dict]]]:
    """Flatten row dicts. Nested ``metrics`` collapses to ``<horizon>_<metric>``
    to match the convention in export_cftc_rohit_share_package.py. Nested row
    lists (episodes) are pulled out for their own CSV, keyed by condition."""
    nested: dict[str, list[dict]] = {}
    scalar_rows: list[dict[str, Any]] = []
    for row in rows:
        key = row.get("condition") or row.get("rule") or row.get("signal") or row.get("name")
        flat: dict[str, Any] = {}
        for k, v in row.items():
            if _is_row_list(v):
                for item in v:
                    nested.setdefault(k, []).append({"parent": key, **item})
                flat[f"{k}_count"] = len(v)
            elif isinstance(v, list):
                flat[k] = json.dumps(v)
            else:
                flat[k] = v
        scalar_rows.append(flat)

    frame = pd.json_normalize(scalar_rows, sep="_")
    frame.columns = [c[len("metrics_"):] if c.startswith("metrics_") else c for c in frame.columns]
    return frame, nested


def _meta_rows(payload: dict, skip: set[str]) -> list[dict[str, Any]]:
    """Everything that is not a row list, as long-form key/value pairs."""
    out: list[dict[str, Any]] = []

    def walk(prefix: str, value: Any) -> None:
        if isinstance(value, dict):
            for k, v in value.items():
                walk(f"{prefix}.{k}" if prefix else k, v)
        elif isinstance(value, list):
            if _is_row_list(value):
                out.append({"key": prefix, "value": f"<{len(value)} rows -> see sibling CSV>"})
            else:
                out.append({"key": prefix, "value": json.dumps(value)})
        else:
            out.append({"key": prefix, "value": value})

    for key, value in payload.items():
        if key in skip:
            continue
        walk(key, value)
    return out


def export_one(spec: dict[str, Any], out_dir: Path) -> list[dict[str, Any]]:
    found = newest(spec["stem"])
    if found is None:
        print(f"  SKIP {spec['stem']} — no artifact found")
        return []
    src, run_date = found
    payload = json.loads(src.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        print(f"  SKIP {src.name} — top level is not an object")
        return []

    written: list[dict[str, Any]] = []
    row_keys = {k for k, v in payload.items() if _is_row_list(v)}

    for key in sorted(row_keys):
        frame, nested = _rows_to_frame(payload[key])
        name = f"{spec['stem']}__{key}.csv"
        frame.to_csv(out_dir / name, index=False)
        written.append({"csv_file": name, "rows": len(frame)})

        for nested_key, nested_rows in sorted(nested.items()):
            nested_frame = pd.json_normalize(nested_rows, sep="_")
            nested_name = f"{spec['stem']}__{key}__{nested_key}.csv"
            nested_frame.to_csv(out_dir / nested_name, index=False)
            written.append({"csv_file": nested_name, "rows": len(nested_frame)})

    meta = _meta_rows(payload, skip=row_keys)
    if meta:
        name = f"{spec['stem']}__meta.csv"
        pd.DataFrame(meta).to_csv(out_dir / name, index=False)
        written.append({"csv_file": name, "rows": len(meta)})

    stamped = []
    for entry in written:
        stamped.append(
            {
                "test_id": spec["test"],
                "pdf_part": spec["part"],
                "label": spec["label"],
                "csv_file": entry["csv_file"],
                "rows": entry["rows"],
                "source_json": src.relative_to(ROOT).as_posix(),
                "source_run_date": f"{run_date[:4]}-{run_date[4:6]}-{run_date[6:]}",
                "freshness": spec["freshness"],
            }
        )
    print(f"  {spec['test']:<10} {src.name:<42} -> {len(written)} csv")
    return stamped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory")
    args = parser.parse_args()

    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Reading artifacts from {ART.relative_to(ROOT)}")
    index: list[dict[str, Any]] = []
    for spec in TESTS:
        index.extend(export_one(spec, out_dir))

    for bundle in EXISTING_BUNDLES:
        path = ROOT / bundle["path"]
        index.append(
            {
                "test_id": bundle["test"],
                "pdf_part": "",
                "label": "pre-existing export (not regenerated)",
                "csv_file": bundle["path"],
                "rows": "" if not path.is_file() else sum(1 for _ in path.open()) - 1,
                "source_json": "",
                "source_run_date": "",
                "freshness": "EXTERNAL" if path.is_file() else "MISSING",
            }
        )

    index_frame = pd.DataFrame(index)
    index_frame.to_csv(out_dir / "INDEX.csv", index=False)
    print(f"\nWrote {len(index_frame)} index rows -> {(out_dir / 'INDEX.csv').relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
