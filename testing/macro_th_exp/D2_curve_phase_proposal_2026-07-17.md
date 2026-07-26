# D2 — Curve Regime: `post_inversion_steepening` Phase Flag (PROPOSE ONLY)

**Chat:** d2  
**Date:** 2026-07-17  
**Status:** Proposal for Rohit sign-off — **do not implement** until agreed  
**Context:** Macro regime threshold experiments (report section codes **F4** = steepening-of-inversion grid, **B2** = dual percentile storage, **A2** = curve_regime). Reply PDF: `Reply of macro regime and threshold experiments report.pdf`.

---

## Problem statement

`curve_regime_v2` momentum tier (**STEEPENING**) needs **spread ≥ +30 bps** and **≥ +15 bps / 4 weeks** steepening (simple or post-trough metric depending on code path). A **slow grind** re-steepening after inversion can read **NORMAL** on weeks when the simple 4-week change dips below +15 bps — even while spread is recovering from a deep trough (+40–55 bps) and the narrative / v2 cheatsheet still describe **post-inversion steepening** as active.

**Example — 2025-05-23 (Friday anchor):**

| Field | Value |
|-------|-------|
| Spread | **+51 bps** |
| Steepen (post-trough) | **+157 bps** → momentum tier **STEEPENING** |
| Steepen (simple 4wk) | **−4 bps** → momentum tier **NORMAL** |
| Narrative / cheatsheet | Post-inversion steepening phase **active** |

The gap is **momentum vs phase**: tier flips week-to-week; phase should persist across grind.

---

## Recommendation: add a separate PHASE flag (do not replace momentum tier)

Store alongside `curve_regime_v2`:

```json
"post_inversion_steepening": true | false
```

(or enum `ACTIVE` / `INACTIVE` — boolean sufficient for briefing)

Momentum tier stays: `INVERTED` | `FLAT` | `STEEPENING` | `NORMAL`.

---

## (a) Proposed ON / OFF rules

### Prerequisite — formal inversion episode

Same as F2 / report A2:

> **T10Y2Y < 0 for ≥ 4 consecutive weeks** (weekly Friday grid)

### PHASE **ON**

First Friday **after** the inversion episode ends (`spread` crosses back to ≥ 0) where:

1. `spread_bps ≥ 0`, **and**
2. `steepen_4wk_bps` **(post-trough metric)** ≥ **+15 bps**

*Rationale:* Matches F4 / F2a steepening gate and existing `steepen_bps_post_inversion_trough()` in `fred_pull.py`. Uses trough-relative recovery, not raw 4wk diff alone.

### PHASE **OFF** (recommended — Spec A)

Turn **OFF** when **either**:

1. **Normalized:** `spread_bps ≥ +80` (curve fully un-inverted / “normal” shape), **or**
2. **Re-inverted:** new formal inversion episode (≥ 4 consecutive weeks with `spread < 0`)

### PHASE **OFF** — rejected literal rule

> `spread < +30 bps for 4 consecutive weeks` **alone**

**Do not use.** Backfill shows false OFF during Oct–Nov 2024 chop (spread 4–20 bps while still recovering from −106 bps trough). Phase would have ended **2024-09-20** — **before** May 2025 narrative window.

| OFF spec | 2022 episode phase weeks | May 2025 phase active? |
|----------|--------------------------|------------------------|
| Literal re-flatten `<30` × 4wk | 4 | **No** |
| **Recommended (≥80 or re-invert)** | **99 (ongoing)** | **Yes** |

### Open choice for Rohit

If you want an earlier OFF than +80 bps without the false-positive re-flatten rule, consider a **tertiary stall** (not in recommended spec):

- `spread < +30` **and** simple 4wk steepen `< 0` for **≥ 8 consecutive weeks** (momentum stall, not chop)

---

## (b) Historical episodes — backfill (1990 → present)

**Source:** FRED `T10Y2Y`, Friday grid, `curve_features()` post-trough steepen. Artifacts in `testing/macro_th_exp/`.

| Metric | Count |
|--------|-------|
| Formal inversion episodes (≥4wk &lt;0) | **5** |
| Phase episodes triggered (ON rule) | **5** |
| Total phase-active weeks (Spec A) | **165** / 1,907 Fridays (**8.65%**) |
| Weeks phase ON but simple-tier NORMAL | **90** (slow-grind mismatch weeks) |
| Current episode | **#5 ongoing** since 2024-08-30 |

### Episode table (recommended Spec A)

| # | Inversion | Trough | Phase ON | Phase OFF | Weeks | OFF reason |
|---|-----------|--------|----------|-----------|-------|------------|
| 1 | 2000-02-04 → 2000-12-22 | −52 bps | 2000-12-29 | 2001-04-06 | 15 | normalized ≥80 |
| 2 | 2006-02-03 → 2006-03-03 | −16 bps | 2006-03-10 | 2006-06-30 | 17 | re-inverted 4wk |
| 3 | 2006-06-09 → 2006-07-21 | −4 bps | 2007-03-23 | 2007-11-09 | 34 | normalized ≥80 |
| 4 | 2006-08-18 → 2007-03-16 | −18 bps | 2007-03-23 | 2007-11-09 | 34 | normalized ≥80 |
| 5 | **2022-07-08 → 2024-08-23** | **−106 bps** | **2024-08-30** | **ongoing** | **99** | — |

Episode #5 matches the 2022–24 inversion unwind Rohit / cheatsheet describe. Spread at May 2025 (+43–52 bps) is below the +80 OFF gate → phase stays **ON**.

---

## (c) Combo A / E leg behaviour — unchanged unless explicitly wired

### Named combo legs (production `combo_detector.py`)

| Combo | Required legs | CURVE a leg? |
|-------|---------------|--------------|
| **A** | NFCI, HY, WALCL, CNH (2-of-4 rare+) | **No** |
| **E** | CAPE, NFCI, CFTC (3-of-3) | **No** |

`CONFIG.yaml` tags CURVE `combos: [A, E]` for **analytics / percentile context**, not as a firing leg.

### Phase flag alone

| Path | Changes if phase added as storage-only? |
|------|----------------------------------------|
| Combo A fire logic | **No** |
| Combo E fire logic | **No** |
| CURVE RARE/EXTREME tier (`percentiles.py`) | **No** — gates use spread + steepen thresholds, not phase |
| Hostile regime filter (`hostile_curve_regimes: [INVERTED]`) | **No** — phase ON can occur while spread ≥ 0 (not INVERTED) |
| Regime Sharpe multipliers (`STEEPENING` = 0.95) | **No** — uses `curve_regime_v2` tier, not phase |
| Briefing narrative / cheatsheet | **Yes** — intended consumer |

### Calendar overlap (informational only)

Fires that happened to fall on phase-active Fridays (`macro_regime_log_v2` backfill window):

| Combo | Total fires in DB | During phase-active weeks |
|-------|-------------------|---------------------------|
| A | 174 | 3 |
| E | 514 | 115 |

Overlap is **calendar coincidence** during the long 2022–25 episode (#5). Phase flag does **not** add/remove CURVE as a leg and does **not** change A/E threshold crossings.

**Verdict:** Safe to add as **orthogonal metadata**. Wire to combo logic only if Rohit explicitly requests (e.g. Combo E amplifier alongside G1 7WK_GRIND).

---

## Artifacts

| File | Description |
|------|-------------|
| `D2_curve_phase_proposal_2026-07-17.md` | This note |
| `D2_curve_phase_proposal_2026-07-17.json` | Machine summary + May 2025 anchor |
| `D2_curve_phase_episodes_recommended_2026-07-17.csv` | Episode table |
| `D2_curve_phase_weekly_panel.csv` | Full Friday panel (tier vs phase) |
| `D2_may2025_simple_vs_posttrough.csv` | Simple vs post-trough tier comparison Apr–Jun 2025 |
| `D2_phase_off_spec_comparison_2026-07-17.json` | OFF-rule variant comparison |

---

## Decision requested

1. **Approve Spec A OFF** (≥80 bps or re-invert) vs add stall tertiary?  
2. **Storage field name** — `post_inversion_steepening` bool OK?  
3. **Briefing only** first, or also regime JSON / API `/macro/regime`?  
4. **No combo wiring** unless requested — confirm?

**Do not implement** until sign-off.
