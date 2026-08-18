"""Tests 3–4: SQUEEZE and LIQUIDITY EXIT CFTC FM/RM grids (episode-collapsed)."""

from __future__ import annotations

from typing import Any

from src.sentiment_superindex.analysis.cftc_grid_v2 import (
    LIQ_FM_THRESHOLDS,
    LIQ_RM_THRESHOLDS,
    SQUEEZE_FM_THRESHOLDS,
    SQUEEZE_RM_THRESHOLDS,
    run_liquidity_exit_grid_v2,
    run_squeeze_grid_v2,
)
from src.sentiment_superindex.analysis.report_utils import save_artifact, write_md_snippet

_H = ("4w", "8w", "12w")

__all__ = [
    "SQUEEZE_FM_THRESHOLDS",
    "SQUEEZE_RM_THRESHOLDS",
    "LIQ_FM_THRESHOLDS",
    "LIQ_RM_THRESHOLDS",
    "run_and_report",
    "run_squeeze_grid",
    "run_liquidity_exit_grid",
]


def _legacy_metrics(cell: dict[str, Any], *, long_side: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for label in _H:
        m = cell.get("metrics", {}).get(label, {})
        if not m or not m.get("n"):
            out[label] = {"n": 0, "avg": None, "median": None, "win_pct": None, "worst": None, "sharpe": None}
            continue
        out[label] = {
            "n": m.get("n"),
            "avg": m.get("mean"),
            "median": m.get("median"),
            "win_pct": m.get("hit_pct"),
            "worst": m.get("worst"),
            "sharpe": m.get("sharpe"),
        }
    if not long_side:
        dds = []
        for ep in cell.get("all_episodes", []):
            vals = [ep.get(f"ret_{h}") for h in _H]
            vals = [v for v in vals if v is not None]
            if vals:
                dds.append(min(vals))
        if dds:
            import numpy as np

            out["median_drawdown"] = round(float(np.median(dds)), 4)
    return out


def _squeeze_to_legacy(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "fm_max": row.get("fm_pct_max"),
        "rm_min": row.get("rm_pct_min"),
        "n": row.get("n_episodes", 0),
        "n_episodes": row.get("n_episodes", 0),
        "n_weeks": row.get("n_weeks", 0),
        "metrics": _legacy_metrics(row, long_side=True),
    }


def _liq_to_legacy(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "rm_max": row.get("rm_pct_max"),
        "fm_min": row.get("fm_pct_min"),
        "n": row.get("n_episodes", 0),
        "n_episodes": row.get("n_episodes", 0),
        "n_weeks": row.get("n_weeks", 0),
        "metrics": _legacy_metrics(row, long_side=False),
    }


def run_squeeze_grid(start: str = "2006-01-01") -> dict[str, Any]:
    from src.sentiment_superindex.analysis.cftc_episode_metrics import load_analysis_context

    raw = run_squeeze_grid_v2(load_analysis_context(start=start, pctile_start="2006-01-01"))
    rows = [_squeeze_to_legacy(r) for r in raw["rows"] if r.get("pattern") == "SQUEEZE"]
    return {"test_id": "03_squeeze_grid", "rows": rows}


def run_liquidity_exit_grid(start: str = "2006-01-01") -> dict[str, Any]:
    from src.sentiment_superindex.analysis.cftc_episode_metrics import load_analysis_context

    raw = run_liquidity_exit_grid_v2(load_analysis_context(start=start, pctile_start="2006-01-01"))
    rows = [_liq_to_legacy(r) for r in raw["rows"]]
    return {"test_id": "04_liquidity_exit_grid", "rows": rows}


def _cell_12w(r: dict | None) -> str:
    if not r:
        return "n_ep=0"
    n_ep = r.get("n_episodes", r.get("n", 0))
    n_wk = r.get("n_weeks", 0)
    m = r.get("metrics", {}).get("12w", {})
    if not m or not m.get("n"):
        return f"n_ep={n_ep} (wk={n_wk})"
    return f"{m.get('avg')}% / Sh{m.get('sharpe')} (n_ep={n_ep}, wk={n_wk})"


def run_and_report(start: str = "2006-01-01") -> dict[str, Any]:
    """Episode-collapsed grids + Rohit v2 report artifacts."""
    from src.sentiment_superindex.analysis.cftc_episode_metrics import load_analysis_context
    from src.sentiment_superindex.analysis.cftc_grid_v2 import (
        build_rohit_report,
        run_fm_pctile_regression,
    )
    from src.sentiment_superindex.analysis.report_utils import write_md_snippet

    ctx = load_analysis_context(start=start, pctile_start="2006-01-01")
    squeeze_raw = run_squeeze_grid_v2(ctx)
    liq_raw = run_liquidity_exit_grid_v2(ctx)
    regression = run_fm_pctile_regression(ctx)
    save_artifact("03_squeeze_grid_v2", squeeze_raw)
    save_artifact("04_liquidity_exit_grid_v2", liq_raw)
    save_artifact("cftc_fm_pctile_regression", regression)
    write_md_snippet("cftc_rohit_rerun", build_rohit_report(squeeze_raw, liq_raw, regression))

    squeeze = {
        "test_id": "03_squeeze_grid",
        "rows": [_squeeze_to_legacy(r) for r in squeeze_raw["rows"] if r.get("pattern") == "SQUEEZE"],
    }
    liq = {
        "test_id": "04_liquidity_exit_grid",
        "rows": [_liq_to_legacy(r) for r in liq_raw["rows"]],
    }
    save_artifact("03_squeeze_grid", squeeze)
    save_artifact("04_liquidity_exit_grid", liq)
    md = "# Tests 3–4: CFTC grids (episode-collapsed)\n\n"
    md += "Consecutive qualifying weeks → one episode (first fire). Stats on **n_ep**; **wk** = qualifying weeks.\n\n"
    md += "## SQUEEZE heatmap (12w avg SPX % / Sharpe)\n\n"
    md += "| FM < | RM > 40 | RM > 45 | RM > 50 | RM > 55 | RM > 60 | RM > 65 |\n"
    md += "|------|-----------|-----------|-----------|-----------|-----------|----------|\n"
    for fm in SQUEEZE_FM_THRESHOLDS:
        cells = []
        for rm in SQUEEZE_RM_THRESHOLDS:
            row = next((x for x in squeeze["rows"] if x["fm_max"] == fm and x["rm_min"] == rm), None)
            cells.append(_cell_12w(row))
        md += f"| {fm} | " + " | ".join(cells) + " |\n"
    ranked = sorted(
        (r for r in squeeze["rows"] if r.get("metrics", {}).get("12w", {}).get("sharpe") is not None),
        key=lambda x: x["metrics"]["12w"].get("sharpe") or 0,
        reverse=True,
    )
    if ranked:
        best = ranked[0]
        md += (
            f"\n**Highest 12w Sharpe (episode n):** FM<{best['fm_max']}, RM>{best['rm_min']} "
            f"(n_ep={best['n_episodes']}, wk={best['n_weeks']}).\n"
        )
    md += "\n## LIQUIDITY EXIT (top cells by episode n)\n"
    for r in sorted(liq["rows"], key=lambda x: -x.get("n_episodes", 0))[:10]:
        m4 = r.get("metrics", {}).get("4w", {})
        md += (
            f"- RM<{r['rm_max']} FM>{r['fm_min']}: n_ep={r['n_episodes']} (wk={r['n_weeks']}), "
            f"4w SPX down {m4.get('win_pct')}%\n"
        )
    write_md_snippet("03_04_cftc_grid", md)
    return {"squeeze": squeeze, "liquidity": liq, "v2": {"squeeze": squeeze_raw, "liquidity": liq_raw, "regression": regression}}
