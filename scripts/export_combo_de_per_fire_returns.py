#!/usr/bin/env python3
"""Export per-trigger SPX forward returns for Combo D and Combo E."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.data.yahoo_pull import fetch_yahoo_close  # noqa: E402
from src.macro_intelligence.db.connection import get_connection, init_db  # noqa: E402
from src.macro_intelligence.engine.forward_returns import (  # noqa: E402
    _nyse_sessions,
    forward_return_pct,
)

DEFAULT_OUT = (
    ROOT / "testing/macro_th_exp/testingv1_feedback/csv_exports/combo_de_per_fire_returns"
)

# Trading-day offsets (NYSE sessions) from fire date.
COMBO_D_HORIZONS: list[tuple[str, int]] = [
    ("1W", 5),
    ("2W", 10),
    ("3W", 15),
    ("4W", 20),
    ("1M", 21),
    ("2M", 42),
]

# Combo E horizon sweep: 1M–3M then 3M steps through 18M (same trading days as T11 sweep).
COMBO_E_HORIZONS: list[tuple[str, int]] = [
    ("1M", 21),
    ("2M", 42),
    ("3M", 63),
    ("6M", 126),
    ("9M", 189),
    ("12M", 252),
    ("15M", 315),
    ("18M", 378),
]

STATUS_RANK = {
    "ACTIVE": 5,
    "CONFIRMED_3_OF_3": 4,
    "CONFIRMED": 3,
    "WATCH": 2,
    "INACTIVE": 1,
}


def _fetch_fires(letter: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT combo_id, date, status
            FROM combo_fires
            WHERE runic_combo = ?
            ORDER BY date, combo_id
            """,
            (letter,),
        ).fetchall()
    by_date: dict[str, dict[str, Any]] = {}
    for row in rows:
        d = row["date"]
        existing = by_date.get(d)
        rank = STATUS_RANK.get(row["status"] or "", 0)
        if existing is None or rank > existing["_rank"]:
            by_date[d] = {
                "trigger_date": d,
                "status": row["status"],
                "combo_id": row["combo_id"],
                "_rank": rank,
            }
    fires = sorted(by_date.values(), key=lambda x: x["trigger_date"])
    for f in fires:
        f.pop("_rank", None)
    return fires


def _spx_change_col(label: str) -> str:
    return f"spx_change_pct_{label}"


def _bear_hit_col(label: str) -> str:
    return f"bear_hit_{label}"


def _build_rows(
    fires: list[dict[str, Any]],
    horizons: list[tuple[str, int]],
    spx: pd.Series,
    sessions: pd.DatetimeIndex,
    direction: str,
) -> list[dict[str, Any]]:
    bullish = direction == "bullish"
    out: list[dict[str, Any]] = []
    for fire in fires:
        dt = pd.Timestamp(fire["trigger_date"])
        row: dict[str, Any] = {
            "trigger_date": fire["trigger_date"],
            "status": fire["status"],
            "combo_id": fire["combo_id"],
        }
        for label, days in horizons:
            chg_col = _spx_change_col(label)
            hit_col = _bear_hit_col(label)
            ret = forward_return_pct(spx, dt, days, sessions=sessions)
            row[chg_col] = round(ret, 4) if ret is not None else ""
            if ret is not None:
                hit = (ret > 0) if bullish else (ret < 0)
                row[hit_col] = 1 if hit else 0
            else:
                row[hit_col] = ""
        out.append(row)
    return out


def _summary(
    letter: str,
    fires: list[dict[str, Any]],
    horizons: list[tuple[str, int]],
    rows: list[dict[str, Any]],
    direction: str,
    spx_start: str,
    spx_end: str,
) -> dict[str, Any]:
    bullish = direction == "bullish"
    horizon_stats = []
    for label, days in horizons:
        col = _spx_change_col(label)
        hit_col = _bear_hit_col(label)
        mature = [r for r in rows if r.get(col) != ""]
        n = len(mature)
        if n:
            hit_rate = sum(1 for r in mature if r.get(hit_col) == 1) / n * 100
            avg_ret = sum(float(r[col]) for r in mature) / n
        else:
            hit_rate = None
            avg_ret = None
        horizon_stats.append(
            {
                "horizon": label,
                "trading_days": days,
                "n_mature": n,
                "hit_rate_pct": round(hit_rate, 1) if hit_rate is not None else None,
                "avg_spx_return_pct": round(avg_ret, 2) if avg_ret is not None else None,
            }
        )
    best = max(
        (h for h in horizon_stats if h["hit_rate_pct"] is not None),
        key=lambda h: h["hit_rate_pct"],
        default=None,
    )
    return {
        "combo": letter,
        "direction": direction,
        "backtest_period": {
            "first_fire": fires[0]["trigger_date"] if fires else None,
            "last_fire": fires[-1]["trigger_date"] if fires else None,
            "n_trigger_dates": len(fires),
            "spx_price_history_start": spx_start,
            "spx_price_history_end": spx_end,
            "note": (
                "Fires from combo_fires backfill (named combo detector replay). "
                "Returns mature only when full forward window exists in ^GSPC history."
            ),
        },
        "horizons": horizon_stats,
        "max_hit_rate_horizon": best["horizon"] if best else None,
        "max_hit_rate_pct": best["hit_rate_pct"] if best else None,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


COMBO_NAMES = {
    "D": "FOMO Top",
    "E": "Valuation Extreme",
}


def _analysis_blurb(letter: str, summary: dict[str, Any]) -> list[str]:
    """Short interpretation lines for the CSV header block."""
    hs = summary["horizons"]
    period = summary["backtest_period"]
    best_h = summary.get("max_hit_rate_horizon")
    best_pct = summary.get("max_hit_rate_pct")
    signal_kind = (
        "tactical top signal" if letter == "D" else "structural valuation-risk signal"
    )
    lines = [
        (
            f"Bear hit rate peaks at {best_h} ({best_pct}%) across mature episodes. "
            f"Longer horizons show lower bear-hit % — typical for a {signal_kind} "
            f"in a structurally bullish sample period."
        ),
    ]
    avg_rets = [h["avg_spx_return_pct"] for h in hs if h["avg_spx_return_pct"] is not None]
    if avg_rets and all(r > 0 for r in avg_rets):
        lines.append(
            "Average SPX change is positive at every horizon (bull drift dominates); "
            "bear_hit=1 only when SPX is negative on that row."
        )
    elif avg_rets:
        neg = [h for h in hs if h["avg_spx_return_pct"] is not None and h["avg_spx_return_pct"] < 0]
        if neg:
            lines.append(
                f"Average SPX change turns negative from {neg[0]['horizon']} onward "
                f"({neg[0]['avg_spx_return_pct']:+.2f}%), consistent with slow structural headwind."
            )
    if letter == "D":
        lines.append(
            "Validated primary horizon = 5D (1W). Cheatsheet ~70%+ figures used bullish/longer "
            "windows; this table uses bearish SPX-down hit on all fires in combo_fires."
        )
    elif letter == "E":
        lines.append(
            "Horizon sweep: 1M, 2M, 3M, 6M, 9M, 12M, 15M, 18M (NYSE trading days). "
            "15M/18M computed from ^GSPC on the fly (not stored in forward_returns). "
            "Bear hit typically peaks at shorter horizons; 12M is nightly primary."
        )
    lines.append(
        f"Population: {period['n_trigger_dates']} distinct trigger dates "
        f"({period['first_fire']} → {period['last_fire']})."
    )
    return lines


def _summary_header_lines(
    letter: str,
    summary: dict[str, Any],
    horizons: list[tuple[str, int]],
) -> list[str]:
    """Comment-prefixed summary block written above the data table."""
    name = COMBO_NAMES.get(letter, letter)
    period = summary["backtest_period"]
    hs = summary["horizons"]
    lines: list[str] = [
        f"# SUMMARY AND ANALYSIS — Combo {letter} ({name})",
        f"# Generated: {summary['generated_at']}",
        f"# Direction: {summary['direction']} | bear_hit=1 when SPX change % < 0",
        (
            f"# Backtest: {period['n_trigger_dates']} triggers | "
            f"{period['first_fire']} → {period['last_fire']} | "
            f"^GSPC history {period['spx_price_history_start']} → {period['spx_price_history_end']}"
        ),
        "#",
        "# horizon,trading_days,n_mature,avg_spx_change_pct,bear_hit_rate_pct",
    ]
    for h in hs:
        avg = h["avg_spx_return_pct"]
        hr = h["hit_rate_pct"]
        lines.append(
            f"# {h['horizon']},{h['trading_days']},{h['n_mature']},"
            f"{avg if avg is not None else ''},{hr if hr is not None else ''}"
        )
    lines.append("#")
    lines.append("# Analysis:")
    for para in _analysis_blurb(letter, summary):
        lines.append(f"# {para}")
    lines.append("#")
    lines.append("# --- PER-TRIGGER DATA BELOW ---")
    return lines


def _write_csv(
    path: Path,
    rows: list[dict[str, Any]],
    fieldnames: list[str],
    summary_lines: list[str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        if summary_lines:
            f.write("\n".join(summary_lines) + "\n")
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def export(out_dir: Path, spx_start: str = "1990-01-01") -> dict[str, Any]:
    init_db()
    spx = fetch_yahoo_close("^GSPC", spx_start)
    sessions = _nyse_sessions()
    spx_end = str(spx.index.max().date()) if not spx.empty else None

    meta: dict[str, Any] = {
        "output_dir": str(out_dir),
        "column_definitions": {
            "trigger_date": "Combo fire / trigger date (NYSE calendar day).",
            "spx_change_pct_{horizon}": (
                "SPX (^GSPC) percent change from trigger close to horizon close. "
                "Positive = SPX up; negative = SPX down. 4 decimal places. "
                "Empty = forward window not yet mature in price history."
            ),
            "bear_hit_{horizon}": (
                "Binary bearish hit flag for Combo D/E (bearish combos). "
                "1 = SPX fell (spx_change_pct < 0). "
                "0 = SPX rose or was flat (spx_change_pct >= 0). "
                "NOT a percent return — do not read 0 as 0% SPX change."
            ),
        },
        "combos": {},
    }

    specs = [
        ("D", COMBO_D_HORIZONS, "bearish", "combo_d_per_fire_returns.csv"),
        ("E", COMBO_E_HORIZONS, "bearish", "combo_e_per_fire_returns.csv"),
    ]

    for letter, horizons, direction, filename in specs:
        fires = _fetch_fires(letter)
        rows = _build_rows(fires, horizons, spx, sessions, direction)
        change_cols = [_spx_change_col(label) for label, _ in horizons]
        hit_cols = [_bear_hit_col(label) for label, _ in horizons]
        fieldnames = ["trigger_date", "status", "combo_id", *change_cols, *hit_cols]
        csv_path = out_dir / filename
        summary = _summary(letter, fires, horizons, rows, direction, spx_start, spx_end or "")
        header_lines = _summary_header_lines(letter, summary, horizons)
        _write_csv(csv_path, rows, fieldnames, summary_lines=header_lines)
        meta["combos"][letter] = {
            "csv": str(csv_path),
            "summary": summary,
            "spx_change_columns": change_cols,
            "bear_hit_columns": hit_cols,
        }

    meta_path = out_dir / "combo_de_per_fire_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    meta["meta_json"] = str(meta_path)
    return meta


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    parser.add_argument("--spx-start", default="1990-01-01")
    args = parser.parse_args()
    meta = export(Path(args.out_dir), spx_start=args.spx_start)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
