# Backtests invalidated by the CNN F&G and HY OAS fixes — agree this list before re-running

**Date:** 2026-08-17
**Requested by:** Rohit, 6 Aug 2026 — *"every SSI backtest predating these fixes is stale, and nothing gets signed off a grid run on the old data. Before re-running: send me the LIST of which backtests are affected and who owns each. I'd rather agree the list than discover halfway through that two of you re-ran the same grid."*

## Read this first — the order was not followed

Six grids were re-run on **7 and 12 Aug, before this list existed**. That is the duplication risk Rohit named, so they are marked ⚠️ below rather than quietly listed as done. Nothing further gets re-run until this list is agreed.

## What changed, and what it touches

| Fix | Date | What moved | Which SSI inputs are affected |
|---|---|---|---|
| **CNN Fear & Greed** — crypto-index contamination removed; window extended to Jul 2020 via API and May 2012–Jul 2020 via Wayback reconstruction | 2026-08 | **Layer 1 history changed for 2012–2020**, and **2012–2018 is populated for the first time** | `cnn_fg` (Layer 1) |
| **HY OAS** — 6,620 proxy rows replaced with real ICE BofA OAS; continuous real data from Dec 1996 | 2026-08 | **Layer 2 history changed**; macro HY percentiles pre-2023 changed | `hyg_lqd` (Layer 2), macro `HY` variable, Combos A/B/F/G legs |
| Residual gaps disclosed, not fixed | — | CNN Jan 2011–May 2012 (~16 months) has no verifiable snapshot; 7 HY bond-holiday dates still on proxy | — |

**Rule of thumb:** any test whose signal path includes `cnn_fg` or `hyg_lqd`, or that scores against a pre-2023 HY percentile, is stale. Tests confined to CFTC, breadth, DBMF or VIX inputs are not affected by these two fixes.

## The list

Owner column reflects who ran it last. **Status is as of 2026-08-17.**

### Affected — must re-run (Layer 1 via `cnn_fg`)

| # | Test | Owner | Status |
|---|---|---|---|
| 01 | Long threshold sweep | Divyanshu | **STALE — not re-run.** Scores the composite, which includes `cnn_fg` |
| 02 | Short threshold sweep | Divyanshu | **STALE — not re-run** |
| 05 | TP/SL optimization | Divyanshu | **STALE — not re-run.** Entries come from composite thresholds |
| 06 | CNN Fear & Greed | Divyanshu | **STALE — must re-run.** This is the test *of* the fixed input |
| 09 | Z-score vs percentile | Divyanshu | **STALE — not re-run.** Normalisation compared across Layer 1 inputs |
| 12 | Bollinger SSI | Divyanshu | **STALE — not re-run.** Bands computed on the composite series |
| 14 | Gross/net divergence | Divyanshu | **STALE — not re-run** |
| 21 | Staleness decay | Divyanshu | ⚠️ **RE-RUN 7 Aug, before this list.** Includes `cnn_fg` age buckets — result stands but the ordering was wrong |

### Affected — must re-run (Layer 2 via `hyg_lqd`)

| # | Test | Owner | Status |
|---|---|---|---|
| 08 | HYG/LQD widening | Divyanshu | **STALE — must re-run.** This is the test *of* the changed input |
| 10 | Layer 2 confirmation | Divyanshu | **STALE — superseded by 22, which was itself re-run early (see below)** |
| 20 | Layer 2 z-score sweep | Divyanshu | **STALE — superseded by 22** |
| 22 | Layer 2 gate 2-D grid | Divyanshu | ⚠️ **RE-RUN 11–12 Aug, before this list.** 6-gate joint sweep includes `hyg_lqd`; **pending Rohit's decision** on keep/tighten/demote |

### Affected — macro side (pre-2023 HY percentiles)

| Item | Owner | Status |
|---|---|---|
| Combo B HY dual-leg tests (`tests/test_combo_b_hy_dual.py`, Oct 2022 fixture) | Divyanshu | **REVIEW** — fixtures encode HY values that were proxy-derived |
| Combos A / F / G HY legs in the 291-combo discovery outputs | Divyanshu | **STALE** — discovery ran on the proxy panel |
| D1 regime bucket series | Divyanshu | **REGENERATED 17 Aug as v1.2** (also picks up the B-above-C priority change) |
| Macro regime v2 experiment report | Divyanshu | **REVIEW** — HY percentile inputs changed pre-2023 |

### Not affected by these two fixes

| # | Test | Why not |
|---|---|---|
| 03 | Squeeze grid | CFTC-only inputs. ⚠️ Re-run 7 and 11 Aug anyway (fresh CFTC data), so the result is current |
| 04 | Liquidity exit grid | CFTC-only. ⚠️ Same — re-run 7 and 11 Aug |
| 07 | DBMF beta | DBMF/SPY only, 2019+ |
| 11 | VIX regime multiplier | VIX only — but see the VXTS convention note in `docs/rohit_6aug_answers_2026-08-17.md` §8 |
| 13 | Stochastic McClellan | Breadth only |
| 15 | SBI short signal | Breadth only. ⚠️ Re-run 12 Aug; returned n=0 for an unrelated C++ environment reason |
| 17 | TrendPulse deterioration | Signal-side, not SSI composite |
| 18 | COT FM long gate | CFTC only. ⚠️ Re-run 7 Aug |
| 19 | VIX/FM washout | VIX + CFTC only |

## Tally

| Bucket | Count |
|---|---|
| Stale, **not** yet re-run | 11 |
| ⚠️ Re-run before this list existed (7/12 Aug) | 6 |
| Regenerated 17 Aug | 1 |
| Needs review rather than a full re-run | 3 |
| Confirmed unaffected | 9 |

## Proposed re-run order (awaiting agreement)

1. **06 CNN F&G** and **08 HYG/LQD** first — they are the tests of the two changed inputs, so everything downstream depends on their verdicts.
2. Then the composite-threshold family: **01, 02, 05, 09, 12, 14**.
3. Then **10 / 20 / 22** as one Layer 2 pass, rather than three overlapping sweeps.
4. Macro side last: Combo A/B/F/G HY legs and the 291-combo discovery panel.

Nothing in steps 2–4 starts until Rohit agrees the list, so two people cannot re-run the same grid.
