# MindWealth UI Repository Todos

Task log for MindWealth UI (`/home/ubuntu/uiv2/git/MindWealth_UI`).

## Entry Format

Each entry must include:

- Task description
- Status: SUCCESSFUL / UNSUCCESSFUL
- Summary of outcome
- Relevant files changed (if any)

Maintain sequential numbering within each date. Continue numbering from the latest entry for that date.

---

## 2026-06-06

1. **Create MindWealth_UI repository operating rules and todo log** — SUCCESSFUL
   - Summary: Created always-applied Cursor rule defining repository scope, mandatory task logging, and completion protocol. Created project todo log with `mindwealth_ui_repo` naming.
   - Files changed:
     - `/home/ubuntu/uiv2/git/MindWealth_UI/.cursor/rules/mindwealth-ui-repository-rules.mdc`
     - `/home/ubuntu/uiv2/git/MindWealth_UI/.cursor/mindwealth_ui_repo_todos.md`

3. **Runic PDF Quality & Narrative Upgrade — raise narrative_max_tokens to 1200, add fetch_macro_headlines, rewrite 5-paragraph Claude prompt, full visual PDF/HTML redesign** — SUCCESSFUL
   - Summary: (1) Raised `narrative_max_tokens` 500→1200 in CONFIG.yaml. (2) Added `fetch_macro_headlines()` to `geo_news.py` for broad macro Tavily context. (3) Rewrote `nightly_briefing.py` with detailed 5-paragraph SYSTEM prompt (dominant signal, all combos, 3 reasons, analogs, posture). (4) Rebuilt `briefing_renderer.py` with dark navy (#0A1628) header band, green ACTIVE / amber WATCH combo rows, 3-column regime grid, EXTREME/HIGH tier-coloured variable dashboard, navy recommendation box, centred footer — for both PDF (reportlab Platypus) and HTML. (5) Updated tests with colour-palette smoke check. (6) Verified nightly run: 7.6 KB PDF generated with full 5-paragraph narrative.
   - Files changed:
     - `macro_intelligence/CONFIG.yaml`
     - `src/macro_intelligence/claude/geo_news.py`
     - `src/macro_intelligence/claude/nightly_briefing.py`
     - `src/macro_intelligence/output/briefing_renderer.py`
     - `tests/test_briefing_renderer.py`

8. **Web-verified data audit of nightly report variables and combo classifications** — SUCCESSFUL
   - Summary: Cross-checked all 12 variables and all 7 combo statuses against live web sources (FRED, CBOE, Advisor Perspectives, Multpl, Convex). Confirmed: NFCI, HY, VIX, CURVE correct. CAPE within range. Found 6 pipeline issues logged as T-01 through T-06 in job status TODO section.
   - Key findings: (1) Fed Cycle "CUTTING_LATE" misleading during 5-month Fed pause with hike risk; (2) VIX +40% spike not tier-escalated; (3) CAPE source inconsistency; (4) Combo B WATCH on 1/3 legs ambiguous in report; (5) Combo F Week 1 needs trigger audit logging; (6) 6 variables cannot be independently web-verified without API.
   - Files changed: `docs/mindwealth_ui_job_status.md`

7. **Document Signal column behaviour (direction engine vs renderer fallback) in README_MAINTENANCE.md** — SUCCESSFUL
   - Summary: Added "Variable dashboard — Signal column behaviour" section explaining that the engine sets direction only for RARE/EXTREME tier; renderer `_derive_direction()` fallback covers NORMAL tier using percentile ≥ 50 = UP.
   - Files changed: `macro_intelligence/README_MAINTENANCE.md`

6. **Fix empty Signal column in variable dashboard + audit both briefing tables** — SUCCESSFUL
   - Summary: Signal/direction was only set by the engine for RARE/EXTREME tier variables (by design). Added `_derive_direction()` in `briefing_renderer.py` that falls back to percentile-based UP/DOWN (pctile ≥ 50 = UP, < 50 = DOWN) for NORMAL tier variables, so all 12 rows now have a Signal value. Full column audit confirmed all other columns in Table 1 (Combo Status) and Table 2 (Variable Dashboard) are correctly sourced from engine/DB/config with no incorrect hardcoding.
   - Files changed: `src/macro_intelligence/output/briefing_renderer.py`

5. **Fix empty Direction, 3M Hit Rate, Avg 3M SPX columns for INACTIVE/WATCH combos in briefing table** — SUCCESSFUL
   - Summary: Added `_all_time_combo_stats()` querying DB `combo_fires JOIN forward_returns` for per-combo historical hit rate and avg 3M return. INACTIVE and WATCH rows now show direction from config and all-time stats from DB (G has no DB data yet so remains —).
   - Files changed: `src/macro_intelligence/output/briefing_renderer.py`

4. **Remove "Generated HH:MM ET" timestamp from PDF/HTML report header** — SUCCESSFUL
   - Summary: Removed `generated_et` field from `build_briefing_sections()` and stripped it from both the HTML subtitle bar and the PDF header Paragraph. All 4 tests pass.
   - Files changed: `src/macro_intelligence/output/briefing_renderer.py`

2. **Analyze macro regime v2 mail PDF and create summary** — SUCCESSFUL
   - Summary: Read Rohit's consolidated macro regime system v2 email (8 pages). Created structured summary in docs/ssi_validation. Renamed source PDF from `Threshold experiments mail.pdf` to `Macro_Regime_System_v2_Consolidated_Plan_Mail.pdf`.
   - Files changed:
     - `/home/ubuntu/uiv2/git/MindWealth_UI/docs/ssi_validation/MACRO_REGIME_V2_CONSOLIDATED_PLAN_SUMMARY.md` (created)
     - `/home/ubuntu/uiv2/git/MindWealth_UI/macro_intelligence_docs/Macro_Regime_System_v2_Consolidated_Plan_Mail.pdf` (renamed from `Threshold experiments mail.pdf`)

11. **Update SSI_OPEN_QUESTIONS_SUMMARY.md with Part II experiment results** — SUCCESSFUL
   - Summary: Added §9 (Part II — 2026-06-06 run) to `SSI_OPEN_QUESTIONS_SUMMARY.md` covering all 7 sub-sections (Tests 5, 6, 12, 14, 15, 16, 17). Updated test status entries in the Part 9 table. Updated doc header to reflect dual validation dates.
   - Files changed:
     - `docs/ssi_validation/SSI_OPEN_QUESTIONS_SUMMARY.md`

10. **Implement SSI validation experiments plan** — SUCCESSFUL
   - Summary: Implemented full SSI open-questions experiment plan from `SSI_OPEN_QUESTIONS_SUMMARY.md`. CNN F&G cache backfilled to 2018 via Alternative.me (now 28 greed>80 crossings, 68 fear<20). Test 14 forward-return export gap fixed (horizons mismatch bug). Test 16 now live-checks AAII and CPI → 12/12 PASS. New Test 17 (TrendPulse deterioration) module written. Validation suite re-run; Tests 6/12/14/16/17 refreshed. Test 5 (TP/SL) run via MindWealth adapter → best TP×5/SL×20 (Sharpe 4.06). Test 15 (SBI short) confirmed accessible but requires overnight batch run. SIGNOFF.md updated with full status table and 5 pending Rohit decisions.
   - Files changed:
     - `src/sentiment_superindex/data/cnn_fear_greed.py` (backfill from Alternative.me)
     - `src/sentiment_superindex/analysis/gross_net_divergence.py` (horizons mismatch fix)
     - `src/sentiment_superindex/analysis/friday_pull_checklist.py` (live AAII+CPI checks)
     - `src/sentiment_superindex/analysis/trendpulse_deterioration.py` (new Test 17)
     - `scripts/mindwealth_adapters/sbi_breadth.py` (initialise_arguments fix)
     - `scripts/run_ssi_validation_suite.py` (Test 17 registered)
     - `docs/ssi_validation/SIGNOFF.md` (full status table + decision items)
     - `docs/ssi_validation/17_trendpulse_deterioration.md` (new doc stub + data gap note)
     - `macro_intelligence/analysis/ssi_validation/` (new 20260606 artifacts for Tests 5,6,12,14,15,16,17)

9. **Implement Macro Regime v2 end-to-end experiment program (Parts A–I + FM track)** — SUCCESSFUL
   - Summary: Built and ran full experiment suite per consolidated v2 plan. Added shadow v2 regime labels (`macro_regime_log_v2`), emission vector backfill, FM percentile band analysis (X-FM-1..5), Parts A–G experiments, Monte Carlo combo cancel probability (Part E), HMM prototype + regime_backtest (Part D research-only), Part H 298-combo pipeline re-run (132 survivors, 62 promotion candidates), and master report. Fixed nightly `generic_combo_watch` prefilter bug (`generic_hit_rate` + full var signature). Key FM findings: extreme short 60% SPX up at 3m (n=35); extreme long 82% SPX down at 3m; Combo B 79.8% SPX higher at 3m (n=89). TWY_ROC Apr 2025 anchor passes (−0.55pp DOVISH). Production `regime_rules.py` unchanged (shadow-only until Rohit sign-off).
   - Files changed:
     - `scripts/run_regime_v2_experiment_suite.py` (created)
     - `src/macro_intelligence/analysis/regime_experiments/` (created: run_all, fm_events, metrics, shadow_backfill, report_builder, hmm_prototype, regime_backtest)
     - `src/macro_intelligence/engine/regime_v2_shadow.py` (created)
     - `src/macro_intelligence/engine/combo_cancel_probability.py` (created)
     - `src/macro_intelligence/engine/hit_rates.py` (added `generic_hit_rate`)
     - `src/macro_intelligence/engine/prefilter.py` (fixed var signature lookup)
     - `src/macro_intelligence/jobs/nightly_run.py` (prefilter sig fix)
     - `src/macro_intelligence/db/migrate.py` (v2 table DDL)
     - `tests/test_regime_v2_experiments.py` (created)
     - `docs/ssi_validation/MACRO_REGIME_V2_EXPERIMENT_REPORT.md` (created)
     - `macro_intelligence/analysis/regime_v2_experiments/*.json` (10 artifact files + manifest)
