# Part H Beta Re-run with v2 Shadow Regimes

**Date:** 2026-07-07  
**Actions taken:** Retagged 13,160 generic `combo_fires` with `macro_regime_log_v2`; re-ran full 298-signature funnel with real hostile HR.

---

## What we fixed

Previously every `combo_fires.macro_regime` was **empty** — hostile check auto-passed (`hostile_hr = null` → pass). We:

1. Merged v2 shadow labels from `macro_regime_log_v2` into each fire (exact Friday match, else nearest prior Friday).
2. Persisted to DB via `scripts/retag_combo_fires_v2_regimes.py`.
3. Updated `load_generic_fires()` to always enrich from v2 on read.
4. Re-ran the Part H funnel with true regime tags.

**Hostile definition (unchanged from CONFIG):** `fed_cycle` = TIGHTENING / HIKING_* **or** `curve_regime` = INVERTED (using v2 labels: `fed_cycle_v2`, `curve_regime_v2`).

**Unconditional baseline:** mean `spx_3m` across all 13,089 generic fires = **+3.14%**.

---

## Funnel: before vs after (true comparison)

| Stage | Before (no regime tags) | After (v2 tags) | Δ |
|-------|------------------------:|----------------:|--:|
| Surfaced (≥3 fires, ≥60% HR) | 187 | 187 | 0 |
| **Beta pass** | **132** | **127** | **−5** |
| Survivors | 132 | 127 | −5 |
| **Promotion (≥5 fires, ≥80% HR)** | **62** | **62** | **0** |
| Survivors with hostile HR computed | 0 | 106 | +106 |

**Bottom line:** Real hostile tagging **killed 5 surfaced combos** on beta (mostly `beats_regime_base` or hostile HR = 0%). **All 62 promotion candidates still pass** — none dropped.

### 5 combos that lost survivor status (failed beta)

| Signature | n | 3m HR | Hostile HR | Why failed |
|-----------|--:|------:|-----------:|------------|
| `CAPE+CFTC+WALCL` | 92 | 70.7% | 79.0% | `beats_regime_base = false` |
| `CFTC+WTI` | 177 | 73.6% | 75.0% | `beats_regime_base = false` |
| `CNH+WALCL` | 4 | 75.0% | **0.0%** | Hostile subsample all lost |
| `HY+VXTS` | 3 | 66.7% | **0.0%** | Hostile subsample all lost |
| `CAPE+HY+VXTS` | 3 | 66.7% | **0.0%** | Hostile subsample all lost |

None of these were in the 62 promotion set.

---

## 8-theme shortlist — v2 beta detail

All 8 still pass beta and remain promotion candidates.

| Signature | n | 3m HR | Avg 3m | Hostile n | Hostile HR | Beats uncond / single / regime |
|-----------|--:|------:|-------:|----------:|-----------:|-------------------------------|
| `CURVE+WALCL` | 73 | 84.9% | +5.11% | 69 | **84.1%** | ✓ / ✓ / ✓ |
| `CNH+VIX` | 26 | 88.5% | +6.50% | 17 | **82.4%** | ✓ / ✓ / ✓ |
| `CNH+GSR+WTI` | 15 | 93.3% | +6.54% | 12 | **91.7%** | ✓ / ✓ / ✓ |
| `CFTC+VIX+VXTS` | 13 | 100% | +11.46% | 3 | **100%** | ✓ / ✓ / ✓ |
| `CAPE+VIX+VXTS` | 23 | 87.0% | +10.17% | 3 | **100%** | ✓ / ✓ / ✓ |
| `CURVE+GSR+WALCL` | 27 | 85.2% | +5.56% | 25 | **84.0%** | ✓ / ✓ / ✓ |
| `CNH+CURVE+WALCL` | 23 | 87.0% | +4.78% | 23 | **87.0%** | ✓ / ✓ / ✓ |
| `CAPE+HY` | 8 | 87.5% | +14.17% | 5 | **80.0%** | ✓ / ✓ / ✓ |

### Caveats on shortlist

1. **`CFTC+VIX+VXTS` / `CAPE+VIX+VXTS`** — only **3 hostile fires** each; 100% hostile HR is real but tiny n.
2. **Five other promos** (not in shortlist) have **zero hostile fires** — hostile check still auto-passes: `CPI+GSR`, `CPI+GSR+WTI`, `CAPE+CPI+GSR`, `CAPE+NFCI+VXTS`, `CFTC+NFCI+WALCL`. Mostly 2024/2026 CPI clusters.
3. **`CAPE+HY`** — hostile HR exactly **80.0%** at n=5; thinnest shortlist member.

---

## Beta filter recap (now actually enforced)

For each **bullish** combo at **spx_3m**:

1. **beats_unconditional** — combo avg > +3.14% pool average  
2. **beats_single_var** — combo avg > single-variable fires for same legs  
3. **beats_regime_base** — combo avg > avg return of all fires in same `fed_cycle`  
4. **hostile_ok** — if any hostile-tagged fires exist, hostile hit rate ≥ **55%**; else skip  

4,369 of 13,160 generic fires (~43%) fall in hostile regimes (TIGHTENING or INVERTED).

---

## Recommendation (unchanged, now better supported)

- **Keep the 8-theme shortlist** for Step 7 / Rohit — all survive real beta.  
- **Prioritize T1** (`CURVE+WALCL`, `CNH+VIX`, `CNH+GSR+WTI`) — large n + hostile HR > 82%.  
- **Flag D/G echo** (`CFTC+VIX+VXTS`) — strong stats but hostile n=3.  
- **Defer CPI-only promos** with no hostile sample — beta gate not stress-tested.  
- **Next:** run Step 7 Claude narratives on the 8 signatures.

---

## Files

| File | Contents |
|------|----------|
| `v2_beta_rerun_summary.json` | Machine-readable funnel + shortlist |
| `v2_shortlist_beta.csv` | 8-theme beta detail |
| `v2_promotion_comparison.csv` | Promo/beta deltas |
| `scripts/retag_combo_fires_v2_regimes.py` | DB retag utility |
