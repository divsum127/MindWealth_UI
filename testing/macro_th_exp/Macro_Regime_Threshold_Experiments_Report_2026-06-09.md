# Macro Regime and Threshold Experiments Report

I created an experiment pipeline macro regime v2 experiment suite and spent the last few days reconciling those results against Rohit sir's consolidated plan PDF. I have added answers to the questions that you had asked along with my doubts for you. 

<!-- **Sources:** shadow run via `scripts/run_regime_v2_experiment_suite.py`, artifacts in `macro_intelligence/analysis/regime_v2_experiments/`, SSI validation in `testing/ssi_th_exp/SSI_OPEN_QUESTIONS_SUMMARY.md`. -->

---

<!-- ## The short version

| Track | Run date | Status | Production wired? |
|-------|----------|--------|-------------------|
| Regime v2 Parts A–H + FM | 2026-06-06 | Shadow complete | No (legacy labels in nightly PDF) |
| SSI threshold tests 1–17 | 2026-06-04 to 2026-06-07 | 17/17 classified; 7 DATA_FIXED, 10 CREDIBLE | SSI live; thresholds validated separately |
| Nightly briefing fixes | 2026-06-09 | Live in engine | Yes (combo metadata, WALCL, PDF tables) |

| Deliverable | Shadow | GO? | Blocker |
|-------------|--------|-----|---------|
| A: 5 regime dimensions | 1,901 Fridays | GO shadow | PIVOTING n=27; prompt not updated |
| B: TWY_ROC + dual pctiles | TWY pass; B4 fail | GO with CONFIG fix | 4 window mismatches |
| C: Emission vectors | 8,805 rows | GO | Daily job not wired |
| D: HMM | Prototype only | DEFER | No hit-rate gain; 0mo live vectors |
| E: Cancel probability | Combo C MC built | GO | Not on briefing |
| F: Quant regime defs | F2/F2a pass; F4 grid | GO (F4 mechanism only) | F1 Oct 2022 misfire |
| G: Persistence | G1/G2 tested | GO | Not in briefing |
| H: 298-combo pipeline | 132 survivors, 62 promo candidates | GO | Tavila step skipped; legacy regime tags |

--- -->

## Part A: Five regime dimensions

### A1: fed_cycle (7 states → 4 states)

| Question | Answered? | Answer |
|----------|-----------|--------|
| Does 4-state collapse give enough observations per state? | Partially | TIGHTENING 763 (40.1%), EASING 727 (38.2%), EASY 384 (20.2%). All exceed ≥30 obs. PIVOTING = 27 (1.4%). |
| Is any state degenerate? | Mostly yes | No state >80% dominance. PIVOTING statistically thin. |
| Can we ship v2 fed_cycle to production? | No | Shadow labels exist; production still uses legacy 7-state. |

**Doubt for Rohit sir:** PIVOTING has only 27 Fridays. Merge into EASING, widen the definition, or add PAUSING as a fifth state? Fed is currently on hold with no v2 label (job tracker T-01).

### A2: curve_regime (4 states + fiscal caveat)

| Question | Answered? | Answer |
|----------|-----------|--------|
| Does fiscal deficit >5% weaken inversion signal? | Directionally yes | 13 inverted episodes. No-offset (deficit ≤5%): n=12, 41.7% bearish 3m. Fiscal-offset: n=1, 0% bearish (likely 2022–23). |
| Are 4 curve states stable in backfill? | Yes | All four appear. Oct 2022: 14 inverted weeks via F2 rule. |

**Doubt for Rohit sir:** Fiscal-offset bucket has n=1. Cannot confirm 2022–23 tagging statistically. 

### A3: val_regime + CAPE velocity

| Question | Answered? | Answer |
|----------|-----------|--------|
| Does CAPE velocity add signal beyond static level? | Not yet | Level extreme 3m: n=863, 74.2% SPX up, avg +3.08%. Velocity rank delta 6m: n=531, 74.6% up, avg +2.68%. Hit rates differ 0.4 pp only. |
| Does triple storage help Combo E? | Partially | Combo E high-CAPE 6m: n=507, 79.1% hit, avg +6.41%. Moderate-CAPE bucket: n=0. |

**Doubt for Rohit sir:** Fresh cross into EXTREME CAPE: n=0 with current definition. Cannot test "fresh crossing vs sitting at extreme for 3 years" yet.

### A4: geo_overlay (6 → 3 states)

| Question | Answered? | Answer |
|----------|-----------|--------|
| Is 3-state geo more reproducible than 6-state? | Yes (qualitatively) | NEUTRAL 1,855 (97.6%), ELEVATED_RISK 25 (1.3%), CRISIS 21 (1.1%). |
| Does geo slice combo performance meaningfully? | No | FM geo slices mostly n<10. CRISIS n=2, ELEVATED_RISK n=1 at extreme-short FM. |

### A5: liquidity (2 → 4/9 states)

Rohit sir's plan moves liquidity from binary GLOBAL_EASY / GLOBAL_TIGHT to a **2×2 grid**: easy vs tight **level** (from NFCI) crossed with improving vs tightening **direction** (from WALCL month-over-month change). That is the right design. What the shadow backfill showed is that real data does not always land in one of four clean quadrants.

**How the 9 states are built** (`regime_v2_shadow.py`):

| Input | Rule | Output |
|-------|------|--------|
| NFCI ≤ −0.3 | Easy financial conditions | Level = EASY |
| NFCI ≥ +0.3 | Tight financial conditions | Level = TIGHT |
| Between −0.3 and +0.3 | Neither extreme | Level = **NEUTRAL** (not in plan's 2×2) |
| WALCL MoM > +0.3% | Balance sheet expanding | Direction = IMPROVING |
| WALCL MoM < −0.3% | Balance sheet shrinking (QT) | Direction = TIGHTENING |
| Between −0.3% and +0.3% | No clear move | Direction = **FLAT** (not in plan's 2×2) |

Label format is `{LEVEL}_{DIRECTION}`, giving **3 levels × 3 directions = 9 states**. The plan's pure 4-state grid would require every Friday to be EASY or TIGHT (no NEUTRAL) and IMPROVING or TIGHTENING (no FLAT).

**Full backfill distribution (1,901 Fridays):**

| State | Count | % of sample | Passes ≥30 obs? |
|-------|-------|-------------|-----------------|
| EASY_FLAT | 746 | 39.2% | Yes |
| EASY_IMPROVING | 403 | 21.2% | Yes |
| EASY_TIGHTENING | 287 | 15.1% | Yes |
| NEUTRAL_FLAT | 219 | 11.5% | Yes |
| NEUTRAL_TIGHTENING | 72 | 3.8% | Yes |
| NEUTRAL_IMPROVING | 62 | 3.3% | Yes |
| TIGHT_IMPROVING | 50 | 2.6% | Yes |
| TIGHT_TIGHTENING | 32 | 1.7% | Yes |
| TIGHT_FLAT | 30 | 1.6% | Yes |

Worth noting: **50.8%** of all Fridays sit in a `*_FLAT` direction bucket (965/1,901), and **26.4%** are `NEUTRAL_*` level (501/1,901). That is why the backfill produced 9 labels, not 4. Forcing a pure 2×2 would misclassify roughly half the history whenever WALCL MoM is near zero (common during QT pause, post-QE plateau, or noisy weekly prints).

**Does WALCL direction add signal?** I sliced FM positioning events by liquidity_v2 at the 3m horizon:

| Band | Liquidity slice | n | SPX up 3m | Notes |
|------|-----------------|---|-----------|-------|
| Extreme short FM (<15th) | EASY_FLAT | 6 | 50.0% | No clear edge |
| Extreme short FM | EASY_IMPROVING | 10 | 60.0% | Similar to FLAT |
| Extreme short FM | EASY_TIGHTENING | 10 | 50.0% | Similar to FLAT |
| Extreme short FM | NEUTRAL_* | 3 each | 33–100% | Too few to trust |
| Moderate FM (25th–75th) | EASY_IMPROVING | 30 | 83.3% | Highest slice |
| Moderate FM | EASY_FLAT | 20 | 70.0% | |
| Moderate FM | EASY_TIGHTENING | 23 | 65.2% | ~18 pp below IMPROVING |
| Moderate FM | TIGHT_* | 1–2 | n/a | Unusable |

Direction is **encoded correctly** in the labels (EASY_TIGHTENING vs EASY_IMPROVING are distinct periods). But at the FM-event level, hit rates within the EASY level cluster around 50–60% for extreme short and 65–83% for moderate. The spread is not large enough yet to treat liquidity direction as a standalone combo filter. TIGHT_* buckets are too thin (n=30–50 in the full backfill, n=1–2 at FM events) for any regime-conditional conclusion.

| Question | Answered? | Answer |
|----------|-----------|--------|
| Does WALCL direction distinguish tightening vs improving? | **Built yes; signal unproven** | Labels separate IMPROVING/TIGHTENING/FLAT using WALCL MoM ±0.3% thresholds. Distribution shows direction matters descriptively (EASY_IMPROVING 403 vs EASY_TIGHTENING 287 Fridays). FM slices do not show a reliable performance gap at event level. |
| Is 4-state 2×2 enough or do we need FLAT variants? | **Yes: keep 9 for labels, collapse to 4 for analytics** | See recommendation below. |

**My answer on 4 vs 9 states (from backfill + logic):**

I recommend a **two-tier approach**, not picking one number for everything:

1. **Production regime storage and classifier output: use 9 states.** Forcing 4 would mislabel ~50% of Fridays where WALCL direction is flat or NFCI is in the neutral band. The 9-state scheme is honest to the data and matches how `liquidity_v2()` is already implemented. Every cell passes the ≥30 obs rule in the full backfill (thinnest is TIGHT_FLAT at n=30).

2. **Combo hit-rate tables, beta filter, and briefing footnotes: collapse to 4 pure 2×2 buckets** when slicing performance, because 9-way slices are too thin at the event level (FM extreme short: n=6–10 per EASY cell; TIGHT cells nearly empty).

**Collapse rules I would use for analytics:**

| 9-state label | Collapsed 4-state bucket |
|---------------|--------------------------|
| EASY_IMPROVING | EASY + IMPROVING |
| EASY_TIGHTENING | EASY + TIGHTENING |
| EASY_FLAT | EASY + IMPROVING if prior 4wk WALCL trend positive, else EASY + TIGHTENING (or hold FLAT as "no direction call") |
| NEUTRAL_IMPROVING | EASY + IMPROVING (NFCI < 0 → lean easy) |
| NEUTRAL_TIGHTENING | EASY + TIGHTENING (or TIGHT + TIGHTENING if NFCI > 0) |
| NEUTRAL_FLAT | NEUTRAL level: split by NFCI sign or exclude from 4-way slice |
| TIGHT_IMPROVING | TIGHT + IMPROVING |
| TIGHT_TIGHTENING | TIGHT + TIGHTENING |
| TIGHT_FLAT | TIGHT + dominant recent WALCL trend |

3. **Do not drop FLAT or NEUTRAL from storage.** FLAT is economically real (QT on hold, balance sheet plateau, weekly WALCL noise). NEUTRAL NFCI is real (mildly loose conditions that do not clear the ±0.3 easy/tight gate). Dropping them would recreate the old binary GLOBAL_EASY/TIGHT problem under a new name.

<!-- 4. **What would change my mind:** If a re-run after CONFIG B4 fixes (WALCL → full-history window, now live in production nightly as of 2026-06-09) shows IMPROVING vs TIGHTENING splits Combo F or D hit rates by ≥15 pp with n≥20 per cell, I would promote direction to a conviction modifier. Current data does not support that. -->

**Remaining doubt for Rohit sir:** 
- What is the final decision on the 4 vs 9 states?
- The collapse rules for NEUTRAL_FLAT and EASY_FLAT are judgment calls. Do you prefer NEUTRAL level folded into EASY (majority of NEUTRAL Fridays have NFCI slightly negative) or kept as a third level in the classifier prompt only?

<!-- ### Deliverable A summary

| Question | Answered? | Answer |
|----------|-----------|--------|
| Report label distribution (no degenerate states)? | Done | Full distributions logged. PIVOTING flagged thin. |
| Update production Section 5.2 classifier prompt? | Not done | Shadow logic runs; live prompt unchanged. |
| Re-run backfill after prompt finalization? | Not done | Initial backfill complete 2026-06-06. |

--- -->

## Part B: 14th variable and history windows

### B1: TWY_ROC (#14)

| Question | Answered? | Answer |
|----------|-----------|--------|
| Did TWY_ROC call Apr 2025 bottom before lagging fed labels? | Yes | Apr 7 2025: TWY_ROC −0.55pp DOVISH (DGS2 3.73%). Legacy fed still TIGHTENING/PAUSING. |
| Are ±0.30pp bands validated? | Partially | Anchor passes (well below −0.30). No full historical band sweep. |
| Is TWY_ROC excluded from combos? | Yes | 298 signatures from 13 vars only. 13,089 generic fires without TWY_ROC leg. |

### B2: Dual percentile storage

| Question | Answered? | Answer |
|----------|-----------|--------|
| Does dual percentile storage work? | Yes | 14,457 rows with both unconditional + regime pctile. 0 unconditional-only rows. |
| Does <50 fallback logic work when needed? | Not tested | 0 fallbacks in backfill. Every fed_cycle had ≥50 obs in practice. |
| Are history windows correct per variable? | No | 4 FAIL: HY/VIX/VXTS configured `full` (plan wants `rolling_3y`); WALCL was `rolling_3y` (plan wants `full`). WALCL fixed in production nightly 2026-06-09 but B4 audit not re-run. |

### B3: Triple CAPE storage

| Question | Answered? | Answer |
|----------|-----------|--------|
| Which CAPE storage combo predicts best? | Preliminary: level | Level wins avg return by +0.40pp. Not a rigorous multivariate test. |
| Does velocity beat level for Combo E? | No clear win | High-CAPE Combo E 6m strong regardless of velocity tier. |

### Deliverable B summary

TWY anchor **PASS**. Dual storage **PASS**. Window audit **FAIL** (4 vars). TWY not in nightly pull yet.

---

## Part C: Emission probability vectors

| Question | Answered? | Answer |
|----------|-----------|--------|
| Can we store 14 daily percentile vectors? | Yes | 8,805 daily rows backfilled. |
| Do sub-threshold readings accumulate useful signal? | Maybe | VIX 65th–79th pctile (below RARE): n=7, 85.7% positive 3m. Too small for statistical gate. |
| Do vectors detect shifts earlier than binary? | No (so far) | 864 VIX RARE events: median lag binary vs vector = 0.0 days. |
| When can HMM training start? | Not yet | Need 6+ months live vectors. Clock at 0 months. |

**Doubt for Rohit sir:** Prototype HMM did not improve Combo B (−1.2 pp) or D (−1.9 pp). Is ~Dec 2026 still the right HMM target?

---

## Part D: HMM layer

| Question | Answered? | Answer |
|----------|-----------|--------|
| Can HMM posteriors feed classifier as soft prior? | Not in production | Prototype: Jun 2026 sample Risk-On 42.9%, Risk-Off 23.8%, Transition 33.3%. |
| Does HMM detect shifts before binary thresholds? | Not validated | D3 shift-timing backtest not completed. |
| HSMM for combo duration exit probability? | Not started | Correctly deferred. |
| Does HMM improve Sharpe/win rate/drawdown? | No on win rate | Combo B: 79.8% → 78.6% with Risk-Off filter (n=56). Combo D: 28.1% → 26.2% (n=103). Sharpe/drawdown not reported. |
| When is production HMM ready? | ~Dec 2026 earliest | Live C1 not wired. |

---

## Part E: Cancel probability

| Question | Answered? | Answer |
|----------|-----------|--------|
| Can we compute Combo C cancel prob via MC? | Yes | 10,000 GBM paths. WTI leg 8.31%, CPI leg 27.04%, combined 2.25%. |
| Is probability calibrated to history? | No | 4 historical episodes, 0 realized cancels vs 2.25% predicted. |
| Live cancel % on briefing? | Not yet | Function built, not displayed. |
| Combo D/F/G cancel formulas? | Documented only | Only Combo C implemented as reusable function. |

---

## Part F: Formal regime definitions

### F1: TIGHTENING-LATE

| Question | Answered? | Answer |
|----------|-----------|--------|
| Does F1 match Oct 2022? | No | tightening_late_f1 = False. FFR ~3.25% below >3.5% threshold. Legacy was HIKING_LATE. hiking_period_f3 = true. |
| All fed states have numeric rules? | No | F1 proposed for TIGHTENING-LATE only. Full 4-state quant defs not validated. |

### F2: INVERTED

| Question | Answered? | Answer |
|----------|-----------|--------|
| Reproducible INVERTED from T10Y2Y? | Yes (shadow) | T10Y2Y < 0 for ≥4 consecutive weeks. Oct 2022: 14 inverted weeks. |
<!-- | Aligned with Ahil's steepening gate? | Pending | Same T10Y2Y source.  | -->

### F2a: STEEPENING

| Question | Answered? | Answer |
|----------|-----------|--------|
| STEEPENING detectable from numeric rules? | Yes (shadow) | ≥+15 bps/4wk RARE, ≥+40 EXTREME. |
<!-- | Classifier uses numbers not context? | Not in production | Production still partly Claude-inferred for curve. | -->

### F4: Steepening-of-inversion short grid

| Trough | Steepen 4wk | n | SPX down 3m |
|--------|-------------|---|-------------|
| −50 bps | +15 bps | 17 | 17.6% |
| −50 bps | +40 bps | 4 | 25.0% |
| −80 bps | +15 bps | 9 | 33.3% |
| −80 bps | +40 bps | 2 | 0% |

| Question | Answered? | Answer |
|----------|-----------|--------|
| −50 vs −80 trough? | Grid run, no stat winner | −80/+15 best cell (33.3%, n=9) but below 55% bar. |
| +15 vs +40 steepening? | +15 wins on n | +40 cells n=2–4, meaningless. |
| Can F4 be promoted on backtest alone? | No | Best 33.3% vs ≥80% naming gate. Mechanism+analog only. |
<!-- | Ahil alignment? | Pending | Thresholds provisional. | -->

---

## Part G: Persistence signals

### G1: SEVEN_WEEK_GRIND

| Question | Answered? | Answer |
|----------|-----------|--------|
| Is 7-week grind a standalone short? | No | n=2 episodes. Both negative 6m (avg −5.91%). standalone_short_ok = false. Matches plan (Combo E amplifier). |
| Wire as Combo E amplifier? | Built, not live | persistence_fires table in shadow. Briefing does not show grind status. |

### G2: VIX_SUPPRESSED

| Question | Answered? | Answer |
|----------|-----------|--------|
| Does VIX suppressed precede vol spike ~50%? | No | n=1,973 periods. Lead rate to VIX>25 within 35d: **8.5%** (168/1,973). Plan claimed ~50%. |
| Precursor for Combo D? | Directionally yes, weakly | ~91.5% false watches if treated as sell trigger. Correct framing: watch flag only. |

---

## Part H: Nine-step combo discovery pipeline

| Step | Question | Answered? | Answer |
|------|----------|-----------|--------|
| 1 Detection | 298 combos scanned? | Yes | 225 with ≥1 fire. 13,089 total generic fires. |
| 2 Forward returns | SPX 1m–12m stored? | Yes | Complete in pipeline JSON. |
| 3 Regime tagging | v2 labels used? | Partially | **Legacy** regime tags on existing combo_fires. |
| 4 Surfacing | ≥3 fires, ≥60% HR? | Yes | 187 surfaced. |
| 5 Beta filter | Beat hostile regimes? | Yes | 132 pass (≥55% and ≥60% both reported). |
| 6 Directionality | ≥2 of 5 dimensions? | Yes | 132 pass (same set as beta). |
| 7 Tavila story | Economic narrative? | No | use_claude=False. Skipped. |
| 8 Naming gate | ≥5 fires, ≥80% HR? | Partially | 62 promotion candidates. **0 promoted** to new named combos. |
| 9 Output table | Cancel prob attached? | No | Part E not wired to live output per combo. |

**Pipeline funnel:**

| Stage | Count |
|-------|-------|
| Signatures | 298 |
| With fires | 225 |
| Surfaced | 187 |
| Beta + directionality pass | 132 |
| Promotion candidates | 62 |
| Promoted to production names | 0 |

**Doubts for Rohit sir:** Beta 55% or 60% for 62 candidates? Re-tag with v2 regimes before final review? Run Tavily step 7 before any promotion?

---

## Part I: Sample-size (covered in brief)

| Rule | Threshold | Observed in run |
|------|-----------|-----------------|
| Regime-conditional percentile minimum | ≥30 obs | PIVOTING fails (n=27) |
| Fallback to unconditional | <50 obs | 0 fallbacks triggered |
| Statistical gate | ≥5 fires | Applied to FM bands, unnamed combos |
| Mechanism gate | 2–4 fires OK | F4, Combo B washout |

Two evidence standards are working as designed: F4 correctly stays on mechanism+analog because win rates are too low for statistical promotion.

---

## FM and regime isolation (Rohit sir's additional ask on WhatsApp)

### Extreme short FM (<15th pctile)

| Test | n | SPX up 3m | FM wrong / contrary |
|------|---|-----------|---------------------|
| Combo B fires (incl. WATCH) | 89 | 79.8% | Validates direction vs Rohit sir's 87.5% (7/8) |
| Raw FM <15 crossings | 35 | 60.0% | Weaker than headline claim |
| EASY fed_cycle slice | 6 | 83.3% | Strongest regime |
| FLAT curve slice | 6 | 33.3% | Signal breaks here |

| Question | Answered? | Answer |
|----------|-----------|--------|
| Is extreme-short FM a contrary indicator? | Conditionally yes | Works best with full Combo B legs, not FM alone. |
| Why 89 vs "8 confirmed"? | Explained | DB counts WATCH rows with partial legs. Confirmed-only slice not yet run (open P0 task). |

### Extreme long FM (>85th pctile)

| Horizon | Raw FM: SPX down | Raw FM: wrong (SPX up) | Combo D: wrong |
|---------|------------------|------------------------|----------------|
| 1 week | 41.0% | 59.0% | 61.5% |
| 3 months | 17.9% | 82.1% | 71.9% |

| Question | Answered? | Answer |
|----------|-----------|--------|
| FM wrong 72–85% at short horizons? | Partially | Backtest shows ~59–62%, roughly 10–20 pp below Rohit sir's band. |
| Signal degrades at 3m? | Yes (correction doesn't happen) | 82% FM wrong at 3m for raw band. |
| Regime impact on Combo D? | Yes | HIKING_LATE 18.3% SPX down 3m (n=197) vs CUTTING_LATE 43.2% (n=155). |

### Moderate FM (25th–75th)

| Metric | Value |
|--------|-------|
| Crossings | 84 |
| SPX up 3m | 76.2% |
| Avg 3m return | +3.15% |

Rohit sir was right to be skeptical. This looks like equity drift, not an independent FM edge. No alpha from fading or following moderate FM.

### Named combos A–G by fed cycle (3m)

| Combo | Dir | n | Overall hit | Best slice | Worst slice |
|-------|-----|---|-------------|------------|-------------|
| A | Bear | 174 | 23% down | CUTTING_LATE 50% (n=26) | QE 20% (n=112) |
| B | Bull | 89 | 79.8% up | HIKING_LATE 83% (n=48) | CUTTING_LATE 76% (n=41) |
| C | Bull | 4 | 0% up | n too small | n/a |
| D | Bear | 452 | 28% down | CUTTING_LATE 43% | HIKING_LATE 18% |
| E | Bear | 507 | 20% down | Flat ~14–27% | QE 14% |
| F | Bull | 704 | 74.9% up | QE 82% (n=212) | CUTTING_LATE 64% |
| G | n/a | 0 | No fires | n/a | n/a |

| Question | Answered? | Answer |
|----------|-----------|--------|
| Does regime materially change combo performance? | Yes | D: 2.4× spread HIKING vs CUTTING. F: 18 pp QE vs CUTTING spread. |
| Full 5-dimension slicing done? | Partially | fed_cycle reliable; other dims mostly n<10. |
| Combo C working? | No in sample | 4 fires, 0% 3m up, avg +17.8% (market rose against signal). |

---

<!-- ## SSI threshold experiments (parallel track)

Separate from the regime PDF but part of the same "threshold experiments" mandate. I fixed the SSI history bottleneck on 2026-06-06 (NAAIM backfill + NaN gate fix): history went from 83 days to 2,565 rows (~7 years, 2019-06-07 to 2026-06-06).

| Test | Name | Status | Key finding |
|------|------|--------|-------------|
| 1 | Long gate sweep | DATA_FIXED | Validated with 7y history |
| 2 | Short gate sweep | DATA_FIXED | At SSI≥0.85, SPX down only **26%** of time (weak short gate) |
| 3 | CFTC squeeze grid | CREDIBLE | **68%** 4w win as long signal |
| 4 | Liquidity exit grid | CREDIBLE | Credible on 16y CFTC data |
| 8 | HYG/LQD delta | CREDIBLE | −3% threshold: **77.4%** 1w win, avg +3.43% 4w |
| 9 | Z-score vs percentile | DATA_FIXED | Part of emission-vector philosophy alignment |
| 12 | Bollinger + SSI | DATA_FIXED | Breadth extended to 2015; re-run possible |
| 13 | Stochastic/McClellan | CREDIBLE | McClellan now 2014+ after breadth fix |

| Classification | Count |
|----------------|-------|
| CREDIBLE | 10 |
| DATA_FIXED | 7 |
| BLOCKED | 0 |

SSI thresholds and Runic RARE/EXTREME tiers remain separate systems unless explicitly cross-wired (e.g. `ssi_multiplier`).

---

## Master Q&A closure (plan §6 + §15)

| # | Question | Answered? | Answer |
|---|----------|-----------|--------|
| 1 | TWY_ROC ±0.30pp bands | Partial | Apr 2025 pass. Full sweep not done. |
| 2 | F4 trough/steepen grid | Partial | Best 33.3% (n=9). Mechanism only. |
| 3 | Apr 2025 DGS2 vs fed_cycle | Yes | TWY DOVISH, legacy fed TIGHTENING. |
| 4 | Dual pctile <50 fallback | Yes (built) | 0 fallbacks in backfill. |
| 5 | Beta 55% vs 60% | No | Both in JSON. Rohit decision pending. |
| 6 | 2-of-3 vs 3-of-3 | Partial | Diagnostic only. |
| 7 | 6mo before HMM | Deferred | Clock at 0. Prototype no gain. |
| 8 | T10Y2Y vs Ahil | No | Ahil review pending. |
| 9 | Classifier prompt update | No | Pending sign-off. |
| 10 | Rohit FM Q&A | Yes | See FM section above. Partial validation. |

--- -->

<!-- ## What I'd change based on this

1. Re-slice Combo B as **confirmed-only (3/3 legs ACTIVE)** before the next Rohit sync. That probably closes most of the gap between 79.8% and 87.5%.
2. Fix CONFIG B4 windows (HY/VIX/VXTS → rolling_3y) and re-run the suite so shadow and production percentiles agree.
3. Wire cancel probability to the briefing for every active combo (Part E is built).
4. Hold HMM and new named combos until Rohit signs A/B/C and we have live emission vectors.
5. Add regime footnotes to combo hit rates in the PDF once v2 labels swap in.

That said, I would not rush the production regime swap. The shadow data is good enough for review; the briefing readers are still trained on CUTTING_LATE and HIKING_LATE labels.

--- -->

## My doubts and questions

- PIVOTING at n=27: is it a real state or label noise? Merging into EASING is pragmatic but might hide genuine pivot weeks.
- I have not stripped unconditional market drift from the moderate FM 76.2% result. Does it still look special vs buy-and-hold?
- Combo C has n=4 and 0% hit. Should we show C hit rates in the briefing at all until we have more completed episodes?
<!-- - Part H found 62 combos at ≥80% hit rate. How many are just re-labelling existing A–G leg combinations vs genuinely new structure? -->
- VIX suppressed lead rate is 8.5% vs plan's ~50%. Did we measure the wrong window, or is the plan figure an informal estimate that needs updating?
<!-- - Ahil's steepening-of-inversion work vs our F4 grid: are we measuring the same thing, or will that review surface a definitional mismatch? -->
- For production GO-live, what is the rollback plan if v2 fed_cycle labels confuse readers who have used legacy names for months?
- SSI short gate is weak at 26% SPX-down when SSI≥0.85. Is that acceptable for live sizing, or do we need a tighter gate despite the backtest?

<!-- ---

*Sources: `understanding_and_research/Macro_Regime_System_v2_Understanding.md`, `experiment_manifest.json`, `X-FM_all.json`, `X_COMBO_regime_slices.json`, `SSI_OPEN_QUESTIONS_SUMMARY.md`. Shadow run: 2026-06-06.* -->
