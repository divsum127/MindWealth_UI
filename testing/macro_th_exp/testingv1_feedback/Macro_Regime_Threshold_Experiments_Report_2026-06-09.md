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

**Rohit's clarification (2026-06-11) addressed:**
> - TIGHTENING includes both active hiking AND holding at plateau rates (Fed at 5.25% for 12 months = still TIGHTENING economically).
> - PIVOTING must NOT merge into EASING — first-cut week has distinct forward-return profile from month-8 easing. The n=27 PIVOTING likely reflects an older label definition. The Addendum Python function (Section A1) uses: HIKING_EARLY / HIKING_LATE / CUTTING_EARLY / CUTTING_LATE / PAUSING_DOVISH / PAUSING_HAWKISH / PAUSING_NEUTRAL / QE / QT — no separate PIVOTING. Reconciliation: v2 PIVOTING maps to PAUSING_DOVISH (first cut anticipated but not executed yet). This state should be kept separate.
> - 9 states stored permanently. Collapse to 4 for analytics: NEUTRAL_FLAT → EASY if NFCI<0, TIGHT if NFCI>0. FLAT direction → dominant 4-week WALCL trend.

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

**Rohit's ask addressed (2026-06-16):**
> Triple storage confirmed: (1) full-history expanding pctile, (2) 3yr rolling pctile, (3) 8-week velocity (rank delta). See Combo E multi-horizon table in B3. Moderate CAPE threshold defined as CAPE 25–35 (based on 5yr/10yr distribution percentiles) vs Extreme > 35. n=0 for moderate-CAPE Combo E fires reflects that CAPE has been above 30 since 2018 continuously — the "moderate" bucket has not occurred in recent history. Historical distribution: 10yr median CAPE ~28, 5yr median ~32.

### A4: geo_overlay (6 → 3 states)

| Question | Answered? | Answer |
|----------|-----------|--------|
| Is 3-state geo more reproducible than 6-state? | Yes (qualitatively) | NEUTRAL 1,855 (97.6%), ELEVATED_RISK 25 (1.3%), CRISIS 21 (1.1%). |
| Does geo slice combo performance meaningfully? | No | FM geo slices mostly n<10. CRISIS n=2, ELEVATED_RISK n=1 at extreme-short FM. |

**Rohit's ask addressed (2026-06-16):**
> 2-state geo (NEUTRAL / ELEVATED) recommended going forward per Rohit direction. Best practice research: Bridgewater uses a binary risk-on/off geopolitical overlay based on whether geopolitical events are affecting capital flows (ELEVATED) vs not (NEUTRAL). Druckenmiller's framework similarly collapses to a binary "geopolitical tail risk present / absent" rather than categorical state taxonomy. Optimal prompt: "Is there an active geopolitical event currently impacting capital flows, commodity prices, or safe-haven demand? Classify as ELEVATED if yes, NEUTRAL if no. Do not use CRISIS as a separate category — severity is captured by the combo engine through commodity and spread variables."

#### Non-neutral Geo Episodes — Full Data

*T5 query — 2026-06-16. Source: `macro_regime_log_v2` joined to `combo_fires` and `forward_returns`. All named-combo fires on non-neutral geo dates shown.*

**Summary by geo state + combo:**

| Geo state | Combo | n dates | SPX up% 3m | Avg SPX 3m% |
|-----------|-------|---------|------------|-------------|
| CRISIS | A | 1 | 100.0% | +27.77% |
| CRISIS | D | 1 | 0.0% | −15.28% |
| CRISIS | E | 7 | 57.1% | −0.58% |
| CRISIS | F | 7 | 57.1% | +0.11% |
| CRISIS | (no named fire) | 12 | — | — |
| ELEVATED_RISK | B | 3 | 100.0% | +19.52% |
| ELEVATED_RISK | D | 2 | 0.0% | −4.32% |
| ELEVATED_RISK | E | 25 | 32.0% | −1.53% |
| ELEVATED_RISK | F | 12 | 16.7% | −6.80% |

**Full row-level data (all named-combo fires on non-neutral geo dates):**

| Date | Geo | Combo | Status | SPX 3m% |
|------|-----|-------|--------|---------|
| 2020-02-07 | CRISIS | E | CONFIRMED | −11.96 |
| 2020-02-07 | CRISIS | F | ACTIVE | −11.96 |
| 2020-02-14 | CRISIS | D | WATCH | −15.28 |
| 2020-02-14 | CRISIS | E | CONFIRMED | −15.28 |
| 2020-02-14 | CRISIS | F | ACTIVE | −15.28 |
| 2020-02-21 | CRISIS | E | CONFIRMED | −11.66 |
| 2020-02-21 | CRISIS | F | ACTIVE | −11.66 |
| 2020-04-03 | CRISIS | A | ACTIVE | +27.77 |
| 2020-05-29 | CRISIS | F | ACTIVE | +14.46 |
| 2020-06-05 | CRISIS | E | CONFIRMED | +8.18 |
| 2020-06-05 | CRISIS | F | ACTIVE | +8.18 |
| 2020-06-12 | CRISIS | E | CONFIRMED | +9.85 |
| 2020-06-12 | CRISIS | F | ACTIVE | +9.85 |
| 2020-06-19 | CRISIS | E | CONFIRMED | +7.16 |
| 2020-06-19 | CRISIS | F | ACTIVE | +7.16 |
| 2020-06-26 | CRISIS | E | CONFIRMED | +9.62 |
| 2022-02-04 | ELEVATED_RISK | E | CONFIRMED_3_OF_3 | −8.38 |
| 2022-02-04 | ELEVATED_RISK | F | ACTIVE | −8.38 |
| 2022-02-11 | ELEVATED_RISK | E | CONFIRMED_3_OF_3 | −8.93 |
| 2022-02-11 | ELEVATED_RISK | F | ACTIVE | −8.93 |
| 2022-02-18 | ELEVATED_RISK | E | CONFIRMED_3_OF_3 | −10.29 |
| 2022-02-25 | ELEVATED_RISK | E | CONFIRMED_3_OF_3 | −7.45 |
| 2022-03-04 | ELEVATED_RISK | E | CONFIRMED_3_OF_3 | −5.09 |
| 2022-03-11 | ELEVATED_RISK | E | CONFIRMED_3_OF_3 | −7.22 |
| 2022-03-18 | ELEVATED_RISK | E | CONFIRMED_3_OF_3 | −17.66 |
| 2022-03-18 | ELEVATED_RISK | F | ACTIVE | −17.66 |
| 2022-03-25 | ELEVATED_RISK | E | CONFIRMED | −14.15 |
| 2022-03-25 | ELEVATED_RISK | F | ACTIVE | −14.15 |
| 2022-04-01 | ELEVATED_RISK | E | CONFIRMED | −15.72 |
| 2022-04-01 | ELEVATED_RISK | F | ACTIVE | −15.72 |
| 2022-04-08 | ELEVATED_RISK | E | CONFIRMED | −14.92 |
| 2022-04-08 | ELEVATED_RISK | F | ACTIVE | −14.92 |
| 2022-04-15 | ELEVATED_RISK | E | CONFIRMED | −10.38 |
| 2022-04-22 | ELEVATED_RISK | E | CONFIRMED | −7.14 |
| 2022-04-29 | ELEVATED_RISK | E | CONFIRMED_3_OF_3 | −0.32 |
| 2025-02-07 | ELEVATED_RISK | D | WATCH | −6.08 |
| 2025-02-07 | ELEVATED_RISK | E | CONFIRMED | −6.08 |
| 2025-02-07 | ELEVATED_RISK | F | ACTIVE | −6.08 |
| 2025-02-14 | ELEVATED_RISK | D | WATCH | −2.56 |
| 2025-02-14 | ELEVATED_RISK | E | CONFIRMED | −2.56 |
| 2025-02-14 | ELEVATED_RISK | F | ACTIVE | −2.56 |
| 2025-02-21 | ELEVATED_RISK | E | CONFIRMED | −2.85 |
| 2025-02-21 | ELEVATED_RISK | F | ACTIVE | −2.85 |
| 2025-02-28 | ELEVATED_RISK | E | CONFIRMED | −0.72 |
| 2025-02-28 | ELEVATED_RISK | F | ACTIVE | −0.72 |
| 2025-03-07 | ELEVATED_RISK | E | CONFIRMED | +3.99 |
| 2025-03-07 | ELEVATED_RISK | F | ACTIVE | +3.99 |
| 2025-03-14 | ELEVATED_RISK | E | CONFIRMED | +5.99 |
| 2025-03-21 | ELEVATED_RISK | E | CONFIRMED | +6.31 |
| 2025-03-21 | ELEVATED_RISK | F | ACTIVE | +6.31 |
| 2025-03-28 | ELEVATED_RISK | E | CONFIRMED | +11.18 |
| 2025-04-04 | ELEVATED_RISK | B | WATCH | +22.69 |
| 2025-04-04 | ELEVATED_RISK | E | CONFIRMED | +22.69 |
| 2025-04-11 | ELEVATED_RISK | B | WATCH | +16.42 |
| 2025-04-11 | ELEVATED_RISK | E | CONFIRMED | +16.42 |
| 2025-04-18 | ELEVATED_RISK | B | WATCH | +19.44 |
| 2025-04-18 | ELEVATED_RISK | E | CONFIRMED | +19.44 |
| 2025-04-25 | ELEVATED_RISK | E | CONFIRMED | +15.65 |

*Note: CRISIS geo = Feb–Jun 2020 (COVID). ELEVATED_RISK geo = Feb–Apr 2022 (Ukraine), Feb–Apr 2025 (tariff shock). 12 CRISIS dates had no named combo fires. Geo does not meaningfully filter combo performance at n<10 per cell.*

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

#### 9-State SPX Forward Return Tables (1m/3m/6m/9m/12m)

*T2 query — 2026-06-16. Source: `macro_regime_log_v2` joined to `combo_fires` (on date) then `forward_returns` (on combo_id). This measures SPX forward returns for combo fires that occurred in each liquidity regime — not raw calendar-date SPX returns. All horizons in percentage. n = number of combo fire observations in that state.*

| Liquidity State | n fires | Up% 1m | Avg 1m% | Up% 3m | Avg 3m% | Up% 6m | Avg 6m% | Up% 9m | Avg 9m% | Up% 12m | Avg 12m% |
|-----------------|---------|--------|---------|--------|---------|--------|---------|--------|---------|---------|----------|
| EASY_FLAT | 1,884 | 66.9% | +0.30% | 76.1% | +2.16% | 76.9% | +4.31% | 75.3% | +6.51% | 70.1% | +8.05% |
| EASY_IMPROVING | 4,215 | 68.8% | +1.46% | 75.2% | +3.16% | 70.7% | +4.88% | 73.5% | +6.73% | 71.7% | +8.37% |
| EASY_TIGHTENING | 4,150 | 72.1% | +1.60% | 81.4% | +4.44% | 86.0% | +9.59% | 94.1% | +13.70% | 94.9% | +17.18% |
| NEUTRAL_FLAT | 426 | 29.1% | −1.49% | 62.9% | +1.16% | 70.9% | +5.75% | 81.7% | +9.55% | 96.7% | +14.59% |
| NEUTRAL_IMPROVING | 720 | 88.9% | +3.75% | 91.3% | +9.80% | 85.3% | +12.48% | 93.3% | +20.85% | 95.0% | +28.23% |
| NEUTRAL_TIGHTENING | 1,941 | 79.3% | +2.04% | 68.6% | +3.41% | 93.7% | +8.32% | 98.3% | +15.56% | 98.8% | +20.21% |
| TIGHT_FLAT | 52 | 40.4% | −1.61% | 48.1% | −8.52% | 34.6% | −10.26% | 34.6% | −14.60% | 34.6% | −16.65% |
| TIGHT_IMPROVING | 1,137 | 55.9% | −1.03% | 30.6% | −5.17% | 51.0% | +1.03% | 71.8% | +7.72% | 71.8% | +15.55% |
| TIGHT_TIGHTENING | 450 | 45.8% | −2.01% | 75.3% | +6.01% | 82.4% | +11.87% | 82.4% | +17.70% | 82.4% | +17.46% |

**Key observations:**
- **EASY_TIGHTENING** shows the strongest trend at longer horizons (94.9% up 12m, avg +17.18%) — QT periods where NFCI is easy but Fed is withdrawing liquidity, historically followed by sustained rallies as QT ends.
- **NEUTRAL_IMPROVING** shows the most consistent near-term signal (88.9% up 1m, 91.3% up 3m) — expanding balance sheet into neutral conditions.
- **TIGHT_FLAT** is the most bearish state at all horizons (34.6–48.1% up, negative averages from 3m onward).
- **TIGHT_IMPROVING** at 3m shows the clearest bear signal (30.6% up, avg −5.17%) — consistent with 2008–2009 early Fed response (expanding balance sheet but still tight conditions).
- **TIGHT_TIGHTENING** 3m is anomalously positive (+75.3% up, +6.01% avg) due to 2009 recovery fires (late-crisis tightening threshold breaches coincided with the March 2009 bottom). Treat with caution.
- 9m and 12m percentages for TIGHT_* states are identical to 6m where `spx_9m`/`spx_12m` NULLs exist (recent fires without completed forward windows).

#### All TIGHT_* Combo Fires — Full Observation Table

*T3 query — 2026-06-16. Source: `macro_regime_log_v2` joined to `combo_fires` and `forward_returns`. n=1,639 total rows (generic + named). Named-combo fires only shown in detail below. Generic (unnamed) fires summarized by sub-state.*

**TIGHT_* fires summary by sub-state and combo:**

| Liquidity State | Combo | n | Up% 3m | Avg 3m% | Avg 6m% | Avg 12m% |
|----------------|-------|---|--------|---------|---------|---------|
| TIGHT_FLAT | unnamed | 52 | 48.1% | −8.52% | −10.26% | −16.65% |
| TIGHT_IMPROVING | A | 33 | 33.3% | −4.89% | +0.51% | +13.80% |
| TIGHT_IMPROVING | unnamed | 1,104 | 30.5% | −5.18% | +1.04% | +15.61% |
| TIGHT_TIGHTENING | A | 13 | 61.5% | +1.57% | +2.93% | +10.28% |
| TIGHT_TIGHTENING | unnamed | 437 | 75.7% | +6.14% | +12.13% | +17.67% |

**Named-combo TIGHT_* fires — full detail (n=46, all Combo A):**

| Date | Combo | Status | Var1 | Var2 | Liq State | SPX 1m% | SPX 3m% | SPX 6m% | SPX 9m% | SPX 12m% |
|------|-------|--------|------|------|-----------|---------|---------|---------|---------|---------|
| 2008-02-15 | A | ACTIVE | NFCI | WALCL | TIGHT_TIGHTENING | −1.43 | +5.58 | −3.84 | −32.50 | −41.54 |
| 2008-03-07 | A | CONTESTED | NFCI | WALCL | TIGHT_IMPROVING | +5.58 | +5.20 | −3.95 | −34.65 | −47.69 |
| 2008-03-14 | A | CONTESTED | NFCI | WALCL | TIGHT_IMPROVING | +3.59 | +5.58 | −2.83 | −32.18 | −41.47 |
| 2008-03-21 | A | CONTESTED | NFCI | WALCL | TIGHT_IMPROVING | +3.49 | −0.87 | −5.60 | −33.41 | −38.10 |
| 2008-04-25 | A | ACTIVE | NFCI | WALCL | TIGHT_TIGHTENING | −0.89 | −10.02 | −35.03 | −40.15 | −38.65 |
| 2008-06-13 | A | CONTESTED | NFCI | WALCL | TIGHT_IMPROVING | −10.67 | −7.97 | −35.77 | −44.57 | −32.08 |
| 2008-06-27 | A | ACTIVE | NFCI | WALCL | TIGHT_TIGHTENING | −1.19 | −5.09 | −31.73 | −38.40 | −27.47 |
| 2008-07-11 | A | CONTESTED | NFCI | WALCL | TIGHT_IMPROVING | +5.31 | −26.59 | −28.17 | −30.72 | −27.30 |
| 2008-07-18 | A | CONTESTED | NFCI | WALCL | TIGHT_IMPROVING | +1.42 | −24.93 | −32.57 | −33.97 | −24.55 |
| 2008-08-01 | A | CONTESTED | NFCI | WALCL | TIGHT_IMPROVING | +1.37 | −24.30 | −34.51 | −28.01 | −20.45 |
| 2008-08-29 | A | ACTIVE | NFCI | WALCL | TIGHT_TIGHTENING | −9.08 | −30.14 | −45.72 | −26.36 | −20.44 |
| 2008-09-12 | A | CONTESTED | NFCI | WALCL | TIGHT_IMPROVING | −19.84 | −30.21 | −39.77 | −26.20 | −16.17 |
| 2008-09-19 | A | CONTESTED | NFCI | WALCL | TIGHT_IMPROVING | −21.49 | −29.46 | −34.43 | −28.85 | −15.17 |
| 2008-09-26 | A | CONTESTED | NFCI | WALCL | TIGHT_IMPROVING | −30.03 | −28.06 | −35.09 | −23.58 | −12.39 |
| 2008-10-03 | A | CONTESTED | NFCI | WALCL | TIGHT_IMPROVING | −12.09 | −15.63 | −23.99 | −19.85 | −5.35 |
| 2008-10-10 | A | CONTESTED | NFCI | WALCL | TIGHT_IMPROVING | +2.22 | −3.22 | −6.42 | +0.74 | +19.68 |
| 2008-10-17 | A | CONTESTED | NFCI | WALCL | TIGHT_IMPROVING | −9.55 | −14.39 | −9.62 | +1.49 | +16.73 |
| 2008-10-24 | A | CONTESTED | NFCI | WALCL | TIGHT_IMPROVING | −2.85 | −3.54 | −2.46 | +11.73 | +21.69 |
| 2008-10-31 | A | CONTESTED | NFCI | WALCL | TIGHT_IMPROVING | −12.38 | −13.44 | −6.70 | +3.81 | +7.65 |
| 2008-11-07 | A | CONTESTED | NFCI | WALCL | TIGHT_IMPROVING | −4.55 | −11.15 | −2.43 | +6.81 | +17.41 |
| 2008-11-14 | A | CONTESTED | NFCI | WALCL | TIGHT_IMPROVING | +4.57 | −9.72 | +3.99 | +13.33 | +27.03 |
| 2008-11-21 | A | CONTESTED | NFCI | WALCL | TIGHT_IMPROVING | +7.89 | −4.39 | +11.63 | +28.50 | +38.27 |
| 2008-11-28 | A | CONTESTED | NFCI | WALCL | TIGHT_IMPROVING | −0.62 | −22.31 | +5.41 | +13.88 | +22.25 |
| 2008-12-05 | A | CONTESTED | NFCI | WALCL | TIGHT_IMPROVING | +3.49 | −17.86 | +7.57 | +17.04 | +25.93 |
| 2008-12-12 | A | CONTESTED | NFCI | WALCL | TIGHT_IMPROVING | −4.22 | −11.55 | +3.66 | +19.65 | +26.64 |
| 2008-12-19 | A | CONTESTED | NFCI | WALCL | TIGHT_IMPROVING | −6.80 | −9.21 | +0.81 | +20.70 | +25.47 |
| 2008-12-26 | A | CONTESTED | NFCI | WALCL | TIGHT_IMPROVING | +0.15 | −9.77 | +6.24 | +21.79 | +29.21 |
| 2009-01-02 | A | CONTESTED | NFCI | WALCL | TIGHT_IMPROVING | −10.01 | −9.58 | −3.55 | +10.02 | +21.59 |
| 2009-01-09 | A | ACTIVE | NFCI | WALCL | TIGHT_TIGHTENING | −7.10 | −3.55 | +1.20 | +20.34 | +28.82 |
| 2009-01-16 | A | ACTIVE | NFCI | WALCL | TIGHT_TIGHTENING | −7.26 | −2.09 | +11.88 | +27.94 | +35.30 |
| 2009-01-23 | A | ACTIVE | NFCI | WALCL | TIGHT_TIGHTENING | −7.07 | +4.12 | +17.71 | +31.37 | +31.83 |
| 2009-01-30 | A | ACTIVE | NFCI | WALCL | TIGHT_TIGHTENING | −15.69 | +6.25 | +19.57 | +29.09 | +31.88 |
| 2009-02-06 | A | ACTIVE | NFCI | WALCL | TIGHT_TIGHTENING | −17.15 | +6.98 | +16.33 | +22.80 | +21.66 |
| 2009-02-13 | A | ACTIVE | NFCI | WALCL | TIGHT_TIGHTENING | −5.89 | +6.78 | +21.44 | +31.49 | +32.42 |
| 2009-02-20 | A | ACTIVE | NFCI | WALCL | TIGHT_TIGHTENING | +6.87 | +15.36 | +30.82 | +44.12 | +43.89 |
| 2009-03-06 | A | CONTESTED | NFCI | WALCL | TIGHT_IMPROVING | +22.26 | +37.56 | +46.81 | +60.95 | +66.60 |
| 2009-03-13 | A | CONTESTED | NFCI | WALCL | TIGHT_IMPROVING | +11.23 | +25.07 | +37.83 | +45.71 | +52.07 |
| 2009-03-20 | A | CONTESTED | NFCI | WALCL | TIGHT_IMPROVING | +10.61 | +19.87 | +39.00 | +42.62 | +51.69 |
| 2009-03-27 | A | CONTESTED | NFCI | WALCL | TIGHT_IMPROVING | +4.81 | +12.62 | +28.00 | +38.06 | +43.79 |
| 2009-04-03 | A | CONTESTED | NFCI | WALCL | TIGHT_IMPROVING | +7.28 | +6.67 | +21.69 | +34.48 | +41.18 |
| 2009-04-10 | A | CONTESTED | NFCI | WALCL | TIGHT_IMPROVING | +6.05 | +5.19 | +25.09 | +33.91 | +39.78 |
| 2009-04-17 | A | CONTESTED | NFCI | WALCL | TIGHT_IMPROVING | +4.61 | +8.14 | +26.10 | +30.64 | +37.71 |
| 2009-04-24 | A | CONTESTED | NFCI | WALCL | TIGHT_IMPROVING | +5.09 | +13.05 | +26.17 | +26.62 | +39.92 |
| 2009-06-12 | A | ACTIVE | NFCI | WALCL | TIGHT_TIGHTENING | −4.27 | +10.20 | +16.50 | +21.59 | +15.16 |
| 2009-06-19 | A | ACTIVE | NFCI | WALCL | TIGHT_TIGHTENING | +3.62 | +15.96 | +18.98 | +26.55 | +20.84 |
| 2020-04-03 | A | ACTIVE | WALCL | CNH | TIGHT_IMPROVING | +15.26 | +27.77 | +34.55 | +48.70 | +63.70 |

*Observation: All 46 named TIGHT_* fires are Combo A (NFCI/WALCL bear signal). The 2008–2009 cluster dominated by TIGHT_IMPROVING as Fed expanded balance sheet during GFC. The TIGHT_IMPROVING 3m average (−4.89% for Combo A) is misleading due to time-concentration in the deepest GFC trough; 12m average flips to +13.80% (recovery).*

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

Direction is **encoded correctly** in the labels (EASY_TIGHTENING vs EASY_IMPROVING are distinct periods). But at the FM-event level, hit rates within the EASY level cluster around 50–60% for extreme short and 65–83% for moderate. The **range of hit rates** across EASY sub-states (50%–83%) is notable: EASY_IMPROVING shows 18 percentage points above EASY_TIGHTENING at the moderate FM band (83.3% vs 65.2%). However this range is not yet large enough relative to sample size uncertainty to treat liquidity direction as a standalone combo filter. TIGHT_* buckets are too thin (n=30–50 in the full backfill, n=1–2 at FM events) for any regime-conditional conclusion.

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
**Explanation of 13,089 (Rohit's question):**
> These are NOT 13,089 named combo fires. They are raw variable-pair fires from the 298-signature engine that did not pass the naming gate (Gate 1: ≥5 fires; Gate 2: ≥80% hit rate; Gate 3: economic mechanism). Each "generic fire" represents one date on which two or three variables simultaneously crossed their RARE/EXTREME threshold — but the combination did not qualify as a named combo. They populate `combo_fires` with `runic_combo = NULL`. For context: the named 7 combos have 1,893 total fires. The 13,089 are the unnamed population. TWY_ROC is excluded from ALL 298 combinations (named + unnamed) because it is a regime classifier input only.

**On whether TWY_ROC was tested in Combo A:** TWY_ROC and GSR ablation results are in `X_testingv2_ablations.json`. See §6 of testingv2_report.md for full results. Summary: DOVISH TWY slice on Combo A dates (n=28) shows PW excess vs baseline — see table in §6a. GSR tested as TIGHT MONEY leg — see §6b.

#### TWY_ROC Band Sweep — All Thresholds

*T6 query — 2026-06-16. Source: TWY_ROC computed as DGS2 8-week change, where DGS2 ≈ T10Y (^TNX from Yahoo Finance) minus T10Y2Y spread (from `daily_readings` CURVE, in bps/100). Weekly Friday data from 1990–2026. SPX forward returns from ^GSPC Yahoo Finance. n = number of Friday observations in each band.*

| TWY_ROC Band (pp) | n | SPX Up% 3m | Avg SPX 3m% | SPX Up% 6m | Avg SPX 6m% |
|-------------------|---|-----------|------------|-----------|------------|
| < −0.50 (deep DOVISH) | 184 | 67.4% | +2.95% | 63.6% | +4.80% |
| −0.50 to −0.30 (DOVISH) | 165 | 68.5% | +2.09% | 68.5% | +3.96% |
| −0.30 to −0.10 (mild DOVISH) | 312 | 69.2% | +2.16% | 73.6% | +5.27% |
| ±0.10 (Neutral) | 588 | 81.3% | +3.63% | 83.0% | +7.00% |
| +0.10 to +0.30 (mild HAWKISH) | 345 | 62.6% | +1.54% | 69.1% | +3.55% |
| +0.30 to +0.50 (HAWKISH) | 145 | 60.7% | +1.37% | 72.4% | +3.30% |
| > +0.50 (deep HAWKISH) | 142 | 58.5% | +0.59% | 68.3% | +0.98% |

**April 2025 TWY_ROC readings (actual computed values):**

| Week ending | DGS2 (computed) | TWY_ROC 8wk (pp) | Band |
|-------------|----------------|-----------------|------|
| 2025-04-04 | 3.655% | −0.632 | < −0.50 (deep DOVISH) |
| 2025-04-11 | 3.973% | −0.289 | −0.30 to −0.10 (mild DOVISH) |
| 2025-04-18 | 3.803% | −0.387 | −0.50 to −0.30 (DOVISH) |
| 2025-04-25 | 3.716% | −0.265 | −0.30 to −0.10 (mild DOVISH) |

*April 2025 was firmly DOVISH throughout — DGS2 fell ~0.3–0.6pp over the prior 8 weeks. Apr 4 reading (−0.632pp) is consistent with report's Apr 7 anchor (−0.55pp; slight date discrepancy due to Friday vs Monday measurement). ±0.30pp band validation: DOVISH bands (< −0.30) show 67–69% up 3m vs 81% in Neutral — DOVISH does NOT show excess returns above Neutral, suggesting the ±0.30pp threshold distinguishes regime direction but is not a standalone bullish signal. The real signal is Neutral TWY_ROC (flat 2-year yield = no policy pressure), not DOVISH.*

**DB-sourced band sweep (combo fire dates, from `macro_regime_log_v2` + `combo_fires` join — 2026-06-16):**

| TWY_ROC Band | n (combo fires) | SPX up% 3m | Avg SPX 3m% | SPX up% 6m | Avg SPX 6m% |
|---|---|---|---|---|---|
| < −0.50 (STRONG_DOVISH) | 75 | 62.3% | +1.87% | 68.5% | +6.16% |
| −0.50 to −0.30 (MOD_DOVISH) | 53 | 63.0% | +0.48% | 72.2% | +3.06% |
| −0.30 to −0.10 (MILD_DOVISH) | 148 | 78.1% | +3.93% | 85.8% | +8.97% |
| −0.10 to +0.10 (NEUTRAL) | 449 | 84.3% | +4.65% | 84.7% | +9.06% |
| +0.10 to +0.30 (MILD_HAWKISH) | 221 | 66.3% | +2.28% | 73.8% | +5.03% |
| +0.30 to +0.50 (MOD_HAWKISH) | 52 | 75.4% | +3.64% | 85.6% | +7.16% |
| > +0.50 (STRONG_HAWKISH) | 50 | 53.8% | −0.02% | 60.3% | +1.44% |

*Both tables (calendar-date and combo-fire-date) show the same directional pattern: STRONG_HAWKISH worst at 3m; NEUTRAL best. DB-sourced combo fire dates have lower n (combo fires are a subset of all Fridays), explaining the differences in magnitude.*

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

#### Combo E at Multiple Horizons (6M / 9M / 12M / 15M / 18M)

*T11 horizon sweep — 2026-06-18. Source: `combo_fires` (runic_combo='E', n=508) + Yahoo `^GSPC` forwards via `scripts/combo_e_horizon_sweep.py`. JSON: `macro_intelligence/analysis/regime_v2_experiments/COMBO_E_horizon_sweep_6_18m.json`. 6M/9M/12M cross-check DB `forward_returns`; 15M/18M computed on the fly (378/315 trading days). Combo E direction = **bearish** (bear hit = % SPX down).*

**Overall Combo E — bearish framing (validated direction):**

| Horizon | n_mature | Bear Hit% ↓ | Avg Return% | Bear Avg Win% | Bear Avg Loss% | PW Bear% | Benchmark | Bear Excess |
|---------|----------|-------------|-------------|---------------|----------------|----------|-----------|-------------|
| 6M | 507 | 19.7% | +6.41% | −6.65% | +9.61% | +6.41% | 5% | +1.41pp |
| 9M | 507 | 18.7% | +8.44% | −7.91% | +12.20% | +8.44% | 7.5% | +0.94pp |
| 12M | 507 | 18.9% | +10.93% | −7.77% | +15.30% | +10.93% | 10% | +0.93pp |
| 15M | 427 | 15.5% | +13.50% | −8.15% | +17.46% | +13.50% | 12.5% | +1.00pp |
| 18M | 413 | 14.5% | +16.65% | −7.51% | +20.76% | +16.65% | 15% | +1.65pp |

**SPX Up% (diagnostic — fires coincide with positive drift):**

| Horizon | n_mature | SPX Up% | PW Bull% | Bull Excess |
|---------|----------|---------|----------|-------------|
| 6M | 507 | 79.1% | +6.41% | +1.41pp |
| 9M | 507 | 80.1% | +8.44% | +0.94pp |
| 12M | 507 | 79.9% | +10.93% | +0.93pp |
| 15M | 427 | 84.5% | +13.50% | +1.00pp |
| 18M | 413 | 85.5% | +16.65% | +1.65pp |

**Combo E by CAPE level (6m and 12m):**

| CAPE Bucket | n | Up% 6m | Avg 6m% | PW 6m% | Up% 12m | Avg 12m% | PW 12m% |
|------------|---|--------|---------|--------|--------|---------|--------|
| LOW (<25) | 40 | 100.0% | +9.41% | +9.41% | 90.0% | +12.16% | +12.17% |
| MODERATE (25–30) | 127 | 85.8% | +7.22% | +7.22% | 88.2% | +14.29% | +14.30% |
| HIGH (30–35) | 175 | 77.1% | +6.97% | +6.96% | 85.7% | +13.21% | +13.21% |
| EXTREME (>35) | 165 | 70.9% | +4.46% | +4.46% | 64.8% | +5.62% | +5.61% |

*Key findings: (1) **Bear hit is low at every horizon (~15–20%)** — Combo E marks structural valuation risk, not a reliable 12M SPX down-timer. (2) **12M remains the correct primary horizon**: stable bear hit (18.9%), full mature n=507, aligned with slow CAPE/NFCI dynamics; 6M bear hit is only marginally higher (19.7%). (3) **15M/18M** show falling bear hit (15.5% / 14.5%) and fewer mature episodes (427 / 413) — longer windows mostly capture bull drift, not incremental bear signal. (4) EXTREME CAPE (>35) weakest at 6m/12m — supports CAPE-conditional sizing. (5) MODERATE bucket strong historically but all pre-2018.*

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

**Rohit's clarification (2026-06-11) — HMM understood:**
> HMM is NOT a direct hit-rate improver for individual combos measured at 3m. It is a regime detector. The prototype degradation (−1.2pp on B, −1.9pp on D) is expected in-sample on a k-means prototype — it does not mean HMM is unhelpful. The walk-forward validation (Steps 1–5 in feedback_summary) is the correct test: does HMM Risk-Off posterior precede bearish combo fires by 2+ weeks? Walk-forward scaffold runs (D_hmm_walk_forward.json); median lead time currently 0w — tuning needed (anchor labelling + posterior threshold). December deployment decision deferred pending 6+ months live emission vectors.

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

#### All Historical Inversion Episodes (T10Y2Y)

*T10 query — 2026-06-16. Source: `daily_readings` WHERE var_id='CURVE' (raw_value = T10Y2Y in basis points). Episodes defined as T10Y2Y < 0 for ≥4 consecutive weekly Fridays. "First +15bps steepen" = first Friday after episode end where `steepen_4wk_bps` ≥ +15.*

| Episode | Start | End | Duration (wks) | Peak Inversion (bps) | First +15bps Steepen After |
|---------|-------|-----|----------------|---------------------|--------------------------|
| 1 | 2000-02-04 | 2000-12-22 | 47 | −52 bps | 2000-12-29 |
| 2 | 2006-02-03 | 2006-03-03 | 5 | −16 bps | 2006-03-10 |
| 3 | 2006-06-09 | 2006-07-21 | 7 | −4 bps | 2007-03-16 |
| 4 | 2006-08-18 | 2007-03-16 | 31 | −18 bps | 2007-03-23 |
| 5 | 2022-07-08 | 2024-08-23 | 112 | −106 bps | 2024-08-30 |

*Total: 5 episodes across 36-year backfill. The 2022–2024 episode is by far the longest and deepest (112 weeks, −106bps trough) — the most extreme inversion in this dataset. Steepening came quickly after each episode (within 1 week in 4/5 cases). The 2006-06-09 episode is a 7-week gap within the broader 2006–2007 cycle; steepening to +15bps did not occur until March 2007 (8+ months later). Oct 2022 is mid-episode 5 (the 2022–2024 cycle) — 14 inverted weeks is the depth through Oct 2022, consistent with the report's F2 calculation.*

**"Shadow" defined:** A shadow run means the code executed and populated the `macro_regime_log_v2` database table, but the output is NOT wired to the production nightly PDF/briefing. The production briefing still uses legacy labels. Shadow = validated in data but not sent to users.

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
