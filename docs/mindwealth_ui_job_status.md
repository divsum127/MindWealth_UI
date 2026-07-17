# MindWealth UI — Job Status

Task tracking for MindWealth UI (`/home/ubuntu/uiv2/git/MindWealth_UI`).

**Files:**
- Job Status (this file): `/home/ubuntu/uiv2/git/MindWealth_UI/docs/mindwealth_ui_job_status.md`
- Implementation Details: `/home/ubuntu/uiv2/git/MindWealth_UI/docs/mindwealth_ui_repo_job_status_details.md`

---

## TODO

_Tasks that are planned or currently in progress. Move to DONE when completed._

---

### Data & Pipeline Integrity Audit — 2026-06-06
_Findings from web-verified cross-check of nightly report variables and combo classifications._

#### 🔴 Priority 1 — Fix Required

**T-01: Fed Cycle persists as "CUTTING_LATE" during 5-month Fed pause with hike risk**
- **What**: `fed_cycle_at_date()` in `fed_cycle.py` carries forward the last known cycle label (`CUTTING_LATE`) during a PAUSE via the `series.iloc[-1]` fallback (lines 187-190). The Fed has been on hold at 3.50–3.75% since at least January 2026 (FOMC meetings Jan 28, Mar 18, Apr 29 all held). The Jun 5 jobs report (172K, above consensus) now has markets pricing 42.7% probability of a Dec 2026 rate HIKE. Reporting `CUTTING_LATE` when the Fed is paused and hike-risk is rising mis-frames the narrative and regime analysis.
- **Fix needed**: Introduce a `PAUSING` label that activates after N consecutive weeks of PAUSE following a cutting cycle, OR add a `hike_risk_threshold` (e.g. CME FedWatch >30%) override. At minimum, add `PAUSING_POST_CUT` as a distinct state after `cycle_early_months` of pause.
- **Files**: `src/macro_intelligence/engine/fed_cycle.py`, `macro_intelligence/CONFIG.yaml`

~~**T-02: Nightly job does not auto-refresh CFTC TFF ZIP on Fridays — data goes stale by one week**~~ → **FIXED 2026-06-07** — see DONE section.

~~**T-03: `_combo_c_weeks()` will show perpetual Week 1 when Combo C re-activates**~~ → **FIXED 2026-06-07** — episode anchor pattern applied (see DONE #15).

**T-03: VIX single-day spike magnitude not detected — tier stays NORMAL despite +40% jump**
- **What**: On Jun 5, 2026, VIX jumped 39.68% (15.40 → 21.51) driven by Broadcom guidance miss and strong jobs report (chip stocks lost $1.3T market cap; S&P 500 −2.63%). The system classifies VIX as NORMAL because the absolute level (21.51) is below the RARE threshold (25.0 abs_level). No mechanism exists to detect single-day spike magnitude as a stress signal. A 40% one-day spike is historically significant and should escalate tier.
- **Fix needed**: Add `single_day_pct_change` threshold to VIX tier logic in `evaluate_variable_tier()` (e.g. daily change ≥ 25% → RARE, ≥ 40% → EXTREME regardless of abs level). Requires pulling prior-day VIX close alongside current.
- **Files**: `src/macro_intelligence/engine/percentiles.py`, `macro_intelligence/CONFIG.yaml`

---

#### 🟡 Priority 2 — Investigate / Improve

**T-03: CAPE value inconsistency between sources (~1.3pt gap)**
- **What**: Report shows CAPE = 42.70. Multpl (Shiller's official data): 42.84 (Jun 2, 2026). GuruFocus: 41.44 (Jun 2026). The 1.3-point GuruFocus gap is meaningful at the EXTREME classification threshold (32). If the system scrapes from a third source, it may drift from Shiller's canonical series.
- **Fix needed**: Confirm which URL `cape_scrape.py` fetches from; standardise to `multpl.com/shiller-pe` (Shiller's official distributor). Add a sanity-check log warning if scraped CAPE deviates >1.0 from prior week's value.
- **Files**: `src/macro_intelligence/data/cape_scrape.py`

**T-04: Combo B WATCH triggered by only 1 of 3 required conditions (CFTC only)**
- **What**: Combo B (Capitulation) requires VIX ≥ 25, HY ≥ 400bps, AND CFTC ≤ 15th pctile. Current: VIX = 21.51 (❌), HY = 274bps (❌), CFTC = 5th pctile (✅). Only 1 of 3 legs met, yet the report displays B as WATCH with "BULLISH" direction. Per architecture §4.6, 1+ legs = WATCH, but this single-leg WATCH may mislead readers into thinking capitulation is forming.
- **Fix needed**: In the combo status table, add a "Legs Met" sub-column (e.g. "1/3") so readers understand how far B is from activation. Alternatively, raise the WATCH floor to ≥ 2/3 conditions.
- **Files**: `src/macro_intelligence/output/briefing_renderer.py`, `src/macro_intelligence/engine/combo_detector.py`

**T-05: Combo F Week 1 activation on a down-2.63% day needs reclaim validation**
- **What**: Combo F (Recovery) fired as ACTIVE Week 1. The trigger requires SPX weekly close to be 3%+ above the 50-week moving average. SPX closed Jun 5 at 7,384.67 — below its 50-DAY MA (7,561.51). Cannot independently confirm the 50-WEEK MA level from web, but the 9-week winning streak that just ended and prior lows make it plausible SPX is above the 50wma. However, the combo firing on the same week the winning streak broke (−2.63% selloff) needs a review of whether the Friday close was the trigger date.
- **Fix needed**: Add a log line in `combo_detector.py` that prints SPX close vs 50wma value and % above when Combo F fires, so the trigger can be audited in the nightly log. Also ensure the detection uses the weekly close (not an intraday print) for the 3% reclaim check.
- **Files**: `src/macro_intelligence/engine/combo_detector.py`, `jobs/nightly_run.py`

---

#### ⚪ Priority 3 — Data Gaps (Cannot Web-Verify)

**T-06: WALCL, CNH, WTI (4wk change), VXTS, CFTC raw value, CPI surprise cannot be independently web-verified**
- **What**: These 6 variables pull from FRED/Yahoo/CFTC data with weekly update cycles and lag. The values look internally consistent but cannot be confirmed via public web search without API access.
- **Fix needed**: Add a weekly data validation script that fetches each variable from its primary source and compares against the stored DB value, logging any deviation > configured threshold. Alert to Slack/email if any variable is stale (> N days old) or deviates > X% from live feed.
- **Files**: `scripts/export_data_validation.py` (extend), `src/macro_intelligence/data/pull_all.py`

---

## DONE

_Completed tasks. Each entry includes status, date, outcome summary, and files changed._

---

### 2026-07-16

1. **F4 v2 steepening driver split (D3 spec) — context + analysis run** — SUCCESSFUL
   - Summary: Mapped report section codes (F4, B2, etc.) to PDF Parts A–I. Implemented and ran `scripts/f4_v2_steepening_driver_split.py` on the −50/+15 cell (n=17): classified episodes by DGS2/DGS10 4-week yield moves (BULL/BEAR/TWIST), tagged HY OAS widening and ICSA claims momentum, compared SPX 3m/6m to unconditional rolling-window benchmark (~29.4% SPX-down at 3m). **Verdict: PARK F4** — pooled hit rate 17.6% vs 29.4% baseline (negative short edge); hypothesis bucket “BULL steepening + HY widening” has **n=0**; 2022–23 episodes classify mostly BEAR/TWIST (normalization steepening), not recessionary BULL. No prod impact — research artifact only.
   - Files changed:
     - `scripts/f4_v2_steepening_driver_split.py` (new)
     - `macro_intelligence/analysis/regime_v2_experiments/F4_v2_steepening_driver_split.json` (new)

2. **D5 — Fed-cycle re-slicing on recalibrated D/E thresholds (macro_th_exp)** — SUCCESSFUL
   - Summary: Re-ran fed-cycle slices for recalibrated D (`VXTS≥1.18/CFTC≥95/VIX≤13`, 2-of-3, n=46) @ 1W/2W and E (`CAPE≥32/NFCI≤−0.15/CFTC≥85`, 3-of-3, n=10) @ 6M/9M/12M. **(a)** CUTTING_LATE vs HIKING_LATE spread **survives** at 1W (92.3% vs 41.7%, +50.6 pp) and 2W (69.2% vs 33.3%, +35.9 pp) — wider than legacy 3M spread (43.2% vs 18.3%, +24.9 pp). **(b)** E per-fed slices all **CANNOT USE** (n&lt;10); D QE n=9 **CANNOT USE**. Research only — no CONFIG/prod change.
   - Files changed:
     - `testing/macro_th_exp/run_d5_fed_cycle_reslice.py` (new)
     - `testing/macro_th_exp/D5_fed_cycle_reslice_2026-07-16.{csv,json,md}` (new)
     - `testing/macro_th_exp/D5_fed_cycle_per_fire_2026-07-16.csv` (new)

3. **D6 — Quick answers to open macro regime doubts (macro_th_exp)** — SUCCESSFUL
   - Summary: Captured Rohit sign-off from reply PDF thread: **(1)** A1 PIVOTING n=27 → merge into EASING for analytics only; **(2)** A5 keep 9-state liquidity storage + 4-state analytics collapse; **(3)** NEUTRAL folded into EASY for 4-way slice, kept in classifier storage; **(4)** Combo C n=4 → briefing shows "insufficient episodes" not hit rate; **(5)** HMM Dec 2026 target stands but excluded from short-gating (B/D/G) until walk-forward positive lift (prototype −1.2pp B, −1.9pp D). Docs only — no code/CONFIG change.
   - Files changed:
     - `testing/macro_th_exp/D6_open_doubts_resolution_2026-07-16.md` (new)
     - `testing/macro_th_exp/D6_open_doubts_resolution_2026-07-16.json` (new)

4. **D6 implementation — analytics collapse + Combo C min-n guard** — SUCCESSFUL
   - Summary: Wired `fed_cycle_v2_analytics()`, `collapse_liquidity_v2_analytics()`, `regime_value_for_analytics()` in `regime_v2_shadow.py`; `slice_by_regime()` auto-collapses fed/liquidity for analytics; `combo_metadata` returns "insufficient episodes" when n&lt;5 (Combo C explicit in CONFIG); briefing/API inherit via `format_hit_rate_display`. 26 tests pass.
   - Files changed:
     - `src/macro_intelligence/engine/regime_v2_shadow.py`
     - `src/macro_intelligence/analysis/regime_experiments/metrics.py`
     - `src/macro_intelligence/analysis/regime_experiments/fm_events.py`
     - `src/macro_intelligence/engine/combo_metadata.py`
     - `macro_intelligence/CONFIG.yaml`
     - `tests/test_regime_v2_experiments.py`, `tests/test_combo_metadata.py`

5. **D6 smoke tests + regime analytics re-slice** — SUCCESSFUL
   - Summary: `run_d6_smoke_tests.py` — **8/8 pass** (Combo C insufficient episodes, briefing rows, API `get_combo_detail`/`get_all_combos`, FM no PIVOTING bucket). `run_d6_regime_analytics_reslice.py` — PIVOTING n=27→EASING, 9→4 liquidity; 4 CSVs + report.
   - Files changed:
     - `testing/macro_th_exp/run_d6_smoke_tests.py`, `run_d6_regime_analytics_reslice.py` (new)
     - `testing/macro_th_exp/D6_smoke_tests_2026-07-17.{md,json}` (new)
     - `testing/macro_th_exp/D6_regime_analytics_2026-07-17.{md,json}` + 4 CSVs (new)

### 2026-07-17

1. **Promote Combo E BEST PRODUCTION SCORE thresholds + CFTC escalation alert** — SUCCESSFUL
   - Summary: Rohit sign-off on E gates CAPE≥32 / NFCI≤−0.15 / CFTC≥85 / **3-of-3** (n≥10 production score). Wired into `CONFIG.yaml`. Detector requires all three legs for CONFIRMED_3_OF_3; partial → WATCH. **ESCALATION_ALERT** when CFTC FM pctile rises ≥5 pts over 4 weeks while E is active. Briefing/dominant/API cheatsheet updated. Tests: `tests/test_combo_e_thresholds.py` (5 passed with dominant suite).
   - Files changed:
     - `macro_intelligence/CONFIG.yaml`
     - `src/macro_intelligence/engine/combo_detector.py`
     - `src/macro_intelligence/engine/dominant.py`
     - `src/macro_intelligence/jobs/nightly_run.py`
     - `src/macro_intelligence/output/briefing_renderer.py`
     - `src/macro_intelligence/claude/nightly_briefing.py`
     - `api/services/macro_service.py`
     - `tests/test_combo_e_thresholds.py` (new)

2. **Promote Combo D BEST PRODUCTION SCORE thresholds + true 2-of-3** — SUCCESSFUL
   - Summary: From `de_threshold_test_analysis.md` case #4: VXTS≥1.18 / CFTC≥95 / VIX≤13 / **2-of-3** (n=46, 56.5% bear @1W). Detector rewritten to true 2-of-3 (ACTIVE ≥2 legs, WATCH at 1); VIX gate inclusive ≤. Horizons: D primary 1W + secondary 2W; E secondary 6M kept. API cheatsheet + Claude prompt updated. E left as already-promoted production score. Tests: `tests/test_combo_d_thresholds.py` (6 passed).
   - Files changed:
     - `macro_intelligence/CONFIG.yaml`
     - `src/macro_intelligence/engine/combo_detector.py`
     - `src/macro_intelligence/claude/nightly_briefing.py`
     - `api/services/macro_service.py`
     - `tests/test_combo_d_thresholds.py` (new)

3. **Formal re-run D/E threshold sweeps against live CONFIG** — SUCCESSFUL
   - Summary: Re-ran `run_combo_de_followup.py` + `run_combo_de_study.py` on post-promotion CONFIG. Live D/E gates = analysis BEST PRODUCTION SCORE (#4); hit rates match (D n=46 / 56.52% @1W; E n=10 / 66.67% @6/9/12M). Followup ranks both as #1 production_score. Fixed D baseline tagging to use `min_of_three` (was hardcoded legs=3).
   - Files changed:
     - `testing/combo_de_thresholds/run_combo_de_study.py`
     - `testing/combo_de_thresholds/run_combo_de_followup.py`
     - `testing/combo_de_thresholds/de_threshold_config_recheck_2026-07-17.md` (new)
     - `testing/combo_de_thresholds/output_files/*` (regenerated)

### 2026-07-09

1. **Audit: adverse-regime / date-indexed combo classification API for Ahil** — SUCCESSFUL
   - Summary: No existing API exposes a date-indexed active-combo classification series or an `adverse_regime` boolean. Current macro endpoints only serve latest nightly snapshot (`/macro/combo/active`, `/macro/combos`, `/macro/regime`, `/macro/runic/nightly`) plus per-combo analog fire dates. Building blocks exist in `runic.db.combo_fires` + cheatsheet direction metadata in `CONFIG.yaml` / `_COMBO_STATIC`. Recommend new `GET /api/v1/macro/combos/classification-history` (or CSV handoff) for Ahil’s conditioning flag. Zero prod impact — analysis only.
   - Files changed: none (read-only audit)

2. **Export Test 3 adverse-regime CSV for Ahil (`combo_classification_history.csv`)** — SUCCESSFUL
   - Summary: Added `scripts/export_combo_classification_history.py`; generated daily forward-filled series (7,796 rows, 602 adverse days) and Friday-only variant under `testing/5_regime_uplift/`. Dominant = CONFIG PRIORITY; adverse per Test 3 rules (C/D/E, G ACTIVE-class, A FEARFUL).
   - Files changed:
     - `scripts/export_combo_classification_history.py` (new)
     - `testing/5_regime_uplift/combo_classification_history.csv` (new)
     - `testing/5_regime_uplift/combo_classification_history_fridays.csv` (new)
     - `testing/5_regime_uplift/README.md` (new)

### 2026-07-07

1. **v2 regime retag + Part H beta re-run (Item 15 follow-up)** — SUCCESSFUL
   - Summary: Retagged 13,160 generic combo_fires with macro_regime_log_v2 shadow labels; re-ran 298-combo funnel with real hostile HR. Funnel: beta pass 132→127 (−5 non-promo survivors failed); all 62 promotion candidates still pass. Eight-theme shortlist validated — hostile HR now real (e.g. CURVE+WALCL 84.1% on n=69 hostile). Added regime_v2_enrich.py, retag script, v2 analysis outputs.
   - Files changed:
     - `src/macro_intelligence/analysis/regime_v2_enrich.py` (new)
     - `src/macro_intelligence/analysis/combo_discovery_pipeline.py`
     - `scripts/retag_combo_fires_v2_regimes.py` (new)
     - `testing/291_combo_tests/run_v2_beta_rerun.py` (new)
     - `testing/291_combo_tests/ANALYSIS_REPORT_v2_beta.md` (new)
     - `testing/291_combo_tests/v2_beta_rerun_summary.json` (new)
     - `testing/291_combo_tests/v2_shortlist_beta.csv` (new)

### 2026-06-25

1. **298-combo promotion analysis + economic rationale shortlist (Item 15)** — SUCCESSFUL
   - Summary: Analyzed Part H `combo_discovery_20260606.json` (298 signatures → 62 promotion candidates at ≥80% 3m hit). All 62 are bullish; 52 unique fire-date clusters (heavy redundancy). Drafted economic rationale by theme; recommended 8-signature shortlist (5 Tier-1, 3 Tier-2) for Step 7 Claude review. Flagged overlap with named combos D/F/G and 2024/2026 overfit clusters. Outputs in `testing/291_combo_tests/`.
   - Files changed:
     - `testing/291_combo_tests/ANALYSIS_REPORT.md` (new)
     - `testing/291_combo_tests/shortlist_tiered.csv` (new)
     - `testing/291_combo_tests/promotion_candidates_62.csv` (new)
     - `testing/291_combo_tests/cluster_redundancy.csv` (new)
     - `testing/291_combo_tests/funnel_summary.json` (new)

---

### 2026-06-06

1. **Create report-creation Cursor skill + add PDF export rule** — SUCCESSFUL
   - Date: 2026-06-06
   - Summary: Created a project-level Cursor skill at `.cursor/skills/report-creation/SKILL.md` that enforces four non-negotiable rules: human-like tone with naturalistic imperfections, zero em dashes, every claim backed by visible data (tables preferred), and PDF export after Markdown completion. PDF export covers three methods (md-to-pdf, pandoc, Python weasyprint) with naming convention and verification step.
   - Files changed:
     - `/home/ubuntu/uiv2/git/MindWealth_UI/.cursor/skills/report-creation/SKILL.md` (created + updated)

2. **Setup PDF export environment and test end-to-end** — SUCCESSFUL
   - Date: 2026-06-06
   - Summary: Installed `weasyprint` and `markdown` for Python 3.12 system-wide. Created `export_pdf.py` utility script with styled CSS output (navy headings, coloured tables, alternating rows). Updated Rule 4 in SKILL.md to reference the script. End-to-end test: 13,003-byte PDF generated from sample report in 1.7 seconds.
   - Files changed:
     - `/home/ubuntu/uiv2/git/MindWealth_UI/.cursor/skills/report-creation/scripts/export_pdf.py` (created)
     - `/home/ubuntu/uiv2/git/MindWealth_UI/.cursor/skills/report-creation/SKILL.md` (Rule 4 updated)

4. **Update report-creation skill: no formal sections, add "My doubts and questions"** — SUCCESSFUL
   - Date: 2026-06-06
   - Summary: Added Rule 4 (no corporate section names like Overview, Executive Summary, Sign-off etc.) and Rule 5 (renamed from old Rule 4, PDF export). Updated report template to use descriptive headings and added mandatory "My doubts and questions" section at the end. Updated checklist with 3 new items. Added before/after examples for both new rules.
   - Files changed:
     - `/home/ubuntu/uiv2/git/MindWealth_UI/.cursor/skills/report-creation/SKILL.md`

5. **Generate SSI Validation Experiment Report (Markdown + PDF)** — SUCCESSFUL
   - Date: 2026-06-06
   - Summary: Created full SSI validation report covering 11 key findings across all 16 tests (14 completed, 2 pending). All four skill rules applied: human tone with naturalistic imperfections, zero em dashes, every finding backed by a data table, PDF exported. 61,398-byte PDF generated in 3.5 seconds.
   - Files changed:
     - `/home/ubuntu/uiv2/git/MindWealth_UI/docs/ssi_validation/SSI_Validation_Report_2026-06-06.md` (created)
     - `/home/ubuntu/uiv2/git/MindWealth_UI/docs/ssi_validation/SSI_Validation_Report_2026-06-06.pdf` (created)

2. **Create MindWealth_UI repository operating rules and todo log** — SUCCESSFUL
   - Date: 2026-06-06
   - Summary: Created always-applied Cursor rule defining repository scope, mandatory task logging, and completion protocol. Created project todo log with `mindwealth_ui_repo` naming.
   - Files changed:
     - `/home/ubuntu/uiv2/git/MindWealth_UI/.cursor/rules/mindwealth-ui-repository-rules.mdc`
     - `/home/ubuntu/uiv2/git/MindWealth_UI/.cursor/mindwealth_ui_repo_todos.md`

2. **Analyze macro regime v2 mail PDF and create summary** — SUCCESSFUL
   - Date: 2026-06-06
   - Summary: Read Rohit's consolidated macro regime system v2 email (8 pages). Created structured summary in docs/ssi_validation. Renamed source PDF from `Threshold experiments mail.pdf` to `Macro_Regime_System_v2_Consolidated_Plan_Mail.pdf`.
   - Files changed:
     - `/home/ubuntu/uiv2/git/MindWealth_UI/docs/ssi_validation/MACRO_REGIME_V2_CONSOLIDATED_PLAN_SUMMARY.md` (created)
     - `/home/ubuntu/uiv2/git/MindWealth_UI/macro_intelligence_docs/Macro_Regime_System_v2_Consolidated_Plan_Mail.pdf` (renamed)

3. **Runic PDF Quality & Narrative Upgrade — raise narrative_max_tokens to 1200, add fetch_macro_headlines, rewrite 5-paragraph Claude prompt, full visual PDF/HTML redesign** — SUCCESSFUL
   - Date: 2026-06-06
   - Summary: (1) Raised `narrative_max_tokens` 500→1200 in CONFIG.yaml. (2) Added `fetch_macro_headlines()` to `geo_news.py` for broad macro Tavily context. (3) Rewrote `nightly_briefing.py` with detailed 5-paragraph SYSTEM prompt (dominant signal, all combos, 3 reasons, analogs, posture). (4) Rebuilt `briefing_renderer.py` with dark navy (#0A1628) header band, green ACTIVE / amber WATCH combo rows, 3-column regime grid, EXTREME/HIGH tier-coloured variable dashboard, navy recommendation box, centred footer — for both PDF (reportlab Platypus) and HTML. (5) Updated tests with colour-palette smoke check. (6) Verified nightly run: 7.6 KB PDF generated with full 5-paragraph narrative.
   - Files changed:
     - `macro_intelligence/CONFIG.yaml`
     - `src/macro_intelligence/claude/geo_news.py`
     - `src/macro_intelligence/claude/nightly_briefing.py`
     - `src/macro_intelligence/output/briefing_renderer.py`
     - `tests/test_briefing_renderer.py`

4. **Remove "Generated HH:MM ET" timestamp from PDF/HTML report header** — SUCCESSFUL
   - Date: 2026-06-06
   - Summary: Removed `generated_et` field from `build_briefing_sections()` and stripped it from both the HTML subtitle bar and the PDF header Paragraph. All 4 tests pass.
   - Files changed:
     - `src/macro_intelligence/output/briefing_renderer.py`

5. **Update repository rules, rename todo to job status file, add TODO/DONE sections, create job status details file** — SUCCESSFUL
   - Date: 2026-06-06
   - Summary: Updated `mindwealth-ui-repository-rules.mdc` with new file paths, TODO/DONE workflow instructions, and reference to details file. Created `mindwealth_ui_job_status.md` with two-section structure. Created `mindwealth_ui_repo_job_status_details.md` for implementation detail tracking. Migrated content from old todo file.
   - Files changed:
     - `/home/ubuntu/uiv2/git/MindWealth_UI/.cursor/rules/mindwealth-ui-repository-rules.mdc`
     - `/home/ubuntu/uiv2/git/MindWealth_UI/docs/mindwealth_ui_job_status.md` (created)
     - `/home/ubuntu/uiv2/git/MindWealth_UI/docs/mindwealth_ui_repo_job_status_details.md` (created)

6. **Implement Macro Regime v2 end-to-end experiment program (Parts A–I + FM track)** — SUCCESSFUL
   - Date: 2026-06-06
   - Summary: Built and ran full experiment suite per Rohit's consolidated v2 plan. Shadow v2 regime backfill (~1,901 Fridays), emission vectors (8,805 rows), FM deep dive (X-FM-1..5 with regime slices), Parts A–G + E cancel MC + D HMM prototype, Part H combo discovery re-run (298 sigs → 132 survivors → 62 promotion candidates). Fixed nightly `generic_combo_watch` prefilter (full var signature + `generic_hit_rate`). Master report and JSON artifacts archived. Production regime labels unchanged pending Rohit sign-off.
   - Run command: `.venv/bin/python scripts/run_regime_v2_experiment_suite.py`
   - Key results: FM extreme short 60% SPX up at 3m (n=35); FM extreme long 82% SPX down at 3m; Combo B 79.8% SPX higher at 3m (n=89); TWY_ROC Apr 2025 −0.55pp DOVISH (pass).
   - Files changed:
     - `scripts/run_regime_v2_experiment_suite.py` (created)
     - `src/macro_intelligence/analysis/regime_experiments/` (created)
     - `src/macro_intelligence/engine/regime_v2_shadow.py` (created)
     - `src/macro_intelligence/engine/combo_cancel_probability.py` (created)
     - `src/macro_intelligence/engine/hit_rates.py`, `prefilter.py`
     - `src/macro_intelligence/jobs/nightly_run.py`
     - `src/macro_intelligence/db/migrate.py`
     - `tests/test_regime_v2_experiments.py` (created)
     - `docs/ssi_validation/MACRO_REGIME_V2_EXPERIMENT_REPORT.md` (created)
     - `macro_intelligence/analysis/regime_v2_experiments/*.json`

7. **Fix Combo F week counter — episode start vs last fire** — SUCCESSFUL
   - Date: 2026-06-06
   - Summary: `_combo_f_weeks()` was using `ORDER BY date DESC LIMIT 1` (last fire row) as the start date, so the 26-week counter perpetually showed Week 1–2 because the nightly job writes a fresh row every Friday. Fixed to anchor on the first F fire strictly after the last week SPX closed below the 50-week WMA. For the current episode (last below = 2026-03-27, episode start = 2026-04-03), the briefing now correctly shows Week 10 (MEDIUM bucket) instead of Week 1 (SHORT).
   - Files changed:
     - `src/macro_intelligence/engine/combo_detector.py` (`_combo_f_weeks` function)

8. **Full combo A–G fire audit against MACRO_INTELLIGENCE_MASTER.md spec** — SUCCESSFUL
   - Date: 2026-06-06
   - Summary: Audited all 7 named combos against MACRO_INTELLIGENCE_MASTER.md. All statuses for Jun 6 are correct (A INACTIVE, B WATCH 1/3, C INACTIVE, D INACTIVE, E CONFIRMED 2/3 CAPE+NFCI, F ACTIVE Week 10 MEDIUM, G INACTIVE). Three spec-vs-code discrepancies found and fixed: (1) Combo F entry trigger used weekly_return>=3% instead of spec's "close 3% above WMA level" — fixed to level test; (2) Combo E NFCI boundary `< -0.3` changed to `<= -0.3` per spec's `≤ -0.3`; (3) Combo G VIX boundary `< 20` changed to `<= 20` per spec's `≤ 20`. Priority table (C=100,B=90,F=80,E=70,D=60,G=50,A=40), dominant signal (Combo F), CONTESTED-to-WATCH routing, and cancel logic all verified correct. One deferred finding: `_combo_c_weeks()` has the same week-reset pattern as the pre-fix `_combo_f_weeks()` — benign now (C inactive) but needs fixing before next C episode.
   - Files changed:
     - `src/macro_intelligence/engine/combo_detector.py` (3 spec fixes)

9. **Data sources audit + comprehensive sources reference added to MACRO_INTELLIGENCE_MASTER.md** — SUCCESSFUL
   - Date: 2026-06-07
   - Summary: Audited all 12 variable data sources by reading every puller file. Found two bugs in the master doc: (1) CPI consensus primary source was labelled "Investing.com" but the code uses Trading Economics as primary — Investing.com is only a fallback when INVESTING_HTTP_PROXY env var is set; (2) WTI variable description omitted its FRED DCOILWTICO fallback. Both fixed inline. Also added a new "## 2b. Data Sources Reference" section covering all 12 variables with exact API endpoint URLs, FRED series IDs, Yahoo Finance tickers, exact page/table locations, fallback sources, history start dates, publication frequencies, and units. The section becomes the single authoritative reference for operators and future developers.
   - Files changed:
     - `docs/MACRO_INTELLIGENCE_MASTER.md` (new section 2b + two inline fixes)

12. **Add data gap tables from data_gap_report to MACRO_INTELLIGENCE_MASTER.md (section 2c)** — SUCCESSFUL
   - Date: 2026-06-07
   - Summary: Added new section "## 2c. Data Gap Status — Current Implementation" to `MACRO_INTELLIGENCE_MASTER.md` immediately after the data sources reference (2b). Section includes two sub-tables (SSI variables, Runic DB variables) and an overall summary table matching the audited gap report. Updated table of contents to link 2b and 2c as sub-entries under section 2.
   - Files changed:
     - `docs/MACRO_INTELLIGENCE_MASTER.md` (new section 2c + TOC update)

11. **Permanent auto-refresh of CFTC TFF ZIP — eliminates manual intervention (T-02)** — SUCCESSFUL
   - Date: 2026-06-07
   - Summary: Added `refresh_cftc_zip_if_stale(year)` to `cftc_pull.py`. The function fires a download from `https://www.cftc.gov/files/dea/history/fut_fin_txt_{year}.zip` when any of three independent triggers fire: (1) **Friday trigger** — today is Friday AND local file is > 12h old (post-release); (2) **Staleness trigger** — local file is older than 8 days (missed a weekly release); (3) **Size trigger** — CFTC remote Content-Length is strictly larger than the local file (catches mid-week re-publications and the first run after any gap). After a successful download, `_TFF_RAW_CACHE` is cleared forcing a fresh parse. Wired into `load_all_series()` in `pull_all.py` immediately before `fetch_cftc_fast_money_net()` — so every nightly run automatically stays fresh. Tested: stale-file trigger downloads and confirms correct size; fresh-file test returns False correctly; `load_all_series()` returns Jun-2 FM net −503,509.
   - Files changed:
     - `src/macro_intelligence/data/cftc_pull.py` (`refresh_cftc_zip_if_stale` added)
     - `src/macro_intelligence/data/pull_all.py` (auto-refresh call before CFTC fetch)

10. **CFTC data staleness investigation and fix — stale May-26 data updated to Jun-2 report** — SUCCESSFUL
   - Date: 2026-06-07
   - Summary: Verified CFTC FM net value against CFTC.gov. Found local cache (fut_fin_txt_2026.zip, downloaded Jun 3) was missing the June 5 CFTC release (per official 2026 CFTC release schedule, the June 2 data was published on **Friday June 5** — note: June 6 is a Saturday, CFTC never publishes on Saturday). System was using May 26 data (FM net −459,415, percentile 5.1%). Correct June 2 values: FM Long 160,224, FM Short 663,733, FM Net **−503,509**, percentile **1.28–1.91%** (rolling 3yr window, rounds to 2% in briefing). Also found and deleted 4 erroneous future-dated CFTC DB rows (2026-06-12 to 2026-07-03) with stale May-26 values written by the macro v2 backfill experiment. No combo status changes (all combos still WATCH/ACTIVE/CONFIRMED as before). Briefing HTML and PDF regenerated with correct value.
   - Files changed:
     - `macro_intelligence/data_cache/cftc/fut_fin_txt_2026.zip` (refreshed from CFTC.gov)
     - `macro_intelligence/data/runic.db` (cftc_positioning table — Jun 6 updated, 4 future rows deleted)
     - `macro_intelligence/output/runic_briefing_2026-06-06.html` / `.pdf` (regenerated)

11. **SSI Data Gap Investigation + NAAIM Backfill + build_ssi_history Code Fix** — SUCCESSFUL
   - Date: 2026-06-06
   - Summary: Investigated why `build_ssi_history` returned only 83 days. Found two root causes: (1) NAAIM cache had only 11 rows (2026-03-25 to 2026-06-03) because the scraper had never fetched historical data; (2) `build_ssi_history` required ALL series (including auxiliary breadth metrics) to have data, not just the 4 weighted components. Fix 1: Downloaded NAAIM "Data since Inception" Excel from naaim.org, extended cache to 1,039 rows (2006-07-05 to 2026-06-03). Fix 2: Changed NaN gate in `ssi_score.py` to only check weighted components. SSI history now spans 2019-06-07 to 2026-06-06 (2,565 rows, ~7 years). All 7 previously blocked tests (1, 2, 9, 10, 11, 12, 17) now classified as DATA_FIXED.
   - Files changed:
     - `macro_intelligence/data/ssi/naaim_exposure.csv` (extended 11 → 1,039 rows)
     - `src/sentiment_superindex/engine/ssi_score.py` (NaN gate fix)
     - `docs/ssi_validation/SSI_OPEN_QUESTIONS_SUMMARY.md` (new DATA GAP STATUS section added)

10. **SSI Validation full variable backfill + 5 code bug fixes + corrected re-runs** — SUCCESSFUL
   - Date: 2026-06-06
   - Summary: Comprehensive backfill and bug-fix pass for all SSI validation components. (1) Verified all data component ranges; extended breadth download from 2y to 5y. (2) Fixed `forward_return_pct` silent bug: was returning last available SPX price when end_date exceeded data — now returns None. (3) Fixed horizons key mismatch in `cftc_grid.py`, `dbmf_beta_study.py`, `hyg_lqd_study.py` — all showed n=0 returns because custom horizons were passed to `returns_at_horizons` but not to `summarize_returns`. (4) Rewrote `dbmf_beta_study.py` with OLS regression (4-horizon), 3yr rolling percentile, and Granger causality. (5) Installed statsmodels + scipy. (6) Re-ran full validation suite (16 min runtime). Key corrected findings: short gate weak (26% SPX-down at SSI≥0.85); CFTC squeeze is a long signal (68% 4w win); HYG/LQD −3% = buy signal (77% 1w win); DBMF 4w OLS significant (R²=0.004, p=0.007). (7) CNN F&G 2011-2018 gap cannot be filled (no free source; Alternative.me is crypto F&G only). (8) Added Part III to SSI_OPEN_QUESTIONS_SUMMARY.md with all corrected results.
   - Files changed:
     - `src/macro_intelligence/engine/forward_returns.py`
     - `src/sentiment_superindex/analysis/cftc_grid.py`
     - `src/sentiment_superindex/analysis/dbmf_beta_study.py`
     - `src/sentiment_superindex/analysis/hyg_lqd_study.py`
     - `src/sentiment_superindex/data/sp500_breadth.py`
     - `docs/ssi_validation/SSI_OPEN_QUESTIONS_SUMMARY.md`

11. **Data gap report: current history vs spec requirements** — SUCCESSFUL
   - Date: 2026-06-06
   - Summary: Created data gap report using the report-creation skill. Compared all SSI and Runic DB variables against spec-required date ranges. Three categories: (1) Fixable now: breadth indicators (run pull_all.py with period=5y); (2) Blocked by paid data: HY OAS full history (ICE licensing) and CNN stock F&G 2011-2018; (3) Structurally impossible: CFTC FM pre-2010, DBMF pre-2019, HYG pre-2007. Flagged CNN cache mislabelling risk.
   - Files: docs/ssi_validation/data_gap_report_2026-06-06.md, docs/ssi_validation/data_gap_report_2026-06-06.pdf

13. **Extend breadth indicators to 2015 using start-date download** — SUCCESSFUL
   - Date: 2026-06-07
   - Summary: Added `start` parameter to `_download_closes` and `load_breadth_frame` in `sp500_breadth.py`. Re-ran with `start="2014-01-01"` (gives 200-day MA warmup so pct_above_200dma valid from Jan 2015). All three CSVs extended to spec-required 2015+ start in 45 seconds. pct_above_200dma: 2015-01-02 (2,873 rows); nh_nl_ratio: 2015-01-05 (2,096 rows); mcclellan: 2014-01-02 (3,126 rows). Tests 12 and 13 now fully unblocked. Updated data_gap_report_2026-06-06.md and PDF.
   - Files changed: `src/sentiment_superindex/data/sp500_breadth.py`, `macro_intelligence/data/ssi/pct_above_200dma.csv`, `macro_intelligence/data/ssi/nh_nl_ratio.csv`, `macro_intelligence/data/ssi/mcclellan_oscillator.csv`, `docs/ssi_validation/data_gap_report_2026-06-06.md/.pdf`

14. **Data gap report — fixes applied and next actions logged** — 2026-06-07

   **Fixes Applied:**

   | What was fixed | Before | After |
   |----------------|--------|-------|
   | `pct_above_200dma` | 2025-04-17 (~14 mo) | 2015-01-02 → 2026-06-05 (11 yr) ✅ |
   | `nh_nl_ratio` | 2025-02-13 (~16 mo) | 2015-01-05 → 2026-06-05 (11 yr) ✅ |
   | `mcclellan` | 2025-02-13 (~16 mo) | 2014-01-02 → 2026-06-05 (12 yr) ✅ |
   | HY OAS history | 163 real rows (2023-2026) | 1997-2026 via BAA10Y proxy (7,364 rows total) |
   | Breadth NaN bug | Live path silently returned empty | Fixed per-row valid-stock counters in `compute_daily_breadth_stats` |
   | CNN F&G label | Undocumented crypto proxy | Module docstring + inline comments corrected |

   **Next Actions (open items):**

   | Priority | Variable | Action |
   |----------|----------|--------|
   | High | CNN F&G | Divyanshu to export Bloomberg CNN F&G history (2011–2018) as CSV → `macro_intelligence/data/ssi/cnn_fear_greed.csv` |
   | High | HY OAS | Obtain ICE BofA BAMLH0A0HYM2 full history from Bloomberg or ICE Direct; replace proxy rows (`signal_tier='PROXY'`) in `runic.db` |
   | Low | CPI Surprise | Fetch Cleveland Fed inflation forecast as historical consensus baseline; compute surprise = actual − forecast and backfill to 2010+ |
   | None | CFTC FM/RM pre-2010 | Not actionable — data does not exist |

   - Files updated: `docs/ssi_validation/data_gap_report_2026-06-06.md/.pdf`

13. **SSI experiment audit vs DivyanshuTestList PDF** — SUCCESSFUL
   - Date: 2026-06-07
   - Summary: Cross-referenced all 17 numbered tests in SSI_OPEN_QUESTIONS_SUMMARY.md against the original SSI_OpenQuestions_DivyanshuTestList (1).pdf. Produced interactive canvas audit and appended full audit report as Section 11 to testing/ssi_th_exp/SSI_OPEN_QUESTIONS_SUMMARY.md. Findings: 12/17 fully credible (Part III data only), 4 partially credible, 3 not credible (Test 6 wrong data source — crypto proxy not CNN stock F&G; Test 12 zero combo events; Test 15 not run). 4 PDF sub-experiments never run as tests (COT FM sweep, VIX/FM distribution, Layer 2 z-score 0→2.0 sweep, HYG/LQD Granger causality). Note: breadth data extended to 2015 on 2026-06-07 means Tests 12 and 13 can now be rerun with meaningful data.
   - Files changed: testing/ssi_th_exp/SSI_OPEN_QUESTIONS_SUMMARY.md (Section 11 appended), canvas ssi-threshold-experiment-audit.canvas.tsx created

23. **Macro report update understanding doc (create-understanding-doc skill)** — SUCCESSFUL
   - Date: 2026-06-09
   - Summary: Created `understanding_and_research/Macro_Report_Update_Understanding.md`: plain-English guide for Divyanshu 11-point review with glossary, per-point status/Q&A tables, MRU checklist, consolidated doubts for Rohit Sir.
   - Files changed:
     - `testing/macro_report_updates/understanding_and_research/Macro_Report_Update_Understanding.md` (created)
     - `testing/macro_report_updates/MACRO_REPORT_UPDATE_STATUS.md` (artifact index)

22. **Macro report update pipeline report (report-creation skill)** — SUCCESSFUL
   - Date: 2026-06-09
   - Summary: Created `MACRO_REPORT_UPDATE_PIPELINE_REPORT_2026-06-09.md/.pdf`: Divyanshu 11-point vs plan/status match, pipeline changes, explicit Q&A (G→B, HY audit, horizons, tone), challenges, open MRU items. PDF 56 KB.
   - Files changed:
     - `testing/macro_report_updates/MACRO_REPORT_UPDATE_PIPELINE_REPORT_2026-06-09.md`
     - `testing/macro_report_updates/MACRO_REPORT_UPDATE_PIPELINE_REPORT_2026-06-09.pdf`
     - `testing/macro_report_updates/MACRO_REPORT_UPDATE_STATUS.md` (file index)

21. **Macro TH experiment pipeline report (report-creation skill)** — SUCCESSFUL
   - Date: 2026-06-09
   - Summary: Created `MACRO_TH_EXP_PIPELINE_REPORT_2026-06-09.md/.pdf` in `testing/macro_th_exp/`: plan vs status match, pipeline updates (regime v2 shadow + production nightly fixes), Rohit FM/regime Q&A, plan §6 closure, challenges. PDF exported (52 KB).
   - Files changed:
     - `testing/macro_th_exp/MACRO_TH_EXP_PIPELINE_REPORT_2026-06-09.md`
     - `testing/macro_th_exp/MACRO_TH_EXP_PIPELINE_REPORT_2026-06-09.pdf`
     - `testing/macro_th_exp/MACRO_TH_EXP_STATUS_ANALYSIS.md` (file index link)

20. **Fix PDF combo status table text overlap** — SUCCESSFUL
   - Date: 2026-06-09
   - Summary: Fixed ReportLab combo table in `briefing_renderer.py`: Paragraph wrapping, full-width column layout, duration line breaks, nowrap for status/hit-rate columns. Regenerated `runic_briefing_2026-06-09.pdf`.
   - Files changed:
     - `src/macro_intelligence/output/briefing_renderer.py`
     - `tests/test_briefing_renderer.py`
     - `testing/macro_report_updates/runic_briefing_2026-06-09.pdf`

19. **Generate post-update nightly briefing in macro_report_updates** — SUCCESSFUL
   - Date: 2026-06-09
   - Summary: Generated nightly report `as_of=2026-07-03` (latest full DB date) with updated engine; stored HTML/PDF/JSON in `testing/macro_report_updates/`. Live FRED pull skipped (504 timeout); used cached `daily_readings`. Claude narrative included.
   - Files changed:
     - `testing/macro_report_updates/runic_briefing_2026-07-03.html/.pdf`
     - `testing/macro_report_updates/runic_output_2026-07-03.json`
     - `testing/macro_report_updates/nightly_run_summary_2026-07-03.json`

18. **Create macro report update current status file** — SUCCESSFUL
   - Date: 2026-06-07
   - Summary: Added `MACRO_REPORT_UPDATE_STATUS.md` in `testing/macro_report_updates/` with DONE (R-01..R-11 + MRU-01..03) and TODO (MRU-04..06 + open items) at-a-glance snapshot.
   - Files changed:
     - `testing/macro_report_updates/MACRO_REPORT_UPDATE_STATUS.md` (created)

17. **Execute MRU-01/02/03 — G→B cascade, HY audit, Combo C CANCELLED smoke test** — SUCCESSFUL
   - Date: 2026-06-07
   - Summary: Ran `scripts/analyze_combo_g_b_cascade.py` over 1,018 Fridays (2007–2026): 3 B ACTIVE episodes, 0 G fires, 0/3 G→B within 6 weeks; HY audit recommends **keep_400bps** but Oct 2022 fails new 80th pctile dual gate (427 bps, 35th pctile). Production nightly smoke test on `as_of=2026-07-03` after 4-Friday cancel (Jun 12–Jul 3): Combo C `CANCELLED`, `cancel_date=2026-07-03`, brown row in briefing HTML/PDF. Part 2 added to analysis doc.
   - Files changed:
     - `scripts/analyze_combo_g_b_cascade.py` (created)
     - `testing/macro_report_updates/mru01_mru02_results.json`, `mru01_mru02_results.md` (created)
     - `testing/macro_report_updates/MACRO_REPORT_UPDATE_ANALYSIS.md` (Part 2)
     - `testing/macro_report_updates/MACRO_REPORT_UPDATE_TODO.md` (MRU-01..03 → DONE)
     - `macro_intelligence/output/runic_briefing_2026-07-03.html/.pdf`
     - `macro_intelligence/data/runic.db` (`combo_c_cancel.cancel_date`)

16. **Log macro report follow-up todos (MRU-01..03)** — SUCCESSFUL
   - Date: 2026-06-07
   - Summary: Added three deferred follow-ups to main job tracker and `testing/macro_report_updates/MACRO_REPORT_UPDATE_TODO.md`: G→B cascade timing script, HY threshold audit at historical B fires, production nightly smoke test for Combo C CANCELLED row. Cross-linked from `MACRO_REPORT_UPDATE_ANALYSIS.md`.
   - Files changed:
     - `docs/mindwealth_ui_job_status.md` (TODO section MRU-01..03)
     - `testing/macro_report_updates/MACRO_REPORT_UPDATE_TODO.md` (created)
     - `testing/macro_report_updates/MACRO_REPORT_UPDATE_ANALYSIS.md` (open items cross-link)

15. **Macro report pipeline + engine update (11-point Divyanshu review)** — SUCCESSFUL
   - Date: 2026-06-07
   - Summary: Analyzed all points in `Report update todo details.md`; created formatted requirements/plan docs; implemented engine and briefing fixes: bearish per-combo hit rates with validated horizons (E=12m bearish, G=N/A), Combo C CANCELLED status + cancel_date + governing CPI cancel logic + HOT surprise fire, Combo B HY/VIX dual percentile gates, WALCL full-history MoM percentile, EASY_MONEY rename, F/C episode start dates, Claude tone guardrails, CFTC source notes. 15 unit tests passed. Analysis doc in `testing/macro_report_updates/`. G→B cascade and HY historical B audit deferred to follow-up script.
   - Files changed:
     - `testing/macro_report_updates/MACRO_REPORT_UPDATE_REQUIREMENTS.md` (created)
     - `testing/macro_report_updates/MACRO_REPORT_UPDATE_PLAN.md` (created)
     - `testing/macro_report_updates/MACRO_REPORT_UPDATE_ANALYSIS.md` (created)
     - `src/macro_intelligence/engine/combo_metadata.py` (created)
     - `src/macro_intelligence/engine/combo_detector.py`, `combo_c_cancel.py`, `dominant.py`
     - `src/macro_intelligence/jobs/nightly_run.py`
     - `src/macro_intelligence/output/briefing_renderer.py`, `json_writer.py`
     - `src/macro_intelligence/claude/nightly_briefing.py`
     - `macro_intelligence/CONFIG.yaml`
     - `docs/MACRO_INTELLIGENCE_MASTER.md`
     - `tests/test_combo_metadata.py`, `test_combo_c_fire.py`, `test_combo_b_hy_dual.py`, `test_walcl_percentile.py` (created/updated)

12. **Fix all self-fixable data gaps identified in gap report** — SUCCESSFUL
   - Date: 2026-06-06
   - Summary: Applied all three fixes identified as "Fixable now": (1) CNN F&G mislabelling corrected — module docstring and inline comment now clearly state Alternative.me is the CRYPTO F&G index (not CNN stock market F&G), and covers 2018+ not 2011+. (2) HY OAS backfill: 7,201 proxy rows inserted into runic.db using FRED BAA10Y (Moody's Baa-Treasury spread) calibrated against real HY OAS in the 2023-2026 overlap (R²=0.40, n=153). Real rows' pctile_rank_3yr recomputed with full history. Date range extended from 2023-2026 to 1997-2026. (3) Breadth indicators: Fixed critical NaN-accumulation bug in compute_daily_breadth_stats (initial np.full(n,nan) + anything = nan). Now uses per-row valid-stock counters. Extended pct_above_200dma to 2022-03-21→2026-06-05 (4yr), nh_nl_ratio to 2022-06-03→2026-06-05 (4yr), mcclellan to 2021-06-07→2026-06-05 (5yr). Previous coverage was only ~14 months for all three.
   - Files changed:
     - `src/sentiment_superindex/data/cnn_fear_greed.py`
     - `src/sentiment_superindex/data/sp500_breadth.py`
     - `macro_intelligence/data/ssi/pct_above_200dma.csv`
     - `macro_intelligence/data/ssi/nh_nl_ratio.csv`
     - `macro_intelligence/data/ssi/mcclellan_oscillator.csv`
     - `macro_intelligence/data/runic.db` (7,201 HY proxy rows + pctile recompute)

### 2026-06-07

1. **Macro threshold & regime experiment status analysis (macro_th_exp)** — SUCCESSFUL
   - Date: 2026-06-07
   - Summary: Reviewed all regime v2 experiment artifacts (2026-06-06 run), consolidated plan PDF, and Rohit's FM/regime follow-up in `additional_details.md`. Created status analysis answering FM extreme short/long/moderate claims with regime slices; documented Parts A–H completion vs production blockers; added forward plan with P0–P2 sequencing and follow-up experiments R-1–R-4.
   - Files changed:
     - `testing/macro_th_exp/MACRO_TH_EXP_STATUS_ANALYSIS.md` (created)
     - `testing/macro_th_exp/MACRO_TH_EXP_PLAN.md` (created)

2. **SSI open-questions deep-dive fixes (Phase 1 + missing Part 1 experiments)** — SUCCESSFUL
   - Date: 2026-06-07
   - Summary: Rewrote §4.1–§4.5, §4.7, §4.12, §5, and §9.1 in `SSI_OPEN_QUESTIONS_SUMMARY.md` using Part III (20260606) JSON artifacts. Added and ran Tests 18 (COT FM 15th–45th sweep), 19 (VIX≥35 FM distribution), 20 (Layer 2 z-score 0–2.0 sweep). Updated validation suite, CFTC heatmap report, TP/SL top-10 report.
   - Files changed:
     - `testing/ssi_th_exp/SSI_OPEN_QUESTIONS_SUMMARY.md`
     - `src/sentiment_superindex/analysis/cot_fm_long_gate.py` (new)
     - `src/sentiment_superindex/analysis/vix_fm_washout.py` (new)
     - `src/sentiment_superindex/analysis/layer2_zscore_sweep.py` (new)
     - `src/sentiment_superindex/analysis/cftc_grid.py`, `tp_sl_sweep.py`, `ssi_history.py`
     - `scripts/run_ssi_validation_suite.py`
     - `macro_intelligence/analysis/ssi_validation/18_cot_fm_long_gate_20260607.json`
     - `macro_intelligence/analysis/ssi_validation/19_vix_fm_washout_20260607.json`
     - `macro_intelligence/analysis/ssi_validation/20_layer2_zscore_sweep_20260607.json`

### 2026-06-09

1. **Macro Regime System v2 consolidated plan — plain-English understanding doc** — SUCCESSFUL
   - Date: 2026-06-09
   - Summary: Read Rohit's consolidated plan PDF (`Macro_Regime_System_v2_Consolidated_Plan_Mail.pdf`) and created a detailed plain-English understanding guide in `testing/macro_th_exp/understanding_and_research/`. Document explains all nine parts (A–I), deliverables A–H, build sequencing, technical terms as they appear, and suggested follow-up questions for Rohit.
   - Files changed:
     - `testing/macro_th_exp/understanding_and_research/Macro_Regime_System_v2_Understanding.md` (created)

2. **Expand understanding doc with experiment status per Part A–H** — SUCCESSFUL
   - Date: 2026-06-09
   - Summary: Enriched `Macro_Regime_System_v2_Understanding.md` using `MACRO_TH_EXP_STATUS_ANALYSIS.md` and `experiment_manifest.json`. Each subsection A1–H9 now includes what was done (2026-06-06 shadow run), results, and Q&A closure (answered vs open + why). Added FM/regime isolation (Section 14), master Q&A table, production blockers, and artifact index.
   - Files changed:
     - `testing/macro_th_exp/understanding_and_research/Macro_Regime_System_v2_Understanding.md` (updated)

3. **Understanding doc Q&A tables — separate Answer/Gap columns with numeric detail** — SUCCESSFUL
   - Date: 2026-06-09
   - Summary: Refactored all experiment Q&A tables in understanding doc to use separate Answer and Gap columns (replacing combined Answer/gap). Expanded every answer with backtest numbers (n, hit rates, averages, deltas) from experiment_manifest.json and status analysis.
   - Files changed:
     - `testing/macro_th_exp/understanding_and_research/Macro_Regime_System_v2_Understanding.md` (updated)

4. **Reframe understanding doc gaps as doubts to ask Rohit Sir** — SUCCESSFUL
   - Date: 2026-06-09
   - Summary: Renamed Gap column to "Doubts to ask Rohit Sir" across all Q&A tables; replaced sign-off/blocker framing with doubt questions; consolidated Section 16 as master doubts list (18 items); removed duplicate Section 19; added reading guide in Section 1.
   - Files changed:
     - `testing/macro_th_exp/understanding_and_research/Macro_Regime_System_v2_Understanding.md` (updated)

5. **Create create-understanding-doc Cursor skill** — SUCCESSFUL
   - Date: 2026-06-09
   - Summary: Created project-level Cursor skill at `.cursor/skills/create-understanding-doc/` that codifies the plain-English understanding doc workflow: spec vs status comparison per section, old-vs-new tables, Q&A tables with separate Answer and Doubts to ask Rohit Sir columns (numeric evidence required), consolidated doubts master list, and document template.
   - Files changed:
     - `.cursor/skills/create-understanding-doc/SKILL.md` (created)
     - `.cursor/skills/create-understanding-doc/TEMPLATE.md` (created)

6. **SSI Open Questions PDF — plain-English understanding doc** — SUCCESSFUL
   - Date: 2026-06-09
   - Summary: Created `SSI_OpenQuestions_Understanding.md` from Divyanshu test-list PDF and `SSI_OPEN_QUESTIONS_SUMMARY.md` (Part III validation + Tests 18–20). Mirrors PDF Parts 1–10 and numbered tests 1–20 with experiment status, old-vs-new tables, Q&A with numeric answers, deliverables checklist, and 18 consolidated doubts for Rohit Sir.
   - Files changed:
     - `testing/ssi_th_exp/understanding_and_research/SSI_OpenQuestions_Understanding.md` (created)

7. **Macro regime and threshold experiments report (report-creation skill)** — SUCCESSFUL
   - Date: 2026-06-09
   - Summary: Created full experiment report from `Macro_Regime_System_v2_Understanding.md` Q&A tables (Parts A–I, FM/regime isolation, SSI threshold track, master Q&A closure). Applied report-creation skill rules (first person, data tables, doubts section, zero em dashes). Exported PDF (68,323 bytes).
   - Files changed:
     - `testing/macro_th_exp/Macro_Regime_Threshold_Experiments_Report_2026-06-09.md` (created)
     - `testing/macro_th_exp/Macro_Regime_Threshold_Experiments_Report_2026-06-09.pdf` (created)

8. **QUESTION_DETAILS.md — plain-English Q&A and doubts reference** — SUCCESSFUL
   - Date: 2026-06-09
   - Summary: Created detailed companion doc expanding every question, answer, and Rohit doubt from the experiments report: why each question arose, what was run, simple-English answers with numbers, inline term definitions, and consolidated 18-item doubts master list.
   - Files changed:
     - `testing/macro_th_exp/QUESTION_DETAILS.md` (created)

### 2026-06-10

1. **Part H promotion candidates CSV + review script** — SUCCESSFUL
   - Date: 2026-06-10
   - Summary: Exported 62 Part H promotion candidates from `combo_discovery_20260606.json` to compact review CSV for Rohit. Added `scripts/show_combo_promotion_candidates.py` to print candidates with fire dates and optionally write CSV; verified 62 rows sorted by primary_hit_rate desc, n_fires desc.
   - Files changed:
     - `testing/macro_th_exp/part_h_promotion_candidates_20260606.csv` (created)
     - `scripts/show_combo_promotion_candidates.py` (created)

2. **Understanding doc: period & variables for A1–H** — SUCCESSFUL
   - Date: 2026-06-10
   - Summary: Added **Experiment run — period & variables** tables to all Part A (A1–A5 + Deliverable A), B (B1–B3 + Deliverable B), C, D, E, F (F1–F4 + Deliverable F), G (G1–G2 + Deliverable G), and H (Steps 1–9 + Deliverable H) in `Macro_Regime_System_v2_Understanding.md`. Documents history windows, input series (FRED/Yahoo/DB), cadence, and SPX outcome horizons per subsection.
   - Files changed:
     - `testing/macro_th_exp/understanding_and_research/Macro_Regime_System_v2_Understanding.md`

3. **Rohit v2 feedback plan + response report** — SUCCESSFUL (partial execution)
   - Date: 2026-06-10
   - Summary: Created `testingv2_plan.md` (step-by-step todos + report format guidelines from Rohit feedback). Created `testingv2_report.md` answering all feedback sections inline (PW returns at validated horizons for combos A–F, VIX n=7 instance table, HMM prototype limitations, TIGHT_* liquidity tables, curve bug root cause, TWY_ROC/GSR not tested, PIVOTING reconciliation). HMM walk-forward, 11-variable sweeps, F4 PW per-instance, and curve fix remain PENDING per plan.
   - Files changed:
     - `testing/macro_th_exp/testingv2_plan.md` (created)
     - `testing/macro_th_exp/testingv2_report.md` (created)

4. **Testing v2 implementation pass (fixes, scripts, cron)** — SUCCESSFUL
   - Date: 2026-06-11
   - Summary: Executed v2 plan items: fixed curve post-trough steepen (T10Y2Y → STEEPENING), FEARFUL→TIGHT_MONEY rename, F4 PW columns, 11-variable sweep script + JSON, HMM walk-forward scaffold (hmmlearn), emission_vectors daily cron (merged, email job preserved), Combo C MC cancel prob on briefing, TWY/GSR ablations. `testingv2_status.md` tracks progress. 12 unit tests pass.
   - Files changed:
     - `src/macro_intelligence/data/fred_pull.py`, `metrics.py`, `combo_detector.py`, `dominant.py`, `combo_metadata.py`, `nightly_run.py`, `briefing_renderer.py`, `run_all.py`
     - `scripts/per_variable_threshold_sweep.py`, `hmm_walk_forward.py`, `run_emission_vectors_daily.py`, `testingv2_ablations.py`, `install_aws_cron.sh`
     - `tests/test_curve_steepen.py`, `tests/test_combo_a_vote.py`
     - `requirements.txt`, `testing/macro_th_exp/testingv1_feedback/testingv2_status.md`
     - Artifacts: `F_per_variable_sweep.json`, `D_hmm_walk_forward.json`, `X_testingv2_ablations.json`

### 2026-06-11

1. **Production CURVE re-pull + shadow backfill + testingv2_report refresh** — SUCCESSFUL
   - Date: 2026-06-11
   - Summary: Re-ran production data pull with fixed `curve_features` (targeted CURVE refresh for 1,910 `daily_readings` dates, ~69s) and shadow backfill via `run_regime_v2_experiment_suite.py --skip-h-part --skip-report` (~2m13s). Verified post-backfill: `steepen_4wk_bps` +144bps (was −7/−11), `curve_regime_v2=STEEPENING` on latest Fridays (23/23 in 2026 YTD). Refreshed `testingv2_report.md` §1c, §1d, §2b–2d, §4, §6, §8, §9, and summary table from JSON artifacts; synced `testingv2_status.md`.
   - Files changed:
     - `macro_intelligence/data/runic.db` (CURVE meta + `macro_regime_log_v2`)
     - `macro_intelligence/analysis/regime_v2_experiments/*.json` (suite re-run)
     - `testing/macro_th_exp/testingv1_feedback/testingv2_report.md`
     - `testing/macro_th_exp/testingv1_feedback/testingv2_status.md`

2. **Sync testingv2_plan.md status + report coverage column** — SUCCESSFUL
   - Date: 2026-06-11
   - Summary: Updated all plan step Status values from `testingv2_status.md`; added **In v2 report?** column mapping each step to `testingv2_report.md` sections (✅/🔄/⏳); added step 5.4 (TWY/GSR ablation); refreshed priority order for remaining work.
   - Files changed:
     - `testing/macro_th_exp/testingv1_feedback/testingv2_plan.md`

4. **Generate nightly macro briefing for 2026-06-12 + website data snapshot MD** — SUCCESSFUL
   - Date: 2026-06-12
   - Summary: Ran full nightly pipeline (`run_nightly(as_of=2026-06-12, use_claude=True)`). Dominant Combo F week 11 (MEDIUM), posture TACTICAL EASY MONEY; Combo E CONFIRMED (CAPE+NFCI); Combo B WATCH (CFTC 1.3rd pctile); Combo C CANCELLED (2026-07-03). WTI EXTREME at −14.58% 4wk (1st pctile), CFTC EXTREME at −503,509 contracts (1st pctile), CAPE EXTREME at 42.70x (99.5th pctile), GSR EXTREME at 13.87 (96.6th pctile). Created `website_data_2026-06-12.md` with full page data snapshot.
   - Files changed:
     - `macro_intelligence/output/runic_briefing_2026-06-12.pdf`
     - `macro_intelligence/output/runic_briefing_2026-06-12.html`
     - `testing/macro_report_updates/runic_briefing_2026-06-12.pdf`
     - `testing/macro_report_updates/runic_briefing_2026-06-12.html`
     - `testing/macro_report_updates/runic_output_2026-06-12.json`
     - `testing/macro_report_updates/website_data_2026-06-12.md`

4. **Macro variable threshold validation plan — testingv2 refined** — SUCCESSFUL
   - Date: 2026-06-16
   - Summary: Refined `testing/macro_th_exp/testingv2/` plan after DB verification: mixed 0–1/0–100 percentile storage (~220 legacy rows), prior sweep 13/22 bands n=0, pctile-only bands vs CONFIG raw thresholds. Added Combo D gate sweeps, hostile-regime PW methodology (HIKING/INVERTED), benchmark table (1m–12m), infrastructure gaps audit, P1.0 DB normalization step. Plan-only — no backtests executed.
   - Files changed:
     - `testing/macro_th_exp/testingv2/threshold_validation_plan.md` (updated)
     - `testing/macro_th_exp/testingv2/testingv2_status.md` (updated)

5. **Macro Regime Report inline edits + 6 new DB queries (testingv4)** — SUCCESSFUL
   - Date: 2026-06-16
   - Summary: Ran 6 new tests against `macro_intelligence/data/runic.db` (T2: 9-state WALCL SPX tables; T3: TIGHT_* combo fires; T4: Combo E multi-horizon CAPE; T5: geo overlay non-neutral episodes; T6: TWY_ROC band sweep; T10: historical T10Y2Y inversion episodes). Inserted all results as data tables directly inline in the report at the specified sections. Added 8 text clarifications from Rohit's 2026-06-11/2026-06-16 feedback. Created `testingv4_status.md`.
   - Files changed:
     - `testing/macro_th_exp/testingv1_feedback/Macro_Regime_Threshold_Experiments_Report_2026-06-09.md` (inline edits)
     - `testing/macro_th_exp/testingv1_feedback/testingv4_status.md` (new)

6. **Execute full testingv2 threshold validation experiment (P1–P4)** — SUCCESSFUL
   - Date: 2026-06-16
   - Summary: Completed end-to-end threshold validation: normalized 220 legacy 0–1 percentile rows; fixed `per_variable_threshold_sweep.py` (0–100 bands + CURVE); built and ran `threshold_sweep_v2.py` (12 variable JSONs + SUMMARY.json with first-crossing PW + hostile slice); extended `combo_threshold_sweep.py` for Combo B/F/E/D gate sweeps via leg replay; wrote `threshold_validation_report.md` + PDF. Key finding: WTI threshold change justified (down-side −15% band); Combo B 3-of-3 n=0; most CONFIG thresholds confirmed.
   - Files changed:
     - `scripts/normalize_pctile_scale.py`, `scripts/threshold_sweep_v2.py`, `scripts/combo_gate_sweep_v2.py`
     - `scripts/per_variable_threshold_sweep.py`
     - `src/macro_intelligence/analysis/combo_threshold_sweep.py`
     - `macro_intelligence/analysis/regime_v2_experiments/F_per_variable_sweep_v2.json`
     - `macro_intelligence/analysis/regime_v2_experiments/threshold_sweep_v2/` (12 sweeps + SUMMARY + 4 combo JSONs)
     - `testing/macro_th_exp/testingv2/threshold_validation_report.md`, `.pdf`, `testingv2_status.md`

7. **Rohit feedback sectionwise answers document** — SUCCESSFUL
   - Date: 2026-06-16
   - Summary: Created `feedback_sectionwise_answers.md` answering all 32 TODO/question blocks from `feedback_sectionwise_details.md` with inline data tables (validated horizons, 9-state liquidity, TWY_ROC band sweep, geo combo slices, CAPE buckets, inversion episodes, HMM reframe). 28 answered with data; 4 pending (i3 cheatsheet compare, 18M horizon, WALCL FM threshold sweep, Parth web UI).
   - Files changed:
     - `testing/macro_th_exp/testingv1_feedback/feedback_sectionwise_answers.md` (created)

8. **Expand threshold_validation_report.md with full supporting data** — SUCCESSFUL
   - Date: 2026-06-16
   - Summary: Expanded testingv2 report (~1,679 lines) with method/instruments/duration/band-range tables, instrument reference (12 variables + SPX forward), and appendix sections for every variable and combo showing n, hit%, avg win/loss, PW expected, benchmark, excess at 1M/3M/6M/9M/12M per swept band. Re-exported PDF (251 KB).
   - Files changed:
     - `testing/macro_th_exp/testingv2/threshold_validation_report.md`, `.pdf`
     - `testing/macro_th_exp/testingv2/testingv2_status.md`

9. **Contextual verdict columns for threshold validation §4a/§4b** — SUCCESSFUL
   - Date: 2026-06-16
   - Summary: Replaced mechanical verdict logic (Δ≥2pp, hit≥60%) with variable-aware analyst judgments in `generate_section4_tables.py`; regenerated all §4a/§4b tables and report/PDF. Only WTI down-leg flagged "Consider down_15pct"; all other variables Keep CONFIG or Defer (CPI/CAPE sparse).
   - Files changed:
     - `scripts/generate_section4_tables.py`
     - `testing/macro_th_exp/testingv2/threshold_validation_report.md`, `.pdf`
     - `testing/macro_th_exp/testingv2/_section_4a_table.md`, `_section_4b_table.md`

10. **Threshold validation v2 understanding doc** — SUCCESSFUL
   - Date: 2026-06-16
   - Summary: Created plain-English understanding guide from threshold_validation_plan + report + testingv2_status: top summary of P1–P4 experiments/outcomes, glossary, per-phase Q&A tables, consolidated doubts for Rohit Sir, artifact index.
   - Files changed:
     - `testing/macro_th_exp/testingv2/understanding_and_research/Threshold_Validation_v2_Understanding.md`

11. **Rohit feedback sectionwise answers understanding doc** — SUCCESSFUL
   - Date: 2026-06-16
   - Summary: Plain-English guide from feedback_sectionwise_details + feedback_sectionwise_answers + testingv4_status: top summary table of §1/T2–T10 experiments and outcomes, glossary, per-section Q&A, 15 consolidated doubts for Rohit Sir, deliverables checklist, artifact index.
   - Files changed:
     - `testing/macro_th_exp/testingv1_feedback/understanding_and_research/Rohit_Feedback_Sectionwise_Answers_Understanding.md`

12. **Combo E horizon validation sweep 6M–18M (T11)** — SUCCESSFUL
   - Date: 2026-06-18
   - Summary: Planned and ran `combo_e_horizon_sweep.py` for Combo E at 6/9/12/15/18M (3M steps); bear hit 18.9% at 12M (n=507) validates keeping 12M primary; updated main experiments report B3, feedback_sectionwise_answers, testingv4_status, understanding doc.
   - Files changed:
     - `testing/macro_th_exp/testingv1_feedback/combo_e_horizon_plan.md`
     - `scripts/combo_e_horizon_sweep.py`
     - `macro_intelligence/analysis/regime_v2_experiments/COMBO_E_horizon_sweep_6_18m.json`
     - `testing/macro_th_exp/testingv1_feedback/Macro_Regime_Threshold_Experiments_Report_2026-06-09.md`
     - `testing/macro_th_exp/testingv1_feedback/feedback_sectionwise_answers.md`
     - `testing/macro_th_exp/testingv1_feedback/testingv4_status.md`
     - `testing/macro_th_exp/testingv1_feedback/understanding_and_research/Rohit_Feedback_Sectionwise_Answers_Understanding.md`

13. **Fix Combo C §1 horizon table — immature forward returns** — SUCCESSFUL
   - Date: 2026-06-18
   - Summary: Root cause: stale spx_3m/spx_6m on Mar 2026 C fires (+17% immature) caused false 0% bear hit and blank avg win. Added `combo_validated_horizons_table.py` (dedupe dates, mature-window only); nulled C forward_returns in DB; updated feedback_sectionwise_answers §1 and testingv2_report §1b.
   - Files changed:
     - `scripts/combo_validated_horizons_table.py`
     - `macro_intelligence/analysis/regime_v2_experiments/COMBO_validated_horizons_pw.json`
     - `testing/macro_th_exp/testingv1_feedback/feedback_sectionwise_answers.md`
     - `testing/macro_th_exp/testingv1_feedback/testingv2_report.md`
     - `macro_intelligence/data/runic.db` (Combo C forward_returns corrected)

3. **Generate nightly macro briefing for 2026-06-10** — SUCCESSFUL
   - Date: 2026-06-11
   - Summary: Ran full nightly pipeline (`run_nightly(as_of=2026-06-10, use_claude=True)`) with live DB data (12 variables). Dominant Combo F week 10 (MEDIUM), posture TACTICAL EASY MONEY; Combo E CONFIRMED (CAPE+NFCI, 19% 12M); Combo B WATCH. Briefing PDF/HTML/JSON written to `macro_intelligence/output/` and `testing/macro_report_updates/`.
   - Files changed:
     - `macro_intelligence/output/runic_briefing_2026-06-10.pdf`
     - `macro_intelligence/output/runic_briefing_2026-06-10.html`
     - `testing/macro_report_updates/runic_briefing_2026-06-10.pdf`
     - `testing/macro_report_updates/runic_briefing_2026-06-10.html`
     - `testing/macro_report_updates/runic_output_2026-06-10.json`
     - `testing/macro_report_updates/nightly_run_summary_2026-06-10.json`

### 2026-06-17

1. **Nightly CAPE/CFTC source freshness check + auto-refresh on lag** — SUCCESSFUL
   - Date: 2026-06-17
   - Summary: Every nightly run now compares CAPE and CFTC source observation dates to report `as_of`, re-scrapes multpl when CAPE lag > 7d, force-refreshes CFTC ZIP when latest Tuesday position is older than expected. JSON `source_freshness` audit; CAPE/CFTC dashboard notes show source date + lag. Verified on 2026-06-16: CAPE refreshed 2026-06-04 → 2026-06-16; CFTC Jun 9 expected (7d lag OK).
   - Files changed:
     - `src/macro_intelligence/data/source_freshness.py`
     - `src/macro_intelligence/data/pull_all.py`
     - `src/macro_intelligence/data/cftc_pull.py`
     - `src/macro_intelligence/jobs/nightly_run.py`
     - `src/macro_intelligence/output/briefing_renderer.py`
     - `macro_intelligence/CONFIG.yaml`
     - `scripts/run_macro_nightly.py`
     - `tests/test_source_freshness.py`

### 2026-06-18

6. **Combo B regime-adjusted hit rate — run, validated, spec discrepancy found** — SUCCESSFUL
   - Date: 2026-06-25
   - Summary: Ran Q9 Combo B regime analysis against live DB (n=274 mature fires). Found spec claim (91% cutting, 68% hiking) is WRONG. Actual: CUTTING_LATE=65.3%, HIKING_LATE=77.8%, QE=91.7%. The spec's "91% cutting" matches QE label, not CUTTING_LATE. Join key bug in user-provided SQL fixed (return_id → combo_id). Generated summary CSV (4 rows) + per-fire CSV (276 rows). Recommended presentation table added to feedback_sectionwise_answers.md.
   - Files changed:
     - `testing/macro_th_exp/testingv1_feedback/feedback_sectionwise_answers.md`
     - `testing/macro_th_exp/testingv1_feedback/csv_exports/combo_b_fed_cycle_hit_rates.csv` (new)
     - `testing/macro_th_exp/testingv1_feedback/csv_exports/combo_b_per_fire_regime.csv` (new)

5. **Fed cycle matrix formalisation + Claude temperature=0 fix** — SUCCESSFUL
   - Date: 2026-06-25
   - Summary: Answered fed_cycle matrix questions. Confirmed: (a) 7 raw fed_cycle states exist in code; curve_regime has 4 states (INVERTED/FLAT/STEEPENING/NORMAL) — Divyanshu correct. (b) A 4-state `fed_cycle_v2` collapse exists in `regime_v2_shadow.py` (TIGHTENING/PIVOTING/EASING/EASY), NOT the 3-state simplification discussed — the 3×3 matrix is conceptual only, not formalised. (c) Hit rates grouped as: binary HOSTILE filter in threshold sweep; 4-state fed_cycle_v2 in fm_events analytics. (d) BUG FIXED: `call_claude()` was missing `temperature` — API defaulted to 1.0. Fixed to `temperature=0.0` default so historical replays are deterministic.
   - Files changed:
     - `src/macro_intelligence/claude/_client.py` (temperature=0.0 added)
     - `testing/macro_th_exp/testingv1_feedback/feedback_sectionwise_answers.md`

4. **Add T2 9-state liquidity_v2 CSVs to csv_exports + JSON to regime_v2_experiments** — SUCCESSFUL
   - Date: 2026-06-25
   - Summary: Re-ran T2 query (combo_fires × macro_regime_log_v2 × forward_returns) for all 9 liquidity_v2 states. Generated: (1) summary CSV (9 rows, up%/avg% at 1m/3m/6m/9m/12m), (2) per-fire CSV (15,161 rows), (3) JSON experiment artifact. Updated feedback_sectionwise_answers.md A6.g reference to point to all three files.
   - Files changed:
     - `testing/macro_th_exp/testingv1_feedback/csv_exports/liquidity_v2_9state_spx_returns.csv` (new)
     - `testing/macro_th_exp/testingv1_feedback/csv_exports/liquidity_v2_9state_perfire_rows.csv` (new)
     - `macro_intelligence/analysis/regime_v2_experiments/liquidity_v2_9state_spx_returns.json` (new)
     - `testing/macro_th_exp/testingv1_feedback/feedback_sectionwise_answers.md`

3. **Fix geo table, TIGHT_* unnamed clarification, CSV exports, WALCL actual counts** — SUCCESSFUL
   - Date: 2026-06-18
   - Summary: (1) Geo table: added validated hit% column — prior table only showed "SPX up%" which is meaningless for bearish combos (D/E). Now shows % of fires where signal was correct per combo direction. (2) TIGHT_* unnamed: clarified that "unnamed" = generic pair-threshold events where runic_combo IS NULL (did not pass naming gate), NOT unnamed versions of A–G. Only Combo A has named fires in TIGHT_*. (3) Created CSV export directory with 3 files: 46-row TIGHT_* Combo A table, 58-row geo overlay table, WALCL threshold distribution. (4) WALCL "~est." replaced with actual DB counts (NFCI-EASY Fridays n=719): ±0.3% → 291/230/198; ±0.2% → 309/273/137; ±0.1% → 335/309/75.
   - Files changed:
     - `testing/macro_th_exp/testingv1_feedback/feedback_sectionwise_answers.md`
     - `testing/macro_th_exp/testingv1_feedback/csv_exports/tight_liquidity_named_combo_46rows.csv` (new)
     - `testing/macro_th_exp/testingv1_feedback/csv_exports/geo_overlay_combo_fires_non_neutral.csv` (new)
     - `testing/macro_th_exp/testingv1_feedback/csv_exports/walcl_mom_threshold_distribution.csv` (new)

3. **Add SSI API endpoints (v1.4.0) — summary, history, multiplier — and push docs** — SUCCESSFUL
   - Date: 2026-06-19
   - Summary: Added 3 new SSI endpoints backed by `ssi.db`. `GET /macro/ssi/summary` returns the latest snapshot with full per-input vote breakdown. `GET /macro/ssi/history` returns a daily time series (configurable `?days=N`, max 90, chronological). `GET /macro/ssi/multiplier` is a lightweight sizing endpoint. Added service functions in `macro_service.py`, 10 new unit tests (32/32 pass total), 3 endpoint doc pages, updated README/changelog/services catalog to v1.4.0. Committed and pushed to `divsum127/mindwealth-api-docs` (`4863c2c → 1627656`).
   - Files changed:
     - `api/services/macro_service.py` (3 new functions: `get_ssi_summary`, `get_ssi_history`, `get_ssi_multiplier`)
     - `api/routers/macro.py` (3 new SSI routes)
     - `tests/test_api_macro.py` (10 new tests — TestSSIEndpoints class)
     - `docs/mindwealth-api-docs/README.md` (v1.4.0)
     - `docs/mindwealth-api-docs/changelog.md` (v1.4.0 entry)
     - `docs/mindwealth-api-docs/services/README.md` (71 ops)
     - `docs/mindwealth-api-docs/services/macro/README.md` (20 endpoints)
     - `docs/mindwealth-api-docs/services/macro/endpoints/get-ssi-summary.md` (new)
     - `docs/mindwealth-api-docs/services/macro/endpoints/get-ssi-history.md` (new)
     - `docs/mindwealth-api-docs/services/macro/endpoints/get-ssi-multiplier.md` (new)

2. **Create Macro Intelligence API endpoints for full frontend view (v1.3.0)** — SUCCESSFUL
   - Date: 2026-06-18
   - Summary: Implemented 13 new macro API endpoints covering all 6 tabs of the `MindWealth_Macro_Runic_Latest.html` frontend view. Created `api/services/macro_service.py` as dedicated macro service layer with DB + JSON helpers. Expanded `api/routers/macro.py` to 17 total endpoints. Added 22 unit tests (all pass). Live curl suite: 22/23 pass (run-nightly excluded due to sync duration). Committed v1.3.0 docs to `docs/mindwealth-api-docs/` with 13 new endpoint pages.
   - Files changed:
     - `api/services/macro_service.py` (new)
     - `api/routers/macro.py` (expanded: 4 → 17 endpoints)
     - `tests/test_api_macro.py` (new — 22 tests)
     - `docs/mindwealth-api-docs/README.md` (version 1.3.0)
     - `docs/mindwealth-api-docs/changelog.md` (v1.3.0 entry)
     - `docs/mindwealth-api-docs/services/README.md` (68 ops)
     - `docs/mindwealth-api-docs/services/macro/README.md` (17 endpoints)
     - `docs/mindwealth-api-docs/services/macro/endpoints/` (13 new .md files)

1. **Upgrade Claude prompt + template briefing — analytical narrative, full combo coverage** — SUCCESSFUL
   - Date: 2026-06-18
   - Summary: Fixed ordering bug (`combo_status_rows` built after narrative — now built before). Rewrote SYSTEM prompt with 12-variable + 7-combo significance guides; 600-750w five-section format. Updated USER prompt with all 7 combo rows, EXTREME/RARE tier lists, CFTC RM note, SSI multiplier, VIX bypass. Completely rewrote `_template_briefing` fallback to produce ~200 words of interpretive analytical prose — CFTC fuel, WTI implications, Combo E headwind, VXTS/Combo D gap, competing combo summary, posture conditions. Verified on 2026-06-16 run.
   - Files changed:
     - `src/macro_intelligence/claude/nightly_briefing.py`
     - `src/macro_intelligence/jobs/nightly_run.py`
     - `macro_intelligence/CONFIG.yaml`

### 2026-06-23

1. **Fix dominant_reason generation for all combos + Combo C backfill + tests** — SUCCESSFUL
   - Summary: Refactored `_build_reason()` to use status-aware verbs, conditional duration clauses, honest outrank wording (`configured priority rank`), and shared `format_reason_hit_rate*` helpers (no fake `0%` or `week None`). Added `scripts/backfill_named_combo_fires.py` with documented Combo C analog seeding + forward-return backfill (C mature 6M n=3). Expanded tests: `tests/test_dominant_reason.py` (20 cases), `tests/test_dominant_priority.py` (7 cases). 52/52 pytest pass (venv). Nightly JSON updated with new reason string.
   - Files changed:
     - `src/macro_intelligence/engine/combo_metadata.py`
     - `src/macro_intelligence/engine/dominant.py`
     - `src/macro_intelligence/data/yahoo_pull.py`
     - `scripts/backfill_named_combo_fires.py` (new)
     - `tests/test_dominant_reason.py` (new)
     - `tests/test_dominant_priority.py`
     - `tests/test_api_macro.py`
     - `macro_intelligence/output/runic_output.json`

### 2026-06-24

1. **Export Combo D/E per-trigger forward-return CSVs** — SUCCESSFUL
   - Summary: Threshold-sweep artifacts had aggregate gate stats only, not per-fire tables at requested horizons. Added `scripts/export_combo_de_per_fire_returns.py` and generated CSVs: Combo D (1W–2M, 435 trigger dates, 2010-12-10→2026-07-03) and Combo E (1M–6M monthly, 484 dates, 2010-09-24→2026-07-03). Each row = trigger date; columns = SPX % return post-trigger; `hit_*` = bearish hit (SPX down). Meta JSON includes backtest period and per-horizon hit-rate summary.
   - Files changed:
     - `scripts/export_combo_de_per_fire_returns.py` (new)
     - `testing/macro_th_exp/testingv1_feedback/csv_exports/combo_de_per_fire_returns/combo_d_per_fire_returns.csv`
     - `testing/macro_th_exp/testingv1_feedback/csv_exports/combo_de_per_fire_returns/combo_e_per_fire_returns.csv`
     - `testing/macro_th_exp/testingv1_feedback/csv_exports/combo_de_per_fire_returns/combo_de_per_fire_meta.json`

2. **Combo D threshold sweep (VXTS/CFTC/VIX) — all horizons CSV export** — SUCCESSFUL
   - Summary: Ran 504-experiment factorial + univariate sweep on Combo D gates (VXTS≥, CFTC pctile≥, VIX≤, 2–3 legs) across horizons 1W–2M. Outputs: `combo_d_threshold_sweep_all_horizons.csv` (3024 rows), `combo_d_threshold_sweep_experiment_summary.csv` (min/max/mean hit & SPX stats), `combo_d_threshold_sweep_top_candidates.csv` (top 25 by 1W bear hit, n≥10). Best candidate: vxts 1.18, cftc 75, vix 16, 2-of-3 → 78 events, 58.4% bear hit 1W, avg SPX −0.29% at 1W. CONFIG 3-of-3 baseline: 31 events, 41.9% 1W. No variant clears 60% at all horizons.
   - Files changed:
     - `scripts/combo_d_threshold_sweep_export.py` (new)
     - `testing/macro_th_exp/testingv1_feedback/csv_exports/combo_d_threshold_sweep/*.csv`
     - `testing/macro_th_exp/testingv1_feedback/csv_exports/combo_d_threshold_sweep/combo_d_threshold_sweep_meta.json`

3. **Fix Combo B WATCH showing 0/3 legs in API — expose confirmed_legs on watch combos** — SUCCESSFUL
   - Date: 2026-06-24
   - Summary: WATCH combos (e.g. B) were emitted as bare strings with no `confirmed_legs`, so `/macro/combos/B` returned `confirmed_legs: []` and UI showed 0/3. Added `evaluate_combo_b_legs` / `evaluate_combo_d_legs`, populated `macro_regime.confirmed_legs` on WATCH fires, enriched `watch_combos` to dicts (`legs_confirmed`, `pending`), updated `combo_status_rows`, `macro_service.get_combo_detail`, and briefing renderer. Verified locally: B → WATCH 1/3, `confirmed_legs: ["CFTC"]`, pending VIX+HY (as of 2026-06-23 readings). Production API still on prior JSON until nightly redeploy.
   - Files changed:
     - `src/macro_intelligence/engine/combo_detector.py`
     - `src/macro_intelligence/jobs/nightly_run.py`
     - `src/macro_intelligence/output/briefing_renderer.py`
     - `src/macro_intelligence/output/json_writer.py`
     - `api/services/macro_service.py`
     - `src/pages/runic_page.py`
     - `tests/test_combo_b_hy_dual.py`
     - `macro_intelligence/output/runic_output.json`

4. **Combo D & E full threshold study (sweep + sync + regime overlay)** — SUCCESSFUL
   - Date: 2026-06-24
   - Summary: Ran 350 D + 377 E gate experiments on Friday first-crossing episodes (5d cooldown), not weekly WATCH backfill. Outputs in `testing/combo_de_thresholds/output_files/`: sweep detail/summary CSVs, sync analysis, yield-curve regime overlay, recommended thresholds, master analysis CSV, `study_meta.json`. **80% bear-hit target not met for D at any n≥10; met for E only at n≤4.** Best practical D (n 15–50): VXTS≥1.25, CFTC≥95, VIX≤16, 2-of-3 → 42 events, 54.8% bear @1W. Best practical E: CAPE≥30, NFCI≤−0.20, CFTC≥92, 3-of-3 → 16 events, 46.7% bear @12M. CONFIG baseline D: 31 events, 41.9% @1W; E: 22 events, 9.1% @12M. D+E sync (best pair): 3 dates, 66.7% bear @1W / 0% @12M.
   - Files changed:
     - `testing/combo_de_thresholds/run_combo_de_study.py` (new)
     - `testing/combo_de_thresholds/output_files/*.csv`
     - `testing/combo_de_thresholds/output_files/study_meta.json`

5. **Combo D/E follow-up experiments — production-viable (no 80%) + sync overlay** — SUCCESSFUL
   - Date: 2026-06-24
   - Summary: Extended finer-grid sweeps (1131 D, 382 E with n≥10). Best production-scored D: VXTS 1.18/CFTC 95/VIX 13/2-of-3 (n=46, 56.5% bear @1W). Best E n≥10: CAPE 32/NFCI −0.15/CFTC 85/3-of-3 (n=10, 66.7% @12M). 1600 D×E sync pair matrix: CONFIG sync 60% @1W (+18pp lift) but 0% bear @12M on overlap; mean sync lift @1W negative (−2.8pp) across pairs — tactical overlay works for selected gates, not structural confirmation.
   - Files changed:
     - `testing/combo_de_thresholds/run_combo_de_followup.py` (new)
     - `testing/combo_de_thresholds/output_files/case1_*.csv`, `case2_*.csv`, `followup_meta.json`

### 2026-06-27

1. **Remove git commit/push from update_trade_data.sh (local-only data sync)** — SUCCESSFUL
   - Date: 2026-06-27
   - Summary: Dropped `git add`, `git commit`, and `git push` from the daily trade-data pipeline so prod (`uiv2/git`) updates `trade_store/`, chatbot data, and conviction artifacts on disk only. Supports dev/prod split: code flows dev → git remote → prod pull; data no longer competes on `main`.
   - Files changed:
     - `update_trade_data.sh`

### 2026-07-03

1. **Macro scheduled-events API endpoints + frontend integration guide (v1.5.0)** — SUCCESSFUL
   - Date: 2026-07-03
   - Summary: Added three new macro API routes (`/macro/events/pre-catalyst`, `/macro/events/post-regime`, `/macro/events/calendar`) without changing existing endpoint response shapes. Reverted `pre_catalyst`/`post_event_regime` from `GET /macro/regime`. Documented endpoints, changelog v1.5.0, OpenAPI export, and frontend wiring guide.
   - Files changed:
     - `api/services/macro_service.py`
     - `api/routers/macro.py`
     - `tests/test_api_macro.py`
     - `docs/api/services/macro/README.md`
     - `docs/api/services/macro/endpoints/get-pre-catalyst.md` (new)
     - `docs/api/services/macro/endpoints/get-post-event-regime.md` (new)
     - `docs/api/services/macro/endpoints/get-scheduled-events-calendar.md` (new)
     - `docs/api/frontend/macro-scheduled-events-integration.md` (new)
     - `docs/api/changelog.md`
     - `docs/api/openapi/mindwealth-v1.json`

### 2026-06-30

1. **Pre/Post scheduled-event regime intelligence (7a + 7b)** — SUCCESSFUL
   - Summary: Added pre-catalyst fragility score (60th–79th / 21st–40th percentile near-threshold count before CPI/FOMC/NFP), extended macro calendar (FRED + optional Investing.com) for FOMC/NFP, post-event 48h regime transition classifier (5 types), FRED yield window helpers, nightly JSON fields `pre_catalyst` and `post_event_regime`, API exposure, briefing context. 21 unit tests pass.
   - Files changed:
     - `macro_intelligence/CONFIG.yaml`
     - `src/macro_intelligence/data/macro_calendar.py` (new)
     - `src/macro_intelligence/data/yield_window.py` (new)
     - `src/macro_intelligence/data/fred_pull.py`
     - `src/macro_intelligence/data/pull_all.py`
     - `src/macro_intelligence/engine/pre_catalyst_fragility.py` (new)
     - `src/macro_intelligence/engine/post_event_transition.py` (new)
     - `src/macro_intelligence/jobs/nightly_run.py`
     - `src/macro_intelligence/output/json_writer.py`
     - `src/macro_intelligence/claude/nightly_briefing.py`
     - `api/services/macro_service.py`
     - `scripts/sync_macro_calendar.py` (new)
     - `scripts/backfill_event_transitions.py` (new)
     - `tests/test_pre_catalyst_fragility.py` (new)
     - `tests/test_macro_calendar.py` (new)
     - `tests/test_post_event_transition.py` (new)
     - `tests/test_runic_output_schema.py`

2. **API security hardening — invite-only auth (FastAPI + Nuxt + Streamlit)** — SUCCESSFUL
   - Date: 2026-06-30
   - Summary: Implemented mandatory `X-API-Key`, JWT invite-only auth (`/api/v1/auth/*`), chatbot session ownership, Nuxt proxy + login/accept-invite/admin UI, Streamlit gate, bootstrap/invite scripts, `config/users.json` (gitignored). Dev API `:8507` live with API key; Nuxt `:8512` proxies to dev until prod deploy. **93 API tests pass.** Prod `:8506` still on pre-auth code until `chatbot-dev` → `chatbot-prod` merge + pull.
   - Files changed:
     - `api/routers/auth.py`, `api/schemas/auth.py`, `api/services/auth_service.py` (new)
     - `api/dependencies.py`, `api/main.py`, `api/routers/chatbot.py`, `api/services/chatbot_service.py`
     - `chatbot/session_manager.py`, `src/auth/streamlit_gate.py`, `app.py`
     - `config/users.json.example`, `scripts/bootstrap_admin.py`, `scripts/invite_user.py`
     - `scripts/mindwealth-api-dev.service`, `scripts/mindwealth-api.service`, `requirements.txt`, `.gitignore`
     - `tests/test_api_auth.py` (new), `tests/test_api_chatbot.py`, `tests/test_api_conviction.py`, `tests/test_api_integration.py`
     - `MindwealthUI_Vue`: `server/routes/api/v1/[...].ts`, `composables/useAuth.ts`, `middleware/auth.global.ts`, `pages/login.vue`, `pages/accept-invite.vue`, `pages/admin/users.vue`, chat server routes

3. **Per-user activity logging (pages, clicks, chat) with admin toggle** — SUCCESSFUL
   - Date: 2026-06-30
   - Summary: Added `activity_logging_enabled` per user, admin On/Off toggle on `/admin/users`, JSONL logs under `activity_logs/{email_slug}/` (navigation, clicks, chat). Nuxt client tracks page views + clicks when enabled; FastAPI logs chat messages on enqueue.
   - Files changed:
     - `api/services/activity_log_service.py`, `api/routers/activity.py`, `api/schemas/activity.py` (new)
     - `api/services/auth_service.py`, `api/schemas/auth.py`, `api/routers/auth.py`, `api/routers/chatbot.py`, `api/main.py`
     - `config/users.json.example`, `.gitignore`, `tests/test_activity_log.py` (new)
     - `MindwealthUI_Vue`: `composables/useActivityLog.ts`, `plugins/activity-log.client.ts`, `pages/admin/users.vue`, `composables/useAuth.ts`

4. **Dev → prod migration todos doc + Cursor rules** — SUCCESSFUL
   - Date: 2026-06-30
   - Summary: Added `docs/dev_to_prod_migration_todos.md` with full auth/activity logging prod checklist (incl. Nuxt → `:8507` dev shortcut to revert). Updated `.cursor/rules/mindwealth-ui-repository-rules.mdc` to require migration doc updates after dev changes with prod impact.
   - Files changed:
     - `docs/dev_to_prod_migration_todos.md` (new)
     - `.cursor/rules/mindwealth-ui-repository-rules.mdc`

5. **API rate limiting (FastAPI tiers + Nuxt BFF auth/rate middleware)** — SUCCESSFUL
   - Date: 2026-06-30
   - Summary: Tiered rate limits via middleware (`user` → `apikey` → `ip` keys), env-configurable defaults, 429 + `Retry-After`. Nuxt BFF requires session cookie on `/api/*` (excl. `/api/v1` proxy) + light IP limits. Five new rate-limit tests pass; existing suites disable limits in setUp.
   - Files changed:
     - `api/rate_limit.py`, `api/rate_limit_config.py`, `api/main.py`, `requirements.txt`, `.env.example`
     - `config/rate_limits.yaml` — editable admin vs user limits
     - `tests/test_rate_limit.py`, `tests/api_test_helpers.py`, test setUp patches
     - `docs/dev_to_prod_migration_todos.md`
     - `MindwealthUI_Vue`: `server/utils/require-auth.ts`, `server/middleware/bff-auth.ts`, `server/middleware/bff-rate-limit.ts`

6. **Role-based rate limits (admin vs user) + YAML config** — SUCCESSFUL
   - Date: 2026-07-07
   - Summary: Admin JWT gets generous limits (reads 200/10s, chat 30/min); standard users keep anti-abuse caps (reads 30/10s, chat 3/min). Single config file `config/rate_limits.yaml`; dev API restarted on `:8507`.
   - Files changed: `config/rate_limits.yaml`, `api/rate_limit_config.py`, `api/rate_limit.py`, `tests/test_rate_limit.py`, `.env.example`

7. **Test suite green + prod-merge blockers fixed** — SUCCESSFUL
   - Date: 2026-07-09
   - Summary: Root-cause fixes: `tests/conftest.py` + `load_dotenv(override=False)` stops `.env` API_KEY breaking tests; combo_c_cancel DB reset in setUp; smart_data_fetcher respects `date_filter_mode=entry_or_exit`; enrich adds `function`/`interval`; signals surface tests updated for pipeline-persisted CSV columns. **349 pytest passed.**
   - Files changed: `tests/conftest.py`, `src/config_paths.py`, `chatbot/config.py`, `chatbot/smart_data_fetcher.py`, `api/services/signal_enrichment_service.py`, `tests/test_combo_c_cancel.py`, `tests/test_api_signals_surface.py`, `docs/dev_to_prod_migration_todos.md`

8. **Release A commit pushed to origin/chatbot-dev** — SUCCESSFUL
   - Date: 2026-06-30
   - Summary: Staged only Release A paths (44 files); commit `a1cd39f36` `feat(release-a): auth, activity logs, API rate limits`; pushed to `https://github.com/divsum127/MindWealth_UI.git` `chatbot-dev`. Macro/combo WIP and runtime artifacts left unstaged.
   - Files changed: see commit `a1cd39f36` (auth, activity, rate limits, tests, migration doc, systemd templates)

### 2026-07-16

1. **D4 — B4 window audit re-run (macro_th_exp)** — SUCCESSFUL
   - Date: 2026-07-16
   - Summary: Re-ran `_run_b4_window_audit()` against live `CONFIG.yaml`. WALCL fix (2026-06-09) confirmed PASS (`full`/`full`). HY, VIX, VXTS still FAIL (`full` vs plan `rolling_3y`) — 3/12 mismatches, B4 pass=false. These vars feed short-gate combos B/D/G. Flagged open spec conflict with Rohit 2026-06-11 structural-window override.
   - Files changed:
     - `testing/macro_th_exp/D4_window_audit_rerun_2026-07-16.json` (created)
     - `testing/macro_th_exp/D4_window_audit_rerun_2026-07-16.md` (created)

2. **D5 — Fed-cycle re-slicing on recalibrated D/E thresholds (macro_th_exp)** — SUCCESSFUL
   - Date: 2026-07-16
   - Summary: Recalibrated D/E fed-cycle slices at validated horizons. D spread CUTTING_LATE−HIKING_LATE survives at 1W (+50.6 pp) and 2W (+35.9 pp). E per-fed slices CANNOT USE (n&lt;10). See `testing/macro_th_exp/D5_fed_cycle_reslice_2026-07-16.md`.
   - Files changed:
     - `testing/macro_th_exp/run_d5_fed_cycle_reslice.py` (new)
     - `testing/macro_th_exp/D5_fed_cycle_reslice_2026-07-16.*` (new)

3. **Promote Combo E BEST PRODUCTION SCORE + CFTC escalation** — SUCCESSFUL
   - Date: 2026-07-17
   - Summary: CONFIG E → CAPE≥32 / NFCI≤−0.15 / CFTC≥85 / 3-of-3; ESCALATION_ALERT on CFTC pctile rise ≥5/4wk. Detector, briefing, dominant, API cheatsheet wired.
   - Files: `macro_intelligence/CONFIG.yaml`, `combo_detector.py`, `dominant.py`, `nightly_run.py`, `briefing_renderer.py`, `nightly_briefing.py`, `macro_service.py`, `tests/test_combo_e_thresholds.py`

4. **Promote Combo D BEST PRODUCTION SCORE + 2-of-3** — SUCCESSFUL
   - Date: 2026-07-17
   - Summary: CONFIG D → VXTS≥1.18 / CFTC≥95 / VIX≤13 / 2-of-3; true 2-of-3 detector; horizons 1W+2W.
   - Files: `macro_intelligence/CONFIG.yaml`, `combo_detector.py`, `nightly_briefing.py`, `macro_service.py`, `tests/test_combo_d_thresholds.py`

### 2026-07-14

1. **Test 5 — Regime Sharpe uplift (SPY/TLT/GLD/HYG vs 5-dimension overlay)** — SUCCESSFUL
   - Date: 2026-07-14
   - Summary: Built full Michele demo backtest in `testing/5_regime_uplift/`. Equal-weight monthly-rebalance basket (2007-04 → 2026-07). Baseline Sharpe 0.885 → regime overlay 0.938 (+0.053). Overlay lowers CAGR (7.72%→6.39%) but improves max DD (−22.6%→−17.6%). v1 multipliers from economic priors in `multiplier_spec.md`. Outputs: REPORT.md, summary_metrics.json, daily CSVs.
   - Files changed:
     - `testing/5_regime_uplift/PLAN.md` (new)
     - `testing/5_regime_uplift/multiplier_spec.md` (new)
     - `testing/5_regime_uplift/run_regime_sharpe_uplift.py` (new)
     - `testing/5_regime_uplift/README.md` (updated)
     - `testing/5_regime_uplift/output_files/*` (new)

### 2026-07-13

1. **Fix prod login for admin@mindwealth.co (password mismatch)** — SUCCESSFUL
   - Date: 2026-07-13
   - Summary: Prod admin was bootstrapped with a random password at deploy; user expected dev/original password. Reset prod password to match dev; verified login via API and Nuxt proxy.
   - Files: prod `config/users.json`, `config/.bootstrap_admin_password`

### 2026-07-12

1. **Release B — macro, cross-function, analysis artifacts → prod** — SUCCESSFUL
   - Date: 2026-07-12
   - Summary: Commits `03903169b`..`a577c1775` on `chatbot-dev`; prod merge `caff62630`. Features: pre/post catalyst macro APIs, cross-function exit flags, combo classification export, threshold sweep artifacts. Prod deployed; 21 endpoint smoke checks pass on `:8506`.
   - Files: see commits on `chatbot-dev`; excluded `monitored_trades.json`

### 2026-07-11

1. **Release A prod deploy (merge, pull, bootstrap, Nuxt BFF, smoke tests)** — SUCCESSFUL
   - Date: 2026-07-11
   - Summary: `chatbot-prod` merge `1f84f86ad` pushed; prod `prod-pull-and-restart.sh`; `.env` + `RATE_LIMIT_ENABLED=true`; admin bootstrapped on prod; Nuxt `7661255` + build; `mindwealth-ui` → `NUXT_API_BASE_URL=:8506`. Smoke: health 401/200, login 200, BFF 401/200, chatbot 401 without JWT.
   - Files changed: prod `.env`, `config/users.json`, `config/.bootstrap_admin_password`; `/etc/systemd/system/mindwealth-ui.service`; `MindwealthUI_Vue/server/middleware/*`, `server/utils/require-auth.ts`; `docs/dev_to_prod_migration_todos.md`

### 2026-06-29

1. **Rename uiv2/dev directory to uiv2/prod** — SUCCESSFUL
   - Date: 2026-06-29
   - Summary: Renamed `/home/ubuntu/uiv2/dev` → `/home/ubuntu/uiv2/prod`. Updated nightly `emailscript.sh` cron path and job status details reference.
   - Files changed:
     - `/home/ubuntu/MindWealth/emailscript.sh`
     - `docs/mindwealth_ui_repo_job_status_details.md`

2. **Strengthen Cursor rules: never edit uiv2/prod** — SUCCESSFUL
   - Date: 2026-06-29
   - Summary: Updated project and global Cursor rules with explicit read-only prod scope, path guard before edits, and mandatory warnings for accidental or user-requested prod changes.
   - Files changed:
     - `.cursor/rules/mindwealth-ui-repository-rules.mdc`
     - `/home/ubuntu/.cursor/rules/mindwealth-repository-rules.mdc`

### 2026-07-03

1. **All combos A–G threshold sweep + CONFIG vs spec analysis** — SUCCESSFUL
   - Date: 2026-07-03
   - Summary: Ran full threshold sweeps for combos A–G with combo-specific horizon spreads (tactical 1W–4W for D/G, structural 3M–18M for E, etc.). Outputs: per-combo `combo_*_sweep_summary.csv` / `detail.csv` with min/max/avg hit stats in CSV header, `all_combos_config_vs_spec.csv`, `all_combos_best_thresholds.csv`, `ANALYSIS.md`, `study_meta.json`. CONFIG vs spec: A +0.9pp, F +7.7pp @ primary; D −36pp, E −64pp; C/G too few episodes on first-crossing model.
   - Files changed:
     - `testing/combo_all_thresholds/run_all_combos_study.py` (new)
     - `testing/combo_all_thresholds/output_files/*`

2. **Enhanced ANALYSIS.md — top threshold tables + variable recommendations** — SUCCESSFUL
   - Date: 2026-07-03
   - Summary: Extended Combo C (79 exps, max n=6) and G (107 exps, max n=12) sweeps. Regenerated `ANALYSIS.md` section 2 with per-combo top-5 horizon tables; section 3–4 full-gate + master variable table; CSVs `all_combos_recommended_full_config.csv`, `all_combos_best_threshold_per_variable.csv`. Combo C: no config hits spec 83% @6M (best 6M bear = 0%).
   - Files changed:
     - `testing/combo_all_thresholds/run_extended_c_g_sweep.py` (new)
     - `testing/combo_all_thresholds/generate_enhanced_analysis.py` (new)
     - `testing/combo_all_thresholds/output_files/ANALYSIS.md`, `combo_C_extended_sweep_summary.csv`, `combo_G_extended_sweep_summary.csv`
