# Macro Report & Engine Update — Implementation Plan

**Date:** 2026-06-07  
**Requirements:** `MACRO_REPORT_UPDATE_REQUIREMENTS.md`

---

## Phase 1 — Foundation (combo metadata + config)

1. Add `combo_hit_rates` section to `CONFIG.yaml` with per-combo:
   - `bullish` / `bearish` / `null`
   - `primary_horizon`, `secondary_horizon`
   - `show_hit_rate` (false for G)
   - `horizon_label` for PDF column header
2. Create `engine/combo_metadata.py`:
   - `combo_bullish(letter) -> bool | None`
   - `combo_primary_horizon(letter) -> str | None`
   - `combo_hit_rate_stats(letter) -> dict`
   - `horizon_display_label(col) -> str` (e.g. `spx_12m` → `12M`)
3. Change WALCL `pctile_window` from `rolling_3y` → `full`, `pctile_start: 2008-01-01`.

---

## Phase 2 — Engine logic fixes

### 2a. Hit rates (R-01, R-09)
- Replace hardcoded `bullish=(combo in ("B","F"))` with `combo_metadata.combo_bullish()`.
- `dominant._build_reason()` uses primary horizon + numeric labels.
- `briefing_renderer._all_time_combo_stats()` respects direction per combo.

### 2b. Combo C (R-02, R-11)
- **Fire:** `cpi_surprise >= +0.2` (not `abs >= 0.2`).
- **Cancel CPI:** `_governing_cpi_print(as_of)` — latest confirmed CPI ≤ as_of; leg passes if `actual <= consensus`.
- **Schema:** `combo_c_cancel.cancel_date TEXT`.
- **Cancel check** in `nightly_run.py` (same as Friday pull).
- **`_combo_c_weeks()`:** episode anchor = first C fire after last WTI < 10%.
- **Briefing:** if `cancel_date` set and not active → status `CANCELLED`.

### 2c. Combo B HY dual (R-10)
- Convert FRED HY % to bps: `hy_bps = raw * 100`.
- `hy_ok = hy_bps >= 400 AND hy_pctile >= 80` (full-history percentile from reading).
- VIX: `vix >= 25 AND vix_pctile >= 80` per PDF spec.
- Update `evaluate_combo_b_at_date()` for tests.

### 2d. Combo A vote (R-07)
- `BRAVE` → `EASY_MONEY`; display as `EASY MONEY / BULLISH`.
- `TACTICAL_BRAVE` → `TACTICAL_EASY_MONEY` in posture strings.

### 2e. Combo E legs (R-05)
- Add `confirmed_legs: list[str]` to active combo dicts for E (and others where useful).

### 2f. Combo F start date (R-03)
- Expose `episode_start_date` from `_combo_f_episode_start()`.

---

## Phase 3 — Report pipeline

### 3a. Briefing renderer
- Combo table columns: `Primary Hit` + `Avg Return` (horizon-specific labels per row).
- Combo G: `N/A` for hit rate columns.
- CANCELLED row styling (distinct from INACTIVE grey).
- Variable dashboard: CFTC footnote row / meta column.
- POSTURE labels use EASY MONEY terminology.

### 3b. Claude nightly briefing
- System prompt additions:
  - No subjective adjectives (commanding, dismal, etc.).
  - Use `3m`, `6m`, `12m`, `5d` not spelled numbers.
  - Combo G: timing warning, not return predictor.
  - Combo G testable from 2007 only.
- Pass `confirmed_legs` and per-combo horizon stats in user payload.

---

## Phase 4 — Testing

| Test file | Coverage |
|-----------|----------|
| `tests/test_combo_metadata.py` | Horizons, bearish E, G no HR |
| `tests/test_combo_c_cancel.py` | Governing CPI, cancel_date |
| `tests/test_combo_c_fire.py` | HOT surprise fire, cold no-fire |
| `tests/test_combo_b_hy_dual.py` | Abs + pctile dual |
| `tests/test_combo_a_vote.py` | EASY_MONEY rename |
| `tests/test_walcl_percentile.py` | MoM near-zero ~50th pctile |

Run: `python -m pytest tests/test_combo_*.py tests/test_macro_percentiles.py -q`

---

## Phase 5 — Documentation

1. `testing/macro_report_updates/MACRO_REPORT_UPDATE_ANALYSIS.md` — before/after, experiment results, open items.
2. `docs/MACRO_INTELLIGENCE_MASTER.md` — §3 combos, §6 thresholds, briefing section.
3. Job status logs per repository rules.

---

## Rollout order

```
Config + metadata → Engine fixes → Nightly integration → Briefing/PDF → Tests → Docs
```

## Risks & mitigations

| Risk | Mitigation |
|------|------------|
| HY unit confusion (% vs bps) | Central `_hy_oas_bps()` helper |
| Existing combo_fires hit rates at wrong horizon | `_all_time_combo_stats` recomputes from DB with correct horizon |
| Cancel state lost on DB without migration | `migrate_db()` adds `cancel_date` column idempotently |
| Claude still uses flowery language | Template fallback + prompt constraints; `dominant_reason` is Python-controlled |
