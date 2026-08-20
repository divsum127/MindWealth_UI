# SSI & Layer 2 — Threshold Justification (Single Reference)

**Purpose:** One document explaining **every production threshold** for the Sentiment SuperIndex (SSI): what it is, why that number, what evidence supports it, and what was rejected.

**Config file (source of truth):** [`macro_intelligence/SSI_CONFIG.yaml`](../../macro_intelligence/SSI_CONFIG.yaml)  
**Code:** [`src/sentiment_superindex/engine/ssi_score.py`](../../src/sentiment_superindex/engine/ssi_score.py), [`layer2.py`](../../src/sentiment_superindex/engine/layer2.py), [`positioning.py`](../../src/sentiment_superindex/engine/positioning.py)  
**Evidence run:** 2026-06-04 — [`macro_intelligence/analysis/ssi_validation/`](../../macro_intelligence/analysis/ssi_validation/)  
**Open Questions spec:** `macro_intelligence_docs/SSI_OpenQuestions_DivyanshuTestList (1).docx`

**Status labels used below:**

| Label | Meaning |
|-------|---------|
| **APPROVED** | Keep in production; evidence or strong design rationale documented |
| **APPROVED (design)** | Practitioner / spec intent; limited or no full-history optimization |
| **ALTERNATIVE** | Sweeps suggest a different number; CONFIG uses a balanced default until Rohit signs |
| **REJECTED** | Tested or spec-reviewed; do not use |
| **PENDING** | Needs more data or MindWealth run (e.g. TP/SL) |

**Rohit sign-off:** [SIGNOFF.md](SIGNOFF.md)

---

## How to read a threshold row

Each threshold below follows the same pattern:

1. **Parameter** — YAML key or code constant  
2. **Value in production** — what runs today  
3. **Plain English** — what it does  
4. **Why this number** — design intent + validation  
5. **Evidence** — Test #, n events, forward SPX behavior where relevant  
6. **Alternatives considered** — what we swept and why not chosen (yet)

---

# Part A — Composite SSI score (how the daily number is built)

These settings affect **every day’s SSI level** before long/short gates fire.

## A1. `ssi_score.history_years: 5`

| | |
|--|--|
| **Value** | 5 years |
| **Plain English** | When we ask “how extreme is today?”, we compare to roughly the **last five years** of history. |
| **Why** | Matches the Open Questions doc (“~20th percentile of 5y distribution” for longs). Five years includes a full cycle (COVID, rate hikes, recovery) without going back so far that old regimes dominate. |
| **Evidence** | Used consistently in `build_ssi_history_frame` and percentile gates (Tests 1–2). |
| **Status** | **APPROVED (design)** |

## A2. `ssi_score.design_percentile: 20`

| | |
|--|--|
| **Value** | 20 |
| **Plain English** | Documentation anchor: “extreme bearish” ≈ **bottom 20%** of the 5-year SSI distribution. Aligns with `long_entry_pctile: 20`. |
| **Why** | Not a separate gate; documents intent that long entries should be **unusually low** SSI, not merely below average. |
| **Evidence** | Test 1–2: percentile ≤ 20 → 16 events (2015–2026), ~81% SPX up at 3m, avg ~+4.1%. |
| **Status** | **APPROVED** |

## A3. `ssi_score.zscore_clip: 3.0`

| | |
|--|--|
| **Value** | 3.0 |
| **Plain English** | Each input is converted to a **z-score** (standard deviations from its mean), then **capped at ±3** so one wild day cannot dominate the composite. |
| **Why** | Fat-tail markets can produce huge z-scores; clipping limits damage to the combined score. Open Questions note z-scores can **understate** true extremes (Test 9). |
| **Evidence** | Test 9: percentile-based composite is a **future option**, not production. |
| **Status** | **APPROVED (design)** — revisit if Test 9 signed for production switch |

## A4. Composite weights (`hyg_lqd` 0.30, `dbmf_beta` 0.25, `cnn_fg` 0.25, `vix_ratio` 0.20)

| Input | Weight | Plain English | Why this weight |
|-------|--------|---------------|-----------------|
| **HYG/LQD** | 30% | Credit risk (high-yield vs safe bonds) | Largest weight: credit often leads equity stress; spec treats HY widening as core risk-off signal. |
| **DBMF beta** | 25% | CTA / managed-futures positioning vs stocks | Second: systematic macro funds matter for liquidity and trends. |
| **CNN Fear & Greed** | 25% | Retail/survey-style sentiment | Balanced with DBMF; fear/greed is fast-moving. |
| **VIX ratio** | 20% | Near-term vs 3-month implied volatility | Slightly lower: already partly reflected in macro/Runic combos; still flags term-structure stress. |

**Evidence:** No single “weight sweep” in validation suite; weights are **APPROVED (design)** from SSI spec. Changing weights requires a dedicated study (out of scope for Open Questions Part 9).

**Status:** **APPROVED (design)**

## A5. CNN mapping inside composite (code, not YAML): fear ≤ 25, greed ≥ 75

| Code rule | Effect on component |
|-----------|---------------------|
| CNN ≤ **25** | Component score ≈ **+0.8** (strong risk-off contribution) |
| CNN ≥ **75** | Component score ≈ **−0.8** (strong risk-on / greed) |
| Between | Linear from 50 |

**Why 25 / 75:** Layer 2 uses the same band (see C4). CNN’s public scale is 0–100; 25/75 are **extreme but not only the tail** (vs &lt;20 / &gt;80 in Test 6 crossings). Slightly wider than “extreme fear/greed” so the composite can react before a rare &lt;20 print.

**Evidence:** Test 6 (&lt;20 fear) had very few crossing events in our CNN series; production uses **level** rules in composite, not only crossings.

**Status:** **APPROVED (design)** — aligned with Layer 2 `fear_max` / `greed_min`

## A6. VIX ratio mapping inside composite (code): stress ≥ 1.05, complacency ≤ 0.95

| Code rule | Plain English |
|-----------|---------------|
| Ratio ≥ **1.05** | Near-term vol elevated vs 3-month → risk-off component **−0.7** |
| Ratio ≤ **0.95** | Complacent term structure → risk-on **+0.5** |

**Why:** **1.05** = mild backwardation / stress; **1.10** is used in macro Friday flags as “stronger” stress. Composite uses a **lower** bar so SSI feels stress earlier. **0.95** = contango / calm vol.

**Evidence:** Layer 2 uses `stress_min: 1.05` and `complacency_max: 0.95` (same numbers).

**Status:** **APPROVED (design)**

---

# Part B — Long and short entry gates (`thresholds` in YAML)

These decide when `positioning.json` marks **long** or **short** as **active** (see `positioning.py`: fires if **either** percentile **or** level condition is met).

## B1. `long_entry_pctile: 20` — **PRIMARY long gate**

| | |
|--|--|
| **Plain English** | **Long** bias allowed when today’s SSI is in the **bottom 20%** of the last 5 years. |
| **Why** | Implements “extreme bearish” from the spec without relying on raw level −0.6 (which almost never triggers). Markets **bottom faster** than they top; rare low percentile captures capitulation-like readings. |
| **Evidence (2015–2026)** | **n = 16** events; 3m forward SPX: **avg +4.08%**, **win 81.25%**, worst −0.34%. |
| **Alternatives** | ≤10: n=5, stronger 3m stats but **too few** events. ≤25: n=19, slightly lower edge. Sweep “best” by avg return suggested ≤10; **CONFIG keeps 20** for **more fires** and stability. |
| **Status** | **APPROVED** — primary long gate |

## B2. `long_entry: -0.6` — **SECONDARY long gate**

| | |
|--|--|
| **Plain English** | Also allow long if composite level ≤ **−0.6**. |
| **Why** | Original symmetric spec (−0.6 long / +0.6 short). Kept as **backup** if percentile and level disagree. |
| **Evidence** | **n = 0** fires on level sweep −0.3 to −0.9 (2015–2026). Composite rarely reaches −0.6. |
| **Status** | **APPROVED (design)** — harmless fallback; **do not** use as primary justification |

## B3. `short_entry_pctile: 85` — **PRIMARY short gate**

| | |
|--|--|
| **Plain English** | **Short** bias allowed when SSI is in the **top 15%** (≥ 85th percentile) of the 5-year range — **unusually bullish** composite. |
| **Why** | Open Questions: **tops are slow**; symmetric +0.6 shorts fire too early. **85** demands more extreme greed than “above average” (50) or even 70. |
| **Evidence (2015–2026)** | **n = 7** at ≥85; 1w SPX down **57%** of the time; 3m avg SPX still **+2.7%** (shorts lose on 3m hold — structural bull bias in sample). Stricter **90**: n=5, better 1w fade, fewer events. |
| **Alternatives** | ≥90: fewer, slightly better short-term; sweep JSON suggested 90 for “best” 3m avg. **85** = compromise between **frequency** and **extremity**. |
| **Status** | **APPROVED** — primary short gate; Rohit may prefer **90** for stricter shorts |

## B4. `short_entry: 0.85` — **SECONDARY short gate**

| | |
|--|--|
| **Plain English** | Also allow short if composite level ≥ **+0.85**. |
| **Why** | Replaces rejected **+0.6**. Level gate catches high composite even if percentile calc is edge-case. |
| **Evidence** | Level ≥0.6: n=57, 3m avg SPX **+5.7%**, win **3.5%** → **REJECTED**. Level ≥0.85: n=30, still positive 3m avg but **less bad** than 0.6. Level ≥0.9: n=23. |
| **Rejected** | **`short_entry: 0.6`** — Open Questions + sweep: fires too often, SPX still rallies. |
| **Status** | **APPROVED** — secondary; supports asymmetric story with B3 |

## B5. Rejected symmetric pair: `long −0.6` / `short +0.6`

| | |
|--|--|
| **Why rejected** | Spec and data: **bottoms sharp, tops slow**. +0.6 short = 57 historical fires with **~96%** of 3m paths still positive for SPX (short “win” ~3.5%). |
| **Status** | **REJECTED** for shorts; long −0.6 kept only as non-firing secondary |

---

# Part C — Layer 2 confirmation (size multiplier, not direction)

Layer 2 does **not** flip long/short. It sets **`ssi_multiplier`**: 1.2 (confirmed), 1.0 (partial), 0.8 (unconfirmed).

## C1. `layer2.min_confirmed: 2` (≥2 of **6** gates, same side)

| | |
|--|--|
| **Plain English** | Need **at least 2 of 6** Layer 2 gates to agree on the **same direction** (long vs short) for `LONG_CONFIRMED` / `SHORT_CONFIRMED`. Short tally must stay below N (else `CONTESTED`). |
| **Why** | Reduces false positives from one noisy indicator; briefing: “prevents false positives from sentiment alone.” **Not empirically derived** before Aug 2026 — design intent. |
| **Evidence** | **Test 10** (legacy 4-input): min_votes 0–3 identical on long-gate days — not comparable to 6-gate. **Test 22** (6-gate joint grid, 2010–2026): at `gate_z_min=0.5`, min=2 → n=**180** long+gate, **45%** 3m hit; min=3 → n=**141**, **46%** hit; min=4 → n=**25** (too thin). Raising count alone does not monotonically improve quality. |
| **Alternatives** | min=3 at z=0.5 (fewer fires, similar hit). z≥1.25 + min=2 (n=94, **52%** hit). min=4 eliminates most signal. |
| **Status** | **PENDING Rohit** — design default defensible; Test 22 shows trade-offs, not a single optimum. |

## C2. Multipliers: CONFIRMED **1.20**, PARTIAL **1.00**, UNCONFIRMED **0.80**

| Status | Multiplier | Plain English |
|--------|------------|---------------|
| CONFIRMED | 1.2 | Increase intended size when sentiment **confirms** the trade direction context |
| PARTIAL | 1.0 | Neutral |
| UNCONFIRMED | 0.8 | Reduce size when signals **disagree** |

**Why 20% up / 20% down:** Round, symmetric sizing bands; Open Questions asked to validate **VIX regime** interaction (Test 11), not to re-optimize these three numbers. Oct 2022: Combo B → **`vix_bypass`** overrides reduction when macro says so.

**Evidence:** Test 11 — Combo B Oct 2022 → `vix_bypass: true`. Full 20y equity curve **not** run (waived).

**Status:** **APPROVED (design)**

## C3. HYG/LQD vote: `risk_on_pctile_min: 70`, `risk_off_pctile_max: 30`

| Threshold | Vote fires when |
|-----------|-----------------|
| **≥ 70th percentile** | HYG/LQD ratio unusually **high** → **risk-on** vote |
| **≤ 30th percentile** | Ratio unusually **low** → **risk-off** vote |

**Plain English:** Compares **today’s** HYG/LQD ratio to its own ~5y history (percentile), not the Open Questions “−1.5% in 4 weeks” rule (that’s Test 8 for research).

**Why 70/30:** Classic “extreme third-ish” band (top/bottom ~30%). Wider than 80/20 → more votes, less missing credit turns.

**Evidence:** Test 8 — 4w drop &lt;−1.5%: n=70 stress episodes, median **3 days** to VIX&gt;25; supports **risk-off** vote logic. Test 3–4 grids use **different** FM/RM rules (macro CFTC, not this vote).

**Status:** **APPROVED (design)** — Layer 2 uses percentile of **level**; Test 8 validates **change** threshold for spec completeness

## C4. DBMF beta vote: `low_beta_max: 0.5`, `high_beta_min: 1.2`

| Threshold | Plain English |
|-----------|---------------|
| **beta ≤ 0.5** | “Low beta” → vote (CTAs not strongly long equities) |
| **beta ≥ 1.2** | “High beta” → vote (strong equity beta) |

**Why:** Open Questions suggested **&lt; −0.10** for “CTAs short equities” in signal research. Layer 2 uses **absolute beta bands** on the 21-day DBMF/SPY regression — different scale. **0.5** = subdued equity beta; **1.2** = elevated.

**Evidence:** Test 7 — beta &lt; −0.10: n≈29 crossing episodes; 2w forward mixed. Production bands are **not** identical to Test 7 cutoffs; Test 7 informs **direction**, not exact YAML numbers.

**Status:** **APPROVED (design)** — consider aligning research threshold (−0.10) in a future Layer 2 revision

## C5. CNN Fear & Greed vote: `fear_max: 25`, `greed_min: 75`

| Threshold | Vote fires when |
|-----------|-----------------|
| **≤ 25** | Extreme **fear** |
| **≥ 75** | Extreme **greed** |

**Why:** Matches composite CNN mapping (A5). Test 6 studied **crossings** at &lt;20 / &gt;80 (stricter); few greed crossings in data.

**Evidence:** Test 6 — fear &lt;20 rare (n=3); when fear extreme, longer horizons often positive SPX (buy fear). Supports fear vote as **contrarian stress**, not “short stocks.”

**Status:** **APPROVED (design)**

## C6. VIX ratio vote: `stress_min: 1.05`, `complacency_max: 0.95`

| Threshold | Vote fires when |
|-----------|-----------------|
| **≥ 1.05** | Term structure **stress** (near vol &gt; longer-dated) |
| **≤ 0.95** | **Complacency** (contango / calm) |

**Why:** Same as composite (A6). Macro Friday checklist uses **1.10** for “D combo” style flags — Layer 2 is **slightly more sensitive** (1.05).

**Status:** **APPROVED (design)**

---

# Part D — Research / macro thresholds (spec Part 9, not all in SSI YAML)

Documented here so one file covers **all** numbers the Open Questions doc raised.

## D1. SQUEEZE (Test 3): FM percentile **&lt; 30–40**, RM **&gt; 40–65**

| | |
|--|--|
| **Spec intent** | Fast Money (speculators) very low vs Real Money still high → “squeeze” setup. |
| **What we tested** | Grid of FM/RM percentile pairs; many cells **n &gt; 160** (2006–2026). |
| **In SSI production?** | **No** — lives in **Runic/CFTC macro** context, not Layer 2 votes. |
| **Status** | **APPROVED** as macro research; **not** SSI CONFIG keys |

## D2. LIQUIDITY EXIT (Test 4): RM **&lt; 15–40**, FM **&gt; 45–75**

| | |
|--|--|
| **Spec intent** | Real Money exiting while specs still elevated. |
| **Evidence** | Many combinations n ≈ 96–123. |
| **In SSI production?** | **No** — macro combo research. |
| **Status** | **APPROVED** as macro research |

## D3. HYG/LQD 4-week change (Test 8): **−1.0%, −1.5%, −2.0%, −3.0%**

| Cutoff | n (episodes) | Note |
|--------|----------------|------|
| −1.0% | 110 | More fires |
| −1.5% | 70 | Spec “RARE” candidate |
| −2.0% | 52 | |
| −3.0% | stricter | Fewer fires |

**Production:** Layer 2 uses **ratio percentile**, not 4w % change. **−1.5%** justified as **spec-aligned stress** if we add a dedicated “widening” flag later.

**Status:** **APPROVED** for spec; **ALTERNATIVE** to wire into Layer 2

## D4. DBMF beta research (Test 7): **−0.05, −0.10, −0.15, −0.20**

**Production Layer 2** uses 0.5 / 1.2 beta bands (C4). **−0.10** is the Open Questions “CTAs short equities” research line.

**Status:** **−0.10 APPROVED** for narrative; **0.5 / 1.2 APPROVED (design)** for votes until recalibrated

## D5. CNN crossings (Test 6): **&lt;20, &lt;10, &gt;80, &gt;90**

| | |
|--|--|
| **Finding** | Extreme **fear** crossings rare; **greed** &gt;80/90 had **0** crossings in this run (data/crossing definition). |
| **Production** | Votes use **25 / 75** levels, not crossing rules. |
| **Status** | **&lt;20 fear APPROVED** as “buy fear” narrative; **greed shorts** need more CNN history before tightening past **75** |

## D6. Take profit / stop loss (Test 5): **10× / 15×** daily vol

| | |
|--|--|
| **Spec** | TP = entry × (1 + **10** × daily vol); SL = entry × (1 − **15** × daily vol) for longs (MindWealth PulseGauge). |
| **Evidence** | Adapter sweeps TP 5–20, SL 8–25 on SPY; best Sharpe in sample near grid middle (not archived in repo JSON yet). |
| **In SSI YAML?** | **No** — C++ / strategy layer, not `SSI_CONFIG.yaml`. |
| **Status** | **PENDING** full archived run; **10/15 APPROVED (design)** from legacy code until sweep signed |

## D7. Z-score vs percentile SSI (Test 9)

| | |
|--|--|
| **Question** | Should the **composite** use percentile ranks instead of z-scores? |
| **Decision** | **Keep z-scores** in production; percentile composite is experimental. |
| **Status** | **REJECTED for production switch** until Rohit sign-off |

## D8. COT FM long gate (Test 18): `cot_fast_money_max_pct` **15–45**

| | |
|--|--|
| **Spec intent** | Long-entry **condition 3**: Fast Money net positioning below Xth percentile of 3yr rolling window → contrarian long confirmation. PDF default **&lt;30** was never validated. |
| **What we tested** | Weekly CFTC FM net percentile sweep **15, 20, 25, 30, 35, 40, 45**; SPX forward returns 1w–12m on all weeks where FM &lt; X (2010–2026). Artifact: `18_cot_fm_long_gate_20260807.json`. |
| **Key results (3m horizon)** | FM&lt;**15**: n=154, +2.83%, 72.7% win. FM&lt;**20**: n=198, **+3.13%**, **73.7%** win. FM&lt;**30** (PDF): n=268, +2.78%, 72.8% win. FM&lt;**45**: n=378, +2.97%, 74.9% win. |
| **6m horizon** | FM&lt;20 peaks at **+8.35%** (87.7% win, n=195); FM&lt;30 +7.48%; FM&lt;45 +6.95%. Tighter cutoff = higher per-event return, fewer fires. |
| **In SSI production?** | **No** — macro/Runic long-confirmation context (`LONG_RULES['cot_fast_money_max_pct']` in spec; not wired to SSI CONFIG or sizing). |
| **Recommendation** | **FM&lt;20–25** for long confirmation; keep **30** only if Rohit prefers frequency over hit rate. |
| **Status** | **APPROVED** as research; **PENDING** Rohit sign-off before CONFIG change |

---

# Part E — Decision summary table (production CONFIG)

| Parameter | Value | Primary justification | Status |
|-----------|-------|----------------------|--------|
| `long_entry_pctile` | **20** | Bottom 20% of 5y SSI; n=16, ~81% SPX up @ 3m | **APPROVED** |
| `long_entry` | **−0.6** | Spec legacy; 0 fires on sweep | Secondary only |
| `short_entry_pctile` | **85** | Top 15% of 5y; avoids early +0.6 shorts | **APPROVED** |
| `short_entry` | **0.85** | Asymmetric with long; rejects +0.6 | **APPROVED** |
| `short_entry` | **+0.6** | — | **REJECTED** |
| `min_confirmed` | **2** | 2 of 4 votes | **APPROVED (design)** |
| `CONFIRMED` / `PARTIAL` / `UNCONFIRMED` | **1.2 / 1.0 / 0.8** | Size bands | **APPROVED (design)** |
| `hyg_lqd` vote | **70 / 30** | Credit extreme percentiles | **APPROVED (design)** |
| `dbmf_beta` vote | **0.5 / 1.2** | Beta bands | **APPROVED (design)** |
| `cnn_fg` vote | **25 / 75** | Fear / greed | **APPROVED (design)** |
| `vix_ratio` vote | **1.05 / 0.95** | Stress / complacency | **APPROVED (design)** |
| Composite weights | **30/25/25/20** | Credit-heavy blend | **APPROVED (design)** |
| `zscore_clip` | **3.0** | Limit tail impact | **APPROVED (design)** |
| Percentile SSI composite | — | Test 9 | **Not production** |

---

# Part F — What Rohit should confirm

1. **Short percentile 85 vs 90** — More fires (85) vs stricter greed (90).  
2. **Long percentile 20 vs 10** — Sweep favors 10 on avg 3m return but only 5 events.  
3. **DBMF vote bands (0.5 / 1.2) vs research −0.10** — Align Layer 2 with Test 7 or keep design bands.  
4. **Sign [SIGNOFF.md](SIGNOFF.md)** after reviewing this doc and [01_long_threshold_sweep.md](01_long_threshold_sweep.md).

---

# Part G — How to re-run evidence

```bash
cd /home/ubuntu/uiv2/git/MindWealth_UI
.venv/bin/python scripts/run_ssi_validation_suite.py --start 2015-01-01
```

Update this document when CONFIG changes or a new validation stamp is produced.

---

*This is the single threshold-justification reference. Narrative overview: [SSI_OPEN_QUESTIONS_SUMMARY.md](SSI_OPEN_QUESTIONS_SUMMARY.md). Raw tables: `01`–`16` reports and `macro_intelligence/analysis/ssi_validation/*.json`.*
