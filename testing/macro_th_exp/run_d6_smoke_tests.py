#!/usr/bin/env python3
"""D6 smoke tests — Combo C insufficient episodes, briefing display, API service path, FM analytics collapse."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT_DIR = Path(__file__).resolve().parent
DATE_TAG = datetime.now(UTC).strftime("%Y-%m-%d")


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "pass": ok, "detail": detail}


def run_smoke_tests() -> dict[str, Any]:
    results: list[dict[str, Any]] = []

    # 1. Combo C hit rate stats
    from src.macro_intelligence.engine.combo_metadata import (
        combo_hit_rate_stats,
        format_hit_rate_display,
        min_episodes_for_hit_rate,
    )

    c_stats = combo_hit_rate_stats("C")
    hr_txt, avg_txt = format_hit_rate_display(c_stats)
    min_n = min_episodes_for_hit_rate("C")
    n_primary = c_stats.get("n_obs_primary") or 0
    results.append(
        _check(
            "combo_c_insufficient_episodes_flag",
            bool(c_stats.get("insufficient_episodes")) and c_stats.get("hit_rate_primary") is None,
            f"n_primary={n_primary}, min={min_n}, insufficient={c_stats.get('insufficient_episodes')}",
        )
    )
    results.append(
        _check(
            "combo_c_briefing_display_string",
            hr_txt == "insufficient episodes" and avg_txt == "—",
            f"hit_rate_cell={hr_txt!r}, avg_cell={avg_txt!r}",
        )
    )

    # 2. Briefing all-time stats table includes Combo C string
    from src.macro_intelligence.output.briefing_renderer import _all_time_combo_stats

    db_stats = _all_time_combo_stats()
    c_row = db_stats.get("C", {})
    results.append(
        _check(
            "briefing_all_time_combo_c_row",
            c_row.get("hit_rate_display") == "insufficient episodes",
            f"hit_rate_display={c_row.get('hit_rate_display')!r}",
        )
    )

    # 3. Build combo status rows from minimal payload (INACTIVE C uses db_stats)
    from src.macro_intelligence.output.briefing_renderer import build_combo_status_rows

    payload = {
        "date": DATE_TAG,
        "active_combos": [],
        "watch_combos": [],
        "combo_c_cancel": {},
    }
    rows = build_combo_status_rows(payload)
    c_status = next((r for r in rows if r.get("combo") == "C"), None)
    results.append(
        _check(
            "briefing_combo_status_row_c",
            c_status is not None and c_status.get("hit_rate_3m") == "insufficient episodes",
            f"C row hit_rate_3m={c_status.get('hit_rate_3m') if c_status else None!r}",
        )
    )

    # 4. API macro_service path (no HTTP server required)
    try:
        from api.services import macro_service as msvc

        detail = msvc.get_combo_detail("C")
        hr = detail.get("hit_rate_stats") or {}
        api_ok = (
            hr.get("insufficient_episodes") is True
            and hr.get("hit_rate_primary") is None
            and detail.get("hit_rate_primary") is None
        )
        results.append(
            _check(
                "api_get_combo_detail_c",
                api_ok,
                f"insufficient={hr.get('insufficient_episodes')}, n={hr.get('n_obs_primary')}",
            )
        )
    except Exception as exc:
        results.append(_check("api_get_combo_detail_c", False, f"exception: {exc}"))

    # 5. list_named_combos includes C with insufficient display
    try:
        from api.services import macro_service as msvc

        all_combos = msvc.get_all_combos()
        c_entry = next((c for c in all_combos.get("combos", []) if c.get("combo") == "C"), None)
        results.append(
            _check(
                "api_list_named_combos_c",
                c_entry is not None
                and (c_entry.get("hit_rate_primary") is None or c_entry.get("insufficient_episodes")),
                f"hit_rate_primary={c_entry.get('hit_rate_primary') if c_entry else None}",
            )
        )
    except Exception as exc:
        results.append(_check("api_list_named_combos_c", False, f"exception: {exc}"))

    # 6. FM slice: no PIVOTING bucket after analytics collapse
    from src.macro_intelligence.analysis.regime_experiments.fm_events import (
        extract_fm_band_events,
        load_regime_v2_map,
    )
    from src.macro_intelligence.analysis.regime_experiments.metrics import slice_by_regime
    from src.macro_intelligence.data.yahoo_pull import fetch_yahoo_close

    reg_map = load_regime_v2_map()
    spx = fetch_yahoo_close("^GSPC", "1990-01-01")
    events = extract_fm_band_events("extreme_short", spx=spx, regime_map=reg_map)
    sliced = slice_by_regime(events, "fed_cycle_v2", "spx_3m", bullish=True)
    has_pivoting = "PIVOTING" in sliced
    easing_n = (sliced.get("EASING") or {}).get("n") or 0
    results.append(
        _check(
            "fm_fed_slice_no_pivoting_bucket",
            not has_pivoting,
            f"buckets={list(sliced.keys())}, EASING n={easing_n}",
        )
    )

    # 7. Liquidity analytics collapse produces ≤4 buckets on FM slice
    liq_sliced = slice_by_regime(events, "liquidity_v2", "spx_3m", bullish=True)
    results.append(
        _check(
            "fm_liquidity_analytics_max_4_buckets",
            len(liq_sliced) <= 4,
            f"buckets={list(liq_sliced.keys())} (n={len(liq_sliced)})",
        )
    )

    passed = sum(1 for r in results if r["pass"])
    return {
        "task": "D6_smoke_tests",
        "date": DATE_TAG,
        "passed": passed,
        "total": len(results),
        "all_pass": passed == len(results),
        "results": results,
    }


def _md_report(report: dict[str, Any]) -> str:
    lines = [
        "# D6 — Smoke Tests",
        "",
        f"**Date:** {DATE_TAG}",
        f"**Result:** {report['passed']}/{report['total']} passed — "
        + ("**ALL PASS**" if report["all_pass"] else "**FAILURES**"),
        "",
        "| Test | Pass | Detail |",
        "|------|------|--------|",
    ]
    for r in report["results"]:
        mark = "✅" if r["pass"] else "❌"
        lines.append(f"| {r['name']} | {mark} | {r['detail']} |")
    lines += [
        "",
        "## Scope",
        "",
        "- Combo C `insufficient episodes` (DB n&lt;5 at 6M primary horizon)",
        "- Briefing renderer all-time + status rows",
        "- API `macro_service.get_combo_detail('C')` and `get_all_combos()`",
        "- FM `fed_cycle_v2` slice has no PIVOTING bucket; liquidity ≤4 analytics buckets",
        "",
        "Run: `.venv/bin/python testing/macro_th_exp/run_d6_smoke_tests.py`",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    report = run_smoke_tests()
    json_path = OUT_DIR / f"D6_smoke_tests_{DATE_TAG}.json"
    md_path = OUT_DIR / f"D6_smoke_tests_{DATE_TAG}.md"
    json_path.write_text(json.dumps(report, indent=2))
    md_path.write_text(_md_report(report))
    print(json.dumps(report, indent=2))
    print(f"\nWrote {json_path} and {md_path}")
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
