# Macro Report & Engine Update Requirements

**Source:** `Report update todo details.md` (Divyanshu review of Runic briefing PDF v2.2)  
**Date compiled:** 2026-06-07  
**Scope:** Report pipeline (`briefing_renderer`, `nightly_briefing`) + macro intelligence engine (`combo_detector`, `hit_rates`, `combo_c_cancel`, percentiles)

---

## Summary Table

| ID | Area | Priority | Type | Status |
|----|------|----------|------|--------|
| R-01 | Hit rate direction (Combo E bearish) | P0 | Bug fix | Planned |
| R-02 | Combo C CANCELLED state + cancel date | P0 | Feature | Planned |
| R-03 | Combo F week start date in briefing | P1 | UX | Planned |
| R-04 | Narrative tone (no "commanding"; numeric horizons) | P1 | Prompt | Planned |
| R-05 | Combo E CFTC leg clarity (80th pctile) | P0 | Logic/display | Planned |
| R-06 | WALCL percentile on MoM% distribution | P0 | Bug fix | Planned |
| R-07 | BRAVE → EASY MONEY / BULLISH (Combo A) | P1 | Rename | Planned |
| R-08 | CFTC data source documentation | P2 | Docs/display | Planned |
| R-09 | Per-combo validated hit-rate horizons | P0 | Spec fix | Planned |
| R-10 | Combo G/B historical validation experiments | P2 | Analysis | Planned |
| R-11 | Combo C fire + cancel logic corrections | P0 | Spec fix | Planned |

---

## R-01 — Bearish combo hit rate inversion (Combo E)

**Problem:** Combo E shown at ~19.9% hit rate. E is **bearish** — hit rate = fraction of fires where SPX return is **negative** at the validated horizon.

**Root cause (suspected):** Briefing `_all_time_combo_stats()` always counts `spx_3m > 0`, ignoring combo direction.

**Required fix:**
- Label each combo `bullish` or `bearish` in config/metadata.
- Hit rate: bullish → `return > 0`; bearish → `return < 0`.
- Apply at engine (`nightly_run`, `dominant`) and report (`briefing_renderer`).

**Acceptance:** Combo E hit rate reflects % of fires with negative SPX at primary horizon (12m), not positive at 3m.

---

## R-02 — Combo C CANCELLED vs INACTIVE

**Problem:** Combo C shows INACTIVE when it should show **CANCELLED** with cancel date after 4 consecutive Fridays of WTI < +5% and CPI leg passing.

**Required fix:**
- Distinct `CANCELLED` status in briefing/PDF (not INACTIVE).
- Persist `cancel_date` when 4-Friday rule completes.
- Run cancel check in nightly job (not only Friday pull).

**Acceptance:** Post-cancel briefing row: `CANCELLED · cancelled YYYY-MM-DD`.

---

## R-03 — Combo F duration: episode start date

**Problem:** "Week 10 (MEDIUM)" unclear — is week 10 complete or starting next Monday?

**Required fix:** Show episode anchor date, e.g. `Week 10 of 26 (MEDIUM) · started 2026-04-03`.

---

## R-04 — Narrative language constraints

**Problem:** Claude narrative uses subjective words ("commanding", "dismal") and spells out "three-month".

**Required fix:**
- Python `dominant_reason` uses neutral numeric phrasing.
- Claude system prompt: no subjective adjectives; use `3m`, `6m`, `12m` not spelled numbers; state hit rates as `75% 6m hit rate`.

**Source:** Claude API generates narrative; Python generates `dominant_reason` — both need guardrails.

---

## R-05 — Combo E confirmation vs CFTC percentile

**Problem:** E marked confirmed while CFTC dashboard shows 5th percentile. E CFTC **leg** requires **≥ 80th percentile** (2-of-3 rule).

**Clarification:** E can confirm on CAPE + NFCI without CFTC. Briefing must show **which legs are active**, not imply all three.

**Required fix:** Expose `confirmed_legs` in combo payload; dominant reason cites active legs only.

---

## R-06 — WALCL percentile at near-zero MoM%

**Problem:** WALCL MoM 0.03% shown as 85th percentile — should be ~50th.

**Root cause (suspected):** Percentile window/distribution mismatch (3y rolling in recent QT regime vs full-history MoM%).

**Required fix:**
- Percentile computed on **WALCL MoM%** series (not absolute WALCL level).
- Use **full expanding history** from 2008 (FRED WALCL inception for meaningful BS changes).

**Acceptance:** 0.03% MoM maps to ~40–60th percentile, not 85th.

---

## R-07 — Combo A: BRAVE → EASY MONEY / BULLISH

**Problem:** "BRAVE" miscommunicates euphoria/easy-money conditions. Divyanshu prefers **EASY MONEY** or **BULLISH** for Combo A liquidity-ease vote.

**Required fix:** Rename internal vote label and all briefing/posture display strings.

---

## R-08 — CFTC source clarification

**Required:** Document in briefing variable dashboard:
- Source: CFTC.gov TFF futures-only report
- Contract: S&P 500 Consolidated
- Classification: Leveraged Money (Fast Money) net long − short
- Lag: Friday report reflects prior Tuesday positions (~3-day lag)

---

## R-09 — Per-combo validated hit-rate horizons

**Problem:** PDF shows uniform "3M Hit Rate" for all combos — wrong for several.

| Combo | Primary horizon | Secondary | Return predictor? |
|-------|-----------------|-----------|-------------------|
| A | 6m | 3m | Yes |
| B | 3m | — | Yes |
| C | 6m | 3m | Yes (duration-tracked) |
| D | 5d (`spx_1w`) | — | Yes |
| E | 12m | — | Yes (slow structural) |
| F | 6m | 3m | Yes |
| G | — | — | **No** (timing warning only) |

**Sources:** i3 Invest tables, institutional research, economic reasoning (see original todo §9).

**Required fix:** Dynamic horizon column per combo in briefing table; engine hit-rate queries use primary horizon.

---

## R-10 — Combo G/B validation experiments (open questions)

### G testability
- Pre-2007 B instances lack 3m VIX data → **Combo G testable from 2007 only** (note in briefing).

### G → B lead time
| Instance | G lead before B |
|----------|-----------------|
| Pre-Aug 2015 | ~3 weeks |
| Pre-Dec 2018 | ~4 weeks |
| Pre-COVID Feb 2020 | ~3 weeks |
| Apr 2025 | G fired; B never completed |

**Action:** Measure elapsed G→B weeks for all post-2007 B fires; report how many had G within 6 weeks.

### Combo B HY threshold audit
**Action:** For each confirmed B fire since 1990, record HY OAS on fire date.
- If any instance had HY 375–400 bps → lower 400 bps floor.
- Confirm **dual condition:** HY > 400 bps **AND** ≥ 80th percentile of **full** history (1996+, no 3y rolling).

### Combo G special rules
Per `Runic Agent Named Combos v2.pdf` row G — leading indicator, credit-vol divergence, watch G→B cascade.

---

## R-11 — Combo C fire + cancel logic (supersedes PDF page 2)

### Fire condition (CORRECTION)
- **Correct:** CPI actual > consensus by **≥ +0.2pp** (HOT surprise).
- **Wrong (PDF):** CPI actual ≤ consensus in fire row (that belongs in cancel only).

### Cancel — CPI leg
On each Friday:
1. Use **most recent confirmed CPI print** (regardless of publication week).
2. `actual ≤ consensus` → CPI leg **PASSES**.
3. `actual > consensus` → CPI leg **BLOCKED**.
4. BLS delay/shutdown → last confirmed print governs; no pending flags, no clock pause.
5. WTI 4-Friday counter runs independently; resets to 0 if either leg fails.
6. **PPI is NOT a CPI substitute** in cancel logic. PPI stored as `ppi_cooling` for narrative only.

### Cancel — WTI leg
4 consecutive Fridays with rolling 28-day WTI change < +5%.

---

## Experiments & Tests to Run

| Test ID | Description | Pass criteria |
|---------|-------------|---------------|
| T-HR-01 | Combo E hit rate at 12m, bearish | HR = % negative SPX_12m |
| T-HR-02 | Combo C hit rate at 6m primary, 3m secondary | Table shows both |
| T-HR-03 | Combo G row shows "N/A" not hit rate | No return HR displayed |
| T-CC-01 | Combo C fire requires CPI surprise ≥ +0.2pp | Cold surprise does not fire |
| T-CC-02 | Cancel uses governing CPI print | Not week-window PPI fallback |
| T-CC-03 | CANCELLED status after 4 Fridays | Date stored |
| T-HY-01 | Combo B HY dual: abs + 80th pctile full history | Both required |
| T-WAL-01 | WALCL 0.03% MoM percentile | ~50th not 85th |
| T-GB-01 | G→B lead time analysis | Document in analysis doc |

---

## Files Expected to Change

| File | Changes |
|------|---------|
| `macro_intelligence/CONFIG.yaml` | Horizons, WALCL window, combo metadata, posture labels |
| `src/macro_intelligence/engine/combo_metadata.py` | **New** — direction, horizons, labels |
| `src/macro_intelligence/engine/combo_detector.py` | C fire, B HY dual, A vote rename, C/F weeks |
| `src/macro_intelligence/engine/combo_c_cancel.py` | CPI governing print, cancel_date |
| `src/macro_intelligence/engine/dominant.py` | Horizon-aware reasons |
| `src/macro_intelligence/jobs/nightly_run.py` | Cancel check, horizon hit rates |
| `src/macro_intelligence/output/briefing_renderer.py` | CANCELLED, horizons, CFTC source |
| `src/macro_intelligence/claude/nightly_briefing.py` | Tone constraints |
| `src/macro_intelligence/output/json_writer.py` | cancel_date in payload |
| `src/macro_intelligence/db/schema.sql` + `migrate.py` | cancel_date column |
| `tests/test_*` | New/updated unit tests |
| `docs/MACRO_INTELLIGENCE_MASTER.md` | Engine spec updates |
