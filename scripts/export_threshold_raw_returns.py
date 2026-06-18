#!/usr/bin/env python3
"""Export per-event SPX forward returns for threshold sweep bands (sections 4a/4b)."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.threshold_sweep_v2 import (  # noqa: E402
    HORIZONS,
    PRIMARY_HORIZON,
    VAR_BAND_BUILDERS,
    first_crossings,
    is_hostile,
    load_regime_map,
    load_var_series,
    regime_at,
)
from src.macro_intelligence.config import load_config  # noqa: E402
from src.macro_intelligence.data.yahoo_pull import fetch_yahoo_close  # noqa: E402
from src.macro_intelligence.db.connection import init_db  # noqa: E402
from src.macro_intelligence.engine.forward_returns import (  # noqa: E402
    _nyse_sessions,
    forward_return_pct,
)

CONFIG_RARE_BY_BAND: dict[str, str] = {
    "CAPE_high_28": "high ≥28",
    "CAPE_low_16": "low ≤16",
    "CFTC_short_15": "pctile ≤15",
    "CFTC_long_85": "pctile ≥85",
    "CNH_down_1.5pct": "|4wk| ≥1.5% (down)",
    "CNH_up_1.5pct": "|4wk| ≥1.5% (up)",
    "CPI_hot_0.20": "|surprise| ≥0.20pp",
    "CURVE_invert_30bps": "spread ≤−30bps",
    "CURVE_steepen_15bps": "steepen ≥15bps (4wk)",
    "GSR_up_5pct": "|4wk| ≥5%",
    "HY_400bps": "OAS ≥400 OR pctile ≥80",
    "NFCI_easy_0.3": "SD ≤−0.3 OR pctile ≤20",
    "NFCI_tight_0.3": "SD ≥+0.3 OR pctile ≥80",
    "VIX_25plus": "level ≥25 AND pctile ≥80",
    "VXTS_backward_1.10": "ratio ≥1.10",
    "VXTS_contango_0.95": "ratio ≤0.95",
    "WALCL_expand_0.8": "|MoM| ≥0.8% (expand)",
    "WALCL_contract_0.8": "|MoM| ≥0.8% (contract)",
    "WTI_down_6pct": "|4wk| ≥6% (down)",
    "WTI_up_6pct": "|4wk| ≥6% (up)",
}

CONFIG_EXTREME_BY_BAND: dict[str, str] = {
    "CAPE_high_28": "high ≥32",
    "CAPE_high_32": "high ≥32",
    "CAPE_low_16": "low ≤12",
    "CAPE_low_12": "low ≤12",
    "CFTC_short_15": "pctile ≤5",
    "CFTC_short_5": "pctile ≤5",
    "CFTC_long_85": "pctile ≥95",
    "CFTC_long_95": "pctile ≥95",
    "CNH_down_1.5pct": "|4wk| ≥3.5% (down)",
    "CNH_down_3.5pct": "|4wk| ≥3.5% (down)",
    "CNH_up_1.5pct": "|4wk| ≥3.5% (up)",
    "CNH_up_3.5pct": "|4wk| ≥3.5% (up)",
    "CPI_hot_0.20": "|surprise| ≥0.40pp",
    "CPI_hot_0.40": "|surprise| ≥0.40pp",
    "CURVE_invert_30bps": "spread ≤−80bps",
    "CURVE_invert_80bps": "spread ≤−80bps",
    "CURVE_steepen_15bps": "steepen ≥40bps (4wk)",
    "CURVE_steepen_40bps": "steepen ≥40bps (4wk)",
    "GSR_up_5pct": "|4wk| ≥8%",
    "GSR_up_8pct": "|4wk| ≥8%",
    "HY_400bps": "OAS ≥500 OR pctile ≥95",
    "HY_500bps": "OAS ≥500 OR pctile ≥95",
    "NFCI_easy_0.3": "SD ≤−0.8 OR pctile ≤5",
    "NFCI_tight_0.3": "SD ≥+0.8 OR pctile ≥95",
    "VIX_25plus": "level ≥35 AND pctile ≥95",
    "VIX_35plus": "level ≥35 AND pctile ≥95",
    "VXTS_backward_1.10": "ratio ≥1.20",
    "VXTS_backward_1.20": "ratio ≥1.20",
    "VXTS_contango_0.95": "ratio ≤0.85",
    "VXTS_contango_0.85": "ratio ≤0.85",
    "WALCL_expand_0.8": "|MoM| ≥2.0% (expand)",
    "WALCL_expand_2.0": "|MoM| ≥2.0% (expand)",
    "WALCL_contract_0.8": "|MoM| ≥2.0% (contract)",
    "WALCL_contract_2.0": "|MoM| ≥2.0% (contract)",
    "WTI_down_6pct": "|4wk| ≥10% (down)",
    "WTI_down_10pct": "|4wk| ≥10% (down)",
    "WTI_up_6pct": "|4wk| ≥10% (up)",
    "WTI_up_10pct": "|4wk| ≥10% (up)",
}

FIELDNAMES = [
    "variable",
    "band_label",
    "threshold_value",
    "direction",
    "bullish",
    "is_config_rare",
    "is_config_extreme",
    "config_rare",
    "config_extreme",
    "primary_horizon",
    "event_date",
    "raw_value",
    "pctile",
    "spx_return_1m_pct",
    "spx_return_3m_pct",
    "spx_return_6m_pct",
    "spx_return_9m_pct",
    "spx_return_12m_pct",
    "benchmark_1m_pct",
    "benchmark_3m_pct",
    "benchmark_6m_pct",
    "benchmark_9m_pct",
    "benchmark_12m_pct",
    "fed_cycle",
    "curve_regime",
    "hostile_regime",
]


def short_label(label: str) -> str:
    return label.replace("_CURRENT_RARE", "").replace("_CURRENT_EXTREME", "").replace("_CURRENT", "")


VAR_DEFAULT_CONFIG: dict[str, tuple[str, str]] = {
    "VIX": (CONFIG_RARE_BY_BAND["VIX_25plus"], CONFIG_EXTREME_BY_BAND["VIX_25plus"]),
    "HY": (CONFIG_RARE_BY_BAND["HY_400bps"], CONFIG_EXTREME_BY_BAND["HY_400bps"]),
    "CFTC": (CONFIG_RARE_BY_BAND["CFTC_long_85"], CONFIG_EXTREME_BY_BAND["CFTC_long_85"]),
    "NFCI": (CONFIG_RARE_BY_BAND["NFCI_easy_0.3"], CONFIG_EXTREME_BY_BAND["NFCI_easy_0.3"]),
    "WALCL": (CONFIG_RARE_BY_BAND["WALCL_expand_0.8"], CONFIG_EXTREME_BY_BAND["WALCL_expand_0.8"]),
    "WTI": (CONFIG_RARE_BY_BAND["WTI_up_6pct"], CONFIG_EXTREME_BY_BAND["WTI_up_6pct"]),
    "CNH": (CONFIG_RARE_BY_BAND["CNH_up_1.5pct"], CONFIG_EXTREME_BY_BAND["CNH_up_1.5pct"]),
    "GSR": (CONFIG_RARE_BY_BAND["GSR_up_5pct"], CONFIG_EXTREME_BY_BAND["GSR_up_5pct"]),
    "VXTS": (CONFIG_RARE_BY_BAND["VXTS_contango_0.95"], CONFIG_EXTREME_BY_BAND["VXTS_contango_0.95"]),
    "CAPE": (CONFIG_RARE_BY_BAND["CAPE_high_28"], CONFIG_EXTREME_BY_BAND["CAPE_high_28"]),
    "CPI": (CONFIG_RARE_BY_BAND["CPI_hot_0.20"], CONFIG_EXTREME_BY_BAND["CPI_hot_0.20"]),
    "CURVE": (CONFIG_RARE_BY_BAND["CURVE_steepen_15bps"], CONFIG_EXTREME_BY_BAND["CURVE_steepen_15bps"]),
}


def config_pair(side: str, var_id: str) -> tuple[str, str]:
    cfg_r = CONFIG_RARE_BY_BAND.get(side)
    cfg_e = CONFIG_EXTREME_BY_BAND.get(side)
    if cfg_r is None or cfg_e is None:
        fallback = VAR_DEFAULT_CONFIG.get(var_id, ("—", "—"))
        cfg_r = cfg_r or fallback[0]
        cfg_e = cfg_e or fallback[1]
    return cfg_r, cfg_e


def band_tier_flags(label: str, var_id: str) -> tuple[bool, bool]:
    rare = "CURRENT_RARE" in label or (var_id == "NFCI" and label.endswith("_CURRENT"))
    extreme = "CURRENT_EXTREME" in label
    return rare, extreme


def include_in_rare_file(label: str, var_id: str) -> bool:
    _, extreme = band_tier_flags(label, var_id)
    return not extreme


def include_in_extreme_file(label: str, var_id: str) -> bool:
    rare, _ = band_tier_flags(label, var_id)
    return not rare


def collect_event_rows(
    *,
    start: str,
    spx: pd.Series,
    sessions: pd.DatetimeIndex,
    regime_map: dict[str, dict[str, Any]],
    tier_filter: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    benchmarks = {h: bench for h, _, bench in HORIZONS}

    for var_id in VAR_BAND_BUILDERS:
        series = load_var_series(var_id, start)
        bands = VAR_BAND_BUILDERS[var_id]()
        primary = PRIMARY_HORIZON.get(var_id, "spx_3m")

        for band in bands:
            if tier_filter == "rare" and not include_in_rare_file(band.band_label, var_id):
                continue
            if tier_filter == "extreme" and not include_in_extreme_file(band.band_label, var_id):
                continue

            side = short_label(band.band_label)
            cfg_r, cfg_e = config_pair(side, var_id)
            is_rare, is_extreme = band_tier_flags(band.band_label, var_id)

            for event in first_crossings(series, band.in_band):
                dt = pd.Timestamp(event["date"])
                reg = regime_at(regime_map, dt)
                fed = reg.get("fed_cycle") or reg.get("fed_cycle_legacy") or reg.get("fed_cycle_v2")
                curve = reg.get("curve_regime") or reg.get("curve_regime_v2") or reg.get("curve_regime_legacy")
                hostile = is_hostile(reg)

                rets: dict[str, float | None] = {}
                for h_key, days, _ in HORIZONS:
                    col = h_key.replace("spx_", "spx_return_") + "_pct"
                    rets[col] = forward_return_pct(spx, dt, days, sessions=sessions)

                rows.append(
                    {
                        "variable": var_id,
                        "band_label": side,
                        "threshold_value": band.threshold_value,
                        "direction": band.direction,
                        "bullish": band.bullish,
                        "is_config_rare": is_rare,
                        "is_config_extreme": is_extreme,
                        "config_rare": cfg_r,
                        "config_extreme": cfg_e,
                        "primary_horizon": primary,
                        "event_date": event["date"],
                        "raw_value": event.get("raw"),
                        "pctile": event.get("pctile"),
                        "spx_return_1m_pct": rets.get("spx_return_1m_pct"),
                        "spx_return_3m_pct": rets.get("spx_return_3m_pct"),
                        "spx_return_6m_pct": rets.get("spx_return_6m_pct"),
                        "spx_return_9m_pct": rets.get("spx_return_9m_pct"),
                        "spx_return_12m_pct": rets.get("spx_return_12m_pct"),
                        "benchmark_1m_pct": benchmarks["spx_1m"],
                        "benchmark_3m_pct": benchmarks["spx_3m"],
                        "benchmark_6m_pct": benchmarks["spx_6m"],
                        "benchmark_9m_pct": benchmarks["spx_9m"],
                        "benchmark_12m_pct": benchmarks["spx_12m"],
                        "fed_cycle": fed,
                        "curve_regime": curve,
                        "hostile_regime": hostile,
                    }
                )
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def export(start: str, out_dir: Path) -> dict[str, Any]:
    init_db()
    spx = fetch_yahoo_close("^GSPC", start)
    sessions = _nyse_sessions()
    regime_map = load_regime_map()

    rare_rows = collect_event_rows(
        start=start, spx=spx, sessions=sessions, regime_map=regime_map, tier_filter="rare"
    )
    extreme_rows = collect_event_rows(
        start=start, spx=spx, sessions=sessions, regime_map=regime_map, tier_filter="extreme"
    )

    rare_path = out_dir / "section_4a_rare_threshold_raw_returns.csv"
    extreme_path = out_dir / "section_4b_extreme_threshold_raw_returns.csv"
    write_csv(rare_path, rare_rows)
    write_csv(extreme_path, extreme_rows)

    meta = {
        "start_date": start,
        "rare_events": len(rare_rows),
        "extreme_events": len(extreme_rows),
        "rare_path": str(rare_path),
        "extreme_path": str(extreme_path),
    }
    (out_dir / "section_4_raw_returns_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="1990-01-01")
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "testing/macro_th_exp/testingv2"),
    )
    args = parser.parse_args()
    load_config()  # ensure CONFIG loads
    meta = export(args.start, Path(args.out_dir))
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
