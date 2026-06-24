"""Portfolio Sizer + Risk service layer.

Implements:
  - GET /api/v1/portfolio/sizer   → full PortfolioResponse per §4 of PORTFOLIO_BACKEND_REQUIREMENTS
  - GET /api/v1/portfolio/risk    → cluster correlation matrix + breaches per §5
  - POST /api/v1/portfolio/risk/analyze → user-holdings analysis
  - GET /api/v1/portfolio/risk/search  → ticker autocomplete
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from api.utils import dataframe_to_records
from src.config_paths import (
    CONVICTION_OUTPUT_DIR,
    CONVICTION_UNIVERSE_FILE,
    MACRO_INTEL_OUTPUT_DIR,
    TRADE_STORE_US_DIR,
    VIRTUAL_TRADING_LONG_CSV,
    VIRTUAL_TRADING_SHORT_CSV,
)
from src.utils.file_discovery import get_latest_csv_file

_TICKER_NAMES_CACHE_PATH = MACRO_INTEL_OUTPUT_DIR / "portfolio_ticker_names.json"
_CORRELATIONS_CACHE_PATH = MACRO_INTEL_OUTPUT_DIR / "portfolio_cluster_correlations.json"
_CORRELATIONS_MAX_AGE_DAYS = 7

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

PORTFOLIO_NOTIONAL: int = 100_000_000
IDLE_CASH_YIELD_PCT: float = 3.5

# Scenario → base regime_max_pct
_SCENARIO_REGIME_MAX: dict[str, float] = {
    "normal": 80.0,
    "stress": 65.0,
    "lowvol": 85.0,
}

# BQ tier → share of cluster budget (fraction)
_BQ_TIERS: list[tuple[float, str, float]] = [
    (8.0,  "MAX",     1.00),
    (5.0,  "TACTICAL", 0.75),
    (2.0,  "REDUCED",  0.40),
    (-99,  "BLOCKED",  0.00),
]

# Cluster definitions: id → label, budget_pct (NORMAL scenario)
_CLUSTERS: list[dict[str, Any]] = [
    {"id": "global_risk_on",  "label": "Global risk-on",    "budget_pct": 18.0},
    {"id": "semiconductors",  "label": "Semiconductors",     "budget_pct": 10.0},
    {"id": "financials",      "label": "Financials",         "budget_pct": 12.0},
    {"id": "commodities",     "label": "Commodities",        "budget_pct": 10.0},
    {"id": "canada_def",      "label": "Canada defensive",   "budget_pct": 8.0},
    {"id": "us_tech",         "label": "US Tech",            "budget_pct": 12.0},
    {"id": "india",           "label": "India",              "budget_pct": 8.0},
    {"id": "bonds",           "label": "Bonds",              "budget_pct": 5.0},
    {"id": "other",           "label": "Other",              "budget_pct": 17.0},
]

# Stress / low-vol budget scale factors (until Ahil confirms per-cluster values)
_SCENARIO_BUDGET_SCALE: dict[str, float] = {
    "normal": 1.00,
    "stress": 0.80,
    "lowvol": 1.05,
}

# Ticker → cluster (explicit map). Extended from VT book + conviction universe.
_TICKER_CLUSTER_MAP: dict[str, str] = {
    # Global risk-on ETFs / indices
    "SPY": "global_risk_on", "IWM": "global_risk_on", "QQQ": "global_risk_on",
    "VGK": "global_risk_on", "EEM": "global_risk_on", "ACWX": "global_risk_on",
    "DIA": "global_risk_on", "EFA": "global_risk_on", "EWJ": "global_risk_on",
    "FXI": "global_risk_on", "ASHR": "global_risk_on", "KWEB": "global_risk_on",
    "MCHI": "global_risk_on", "ENZL": "global_risk_on", "3033.HK": "global_risk_on",
    "XLU": "global_risk_on", "XLV": "global_risk_on", "XLY": "global_risk_on",
    "^GSPC": "global_risk_on", "^DJI": "global_risk_on", "^NDX": "global_risk_on",
    "^BVSP": "global_risk_on",
    # Semis
    "NVDA": "semiconductors", "AMD": "semiconductors", "INTC": "semiconductors",
    "AVGO": "semiconductors", "TSM": "semiconductors", "MRVL": "semiconductors",
    "AMAT": "semiconductors", "KLAC": "semiconductors", "LRCX": "semiconductors",
    "SOXX": "semiconductors", "SMH": "semiconductors", "ASML": "semiconductors",
    "MU": "semiconductors", "005930.KS": "semiconductors", "000660.KS": "semiconductors",
    # Financials
    "JPM": "financials", "BAC": "financials", "GS": "financials",
    "MS": "financials", "C": "financials", "WFC": "financials",
    "XLF": "financials", "KBE": "financials", "BRK-B": "financials", "MA": "financials",
    # Commodities
    "GLD": "commodities", "SLV": "commodities", "GC=F": "commodities",
    "CL=F": "commodities", "USO": "commodities", "USCI": "commodities",
    "XLE": "commodities", "XOP": "commodities", "GDX": "commodities", "DBC": "commodities",
    "WPM": "commodities", "BTC-USD": "commodities", "ETH-USD": "commodities", "IBIT": "commodities",
    # US Tech
    "AAPL": "us_tech", "MSFT": "us_tech", "AMZN": "us_tech",
    "GOOGL": "us_tech", "GOOG": "us_tech", "META": "us_tech", "NFLX": "us_tech",
    "ARM": "us_tech", "CRM": "us_tech", "ADBE": "us_tech", "ORCL": "us_tech",
    "PLTR": "us_tech", "ZM": "us_tech", "UBER": "us_tech", "LYFT": "us_tech",
    "TSLA": "us_tech", "COIN": "us_tech", "VGT": "us_tech", "PPH": "us_tech", "JETS": "us_tech",
    # Bonds
    "TLT": "bonds", "IEF": "bonds", "BND": "bonds", "AGG": "bonds", "LQD": "bonds",
    "IEI": "bonds", "IHI": "bonds", "RINF": "bonds", "^TNX": "bonds",
    # India
    "INDY": "india", "EPI": "india", "INDA": "india", "HDB": "india", "INFY": "india",
    "^NSEI": "india",
}

# Conviction business_type → cluster when ticker not in explicit map.
_BUSINESS_TYPE_CLUSTER: dict[str, str] = {
    "compounder": "global_risk_on",
    "saas": "us_tech",
    "income": "financials",
    "cyclical": "commodities",
}

# asset_type fallback when business_type is unknown.
_ASSET_TYPE_CLUSTER: dict[str, str] = {
    "ETF": "global_risk_on",
    "INDEX": "global_risk_on",
    "EQUITY": "global_risk_on",
    "CRYPTOCURRENCY": "commodities",
    "CURRENCY": "other",
}

# Cluster ETF proxies for rolling correlation (1y daily returns).
_CLUSTER_ETF_PROXIES: dict[str, str] = {
    "global_risk_on": "SPY",
    "semiconductors": "SOXX",
    "financials": "XLF",
    "commodities": "GLD",
    "canada_def": "EWC",
    "us_tech": "QQQ",
    "india": "INDA",
    "bonds": "TLT",
}

# Suffix-based Canada assignment
_CANADA_SUFFIXES = (".TO", ".V", ".TSX")

# Cluster correlation labels (8×8 excluding "other").
_CORRELATION_LABELS = [c["id"] for c in _CLUSTERS if c["id"] != "other"]

# Static fallback if live/cache correlation unavailable.
_CORRELATION_MATRIX_FALLBACK: list[list[float]] = [
    [1.00,  0.75,  0.59,  0.29,  0.70,  0.94,  0.53,  0.19],
    [0.75,  1.00,  0.19,  0.31,  0.48,  0.86,  0.37,  0.11],
    [0.59,  0.19,  1.00,  0.04,  0.51,  0.38,  0.34,  0.10],
    [0.29,  0.31,  0.04,  1.00,  0.59,  0.30,  0.19,  0.13],
    [0.70,  0.48,  0.51,  0.59,  1.00,  0.60,  0.42,  0.21],
    [0.94,  0.86,  0.38,  0.30,  0.60,  1.00,  0.47,  0.15],
    [0.53,  0.37,  0.34,  0.19,  0.42,  0.47,  1.00,  0.28],
    [0.19,  0.11,  0.10,  0.13,  0.21,  0.15,  0.28,  1.00],
]

_BREACH_RHO_WARN = 0.75
_BREACH_RHO_ACTION = 0.85


# ─────────────────────────────────────────────────────────────────────────────
# Data loaders
# ─────────────────────────────────────────────────────────────────────────────

def _read_csv(path: Path | str | None) -> pd.DataFrame:
    if path is None:
        return pd.DataFrame()
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return pd.DataFrame()
    try:
        df = pd.read_csv(p)
        return df if not df.empty else pd.DataFrame()
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _load_vt(side: str) -> pd.DataFrame:
    """Load open virtual trading positions for a given side."""
    base = f"virtual_trading_{side}.csv"
    path = get_latest_csv_file(base, str(TRADE_STORE_US_DIR))
    if path is None:
        path = str(VIRTUAL_TRADING_LONG_CSV if side == "long" else VIRTUAL_TRADING_SHORT_CSV)
    df = _read_csv(path)
    if df.empty:
        return df
    if "Status" in df.columns:
        df = df[df["Status"].astype(str).str.lower() == "open"].copy()
    return df


def _load_conviction_overlay(side: str) -> pd.DataFrame:
    """Latest conviction overlay for long/short VT book."""
    path = CONVICTION_OUTPUT_DIR / f"virtual_trading_{side}_conviction.csv"
    return _read_csv(path)


def _load_runic_safe() -> dict[str, Any]:
    """Load runic_output.json; return {} on missing."""
    try:
        from api.services.macro_service import _load_runic
        return _load_runic()
    except Exception:
        return {}


def _load_ssi_safe() -> dict[str, Any]:
    """Load SSI multiplier; return defaults on error."""
    try:
        from api.services.macro_service import get_ssi_multiplier
        return get_ssi_multiplier()
    except Exception:
        return {"ssi_multiplier": 1.0}


def _load_json_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save_json_cache(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def _load_ticker_names_cache() -> dict[str, str]:
    payload = _load_json_cache(_TICKER_NAMES_CACHE_PATH)
    names = payload.get("names", {})
    return {str(k).upper(): str(v) for k, v in names.items() if v}


def _refresh_ticker_names_cache(symbols: set[str], *, max_fetch: int = 15) -> dict[str, str]:
    """Return name map; fetch up to max_fetch missing symbols per call."""
    cache = _load_ticker_names_cache()
    missing = sorted(s for s in symbols if s not in cache)
    if missing:
        try:
            import yfinance as yf  # type: ignore

            for i in range(0, min(len(missing), max_fetch), 15):
                chunk = missing[i : i + 15]
                tickers = yf.Tickers(" ".join(chunk))
                for sym in chunk:
                    try:
                        ti = tickers.tickers.get(sym)
                        info = ti.info if ti else {}
                        cache[sym] = str(
                            info.get("longName") or info.get("shortName") or sym
                        )
                    except Exception:
                        cache[sym] = sym
            _save_json_cache(
                _TICKER_NAMES_CACHE_PATH,
                {"as_of": datetime.now(timezone.utc).isoformat(), "names": cache},
            )
        except Exception:
            for sym in missing[:max_fetch]:
                cache.setdefault(sym, sym)
    return {s: cache.get(s, s) for s in symbols}


def _compute_spx_trend_mult() -> tuple[float, dict[str, Any]]:
    """SPX vs 200-day MA multiplier. Below MA → 0.90 haircut."""
    meta: dict[str, Any] = {"source": "yfinance", "symbol": "^GSPC"}
    try:
        import yfinance as yf  # type: ignore

        hist = yf.Ticker("^GSPC").history(period="1y")
        if hist.empty or len(hist) < 200:
            meta["note"] = "Insufficient history for 200d MA"
            return 1.0, meta
        close = hist["Close"]
        ma200 = float(close.rolling(200).mean().iloc[-1])
        current = float(close.iloc[-1])
        above = current >= ma200
        meta.update({
            "spx_price": round(current, 2),
            "spx_ma200": round(ma200, 2),
            "above_ma200": above,
        })
        return (1.0 if above else 0.90), meta
    except Exception as exc:
        meta["error"] = str(exc)
        return 1.0, meta


def _compute_correlation_matrix_live() -> tuple[list[str], list[list[float]], dict[str, Any]]:
    """Compute cluster correlation from ETF proxy returns."""
    labels = _CORRELATION_LABELS
    meta: dict[str, Any] = {"source": "computed", "proxies": _CLUSTER_ETF_PROXIES}
    try:
        import yfinance as yf  # type: ignore

        tickers = [_CLUSTER_ETF_PROXIES[cid] for cid in labels]
        data = yf.download(tickers, period="1y", progress=False)["Close"]
        rets = data.pct_change().dropna()
        corr = rets.corr()
        matrix: list[list[float]] = []
        for li in labels:
            row: list[float] = []
            for lj in labels:
                if li == lj:
                    row.append(1.0)
                else:
                    row.append(round(float(corr.loc[_CLUSTER_ETF_PROXIES[li], _CLUSTER_ETF_PROXIES[lj]]), 4))
            matrix.append(row)
        meta["window_days"] = len(rets)
        meta["as_of"] = datetime.now(timezone.utc).isoformat()
        _save_json_cache(
            _CORRELATIONS_CACHE_PATH,
            {"labels": labels, "matrix": matrix, **meta},
        )
        return labels, matrix, meta
    except Exception as exc:
        meta["error"] = str(exc)
        return labels, _CORRELATION_MATRIX_FALLBACK, meta


def _load_correlation_matrix() -> tuple[list[str], list[list[float]], dict[str, Any]]:
    """Load cached cluster correlations; refresh if stale."""
    payload = _load_json_cache(_CORRELATIONS_CACHE_PATH)
    labels = payload.get("labels") or _CORRELATION_LABELS
    matrix = payload.get("matrix")
    meta: dict[str, Any] = {
        "source": payload.get("source", "cache"),
        "as_of": payload.get("as_of"),
        "proxies": payload.get("proxies", _CLUSTER_ETF_PROXIES),
        "window_days": payload.get("window_days"),
    }
    if matrix and len(matrix) == len(labels):
        stale = True
        if payload.get("as_of"):
            try:
                as_of = datetime.fromisoformat(str(payload["as_of"]).replace("Z", "+00:00"))
                age_days = (datetime.now(timezone.utc) - as_of).days
                stale = age_days >= _CORRELATIONS_MAX_AGE_DAYS
                meta["age_days"] = age_days
            except ValueError:
                stale = True
        if not stale:
            meta["source"] = "cache"
            return labels, matrix, meta
    return _compute_correlation_matrix_live()


# ─────────────────────────────────────────────────────────────────────────────
# Cluster assignment
# ─────────────────────────────────────────────────────────────────────────────

def _assign_cluster(
    symbol: str,
    business_type: str = "",
    asset_type: str = "",
) -> str:
    sym = str(symbol).upper().strip()
    if sym in _TICKER_CLUSTER_MAP:
        return _TICKER_CLUSTER_MAP[sym]
    for sfx in _CANADA_SUFFIXES:
        if sym.endswith(sfx.upper()):
            return "canada_def"
    if sym.endswith(".NS") or sym.endswith(".BO"):
        return "india"
    if sym.endswith(".NZ"):
        return "other"

    bt = str(business_type).strip().lower()
    if bt and bt != "nan" and bt in _BUSINESS_TYPE_CLUSTER:
        return _BUSINESS_TYPE_CLUSTER[bt]

    at = str(asset_type).strip().upper()
    if at and at in _ASSET_TYPE_CLUSTER:
        return _ASSET_TYPE_CLUSTER[at]

    # Legacy keyword hints from business_type text
    bt_lower = bt.lower()
    if "commodity" in bt_lower or "energy" in bt_lower or "material" in bt_lower:
        return "commodities"
    if "financial" in bt_lower or "bank" in bt_lower or "insur" in bt_lower:
        return "financials"
    if "tech" in bt_lower or "semi" in bt_lower or "software" in bt_lower:
        return "us_tech"
    if "bond" in bt_lower or "fixed" in bt_lower or "treasur" in bt_lower:
        return "bonds"
    return "other"


# ─────────────────────────────────────────────────────────────────────────────
# Sizing helpers
# ─────────────────────────────────────────────────────────────────────────────

def _bq_tier(bq: float | None) -> tuple[str, float]:
    """Return (tier_label, share_fraction) for a BQ score."""
    if bq is None:
        # None means NOT_APPLICABLE (ETF/INDEX) — not unscored equities.
        # Default to REDUCED tier; caller applies further adjustments.
        return "REDUCED", 0.40
    for threshold, label, share in _BQ_TIERS:
        if bq >= threshold:
            return label, share
    return "BLOCKED", 0.0


def _detect_flags(row: dict[str, Any], multi_sig_tickers: set[str]) -> list[str]:
    flags: list[str] = []
    ticker = str(row.get("ticker") or row.get("Symbol") or "").upper()
    if ticker in multi_sig_tickers:
        flags.append("MULTI-SIG")
    if row.get("fd_positive") or str(row.get("rationale", "")).find("FD+") != -1:
        flags.append("FD+")
    if row.get("fd_negative") or str(row.get("rationale", "")).find("FD-") != -1:
        flags.append("FD-")
    if row.get("yield_trap_warning") or row.get("yield_trap"):
        flags.append("YIELD TRAP")
    return flags


def _adjusted_share(base_share: float, flags: list[str], combo_c_active: bool, direction: str) -> float:
    share = base_share
    if "YIELD TRAP" in flags:
        return 0.0
    if "FD+" in flags:
        share = min(1.0, share + 0.10)
    if "FD-" in flags:
        share = max(0.0, share - 0.15)
    if combo_c_active and direction.lower() == "long":
        share = max(0.0, share - 0.20)
    return share


# ─────────────────────────────────────────────────────────────────────────────
# Ceiling computation
# ─────────────────────────────────────────────────────────────────────────────

def _compute_ceiling(
    scenario: str,
    runic: dict[str, Any],
    ssi: dict[str, Any],
    *,
    spx_trend_mult: float | None = None,
    spx_trend_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    regime_max = _SCENARIO_REGIME_MAX.get(scenario, 80.0)

    # VIX from runic — actual field is 'pctile_3yr' in variables_dashboard
    variables = runic.get("variables_dashboard", [])
    var_map: dict[str, Any] = {v.get("variable", ""): v for v in variables if isinstance(v, dict)}
    vix_var = var_map.get("VIX", {})
    vix_level: float | None = vix_var.get("current")
    # runic stores percentile as 'pctile_3yr' (0-100 scale)
    vix_pct: float | None = (
        vix_var.get("pctile_3yr")
        or vix_var.get("percentile")
        or vix_var.get("pct")
    )

    # VIX regime from percentile
    if vix_pct is not None:
        if vix_pct < 30:
            vix_regime = "LOW_VOL"
        elif vix_pct > 70:
            vix_regime = "STRESS"
        else:
            vix_regime = "NORMAL"
    else:
        vix_regime = "NORMAL"

    # VIX level multiplier
    if vix_level is not None:
        if vix_level > 30:
            vix_level_mult = 0.90
        elif vix_level > 25:
            vix_level_mult = 0.95
        else:
            vix_level_mult = 1.00
    else:
        vix_level_mult = 1.00

    # SPX trend multiplier from ^GSPC 200d MA (yfinance) unless precomputed.
    if spx_trend_mult is None:
        spx_trend_mult, spx_meta = _compute_spx_trend_mult()
    else:
        spx_meta = spx_trend_meta or {}

    # HY credit multiplier from runic HY variable.
    # runic stores HY as PERCENTAGE (e.g. 2.66 = 266bps).
    # Thresholds: >5.0% = 500bps (high stress), >4.0% = 400bps, >3.0% = 300bps.
    hy_var = var_map.get("HY", {})
    hy_pct: float | None = hy_var.get("current")  # in % (divide by 100 to get decimal)
    hy_bps: float | None = round(hy_pct * 100, 1) if hy_pct is not None else None
    if hy_pct is not None:
        if hy_pct > 5.0:      # > 500bps
            hy_credit_mult = 0.80
        elif hy_pct > 4.0:    # > 400bps
            hy_credit_mult = 0.85
        elif hy_pct > 3.0:    # > 300bps
            hy_credit_mult = 0.90
        else:                  # <= 300bps — benign credit environment
            hy_credit_mult = 1.00
    else:
        hy_credit_mult = 0.90  # default haircut when data unavailable

    # SSI multiplier: spec calls it a "haircut" multiplier.
    # Values > 1.0 occur when SSI is bullish (risk-on posture); spec intent is a haircut
    # when SSI is risk-off. Cap at 1.0 so it only reduces, never inflates, the ceiling.
    ssi_multiplier_raw: float = float(ssi.get("ssi_multiplier") or 1.0)
    ssi_multiplier: float = min(1.0, ssi_multiplier_raw)

    raw_ceiling = regime_max * vix_level_mult * spx_trend_mult * hy_credit_mult * ssi_multiplier
    final_ceiling_pct = round(min(100.0, raw_ceiling), 2)

    formula_text = (
        f"{regime_max:.0f}% regime max"
        f" × {vix_level_mult:.2f} VIX"
        f" × {spx_trend_mult:.2f} trend"
        f" × {hy_credit_mult:.2f} HY credit"
        f" × {ssi_multiplier:.2f} SSI"
    )

    # Regime from macro — actual keys: 'val_regime', 'geo_overlay'
    regime_data: dict[str, Any] = runic.get("regime", {})
    val_regime: str = regime_data.get("val_regime") or regime_data.get("valuation") or "UNKNOWN"
    geo_overlay: str = regime_data.get("geo_overlay") or regime_data.get("geo") or "NEUTRAL"

    if hy_bps is not None:
        hy_stress = "high stress" if hy_bps > 500 else "mild stress" if hy_bps > 300 else "benign"
        hy_note = f"HY credit at {hy_bps:.0f}bps = {hy_stress}; {int((1-hy_credit_mult)*100)}% haircut applied."
    else:
        hy_note = "HY credit data unavailable; default 10% haircut applied."

    return {
        "vix": vix_level,
        "vix_pct": round(vix_pct, 1) if vix_pct is not None else None,
        "vix_regime": vix_regime,
        "val_regime": val_regime,
        "geo_overlay": geo_overlay,
        "regime_max_pct": regime_max,
        "ssi_multiplier": ssi_multiplier,
        "ssi_multiplier_raw": ssi_multiplier_raw,
        "vix_level_mult": vix_level_mult,
        "spx_trend_mult": spx_trend_mult,
        "spx_trend_meta": spx_meta,
        "hy_credit_mult": hy_credit_mult,
        "hy_bps": hy_bps,
        "final_ceiling_pct": final_ceiling_pct,
        "formula_text": formula_text,
        "portfolio_notional": PORTFOLIO_NOTIONAL,
        "idle_cash_yield_pct": IDLE_CASH_YIELD_PCT,
        "note": hy_note,
        "steps": [
            {"label": "Regime max", "value": f"{regime_max:.0f}%"},
            {"label": "VIX level mult", "value": f"×{vix_level_mult:.2f}"},
            {"label": "SPX trend mult", "value": f"×{spx_trend_mult:.2f}"},
            {"label": "HY credit mult", "value": f"×{hy_credit_mult:.2f}"},
            {"label": "SSI mult", "value": f"×{ssi_multiplier:.2f}"},
            {"label": "Final ceiling", "value": f"{final_ceiling_pct:.1f}%"},
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Active combo helpers
# ─────────────────────────────────────────────────────────────────────────────

def _active_combos_payload(runic: dict[str, Any]) -> list[dict[str, Any]]:
    combos = runic.get("active_combos", [])
    out = []
    for c in combos:
        cid = c.get("combo", "")
        label = f"COMBO {cid} wk {c.get('duration_weeks', '?')}"
        direction = c.get("direction") or c.get("brave_fearful") or ""
        hit = c.get("hit_rate_3m") or c.get("hit_rate_primary")
        detail_parts = []
        if hit:
            detail_parts.append(f"{direction} {int(hit)}%")
        if cid == "C":
            detail_parts.append("new entries −20 pct pts")
        out.append({"id": cid, "label": label, "detail": " · ".join(detail_parts)})
    return out


def _combo_c_active(runic: dict[str, Any]) -> bool:
    return any(c.get("combo") == "C" for c in runic.get("active_combos", []))


def _macro_override(runic: dict[str, Any]) -> dict[str, Any]:
    regime = runic.get("regime", {})
    reasons = []
    # Actual key is 'val_regime' in runic_output.json
    val = (regime.get("val_regime") or regime.get("valuation") or "").upper()
    if "EXTREME" in val:
        cape_val = None
        for v in runic.get("variables_dashboard", []):
            if isinstance(v, dict) and v.get("variable") == "CAPE":
                cape_val = v.get("current")
        reasons.append(f"Valuation extreme: CAPE {cape_val:.1f}×" if cape_val else "Valuation extreme")
    # Actual key is 'geo_overlay' in runic_output.json
    geo = (regime.get("geo_overlay") or regime.get("geo") or "").upper()
    if geo and geo != "NEUTRAL":
        reasons.append(f"Geopolitical: {geo}")
    return {"active": bool(reasons), "reasons": reasons}


# ─────────────────────────────────────────────────────────────────────────────
# Main sizer function
# ─────────────────────────────────────────────────────────────────────────────

def get_portfolio_sizer(scenario: str = "normal") -> dict[str, Any]:
    """Build full PortfolioResponse for a given scenario.

    scenario: 'normal' | 'stress' | 'lowvol'
    """
    scenario = scenario.lower()
    if scenario not in _SCENARIO_REGIME_MAX:
        raise ValueError(f"Invalid scenario '{scenario}'. Use: normal, stress, lowvol")

    runic = _load_runic_safe()
    ssi = _load_ssi_safe()
    combo_c = _combo_c_active(runic)

    spx_trend_mult, spx_meta = _compute_spx_trend_mult()
    ceiling = _compute_ceiling(
        scenario, runic, ssi,
        spx_trend_mult=spx_trend_mult,
        spx_trend_meta=spx_meta,
    )
    final_pct = ceiling["final_ceiling_pct"]
    notional = PORTFOLIO_NOTIONAL
    deployed_cap_usd = round(notional * final_pct / 100)

    # Load VT book (open positions)
    long_df = _load_vt("long")
    short_df = _load_vt("short")

    # Load conviction overlays
    long_conv = _load_conviction_overlay("long")
    short_conv = _load_conviction_overlay("short")

    # Merge conviction into long positions
    long_rows = _merge_conviction(long_df, long_conv, side="long")
    short_rows = _merge_conviction(short_df, short_conv, side="short")
    all_rows = long_rows + short_rows

    # Detect MULTI-SIG tickers (same ticker with ≥2 open signals)
    from collections import Counter
    ticker_counts: Counter[str] = Counter(
        str(r.get("ticker") or r.get("Symbol") or "").upper()
        for r in all_rows
    )
    multi_sig_tickers: set[str] = {t for t, n in ticker_counts.items() if n >= 2 and t}

    # Resolve company names from cache (never null — fallback to ticker symbol).
    unique_tickers = {
        str(r.get("ticker") or r.get("Symbol") or "").upper()
        for r in all_rows
    } - {""}
    name_map = _refresh_ticker_names_cache(unique_tickers, max_fetch=0)

    # Assign clusters and compute sizing
    budget_scale = _SCENARIO_BUDGET_SCALE.get(scenario, 1.0)
    cluster_map: dict[str, dict[str, Any]] = {}
    for c in _CLUSTERS:
        scaled_pct = round(c["budget_pct"] * budget_scale, 2)
        cluster_map[c["id"]] = {
            "id": c["id"],
            "label": c["label"],
            "budget_pct": scaled_pct,
            "budget_usd": round(notional * scaled_pct / 100),
            "deployed_usd": 0,
            "deployed_pct": 0.0,
            "max_pct": scaled_pct,
            "positions": [],
        }

    sized_rows: list[dict[str, Any]] = []
    for row in all_rows:
        ticker = str(row.get("ticker") or row.get("Symbol") or "").upper()
        business_type = str(row.get("business_type") or "")
        asset_type = str(row.get("asset_type") or "")
        cluster_id = _assign_cluster(ticker, business_type, asset_type)
        cluster = cluster_map[cluster_id]

        bq = row.get("bq_raw")
        if bq is not None:
            try:
                bq = float(bq)
            except (TypeError, ValueError):
                bq = None

        verdict = str(row.get("verdict") or "")
        not_applicable = verdict.upper() == "NOT_APPLICABLE"
        unscored = bq is None and not not_applicable and not verdict
        tier_label, base_share = _bq_tier(bq)

        # For NOT_APPLICABLE (ETFs/Indexes): use conviction_score as guidance if available
        if not_applicable and bq is None:
            cscore = _safe_float(row.get("conviction_score"))
            if cscore is not None:
                # Map conviction_score (typically −10 to +10) to tier
                if cscore >= 5:
                    tier_label, base_share = "TACTICAL", 0.75
                elif cscore >= 2:
                    tier_label, base_share = "REDUCED", 0.40
                elif cscore < 0:
                    tier_label, base_share = "BLOCKED", 0.00
                # else keep REDUCED default

        flags = _detect_flags(row, multi_sig_tickers)
        direction = str(row.get("Signal") or row.get("direction") or "Long")
        adj_share = _adjusted_share(base_share, flags, combo_c, direction)

        blocked = adj_share == 0.0 or tier_label == "BLOCKED"
        allocation_usd = 0 if blocked else round(cluster["budget_usd"] * adj_share)
        allocation_pct = round(allocation_usd / notional * 100, 4) if notional else 0.0

        win_rate_val = _safe_float(row.get("Backtested Win Rate [%]"))

        # P&L enrichment
        entry_price = _safe_float(row.get("Entry Price"))
        today_price = _safe_float(row.get("Today price"))
        pnl_pct_raw = str(row.get("Realised/Unrealised Profit") or "").replace("%", "").strip()
        pnl_pct = _safe_float(pnl_pct_raw)

        shares: float | None = None
        market_value_usd: float | None = None
        pnl_usd: float | None = None
        if allocation_usd and entry_price and entry_price > 0:
            shares = round(allocation_usd / entry_price, 4)
        if shares is not None and today_price is not None:
            market_value_usd = round(shares * today_price, 2)
        if market_value_usd is not None and allocation_usd:
            pnl_usd = round(market_value_usd - allocation_usd, 2)

        sized_row: dict[str, Any] = {
            "ticker": ticker,
            "name": name_map.get(ticker, ticker),
            "investment_type": cluster["label"],
            "cluster_id": cluster_id,
            "function": row.get("Function") or row.get("function"),
            "interval": _normalize_interval(row.get("Interval") or row.get("interval")),
            "direction": direction,
            "entry_date": row.get("Entry Date"),
            "entry_price": entry_price,
            "today_price": today_price,
            "shares": shares,
            "market_value_usd": market_value_usd,
            "pnl_usd": pnl_usd,
            "pnl_pct": pnl_pct,
            "bq_score": bq,
            "conviction_score": _safe_float(row.get("conviction_score")),
            "verdict": verdict or None,
            "not_applicable": not_applicable,
            "unscored": unscored,
            "size_tier": f"{tier_label} {int(adj_share*100)}%" if not blocked else "BLOCKED",
            "allocation_usd": allocation_usd,
            "allocation_pct": allocation_pct,
            "flags": flags,
            "blocked": blocked,
            "blocked_reason": (
                "YIELD TRAP" if "YIELD TRAP" in flags
                else "No conviction score — run conviction engine" if unscored and blocked
                else "No conviction score — conservative REDUCED tier" if unscored
                else "conviction_score < 0" if not_applicable and blocked
                else "BQ < 2" if tier_label == "BLOCKED" and not not_applicable
                else None
            ),
            "win_rate": win_rate_val,
            "backtested_win_rate_pct": win_rate_val,
            "win_rate_label": "Backtested Win Rate",
        }

        if not blocked:
            cluster["deployed_usd"] += allocation_usd

        cluster["positions"].append(sized_row)
        sized_rows.append(sized_row)

    # Compute deployed_pct per cluster
    for c in cluster_map.values():
        c["deployed_pct"] = round(c["deployed_usd"] / notional * 100, 4) if notional else 0.0

    # Summary
    total_deployed = sum(c["deployed_usd"] for c in cluster_map.values())
    total_deployed = min(total_deployed, deployed_cap_usd)  # cap at ceiling
    cash_usd = notional - total_deployed
    idle_income = round(cash_usd * IDLE_CASH_YIELD_PCT / 100, 0)
    open_count = sum(1 for r in sized_rows if not r["blocked"])

    summary = {
        "deployed_usd": total_deployed,
        "deployed_pct": round(total_deployed / notional * 100, 2),
        "cash_usd": cash_usd,
        "cash_pct": round(cash_usd / notional * 100, 2),
        "idle_income_usd": idle_income,
        "open_position_count": open_count,
    }

    # Constraints
    constraints = _build_constraints(cluster_map, combo_c, summary)

    # Active combos
    active_combos = _active_combos_payload(runic)

    return {
        "date": runic.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "as_of": datetime.now(timezone.utc).isoformat(),
        "scenario": scenario,
        "scenarios_available": True,
        "ceiling": ceiling,
        "summary": summary,
        "clusters": list(cluster_map.values()),
        "pnl_rows": sized_rows,
        "constraints": constraints,
        "active_combos": active_combos,
        "macro_override": _macro_override(runic),
        "risk": {
            "available": True,
            "message": "Use GET /api/v1/portfolio/risk for full correlation matrix.",
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _safe_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        f = float(str(val).replace("%", "").strip())
        return None if math.isnan(f) else f
    except (ValueError, TypeError):
        return None


def _normalize_interval(raw: Any) -> str | None:
    if raw is None:
        return None
    r = str(raw).strip().lower()
    if r.startswith("m"):
        return "Monthly"
    if r.startswith("w"):
        return "Weekly"
    if r.startswith("d"):
        return "Daily"
    return str(raw)


def _merge_conviction(vt_df: pd.DataFrame, conv_df: pd.DataFrame, side: str) -> list[dict[str, Any]]:
    """Merge VT rows with conviction overlay on Symbol/ticker.

    Handles duplicate tickers by taking the first conviction row per ticker.
    """
    if vt_df.empty:
        return []
    rows = dataframe_to_records(vt_df)
    if conv_df.empty:
        return rows
    conv_df = conv_df.copy()
    # Normalise key column name
    if "ticker" not in conv_df.columns and "Symbol" in conv_df.columns:
        conv_df = conv_df.rename(columns={"Symbol": "ticker"})
    if "ticker" not in conv_df.columns:
        return rows

    conv_df["ticker"] = conv_df["ticker"].astype(str).str.upper()
    # Drop duplicates — keep first occurrence per ticker to avoid orient='index' error
    conv_dedup = conv_df.drop_duplicates(subset=["ticker"], keep="first")
    conv_index: dict[str, dict[str, Any]] = {}
    for rec in dataframe_to_records(conv_dedup):
        t = str(rec.get("ticker") or "").upper()
        if t:
            conv_index[t] = rec

    merged = []
    for row in rows:
        sym = str(row.get("Symbol") or "").upper()
        extra = conv_index.get(sym, {})
        merged.append({**extra, **row})  # VT fields take priority for price/date cols
    return merged


def _build_constraints(
    cluster_map: dict[str, dict[str, Any]],
    combo_c: bool,
    summary: dict[str, Any],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    over_budget = [c for c in cluster_map.values() if c["deployed_usd"] > c["budget_usd"]]
    if over_budget:
        names = ", ".join(c["label"] for c in over_budget)
        items.append({"level": "warn", "title": "Cluster over budget", "body": f"{names} exceed cluster budget."})
    else:
        items.append({"level": "ok", "title": "Cluster caps", "body": "All clusters within budget."})

    if combo_c:
        items.append({"level": "warn", "title": "Combo C active", "body": "New long entries reduced by 20 pct pts this week."})

    cash_pct = summary.get("cash_pct", 100.0)
    if cash_pct < 10:
        items.append({"level": "bad", "title": "Low cash floor", "body": f"Cash at {cash_pct:.1f}% — below 10% minimum."})
    elif cash_pct < 20:
        items.append({"level": "warn", "title": "Cash floor", "body": f"Cash at {cash_pct:.1f}% — approaching minimum."})
    else:
        items.append({"level": "ok", "title": "Cash floor", "body": f"Cash at {cash_pct:.1f}% — adequate."})

    return items


# ─────────────────────────────────────────────────────────────────────────────
# Portfolio Risk service
# ─────────────────────────────────────────────────────────────────────────────

def get_portfolio_risk(scenario: str = "normal") -> dict[str, Any]:
    """Cluster correlation matrix + breach list + cluster weight bars."""
    scenario = scenario.lower()
    if scenario not in _SCENARIO_REGIME_MAX:
        raise ValueError(f"Invalid scenario '{scenario}'. Use: normal, stress, lowvol")

    labels, matrix, corr_meta = _load_correlation_matrix()

    # Cluster weights from sizer for requested scenario
    try:
        sizer = get_portfolio_sizer(scenario)
        clusters = sizer.get("clusters", [])
        notional = PORTFOLIO_NOTIONAL
    except Exception:
        clusters = []
        notional = PORTFOLIO_NOTIONAL

    # Build weight map by cluster id
    weight_map: dict[str, float] = {}
    for c in clusters:
        cid = c.get("id", "")
        if cid in labels:
            weight_map[cid] = c.get("deployed_pct", 0.0)

    # Breaches
    breaches: list[dict[str, Any]] = []
    n = len(labels)
    for i in range(n):
        for j in range(i + 1, n):
            rho = matrix[i][j]
            if rho > _BREACH_RHO_WARN:
                ci = labels[i]
                cj = labels[j]
                wi = weight_map.get(ci, 0.0)
                wj = weight_map.get(cj, 0.0)
                combined_pct = round(wi + wj, 2)
                combined_usd = round(notional * combined_pct / 100)
                cap_pct = 20.0  # max combined for correlated pair
                level = "action" if rho > _BREACH_RHO_ACTION else "watch"

                ci_label = next((c["label"] for c in _CLUSTERS if c["id"] == ci), ci)
                cj_label = next((c["label"] for c in _CLUSTERS if c["id"] == cj), cj)

                rec = ""
                if combined_pct > cap_pct:
                    excess_usd = round((combined_pct - cap_pct) / 100 * notional)
                    rec = f"Reduce {cj_label} by ~${excess_usd:,} or trim {ci_label}."

                breaches.append({
                    "pair": [ci, cj],
                    "pair_labels": [ci_label, cj_label],
                    "rho": round(rho, 2),
                    "level": level,
                    "combined_weight_pct": combined_pct,
                    "combined_weight_usd": combined_usd,
                    "cap_pct": cap_pct,
                    "recommendation": rec or None,
                })

    weight_bars = [
        {
            "cluster_id": cid,
            "label": next((c["label"] for c in _CLUSTERS if c["id"] == cid), cid),
            "deployed_pct": weight_map.get(cid, 0.0),
            "max_pct": next((c["budget_pct"] for c in _CLUSTERS if c["id"] == cid), 0.0),
        }
        for cid in labels
    ]

    return {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "scenario": scenario,
        "labels": labels,
        "matrix": matrix,
        "correlation_meta": corr_meta,
        "breaches": breaches,
        "breach_threshold_watch": _BREACH_RHO_WARN,
        "breach_threshold_action": _BREACH_RHO_ACTION,
        "cluster_weights": weight_bars,
    }


def analyze_user_holdings(holdings: list[dict[str, Any]], cash_usd: float = 0.0) -> dict[str, Any]:
    """Analyze user-entered holdings vs model book.

    holdings: [{"symbol": "SPY", "quantity": 120}, ...]
    """
    if not holdings:
        raise ValueError("holdings list is empty")

    # Resolve live prices (use today_price from VT or yfinance if available)
    enriched: list[dict[str, Any]] = []
    total_notional = cash_usd

    for h in holdings:
        symbol = str(h.get("symbol") or "").upper().strip()
        qty = float(h.get("quantity") or 0)
        price: float | None = _fetch_price_safe(symbol)
        notional_val = round(qty * price, 2) if price else 0.0
        total_notional += notional_val
        cluster_id = _assign_cluster(symbol, asset_type=str(h.get("asset_type") or ""))
        cluster_label = next((c["label"] for c in _CLUSTERS if c["id"] == cluster_id), cluster_id)
        name = _refresh_ticker_names_cache({symbol}, max_fetch=1).get(symbol, symbol)
        enriched.append({
            "symbol": symbol,
            "name": name,
            "quantity": qty,
            "live_price": price,
            "notional_usd": notional_val,
            "cluster_id": cluster_id,
            "cluster_label": cluster_label,
        })

    if total_notional <= 0:
        raise ValueError("Could not compute total notional — prices unavailable or all quantities zero.")

    # User cluster weights
    user_weights: dict[str, float] = {}
    for h in enriched:
        cid = h["cluster_id"]
        user_weights[cid] = user_weights.get(cid, 0.0) + (h["notional_usd"] / total_notional * 100)

    # Concentration check vs model
    suggestions: list[dict[str, Any]] = []
    for cid, wpct in user_weights.items():
        model_max = next((c["budget_pct"] for c in _CLUSTERS if c["id"] == cid), 17.0)
        if wpct > model_max * 1.5:
            label = next((c["label"] for c in _CLUSTERS if c["id"] == cid), cid)
            suggestions.append({
                "cluster_id": cid,
                "label": label,
                "user_pct": round(wpct, 2),
                "model_max_pct": model_max,
                "action": f"Overweight {label} at {wpct:.1f}% vs model max {model_max}%. Consider trimming.",
            })

    # Correlation breaches involving user clusters
    user_cluster_ids = set(user_weights.keys())
    labels, matrix, _ = _load_correlation_matrix()
    breaches: list[dict[str, Any]] = []
    n = len(labels)
    for i in range(n):
        for j in range(i + 1, n):
            ci, cj = labels[i], labels[j]
            if ci not in user_cluster_ids and cj not in user_cluster_ids:
                continue
            rho = matrix[i][j]
            if rho > _BREACH_RHO_WARN:
                wi = user_weights.get(ci, 0.0)
                wj = user_weights.get(cj, 0.0)
                if wi > 0 and wj > 0:
                    ci_label = next((c["label"] for c in _CLUSTERS if c["id"] == ci), ci)
                    cj_label = next((c["label"] for c in _CLUSTERS if c["id"] == cj), cj)
                    breaches.append({
                        "pair": [ci, cj],
                        "pair_labels": [ci_label, cj_label],
                        "rho": round(rho, 2),
                        "user_combined_pct": round(wi + wj, 2),
                        "recommendation": f"High correlation ({rho:.2f}) between {ci_label} and {cj_label}. Diversify.",
                    })

    return {
        "total_notional_usd": round(total_notional, 2),
        "cash_usd": cash_usd,
        "position_count": len(enriched),
        "positions": enriched,
        "cluster_weights": [
            {"cluster_id": cid, "pct": round(pct, 2)} for cid, pct in sorted(user_weights.items(), key=lambda x: -x[1])
        ],
        "concentration_warnings": suggestions,
        "correlation_breaches": breaches,
    }


def _fetch_price_safe(symbol: str) -> float | None:
    """Try to find today_price for symbol from open VT positions; fallback to yfinance."""
    try:
        long_df = _load_vt("long")
        short_df = _load_vt("short")
        for df in (long_df, short_df):
            if not df.empty and "Symbol" in df.columns and "Today price" in df.columns:
                match = df[df["Symbol"].astype(str).str.upper() == symbol]
                if not match.empty:
                    val = match.iloc[0]["Today price"]
                    p = _safe_float(val)
                    if p and p > 0:
                        return p
    except Exception:
        pass
    try:
        import yfinance as yf  # type: ignore
        t = yf.Ticker(symbol)
        info = t.fast_info
        price = getattr(info, "last_price", None)
        return float(price) if price else None
    except Exception:
        return None


def search_tickers(q: str, limit: int = 20) -> list[dict[str, Any]]:
    """Ticker autocomplete from VT book, conviction universe, and conviction store."""
    q_upper = q.upper().strip()
    results: dict[str, dict[str, Any]] = {}
    name_cache = _load_ticker_names_cache()

    def _add(sym: str, source: str) -> None:
        sym = sym.upper().strip()
        if not sym or sym in results:
            return
        if q_upper not in sym:
            return
        results[sym] = {
            "symbol": sym,
            "name": name_cache.get(sym, sym),
            "source": source,
        }

    for side in ("long", "short"):
        df = _load_vt(side)
        if not df.empty and "Symbol" in df.columns:
            for sym in df["Symbol"].astype(str).str.upper().unique():
                _add(sym, "vt_book")

    if CONVICTION_UNIVERSE_FILE.exists():
        for line in CONVICTION_UNIVERSE_FILE.read_text().splitlines():
            _add(line.strip(), "conviction_universe")

    try:
        from src.conviction_engine.store import list_records

        for rec in list_records():
            _add(str(rec.get("ticker") or ""), "conviction_store")
    except Exception:
        pass

    sorted_results = sorted(
        results.values(),
        key=lambda x: (not x["symbol"].startswith(q_upper), x["symbol"]),
    )
    return sorted_results[:limit]
