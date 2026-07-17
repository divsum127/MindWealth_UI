#!/usr/bin/env python3
"""D5 — Fed-cycle re-slicing on recalibrated Combo D/E thresholds at validated horizons."""

from __future__ import annotations

import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.analysis.combo_threshold_sweep import (  # noqa: E402
    _aligned_dates,
    _reading_on,
    load_readings_panel,
)
from src.macro_intelligence.data.yahoo_pull import fetch_yahoo_close  # noqa: E402
from src.macro_intelligence.engine.fed_cycle import fed_cycle_at_date  # noqa: E402
from src.macro_intelligence.engine.forward_returns import (  # noqa: E402
    _nyse_sessions,
    forward_return_pct,
)
from testing.combo_de_thresholds.run_combo_de_study import (  # noqa: E402
    _crossing_indices,
    _d_pass,
    _e_pass,
    _fridays,
    _precompute_returns,
    _stats,
)

OUT_DIR = Path(__file__).resolve().parent
DATE_TAG = datetime.now(UTC).strftime("%Y-%m-%d")
MIN_N_USE = 10
COOLDOWN_DAYS = 5

# Recalibrated production candidates (post threshold sweep)
D_CONFIG = {
    "experiment_id": "D_v1.18_c95_x13_l2",
    "vxts_min": 1.18,
    "cftc_min_pctile": 95,
    "vix_max": 13,
    "legs_required": 2,
    "horizons": [("1W", 5), ("2W", 10)],
    "validated_horizon": "1W",
}

E_CONFIG = {
    "experiment_id": "E_cape32_nfci-0.15_cftc85_l3",
    "cape_min": 32,
    "nfci_easy_max": -0.15,
    "cftc_min_pctile": 85,
    "legs_required": 3,
    "horizons": [("6M", 126), ("9M", 189), ("12M", 252)],
    "validated_horizons": ["6M", "9M", "12M"],
    "cftc_escalation_note": "3-of-3 gate includes CFTC>=85; escalation alert is briefing overlay when CFTC pctile rises during active E episode",
}

# Legacy baseline (uniform 3M, production CONFIG thresholds) — from X_COMBO_regime_slices.json
LEGACY_BASELINE = {
    "D": {
        "horizon": "3M",
        "overall_n": 452,
        "overall_bear_hit_pct": 28.1,
        "HIKING_LATE": {"n": 197, "bear_hit_pct": 18.3},
        "CUTTING_LATE": {"n": 155, "bear_hit_pct": 43.2},
        "QE": {"n": 100, "bear_hit_pct": 24.0},
        "spread_cutting_minus_hiking_pp": 24.9,
        "spread_ratio": 2.36,
    },
    "E": {
        "horizon": "3M",
        "overall_n": 507,
        "overall_bear_hit_pct": 19.9,
        "HIKING_LATE": {"n": 221, "bear_hit_pct": 18.1},
        "CUTTING_LATE": {"n": 159, "bear_hit_pct": 22.0},
        "QE": {"n": 127, "bear_hit_pct": 14.2},
    },
}


def _arrays(panel, dates: list[str], vars_: list[str]) -> tuple[np.ndarray, ...]:
    arrs = []
    for vid in vars_:
        col = []
        for ds in dates:
            r = _reading_on(panel, vid, ds)
            if vid == "CFTC":
                col.append(float(r["pctile"]) if r and r["pctile"] is not None else np.nan)
            else:
                col.append(float(r["raw"]) if r and r["raw"] is not None else np.nan)
        arrs.append(np.array(col))
    valid = np.ones(len(dates), dtype=bool)
    for a in arrs:
        valid &= ~np.isnan(a)
    return (*arrs, valid)


def _fed_label(ds: str) -> str:
    label, _ = fed_cycle_at_date(ds)
    return label


def _verdict(n_events: int) -> str:
    return "USE" if n_events >= MIN_N_USE else "CANNOT USE"


def _slice_rows(
    combo: str,
    config: dict[str, Any],
    dates: list[str],
    indices: list[int],
    fwd: dict[int, dict[str, float | None]],
    horizons: list[tuple[str, int]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_fed: dict[str, list[int]] = {}
    for i in indices:
        fed = _fed_label(dates[i])
        by_fed.setdefault(fed, []).append(i)

    for fed in sorted(by_fed):
        fed_idx = by_fed[fed]
        for horizon, _td in horizons:
            s = _stats(fed_idx, fwd, horizon)
            n_ev = len(fed_idx)
            rows.append(
                {
                    "combo": combo,
                    "config_id": config["experiment_id"],
                    "fed_cycle": fed,
                    "horizon": horizon,
                    "n_events": n_ev,
                    "n_mature": s["n_mature"],
                    "bear_hit_pct": s["bear_hit_pct"],
                    "avg_spx_pct": s["avg_spx_pct"],
                    "min_spx_pct": s["min_spx_pct"],
                    "max_spx_pct": s["max_spx_pct"],
                    "verdict": _verdict(n_ev),
                }
            )

    for horizon, _td in horizons:
        s = _stats(indices, fwd, horizon)
        rows.append(
            {
                "combo": combo,
                "config_id": config["experiment_id"],
                "fed_cycle": "OVERALL",
                "horizon": horizon,
                "n_events": len(indices),
                "n_mature": s["n_mature"],
                "bear_hit_pct": s["bear_hit_pct"],
                "avg_spx_pct": s["avg_spx_pct"],
                "min_spx_pct": s["min_spx_pct"],
                "max_spx_pct": s["max_spx_pct"],
                "verdict": _verdict(len(indices)),
            }
        )
    return rows


def _per_fire_rows(
    combo: str,
    config: dict[str, Any],
    dates: list[str],
    indices: list[int],
    fwd: dict[int, dict[str, float | None]],
    horizons: list[tuple[str, int]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i in indices:
        row: dict[str, Any] = {
            "combo": combo,
            "config_id": config["experiment_id"],
            "trigger_date": dates[i],
            "fed_cycle": _fed_label(dates[i]),
        }
        for horizon, _td in horizons:
            ret = fwd[i][horizon]
            row[f"spx_change_pct_{horizon}"] = round(ret, 4) if ret is not None else ""
            row[f"bear_hit_{horizon}"] = (
                1 if ret is not None and ret < 0 else (0 if ret is not None else "")
            )
        rows.append(row)
    return rows


def _spread_analysis(
    slice_rows: list[dict[str, Any]], horizon: str
) -> dict[str, Any]:
    def hit(fed: str) -> dict[str, Any] | None:
        for r in slice_rows:
            if r["fed_cycle"] == fed and r["horizon"] == horizon:
                return r
        return None

    cutting = hit("CUTTING_LATE")
    hiking = hit("HIKING_LATE")
    out: dict[str, Any] = {"horizon": horizon}
    if cutting and hiking:
        c_hit = cutting["bear_hit_pct"]
        h_hit = hiking["bear_hit_pct"]
        out["CUTTING_LATE"] = {
            "n": cutting["n_events"],
            "bear_hit_pct": c_hit,
            "verdict": cutting["verdict"],
        }
        out["HIKING_LATE"] = {
            "n": hiking["n_events"],
            "bear_hit_pct": h_hit,
            "verdict": hiking["verdict"],
        }
        if c_hit is not None and h_hit is not None:
            out["spread_cutting_minus_hiking_pp"] = round(c_hit - h_hit, 2)
            out["spread_ratio"] = round(c_hit / h_hit, 2) if h_hit else None
        both_usable = cutting["verdict"] == "USE" and hiking["verdict"] == "USE"
        out["spread_usable"] = both_usable
        if both_usable and out.get("spread_cutting_minus_hiking_pp") is not None:
            legacy = LEGACY_BASELINE["D"]["spread_cutting_minus_hiking_pp"]
            out["legacy_spread_pp"] = legacy
            out["spread_survives_recalibration"] = out["spread_cutting_minus_hiking_pp"] > 0
            out["spread_magnitude_vs_legacy"] = (
                "similar"
                if abs(out["spread_cutting_minus_hiking_pp"] - legacy) <= 10
                else ("wider" if out["spread_cutting_minus_hiking_pp"] > legacy else "narrower")
            )
    return out


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    keys: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for k in row:
            if k not in seen:
                seen.add(k)
                keys.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def _markdown_report(
    d_slices: list[dict[str, Any]],
    e_slices: list[dict[str, Any]],
    d_spread_1w: dict[str, Any],
    d_spread_2w: dict[str, Any],
    meta: dict[str, Any],
) -> str:
    lines = [
        "# D5 — Fed-Cycle Re-Slicing on Recalibrated Thresholds",
        "",
        f"**Date:** {DATE_TAG}  ",
        "**Task:** Re-run named-combo-by-fed-cycle tables using recalibrated D/E configs at validated horizons (not legacy production thresholds @ uniform 3M).",
        "",
        "## Configs (recalibrated)",
        "",
        "| Combo | Thresholds | Legs | Validated horizon(s) |",
        "|-------|------------|------|----------------------|",
        f"| **D** | VXTS ≥{D_CONFIG['vxts_min']} / CFTC ≥{D_CONFIG['cftc_min_pctile']} / VIX ≤{D_CONFIG['vix_max']} | {D_CONFIG['legs_required']}-of-3 | **1W** (also **2W**) |",
        f"| **E** | CAPE ≥{E_CONFIG['cape_min']} / NFCI ≤{E_CONFIG['nfci_easy_max']} / CFTC ≥{E_CONFIG['cftc_min_pctile']} | {E_CONFIG['legs_required']}-of-3 | **6M / 9M / 12M** |",
        "",
        f"E note: {E_CONFIG['cftc_escalation_note']}.",
        "",
        f"**Sample rule:** slices with n < {MIN_N_USE} episodes → **CANNOT USE** (no hit rate reported as actionable).",
        "",
        "## (a) Combo D — CUTTING_LATE vs HIKING_LATE spread",
        "",
        "### Legacy baseline (superseded)",
        "",
        "Production CONFIG @ **3M**: overall **28.1%** bear hit (n=452).",
        "",
        "| fed_cycle | n | bear hit 3M |",
        "|-----------|---|-------------|",
        f"| CUTTING_LATE | {LEGACY_BASELINE['D']['CUTTING_LATE']['n']} | **{LEGACY_BASELINE['D']['CUTTING_LATE']['bear_hit_pct']}%** |",
        f"| HIKING_LATE | {LEGACY_BASELINE['D']['HIKING_LATE']['n']} | **{LEGACY_BASELINE['D']['HIKING_LATE']['bear_hit_pct']}%** |",
        f"| Spread (CUTTING − HIKING) | | **{LEGACY_BASELINE['D']['spread_cutting_minus_hiking_pp']} pp** ({LEGACY_BASELINE['D']['spread_ratio']}×) |",
        "",
        "### Recalibrated @ validated horizons",
        "",
    ]

    def spread_table(spread: dict[str, Any], title: str) -> list[str]:
        out = [f"#### {title}", ""]
        if not spread.get("CUTTING_LATE"):
            out.append("_CUTTING_LATE or HIKING_LATE slice missing._")
            out.append("")
            return out
        c = spread["CUTTING_LATE"]
        h = spread["HIKING_LATE"]
        out.extend(
            [
                "| fed_cycle | n | verdict | bear hit % |",
                "|-----------|---|---------|------------|",
                f"| CUTTING_LATE | {c['n']} | {c['verdict']} | {c['bear_hit_pct'] if c['verdict']=='USE' else '—'} |",
                f"| HIKING_LATE | {h['n']} | {h['verdict']} | {h['bear_hit_pct'] if h['verdict']=='USE' else '—'} |",
            ]
        )
        if spread.get("spread_usable"):
            out.append(
                f"| Spread | | | **{spread['spread_cutting_minus_hiking_pp']} pp** "
                f"({spread.get('spread_ratio')}×) vs legacy {spread.get('legacy_spread_pp')} pp |"
            )
            survives = spread.get("spread_survives_recalibration")
            mag = spread.get("spread_magnitude_vs_legacy")
            out.append("")
            out.append(
                f"**Verdict:** Spread **{'survives' if survives else 'does not survive'}** recalibration "
                f"({mag} vs legacy)."
            )
        else:
            out.append("")
            out.append(
                "**Verdict:** **CANNOT USE** — at least one fed slice below "
                f"n={MIN_N_USE}; do not compare spread at this horizon."
            )
        out.append("")
        return out

    lines.extend(spread_table(d_spread_1w, "1W (validated primary)"))
    lines.extend(spread_table(d_spread_2w, "2W (secondary)"))

    lines.extend(
        [
            "## (b) Full fed-cycle tables",
            "",
            "### Combo D",
            "",
            "| fed_cycle | horizon | n | n_mature | bear hit % | avg SPX % | verdict |",
            "|-----------|---------|---|----------|------------|-----------|---------|",
        ]
    )
    for r in sorted(d_slices, key=lambda x: (x["horizon"], x["fed_cycle"])):
        hit = f"{r['bear_hit_pct']}" if r["verdict"] == "USE" and r["bear_hit_pct"] is not None else "—"
        avg = f"{r['avg_spx_pct']}" if r["verdict"] == "USE" and r["avg_spx_pct"] is not None else "—"
        lines.append(
            f"| {r['fed_cycle']} | {r['horizon']} | {r['n_events']} | {r['n_mature']} | {hit} | {avg} | {r['verdict']} |"
        )

    lines.extend(
        [
            "",
            "### Combo E",
            "",
            "| fed_cycle | horizon | n | n_mature | bear hit % | avg SPX % | verdict |",
            "|-----------|---------|---|----------|------------|-----------|---------|",
        ]
    )
    for r in sorted(e_slices, key=lambda x: (x["horizon"], x["fed_cycle"])):
        hit = f"{r['bear_hit_pct']}" if r["verdict"] == "USE" and r["bear_hit_pct"] is not None else "—"
        avg = f"{r['avg_spx_pct']}" if r["verdict"] == "USE" and r["avg_spx_pct"] is not None else "—"
        lines.append(
            f"| {r['fed_cycle']} | {r['horizon']} | {r['n_events']} | {r['n_mature']} | {hit} | {avg} | {r['verdict']} |"
        )

    lines.extend(
        [
            "",
            "## Method",
            "",
            "- Episode = first Friday crossing recalibrated gate with 5-calendar-day cooldown.",
            "- fed_cycle = legacy 7-state label from `fed_cycle_at_date()` (FRED DFF + WALCL).",
            "- Bear hit = % episodes where SPX forward return < 0 at horizon.",
            f"- Total D episodes: {meta['n_d_events']}; total E episodes: {meta['n_e_events']}.",
            "",
            "## Artifacts",
            "",
            f"- `D5_fed_cycle_reslice_{DATE_TAG}.csv` — slice summary",
            f"- `D5_fed_cycle_per_fire_{DATE_TAG}.csv` — per-episode rows with fed_cycle",
            f"- `D5_fed_cycle_reslice_{DATE_TAG}.json` — machine-readable payload",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    panel = load_readings_panel("2007-01-01")
    spx = fetch_yahoo_close("^GSPC", "1990-01-01")
    sessions = _nyse_sessions()

    d_dates_all = _aligned_dates(panel, ["VXTS", "CFTC", "VIX"])
    e_dates_all = _aligned_dates(panel, ["CAPE", "NFCI", "CFTC"])
    d_dates = _fridays(d_dates_all)
    e_dates = _fridays(e_dates_all)

    vxts, cftc_d, vix, d_valid = _arrays(panel, d_dates, ["VXTS", "CFTC", "VIX"])
    cape, nfci, cftc_e, e_valid = _arrays(panel, e_dates, ["CAPE", "NFCI", "CFTC"])

    d_in = (
        _d_pass(
            vxts,
            cftc_d,
            vix,
            D_CONFIG["vxts_min"],
            D_CONFIG["cftc_min_pctile"],
            D_CONFIG["vix_max"],
            D_CONFIG["legs_required"],
        )
        & d_valid
    )
    e_in = (
        _e_pass(
            cape,
            nfci,
            cftc_e,
            E_CONFIG["cape_min"],
            E_CONFIG["nfci_easy_max"],
            E_CONFIG["cftc_min_pctile"],
            E_CONFIG["legs_required"],
        )
        & e_valid
    )

    d_idx = _crossing_indices(d_in, d_dates)
    e_idx = _crossing_indices(e_in, e_dates)

    fwd_d = _precompute_returns(d_dates, spx, sessions, D_CONFIG["horizons"])
    fwd_e = _precompute_returns(e_dates, spx, sessions, E_CONFIG["horizons"])

    d_slices = _slice_rows("D", D_CONFIG, d_dates, d_idx, fwd_d, D_CONFIG["horizons"])
    e_slices = _slice_rows("E", E_CONFIG, e_dates, e_idx, fwd_e, E_CONFIG["horizons"])

    per_fire = _per_fire_rows("D", D_CONFIG, d_dates, d_idx, fwd_d, D_CONFIG["horizons"])
    per_fire.extend(_per_fire_rows("E", E_CONFIG, e_dates, e_idx, fwd_e, E_CONFIG["horizons"]))

    d_spread_1w = _spread_analysis(d_slices, "1W")
    d_spread_2w = _spread_analysis(d_slices, "2W")

    meta = {
        "generated_at": datetime.now(UTC).isoformat(),
        "task": "D5_fed_cycle_reslice",
        "min_n_use": MIN_N_USE,
        "d_config": D_CONFIG,
        "e_config": E_CONFIG,
        "legacy_baseline": LEGACY_BASELINE,
        "n_d_events": len(d_idx),
        "n_e_events": len(e_idx),
        "friday_d_dates": len(d_dates),
        "friday_e_dates": len(e_dates),
        "d_overall_1W": next(r for r in d_slices if r["fed_cycle"] == "OVERALL" and r["horizon"] == "1W"),
        "e_overall_12M": next(r for r in e_slices if r["fed_cycle"] == "OVERALL" and r["horizon"] == "12M"),
        "d_spread_1W": d_spread_1w,
        "d_spread_2W": d_spread_2w,
    }

    csv_path = OUT_DIR / f"D5_fed_cycle_reslice_{DATE_TAG}.csv"
    per_fire_path = OUT_DIR / f"D5_fed_cycle_per_fire_{DATE_TAG}.csv"
    json_path = OUT_DIR / f"D5_fed_cycle_reslice_{DATE_TAG}.json"
    md_path = OUT_DIR / f"D5_fed_cycle_reslice_{DATE_TAG}.md"

    all_slices = d_slices + e_slices
    _write_csv(csv_path, all_slices)
    _write_csv(per_fire_path, per_fire)
    json_path.write_text(json.dumps({"meta": meta, "slices": all_slices}, indent=2, default=str), encoding="utf-8")
    md_path.write_text(_markdown_report(d_slices, e_slices, d_spread_1w, d_spread_2w, meta), encoding="utf-8")

    print(json.dumps(meta, indent=2, default=str))
    print(f"Wrote {csv_path}, {per_fire_path}, {json_path}, {md_path}")


if __name__ == "__main__":
    main()
