#!/usr/bin/env python3
"""Generate section 4a/4b summary tables from threshold_sweep_v2 JSON artifacts."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SWEEP_DIR = ROOT / "macro_intelligence/analysis/regime_v2_experiments/threshold_sweep_v2"
HORIZON_LABEL = {"spx_1m": "1M", "spx_3m": "3M", "spx_6m": "6M", "spx_9m": "9M", "spx_12m": "12M"}

CONFIG_RARE_BY_BAND: dict[str, str] = {
    "CAPE_high_28": "high ≥28", "CAPE_low_16": "low ≤16",
    "CFTC_short_15": "pctile ≤15", "CFTC_long_85": "pctile ≥85",
    "CNH_down_1.5pct": "|4wk| ≥1.5% (down)", "CNH_up_1.5pct": "|4wk| ≥1.5% (up)",
    "CPI_hot_0.20": "|surprise| ≥0.20pp",
    "CURVE_invert_30bps": "spread ≤−30bps", "CURVE_steepen_15bps": "steepen ≥15bps (4wk)",
    "GSR_up_5pct": "|4wk| ≥5%",
    "HY_400bps": "OAS ≥400 OR pctile ≥80",
    "NFCI_easy_0.3": "SD ≤−0.3 OR pctile ≤20", "NFCI_tight_0.3": "SD ≥+0.3 OR pctile ≥80",
    "VIX_25plus": "level ≥25 AND pctile ≥80",
    "VXTS_backward_1.10": "ratio ≥1.10", "VXTS_contango_0.95": "ratio ≤0.95",
    "WALCL_expand_0.8": "|MoM| ≥0.8% (expand)", "WALCL_contract_0.8": "|MoM| ≥0.8% (contract)",
    "WTI_down_6pct": "|4wk| ≥6% (down)", "WTI_up_6pct": "|4wk| ≥6% (up)",
}

CONFIG_EXTREME_BY_BAND: dict[str, str] = {
    "CAPE_high_28": "high ≥32", "CAPE_high_32": "high ≥32", "CAPE_low_16": "low ≤12", "CAPE_low_12": "low ≤12",
    "CFTC_short_15": "pctile ≤5", "CFTC_short_5": "pctile ≤5",
    "CFTC_long_85": "pctile ≥95", "CFTC_long_95": "pctile ≥95",
    "CNH_down_1.5pct": "|4wk| ≥3.5% (down)", "CNH_down_3.5pct": "|4wk| ≥3.5% (down)",
    "CNH_up_1.5pct": "|4wk| ≥3.5% (up)", "CNH_up_3.5pct": "|4wk| ≥3.5% (up)",
    "CPI_hot_0.20": "|surprise| ≥0.40pp", "CPI_hot_0.40": "|surprise| ≥0.40pp",
    "CURVE_invert_30bps": "spread ≤−80bps", "CURVE_invert_80bps": "spread ≤−80bps",
    "CURVE_steepen_15bps": "steepen ≥40bps (4wk)", "CURVE_steepen_40bps": "steepen ≥40bps (4wk)",
    "GSR_up_5pct": "|4wk| ≥8%", "GSR_up_8pct": "|4wk| ≥8%",
    "HY_400bps": "OAS ≥500 OR pctile ≥95", "HY_500bps": "OAS ≥500 OR pctile ≥95",
    "NFCI_easy_0.3": "SD ≤−0.8 OR pctile ≤5", "NFCI_tight_0.3": "SD ≥+0.8 OR pctile ≥95",
    "VIX_25plus": "level ≥35 AND pctile ≥95", "VIX_35plus": "level ≥35 AND pctile ≥95",
    "VXTS_backward_1.10": "ratio ≥1.20", "VXTS_backward_1.20": "ratio ≥1.20",
    "VXTS_contango_0.95": "ratio ≤0.85", "VXTS_contango_0.85": "ratio ≤0.85",
    "WALCL_expand_0.8": "|MoM| ≥2.0% (expand)", "WALCL_expand_2.0": "|MoM| ≥2.0% (expand)",
    "WALCL_contract_0.8": "|MoM| ≥2.0% (contract)", "WALCL_contract_2.0": "|MoM| ≥2.0% (contract)",
    "WTI_down_6pct": "|4wk| ≥10% (down)", "WTI_down_10pct": "|4wk| ≥10% (down)",
    "WTI_up_6pct": "|4wk| ≥10% (up)", "WTI_up_10pct": "|4wk| ≥10% (up)",
}

# EXTREME-only CONFIG bands need explicit RARE column (not var default)
CONFIG_RARE_BY_BAND.update({
    "CAPE_high_32": "high ≥28",
    "CAPE_low_12": "low ≤16",
    "CFTC_short_5": "pctile ≤15",
    "CFTC_long_95": "pctile ≥85",
    "CNH_down_3.5pct": "|4wk| ≥1.5% (down)",
    "CNH_up_3.5pct": "|4wk| ≥1.5% (up)",
    "CPI_hot_0.40": "|surprise| ≥0.20pp",
    "CURVE_invert_80bps": "spread ≤−30bps",
    "CURVE_steepen_40bps": "steepen ≥15bps (4wk)",
    "GSR_up_8pct": "|4wk| ≥5%",
    "HY_500bps": "OAS ≥400 OR pctile ≥80",
    "VIX_35plus": "level ≥25 AND pctile ≥80",
    "VXTS_backward_1.20": "ratio ≥1.10",
    "VXTS_contango_0.85": "ratio ≤0.95",
    "WALCL_expand_2.0": "|MoM| ≥0.8% (expand)",
    "WALCL_contract_2.0": "|MoM| ≥0.8% (contract)",
    "WTI_down_10pct": "|4wk| ≥6% (down)",
})

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


def short_label(label: str) -> str:
    return label.replace("_CURRENT_RARE", "").replace("_CURRENT_EXTREME", "").replace("_CURRENT", "")


def band_side(band_label: str, var_id: str) -> str:
    s = short_label(band_label)
    if var_id == "CAPE":
        return "high" if "high" in s else "low"
    if var_id == "CFTC":
        return "short" if "short" in s else "long"
    if var_id == "CNH":
        return "down" if "down" in s else "up"
    if var_id == "CURVE":
        return "invert" if "invert" in s else "steepen"
    if var_id == "WALCL":
        return "expand" if "expand" in s else "contract"
    if var_id == "WTI":
        return "down" if "down" in s else "up"
    if var_id == "VXTS":
        return "backward" if "backward" in s else "contango"
    if var_id == "NFCI":
        return "easy" if "easy" in s else "tight"
    return "default"


def config_pair(side: str, var_id: str) -> tuple[str, str]:
    cfg_r = CONFIG_RARE_BY_BAND.get(side)
    cfg_e = CONFIG_EXTREME_BY_BAND.get(side)
    if cfg_r is None or cfg_e is None:
        fallback = VAR_DEFAULT_CONFIG.get(var_id, ("—", "—"))
        cfg_r = cfg_r or fallback[0]
        cfg_e = cfg_e or fallback[1]
    return cfg_r, cfg_e


def fmt_hit(hit: float | None, bullish: bool) -> str:
    if hit is None:
        return "n/a"
    suffix = "" if bullish else " ↓"
    return f"{hit * 100:.1f}%{suffix}"


def fmt_pp(x: float | None) -> str:
    if x is None:
        return "n/a"
    return f"{x:+.2f}%".replace("-", "−")


def fmt_avg(x: float | None) -> str:
    if x is None:
        return "n/a"
    return f"{x:+.2f}%".replace("-", "−")


def fmt_delta(x: float | None) -> str:
    if x is None:
        return ""
    return f"{x:+.2f}".replace("-", "−")


def band_metrics(band: dict[str, Any], ph: str) -> dict[str, Any]:
    h = (band.get("horizons") or {}).get(ph) or {}
    return {
        "n": h.get("n"),
        "hit": h.get("hit_rate"),
        "excess": h.get("excess_pct"),
        "avg": h.get("avg"),
        "bullish": band.get("bullish", True),
    }


def best_same_side_alt(
    bands: list[dict[str, Any]],
    ph: str,
    current: dict[str, Any],
    current_label: str,
    tier: str,
) -> dict[str, Any] | None:
    cur_side = band_side(current_label, current.get("variable", ""))
    cur_m = band_metrics(current, ph)
    cur_bullish = current.get("bullish", True)
    best: dict[str, Any] | None = None
    best_score: tuple[float, float] | None = None

    for b in bands:
        lbl = b.get("band_label") or ""
        if lbl == current_label:
            continue
        if tier == "RARE" and "CURRENT_EXTREME" in lbl:
            continue
        if tier == "EXTREME" and "CURRENT_RARE" in lbl:
            continue
        if band_side(lbl, current.get("variable", "")) != cur_side:
            continue
        m = band_metrics(b, ph)
        if m["n"] is None or m["n"] < 5:
            continue
        hit = m["hit"] or 0.0
        excess = m["excess"]
        if excess is None:
            continue
        # Bearish: rank by hit rate first, then excess (avoids 0% hit / SPX rally trap)
        if not cur_bullish:
            score = (hit, excess)
        else:
            score = (excess, hit)
        if best_score is None or score > best_score:
            best_score = score
            best = b
    return best


_VERDICT_OVERRIDES: dict[tuple, str] = {
    ("CAPE", "RARE", "high", "CAPE_high_28"): (
        "Keep CONFIG — Combo E uses CAPE≥28; alt high_30 raises bear hit to 27% but still poor "
        "timing signal and lowers structural severity"
    ),
    ("CAPE", "RARE", "low", "CAPE_low_16"): (
        "Keep CONFIG — only 2 deep-value episodes; threshold defines historic capitulation bucket, not optimizable"
    ),
    ("CAPE", "EXTREME", "high", "CAPE_high_32"): (
        "Keep CONFIG — extreme high CAPE is slow-burn valuation risk; alt high_30 is less extreme, not more informative"
    ),
    ("CAPE", "EXTREME", "low", "CAPE_low_12"): (
        "Keep CONFIG — zero first-crossings at ≤12 since 1990; level retained for symmetry with low_16 RARE"
    ),
    ("CPI", "RARE", "default", "CPI_hot_0.20"): (
        "Defer — single event at 0.20pp; need more CPI surprise releases before any threshold move"
    ),
    ("CPI", "EXTREME", "default", "CPI_hot_0.40"): (
        "Defer — no EXTREME fires yet; 0.40pp retained pending longer CPI surprise series"
    ),
    ("WTI", "RARE", "down", "WTI_down_6pct"): (
        "Consider down_15pct — large oil drawdown bucket (n=30, 73% bull hit 6M) better matches "
        "supply-shock recovery than ±6% symmetric leg; modest +0.8pp excess vs down_6pct"
    ),
    ("WTI", "RARE", "up", "WTI_up_6pct"): (
        "Keep CONFIG — oil spike is stress marker for Combo C but weak SPX-timing (31% bear hit); "
        "no same-side alt improves both hit and excess"
    ),
    ("WTI", "EXTREME", "down", "WTI_down_10pct"): (
        "Consider down_15pct — same recovery thesis as RARE down leg; +1.6pp excess with similar hit"
    ),
    ("WTI", "EXTREME", "up", "WTI_up_10pct"): (
        "Keep CONFIG — extreme up-oil fires are real (n=93) but SPX path is mixed; no compelling same-side retune"
    ),
    ("VIX", "RARE", "default", "VIX_25plus"): (
        "Keep CONFIG — n=72 robust; level≥25+pctile≥80 is Combo B capitulation gate; "
        "pctile-only alt trades fear level for weaker discrimination"
    ),
    ("VIX", "EXTREME", "default", "VIX_35plus"): (
        "Keep CONFIG — extreme fear episodes (n=19); alt does not improve fear-spike signal meaningfully"
    ),
    ("HY", "RARE", "default", "HY_400bps"): (
        "Keep CONFIG — OAS≥400 OR pctile≥80 matches Combo B/A credit stress; tighter 600bps "
        "raises excess slightly but cuts n and bear hit"
    ),
    ("HY", "EXTREME", "default", "HY_500bps"): (
        "Keep CONFIG — 500bps / 95th pctile is standard extreme widening; alt 600bps loses events"
    ),
    ("CFTC", "RARE", "short", "CFTC_short_15"): (
        "Keep CONFIG — contrarian short-squeeze bucket (63% bull hit); loosening to ≤10 adds "
        "fires with only +1.6pp excess — not worth diluting capitulation purity"
    ),
    ("CFTC", "RARE", "long", "CFTC_long_85"): (
        "Keep CONFIG — crowded-fast-money warning for Combo E; bear hit stays ~20% at 3M "
        "(structural, not timing); long_90 not materially better"
    ),
    ("CFTC", "EXTREME", "short", "CFTC_short_5"): (
        "Keep CONFIG — extreme short positioning aligns with Combo B; alt ≤10 similar profile"
    ),
    ("CFTC", "EXTREME", "long", "CFTC_long_95"): (
        "Keep CONFIG — 95th pctile extreme crowding; marginal alt gain not worth retiering"
    ),
    ("CNH", "RARE", "down", "CNH_down_1.5pct"): (
        "Keep CONFIG — yuan-strength shock already 82% bull hit at 3M; looser 1.0% trades "
        "0.5pp excess for less specific geo signal"
    ),
    ("CNH", "RARE", "up", "CNH_up_1.5pct"): (
        "Keep CONFIG — yuan weakness is geo-stress marker but poor SPX down-timing at 3M; "
        "no alt fixes economic story"
    ),
    ("CNH", "EXTREME", "down", "CNH_down_3.5pct"): (
        "Keep CONFIG — only n=2 at extreme; cannot retune; 3.5% remains policy extreme"
    ),
    ("CNH", "EXTREME", "up", "CNH_up_3.5pct"): (
        "Keep CONFIG — n=3 at extreme up; insufficient to move; 3.5% retained"
    ),
    ("CURVE", "RARE", "invert", "CURVE_invert_30bps"): (
        "Keep CONFIG — −30bps inversion is standard recession watch; milder −20bps does not "
        "improve recession-timing hit enough to matter"
    ),
    ("CURVE", "RARE", "steepen", "CURVE_steepen_15bps"): (
        "Keep CONFIG — post-trough steepening (76% bull hit) is recovery confirm; "
        "looser 5bps steepen dilutes signal"
    ),
    ("CURVE", "EXTREME", "invert", "CURVE_invert_80bps"): (
        "Keep CONFIG — deep inversion (n=2) too sparse; −80bps kept as deep recession marker"
    ),
    ("CURVE", "EXTREME", "steepen", "CURVE_steepen_40bps"): (
        "Keep CONFIG — violent steepening already strong (71% hit); looser alts worse"
    ),
    ("GSR", "RARE", "default", "GSR_up_5pct"): (
        "Keep CONFIG — gold/silver risk-off proxy; 3M SPX timing weak across all bands; "
        "5% is adequate RARE without overfitting"
    ),
    ("GSR", "EXTREME", "default", "GSR_up_8pct"): (
        "Keep CONFIG — extreme GSR rise is risk-off context, not actionable SPX timer at 3M"
    ),
    ("NFCI", "RARE", "easy", "NFCI_easy_0.3"): (
        "Keep CONFIG — easy conditions (Combo A/E); small n but 75% hit; alt easy_0.5 loosens "
        "definition without economic gain"
    ),
    ("NFCI", "RARE", "tight", "NFCI_tight_0.3"): (
        "Keep CONFIG — tight liquidity marker; n=8 borderline; paired easy/tight ±0.3 SD is CONFIG standard"
    ),
    ("NFCI", "EXTREME", "easy", "NFCI_easy_0.3"): (
        "Keep CONFIG — NFCI uses same ±0.3 SD tier in production; no extreme-only easy band"
    ),
    ("NFCI", "EXTREME", "tight", "NFCI_tight_0.3"): (
        "Keep CONFIG — see RARE tight; ±0.3 SD retained for Combo symmetry"
    ),
    ("VXTS", "RARE", "backward", "VXTS_backward_1.10"): (
        "Keep CONFIG — backwardation is stress (Combo D); 3M bear hit ~26% — term structure "
        "warns but does not time SPX dips; 1.10 ratio standard"
    ),
    ("VXTS", "RARE", "contango", "VXTS_contango_0.95"): (
        "Keep CONFIG — complacency (76% bull hit); 0.95 contango is Combo G/D reference; "
        "0.90 alt adds +0.25pp only with n=12"
    ),
    ("VXTS", "EXTREME", "backward", "VXTS_backward_1.20"): (
        "Keep CONFIG — extreme backwardation (n=86); marginal alt improvement not worth retiering"
    ),
    ("VXTS", "EXTREME", "contango", "VXTS_contango_0.85"): (
        "Keep CONFIG — n=4 at 0.85; too few extreme complacency fires to loosen further"
    ),
    ("WALCL", "RARE", "expand", "WALCL_expand_0.8"): (
        "Keep CONFIG — QE impulse (Combo A/C); expand_0.5 adds events but excess only +0.9pp; "
        "0.8% MoM is meaningful liquidity injection"
    ),
    ("WALCL", "RARE", "contract", "WALCL_contract_0.8"): (
        "Keep CONFIG — QT marker; bearish SPX read weak at 3M (liquidity lags); threshold OK"
    ),
    ("WALCL", "EXTREME", "expand", "WALCL_expand_2.0"): (
        "Keep CONFIG — crisis-era expansion (81% hit); already strong; no need to retune"
    ),
    ("WALCL", "EXTREME", "contract", "WALCL_contract_2.0"): (
        "Keep CONFIG — severe QT episodes rare (n=11); alt does not change policy read"
    ),
}


def _lookup_override(var: str, tier: str, side: str, band: str) -> str | None:
    key = (var, tier, side, band)
    if key in _VERDICT_OVERRIDES:
        return _VERDICT_OVERRIDES[key]
    key_default = (var, tier, "default", band)
    if key_default in _VERDICT_OVERRIDES:
        return _VERDICT_OVERRIDES[key_default]
    return None


def contextual_verdict(
    var: str,
    tier: str,
    side: str,
    cur_m: dict[str, Any],
    best_m: dict[str, Any] | None,
    delta: float | None,
    *,
    same_band: bool = False,
    cur_n_insufficient: bool = False,
    no_alt: bool = False,
) -> str:
    """Analyst verdict: variable meaning + whether best alt materially improves CONFIG."""
    band = cur_m.get("band", "")
    cn = cur_m.get("n") or 0
    cur_hit = cur_m.get("hit")
    cur_ex = cur_m.get("excess")
    cur_avg = cur_m.get("avg")
    bullish = cur_m.get("bullish", True)
    override = _lookup_override(var, tier, side, band)

    if same_band:
        return "Keep CONFIG — best same-side band is current cutoff"

    if override and (no_alt or not best_m or not best_m.get("band")):
        return override

    if cur_n_insufficient or cn < 3:
        if var == "CPI":
            return "Defer — CPI surprise history only from 2024 (n<3); threshold untestable"
        if var == "CAPE" and side == "low":
            return "Defer — deep-value CAPE fires too rare (n<3); keep CONFIG for policy consistency"
        if override:
            return override
        return f"Defer — too few events (n={cn}) to compare alternatives"

    if no_alt or not best_m or not best_m.get("band"):
        return "Keep CONFIG — no same-side alternative with enough events to compare"

    bn = best_m.get("n") or 0
    b_band = best_m.get("band", "")
    b_hit = best_m.get("hit")
    b_ex = best_m.get("excess")
    d_ex = delta if delta is not None else ((b_ex or 0) - (cur_ex or 0) if b_ex is not None and cur_ex is not None else None)
    d_hit = (b_hit - cur_hit) if b_hit is not None and cur_hit is not None else None

    if override:
        return override

    if not bullish and (cur_hit or 0) < 0.35 and (cur_avg or 0) > 3:
        return f"Keep CONFIG — bear hit weak and SPX rallied after fires; alt {b_band} does not improve economic read"
    if d_ex is not None and d_ex >= 1.5 and (b_hit or 0) >= (cur_hit or 0) and bn >= cn * 0.4:
        return f"Consider {b_band} — +{d_ex:.1f}pp excess, similar or better hit; review combo linkage"
    if d_ex is not None and d_ex < -1.0:
        return f"Keep CONFIG — alt {b_band} worse excess ({d_ex:+.1f}pp)"
    if d_hit is not None and d_hit > 0.05 and (d_ex or 0) > 0:
        return f"Marginal — {b_band} improves hit +{d_hit*100:.0f}pp but small excess gain; keep CONFIG unless combo retune"
    return f"Keep CONFIG — alt {b_band} not materially better for how {var} is used in combos"


def verdict(
    cur_m: dict[str, Any],
    best_m: dict[str, Any] | None,
    delta: float | None,
    *,
    var: str = "",
    tier: str = "",
    side: str = "",
    same_band: bool = False,
    cur_n_insufficient: bool = False,
) -> str:
    return contextual_verdict(
        var,
        tier,
        side,
        cur_m,
        best_m,
        delta,
        same_band=same_band,
        cur_n_insufficient=cur_n_insufficient,
        no_alt=best_m is None or not best_m.get("band"),
    )


def collect_rows(tier: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(SWEEP_DIR.glob("*_sweep.json")):
        if path.name.startswith("COMBO"):
            continue
        data = json.loads(path.read_text())
        var = data["variable"]
        ph = data.get("primary_horizon", "spx_3m")
        hz = HORIZON_LABEL.get(ph, ph)
        bands = data.get("sweep_results", [])

        if tier == "RARE":
            markers = ["CURRENT_RARE", "_CURRENT"] if var == "NFCI" else ["CURRENT_RARE"]
        else:
            markers = ["CURRENT_EXTREME"]

        seen: set[str] = set()
        for b in bands:
            lbl = b.get("band_label") or ""
            if tier == "RARE" and var == "NFCI":
                if not lbl.endswith("_CURRENT") or "CURRENT_RARE" in lbl or "CURRENT_EXTREME" in lbl:
                    continue
            elif not any(m in lbl for m in markers):
                continue
            if lbl in seen:
                continue
            seen.add(lbl)

            side = short_label(lbl)
            cfg_r, cfg_e = config_pair(side, var)
            b["variable"] = var
            cur_m = band_metrics(b, ph)
            cur_m["band"] = side
            cur_m["bullish"] = b.get("bullish", True)

            side_key = band_side(lbl, var)
            best = best_same_side_alt(bands, ph, b, lbl, tier)
            if best:
                best_m = band_metrics(best, ph)
                best_m["band"] = short_label(best["band_label"])
                best_m["bullish"] = best.get("bullish", True)
                delta = None
                if cur_m["excess"] is not None and best_m.get("excess") is not None:
                    delta = best_m["excess"] - cur_m["excess"]
                same = best_m["band"] == cur_m["band"]
                note = verdict(
                    cur_m,
                    best_m,
                    delta,
                    var=var,
                    tier=tier,
                    side=side_key,
                    same_band=same,
                    cur_n_insufficient=(cur_m["n"] or 0) < 5,
                )
            else:
                best_m = {}
                note = verdict(
                    cur_m,
                    None,
                    None,
                    var=var,
                    tier=tier,
                    side=side_key,
                    cur_n_insufficient=(cur_m["n"] or 0) < 5,
                )

            rows.append(
                {
                    "var": var,
                    "hz": hz,
                    "dir": "Bull" if cur_m["bullish"] else "Bear",
                    "cfg_r": cfg_r,
                    "cfg_e": cfg_e,
                    "cur_m": cur_m,
                    "best_m": best_m,
                    "note": note,
                }
            )
    return rows


def escape_md_cell(text: str | int | None) -> str:
    """Escape pipe characters so CONFIG labels like |4wk| do not break markdown tables."""
    if text is None:
        return ""
    return str(text).replace("|", "\\|")


def md_table(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| Variable | Hz | Dir | Role | Band | CONFIG RARE | CONFIG EXTREME | n | Hit% | Avg SPX | PW excess | Verdict |",
        "|----------|-----|-----|------|------|-------------|----------------|---|------|---------|-----------|---------|",
    ]
    for r in rows:
        cm = r["cur_m"]
        lines.append(
            f"| {escape_md_cell(r['var'])} | {escape_md_cell(r['hz'])} | {escape_md_cell(r['dir'])} | Current | "
            f"{escape_md_cell(cm['band'])} | {escape_md_cell(r['cfg_r'])} | {escape_md_cell(r['cfg_e'])} | "
            f"{escape_md_cell(cm['n'])} | {escape_md_cell(fmt_hit(cm['hit'], cm['bullish']))} | "
            f"{escape_md_cell(fmt_avg(cm.get('avg')))} | {escape_md_cell(fmt_pp(cm['excess']))} | |"
        )
        bm = r["best_m"]
        if bm.get("band"):
            lines.append(
                f"| {escape_md_cell(r['var'])} | {escape_md_cell(r['hz'])} | {escape_md_cell(r['dir'])} | Best alt | "
                f"{escape_md_cell(bm['band'])} | {escape_md_cell(r['cfg_r'])} | {escape_md_cell(r['cfg_e'])} | "
                f"{escape_md_cell(bm.get('n', 'n/a'))} | {escape_md_cell(fmt_hit(bm.get('hit'), bm.get('bullish', True)))} | "
                f"{escape_md_cell(fmt_avg(bm.get('avg')))} | {escape_md_cell(fmt_pp(bm.get('excess')))} | "
                f"{escape_md_cell(r['note'])} |"
            )
        else:
            lines.append(
                f"| {escape_md_cell(r['var'])} | {escape_md_cell(r['hz'])} | {escape_md_cell(r['dir'])} | Best alt | — | "
                f"{escape_md_cell(r['cfg_r'])} | {escape_md_cell(r['cfg_e'])} | "
                f"n/a | n/a | n/a | n/a | {escape_md_cell(r['note'])} |"
            )
    return "\n".join(lines)


def main() -> None:
    rare = md_table(collect_rows("RARE"))
    extreme = md_table(collect_rows("EXTREME"))
    out = ROOT / "testing/macro_th_exp/testingv2"
    (out / "_section_4a_table.md").write_text(rare + "\n", encoding="utf-8")
    (out / "_section_4b_table.md").write_text(extreme + "\n", encoding="utf-8")
    print("wrote tables", len(rare.splitlines()), len(extreme.splitlines()))


if __name__ == "__main__":
    main()
