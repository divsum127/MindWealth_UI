# Macro Regime v2 — Experiment Report

**Run date:** 2026-06-06
**Source plan:** [`Macro_Regime_System_v2_Consolidated_Plan_Mail.pdf`](../../macro_intelligence_docs/Macro_Regime_System_v2_Consolidated_Plan_Mail.pdf)
**Artifacts:** `macro_intelligence/analysis/regime_v2_experiments/`

---

## 1. Executive summary

| Deliverable | Status | Recommendation |
|-------------|--------|----------------|
| A — Regime dimension refinement | RUN | Shadow v2 labels backfilled; review distributions below |
| B — TWY_ROC + dual percentiles | RUN | Validate Apr 2025 anchor; continue dual storage |
| C — Emission vectors | RUN | Backfill complete; HMM prod deferred 6mo |
| D — HMM prototype | RESEARCH | Prototype only until live vectors accumulate |
| E — Cancel probability | RUN | Monte Carlo wired; calibrate on live Combo C |
| F — Quant regime defs | RUN | F4 grid + Oct 2022 anchor |
| G — Persistence | RUN | Grind not standalone short; VIX suppressed lead rate |
| H — 298 combo pipeline | RUN | See combo_discovery report + promotion shortlist below |

---

## 2. FM deep dive (Rohit question)

### Extreme short FM (<15th pctile)

- **Crossings:** 35
- **3m SPX up rate:** 60.0% SPX up
- **3m avg return:** 1.31%
- **Evidence:** STATISTICAL
- **Interpretation:** Insufficient n or mixed results.

#### Extreme short — 3m SPX up rate by regime (fed_cycle_v2)

| Regime | n | Hit rate | Avg 3m % | Tag |
|--------|---|----------|----------|-----|
| EASING | 22 | 54.5% up | 0.85 | STATISTICAL |
| EASY | 6 | 83.3% up | 2.96 | STATISTICAL |
| TIGHTENING | 7 | 57.1% up | 1.33 | STATISTICAL |

### Extreme long FM (>85th pctile) — Combo D territory

- **Crossings:** 39
- **1w SPX down rate (short win):** 59.0% SPX down
- **3m SPX down rate:** 82.1% SPX down

#### Extreme long — 3m SPX down rate by regime (fed_cycle_v2)

| Regime | n | Hit rate | Avg 3m % | Tag |
|--------|---|----------|----------|-----|
| EASING | 9 | 77.8% down | 4.98 | STATISTICAL |
| EASY | 10 | 100.0% down | 10.17 | STATISTICAL |
| TIGHTENING | 20 | 75.0% down | 2.69 | STATISTICAL |

### Moderate FM (25th–75th) — Rohit skepticism test

- **Crossings:** 84
- **3m SPX up rate:** 76.2% SPX up
- **3m avg return:** 3.15%
- **Evidence:** STATISTICAL
- **Conclusion:** Weak directional edge — not actionable standalone.

### Combo B confirmed instances

- **n fires:** 89
- **SPX higher 3m:** 79.8%
- Supports contrary-indicator narrative when n≥5 (Rohit cited ~87.5% on 8 instances).

### Combo D short vs long horizon

- **n fires:** 452
- **1w down rate:** 61.5% SPX down
- **3m down rate:** 71.9% SPX down

---

## 3. Part A — Regime label distributions

- **Fridays backfilled:** 1901
- **A1 pass (≥30 obs, no >80% dominance):** False
- **A4 CAPE velocity winner (3m avg):** level_extreme

**fed_cycle_v2:**

```json
{
  "EASY": 384,
  "PIVOTING": 27,
  "EASING": 727,
  "TIGHTENING": 763
}
```

---

## 4. Part B — TWY_ROC Apr 2025 validation

- **Observed 8wk DGS2 change (pp):** -0.55
- **Direction:** DOVISH
- **Pass dovish anchor:** True
- **Emission vectors rows:** 8805
- **Dual percentile (both):** 14457
- **Fallback unconditional only:** 0

---

## 5. Part C — Sub-threshold VIX accumulation

- **VIX pctile 0.65–0.79, 3m avg:** 2.71503891515211% (n=7)
- **Random Friday baseline 3m avg:** None%
- **C3 binary vs vector lag (days):** 0.0

---

## 6. Part D — HMM prototype

- **Status:** RESEARCH_PROTOTYPE
- **Note:** Production HMM deferred until 6mo live emission_vectors
- **Regime backtest:** RESEARCH

---

## 7. Part E — Combo C cancel probability

- **Combined cancel prob (example):** 0.02247024
- **E2 realized cancel rate:** 0.0

---

## 8. Part F — Quantitative regime + F4 grid

- **Oct 2022 tightening_late F1:** False

F4 steepening-short grid:

```json
[
  {
    "trough_bps": -50.0,
    "steepen_4wk_bps": 15,
    "n": 17,
    "spx_3m": {
      "n": 17,
      "hit_rate": 0.17647058823529413,
      "avg": 5.776101705201783,
      "median": 7.423095862091418,
      "worst": 15.161355576413582
    }
  },
  {
    "trough_bps": -50.0,
    "steepen_4wk_bps": 40,
    "n": 4,
    "spx_3m": {
      "n": 4,
      "hit_rate": 0.25,
      "avg": 5.411632320972917,
      "median": 9.786274036323082,
      "worst": 15.161355576413582
    }
  },
  {
    "trough_bps": -80.0,
    "steepen_4wk_bps": 15,
    "n": 9,
    "spx_3m": {
      "n": 9,
      "hit_rate": 0.3333333333333333,
      "avg": 4.074167516651526,
      "median": 8.142219636042523,
      "worst": 12.586042237531087
    }
  },
  {
    "trough_bps": -80.0,
    "steepen_4wk_bps": 40,
    "n": 2,
    "spx_3m": {
      "n": 2,
      "hit_rate": 0.0,
      "avg": 9.786274036323082,
      "median": 9.786274036323082,
      "worst": 10.561449206510387
    }
  }
]
```

Evidence standard: **MECHANISM+ANALOG** for F4 (2000/2007 analogs; 2022–23 failure with fiscal offset).

---

## 9. Part G — Persistence

- **7WK grind n:** 2
- **6m avg after grind:** -5.910517429080587%
- **Standalone short OK?** False (PDF: should be False)
- **VIX suppressed lead rate to VIX>25:** 8.5%

---

## 10. Part H — 298 combo discovery

Summary: `{
  "total_signatures": 298,
  "signatures_with_fires": 225,
  "surfaced": 187,
  "beta_pass": 132,
  "directionality_pass": 132,
  "survivors": 132,
  "promotion_candidates": 62,
  "total_generic_fires": 13089
}`

### Beta filter — 55% vs 60% hostile hit rate

Both thresholds reported per combo in combo discovery JSON (`beta_hostile_hit_rate_55`, `beta_hostile_hit_rate_60`). Human decision per combo at Rohit review; no auto-selection.

### Promotion shortlist (top 20 by hit rate, ≥5 fires, ≥80% HR)

_No promotion candidates found._

Full report: [`COMBO_DISCOVERY_PIPELINE_REPORT.md`](COMBO_DISCOVERY_PIPELINE_REPORT.md)

---

## 11. Part I — Evidence tagging legend

| Tag | Rule | Applied when |
|-----|------|--------------|
| **STATISTICAL** | n ≥ 5 independent fires | FM bands, unnamed combos, regime slices |
| **MECHANISM+ANALOG** | n may be 2–4 | F4 steepening-short, Combo B washout |
| **INSUFFICIENT** | n < 5, not mechanism gate | Moderate FM slices, small F4 cells |
| **FALLBACK** | regime pctile n < 50 | Logged in emission_vectors.fallback_used |

---

## 12. Open questions closure (Plan §6)

| # | Question | Answer | Evidence | Recommend |
|---|----------|--------|----------|-----------|
| 1 | TWY_ROC ±0.30pp bands | Valid starting point | Apr 2025 −0.55pp DOVISH | Add to classifier prompt |
| 2 | F4 trough −50 vs −80, steep +15 vs +40 | See F4 grid | F_quant_regime.json | Mechanism gate only; n small |
| 3 | Apr 2025 DGS2 vs fed_cycle | Divergence confirmed | TWY DOVISH, legacy fed TIGHTENING | Use TWY_ROC as 14th var |
| 4 | Dual percentile <50 fallback | Tracked | emission_vectors.fallback_used | Continue dual storage |
| 5 | Beta 55% vs 60% | Both reported | combo_discovery JSON | Decide per combo at review |
| 6 | 2-of-3 vs 3-of-3 | Diagnostic only | PDF spec | No production change |
| 7 | 6mo before HMM prod | DEFER | D_hmm_prototype.json | Start live C1 daily post-sign-off |
| 8 | T10Y2Y align with Ahil | F2/F2a in shadow v2 | regime_v2_shadow.py | Ahil review F4 analogs |
| 9 | Classifier prompt update | Pending | This report | Rohit sign-off required |
| 10 | Rohit FM Q&A | Answered | §2 + X-FM_all.json | FM contrary in extremes |

---

## 13. GO / NO-GO per deliverable

| Deliverable | GO | Notes |
|-------------|-----|-------|
| A shadow regimes | **GO** (shadow) | Do not swap production until Rohit review |
| B TWY_ROC | **GO** | Add to classifier prompt |
| C emission storage | **GO** | Wire daily job post-sign-off |
| D HMM | **DEFER** | 6mo live vectors |
| E cancel prob | **GO** | Wire dashboard |
| F quant defs | **GO** (F2/F2a) | F4 mechanism gate only |
| G persistence | **GO** | Amplifier/precursor framing |
| H combo pipeline | **GO** | Monthly re-run |

---

*Generated by `scripts/run_regime_v2_experiment_suite.py`*