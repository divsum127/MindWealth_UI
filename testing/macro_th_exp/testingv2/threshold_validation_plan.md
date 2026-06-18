# Macro Variable Threshold Validation — Testing v2 Plan

**Date:** 2026-06-16  
**Goal:** Confirm whether current threshold values for all 12 macro variables are optimal. For each variable, sweep multiple threshold levels above and below the current RARE/EXTREME cutoffs and measure whether a different value produces meaningfully better forward SPX returns (using probability-weighted PW framework from Rohit spec).

**Primary output:** Per-variable threshold comparison tables → `macro_intelligence/analysis/regime_v2_experiments/threshold_sweep_v2/`  
**Script to build:** `scripts/threshold_sweep_v2.py`  
**Status tracker:** `testingv2_status.md` (this directory)

**Related artifacts:**
- Feedback & prior work: `testing/macro_th_exp/testingv1_feedback/` (`feedback_sectionwise_details.md`, `testingv2_plan.md`, `testingv2_report.md`, `testingv4_plan.md`)
- Prior sweep (broken): `scripts/per_variable_threshold_sweep.py` → `macro_intelligence/analysis/regime_v2_experiments/F_per_variable_sweep.json`
- Combo sweep stub: `src/macro_intelligence/analysis/combo_threshold_sweep.py` (Combo B only; no PW / hostile slice)
- Current thresholds: `macro_intelligence/CONFIG.yaml`

---

## Context: Current Thresholds (from `macro_intelligence/CONFIG.yaml`)

| Variable | Paradigm | Window | RARE threshold | EXTREME threshold | Direction |
|----------|----------|--------|----------------|-------------------|-----------|
| **NFCI** | DUAL (level) | full (1973) | pctile ≥80 or ≤20; SD ≥±0.3 | pctile ≥95 or ≤5; SD ≥±0.8 | UP=tight, DOWN=easy |
| **HY** | DUAL | full (1996) | OAS ≥400bps or pctile ≥80 | OAS ≥500bps or pctile ≥95 | UP=widening |
| **VIX** | DUAL | full (1990) | level ≥25 AND pctile ≥80 | level ≥35 AND pctile ≥95 | UP=fear |
| **VXTS** | RATIO | full (2007) | ratio ≤0.95 or ≥1.10 | ratio ≤0.85 or ≥1.20 | UP if >1 (backwardation) |
| **CFTC** | PCTILE | rolling_3y | pctile ≤15 or ≥85 | pctile ≤5 or ≥95 | DOWN if ≤50 |
| **WTI** | ROC | rolling_3y | \|4wk%\| ≥6.0% | \|4wk%\| ≥10.0% | UP/DOWN by sign |
| **CNH** | ROC | rolling_3y | \|4wk%\| ≥1.5% | \|4wk%\| ≥3.5% | UP/DOWN by sign |
| **WALCL** | ROC | full (2008) | MoM% ≥±0.8% | MoM% ≥±2.0% | UP/DOWN by sign |
| **GSR** | ROC | rolling_3y | \|4wk%\| ≥5.0% | \|4wk%\| ≥8.0% | UP/DOWN by sign |
| **CPI** | ABS | rolling_3y | \|surprise\| ≥0.2pp | \|surprise\| ≥0.4pp | UP if hot |
| **CAPE** | ABS | full (1881) | level ≥28 or ≤16 | level ≥32 or ≤12 | UP if high |
| **CURVE** | DUAL | full (1976) | spread ≤−30bps or steepen ≥15bps | spread ≤−80bps or steepen ≥40bps | DOWN if inverted |

**Known issues (verified 2026-06-16):**

1. **Percentile scale mismatch** — `percentiles.py` computes `unconditional_pctile` on **0–100** scale, but `daily_readings` has **mixed storage**: ~220 rows ≤1.0 (legacy 0–1) vs ~14,285 rows >1.0 (current 0–100). Example: VIX min=0.014, max=100.0.
2. **Sweep script bands on 0–1** — `per_variable_threshold_sweep.py` uses bands like `0.70–0.79`, which only match legacy rows; 13/22 bands in `F_per_variable_sweep.json` have `n_events=0`.
3. **Pctile-only, not CONFIG thresholds** — prior sweep tests percentile bands (70–79 vs 80+), not raw RARE/EXTREME cutoffs (VIX≥25, HY≥400bps, etc.) and excludes **CURVE** (11 vars only).
4. **No hostile-regime slice** — prior results lack HIKING/INVERTED subset required by Rohit §7.

This plan uses **normalized 0–100 pctiles**, **raw-value bands** per CONFIG, **first-crossing** logic, and **hostile-regime PW** re-slices.

---

## Experiment Design

### What we are testing

For each variable independently (not in combo), we ask:
> "If the RARE entry threshold were set at value X instead of the current value, would the distribution of SPX forward returns at 1m/3m/6m/9m/12m be materially better?"

This is a **single-variable isolation test** — NOT the full combo engine. It answers: does the threshold value for variable X add incremental signal vs lower/higher values?

### Return metric: Probability-Weighted (PW) framework (Rohit spec)

For each threshold band, compute:
- **n** = number of first-crossing events (variable enters band from below/above)
- **Hit rate** = % of events where SPX moved in predicted direction
- **Avg win** = mean SPX return in predicted-direction instances
- **Avg loss** = mean SPX return in counter-direction instances  
- **PW expected** = `(hit_rate × avg_win) + ((1 − hit_rate) × avg_loss)`
- **Benchmark** = unconditional drift (+0.5% 1m, +2.5% 3m, +5% 6m, +10% 12m)
- **Excess** = PW expected − benchmark

**Signal fires when:** variable crosses from below threshold into the band (first-crossing logic to avoid counting a single prolonged episode many times).

### Horizons

Every table shows: **1m / 3m / 6m / 9m / 12m** (21 / 63 / 126 / 189 / 252 trading days).

| Horizon | Trading days | Unconditional benchmark (SPX drift) |
|---------|--------------|-------------------------------------|
| 1m | 21 | +1.25% |
| 3m | 63 | +2.5% |
| 6m | 126 | +5.0% |
| 9m | 189 | +7.5% |
| 12m | 252 | +10.0% |

Source: `src/macro_intelligence/analysis/regime_experiments/metrics.py` (`BENCHMARK_PCT`).

### Hostile-regime validation (success criterion #4)

For each band at its primary horizon, re-compute PW on the **hostile subset** only:

| Hostile dimension | Values (from CONFIG) | Join key |
|-------------------|----------------------|----------|
| Fed cycle | `HIKING_EARLY`, `HIKING_LATE`, `TIGHTENING` | `regime_snapshots.fed_cycle` on event date |
| Yield curve | `INVERTED` | `regime_snapshots.curve_regime` |

Event is **hostile** if either condition holds. Report: `n_hostile`, `hit_rate_hostile`, `pw_expected_hostile`, `excess_hostile`. A threshold change **fails** criterion #4 if hostile `excess_hostile` drops >2pp vs current threshold (prevents QE/bull-only overfitting per Rohit `Additional_email.md` §7).

---

## Per-Variable Sweep Bands

### 1. VIX (level + percentile, full history 1990)

**Current RARE:** level ≥25 AND pctile ≥80  
**Current EXTREME:** level ≥35 AND pctile ≥95  
**Direction:** UP (VIX spike = bearish signal for equities)

| Band to test | VIX level | Pctile approx | Hypothesis |
|---|---|---|---|
| T1 | ≥15 (low caution) | ~50th | Very loose — likely noise |
| T2 | ≥18 (moderate) | ~60th | Starting to matter? |
| T3 | ≥20 (elevated) | ~65–68th | Below current RARE |
| **T4 (CURRENT RARE)** | ≥25 | ~80th | Baseline |
| T5 | ≥28 | ~85th | Tighter — fewer but higher conviction? |
| T6 | ≥30 | ~88th | |
| **T7 (CURRENT EXTREME)** | ≥35 | ~95th | Extreme baseline |
| T8 | ≥40 | ~97th | Very rare (2008, 2020 only) |

Also test: VIX **65–79th pctile band** (sub-RARE) — already has 7 instances in existing sweep with 85.7% hit rate.

### 2. HY (OAS spread level + percentile, full history 1996)

**Current RARE:** OAS ≥400bps OR pctile ≥80  
**Current EXTREME:** OAS ≥500bps OR pctile ≥95

| Band | OAS bps | Hypothesis |
|---|---|---|
| T1 | ≥300 | Very early stress |
| T2 | ≥350 | Moderate stress |
| **T3 (CURRENT RARE abs)** | ≥400 | Baseline |
| T4 | ≥450 | Tighter |
| **T5 (CURRENT EXTREME abs)** | ≥500 | Extreme baseline |
| T6 | ≥600 | GFC/COVID levels only |
| T7 | pctile ≥70 | Pctile-only, below current 80 |
| T8 | pctile ≥75 | |

### 3. CFTC (Fast Money net pctile, rolling_3y)

**Direction:** Short-side (pctile ≤15 = extreme short = contrarian bullish)  
**Current RARE:** pctile ≤15 or ≥85  
**Current EXTREME:** pctile ≤5 or ≥95

Short side (bearish FM = contrarian long signal):

| Band | Pctile ≤ | Hypothesis |
|---|---|---|
| T1 | ≤30 | Wide net |
| T2 | ≤20 | |
| **T3 (CURRENT RARE)** | ≤15 | Baseline |
| T4 | ≤10 | Tighter |
| **T5 (CURRENT EXTREME)** | ≤5 | Extreme baseline |

Long side (FM crowded long = bearish signal):

| Band | Pctile ≥ | Hypothesis |
|---|---|---|
| T1 | ≥70 | |
| T2 | ≥80 | |
| **T3 (CURRENT RARE)** | ≥85 | Baseline |
| T4 | ≥90 | |
| **T5 (CURRENT EXTREME)** | ≥95 | |

### 4. NFCI (financial conditions, full history 1973)

**Direction:** Low NFCI (≤−0.3) = EASY = bullish; High NFCI (≥+0.3) = TIGHT = bearish  
**Current RARE:** pctile ≤20 (easy) or ≥80 (tight); SD ≤−0.3 or ≥+0.3

Easy side (contrarian bullish after extreme tightness resolves):

| Band | NFCI SD ≤ | Pctile ≤ |
|---|---|---|
| T1 | −0.1 | 35 |
| T2 | −0.2 | 25 |
| **T3 (CURRENT)** | −0.3 | 20 |
| T4 | −0.5 | 12 |
| T5 | −0.8 | 5 |

Tight side (bearish):

| Band | NFCI SD ≥ | Pctile ≥ |
|---|---|---|
| **T1 (CURRENT)** | +0.3 | 80 |
| T2 | +0.5 | 88 |
| T3 | +0.8 | 95 |

### 5. WALCL (Fed balance sheet MoM%, full history 2008)

**Current RARE:** MoM ≥±0.8%  
**Current EXTREME:** MoM ≥±2.0%

Expansion side (bullish — QE signal):

| Band | MoM% ≥ |
|---|---|
| T1 | +0.3% |
| T2 | +0.5% |
| **T3 (CURRENT RARE)** | +0.8% |
| T4 | +1.5% |
| **T5 (CURRENT EXTREME)** | +2.0% |
| T6 | +3.0% |

Contraction side (bearish — QT signal):

| Band | MoM% ≤ |
|---|---|
| T1 | −0.3% |
| T2 | −0.5% |
| **T3 (CURRENT RARE)** | −0.8% |
| T4 | −1.5% |
| **T5 (CURRENT EXTREME)** | −2.0% |

### 6. WTI (4-week % change, rolling_3y)

**Current RARE:** |4wk%| ≥6.0%  
**Current EXTREME:** |4wk%| ≥10.0%

Down side (crude collapse = Combo C entry, also Combo F catalyst):

| Band | 4wk% ≤ |
|---|---|
| T1 | −3% |
| T2 | −5% |
| **T3 (CURRENT RARE)** | −6% |
| T4 | −8% |
| **T5 (CURRENT EXTREME)** | −10% |
| T6 | −15% |

Up side (crude spike = inflation risk, Combo C):

| Band | 4wk% ≥ |
|---|---|
| T1 | +5% |
| **T2 (CURRENT RARE)** | +6% |
| T3 | +8% |
| **T4 (CURRENT EXTREME)** | +10% |
| T5 | +15% |

### 7. CNH (USD/CNH 4wk%, rolling_3y)

**Current RARE:** |4wk%| ≥1.5%  
**Current EXTREME:** |4wk%| ≥3.5%

Up side (CNH weakening = RMB stress, risk-off):

| Band | 4wk% ≥ |
|---|---|
| T1 | +0.5% |
| T2 | +1.0% |
| **T3 (CURRENT RARE)** | +1.5% |
| T4 | +2.5% |
| **T5 (CURRENT EXTREME)** | +3.5% |

Down side (CNH strengthening):

| Band | 4wk% ≤ |
|---|---|
| T1 | −0.5% |
| T2 | −1.0% |
| **T3 (CURRENT RARE)** | −1.5% |
| T4 | −2.5% |
| **T5 (CURRENT EXTREME)** | −3.5% |

### 8. GSR (Gold/Silver Ratio 4wk%, rolling_3y)

**Current RARE:** |4wk%| ≥5.0%  
**Current EXTREME:** |4wk%| ≥8.0%

Up side (GSR rising = gold outperforming = risk-off):

| Band | 4wk% ≥ |
|---|---|
| T1 | +2% |
| T2 | +3% |
| T3 | +4% |
| **T4 (CURRENT RARE)** | +5% |
| T5 | +6% |
| **T6 (CURRENT EXTREME)** | +8% |
| T7 | +10% |

### 9. VXTS (VIX3M/VIX ratio, full history 2007)

**Backwardation (VXTS > 1 → stress signal):**

| Band | Ratio ≥ |
|---|---|
| T1 | 1.02 |
| T2 | 1.05 |
| **T3 (CURRENT RARE)** | 1.10 |
| T4 | 1.15 |
| **T5 (CURRENT EXTREME)** | 1.20 |

**Contango (VXTS < 1 → complacency, Combo D):**

| Band | Ratio ≤ |
|---|---|
| **T1 (CURRENT RARE)** | 0.95 |
| T2 | 0.90 |
| **T3 (CURRENT EXTREME)** | 0.85 |
| T4 | 0.80 |

### 10. CAPE (Shiller P/E, full history 1881)

**Current RARE:** ≥28  
**Current EXTREME:** ≥32  

High side (valuation extreme = bearish 12m):

| Band | CAPE ≥ |
|---|---|
| T1 | 22 (historical avg) |
| T2 | 25 |
| **T3 (CURRENT RARE)** | 28 |
| T4 | 30 |
| **T5 (CURRENT EXTREME)** | 32 |
| T6 | 35 |
| T7 | 38 (current region) |

Low side (CAPE cheap = contrarian bullish):

| Band | CAPE ≤ |
|---|---|
| **T1 (CURRENT RARE)** | 16 |
| T2 | 14 |
| **T3 (CURRENT EXTREME)** | 12 |

### 11. CPI Surprise (rolling_3y)

**Current RARE:** |surprise| ≥0.2pp  
**Current EXTREME:** |surprise| ≥0.4pp

Hot side (CPI beats = bearish signal via Combo C):

| Band | Surprise ≥ |
|---|---|
| T1 | +0.05pp |
| T2 | +0.10pp |
| **T3 (CURRENT RARE)** | +0.20pp |
| T4 | +0.30pp |
| **T5 (CURRENT EXTREME)** | +0.40pp |
| T6 | +0.60pp |

### 12. CURVE (10Y–2Y spread + steepening, full history 1976)

**Inversion side:**

| Band | Spread ≤ |
|---|---|
| T1 | −10bps |
| T2 | −20bps |
| **T3 (CURRENT RARE)** | −30bps |
| T4 | −50bps |
| **T5 (CURRENT EXTREME)** | −80bps |
| T6 | −100bps |

**Steepening-from-inversion side:**

| Band | 4wk steepen ≥ |
|---|---|
| T1 | +5bps |
| T2 | +10bps |
| **T3 (CURRENT RARE)** | +15bps |
| T4 | +25bps |
| **T5 (CURRENT EXTREME)** | +40bps |

---

## Script Plan: `scripts/threshold_sweep_v2.py`

### Architecture

```python
# Key functions to build:

def first_crossings(series, threshold, direction='up'):
    """Return dates where series crosses threshold from below (direction='up')
    or above (direction='down'). Uses 1-week cooldown to avoid re-triggering."""

def compute_pw_returns(crossing_dates, spx, horizon_days, direction):
    """For each crossing date, get SPX forward return at horizon.
    Compute: n, hit_rate, avg_win, avg_loss, pw_expected, benchmark, excess."""

def sweep_variable(var_id, bands, spx, db_connection):
    """Run all bands for one variable. Use daily_readings for pctile-based
    variables; pull raw series from DB or yahoo for level-based."""

def run_full_sweep():
    """Run all 12 variables → write per-variable JSON to
    macro_intelligence/analysis/regime_v2_experiments/threshold_sweep_v2/"""
```

### Data sources

| Variable | Source in DB | Raw series available? |
|---|---|---|
| VIX, CAPE, NFCI, HY, WTI, CNH, GSR, WALCL, CPI | `daily_readings` | Yes (raw_value + unconditional_pctile) |
| CFTC | `daily_readings` (rolling_3y pctile) | Yes |
| VXTS | `daily_readings` | Yes (ratio as raw_value) |
| CURVE | `daily_readings` (spread as raw_value, steepen in meta_json) | Yes |
| SPX | Yahoo Finance via `fetch_yahoo_close('^GSPC')` | Yes |

### Fix for existing sweep script + DB normalization

**P1.0 — Normalize DB percentiles (prerequisite):**
- One-time migration: rows with `unconditional_pctile <= 1.0` AND `unconditional_pctile >= 0` → multiply by 100
- Add assertion in pull pipeline: reject/store warning if pctile ∉ [0, 100]
- Re-run shadow backfill for affected date ranges if needed

**P1.1 — Fix `per_variable_threshold_sweep.py`:**
- Change `SWEEP_BANDS` lo/hi to 0–100 (e.g. `70, 79` not `0.70, 0.79`)
- Add CURVE (steepen + inversion pctile bands)
- Re-emit as `F_per_variable_sweep_v2.json` for regression compare

**`threshold_sweep_v2.py` (new) will:**
- Use normalized `unconditional_pctile` (0–100) for pctile-based bands
- Use `raw_value` (+ `meta_json` for CURVE steepen) for absolute-level bands
- First-crossing with **5 trading-day cooldown** after exit (avoids re-firing during prolonged episodes)
- Dual-condition vars (VIX, HY, NFCI): fire only when **both** level AND pctile legs cross (matches production tier logic)
- Hostile-regime PW slice via `regime_snapshots` join
- Reuse `probability_weighted_summary()` from `regime_experiments/metrics.py`

**Extend `combo_threshold_sweep.py`:**
- Add PW columns + validated horizons per combo (B=3M, D=5D, E=12M, F=6M)
- Gate sweeps for B/D/E/F as defined above
- Write combo JSONs to `threshold_sweep_v2/COMBO_*_gate_sweep.json`

---

## Output format (per variable JSON)

```json
{
  "variable": "VIX",
  "current_rare_threshold": 25,
  "current_extreme_threshold": 35,
  "sweep_results": [
    {
      "band_label": "VIX_20plus",
      "threshold_value": 20,
      "direction": "UP",
      "n": 47,
      "horizons": {
        "1m": {"hit_rate": 0.55, "avg_win": 3.1, "avg_loss": -2.8, "pw_expected": 0.42, "benchmark": 0.5, "excess": -0.08},
        "3m": {"hit_rate": 0.62, ...},
        "6m": {...},
        "9m": {...},
        "12m": {...}
      }
    },
    ...
  ],
  "recommendation": "Current RARE threshold (VIX ≥25) appears justified — lower thresholds add noise without PW gain.",
  "run_date": "2026-06-16"
}
```

Final summary JSON: `threshold_sweep_v2/SUMMARY.json` — table of current threshold, best-performing alternative, PW excess difference.

---

## Named Combo Threshold Tests (separate from per-variable)

Beyond single-variable sweeps, test the named combo entry gates directly:

### Combo B (most data: n=89)
Current gates: VIX≥25, HY≥400bps, CFTC≤15th pctile  
Test: relax each gate independently and measure hit rate change

| Test | Change | Expected |
|---|---|---|
| CB-1 | VIX≥20 (from 25) | More fires, lower hit rate? |
| CB-2 | VIX≥30 (from 25) | Fewer fires, higher hit rate? |
| CB-3 | HY≥350 (from 400) | More fires |
| CB-4 | HY≥450 (from 400) | Fewer, higher conviction |
| CB-5 | CFTC≤20 (from 15) | More fires |
| CB-6 | CFTC≤10 (from 15) | Fewer, higher conviction |
| CB-7 | 2-of-3 legs (from 3-of-3) | WATCH behavior analysis |

### Combo F (most data: n=704)
Current: SPX ≥3% above 50WMA + CFTC≤50th  
Test: SPX threshold at 1%, 2%, 3%, 5% above WMA

### Combo E (n=507 but most NORMAL regime)
Current: ≥2 of 3: CAPE≥28, NFCI≤−0.3, CFTC≥80th  
Test: CAPE level at 25, 28, 30, 32; NFCI easy at −0.2/−0.3/−0.4; CFTC crowded at 75/80/85

| Test | Change | Expected |
|---|---|---|
| CE-1 | CAPE≥25 (from 28) | More fires |
| CE-2 | CAPE≥30 (from 28) | Fewer, higher conviction |
| CE-3 | CAPE≥32 (from 28) | Extreme-only |
| CE-4 | NFCI≤−0.2 (from −0.3) | Looser easy-money leg |
| CE-5 | CFTC≥75 (from 80) | Looser crowded-long leg |

**Validated horizon:** 12M (primary per Rohit).

### Combo D (FOMO Top — bearish, thin n)
Current gates: VXTS≥1.10, CFTC≥85th pctile, VIX≤18  
Test: relax/tighten each gate; re-run at **5D** validated horizon

| Test | Change | Expected |
|---|---|---|
| CD-1 | VXTS≥1.05 (from 1.10) | More fires, lower hit? |
| CD-2 | VXTS≥1.15 (from 1.10) | Fewer, higher conviction |
| CD-3 | CFTC≥80 (from 85) | More fires |
| CD-4 | CFTC≥90 (from 85) | Fewer |
| CD-5 | VIX≤20 (from 18) | Looser complacency filter |
| CD-6 | VIX≤15 (from 18) | Tighter — only low-fear tops |
| CD-7 | 2-of-3 legs (from 3-of-3) | WATCH vs ACTIVE behavior |

**Validated horizon:** 5D (5 trading days per Rohit spec).

---

## Named Combo Tests for Validated Horizons

Per Rohit spec — re-run each named combo at its validated horizon with PW columns:

| Combo | Current result (3m) | Validated horizon | Re-run needed? |
|---|---|---|---|
| B | 79.8% up, PW +5.03% | 3M ✓ | No (already done) |
| C | 0% up | 6M primary | Yes — too few instances |
| D | 28.1% down | 5D | Yes 🆕 |
| E | 18.9% down (12M) | 12M ✓ | Done (testingv2) |
| F | 78.8% up (6M) | 6M ✓ | Done (testingv2) |
| G | No return table | — | N/A |

---

## Phase plan and execution order

### Phase 1 — Fix data foundation (prerequisite)

| Step | Action | Script | Priority |
|---|---|---|---|
| P1.0 | Normalize mixed 0–1 / 0–100 pctiles in `daily_readings` | Migration in `db/migrate.py` or one-off script | P0 |
| P1.1 | Fix scale bug in `per_variable_threshold_sweep.py` (0–1 → 0–100 bands) | Edit existing script | P0 |
| P1.2 | Re-run corrected sweep → `F_per_variable_sweep_v2.json` | `scripts/per_variable_threshold_sweep.py` | P0 |
| P1.3 | Confirm VIX/HY/VXTS/NFCI/CURVE/CAPE on FULL expanding window in CONFIG | Verify CONFIG.yaml | P0 |

### Phase 2 — Build and run threshold_sweep_v2.py

| Step | Action | Priority |
|---|---|---|
| P2.1 | Build `scripts/threshold_sweep_v2.py` with first-crossing logic + PW framework | P0 |
| P2.2 | Run all 12 variables → 12 JSON output files | P0 |
| P2.3 | Build `SUMMARY.json` — current vs best threshold per variable | P0 |

### Phase 3 — Named combo threshold tests

| Step | Action | Priority |
|---|---|---|
| P3.1 | Combo B gate sweep (VIX/HY/CFTC at multiple levels) | P1 |
| P3.2 | Combo F SPX threshold sweep (1%/2%/3%/5% above WMA) | P1 |
| P3.3 | Combo E gate sweep (CAPE/NFCI/CFTC levels) at 12M | P1 |
| P3.4 | Combo D gate sweep (VXTS/CFTC/VIX) at 5D with PW | P1 |

### Phase 4 — Document and report

| Step | Action | Priority |
|---|---|---|
| P4.1 | Create `testingv2/threshold_validation_report.md` — inline Q→A→table for each variable | P1 |
| P4.2 | Flag any thresholds where alternative clearly outperforms (excess > +2pp at 3m) | P1 |
| P4.3 | Update `testingv2_status.md` | P2 |

---

## Success criteria (per Rohit framework)

A threshold change is **justified** if:
1. Alternative threshold has PW excess **≥+2pp higher** than current threshold at the validated horizon
2. n ≥5 events (Gate 1 minimum)
3. Hit rate ≥60% (above unconditional ~55% of quarters positive)
4. Works in HIKING or INVERTED periods (not just QE/bull — prevents beta contamination per Rohit additional email §7)

A current threshold is **confirmed** if no alternative clears all four bars.

---

## Files to create in this directory

| File | Purpose |
|---|---|
| `threshold_validation_plan.md` | This file |
| `testingv2_status.md` | Live execution tracker |
| `threshold_validation_report.md` | Final inline results (Q→A→table per variable) |

## Experiment outputs (in `macro_intelligence/analysis/regime_v2_experiments/threshold_sweep_v2/`)

| File | Contents |
|---|---|
| `VIX_sweep.json` | VIX all threshold bands, all horizons, PW |
| `HY_sweep.json` | HY |
| `CFTC_sweep.json` | CFTC |
| `NFCI_sweep.json` | NFCI |
| `WALCL_sweep.json` | WALCL |
| `WTI_sweep.json` | WTI |
| `CNH_sweep.json` | CNH |
| `GSR_sweep.json` | GSR |
| `VXTS_sweep.json` | VXTS |
| `CAPE_sweep.json` | CAPE |
| `CPI_sweep.json` | CPI |
| `CURVE_sweep.json` | CURVE |
| `COMBO_B_gate_sweep.json` | Combo B gate sensitivity |
| `COMBO_F_spx_sweep.json` | Combo F SPX threshold |
| `COMBO_E_cape_sweep.json` | Combo E CAPE/NFCI/CFTC gates |
| `COMBO_D_gate_sweep.json` | Combo D VXTS/CFTC/VIX gates at 5D |
| `SUMMARY.json` | Cross-variable summary + combo gate summary |

---

## Infrastructure gaps (pre-execution audit)

| Gap | Impact | Resolution in plan |
|-----|--------|-------------------|
| Mixed pctile scale in DB (~1.5% legacy 0–1) | Under-counts events in pctile bands | P1.0 migration |
| `per_variable_threshold_sweep.py` 0–1 bands | 13/22 bands have n=0 in prior JSON | P1.1 fix |
| Prior sweep pctile-only, no raw thresholds | Cannot validate CONFIG RARE/EXTREME values | `threshold_sweep_v2.py` raw bands |
| CURVE excluded from v1 sweep | 12th variable untested | Add in P1.1 + P2.2 |
| `combo_threshold_sweep.py` stub | Combo B only; no PW/hostile/horizons | Extend in Phase 3 |
| Combo B all WATCH (0 ACTIVE in DB) | Gate sweeps must simulate legs, not just `combo_fires` | Use historical leg replay |
| No `threshold_sweep_v2/` output dir yet | — | Created on first P2.2 run |

---

*Plan created 2026-06-16; updated 2026-06-16 with DB scale verification, Combo D gates, hostile-regime methodology, and infrastructure audit. Next step: P1.0 DB normalization, then P1.1 script fix.*
