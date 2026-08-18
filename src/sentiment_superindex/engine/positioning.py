"""Build positioning.json payload."""

from __future__ import annotations

import logging

from datetime import datetime
from typing import Any

import pandas as pd

from src.sentiment_superindex.config import coverage_policy, load_config, staleness_policy
from src.sentiment_superindex.data.alignment import max_stale_days_for_cadence
from src.sentiment_superindex.engine.layer2 import (
    derive_layer2_sizing,
    evaluate_layer2_gates,
    hyg_vix_legacy_votes,
)
from src.sentiment_superindex.data.pull_all import layer3_for_date, load_all_series, values_as_of
from src.sentiment_superindex.engine.regime_block import build_regime_block
from src.sentiment_superindex.engine.superindex import build_superindex
from src.sentiment_superindex.engine.ssi_score import compute_ssi_at_date

logger = logging.getLogger("ssi.positioning")


# Display rounding policy: 2 decimals for every indicator (oscillators, ratios,
# betas, breadth %, spreads, CFTC net positions, etc). 4 decimals is reserved for
# actual currency pairs (e.g. USDCNH) where the extra precision is meaningful.
# No SSI input is currently a currency pair; this set exists so a future FX input
# (e.g. if a currency-pair series is ever added to layer2/layer3) automatically
# gets the wider precision instead of silently defaulting to 2dp.
_CURRENCY_PAIR_KEYS = frozenset(
    {"usdcnh", "eurusd", "gbpusd", "usdjpy", "audusd", "usdcad", "usdchf", "nzdusd"}
)

# Layer-1 display keys → series keys + publication cadence (DATA_SOURCES.yaml).
_LAYER1_INPUT_META: dict[str, dict[str, str]] = {
    "aaii_spread": {"series_key": "aaii_spread", "cadence": "weekly", "schedule_et": "Thu"},
    "naaim_exposure": {"series_key": "naaim_exposure", "cadence": "weekly", "schedule_et": "Wed"},
    "cnn_fg_raw": {"series_key": "cnn_fg", "cadence": "daily"},
    "put_call_ema": {"series_key": "put_call_ema", "cadence": "daily"},
}


def _display_decimals(key: str | None) -> int:
    if key and key.lower() in _CURRENCY_PAIR_KEYS:
        return 4
    return 2


def _round_display(
    value: float | None, *, key: str | None = None, decimals: int | None = None
) -> float | None:
    if value is None:
        return None
    if decimals is None:
        decimals = _display_decimals(key)
    rounded = round(float(value), decimals)
    if abs(rounded) < 10 ** (-decimals):
        rounded = 0.0
    return rounded


def _layer1_inputs_meta(
    series: dict[str, pd.Series],
    as_of: pd.Timestamp,
) -> dict[str, dict[str, Any]]:
    """Per Layer-1 input: cadence, as-of survey/print date, staleness vs dashboard date."""
    out: dict[str, dict[str, Any]] = {}
    as_of_norm = as_of.normalize()
    for display_key, spec in _LAYER1_INPUT_META.items():
        series_key = spec["series_key"]
        s = series.get(series_key)
        as_of_date: str | None = None
        stale_days: int | None = None
        if s is not None and not s.empty:
            sl = s.loc[:as_of].dropna()
            if not sl.empty:
                last_ts = sl.index[-1]
                as_of_date = pd.Timestamp(last_ts).strftime("%Y-%m-%d")
                # stale_days = CALENDAR days between dashboard date and last print (not business days).
                stale_days = int((as_of_norm - pd.Timestamp(last_ts).normalize()).days)
        entry: dict[str, Any] = {
            "cadence": spec["cadence"],
            "as_of": as_of_date,
            "stale_days": stale_days,
            "max_stale_days": max_stale_days_for_cadence(spec["cadence"]),
        }
        if spec.get("schedule_et"):
            entry["schedule_et"] = spec["schedule_et"]
        if series_key == "aaii_spread" and s is not None:
            entry["source"] = s.attrs.get("aaii_source")
        out[display_key] = entry
    return out


def _layer3_display_value(
    layer3_components: dict[str, Any],
    layer3_cftc: dict[str, Any],
    component_key: str,
    cftc_fallback_key: str | None = None,
) -> float | None:
    """Layer-3 display raw: prefer scored component, else CFTC snapshot for UI."""
    raw = layer3_components.get(component_key, {}).get("raw")
    if raw is not None:
        return _round_display(raw, key=component_key)
    if cftc_fallback_key and layer3_cftc:
        fallback = layer3_cftc.get(cftc_fallback_key)
        if fallback is not None:
            return _round_display(float(fallback), key=component_key)
    return None


def _layer3_cftc_meta(as_of: pd.Timestamp, cftc: dict[str, Any]) -> dict[str, Any]:
    """COT freshness meta for UI stale-dating (mirrors layer1 inputs_meta shape)."""
    if not cftc:
        return {}
    position_date = cftc.get("position_date")
    stale_days: int | None = None
    release_date: str | None = None
    if position_date:
        pos_ts = pd.Timestamp(position_date)
        stale_days = int((as_of.normalize() - pos_ts.normalize()).days)
        release_date = (pos_ts + pd.Timedelta(days=3)).strftime("%Y-%m-%d")
    return {
        "cadence": "weekly",
        "schedule_et": "Fri",
        "as_of": position_date,
        "position_date": position_date,
        "release_date": release_date,
        "expected_release": cftc.get("expected_release"),
        "next_release": cftc.get("next_release"),
        "stale_days": stale_days,
        "max_stale_days": max_stale_days_for_cadence("weekly"),
        "stale": bool(cftc.get("stale")),
        "data_freshness": cftc.get("data_freshness"),
        "positioning_pattern": cftc.get("positioning_pattern"),
        "squeeze_setup": cftc.get("squeeze_setup"),
        "liquidity_exit": cftc.get("liquidity_exit"),
        "gross_net_divergence_active": cftc.get("gross_net_divergence_active"),
        "pattern_label": cftc.get("pattern_label"),
    }



def _staleness_policy_block() -> dict[str, Any]:
    """The resolved staleness policy, emitted so the UI reads it instead of duplicating it."""
    max_stale_days, default_penalty, penalty_by_signal = staleness_policy()
    min_counts, min_weight_retained = coverage_policy()
    return {
        "max_stale_days": max_stale_days,
        "weight_penalty": default_penalty,
        "weight_penalty_by_signal": penalty_by_signal,
        "coverage": {
            "min_available_count": min_counts,
            "min_nominal_weight_retained": min_weight_retained,
        },
        "source": "SSI_CONFIG.yaml",
    }


def build_positioning_payload(as_of: str | None = None) -> dict[str, Any]:
    as_of = as_of or datetime.now().strftime("%Y-%m-%d")
    cfg = load_config()
    th = cfg.get("thresholds", {})

    superindex = build_superindex(as_of)
    level = float(superindex["ssi_level"])
    _, pctile, _ = compute_ssi_at_date(as_of)
    as_of_ts = pd.Timestamp(as_of)
    all_series = load_all_series()
    raw_inputs = values_as_of(all_series, as_of_ts)
    layer1_inputs_meta = _layer1_inputs_meta(all_series, as_of_ts)

    layer1 = superindex["layers"].get("layer1", {}).get("components", {})
    layer2 = superindex["layers"].get("layer2", {}).get("components", {})
    layer3 = superindex["layers"].get("layer3", {}).get("components", {})
    hyg_vix_votes = hyg_vix_legacy_votes(as_of)
    gate_summary = evaluate_layer2_gates(layer2, legacy_votes=hyg_vix_votes)
    layer2_status, layer2_count, ssi_mult = derive_layer2_sizing(gate_summary)
    layer3_cftc = layer3_for_date(as_of)

    # Coverage gate (2026-08-18). A gate decision built on a fraction of its inputs is not a
    # market call, so when any layer is UNRELIABLE the size multiplier goes neutral instead of
    # 0.80x / 1.20x. Without this, the 2026-08-18 outage -- four of six Layer 2 inputs lost to
    # a dead ^VIX3M feed -- published "UNCONFIRMED, 0.80x size" as though the market had moved.
    unreliable_layers = {
        key: layer["signal_coverage"].get("unreliable_reason")
        for key, layer in superindex.get("layers", {}).items()
        if layer.get("signal_coverage") and not layer["signal_coverage"].get("reliable", True)
    }
    coverage_ok = not unreliable_layers
    if not coverage_ok:
        logger.error(
            "SSI coverage gate active -- forcing neutral multiplier (was %.2fx): %s",
            ssi_mult,
            "; ".join(f"{k}: {v}" for k, v in unreliable_layers.items()),
        )
        ssi_mult = 1.0
        layer2_status = "COVERAGE_INCOMPLETE"

    long_th = float(th.get("long_entry", -0.6))
    short_th = float(th.get("short_entry", 0.85))
    long_pct_th = float(th.get("long_entry_pctile", 20))
    short_pct_th = float(th.get("short_entry_pctile", 85))

    long_active = (pctile is not None and pctile <= long_pct_th) or level <= long_th
    short_active = (pctile is not None and pctile >= short_pct_th) or level >= short_th

    long_mult = ssi_mult if long_active else 1.0
    short_mult = ssi_mult if short_active else (0.8 if layer2_status == "UNCONFIRMED" else 1.0)

    layers_out: dict[str, Any] = {}
    for layer_key, layer in superindex.get("layers", {}).items():
        layer_out: dict[str, Any] = {
            "score": round(layer["score"], 4) if layer.get("score") is not None else None,
            "weight": layer.get("weight"),
            "components": layer.get("components", {}),
        }
        if layer.get("signal_coverage"):
            layer_out["signal_coverage"] = layer["signal_coverage"]
        layers_out[layer_key] = layer_out

    return {
        "date": as_of,
        "ssi_level": round(level, 4),
        "ssi_percentile_5y": round(pctile, 2) if pctile is not None else None,
        "layer2_status": layer2_status,
        "layer2_confirmed_count": layer2_count,
        "ssi_multiplier": ssi_mult,
        "coverage_ok": coverage_ok,
        "coverage_unreliable_layers": unreliable_layers,
        "layer2_gate_direction": gate_summary.direction,
        "layer2_gate_label": gate_summary.label,
        "regime": build_regime_block(ssi_mult),
        "layers": layers_out,
        "signals": {
            "long": {
                "size_mult": long_mult,
                "entry_threshold": long_th,
                "active": long_active,
            },
            "short": {
                "size_mult": short_mult,
                "entry_threshold": short_th,
                "active": short_active,
            },
        },
        # Published so consumers stop keeping their own copy of these numbers. The Nuxt
        # freshness util used to hardcode "mirrors SSI_CONFIG.yaml" values; a mirror that
        # cannot be checked is a mirror that eventually lies.
        "staleness_policy": _staleness_policy_block(),
        "inputs_meta": {
            "layer1": layer1_inputs_meta,
            "layer3_cftc": _layer3_cftc_meta(as_of_ts, layer3_cftc),
        },
        "inputs": {
            "layer2_votes": gate_summary.votes,
            "layer2_gate_votes": gate_summary.votes,
            "layer2_gate_confirmed_count": gate_summary.confirmed_count,
            "layer2_gate_conf_long": gate_summary.conf_long,
            "layer2_gate_conf_short": gate_summary.conf_short,
            "layer2_gate_direction": gate_summary.direction,
            "layer2_gate_label": gate_summary.label,
            "layer3_cftc": layer3_cftc,
            "layer1": {
                "aaii_spread": _round_display(raw_inputs.get("aaii_spread"), key="aaii_spread"),
                "naaim_exposure": _round_display(raw_inputs.get("naaim_exposure"), key="naaim_exposure"),
                "put_call_ema": _round_display(raw_inputs.get("put_call_ema"), key="put_call_ema"),
                "cnn_fg_raw": _round_display(raw_inputs.get("cnn_fg"), key="cnn_fg"),
            },
            "layer2": {
                "mcclellan": _round_display(raw_inputs.get("mcclellan"), key="mcclellan"),
                "nh_nl_ratio": _round_display(raw_inputs.get("nh_nl_ratio"), key="nh_nl_ratio"),
                "hyg_lqd": _round_display(raw_inputs.get("hyg_lqd"), key="hyg_lqd"),
                "skew": _round_display(raw_inputs.get("skew"), key="skew"),
                "vix_ratio": _round_display(raw_inputs.get("vix_ratio"), key="vix_ratio"),
                "pct_above_200dma": _round_display(raw_inputs.get("pct_above_200dma"), key="pct_above_200dma"),
            },
            "layer3": {
                "dbmf_beta": _round_display(layer3.get("dbmf_beta", {}).get("raw"), key="dbmf_beta"),
                "cftc_fm_net": _layer3_display_value(layer3, layer3_cftc, "cftc_fm_net", "fm_net"),
                "cftc_rm_net": _layer3_display_value(layer3, layer3_cftc, "cftc_rm_net", "rm_net"),
                "gross_net": _layer3_display_value(
                    layer3, layer3_cftc, "gross_net", "gross_net_divergence"
                ),
            },
            "layer1_components": layer1,
            "layer2_components": layer2,
            "layer3_components": layer3,
        },
        "validation": {
            "threshold_source": "SSI_CONFIG.yaml",
            "design_percentile": cfg.get("ssi_score", {}).get("design_percentile", 20),
            "composite_model": "3-layer superindex (40/35/25 z-score layer means)",
            "notes": "Empirical sweep: run scripts/run_ssi_threshold_sweep.py",
        },
    }
