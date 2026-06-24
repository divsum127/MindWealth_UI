"""
Signal enrichment service — computes surface / quality fields for API responses.

Reads pre-computed CSV columns (er, signal_alpha, composite_score, asset_class, timeliness_score)
and adds supplementary fields that are NOT persisted to CSV by the nightly pipeline:
    window_remaining_pct, tier, exit_fired, alpha_interpretation,
    er_annualized, signal_alpha_annualized, mtm_pct, days_elapsed, avg_hold_days.

All math is pure Python. No Dash / Plotly dependency.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd

from src.config_paths import CONVICTION_DAILY_DIR

# ── Constants mirrored from claude_lateness_metrics.py (v4 calibrated) ────────

TRADING_DAYS_PER_YEAR = 252

# Tier gate thresholds (Supplementary §1)
_TIER_A_COMPOSITE = 40.0
_TIER_A_WINDOW = 30.0
_TIER_A_RR = 1.0
_TIER_A_FWD_WR = 60.0
_BEST_COMPOSITE = 20.0
_BEST_WINDOW = 15.0

# Alpha interpretation thresholds
_AI_FAIL_THRESHOLD = -15.0
_AI_WARN_THRESHOLD = -5.0
_AI_PASSIVE_ALPHA_MIN = 1.0


# ── Field parsers ──────────────────────────────────────────────────────────────

def _parse_float(val: Any, strip_chars: str = "%") -> float | None:
    if val is None:
        return None
    s = str(val).strip()
    if s in ("", "N/A", "nan", "None", "—"):
        return None
    for ch in strip_chars:
        s = s.replace(ch, "")
    s = s.strip()
    try:
        return float(s)
    except ValueError:
        return None


def _parse_hold_days_from_str(raw: str) -> int | None:
    """Parse average hold days from 'Max/Min/Avg' formatted string."""
    if not raw or str(raw).strip() in ("", "N/A", "nan"):
        return None
    parts = str(raw).strip().split("/")
    avg_str = parts[-1].strip() if len(parts) >= 1 else ""
    return _extract_days(avg_str)


def _extract_days(s: str) -> int | None:
    """Convert formatted day string ('20 days', '2.0 months', '1 year', '20') → int days."""
    try:
        cleaned = str(s).strip()
        match = re.search(r"(\d+\.?\d*)", cleaned)
        if not match:
            return None
        val = float(match.group(1))
        lower = cleaned.lower()
        if "year" in lower:
            return int(val * 360)
        if "month" in lower:
            return int(val * 30)
        return int(val)
    except Exception:
        return None


def _parse_days_elapsed(raw: Any) -> int | None:
    """Parse 'Trading Days between Signal and Today Date' field → int."""
    if raw is None:
        return None
    text = str(raw).strip().lower().replace("days", "").strip()
    try:
        return int(float(text))
    except ValueError:
        return None


def _parse_mtm_pct(raw: Any) -> float | None:
    """Parse 'Current Mark to Market and Holding Period' → MTM % float."""
    if raw is None:
        return None
    text = str(raw).strip()
    match = re.search(r"([+\-]?\d+\.?\d*)\s*%", text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def _parse_fwd_wr(raw: Any) -> float | None:
    """Parse forward test win rate field → float."""
    if raw is None:
        return None
    parts = str(raw).split("/")
    try:
        return float(parts[0].strip().rstrip("%").strip())
    except (ValueError, IndexError):
        return None


def _is_exit_fired(row: dict[str, Any]) -> bool:
    """True when Exit Signal column contains a real date/price (not empty/N/A)."""
    val = str(row.get("Exit Signal Date/Price[$]", "") or "").strip()
    return bool(val) and val not in ("", "N/A", "No Exit Yet", "nan", "None")


def _parse_signal_alpha(row: dict[str, Any]) -> float | None:
    """Read pre-computed Signal Alpha Per Trade [%] from CSV row."""
    return _parse_float(row.get("Signal Alpha Per Trade [%]"))


def _parse_cagr_diff(row: dict[str, Any]) -> float | None:
    """Parse CAGR difference (Strategy - Buy and Hold) [%]."""
    raw = row.get("CAGR difference (Strategy - Buy and Hold) [%]", "")
    return _parse_float(raw)


def _parse_bh_cagr(row: dict[str, Any]) -> float | None:
    """Parse B&H CAGR [%]."""
    return _parse_float(row.get("CAGR of Buy and Hold [%]"))


def _get_direction(row: dict[str, Any]) -> str:
    """Return 'Long' or 'Short' from symbol field."""
    symbol_field = str(row.get("Symbol, Signal, Signal Date/Price[$]", ""))
    parts = symbol_field.split(",")
    if len(parts) >= 2:
        direction = parts[1].strip().lower()
        if direction in ("short", "s"):
            return "Short"
    return "Long"


def _parse_rr_static(row: dict[str, Any]) -> float | None:
    return _parse_float(row.get("R:R Static"))


def _annualize(per_trade_pct: float | None, hold_days: int | None) -> float | None:
    """Annualize a per-trade return: val × 252 / hold_days."""
    if per_trade_pct is None or hold_days is None or hold_days <= 0:
        return None
    result = per_trade_pct * TRADING_DAYS_PER_YEAR / hold_days
    return round(result, 4)


# ── Alpha interpretation (mirrors claude_lateness_metrics logic) ───────────────

def _compute_alpha_interpretation(
    signal_alpha: float | None,
    cagr_diff: float | None,
    direction: str,
    bt_bh_cagr: float | None = None,
) -> dict[str, str] | None:
    """Return alpha interpretation object or None when no issue."""
    if cagr_diff is None or cagr_diff >= 0:
        return None
    is_short = direction.upper().startswith("SHORT") or direction.upper() == "S"
    benchmark = "cash (IRX)" if is_short else "B&H"
    if cagr_diff < _AI_FAIL_THRESHOLD:
        return {
            "type": "fail",
            "label": "A2d FAIL",
            "detail": (
                f"Strategy underperforms {benchmark} by {abs(cagr_diff):.1f}%/yr. "
                "Hard disqualifier."
            ),
        }
    if cagr_diff < _AI_WARN_THRESHOLD:
        if is_short:
            return {
                "type": "warn",
                "label": "better held as cash",
                "detail": (
                    f"Short signal underperforms {benchmark} by {abs(cagr_diff):.1f}%/yr. "
                    "Short not justified vs cash alternative."
                ),
            }
        if signal_alpha is not None and signal_alpha > _AI_PASSIVE_ALPHA_MIN:
            return {
                "type": "warn",
                "label": "passive hold preferred",
                "detail": (
                    f"Signal alpha positive but stepping out between signals costs "
                    f"{abs(cagr_diff):.1f}%/yr vs {benchmark}."
                ),
            }
        return {
            "type": "warn",
            "label": "avoid this combo",
            "detail": (
                f"Strategy underperforms {benchmark} by {abs(cagr_diff):.1f}%/yr. "
                "Avoid this signal/asset combination."
            ),
        }
    # -5 <= cagr_diff < 0
    return {
        "type": "info",
        "label": "mild timing cost",
        "detail": (
            f"Mild CAGR lag vs {benchmark} ({cagr_diff:.1f}%/yr). "
            "Minor cash-gap effect; acceptable."
        ),
    }


# ── Tier computation (mirrors Supplementary §1 gate logic) ────────────────────

def _compute_tier(
    composite_score: float | None,
    window_remaining_pct: float | None,
    alpha_interp: dict | None,
    rr_static: float | None,
    fwd_wr: float | None,
    exit_fired: bool,
) -> str:
    if exit_fired:
        return "exit"
    ai_type = (alpha_interp or {}).get("type")
    if (
        composite_score is not None
        and composite_score > _TIER_A_COMPOSITE
        and window_remaining_pct is not None
        and window_remaining_pct > _TIER_A_WINDOW
        and ai_type != "fail"
        and rr_static is not None
        and rr_static >= _TIER_A_RR
        and fwd_wr is not None
        and fwd_wr >= _TIER_A_FWD_WR
    ):
        return "tA"
    if (
        composite_score is not None
        and composite_score > _BEST_COMPOSITE
        and window_remaining_pct is not None
        and window_remaining_pct > _BEST_WINDOW
        and ai_type != "fail"
    ):
        return "best"
    return "tierc"


# ── Conviction overlay merge ───────────────────────────────────────────────────

def _build_conviction_index() -> dict[tuple[str, str, str, str], dict[str, Any]]:
    """Load latest conviction overlay and index by (symbol, function, interval, direction)."""
    today = pd.Timestamp.today().strftime("%Y-%m-%d")
    conviction_dir = Path(CONVICTION_DAILY_DIR)
    patterns = [
        conviction_dir / today / f"{today}_outstanding_signal_conviction.csv",
        conviction_dir / today / f"{today}_all_signal_conviction.csv",
        conviction_dir / today / f"{today}_new_signal_conviction.csv",
    ]
    # walk back up to 30 days if today's conviction data not available
    for offset in range(30):
        check_date = (pd.Timestamp.today() - pd.Timedelta(days=offset)).strftime("%Y-%m-%d")
        for pattern in patterns:
            path = conviction_dir / check_date / str(pattern.name).replace(today, check_date)
            if path.exists() and path.stat().st_size > 0:
                try:
                    df = pd.read_csv(path)
                    idx: dict[tuple[str, str, str, str], dict[str, Any]] = {}
                    for _, row in df.iterrows():
                        row_dict = row.to_dict()
                        sym_field = str(row_dict.get("Symbol, Signal, Signal Date/Price[$]", ""))
                        parts = sym_field.split(",")
                        sym = parts[0].strip() if parts else ""
                        fn = str(row_dict.get("Function", "")).strip()
                        interval_field = str(row_dict.get("Interval, Confirmation Status", ""))
                        interval = interval_field.split(",")[0].strip() if interval_field else ""
                        direction = parts[1].strip() if len(parts) >= 2 else "Long"
                        key = (sym.upper(), fn.upper(), interval.upper(), direction.upper())
                        idx[key] = row_dict
                    if idx:
                        return idx
                except Exception:
                    continue
    return {}


_CONVICTION_CACHE: dict[str, Any] = {"date": None, "data": {}}


def _get_conviction(symbol: str, function: str, interval: str, direction: str) -> dict[str, Any]:
    """Return conviction fields for this signal (cached per calendar day)."""
    today = pd.Timestamp.today().strftime("%Y-%m-%d")
    if _CONVICTION_CACHE["date"] != today:
        _CONVICTION_CACHE["date"] = today
        _CONVICTION_CACHE["data"] = _build_conviction_index()
    key = (symbol.upper(), function.upper(), interval.upper(), direction.upper())
    return _CONVICTION_CACHE["data"].get(key, {})


# ── Core MindWealth enrichment fallback (all_signal CSV lacks MasterSpec cols) ─

def _masterspec_precomputed(row: dict[str, Any]) -> bool:
    """True when nightly pipeline already wrote composite / E[R] columns."""
    return (
        _parse_float(row.get("Signal Quality Composite Score")) is not None
        or _parse_float(row.get("composite_score")) is not None
    )


def _get_enrich_signal_dict():
    """Lazy import of MindWealth enrich_signal_dict (no Dash/Plotly dep)."""
    import sys

    from src.config_paths import MINDWEALTH_ROOT

    root = str(MINDWEALTH_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    from helper_functions.claude_lateness_metrics import enrich_signal_dict

    return enrich_signal_dict


def _build_exit_lookup(records: list[dict[str, Any]]) -> Any:
    import sys

    from src.config_paths import MINDWEALTH_ROOT

    root = str(MINDWEALTH_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    from helper_functions.claude_lateness_metrics import build_exit_lookup

    return build_exit_lookup(records)


def _apply_core_enrichment(
    row: dict[str, Any],
    exit_lookup: Any = None,
) -> dict[str, Any]:
    """Run full MasterSpec math when CSV rows lack pre-computed quality columns."""
    row_copy = dict(row)
    sym_field = row_copy.get("Symbol, Signal, Signal Date/Price[$]", "")
    if sym_field and not row_copy.get("Symbol"):
        row_copy["Symbol"] = str(sym_field).split(",")[0].strip()
    return _get_enrich_signal_dict()(row_copy, exit_lookup=exit_lookup)


# ── Main enrichment function ───────────────────────────────────────────────────

def enrich_record(
    row: dict[str, Any],
    exit_lookup: Any = None,
) -> dict[str, Any]:
    """
    Compute all surface/quality fields for one signal CSV row dict.

    Returns a dict with:
    - All original CSV fields preserved
    - Supplementary fields injected/computed:
        window_remaining_pct, tier, exit_fired, alpha_interpretation,
        er_annualized, signal_alpha_annualized, mtm_pct, days_elapsed, avg_hold_days,
        composite_score (from CSV, renamed), conviction_bq_score, conviction_fs_class
    """
    out = dict(row)

    # ── Parse hold days (all trades → win trades fallback) ─────────────────────
    all_trades_hold = _parse_hold_days_from_str(
        str(row.get("Backtested Holding Period (All Trades) (days) (Max/Min/Avg)", "") or "")
    )
    win_trades_hold = _parse_hold_days_from_str(
        str(row.get("Backtested Holding Period(Win Trades) (days) (Max/Min/Avg)", "") or "")
    )
    avg_hold_days = all_trades_hold if all_trades_hold is not None else win_trades_hold

    # ── Days elapsed ────────────────────────────────────────────────────────────
    days_elapsed = _parse_days_elapsed(row.get("Trading Days between Signal and Today Date"))

    # ── Core fallback for reports without MasterSpec columns (e.g. all_signal) ─
    core: dict[str, Any] = {}
    if not _masterspec_precomputed(row):
        try:
            core = _apply_core_enrichment(row, exit_lookup=exit_lookup)
        except Exception:
            core = {}

    if core.get("avg_hold_days") is not None:
        avg_hold_days = core["avg_hold_days"]
    if core.get("days_elapsed") is not None:
        days_elapsed = core["days_elapsed"]

    # ── Window remaining % ──────────────────────────────────────────────────────
    window_remaining_pct: float | None = core.get("window_remaining_pct")
    if window_remaining_pct is None:
        if avg_hold_days is not None and avg_hold_days > 0 and days_elapsed is not None:
            window_remaining_pct = round(
                (avg_hold_days - days_elapsed) / avg_hold_days * 100, 2
            )

    # ── Pre-computed fields (from nightly pipeline or core fallback) ───────────
    er = _parse_float(row.get("Expected Return E[R] [%]")) or core.get("er")
    signal_alpha = _parse_signal_alpha(row) or core.get("signal_alpha_per_trade")
    composite_score_raw = (
        _parse_float(row.get("Signal Quality Composite Score"))
        or _parse_float(row.get("composite_score"))
        or core.get("composite_score")
    )
    timeliness_score = _parse_float(row.get("Timeliness Score")) or core.get("timeliness_score")
    asset_class = (
        str(row.get("Asset Class", "") or core.get("asset_class") or "").strip()
        or "equity"
    )

    # ── Annualized fields ───────────────────────────────────────────────────────
    er_annualized = core.get("er_annualized") or _annualize(er, avg_hold_days)
    signal_alpha_annualized = core.get("signal_alpha_annualized") or _annualize(
        signal_alpha, avg_hold_days
    )

    # ── MTM % ───────────────────────────────────────────────────────────────────
    mtm_pct = _parse_mtm_pct(row.get("Current Mark to Market and Holding Period"))

    # ── Exit fired ──────────────────────────────────────────────────────────────
    exit_fired = core.get("exit_fired") if "exit_fired" in core else _is_exit_fired(row)

    # ── Alpha interpretation ────────────────────────────────────────────────────
    direction = _get_direction(row)
    cagr_diff = _parse_cagr_diff(row) or core.get("cagr_diff")
    bt_bh_cagr = _parse_bh_cagr(row)
    alpha_interpretation = core.get("alpha_interpretation")
    if alpha_interpretation is None:
        alpha_interpretation = _compute_alpha_interpretation(
            signal_alpha, cagr_diff, direction, bt_bh_cagr
        )

    # ── Tier ────────────────────────────────────────────────────────────────────
    rr_static = _parse_rr_static(row) or core.get("rr_static")
    fwd_wr_raw = row.get(
        "Forward Testing Win Rate[%]/No. of Analysed Trades/Avg Holding Period "
        "(days) (Across ALL Assets)"
    )
    fwd_wr = _parse_fwd_wr(fwd_wr_raw)
    tier = core.get("tier") or _compute_tier(
        composite_score_raw, window_remaining_pct,
        alpha_interpretation, rr_static, fwd_wr, exit_fired,
    )

    # ── Parse symbol / function / interval for conviction lookup ────────────────
    sym_field = str(row.get("Symbol, Signal, Signal Date/Price[$]", ""))
    sym_parts = sym_field.split(",")
    symbol = sym_parts[0].strip()
    function = str(row.get("Function", "")).strip()
    interval_field = str(row.get("Interval, Confirmation Status", ""))
    interval = interval_field.split(",")[0].strip() if interval_field else ""

    # ── Conviction overlay ──────────────────────────────────────────────────────
    conviction = _get_conviction(symbol, function, interval, direction)
    conviction_score = _parse_float(conviction.get("conviction_score"))
    conviction_bq_score = _parse_float(conviction.get("bq_raw"))
    conviction_fs_class = conviction.get("fs_class") or None

    # ── Write supplementary fields into output ──────────────────────────────────
    out.update(
        {
            "avg_hold_days": avg_hold_days,
            "days_elapsed": days_elapsed,
            "window_remaining_pct": window_remaining_pct,
            "er_annualized": er_annualized,
            "signal_alpha_annualized": signal_alpha_annualized,
            "mtm_pct": mtm_pct,
            "exit_fired": exit_fired,
            "alpha_interpretation": alpha_interpretation,
            "tier": tier,
            "direction": direction,
            "symbol": symbol,
            "asset_class": asset_class,
            # Normalized names for frontend alias lookup
            "composite_score": composite_score_raw,
            "timeliness_score": timeliness_score,
            "er": er,
            "signal_alpha": signal_alpha,
            "rr_static": rr_static,
            "fwd_wr": fwd_wr,
            "cagr_diff": cagr_diff,
            "conviction_score": conviction_score,
            "conviction_bq_score": conviction_bq_score,
            "conviction_fs_class": conviction_fs_class,
        }
    )
    return out


def enrich_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Enrich a list of signal CSV-row dicts with supplementary surface fields."""
    if not records:
        return []
    exit_lookup = None
    if any(not _masterspec_precomputed(r) for r in records):
        try:
            exit_lookup = _build_exit_lookup(records)
        except Exception:
            exit_lookup = None
    return [enrich_record(r, exit_lookup=exit_lookup) for r in records]


# ── Summary helpers ────────────────────────────────────────────────────────────

def compute_signal_summary(enriched_records: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute sidebar KPI counts from enriched records."""
    total = len(enriched_records)
    long_count = sum(1 for r in enriched_records if r.get("direction", "Long") == "Long")
    short_count = total - long_count
    tier_counts: dict[str, int] = {}
    function_counts: dict[str, int] = {}
    exited = 0
    for r in enriched_records:
        t = r.get("tier", "tierc")
        tier_counts[t] = tier_counts.get(t, 0) + 1
        fn = r.get("Function") or r.get("function", "Unknown")
        function_counts[fn] = function_counts.get(fn, 0) + 1
        if r.get("exit_fired"):
            exited += 1
    return {
        "total": total,
        "long": long_count,
        "short": short_count,
        "exited": exited,
        "tier_counts": tier_counts,
        "function_counts": function_counts,
    }
