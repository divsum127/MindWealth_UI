"""Join shadow v2 regime labels onto combo fire records for Part H discovery."""

from __future__ import annotations

import json
from typing import Any

from src.macro_intelligence.db.connection import get_connection

REGIME_DIM_KEYS = ("fed_cycle", "curve_regime", "val_regime", "geo_overlay", "liquidity")


def normalize_v2_regime(v2: dict[str, Any]) -> dict[str, Any]:
    """Map macro_regime_log_v2 JSON to discovery pipeline dimension keys."""
    out: dict[str, Any] = {
        "fed_cycle": str(v2.get("fed_cycle_v2") or v2.get("fed_cycle_legacy") or ""),
        "curve_regime": str(v2.get("curve_regime_v2") or v2.get("curve_regime_legacy") or ""),
        "val_regime": str(v2.get("val_regime") or ""),
        "geo_overlay": str(v2.get("geo_overlay_v2") or v2.get("geo_overlay") or ""),
        "liquidity": str(v2.get("liquidity_v2") or v2.get("liquidity_legacy") or ""),
        "fed_cycle_v2": v2.get("fed_cycle_v2"),
        "fed_cycle_legacy": v2.get("fed_cycle_legacy"),
        "curve_regime_v2": v2.get("curve_regime_v2"),
        "curve_regime_legacy": v2.get("curve_regime_legacy"),
        "liquidity_v2": v2.get("liquidity_v2"),
        "geo_overlay_v2": v2.get("geo_overlay_v2"),
        "regime_source": "v2_shadow",
    }
    return out


def load_v2_regime_index() -> dict[str, dict[str, Any]]:
    """date -> normalized v2 regime dict."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT date, regime_json FROM macro_regime_log_v2 ORDER BY date"
        ).fetchall()
    index: dict[str, dict[str, Any]] = {}
    for row in rows:
        try:
            raw = json.loads(row["regime_json"])
        except json.JSONDecodeError:
            continue
        index[str(row["date"])] = normalize_v2_regime(raw)
    return index


def lookup_v2_regime(index: dict[str, dict[str, Any]], date: str) -> dict[str, Any] | None:
    """Exact Friday match, else nearest prior v2 date."""
    if date in index:
        return index[date]
    prior = [d for d in index if d <= date]
    if not prior:
        return None
    return index[max(prior)]


def merge_regime(existing: dict[str, Any] | None, v2_norm: dict[str, Any]) -> dict[str, Any]:
    """V2 dims overwrite; preserve combo-specific keys (confirmed_legs, episode_start, etc.)."""
    merged = dict(v2_norm)
    if existing:
        for key, val in existing.items():
            if key in REGIME_DIM_KEYS:
                continue
            merged[key] = val
    return merged


def enrich_regime_dict(
    existing: dict[str, Any] | None,
    date: str,
    index: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    idx = index if index is not None else load_v2_regime_index()
    v2 = lookup_v2_regime(idx, date)
    if v2 is None:
        return dict(existing or {})
    return merge_regime(existing, v2)


def retag_combo_fires_in_db(*, generic_only: bool = False) -> dict[str, int]:
    """Persist v2 regime merge into combo_fires.macro_regime."""
    index = load_v2_regime_index()
    stats = {"updated": 0, "skipped_no_v2": 0, "total": 0}
    with get_connection() as conn:
        where = "WHERE runic_combo IS NULL" if generic_only else ""
        rows = conn.execute(
            f"SELECT combo_id, date, macro_regime FROM combo_fires {where}"
        ).fetchall()
        stats["total"] = len(rows)
        for row in rows:
            existing: dict[str, Any] = {}
            if row["macro_regime"]:
                try:
                    existing = json.loads(row["macro_regime"])
                except json.JSONDecodeError:
                    existing = {}
            merged = enrich_regime_dict(existing, str(row["date"]), index)
            if merged.get("regime_source") != "v2_shadow":
                stats["skipped_no_v2"] += 1
                continue
            conn.execute(
                "UPDATE combo_fires SET macro_regime = ? WHERE combo_id = ?",
                (json.dumps(merged), row["combo_id"]),
            )
            stats["updated"] += 1
        conn.commit()
    return stats
