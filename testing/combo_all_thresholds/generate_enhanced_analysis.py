#!/usr/bin/env python3
"""Regenerate ANALYSIS.md section 2 + variable recommendation tables from sweep CSVs."""

from __future__ import annotations

import sys
from io import StringIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from testing.combo_all_thresholds.run_all_combos_study import COMBO_SPECS, OUT_DIR  # noqa: E402

PRIMARY = {
    "A": "hit_6M",
    "B": "hit_3M",
    "C": "hit_6M",
    "D": "hit_1W",
    "E": "hit_12M",
    "F": "hit_6M",
    "G": "hit_3W",
}

VAR_COLS = {
    "A": ["min_of_four", "rare_pctile_high", "rare_pctile_low", "hy_bps_rare", "walcl_mom_rare_pct"],
    "B": ["vix_min", "hy_bps_min", "cftc_max_pctile", "legs_required"],
    "C": ["wti_4wk_min_pct", "cpi_surprise_min", "walcl_flat_max_pct", "legs_required"],
    "D": ["vxts_min", "cftc_min_pctile", "vix_max", "legs_required"],
    "E": ["cape_min", "nfci_easy_max", "cftc_min_pctile", "legs_required"],
    "F": ["spx_50wma_reclaim_pct", "cftc_max_pctile"],
    "G": ["vxts_max", "vix_max", "hy_widen_4wk_bps_min"],
}


def _load_summary(letter: str) -> pd.DataFrame:
    paths = [OUT_DIR / f"combo_{letter}_sweep_summary.csv"]
    if letter in ("C", "G"):
        ext = OUT_DIR / f"combo_{letter}_extended_sweep_summary.csv"
        if ext.exists():
            paths.append(ext)
    frames = []
    for p in paths:
        lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if not ln.startswith("#")]
        if lines:
            frames.append(pd.read_csv(StringIO("\n".join(lines))))
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset=["experiment_id"], keep="first")
    return df


def _fmt(v: Any) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if isinstance(v, float):
        if abs(v - round(v)) < 1e-9:
            return str(int(round(v)))
        return f"{v:.2f}"
    return str(v)


def _top_table(df: pd.DataFrame, letter: str, top_n: int = 5, min_n: int = 3) -> str:
    spec = COMBO_SPECS[letter]
    primary = PRIMARY[letter]
    hit_cols = [c for c in df.columns if c.startswith("hit_") and c != "hit_mean_all_horizons"]
    horizon_labels = [c.replace("hit_", "") for c in hit_cols]

    pool = df[df["n_events"] >= min_n].copy()
    if pool.empty:
        pool = df[df["n_events"] >= 1].copy()
    if pool.empty:
        return f"*No episodes in sweep for Combo {letter} — cannot rank thresholds.*\n"

    primary = PRIMARY[letter]

    def rank_score(row: pd.Series) -> float:
        hit = row.get(primary)
        if hit is None or (isinstance(hit, float) and np.isnan(hit)):
            hit = row.get("hit_mean_all_horizons") or 0
        n = int(row.get("n_events") or 0)
        return float(hit) - (5 if n < 5 else 0)

    pool["_rank_score"] = pool.apply(rank_score, axis=1)
    pool = pool.sort_values("_rank_score", ascending=False).head(top_n)

    cols = ["rank", "experiment_id", "n_events", "gate_text"] + hit_cols + ["hit_mean_all_horizons"]
    lines = [
        f"### Combo {letter} — {spec.label} (top {len(pool)} by {primary.replace('hit_', '')}, n≥{min_n} or all available)",
        "",
        "| " + " | ".join(
            ["Rank", "n", "Gate"] + horizon_labels + ["Mean", "Primary"]
        ) + " |",
        "|" + "|".join(["---"] * (3 + len(horizon_labels) + 2)) + "|",
    ]
    for i, (_, r) in enumerate(pool.iterrows(), 1):
        hits = [_fmt(r.get(c)) + "%" if r.get(c) is not None and not pd.isna(r.get(c)) else "—" for c in hit_cols]
        mean_h = _fmt(r.get("hit_mean_all_horizons"))
        prim = _fmt(r.get(primary))
        gate = _gate_md(str(r.get("gate_text", "")))
        lines.append(
            f"| {i} | {int(r['n_events'])} | {gate} | "
            + " | ".join(hits)
            + f" | {mean_h}% | **{prim}%** |"
        )
    lines.append("")
    return "\n".join(lines)


def _variable_univariate_best(df: pd.DataFrame, letter: str, min_n: int = 3) -> list[dict]:
    """Best hit per swept variable value (univariate rows only)."""
    spec = COMBO_SPECS[letter]
    primary = PRIMARY[letter]
    rows_out: list[dict] = []
    uni = df[df["sweep_type"].astype(str).str.contains("univariate|extended_", na=False)]
    if uni.empty:
        return rows_out

    var_map = {
        "A": {
            "univariate_pctile": "rare_pctile_high",
            "univariate_hy": "hy_bps_rare",
            "univariate_walcl": "walcl_mom_rare_pct",
            "legs": "min_of_four",
        },
        "B": {
            "univariate_vix": "vix_min",
            "univariate_hy": "hy_bps_min",
            "univariate_cftc": "cftc_max_pctile",
        },
        "C": {
            "univariate_wti": "wti_4wk_min_pct",
            "extended_wti": "wti_4wk_min_pct",
            "univariate_cpi": "cpi_surprise_min",
            "extended_cpi": "cpi_surprise_min",
            "univariate_walcl": "walcl_flat_max_pct",
            "extended_walcl": "walcl_flat_max_pct",
        },
        "D": {
            "univariate_vxts": "vxts_min",
            "univariate_cftc": "cftc_min_pctile",
            "univariate_vix": "vix_max",
        },
        "E": {
            "univariate_cape": "cape_min",
            "univariate_nfci": "nfci_easy_max",
            "univariate_cftc": "cftc_min_pctile",
        },
        "F": {"univariate_spx": "spx_50wma_reclaim_pct", "univariate_cftc": "cftc_max_pctile"},
        "G": {
            "univariate_vxts": "vxts_max",
            "extended_vxts": "vxts_max",
            "univariate_vix": "vix_max",
            "extended_vix": "vix_max",
            "univariate_hy": "hy_widen_4wk_bps_min",
            "extended_hy": "hy_widen_4wk_bps_min",
        },
    }
    for sweep_type, col in var_map.get(letter, {}).items():
        sub = uni[uni["sweep_type"] == sweep_type]
        if sub.empty or col not in sub.columns:
            continue
        for val, grp in sub.groupby(col):
            grp = grp[grp["n_events"] >= min_n] if (grp["n_events"] >= min_n).any() else grp
            if grp.empty:
                continue
            best = grp.sort_values(primary, ascending=False, na_position="last").iloc[0]
            rows_out.append(
                {
                    "combo": letter,
                    "variable": col,
                    "threshold_value": val,
                    "sweep_type": sweep_type,
                    "primary_horizon": primary.replace("hit_", ""),
                    "primary_hit_pct": best.get(primary),
                    "n_events": int(best["n_events"]),
                    "hit_mean_all_horizons": best.get("hit_mean_all_horizons"),
                    "gate_text": best.get("gate_text"),
                    "experiment_id": best.get("experiment_id"),
                }
            )
    return rows_out


def _best_per_variable_value(df: pd.DataFrame, letter: str) -> pd.DataFrame:
    """For each variable, pick threshold value with highest primary hit (n≥3 preferred)."""
    primary = PRIMARY[letter]
    cols = [c for c in VAR_COLS.get(letter, []) if c in df.columns]
    records = []
    for col in cols:
        for val, grp in df.groupby(col):
            if pd.isna(val):
                continue
            g = grp[grp["n_events"] >= 3]
            if g.empty:
                g = grp[grp["n_events"] >= 1]
            if g.empty:
                continue
            best = g.sort_values(primary, ascending=False, na_position="last").iloc[0]
            records.append(
                {
                    "combo": letter,
                    "variable": col,
                    "threshold_value": val,
                    "n_events": int(best["n_events"]),
                    "primary_horizon": primary.replace("hit_", ""),
                    "primary_hit_pct": best.get(primary),
                    "hit_mean_all_horizons": best.get("hit_mean_all_horizons"),
                    "experiment_id": best["experiment_id"],
                    "gate_text": best["gate_text"],
                }
            )
    return pd.DataFrame(records)


def _recommended_full_config(df: pd.DataFrame, letter: str) -> dict | None:
    spec = COMBO_SPECS[letter]
    primary = PRIMARY[letter]

    def score(row: pd.Series) -> float:
        hit = row.get(primary)
        if hit is None or (isinstance(hit, float) and np.isnan(hit)):
            hit = row.get("hit_mean_all_horizons") or 0
        n = int(row.get("n_events") or 0)
        return float(hit) - (8 if n < 5 else 0) - (3 if n < 3 else 0)

    pool = df[df["n_events"] >= 1]
    if pool.empty:
        return None
    best = pool.iloc[pool.apply(score, axis=1).argmax()]
    return best.to_dict()


def _gate_md(text: str) -> str:
    return str(text).replace("|", " ").replace("  ", " ").strip()


def main() -> None:
    all_var_rows: list[dict] = []
    recommended_rows: list[dict] = []

    section2_parts: list[str] = [
        "## 2. Top thresholds by horizon (from sweep data)",
        "",
        "Ranked by primary horizon hit rate. Values are measured from first-crossing episodes (5-day cooldown).",
        "Combo C/G include extended sweeps where base grid had n<3.",
        "",
    ]

    for letter in "ABCDEFG":
        df = _load_summary(letter)
        if df.empty:
            continue
        section2_parts.append(_top_table(df, letter))
        all_var_rows.extend(_variable_univariate_best(df, letter))
        var_df = _best_per_variable_value(df, letter)
        if not var_df.empty:
            var_df.to_csv(OUT_DIR / f"combo_{letter}_variable_best_by_value.csv", index=False)

        best = _recommended_full_config(df, letter)
        if best:
            spec = COMBO_SPECS[letter]
            primary = PRIMARY[letter]
            rec = {
                "combo": letter,
                "label": spec.label,
                "spec_hit_pct": spec.spec_hit_pct,
                "spec_horizon": spec.spec_horizon_label,
                "recommended_gate": best.get("gate_text"),
                "experiment_id": best.get("experiment_id"),
                "n_events": best.get("n_events"),
                "primary_horizon": primary.replace("hit_", ""),
                "primary_hit_pct": best.get(primary),
                "hit_mean_all_horizons": best.get("hit_mean_all_horizons"),
                "is_config_baseline": best.get("is_config_baseline"),
            }
            for col in VAR_COLS.get(letter, []):
                if col in best:
                    rec[col] = best[col]
            recommended_rows.append(rec)

    # Variable recommendation: best value per variable per combo
    var_best_df = pd.DataFrame(all_var_rows)
    if not var_best_df.empty:
        var_best_df.to_csv(OUT_DIR / "all_combos_variable_univariate_best.csv", index=False)

    # Aggregate: for each variable across combos, table of best threshold per combo
    agg_records = []
    for letter in "ABCDEFG":
        df = _load_summary(letter)
        if df.empty:
            continue
        bpv = _best_per_variable_value(df, letter)
        if bpv.empty:
            continue
        for _, r in bpv.iterrows():
            agg_records.append(r.to_dict())
    agg_df = pd.DataFrame(agg_records)
    if not agg_df.empty:
        agg_df.to_csv(OUT_DIR / "all_combos_best_threshold_per_variable.csv", index=False)

    rec_df = pd.DataFrame(recommended_rows)
    rec_df.to_csv(OUT_DIR / "all_combos_recommended_full_config.csv", index=False)

    # Build section 3 tables in markdown
    section3: list[str] = [
        "## 3. Recommended full gate per combo (best primary hit, prefer n≥5)",
        "",
    ]
    if not rec_df.empty:
        section3.append(
            "| Combo | n | Primary hit | Spec | Gate | Key thresholds |"
        )
        section3.append("|---|---:|---:|---:|---|---|")
        for _, r in rec_df.iterrows():
            keys = []
            for col in VAR_COLS.get(r["combo"], []):
                if col in r and pd.notna(r[col]):
                    keys.append(f"{col}={_fmt(r[col])}")
            section3.append(
                f"| **{r['combo']}** | {int(r['n_events'])} | {_fmt(r['primary_hit_pct'])}% @ {r['primary_horizon']} "
                f"| {r['spec_hit_pct']}% | {_gate_md(str(r['recommended_gate']))} | {', '.join(keys)} |"
            )
        section3.append("")

    # Master cross-combo variable table (one row per combo × variable, best value from sweep)
    section3.append("## 4. Master variable threshold table (best value per variable, measured)")
    section3.append("")
    if not agg_df.empty:
        section3.append(
            "| Combo | Variable | Best threshold | n | Primary horizon | Primary hit % | Mean hit all H | Experiment |"
        )
        section3.append("|---|---|---|---:|---|---:|---:|---|")
        op_map = {
            "vix_min": "≥", "hy_bps_min": "≥", "cftc_max_pctile": "≤", "cftc_min_pctile": "≥",
            "vxts_min": "≥", "vix_max": "≤", "vxts_max": "<", "cape_min": "≥", "nfci_easy_max": "≤",
            "wti_4wk_min_pct": "≥", "cpi_surprise_min": "≥", "walcl_flat_max_pct": "< abs",
            "spx_50wma_reclaim_pct": "≥", "hy_widen_4wk_bps_min": "≥", "hy_bps_rare": "≥",
            "walcl_mom_rare_pct": "≥ abs", "rare_pctile_high": "≥", "rare_pctile_low": "≤",
            "min_of_four": "≥", "legs_required": "=",
        }
        for _, r in agg_df.sort_values(["combo", "variable"]).iterrows():
            op = op_map.get(r["variable"], "")
            thr = f"{op} {_fmt(r['threshold_value'])}" if op else _fmt(r["threshold_value"])
            section3.append(
                f"| {r['combo']} | {r['variable']} | {thr} | {int(r['n_events'])} | {r['primary_horizon']} "
                f"| {_fmt(r['primary_hit_pct'])} | {_fmt(r['hit_mean_all_horizons'])} | {r['experiment_id']} |"
            )
        section3.append("")

    section3.append("## 5. Best threshold value per variable (detail by combo)")
    section3.append("")
    for letter in "ABCDEFG":
        p = OUT_DIR / f"combo_{letter}_variable_best_by_value.csv"
        if not p.exists():
            continue
        vdf = pd.read_csv(p)
        if vdf.empty:
            continue
        spec = COMBO_SPECS[letter]
        section3.append(f"### Combo {letter} — {spec.label}")
        section3.append("")
        section3.append(
            "| Variable | Best value | n | Primary hit | Mean hit all horizons | Experiment |"
        )
        section3.append("|---|---|---:|---:|---:|---|")
        for var, grp in vdf.groupby("variable"):
            best = grp.sort_values("primary_hit_pct", ascending=False, na_position="last").iloc[0]
            section3.append(
                f"| {var} | {_fmt(best['threshold_value'])} | {int(best['n_events'])} | "
                f"{_fmt(best['primary_hit_pct'])}% | {_fmt(best['hit_mean_all_horizons'])}% | {best['experiment_id']} |"
            )
        section3.append("")

    # Read existing section 1 and notes from ANALYSIS if present
    analysis_path = OUT_DIR / "ANALYSIS.md"
    old = analysis_path.read_text(encoding="utf-8") if analysis_path.exists() else ""
    section1 = old.split("## 2.")[0].strip() if "## 2." in old else old

    notes = """## 6. Interpretation notes

- **A:** Proxy rare legs via pctile bands; production uses variable-engine RARE/EXTREME tiers.
- **B:** VIX≥28 on strict 3-of-3 matches spec 87.5% @3M (n=8) in replay.
- **C:** Extended sweep (79 experiments, max n=6): **no configuration reached spec 83% @6M** on episode replay; best 6M bear hit = 0%.
- **G:** Extended sweep (107 experiments) required — CONFIG VXTS<1.0 yields n=0. Best n≥5: 66.7% @3W (spec 75%); n=3 configs show 100% @3W but not robust.
- **D/E:** CONFIG far below spec; tightened gates in section 3.
- **F:** CONFIG and sweep agree — strong bullish 6M.

CSV exports: `all_combos_recommended_full_config.csv`, `all_combos_best_threshold_per_variable.csv`, `combo_*_variable_best_by_value.csv`, `combo_C_extended_sweep_summary.csv`, `combo_G_extended_sweep_summary.csv`.
"""

    new_doc = "\n".join(
        [
            section1,
            "",
            "\n".join(section2_parts),
            "\n".join(section3),
            notes,
        ]
    )
    analysis_path.write_text(new_doc, encoding="utf-8")
    print(f"Wrote {analysis_path}")
    print(f"Recommended configs: {len(rec_df)}")
    print(f"Variable rows: {len(agg_df) if not agg_df.empty else 0}")


if __name__ == "__main__":
    main()
