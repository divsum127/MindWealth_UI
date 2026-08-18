"""Layer 4 regime labels + size multiplier for positioning.json."""

from __future__ import annotations

import json
from typing import Any

from src.config_paths import MACRO_INTEL_JSON_PATH


def _var_map_from_runic() -> dict[str, dict[str, Any]]:
    if not MACRO_INTEL_JSON_PATH.exists():
        return {}
    try:
        data = json.loads(MACRO_INTEL_JSON_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    variables = data.get("variables_dashboard") or []
    return {
        str(v.get("variable", "")): v
        for v in variables
        if isinstance(v, dict) and v.get("variable")
    }


def _vix_regime_label(vix_pct: float | None) -> str:
    if vix_pct is None:
        return "NORMAL"
    if vix_pct < 30:
        return "LOW_VOL"
    if vix_pct > 70:
        return "STRESS"
    return "NORMAL"


def _trend_regime_label() -> tuple[str, dict[str, Any]]:
    """SPX vs its 200-day MA.

    Reads the cached ^GSPC close series rather than a live ``yf.Ticker(...).history(period=
    "1y")`` call. The live call had no cache and no retry, so a single yfinance hiccup put
    ``spx_price``/``spx_ma200`` at NaN and the trend leg at UNKNOWN -- observed in the live
    payload during the 2026-08-18 audit. The cache also removes the 1-year window's own
    fragility: 200 sessions out of ~252 leaves almost no headroom for a short response.
    """
    meta: dict[str, Any] = {"source": "ssi_yahoo_cache", "symbol": "^GSPC"}
    try:
        from src.sentiment_superindex.data.yahoo_cache import cached_yahoo_close

        close = cached_yahoo_close("^GSPC", "1990-01-01")
        if close.empty or len(close) < 200:
            meta["note"] = "Insufficient history for 200d MA"
            return "UNKNOWN", meta
        ma200 = float(close.rolling(200).mean().iloc[-1])
        current = float(close.iloc[-1])
        above = current >= ma200
        meta.update(
            {
                "spx_price": round(current, 2),
                "spx_ma200": round(ma200, 2),
                "above_ma200": above,
            }
        )
        return ("ABOVE_MA200" if above else "BELOW_MA200"), meta
    except Exception as exc:
        meta["error"] = str(exc)
        return "UNKNOWN", meta


def _credit_regime_label(hy_pct: float | None) -> str:
    if hy_pct is None:
        return "UNKNOWN"
    hy_bps = hy_pct * 100
    if hy_bps > 500:
        return "HIGH_STRESS"
    if hy_bps > 300:
        return "MILD_STRESS"
    return "BENIGN"


def build_regime_block(ssi_multiplier: float) -> dict[str, Any]:
    """Regime multiplier block (Layer 4) — not a scored SSI layer."""
    var_map = _var_map_from_runic()
    vix_var = var_map.get("VIX", {})
    hy_var = var_map.get("HY", {})
    vix_pct = vix_var.get("pctile_3yr") or vix_var.get("percentile")
    hy_pct = hy_var.get("current")
    trend_regime, trend_meta = _trend_regime_label()
    hy_bps = round(float(hy_pct) * 100, 1) if hy_pct is not None else None
    return {
        "vix_regime": _vix_regime_label(float(vix_pct) if vix_pct is not None else None),
        "trend_regime": trend_regime,
        "credit_regime": _credit_regime_label(float(hy_pct) if hy_pct is not None else None),
        "size_mult": round(float(ssi_multiplier), 2),
        "meta": {
            "vix_pctile_3yr": round(float(vix_pct), 2) if vix_pct is not None else None,
            "hy_bps": hy_bps,
            "spx_trend": trend_meta,
            "source": "runic_variables+yfinance" if var_map else "yfinance",
        },
    }
