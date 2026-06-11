#!/usr/bin/env python3
"""Export 26-variable validation checklist CSV (macro + SSI per DATA_SOURCES.yaml)."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.macro_intelligence.config import load_config
from src.macro_intelligence.data.pull_all import load_all_series
from src.macro_intelligence.db.connection import get_connection, init_db
from src.sentiment_superindex.data.pull_all import load_all_series as load_ssi_series

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
        last = float(s.iloc[-1]) if s is not None and not getattr(s, "empty", True) else None
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
        last = float(s.iloc[-1]) if s is not None and not getattr(s, "empty", True) else None
        rows.append([vid, entry.get("system"), entry.get("source"), n, last, "live", "—"])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["var_id", "system", "source", "row_count", "last_value", "pull_status", "pulled_at"])
        w.writerows(rows)
    print(f"Wrote {OUT} ({len(rows)} variables)")


if __name__ == "__main__":
    main()
