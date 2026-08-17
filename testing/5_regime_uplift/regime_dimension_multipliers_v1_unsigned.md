# Regime position multipliers — v1 (economic priors)

**Status:** Illustrative for Michele demo. Not production-signed. Replace with Rohit-approved table when available.

**Mechanism:** Each dimension contributes a multiplier in `(0, 1]`.  
**Combined:** `gross_mult = clip(m_fed × m_curve × m_val × m_geo × m_liq, 0.40, 1.00)`.

Applied with **1-day lag** to portfolio gross exposure (signal known after prior close).

---

## fed_cycle_v2

| State | mult | Rationale |
|-------|------|-----------|
| TIGHTENING | 0.82 | Fed hiking / tight — headwind for risk assets |
| PIVOTING | 0.92 | Turning point — reduce until direction clear |
| EASING | 1.00 | Cuts underway — supportive |
| EASY | 1.00 | Accommodative |

## curve_regime_v2

| State | mult | Rationale |
|-------|------|-----------|
| INVERTED | 0.78 | Recession signal — reduce risk |
| FLAT | 0.90 | Uncertain growth |
| NORMAL | 1.00 | Benign |
| STEEPENING | 0.95 | Often late-cycle / inflation re-pricing |

## val_regime

| State | mult | Rationale |
|-------|------|-----------|
| EXTREME_CAPE | 0.85 | Valuation headwind (Combo E territory) |
| ELEVATED_CAPE | 0.92 | Elevated but not extreme |
| NORMAL | 1.00 | Fair |
| CHEAP_CAPE | 1.00 | Supportive entry |

## geo_overlay_v2

| State | mult | Rationale |
|-------|------|-----------|
| CRISIS | 0.70 | COVID-style shock |
| ELEVATED_RISK | 0.85 | Ukraine / tariff episodes |
| NEUTRAL | 1.00 | No geo overlay |

## liquidity_v2 (level bucket)

| Prefix | mult | Rationale |
|--------|------|-----------|
| TIGHT_ | 0.80 | NFCI tight — financial stress |
| NEUTRAL_ | 0.95 | Middle |
| EASY_ | 1.00 | Easy conditions |

Unknown / missing → **0.95** (mild haircut).
