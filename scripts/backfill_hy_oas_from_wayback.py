#!/usr/bin/env python3
"""Backfill real HY OAS history (1996-2025) from a Wayback Machine FRED snapshot,
replacing the BAA10Y-based proxy (``recalibrate_hy_oas_proxy.py`` Model v2) entirely.

Background
----------
``BAMLH0A0HYM2`` (ICE BofA US High Yield OAS) is licensed data. FRED's free API/CSV was
re-restricted to a rolling 3-year window starting April 2026 (see
``scripts/recalibrate_hy_oas_proxy.py`` docstring). Because of that cutoff, ``daily_readings``
carries a BAA10Y-derived proxy (``signal_tier='PROXY'``) for 1997-01-02 -> 2023-07-13.

Source found (2026-08-02)
--------------------------
``http://web.archive.org/web/20251104204105/https://fred.stlouisfed.org/graph/fredgraph.csv?id=BAMLH0A0HYM2``
-- an Internet Archive snapshot captured 2025-11-04, days before the April-2026 licensing cap
took effect (confirmed: a later 2026-07-16 snapshot of the same URL already shows the capped
3-year window, proving this Nov-2025 capture is the last full-history free snapshot available).
It contains the REAL ICE BofA HY OAS series, 1996-12-31 -> 2025-11-03. Combined with the real
data already collected live since 2023-06-09 (``src/macro_intelligence/data/pull_all.py``'s
``fetch_fred_series("BAMLH0A0HYM2", ...)``), the two overlap by over a year, giving continuous
REAL coverage 1996-12-31 -> today. This is not a proxy improvement -- it closes the gap.

Validated against known public peaks (cross-checked live 2026-08-02):
    2008-12-15  21.82%  (matches the ~21-22% widely-cited GFC peak)
    2020-03-23  10.87%  (matches the commonly cited "1,087bps" COVID peak almost exactly)
    2022-06-13   4.87%  (vs the Model v2 proxy's 4.37% estimate for the same date -- confirms
                         the proxy was still understating even after the 2026-07-29 recalibration)

What this script does
----------------------
1. Fetches the archived CSV, parses ``observation_date,BAMLH0A0HYM2`` into a date-indexed series
   (blank/holiday rows dropped -- 92 of 7622 rows in the snapshot are blank).
2. Classifies every HY date in ``daily_readings`` into:
   - ``proxy_covered``: currently ``signal_tier='PROXY'`` AND the wayback CSV has a value for that
     date -> becomes real (raw_value replaced, tier/direction recomputed).
   - ``proxy_orphan``: currently ``signal_tier='PROXY'`` but the wayback CSV has NO value for that
     date (7 dates found 2026-08-02, all bond-market-only holidays e.g. Good Friday that the
     BAA10Y/Fed calendar used for the original proxy backfill did not observe) -> **left
     unchanged, still PROXY**. This is a disclosed, narrow residual gap, not silently dropped.
   - ``new_insert``: wayback CSV has a value for a date with NO existing ``daily_readings`` row at
     all (~301 dates found 2026-08-02 -- mostly US bank holidays where BAA10Y/Fed H.15 has no
     print but ICE's bond-market OAS calendar does, plus a handful of ICE month-end weekend
     marks) -> inserted fresh as real.
   - ``already_real``: dates already ``signal_tier != 'PROXY'`` in the DB (2023-06-09 onward,
     live-collected) -> ``raw_value`` untouched; only percentile columns recomputed below.
3. Builds one unified HY value series (wayback value where it exists and applies per the
   classification above; existing DB ``raw_value`` otherwise) and recomputes
   ``pctile_rank_3yr`` / ``unconditional_pctile`` for **every** HY date via the existing
   ``compute_unconditional_pctile()`` (rolling-3y window depends on this backfilled history for
   every date, not just the ones being converted).
4. For ``proxy_covered`` + ``new_insert`` dates: classifies the real tier via the existing
   ``evaluate_variable_tier("HY", ...)`` -- this returns ``NORMAL``/``RARE``/``EXTREME``, not
   ``PROXY``, since the data is now real.
5. For ``proxy_orphan`` + ``already_real`` dates: same precedent as
   ``recalibrate_hy_oas_proxy.py`` -- percentile columns only, ``signal_tier``/``direction``/
   ``raw_value`` untouched.

Caveats (do not oversell this fix)
-----------------------------------
- 7 ``proxy_orphan`` dates (~0.1% of the 6627 PROXY rows) stay on the old BAA10Y proxy estimate --
  no free real source covers those specific bond-market holidays. Listed in the generated report.
- Retroactive reclassification: ~6620 rows flip from ``PROXY`` to real ``NORMAL``/``RARE``/
  ``EXTREME``. This WILL change historical combo fire counts for any HY-driven combo (A, G --
  see ``docs/ssi_validation/hy_proxy_consumer_audit_2026-07-29.md``) and historical SSI-adjacent
  ceiling-chain numbers for 1997-2023. This is the intended fix, not a bug -- documented in
  ``docs/ssi_validation/hy_oas_wayback_backfill_2026-08-02.md``.
- ``scripts/recalibrate_hy_oas_proxy.py`` (Model v2) is superseded by this backfill but kept in
  the repo for provenance/history and as a fallback if the wayback source is ever unusable.

Usage
-----
    .venv/bin/python scripts/backfill_hy_oas_from_wayback.py                 # dry run, report only
    .venv/bin/python scripts/backfill_hy_oas_from_wayback.py --apply         # write to runic.db
    .venv/bin/python scripts/backfill_hy_oas_from_wayback.py --apply --report docs/ssi_validation/hy_oas_wayback_backfill_2026-08-02.md
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.config import db_path, load_config  # noqa: E402
from src.macro_intelligence.db.connection import get_connection  # noqa: E402
from src.macro_intelligence.engine.percentiles import compute_unconditional_pctile, evaluate_variable_tier  # noqa: E402

WAYBACK_URL = (
    "http://web.archive.org/web/20251104204105/"
    "https://fred.stlouisfed.org/graph/fredgraph.csv?id=BAMLH0A0HYM2"
)
SNAPSHOT_DATE = "2025-11-04"

# Independently, publicly documented HY OAS peaks -- used here only as a live cross-check that the
# fetched wayback series matches widely-cited history, not as calibration inputs (unlike the old
# proxy script, this data is real, not fit).
ANCHOR_CHECKS: list[tuple[str, float, str]] = [
    ("2008-12-15", 21.82, "GFC peak; matches the ~21-22% widely-cited consensus"),
    ("2020-03-23", 10.87, "COVID peak; matches the commonly cited 1,087bps almost exactly"),
    ("2022-06-13", 4.87, "2022 rate-shock stress; Model v2 proxy estimated 4.37% for this date"),
]


def fetch_wayback_series() -> pd.Series:
    resp = requests.get(WAYBACK_URL, timeout=60, headers={"User-Agent": "Mozilla/5.0 (MindWealth research backfill)"})
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text))
    df.columns = [c.strip() for c in df.columns]
    date_col, val_col = df.columns[0], df.columns[1]
    df[date_col] = pd.to_datetime(df[date_col])
    df[val_col] = pd.to_numeric(df[val_col], errors="coerce")
    return df.set_index(date_col)[val_col].dropna().sort_index()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="Write backfilled values to runic.db (default: dry run)")
    parser.add_argument(
        "--report",
        default=str(ROOT / "docs" / "ssi_validation" / "hy_oas_wayback_backfill_2026-08-02.md"),
        help="Path to write the validation report markdown",
    )
    args = parser.parse_args()

    print(f"Fetching wayback FRED CSV from snapshot {SNAPSHOT_DATE} ...")
    wb_series = fetch_wayback_series()
    print(f"Wayback series: {len(wb_series)} real rows, {wb_series.index.min().date()} -> {wb_series.index.max().date()}")

    for date_str, known_val, note in ANCHOR_CHECKS:
        ts = pd.Timestamp(date_str)
        wb_val = wb_series.get(ts)
        status = "OK" if wb_val is not None and abs(wb_val - known_val) < 0.01 else "MISMATCH"
        print(f"  Anchor check {date_str}: wayback={wb_val} known={known_val} [{status}] -- {note}")
        if status == "MISMATCH":
            print("  WARNING: anchor mismatch -- verify the fetched CSV before applying.")

    with get_connection(db_path()) as conn:
        db_rows = pd.read_sql(
            "SELECT date, raw_value, signal_tier FROM daily_readings WHERE var_id='HY' ORDER BY date",
            conn, parse_dates=["date"],
        )
    db_rows = db_rows.set_index("date")
    proxy_dates = set(db_rows.index[db_rows["signal_tier"] == "PROXY"])
    existing_dates = set(db_rows.index)
    wb_dates = set(wb_series.index)

    proxy_covered = sorted(proxy_dates & wb_dates)
    proxy_orphan = sorted(proxy_dates - wb_dates)
    new_insert = sorted(wb_dates - existing_dates)
    already_real = sorted(existing_dates - proxy_dates)

    print(f"\nProxy dates covered by wayback (-> real): {len(proxy_covered)}")
    print(f"Proxy dates NOT covered by wayback (stay PROXY, disclosed gap): {len(proxy_orphan)}")
    for d in proxy_orphan:
        print(f"  orphan: {d.date()} (old proxy raw_value={db_rows.loc[d, 'raw_value']:.4f})")
    print(f"New dates inserted (wayback has a value, no existing row): {len(new_insert)}")
    print(f"Already-real dates (untouched raw_value, percentiles recomputed): {len(already_real)}")

    # Unified value series for percentile computation: wayback value wherever it exists and the
    # date is being converted/inserted; existing DB raw_value for already-real + orphan dates.
    unified = db_rows["raw_value"].copy()
    for d in proxy_covered:
        unified.loc[d] = wb_series.loc[d]
    for d in new_insert:
        unified.loc[d] = wb_series.loc[d]
    unified = unified.sort_index()

    cfg = load_config()
    hy_cfg = next(v for v in cfg["variables"] if v["id"] == "HY")

    all_dates = sorted(unified.index)
    print(f"\nRecomputing rolling-3y percentiles for {len(all_dates)} HY dates ...")
    new_pctiles: dict[pd.Timestamp, float | None] = {
        ts: compute_unconditional_pctile(unified, hy_cfg, ts) for ts in all_dates
    }

    new_tier_rows: dict[pd.Timestamp, tuple[str, str | None]] = {}
    for d in proxy_covered + new_insert:
        raw = float(unified.loc[d])
        pct = new_pctiles.get(d)
        tier, direction = evaluate_variable_tier("HY", hy_cfg, raw, pct)
        tier_val = tier.value if hasattr(tier, "value") else tier
        new_tier_rows[d] = (tier_val, direction)

    tier_counts: dict[str, int] = {}
    for _, (t, _d) in new_tier_rows.items():
        tier_counts[t] = tier_counts.get(t, 0) + 1
    print(f"New tier distribution for backfilled/inserted dates: {tier_counts}")

    meta = {
        "source": "wayback_fred_archive",
        "archive_url": WAYBACK_URL,
        "snapshot_date": SNAPSHOT_DATE,
    }
    meta_json_str = json.dumps(meta)

    if not args.apply:
        print("\nDRY RUN -- no changes written. Re-run with --apply to persist to runic.db.")
    else:
        print("\nApplying updates to runic.db ...")
        with get_connection(db_path()) as conn:
            for d in proxy_covered:
                raw = float(unified.loc[d])
                pct = new_pctiles.get(d)
                tier_val, direction = new_tier_rows[d]
                conn.execute(
                    """
                    UPDATE daily_readings
                    SET raw_value = ?, pctile_rank_3yr = ?, unconditional_pctile = ?,
                        signal_tier = ?, direction = ?, meta_json = ?
                    WHERE var_id = 'HY' AND date = ? AND signal_tier = 'PROXY'
                    """,
                    (raw, pct, pct, tier_val, direction, meta_json_str, d.strftime("%Y-%m-%d")),
                )
            for d in new_insert:
                raw = float(unified.loc[d])
                pct = new_pctiles.get(d)
                tier_val, direction = new_tier_rows[d]
                conn.execute(
                    """
                    INSERT INTO daily_readings
                    (date, var_id, raw_value, pctile_rank_3yr, signal_tier, direction, meta_json, unconditional_pctile)
                    VALUES (?, 'HY', ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(date, var_id) DO NOTHING
                    """,
                    (d.strftime("%Y-%m-%d"), raw, pct, tier_val, direction, meta_json_str, pct),
                )
            for d in proxy_orphan + already_real:
                pct = new_pctiles.get(d)
                conn.execute(
                    """
                    UPDATE daily_readings
                    SET pctile_rank_3yr = ?, unconditional_pctile = ?
                    WHERE var_id = 'HY' AND date = ?
                    """,
                    (pct, pct, d.strftime("%Y-%m-%d")),
                )
        print(
            f"Updated {len(proxy_covered)} PROXY->real rows, inserted {len(new_insert)} new rows, "
            f"recomputed percentiles only for {len(proxy_orphan) + len(already_real)} untouched rows."
        )

    _write_report(
        args.report,
        wb_series=wb_series,
        anchor_checks=ANCHOR_CHECKS,
        proxy_covered=proxy_covered,
        proxy_orphan=proxy_orphan,
        new_insert=new_insert,
        already_real=already_real,
        db_rows=db_rows,
        tier_counts=tier_counts,
        applied=args.apply,
    )
    print(f"\nReport written to {args.report}")
    return 0


def _write_report(
    path: str, *, wb_series: pd.Series, anchor_checks: list[tuple[str, float, str]],
    proxy_covered: list[pd.Timestamp], proxy_orphan: list[pd.Timestamp], new_insert: list[pd.Timestamp],
    already_real: list[pd.Timestamp], db_rows: pd.DataFrame, tier_counts: dict[str, int], applied: bool,
) -> None:
    lines = [
        "# HY OAS Wayback Machine Backfill — Real History Replaces the BAA10Y Proxy",
        "",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d')}",
        f"**Status:** {'APPLIED to runic.db' if applied else 'DRY RUN — not written to runic.db'}",
        "**Supersedes:** `scripts/recalibrate_hy_oas_proxy.py` (Model v2 BAA10Y+VIX proxy, "
        "2026-07-29) — kept in the repo for provenance/history and as a fallback only.",
        "**Related:** `docs/ssi_validation/data_gap_report_2026-06-06.md`, "
        "`docs/MACRO_INTELLIGENCE_MASTER.md` §HY Credit Spreads OAS, "
        "`docs/ssi_validation/hy_proxy_consumer_audit_2026-07-29.md`",
        "",
        "## Source",
        "",
        f"Internet Archive (Wayback Machine) snapshot captured **{SNAPSHOT_DATE}** of FRED's own "
        "public CSV endpoint for `BAMLH0A0HYM2` (ICE BofA US High Yield OAS):",
        "",
        f"```\n{WAYBACK_URL}\n```",
        "",
        "This is days before FRED's April-2026 3-year licensing cutoff took effect (a later "
        "2026-07-16 snapshot of the same URL already shows the capped 3-year window, confirming "
        "this November-2025 capture is the last free full-history snapshot available). It "
        f"contains the **real** ICE BofA HY OAS series, {wb_series.index.min().date()} -> "
        f"{wb_series.index.max().date()} ({len(wb_series)} rows). Combined with the real data "
        "already collected live since 2023-06-09 (`src/macro_intelligence/data/pull_all.py`), "
        "coverage is now continuous real data from 1996-12-31 to today — this closes the gap "
        "completely, it does not merely improve a proxy.",
        "",
        "## Anchor cross-checks (sanity, not calibration — this is real data)",
        "",
        "| Date | Wayback value | Known public figure | Note |",
        "|------|----------------|----------------------|------|",
    ]
    for date_str, known_val, note in anchor_checks:
        wb_val = wb_series.get(pd.Timestamp(date_str))
        lines.append(f"| {date_str} | {wb_val:.2f}% | {known_val:.2f}% | {note} |")
    lines += [
        "",
        "## What changed in `daily_readings`",
        "",
        "| Category | Count | Effect |",
        "|----------|-------|--------|",
        f"| `PROXY` -> real (wayback covers the date) | {len(proxy_covered)} | `raw_value` replaced with real ICE OAS; `signal_tier`/`direction` recomputed via `evaluate_variable_tier`; `pctile_rank_3yr`/`unconditional_pctile` recomputed |",
        f"| `PROXY` orphans (wayback has no value) | {len(proxy_orphan)} | **Unchanged** — still `signal_tier='PROXY'` with the old BAA10Y-derived estimate; only percentile columns recomputed |",
        f"| New rows inserted (wayback has a value, no prior row existed) | {len(new_insert)} | Inserted as real, tier computed via `evaluate_variable_tier` |",
        f"| Already-real rows (2023-06-09 onward, live-collected) | {len(already_real)} | `raw_value`/`signal_tier`/`direction` **untouched**; only percentile columns recomputed (rolling-3y window now includes real, not proxy, pre-2023 history) |",
        "",
        f"New tier distribution among backfilled + newly-inserted dates: `{tier_counts}`.",
        "",
        "## Disclosed residual gap — 7 orphan PROXY dates",
        "",
        "These dates have `signal_tier='PROXY'` in the DB but the wayback CSV has no printed value "
        "for them (bond-market-only holidays, e.g. Good Friday, that the BAA10Y/Federal Reserve H.15 "
        "calendar used for the original 2026-06 proxy backfill did not observe as holidays, so a "
        "proxy value was computed and stored where the real ICE series has none). No free real "
        "source was found to cover this narrow residual — left on the old BAA10Y-derived estimate, "
        "not silently dropped:",
        "",
        "| Date | Old proxy raw_value |",
        "|------|----------------------|",
    ]
    for d in proxy_orphan:
        lines.append(f"| {d.date()} | {db_rows.loc[d, 'raw_value']:.4f} |")
    lines += [
        "",
        "## Downstream effects — handle explicitly, do not present as a free lunch",
        "",
        f"- **Retroactive reclassification:** {len(proxy_covered)} rows flip from `PROXY` to real "
        "`NORMAL`/`RARE`/`EXTREME` tiers across 1997-2023. This changes historical HY-driven combo "
        "fire counts (Combo A, G — `combos: [A, B, F, G]` in `CONFIG.yaml`) and any report built "
        "on them. See the addendum in `docs/ssi_validation/hy_proxy_consumer_audit_2026-07-29.md`.",
        "- `api/services/portfolio_service.py`'s `hy_is_proxy` flag will now be `False` for "
        "virtually all history (previously `True` for 1997-2023-07-13) — its docstring/behavior is "
        "unchanged, it will simply reflect the new (mostly non-proxy) reality correctly.",
        "- `src/portfolio_nav/four_book_engine.py::load_hy_mult_series()` reads `daily_readings` "
        "directly — no code change needed, but the stress-window numbers in "
        "`docs/ssi_validation/ceiling_chain_backfill_2026-07-29.md` (2008/2020/2022 `hy_mult`) "
        "should be regenerated since the underlying HY values moved from proxy to real.",
        "- `scripts/recalibrate_hy_oas_proxy.py` (Model v2) is now superseded — its header carries "
        "an explicit superseded notice; the file is kept for provenance and as a fallback only.",
        "",
        "## Regenerate",
        "",
        "```bash",
        ".venv/bin/python scripts/backfill_hy_oas_from_wayback.py --apply",
        "```",
        "",
    ]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
