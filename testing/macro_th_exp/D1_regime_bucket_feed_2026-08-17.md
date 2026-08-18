# D1 — Regime Bucket Feed

**Date:** 2026-08-17  
**Series version:** `D1_regime_bucket_v1.2_2026-08-17`  
**Owner:** Divyanshu  
**Consumer:** Ahil P3 (headline stats per regime)

## Summary

- Daily rows: **2258** (2018-01-01 → 2026-08-14)
- Friday evaluations: **450**
- Bucket counts (daily): ADVERSE=252, BENIGN=1648, MIXED=358
- Bucket counts (Fridays): ADVERSE=50, BENIGN=328, MIXED=72

## Bucket definitions (post-D5)

| Bucket | Rule |
|--------|------|
| **ADVERSE** | Dominant combo bearish/cautionary at recalibrated gates: C/D/E ACTIVE, G ACTIVE, A TIGHT_MONEY |
| **BENIGN** | Dominant B/F bullish, A EASY_MONEY, or no adverse dominant |
| **MIXED** | Conflicting ACTIVE combos (bullish + bearish/cautionary), or Combo A CONTESTED |

## Recalibrated gates (D5 dependency)

| Combo | Gates | Validated horizon | D5 overall bear hit |
|-------|-------|-------------------|---------------------|
| D | VXTS≥1.18 / CFTC≥95 / VIX≤13 (2-of-3) | 1W | 56.52% |
| E | CAPE≥32 / NFCI≤-0.15 / CFTC≥85 (3-of-3) | 6M, 9M, 12M | 66.67% |

## Point-in-time discipline

- Each Friday: `get_readings_as_of(date)` + `detect_named_combos()` on recalibrated `CONFIG.yaml` gates.
- Mon–Thu: forward-fill last Friday bucket (`is_forward_filled=true`).
- Percentiles in `daily_readings` are as-of that date (backfill expanding history).

## Section code map (report PDF)

| Code | Meaning |
|------|---------|
| **B2** | Dual percentile storage (unconditional + regime_pctile) |
| **F4** | Steepening-of-inversion short grid (mechanism-only; not in bucket feed) |
| **D5** | Fed-cycle re-slice on recalibrated D/E — defines ADVERSE bearish combos |

## Artifacts

- `D1_regime_bucket_daily_2026-08-17.csv`
- `D1_regime_bucket_fridays_2026-08-17.csv`
- `D1_regime_bucket_feed_2026-08-17.json`
- `D1_regime_bucket_feed_2026-08-17.md` (this file)

## Caveats

- Combo C: sequential replay of 4-Friday cancel rule (not live `combo_c_cancel` flag).
- Combo F episode weeks read `combo_fires` history ≤ as_of (point-in-time).
- WATCH-only bearish legs (D/E partial) classify as BENIGN unless dominant is adverse.
