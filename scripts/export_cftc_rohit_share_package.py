#!/usr/bin/env python3
"""Build Rohit-shareable CFTC package: INDEX report + CSV exports + PDF."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ART = ROOT / "macro_intelligence" / "analysis" / "ssi_validation"
DEFAULT_OUT = ROOT / "docs" / "ssi_validation" / "CFTC_ROHIT_SHARE_20260811"
REPORT_SRC = ROOT / "docs" / "ssi_validation" / "CFTC_PATTERN_THRESHOLD_REPORT_FOR_ROHIT_20260811.md"
GITHUB_REPO = "divsum127/MindWealth_UI"
GITHUB_BRANCH = "chatbot-dev"
HORIZONS = ["4w", "8w", "12w", "6m", "12m"]


def latest(pattern: str) -> Path:
    files = sorted(ART.glob(pattern))
    if not files:
        raise FileNotFoundError(f"No artifacts matching {pattern}")
    return files[-1]


def _flatten_cell(row: dict[str, Any], *, horizon: str | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "pattern": row.get("pattern"),
        "condition": row.get("condition"),
        "fm_pct_max": row.get("fm_pct_max"),
        "rm_pct_min": row.get("rm_pct_min"),
        "rm_pct_max": row.get("rm_pct_max"),
        "fm_pct_min": row.get("fm_pct_min"),
        "fm_net_max": row.get("fm_net_max"),
        "fm_net_fixed_pctile": row.get("fm_net_fixed_pctile"),
        "n_weeks": row.get("n_weeks"),
        "n_episodes": row.get("n_episodes"),
    }
    metrics = row.get("metrics") or {}
    if horizon:
        m = metrics.get(horizon) or {}
        for k, v in m.items():
            out[f"{horizon}_{k}"] = v
    else:
        for h, m in metrics.items():
            if not isinstance(m, dict):
                continue
            for k, v in m.items():
                out[f"{h}_{k}"] = v
    return out


def grid_to_csv(rows: list[dict], path: Path, *, horizon: str | None = None) -> None:
    flat = [_flatten_cell(r, horizon=horizon) for r in rows]
    if not flat:
        path.write_text("", encoding="utf-8")
        return
    pd.DataFrame(flat).to_csv(path, index=False)


def export_episodes(rows: list[dict], path: Path, *, horizon: str, top_n_cells: int = 15) -> None:
    from src.sentiment_superindex.analysis.cftc_report_format import rank_cells_by_gap

    squeeze = [r for r in rows if r.get("pattern") == "SQUEEZE"]
    liq = [r for r in rows if r.get("pattern") == "LIQUIDITY_EXIT"]
    ranked_sq = rank_cells_by_gap(squeeze, "12w", squeeze_only=True)[:top_n_cells]
    ranked_liq = rank_cells_by_gap(liq, "4w", long_side=False)[:top_n_cells]
    episode_rows: list[dict[str, Any]] = []
    for cell in ranked_sq + ranked_liq:
        ret_key = f"ret_{horizon}"
        ex_key = f"excess_{horizon}"
        for ep in cell.get("all_episodes") or []:
            episode_rows.append(
                {
                    "condition": cell.get("condition"),
                    "pattern": cell.get("pattern"),
                    "episode_date": ep.get("date"),
                    f"spx_return_{horizon}": ep.get(ret_key),
                    f"excess_{horizon}": ep.get(ex_key),
                }
            )
    pd.DataFrame(episode_rows).to_csv(path, index=False)


def export_robustness(data: dict, path: Path) -> None:
    rows: list[dict[str, Any]] = []
    for cell in data.get("cells", []):
        cond = cell.get("condition")
        stab = cell.get("subsample_stability") or {}
        full = stab.get("full") or {}
        rows.append(
            {
                "condition": cond,
                "scope": "full",
                "offset": "",
                **{k: full.get(k) for k in ("n_weeks", "n_episodes", "mean", "median", "mean_excess", "hit_pct", "hit_excess_pct")},
                "stable_across_offsets": stab.get("stable_across_offsets"),
                "offsets_positive_excess": stab.get("offsets_positive_excess"),
                "offsets_with_data": stab.get("offsets_with_data"),
            }
        )
        for off in stab.get("offsets") or []:
            rows.append(
                {
                    "condition": cond,
                    "scope": "offset",
                    "offset": off.get("offset"),
                    "n_weeks": off.get("n_weeks"),
                    "n_episodes": off.get("n_episodes"),
                    "mean": off.get("mean"),
                    "median": off.get("median"),
                    "mean_excess": off.get("mean_excess"),
                    "hit_pct": off.get("hit_pct"),
                    "hit_excess_pct": off.get("hit_excess_pct"),
                    "stable_across_offsets": "",
                    "offsets_positive_excess": "",
                    "offsets_with_data": "",
                }
            )
    pd.DataFrame(rows).to_csv(path, index=False)


def github_link(rel_path: str) -> str:
    return f"https://github.com/{GITHUB_REPO}/blob/{GITHUB_BRANCH}/{rel_path}"


def github_raw(rel_path: str) -> str:
    return f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/{rel_path}"


def build_index(
    out_dir: Path,
    *,
    squeeze_path: Path,
    liq_path: Path,
    files: dict[str, str],
) -> str:
    rel_base = out_dir.relative_to(ROOT).as_posix()
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [
        "# CFTC SQUEEZE / LIQUIDITY EXIT — Share Package for Rohit",
        "",
        f"**Package date:** {today}  ",
        f"**COT data through:** 2026-08-04 (Tuesday position date)  ",
        f"**Spec:** Rohit Aug 4, 2026 email (episode collapse, extended FM axis, mean−median gap, PAR/excess, robustness)",
        "",
        "---",
        "",
        "## Quick links (after push to `chatbot-dev`)",
        "",
        f"| Item | View | Download |",
        f"|------|------|----------|",
        f"| **Start here — sign-off report** | [REPORT.md](REPORT.md) | [raw]({github_raw(f'{rel_base}/REPORT.md')}) |",
        f"| **This index** | [INDEX.md](INDEX.md) | [GitHub]({github_link(f'{rel_base}/INDEX.md')}) |",
    ]
    for label, fname in files.items():
        rel = f"{rel_base}/csv/{fname}"
        lines.append(f"| {label} | [csv/{fname}](csv/{fname}) | [raw CSV]({github_raw(rel)}) |")
    lines += [
        "",
        "## Executive summary",
        "",
        "1. **Ranking metric:** mean − median gap at 12w (SQUEEZE) / 4w (LIQUIDITY EXIT), read with dated episodes — **not Sharpe**.",
        "2. **Top SQUEEZE cell:** `FM_roll_pct<10 AND RM_roll_pct>55` — n_ep=21, 12w gap ≈ +0.41%, excess_hit 65%.",
        "3. **PDF default FM<30/RM>50:** negative gap (−0.57%) — tracks market, not tail.",
        "4. **Extreme FM<5:** n_ep=6 only — high mean (~5.8%) but tiny sample.",
        "5. **LIQUIDITY EXIT RM<30/FM>60:** n_ep=40, 4w hit 32.5% — stress context flag, not a clean short.",
        "6. **Sample start:** raw TFF from 2006-06-13; first **full 156-week** rolling window **2009-06-02** → GFC Sep 2008–May 2009 excluded from rolling-percentile grids.",
        "7. **Display wiring:** held pending sign-off (flags only, no composite sizing).",
        "",
        "## Package contents",
        "",
        "### Reports",
        "",
        "- `REPORT.md` — full sign-off report (heatmaps, top cells, recommendations)",
        "- `TAIL_EPISODES.md` — dated episode lists (FM>70/75 discontinuity explained)",
        "- `ROBUSTNESS.md` — 12-offset subsample stability tables",
        "- `FM_DISTRIBUTION.md` — FM net fixed distribution + proposed absolute cuts",
        "- `data/README.md` — column definitions for CSV files",
        "",
        "### CSV data (`csv/`)",
        "",
    ]
    for label, fname in files.items():
        lines.append(f"- `{fname}` — {label}")
    lines += [
        "",
        "### Supporting files",
        "",
        "- `data/fm_net_distribution_histogram.png` — FM net fixed distribution",
        "- `data/sample_diagnostics.json` — sample start / window diagnostics",
        "- `data/benchmark.json` — PAR benchmark returns per horizon",
        "",
        "## Methodology (short)",
        "",
        "| Item | Value |",
        "|------|-------|",
        "| Percentile window | 156 weeks rolling |",
        "| Episode collapse | Consecutive qualifying weeks → one episode (first fire) |",
        "| Benchmark | Mean SPX forward return across all weeks in sample |",
        "| Excess | Episode return minus benchmark; excess_hit = beat market |",
        "| SQUEEZE | FM pctile < X AND RM pctile > Y |",
        "| LIQUIDITY EXIT | RM pctile < X AND FM pctile > Y |",
        "",
        "## Source artifacts",
        "",
        f"- `{squeeze_path.relative_to(ROOT)}`",
        f"- `{liq_path.relative_to(ROOT)}`",
        "",
        "## Regenerate",
        "",
        "```bash",
        ".venv/bin/python scripts/run_cftc_rohit_rerun.py",
        ".venv/bin/python scripts/compile_cftc_pattern_threshold_report.py",
        ".venv/bin/python scripts/export_cftc_rohit_share_package.py",
        "```",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Export CFTC Rohit share package")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--squeeze", type=Path, default=None)
    parser.add_argument("--liquidity", type=Path, default=None)
    parser.add_argument("--no-pdf", action="store_true")
    args = parser.parse_args()

    squeeze_path = args.squeeze or latest("03_squeeze_grid_v2_*.json")
    liq_path = args.liquidity or latest("04_liquidity_exit_grid_v2_*.json")
    robustness_path = latest("cftc_robustness_subsample_*.json")
    regression_path = latest("cftc_fm_pctile_regression_*.json")

    squeeze = json.loads(squeeze_path.read_text(encoding="utf-8"))
    liq = json.loads(liq_path.read_text(encoding="utf-8"))
    robustness = json.loads(robustness_path.read_text(encoding="utf-8"))
    regression = json.loads(regression_path.read_text(encoding="utf-8"))

    out = args.out
    csv_dir = out / "csv"
    data_dir = out / "data"
    pdf_dir = out / "pdf"
    for d in (csv_dir, data_dir, pdf_dir):
        d.mkdir(parents=True, exist_ok=True)

    sq_rows = squeeze.get("rows", [])
    liq_rows = liq.get("rows", [])

    csv_files = {
        "SQUEEZE grid (12w metrics)": "squeeze_grid_12w.csv",
        "SQUEEZE grid (all horizons)": "squeeze_grid_all_horizons.csv",
        "LIQUIDITY EXIT grid (4w metrics)": "liquidity_exit_grid_4w.csv",
        "LIQUIDITY EXIT grid (all horizons)": "liquidity_exit_grid_all_horizons.csv",
        "Dated episodes (top cells)": "episode_dates_top_cells.csv",
        "12-offset subsample robustness": "robustness_subsample.csv",
        "FM pctile regression": "fm_pctile_regression.csv",
        "FM fixed distribution": "fm_net_distribution.csv",
        "PAR row (unconditional)": "par_row.csv",
        "Sample diagnostics": "sample_diagnostics.csv",
    }

    grid_to_csv([r for r in sq_rows if r.get("pattern") == "SQUEEZE"], csv_dir / "squeeze_grid_12w.csv", horizon="12w")
    grid_to_csv([r for r in sq_rows if r.get("pattern") == "SQUEEZE"], csv_dir / "squeeze_grid_all_horizons.csv")
    grid_to_csv([r for r in sq_rows if r.get("pattern") == "SQUEEZE_ABS"], csv_dir / "squeeze_absolute_cuts.csv")
    grid_to_csv(liq_rows, csv_dir / "liquidity_exit_grid_4w.csv", horizon="4w")
    grid_to_csv(liq_rows, csv_dir / "liquidity_exit_grid_all_horizons.csv")
    export_episodes(sq_rows + liq_rows, csv_dir / "episode_dates_top_cells.csv", horizon="12w")
    export_robustness(robustness, csv_dir / "robustness_subsample.csv")
    pd.DataFrame(regression.get("rows", [])).to_csv(csv_dir / "fm_pctile_regression.csv", index=False)

    fm_dist = squeeze.get("fm_distribution") or {}
    pd.DataFrame([fm_dist]).to_csv(csv_dir / "fm_net_distribution.csv", index=False)
    pd.DataFrame([squeeze.get("sample_diagnostics") or {}]).to_csv(csv_dir / "sample_diagnostics.csv", index=False)

    par_rows = []
    for label, m in (squeeze.get("par") or {}).get("metrics", {}).items():
        par_rows.append({"horizon": label, **m})
    pd.DataFrame(par_rows).to_csv(csv_dir / "par_row.csv", index=False)

    # Copy report + histogram
    if REPORT_SRC.is_file():
        shutil.copy2(REPORT_SRC, out / "REPORT.md")
    hist_glob = sorted((ROOT / "docs/ssi_validation/_generated").glob("cftc_fm_net_distribution_histogram_*.png"))
    if hist_glob:
        shutil.copy2(hist_glob[-1], data_dir / "fm_net_distribution_histogram.png")

    (data_dir / "sample_diagnostics.json").write_text(
        json.dumps(squeeze.get("sample_diagnostics") or {}, indent=2), encoding="utf-8"
    )
    (data_dir / "benchmark.json").write_text(
        json.dumps(squeeze.get("benchmark") or {}, indent=2), encoding="utf-8"
    )

    (data_dir / "README.md").write_text(
        """# CSV column reference

## squeeze_grid_12w.csv / liquidity_exit_grid_4w.csv
One row per grid cell at the primary ranking horizon.
- `n_weeks` — qualifying weeks (before episode collapse)
- `n_episodes` — collapsed distinct episodes
- `{horizon}_mean`, `{horizon}_median`, `{horizon}_mean_median_gap` — SPX forward return stats
- `{horizon}_hit_pct` — positive return share
- `{horizon}_mean_excess`, `{horizon}_hit_excess_pct` — vs unconditional market benchmark

## episode_dates_top_cells.csv
Every episode date for top-ranked cells with SPX return and excess at 12w.

## robustness_subsample.csv
12-offset non-overlapping subsample stability (Rohit primary robustness test).

## fm_net_distribution.csv
Fixed (non-rolling) percentiles of FM net contracts over full sample.
""",
        encoding="utf-8",
    )

    index_md = build_index(out, squeeze_path=squeeze_path, liq_path=liq_path, files=csv_files)
    (out / "INDEX.md").write_text(index_md, encoding="utf-8")

    if not args.no_pdf and REPORT_SRC.is_file():
        try:
            from scripts.export_cftc_threshold_report_pdfs import md_to_pdf

            md_to_pdf(REPORT_SRC, pdf_dir / "CFTC_PATTERN_THRESHOLD_REPORT_FOR_ROHIT_20260811.pdf", "CFTC Report")
            print(f"PDF: {pdf_dir / 'CFTC_PATTERN_THRESHOLD_REPORT_FOR_ROHIT_20260811.pdf'}")
        except Exception as exc:
            print(f"PDF skipped: {exc}")

    rel = out.relative_to(ROOT).as_posix()
    print(f"Package: {out}")
    print(f"INDEX: {out / 'INDEX.md'}")
    print(f"Share link (after git push): {github_link(rel + '/INDEX.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
