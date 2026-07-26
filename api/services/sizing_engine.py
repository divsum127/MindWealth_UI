"""D1 — sizing engine retirement into the portfolio method.

Implements 15July_imp_spec_additions.md D1: the portfolio method becomes the only producer
of a signal's size — ``size = NAV/N × Conviction multiplier × SSI ceiling scalar`` for
single-name equities, with sleeve ceilings enforced as **admission slots**, not independent
per-cluster percentage budgets.

Worked example (D1): $10,000,000 portfolio, N=60 → every slot is $166,667 = 1.67% of NAV.
US Tech ceiling 12% → ``floor(12 / (100/60)) = 7`` max slots. The 8th US Tech signal is never
resized or blocked to zero — it **waits** for a US Tech slot to free.

This module is additive: ``api/services/portfolio_service.py`` calls into it only when
``SIZING_ENGINE_VERSION=d1_slots`` (env or policy). The legacy cluster-percentage engine
(pre-D1) remains the default until the sleeve table and N are confirmed by Rohit (Ask 1, Ask 4
in OPEN_QUESTIONS_FOR_ROHIT.md) — see api/services/policy_service.py for the config-driven
interim defaults either path reads.

D7 (one source for weights): both Sizing & Allocation (``get_portfolio_sizer``) and Portfolio
Risk (``get_portfolio_risk``) call ``compute_d1_sizing`` — the same computed true-weight and
sleeve fields feed both pages' bars and breach math, so they can never silently drift apart.
"""

from __future__ import annotations

import math
from typing import Any

from api.services import policy_service


def max_slots_for_sleeve(ceiling_pct: float, n_slots: int) -> int:
    """floor(sleeve_ceiling_pct / (100/N)) — D1's US Tech worked example formula (Ask 4)."""
    if n_slots <= 0:
        return 0
    return math.floor(ceiling_pct * n_slots / 100.0)


def _rank_key(p: dict[str, Any]) -> tuple[float, float]:
    """Admission rank — Signal Quality Score first, then adjusted conviction share as tiebreak."""
    bq = p.get("bq")
    score = bq if bq is not None else -1e9
    return (score, p.get("rank_weight", 0.0))


def compute_d1_sizing(
    pending_by_sleeve: dict[str, list[dict[str, Any]]],
    *,
    notional: float,
    final_ceiling_pct: float,
    n_slots: int | None = None,
    sleeves: list[dict[str, Any]] | None = None,
    scenario: str = "normal",
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Admit positions into NAV/N slots under per-sleeve caps; excess signals wait.

    ``pending_by_sleeve``: sleeve_id -> list of pending dicts, each carrying at minimum
    ``row``, ``ticker``, ``bq``, ``verdict``, ``not_applicable``, ``tier_label``,
    ``adj_share`` (conviction multiplier), ``flags``, ``direction``, ``blocked``,
    ``rank_weight`` — the exact shape ``portfolio_service.get_portfolio_sizer`` Pass 1 builds.

    Returns (sleeve_map, sized_rows) shaped like the legacy cluster_map/sized_rows so callers
    can swap engines without reshaping the response.
    """
    n = n_slots if n_slots is not None else policy_service.get_n_slots()[0]
    sleeve_cfg = sleeves if sleeves is not None else policy_service.get_sleeves()
    scale = policy_service.get_sleeve_scenario_scale(scenario)
    ceiling_fraction = min(1.0, max(0.0, final_ceiling_pct / 100.0))
    slot_dollars = notional / n if n else 0.0

    sleeve_map: dict[str, dict[str, Any]] = {}
    for s in sleeve_cfg:
        scaled_ceiling = round(float(s["ceiling_pct"]) * scale, 4)
        sleeve_map[s["id"]] = {
            "id": s["id"],
            "label": s["label"],
            "budget_pct": scaled_ceiling,  # kept for backward-compat field name
            "ceiling_pct": scaled_ceiling,
            "budget_usd": round(notional * scaled_ceiling / 100),
            "slots_max": max_slots_for_sleeve(scaled_ceiling, n),
            "slots_used": 0,
            "deployed_usd": 0,
            "deployed_pct": 0.0,
            "max_pct": scaled_ceiling,
            "true_weight_pct": 0.0,
            "positions": [],
        }
    # Anything not in the configured sleeve list still needs a bucket (fallback = "other").
    for sid in pending_by_sleeve:
        if sid not in sleeve_map:
            sleeve_map[sid] = {
                "id": sid, "label": sid, "budget_pct": 0.0, "ceiling_pct": 0.0, "budget_usd": 0,
                "slots_max": 0, "slots_used": 0, "deployed_usd": 0, "deployed_pct": 0.0,
                "max_pct": 0.0, "true_weight_pct": 0.0, "positions": [],
            }

    total_slots_used = 0
    sized_rows: list[dict[str, Any]] = []
    slot_index_counter = 0

    for sleeve_id, pending in pending_by_sleeve.items():
        sleeve = sleeve_map[sleeve_id]
        # Blocked (BQ<2, non-N/A) never consumes a slot — they stay $0 rows, per A1's ledger rule.
        eligible = [p for p in pending if not p.get("blocked")]
        ranked = sorted(eligible, key=_rank_key, reverse=True)

        for p in ranked:
            waiting = False
            reason: str | None = None
            if sleeve["slots_used"] >= sleeve["slots_max"]:
                waiting, reason = True, "sleeve_full"
            elif total_slots_used >= n:
                waiting, reason = True, "portfolio_full"

            if waiting:
                allocation_usd = 0
            else:
                slot_index_counter += 1
                sleeve["slots_used"] += 1
                total_slots_used += 1
                conviction_mult = p.get("adj_share", 0.0)
                allocation_usd = round(slot_dollars * conviction_mult * ceiling_fraction)
                sleeve["deployed_usd"] += allocation_usd

            p["_d1_waiting"] = waiting
            p["_d1_wait_reason"] = reason
            p["_d1_slot_index"] = None if waiting else slot_index_counter
            p["_d1_allocation_usd"] = allocation_usd
            sized_rows.append(p)

        # Blocked rows still ride along as $0 ledger rows (never removed — A1's ledger rule).
        for p in pending:
            if p.get("blocked"):
                p["_d1_waiting"] = False
                p["_d1_wait_reason"] = None
                p["_d1_slot_index"] = None
                p["_d1_allocation_usd"] = 0
                sized_rows.append(p)

    for sleeve in sleeve_map.values():
        sleeve["deployed_pct"] = round(sleeve["deployed_usd"] / notional * 100, 4) if notional else 0.0
        sleeve["true_weight_pct"] = sleeve["deployed_pct"]
        sleeve["slots_available"] = max(0, sleeve["slots_max"] - sleeve["slots_used"])
        sleeve["full"] = sleeve["slots_used"] >= sleeve["slots_max"]

    return sleeve_map, sized_rows


def sizing_engine_version() -> str:
    """'d1_slots' | 'legacy' — which allocation engine get_portfolio_sizer uses."""
    import os

    env = os.getenv("SIZING_ENGINE_VERSION", "").strip().lower()
    if env in ("d1_slots", "legacy"):
        return env
    return "legacy"


def clamp_display_pct(value: float, *, cap: float = 100.0) -> float:
    """D3 interim guard — never let a displayed weight/bar read above ``cap``.

    D1's slot model is structurally capped by construction (slots sum <= N, each slot
    <= notional/N), so this only matters for the legacy engine while it's still the default.
    """
    return max(0.0, min(cap, value))
