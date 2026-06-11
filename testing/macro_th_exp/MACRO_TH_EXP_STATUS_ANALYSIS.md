# Macro Intelligence Threshold & Regime Experiments — Status Analysis

**Date:** 2026-06-07  
**Audience:** Divyanshu, Rohit  
**Source requirements:** [`macro_intelligence_docs/Macro_Regime_System_v2_Consolidated_Plan_Mail.pdf`](../../macro_intelligence_docs/Macro_Regime_System_v2_Consolidated_Plan_Mail.pdf) (originally `Threshold experiments mail.pdf`)  
**Structured summary:** [`docs/ssi_validation/MACRO_REGIME_V2_CONSOLIDATED_PLAN_SUMMARY.md`](../../docs/ssi_validation/MACRO_REGIME_V2_CONSOLIDATED_PLAN_SUMMARY.md)  
**Experiment run:** 2026-06-06 — [`docs/ssi_validation/MACRO_REGIME_V2_EXPERIMENT_REPORT.md`](../../docs/ssi_validation/MACRO_REGIME_V2_EXPERIMENT_REPORT.md)  
**Artifacts:** [`macro_intelligence/analysis/regime_v2_experiments/`](../../macro_intelligence/analysis/regime_v2_experiments/)  
**Rohit follow-up:** [`additional_details.md`](additional_details.md)

---

## 1. What this directory tracks

This folder (`testing/macro_th_exp/`) is the working area for **macro threshold and regime experiment status**. It sits alongside two related but distinct workstreams:

| Workstream | Scope | Primary docs | Run date |
|------------|-------|--------------|----------|
| **Regime v2 (Runic)** | 5 regime dimensions, 14th variable TWY_ROC, emission vectors, HMM, 298-combo pipeline, FM/regime isolation | Consolidated Plan PDF, experiment report Parts A–I | 2026-06-06 |
| **SSI thresholds** | Layer 1/2 gates, CFTC squeeze, HYG/LQD, DBMF beta, breadth | `SSI_OpenQuestions_DivyanshuTestList`, `SSI_THRESHOLD_JUSTIFICATION.md` | 2026-06-04 to 2026-06-07 |

The consolidated plan PDF is **regime + Runic combo methodology**, not the SSI gate sweep. SSI threshold experiments are documented under `testing/ssi_th_exp/` and `docs/ssi_validation/`.

---

## 2. Overall status (2026-06-07)

### Experiment execution: COMPLETE (research / shadow)

All eight deliverables (A–H) from the consolidated plan were **run once** on 2026-06-06 via:

```bash
.venv/bin/python scripts/run_regime_v2_experiment_suite.py
```

| Deliverable | Experiment status | Production status | GO/NO-GO |
|-------------|-------------------|-------------------|----------|
| **A** — Regime dimension refinement | RUN — 1,901 Fridays backfilled in shadow | Production still uses legacy 7-state fed_cycle, 2-state liquidity | GO (shadow only) |
| **B** — TWY_ROC + dual percentiles | RUN — Apr 2025 anchor passes (−0.55pp DOVISH) | TWY_ROC not in nightly pull | GO |
| **C** — Emission vectors | RUN — 8,805 rows backfilled | Daily live job not wired | GO (post sign-off) |
| **D** — HMM layer | RESEARCH prototype only | Deferred until 6+ months live vectors (~Dec 2026 earliest) | DEFER |
| **E** — Cancel probability (Combo C MC) | RUN — function built | Not wired to briefing/dashboard | GO |
| **F** — Quantitative regime defs | RUN — F2/F2a pass; F4 grid run | Production `regime_rules.py` unchanged | GO (F4 = mechanism gate only) |
| **G** — Persistence (7WK grind, VIX suppressed) | RUN | Not in nightly briefing framing yet | GO |
| **H** — 298-combo discovery pipeline | RUN — 132 survivors, 62 promotion candidates | Monthly re-run; no new named combos promoted | GO |

**Bottom line:** Experiments are **done in shadow/analysis mode**. Nothing from v2 regime labels, TWY_ROC, emission vectors, or HMM has been swapped into production nightly output. Rohit sign-off is the gate for each GO item above.

---

## 3. Answers to Rohit's FM / regime questions (`additional_details.md`)

Rohit asked to validate three FM positioning claims and to **isolate regime impact on combos**. Below: backtest results from `X-FM_all.json` and `X_COMBO_regime_slices.json` (1990–2026 history, CFTC FM percentile bands, shadow v2 regime tags).

### 3.1 FM extreme short (<15th percentile) — contrary indicator?

| Metric | Rohit claim | Backtest result | Verdict |
|--------|-------------|-----------------|--------|
| Combo B confirmed fires, SPX higher 3m | ~87.5% (7/8 since 1990) | **79.8%** (71/89 fires) | **Mostly validated** — same direction, slightly lower rate; n much larger |
| All FM <15th crossings, SPX up 3m | Implied ~87% | **60.0%** (21/35 crossings) | **Weaker** — raw band ≠ Combo B leg set |
| FM "wrong" rate at 3m (extreme short) | FM wrong when SPX up | **60%** SPX up | Directionally right, magnitude below Rohit's 87.5% |

**Regime isolation (3m SPX up rate by fed_cycle_v2):**

| Regime | n | SPX up 3m | Notes |
|--------|---|-----------|-------|
| EASING | 22 | 54.5% | Weakest slice — not a clean contrary signal |
| TIGHTENING | 7 | 57.1% | Small n |
| EASY | 6 | 83.3% | Strongest — aligns with Rohit |
| FLAT curve | 6 | **33.3%** | **Contrary signal fails** in flat-curve regimes |
| INVERTED curve | 4 | 75.0% | Supports washout narrative |
| NORMAL curve | 22 | 63.6% | Moderate support |

**Takeaway:** Extreme-short FM is a **conditional** contrary indicator. It is strongest when tied to **Combo B leg alignment** (VIX + HY + CFTC together), not FM percentile alone. Regime matters: flat-curve environments break the pattern.

---

### 3.2 FM extreme long (>85th percentile) — Combo D territory?

| Horizon | Rohit claim (FM wrong) | Backtest: SPX down rate | Backtest: FM wrong (= SPX up) |
|---------|------------------------|-------------------------|-------------------------------|
| 1 week | 72–85% wrong at 5–10 days | 41% SPX down | **59% FM wrong** |
| 3 months | Signal degrades at longer horizons | 18% SPX down | **82% FM wrong** (SPX keeps rising) |

For **Combo D fires specifically** (not raw FM band):

| Horizon | SPX down rate | FM wrong (SPX up) |
|---------|---------------|-------------------|
| 1 week | 38.5% | **61.5%** |
| 3 months | 28.1% | **71.9%** |

**Verdict:** Rohit is **partially right**. At **short horizons**, raw FM extreme long shows ~59% FM wrong (below his 72–85% band). Combo D fires are closer at 1w (~62% wrong). At **3m**, FM extreme long is wrong **most of the time** (82% SPX up) — markets stay expensive and trend-followers stay long. This matches Rohit's "signal degrades at longer horizons" only if you interpret "degrades" as "correction doesn't happen"; the contrary edge is actually **stronger** at 3m than 1w for raw FM band.

**Regime slices (Combo D, 3m SPX down by fed_cycle_legacy):**

| Regime | n | SPX down 3m |
|--------|---|-------------|
| HIKING_LATE | 197 | 18.3% |
| CUTTING_LATE | 155 | 43.2% |
| QE | 100 | 24.0% |

Combo D short signal is **weakest in HIKING_LATE** — regime conditioning is essential before using D as a standalone short.

---

### 3.3 FM moderate (25th–75th percentile) — "trend is your friend"?

| Metric | Result |
|--------|--------|
| Crossings | 84 |
| SPX up 3m | **76.2%** |
| Avg 3m return | +3.15% |

Rohit flagged this statement as **not necessarily accurate**. Backtest shows moderate FM coincides with bullish 3m outcomes **76% of the time**, but that is largely **consistent with unconditional equity drift**, not a proven independent edge for or against FM. **No actionable standalone signal** — treat as baseline, not alpha.

---

### 3.4 Regime impact on named combos A–G

From `X_COMBO_regime_slices.json` (3m horizon, legacy fed_cycle tags on stored fires):

| Combo | Overall n | Overall 3m "hit" | Strongest regime slice | Weakest regime slice |
|-------|-----------|------------------|------------------------|----------------------|
| **A** (bearish) | 174 | 23% SPX down | CUTTING_LATE 50% down (n=26) | QE 20% down (n=112) |
| **B** (bullish) | 89 | **79.8% SPX up** | HIKING_LATE 83% up (n=48) | CUTTING_LATE 76% up (n=41) |
| **C** (bullish) | 4 | 0% up (all failed) | n too small | — |
| **D** (bearish) | 452 | 28% SPX down | CUTTING_LATE 43% down | HIKING_LATE 18% down |
| **E** (bearish) | 507 | 20% SPX down | CUTTING_LATE 18% down | QE 14% down |
| **F** (bullish) | 704 | **74.9% SPX up** | QE 82% up (n=212) | CUTTING_LATE 64% up (n=248) |
| **G** | 0 | — | No fires in DB | — |

**Regime isolation conclusion:** Combo performance **varies materially by fed cycle**. Examples:
- **B** holds across regimes (76–83% up) — robust bullish washout signal.
- **D** is regime-dependent: useful mainly outside HIKING_LATE.
- **F** is strongest in QE (82% up) — beta filter in Part H is justified.

Full 5-dimension slicing (curve, liquidity, val, geo) is in `X-FM_all.json` regime_slices; fed_cycle is the most populated dimension.

---

## 4. Part-by-part experiment findings (condensed)

### Part A — Regime labels (shadow v2)

- **fed_cycle_v2:** TIGHTENING 763, EASING 727, EASY 384, PIVOTING 27
- **A1 pass:** **False** — PIVOTING n=27 below ≥30 obs threshold
- **geo_overlay_v2:** NEUTRAL 1855, ELEVATED_RISK 25, CRISIS 21 (6→3 collapse works)
- **liquidity_v2:** 9 composite states (2×2 level × direction + flat variants)
- **Fiscal caveat (A5):** Inversion + deficit >5% GDP bucket: 0% 3m hit (n=1); no-offset bucket 42% (n=12). Supports weakening inversion signal under fiscal dominance (2022–23).

### Part B — TWY_ROC & percentiles

- Apr 7 2025: DGS2 8wk change **−0.55pp → DOVISH** while legacy fed still TIGHTENING — anchor **passes**
- Dual percentile: 14,457 rows both unconditional + regime; **0 fallbacks** in backfill
- **B4 window audit FAIL:** HY, VIX, VXTS configured `full` but plan expects `rolling_3y`; WALCL configured `rolling_3y` but plan expects `full` — CONFIG.yaml alignment still open

### Part C — Emission vectors

- 8,805 daily vectors backfilled
- Sub-threshold VIX (65th–79th pctile): n=7, 85.7% positive 3m — too few for statistical gate
- Binary vs vector lag: **0 days** median (no early-warning gain yet at RARE threshold)

### Part D — HMM

- Prototype only (k-means-style on mean percentile vector, not production HMM)
- Production blocked until **~Dec 2026** (6 months live C1 vectors from sign-off)
- Regime backtest on Combo B/D: HMM Risk-Off filter does not improve hit rates in prototype

### Part E — Cancel probability

- Combo C combined cancel prob example: **2.2%**
- E2 calibration: 4 historical episodes, 0 realized cancels — under-calibration suspected

### Part F — Quantitative defs + F4 steepening-short grid

| Trough (bps) | Steepen 4wk (bps) | n | SPX down 3m |
|--------------|-------------------|---|-------------|
| −50 | +15 | 17 | 17.6% |
| −50 | +40 | 4 | 25% |
| −80 | +15 | 9 | 33.3% |
| −80 | +40 | 2 | 0% |

Win rates **do not support statistical promotion**. Plan correctly treats F4 as **MECHANISM+ANALOG** only (2000, 2007; 2022–23 failure with fiscal offset). Oct 2022 `tightening_late` F1: **False** (known gap vs legacy HIKING_LATE label).

### Part G — Persistence

- **7-week grind:** n=2, both negative 6m — **not standalone short** (matches PDF intent)
- **VIX suppressed → VIX>25 within 35d:** 8.5% lead rate — weak precursor (~50% claimed in plan not reproduced)

### Part H — 298-combo pipeline

| Stage | Count |
|-------|-------|
| Signatures | 298 |
| With fires | 225 |
| Surfaced (≥3 fires, ≥60% HR) | 187 |
| Beta + directionality pass | 132 |
| Promotion candidates (≥5 fires, ≥80% HR) | 62 |

Tavila economic story step **skipped** (`use_claude=False`). No new combos promoted to production names. Top survivors are CPI/WTI/CFTC/VIX-heavy 3-variable sets — many overlap existing combo legs.

---

## 5. Open questions from plan §6 — closure status

| # | Question | Status |
|---|----------|--------|
| 1 | TWY_ROC ±0.30pp bands | Validated as starting point (Apr 2025 pass) |
| 2 | F4 trough −50 vs −80, steep +15 vs +40 | Grid run — mechanism gate only, n too small |
| 3 | Apr 2025 DGS2 vs fed_cycle | Divergence confirmed — TWY_ROC adds leading signal |
| 4 | Dual percentile <50 fallback | Implemented and logged; 0 fallbacks in backfill |
| 5 | Beta 55% vs 60% | Both reported in combo JSON — **human decision pending** |
| 6 | 2-of-3 vs 3-of-3 legs | Diagnostic only — no production change |
| 7 | 6mo before HMM prod | **DEFER** — clock not started (live C1 not wired) |
| 8 | T10Y2Y align with Ahil steepening work | F2/F2a in shadow — **Ahil review pending** |
| 9 | Classifier prompt update (Part A dims) | **Pending Rohit sign-off** |
| 10 | Rohit FM Q&A | **Answered in §3 above** — partial validation |

---

## 6. Known gaps and report inconsistencies

1. **Master experiment report hit-rate labels:** For bearish signals (FM extreme long, Combo D), the report sometimes quotes **FM wrong rate** (1 − SPX_down_rate) under the label "SPX down rate". Raw JSON in `X-FM_all.json` stores SPX down rate directly. Always read JSON for audit.
2. **Combo B fire count:** 89 WATCH/ACTIVE rows in DB vs Rohit's "8 confirmed Combo B instances" — detection criteria differ (WATCH includes partial legs).
3. **Production vs shadow:** All regime slices use **shadow v2** (`macro_regime_log_v2`); production briefing still shows legacy labels.
4. **Part H regime tags:** Combo discovery used **legacy** regime JSON on existing `combo_fires` — re-tag with v2 before final beta filter sign-off.
5. **CFTC history:** FM bands pre-2010 sparse — long-history FM stats dominated by post-2010 CFTC TFF era.
6. **SSI threshold track:** Separate from this PDF; 12/17 SSI tests credible as of 2026-06-07 (`testing/ssi_th_exp/SSI_OPEN_QUESTIONS_SUMMARY.md` Section 11).

---

## 7. Production blockers (what prevents GO-live of v2)

| Blocker | Owner | Notes |
|---------|-------|-------|
| Rohit sign-off on shadow regime labels | Rohit | A1 PIVOTING thin; fed PAUSING not in v2 |
| Wire TWY_ROC + dual percentiles to nightly | Eng | B4 CONFIG window fixes first |
| Wire daily emission_vectors job | Eng | Starts 6-month HMM clock |
| Classifier prompt update (Section 5.2) | Eng + Rohit | Part A state lists |
| Ahil review F4 analog alignment | Ahil | Steepening-of-inversion gate |
| Beta 55 vs 60% per combo decision | Rohit | 62 promotion candidates waiting |
| Dashboard cancel probability | Eng | Part E built, not displayed |

---

## 8. Key file index

| File | Purpose |
|------|---------|
| `additional_details.md` | Rohit's FM/regime validation ask |
| `MACRO_TH_EXP_PIPELINE_REPORT_2026-06-09.md` / `.pdf` | Pipeline updates + Rohit Q&A report (report-creation skill) |
| `MACRO_TH_EXP_STATUS_ANALYSIS.md` | This document |
| `MACRO_TH_EXP_PLAN.md` | Forward plan and sequencing |
| `../../macro_intelligence_docs/Macro_Regime_System_v2_Consolidated_Plan_Mail.pdf` | Source requirements |
| `../../docs/ssi_validation/MACRO_REGIME_V2_EXPERIMENT_REPORT.md` | Master experiment report |
| `../../macro_intelligence/analysis/regime_v2_experiments/experiment_manifest.json` | Single JSON rollup |
| `../../macro_intelligence/analysis/regime_v2_experiments/X-FM_all.json` | FM + regime slices |
| `../../macro_intelligence/analysis/regime_v2_experiments/X_COMBO_regime_slices.json` | Combo A–G by regime |
| `../../docs/ssi_validation/COMBO_DISCOVERY_PIPELINE_REPORT.md` | Part H ranked survivors |
| `../../scripts/run_regime_v2_experiment_suite.py` | Re-run entry point |

---

*Analysis prepared 2026-06-07 from 2026-06-06 experiment run artifacts. Re-run experiments after CONFIG window fixes or production regime swap.*
