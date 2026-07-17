# D4 — Window Audit Re-run (B4)

**Date:** 2026-07-16  
**Task:** Re-run B4 window audit after WALCL CONFIG fix (2026-06-09). Confirm all four originally flagged variables.  
**Source spec:** Part B2/B4 in consolidated plan; B4 logic in `src/macro_intelligence/analysis/regime_experiments/run_all.py`  
**CONFIG:** `macro_intelligence/CONFIG.yaml` (live as of this run)

---

## Executive summary

| Metric | Prior (2026-06-06/11) | This re-run (2026-07-16) |
|--------|----------------------|--------------------------|
| B4 pass | **FAIL** | **FAIL** |
| Mismatch count | 4 | **3** |
| WALCL | FAIL (`rolling_3y` vs plan `full`) | **PASS** (`full` / `full`) |
| HY | FAIL (`full` vs plan `rolling_3y`) | **FAIL** (unchanged) |
| VIX | FAIL (`full` vs plan `rolling_3y`) | **FAIL** (unchanged) |
| VXTS | FAIL (`full` vs plan `rolling_3y`) | **FAIL** (unchanged) |

**WALCL fix confirmed.** Three short-gate variables still misconfigured vs the B4 plan rule set.

---

## B4 audit rule (unchanged)

```
Structural → full history:  CAPE, NFCI, WALCL, CURVE, DXY
Flow / all others → rolling_3y:  HY, VIX, VXTS, CFTC, WTI, CNH, CPI, GSR, …
```

Implementation: `_run_b4_window_audit()` in `run_all.py`.

---

## Full 12-variable audit

| var_id | configured | plan expected | pass | combos | short-gate combos (B/D/G) |
|--------|------------|---------------|------|--------|---------------------------|
| NFCI | full | full | ✓ | A, E | — |
| **HY** | **full** | **rolling_3y** | **✗** | A, B, F, G | **B, G** |
| **WALCL** | **full** | **full** | **✓** | A, C | — |
| CNH | rolling_3y | rolling_3y | ✓ | A, C, G | G |
| WTI | rolling_3y | rolling_3y | ✓ | C | — |
| **VIX** | **full** | **rolling_3y** | **✗** | B, D, G | **B, D, G** |
| **VXTS** | **full** | **rolling_3y** | **✗** | D, G | **D, G** |
| CFTC | rolling_3y | rolling_3y | ✓ | B, D, E, F | B, D |
| CURVE | full | full | ✓ | A, E | — |
| CPI | rolling_3y | rolling_3y | ✓ | C | — |
| GSR | rolling_3y | rolling_3y | ✓ | A | — |
| CAPE | full | full | ✓ | E | — |

**Score:** 9 / 12 pass. **B4 pass = false.**

---

## Why this is not cosmetic (short-gate combos)

The three remaining mismatches feed the named short-gate combos under evaluation:

| Combo | Role | Variables affected by window mismatch |
|-------|------|--------------------------------------|
| **B** | Bullish (all legs required) | HY (high OAS + pctile), VIX (level + pctile), CFTC ✓ |
| **D** | Bearish | VXTS (ratio pctile), VIX (max level gate), CFTC ✓ |
| **G** | Bearish | HY, VIX, VXTS, CNH ✓ |

Wrong `pctile_window` changes unconditional percentile ranks → shifts which Fridays cross RARE/EXTREME thresholds → changes combo fire dates and reported hit rates for B/D/G sweeps.

CFTC, CNH, WTI, CPI, GSR already match plan. The blocker is specifically HY / VIX / VXTS on `full` where B4 expects `rolling_3y`.

---

## WALCL confirmation

| Field | 2026-06-06 (original audit) | 2026-07-16 (this re-run) |
|-------|----------------------------|--------------------------|
| configured | `rolling_3y` | `full` |
| expected | `full` | `full` |
| status | FAIL | **PASS** |

Production nightly fix on 2026-06-09 is reflected in CONFIG. B4 was not re-run until this task.

---

## Open spec conflict (Rohit feedback 2026-06-11)

On the Reply doc B2 thread, Rohit noted:

> VIX, HY, VXTS should **not** be 3-year rolling. Structural/level variables (CAPE, **VIX**, yield curve, NFCI, GSR): **FULL EXPANDING HISTORY**. Flow/ROC (WTI, CNH, **WALCL MoM%**, CPI, TWY_ROC): **3-year ROLLING**.

That would classify HY and VXTS as structural (full) and WALCL as flow (rolling_3y) — the **opposite** of the current B4 rule set for HY/VXTS/WALCL.

**This re-run uses the coded B4 rule from the consolidated plan / experiment suite**, not the June 11 override. Resolving which spec is authoritative is a Rohit sign-off item before changing CONFIG.

---

## Artifacts

| File | Description |
|------|-------------|
| `D4_window_audit_rerun_2026-07-16.json` | Machine-readable B4 payload + per-var table |
| `D4_window_audit_rerun_2026-07-16.md` | This report |

**Re-run command:**

```bash
cd /home/ubuntu/uiv2/git/MindWealth_UI
.venv/bin/python -c "from src.macro_intelligence.analysis.regime_experiments.run_all import _run_b4_window_audit; import json; print(json.dumps(_run_b4_window_audit(), indent=2))"
```

---

## Recommended next step

1. **Rohit decision:** B4 plan rule (HY/VIX/VXTS → `rolling_3y`) vs June 11 structural override (keep `full` for HY/VIX/VXTS; WALCL → `rolling_3y`).
2. If plan rule stands: patch `CONFIG.yaml` lines for HY, VIX, VXTS → `pctile_window: rolling_3y`; recompute percentiles; re-run combo B/D/G gate sweeps.
3. If override stands: update `_run_b4_window_audit()` structural set to include HY, VIX, VXTS and move WALCL to flow; re-run B4 (should pass with current CONFIG except WALCL).

Until resolved, **B4 remains FAIL** and short-gate hit rates for B/D/G are computed against mismatched windows.
