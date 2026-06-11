"""SSI threshold sweep — level + 5y percentile, multi-horizon."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.config_paths import SSI_ANALYSIS_DIR
from src.sentiment_superindex.analysis.forward_metrics import (
    DEFAULT_HORIZONS,
    load_spx,
    returns_at_horizons,
    summarize_returns,
)
from src.sentiment_superindex.analysis.report_utils import metrics_table, save_artifact, write_md_snippet
from src.sentiment_superindex.analysis.ssi_history import build_ssi_history_frame
from src.sentiment_superindex.config import load_config


def _sweep_side(
    hist: pd.DataFrame,
    spx: pd.Series,
    *,
    column: str,
    thresholds: list[float],
    compare: str,
    long_side: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for thr in thresholds:
        if compare == "le":
            fires = hist[hist[column] <= thr]
        elif compare == "ge":
            fires = hist[hist[column] >= thr]
        else:
            fires = hist[hist[column] <= thr] if long_side else hist[hist[column] >= thr]
        if fires.empty:
            rows.append({"threshold": thr, "gate": column, "n_fires": 0, "metrics": {}})
            continue
        ret_rows = returns_at_horizons(spx, fires.index.tolist())
        metrics = summarize_returns(ret_rows, long_side=long_side)
        rows.append({"threshold": thr, "gate": column, "n_fires": len(fires), "metrics": metrics})
    return rows


def sweep_thresholds(
    start: str = "2015-01-01",
    end: str | None = None,
) -> dict[str, Any]:
    cfg = load_config()
    th = cfg.get("thresholds", {})
    hist = build_ssi_history_frame(start)
    if hist.empty:
        return {"error": "no_ssi_history", "test_id": "01_02_threshold_sweep"}

    end_ts = pd.Timestamp(end) if end else hist.index.max()
    hist = hist.loc[(hist.index >= pd.Timestamp(start)) & (hist.index <= end_ts)]
    spx = load_spx(start)

    long_level = list(np.arange(float(th.get("long_sweep_start", -0.3)), float(th.get("long_sweep_end", -0.9)) - 0.001, -float(th.get("long_sweep_step", 0.1))))
    short_level = [float(x) for x in th.get("short_sweep_values", [0.4, 0.5, 0.6, 0.7, 0.8, 0.9])]
    long_pct = list(range(10, 45, 5))
    short_pct = list(range(55, 96, 5))

    long_level_rows = _sweep_side(hist, spx, column="ssi_level", thresholds=long_level, compare="le", long_side=True)
    short_level_rows = _sweep_side(hist, spx, column="ssi_level", thresholds=short_level, compare="ge", long_side=False)
    long_pct_rows = _sweep_side(hist, spx, column="ssi_pctile_5y", thresholds=long_pct, compare="le", long_side=True)
    short_pct_rows = _sweep_side(hist, spx, column="ssi_pctile_5y", thresholds=short_pct, compare="ge", long_side=False)

    best_long_pct = max(
        (r for r in long_pct_rows if r.get("n_fires", 0) >= 5 and r.get("metrics", {}).get("3m", {}).get("avg") is not None),
        key=lambda x: x["metrics"]["3m"]["avg"],
        default=None,
    )
    best_short_pct = max(
        (r for r in short_pct_rows if r.get("n_fires", 0) >= 5 and r.get("metrics", {}).get("3m", {}).get("avg") is not None),
        key=lambda x: -x["metrics"]["3m"]["avg"],
        default=None,
    )

    return {
        "test_id": "01_02_threshold_sweep",
        "start": start,
        "end": str(end_ts.date()),
        "horizons": list(DEFAULT_HORIZONS.keys()),
        "long_level_sweep": long_level_rows,
        "short_level_sweep": short_level_rows,
        "long_pctile_sweep": long_pct_rows,
        "short_pctile_sweep": short_pct_rows,
        "recommended": {
            "long_entry_pctile": best_long_pct["threshold"] if best_long_pct else 20,
            "short_entry_pctile": best_short_pct["threshold"] if best_short_pct else 85,
            "long_entry_level": th.get("long_entry", -0.6),
            "short_entry_level": th.get("short_entry", 0.85),
            "rationale": "Primary gate: 5y percentile; level sweep for comparison",
        },
    }


def run_and_report(start: str = "2015-01-01", end: str | None = None) -> dict[str, Any]:
    result = sweep_thresholds(start=start, end=end)
    save_artifact("01_02_threshold_sweep", result)
    md = "# Tests 1–2: SSI entry threshold sweeps\n\n"
    if "error" in result:
        md += f"Error: {result['error']}\n"
    else:
        md += "## Long — 5y percentile (primary)\n"
        for r in result.get("long_pctile_sweep", [])[:8]:
            md += f"\n**Threshold ≤ {r['threshold']}** (n={r['n_fires']})\n"
            md += metrics_table(r.get("metrics", {}))
        md += "\n## Short — 5y percentile\n"
        for r in result.get("short_pctile_sweep", [])[:8]:
            md += f"\n**Threshold ≥ {r['threshold']}** (n={r['n_fires']})\n"
            md += metrics_table(r.get("metrics", {}))
    write_md_snippet("01_02_threshold_sweep", md)
    return result


def write_sweep_report(result: dict[str, Any], prefix: str = "ssi_threshold_sweep") -> tuple[Path, Path]:
    SSI_ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = pd.Timestamp.now().strftime("%Y%m%d")
    json_path = SSI_ANALYSIS_DIR / f"{prefix}_{stamp}.json"
    json_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    rows = []
    for key in ("long_level_sweep", "short_level_sweep", "long_pctile_sweep", "short_pctile_sweep"):
        for r in result.get(key, []):
            rows.append({"sweep": key, **{k: v for k, v in r.items() if k != "metrics"}})
    csv_path = SSI_ANALYSIS_DIR / f"{prefix}_{stamp}.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    return json_path, csv_path


def apply_recommended_to_config(result: dict[str, Any]) -> None:
    import yaml

    from src.config_paths import SSI_CONFIG

    rec = result.get("recommended", {})
    with SSI_CONFIG.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg.setdefault("thresholds", {})
    if "long_entry_level" in rec:
        cfg["thresholds"]["long_entry"] = rec["long_entry_level"]
    if "short_entry_level" in rec:
        cfg["thresholds"]["short_entry"] = rec["short_entry_level"]
    if "long_entry_pctile" in rec:
        cfg["thresholds"]["long_entry_pctile"] = rec["long_entry_pctile"]
    if "short_entry_pctile" in rec:
        cfg["thresholds"]["short_entry_pctile"] = rec["short_entry_pctile"]
    cfg["thresholds"]["threshold_source"] = f"sweep_{pd.Timestamp.now().strftime('%Y-%m-%d')}"
    with SSI_CONFIG.open("w", encoding="utf-8") as f:
        yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)
