# Combo E Horizon Validation — 6M to 18M (3M steps)

**Date:** 2026-06-16  
**Goal:** Pick the correct validated horizon for Combo E (Valuation Extreme) by measuring SPX outcomes at **6M, 9M, 12M, 15M, 18M** (NYSE trading-day windows: 126, 189, 252, 315, 378).

## Context

- Combo E is **bearish** (`combo_hit_rates.E.direction: bearish`); primary horizon in CONFIG is **12M**.
- Prior T4 (testingv4) joined `forward_returns` but **spx_15m / spx_18m** were not stored — 18M was marked “not in DB.”
- Rohit feedback (B3): test **6–18M** maturities; each leg has different dynamics (CAPE slow, NFCI medium, CFTC positioning).

## Method

| Item | Spec |
|------|------|
| Population | All `combo_fires` where `runic_combo = 'E'` |
| Returns | Compute SPX `^GSPC` forward % from fire date via `forward_return_pct()` (same as pipeline) |
| Horizons | 6M (126d), 9M (189d), 12M (252d), 15M (315d), 18M (378d) |
| Bear metrics | Hit% ↓ = % SPX down; PW bear = `(hit × avg_down) + ((1−hit) × avg_up)` |
| Bull metrics | SPX Up% and PW bull (for continuity with T4 table) |
| Benchmarks | 5% / 7.5% / 10% / 12.5% / 15% drift at 6/9/12/15/18M |
| Mature n | Only fires where forward window ≤ last SPX price date |

## Success criteria (analyst)

1. **Bear hit rate** — which horizon best matches “structural valuation risk” (not necessarily highest % down).
2. **n_mature** — enough completed episodes (target ≥30 per Rohit obs rule where possible).
3. **PW excess (bear)** — does any horizon show meaningfully better bear framing vs drift?
4. **Stability** — bear hit should not collapse at longer horizons if 12M is correct primary.

## Outputs

- JSON: `macro_intelligence/analysis/regime_v2_experiments/COMBO_E_horizon_sweep_6_18m.json`
- Script: `scripts/combo_e_horizon_sweep.py`
- Report patches: B3 in main experiments report + `feedback_sectionwise_answers.md` + `testingv4_status.md`

## Not in scope

- Changing `combo_hit_rates.E.primary_horizon` in CONFIG (recommendation only).
- CAPE bucket re-slice at 15M/18M (overall table first; buckets optional follow-up).
