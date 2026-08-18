#!/usr/bin/env python3
"""Export 26-variable validation checklist CSV (macro + SSI per DATA_SOURCES.yaml)."""

from __future__ import annotations

import csv
import sys

import pandas as pd
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.config import load_config
from src.macro_intelligence.data.pull_all import load_all_series
from src.macro_intelligence.db.connection import get_connection, init_db
from src.sentiment_superindex.data.pull_all import load_all_series as load_ssi_series
from src.sentiment_superindex.config import SSI_INPUT_CADENCE
from src.sentiment_superindex.data.alignment import max_stale_days_for_cadence

OUT = ROOT / "macro_intelligence" / "output" / "data_validation_checklist.csv"
SOURCES = ROOT / "macro_intelligence" / "DATA_SOURCES.yaml"

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

# Every key the superindex actually scores. The map above is keyed by DATA_SOURCES.yaml var_id
# and covers only the nine inputs that happen to be declared there -- the remaining five
# (put/call, VIX term structure, both COT legs and their gross) were absent from this report,
# which is part of why a dead ^VIX3M went unnoticed for a month (audit 2026-08-18).
SSI_SCORED_KEYS = [
    "aaii_spread",
    "naaim_exposure",
    "put_call_ema",
    "cnn_fg",
    "mcclellan",
    "nh_nl_ratio",
    "hyg_lqd",
    "skew",
    "vix_ratio",
    "pct_above_200dma",
    "dbmf_beta",
    "cftc_fm_net",
    "cftc_rm_net",
    "gross_net",
]



def _last_value(series) -> float | None:
    """Last scalar value of a series, or None.

    Some macro variables load as a multi-column frame, whose ``.iloc[-1]`` is itself a Series
    -- ``float()`` on that raises and took the whole report down (pre-existing; found while
    extending this script on 2026-08-18). A report about data health must not itself fall over
    on odd-shaped data.
    """
    if series is None or getattr(series, "empty", True):
        return None
    try:
        value = series.iloc[-1]
        if hasattr(value, "iloc"):
            value = value.iloc[0]
        return float(value)
    except (TypeError, ValueError, IndexError):
        return None


def main() -> None:
    init_db()
    macro_series = load_all_series(force=True)
    ssi_series = load_ssi_series(force=True)
    cfg = load_config()
    ds = yaml.safe_load(SOURCES.read_text(encoding="utf-8"))
    rows = []

    for var in cfg.get("variables", []):
        vid = var["id"]
        s = macro_series.get(vid)
        n = len(s) if s is not None and hasattr(s, "__len__") else 0
        last = _last_value(s)
        with get_connection() as conn:
            log = conn.execute(
                "SELECT status, pulled_at FROM data_pull_log WHERE source_id LIKE ? ORDER BY log_id DESC LIMIT 1",
                (f"%{vid.lower()}%",),
            ).fetchone()
        rows.append(
            [vid, "macro", var.get("source"), n, last, log["status"] if log else "—", log["pulled_at"] if log else "—"]
        )

    for entry in ds.get("variables", []):
        vid = entry.get("var_id", "")
        if entry.get("system", "").startswith("macro") and vid in {r[0] for r in rows}:
            continue
        key = SSI_KEY_MAP.get(vid)
        if vid in ("CFTC_FM", "CFTC_RM", "GROSS_NET_DIV"):
            rows.append([vid, entry.get("system"), entry.get("source"), "—", "—", "derived", "layer3"])
            continue
        s = ssi_series.get(key) if key else None
        n = len(s) if s is not None and hasattr(s, "__len__") else 0
        last = _last_value(s)
        rows.append([vid, entry.get("system"), entry.get("source"), n, last, "live", "—"])

    # Every scored SSI input, keyed by the name the engine uses, with the age that decides
    # whether it is still eligible. This is the view that would have shown NAAIM and
    # ^VIX3M dead: row_count alone cannot, because a frozen cache keeps its rows.
    today = pd.Timestamp.now().normalize()
    for key in SSI_SCORED_KEYS:
        series = ssi_series.get(key)
        n = len(series) if series is not None and hasattr(series, "__len__") else 0
        if series is None or getattr(series, "empty", True):
            rows.append([f"SSI::{key}", "ssi_scored", "-", 0, None, "MISSING", "—"])
            continue
        last_ts = series.index[-1]
        age_days = int((today - pd.Timestamp(last_ts).normalize()).days)
        max_stale = max_stale_days_for_cadence(SSI_INPUT_CADENCE.get(key, "weekly"))
        status = "STALE" if age_days > max_stale else "OK"
        rows.append([
            f"SSI::{key}",
            "ssi_scored",
            f"cadence={SSI_INPUT_CADENCE.get(key, '?')} max_stale={max_stale}d",
            n,
            _last_value(series),
            f"{status} (age {age_days}d)",
            pd.Timestamp(last_ts).strftime("%Y-%m-%d"),
        ])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["var_id", "system", "source", "row_count", "last_value", "pull_status", "pulled_at"])
        w.writerows(rows)
    stale = [r[0] for r in rows if str(r[5]).startswith(("STALE", "MISSING"))]
    print(f"Wrote {OUT} ({len(rows)} variables)")
    if stale:
        print(f"DEGRADED SSI INPUTS ({len(stale)}): {', '.join(stale)}")


if __name__ == "__main__":
    main()
