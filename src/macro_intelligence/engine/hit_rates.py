"""Hit rate SQL helpers — raw and regime-adjusted."""

from __future__ import annotations

from typing import Any

from src.macro_intelligence.db.connection import get_connection


def raw_hit_rate(
    runic_combo: str,
    horizon: str = "spx_3m",
    bullish: bool = True,
) -> dict[str, Any]:
    col = horizon
    cmp = ">" if bullish else "<"
    sql = f"""
        SELECT
            CAST(SUM(CASE WHEN fr.{col} {cmp} 0 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) AS hit_rate,
            COUNT(*) AS n_obs,
            AVG(fr.{col}) AS avg_return
        FROM combo_fires cf
        JOIN forward_returns fr ON cf.combo_id = fr.combo_id
        WHERE cf.runic_combo = ?
          AND fr.{col} IS NOT NULL
    """
    with get_connection() as conn:
        row = conn.execute(sql, (runic_combo,)).fetchone()
    if not row or row["n_obs"] == 0:
        return {"hit_rate": None, "n_obs": 0, "avg_return": None}
    return {"hit_rate": row["hit_rate"], "n_obs": row["n_obs"], "avg_return": row["avg_return"]}


def regime_adjusted_hit_rate(
    runic_combo: str,
    fed_cycle_like: str = "CUT%",
    horizon: str = "spx_3m",
    bullish: bool = True,
) -> dict[str, Any]:
    col = horizon
    cmp = ">" if bullish else "<"
    sql = f"""
        SELECT
            CAST(SUM(CASE WHEN fr.{col} {cmp} 0 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) AS hit_rate,
            COUNT(*) AS n_obs,
            AVG(fr.{col}) AS avg_return
        FROM combo_fires cf
        JOIN forward_returns fr ON cf.combo_id = fr.combo_id
        WHERE cf.runic_combo = ?
          AND fr.{col} IS NOT NULL
          AND json_extract(cf.macro_regime, '$.fed_cycle') LIKE ?
    """
    with get_connection() as conn:
        row = conn.execute(sql, (runic_combo, fed_cycle_like)).fetchone()
    if not row or row["n_obs"] == 0:
        return {"hit_rate": None, "n_obs": 0, "avg_return": None}
    return {"hit_rate": row["hit_rate"], "n_obs": row["n_obs"], "avg_return": row["avg_return"]}
