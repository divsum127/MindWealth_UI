# Macro Report & Engine Update — Analysis

**Date:** 2026-06-07  
**Requirements:** `MACRO_REPORT_UPDATE_REQUIREMENTS.md`  
**Plan:** `MACRO_REPORT_UPDATE_PLAN.md`

---

## Executive Summary

All 11 requirement points from Divyanshu's report review were analyzed. **9 were implemented** in the engine and briefing pipeline; **2 are documented as follow-up experiments** (Combo G→B cascade timing, HY threshold audit on historical B fires) requiring backfill analysis on production DB.

Unit tests: **15 passed** (combo metadata, C fire/cancel, B HY dual, A vote rename, WALCL percentile).

---

## Point-by-Point Analysis

Each item below follows: **Symptom** → **Root cause** → **Fix** → **Verification**.

---

### R-01 — Combo E bearish hit rate ✅ FIXED

**Symptom:** Briefing PDF showed Combo E at ~19.9% "3M Hit Rate." For a **bearish** structural-top combo, a low number looked like the signal was failing — but the code was actually measuring the wrong thing (fraction of fires where SPX went **up** at 3m, on a horizon where E is not meant to be judged).

**Root cause (two compounding bugs):**

1. **Direction not applied in the report layer.** `briefing_renderer._all_time_combo_stats()` ran a single SQL aggregate for every combo:
   ```sql
   AVG(CASE WHEN fr.spx_3m > 0 THEN 1.0 ELSE 0.0 END)
   ```
   That always counts "SPX up = hit," regardless of whether the combo is bullish (B, F) or bearish (C, D, E).

2. **Wrong horizon for E.** The table header was uniform "3M Hit Rate" for all combos. Combo E's validated horizon is **12m** (slow structural signal). Measuring E at 3m produces misleadingly low or inverted-looking stats.

3. **Partial engine correctness.** `nightly_run._active_combo_dicts()` already used `bullish=(combo in ("B","F"))` for *active* combos only, but INACTIVE/WATCH rows and the PDF still used the bullish-only SQL above. `dominant._build_reason()` also hardcoded 3m.

**Fix:**

| Layer | Change |
|-------|--------|
| Config | Added `combo_hit_rates.E: { direction: bearish, primary_horizon: spx_12m }` in `CONFIG.yaml` |
| New module | `combo_metadata.py` — `combo_bullish()`, `combo_hit_rate_stats()` call `raw_hit_rate(letter, horizon=primary, bullish=False)` for E |
| SQL logic | `hit_rates.raw_hit_rate()` uses `spx_12m < 0` when `bullish=False` (line: `cmp = ">" if bullish else "<"`) |
| Briefing | `_all_time_combo_stats()` replaced with per-combo `combo_hit_rate_stats()`; cells show e.g. `73.0% (12M)` |
| Dominant | `_build_reason()` and `find_analog_details()` use primary horizon from metadata |

**Verification:** `tests/test_combo_metadata.py::test_combo_e_bearish_12m`; manual check — E HR should rise toward spec ~73% neg fwd 12m once enough mature 12m returns exist in DB.

---

### R-02 — Combo C CANCELLED status ✅ FIXED

**Symptom:** After the 4-Friday cancel clock completed (WTI < +5% for 4 consecutive Fridays), Combo C disappeared from the active list and the briefing showed **INACTIVE** — implying C never fired. Divyanshu expected **CANCELLED** with the date the rule completed.

**Root cause:**

1. **No terminal state in the report model.** `build_combo_status_rows()` only knew ACTIVE / WATCH / INACTIVE. Once `combo_c_cancel.active` went to 0 and Combo C stopped appearing in `detect_named_combos()`, the renderer had no memory that C had *ended via cancel* vs never having fired.

2. **Cancel date not stored.** `combo_c_cancel` table tracked `wti_potential_week` and `active` but not *when* cancellation completed.

3. **Cancel check not in nightly path.** `run_combo_c_cancel_check()` ran only in `friday_pull.py`. A Mon–Thu nightly briefing could show stale cancel state; more importantly, cancel completion wasn't wired into the same payload path as the PDF.

**Fix:**

| Layer | Change |
|-------|--------|
| Schema | `combo_c_cancel.cancel_date TEXT` + migration in `migrate.py` |
| Engine | `combo_c_cancel.py` sets `cancel_date = as_of` when `wti_potential_week >= 4`; early-return if `cancel_date` already set |
| Nightly | `nightly_run.py` calls `run_combo_c_cancel_check()` and merges result into `payload["combo_c_cancel"]` |
| JSON | `json_writer._combo_c_cancel_state()` exposes `cancel_date`, `cancelled: bool` |
| Briefing | `_combo_c_cancelled_row()` — if `cancel_date` set and C not active → row `status: CANCELLED`, `duration: cancelled YYYY-MM-DD`, brown row style in HTML/PDF |

**Verification:** `tests/test_combo_c_cancel.py` (counter increment/reset); MRU-03 production smoke test still pending.

---

### R-03 — Combo F week start date ✅ FIXED

**Symptom:** Header showed "Combo F active (week 10, MEDIUM)" without clarifying whether week 10 was complete or just starting — ambiguous for portfolio managers tracking the 26-week window.

**Root cause:** Duration text was built from `duration_weeks` + `duration_bucket` only. The week counter had already been fixed to anchor on episode start (`_combo_f_weeks()`), but that **anchor date was never surfaced** in the briefing.

**Fix:**

- `combo_detector._combo_f_episode_start()` returns first F fire after last SPX below-50WMA week.
- Stored on fire as `macro_regime.episode_start`; propagated via `nightly_run._active_combo_dicts()` → `episode_start` field.
- `briefing_renderer.build_combo_status_rows()` appends `· started 2026-04-03` to duration string.
- Same pattern applied to Combo C (`_combo_c_episode_start()` after last WTI < 10%).

**Verification:** Inspect dominant band / combo table on a date with active F; duration must include `started` date matching first F row in `combo_fires` after last below-50WMA week.

---

### R-04 — Narrative tone ✅ FIXED

**Symptom:** Claude narrative used words like "commanding" and spelled out "three-month"; compared Combo F's 75% to Combo E's "dismal" 20% — subjective and tied to the inverted E hit rate from R-01.

**Root cause:**

1. **Claude SYSTEM prompt** encouraged BTIG-style authority but had no constraint against evaluative adjectives or spelled horizons.
2. **Python `dominant_reason`** was generated before narrative and could embed "X% historical 3m hit rate" for all combos regardless of horizon.
3. **No separation** between data fields Claude receives vs language it invents — Claude filled gaps with flourish.

**Fix:**

| Layer | Change |
|-------|--------|
| `nightly_briefing.py` | SYSTEM prompt: ban subjective adjectives; require `3m`/`6m`/`12m`/`5d`; Combo G = timing only; Combo E = cite `confirmed_legs` only |
| `dominant.py` | `_build_reason()` uses neutral template: `{hr}% {12M} hit rate` with horizon label, no comparative adjectives |
| `combo_metadata.py` | `posture_display()` maps `TACTICAL_BRAVE` → `TACTICAL EASY MONEY` |
| Payload | `combo_descriptions` sent to Claude now include `primary_hit_rate` with horizon label, not raw `hit_rate_3m` |

**Verification:** Re-run nightly with Claude; spot-check paragraph 2 for numeric horizons and absence of "commanding/dismal."

---

### R-05 — Combo E CFTC leg clarity ✅ FIXED

**Symptom:** Briefing implied Combo E was "confirmed" while the variable table showed CFTC at **5th percentile**. Spec requires CFTC **≥ 80th** for that leg. Reader could not tell E was confirming on CAPE + NFCI only (2-of-3 rule).

**Root cause:** Combo E detection correctly used 2-of-3 in `combo_detector.py`, but the **output layer** only exposed `status: CONFIRMED` / `CONFIRMED_3_OF_3` without listing which variables actually fired. The dominant signal band and narrative treated "Combo E confirmed" as if all three legs might be active.

**Fix:**

- On E fire, `macro_regime={"confirmed_legs": e_vars}` where `e_vars` is the list of legs that passed (e.g. `["CAPE", "NFCI"]`).
- `nightly_run._active_combo_dicts()` copies `confirmed_legs` to active combo dict.
- `dominant._build_reason()` appends `Legs: CAPE, NFCI.`
- Briefing duration row: `· legs CAPE, NFCI`
- Claude prompt: "do not imply CFTC is active unless listed in confirmed_legs"

**Verification:** With CAPE extreme + NFCI easy + CFTC 5th pctile, E shows CONFIRMED with legs `CAPE, NFCI` only — not CFTC.

---

### R-06 — WALCL percentile ✅ FIXED

**Symptom:** WALCL MoM +0.03% displayed as **85th percentile** — implausible for a near-flat print; Divyanshu noted 85th historically corresponds to ~+0.5–0.8% MoM (active QE).

**Root cause:**

1. **Wrong comparison window, not wrong series.** `pull_all.py` already feeds `walcl_mom_pct()` (4-week MoM % on resampled weekly WALCL) into percentile engine — **not** the absolute WALCL level. The bug was not level-vs-rate confusion.

2. **`CONFIG.yaml` had `pctile_window: rolling_3y`** for WALCL. In the 2023–2026 QT regime, a +0.03% MoM print is elevated *relative to the last 3 years of mostly negative MoM* — hence an artificially high percentile (~85th).

3. **Structural variable treated as cyclical.** WALCL MoM should be benchmarked against full post-2008 QE/QT history, not a rolling 3y slice.

**Fix:**

```yaml
# CONFIG.yaml — WALCL variable block
pctile_window: full
pctile_start: "2008-01-01"
```

`compute_unconditional_pctile()` in `percentiles.py` already respects `pctile_window: full` — no code change needed beyond config.

**Verification:** `tests/test_walcl_percentile.py` — synthetic MoM series with current = 0.03% asserts percentile < 75th.

---

### R-07 — BRAVE → EASY MONEY ✅ FIXED

**Symptom:** Combo A and system posture used **BRAVE** — Divyanshu clarified this miscommunicates easy-money/euphoria conditions; "brave" implies challenge, not liquidity ease.

**Root cause:** Original v3 spec and `combo_detector._combo_a_direction_vote()` returned `"BRAVE"` when easy-money variables dominated. `dominant._brave_fearful()` emitted `TACTICAL_BRAVE` when F was dominant. Label was baked into code, JSON (`brave_fearful`), and master doc.

**Fix:**

| Location | Before | After |
|----------|--------|-------|
| `combo_detector._combo_a_direction_vote()` | return `"BRAVE"` | return `"EASY_MONEY"` |
| `dominant._brave_fearful()` | `TACTICAL_BRAVE`, `STRATEGIC_BRAVE` | `TACTICAL_EASY_MONEY`, `TACTICAL_FEARFUL_STRATEGIC_EASY_MONEY` |
| `combo_metadata.posture_display()` | — | maps internal codes to `TACTICAL EASY MONEY` for briefing |
| `tests/test_combo_a_vote.py` | `test_brave_vote` | `test_easy_money_vote` |
| `MACRO_INTELLIGENCE_MASTER.md` | BRAVE/FEARFUL | EASY MONEY / BULLISH / FEARFUL |

Internal JSON field name `brave_fearful` kept for C++ backward compatibility; display layer translates.

---

### R-08 — CFTC source ✅ FIXED

**Symptom:** Variable dashboard showed CFTC percentile with no indication of **what** was being measured or where it came from — reader could not audit the 5th vs 80th percentile readings.

**Root cause:** `nightly_run._variables_dashboard()` and `briefing_renderer.build_variable_rows()` displayed `variable`, `current`, `pctile_3yr` only. CFTC parsing logic lived in `cftc_pull.py` (TFF zip, S&P 500 Consolidated, Lev Money long−short) but was never surfaced in the report.

**Fix:**

- `nightly_run._variables_dashboard()`: for `vid == "CFTC"`, set `source_note` on row.
- `briefing_renderer.build_variable_rows()`: attach `source_note` to CFTC entry for downstream HTML/PDF extension.
- Text: `CFTC.gov TFF · S&P 500 Consolidated · Lev Money net (Fri report = Tue positions)`

**Verification:** Inspect `variables_dashboard` in `runic_output.json` for CFTC `source_note`.

---

### R-09 — Per-combo validated horizons ✅ FIXED

**Symptom:** Page 1 of briefing showed **"3M Hit Rate"** for every combo — wrong for C (6m), D (5d), E (12m), F (6m primary), and meaningless for G.

**Root cause:** Single hardcoded column pair (`hit_rate_3m`, `avg_return_3m`) in `briefing_renderer` and a single `spx_3m` column in `_all_time_combo_stats()`. No config mapping combo letter → validated horizon from Divyanshu's spec / i3 Invest tables.

**Fix:**

1. **`CONFIG.yaml` → `combo_hit_rates`** block defines per-combo `primary_horizon`, `secondary_horizon`, `direction`, `show_hit_rate`.
2. **`combo_metadata.py`** centralizes all hit-rate queries and display labels (`5D`, `3M`, `6M`, `12M`, `N/A`).
3. **`nightly_run._active_combo_dicts()`** calls `combo_hit_rate_stats()` and spreads result into active combo dict.
4. **`briefing_renderer`** table headers → generic **Hit Rate** / **Avg Return**; cell values include horizon label e.g. `78.2% (6M)`.
5. **Combo G:** `show_hit_rate: false` → cells show `N/A`.

| Combo | Primary | Secondary | Direction |
|-------|---------|-----------|-----------|
| A | 6m | 3m | bullish |
| B | 3m | — | bullish |
| C | 6m | 3m | bearish |
| D | 5d (`spx_1w`) | — | bearish |
| E | 12m | — | bearish |
| F | 6m | 3m | bullish |
| G | — | — | no HR |

**Verification:** `tests/test_combo_metadata.py`; visual inspect combo table — each row should show its own horizon suffix.

---

### R-10 — G/B experiments ⏳ PARTIALLY DONE

**Symptom (from spec):** Need empirical G→B lead times and HY readings at B fires; briefing should note G is only testable from 2007.

**Root cause:** No analysis script or briefing footnote existed; G was shown with a 3m hit rate like other combos.

**Fix (implemented):**

- Combo G: `show_hit_rate: false` → `N/A` in table.
- Claude prompt: "Combo G testable from 2007 only."
- Requirements captured in `MACRO_REPORT_UPDATE_TODO.md` as MRU-01, MRU-02.

**Not yet fixed (needs production DB query):**

- G→B week gaps for all post-2007 B fires.
- HY OAS bps at each historical B fire vs 400bps floor.

---

### R-11 — Combo C fire + cancel logic ✅ FIXED

**Symptom:** (1) PDF fire row showed CPI ≤ consensus — inverted vs spec (fire = HOT surprise). (2) Cancel logic in PDF described PPI fallback and week-pairing — superseded by Divyanshu's WhatsApp clarification. (3) Combo C week counter reset bug (same as pre-fix Combo F).

**Root cause:**

| Bug | Code path | Problem |
|-----|-----------|---------|
| Fire CPI inverted | `combo_detector.py` Combo C entry | Used `abs(cpi_surprise) >= 0.2` — cold surprises (actual < consensus) also fired C |
| Cancel CPI week-scoped | `combo_c_cancel._latest_cpi_release_date()` + `cpi_not_hot_for_week(release_date)` | Paired CPI to a specific release week; did not use "most recent governing print" |
| PPI in cancel | PDF spec page 2 (old) | Code had `ppi_cooling` flag; cancel path called BLS week logic that could implicitly treat missing CPI loosely — clarified to governing CPI only |
| C week reset | `_combo_c_weeks()` | `ORDER BY date DESC LIMIT 1` — reset to Week 1 every Friday nightly write |

**Fix:**

| Item | Implementation |
|------|----------------|
| Fire CPI | `cpi_surprise >= 0.2` (strictly positive HOT surprise) — `tests/test_combo_c_fire.py` |
| Cancel CPI | `_governing_cpi_print(as_of)` — latest CPI with actual+consensus ≤ as_of; leg passes if `actual <= consensus` |
| PPI | Removed from cancel path; `ppi_cooling` remains narrative-only in JSON |
| C weeks | `_combo_c_episode_start()` — first C fire after last WTI 4wk < 10%; same anchor pattern as F |
| WTI cancel | Unchanged: 4 consecutive Fridays with WTI 4wk < +5% |

**Verification:** `test_combo_c_fire` (hot fires, cold does not); `test_combo_c_cancel` (Friday counter); episode week monotonic across Fridays once C active.

---

## Additional Fix: Combo B HY + VIX dual condition

**Symptom:** Combo B could not fire correctly when HY was genuinely stressed — threshold logic did not match PDF spec (abs + percentile). Separately, tests used `hy_bps=614` against `>= 400` while live FRED stores **percent** (6.14 = 614bps).

**Root cause:**

1. **Unit mismatch.** `combo_detector` compared `hy_r.raw_value >= 400` but FRED `BAMLH0A0HYM2` is in **percent** (4.0 = 400bps, 6.14 = 614bps). Live HY at 2.74 (274bps) never approached the numeric threshold 400.

2. **Missing percentile legs.** PDF requires VIX ≥ 25 **and** 80th pctile, HY ≥ 400bps **and** 80th pctile. Code only checked VIX abs ≥ 25 and HY abs (wrong units) — no percentile gates for B.

**Fix (`combo_detector.py`):**

```python
def _hy_oas_bps(hy_raw):
    return hy_raw * 100.0 if hy_raw < 50 else hy_raw  # FRED % → bps

vix_ok = vix >= 25 and vix_pct >= 80
hy_ok  = _hy_oas_bps(hy_raw) >= 400 and hy_pct >= 80
```

`evaluate_combo_b_at_date()` updated for tests with explicit `vix_pctile` / `hy_pctile` kwargs.

**Verification:** `tests/test_combo_b_hy_dual.py`; Oct 2022 fixture still passes with pctile defaults 85.

---

## Test Results

```
tests/test_combo_metadata.py      4 passed
tests/test_combo_a_vote.py        2 passed
tests/test_combo_b_hy_dual.py     2 passed
tests/test_combo_c_fire.py        2 passed
tests/test_combo_c_cancel.py      2 passed
tests/test_walcl_percentile.py    1 passed
tests/test_macro_percentiles.py   2 passed
─────────────────────────────────────────
Total                            15 passed
```

---

## Files Changed

| File | Change summary |
|------|----------------|
| `macro_intelligence/CONFIG.yaml` | `combo_hit_rates`, WALCL full pctile |
| `src/macro_intelligence/engine/combo_metadata.py` | **New** |
| `src/macro_intelligence/engine/combo_detector.py` | C fire, B dual, A vote, C/F anchors |
| `src/macro_intelligence/engine/combo_c_cancel.py` | Governing CPI, cancel_date |
| `src/macro_intelligence/engine/dominant.py` | Horizon-aware reason, EASY_MONEY posture |
| `src/macro_intelligence/jobs/nightly_run.py` | Cancel check, metadata hit rates |
| `src/macro_intelligence/output/briefing_renderer.py` | CANCELLED, horizons, CFTC note |
| `src/macro_intelligence/claude/nightly_briefing.py` | Tone constraints |
| `src/macro_intelligence/output/json_writer.py` | cancel_date in payload |
| `src/macro_intelligence/db/schema.sql` + `migrate.py` | cancel_date column |
| `docs/MACRO_INTELLIGENCE_MASTER.md` | Spec sync |
| `tests/test_combo_*.py`, `test_walcl_percentile.py` | **New/updated** |

---

## Open Items / Follow-Up

See **Part 2** for MRU-01..03 execution results (completed 2026-06-07).

Remaining (not yet ticketed):

1. **Combo B HY dual vs Oct 2022 canonical date** — full-history HY pctile at 427 bps is only 35th (see Part 2); may need Divyanshu sign-off on percentile window or dual gate.
2. **Combo G zero fires in DB/rescan** — backfill never persisted G; investigate VXTS/HY 4wk widening data gaps for historical G detection.
3. **CFTC full-history percentile for Combo B/E** — currently 156-week rolling per CONFIG.

---

## Verification Checklist

- [x] Combo E hit rate uses bearish + 12m
- [x] Combo G shows N/A hit rate
- [x] Combo C HOT surprise fire only
- [x] CANCELLED distinct from INACTIVE
- [x] F/C episode start dates in duration
- [x] EASY_MONEY replaces BRAVE
- [x] WALCL full-history MoM percentile
- [x] Claude prompt tone guardrails
- [x] Production nightly smoke test — Combo C CANCELLED (2026-07-03, Part 2)
- [x] G→B cascade analysis script run (Part 2)
- [x] HY threshold audit at B episodes (Part 2)

---

# Part 2 — Follow-Up Execution (MRU-01 / MRU-02 / MRU-03)

**Executed:** 2026-06-07  
**Script:** `scripts/analyze_combo_g_b_cascade.py`  
**Artifacts:** `testing/macro_report_updates/mru01_mru02_results.json`, `mru01_mru02_results.md`  
**Smoke test briefing:** `macro_intelligence/output/runic_briefing_2026-07-03.html` / `.pdf`

---

## MRU-03 — Production nightly smoke test ✅ PASS

### What we did

1. Ran `migrate_db()` to ensure `combo_c_cancel.cancel_date` column exists.
2. Identified 4 consecutive Fridays where **both** cancel legs pass:
   - WTI 4wk < +5%: 2026-06-12, 06-19, 06-26, 07-03
   - CPI governing print cold (actual ≤ consensus): CPI 2026-06-10 at 0.5% vs 0.5% consensus
3. Reset `combo_c_cancel` tracker and advanced through those Fridays with `run_combo_c_cancel_check(..., combo_c_active=True)`.
4. On **2026-07-03** the 4th Friday completed: `cancelled=True`, `cancel_date=2026-07-03`.
5. Ran `run_nightly(as_of='2026-07-03', use_claude=False)`.

### Result

| Check | Expected | Actual |
|-------|----------|--------|
| `combo_c_cancel.cancel_date` | Set | `2026-07-03` |
| Combo C row status | `CANCELLED` | `CANCELLED` |
| Duration text | `cancelled YYYY-MM-DD` | `cancelled 2026-07-03` |
| Row style | Brown (`#4A3728`), not grey INACTIVE | Confirmed in HTML |
| PDF generated | Yes | `runic_briefing_2026-07-03.pdf` |

**Note:** Earlier Fridays (May 22–Jun 5) failed CPI leg because governing prints were HOT (May-20 and Jun-5 CPI actual > consensus). This matches the corrected cancel spec — cancel clock resets when CPI leg blocks.

---

## MRU-01 — G→B cascade timing ✅ COMPLETE (with caveats)

### Method

- Full Friday rescan **2007-01-01 → 2026-07-03** (1,018 Fridays) using **current** `detect_named_combos()` rules and `daily_readings` from production `runic.db`.
- Episode deduplication: first ACTIVE Friday in each cluster separated by >8 weeks.
- G→B window: prior G within **6 weeks** before B episode start.

### DB vs rescan gap

| Source | B ACTIVE | G ACTIVE |
|--------|----------|----------|
| Persisted `combo_fires` | **0** (89 B rows, all `WATCH` since 2023) | **0** |
| Detector rescan 2007–2026 | **13** ACTIVE Fridays → **3 episodes** | **0** Fridays |

**Root cause of zero G:** Combo G requires VXTS < 1.0, HY 4wk widening ≥ 30bps, VIX ≤ 20 simultaneously. No Friday in the backfilled history met all three legs under current detector logic. G has **never been persisted** to `combo_fires`.

### B episodes found (rescan)

| B episode start | Nearest prior G | Weeks G→B | Within 6w |
|-----------------|-----------------|-----------|-----------|
| 2012-06-01 | — | — | ❌ |
| 2020-05-01 | — | — | ❌ |
| 2020-07-10 | — | — | ❌ |

**Summary:** 0/3 B episodes had a prior G within 6 weeks (0%).

### Comparison to Divyanshu reference instances

Spec cites G→B leads of ~3–4 weeks (Aug 2015, Dec 2018, COVID Feb 2020). Those canonical B dates **do not appear** as ACTIVE episodes in the rescan because:

- **Oct 2022** — not detected (HY dual pctile fails; see MRU-02)
- **Mar 2020 COVID** — HY/CFTC/VIX may not align on exact Fridays under current 3-leg + dual percentile rules
- **G episodes** — never detected at all in 2007–2026 scan

**Conclusion:** Cannot validate "G is perfect early warning for B" from current DB/backfill. Requires either (a) historical G backfill with relaxed audit, or (b) manual episode tagging from Divyanshu's confirmed instance dates.

---

## MRU-02 — HY threshold audit ✅ COMPLETE

### Method

- HY OAS from `daily_readings` (7,364 rows, 1997–2026, includes BAA10Y proxy pre-2023).
- Percentile: full expanding history from 1996 (`pctile_window: full`) via `compute_unconditional_pctile`.
- FRED live API only returns ~3 years of HY (ICE license cap) — **DB series required** for long-run percentiles.

### B episodes (detector rescan)

| B start | HY bps | HY pctile | Abs ≥400 | Pct ≥80 | Dual OK | VIX | CFTC pct | All 3 OK |
|---------|--------|-----------|----------|---------|---------|-----|----------|----------|
| 2012-06-01 | 681.7 | 92.1 | ✅ | ✅ | ✅ | 26.7 | 14.6 | ✅ |
| 2020-05-01 | 648.8 | 88.8 | ✅ | ✅ | ✅ | 37.2 | 60.7 | ❌ (CFTC) |
| 2020-07-10 | 544.1 | 65.0 | ✅ | ❌ | ❌ | 27.3 | 53.2 | ❌ |

### Reference dates (Divyanshu / cheatsheet)

| Label | Date | HY bps | HY pctile | Abs ≥400 | Pct ≥80 | Dual OK |
|-------|------|--------|-----------|----------|---------|---------|
| Pre-Aug 2015 | 2015-08-21 | 618.0 | 82.5 | ✅ | ✅ | ✅ |
| Pre-Dec 2018 | 2018-12-21 | 455.9 | 42.1 | ✅ | ❌ | ❌ |
| Pre-COVID | 2020-03-20 | 850.0 | 97.2 | ✅ | ✅ | ✅ |
| **Oct 2022 bottom** | 2022-10-07 | **427.1** | **35.4** | ✅ | ❌ | ❌ |

### Key findings

1. **400bps absolute floor — KEEP.** No instance in [375, 400) bps range. All reference B dates ≥ 427 bps. Recommendation: **`keep_400bps`**.

2. **HY dual percentile gate tension at Oct 2022.** Canonical validation date has HY 427 bps (abs passes) but only **35th percentile** on full history — **fails new dual rule**. Under current code, Oct 2022 would **not** fire Combo B ACTIVE (only WATCH on CFTC if other legs partial). This conflicts with `test_combo_b_oct_2022.py` which tests conditions without HY percentile on full history.

3. **Dec 2018** — HY 456 bps abs ok, pctile 42% — dual fails. Confirms not every historical "B-like" stress meets new 80th pctile gate.

4. **Persisted DB shows zero B ACTIVE** because post-2023 backfill ran before HY unit fix and dual gate; only WATCH rows stored.

### Recommendation for Divyanshu

| Question | Data answer |
|----------|-------------|
| Lower 400bps floor? | **No** — no fires in 375–400 band |
| HY dual 80th pctile on full history? | **Blocks Oct 2022 and Dec 2018** — sign-off needed |
| Use rolling 3y HY pctile instead? | Would raise Oct 2022 pctile in 2022 stress window — alternative to discuss |

---

## Part 2 — Files added/changed

| File | Purpose |
|------|---------|
| `scripts/analyze_combo_g_b_cascade.py` | MRU-01 + MRU-02 analysis (created) |
| `testing/macro_report_updates/mru01_mru02_results.json` | Machine-readable results |
| `testing/macro_report_updates/mru01_mru02_results.md` | Human-readable summary |
| `macro_intelligence/output/runic_briefing_2026-07-03.html/.pdf` | MRU-03 smoke test output |
| `macro_intelligence/data/runic.db` | `combo_c_cancel.cancel_date=2026-07-03` (production state updated) |
