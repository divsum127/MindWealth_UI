#!/usr/bin/env python3
"""Print Part H combo promotion candidates (with fire dates) from combo_discovery JSON."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

COMBO_DISCOVERY_DIR = ROOT / "macro_intelligence" / "analysis" / "combo_discovery"

CSV_COLUMNS = [
    "signature",
    "var_ids",
    "combo_size",
    "bullish",
    "n_fires",
    "primary_hit_rate",
    "primary_avg_return",
    "spx_3m_hit_rate",
    "spx_3m_avg_return",
    "beta_pass",
    "directionality_dims_passing",
    "story_status",
    "fire_dates_count",
    "first_fire_date",
    "last_fire_date",
]


def _latest_combo_discovery_json() -> Path:
    candidates = sorted(COMBO_DISCOVERY_DIR.glob("combo_discovery_*.json"))
    if not candidates:
        raise FileNotFoundError(f"No combo_discovery_*.json under {COMBO_DISCOVERY_DIR}")
    return candidates[-1]


def _load_payload(json_path: Path) -> dict:
    with json_path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _horizon_field(entry: dict, horizon: str, field: str) -> float | None:
    horizons = entry.get("horizons") or {}
    block = horizons.get(horizon) or {}
    value = block.get(field)
    return value if value is not None else None


def _row_from_entry(entry: dict) -> dict[str, object]:
    fire_dates = sorted(entry.get("fire_dates") or [])
    return {
        "signature": entry.get("signature", ""),
        "var_ids": "|".join(entry.get("var_ids") or []),
        "combo_size": entry.get("combo_size"),
        "bullish": entry.get("bullish"),
        "n_fires": entry.get("n_fires"),
        "primary_hit_rate": entry.get("primary_hit_rate"),
        "primary_avg_return": entry.get("primary_avg_return"),
        "spx_3m_hit_rate": _horizon_field(entry, "spx_3m", "hit_rate"),
        "spx_3m_avg_return": _horizon_field(entry, "spx_3m", "avg_return"),
        "beta_pass": entry.get("beta_pass"),
        "directionality_dims_passing": entry.get("directionality_dims_passing"),
        "story_status": entry.get("story_status"),
        "fire_dates_count": len(fire_dates),
        "first_fire_date": fire_dates[0] if fire_dates else "",
        "last_fire_date": fire_dates[-1] if fire_dates else "",
    }


def _sorted_promotion_candidates(payload: dict) -> list[dict]:
    candidates = list(payload.get("promotion_candidates") or [])
    candidates.sort(
        key=lambda e: (
            -(e.get("primary_hit_rate") or 0),
            -(e.get("n_fires") or 0),
            e.get("signature") or "",
        )
    )
    return candidates


def write_promotion_candidates_csv(payload: dict, out_path: Path) -> int:
    rows = [_row_from_entry(e) for e in _sorted_promotion_candidates(payload)]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def print_promotion_candidates(payload: dict, json_path: Path) -> int:
    candidates = _sorted_promotion_candidates(payload)
    run_date = payload.get("run_date", "unknown")
    summary = payload.get("summary") or {}
    print(f"Source: {json_path}")
    print(f"Run date: {run_date}")
    print(
        f"Promotion candidates: {len(candidates)} "
        f"(summary says {summary.get('promotion_candidates', '?')})"
    )
    print("-" * 72)
    for idx, entry in enumerate(candidates, start=1):
        fire_dates = sorted(entry.get("fire_dates") or [])
        spx_3m_hr = _horizon_field(entry, "spx_3m", "hit_rate")
        spx_3m_avg = _horizon_field(entry, "spx_3m", "avg_return")
        print(
            f"{idx:2}. {entry.get('signature')}  "
            f"n={entry.get('n_fires')}  "
            f"HR={entry.get('primary_hit_rate')}  "
            f"avg={entry.get('primary_avg_return')}%  "
            f"spx_3m={spx_3m_hr}/{spx_3m_avg}%  "
            f"beta={entry.get('beta_pass')}  "
            f"dir_dims={entry.get('directionality_dims_passing')}  "
            f"story={entry.get('story_status')}"
        )
        if fire_dates:
            print(f"    fires ({len(fire_dates)}): {', '.join(fire_dates)}")
        else:
            print("    fires (0): none")
    return len(candidates)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Show Part H combo promotion candidates from combo_discovery JSON"
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        help="Path to combo_discovery JSON (default: latest in analysis/combo_discovery/)",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help="Write compact review CSV to this path",
    )
    args = parser.parse_args()

    json_path = args.json.resolve() if args.json else _latest_combo_discovery_json()
    if not json_path.is_file():
        print(f"JSON not found: {json_path}", file=sys.stderr)
        return 1

    payload = _load_payload(json_path)
    count = print_promotion_candidates(payload, json_path)

    if args.csv:
        csv_path = args.csv.resolve()
        written = write_promotion_candidates_csv(payload, csv_path)
        print("-" * 72)
        print(f"Wrote CSV ({written} rows): {csv_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
