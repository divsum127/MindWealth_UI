#!/usr/bin/env python3
"""Validate production TFF columns against CFTC_TFF_COLUMNS.yaml and live zip."""

from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import pandas as pd
import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MANIFEST = ROOT / "macro_intelligence" / "CFTC_TFF_COLUMNS.yaml"


def load_manifest() -> dict:
    return yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))


def fetch_tff_header(*, zip_path: Path | None = None, year: int | None = None) -> list[str]:
    from datetime import datetime

    if zip_path is not None:
        with zipfile.ZipFile(zip_path) as zf:
            txt = [n for n in zf.namelist() if n.lower().endswith(".txt")][0]
            df = pd.read_csv(zf.open(txt), nrows=1, low_memory=False)
        return list(df.columns)
    y = year or datetime.now().year
    url = f"https://www.cftc.gov/files/dea/history/fut_fin_txt_{y}.zip"
    resp = requests.get(url, timeout=90)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        txt = [n for n in zf.namelist() if n.lower().endswith(".txt")][0]
        df = pd.read_csv(zf.open(txt), nrows=1, low_memory=False)
    return list(df.columns)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, help="Local fut_fin_txt_YYYY.zip (from download_cftc_tff_zip.py)")
    parser.add_argument("--year", type=int, help="Download year from CFTC if --zip not set")
    args = parser.parse_args()

    manifest = load_manifest()
    required = manifest["required_columns"]
    live_cols = set(fetch_tff_header(zip_path=args.zip, year=args.year))
    missing = [k for k, col in required.items() if col not in live_cols]
    print(f"Manifest: {MANIFEST}")
    print(f"Live TFF columns: {len(live_cols)}")
    if missing:
        print("MISSING required columns:", missing)
        for k, col in required.items():
            print(f"  {k}: {col} -> {'OK' if col in live_cols else 'MISSING'}")
        return 1
    print("All required columns present in live TFF file.")
    print("Market primary:", manifest["market"]["primary"])
    print("FM:", manifest["net_formulas"]["fm_net"])
    print("RM:", manifest["net_formulas"]["rm_net"])
    from src.macro_intelligence.data.cftc_pull import fetch_cftc_fast_money_net

    s = fetch_cftc_fast_money_net(2020)
    print(f"Parser smoke: FM series length={len(s)}, last={float(s.iloc[-1]) if len(s) else 'n/a'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
