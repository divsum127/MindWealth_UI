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

4. **Remove "Generated HH:MM ET" timestamp from PDF/HTML report header** — SUCCESSFUL
   - Summary: Removed `generated_et` field from `build_briefing_sections()` and stripped it from both the HTML subtitle bar and the PDF header Paragraph. All 4 tests pass.
   - Files changed: `src/macro_intelligence/output/briefing_renderer.py`

2. **Analyze macro regime v2 mail PDF and create summary** — SUCCESSFUL
   - Summary: Read Rohit's consolidated macro regime system v2 email (8 pages). Created structured summary in docs/ssi_validation. Renamed source PDF from `Threshold experiments mail.pdf` to `Macro_Regime_System_v2_Consolidated_Plan_Mail.pdf`.
   - Files changed:
     - `/home/ubuntu/uiv2/git/MindWealth_UI/docs/ssi_validation/MACRO_REGIME_V2_CONSOLIDATED_PLAN_SUMMARY.md` (created)
     - `/home/ubuntu/uiv2/git/MindWealth_UI/macro_intelligence_docs/Macro_Regime_System_v2_Consolidated_Plan_Mail.pdf` (renamed from `Threshold experiments mail.pdf`)

5. **Implement Macro Regime v2 end-to-end experiment program (Parts A–I + FM track)** — SUCCESSFUL
   - Summary: Built and ran full experiment suite per consolidated v2 plan. Added shadow v2 regime labels, emission vector backfill, FM percentile band analysis (X-FM-1..5), Parts A–G experiments, Monte Carlo combo cancel probability, HMM prototype + regime_backtest (research-only), Part H 298-combo pipeline re-run, and master report. Fixed nightly generic combo prefilter bug. Key FM findings: extreme short 60% SPX up at 3m; extreme long 82% SPX down at 3m; Combo B 79.8% SPX higher at 3m. TWY_ROC Apr 2025 anchor passes. Production regime_rules.py unchanged.
   - Files changed:
     - `scripts/run_regime_v2_experiment_suite.py`
     - `src/macro_intelligence/analysis/regime_experiments/` (8 modules)
     - `src/macro_intelligence/engine/regime_v2_shadow.py`
     - `src/macro_intelligence/engine/combo_cancel_probability.py`
     - `src/macro_intelligence/engine/hit_rates.py`, `prefilter.py`
     - `src/macro_intelligence/jobs/nightly_run.py`
     - `src/macro_intelligence/db/migrate.py`
     - `tests/test_regime_v2_experiments.py`
     - `docs/ssi_validation/MACRO_REGIME_V2_EXPERIMENT_REPORT.md`
     - `macro_intelligence/analysis/regime_v2_experiments/*.json`
