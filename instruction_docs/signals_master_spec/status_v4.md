# MindWealth Signals MasterSpec — Implementation Status v4

**Date:** 2026-06-22  
**Document type:** Post-implementation record — **Quality Composite v4 Calibrated**  
**Reference:** `MindWealth_Composite_v4_Calibrated.pdf` (Rohit → Divyanshu, June 2026)  
**Prior baseline:** `status_v2.md` (3-component per-trade composite), `status_v3.md` / `status_v5.md` (supplementary fields)  
**Core repo:** `/home/ubuntu/MindWealth`  
**UI repo:** `/home/ubuntu/uiv2/git/MindWealth_UI`

> **Naming note:** `MindWealth/instruction_docs_2/status_v4.md` is a separate audit doc for the Supplementary + AlphaInterp PDFs. **This file** records the **Composite v4 Calibrated** formula upgrade only.

---

## Summary

| Area | v2 / v3 baseline | v4 Calibrated (this release) |
|------|------------------|------------------------------|
| Composite components | C1 + C2 + C3 | **C1 + C2 + C3 + C4** |
| E[R] / signal_alpha in composite | Per-trade % | **Annualized** (`× 252 / hold_days`) |
| C1 weight / R_ref | 50 pts; equity R_ref = 10% per-trade | **40 pts**; equity R_ref = **50% annualized** |
| C2 weight / clip | 15 pts; `/5` per-trade | **25 pts**; **ALPHA_CLIP = 45%** annualized |
| C3 Sharpe | 20 pts (unchanged formula) | 20 pts (unchanged) |
| C4 CAGR_diff | Not in composite (Gate A2d only) | **10 pts**; **CAGR_CLIP = 5%** equity |
| Score range | −21 to +73 | **≈ −41 to +83** |
| Hold-period proxy | All-trades avg only | **Win-trades hold** when all-trades N/A |
| Gate A2a (`ER_GATE_MIN`) | Per-trade % | **Unchanged** (per-trade) |

**Net result:** Bubble chart Y-axis, `<surface_json>` `composite_score`, and Python `tier` gates now use the calibrated 4-component annualized formula. Equity thresholds match the June 2026 80th-percentile calibration run.

---

## What changed vs v2 composite

### 1. Annualization

Before threshold comparison:

```
E[R]_annualized           = er_per_trade × (252 / avg_hold_days)
signal_alpha_annualized   = signal_alpha_per_trade × (252 / avg_hold_days)
```

`avg_hold_days` from `Backtested Holding Period (All Trades)`; if N/A, proxy from **win-trades** hold column (same rule as calibration spreadsheet).

### 2. Four components

| Component | Formula | Max pts |
|-----------|---------|---------|
| C1 | `clip(E[R]_ann / R_ref, 0, 1) × 40` | 40 |
| C2 | `clip(signal_alpha_ann / ALPHA_CLIP, −1, +1) × 25` | 25 |
| C3 | `clip((Sharpe − 0.3) / 1.5, −0.3, +0.4) × 20` | 20 |
| C4 | `clip(CAGR_diff / CAGR_CLIP, −1, +1) × 10` | 10 |

`composite_score = C1 + C2 + C3 + C4` — **not** clamped to 0–100.

### 3. Calibrated thresholds (equity)

| Constant | v2 | v4 equity |
|----------|-----|-----------|
| `R_REF` | 10.0 (% per trade) | **50.0** (% annualized) |
| `ALPHA_CLIP` | implicit `/5` | **45.0** (% annualized) |
| `CAGR_CLIP` | — | **5.0** (%/yr) |

Non-equity classes use **provisional** annualized thresholds (scaled from v2 per-trade values). PDF explicitly says do **not** reuse equity numbers for other asset classes until a dedicated calibration run.

### 4. Calibration smoke examples (from PDF)

| Signal | Expected composite |
|--------|-------------------|
| WFG.TO (E[R]_ann 48.7%, α_ann 43.1%, Sharpe 1.17, CAGR_diff +7.8%) | **≈ 80.9** |
| ATZ.TO Daily (CAGR_diff −35.6% → C4 floor) | **≈ 53.5** |

Both covered by automated tests.

---

## Implementation detail

### MindWealth core — `claude_lateness_metrics.py`

| Symbol | Role |
|--------|------|
| `TRADING_DAYS_PER_YEAR = 252` | Annualization divisor |
| `R_REF`, `ALPHA_CLIP`, `CAGR_CLIP` | Per-asset-class v4 thresholds |
| `ER_GATE_MIN` | Gate A2a — **per-trade**, unchanged |
| `_parse_holding_days_from_field()` | Parse Max/Min/Avg hold strings |
| `parse_avg_holding_days()` | All-trades → win-trades fallback |
| `annualize_per_trade_return()` | `per_trade × 252 / hold_days` |
| `compute_composite_score(er, signal_alpha, sharpe, cagr_diff, avg_hold_days, asset_class)` | v4 4-component scorer |
| `enrich_signal_dict()` | Adds `er_annualized`, `signal_alpha_annualized`, passes `cagr_diff` to composite |
| `signal_to_surface_row()` | Exports `er_annualized`, `signal_alpha_annualized` in `<surface_json>` |

**Breaking change:** `compute_composite_score()` signature now requires `cagr_diff` and `avg_hold_days`. Returns `None` when hold days missing (cannot annualize).

### `constant.py`

- `GOOD_SIGNAL_QUERY` SIGNAL QUALITY COMPOSITE section rewritten for v4 (C1–C4, annualization, calibrated equity thresholds, score range −41 to +83).
- `<surface_json>` example includes `er_annualized` and `signal_alpha_annualized`.

### MindWealth_UI

| File | Change |
|------|--------|
| `src/components/quality_bubble_chart.py` | Y-axis label v4; caption C1–C4; hover adds annualized fields |
| `src/utils/signal_quality.py` | Exports `er_annualized`, `signal_alpha_annualized` to chart rows |

**Unchanged:** `tier` gate thresholds (`composite_score > 40` for tA, `> 20` for best) — same numeric cutoffs; scores will shift with recalibrated composite.

---

## Test coverage

```bash
cd /home/ubuntu/MindWealth
python3 -m pytest tests/test_signals_masterspec_g3.py -v
```

**Result at v4 release:** **19 passed** (was 15 at v5 supplementary release).

| New test | Covers |
|----------|--------|
| `test_composite_v4_wfg_example` | WFG.TO ≈ 80.9 |
| `test_composite_v4_atz_daily_c4_floor` | ATZ.TO C4 floor ≈ 53.5 |
| `test_annualize_per_trade_return` | Annualization helper |
| `test_holding_days_fallback_to_win_trades` | Hold-period proxy |
| `test_enrich_supplementary_fields_on_surface_row` | + `er_annualized`, `signal_alpha_annualized` in surface |

---

## Residual gaps

| Gap | Owner | Notes |
|-----|-------|-------|
| Non-equity threshold calibration | Spec owner | Provisional values only; equity calibrated at 80th pct |
| `tier` gate recalibration | Parth / Rohit | Cutoffs (40/20) may need retuning after score distribution shift |
| Tier distribution on live signals | Ops | Re-run nightly pipeline to refresh composite scores in reports |
| `instruction_docs_2/status_v4.md` naming | Docs | Supplementary audit doc — different scope from this file |

---

## Files changed

| File | Change |
|------|--------|
| `MindWealth/helper_functions/claude_lateness_metrics.py` | v4 composite, annualization, hold fallback, surface fields |
| `MindWealth/constant.py` | GOOD_SIGNAL_QUERY v4 formula + surface_json example |
| `MindWealth/tests/test_signals_masterspec_g3.py` | +4 v4 calibration tests (19 total) |
| `MindWealth_UI/src/components/quality_bubble_chart.py` | v4 labels + hover |
| `MindWealth_UI/src/utils/signal_quality.py` | Annualized field export |
| `MindWealth_UI/instruction_docs/signals_master_spec/status_v4.md` | This document |

---

## Relationship to other status docs

| Document | Role |
|----------|------|
| `status_v2.md` | Original A1–G3 implementation (3-component composite) |
| `status_v3.md` | UI bubble chart + surface_json inject snapshot |
| **`status_v4.md` (this file)** | **Composite v4 Calibrated formula** |
| `instruction_docs_2/status_v4.md` | Supplementary/AlphaInterp **pre-v5 audit** (different topic) |
| `instruction_docs_2/status_v5.md` | Supplementary §1/§2/§3/§6 implementation record |

---

*v4 Calibrated composite implemented per `MindWealth_Composite_v4_Calibrated.pdf`. For supplementary payload fields (tier, alpha_interpretation, etc.), see `instruction_docs_2/status_v5.md`.*
