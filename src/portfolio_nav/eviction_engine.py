"""1C admission/eviction engine — A1/A2/A3 + D4's exit_type=eviction + D5.

Pure decision functions, no I/O — the live holdings pipeline (real-time exit classification)
and any future ledger replay share exactly one eviction rule (D7's "one source" applied to
exits, not just weights).

- **1C** (default, ``margin_m=0``): when the book is full, a challenger evicts the weakest
  held position only if ``challenger_score - weakest_score >= margin_m``.
- **A2 churn softener**: sweep ``margin_m`` in ``{0, 5, 10, 15, 20}`` — fewer marginal
  evictions as M rises. Read from ``config/portfolio_policy.yaml`` (``eviction.margin_m``),
  never hardcoded, so Ahil's sweep winner is a one-line config flip.
- **A3 F5 freeze-at-N**: admission strictly by Signal Quality Score rank into naturally-freed
  slots only — never evicts. Isolates 1C's admission effect from its eviction effect.

No historical eviction/slot-occupancy log exists anywhere in production. Rather than
fabricate one, ``portfolio_pipeline_service.run_eviction_check`` calls this module once per
day and persists decisions into ``book_snapshot_store.eviction_log`` — exact, going forward,
from the day it first runs (see book_snapshot_store.py's module docstring).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Candidate:
    """One live or candidate signal — minimal shape eviction decisions need."""

    key: tuple[str, str, str, str]  # (ticker, function, interval, direction)
    ticker: str
    score: float | None


@dataclass(frozen=True)
class EvictionPair:
    """One eviction event — the weakest holding removed and the challenger that displaced it."""

    evicted: Candidate
    challenger: Candidate
    margin: float | None


@dataclass
class EvictionDecision:
    evicted: list[Candidate] = field(default_factory=list)
    evictions: list[EvictionPair] = field(default_factory=list)
    admitted: list[Candidate] = field(default_factory=list)
    waiting: list[Candidate] = field(default_factory=list)
    mode: str = "1c"
    margin_m: float = 0.0


def _sort_key(c: Candidate) -> tuple[bool, float]:
    return (c.score is None, c.score if c.score is not None else -1e9)


def decide_admissions(
    *,
    held: list[Candidate],
    candidates: list[Candidate],
    n_max: int,
    margin_m: float = 0.0,
    freeze_at_n: bool = False,
) -> EvictionDecision:
    """Run one day's admission/eviction pass.

    ``held``: currently-open positions (already admitted).
    ``candidates``: today's new entry signals competing for slots.
    Returns which candidates get admitted, which held positions get evicted to make room
    (empty when ``freeze_at_n``), and which candidates wait.

    Pure function — no config/policy lookups. Callers (e.g.
    ``api/services/portfolio_pipeline_service.py``) resolve ``margin_m`` /
    ``freeze_at_n`` from ``api/services/policy_service.py`` and pass them in explicitly.
    """
    m = margin_m
    freeze = freeze_at_n

    current_held = sorted(held, key=_sort_key)  # ascending — weakest first
    ranked_candidates = sorted(candidates, key=_sort_key, reverse=True)  # strongest first

    result = EvictionDecision(mode="f5_freeze" if freeze else "1c", margin_m=m)

    for cand in ranked_candidates:
        if len(current_held) < n_max:
            result.admitted.append(cand)
            current_held.append(cand)
            current_held.sort(key=_sort_key)
            continue

        if freeze:
            result.waiting.append(cand)
            continue

        weakest = current_held[0]
        challenger_score = cand.score if cand.score is not None else -1e9
        weakest_score = weakest.score if weakest.score is not None else -1e9
        if challenger_score - weakest_score >= m:
            result.evicted.append(weakest)
            result.evictions.append(EvictionPair(
                evicted=weakest, challenger=cand,
                margin=eviction_margin(cand.score, weakest.score),
            ))
            result.admitted.append(cand)
            current_held = current_held[1:] + [cand]
            current_held.sort(key=_sort_key)
        else:
            result.waiting.append(cand)

    return result


def eviction_margin(challenger_score: float | None, weakest_score: float | None) -> float | None:
    """challenger_score - weakest_score — the figure A2's churn softener gates on."""
    if challenger_score is None or weakest_score is None:
        return None
    return round(challenger_score - weakest_score, 2)
