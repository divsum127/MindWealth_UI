# MindWealth Instruction Docs — Open Doubts & Clarifications

**Date:** 2026-06-22  
**Scope:** `signals_master_spec/` + `macro_intelligence_docs/`  
**Purpose:** Track ambiguities blocking full spec closure. Resolve with Rohit / Ahil / spec owner.

---

## Signals MasterSpec

### 1. R_ref table — revised values not specified

**Source:** `additional_details.md` line 20: *"changing the r ref table as what i put was too aggressive"*

**Current code** (`MindWealth/helper_functions/claude_lateness_metrics.py`):

| asset_class   | R_ref (%) | ER_GATE_MIN (%) |
|---------------|-----------|-----------------|
| equity        | 10.0      | 2.0             |
| equity_etf    | 4.0       | 0.8             |
| commodity_etf | 6.0       | 1.2             |
| bond_etf      | 1.5       | 0.3             |
| crypto_etf    | 15.0      | 3.0             |
| index         | 3.0       | 0.6             |
| currency      | 1.5       | 0.3             |
| crypto        | 20.0      | 4.0             |

**Doubt:** What are the approved replacement R_ref and ER_GATE_MIN values? Should ER_GATE_MIN remain `R_ref × 0.2` or use a separate spec table?

---

### 2. `reward_remaining_pct` vs `upside_remaining_pct` naming

**Source:** Spec PDF / early `status_v2.md` used `upside_remaining_pct`; implementation renamed to `reward_remaining_pct` with signal-date entry anchor (not theoretical entry).

**Current behaviour:** Entry anchor = signal-date price; capped at 100% when price moves against position.

**Doubt:** Is the rename + signal-date anchor the final spec, or should lateness functions (TrendPulse / Fractal Track) use `theoretical_entry_price` for this metric?

---

### 3. OscillatorDelta theoretical entry (Ahil A2 dependency)

**Source:** `status.md` — Ahil task A2 (3-scenario entry lag study) **NOT STARTED**.

**Current code:** `compute_theoretical_entry_price()` uses `signal_price` as proxy for OSCILLATOR DELTA until A2 confirms divergence-end price.

**Doubt:** Should Gate A3 lateness or `reward_remaining_pct` block on OscillatorDelta until A2 is complete?

---

### 4. IBKR B&H CAGR window (Ahil A3)

**Source:** `status.md` — confirm IBKR TrendPulse Daily B&H CAGR uses same 4-year window as strategy backtest.

**Doubt:** If windows differ, should `random_window_return` / `signal_alpha_per_trade` use a harmonised B&H window per asset?

---

### 5. `surface_json` — Claude-generated vs Python-precomputed

**Source:** `constant.py` GOOD_SIGNAL_QUERY asks Claude to emit `<surface_json>`; Python already precomputes `composite_score`, `er`, etc. in `enrich_signal_dict()`.

**Observed:** Nightly reports (e.g. 2026-06-17) still output legacy `quality_score` (0–100 WR proxy) and omit new fields.

**Doubt:** Should the pipeline append a Python-authored `<surface_json>` block after Claude output (deterministic), or rely on Claude to copy precomputed fields from the payload?

---

### 6. Conviction overlay timing vs email cron

**Source:** Gate A2c expects per-signal `conviction_score`, `fs_class`, `yield_trap` in payload.

**Current fix:** `send_email.py` loads conviction overlay CSVs from `MindWealth_UI/conviction_store` by date.

**Doubt:** What is the required run order? Must conviction daily pipeline complete **before** `send_email.py` Claude step? Which overlay files are authoritative (`new_signal` only vs `all_signal` / `outstanding` / `claude_signals_report`)?

---

### 7. ASSET_CLASS_MAP completeness

**Source:** `status_v2.md` residual gap.

**Doubt:** Is there a canonical ~200-asset universe list to seed `ASSET_CLASS_MAP` explicitly (vs suffix fallback to `equity`)?

---

### 8. Gate A2d passive-hold threshold

**Source:** `additional_details.md` + `constant.py`: passive-hold flag when `signal_alpha_per_trade < 0.5 AND er > 0`.

**Doubt:** Is 0.5% the final cutoff, or should it be asset-class scaled?

---

### 9. Short signal_alpha formula confirmation

**Source:** `additional_details.md` line 21: *"formula for C2 holds for short positions as well"* with `signal_alpha = E[R]` (no drift credit).

**Current code:** Matches spec for Short in `enrich_signal_dict()`.

**Doubt:** Should Short also subtract `random_window_return` when B&H drift is negative (tailwind for shorts)?

---

### 10. MasterSpec PDF not in repo

**Source:** `status.md` references `MindWealth_Signals_MasterSpec.pdf` but file is not under `instruction_docs/`.

**Doubt:** Please add PDF to `instruction_docs/signals_master_spec/` or confirm `status_v2.md` + `additional_details.md` are the sole source of truth.

---

## Macro Intelligence Docs

### 11. Runic output schema vs regime context in signals email

**Source:** `send_email._fetch_regime_context()` reads `runic_output.json` keys `active_combos` / `watch_combos`.

**Doubt:** Are these the correct field names in production `runic_output.json`? Should stale-file date be checked (reject if `as_of` ≠ analysis date)?

---

### 12. SSI in signals email vs SSI beta gate in GOOD_SIGNAL_QUERY

**Source:** Section A of GOOD_SIGNAL_QUERY describes SSI regime preamble; `_fetch_regime_context()` passes `stance` string only.

**Doubt:** Should the full SSI score / long-short flags / regime multiplier from macro docs be injected, or is stance-only sufficient for v1?

---

### 13. Macro PDFs — variable sourcing for SSI layers

**Source:** `macro_intelligence_docs/SOURCING_DATA_FOR_MACRO_RUNIC_AGENT_variables_and_for_SSI_Layers'.pdf`

**Doubt:** Which variables are mandatory for nightly signals email vs Runic page only? No machine-readable variable manifest exists in repo.

---

### 14. Runic methodology thresholds

**Source:** `Runic_Methodology_Threshold_Justification.pdf`, `Runic_Agent_Combo_Cheatsheet_v2.pdf`

**Doubt:** Are combo active/watch thresholds in `CONFIG.yaml` final, or pending review from methodology PDF?

---

## Implementation Notes (not doubts — for context)

| Item | Location | Status |
|------|----------|--------|
| Core quality fields (A1, B1–B2, C, D, E1, F2, G1–G3) | `MindWealth/` | Implemented; 6/6 G3 tests pass |
| Bubble chart UI | `MindWealth_UI` analysis + Claude pages | Added 2026-06-22 |
| Conviction payload merge | `MindWealth/send_email.py` | Added 2026-06-22 |
| Ahil A2 / A3 | — | Not started (Ahil) |

---

*Add new doubts at the bottom with date + section number. Remove entries once resolved.*
