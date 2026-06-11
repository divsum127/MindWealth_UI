# SSI Open Questions — Plain-English Understanding Guide

**For:** Divyanshu  
**Source spec:** `testing/ssi_th_exp/SSI_OpenQuestions_DivyanshuTestList (1).pdf` (May 25, 2026)  
**Status file:** `testing/ssi_th_exp/SSI_OPEN_QUESTIONS_SUMMARY.md` (validation runs 2026-06-04, 2026-06-06, Part III + Tests 18–20 on 2026-06-07)  
**Purpose:** Explain what the PDF asks you to build and validate, what every technical term means, what we already tested, and **what doubts to raise with Rohit Sir**.

---

## 1. What is this document?

Rohit Sir’s PDF is a **validation homework list** for the **SSI (Sentiment SuperIndex)** — the daily score that drives **`positioning.json`** (how big trades should be) and feeds **Runic** via **`ssi_multiplier`**.

**Your job in one sentence:** Run **17 numbered backtests** (plus Friday data pulls), document every threshold with **n, forward returns, win %, and Sharpe**, and show which “round number” rules from practitioner consensus actually work — before anyone treats them as final production settings.

**Success looks like:** Every open question in the PDF has a numeric answer or a clear “cannot answer yet” with evidence. Production **CONFIG** (`macro_intelligence/SSI_CONFIG.yaml`) either matches the data or has a documented reason it does not.

**How to read the experiment tables:** Every Q&A table has a **Doubts to ask Rohit Sir** column. These are open questions raised by the backtest or status file, not approval requests.

**Important data note:** The first validation run (2026-06-04) used only **83 days** of SSI history and had code bugs (short win % showed 0%). **Part III (2026-06-06)** fixed history to **~7 years** (2,565 rows from 2019-06-07) and re-ran affected tests. **Only Part III numbers are valid** for Tests 1–2, 7–10, and threshold conclusions unless stated otherwise.

---

## 2. Core concepts (read this first)

| Term | Simple meaning |
|------|----------------|
| **SSI (Sentiment SuperIndex)** | One daily number summarizing market “feel” — risk-on vs risk-off — from credit, vol, sentiment, and related inputs. |
| **SSI level** | The raw composite score for a day (roughly −1 to +1). Negative = bearish positioning context; positive = bullish. |
| **Percentile (5-year)** | Where today’s SSI ranks vs the last ~5 years. **20th percentile** = unusually low (good long context). **85th** = unusually high. |
| **Long gate** | Rule that favors **buying** / adding risk when SSI is very low. |
| **Short gate** | Rule that favors **reducing** longs or fading strength when SSI is very high. |
| **SPX / ^GSPC** | S&P 500 index — benchmark for “did the signal work?” via **forward returns** after the signal date. |
| **Forward return** | What SPX did **after** the signal (e.g. **3m** ≈ 63 trading days later). |
| **n (fires / events)** | How many times a rule triggered in the test window. |
| **Win %** | For longs: % of times SPX **rose**. For shorts: % of times SPX **fell** (a “good” short). |
| **Sharpe ratio** | Return per unit of risk — higher is better; misleading when **n** is tiny. |
| **Layer 2** | Four confirmation inputs (HYG/LQD, DBMF beta, CNN F&G, VIX term structure). **≥2 of 4 active** → CONFIRMED → **1.2×** size multiplier. |
| **Z-score** | “How many standard deviations from normal?” Assumes a bell curve — weak in crises when everything spikes together. |
| **Percentile rank (3-year)** | Alternative scoring: rank today vs last 3 years — no bell-curve assumption. |
| **CFTC FM / RM** | **Fast Money** (leveraged funds) vs **Real Money** (asset managers) net positioning from weekly CFTC TFF reports. |
| **SQUEEZE** | FM very short + RM less short — potential short-covering / squeeze setup. |
| **LIQUIDITY EXIT** | RM pulling back while FM still long — “real money leaving.” |
| **HYG / LQD** | High-yield vs investment-grade bond ETFs. **Ratio falling** = credit stress (junk underperforming). |
| **DBMF** | Managed-futures / CTA ETF. **Beta vs SPY** shows whether trend-followers align with or against stocks. |
| **CNN Fear & Greed** | 0–100 sentiment index. Low = fear, high = greed. |
| **VIX / VIX3M** | Near-term vs 3-month implied volatility. **VIX > VIX3M** = backwardation = stress. |
| **TP / SL** | **Take profit / stop loss** as multiples of daily volatility (legacy PulseGauge: 10× / 15×). |
| **SBI** | **Signal Breadth Indicator** — count of internal strategy buy/sell fires (BandMatrix, DeltaDrift, FractalTrack). **Not** % stocks above 200-day average. |
| **Runic** | Separate macro agent (combos A–G, regimes). Reads SSI multiplier; not the same as SSI scoring. |
| **positioning.json** | File the C++ trading engine reads for position sizing. |
| **Granger causality** | Statistical test: does series A **lead** series B over time (e.g. HYG/LQD change before SPX drawdown). |

---

## 3. PART 1 — Critical validation gaps

**What the spec asks:** Prove or reject every major threshold. Most were set by **informed analogy**, not optimization. Run sweeps, grids, and forward-return tables before calling any number “final.”

---

### 1.1 SSI long gate (−0.3 to −0.9 level sweep) — Tests 1

**What the spec asks:** Sweep SSI **level** from −0.3 to −0.9 in 0.1 steps. Count fires; measure SPX 1m/3m/6m returns. Find the **inflection** where returns improve sharply. PDF default long gate is **−0.6** (~20th percentile intent).

#### 1.1 — Experiment status

| | Detail |
|---|--------|
| **What we did** | `01_02_threshold_sweep` via `run_ssi_validation_suite.py`, Part III window 2010→2026-06-06, artifact `01_02_threshold_sweep_20260606.json`. |
| **Results** | −0.6: **n=303**, 3m avg **+6.31%**, win **96.04%**, Sharpe **2.84**. −0.7: **n=228**, 3m **+6.41%**, win **98.25%**, Sharpe **4.44**. |
| **Production** | **`long_entry_pctile: 20`** is primary; **`long_entry: -0.6`** is secondary level gate in CONFIG. |

#### 1.1 — Old vs new

| Aspect | Old / initial run (2026-06-04) | New / Part III (20260606) | Status |
|--------|-------------------------------|---------------------------|--------|
| SSI history length | 83 days | ~7 years (2,565 rows) | Fixed |
| Long level −0.6 fires | **0** (invalid) | **303** | Fixed |
| Primary long gate | Level −0.6 intent | **Percentile ≤20** (n=419) | Production uses pctile |

**Questions we were looking for:**

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Does −0.6 long level ever fire? | **Yes** | With 7yr history, **≤−0.6** fires **303** times; 3m SPX avg **+6.31%**, **96.04%** win rate, Sharpe **2.84**. Sharpe peaks at **−0.7** (n=228, Sharpe **4.44**, 3m win **98.25%**) before sample thins (−0.9: n=61). | **Doubt:** Should primary long gate stay **pctile ≤20** (n=**419**, 3m **+3.14%**, 78% win) for frequency, or tighten to **level ≤−0.7** (n=228, stronger per-event stats but fewer fires)? |
| Is −0.6 the right inflection point? | **Partially** | Returns improve through −0.7 then frequency drops (−0.8: n=132). PDF inflection at −0.6 is **directionally validated** as last “dense” threshold before sparsity. | **Doubt:** −0.7 has better Sharpe but **25% fewer** fires than −0.6 — is that trade-off acceptable for live trading? |

---

### 1.2 SSI short gate (+0.4 to +0.9; asymmetry) — Test 2

**What the spec asks:** Short tops are **not symmetric** to long bottoms. Test whether **+0.8 or +0.9** works better than **+0.6** for shorts.

#### 1.2 — Experiment status

| | Detail |
|---|--------|
| **What we did** | Same `01_02_threshold_sweep_20260606.json`, short level and percentile sweeps. |
| **Results (level)** | +0.6: n=**884**, 3m **+2.78%**, short win **35.61%**. +0.85: n=**336**, 3m **+5.34%**, short win **26.41%**. |
| **Results (percentile)** | ≥85: n=**659**, 3m **+1.38%**, short win **45.65%**. ≥90: n=**505**, 3m **+0.50%**. **≥95: n=326**, 3m **−0.78%**, short win **51.15%**. |
| **Production** | Reject +0.6 primary; **`short_entry_pctile: 85`**, **`short_entry: 0.85`** secondary. |

**Questions we were looking for:**

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Does +0.6 short fire too early? | **Yes** | Level **≥+0.6**: **884** fires, 3m SPX still averages **+2.78%**; only **35.61%** of episodes had SPX down. Bull sample dominates — level shorts are weak. | **Doubt:** Keep +0.6 only as a **research** line, never as production primary? |
| What short threshold actually works? | **Partially** | Only **≥95th percentile** gives **negative** avg 3m SPX (**−0.78%**, n=**326**, 51% short win). ≥85 is better as **caution / reduce longs** (+1.38% avg 3m) than dedicated short. | **Doubt:** CONFIG has **short_entry_pctile: 85** — should we move actionable short context to **≥90** (n=505, ~50% short win) or **≥95** (n=326, negative 3m avg)? |

---

### 1.3 CFTC SQUEEZE grid (FM low, RM high) — Test 3

**What the spec asks:** Grid FM **15–40** × RM **40–65** (step 5). Heatmap of SPX returns 4w/8w/12w later. PDF default: FM&lt;30, RM&gt;50.

#### 1.3 — Experiment status

| | Detail |
|---|--------|
| **What we did** | `03_squeeze_grid_20260606.json`, 2006–2026 weekly CFTC data. |
| **Results** | Best 12w Sharpe (n≥50): **FM&lt;20, RM&gt;45** — n=**122**, 12w avg **+3.32%**, Sharpe **1.18**. PDF default FM&lt;30/RM&gt;50: 12w **+2.60%**, Sharpe **0.85**. |
| **Production** | **Not** an SSI CONFIG gate — Runic / macro research flag. |

#### 1.3 — Old vs new

| Aspect | PDF default | Experiment best cell | Status |
|--------|-------------|---------------------|--------|
| FM threshold | &lt;30th pctile | **&lt;20** | Tighter FM improves 12w Sharpe |
| RM threshold | &gt;50th pctile | **&gt;45–50** | Similar RM band |

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Are PDF round numbers optimal? | **No** | **FM&lt;20 / RM&gt;45** beats FM&lt;30/RM&gt;50 on 12w Sharpe (**1.18** vs **0.85**). All cells show **positive** 12w SPX — pattern is common (100+ weeks), not rare. | **Doubt:** Adopt **FM&lt;20** for Runic SQUEEZE alerts, or keep PDF **30/50** for more frequent flags? |

---

### 1.4 CFTC LIQUIDITY EXIT grid (RM low, FM high) — Test 4

**What the spec asks:** Grid RM **15–40** × FM **45–75**. Include **median drawdown** after each instance.

#### 1.4 — Experiment status

| | Detail |
|---|--------|
| **What we did** | `04_liquidity_exit_grid_20260606.json`. |
| **Results** | Top cell by n: RM&lt;15, FM&gt;45 — n=**89**, 4w SPX-down win **34.83%**, 12w avg **+2.81%**. Stress flag, not clean short. |
| **Production** | Runic research only. |

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Does LIQUIDITY EXIT predict SPX down moves? | **Partially** | ~**35%** 4w SPX-down rate at best cells; 12w avg SPX still **positive**. Useful as **macro stress context**, not standalone short trigger. | **Doubt:** Wire to Combo G warning only, or promote to a named Runic combo leg? |

---

### 1.5 TP/SL multiplier optimization — Test 5

**What the spec asks:** Sweep TP **5–20×** and SL **8–25×** daily vol. Find optimal pair for Sharpe and win rate on SPY long entries.

#### 1.5 — Experiment status

| | Detail |
|---|--------|
| **What we did** | MindWealth adapter, `05_tp_sl_20260606.json`, 535 entries, 256 combinations. |
| **Results** | Best: **TP×5 / SL×20** — n=**430**, Sharpe **4.06**, win **97.67%**, avg return **4.80%**. Legacy **TP×10 / SL×15**: n=**124**, Sharpe **0.91**. |
| **Production** | PulseGauge still on legacy 10×/15× until CONFIG change approved. |

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Is legacy TP×10 / SL×15 optimal? | **No** | Legacy Sharpe **0.91** vs proposed **4.06** — take profit **sooner** (5× vs 10×), stop **wider** (20× vs 15×). | **Doubt:** Approve changing PulseGauge to **TP×5 / SL×20** in production CONFIG? |

---

### 1.6 COT FM long gate sweep (15th–45th pctile) — Test 18

**What the spec asks:** Vary FM percentile **15–45** for long-gate condition; measure hit rate change. PDF default FM&lt;30.

#### 1.6 — Experiment status

| | Detail |
|---|--------|
| **What we did** | New module `cot_fm_long_gate.py`, `18_cot_fm_long_gate_20260607.json`. |
| **Results** | FM&lt;15: n=**157**, 3m **+2.83%**. FM&lt;20: n=**201**, 3m **+3.13%**. FM&lt;30 (PDF): n=**272**, 3m **+2.74%**. |
| **Production** | Macro / Runic confirmation, not SSI CONFIG. |

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Is FM&lt;30 optimal for long confirmation? | **No** | **FM&lt;20** has slightly higher 3m avg (**+3.13%** vs **+2.74%**) with n=**201** vs **272**. | **Doubt:** Use **FM&lt;20–25** for Runic long confirmation instead of PDF **30**? |

---

### 1.7 VIX≥35 + FM percentile distribution — Test 19

**What the spec asks:** On all **VIX≥35** days, what was FM percentile distribution? Where is return inflection? PDF: FM&lt;15 = extreme washout.

#### 1.7 — Experiment status

| | Detail |
|---|--------|
| **What we did** | `vix_fm_washout.py`, `19_vix_fm_washout_20260607.json`. |
| **Results** | **93** VIX≥35 episodes. FM median **54.5**, mean **51.6**. Only **18.3%** had FM&lt;15. FM 0–15 bin: n=**17**, 3m **+8.25%**, 94% SPX up (contrarian long, not short). |
| **Production** | VIX stress flag; FM washout is **minority** of episodes. |

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Is FM&lt;15 common at VIX≥35? | **No** | Only **~18%** of VIX≥35 days have FM&lt;15. Median FM is **54th** — washout is not the typical state. | **Doubt:** Keep VIX≥35 override tied to FM&lt;15, or require only VIX≥35 + FM&lt;20 for higher conviction? |

---

### 1.8 Layer 2 z-score threshold sweep — Tests 10 & 20

**What the spec asks:** Sweep z-score confirmation **0 to 2.0** in 0.25 steps. Measure false positive rate and hit rate. PDF mentioned z&gt;0.5; production uses **vote count** (≥2 of 4 inputs).

#### 1.8 — Experiment status

| | Detail |
|---|--------|
| **What we did** | Test 10: vote count 0–4 (`10_layer2_sweep_20260606.json`). Test 20: z-score sweep (`20_layer2_zscore_sweep_20260607.json`). |
| **Results (votes)** | Long gate days n=**419** for min_votes 0–3; identical metrics. min_votes=4 → **0** days. |
| **Results (z-score)** | z≥**1.25**: n=**105** long+confirm, **90.48%** 3m hit. z≥**1.5**: n=**63**, **92.06%** hit. z=0: n=**396**, **79.29%** hit. |
| **Production** | **`min_confirmed: 2`**, multipliers 1.2 / 1.0 / 0.8. |

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Does raising min_votes improve long quality? | **No** | All **419** long-gate days already have ≤3 votes active — sweeping 0→3 changes nothing. | **Doubt:** Is vote-count Layer 2 too loose in practice? Should we add **z≥1.25** overlay for sizing? |
| What z threshold improves hit rate? | **Yes** | Inflection at **z≥1.25–1.5**: 3m hit **90–92%** on n=**63–105** vs **79%** at z=0 (n=396). | **Doubt:** Deploy z≥1.25 as research overlay only, or change Layer 2 architecture from votes to z-thresholds? |

---

### 1.9 CNN Fear & Greed &lt;20 / &gt;80 — Test 6

**What the spec asks:** Pull CNN F&G from ~2011. SPX returns after fear &lt;20, &lt;10, greed &gt;80, &gt;90 crossings.

#### 1.9 — Experiment status

| | Detail |
|---|--------|
| **What we did** | `06_cnn_fear_greed_20260606.json`. Cache backfilled via Alternative.me API from **2018** (not true CNN stock 2011–2018). |
| **Results** | Fear&lt;20: n=**68**, 3m **+2.83%**, 66% win. Fear&lt;10: n=**18**, 3m **+11.66%**, 94% win. Greed&gt;90: n=**11**, 3m **+5.89%**, **90.91% SPX up** (momentum, not short). |
| **Production** | Layer 2 uses **25/75**, not 20/80. |

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Does extreme fear predict longs? | **Yes** | Fear&lt;10: n=**18**, 3m avg **+11.66%**, **94.44%** win. Supports “buy fear” for long context. | **Doubt:** n=18 is small — keep 25/75 production levels or tighten fear leg? |
| Does greed&gt;80 work for shorts? | **No** | Greed&gt;90: 3m **+5.89%** avg — **momentum continuation**, not fade. Confirms shorts should not use CNN greed. | **Doubt:** Accept Alternative.me proxy from 2018 only, or budget paid CNN stock F&G 2011–2018? |

---

### 1.10 Z-score vs percentile SSI composite — Test 9

**What the spec asks:** Run **both** z-score and 3-year percentile composite. If percentile wins in **2020 and 2022 crises**, switch combination method.

#### 1.10 — Experiment status

| | Detail |
|---|--------|
| **What we did** | `09_zscore_vs_percentile_20260606.json`, parallel percentile path in validation only. |
| **Results** | COVID Feb–Apr 2020: z-path **0** events; percentile path **62** days, 6m avg **+19.33%**, 93.55% win. Oct 2022: z-path **0**; percentile **84** days, 6m **+7.98%**. |
| **Production** | Still **z-score** in `ssi_score.py` — percentile not deployed. |

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Should we switch to percentile composite? | **Open** | Percentile clearly registers crisis days z-score misses (62 vs 0 in 2020). Strong 6–12m forward returns in those windows. | **Doubt:** Switch production `ssi_score.py` to 3yr percentile composite, or keep z-score until a full Sharpe comparison across all regimes is run? |

---

## 4. PART 2 — Specific signal definition gaps

**What the spec asks:** Pin down **quantitative** definitions for HYG/LQD widening, DBMF beta bands, and CNN thresholds.

---

### 2.1 HYG/LQD widening — Test 8

**What the spec asks:** Define “widening” as 4-week **% change** in HYG/LQD ratio. PDF: **RARE −1.5%**, **EXTREME −3.0%**. Test lead time to VIX&gt;25 and Granger vs SPX.

#### 2.1 — Experiment status

| | Detail |
|---|--------|
| **What we did** | `08_hyg_lqd_20260606.json`, thresholds −1.0%, −1.5%, −2.0%, −3.0%. |
| **Results** | −1.5%: n=**116**, median **2 days** to VIX&gt;25 (vs **7 days** at −1.0%, n=**167**). −3.0%: n=**53**, median **0 days**. |
| **Production** | Layer 2 uses **ratio percentiles 70/30**, not 4wk % cuts. |
| **Granger** | **Not run** for HYG/LQD (only DBMF in Test 7). |

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Do PDF −1.5% / −3.0% bands work as stress flags? | **Yes** | Tighter cuts align with faster VIX spike (2 days vs 7). Counts: **116** / **87** / **53** fires. | **Doubt:** Add 4wk % cuts to CONFIG alongside percentiles, or keep percentiles only? |
| Does HYG/LQD Granger-lead SPX? | **No** | Test not executed. PDF Part 2.1 explicitly asked for `run_correlation_analysis()` lags 1–8 weeks. | **Doubt:** Run HYG/LQD Granger before calling Test 8 complete? |

---

### 2.2 DBMF beta threshold — Test 7

**What the spec asks:** 21-day rolling beta vs SPY. Fire at **β &lt; −0.10**. Report 3yr percentile at fire. Regress beta vs SPX forward; report R² and p-value.

#### 2.2 — Experiment status

| | Detail |
|---|--------|
| **What we did** | `07_dbmf_beta_20260606.json`. |
| **Results** | β&lt;−0.10: n=**29**, avg 3yr pctile **20.8**, 4w SPX **+1.33%**, 65.52% win. OLS 4w: R²=**0.004**, p=**0.007**, slope **−0.79**. Granger: **not predictive** (p&gt;0.55). |
| **Production** | Layer 2 uses bands **0.5 / 1.2** (different scale than PDF −0.10). |

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Is β&lt;−0.10 a short trigger? | **No** | Negative beta coincides with **positive** 4w SPX drift (+1.33%) — contrarian **long** context, not standalone short. | **Doubt:** Recalibrate production Layer 2 DBMF bands to PDF −0.10 scale, or keep 0.5/1.2 design bands? |

---

### 2.3 CNN Fear & Greed — see §1.9 (Test 6)

---

## 5. PART 3 — Date corrections

**What the spec asks:** Fix confusion between April **2025** vs **2026** events (tariff shock, VIX backwardation, oil spike, 50WMA reclaim).

#### PART 3 — Status

| | Detail |
|---|--------|
| **What we did** | Documented in status file §3 for ops reference. Test 11 uses **Oct 2022** for vix_bypass spot check, not April 2025. |
| **Production** | N/A — documentation / narrative accuracy. |

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Are combo date narratives correct? | **Yes** | Tariff sell-off Feb–Mar **2025**; VIX backwardation **Apr 7, 2025**; oil spike Apr–May **2026**; 50WMA reclaim **Mar 30, 2026**. | None — reference table for briefing writers. |

---

## 6. PART 4 — Gross/net divergence — Test 14

**What the spec asks:** Revised 3-condition rule: gross &gt;75th pctile 3yr **3+ weeks** + net falling 3 weeks + HYG/LQD 4wk **&lt; −1.0%**. Is it always bearish?

#### PART 4 — Experiment status

| | Detail |
|---|--------|
| **What we did** | `14_gross_net_20260606.json` (forward-return bug fixed). |
| **Results** | n=**25** instances. 4w: avg **+0.08%**, 24% SPX-down. 12w: avg **+2.44%**, 24% SPX-down. SPX rises in **~76%** of episodes. |
| **Production** | Research / Runic context only — not SSI CONFIG. |

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Is gross/net divergence a short signal? | **No** | **72–76%** of episodes see SPX **higher** over 4–12w. Rule flags stress clusters (e.g. Jul–Aug 2021, Mar 2025) but not reliable shorts. | **Doubt:** Use only as Combo G / macro warning text, never as automated short gate? |

---

## 7. PART 5 — VIX regime multiplier — Test 11

**What the spec asks:** VIX&gt;35 cuts size 0.50× — but **Oct 2022** was a historic **buy** bottom (Combo B). **Bypass** multiplier when Combo B or F fired in last 4 weeks.

#### PART 5 — Experiment status

| | Detail |
|---|--------|
| **What we did** | `11_vix_regime_multiplier_20260606.json` — Oct 13 2022 spot check. |
| **Results** | `combo_b=true`, `vix_bypass=true`, multiplier **1.2** on CONFIRMED path. |
| **Not done** | Full 2006–2026 equity curve with vs without multiplier — **waived**. |

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Is vix_bypass wired correctly? | **Yes** | Oct 2022 maps to bypass active when Combo B present — matches PDF Part 5 fix. | **Doubt:** Run full 20yr backtest to quantify economic impact, or accept architectural verification only? |

---

## 8. PART 6 — SBI correction — Test 15

**What the spec asks:** SBI = strategy fire count (not % above 200 DMA). **Short SBI** &gt;90th pctile of 1yr history — validate as **confirmation only**, not standalone.

#### PART 6 — Experiment status

| | Detail |
|---|--------|
| **What we did** | Adapter written; MindWealth imports fixed. **Batch not run** (~1 hr, full S&P 500 per day). |
| **Results** | **No archived JSON.** |
| **Production** | SBI short used as confirmation in docs — **unvalidated empirically**. |

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Is SBI short &gt;90th useful confirmation? | **No** | Test 15 never completed. Cannot cite hit rate or return histogram. | **Doubt:** Approve overnight MindWealth batch run (`sbi_breadth.py --start 2015-01-01`)? |

---

## 9. PART 7 — TrendPulse deterioration — Test 17

**What the spec asks:** Define deterioration as SSI falling **≥0.5/week for 2+ weeks**. Sweep 60th/70th/80th percentile of weekly |ΔSSI|.

#### PART 7 — Experiment status

| | Detail |
|---|--------|
| **What we did** | `trendpulse_deterioration.py` registered as Test 17. |
| **Results** | Initial run: **11 weekly points** — no 2-week episodes. After 7yr SSI backfill, **re-run status unclear** — confirm Part III artifact. |
| **Production** | TrendPulse concept documented; threshold not finalized. |

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Which weekly Δ threshold predicts negative returns? | **No** | Module exists; meaningful episode count pending confirmed re-run with 2,565-day SSI history. | **Doubt:** Re-run Test 17 now that SSI history is fixed — is TrendPulse a product requirement? |

---

## 10. PART 8 — Runic vs SSI overlap

**What the spec asks:** Map duplicated variables (HY credit, VIX, CFTC, NFCI). Avoid double-counting. PDF: exclude VIX from SSI Layer 2; consider NFCI in SSI.

#### PART 8 — Status

| Variable | PDF verdict | Current state |
|----------|-------------|---------------|
| HY credit | Overlap ~0.95 — OAS for Runic, HYG/LQD for SSI | Implemented as designed |
| VIX / VIX3M | Exclude from SSI Layer 2 | **VIX still in SSI Layer 2** in CONFIG |
| CFTC | Complementary — SSI FM/RM split | Both systems use CFTC |
| NFCI | Add to SSI? | **Waiver** — Runic only (WAIVER-NFCI-SSI) |
| CNN F&G | SSI → Runic multiplier (correct layering) | As built |

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Should VIX leave SSI Layer 2? | **Open** | PDF Part 8 recommends removal (McClellan already in SSI). Production still has vix_ratio in Layer 2 votes. | **Doubt:** Remove VIX from Layer 2 to avoid duplication with Runic Combo D, or keep for independent confirmation? |
| Should NFCI enter SSI? | **Deferred** | Explicit waiver — NFCI stays Runic-only. | **Doubt:** Revisit if Runic NFCI and SSI credit signals diverge in live ops? |

---

## 11. PART 9 — Numbered test deliverables (summary)

**What the spec asks:** Run all tests; document n, avg return 1/3/6/12m, Sharpe, hit rate, worst case **before** any threshold is final.

### Deliverables checklist (spec vs status)

| # | Test | Shadow / experiment | Production impact |
|---|------|---------------------|-------------------|
| **1** | Long level sweep | **DONE** Part III | Secondary gate −0.6 |
| **2** | Short level + pctile sweep | **DONE** Part III | Reject +0.6; ≥85 caution, ≥95 short context |
| **3** | SQUEEZE grid | **DONE** | Runic research |
| **4** | LIQUIDITY EXIT grid | **DONE** | Runic research |
| **5** | TP/SL optimization | **DONE** | Pending CONFIG change |
| **6** | CNN F&G | **DONE** (proxy 2018+) | Layer 2 25/75 |
| **7** | DBMF beta | **DONE** | Layer 2 bands 0.5/1.2 |
| **8** | HYG/LQD widening | **DONE** (no Granger) | Layer 2 percentiles |
| **9** | Z-score vs percentile | **DONE** | Z-score still in prod |
| **10** | Layer 2 votes | **DONE** | min_confirmed=2 |
| **10b** | Layer 2 z-score sweep | **DONE** (Test 20) | Research only |
| **11** | VIX multiplier A/B | **Partial** (spot check) | vix_bypass live |
| **12** | Bollinger + SSI | **DONE** but **0 combo events** | Must rerun |
| **13** | Stochastic + McClellan | **DONE** n=3 combo | Must rerun |
| **14** | Gross/net divergence | **DONE** n=25 | Research only |
| **15** | SBI short | **NOT RUN** | Unvalidated |
| **16** | Friday pull checklist | **DONE** 12/12 PASS | Ops automation |
| **17** | TrendPulse deterioration | **Written** — confirm rerun | Open |
| **18** | COT FM sweep | **DONE** 2026-06-07 | Runic |
| **19** | VIX≥35 FM dist | **DONE** 2026-06-07 | Runic |
| **20** | Layer 2 z-score | **DONE** 2026-06-07 | Research |

### Tests 12 & 13 — detail

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Does Bollinger + SSI pctile≤20 improve longs? | **No** | Prior runs: BB-only n=**115**, combo n=**0**. SSI history now 7yr; breadth extended to 2015 — **rerun required**. | **Doubt:** Is Bollinger overlay a product requirement worth rerunning Test 12? |
| Does Stoch+McClellan combo beat either alone? | **No** | n=**6** stoch, n=**0** McClellan-only, n=**3** combo — too small. McClellan now to 2014. | **Doubt:** Rerun Test 13 for advisory stats only, or drop from roadmap? |

---

## 12. PART 10 — Friday pull list — Test 16

**What the spec asks:** Every Friday before COT, pull and log ~18 macro variables (NFCI, HY OAS, VIX, CFTC, curve, CPI surprise, HYG/LQD, DBMF, CNN, AAII, NAAIM, etc.).

#### PART 10 — Experiment status

| | Detail |
|---|--------|
| **What we did** | `friday_pull_checklist.py`, Test 16. Initial: 10/12 PASS. After AAII urllib + CPI Trading Economics fix: **12/12 PASS**. |
| **Production** | `run_macro_friday_pull`, `run_ssi_daily`, `cftc_pull` jobs. |

| Question | Answered? | Answer | Doubts to ask Rohit Sir |
|----------|-----------|--------|-------------------------|
| Is Friday automation complete? | **Yes** | All **12** checklist items PASS including AAII (2,026 rows) and CPI validation. | **Doubt:** Any additional PDF variables missing from nightly jobs? |

---

## 13. Recommended build order (from spec intent)

1. **Fix data pipeline** — SSI history, NAAIM backfill, forward-return bugs (done 2026-06-06).  
2. **Tests 1–4, 7–8** — core threshold and CFTC grids (done Part III).  
3. **Tests 5–6, 9–11, 14, 16** — TP/SL, CNN, z-score, VIX, gross/net, Friday pulls (done or partial).  
4. **Tests 18–20** — PDF sub-experiments COT FM, VIX/FM, z-score (done 2026-06-07).  
5. **Tests 12, 13, 15, 17** — rerun or first run with fixed history / MindWealth batch.  
6. **CONFIG updates** — only after Rohit Sir resolves doubts below.

---

## 14. Doubts to ask Rohit Sir (consolidated master list)

| # | Doubt to ask Rohit Sir | Evidence from status |
|---|------------------------|----------------------|
| 1 | Primary long gate: keep **pctile ≤20** (n=419, 3m +3.14%) or tighten to **level ≤−0.7** (n=228, Sharpe 4.44)? | Part III `01_02_threshold_sweep_20260606.json` |
| 2 | Short pctile: stay at **≥85** (caution), move to **≥90** (n=505, ~50% short win), or **≥95** only (n=326, −0.78% 3m avg)? | Short pctile sweep §4.1 |
| 3 | Approve **TP×5 / SL×20** in PulseGauge vs legacy **10×15** (Sharpe 4.06 vs 0.91)? | `05_tp_sl_20260606.json` |
| 4 | Switch SSI composite from **z-score** to **3yr percentile** after crisis-window win (62 vs 0 days in 2020)? | `09_zscore_vs_percentile_20260606.json` |
| 5 | SQUEEZE research cell: adopt **FM&lt;20 RM&gt;45** vs PDF **FM&lt;30 RM&gt;50**? | `03_squeeze_grid_20260606.json` |
| 6 | COT FM long confirmation: **FM&lt;20** vs PDF **&lt;30**? | `18_cot_fm_long_gate_20260607.json` |
| 7 | VIX≥35 override: require **FM&lt;15** (18% of episodes) or relax to **FM&lt;20**? | `19_vix_fm_washout_20260607.json` |
| 8 | Layer 2: keep **vote count ≥2** or add **z≥1.25** overlay (90.5% 3m hit, n=105)? | `20_layer2_zscore_sweep_20260607.json` |
| 9 | Remove **VIX** from SSI Layer 2 per PDF Part 8, or keep for confirmation? | CONFIG vs PDF overlap table |
| 10 | Approve **~1 hr MindWealth batch** for Test 15 SBI short validation? | No `15_sbi_*.json` archived |
| 11 | Is **Bollinger + SSI** overlay a product requirement (Test 12 rerun)? | Combo n=0 in all prior runs |
| 12 | Re-run **Test 13** McClellan now extended to 2014? | Prior combo n=3 |
| 13 | Re-run **Test 17** TrendPulse with 7yr SSI — is TrendPulse in scope? | 11 weekly points in first run |
| 14 | Run **HYG/LQD Granger** (Part 2.1) before closing Test 8? | Only DBMF Granger done |
| 15 | Budget **paid CNN stock F&G 2011–2018**, or accept Alternative.me proxy from 2018? | Test 6 proxy limitation |
| 16 | Full **20yr VIX multiplier** equity backtest, or waive like Test 11? | Oct 2022 spot check only |
| 17 | DBMF Layer 2: keep **0.5/1.2 bands** or align to PDF **−0.10** cutoff? | Test 7 vs production scale |
| 18 | HYG/LQD stress: add **4wk −1.5%/−3.0%** flags to CONFIG or percentiles only? | Test 8 vs Layer 2 design |

---

## 15. Key artifact index

| File | Purpose |
|------|---------|
| `testing/ssi_th_exp/SSI_OpenQuestions_DivyanshuTestList (1).pdf` | Source requirements (May 25, 2026) |
| `testing/ssi_th_exp/SSI_OPEN_QUESTIONS_SUMMARY.md` | Full status, §4 evidence, §11 audit |
| `macro_intelligence/analysis/ssi_validation/*_20260606.json` | Part III primary artifacts |
| `macro_intelligence/analysis/ssi_validation/18_cot_fm_long_gate_20260607.json` | COT FM sweep |
| `macro_intelligence/analysis/ssi_validation/19_vix_fm_washout_20260607.json` | VIX≥35 FM distribution |
| `macro_intelligence/analysis/ssi_validation/20_layer2_zscore_sweep_20260607.json` | Layer 2 z-score sweep |
| `scripts/run_ssi_validation_suite.py` | Reproduce all tests |
| `macro_intelligence/SSI_CONFIG.yaml` | Production thresholds |
| `docs/ssi_validation/SIGNOFF.md` | Rohit Sir checklist |
| `docs/ssi_validation/SSI_THRESHOLD_JUSTIFICATION.md` | Per-threshold production rationale |

**Reproduce:**
```bash
.venv/bin/python scripts/run_ssi_validation_suite.py
# Tests 5 & 15: omit --skip-mindwealth; MINDWEALTH_ROOT=/home/ubuntu/MindWealth
```

---

## 16. How this relates to work already done

The validation **suite is built and mostly run**. Part III fixed the critical **83-day SSI history** bug and forward-return export errors, so Tests 1–2 and gate conclusions are now trustworthy. Tests **18–20** closed PDF sub-experiments that were missing from the original numbered list. **Production CONFIG** already reflects the main empirical findings (pctile long 20, reject short +0.6, vix_bypass, Layer 2 min_confirmed 2). What remains is **rerunning** Tests 12, 13, 15, 17 with fixed data, resolving **Rohit Sir’s threshold choices** in the master doubts table, and optionally switching composite scoring (Test 9) and PulseGauge TP/SL (Test 5) after those conversations.

---

*Understanding doc generated from `SSI_OpenQuestions_DivyanshuTestList (1).pdf` + `SSI_OPEN_QUESTIONS_SUMMARY.md`.*
