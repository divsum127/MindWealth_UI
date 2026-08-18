# Macro regime dimension multipliers — v1 (economic priors, unsigned)

**Status:** Illustrative, **not production-signed**. Replace with a Rohit-approved table when available.
Tagged `multiplier_version="v1_illustrative_unsigned_geo_off"` in every output that carries it.

**Renamed 2026-08-17** (Rohit 6 Aug): this file used to be `multiplier_spec.md` and its status line
carried a named individual. A file holding unsigned illustrative multipliers should be named after
what it does, not after who saw it.

## Which "dimensions" this is about

There are two different five/four-way splits in the system and they are not the same object:

| | Count | Members |
|---|---|---|
| **Macro regime grid** (this file) | 5 | fed cycle, curve, valuation, geo, liquidity |
| **Signal axes** (signals side) | 4 | asset, function, interval, direction |

Always qualify which is meant. Saying "dimensions" unqualified has already caused confusion.

**Mechanism:** each dimension contributes a multiplier in `(0, 1]`.
**Combined:** `gross_mult = clip(m_fed × m_curve × m_val × m_geo × m_liq, 0.40, 1.00)`.

Applied with **1-day lag** to portfolio gross exposure (signal known after prior close).

### The clip is one-sided — open decision

`MAX_MULT` is **1.00**, so the regime overlay can only ever shrink the book. The VIX and SSI
overlays both reach **1.20**, so two overlays can add exposure and this one cannot. That asymmetry
fell out of where the clip was set rather than being decided. **Left unchanged pending Rohit's
call** — flagged in `docs/rohit_6aug_answers_2026-08-17.md`.

### Stacking check before signing any number

TIGHTENING (0.82) × INVERTED (0.78) = **0.64**, a 36% cut before any other overlay touches the book,
and those two states co-occur often (the Fed tightens, the curve inverts). Run
`scripts/check_regime_multiplier_stacking.py` for the historical frequency and compounded effect
before either number is signed.

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

## geo_overlay_v2 — **SWITCHED OFF 2026-08-17**

| State | mult | Previous | Rationale |
|-------|------|----------|-----------|
| CRISIS | **1.00** | 0.70 | Off pending data |
| ELEVATED_RISK | **1.00** | 0.85 | Off pending data |
| NEUTRAL | 1.00 | 1.00 | No geo overlay |

Rohit 6 Aug: the backfill has geo at **97.6% NEUTRAL**, with only **25 ELEVATED_RISK** and **21
CRISIS** observations and most slices under 10. There is nothing there to calibrate against, so a
multiplier that sits at 1.00 for 97.6% of history and is guesswork the other 2.4% is not earning its
place. Switched off and disclosed rather than carried as a number we cannot defend.

Unknown / missing geo state also maps to **1.00** while the overlay is off (it must not pick up the
0.95 default haircut).

## liquidity_v2 (level bucket)

| Prefix | mult | Rationale |
|--------|------|-----------|
| TIGHT_ | 0.80 | NFCI tight — financial stress |
| NEUTRAL_ | 0.95 | Middle |
| EASY_ | 1.00 | Easy conditions |

Unknown / missing → **0.95** (mild haircut), except geo as noted above.
