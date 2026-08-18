#!/usr/bin/env python3
"""D1 — Regime bucket feed for Ahil P3 (daily BENIGN / ADVERSE / MIXED series).

Point-in-time: each Friday re-runs named-combo detection on daily_readings as-of
that date (recalibrated CONFIG gates — D/E per D5). Daily rows forward-fill from
last Friday evaluation (Mon–Thu carry prior bucket).

Sequence: run after D5 fed-cycle re-slice; bucket ADVERSE mapping follows D5
recalibrated bearish combos (C, D, E) + G ACTIVE + A TIGHT_MONEY.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.config import load_config
from src.macro_intelligence.data.pull_all import get_readings_as_of, load_all_series
from src.macro_intelligence.db.connection import get_connection
from src.macro_intelligence.engine import combo_detector as cd
from src.macro_intelligence.engine.combo_c_cancel import cpi_leg_passes
from src.macro_intelligence.engine.combo_detector import detect_named_combos
from src.macro_intelligence.engine.dominant import is_validated_combo
from src.macro_intelligence.engine.regime_rules import build_python_regime

OUT_DIR = Path(__file__).resolve().parent
DATE_TAG = datetime.now(UTC).strftime("%Y-%m-%d")
# v1.2 (2026-08-17): B moved above C in the dominance priority and low-n combos
# (fewer than 5 matured episodes) demoted below every validated combo — Rohit 2026-08-06.
SERIES_VERSION = f"D1_regime_bucket_v1.2_{DATE_TAG}"

_SERIES_CACHE: dict | None = None


def _cached_load_all_series(force: bool = False):
    global _SERIES_CACHE
    if _SERIES_CACHE is None or force:
        _SERIES_CACHE = load_all_series(force=force)
    return _SERIES_CACHE

START_DATE = "2018-01-01"
END_DATE = "2026-12-31"

ACTIVE_CLASS = frozenset(
    {"ACTIVE", "PARTIAL", "CONFIRMED", "CONFIRMED_3_OF_3", "ESCALATION_ALERT"}
)
STATUS_RANK = {
    "ACTIVE": 6,
    "ESCALATION_ALERT": 5,
    "CONFIRMED_3_OF_3": 4,
    "CONFIRMED": 3,
    "PARTIAL": 2,
    "WATCH": 1,
    "CONTESTED": 0,
}

DESIGN_INTENT = {
    "C": "BEARISH",
    "D": "BEARISH",
    "E": "BEARISH",
    "B": "BULLISH",
    "F": "BULLISH",
    "G": "CAUTIONARY",
    "A": "CONDITIONAL",
}

# D5 recalibrated gates (mirrors CONFIG.yaml + D5_fed_cycle_reslice)
RECALIBRATED_GATES = {
    "D": {
        "experiment_id": "D_v1.18_c95_x13_l2",
        "vxts_min": 1.18,
        "cftc_min_pctile": 95,
        "vix_max": 13,
        "legs_required": 2,
        "validated_horizon": "1W",
        "d5_bear_hit_pct": 56.52,
    },
    "E": {
        "experiment_id": "E_cape32_nfci-0.15_cftc85_l3",
        "cape_min": 32,
        "nfci_easy_max": -0.15,
        "cftc_min_pctile": 85,
        "legs_required": 3,
        "validated_horizons": ["6M", "9M", "12M"],
        "d5_bear_hit_pct": 66.67,
    },
}


def _fridays(start: str, end: str) -> list[str]:
    cur = datetime.strptime(start, "%Y-%m-%d")
    stop = datetime.strptime(end, "%Y-%m-%d")
    out: list[str] = []
    while cur <= stop:
        if cur.weekday() == 4:
            out.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)
    return out


def _parse_a_vote(macro_regime: dict | None) -> str | None:
    if not macro_regime:
        return None
    vote = macro_regime.get("a_vote")
    if not vote:
        return None
    vote = str(vote).upper()
    if vote in ("FEARFUL", "TIGHT_MONEY"):
        return "FEARFUL"
    if vote in ("BRAVE", "EASY_MONEY"):
        return "BRAVE"
    return vote


def _fire_row(fire) -> dict:
    regime = fire.macro_regime or {}
    return {
        "combo": fire.runic_combo,
        "status": fire.status,
        "resolved_intent": _parse_a_vote(regime),
    }


def _resolve_dominant(actives: list[dict]) -> dict | None:
    """Same ordering the live engine uses: PRIORITY, with low-n combos demoted.

    Kept in step with src/macro_intelligence/engine/dominant.py:_rank_key — if the two
    ever diverge, D1 buckets stop matching the posture the system actually took.
    """
    if not actives:
        return None
    dominant_cfg = load_config().get("dominant", {})
    priority = dominant_cfg.get("PRIORITY", {})
    demotion_on = bool(dominant_cfg.get("low_n_demotion", True))

    def rank_key(row: dict) -> tuple[int, int, str]:
        letter = row["combo"]
        low_n = 1 if (demotion_on and not is_validated_combo(letter)) else 0
        return (low_n, -int(priority.get(letter, 0)), letter)

    return sorted(actives, key=rank_key)[0]


def _intent_side(combo: str, status: str, resolved: str | None) -> str:
    if combo in ("C", "D", "E"):
        return "ADVERSE" if status in ACTIVE_CLASS else "WATCH_BEAR"
    if combo in ("B", "F"):
        return "BENIGN" if status in ACTIVE_CLASS else "WATCH_BULL"
    if combo == "G":
        return "ADVERSE" if status in ACTIVE_CLASS else "WATCH_BEAR"
    if combo == "A":
        if status == "CONTESTED":
            return "MIXED"
        if status in ACTIVE_CLASS:
            if resolved == "FEARFUL":
                return "ADVERSE"
            if resolved == "BRAVE":
                return "BENIGN"
        return "NEUTRAL"
    return "NEUTRAL"


def _classify_bucket(actives: list[dict], dominant: dict | None) -> str:
    """Map Friday combo state → BENIGN / ADVERSE / MIXED (D5-informed).

    MIXED only when ACTIVE-class combos conflict (bullish + bearish/cautionary).
    WATCH-only bearish legs → BENIGN (caution without dominant adverse signal).
    """
    active_sides = {_intent_side(a["combo"], a["status"], a.get("resolved_intent")) for a in actives}
    if "MIXED" in active_sides:
        return "MIXED"
    if "BENIGN" in active_sides and "ADVERSE" in active_sides:
        return "MIXED"
    if dominant:
        d_side = _intent_side(
            dominant["combo"],
            dominant["status"],
            dominant.get("resolved_intent"),
        )
        if d_side == "ADVERSE":
            return "ADVERSE"
        if d_side == "MIXED":
            return "MIXED"
    if "ADVERSE" in active_sides:
        return "ADVERSE"
    return "BENIGN"


@dataclass
class ComboCReplay:
    """Point-in-time Combo C persistence (avoids live combo_c_cancel DB flag)."""

    active: bool = False
    wti_potential_week: int = 0
    cancel_cfg: dict = field(default_factory=dict)

    def still_active(self) -> bool:
        return self.active

    def c_new_entry(self, readings: dict) -> bool:
        c_cfg = load_config().get("named_combos", {}).get("C", {})
        wti_r = readings.get("WTI")
        cpi_r = readings.get("CPI")
        walcl_r = readings.get("WALCL")
        if not (wti_r and cpi_r and walcl_r):
            return False
        return bool(
            (wti_r.get("raw_value") or 0) >= c_cfg.get("wti_4wk_min", 10.0)
            and (cpi_r.get("raw_value") or 0) >= c_cfg.get("cpi_surprise_min", 0.2)
            and abs(walcl_r.get("raw_value") or 0) < 0.8
        )

    def after_friday(self, ds: str, readings: dict) -> None:
        """Update C state after Friday evaluation (for next week's persist)."""
        if self.c_new_entry(readings):
            self.active = True
            self.wti_potential_week = 0
            return
        if not self.active:
            return
        wti_r = readings.get("WTI")
        wti_val = wti_r.get("raw_value") if wti_r else None
        wti_max = self.cancel_cfg.get("wti_4wk_max_pct", 5.0)
        need_weeks = self.cancel_cfg.get("consecutive_fridays", 4)
        wti_ok = wti_val is not None and wti_val < wti_max
        cpi_ok, _ = cpi_leg_passes(ds)
        if wti_ok and cpi_ok:
            self.wti_potential_week = min(self.wti_potential_week + 1, need_weeks)
        else:
            self.wti_potential_week = 0
        if self.wti_potential_week >= need_weeks:
            self.active = False


def _empty_friday_state(ds: str) -> dict:
    return {
        "evaluation_date": ds,
        "dominant_combo": "",
        "dominant_status": "",
        "bucket": "BENIGN",
        "design_intent": "NEUTRAL",
        "resolved_intent": "",
        "active_combos": "",
        "watch_combos": "",
        "combo_sides": "",
    }


def _evaluate_friday(ds: str, c_replay: ComboCReplay) -> dict:
    readings = get_readings_as_of(ds)
    if not readings:
        return _empty_friday_state(ds)

    regime = build_python_regime(ds, readings)
    with patch.object(cd, "load_all_series", _cached_load_all_series), patch.object(
        cd, "_combo_c_still_active", c_replay.still_active
    ):
        fires = detect_named_combos(ds, readings, macro_regime=regime)
    named = [_fire_row(f) for f in fires if f.runic_combo in "ABCDEFG"]

    actives = [c for c in named if c["status"] in ACTIVE_CLASS]
    watch = [c for c in named if c["status"] == "WATCH"]
    dominant = _resolve_dominant(actives)
    bucket = _classify_bucket(actives, dominant)

    c_replay.after_friday(ds, readings)

    design = "NEUTRAL"
    resolved = ""
    if dominant:
        combo = dominant["combo"]
        if combo == "A":
            design = dominant.get("resolved_intent") or "NEUTRAL"
            resolved = dominant.get("resolved_intent") or ""
        else:
            design = DESIGN_INTENT.get(combo, "NEUTRAL")

    sides = ";".join(
        f"{c['combo']}:{_intent_side(c['combo'], c['status'], c.get('resolved_intent'))}"
        for c in named
    )

    return {
        "evaluation_date": ds,
        "dominant_combo": dominant["combo"] if dominant else "",
        "dominant_status": dominant["status"] if dominant else "",
        "bucket": bucket,
        "design_intent": design,
        "resolved_intent": resolved,
        "active_combos": ";".join(sorted({c["combo"] for c in actives})),
        "watch_combos": ";".join(sorted({c["combo"] for c in watch})),
        "combo_sides": sides,
    }


def _load_calendar_dates(start: str, end: str) -> list[str]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT date FROM daily_readings
            WHERE date >= ? AND date <= ?
            ORDER BY date ASC
            """,
            (start, end),
        ).fetchall()
    return [r[0] for r in rows]


def build_series(*, start: str = START_DATE, end: str = END_DATE) -> list[dict]:
    fridays = _fridays(start, end)
    # Clip to dates with readings
    with get_connection() as conn:
        max_row = conn.execute("SELECT MAX(date) FROM daily_readings").fetchone()
    if max_row and max_row[0]:
        max_d = max_row[0]
        fridays = [d for d in fridays if d <= max_d]

    _cached_load_all_series(force=True)
    c_replay = ComboCReplay(cancel_cfg=load_config().get("combo_c_cancel", {}))
    friday_states: dict[str, dict] = {}
    for i, ds in enumerate(fridays, 1):
        friday_states[ds] = _evaluate_friday(ds, c_replay)
        if i % 25 == 0 or i == len(fridays):
            print(f"  ... evaluated {i}/{len(fridays)} Fridays ({ds})", flush=True)

    calendar = _load_calendar_dates(start, min(end, max_row[0] if max_row else end))
    friday_dates = sorted(friday_states)
    series: list[dict] = []
    idx = 0
    current: dict | None = None

    for day in calendar:
        while idx < len(friday_dates) and friday_dates[idx] <= day:
            current = friday_states[friday_dates[idx]]
            idx += 1
        if current is None:
            row = {
                "date": day,
                "bucket": "BENIGN",
                "evaluation_date": "",
                "dominant_combo": "",
                "dominant_status": "",
                "design_intent": "NEUTRAL",
                "resolved_intent": "",
                "active_combos": "",
                "watch_combos": "",
                "combo_sides": "",
                "is_forward_filled": False,
            }
        else:
            row = {
                "date": day,
                "is_forward_filled": day != current["evaluation_date"],
                **current,
            }
        series.append(row)
    return series


def _bucket_counts(rows: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for r in rows:
        counts[r["bucket"]] += 1
    return dict(counts)


def _write_csv(path: Path, rows: list[dict]) -> None:
    fields = [
        "date",
        "bucket",
        "dominant_combo",
        "dominant_status",
        "design_intent",
        "resolved_intent",
        "active_combos",
        "watch_combos",
        "evaluation_date",
        "is_forward_filled",
        "series_version",
        "dominant_rule",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "date": row["date"],
                    "bucket": row["bucket"],
                    "dominant_combo": row.get("dominant_combo", ""),
                    "dominant_status": row.get("dominant_status", ""),
                    "design_intent": row.get("design_intent", ""),
                    "resolved_intent": row.get("resolved_intent", ""),
                    "active_combos": row.get("active_combos", ""),
                    "watch_combos": row.get("watch_combos", ""),
                    "evaluation_date": row.get("evaluation_date", ""),
                    "is_forward_filled": "true" if row.get("is_forward_filled") else "false",
                    "series_version": SERIES_VERSION,
                    "dominant_rule": "CONFIG_PRIORITY_v2_B_ABOVE_C_LOW_N_DEMOTED",
                }
            )


def _write_fridays_csv(path: Path, rows: list[dict]) -> None:
    fridays = [r for r in rows if not r.get("is_forward_filled") and r.get("evaluation_date")]
    _write_csv(path, fridays)


def _write_json(path: Path, rows: list[dict], meta: dict) -> None:
    payload = {
        "task": "D1_regime_bucket_feed",
        "series_version": SERIES_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "meta": meta,
        "bucket_counts": _bucket_counts(rows),
        "friday_bucket_counts": _bucket_counts(
            [r for r in rows if not r.get("is_forward_filled") and r.get("evaluation_date")]
        ),
        "rows": len(rows),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_md(path: Path, rows: list[dict], meta: dict) -> None:
    counts = _bucket_counts(rows)
    fri_counts = _bucket_counts(
        [r for r in rows if not r.get("is_forward_filled") and r.get("evaluation_date")]
    )
    lines = [
        "# D1 — Regime Bucket Feed",
        "",
        f"**Date:** {DATE_TAG}  ",
        f"**Series version:** `{SERIES_VERSION}`  ",
        f"**Owner:** Divyanshu  ",
        f"**Consumer:** Ahil P3 (headline stats per regime)",
        "",
        "## Summary",
        "",
        f"- Daily rows: **{len(rows)}** ({meta['start_date']} → {meta['end_date']})",
        f"- Friday evaluations: **{meta['friday_count']}**",
        f"- Bucket counts (daily): {', '.join(f'{k}={v}' for k, v in sorted(counts.items()))}",
        f"- Bucket counts (Fridays): {', '.join(f'{k}={v}' for k, v in sorted(fri_counts.items()))}",
        "",
        "## Bucket definitions (post-D5)",
        "",
        "| Bucket | Rule |",
        "|--------|------|",
        "| **ADVERSE** | Dominant combo bearish/cautionary at recalibrated gates: C/D/E ACTIVE, G ACTIVE, A TIGHT_MONEY |",
        "| **BENIGN** | Dominant B/F bullish, A EASY_MONEY, or no adverse dominant |",
        "| **MIXED** | Conflicting ACTIVE combos (bullish + bearish/cautionary), or Combo A CONTESTED |",
        "",
        "## Recalibrated gates (D5 dependency)",
        "",
        "| Combo | Gates | Validated horizon | D5 overall bear hit |",
        "|-------|-------|-------------------|---------------------|",
        f"| D | VXTS≥{RECALIBRATED_GATES['D']['vxts_min']} / CFTC≥{RECALIBRATED_GATES['D']['cftc_min_pctile']} / VIX≤{RECALIBRATED_GATES['D']['vix_max']} ({RECALIBRATED_GATES['D']['legs_required']}-of-3) | {RECALIBRATED_GATES['D']['validated_horizon']} | {RECALIBRATED_GATES['D']['d5_bear_hit_pct']}% |",
        f"| E | CAPE≥{RECALIBRATED_GATES['E']['cape_min']} / NFCI≤{RECALIBRATED_GATES['E']['nfci_easy_max']} / CFTC≥{RECALIBRATED_GATES['E']['cftc_min_pctile']} ({RECALIBRATED_GATES['E']['legs_required']}-of-3) | {', '.join(RECALIBRATED_GATES['E']['validated_horizons'])} | {RECALIBRATED_GATES['E']['d5_bear_hit_pct']}% |",
        "",
        "## Point-in-time discipline",
        "",
        "- Each Friday: `get_readings_as_of(date)` + `detect_named_combos()` on recalibrated `CONFIG.yaml` gates.",
        "- Mon–Thu: forward-fill last Friday bucket (`is_forward_filled=true`).",
        "- Percentiles in `daily_readings` are as-of that date (backfill expanding history).",
        "",
        "## Section code map (report PDF)",
        "",
        "| Code | Meaning |",
        "|------|---------|",
        "| **B2** | Dual percentile storage (unconditional + regime_pctile) |",
        "| **F4** | Steepening-of-inversion short grid (mechanism-only; not in bucket feed) |",
        "| **D5** | Fed-cycle re-slice on recalibrated D/E — defines ADVERSE bearish combos |",
        "",
        "## Artifacts",
        "",
        f"- `D1_regime_bucket_daily_{DATE_TAG}.csv`",
        f"- `D1_regime_bucket_fridays_{DATE_TAG}.csv`",
        f"- `D1_regime_bucket_feed_{DATE_TAG}.json`",
        f"- `D1_regime_bucket_feed_{DATE_TAG}.md` (this file)",
        "",
        "## Caveats",
        "",
        "- Combo C: sequential replay of 4-Friday cancel rule (not live `combo_c_cancel` flag).",
        "- Combo F episode weeks read `combo_fires` history ≤ as_of (point-in-time).",
        "- WATCH-only bearish legs (D/E partial) classify as BENIGN unless dominant is adverse.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="D1 regime bucket feed export")
    parser.add_argument("--start", default=START_DATE)
    parser.add_argument("--end", default=END_DATE)
    args = parser.parse_args()

    print(f"D1 regime bucket feed — {SERIES_VERSION}", flush=True)
    print(f"  Range: {args.start} → {args.end}", flush=True)
    rows = build_series(start=args.start, end=args.end)

    with get_connection() as conn:
        max_d = conn.execute("SELECT MAX(date) FROM daily_readings").fetchone()[0]

    meta = {
        "start_date": args.start,
        "end_date": min(args.end, max_d) if max_d else args.end,
        "friday_count": sum(1 for r in rows if not r.get("is_forward_filled") and r.get("evaluation_date")),
        "config_source": "macro_intelligence/CONFIG.yaml",
        "d5_artifact": f"D5_fed_cycle_reslice_2026-07-16.json",
        "recalibrated_gates": RECALIBRATED_GATES,
        "dominant_rule": "CONFIG_PRIORITY_v2_B_ABOVE_C_LOW_N_DEMOTED",
        "point_in_time": "daily_readings as-of + Combo C sequential replay + Friday forward-fill",
        "series_version_note": (
            "v1.2 applies Rohit 2026-08-06: B above C, and any combo with fewer than 5 "
            "matured episodes ranks below every validated combo (C n=3). "
            "v1.1 fixed C live-flag leak and WATCH→MIXED over-classification."
        ),
    }

    daily_csv = OUT_DIR / f"D1_regime_bucket_daily_{DATE_TAG}.csv"
    fridays_csv = OUT_DIR / f"D1_regime_bucket_fridays_{DATE_TAG}.csv"
    json_path = OUT_DIR / f"D1_regime_bucket_feed_{DATE_TAG}.json"
    md_path = OUT_DIR / f"D1_regime_bucket_feed_{DATE_TAG}.md"

    _write_csv(daily_csv, rows)
    _write_fridays_csv(fridays_csv, rows)
    _write_json(json_path, rows, meta)
    _write_md(md_path, rows, meta)

    counts = _bucket_counts(rows)
    print(f"Wrote {len(rows)} daily rows → {daily_csv}", flush=True)
    print(f"  buckets: {counts}", flush=True)
    print(f"  artifacts: {fridays_csv.name}, {json_path.name}, {md_path.name}", flush=True)


if __name__ == "__main__":
    main()
