#!/usr/bin/env python3
"""
Download official CFTC Traders in Financial Futures (TFF) zips — no sample from Rohit needed.

CFTC publishes weekly updates inside the annual file:
  https://www.cftc.gov/files/dea/history/fut_fin_txt_{year}.zip  → FinFutYY.txt
Historical bulk (2006–2016):
  https://www.cftc.gov/files/dea/history/fin_fut_txt_2006_2016.zip → F_TFF_2006_2016.txt

Examples:
  .venv/bin/python scripts/download_cftc_tff_zip.py
  .venv/bin/python scripts/download_cftc_tff_zip.py --year 2025 --extract-sample
  .venv/bin/python scripts/download_cftc_tff_zip.py --all-years --start 2006
"""

from __future__ import annotations

import argparse
import io
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.data.cftc_pull import (  # noqa: E402
    CFTC_TFF_BULK_TXT,
    CFTC_TFF_BULK_URL,
    CFTC_TFF_YEAR_URL,
    _market_mask,
    parse_cftc_dataframe,
    parse_cftc_rm_dataframe,
)

MANIFEST = ROOT / "macro_intelligence" / "CFTC_TFF_COLUMNS.yaml"
DEFAULT_CACHE = ROOT / "macro_intelligence" / "data_cache" / "cftc"


def _cache_dir(override: str | None) -> Path:
    d = Path(override) if override else DEFAULT_CACHE
    d.mkdir(parents=True, exist_ok=True)
    return d


def download_url(url: str, dest: Path, *, force: bool) -> Path:
    if dest.exists() and not force:
        print(f"skip (exists): {dest}")
        return dest
    print(f"GET {url}")
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    print(f"wrote {dest} ({len(resp.content):,} bytes)")
    return dest


def download_bulk(cache: Path, *, force: bool) -> Path:
    return download_url(CFTC_TFF_BULK_URL, cache / "fin_fut_txt_2006_2016.zip", force=force)


def download_year(year: int, cache: Path, *, force: bool) -> Path:
    url = CFTC_TFF_YEAR_URL.format(year=year)
    return download_url(url, cache / f"fut_fin_txt_{year}.zip", force=force)


def read_tff_from_zip(zip_path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(zip_path) as zf:
        txt = next(n for n in zf.namelist() if n.lower().endswith(".txt"))
        return pd.read_csv(zf.open(txt), low_memory=False)


def latest_consolidated_row(df: pd.DataFrame) -> pd.Series | None:
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    market_col = manifest["required_columns"]["market"]
    date_col = manifest["required_columns"]["date"]
    primary = manifest["market"]["primary"]
    mask = _market_mask(df[market_col], {"market_primary": primary})
    sub = df.loc[mask].copy()
    if sub.empty:
        return None
    sub[date_col] = pd.to_datetime(sub[date_col], errors="coerce")
    sub = sub.sort_values(date_col)
    return sub.iloc[-1]


def extract_sample(zip_path: Path, out: Path) -> None:
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    df = read_tff_from_zip(zip_path)
    row = latest_consolidated_row(df)
    if row is None:
        raise SystemExit(f"No '{manifest['market']['primary']}' rows in {zip_path}")
    cols = list(manifest["required_columns"].values())
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([row[cols]]).to_csv(out, index=False)
    date_col = manifest["required_columns"]["date"]
    fm = parse_cftc_dataframe(df)
    rm = parse_cftc_rm_dataframe(df)
    d = pd.Timestamp(row[date_col])
    print(f"Latest consolidated report: {d.date()}")
    print(f"  FM net: {float(fm.loc[d]) if d in fm.index else 'n/a'}")
    print(f"  RM net: {float(rm.loc[d]) if d in rm.index else 'n/a'}")
    print(f"  sample CSV: {out}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Download official CFTC TFF zips to local cache")
    parser.add_argument("--cache-dir", help=f"Default: {DEFAULT_CACHE}")
    parser.add_argument("--year", type=int, help="Single year zip (default: current year)")
    parser.add_argument("--start", type=int, default=2006, help="With --all-years, first year")
    parser.add_argument("--all-years", action="store_true", help="Download bulk + every annual zip through current year")
    parser.add_argument("--bulk-only", action="store_true", help="Only 2006-2016 bulk file")
    parser.add_argument("--force", action="store_true", help="Re-download even if file exists")
    parser.add_argument(
        "--extract-sample",
        action="store_true",
        help="Write latest S&P 500 Consolidated row to tests/fixtures/cftc/tff_latest.csv",
    )
    args = parser.parse_args()
    cache = _cache_dir(args.cache_dir)
    print(f"Cache: {cache.resolve()}")

    if args.bulk_only:
        download_bulk(cache, force=args.force)
        return 0

    current = datetime.now().year
    if args.all_years:
        if args.start <= 2016:
            download_bulk(cache, force=args.force)
        for y in range(max(2017, args.start), current + 1):
            download_year(y, cache, force=args.force)
        return 0

    year = args.year or current
    if year <= 2016 and args.start <= 2016:
        zpath = download_bulk(cache, force=args.force)
    else:
        zpath = download_year(year, cache, force=args.force)

    if args.extract_sample:
        out = ROOT / "tests" / "fixtures" / "cftc" / "tff_latest.csv"
        extract_sample(zpath, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
