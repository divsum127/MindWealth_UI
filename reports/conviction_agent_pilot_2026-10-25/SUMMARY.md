# Agent-dimension model comparison — NVDA and GOOG (2026-10-25)

Approved by Rohit on 24 Sep (msg 1a0d2e5829a0cf71): "yes approve for 2 names and yes (request
only(". Run with `scripts/conviction_agent_pilot.py`, hard USD 5 cap. Read-only: nothing was
written to `conviction_store`, so agent dimensions remain request-only.

## Cost

| Model | Calls | Spend | Per call | Full universe (136 equities × 5 dims) |
|---|---:|---:|---:|---:|
| claude-opus-5-5 | 10 | $2.66 | $0.27 | ≈ $180 per run |
| claude-sonnet-5-5 | 10 | $0.85 | $0.085 | ≈ $58 per run |
| **Total** | 20 | **$3.50** of $5.00 | | |

No refusals, no truncations; every call was served by the requested model.

## BQ points each model would add

| Dimension | NVDA Opus 5.5 | NVDA Sonnet 5.5 | GOOG Opus 5.5 | GOOG Sonnet 5.5 |
|---|---:|---:|---:|---:|
| Macro tailwind | 0 (conf capped 0.55) | **+1** (conf 0.70) | 0 (0.65) | 0 (0.55) |
| CEO quality | **+2** (9.5/10, 0.85) | **+2** (9.5/10, 0.85) | 0 (capped 0.55) | 0 (0.55) |
| Competitive moat | 0 (capped 0.55) | 0 (capped 0.55) | 0 (capped 0.55) | 0 (capped 0.55) |
| Deal delay | 0, supply-constrained | 0, supply-constrained | 0, supply-constrained | 0, supply-constrained |
| Reinvestment runway | 0 (0.80) | 0 (0.80) | 0 (0.70) | 0 (0.50) |
| **Total** | **+2** | **+3** | **0** | **0** |

The stored records had never run these dimensions ("scored 0 by absence"), so the baseline is 0.

## Findings

1. **The two models agree on 9 of 10 dimension values.** The one difference is NVDA macro
   tailwind, where Sonnet reported exactly 0.70 confidence and Opus was capped at 0.55.
2. **Both flag a supply constraint, not a deal delay, for both names** (NVDA: supply-bound
   through FY28; GOOG: compute-constrained against its cloud backlog). That is informational
   under the 1 Sep E5 rule, not a penalty, which is how the engine treats it.
3. **The confidence rules, not the model, decide the outcome.** 10 of 20 dimensions landed below
   the 0.7 bar and scored 0. In 6 of them the cause was the "opposing evidence text more than 30
   characters longer" cap, which mostly penalises the more thorough answer (Opus cited 7–11
   sources on those dimensions). The 21 Sep reply already called this cap a rough heuristic.
4. **Sonnet 5.5 is about a third of the cost** for the same answers on this sample.

## Recommendation (for Rohit, not applied)

- Model choice is his call. On this sample, Sonnet 5.5 matches Opus 5.5 on 9 of 10 values at
  about a third of the cost. The code default stays `claude-opus-5-5` until he decides;
  switching needs only `CONVICTION_AGENT_MODEL=claude-sonnet-5-5`.
- Before any wider run, review the opposing-evidence length cap: it decides more outcomes than
  the model does. Two names are too few to judge the agent dimensions' value; that still belongs
  to Ahil's live test (CE-27).

Files: `pilot_results.json` (full model answers with sources and evidence),
`pilot_ledger.json` (per-call tokens and cost).
