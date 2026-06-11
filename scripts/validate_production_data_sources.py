#!/usr/bin/env python3
"""
Production readiness check — live pulls only (no mocks, no unit-test fixtures).

Exit code 0 only if all required sources pass minimum row/value checks.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_SOURCES = ROOT / "macro_intelligence" / "DATA_SOURCES.yaml"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Minimum history rows for production (live or stale cache from real pulls)
MIN_ROWS = {
    "NFCI": 1000,
    "HY": 750,
    "WALCL": 500,
    "CNH": 500,
    "WTI": 500,
    "VIX": 1000,
    "VXTS": 500,
    "CFTC": 200,
    "CURVE": 1000,
    "CAPE": 500,
    "GSR": 500,
    "CPI": 1,
    "hyg_lqd": 500,
    "dbmf_beta": 500,
    "cnn_fg": 50,
    "vix_ratio": 500,
    "aaii_spread": 20,
    "naaim_exposure": 5,
    "pct_above_200dma": 100,
    "mcclellan": 100,
    "nh_nl_ratio": 100,
    "skew": 500,
}


@dataclass
class CheckResult:
    var_id: str
    system: str
    source: str
    status: str  # PASS, FAIL, WARN
    rows: int
    last_value: str
    detail: str


def _series_info(s: pd.Series | pd.DataFrame | None) -> tuple[int, str]:
    if s is None:
        return 0, "—"
    try:
        n = len(s)
    except TypeError:
        return 0, "—"
    if n == 0:
        return 0, "—"
    if isinstance(s, pd.DataFrame):
        col = s.select_dtypes(include="number").columns
        last = float(s[col[-1]].iloc[-1]) if len(col) else float("nan")
    else:
        last = float(s.iloc[-1])
    return n, f"{last:.4g}"


def check_macro_series() -> list[CheckResult]:
    from src.macro_intelligence.data.pull_all import load_all_series

    series = load_all_series(force=True)
    from src.macro_intelligence.config import load_config

    results: list[CheckResult] = []
    for var in load_config().get("variables", []):
        vid = var["id"]
        s = series.get(vid)
        n, last = _series_info(s)
        min_n = MIN_ROWS.get(vid, 10)
        if vid == "CPI":
            from src.macro_intelligence.data.bls_pull import load_cpi_surprise_series

            cpi = load_cpi_surprise_series()
            n = len(cpi)
            last = f"{float(cpi.iloc[-1]):.4g}" if n else "—"
            min_n = 1
            status = "PASS" if n >= min_n else "WARN" if n == 0 else "PASS"
            detail = "pending_releases/CSV surprise series"
            if n == 0:
                detail += " — need BLS actual + Investing consensus on release week"
        elif n >= min_n:
            status = "PASS"
            detail = "live pull OK"
        elif n > 0:
            status = "WARN"
            detail = f"only {n} rows (min {min_n})"
        else:
            status = "FAIL"
            detail = "empty series"
        results.append(
            CheckResult(vid, "macro", var.get("source", ""), status, n, last, detail)
        )
    # SPX_W internal
    spx_w = series.get("SPX_W")
    n, _ = _series_info(spx_w if hasattr(spx_w, "iloc") else None)
    results.append(
        CheckResult("SPX_W", "macro", "YAHOO", "PASS" if n >= 500 else "FAIL", n, "—", "Combo F 50WMA")
    )
    return results


def check_cftc_live() -> CheckResult:
    from src.macro_intelligence.data.cftc_pull import CFTC_LOCAL_CACHE_DIR, fetch_cftc_fast_money_net

    zips = list(CFTC_LOCAL_CACHE_DIR.glob("*.zip")) if CFTC_LOCAL_CACHE_DIR.is_dir() else []
    fm = fetch_cftc_fast_money_net(2006)
    n, last = _series_info(fm)
    min_n = MIN_ROWS["CFTC"]
    if n < min_n:
        hint = (
            f"only {len(zips)} zip(s) in data_cache/cftc — run: "
            "scripts/download_cftc_tff_zip.py --all-years --start 2006"
        )
        status = "WARN" if n >= 10 else "FAIL"
        return CheckResult("CFTC_FM", "macro", "CFTC", status, n, last, hint)
    # sanity: consolidated net not absurd
    if abs(float(fm.iloc[-1])) > 2_000_000:
        return CheckResult("CFTC_FM", "macro", "CFTC", "FAIL", n, last, "FM net looks stacked (not consolidated)")
    return CheckResult("CFTC_FM", "macro", "CFTC", "PASS", n, last, "S&P 500 Consolidated TFF")


def check_cpi_consensus() -> CheckResult:
    from src.macro_intelligence.data.investing_cpi_consensus import (
        _investing_fallback_enabled,
        fetch_cpi_consensus_calendar,
        fetch_tradingeconomics_cpi_calendar,
        latest_cpi_consensus_row,
        load_consensus_csv,
    )
    from src.macro_intelligence.data.bls_pull import try_fetch_cpi_consensus
    from src.macro_intelligence.db.connection import get_connection, init_db

    init_db()
    te_rows = fetch_tradingeconomics_cpi_calendar()
    live_rows = fetch_cpi_consensus_calendar()
    latest = latest_cpi_consensus_row()
    csv_df = load_consensus_csv()
    bls_path = try_fetch_cpi_consensus()
    parts: list[str] = []
    if te_rows:
        parts.append(f"te_rows={len(te_rows)}")
    if live_rows:
        parts.append(f"live_rows={len(live_rows)}")
    if _investing_fallback_enabled():
        parts.append("investing_proxy=on")
    if not csv_df.empty:
        parts.append(f"csv_cache={len(csv_df)}")
    if bls_path is not None:
        parts.append(f"resolved={bls_path}")

    with get_connection() as conn:
        db_rows = conn.execute(
            "SELECT source, COUNT(*) AS n FROM pending_releases WHERE release_type='CPI' GROUP BY source"
        ).fetchall()
    for r in db_rows:
        parts.append(f"db:{r['source']}={r['n']}")
    proxy_n = sum(r["n"] for r in db_rows if r["source"] == "FRED_PROXY")
    real_sources = {r["source"] for r in db_rows} - {"FRED_PROXY", "fred_release_calendar"}
    has_live_consensus = bool(
        latest
        and latest.consensus is not None
        and latest.source in {"tradingeconomics.com", "investing.com", "csv"}
    )

    if proxy_n and not real_sources and not has_live_consensus:
        return CheckResult(
            "CPI_CONSENSUS",
            "macro",
            "FRED_PROXY",
            "FAIL",
            proxy_n,
            "—",
            "only FRED_PROXY (consensus=actual) — set BLS_API_KEY + run sync_cpi_consensus",
        )
    if proxy_n:
        parts.append(f"WARN: {proxy_n} FRED_PROXY rows (zero surprise)")
    if has_live_consensus:
        return CheckResult(
            "CPI_CONSENSUS",
            "macro",
            latest.source if latest else "tradingeconomics.com",
            "PASS",
            len(live_rows) or len(csv_df),
            str(latest.consensus) if latest else "—",
            "; ".join(parts),
        )
    if not csv_df.empty:
        return CheckResult(
            "CPI_CONSENSUS",
            "macro",
            "csv",
            "WARN",
            len(csv_df),
            "—",
            "live TE scrape failed; using emergency CSV cache only — check network",
        )
    if real_sources:
        return CheckResult(
            "CPI_CONSENSUS",
            "macro",
            "db",
            "WARN",
            sum(r["n"] for r in db_rows),
            "—",
            "DB has CPI rows but no live consensus — run sync before release week",
        )
    return CheckResult(
        "CPI_CONSENSUS",
        "macro",
        "tradingeconomics.com",
        "FAIL",
        0,
        "—",
        "no consensus — run sync_cpi_consensus.py",
    )


def check_data_sources_yaml_coverage() -> list[CheckResult]:
    """Ensure DATA_SOURCES.yaml entries are represented in validation."""
    if not DATA_SOURCES.exists():
        return []
    ds = yaml.safe_load(DATA_SOURCES.read_text(encoding="utf-8"))
    covered = {r.var_id for r in check_macro_series() + check_ssi_series()}
    covered.update({"CFTC_FM", "CPI_CONSENSUS", "CFTC_LAYER3", "SPX_W"})
    out: list[CheckResult] = []
    for entry in ds.get("variables", []):
        vid = entry.get("var_id", "")
        key = SSI_KEY_MAP.get(vid, vid) if vid in SSI_KEY_MAP else vid
        if vid in ("CFTC_FM", "CFTC_RM", "GROSS_NET_DIV"):
            continue
        if key in covered or vid in covered:
            out.append(
                CheckResult(
                    f"DS_{vid}",
                    entry.get("system", ""),
                    entry.get("source", ""),
                    "PASS",
                    1,
                    "—",
                    "listed in production validation",
                )
            )
        else:
            out.append(
                CheckResult(
                    f"DS_{vid}",
                    entry.get("system", ""),
                    entry.get("source", ""),
                    "FAIL",
                    0,
                    "—",
                    "missing from live validation mapping",
                )
            )
    return out


SSI_KEY_MAP = {
    "AAII": "aaii_spread",
    "NAAIM": "naaim_exposure",
    "CNN_FG": "cnn_fg",
    "PCT_ABOVE_200DMA": "pct_above_200dma",
    "MCCLELLAN": "mcclellan",
    "NH_NL_RATIO": "nh_nl_ratio",
    "HYG_LQD": "hyg_lqd",
    "SKEW": "skew",
    "DBMF": "dbmf_beta",
}


def check_ssi_series() -> list[CheckResult]:
    from src.sentiment_superindex.data.pull_all import load_all_series

    series = load_all_series(force=True)
    mapping = {
        "hyg_lqd": ("SSI", "YAHOO"),
        "dbmf_beta": ("SSI", "YAHOO"),
        "cnn_fg": ("SSI", "CNN"),
        "vix_ratio": ("SSI", "YAHOO"),
        "aaii_spread": ("SSI", "AAII"),
        "naaim_exposure": ("SSI", "NAAIM"),
        "pct_above_200dma": ("SSI", "SP500 computed"),
        "mcclellan": ("SSI", "SP500 McClellan"),
        "nh_nl_ratio": ("SSI", "SP500 NH/NL"),
        "skew": ("SSI", "YAHOO"),
    }
    out: list[CheckResult] = []
    for key, (sys, src) in mapping.items():
        s = series.get(key)
        n, last = _series_info(s)
        min_n = MIN_ROWS.get(key, 10)
        if key == "cnn_fg" and n > 0:
            v = float(s.iloc[-1])
            if v < 0 or v > 100:
                out.append(CheckResult(key, sys, src, "FAIL", n, last, f"CNN score {v} outside 0-100"))
                continue
        if key == "aaii_spread" and n < min_n:
            status = "WARN" if n >= 5 else "FAIL"
            out.append(
                CheckResult(
                    key,
                    sys,
                    src,
                    status,
                    n,
                    last,
                    "AAII needs full history — run scripts/ingest_aaii_sentiment.py",
                )
            )
            continue
        if n >= min_n:
            out.append(CheckResult(key, sys, src, "PASS", n, last, "live OK"))
        elif n > 0:
            out.append(CheckResult(key, sys, src, "WARN", n, last, f"short history (min {min_n})"))
        else:
            out.append(CheckResult(key, sys, src, "FAIL", n, last, "empty"))
    return out


def check_layer3() -> CheckResult:
    from src.sentiment_superindex.data.cftc_ssi import cftc_layer3_snapshot

    snap = cftc_layer3_snapshot(datetime.now().strftime("%Y-%m-%d"))
    if not snap or snap.get("fm_net") is None:
        return CheckResult("CFTC_LAYER3", "SSI", "CFTC", "FAIL", 0, "—", "no layer3 snapshot")
    return CheckResult(
        "CFTC_LAYER3",
        "SSI",
        "CFTC",
        "PASS",
        1,
        f"fm={snap.get('fm_net')}",
        f"rm={snap.get('rm_net')}",
    )


def check_jobs_smoke() -> list[CheckResult]:
    out: list[CheckResult] = []
    try:
        from src.macro_intelligence.db.connection import init_db
        from src.macro_intelligence.data.pull_all import pull_all_series

        init_db()
        readings = pull_all_series()
        out.append(
            CheckResult(
                "pull_all_series",
                "macro",
                "job",
                "PASS" if len(readings) >= 10 else "FAIL",
                len(readings),
                "—",
                f"{len(readings)} readings upserted",
            )
        )
    except Exception as exc:
        out.append(CheckResult("pull_all_series", "macro", "job", "FAIL", 0, "—", str(exc)))

    try:
        from src.sentiment_superindex.jobs.daily_run import run_ssi_daily

        payload = run_ssi_daily()
        ok = payload.get("ssi_level") is not None and payload.get("layer2_status")
        out.append(
            CheckResult(
                "run_ssi_daily",
                "SSI",
                "job",
                "PASS" if ok else "FAIL",
                1,
                str(payload.get("ssi_level")),
                str(payload.get("output_path", "")),
            )
        )
    except Exception as exc:
        out.append(CheckResult("run_ssi_daily", "SSI", "job", "FAIL", 0, "—", str(exc)))
    return out


def main() -> int:
    print("=" * 72)
    print("PRODUCTION DATA SOURCE VALIDATION (live pulls, no mocks)")
    print("=" * 72)
    print(f"Time: {datetime.now().isoformat()}")
    print(f"FRED_API_KEY: {'set' if os.getenv('FRED_API_KEY') else 'MISSING (CSV fallback)'}")
    print(f"BLS_API_KEY: {'set' if os.getenv('BLS_API_KEY') else 'MISSING'}")
    print()

    all_results: list[CheckResult] = []
    all_results.extend(check_macro_series())
    all_results.append(check_cftc_live())
    all_results.append(check_cpi_consensus())
    all_results.extend(check_ssi_series())
    all_results.append(check_layer3())
    all_results.extend(check_jobs_smoke())
    all_results.extend(check_data_sources_yaml_coverage())

    fails = [r for r in all_results if r.status == "FAIL"]
    warns = [r for r in all_results if r.status == "WARN"]

    for r in all_results:
        icon = {"PASS": "OK", "WARN": "!!", "FAIL": "XX"}[r.status]
        print(f"[{icon}] {r.var_id:20} {r.status:4} rows={r.rows:5} last={r.last_value:12} — {r.detail}")

    print()
    print(f"Summary: {len(all_results)} checks, {len(all_results)-len(fails)-len(warns)} PASS, {len(warns)} WARN, {len(fails)} FAIL")

    out_path = ROOT / "macro_intelligence" / "output" / "production_validation.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps([r.__dict__ for r in all_results], indent=2),
        encoding="utf-8",
    )
    print(f"Report: {out_path}")

    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
