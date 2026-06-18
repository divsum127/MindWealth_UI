# Threshold Validation v2 — Plain-English Understanding Guide

**For:** Anyone implementing or reviewing macro threshold changes in MindWealth  
**Source spec:** `testing/macro_th_exp/testingv2/threshold_validation_plan.md`  
**Status / results:** `testing/macro_th_exp/testingv2/threshold_validation_report.md` (run date: 2026-06-15 sweep, report 2026-06-16)  
**Purpose:** Explain what the validation experiment asked us to do, what we ran, what the numbers say, and what doubts to raise with Rohit Sir.

---

## Summary — experiments performed and outcomes

Brief map of everything we ran and what we learned. Details and Q&A tables follow in later sections.

| # | Experiment | What we did | Outcome |
|---|------------|-------------|---------|
| **P1** | **DB percentile fix** | Found ~220 `daily_readings` rows stored on 0–1 scale instead of 0–100; normalized them; fixed old sweep script bands | **Done.** 0 legacy rows left. Corrected regression sweep (`F_per_variable_sweep_v2.json`) now has events for all 12 variables (old sweep had 13/22 bands with n=0). |
| **P1b** | **Corrected pctile-only sweep** | Re-ran `per_variable_threshold_sweep.py` on 70–100 scale + added CURVE | **Done.** Sanity check only; not used for CONFIG decisions. |
| **P2** | **12-variable threshold sweep** | `threshold_sweep_v2.py`: first-crossing events, 5-day cooldown, SPX forwards at 1M–12M, PW (probability-weighted) excess vs drift, hostile-regime slice | **Done.** 12 JSONs + `SUMMARY.json`. Scan 1990-01-01 → ~2026-07-03. Runtime ~227s. |
| **P2a** | **RARE tier review (§4a)** | Compared current CONFIG RARE vs best same-side alternative per variable at primary horizon | **11/12 Keep CONFIG.** **WTI down-leg only:** Consider `down_15pct` (large oil drawdown, n=30, 73% bull hit 6M, +0.8pp excess vs ±6%). CPI: **Defer** (n=1). |
| **P2b** | **EXTREME tier review (§4b)** | Same as 4a for EXTREME bands | **All Keep CONFIG** except same **WTI down** Consider. CPI/CAPE_low sparse (n=0–2). |
| **P2c** | **Raw returns export** | CSV of every first-crossing event with SPX returns 1M–12M | **4,169** RARE rows + **3,726** EXTREME rows exported for audit. |
| **P3a** | **Combo B gate sweep** | Replayed VIX/HY/CFTC legs on `daily_readings` at 3M bullish; fixed HY leg to CONFIG **OR** (OAS or pctile) | **Current 3-of-3:** n=**9**, hit **77.8%**, excess **+3.96%**. **2-of-3:** n=**41**, hit **75.6%**, excess **+2.15%**. Production `combo_detector` still uses HY **AND** — mismatch noted. |
| **P3b** | **Combo F SPX sweep** | SPX % above 50-week MA at 1/2/3/5% thresholds, 6M horizon | **Keep 3%** (n=42, hit 85.7%, +3.15% excess). 5% adds only +0.35pp excess. |
| **P3c** | **Combo E sweep** | CAPE / NFCI / CFTC gates at 12M bearish | **Keep CAPE≥28**, NFCI≤−0.3, CFTC≥80 — current combo-aligned gates OK. |
| **P3d** | **Combo D sweep** | VXTS / CFTC / VIX gates at 5D bearish | **Weak signal** — no variant hits 60% down-rate; all negative PW excess vs +0.5% 5D benchmark. Current gates as good as any tested. |
| **P4** | **Report + verdicts** | Full report with appendix (all bands × 5 horizons); analyst verdicts (not hard Δ/hit gates) | **3 production changes suggested:** (1) WTI down RARE/EXTREME optional retune, (2) Combo B 2-of-3 for WATCH consideration, (3) Combo F stay at 3%. Everything else unchanged in CONFIG. |

**One-line takeaway:** The data mostly **confirms current `CONFIG.yaml` thresholds**. The only variable-level change worth debating is **WTI down-side** (split large drawdown from symmetric ±6%). Combo B is **statistically rare** at strict 3-of-3 (n=9) but economically strong when it fires.

**How to read the experiment tables:** Every Q&A table has a **Doubts to ask Rohit Sir** column. These are open questions raised by the backtest, not sign-off requests.

---

## 1. What is this document?

The **threshold validation v2** work answers one question: *Are the RARE and EXTREME cutoffs in `macro_intelligence/CONFIG.yaml` still the right levels for predicting SPX forward returns?*

We did **not** re-run the full live combo engine. We ran **single-variable isolation tests** (each macro input on its own) plus **separate gate sweeps** for named combos B, F, E, and D.

Success in the original plan meant clearing four bars: PW excess ≥+2pp vs current, n≥5 events, hit≥60%, and hostile-regime excess not worse by >2pp. The final report also uses **analyst verdicts** that weigh combo role and economic meaning, not only those four numbers.

---

## 2. Core concepts (read this first)

| Term | Simple meaning |
|------|----------------|
| **RARE / EXTREME** | Two severity tiers in CONFIG. RARE = “unusual but not crisis.” EXTREME = “crisis-level.” Each variable has its own numeric definition (e.g. VIX≥25 vs ≥35). |
| **CONFIG.yaml** | Production file that stores the threshold values the nightly macro agent uses today. |
| **First-crossing** | Count an event only when the variable **enters** a band from outside it — not every day it stays inside. Stops one long episode from counting as dozens of signals. |
| **Cooldown (5 days)** | After a first-crossing, ignore new crossings for 5 calendar days. |
| **PW (probability-weighted) expected return** | `(hit% × avg win) + ((1−hit%) × avg loss)` — blends how often SPX moved the “right” way with how big wins and losses were. |
| **Excess** | PW expected minus a **benchmark drift** (e.g. +2.5% at 3M). Positive excess = better than “do nothing in SPX.” |
| **Hit rate** | % of events where SPX moved in the signal’s predicted direction. For **bearish** rows, “Hit% ↓” means SPX went **down**. |
| **Primary horizon** | The main time window we judge each variable on: **3M** for most vars, **6M** for WTI, **12M** for CAPE. |
| **Same-side best alt** | Best alternative threshold on the **same direction** only (e.g. CAPE high vs high, not high vs low), with at least 5 events. |
| **Hostile slice** | Subset of events when Fed was hiking/tightening **or** yield curve was inverted — checks the signal still works in bad macro regimes, not only QE bull runs. |
| **Leg replay (Combo B)** | Reconstruct combo legs from historical `daily_readings` instead of using stored `combo_fires` rows. |
| **OR vs AND (HY leg)** | CONFIG says HY stress if OAS≥400 **or** pctile≥80. Early replay used **AND** (both required), which wrongly gave n=0; fixed to **OR** for the sweep. Production detector may still use AND. |
| **Shadow / experiment** | Backtest and JSON artifacts — not yet changed in live nightly runs unless CONFIG is edited. |

---

## 3. Phase P1 — Data foundation

**What the spec asks:** Fix broken percentile storage and band definitions so sweeps count real events before we trust any threshold comparison.

### P1 — Experiment status

| | Detail |
|---|--------|
| **What we did** | `normalize_pctile_scale.py` on `runic.db`; fixed `per_variable_threshold_sweep.py` to 0–100 bands; re-ran F regression sweep |
| **Results** | **220** rows normalized (VIX 63, NFCI 48, GSR 25, WTI 19, CFTC 17, CNH 17, WALCL 15, HY 8, VXTS 8). **0** legacy 0–1 rows remain. |
| **Production** | DB migration applied; CONFIG thresholds unchanged |

#### P1 — Old vs new

| Aspect | Old / broken | New / fixed | Status |
|--------|--------------|-------------|--------|
| Pctile storage | Mixed 0–1 and 0–100 | All 0–100 | ✅ Migrated |
| Sweep bands | 0.70–0.79 (wrong scale) | 70–79 | ✅ Script fixed |
| Variables in sweep | 11 (no CURVE) | 12 | ✅ CURVE added |
| Bands with n=0 | 13/22 in old F sweep | All 12 vars have events in v2 | ✅ |

**Questions we were looking for:**

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Was the old percentile bug big enough to invalidate prior threshold work? | **Yes** | **220/14,505** pctile rows were on 0–1 scale; VIX example min=0.014. Old `F_per_variable_sweep.json` had **13/22** bands with **n=0**. After fix, v2 sweeps fire on all 12 variables. | **Doubt:** Should we re-run any **testingv1** conclusions that relied on the broken F sweep, or treat v2 as the new baseline? |
| Is the DB migration safe to leave permanent? | **Yes** | Script is idempotent (0 rows on re-run). | None — migration is done. |

---

## 4. Phase P2 — Per-variable threshold sweeps

**What the spec asks:** For each of 12 macro variables, sweep RARE and EXTREME cutoffs above and below CONFIG; measure SPX returns at 1M/3M/6M/9M/12M; compare current vs best alternative; apply hostile slice.

### P2 — Experiment status

| | Detail |
|---|--------|
| **What we did** | `scripts/threshold_sweep_v2.py` on VIX, HY, CFTC, NFCI, WALCL, WTI, CNH, GSR, VXTS, CAPE, CPI, CURVE |
| **Results** | 12 `*_sweep.json` + `SUMMARY.json`; event window **1990-01-01** to **~2026-07-03** |
| **Production** | CONFIG unchanged except **WTI down-side** flagged for discussion |

#### P2 — Old vs new (method)

| Aspect | Prior `per_variable_threshold_sweep` | `threshold_sweep_v2` | Status |
|--------|--------------------------------------|----------------------|--------|
| Threshold type | Pctile bands only | Raw CONFIG values (bps, levels, %) | ✅ v2 |
| Event logic | Unclear / band membership | First-crossing + 5d cooldown | ✅ v2 |
| Hostile slice | Missing | HIKING_* + INVERTED from `macro_regime_log` | ✅ v2 |
| Verdict | Mechanical Δ/hit gates | Analyst judgment per variable (§4) | ✅ Report |

### P2 — Per-variable outcomes (RARE + EXTREME verdicts)

| Variable | Primary Hz | Verdict (both tiers unless noted) | Key numbers |
|----------|------------|-----------------------------------|-------------|
| **CAPE** | 12M | **Keep CONFIG** | High≥28: n=7 RARE, 14.3% bear hit but SPX rallied (+19.5% avg) — structural, not timer. Low≤16: n=2. Low≤12 EXTREME: **0** fires since 1990. |
| **CFTC** | 3M | **Keep CONFIG** | Short≤15: 63% bull hit (n=38). Long≥85: ~20% bear hit — structural crowding warning, not 3M timer. |
| **CNH** | 3M | **Keep CONFIG** | Down 1.5%: **82.4%** bull hit (n=17). Extreme down 3.5%: n=**2** only. |
| **CPI** | 3M | **Defer** | DB starts **2024-01** (31 rows). RARE n=**1**; EXTREME n=**0**. Cannot validate thresholds yet. |
| **CURVE** | 3M | **Keep CONFIG** | Steepen≥15bps: **75.9%** bull hit (n=29). Invert≤−30bps: weak timer; deep −80bps EXTREME n=**2**. |
| **GSR** | 3M | **Keep CONFIG** | Risk-off context; 3M SPX timing weak (~24% bear hit at 5% 4wk). |
| **HY** | 3M | **Keep CONFIG** | RARE OAS≥400: n=42, 45% bear hit. Alt 600bps higher excess but lower hit and n. |
| **NFCI** | 3M | **Keep CONFIG** | Easy ±0.3 SD: 75% bull hit (n=12). Tight side n=7–8 — borderline sample. |
| **VIX** | 3M | **Keep CONFIG** | RARE ≥25+pctile≥80: n=**72**, Combo B gate. Extreme ≥35: n=19, 10.5% bear hit (fear spikes, SPX still rallied). |
| **VXTS** | 3M | **Keep CONFIG** | Backwardation stress marker; ~26% bear hit at 3M. Contango bull ~77% hit. |
| **WALCL** | 3M | **Keep CONFIG** | QE/QT liquidity; expand n=76 RARE; bearish contract weak at 3M (lag). |
| **WTI** | 6M | **Consider down_15pct** (down leg only) | Down RARE ±6%: n=112, 67.9% hit, **−0.65%** excess. Down **15%**: n=30, **73.3%** hit, **+0.16%** excess (+0.8pp vs 6%). Up-leg: weak bear timing (~31% hit) — **keep symmetric CONFIG on up-side**. |

**Questions we were looking for:**

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Should any RARE threshold move based on PW excess alone? | **Mostly No** | Only **WTI down** shows a cleaner economic story at −15% 4wk drawdown. HY/VIX alts with higher excess trade off hit rate or combo semantics (§4 verdicts). | **Doubt:** For WTI, should we **split** CONFIG into directional tiers (down_15% RARE, up_6% RARE) instead of symmetric `\|4wk\| ≥6%`? That changes Combo C wiring. |
| Is high CAPE a good SPX short timer? | **No** | CAPE≥28: **14.3%** bear hit at 12M, avg SPX **+19.5%** — valuation extreme but equities kept rallying in sample. | **Doubt:** Combo E uses CAPE≥28 as **structural** bearish context — should we stop interpreting high CAPE as a **timing** signal in reports? |
| Can we validate CPI thresholds? | **No** | **1** RARE event at 0.20pp; **0** EXTREME at 0.40pp. CPI DB from **2024** only. | **Doubt:** Do we backfill CPI surprise history before the 2024 pipeline, or wait **12–24 months** of live fires? |
| Did hostile slice block any proposed changes? | **Partial** | Computed in JSON appendix; final §4 verdicts weight combo role + n. CAPE/VXTS some null hostile cells when regime log missing. | **Doubt:** For events with **null** hostile excess, should criterion #4 count as pass, fail, or ignore? |

---

## 5. Phase P3 — Named combo gate sweeps

**What the spec asks:** Separately test whether combo **gate** thresholds (not just single variables) should move for Combos B, F, E, D at their validated horizons.

### 5a. Combo B (Capitulation) — 3M bullish

| | Detail |
|---|--------|
| **What we did** | Swept VIX (20/25/30), HY (350/400/450 bps), CFTC (10/15/20 pctile); 3-of-3 and 2-of-3 variants |
| **Results** | **Current 3-of-3** (VIX≥25, HY≥400 OR, CFTC≤15): **n=9**, **77.8%** hit, **+3.96%** excess. **2-of-3:** **n=41**, **75.6%**, **+2.15%**. |
| **Production** | CONFIG gates unchanged; detector HY **AND** vs sweep **OR** mismatch |

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Is strict 3-of-3 too rare historically? | **Partial** | **n=9** over ~36 years — fires are rare but strong. 2-of-3 gives **n=41** with similar hit. | **Doubt:** Should Combo B **WATCH** use 2-of-3 and **ACTIVE** stay 3-of-3, or is n=9 acceptable for a crisis-only combo? |
| Should production HY leg use OR like CONFIG? | **Open** | Sweep uses **OR** per CONFIG → n=9. `combo_detector` may still require **AND**. | **Doubt:** Align production detector to CONFIG OR for HY, or was AND intentional for stricter live firing? |

### 5b. Combo F (Recovery) — 6M bullish

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Keep SPX 3% above 50WMA? | **Yes** | **3%:** n=**42**, hit **85.7%**, excess **+3.15%**. **5%:** n=41, hit 85.4%, excess **+3.50%** (+0.35pp only). | **Doubt:** Is +0.35pp excess worth tightening to 5% for fewer marginal reclaims? |

### 5c. Combo E (Valuation extreme) — 12M bearish

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Keep CAPE≥28 + NFCI≤−0.3 + CFTC≥80? | **Yes** | CAPE≥28: n=22, **9.1%** bear hit, +5.96% excess. Loosening to 25 adds n but lowers hit. Tightening to 30/32 does not improve excess enough. | **Doubt:** Combo E bear hit is **~9%** — is 12M bearish the right framing, or should E be “valuation risk context” not a down bet? |

### 5d. Combo D (FOMO top) — 5D bearish

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Should any Combo D gate change? | **No** | All variants **below 60%** down hit; PW excess **negative** vs +0.5% 5D benchmark. Current VXTS≥1.10 / CFTC≥85 / VIX≤18 tied for best among tested. | **Doubt:** Is **5D** the wrong horizon — should D be tested at **1–2 weeks** instead of 5 trading days? |

---

## 6. Phase P4 — Report, raw exports, and recommendations

**What the spec asks:** Document findings in a report; flag variables clearing all four success criteria; export audit data.

### P4 — Experiment status

| | Detail |
|---|--------|
| **What we did** | `threshold_validation_report.md` + PDF; §4a/4b summary tables; appendix per variable; CSV exports |
| **Results** | Report **~1,766** lines; §4a CSV **4,169** events; §4b CSV **3,726** events |
| **Production** | No CONFIG edits committed as part of report |

**Priority recommendations from report §6:**

| Priority | Recommendation | Evidence |
|----------|----------------|----------|
| 1 | **WTI down-side:** consider `down_15pct` RARE/EXTREME for down leg only | +0.8–1.6pp excess, ~73% bull hit 6M, n=30 |
| 2 | **Combo B:** keep 3-of-3 CONFIG; consider 2-of-3 for WATCH | n=9 vs n=41 |
| 3 | **Combo F:** keep 3% above 50WMA | Optional 5% for +0.35pp only |

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Did any variable clear all four mechanical success bars? | **Partial** | **WTI** flagged in early SUMMARY (`change_justified=true` for down_15 vs up_6). Final §4 uses analyst verdicts — only WTI down is **Consider**; rest **Keep** or **Defer**. | **Doubt:** Should we still require all four bars for CONFIG edits, or is the analyst verdict column the new standard? |

---

## 7. Deliverables checklist (spec vs status)

| ID | Deliverable | Shadow / experiment | Production |
|----|-------------|---------------------|------------|
| **P1** | Normalize pctiles + fix F sweep | ✅ Done | DB updated |
| **P2** | `threshold_sweep_v2.py` + 12 JSONs + SUMMARY | ✅ Done | CONFIG unchanged |
| **P2** | Hostile-regime slice per band | ✅ In JSON appendix | Not in nightly UI |
| **P3** | Combo B/F/E/D gate JSONs | ✅ Done | Combo gates unchanged |
| **P4** | `threshold_validation_report.md` + PDF | ✅ Done | N/A |
| **P4** | Raw returns CSVs §4a/4b | ✅ Done | N/A |
| **—** | Apply WTI down_15pct to CONFIG | ⏳ Not done | Awaiting decision |
| **—** | Align `combo_detector` HY OR with CONFIG | ⏳ Not done | May explain live vs backtest gap |

---

## 8. Recommended build order (if implementing changes)

1. **Decide WTI directional split** with Rohit Sir (down_15% only vs keep symmetric ±6%).
2. **Align Combo B HY leg** in `combo_detector.py` with CONFIG OR if intended.
3. **Optional:** Combo B 2-of-3 WATCH promotion (product decision, not threshold math).
4. **Defer CPI** until more surprise history (or backfill).
5. **Leave** VIX, HY, CAPE, CURVE, GSR, NFCI, CNH, VXTS, WALCL, CFTC, Combo F/E/D gates at current CONFIG.

---

## 9. Doubts to ask Rohit Sir (consolidated master list)

| # | Doubt to ask Rohit Sir | Evidence from status |
|---|------------------------|----------------------|
| 1 | Should WTI CONFIG split into **directional** thresholds (down RARE at −15% 4wk, up RARE stay at ±6%)? | down_15pct: n=30, 73.3% bull 6M, +0.16% excess vs down_6pct n=112, −0.65% excess. Symmetric ROC may be wrong for Combo C. |
| 2 | Is **n=9** acceptable for Combo B strict 3-of-3, or should WATCH promote at 2-of-3 (n=41, 75.6% hit)? | CB_VIX_25 current: n=9, 77.8%, +3.96%. CB_2of3: n=41, +2.15%. |
| 3 | Should production `combo_detector` use **HY OR** (OAS≥400 or pctile≥80) to match CONFIG and the sweep? | Sweep n=0 on 3-of-3 before OR fix; n=9 after. Detector may still use AND. |
| 4 | Is high **CAPE** a timing signal or only **structural risk** for Combo E? | CAPE≥28: 14.3% bear hit 12M, avg SPX +19.5%; PW excess misleading when SPX rallies. |
| 5 | When do we revisit **CPI** thresholds — after how many live surprise events? | CPI DB from 2024; RARE n=1, EXTREME n=0 at 0.20/0.40pp. |
| 6 | Is **Combo D** tested on the wrong horizon (5D vs 1–2 weeks)? | No gate reaches 60% down hit; all negative PW excess at 5D. |
| 7 | How should **null hostile excess** count in criterion #4? | `macro_regime_log` 1,919 rows; some CAPE/VXTS events outside hostile window. |
| 8 | Tighten Combo F from **3% to 5%** above 50WMA for +0.35pp excess? | 3%: n=42, 85.7%, +3.15%. 5%: n=41, 85.4%, +3.50%. |
| 9 | Should **Combo E** stay bearish at 12M when bear hit is only **~9%**? | CE_CAPE_28: n=22, 9.1% down, +5.96% excess 12M. |
| 10 | Re-run **testingv1** threshold conclusions after pctile migration? | 220 rows were wrong scale; old F sweep 13/22 bands n=0. |
| 11 | Keep **CAPE low≤12** EXTREME when **zero** first-crossings since 1990? | Symmetry with low_16 RARE; n=0 at ≤12. |
| 12 | Is **GSR** useful as a standalone SPX timer at 3M, or only as risk-off context in combos? | Best bear hit ~35% at looser 3% band; excess worse than CONFIG 5%. |

---

## 10. Key artifact index

| File | Purpose |
|------|---------|
| `testing/macro_th_exp/testingv2/threshold_validation_plan.md` | Experiment design and sweep bands |
| `testing/macro_th_exp/testingv2/threshold_validation_report.md` | Full results, §4 verdicts, appendix |
| `testing/macro_th_exp/testingv2/threshold_validation_report.pdf` | PDF export of report |
| `testing/macro_th_exp/testingv2/testingv2_status.md` | Phase P1–P4 execution tracker |
| `macro_intelligence/CONFIG.yaml` | Production thresholds under test |
| `macro_intelligence/analysis/regime_v2_experiments/threshold_sweep_v2/*_sweep.json` | Per-variable sweep output (12 files) |
| `macro_intelligence/analysis/regime_v2_experiments/threshold_sweep_v2/SUMMARY.json` | Cross-variable rollup |
| `macro_intelligence/analysis/regime_v2_experiments/threshold_sweep_v2/COMBO_*_sweep.json` | Combo B/F/E/D gate sweeps |
| `testing/macro_th_exp/testingv2/section_4a_rare_threshold_raw_returns.csv` | 4,169 RARE event-level returns |
| `testing/macro_th_exp/testingv2/section_4b_extreme_threshold_raw_returns.csv` | 3,726 EXTREME event-level returns |
| `scripts/threshold_sweep_v2.py` | Main sweep script |
| `scripts/generate_section4_tables.py` | §4a/4b summary table generator |

---

## 11. How this relates to work already done

Testing v2 **closes the loop** on a known data bug (0–1 vs 0–100 percentiles) and replaces pctile-only sweeps with **CONFIG-faithful** first-crossing backtests. Production nightly runs still use the same `CONFIG.yaml` values unless you apply the **WTI down-side** or **Combo B** changes above. This doc is the plain-English map; the report appendix has every band × horizon if you need to audit a single number.

---

*Understanding doc generated from `threshold_validation_plan.md` + `threshold_validation_report.md` + `testingv2_status.md`.*
