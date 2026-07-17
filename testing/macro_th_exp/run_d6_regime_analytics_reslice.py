#!/usr/bin/env python3
"""D6 follow-up — re-run regime slice tables with analytics collapse (PIVOTING→EASING, 9→4 liquidity)."""

from __future__ import annotations

import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.analysis.regime_experiments.fm_events import (  # noqa: E402
    extract_fm_band_events,
    load_regime_v2_map,
)
from src.macro_intelligence.analysis.regime_experiments.metrics import (  # noqa: E402
    slice_by_regime,
    summarize_returns,
)
from src.macro_intelligence.data.yahoo_pull import fetch_yahoo_close  # noqa: E402
from src.macro_intelligence.db.connection import get_connection  # noqa: E402
from src.macro_intelligence.engine.regime_v2_shadow import (  # noqa: E402
    collapse_liquidity_v2_analytics,
    fed_cycle_v2_analytics,
    regime_value_for_analytics,
)

OUT_DIR = Path(__file__).resolve().parent
DATE_TAG = datetime.now(UTC).strftime("%Y-%m-%d")
HORIZONS = ["spx_1m", "spx_3m", "spx_6m", "spx_9m", "spx_12m"]
HORIZON_LABELS = {"spx_1m": "1M", "spx_3m": "3M", "spx_6m": "6M", "spx_9m": "9M", "spx_12m": "12M"}


def _fed_cycle_distribution(reg_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    storage: dict[str, int] = {}
    analytics: dict[str, int] = {}
    for reg in reg_map.values():
        stored = str(reg.get("fed_cycle_v2") or "UNKNOWN")
        storage[stored] = storage.get(stored, 0) + 1
        bucket = fed_cycle_v2_analytics(stored)
        analytics[bucket] = analytics.get(bucket, 0) + 1
    return {
        "n_fridays": sum(storage.values()),
        "storage": dict(sorted(storage.items())),
        "analytics": dict(sorted(analytics.items())),
        "pivoting_storage_n": storage.get("PIVOTING", 0),
        "pivoting_in_analytics_buckets": "PIVOTING" not in analytics,
    }


def _liquidity_distribution(reg_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    storage: dict[str, int] = {}
    analytics: dict[str, int] = {}
    for reg in reg_map.values():
        liq = str(reg.get("liquidity_v2") or "UNKNOWN")
        storage[liq] = storage.get(liq, 0) + 1
        bucket = collapse_liquidity_v2_analytics(liq)
        analytics[bucket] = analytics.get(bucket, 0) + 1
    return {
        "n_fridays": sum(storage.values()),
        "storage_states": len(storage),
        "analytics_states": len(analytics),
        "storage": dict(sorted(storage.items())),
        "analytics": dict(sorted(analytics.items())),
    }


def _fm_slice_rows(band: str, regime_map: dict, spx) -> list[dict[str, Any]]:
    events = extract_fm_band_events(band, spx=spx, regime_map=regime_map)
    bullish = band != "extreme_long"
    rows: list[dict[str, Any]] = []
    for h in HORIZONS:
        sliced = slice_by_regime(events, "fed_cycle_v2", h, bullish=bullish)
        for bucket, stats in sliced.items():
            rows.append(
                {
                    "band": band,
                    "regime_dim": "fed_cycle_v2_analytics",
                    "bucket": bucket,
                    "horizon": HORIZON_LABELS[h],
                    "bullish_success": bullish,
                    "n": stats.get("n"),
                    "hit_rate_pct": round((stats.get("hit_rate") or 0) * 100, 1)
                    if stats.get("hit_rate") is not None
                    else None,
                    "avg_return_pct": round(stats.get("avg") or 0, 2)
                    if stats.get("avg") is not None
                    else None,
                }
            )
    liq_3m = slice_by_regime(events, "liquidity_v2", "spx_3m", bullish=bullish)
    for bucket, stats in liq_3m.items():
        rows.append(
            {
                "band": band,
                "regime_dim": "liquidity_v2_analytics",
                "bucket": bucket,
                "horizon": "3M",
                "bullish_success": bullish,
                "n": stats.get("n"),
                "hit_rate_pct": round((stats.get("hit_rate") or 0) * 100, 1)
                if stats.get("hit_rate") is not None
                else None,
                "avg_return_pct": round(stats.get("avg") or 0, 2)
                if stats.get("avg") is not None
                else None,
            }
        )
    return rows


def _combo_fires_by_regime() -> list[dict[str, Any]]:
    """Named combos A–G × fed_cycle_v2 analytics @ 3M."""
    import json as _json

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT cf.runic_combo, cf.date, cf.macro_regime, fr.spx_3m
            FROM combo_fires cf
            JOIN forward_returns fr ON cf.combo_id = fr.combo_id
            WHERE cf.runic_combo IS NOT NULL AND fr.spx_3m IS NOT NULL
            ORDER BY cf.runic_combo, cf.date
            """
        ).fetchall()
    reg_map = load_regime_v2_map()
    events: list[dict[str, Any]] = []
    for r in rows:
        reg = _json.loads(r["macro_regime"] or "{}")
        if not reg.get("fed_cycle_v2") and r["date"] in reg_map:
            reg = {**reg, **reg_map[r["date"]]}
        events.append(
            {
                "combo": r["runic_combo"],
                "date": r["date"],
                "returns": {"spx_3m": r["spx_3m"]},
                "regime": reg,
            }
        )

    out: list[dict[str, Any]] = []
    for letter in "ABCDEFG":
        subset = [e for e in events if e["combo"] == letter]
        if not subset:
            continue
        bullish = letter in ("B", "F")
        sliced = slice_by_regime(subset, "fed_cycle_v2", "spx_3m", bullish=bullish)
        for bucket, stats in sliced.items():
            out.append(
                {
                    "combo": letter,
                    "fed_cycle_v2_analytics": bucket,
                    "horizon": "3M",
                    "n": stats.get("n"),
                    "hit_rate_pct": round((stats.get("hit_rate") or 0) * 100, 1)
                    if stats.get("hit_rate") is not None
                    else None,
                    "avg_spx_3m_pct": round(stats.get("avg") or 0, 2)
                    if stats.get("avg") is not None
                    else None,
                }
            )
    return out


def _liquidity_combo_fires_9state_vs_4() -> tuple[list[dict], list[dict]]:
    import json as _json

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT cf.date, cf.runic_combo, cf.macro_regime,
                   fr.spx_1m, fr.spx_3m, fr.spx_6m, fr.spx_9m, fr.spx_12m
            FROM combo_fires cf
            JOIN forward_returns fr ON cf.combo_id = fr.combo_id
            WHERE fr.spx_3m IS NOT NULL
            """
        ).fetchall()
    reg_map = load_regime_v2_map()
    buckets_9: dict[str, list[float]] = {}
    buckets_4: dict[str, list[float]] = {}
    for r in rows:
        reg = _json.loads(r["macro_regime"] or "{}")
        if r["date"] in reg_map:
            reg = {**reg_map[r["date"]], **reg}
        liq = str(reg.get("liquidity_v2") or "UNKNOWN")
        ret = r["spx_3m"]
        if ret is None:
            continue
        buckets_9.setdefault(liq, []).append(float(ret))
        collapsed = regime_value_for_analytics(reg, "liquidity_v2")
        buckets_4.setdefault(collapsed, []).append(float(ret))

    def _table(buckets: dict[str, list[float]]) -> list[dict]:
        rows_out = []
        for k, vals in sorted(buckets.items()):
            s = summarize_returns(vals, bullish=True)
            rows_out.append(
                {
                    "liquidity_bucket": k,
                    "n_fires": s["n"],
                    "up_pct_3m": round((s["hit_rate"] or 0) * 100, 1) if s["n"] else None,
                    "avg_spx_3m": round(s["avg"] or 0, 2) if s["n"] else None,
                }
            )
        return rows_out

    return _table(buckets_9), _table(buckets_4)


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def _md_report(payload: dict[str, Any]) -> str:
    fed = payload["fed_cycle_distribution"]
    liq = payload["liquidity_distribution"]
    lines = [
        "# D6 — Regime Analytics Re-slice (post-collapse)",
        "",
        f"**Date:** {DATE_TAG}",
        f"**Task:** Re-run regime-conditional tables with D6 analytics collapse.",
        "",
        "## Fed cycle — storage vs analytics",
        "",
        f"- Fridays in sample: **{fed['n_fridays']}**",
        f"- PIVOTING in storage: **{fed['pivoting_storage_n']}**",
        f"- PIVOTING absent from analytics buckets: **{fed['pivoting_in_analytics_buckets']}** (merged into EASING)",
        "",
        "### Storage counts",
        "",
        "| State | n |",
        "|-------|---|",
    ]
    for k, v in fed["storage"].items():
        lines.append(f"| {k} | {v} |")
    lines += ["", "### Analytics counts (PIVOTING → EASING)", "", "| State | n |", "|-------|---|"]
    for k, v in fed["analytics"].items():
        lines.append(f"| {k} | {v} |")
    lines += [
        "",
        "## Liquidity — 9-state storage vs 4-state analytics",
        "",
        f"- Storage states: **{liq['storage_states']}**",
        f"- Analytics states: **{liq['analytics_states']}**",
        "",
        "## FM band slices (analytics labels)",
        "",
        "See `D6_fm_regime_slices_analytics_{}.csv`.".format(DATE_TAG),
        "",
        "## Named combos by fed_cycle_v2 analytics @ 3M",
        "",
        "See `D6_combo_fed_cycle_analytics_{}.csv`.".format(DATE_TAG),
        "",
        "## Liquidity combo fires — 9-state vs 4-state @ 3M",
        "",
        "See `D6_liquidity_9state_combo_fires_{}.csv` and `D6_liquidity_4state_analytics_combo_fires_{}.csv`.".format(
            DATE_TAG, DATE_TAG
        ),
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    reg_map = load_regime_v2_map()
    if not reg_map:
        print("WARN: macro_regime_log_v2 empty — FM/combo slices may be thin")
    spx = fetch_yahoo_close("^GSPC", "1990-01-01")

    fed_dist = _fed_cycle_distribution(reg_map)
    liq_dist = _liquidity_distribution(reg_map)

    fm_rows: list[dict] = []
    for band in ("extreme_short", "extreme_long", "moderate"):
        fm_rows.extend(_fm_slice_rows(band, reg_map, spx))

    combo_rows = _combo_fires_by_regime()
    liq_9, liq_4 = _liquidity_combo_fires_9state_vs_4()

    prefix = OUT_DIR / f"D6_regime_analytics_{DATE_TAG}"
    _write_csv(
        OUT_DIR / f"D6_fm_regime_slices_analytics_{DATE_TAG}.csv",
        fm_rows,
        ["band", "regime_dim", "bucket", "horizon", "bullish_success", "n", "hit_rate_pct", "avg_return_pct"],
    )
    _write_csv(
        OUT_DIR / f"D6_combo_fed_cycle_analytics_{DATE_TAG}.csv",
        combo_rows,
        ["combo", "fed_cycle_v2_analytics", "horizon", "n", "hit_rate_pct", "avg_spx_3m_pct"],
    )
    _write_csv(
        OUT_DIR / f"D6_liquidity_9state_combo_fires_{DATE_TAG}.csv",
        liq_9,
        ["liquidity_bucket", "n_fires", "up_pct_3m", "avg_spx_3m"],
    )
    _write_csv(
        OUT_DIR / f"D6_liquidity_4state_analytics_combo_fires_{DATE_TAG}.csv",
        liq_4,
        ["liquidity_bucket", "n_fires", "up_pct_3m", "avg_spx_3m"],
    )

    payload = {
        "task": "D6_regime_analytics_reslice",
        "date": DATE_TAG,
        "fed_cycle_distribution": fed_dist,
        "liquidity_distribution": liq_dist,
        "fm_slice_rows": len(fm_rows),
        "combo_slice_rows": len(combo_rows),
        "artifacts": [
            f"D6_fm_regime_slices_analytics_{DATE_TAG}.csv",
            f"D6_combo_fed_cycle_analytics_{DATE_TAG}.csv",
            f"D6_liquidity_9state_combo_fires_{DATE_TAG}.csv",
            f"D6_liquidity_4state_analytics_combo_fires_{DATE_TAG}.csv",
            f"D6_regime_analytics_{DATE_TAG}.json",
            f"D6_regime_analytics_{DATE_TAG}.md",
        ],
    }
    json_path = OUT_DIR / f"D6_regime_analytics_{DATE_TAG}.json"
    md_path = OUT_DIR / f"D6_regime_analytics_{DATE_TAG}.md"
    json_path.write_text(json.dumps(payload, indent=2))
    md_path.write_text(_md_report(payload))

    print(f"Wrote {json_path}")
    print(f"PIVOTING storage n={fed_dist['pivoting_storage_n']}; analytics has PIVOTING={not fed_dist['pivoting_in_analytics_buckets']}")
    print(f"Liquidity: {liq_dist['storage_states']} storage → {liq_dist['analytics_states']} analytics states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
