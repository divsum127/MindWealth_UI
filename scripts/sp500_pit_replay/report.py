#!/usr/bin/env python3
"""Report for the point-in-time S&P 500 BQ replay (CE-29 / CE-30).

Reads replay_rows.csv and writes REPORT.md plus summary CSVs. Rows on the same date are not
independent and quarter-end samples overlap at 6 and 12 months, so HARD vs FULL is compared
date by date (mean difference across dates, with its standard error across dates), never by
pooling rows.

    .venv/bin/python -I scripts/sp500_pit_replay/report.py --rows <dir>/replay_rows.csv --out <dir>
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import pandas as pd

BEAR_TROUGHS = {
    "2011 (euro crisis)": "2011-09-30",
    "2015-16 (oil / China)": "2016-03-31",
    "2018 Q4": "2018-12-31",
    "2020 (COVID)": "2020-03-31",
    "2022": "2022-09-30",
}
BUCKETS = [(-99, 0, "BQ < 0"), (0, 5, "0 ≤ BQ < 5"), (5, 99, "BQ ≥ 5")]


def md_table(df: pd.DataFrame) -> str:
    """Markdown table without the optional tabulate dependency."""
    cols = list(df.columns)

    def fmt(col: str, v: object) -> str:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return "—"
        if isinstance(v, float) and col.startswith("beat_"):
            return f"{v:.0%}"
        if isinstance(v, float) and col.startswith("excess_"):
            return f"{v:+.2%}"
        return str(v)

    out = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join(fmt(c, v) for c, v in zip(cols, row)) + " |" for row in df.itertuples(index=False)]
    return "\n".join(out)


def bucket(bq: float) -> str:
    return next(label for lo, hi, label in BUCKETS if lo <= bq < hi)


def perf_table(df: pd.DataFrame, by: str) -> pd.DataFrame:
    out = []
    for key, g in df.groupby(by):
        row = {by: key, "rows": len(g), "dates": g["date"].nunique()}
        for h in ("3m", "6m", "12m"):
            ex = g[f"excess_{h}"].dropna()
            row[f"excess_{h}_mean"] = round(ex.mean(), 4) if len(ex) else None
            row[f"excess_{h}_median"] = round(ex.median(), 4) if len(ex) else None
            row[f"beat_spx_{h}"] = round((ex > 0).mean(), 3) if len(ex) else None
        out.append(row)
    return pd.DataFrame(out)


def date_level_diff(df: pd.DataFrame, a: str, b: str, h: str) -> tuple[float | None, float | None, int]:
    """Mean over dates of (mean excess of label a − mean excess of label b), its SE, n dates."""
    col = f"excess_{h}"
    per = df.dropna(subset=[col]).groupby(["date", "sell_label"])[col].mean().unstack()
    if a not in per or b not in per:
        return None, None, 0
    d = (per[a] - per[b]).dropna()
    if len(d) < 3:
        return None, None, len(d)
    return float(d.mean()), float(d.std(ddof=1) / math.sqrt(len(d))), len(d)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rows", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()

    all_rows = pd.read_csv(args.rows)
    coverage = all_rows.groupby("date")["scored"].agg(["sum", "count"]).rename(columns={"sum": "scored", "count": "members"})
    coverage["pct"] = (coverage["scored"] / coverage["members"]).round(3)
    df = all_rows[all_rows["scored"] == True].copy()  # noqa: E712
    df["bq_bucket"] = df["bq_raw"].astype(float).map(bucket)

    dist = df.groupby(["date", "bq_bucket"]).size().unstack(fill_value=0)
    dist_pct = dist.div(dist.sum(axis=1), axis=0).round(3)
    by_bucket = perf_table(df, "bq_bucket")
    by_label = perf_table(df[df["sell_label"].isin(["HARD EXIT", "FULL EXIT", "PARTIAL EXIT", "PAUSE SELL"])], "sell_label")
    weak = df[df["conviction"].astype(float) < 2]  # the ladder's quality split only applies here
    by_label_weak = perf_table(weak, "sell_label")

    args.out.mkdir(parents=True, exist_ok=True)
    coverage.to_csv(args.out / "coverage_by_date.csv")
    dist_pct.to_csv(args.out / "bq_distribution_by_date.csv")
    by_bucket.to_csv(args.out / "forward_by_bq_bucket.csv", index=False)
    by_label.to_csv(args.out / "forward_by_sell_label.csv", index=False)

    lines = ["# Point-in-time S&P 500 BQ replay — results", ""]
    lines += [f"Scored {len(df):,} name-dates across {df['date'].nunique()} quarter-ends "
              f"({df['date'].min()} to {df['date'].max()}). Coverage of index members: "
              f"{coverage['pct'].iloc[0]:.0%} on the first date, {coverage['pct'].iloc[-1]:.0%} on the last; "
              "missing names are mostly companies later acquired or delisted, so results flatter weak names.", ""]
    lines += ["## BQ distribution (share of scored members)", "", "| Date | BQ < 0 | 0 ≤ BQ < 5 | BQ ≥ 5 | scored |", "|---|---:|---:|---:|---:|"]
    picks = {"latest": dist_pct.index.max(), **BEAR_TROUGHS}
    for name, d in picks.items():
        if d in dist_pct.index:
            r = dist_pct.loc[d]
            lines.append(f"| {name} ({d}) | {r.get('BQ < 0', 0):.0%} | {r.get('0 ≤ BQ < 5', 0):.0%} | {r.get('BQ ≥ 5', 0):.0%} | {int(dist.loc[d].sum())} |")
    lines += ["", "## Forward excess return vs S&P 500 by BQ bucket", ""]
    lines += [md_table(by_bucket), ""]
    bear = df[df["date"].isin(list(BEAR_TROUGHS.values()))]
    lines += ["## Bear-market troughs only (5 dates: " + ", ".join(BEAR_TROUGHS.values()) + ")", ""]
    lines += [md_table(perf_table(bear, "bq_bucket")), ""]
    lines += ["## By sell-ladder label (names a quant SELL would hit; conviction < +2)", ""]
    lines += [md_table(by_label_weak), ""]
    lines += ["## HARD EXIT vs FULL EXIT (date-level)", "", "| Horizon | HARD − FULL mean excess | SE | t | dates |", "|---|---:|---:|---:|---:|"]
    verdict_rows = []
    for h in ("3m", "6m", "12m"):
        m, se, n = date_level_diff(weak, "HARD EXIT", "FULL EXIT", h)
        t = (m / se) if m is not None and se else None
        verdict_rows.append((h, m, t))
        lines.append(f"| {h} | {m:+.2%} | {se:.2%} | {t:+.2f} | {n} |" if m is not None else f"| {h} | — | — | — | {n} |")
    sig = [h for h, m, t in verdict_rows if t is not None and abs(t) >= 2]
    worse = [h for h, m, t in verdict_rows if m is not None and t is not None and m < 0 and abs(t) >= 2]
    rec = (
        "Keep HARD and FULL separate: HARD EXIT names did measurably worse at " + ", ".join(worse) + "."
        if worse else
        "Merge HARD and FULL EXIT: the replay shows no consistent, significant difference between them."
        if not sig else
        "Keep separate but review: the difference is significant at " + ", ".join(sig) + " but not in the expected direction."
    )
    lines += ["", f"**Recommendation:** {rec}", ""]

    # CE-30: where should the ladder's BQ cut points sit? For names a SELL would hit
    # (conviction < +2), compare names below each candidate cut with names at or above it,
    # date by date, on 12-month excess return.
    lines += ["## Sell-ladder cut points (CE-30)", "",
              "Names with conviction below +2 only. For each candidate BQ cut: mean 12-month excess of names "
              "below the cut minus names at or above it, averaged across dates.", "",
              "| BQ cut | below − above (12m) | SE | t | dates |", "|---:|---:|---:|---:|---:|"]
    sweep = []
    w = weak.dropna(subset=["excess_12m"]).copy()
    w["bq"] = w["bq_raw"].astype(float)
    for cut in range(-4, 9):
        per = w.assign(side=(w["bq"] < cut).map({True: "below", False: "above"})).groupby(["date", "side"])["excess_12m"].mean().unstack()
        if "below" not in per or "above" not in per:
            continue
        d = (per["below"] - per["above"]).dropna()
        if len(d) < 5:
            continue
        m, se = float(d.mean()), float(d.std(ddof=1) / math.sqrt(len(d)))
        sweep.append((cut, m, se, m / se if se else None, len(d)))
        lines.append(f"| {cut} | {m:+.2%} | {se:.2%} | {(m / se) if se else 0:+.2f} | {len(d)} |")
    pd.DataFrame(sweep, columns=["cut", "below_minus_above_12m", "se", "t", "dates"]).to_csv(args.out / "ladder_cut_sweep.csv", index=False)
    best = min((r for r in sweep if r[3] is not None), key=lambda r: r[3], default=None)
    if best:
        lines += ["", f"Strongest separation at BQ < {best[0]} (t = {best[3]:+.2f}). Current cuts: quality collapse below 0, "
                  "valuation stretch at +5 and above. A cut is worth keeping only where its t-stat is clearly negative "
                  "(names below it really do worse).", ""]
    lines += ["## What is neutral by construction", "",
              "- Insider ownership, the five agentic dimensions, the P/E-percentile part of the valuation tax and the dividend-cut penalty score 0 (not replayable point-in-time, or switched off live).",
              "- Forward revenue is trailing revenue; business type is today's store type where held, else the SEC SIC code.",
              "- Rows at the same date overlap at 6 and 12 months; the HARD vs FULL test is done across dates for that reason."]
    (args.out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:40]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
