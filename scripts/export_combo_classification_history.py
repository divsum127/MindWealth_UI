#!/usr/bin/env python3
"""Export date-indexed dominant combo + adverse_regime series for Test 3 / Ahil.

Dominant rule: CONFIG.yaml fixed PRIORITY (same as resolve_dominant).
Adverse rule: user-specified Test 3 conditioning flag (see module docstring in output README).
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.macro_intelligence.config import load_config

DB_PATH = _ROOT / "macro_intelligence" / "data" / "runic.db"
DEFAULT_OUT = _ROOT / "testing" / "5_regime_uplift" / "combo_classification_history.csv"

ACTIVE_CLASS = frozenset({"ACTIVE", "PARTIAL", "CONFIRMED", "CONFIRMED_3_OF_3"})
STATUS_RANK = {
    "ACTIVE": 5,
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


def _parse_a_vote(macro_regime: str | None) -> str | None:
    if not macro_regime:
        return None
    try:
        payload = json.loads(macro_regime)
    except json.JSONDecodeError:
        return None
    vote = payload.get("a_vote")
    if not vote:
        return None
    vote = str(vote).upper()
    if vote in ("FEARFUL", "TIGHT_MONEY"):
        return "FEARFUL"
    if vote in ("BRAVE", "EASY_MONEY"):
        return "BRAVE"
    return vote


def _resolve_dominant(actives: list[dict]) -> dict | None:
    if not actives:
        return None
    priority = load_config().get("dominant", {}).get("PRIORITY", {})

    def rank_key(row: dict) -> tuple[int, str]:
        letter = row["combo"]
        return (-int(priority.get(letter, 0)), letter)

    return sorted(actives, key=rank_key)[0]


def _adverse_regime(dominant: dict | None) -> bool:
    if not dominant:
        return False
    combo = dominant["combo"]
    status = dominant["status"]
    if combo in ("C", "D", "E"):
        return True
    if combo == "G" and status in ACTIVE_CLASS:
        return True
    if combo == "A":
        return dominant.get("resolved_intent") == "FEARFUL"
    return False


def _design_intent(dominant: dict | None) -> str:
    if not dominant:
        return "NEUTRAL"
    combo = dominant["combo"]
    if combo == "A":
        return dominant.get("resolved_intent") or "NEUTRAL"
    return DESIGN_INTENT.get(combo, "NEUTRAL")


def _load_friday_states(conn: sqlite3.Connection) -> dict[str, dict]:
    rows = conn.execute(
        """
        SELECT date, runic_combo, status, macro_regime
        FROM combo_fires
        WHERE runic_combo IN ('A','B','C','D','E','F','G')
        ORDER BY date ASC, combo_id ASC
        """
    ).fetchall()

    by_date: dict[str, dict[str, dict]] = defaultdict(dict)
    for row in rows:
        date, letter, status, macro_regime = row
        letter = str(letter)
        status = str(status or "")
        current = by_date[date].get(letter)
        candidate = {
            "combo": letter,
            "status": status,
            "resolved_intent": _parse_a_vote(macro_regime),
        }
        if current is None or STATUS_RANK.get(status, -1) > STATUS_RANK.get(current["status"], -1):
            by_date[date][letter] = candidate

    fridays: dict[str, dict] = {}
    for date in sorted(by_date):
        combos = by_date[date]
        actives = [c for c in combos.values() if c["status"] in ACTIVE_CLASS]
        watch = [c["combo"] for c in combos.values() if c["status"] == "WATCH"]
        dominant_row = _resolve_dominant(actives)
        fridays[date] = {
            "evaluation_date": date,
            "dominant_combo": dominant_row["combo"] if dominant_row else "",
            "dominant_status": dominant_row["status"] if dominant_row else "",
            "resolved_intent": (dominant_row or {}).get("resolved_intent") or "",
            "design_intent": _design_intent(dominant_row),
            "adverse_regime": _adverse_regime(dominant_row),
            "active_combos": ";".join(sorted({c["combo"] for c in actives})),
            "watch_combos": ";".join(sorted(set(watch))),
        }
    return fridays


def _load_calendar_dates(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT DISTINCT date FROM daily_readings ORDER BY date ASC").fetchall()
    return [r[0] for r in rows]


def build_series(*, forward_fill: bool = True) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    try:
        fridays = _load_friday_states(conn)
        if not forward_fill:
            return [
                {
                    "date": d,
                    "is_forward_filled": False,
                    "dominant_rule": "CONFIG_PRIORITY_v1",
                    **state,
                }
                for d, state in sorted(fridays.items())
            ]

        calendar = _load_calendar_dates(conn)
        friday_dates = sorted(fridays)
        series: list[dict] = []
        idx = 0
        current: dict | None = None
        for day in calendar:
            while idx < len(friday_dates) and friday_dates[idx] <= day:
                current = fridays[friday_dates[idx]]
                idx += 1
            if current is None:
                row = {
                    "date": day,
                    "evaluation_date": "",
                    "dominant_combo": "",
                    "dominant_status": "",
                    "resolved_intent": "",
                    "design_intent": "NEUTRAL",
                    "adverse_regime": False,
                    "active_combos": "",
                    "watch_combos": "",
                    "is_forward_filled": False,
                    "dominant_rule": "CONFIG_PRIORITY_v1",
                }
            else:
                row = {
                    "date": day,
                    "is_forward_filled": day != current["evaluation_date"],
                    "dominant_rule": "CONFIG_PRIORITY_v1",
                    **current,
                }
            series.append(row)
        return series
    finally:
        conn.close()


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "date",
        "dominant_combo",
        "dominant_status",
        "design_intent",
        "resolved_intent",
        "adverse_regime",
        "active_combos",
        "watch_combos",
        "evaluation_date",
        "is_forward_filled",
        "dominant_rule",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    k: (
                        "true"
                        if k in ("adverse_regime", "is_forward_filled") and row.get(k)
                        else "false"
                        if k in ("adverse_regime", "is_forward_filled")
                        else row.get(k, "")
                    )
                    for k in fields
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Export combo classification / adverse regime CSV")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--fridays-only",
        action="store_true",
        help="Emit evaluation Fridays only (no forward-fill to daily calendar)",
    )
    args = parser.parse_args()

    rows = build_series(forward_fill=not args.fridays_only)
    write_csv(args.out, rows)

    adverse_n = sum(1 for r in rows if r["adverse_regime"])
    dominant_n = sum(1 for r in rows if r.get("dominant_combo"))
    print(f"Wrote {len(rows)} rows -> {args.out}")
    print(f"  dates with dominant combo: {dominant_n}")
    print(f"  adverse_regime=true: {adverse_n}")


if __name__ == "__main__":
    main()
