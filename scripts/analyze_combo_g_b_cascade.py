#!/usr/bin/env python3
"""MRU-01 / MRU-02: G→B cascade timing and Combo B HY threshold audit.

Scans historical Fridays (2007+, Combo G testable) using current detector rules
and daily_readings from production runic.db. Writes JSON + markdown to
testing/macro_report_updates/.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.config import load_config
from src.macro_intelligence.data.fred_pull import fetch_fred_series
from src.macro_intelligence.data.pull_all import get_readings_as_of
from src.macro_intelligence.data.yahoo_pull import fetch_yahoo_close
from src.macro_intelligence.db.connection import get_connection, init_db
from src.macro_intelligence.engine.combo_detector import (
    _hy_oas_bps,
    detect_named_combos,
    evaluate_combo_b_at_date,
)
from src.macro_intelligence.engine.percentiles import compute_unconditional_pctile, percentile_rank

OUT_DIR = ROOT / "testing" / "macro_report_updates"

# Reference episodes from Divyanshu spec / cheatsheet (for cross-check)
REFERENCE_EPISODES = [
    {"label": "Pre-Aug 2015", "g_approx": "2015-07-01", "b_approx": "2015-08-24", "note": "~3 weeks G→B"},
    {"label": "Pre-Dec 2018", "g_approx": "2018-11-01", "b_approx": "2018-12-24", "note": "~4 weeks G→B"},
    {"label": "Pre-COVID", "g_approx": "2020-02-01", "b_approx": "2020-03-20", "note": "~3 weeks G→B"},
    {"label": "Oct 2022 bottom", "g_approx": None, "b_approx": "2022-10-13", "note": "Canonical B validation date"},
    {"label": "Apr 2025", "g_approx": "2025-04-01", "b_approx": None, "note": "G fired; B never completed"},
]


def _fridays(start: str, end: str) -> list[str]:
    cur = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")
    out: list[str] = []
    while cur <= end_dt:
        if cur.weekday() == 4:
            out.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)
    return out


def _episode_starts(dates: list[str], gap_weeks: int = 8) -> list[str]:
    """First date of each cluster separated by > gap_weeks."""
    if not dates:
        return []
    sorted_dates = sorted(set(dates))
    episodes: list[str] = [sorted_dates[0]]
    for d in sorted_dates[1:]:
        prev = pd.Timestamp(episodes[-1])
        cur = pd.Timestamp(d)
        if (cur - prev).days > gap_weeks * 7:
            episodes.append(d)
    return episodes


def _hy_series_from_db() -> pd.Series:
    """Full HY history from daily_readings (includes BAA10Y proxy back to 1997)."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT date, raw_value FROM daily_readings WHERE var_id='HY' ORDER BY date"
        ).fetchall()
    if not rows:
        return pd.Series(dtype=float)
    idx = pd.to_datetime([r["date"] for r in rows])
    vals = [float(r["raw_value"]) for r in rows]
    return pd.Series(vals, index=idx).sort_index()


def _hy_raw_at(as_of: str, hy_series: pd.Series) -> float | None:
    ts = pd.Timestamp(as_of)
    slice_ = hy_series.loc[:ts]
    if not slice_.empty:
        return float(slice_.iloc[-1])
    with get_connection() as conn:
        row = conn.execute(
            "SELECT raw_value FROM daily_readings WHERE var_id='HY' AND date<=? ORDER BY date DESC LIMIT 1",
            (as_of,),
        ).fetchone()
    return float(row["raw_value"]) if row and row["raw_value"] is not None else None


def _hy_metrics_at(as_of: str, hy_series: pd.Series, hy_cfg: dict) -> dict:
    ts = pd.Timestamp(as_of)
    raw = _hy_raw_at(as_of, hy_series)
    if raw is None:
        return {"hy_bps": None, "hy_pctile": None}
    bps = _hy_oas_bps(raw)
    pct = compute_unconditional_pctile(hy_series, hy_cfg, ts)
    return {
        "hy_raw_pct": round(raw, 4),
        "hy_bps": round(bps, 1),
        "hy_pctile": round(pct, 1) if pct is not None else None,
        "abs_ok": bps >= 400,
        "pctile_ok": pct is not None and pct >= 80,
        "dual_ok": bps >= 400 and pct is not None and pct >= 80,
    }


def _vix_metrics_at(as_of: str, vix_series: pd.Series, vix_cfg: dict) -> dict:
    ts = pd.Timestamp(as_of)
    slice_ = vix_series.loc[:ts]
    if slice_.empty:
        return {"vix": None, "vix_pctile": None}
    raw = float(slice_.iloc[-1])
    pct = compute_unconditional_pctile(vix_series, vix_cfg, ts)
    return {
        "vix": round(raw, 2),
        "vix_pctile": round(pct, 1) if pct is not None else None,
        "vix_ok": raw >= 25 and pct is not None and pct >= 80,
    }


def _cftc_pctile_at(as_of: str, cftc_series: pd.Series, cftc_cfg: dict) -> float | None:
    ts = pd.Timestamp(as_of)
    hist = cftc_series.loc[:ts].dropna()
    if hist.empty:
        return None
    val = float(hist.iloc[-1])
    return percentile_rank(val, hist)


def scan_fires(start: str, end: str, limit: int = 0) -> tuple[list[str], list[str], list[str]]:
    """Return (b_active_dates, g_active_dates, b_watch_only_dates)."""
    b_active: list[str] = []
    g_active: list[str] = []
    b_watch: list[str] = []
    fridays = _fridays(start, end)
    if limit:
        fridays = fridays[:limit]
    for i, ds in enumerate(fridays, 1):
        readings = get_readings_as_of(ds)
        if not readings:
            continue
        fires = detect_named_combos(ds, readings=readings)
        for f in fires:
            if f.runic_combo == "B":
                if f.status == "ACTIVE":
                    b_active.append(ds)
                elif f.status == "WATCH":
                    b_watch.append(ds)
            elif f.runic_combo == "G" and f.status == "ACTIVE":
                g_active.append(ds)
        if i % 100 == 0:
            print(f"  scanned {i}/{len(fridays)} Fridays ({ds})", flush=True)
    return b_active, g_active, b_watch


def analyze_g_b_cascade(b_episodes: list[str], g_dates: list[str], window_weeks: int = 6) -> list[dict]:
    g_sorted = sorted(set(g_dates))
    rows: list[dict] = []
    for b_date in b_episodes:
        b_ts = pd.Timestamp(b_date)
        prior_g = [g for g in g_sorted if pd.Timestamp(g) < b_ts]
        nearest_g = prior_g[-1] if prior_g else None
        weeks_gap = None
        if nearest_g:
            weeks_gap = round((b_ts - pd.Timestamp(nearest_g)).days / 7, 1)
        within = weeks_gap is not None and weeks_gap <= window_weeks
        rows.append(
            {
                "b_episode_start": b_date,
                "nearest_prior_g": nearest_g,
                "weeks_g_to_b": weeks_gap,
                "g_within_6w": within,
            }
        )
    return rows


def audit_db_combo_fires() -> dict:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT runic_combo, status, COUNT(*) n, MIN(date), MAX(date)
            FROM combo_fires WHERE runic_combo IN ('B','G')
            GROUP BY runic_combo, status
            """
        ).fetchall()
    return [dict(r) for r in rows]


def run_analysis(start: str, end: str, limit: int = 0) -> dict:
    init_db()
    cfg = load_config()
    hy_cfg = next(v for v in cfg["variables"] if v["id"] == "HY")
    vix_cfg = next(v for v in cfg["variables"] if v["id"] == "VIX")
    cftc_cfg = next(v for v in cfg["variables"] if v["id"] == "CFTC")

    print(f"Scanning Fridays {start} → {end} ...", flush=True)
    b_active, g_active, b_watch = scan_fires(start, end, limit=limit)
    b_episodes = _episode_starts(b_active)
    g_episodes = _episode_starts(g_active)

    hy_series = _hy_series_from_db()
    if hy_series.empty:
        hy_series = fetch_fred_series("BAMLH0A0HYM2", "1996-01-01")
    vix_series = fetch_yahoo_close("^VIX", "1990-01-01")
    from src.macro_intelligence.data.cftc_pull import fetch_cftc_fast_money_net

    cftc_series = fetch_cftc_fast_money_net(2006)

    cascade = analyze_g_b_cascade(b_episodes, g_active)
    within_count = sum(1 for r in cascade if r["g_within_6w"])
    hy_rows: list[dict] = []
    for b_date in b_episodes:
        hy_m = _hy_metrics_at(b_date, hy_series, hy_cfg)
        vix_m = _vix_metrics_at(b_date, vix_series, vix_cfg)
        cftc_pct = _cftc_pctile_at(b_date, cftc_series, cftc_cfg)
        cftc_ok = cftc_pct is not None and cftc_pct <= 15
        hy_rows.append(
            {
                "b_episode_start": b_date,
                **hy_m,
                **{f"vix_{k}": v for k, v in vix_m.items()},
                "cftc_pctile": round(cftc_pct, 1) if cftc_pct is not None else None,
                "cftc_ok": cftc_ok,
                "all_three_ok": hy_m.get("dual_ok") and vix_m.get("vix_ok") and cftc_ok,
            }
        )

    ref_hy: list[dict] = []
    for ep in REFERENCE_EPISODES:
        b_d = ep.get("b_approx")
        if not b_d:
            continue
        # nearest Friday on or before
        ts = pd.Timestamp(b_d)
        fr = _fridays("1990-01-01", b_d)
        use = fr[-1] if fr else b_d
        hy_m = _hy_metrics_at(use, hy_series, hy_cfg)
        ref_hy.append({"label": ep["label"], "date": use, **hy_m})

    edge_375_400 = [r for r in hy_rows if r.get("hy_bps") and 375 <= r["hy_bps"] < 400]

    return {
        "generated_at": datetime.now().isoformat(),
        "scan_range": {"start": start, "end": end},
        "db_combo_fires_summary": audit_db_combo_fires(),
        "detector_rescan": {
            "b_active_fridays": len(b_active),
            "b_episodes": b_episodes,
            "g_active_fridays": len(g_active),
            "g_episodes": g_episodes,
            "b_watch_fridays": len(b_watch),
        },
        "mru01_g_b_cascade": {
            "window_weeks": 6,
            "episodes": cascade,
            "summary": {
                "b_episodes_post_2007": len(b_episodes),
                "with_prior_g_within_6w": within_count,
                "without_g_warning": len(b_episodes) - within_count,
                "pct_with_g": round(within_count / len(b_episodes) * 100, 1) if b_episodes else None,
            },
        },
        "mru02_hy_audit": {
            "episodes": hy_rows,
            "edge_375_400bps": edge_375_400,
            "reference_dates": ref_hy,
            "recommendation": (
                "lower_threshold_to_375"
                if edge_375_400
                else "keep_400bps"
            ),
            "dual_failures": [r for r in hy_rows if not r.get("dual_ok")],
        },
        "reference_episodes": REFERENCE_EPISODES,
    }


def write_markdown(report: dict, path: Path) -> None:
    m01 = report["mru01_g_b_cascade"]
    m02 = report["mru02_hy_audit"]
    lines = [
        "# G→B Cascade & Combo B HY Audit Results",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Scan:** {report['scan_range']['start']} → {report['scan_range']['end']}",
        "",
        "## DB state (persisted combo_fires)",
        "",
        "| Combo | Status | Count | Min | Max |",
        "|-------|--------|-------|-----|-----|",
    ]
    for row in report["db_combo_fires_summary"]:
        lines.append(
            f"| {row['runic_combo']} | {row['status']} | {row['n']} | {row['MIN(date)']} | {row['MAX(date)']} |"
        )
    lines += [
        "",
        "## MRU-01 — G→B cascade (detector rescan)",
        "",
        f"- B episodes (ACTIVE): **{m01['summary']['b_episodes_post_2007']}**",
        f"- With prior G within 6 weeks: **{m01['summary']['with_prior_g_within_6w']}**",
        f"- B without G warning: **{m01['summary']['without_g_warning']}**",
        "",
        "| B episode start | Nearest prior G | Weeks G→B | Within 6w |",
        "|-----------------|-----------------|-----------|-----------|",
    ]
    for ep in m01["episodes"]:
        lines.append(
            f"| {ep['b_episode_start']} | {ep['nearest_prior_g'] or '—'} | "
            f"{ep['weeks_g_to_b'] if ep['weeks_g_to_b'] is not None else '—'} | "
            f"{'✅' if ep['g_within_6w'] else '❌'} |"
        )
    lines += [
        "",
        "## MRU-02 — HY at B episodes",
        "",
        f"**Recommendation:** {m02['recommendation']}",
        "",
        "| B start | HY bps | HY pctile | Abs≥400 | Pct≥80 | Dual OK | VIX | All 3 OK |",
        "|---------|--------|-----------|---------|--------|---------|-----|----------|",
    ]
    for r in m02["episodes"]:
        lines.append(
            f"| {r['b_episode_start']} | {r.get('hy_bps','—')} | {r.get('hy_pctile','—')} | "
            f"{'✅' if r.get('abs_ok') else '❌'} | {'✅' if r.get('pctile_ok') else '❌'} | "
            f"{'✅' if r.get('dual_ok') else '❌'} | {r.get('vix_vix','—')} | "
            f"{'✅' if r.get('all_three_ok') else '❌'} |"
        )
    if m02["reference_dates"]:
        lines += ["", "### Reference dates", ""]
        for r in m02["reference_dates"]:
            lines.append(f"- **{r['label']}** ({r['date']}): HY {r.get('hy_bps')} bps, pctile {r.get('hy_pctile')}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2007-01-01")
    parser.add_argument("--end", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--limit", type=int, default=0, help="Limit Fridays (0=all)")
    args = parser.parse_args()

    report = run_analysis(args.start, args.end, limit=args.limit)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / "mru01_mru02_results.json"
    md_path = OUT_DIR / "mru01_mru02_results.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown(report, md_path)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print("Summary:", report["mru01_g_b_cascade"]["summary"])
    print("HY recommendation:", report["mru02_hy_audit"]["recommendation"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
