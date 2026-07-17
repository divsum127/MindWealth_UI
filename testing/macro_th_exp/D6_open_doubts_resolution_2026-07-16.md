# D6 — Quick Answers to Open Doubts (Macro Regime & Threshold Experiments)

**Date:** 2026-07-16  
**Task:** Record Rohit sign-off on five blocking open doubts from the experiment report reply thread.  
**Source report:** `Reply of macro regime and threshold experiments report.pdf` (repo root)  
**Companion artifacts:** D4 (`B4` window audit), D5 (fed-cycle re-slice), F4 v2 driver split (D3)

---

## Section code map (report shorthand → PDF location)

| Code | Report part | Topic |
|------|-------------|--------|
| **A1** | Part A — fed_cycle | 7-state → 4-state collapse; PIVOTING n=27 |
| **A5** | Part A — liquidity | 2→4/9 states; WALCL direction; analytics collapse |
| **B2** | Part B — dual percentile storage | unconditional + regime_pctile; history windows |
| **F4** | Part F — steepening-of-inversion short grid | trough −50/−80 × steepen +15/+40 cells |
| **Part D** | HMM layer | posteriors, shift timing, win-rate filter prototype |
| **Part E** | Cancel probability | Combo C MC cancel; briefing display |
| **Named combos** | FM / A–G tables | Combo C n=4, 0% 3m hit in sample |

Earlier tasks (D3–D5) used the same letter codes. **F4** and **B2** are section labels inside the PDF, not separate D-series tasks.

---

## Executive summary — five resolutions

| # | Open doubt (report) | D6 decision | Analytics vs storage |
|---|---------------------|-------------|----------------------|
| 1 | **A1** PIVOTING n=27 — merge into EASING or keep? | **Merge PIVOTING → EASING for analytics only** | Classifier / `macro_regime_log_v2` may still store `PIVOTING`; hit-rate tables and regime slices use 3-way fed analytics: TIGHTENING / EASING (incl. PIVOTING) / EASY |
| 2 | **A5** 4 vs 9 liquidity states | **Keep 9-state storage; collapse to 4 for analytics** (as recommended in report A5/A6) | `liquidity_v2()` continues `{LEVEL}_{DIRECTION}`; combo slices use 2×2 EASY/TIGHT × IMPROVING/TIGHTENING |
| 3 | **A5** NEUTRAL level in 4-way slice | **Fold NEUTRAL → EASY for analytics**; **keep NEUTRAL as third level in classifier storage** | NFCI neutral band stays in nightly labels and prompt; collapse rules assign NEUTRAL_* → EASY side of 2×2 for hit-rate tables |
| 4 | **Combo C** n=4 — show hit rates in briefing? | **Do not show hit rates at n=4** — display **"insufficient episodes"** | Cancel-probability (Part E) may still surface; validated-horizon HR suppressed until n≥5 (or project min-episode gate) |
| 5 | **Part D / B2 HMM** — Dec 2026 target after prototype hurt B (−1.2 pp) and D (−1.9 pp)? | **December deployment target stands**; **HMM excluded from any short-gating path** until walk-forward validation shows **positive lift** | Continue daily `emission_vectors`; train/evaluate HMM on schedule; no Risk-Off posterior filter on B/D/G until walk-forward passes |

---

## 1. A1 — PIVOTING at n=27 → merge into EASING (analytics)

### Context from report

| v2 state | Fridays | % | ≥30 obs? |
|----------|---------|---|----------|
| TIGHTENING | 763 | 40.1% | Yes |
| EASING | 727 | 38.2% | Yes |
| EASY | 384 | 20.2% | Yes |
| **PIVOTING** | **27** | **1.4%** | **No** |

Report doubt (page ~19): *"PIVOTING at n=27: is it a real state or label noise? Merging into EASING is pragmatic but might hide genuine pivot weeks."*

Reply PDF initially debated keeping PIVOTING separate (CUTTING_EARLY → PIVOTING in `collapse_fed_cycle_v2()`). **D6 supersedes for analytics:** PIVOTING weeks roll into **EASING** when computing regime-conditional combo hit rates, beta filter hostile slices, and briefing footnotes.

### Implementation notes

- **Storage:** `collapse_fed_cycle_v2()` in `regime_v2_shadow.py` may continue emitting `PIVOTING` in `macro_regime_log_v2.regime_json`.
- **Analytics helper (new or documented):** `fed_cycle_v2_analytics(label)` → map `PIVOTING` → `EASING` before slice aggregation.
- **Effect on counts:** EASING analytics bucket ≈ 727 + 27 = **754** Fridays (39.7%); PIVOTING no longer fails the ≥30 obs gate in slice tables.
- **Out of scope for D6:** PAUSING / Fed-on-hold label (job tracker **T-01**) — unchanged.

---

## 2. A5 — Nine-state liquidity storage + four-state analytics collapse

### Context from report

Nine states from NFCI level (EASY / NEUTRAL / TIGHT) × WALCL direction (IMPROVING / TIGHTENING / FLAT). ~50.8% of Fridays in FLAT direction; ~26.4% NEUTRAL level — forcing pure 2×2 would mislabel history.

Report recommendation (A5/A6): two-tier approach — honest 9-state labels in production; collapse for combo hit-rate tables because 9-way FM slices are n=6–10 per cell.

### D6 decision

**Confirmed exactly as recommended.** No reduction of classifier output to 4 states.

### Analytics collapse rules (4-state 2×2)

| 9-state label | Collapsed bucket |
|---------------|------------------|
| EASY_IMPROVING | EASY + IMPROVING |
| EASY_TIGHTENING | EASY + TIGHTENING |
| EASY_FLAT | EASY + IMPROVING if prior 4wk WALCL trend positive, else EASY + TIGHTENING |
| NEUTRAL_IMPROVING | EASY + IMPROVING |
| NEUTRAL_TIGHTENING | EASY + TIGHTENING (or TIGHT + TIGHTENING if NFCI > 0 — judgment retained) |
| NEUTRAL_FLAT | **NEUTRAL → EASY** (D6 #3) |
| TIGHT_IMPROVING | TIGHT + IMPROVING |
| TIGHT_TIGHTENING | TIGHT + TIGHTENING |
| TIGHT_FLAT | TIGHT + dominant recent WALCL trend |

**Code status:** `liquidity_v2()` already emits 9 labels (`regime_v2_shadow.py`). Analytics collapse function not yet centralized — add `collapse_liquidity_v2_analytics()` when re-slicing FM / combo tables.

---

## 3. A5 — NEUTRAL folded into EASY (4-way slice only)

### Context

Report doubt: *"NEUTRAL level folded into EASY (majority of NEUTRAL Fridays have NFCI slightly negative) or kept as third level in classifier prompt only?"*

### D6 decision

- **Classifier storage & nightly briefing regime grid:** keep **NEUTRAL** as a distinct level (third level alongside EASY / TIGHT).
- **Combo hit-rate / beta / FM slice tables:** fold **NEUTRAL_* → EASY** side of the 2×2 analytics grid (per collapse table above).

Rationale: preserves honest daily labels while making 4-way performance slices statistically usable (NEUTRAL_FLAT alone is 219 Fridays in backfill but thin at event level).

---

## 4. Combo C — insufficient episodes in briefing (n=4)

### Context from report

| Combo | Dir | n | Overall hit (legacy 3m) | Note |
|-------|-----|---|---------------------------|------|
| C | Bull (bearish signal) | **4** | **0% up** | n too small; avg +17.8% (market rose against signal) |

Report doubt: *"Combo C has n=4 and 0% hit. Should we show C hit rates in the briefing at all until we have more completed episodes?"*

Part E: cancel-probability MC built (WTI 8.31%, CPI 27.04%, combined 2.25%) — function exists; live cancel % not yet on briefing.

### D6 decision

- **Hit rate / avg return columns for Combo C:** show **`insufficient episodes`** (not 0.0% or N/A that implies a measured rate).
- **Threshold:** suppress actionable HR until **n ≥ 5** mature episodes at validated primary horizon (`spx_6m` per `CONFIG.yaml`) — aligns with Part H naming gate minimum fires.
- **Still allowed on briefing:** ACTIVE/WATCH status, cancel watch (Part E), legs met, direction BEARISH, dominant-reason narrative without numeric HR.

### Implementation touchpoints (deferred to eng sprint)

| File | Change |
|------|--------|
| `macro_intelligence/CONFIG.yaml` | `combo_hit_rates.C.show_hit_rate: false` **or** min-n guard in code |
| `combo_metadata.py` | `combo_hit_rate_stats()` → if `n_obs < 5`, return `display_label: "insufficient episodes"` |
| `briefing_renderer.py` | Render explicit string instead of `0.0% (6M)` |

---

## 5. Part D — HMM: Dec target stands; out of short-gating until walk-forward lift

### Context from report

| Question | Answer in report |
|----------|------------------|
| HMM improve win rate? | **No** — Combo B: 79.8% → 78.6% (−1.2 pp, n=56); Combo D: 28.1% → 26.2% (−1.9 pp, n=103) with Risk-Off filter |
| Production HMM ready? | ~Dec 2026 earliest (6+ months live `emission_vectors`) |
| B2 doubt | Prototype hurt B/D — is Dec still the right target? |

Testingv2 clarification: HMM is a **regime detector**, not a per-combo 3m hit-rate booster; walk-forward (lead time before bearish fires) is the correct acceptance test.

### D6 decision

1. **December 2026 deployment target unchanged** — continue storing daily emission vectors; train HMM on schedule when live history ≥ 6 months.
2. **Hard gate:** HMM posteriors **must not** gate or filter **short-horizon combos B, D, or G** (or any short-gating path) until walk-forward validation demonstrates **positive lift** on the agreed metric (e.g. median lead ≥ 2 weeks before bearish combo fires, or positive Sharpe/drawdown improvement on the Risk-Off track).
3. **Prototype k-means results (−1.2 pp B, −1.9 pp D)** are explicitly **not** grounds to cancel the HMM program — they are grounds to **exclude HMM from production gating** until walk-forward passes.

### Related sections (unchanged by D6)

- **F4:** remains mechanism+analog only (best cell 33.3%, n=9); not a short-gating promotion candidate.
- **B2:** dual percentile storage continues; HMM emission vector = 13–14 percentile ranks per day.

---

## Open doubts **not** resolved in D6 (remain tracked)

| Doubt | Report ref | Status |
|-------|------------|--------|
| Moderate FM 76.2% vs buy-and-hold drift | FM table | Open — needs drift-stripped benchmark |
| VIX suppressed 8.5% vs plan ~50% | G2 | Open — window / definition review |
| v2 fed_cycle GO-live rollback plan | Production | Open |
| SSI short gate 26% at SSI≥0.85 | SSI | Open |
| B4 HY/VIX/VXTS window spec conflict | B2 / D4 | Open — see `D4_window_audit_rerun_2026-07-16.md` |

---

## Implementation checklist (next sprint)

| Priority | Item | Owner hint |
|----------|------|------------|
| P1 | `fed_cycle_v2_analytics()` — PIVOTING → EASING | **Done** |
| P1 | `collapse_liquidity_v2_analytics()` — 9→4 with NEUTRAL→EASY | **Done** |
| P1 | Combo C briefing: **insufficient episodes** when n&lt;5 | **Done** |
| P2 | Re-run regime-conditional combo tables with analytics collapse | **Done** — `D6_regime_analytics_2026-07-17.*` |
| P2 | Smoke tests (briefing + API + FM slice) | **Done** — `D6_smoke_tests_2026-07-17.md` (8/8) |
| P2 | HMM walk-forward report gate doc in classifier prompt (soft prior only, no gating) | Open |
| P3 | Document analytics vs storage in `README_MAINTENANCE.md` | Open |

---

## Artifacts

| File | Description |
|------|-------------|
| `D6_open_doubts_resolution_2026-07-16.md` | This report |
| `D6_open_doubts_resolution_2026-07-16.json` | Machine-readable decisions + section map |

**No code or CONFIG changes in this task** — documentation and sign-off capture only.

---

## Implementation status (2026-07-16 follow-up)

| Item | Status | Location |
|------|--------|----------|
| `fed_cycle_v2_analytics()` | **Done** | `src/macro_intelligence/engine/regime_v2_shadow.py` |
| `collapse_liquidity_v2_analytics()` | **Done** | same |
| `regime_value_for_analytics()` | **Done** | same |
| Analytics collapse in regime slices | **Done** | `metrics.slice_by_regime()` for `fed_cycle_v2` / `liquidity_v2` |
| Combo C min-n guard (n&lt;5 → insufficient episodes) | **Done** | `combo_metadata.py`, `CONFIG.yaml` `min_episodes_for_hit_rate: 5` |
| FM experiment fed_cycle labels | **Done** | `fm_events.collapse_from_json()` uses analytics collapse |
| Regime tables re-slice + CSVs | **Done** | `run_d6_regime_analytics_reslice.py` (2026-07-17) |
| Smoke tests (briefing + API + FM) | **Done** | `run_d6_smoke_tests.py` — 8/8 pass |
