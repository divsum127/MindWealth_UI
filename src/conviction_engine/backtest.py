"""Helpers for comparing historical signal reports with a forward snapshot (MTM backtest)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd

from ..utils.file_discovery import extract_date_from_filename
from .signals import COMPOUND_SIGNAL_COLUMN, TODAY_PRICE_COLUMN, load_signal_file

MTM_COLUMN = "Current Mark to Market and Holding Period"


def build_signal_key(row: pd.Series) -> str:
    """Stable key for matching rows across two exports of the same report type."""
    fn = str(row.get("Function") or "").strip()
    raw = row.get(COMPOUND_SIGNAL_COLUMN)
    text = str(raw or "").strip()
    return f"{fn}|{text}"


def parse_mtm_first_pct(value: Any) -> float | None:
    """Parse leading percent from '4.55%, 15 days' style fields."""
    text = str(value or "").strip()
    if not text or text.lower() == "nan":
        return None
    m = re.match(r"^\s*(-?\d+(?:\.\d+)?)\s*%", text.replace(",", ""))
    if m:
        return float(m.group(1))
    return None


def parse_vs_signal_pct(value: Any) -> float | None:
    """Parse signed % vs signal from '..., 4.55% above' / '2.4% below'."""
    text = str(value or "").strip()
    if not text or text.lower() == "nan":
        return None
    matches = re.findall(r"(-?\d+(?:\.\d+)?)\s*%", text.replace(",", ""))
    if not matches:
        return None
    val = float(matches[-1])
    if re.search(r"\bbelow\b", text, re.I):
        val = -abs(val)
    elif re.search(r"\babove\b", text, re.I):
        val = abs(val)
    return val


def find_report_csv(trade_store_dir: Path, base_filename: str, report_date: str) -> Path | None:
    """Return path to YYYY-MM-DD_<base_filename> if it exists."""
    candidate = trade_store_dir / f"{report_date}_{base_filename}"
    if candidate.exists():
        return candidate
    return None


def latest_matching_report(trade_store_dir: Path, base_filename: str) -> Path | None:
    """Newest dated CSV for base_filename (e.g. outstanding_signal.csv)."""
    best: Path | None = None
    best_dt = None
    for p in trade_store_dir.glob(f"*_{base_filename}"):
        dt = extract_date_from_filename(p.name)
        if dt is None:
            continue
        if best_dt is None or dt > best_dt:
            best_dt = dt
            best = p
    return best


def add_signal_keys(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["_signal_key"] = out.apply(build_signal_key, axis=1)
    return out


def merge_signal_reports(
    historical: pd.DataFrame,
    forward: pd.DataFrame,
) -> pd.DataFrame:
    """Left-join historical rows to forward MTM columns on _signal_key."""
    h = add_signal_keys(historical)
    f = add_signal_keys(forward)
    rename = {
        TODAY_PRICE_COLUMN: "_fwd_today_price_text",
        MTM_COLUMN: "_fwd_mtm_text",
    }
    sub = f[["_signal_key"] + [c for c in rename if c in f.columns]].copy()
    for old, new in rename.items():
        if old in sub.columns:
            sub = sub.rename(columns={old: new})
    merged = h.merge(sub, on="_signal_key", how="left", indicator="_merge_forward")
    return merged


def extract_outcome_columns(merged: pd.DataFrame) -> pd.DataFrame:
    """Add parsed MTM / vs-signal columns from historical and forward text fields."""
    out = merged.copy()
    if TODAY_PRICE_COLUMN in out.columns:
        out["vs_signal_pct_hist"] = out[TODAY_PRICE_COLUMN].map(parse_vs_signal_pct)
    else:
        out["vs_signal_pct_hist"] = None
    if MTM_COLUMN in out.columns:
        out["mtm_pct_hist"] = out[MTM_COLUMN].map(parse_mtm_first_pct)
    else:
        out["mtm_pct_hist"] = None

    if "_fwd_today_price_text" in out.columns:
        out["vs_signal_pct_fwd"] = out["_fwd_today_price_text"].map(parse_vs_signal_pct)
    else:
        out["vs_signal_pct_fwd"] = None
    if "_fwd_mtm_text" in out.columns:
        out["mtm_pct_fwd"] = out["_fwd_mtm_text"].map(parse_mtm_first_pct)
    else:
        out["mtm_pct_fwd"] = None

    vh = pd.to_numeric(out["vs_signal_pct_hist"], errors="coerce")
    vf = pd.to_numeric(out["vs_signal_pct_fwd"], errors="coerce")
    out["vs_signal_delta"] = vf - vh
    return out


def bucket_conviction(score: Any) -> str:
    if score is None or (isinstance(score, float) and pd.isna(score)):
        return "NA"
    try:
        s = float(score)
    except (TypeError, ValueError):
        return "NA"
    if s < 0:
        return "<0"
    if s < 2:
        return "[0,2)"
    if s < 5:
        return "[2,5)"
    return ">=5"


def summarize_buckets(df: pd.DataFrame, conviction_col: str = "conviction_raw", outcome_col: str = "vs_signal_pct_fwd") -> pd.DataFrame:
    """Mean / count / win-rate (vs_signal > 0) by conviction bucket for BUY equities only."""
    work = df.copy()
    if conviction_col not in work.columns:
        raise ValueError(f"Missing {conviction_col}")
    if outcome_col not in work.columns:
        raise ValueError(f"Missing {outcome_col}")
    work["_bucket"] = work[conviction_col].map(bucket_conviction)
    work[outcome_col] = pd.to_numeric(work[outcome_col], errors="coerce")

    rows: list[dict[str, Any]] = []
    for name, grp in work.groupby("_bucket", dropna=False):
        oc = grp[outcome_col].dropna()
        if oc.empty:
            rows.append({"bucket": str(name), "n": len(grp), "n_with_outcome": 0, "mean_outcome": None, "win_rate": None})
            continue
        win = (oc > 0).mean()
        rows.append(
            {
                "bucket": str(name),
                "n": int(len(grp)),
                "n_with_outcome": int(oc.shape[0]),
                "mean_outcome": round(float(oc.mean()), 4),
                "median_outcome": round(float(oc.median()), 4),
                "win_rate": round(float(win), 4),
            }
        )
    return pd.DataFrame(rows)


def run_row_overlay(df: pd.DataFrame, store_dir: Path | None, source_file: Path | None) -> pd.DataFrame:
    """Apply conviction overlay per row (uses current store records; see docs)."""
    from .engine import apply_to_signal

    overlays: list[dict[str, Any]] = []
    for idx, row in df.iterrows():
        mod = apply_to_signal(row, store_dir=store_dir, persist=False, update_layers=False)
        mod["_row_idx"] = idx
        overlays.append(mod)
    return pd.DataFrame(overlays)


def correlation_conviction_outcome(
    df: pd.DataFrame,
    conviction_col: str = "conviction_raw",
    outcome_col: str = "vs_signal_pct_fwd",
) -> dict[str, Any]:
    """Pearson / Spearman correlation when both columns numeric; min n=3."""
    if conviction_col not in df.columns or outcome_col not in df.columns:
        return {"n": 0, "pearson": None, "spearman": None}
    sub = df[[conviction_col, outcome_col]].copy()
    sub[conviction_col] = pd.to_numeric(sub[conviction_col], errors="coerce")
    sub[outcome_col] = pd.to_numeric(sub[outcome_col], errors="coerce")
    sub = sub.dropna()
    n = int(sub.shape[0])
    if n < 3:
        return {"n": n, "pearson": None, "spearman": None}
    return {
        "n": n,
        "pearson": round(float(sub[conviction_col].corr(sub[outcome_col])), 6),
        "spearman": round(float(sub[conviction_col].rank().corr(sub[outcome_col].rank())), 6),
    }


def backtest_from_paths(
    historical_path: Path,
    forward_path: Path,
    store_dir: Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load two snapshots, merge, attach conviction from current store, return (detail_df, summary_df).

    detail_df includes conviction columns and forward `vs_signal_pct_fwd` where matched.
    """
    hist = load_signal_file(historical_path)
    fwd = load_signal_file(forward_path)
    if hist.empty or fwd.empty:
        return pd.DataFrame(), pd.DataFrame()

    merged = merge_signal_reports(hist, fwd)
    merged = extract_outcome_columns(merged)

    overlay_rows: list[dict[str, Any]] = []
    from .engine import apply_to_signal

    for idx, row in merged.iterrows():
        hist_row = row[[c for c in hist.columns if c in row.index]].copy()
        hist_row = hist_row.dropna(how="all")
        mod = apply_to_signal(hist_row, store_dir=store_dir, persist=False, update_layers=False)
        overlay_rows.append(mod)

    ov = pd.DataFrame(overlay_rows)
    detail = pd.concat([merged.reset_index(drop=True), ov.reset_index(drop=True)], axis=1)

    eq = detail[detail["asset_type"].astype(str).str.upper() == "EQUITY"].copy()
    eq_buy = eq[eq["original_signal"].astype(str).str.upper() == "BUY"].copy()
    eq_buy_matched = eq_buy[eq_buy["_merge_forward"] == "both"].copy()
    if eq_buy_matched.empty or "vs_signal_pct_fwd" not in eq_buy_matched.columns:
        summary = pd.DataFrame()
    else:
        summary = summarize_buckets(eq_buy_matched, conviction_col="conviction_raw", outcome_col="vs_signal_pct_fwd")
    return detail, summary
