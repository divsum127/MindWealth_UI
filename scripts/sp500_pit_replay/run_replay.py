#!/usr/bin/env python3
"""Point-in-time S&P 500 BQ replay (CE-29 / CE-30).

Rohit, 21 Sep 2026: "look at all s and p 500 names and run the cionviciotn engine, what is the
distrbiuton of BQ raw... then recommend whether we shd merge or no", "today and in past / bear
markets". Scope: docs/instruction_docs/conviction_engine_issues/sp500_point_in_time_bq_replay_scope.md.

For every quarter-end 2010–2026 and every S&P 500 member on that date with SEC facts, build the
fundamentals a reader could have seen that day, score BQ with the live engine function, add the
EV/Revenue valuation tax, and record the sell-ladder label the engine would give a quant SELL.
Forward 3/6/12-month total-price returns are then compared with the S&P 500.

Neutral by construction (stated in the report): insider ownership, agentic dimensions, P/E
percentile, dividend-cut penalty (still off live). Business type: today's store type where the
name is held, else SEC SIC code.

    .venv/bin/python -I scripts/sp500_pit_replay/run_replay.py \\
        --components <dir>/components.csv --work <cache dir> --out reports/sp500_pit_replay_YYYY-MM-DD
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402

from facts import fetch_compact_facts, fetch_sic  # noqa: E402
from pit import business_type_from_sic, fundamentals_as_of  # noqa: E402
from src.config_paths import CONVICTION_STORE_DIR  # noqa: E402
from src.conviction_engine.fundamentals_enriched import compute_bq_components_auto  # noqa: E402
from src.conviction_engine.pe_history_sec import get_cik_for_ticker  # noqa: E402
from src.conviction_engine.scoring import (  # noqa: E402
    calculate_bq_raw,
    is_coverage_incomplete,
    valuation_tax_breakdown,
    verdict_for_sell,
)

HORIZONS = {"3m": 63, "6m": 126, "12m": 252}  # trading days


def membership(components_csv: Path, start: str, end: str) -> dict[pd.Timestamp, list[str]]:
    comp = pd.read_csv(components_csv, parse_dates=["date"]).sort_values("date")
    out = {}
    for d in pd.date_range(start, end, freq="QE"):
        prior = comp[comp["date"] <= d]
        if not prior.empty:
            out[d] = [t.strip() for t in prior.iloc[-1]["tickers"].split(",") if t.strip()]
    return out


def store_types() -> dict[str, str]:
    types = {}
    for path in Path(CONVICTION_STORE_DIR).glob("*.json"):
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if rec.get("ticker") and rec.get("business_type"):
            types[str(rec["ticker"]).upper()] = rec["business_type"]
    return types


def load_prices(tickers: list[str], cache: Path) -> dict[str, pd.Series]:
    import yfinance as yf

    cache.mkdir(parents=True, exist_ok=True)
    prices: dict[str, pd.Series] = {}
    for t in tickers:
        path = cache / f"{t}.csv"
        if path.exists():
            s = pd.read_csv(path, index_col=0, parse_dates=True).iloc[:, 0]
        else:
            try:
                hist = yf.Ticker(t.replace(".", "-")).history(start="2009-06-01", auto_adjust=True)
                s = hist["Close"] if not hist.empty else pd.Series(dtype=float)
            except Exception:
                s = pd.Series(dtype=float)
            if getattr(s.index, "tz", None) is not None:
                s.index = s.index.tz_localize(None)
            s.to_frame("close").to_csv(path)
        if not s.empty:
            prices[t] = s.sort_index()
    return prices


def price_on(series: pd.Series, d: pd.Timestamp) -> float | None:
    s = series[series.index <= d]
    return float(s.iloc[-1]) if not s.empty and (d - s.index[-1]).days <= 7 else None


def forward(series: pd.Series, d: pd.Timestamp, days: int) -> float | None:
    after = series[series.index > d]
    p0 = price_on(series, d)
    if p0 is None or len(after) < days:
        return None
    return float(after.iloc[days - 1]) / p0 - 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--components", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True, help="cache dir for SEC facts and prices")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--start", default="2010-03-31")
    parser.add_argument("--end", default="2026-09-30")
    parser.add_argument("--limit", type=int, help="first N tickers only (smoke test)")
    args = parser.parse_args()

    members = membership(args.components, args.start, args.end)
    universe = sorted({t for v in members.values() for t in v})
    if args.limit:
        universe = universe[: args.limit]
    ciks = {t: get_cik_for_ticker(t.replace(".", "-")) or get_cik_for_ticker(t) for t in universe}
    covered = [t for t, c in ciks.items() if c]
    print(f"{len(members)} dates, {len(universe)} members, {len(covered)} with an SEC CIK", flush=True)

    facts: dict[str, dict] = {}
    sics: dict[str, str | None] = {}
    for i, t in enumerate(covered, 1):
        f = fetch_compact_facts(ciks[t], args.work / "facts")
        if f:
            facts[t] = f["facts"]
            sics[t] = fetch_sic(ciks[t], args.work / "facts")
        if i % 50 == 0:
            print(f"  facts {i}/{len(covered)}", flush=True)
        time.sleep(0.12)  # SEC fair-access limit is 10 requests/second

    prices = load_prices(sorted(facts) + ["^GSPC"], args.work / "prices")
    spx = prices.get("^GSPC")
    types = store_types()

    rows = []
    for d, tickers in members.items():
        as_of = d.date()
        spx_fwd = {h: (forward(spx, d, n) if spx is not None else None) for h, n in HORIZONS.items()}
        for t in tickers:
            if t not in facts or t not in prices:
                rows.append({"date": as_of.isoformat(), "ticker": t, "scored": False})
                continue
            px = price_on(prices[t], d)
            fund = fundamentals_as_of(facts[t], as_of, px)
            if not fund:
                rows.append({"date": as_of.isoformat(), "ticker": t, "scored": False})
                continue
            btype = types.get(t) or business_type_from_sic(sics.get(t), fund.get("net_margin"))
            fund["ticker"] = t
            bq = compute_bq_components_auto(fund, btype, {"skip_agent_dims": True})
            bq_raw = float(calculate_bq_raw(bq))
            record = {**fund, "business_type": btype, "bq_raw": bq_raw}
            tax = float(valuation_tax_breakdown(record).get("total") or 0.0)
            conviction = bq_raw + tax
            coverage = is_coverage_incomplete(btype)
            label, _, reason = verdict_for_sell(conviction, "long", False, coverage, bq_raw=bq_raw, fs_class=None)
            row = {"date": as_of.isoformat(), "ticker": t, "scored": True, "business_type": btype,
                   "bq_raw": round(bq_raw, 2), "valuation_tax": round(tax, 2), "conviction": round(conviction, 2),
                   "sell_label": label, "sell_reason": reason}
            for h, n in HORIZONS.items():
                r = forward(prices[t], d, n)
                row[f"fwd_{h}"] = round(r, 4) if r is not None else None
                row[f"excess_{h}"] = round(r - spx_fwd[h], 4) if r is not None and spx_fwd[h] is not None else None
            rows.append(row)

    args.out.mkdir(parents=True, exist_ok=True)
    fields = sorted({k for r in rows for k in r}, key=lambda k: (k not in ("date", "ticker", "scored"), k))
    with (args.out / "replay_rows.csv").open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows ({sum(r['scored'] for r in rows)} scored) to {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
