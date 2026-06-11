# Macro Threshold & Regime Experiments: Pipeline Updates and Review Answers

This note pulls together what we actually shipped on the macro intelligence pipeline between the 2026-06-06 regime v2 experiment run and the 2026-06-09 nightly briefing fixes. It is meant for Rohit and Divyanshu as a review packet: plan status vs reality, answers to the FM/regime questions, and the friction we hit along the way.

---

## Where the forward plan stands today

The forward plan (`MACRO_TH_EXP_PLAN.md`) said we are past shadow experiments and into Rohit review plus wiring decisions. That is still accurate.

| Plan phase | Planned state | Actual state (2026-06-09) |
|------------|---------------|---------------------------|
| Shadow experiments A–H | Done | Done (2026-06-06 run) |
| Rohit review packet | P0 item #1 | Done (`MACRO_TH_EXP_STATUS_ANALYSIS.md` §3) |
| CONFIG B4 window fix | P1, not started | **Open** (HY/VIX/VXTS still `full`, WALCL now `full` in production nightly but B4 audit not re-run) |
| Combo B confirmed-only slice | P0 #3 | **Open** (DB still has 89 B WATCH rows, 0 ACTIVE) |
| Production v2 regime swap | Post sign-off | **Not wired** (legacy labels in nightly PDF) |
| HMM production | Dec 2026+ | **Deferred** (prototype only) |

Worth noting here: the **production nightly briefing pipeline** did get a separate round of fixes (Divyanshu's 11-point report review under `testing/macro_report_updates/`). That work is live in engine code and PDF output. The **regime v2 shadow pipeline** is complete in analysis mode but not swapped into production yet.

---

## Pipeline updates we made

### 1. Regime v2 experiment suite (shadow / research)

Single entry point:

```bash
.venv/bin/python scripts/run_regime_v2_experiment_suite.py
```

| Deliverable | What the pipeline does now | Production wired? |
|-------------|---------------------------|-------------------|
| A | 5-dimension shadow regime backfill (1,901 Fridays) | No |
| B | TWY_ROC + dual percentiles (14,457 rows, 0 fallbacks) | TWY_ROC not in nightly pull |
| C | Emission vectors (8,805 daily rows) | No daily job |
| D | HMM prototype (k-means style) | Deferred |
| E | Combo C cancel probability function | Built, not on briefing |
| F | F2/F2a quant defs + F4 steepening grid | Shadow only |
| G | 7WK grind + VIX suppressed persistence | Not in briefing framing |
| H | 298-combo discovery (132 survivors, 62 promotion candidates) | Monthly re-run possible, no new named combos |

Artifacts land in `macro_intelligence/analysis/regime_v2_experiments/` including `X-FM_all.json` and `X_COMBO_regime_slices.json`.

### 2. Production nightly briefing pipeline (Divyanshu review)

These changes affect what you see in `runic_briefing_*.pdf` today:

| Update | Before | After |
|--------|--------|-------|
| Combo hit rates | Uniform 3M, bullish-only SQL | Per-combo horizon + bearish direction (E = 12M bearish) |
| Combo C terminal state | INACTIVE after cancel | CANCELLED + `cancel_date` |
| Combo F duration | Week count only | Week count + `started YYYY-MM-DD` |
| WALCL percentile | Rolling 3Y (inflated ~85th on flat MoM) | Full history from 2008 |
| Combo B HY gate | Single absolute floor | Dual: 400bps + 80th pctile |
| Posture label | BRAVE | EASY MONEY |
| Combo G hit rate | Shown like other combos | N/A (timing warning only) |
| PDF combo table | Fixed narrow columns, text overlap | Paragraph wrap + full-width columns |

**Tests:** 15 combo/metadata tests passed; 5 briefing renderer tests passed after PDF table fix.

**Follow-up scripts:** `scripts/analyze_combo_g_b_cascade.py` (G→B cascade + HY audit), MRU-01..03 executed.

---

## Answers to Rohit's FM and regime questions

Source ask: `additional_details.md`. Backtest JSON: `X-FM_all.json`, `X_COMBO_regime_slices.json` (1990–2026, shadow v2 regime tags).

### Extreme short FM (<15th pctile): contrary indicator?

Rohit claimed ~87.5% SPX higher 3m after extreme short FM (7/8 Combo B cases).

| Test | n | SPX up 3m | Verdict |
|------|---|-----------|---------|
| Combo B fires (all DB rows incl. WATCH) | 89 | 79.8% | Mostly validated, lower rate, much larger n |
| Raw FM <15 crossings | 35 | 60.0% | Weaker than Rohit's headline number |
| FM "wrong" (= SPX up) at extreme short | 35 | 60% | Direction OK, magnitude below 87.5% |

**Regime isolation** (raw FM <15, SPX up 3m by fed_cycle_v2):

| Regime | n | SPX up 3m |
|--------|---|-----------|
| EASING | 22 | 54.5% |
| TIGHTENING | 7 | 57.1% |
| EASY | 6 | 83.3% |
| FLAT curve | 6 | **33.3%** |
| INVERTED curve | 4 | 75.0% |
| NORMAL curve | 22 | 63.6% |

The contrary edge is **conditional**. It holds best when Combo B legs align (VIX + HY + CFTC together), not on FM percentile alone. Flat-curve regimes break the pattern.

### Extreme long FM (>85th pctile): Combo D territory?

| Horizon | Raw FM >85: SPX down | Raw FM >85: FM wrong (SPX up) |
|---------|----------------------|-------------------------------|
| 1 week | 41% | 59% |
| 3 months | 18% | **82%** |

| Horizon | Combo D fires: SPX down | Combo D fires: FM wrong |
|---------|-------------------------|-------------------------|
| 1 week | 38.5% | 61.5% |
| 3 months | 28.1% | 71.9% |

Rohit is **partially right**. Short-horizon wrong rates (~59–62%) sit below his 72–85% band. At 3m, FM extreme long is wrong most of the time because SPX keeps grinding up. Combo D is regime-dependent: only 18.3% SPX down 3m in HIKING_LATE (n=197) vs 43.2% in CUTTING_LATE (n=155).

### Moderate FM (25th–75th): "trend is your friend"?

| Metric | Result |
|--------|--------|
| Crossings | 84 |
| SPX up 3m | 76.2% |
| Avg 3m return | +3.15% |

Rohit flagged this as not necessarily accurate. The backtest shows bullish 3m outcomes most of the time, but that looks a lot like **baseline equity drift**, not a standalone alpha signal. No actionable edge fading moderate FM.

### Regime impact on named combos A–G (3m horizon)

| Combo | n | Overall 3m "hit" | Strongest slice | Weakest slice |
|-------|---|------------------|-----------------|---------------|
| A (bearish) | 174 | 23% SPX down | CUTTING_LATE 50% (n=26) | QE 20% (n=112) |
| B (bullish) | 89 | 79.8% SPX up | HIKING_LATE 83% (n=48) | CUTTING_LATE 76% (n=41) |
| C | 4 | 0% up | n too small | n/a |
| D (bearish) | 452 | 28% SPX down | CUTTING_LATE 43% | HIKING_LATE 18% |
| E (bearish) | 507 | 20% SPX down | (flat across regimes) | n/a |
| F (bullish) | 704 | 74.9% SPX up | QE 82% (n=212) | CUTTING_LATE 64% (n=248) |
| G | 0 | n/a | No fires in DB | n/a |

Combo B is robust across fed cycles. Combo D only really works outside HIKING_LATE. Combo F gets a boost in QE, which supports the Part H beta filter idea.

---

## Plan §6 open questions: closure table

Matches `MACRO_TH_EXP_STATUS_ANALYSIS.md` §5 against `MACRO_TH_EXP_PLAN.md` immediate questions.

| # | Question (consolidated plan) | Answer / status |
|---|------------------------------|-----------------|
| 1 | TWY_ROC ±0.30pp bands | Validated starting point; Apr 2025 anchor passes (−0.55pp DOVISH) |
| 2 | F4 trough −50 vs −80, steep +15 vs +40 | Grid run; win rates <35%; mechanism gate only |
| 3 | Apr 2025 DGS2 vs fed_cycle | Divergence confirmed; TWY_ROC adds leading signal |
| 4 | Dual percentile <50 fallback | Implemented; 0 fallbacks in backfill |
| 5 | Beta 55% vs 60% | Both in JSON; **Rohit decision pending** |
| 6 | 2-of-3 vs 3-of-3 legs | Diagnostic only; no production change |
| 7 | 6mo before HMM prod | **DEFER**; live C1 vectors not wired |
| 8 | T10Y2Y vs Ahil steepening work | F2/F2a in shadow; **Ahil review pending** |
| 9 | Classifier prompt update | **Pending Rohit sign-off** |
| 10 | Rohit FM Q&A | **Answered above**; partial validation |

### Questions queued for Rohit sync (from forward plan §2)

| # | Question | Recommended answer from data |
|---|----------|------------------------------|
| 1 | Approve fed_cycle_v2 4-state (PIVOTING n=27)? | Merge PIVOTING into EASING or drop until n≥30 |
| 2 | F4 steepening-short stays mechanism-only? | **Yes**; grid n too small for statistical promotion |
| 3 | Beta bar 55% or 60%? | Need per-combo call; 62 candidates waiting |
| 4 | TWY_ROC ±0.30pp for classifier? | **Yes** as starting point (Apr 2025 pass) |
| 5 | Start daily emission_vectors job? | **Yes if C approved**; starts 6-month HMM clock |

---

## Challenges we faced (honest list)

| Challenge | What happened | Impact |
|-----------|---------------|--------|
| Shadow vs production split | v2 regime labels live only in `macro_regime_log_v2`, not nightly PDF | Rohit sees legacy CUTTING_LATE etc. in briefing while analysis uses v2 |
| CONFIG B4 window mismatch | HY/VIX/VXTS on `full`, plan wanted `rolling_3y`; WALCL was wrong until macro report fix | Percentile ranks differ between experiment audit and production nightly |
| Combo B count confusion | 89 WATCH rows vs Rohit's "8 confirmed" | Hit rate backtests mix partial-leg WATCH with true capitulation |
| FM report terminology | Bearish signals sometimes labeled "SPX down" when JSON stores FM wrong rate | Audit requires reading raw JSON, not summary tables |
| PIVOTING sample size | n=27 below ≥30 obs gate | A1 validation fails; blocks clean 4-state promotion |
| HMM blocked on live data | Need 6 months production emission vectors | Earliest Dec 2026; prototype shows no Sharpe lift |
| FRED API timeouts | Full nightly pull hit HTTP 504 on 2026-06-09 | Had to fall back to DB cache for some runs |
| PDF table overlap | ReportLab fixed columns + plain strings | Duration text bled into Direction column; fixed with Paragraph wrap |
| Zero Combo G fires | 0 G in DB and 2007–2026 rescan | Cannot validate G→B 3–4 week lead from automated data |
| HY dual gate vs Oct 2022 | 427 bps passes abs floor, fails 80th pctile on full history | Tension between new rule and canonical B date (MRU-02) |
| Part H Claude story step | Ran with `use_claude=False` | 62 promotion candidates have no economic narrative yet |
| CFTC pre-2010 sparsity | FM bands thin before TFF era | Long-history FM stats dominated by post-2010 data |

On the flip side, the experiment suite itself re-runs in about 2 minutes, which made iteration tolerable. The painful parts were mostly definition mismatches (WATCH vs ACTIVE, SPX down vs FM wrong) rather than runtime.

---

## What I'd change based on this

1. **Re-slice Combo B as confirmed-only (3/3 legs ACTIVE)** before the next Rohit sync. That single filter probably closes most of the gap between 79.8% and Rohit's 87.5%.
2. **Fix CONFIG B4 windows and re-run the suite** so shadow and production percentiles speak the same language.
3. **Wire cancel probability to the briefing** (Part E is built; dashboard display is not).
4. **Hold HMM and new named combos** until Rohit signs A/B/C and we have live vectors.
5. **Add regime footnotes to combo hit rates** in the PDF (fed_cycle slices from `X_COMBO_regime_slices.json`) once v2 labels swap in.

---

## My doubts and questions

- Is PIVOTING a real economic state or just label noise at n=27? Merging it into EASING feels pragmatic but might hide genuine pivot weeks.
- The moderate FM "76% SPX up" result: I have not stripped out unconditional market drift. Does it still look special after subtracting a simple buy-and-hold baseline?
- Combo C has n=4 in the regime slice table. Should we even show C hit rates in the briefing until we have more cancelled/completed episodes?
- Part H found 62 combos at ≥80% hit rate. How many are just re-labelling existing A–G leg combinations vs genuinely new structure?
- Ahil's steepening-of-inversion work vs our F4 grid: are we measuring the same thing, or will that review surface a definitional mismatch?
- For production GO-live, what is the rollback plan if v2 fed_cycle labels confuse readers who have been trained on CUTTING_LATE / HIKING_LATE for months?

---

*Report prepared 2026-06-09. Sources: `MACRO_TH_EXP_STATUS_ANALYSIS.md`, `MACRO_TH_EXP_PLAN.md`, `additional_details.md`, `macro_intelligence/analysis/regime_v2_experiments/`, `testing/macro_report_updates/MACRO_REPORT_UPDATE_STATUS.md`.*
