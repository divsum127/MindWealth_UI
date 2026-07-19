# MindWealth UI — Job Status Details

Implementation detail log for MindWealth UI (`/home/ubuntu/uiv2/git/MindWealth_UI`).

This file captures minute-level implementation context for each completed task:
- Assumptions made
- Things deferred or left for future improvement
- Edge cases identified but not handled
- Architecture/design decisions and trade-offs
- Caveats for the next developer

---

---

### 2026-07-18 — Portfolio cluster sizing fix

**Assumptions:** Cluster `budget_pct` values (summing to 100%) apply to the **equity ceiling** (`deployed_cap_usd`), not full $100M notional — matches user expectation that all cluster sizes are fractions of deployed capital (e.g. $80M at 80% ceiling).

**Implementation:** Two-pass sizing — pass 1 scores positions and buckets by cluster; pass 2 splits each cluster's `budget_usd` by `_cluster_rank_weight` (BQ `adj_share` + 0.10 MULTI-SIG boost). Last eligible position in each cluster absorbs rounding remainder so `deployed_usd == budget_usd` exactly.

**Deferred:** If a cluster has zero eligible positions, its budget stays undeployed (cash rises). Empty-cluster redistribution not implemented.

**Edge cases not handled:** Duplicate ticker rows in same cluster each get a proportional slice (by design — one row per signal). Global scale when total cluster budgets exceed ceiling is unnecessary now because budgets are defined on ceiling directly.

**Caveats:** `budget_pct` label still reads as "% of portfolio" in UI mock but dollar cap is % of equity ceiling; confirm with product if display should say "% of deployed" instead.

---

### 2026-07-18 — AI Analyst backend (Overwatch)

**Assumptions:** In-process SSE bus requires single uvicorn worker. Degradation uses weekly FWD win-rate from forward_testing CSVs. System health Claude/Tavily probes run live when keys configured.

**Deferred:** Nuxt BFF migration to call new endpoints directly (separate `MindwealthUI_Vue` repo). Redis pub/sub SSE upgrade if multi-worker needed. Google Sheets sync marker file not yet written by conviction pipeline.

**Edge cases:** India CSV check returns fail when path missing. Portfolio booked-loss alerts run pattern analysis against full forward_testing frame (may be empty). `scan_and_publish_new_alerts` dedup is fingerprint-based, not TTL.

**Decisions:** Spec 60% watch/breach tiers (not legacy 61%+monthly decline). `historical_analogs` written for dominant combo only in nightly JSON. System health admin-gated via JWT `require_admin`.

**Prod impact:** New cron lines via `install_aws_cron_dual.sh`; runtime `overwatch_store/alert_state.json`; confirm API systemd `workers=1`.

---

**Context:** Chat **d2**; report section codes **A2** (curve_regime), **F2/F2a/F4** (inversion + steepening rules). Momentum `STEEPENING` tier is week-to-week; slow post-2022 grind can read **NORMAL** on simple 4wk steepen while narrative keeps post-inversion steepening active.

**Proposed field:** `post_inversion_steepening` boolean alongside `curve_regime_v2` — does **not** replace momentum tier.

**Recommended ON:** First Friday after formal inversion (T10Y2Y &lt;0 for ≥4wk) ends, where spread ≥0 and post-trough `steepen_4wk_bps` ≥+15.

**Recommended OFF (Spec A):** spread ≥+80 bps **or** new formal inversion (≥4wk &lt;0). Rejected: spread &lt;+30 for 4wk alone (false OFF Oct 2024; kills May 2025 phase).

**Backfill (1990→present):** 5 inversion episodes, 5 phase ON, 165 phase-active weeks (8.65%). Episode #5 (2022 trough −106 bps) ON 2024-08-30, ongoing 99 weeks at cut. May 2025-05-23: phase ON, post-trough STEEPENING, simple-tier NORMAL.

**Combo A/E:** CURVE not a named leg (A=NFCI/HY/WALCL/CNH; E=CAPE/NFCI/CFTC). Phase flag storage-only → **no leg behaviour change**. Calendar overlap: A 3/174 fires, E 115/514 fires on phase-active Fridays (coincidence, not causal).

**Deferred:** Implementation in `regime_v2_shadow.py` / briefing / API until Rohit sign-off; optional tertiary OFF (spread &lt;30 + neg simple steepen ×8wk).

**Prod impact:** None — research artifacts only under `testing/macro_th_exp/`.

---

### 2026-07-17 — Formal D/E threshold sweep recheck vs live CONFIG

**Assumptions:** Same episode definition as original study (Friday crossing + 5d cooldown); live CONFIG is analysis case #4 for both D and E; followup production_score still valid ranking.

**What ran:** `run_combo_de_followup.py` + `run_combo_de_study.py` against post-promotion CONFIG.

**Result:** PASS — CONFIG_BASELINE == BEST_PRODUCTION_SCORE for D and E; numbers match analysis.md case #4 (D n=46 / 56.52% @1W; E n=10 / 66.67% @12M).

**Fix:** D baseline tagging used hardcoded `legs==3`; changed to `min_of_three` from CONFIG so 2-of-3 live gates are tagged.

**Deferred:** Update stale “1. CONFIG (current production)” section in `de_threshold_test_analysis.md` (still shows pre-promotion gates). Optional: named-combo backfill so live `combo_fires` / hit-rate DB match new gates.

**Prod impact:** none new — validation only; D/E CONFIG promotion migration entries already `[PENDING]`.

---

### 2026-07-09 — Adverse-regime / combo classification API audit (Ahil handoff)

**Assumptions:** “Adverse regime” = day where active named combo’s cheatsheet design intent is bearish or cautionary. Ahil needs a date-indexed series as conditioning flag for Sharpe uplift / portfolio overlay work.

**Key findings:**
- No endpoint returns historical day→active_combo→intent→adverse_flag.
- Closest: `GET /macro/combo/active` (today only), `GET /macro/combos` (A–G status + direction labels, today), `GET /macro/analogs/{id}` (fire dates for one combo, not daily series).
- Data exists: `combo_fires` in `runic.db` (named A–F fires; G sparse/missing historically). Direction metadata in `CONFIG.yaml` `briefing.combo_direction` and `api/services/macro_service._COMBO_STATIC`.
- Direction conflict: `combo_hit_rates.A.direction=bullish` (hit-rate success side) vs `briefing.combo_direction.A=BEARISH` (cheatsheet design intent). Adverse flag must use cheatsheet intent, not hit-rate direction. G is cautionary (`WARNING LEADING` / BEARISH in briefing).

**Deferred:** Implement endpoint or CSV export; confirm with Divyanshu whether “active” = dominant only vs any ACTIVE/CONFIRMED; fill G history if needed; resolve Combo A intent for adverse mapping.

**Edge cases:** Multiple combos active same day (need dominant via PRIORITY); WATCH vs ACTIVE; Combo E CONFIRMED vs ACTIVE; days with no named combo → adverse=false / NEUTRAL.

**Caveats:** Zero prod migration impact (docs/analysis only). `testing/5_regime_uplift/` is empty — Ahil work not started in repo.

**Prod impact:** none — skip `dev_to_prod_migration_todos.md`.

---

### 2026-07-09 — Test 3 adverse-regime CSV export (Ahil)

**Assumptions:** Dominant = `CONFIG.yaml` PRIORITY among ACTIVE-class combos; Friday `combo_fires` forward-filled to `daily_readings` calendar for daily Test 3 conditioning. Combo A FEARFUL from `macro_regime.a_vote` (`FEARFUL` or `TIGHT_MONEY`).

**Output:** `testing/5_regime_uplift/combo_classification_history.csv` — 7,796 daily rows, 602 `adverse_regime=true`, 3,988 with non-empty dominant. Friday-only sibling: `combo_classification_history_fridays.csv`.

**Deferred:** API endpoint; Divyanshu dominant-rule confirmation; regenerate if PRIORITY or adverse map changes.

**Edge cases:** G has no ACTIVE rows in DB (rule present but unused); CONTESTED A excluded; pre-2007-02-02 no combo history → neutral.

**Caveats:** `dominant_rule=CONFIG_PRIORITY_v1` column documents interim tie-break. README in same folder for Ahil.

**Prod impact:** none.

---

### 2026-06-27 — update_trade_data.sh local-only (no git)

**Assumptions:** Prod checkout at `/home/ubuntu/uiv2/git/MindWealth_UI` runs the script via cron; prod data checkout at `uiv2/prod` owns separate on-disk sync.

**Key decisions:** Remove entire git block (`git add .`, commit, push to `main`) rather than scoping adds — data dirs should stay out of git long-term via `.gitignore` (deferred).

**Deferred:** Gitignore `trade_store/`, `chatbot/data/`, `conviction_store/`; mirror script change in `uiv2/prod` when that checkout exists; document prod `git pull` deploy step.

**Edge cases:** GitHub Actions AAII workflow still pushes to `main`; prod pulls may still update `macro_intelligence/data/aaii_*`. Uncommitted local changes in prod tree are no longer accidentally bundled into a data commit.

**Caveats:** Historical data already on `main` remains until cleaned separately; script header comment updated to reflect local-only behavior.

---

### 2026-06-29 — Rename uiv2/dev to uiv2/prod

**Assumptions:** `uiv2/dev` was the prod data-sync checkout referenced by nightly `emailscript.sh`; renaming aligns directory name with prod role.

**Key decisions:** Filesystem `mv` only — no git remote or branch renames. Updated the single runtime reference in `MindWealth/emailscript.sh`.

**Deferred:** If systemd or other deploy scripts later point at `uiv2/prod`, document explicitly; current API/Streamlit services still use `uiv2/git/MindWealth_UI`.

**Caveats:** Cron runs `emailscript.sh` at 22:00 UTC; change takes effect on next run. No service restart required.

### 2026-06-29 — Cursor rules: uiv2/prod read-only guard

**Assumptions:** Both project (`.cursor/rules/mindwealth-ui-repository-rules.mdc`) and global (`~/.cursor/rules/mindwealth-repository-rules.mdc`) rules must stay in sync so any Cursor session blocks prod edits.

**Key decisions:** Split Repository Scope into **Editable** vs **Read-only**; added **Path guard** (prefix check before every write/shell/git op); separate warning flows for accidental vs user-requested prod edits; emergency prod edit only after explicit user confirmation.

**Deferred:** None.

**Caveats:** Rules are advisory — agent must self-check paths; deploy skill remains at `.cursor/skills/prod-pull-and-details/SKILL.md`.

### 2026-06-09 — Create create-understanding-doc Cursor skill

**Assumptions:**
- Skill lives in project `.cursor/skills/` (same pattern as `report-creation`) so MindWealth UI contributors share the workflow.
- User-provided inputs: source spec, status file, optional output directory under `testing/.../understanding_and_research/`.

**Deferred / Left for Future:**
- No PDF export step in skill (user can invoke `report-creation` separately).
- Skill references macro regime example doc but does not auto-run experiments.

**Key Decisions:**
- Mandatory 4-column Q&A: Question | Answered? | Answer | Doubts to ask Rohit Sir (never "Gap" or sign-off language).
- Progressive disclosure: full document skeleton in `TEMPLATE.md`; workflow and rules in `SKILL.md`.
- `disable-model-invocation: true` so skill loads only when explicitly invoked.

**Caveats:**
- Skill encodes Rohit Sir doubt framing from macro_th_exp workstream; other stakeholders may need a parameterized variant later.

---

### 2026-06-09 — Understanding doc Q&A tables separate Answer/Gap with numeric detail

**Assumptions:**
- All numeric values sourced from `experiment_manifest.json` (2026-06-06 run) and `MACRO_TH_EXP_STATUS_ANALYSIS.md`.

**Key Decisions:**
- Standard 4-column Q&A format: Question | Answered? | Answer | Gap.
- Answer column carries evidence (n, hit %, avg returns); Gap column carries what's missing, untested, or blocked.

**Caveats:**
- Wide markdown tables may wrap awkwardly in some viewers; numbers match JSON artifacts.

---

### 2026-06-09 — Expand understanding doc with experiment status per Part A–H

**Assumptions:**
- Experiment artifacts from 2026-06-06 shadow run are authoritative for done/results unless production wiring noted otherwise.
- FM Q&A from `additional_details.md` treated as extension of plan scope (Section 14).

**Deferred / Left for Future:**
- Re-run experiments after CONFIG B4 fixes — doc notes blockers only.
- Tavila step 7 and HMM Sharpe/drawdown metrics still gaps in experiment output.

**Edge Cases Not Handled:**
- Master report hit-rate label inconsistency for bearish signals — doc points readers to raw JSON.

**Key Decisions:**
- Three-block format per subsection: What we did / Results / Questions answered.
- Section 14 consolidates Rohit FM questions separate from Parts A–H.

**Caveats:**
- Part H regime tags used legacy labels — doc flags re-tag with v2 before sign-off.

---

### 2026-06-09 — Macro Regime System v2 consolidated plan plain-English understanding doc

**Assumptions:**
- User requested the doc in `testing/macro_th_exp/understanding_and_research/` (directory did not exist; created alongside the PDF workstream).
- Existing experiment status (`MACRO_TH_EXP_STATUS_ANALYSIS.md`) and plan summary (`docs/ssi_validation/MACRO_REGIME_V2_CONSOLIDATED_PLAN_SUMMARY.md`) were used for cross-reference on what is already run vs production.

**Deferred / Left for Future:**
- No code implementation — documentation-only task per user request.
- User may want a PDF export via report-creation skill; not requested.

**Edge Cases Not Handled:**
- Doc does not duplicate full numeric threshold tables from Part F — points to formal defs and existing summary for detail.

**Key Decisions:**
- Structured as glossary-first, then part-by-part walkthrough, then deliverables checklist and sequencing — optimized for a developer new to macro regime vocabulary.
- Included link to shadow experiment status so reader knows plan vs current production gap.

**Caveats:**
- Understanding doc is interpretive; authoritative spec remains the PDF and `MACRO_REGIME_V2_CONSOLIDATED_PLAN_SUMMARY.md`.

---

### 2026-06-07 — Log macro report follow-up todos (MRU-01..03)

**Assumptions:**
- MRU-01 and MRU-02 can share one analysis script with two output sections.
- MRU-03 requires a real cancelled Combo C episode in production DB — date TBD at run time.

**Deferred / Left for Future:**
- All three MRU items remain open until scripts run and smoke test passes.

**Key Decisions:**
- IDs `MRU-01`..`MRU-03` in main job file; detailed acceptance criteria in `MACRO_REPORT_UPDATE_TODO.md`.

---

### 2026-06-07 — Macro report pipeline + engine update (11-point review)

**Assumptions:**
- FRED `BAMLH0A0HYM2` values are in percent (4.0 = 400bps); `_hy_oas_bps()` multiplies by 100 when value < 50.
- Combo E primary hit rate at 12m is the correct display even when DB has sparse 12m forward returns (mature fires only).
- `CANCELLED` shown when `combo_c_cancel.cancel_date` is set and Combo C is not in active_combos.

**Deferred / Left for Future:**
- G→B cascade timing analysis script on production `combo_fires`.
- Historical HY OAS at each Combo B fire since 1990 (threshold audit).
- CFTC percentile window still 156-week rolling in CONFIG — may need full-history for structural combos per manager note.

**Edge Cases Not Handled:**
- Combo C cancel_date persists after cancel — re-entry requires manual DB reset of `combo_c_cancel` row.
- Watch combos still show DB all-time hit rates (not live partial-leg rates).

**Key Decisions:**
- Centralized horizons in `combo_metadata.py` + `CONFIG combo_hit_rates` rather than scattering per renderer.
- PPI explicitly excluded from cancel CPI leg (already config flag; cancel code never called PPI).
- Claude narrative constrained by prompt; Python `dominant_reason` is the authoritative numeric summary.

**Caveats:**
- Re-run nightly job on production to verify CANCELLED row if Combo C episode has completed cancel clock.
- `evaluate_combo_b_at_date()` now requires vix_pctile and hy_pctile kwargs (defaults 85 for backward compat in tests).

---

## Detail Entry Format

```
### [DATE] — [TASK TITLE]

**Assumptions:**
- ...

**Deferred / Left for Future:**
- ...

**Edge Cases Not Handled:**
- ...

**Key Decisions:**
- ...

**Caveats:**
- ...
```

---

## 2026-06-06

---

### 2026-06-06 — Create MindWealth_UI repository operating rules and todo log

**Assumptions:**
- Tasks would be tracked per-date with sequential numbering.
- A single flat markdown file would be sufficient for tracking.

**Deferred / Left for Future:**
- No formal TODO/DONE split was implemented in this initial version (addressed in a later task on the same date).
- No distinction between the summary log and detailed implementation notes (also addressed later).

**Edge Cases Not Handled:**
- No handling for tasks spanning multiple dates.

**Key Decisions:**
- Used `alwaysApply: true` in the rule frontmatter so it applies without needing explicit @mention.

**Caveats:**
- The original path `.cursor/mindwealth_ui_repo_todos.md` was later migrated to `docs/mindwealth_ui_job_status.md`.

---

### 2026-06-06 — Analyze macro regime v2 mail PDF and create summary

**Assumptions:**
- The email PDF was treated as the canonical source for the v2 macro regime system design.
- Numbering and section labels in the PDF were assumed to be finalized.

**Deferred / Left for Future:**
- Full implementation of each phase described in the v2 plan is pending.
- Threshold calibration values in the PDF have not yet been validated against live data.

**Edge Cases Not Handled:**
- PDF parsing was manual (read-only); no automated extraction pipeline exists yet.

**Key Decisions:**
- Placed summary under `docs/ssi_validation/` to keep it near related validation docs.

**Caveats:**
- The source PDF was renamed; any references to `Threshold experiments mail.pdf` should be updated to `Macro_Regime_System_v2_Consolidated_Plan_Mail.pdf`.

---

### 2026-06-06 — Runic PDF Quality & Narrative Upgrade

**Assumptions:**
- `narrative_max_tokens=1200` is sufficient for a 5-paragraph narrative without hitting Claude context limits.
- Tavily macro headlines provide useful additional context beyond the signal data already in the prompt.
- reportlab Platypus is the correct long-term renderer for PDF output.

**Deferred / Left for Future:**
- PDF table column widths are hardcoded; dynamic sizing based on content length not yet implemented.
- The `fetch_macro_headlines()` call uses a generic Tavily query — a more targeted query set per regime type would improve signal relevance.
- HTML output is a bonus feature; a dedicated HTML template (Jinja2) would be cleaner than the current inline string approach.
- No caching of Tavily results; repeated runs on the same day re-fetch headlines.

**Edge Cases Not Handled:**
- If Tavily API is unavailable, `fetch_macro_headlines()` returns an empty string silently — no retry or alerting.
- Very long regime variable names may overflow the 3-column regime grid layout.
- Claude API timeout is not explicitly handled; relies on default SDK timeout.

**Key Decisions:**
- Chose dark navy (#0A1628) as primary colour to align with MindWealth brand aesthetic.
- Green for ACTIVE combos and amber for WATCH combos — matches trading signal convention (green=go, amber=caution).
- `EXTREME` tier coloured red, `HIGH` tier amber in the variable dashboard for visual urgency hierarchy.

**Caveats:**
- `briefing_renderer.py` now tightly couples PDF and HTML rendering; if they diverge significantly in future, consider splitting into separate renderer classes.
- Tests only perform smoke checks (colour values present in output); no content-level narrative assertion yet.

---

### 2026-06-06 — Remove "Generated HH:MM ET" timestamp from PDF/HTML report header

**Assumptions:**
- Timestamp was cosmetic and not referenced downstream by any parsing logic.
- Removing it from `build_briefing_sections()` is sufficient; no other call sites generate this field.

**Deferred / Left for Future:**
- If a timestamp is needed in future (e.g. for archival), consider adding it to the footer instead of the header.

**Edge Cases Not Handled:**
- No check for whether downstream consumers (email templates, Slack bot) relied on the timestamp string.

**Key Decisions:**
- Removed the field entirely rather than making it optional, to keep the data model clean.

**Caveats:**
- All 4 tests passed post-removal; no regression observed.

---

### 2026-06-06 — Update repository rules, rename todo to job status file, add TODO/DONE sections, create job status details file

**Assumptions:**
- `mindwealth_ui_job_status.md` is a sufficiently descriptive name for the combined TODO/DONE tracker.
- The old `.cursor/mindwealth_ui_repo_todos.md` file can remain in place as a legacy reference but is no longer the active tracking file.
- The details file (`mindwealth_ui_repo_job_status_details.md`) should be in `docs/` alongside the job status file for discoverability.

**Deferred / Left for Future:**
- The old `docs/mindwealth_ui_repo_todo_details.md` and `.cursor/mindwealth_ui_repo_todos.md` files are now superseded but not deleted — consider archiving or deleting them in a future cleanup.
- A script to auto-move TODO entries to DONE upon task completion would reduce manual overhead.

**Edge Cases Not Handled:**
- No enforcement mechanism if the agent skips updating the tracking files.
- Tasks that were in-progress at time of migration are not represented in the TODO section.

**Key Decisions:**
- Two-file split (status vs. details) keeps the job status file scannable and fast to update, while the details file holds deep context without cluttering the summary.
- Kept date-based numbering consistent with prior convention.
- Rules file updated with explicit "check TODO first, move to DONE" instruction to prevent duplicate entries.

**Caveats:**
- The `alwaysApply: true` rule means every agent session will be instructed to update both files — ensure file paths remain stable.
- The `global_repo_todos.md` at `/home/ubuntu/.cursor/global_repo_todos.md` is a separate cross-repo log and must also be updated per the global rules.

---

## 2026-06-06 — Task 1: Create report-creation Cursor skill

**Implementation Assumptions:**
- Stored as a project-level skill under `.cursor/skills/report-creation/SKILL.md` (not personal `~/.cursor/skills/`) so it is shared with anyone working in this repo.
- `disable-model-invocation: true` set so the skill only activates when explicitly invoked, not ambiguously from context.
- "2-3 naturalistic imperfections" was interpreted as a soft cap — enough to read human, not enough to undermine credibility.
- Em dash prohibition (—) was implemented as a hard rule with explicit replacement alternatives listed in the skill.
- "Tabular format preferred" was interpreted as Markdown tables being the default data format, with the skill allowing deviation only when data is genuinely unavailable.

**Deferred / Left for Future:**
- A validation/linting script that scans generated report text for em dashes before finalising could be added as a utility script in the skill directory.
- Could add domain-specific templates (e.g. a MindWealth nightly briefing template, a portfolio analysis template) as additional reference files.

**Edge Cases Not Handled:**
- Reports sourced from external data pipelines where numbers are unavailable at write time — skill instructs agent to state the limitation, but does not provide a template for how to format that caveat.
- Reports containing charts or images — skill focuses on Markdown tables and does not address image-based data presentation.

**Key Decisions:**
- Chose project-level placement (`.cursor/skills/`) over personal (`~/.cursor/skills/`) since the rules are MindWealth-specific and should apply to any collaborator.
- Used a checklist section as the enforcement mechanism rather than repeating rules inline — keeps the skill concise and scannable.
- Provided explicit before/after examples for each rule to reduce ambiguity about what "correct" looks like.

**Caveats:**
- The imperfection rule (Rule 1) requires the agent to exercise judgment — there is no automated way to enforce the right number or naturalness of errors. The checklist is the only guardrail.

---

### 2026-06-06 — Fix Combo F week counter — episode start vs last fire

**Assumptions:**
- The 26-week active window starts from the first fire after the most recent week SPX was below the 50WMA, which is a clear, unambiguous episode boundary.
- `spx_with_50wma()` is already loaded by the detection path so calling it again in `_combo_f_weeks` is acceptable (cached via Yahoo pull).

**Deferred / Left for Future:**
- If SPX briefly dips below then recovers within the same Friday-to-Friday window, the episode might restart unnecessarily. A ≥2-week below threshold could make this more robust.
- No test added for `_combo_f_weeks` yet; should be added to `tests/test_combo_detector.py`.

**Edge Cases Not Handled:**
- If there is no F fire at all in DB after the last below-week (e.g., first ever run after a dip), function returns None and combo is treated as a new entry — correct behavior.

**Key Decisions:**
- Used `first fire after last below-week` rather than `first fire after last above-cross` because the DB may not have a fire on the exact cross week (CFTC may not have been ≤50 that specific Friday).

**Caveats:**
- The nightly DB still writes a fresh row every Friday with `duration_weeks=1` because the old calculation persists in the write path (`nightly_run.py` calls `detect_named_combos` which now returns the correct week, but DB inserts from prior runs are already wrong). New runs from today onward will have correct week values stored.

---

### 2026-06-06 — Implement Macro Regime v2 end-to-end experiment program (Parts A–I + FM track)

**Assumptions:**
- Shadow v2 labels (`regime_v2_shadow.py`) are sufficient for experiments without modifying production `regime_rules.py` until Rohit sign-off.
- FRED series (T10Y2Y, DGS2, FYFSD) and existing `runic.db` backfill provide adequate history for 1990→today analysis.
- FM percentile bands (<15th, >85th, 25th–75th) map cleanly to Combo B/D territory and Rohit's contrary-indicator question.
- Part H combo discovery can run with `use_claude=False` for engineering validation; Claude narratives deferred to Rohit review session.
- Evidence tagging (STATISTICAL n≥5, MECHANISM+ANALOG for F4) follows Part I of the consolidated plan.

**Deferred / Left for Future:**
- Production swap from legacy 7-state fed_cycle / 2-state liquidity to v2 shadow labels (GO pending Rohit review).
- Part H Claude/Tavily narratives for 132 survivors + 62 promotion candidates (`--use-claude` flag exists but not run).
- Wire `combo_cancel_probability()` to nightly briefing PDF and dashboard.
- Daily emission vector storage in production nightly job (C1 backfill done; live job not wired).
- Production HMM layer — deferred 6 months per PDF until live vectors accumulate.
- HSMM dwell-time (Part D phase 2), CAPE triple-storage full sweep (B5 partial), fiscal caveat A5 depends on FYFSD series quality.
- Beta filter 55% vs 60% human decision per combo — both rates reported in combo discovery; no auto-selection.
- Named combo promotion to Combo H+ requires Rohit written approval.

**Edge Cases Not Handled:**
- `backfill_regime_v2` silently skips dates where `build_regime_v2` throws (no error log aggregation).
- FM events use nearest-prior regime from shadow table when exact Friday missing.
- Combo C cancel calibration (E2) uses `status=CANCELLED` only — no dedicated `cancelled` column in schema.
- B4 window audit flags CONFIG.yaml `pctile_window: full` vs expected `rolling_3y` for flow vars — structural vars use `full` which is intentional but audit may show mismatches.
- Part H re-run uses legacy regime tags on existing combo_fires, not yet re-tagged with v2 shadow JSON.

**Key Decisions:**
- Hybrid approach: minimal schema additions (`macro_regime_log_v2`, `emission_vectors`) + analysis scripts, no production nightly refactor.
- Module-level FRED caching in `regime_v2_shadow.py` to keep ~1,900 Friday backfill under ~2 minutes.
- FM regime slices read from shadow table post-backfill rather than calling `build_regime_v2` per event.
- Cancel probability uses `math.erf` normal CDF — no scipy dependency.
- Prefilter fix: pass full `var1+var2+var3` signature to `apply_prefilter`, not first character only.
- HMM prototype uses k-means-style clustering on mean daily percentile vector — labeled research-only, not production HMM.

**Caveats:**
- Master report: `docs/ssi_validation/MACRO_REGIME_V2_EXPERIMENT_REPORT.md`; artifacts: `macro_intelligence/analysis/regime_v2_experiments/`.
- Re-run: `.venv/bin/python scripts/run_regime_v2_experiment_suite.py` (~2 min); add `--skip-h-part` to skip combo discovery.
- Extreme short FM 3m hit rate (60%) is below Rohit's cited ~87.5% on 8 Combo B instances — aggregate band crossings ≠ Combo B fires; Combo B alone shows 79.8%.
- Do not edit `.cursor/plans/macro_regime_v2_experiments_d80321d2.plan.md` per user instruction.

---

### 2026-06-09 — Macro regime and threshold experiments report (report-creation skill)

**Assumptions:**
- All Q&A content sourced from `understanding_and_research/Macro_Regime_System_v2_Understanding.md` "Questions we were looking for" tables across Parts A–H, FM track (§14), master Q&A (§15), plus SSI threshold classification from `SSI_OPEN_QUESTIONS_SUMMARY.md`.
- Experiment numbers from 2026-06-06 shadow run remain authoritative unless CONFIG B4 re-run changes them.
- Report written in first person per report-creation skill; no production code changes.

**Deferred / Left for Future:**
- Combo B confirmed-only re-slice (called out in report doubts).
- CONFIG B4 window fix + experiment suite re-run.
- Tavila step 7 on 62 promotion candidates.
- PDF regime footnotes once v2 labels swap to production.

**Edge Cases Not Handled:**
- SSI tests 6/12/15 individual result tables abbreviated in report (classification summary only).
- FM report hit-rate terminology caveat noted in prior analysis but not repeated in every FM table.

**Key Decisions:**
- Single consolidated report covering both regime v2 and SSI threshold tracks in one document for Rohit review.
- Used descriptive section headings per skill (no Executive Summary, Conclusion, etc.).
- Em dashes replaced with colons in subsection titles for skill compliance.

**Caveats:**
- PDF: 68,323 bytes via `export_pdf.py`.
- Companion docs remain: `MACRO_TH_EXP_STATUS_ANALYSIS.md`, `MACRO_TH_EXP_PLAN.md`, understanding guide.

---

### 2026-06-09 — QUESTION_DETAILS.md plain-English Q&A reference

**Assumptions:**
- Content mirrors active sections in `Macro_Regime_Threshold_Experiments_Report_2026-06-09.md`.
- Each Q block uses template: why question exists, what was run, answer, terms, doubt.

**Deferred / Left for Future:**
- PDF export of QUESTION_DETAILS.md if requested.
- Sync when report updated after CONFIG B4 re-run or Combo B confirmed-only slice.

**Key Decisions:**
- Filename `QUESTION_DETAILS.md` in `testing/macro_th_exp/`.
- 44 numbered questions (Q1–Q44) plus 18-item consolidated doubts table.

**Caveats:**
- Long-form reference; not a substitute for experiment JSON audit.

---

### 2026-06-07 — Macro threshold & regime experiment status analysis (macro_th_exp)

**Assumptions:**
- 2026-06-06 experiment run artifacts in `macro_intelligence/analysis/regime_v2_experiments/` remain the authoritative backtest unless CONFIG B4 window fix triggers a re-run.
- Rohit's FM claims use "FM wrong" = contrary outcome (SPX up when FM extreme short; SPX up when FM extreme long expecting correction). JSON stores directional hit rates directly; report §2 sometimes quotes (1 − hit_rate) for bearish legs.
- Combo B "89 fires" includes WATCH rows with partial legs; Rohit's "8 confirmed instances" refers to stricter 3/3 leg alignment — called out as follow-up experiment R-1.
- Regime slices use shadow v2 labels (`macro_regime_log_v2`); production briefing still shows legacy fed_cycle.

**Deferred / Left for Future:**
- Re-run X-FM-2 with ACTIVE-only Combo B filter (R-1).
- 5×5 regime heatmaps for combos D and F (R-2).
- CONFIG B4 window audit fix and experiment suite re-run.
- Fix MACRO_REGIME_V2_EXPERIMENT_REPORT.md §2 hit-rate label inconsistency.
- Part H re-tag with v2 regimes before Rohit promotion review.
- Production wiring (TWY_ROC, emission_vectors, cancel prob, v2 label swap) pending Rohit sign-off per plan P2.

**Edge Cases Not Handled:**
- FM band crossings pre-2010 CFTC TFF era under-represented.
- Combo C n=4 too small for regime isolation.
- VIX suppressed lead rate (8.5%) far below plan's ~50% historical claim — needs methodology check.
- F4 grid win rates contradict statistical promotion; correctly gated as MECHANISM+ANALOG only.

**Key Decisions:**
- Documented two parallel tracks: regime v2 (this PDF) vs SSI thresholds (`testing/ssi_th_exp/`).
- FM extreme short validated directionally via Combo B (79.8%) but not via raw band alone (60%).
- FM moderate band confirmed as non-actionable (76% SPX up ≈ equity drift, not FM edge).
- HMM production remains DEFER until 6 months live emission vectors post sign-off.

**Caveats:**
- Analysis lives in `testing/macro_th_exp/`; master experiment report unchanged.
- User asked for docs in macro_th_exp directory only — no changes to production code in this task.

---

### 2026-06-06 — Task 7: SSI Data Gap + NAAIM Backfill + build_ssi_history Fix

**Assumptions:**
- NAAIM "Data since Inception" Excel URL pattern is stable for the current month: `https://naaim.org/wp-content/uploads/{YYYY}/{MM}/USE_Data-since-Inception_{YYYY}-{MM}-{DD}.xlsx`. The URL found was for the 2026-06-03 update.
- The Mean/Average column in the Excel file corresponds to the `exposure` field expected by `naaim_pull.py`.
- Two duplicate dates in the NAAIM Excel (2006-07-05 appeared twice with slightly different values: 19.44 vs 19.444444). Resolved by keeping the last occurrence.
- The SSI score formula uses only 4 weighted components: `hyg_lqd` (0.30), `dbmf_beta` (0.25), `cnn_fg` (0.25), `vix_ratio` (0.20). All other series in `load_all_series()` are auxiliary.

**Architecture decisions:**
- Changed the NaN gate in `build_ssi_history` from "all series must have data" to "only weighted components must have data." This is the semantically correct behavior since auxiliary series (NAAIM, AAII, breadth metrics) are NOT part of the SSI score computation.
- Did NOT modify `naaim_pull.py` to automatically fetch the historical Excel — that would risk re-downloading 86KB on every run. The cache is now pre-populated with full history.
- Did NOT try to extend `pct_above_200dma`, `mcclellan`, or `nh_nl_ratio` because (a) they're not SSI weighted, (b) extending would require bulk yfinance downloads for 500+ tickers over many years, and (c) they're not blocking any test after the code fix.

**Things deferred:**
- `naaim_pull.py` does not yet automatically try the "Data since Inception" Excel as a fallback. Currently the scraper only gets the last 10 rows from the HTML table. This means if the server is down for 3+ months, the cache will still be fresh but the scraper won't self-heal a future gap. A future improvement: add the Excel URL as a fallback in `_scrape_naaim()`.
- The NAAIM Excel URL changes monthly (the date in the filename updates). A future improvement: parse the NAAIM page to find the current Excel link dynamically rather than hard-coding the URL.
- `pct_above_200dma`, `mcclellan`, and `nh_nl_ratio` caches remain short (~12-16 months). They will grow organically over time. If long historical breadth data is needed for a future test, yfinance can provide it using `start`/`end` parameters instead of `period="2y"`, but downloading 500 tickers × many years is a heavy operation.

**Edge cases not handled:**
- The NAAIM Excel file contains two rows for 2006-07-05. The dedup logic keeps the last (19.44000); the slightly different 19.444444 value is dropped. The difference is negligible.
- The DBMF ETF launched 2019-05-09, so SSI history cannot go further back than that date even with all other data extended. Going back to 2015 would require replacing `dbmf_beta` with an alternative CTA proxy for pre-2019 dates.

**Component date ranges as verified (2026-06-06):**
- `hyg_lqd`: 2010-01-04 to 2026-06-05 (4,131 rows)
- `vix_ratio`: 2007-01-03 to 2026-06-05 (4,887 rows)
- `cnn_fg`: 2018-02-01 to 2026-06-06 (3,052 rows)
- `dbmf_beta`: 2019-05-09 to 2026-06-05 (1,779 rows)
- `naaim_exposure`: 2006-07-05 to 2026-06-03 (1,039 rows) — BACKFILLED
- `aaii_spread`: 1987-07-24 to 2026-06-04 (2,026 rows)
- `skew`: 1990-01-02 to 2026-06-05 (9,100 rows)
- `pct_above_200dma`: 2025-04-17 to 2026-06-03 (283 rows)
- `mcclellan`: 2025-02-13 to 2026-06-05 (330 rows)
- `nh_nl_ratio`: 2025-06-03 to 2026-06-05 (255 rows)

---

### 2026-06-07 — Data Sources Audit + Master Doc Sources Reference

**Audit findings by variable:**

| Variable | Primary Source | Fallback | Bug in old doc? |
|----------|---------------|----------|-----------------|
| NFCI | FRED API `NFCI` | FRED public CSV | No — ticker correct, no URL |
| HY | FRED API `BAMLH0A0HYM2` | FRED public CSV | No — ticker correct, no URL; HY 3yr limit documented |
| WALCL | FRED API `WALCL` | FRED public CSV | No |
| CNH | Yahoo `USDCNH=X` | FRED `DEXCHUS` | No — fallback mentioned |
| WTI | Yahoo `CL=F` | FRED `DCOILWTICO` | **YES** — fallback omitted in variable description |
| VIX | Yahoo `^VIX` | None | No |
| VXTS | Yahoo `^VIX3M` ÷ `^VIX`, fallback `^VXV` | None | No — well documented |
| CFTC | CFTC.gov TFF ZIP files | Local cache | No URL given in variable description |
| CURVE | FRED API `T10Y2Y` | FRED public CSV | No |
| CPI actual | BLS API `CUSR0000SA0` | FRED `CPIAUCSL` | No |
| CPI consensus | **Trading Economics** (primary) | Investing.com (PROXY only) | **YES** — doc said Investing.com was primary |
| GSR | Yahoo `GC=F` ÷ `SI=F` | None | No |
| CAPE | multpl.com scrape | Local `cape_history.csv` | No — site mentioned, exact URL/table not given |

**Key decisions:**
- New section "## 2b. Data Sources Reference" added between variables list and combos list. This is the canonical operator reference.
- CPI consensus doc corrected in two places: inline variable description AND the data layer table (line 501).
- WTI variable description updated to include FRED DCOILWTICO fallback.
- All 12 variables now have: API endpoint URL, FRED series ID / Yahoo ticker / scrape URL, exact page element, fallback, history start, publication frequency, units.

**Deferred:**
- CFTC main page URL (`cftc.gov/MarketReports/TradersinFinancialFuturesReports/index.htm`) and exact ZIP URLs now documented in the new section but NOT yet added inline to the Variable 8 description. Variable 8 still only says "Downloaded directly from CFTC.gov". Could add exact URLs to the inline description as well — deferred since the reference section covers it.
- The `cpi_pull.py` file description in the data layer table is still generic ("Orchestrates CPI collection"). Could be expanded to name Trading Economics explicitly.
- `cftc_fm`: 2010-06-15 to 2026-05-26 (833 rows)

**SSI history progression:**
- Before fixes: 83 rows (2026-03-25 to 2026-06-06)
- After NAAIM backfill only: 378 rows (2025-06-03 to 2026-06-06)
- After code fix: 2,565 rows (2019-06-07 to 2026-06-06)

---

### 2026-06-06 — Full Combo A–G Audit Against MACRO_INTELLIGENCE_MASTER.md

**Audit results — all 7 named combos as of 2026-06-06:**

| Combo | Spec Rule | Reading | Expected | Actual | Match |
|-------|-----------|---------|----------|--------|-------|
| A | 2+ of {NFCI,HY,WALCL,CNH} at RARE+ | All 4 NORMAL | INACTIVE | INACTIVE | ✅ |
| B | ALL: VIX≥25, HY≥400bps, CFTC≤15th | VIX=21.5, HY=274bps, CFTC=5th pctile | WATCH (1/3) | WATCH | ✅ |
| C | ALL: WTI≥10%, CPI≥0.2pp, WALCL flat | WTI=−5.1%, CPI=0.14pp | INACTIVE | INACTIVE | ✅ |
| D | ALL: VXTS≥1.10, CFTC≥85th, VIX<18 | VXTS=1.014, CFTC=5th, VIX=21.5 | INACTIVE | INACTIVE | ✅ |
| E | 2+ of: CAPE≥28, NFCI≤−0.3, CFTC≥80th | CAPE=42.7✅, NFCI=−0.494✅, CFTC=5th❌ | CONFIRMED (2/3) | CONFIRMED | ✅ |
| F | Above 50WMA+3%, CFTC≤50th, ≤26wks | 9.1% above WMA, CFTC=5th, wk10 | ACTIVE Wk10 MEDIUM | ACTIVE Wk10 MEDIUM | ✅ |
| G | ALL: VXTS<1.00, HY 4wk≥+30bps, VIX≤20 | VXTS=1.014, HY=−7bps, VIX=21.5 | INACTIVE | INACTIVE | ✅ |

**Priority table verified:** C=100, B=90, F=80, E=70, D=60, G=50, A=40 — exact match to spec.
**Dominant signal:** Combo F (active, priority 80), outranks E (70). TACTICAL_BRAVE direction. ✅
**CONTESTED routing:** Combo A CONTESTED → WATCH list (not dominant). Correctly handled at line 45 of nightly_run.py. ✅
**PENDING_CFTC_CONFIRM:** Implemented in cftc_pull.py data layer (not combo detector) — surfaces when CFTC data is stale. ✅

**Three spec-vs-code bugs fixed:**

1. **Combo F entry trigger (semantic bug):** Code used `weekly_ret_pct >= 3.0` (weekly % gain) as the new-entry trigger. Spec explicitly states "SPX weekly close was ≥3% *higher than the 50-week moving average*" — a LEVEL comparison, not a return. Changed to `pct_above_wma = (close/wma50 - 1) * 100 >= 3.0`. Practical impact: on Apr 3 entry date, close was only 1.2% above WMA but weekly gain was 3.36%; the CFTC check (92.9% > 50%) correctly blocked that entry. Apr 17 (8.6% above WMA, CFTC 21.2%) was the true entry. Fix ensures future episodes start correctly.

2. **Combo E NFCI boundary (off-by-boundary):** Spec: `NFCI ≤ −0.3`. Code had strict `< −0.3`. If NFCI is exactly −0.300, spec fires but old code wouldn't. Changed to `<= −0.3`. Edge case only (NFCI rarely hits threshold exactly) but fixes spec fidelity.

3. **Combo G VIX boundary (off-by-boundary):** Spec: `VIX ≤ 20`. Code had strict `< 20`. Fixed to `<= 20`. Same edge-case pattern.

**Deferred finding:**
- `_combo_c_weeks()` uses `ORDER BY date DESC LIMIT 1` (most recent fire) as episode start. This is the same week-counter reset bug that was fixed for Combo F. Currently benign (Combo C is INACTIVE), but when C next activates, the week counter will show Week 1 perpetually unless fixed. The fix pattern is to anchor on the first C fire after the last WTI-below-10% date (analogous to F's last-SPX-below-50WMA anchor). Tracked as TODO T-02.

**Assumptions:**
- HY FRED series (BAMLH0A0HYM2) stores values in % (e.g., 2.74 = 274 bps). The `_hy_4wk_change_bps()` function correctly multiplies the difference by 100 to convert to bps. Verified: current reading −7 bps (tightening), so Combo G correctly stays inactive.
- CFTC percentile is computed on a rolling 3-year window (156 weeks), matching the spec's rolling window approach.

---

## SSI Validation — Full Variable Backfill + Bug Fixes (2026-06-06)

### Implementation assumptions
- CNN F&G 2011-2018 gap is unfillable via free public APIs. Alternative.me returns CRYPTO F&G (not CNN stock market F&G). The cache uses crypto as proxy for 2018-2026; this should be documented prominently in any production config.
- CFTC TFF data (FM/RM split) physically starts June 2010 — the TFF format was introduced by CFTC around 2009-2010. Cannot go back to 2006 even though the bulk zip file covers 2006-2016 (it has no FM/RM split pre-2010).
- `forward_return_pct` fix uses strict inequality `end_date > spx.index.max()` — returns None for ALL fire dates where the full forward window hasn't elapsed yet. This means recent fire dates (last 3m/6m/12m depending on horizon) will show n=0 which is correct behavior.

### Things deferred
- Running the breadth data refresh with 5y period takes ~15-20 minutes due to yfinance 500-stock downloads. This was not done in this run — the breadth cache was NOT refreshed (sp500_breadth.py period change will take effect on next pull_all.py run).
- Bollinger + SSI test (Test 12) not re-checked after Part III — would need breadth refresh first.
- CNN F&G reconstruction from components (SPX vs 125-day SMA, McClellan, CBOE P/C, VIX, HY spreads) is possible but complex. CBOE P/C ratio is no longer available on Yahoo Finance. Deferred.

### Edge cases not handled
- The SSI history bottleneck is now DBMF ETF inception (2019-05-09). For periods before 2019, DBMF beta is unavailable and the SSI weighted components would need a different CTA proxy (possible alternatives: PIMCO, managed futures indices, or momentum factor).
- NAAIM data has 1,039 weekly rows from 2006. But the SSI only goes back to 2019 due to DBMF. NAAIM data from 2006-2019 is unused in the current SSI formula.
- `_rolling_pctile_3yr` in `dbmf_beta_study.py` is O(n²) — slow for large series. For 1,779 DBMF rows it took ~30-60 seconds. Acceptable for validation; would need optimization for daily production use.

### Key decisions made
- Used `horizons={"2w": 10, "4w": 20, "8w": 40}` for DBMF (not DEFAULT_HORIZONS with 1w/3m/6m) to match the PDF's specified test horizons.
- OLS regression uses `scipy.stats.linregress` with fallback to manual calculation. p-value from linregress is a two-tailed t-test.
- The `forward_return_pct` fix: returns None when `end_date > spx.index.max()` — strict inequality, not >=. This ensures a fire date exactly at `spx.index.max()` can still compute a return (the 0-day return = 0).

### Caveats for next developer
- The "Alternative.me = CNN F&G" comment in `cnn_fear_greed.py` is WRONG. Alternative.me is the cryptocurrency Fear & Greed index. Update the comment when a better source is found. **This has been fixed in the docstring and inline comments as of 2026-06-06.**
- sp500_breadth.py now downloads 5y of daily data for ~500 stocks. This takes 15-20 minutes and generates ~100MB of data in memory. Set CHUNK_SIZE thoughtfully if changing.
- All validation artifacts are timestamped by run date (e.g. `_20260606.json`). If multiple runs happen on the same day, the later run overwrites. Consider adding HH:MM to the filename for production.

---

## Fix All Self-Fixable Data Gaps (2026-06-06)

### Implementation assumptions
- HY OAS proxy uses FRED `BAA10Y` (Moody's Baa-Treasury spread) calibrated against real ICE BofA HY OAS (2023-2026 overlap, n=153). Linear regression: `HY_OAS = 2.0528 * BAA10Y − 0.1833`. R²=0.40 (moderate). BAA10Y is freely available from FRED without ICE licensing.
- Proxy rows are tagged `signal_tier='PROXY'` in `daily_readings` so they can be excluded from production signals if needed.
- Breadth indicators were returning empty live data due to a critical bug: `compute_daily_breadth_stats` initialized accumulators with `np.full(n, np.nan)` then used `+=` — since `nan + anything = nan`, the result was always NaN and the function always returned an empty series. The live path was silently broken, so all returned data was from the cache CSVs only.

### Things deferred
- With R²=0.40, the BAA10Y proxy for HY OAS has moderate fit. In stress periods (2008-2009, 2020), HY spreads blow out proportionally more than Baa spreads, so the proxy likely underestimates peak OAS. For production use, a more sophisticated proxy (e.g. using HYG option-adjusted yield from Bloomberg) would be preferable.
- CNN F&G history 2011-2018 remains unfillable (no free API for CNN stock market version). Deferred.
- The 9 HY OAS proxy rows from Jan 1997 that have `pctile_rank_3yr=NULL` (first 9 trading days, fewer than 10 points in 3yr window) could be backfilled with the 3yr-start percentile, but this is minor.

### Edge cases not handled
- The `pct_above_200dma` and `nh_nl_ratio` series require 200/252-day warmup. With `period=5y` (from ~Jun 2021), first valid pct_above_200dma is ~Mar 2022, nh_nl_ratio ~Jun 2022. History before these dates remains unavailable unless a different data source (e.g. Stockcharts historical breadth data) is used.
- The BAA10Y proxy is clipped at 1.5% minimum (OAS ≤ 150bps is historically implausible for HY). This may not accurately capture ultra-low-spread regimes if they were to occur.

### Key decisions made
- Chose `BAA10Y` over alternatives (HYG price proxy, HYG 30-day yield) because: (1) BAA10Y is a direct spread measure vs. 10yr Treasury, (2) freely available on FRED without licensing issues, (3) shares similar economic drivers to HY OAS (credit risk premium).
- Fixed `compute_daily_breadth_stats` to track per-row valid-stock counts (`pct_valid_count`, `hl_valid_count`) and use them as denominators instead of the static total. This correctly produces NaN for dates before the MA200/52w rolling windows accumulate enough stocks.
- Used `MIN_STOCKS = max(10, len(valid_syms) // 10)` to require at least 10% of valid stocks to have computed MA200 before reporting pct_above_200dma — prevents artificially small-sample percentages.

### Caveats for next developer
- HY OAS proxy rows in `daily_readings` have `signal_tier='PROXY'`. If the production engine uses `signal_tier` for filtering, ensure PROXY rows are handled correctly (either treated as a data source or excluded from signal generation).
- The breadth CSVs (`pct_above_200dma.csv`, `nh_nl_ratio.csv`, `mcclellan_oscillator.csv`) now hold 4-5 years of history. These will be extended further each time `pull_all.py` runs (it calls `fetch_pct_above_200dma()` etc., which downloads fresh 5yr data and merges with cache).
- The breadth computation bug fix (`sp500_breadth.py`) changes behavior: previously the live path silently returned empty, now it returns correct live data. If any downstream code was compensating for the empty-live behavior, it may need review.

---

### 2026-06-07 — Permanent CFTC TFF Auto-Refresh (T-02 Fix)

**Assumptions:**
- CFTC publishes new TFF data every Friday at ~3:30pm ET. On Saturdays and Sundays the nightly job runs but no new ZIP is available; weekday runs also need to handle any missed Friday.
- A lightweight HTTP HEAD request (checks Content-Length only, no body) is fast enough (< 1s) to include in every nightly run — the download itself (~300 KB) is only triggered when needed.
- The three-trigger design (Friday age, staleness age, remote-size) covers all failure modes without requiring clock-precision scheduling.

**Key Decisions:**
- Implemented as `refresh_cftc_zip_if_stale()` inside `cftc_pull.py` (collocated with the rest of the CFTC data logic) rather than in `nightly_run.py` — keeps the refresh self-contained and callable from any context (scripts, notebooks, manual runs).
- Called at the top of `load_all_series()` in `pull_all.py` so it runs automatically on every nightly pull, before `fetch_cftc_fast_money_net()` parses the ZIP.
- Threshold values: Friday = weekday 4; stale = 8 days (one missed weekly release); Friday re-download if file > 12h old (file predates today's ~3:30pm publication).
- Used `_CFTC_STALE_DAYS = 8` as a module-level constant so it can be tuned without reading implementation details.

**Deferred / Left for Future:**
- The function only refreshes the current year's ZIP. If a nightly job runs on Jan 1, the prior-year ZIP will not be refreshed (CFTC stops updating it at year-end; this is acceptable).
- No retry on network failure — a failed download returns False and the system continues with the (potentially stale) local file rather than crashing. This is intentional; one missed refresh is tolerable.
- No Slack/email alert on download failure — logging only. Add alerting if stale data becomes a recurring production issue.

**Edge Cases Not Handled:**
- CFTC occasionally republishes an amended report mid-week (rare). The size trigger will catch this only if the new ZIP is strictly larger. If the amendment shrinks the file (theoretical), the stale-day trigger (8 days) would still catch it within two weeks. No known real-world occurrence of a smaller re-publication.
- Holiday weeks where CFTC delays publication to Monday or Tuesday — the 8-day staleness trigger handles up to one full week of delay.

**Caveats for Next Developer:**
- The global `_TFF_RAW_CACHE` in `cftc_pull.py` is set to `None` after each successful download, forcing `_download_frames()` to re-parse the ZIP on the next call. If you add other callers that hold a reference to the parsed DataFrame, they will not see the update automatically.
- `requests.head()` has a 15-second timeout; `requests.get()` has a 120-second timeout. Both are intentionally conservative for production use. Adjust if CFTC.gov latency degrades.

---

## 2026-06-09

### Task — SSI Open Questions understanding doc

**Assumptions:**
- Part III (`*_20260606.json`) and Tests 18–20 (`*_20260607.json`) are authoritative; 2026-06-04 run numbers are invalid for gate conclusions.
- PDF structure (Parts 1–10 + numbered tests) drives document outline; status file §4/§5/§11 supplies numeric evidence.

**Key decisions:**
- Followed `create-understanding-doc` skill: Q&A columns Question | Answered? | Answer | Doubts to ask Rohit Sir; no sign-off/blocker language.
- Consolidated 18 master doubts from §11.7 and per-section tables (short pctile, TP/SL, z-score switch, SQUEEZE FM, Tests 12/13/15/17).

**Deferred:**
- Test 12/13/15/17 reruns not re-executed as part of doc creation — status reflects pending state.
- PDF not duplicated inline; pointers to JSON artifacts and summary §4.

**Caveats:**
- Test 17 Part III rerun outcome marked "confirm rerun" — user should verify `17_trendpulse_*.json` if present after 7yr backfill.

---

## 2026-06-07

### Task 19 — SSI open-questions deep-dive fixes (Phase 1 + Tests 18–20)

**Assumptions:**
- Part III JSON (`*_20260606.json`) is authoritative for Tests 1–8; §4 in `SSI_OPEN_QUESTIONS_SUMMARY.md` superseded stale 2026-06-04 numbers.
- COT FM sweep uses weekly FM net percentile (156-week window) vs SPX daily forward returns (as-of merge).
- VIX≥35 episodes use daily VIX close; FM pctile is last weekly value on or before episode date.
- Layer 2 z-score sweep uses 3yr (756-day) rolling z on four Layer 2 inputs; confirms when ≥2 inputs have |z| ≥ threshold (production min_confirmed=2).

**Key decisions:**
- Registered Tests 18–20 in `run_ssi_validation_suite.py`; improved CFTC grid markdown with 12w heatmap; TP/SL report shows top-10 Sharpe table.
- Added `_HIST_CACHE` to `build_ssi_history_frame()` — Test 20 runtime ~336s first call.
- Short threshold recommendation updated: **≥95** for actionable short context; **≥85** for caution only.

**Deferred:**
- Test 15 SBI batch (~1 hr MindWealth).
- Test 12/13 reruns with extended breadth/McClellan.
- True CNN stock F&G 2011–2018 (paid data).
- HYG/LQD Granger (sub-experiment D).

**Edge cases not handled:**
- VIX≥35 bin n=6 for FM 30–50 — too small for stable inference.
- Layer 2 z-score at 2.0 has n=12 long days — 100% hit rate not statistically robust.

**Caveats:**
- CNN Test 6 still uses Alternative.me proxy from 2018.
- FM&lt;20 SQUEEZE recommendation (n=122) vs PDF FM&lt;30/RM&gt;50 — Rohit must pick production mapping.

---

### Task 23 — Macro report update understanding doc

**Assumptions:** Source = Divyanshu 11-point `Report update todo details.md`; status from ANALYSIS, STATUS, TODO files.

**Key decisions:** Mirrored all 11 points + Combo B HY add-on + MRU tickets; Q&A tables use mandatory four columns with "Doubts to ask Rohit Sir"; no PDF per skill.

**Deferred:** MRU-04..06 doubts consolidated for Rohit Sir; Divyanshu-specific items framed as evidence-backed doubts.

---

### Task 18 — Macro report update status file

**Assumptions:** Consolidates Part 1 + Part 2 analysis and MRU tracker into single TODO/DONE snapshot for the `macro_report_updates` folder.

**Key decisions:** `MACRO_REPORT_UPDATE_STATUS.md` is the at-a-glance view; `MACRO_REPORT_UPDATE_TODO.md` remains MRU ticket detail.

**Deferred:** MRU-04..06 and unticketed items listed in status file TODO section.

---

### Task 17 — Execute MRU-01/02/03 (G→B cascade, HY audit, Combo C smoke test)

**Implementation assumptions:**
- MRU-01/02 used **detector rescan** (`detect_named_combos()` on every Friday 2007–2026) rather than only persisted `combo_fires`, because DB has zero B ACTIVE and zero G rows (89 B WATCH since 2023 backfill).
- HY percentiles read from `daily_readings` (7,364 rows incl. BAA10Y proxy), not FRED API — live `BAMLH0A0HYM2` returns only ~3 years.
- MRU-03 advanced cancel on four consecutive Fridays (2026-06-12 → 2026-07-03) where WTI 4wk < +5% and governing CPI was cold (2026-06-10 print: actual 0.5 ≤ consensus 0.5). May 2026 Fridays failed CPI hot-surprise leg.

**Key findings:**
- **G→B:** 0 G fires in entire 2007–2026 scan; 3 B episodes (2012-06-01, 2020-05-01, 2020-07-10); none had prior G within 6 weeks.
- **HY audit:** Recommendation `keep_400bps` — no fires in 375–400 bps band. Oct 2022 (427 bps) fails dual 80th pctile on full history (35.4th). Dec 2018 (456 bps, 42nd pctile) also fails dual.
- **MRU-03:** PASS — `combo_c_cancel.cancel_date=2026-07-03`, briefing shows brown CANCELLED row, PDF generated.

**Things deferred:**
- MRU-04: Divyanshu sign-off on HY dual 80th pctile vs Oct 2022 canonical B date.
- MRU-05: Historical Combo G backfill / why zero G fires in rescan.
- MRU-06: Manual G→B episode table from Divyanshu confirmed dates.

**Edge cases not handled:**
- Persisted `combo_fires` vs rescan mismatch — backfill used pre-fix detector rules; no automatic DB reconciliation.
- Oct 2022 test (`test_combo_b_oct_2022.py`) may not include full-history HY percentile gate.

**Caveats for next developer:**
- Production `runic.db` now has `combo_c_cancel.cancelled=True`, `cancel_date=2026-07-03` — next real nightly run will show C as CANCELLED until re-activated.
- FRED API must not be used for long-run HY percentiles; always use DB series.

---

### Task 21 — SSI Experiment Audit vs DivyanshuTestList PDF

**Implementation Assumptions:**
- Treated SSI_OPEN_QUESTIONS_SUMMARY.md as the complete record of all validation runs (2026-06-04, 2026-06-06, 2026-06-06 Part III).
- Only Part III results considered valid for Tests 1–4 and 7–8 (earlier runs had 83-day SSI window and horizons key mismatch bugs).
- Test numbering follows the PDF's Part 9 test list. Test 17 (TrendPulse) was added by the implementation team, not in the PDF's 15+1 spec.

**Findings:**
- 12/17 tests fully credible.
- Test 6 (CNN F&G): uses Alternative.me CRYPTO Fear & Greed as proxy; 2011–2018 CNN stock market data unavailable. Results cannot validate CNN stock market thresholds.
- Test 12 (Bollinger + SSI): 0 combo events in all runs. Now unblocked — breadth extended to 2015 on 2026-06-07. Rerun needed with pctile≤20 gate.
- Test 13 (Stochastic + McClellan): McClellan now extended to 2014; rerun will produce meaningful n. Previously only n=3.
- Test 15 (SBI Short): not run, requires MindWealth batch ~1hr.
- 4 PDF sub-experiments never run: COT FM sweep (15th–45th), VIX>35/FM distribution, Layer 2 z-score sweep 0→2.0, HYG/LQD Granger causality.

**Things Left for Future:**
- Test 6: obtain true CNN stock market F&G 2011–2018 (Bloomberg or alternative source).
- Test 12 + 13: rerun with breadth extended to 2015 (completed 2026-06-07 entry 20).
- Test 15: Rohit decision D-4 then run MindWealth SBI batch.
- Test 17: confirm Part III re-run produced actual TrendPulse episode results.
- Sub-experiments A/B/C/D: COT FM sweep, VIX/FM distribution, Layer 2 z-score sweep, HYG/LQD Granger.

**Caveats:**
- The SSI_OPEN_QUESTIONS_SUMMARY.md §10.7 table shows Tests 12 and 17 as "⚠️" and "✅" respectively, but the text in §9.3 and §9.7 contradicts the ✅ for Test 17 (still says "data gap prevents meaningful results"). Clarify which is authoritative.
- All initial 2026-06-04 numbers for Tests 1–4 and 7–8 are INVALID due to bugs. SIGNOFF.md must reference only Part III artifacts.

---

### Task — Part H promotion candidates CSV + review script

**Implementation assumptions:**
- Source artifact is `macro_intelligence/analysis/combo_discovery/combo_discovery_20260606.json`; `promotion_candidates` key holds exactly 62 entries matching summary count.
- Primary horizon in config is `spx_3m`, so `primary_hit_rate`/`primary_avg_return` align with `spx_3m_*` columns in CSV.
- CSV uses pipe-separated `var_ids` and compact fire-date summary (`fire_dates_count`, `first_fire_date`, `last_fire_date`) rather than full semicolon-separated date lists.

**Key decisions:**
- Script name `show_combo_promotion_candidates.py` follows repo argparse + ROOT pattern from `run_combo_discovery_pipeline.py`.
- Default JSON resolution picks lexicographically latest `combo_discovery_*.json` in analysis dir.
- Sort order: `primary_hit_rate` desc, then `n_fires` desc, then signature tie-break.

**Things deferred:**
- No Claude narrative enrichment in CSV (`story_status` is SKIPPED for all 62 in this run).
- No automatic monthly export hook; Rohit review is one-off from 2026-06-06 artifact.

**Edge cases not handled:**
- Duplicate fire dates in source JSON are preserved in print output but counted as-is in `fire_dates_count`.
- Script does not validate promotion gate thresholds; trusts JSON `promotion_candidates` list.

**Caveats for next developer:**
- Re-run with `--json` after new combo discovery pipeline writes; `--csv` path is caller-specified.
- Full fire dates appear in script stdout only; CSV is intentionally compact for spreadsheet review.

---

### Task — Understanding doc period & variables tables (A1–H)

**Implementation assumptions:**
- All experiment numbers reference the **2026-06-06** shadow run (`run_regime_v2_experiment_suite.py`) unless a subsection uses a narrower window (e.g. B1 anchor dates, Part D 500-row HMM sample).
- **SPX** means **^GSPC** Yahoo close; forward horizons use NYSE trading-day counts (63 td ≈ 3m, 126 td ≈ 6m).
- JSON artifact key mismatch (plan A2=curve vs JSON `A2_geo`, fiscal test under `A5_fiscal_caveat`) is documented in Part A intro.

**Key decisions:**
- Placed **Experiment run — period & variables** immediately before each existing **Experiment status** block for scanability.
- Part H Steps 4–6 share one table (same pipeline pass); Steps 1–3 and 7–9 get focused tables.
- Label-only subsections (A1, A4, A5 backfill) note when **no SPX outcome** was measured in that subsection.

**Things deferred:**
- Section 14 FM/regime questions not expanded (user asked A1–H only).
- Part I sample-size rules unchanged.

**Edge cases not documented in tables:**
- Combo fire history span depends on macro DB backfill start (not re-derived here); Part H cites **13,089** fires at run time.
- A2 fiscal caveat `hit_rate` in JSON uses default bullish=True (% SPX up), while prose sometimes says "bearish hit" — tables note SPX 3m explicitly.

**Caveats for next developer:**
- After CONFIG window fixes or re-backfill, update period counts (1,901 Fridays, 14,457 dual percentile rows) if they change.
- Re-run combo discovery will change Part H funnel numbers; update H summary table accordingly.

---

### Task — Rohit v2 feedback plan + response report

**Implementation assumptions:**
- Rohit feedback (`testingv1_feedback/feedback_summary.md`) is the authoritative question list; v2 report mirrors his section numbering and inline-table format (§10).
- Combo PW returns computed from live DB query 2026-06-10; benchmarks per Rohit (+0.5% 5D, +2.5% 3M, +5% 6M, +10% 12M).
- Combo A reported on bearish (TIGHT MONEY) framing — CONFIG still marks direction bullish (known mismatch).

**Key decisions:**
- Separated **plan** (`testingv2_plan.md`) from **report** (`testingv2_report.md`) so execution status is trackable.
- Documented curve bug root cause (negative `steepen_4wk_bps` in DB) rather than patching in report-only.
- HMM walk-forward and 11-variable sweeps explicitly marked PENDING — not conflated with prototype k-means results.

**Things deferred:**
- F4 per-instance PW columns; 11-variable isolation sweeps; HMM walk-forward Steps 0–5; live daily emission_vectors cron; cancel prob briefing wire; TWY_ROC/GSR Combo A ablation; FEARFUL→TIGHT_MONEY full rename; 46-row TIGHT combo Google Drive export.

**Edge cases not handled:**
- VIX n=7 is all calendar days in band since 2010 (not first-crossing) — only 7 days because 2017 VIX was historically low in absolute terms.
- FM moderate TIGHT_IMPROVING n=1 (2020-04-03 COVID) — aggregate slice shown; Rohit may want more bands if backfill extends.
- Combo C n=4 at all horizons — included for transparency despite statistical gate failure.

**Caveats for next developer:**
- After curve `steepen_4wk` fix, re-run shadow backfill and update §8 in v2 report.
- Walk-forward HMM must use 14-vector `emission_vectors`, not scalar mean prototype in `hmm_prototype.py`.
- Compare combo hit rates to i3 Invest cheatsheet once Rohit shares reference numbers.

---

### Task — Testing v2 implementation pass (2026-06-11)

**Implementation assumptions:**
- Post-trough steepen = max(4wk change, rise from last inversion trough); trough resets only on new inversion after positive spell.
- HMM uses weekly mean emission percentiles with 0.5 neutral fill for sparse vars (CPI).
- Cron install script merges — preserves `emailscript.sh` and all existing macro jobs.

**Key decisions:**
- Combo A vote returns `TIGHT_MONEY` (not `FEARFUL`); `posture_display` maps legacy `TACTICAL_FEARFUL` → display TIGHT MONEY.
- Combo B confirmed-only ablation shows n=0 ACTIVE — all 89 DB rows are WATCH (documents Rohit 8 vs 89 gap).
- Emission daily cron at 18:15 ET Mon–Fri after nightly pull (18:00).

**Things deferred:**
- HMM median lead time 0 — anchor/posterior tuning; 14-var vector vs 12 in DB.
- Cancel prob for D/F/G; shadow suite full re-run; v2 report refresh with new JSON paths.
- Parth web UI TIGHT MONEY labels.

**Edge cases:**
- `run_emission_vectors_daily` upserts 0 rows if `daily_readings` has no row for as-of date (backfill max 2026-07-03).
- F4 PW excess for bearish grid uses positive excess when avg SPX up (mechanism gate not short alpha).

**Caveats:**
- Re-run `pull_all` so production CURVE `meta_json.steepen_4wk_bps` picks up new formula.
- `install_aws_cron.sh` only replaces macro marker lines — safe to re-run.

---

### Task — Production CURVE re-pull + shadow backfill + testingv2_report refresh (2026-06-11)

**Implementation assumptions:**
- Targeted CURVE-only refresh is sufficient for `macro_regime_log_v2` because `build_regime_v2` reads `daily_readings` via `get_readings_as_of`; other variables unchanged.
- `load_all_series(force=True)` inside targeted script repopulates `_CACHE` with new `curve_features` DataFrame before per-date upserts.
- Latest Friday in `macro_regime_log_v2` after backfill is 2026-06-05 (W-FRI range ends at last complete Friday before run date).

**Key decisions:**
- Used inline targeted refresh (1,910 CURVE dates) instead of full `backfill_macro_history.py` (~3+ min savings vs full regime/combo recompute).
- Ran experiment suite with `--skip-h-part --skip-report` to refresh JSON artifacts + `backfill_regime_v2` without combo-discovery re-run.
- Report §8 documents before/after DB verification inline for Rohit audit trail.

**Things deferred:**
- Full `backfill_macro_history.py` for non-CURVE variables (not needed — curve fix isolated to CURVE meta).
- HMM posterior / anchor tuning (median lead 0w remains).
- Cancel prob D/F/G briefing wire; Parth web UI TIGHT MONEY labels.

**Edge cases not handled:**
- `daily_readings` dates through 2026-07-03 (future-dated backfill rows) refreshed but `macro_regime_log_v2` only covers W-FRI through 2026-06-05.
- F4 PW excess positive on bearish grid when avg SPX up — mechanism gate ≠ short alpha (noted in report).

**Caveats for next developer:**
- After any further `fred_pull` curve logic change, re-run targeted CURVE refresh + `backfill_regime_v2` (or full suite).
- `pull_all_series(today)` also run to upsert 2026-06-11 row; CFTC persist triggered on non-Friday run.

---

### Task — Sync testingv2_plan.md status + report coverage column (2026-06-11)

**Implementation assumptions:**
- `testingv2_status.md` is source of truth for implementation Status; `testingv2_report.md` section numbers for report coverage.
- Steps documented as 🔄 in report column when report calls out PENDING explicitly (e.g. i3 cheatsheet, Parth UI, D/F/G cancel).

**Key decisions:**
- Added **In v2 report?** column to all phase tables (not format guidelines).
- Split former implicit TWY/GSR work into explicit plan step 5.4 aligned with status tracker.
- Replaced stale priority list (P0 curve/sweep/HMM) with remaining follow-ups.

**Things deferred:** None — doc-only sync.

**Caveats:** Step 5.5 (Rohit unsent email) has no report section until attachment received.

---

### Task — Generate nightly macro briefing for 2026-06-10 (2026-06-11)

**Implementation assumptions:**
- `daily_readings` for 2026-06-10 already had 12 variables in `runic.db`; no forced FRED re-pull required.
- `use_claude=True` for full five-paragraph narrative (Tavily headlines + regime context).
- Copies written to `testing/macro_report_updates/` alongside default `macro_intelligence/output/`.

**Key decisions:**
- Used inline `run_nightly` + `write_briefing` to testing dir (same pattern as 2026-06-09 run).
- Did not regenerate markdown pipeline report; deliverable is the Runic briefing PDF.

**Things deferred:**
- Analog forward returns show 0% for recent dates (2026-06-19/26, 2026-07-03) because outcomes are not yet realized.

**Edge cases:**
- Combo C not in active list on this date (prior cancel state from MRU-03 may apply on later dates only).
- Combo E shows CONFIRMED with CAPE+NFCI legs but 19% 12M hit rate; F outranks on priority/horizon fit.

**Caveats:**
- Run completed in ~46s; CFTC parse warning (date format inference) is benign.

---

### Task — Macro threshold validation plan refinement (testingv2) (2026-06-16)

**Implementation assumptions:**
- Plan-only task; no backtests executed. Quick DB query via Python confirmed percentile scale inconsistency.
- `percentiles.py` returns 0–100; ~220 legacy rows in `daily_readings` still on 0–1 scale.
- Prior `F_per_variable_sweep.json` is regression baseline only — 13/22 bands have n=0 due to band/scale mismatch.

**Key decisions:**
- Added P1.0 DB normalization before any sweep re-runs.
- `threshold_sweep_v2.py` uses raw CONFIG thresholds + first-crossing + hostile-regime PW slice (HIKING/TIGHTENING/INVERTED).
- Named combo gate sweeps cover B, F, E, D at validated horizons (3M/6M/12M/5D).
- Output path: `macro_intelligence/analysis/regime_v2_experiments/threshold_sweep_v2/`.

**Things deferred:**
- P1.0–P4 execution (script build, sweeps, report) — next session.
- Combo B leg replay logic (0 ACTIVE fires in DB; must simulate from daily legs).

**Edge cases not handled in plan:**
- Dual-condition vars (VIX, HY, NFCI) may have very low n at tightest bands.
- CPI surprise n≈31 may fail n≥5 at extreme bands.

**Caveats:**
- `combo_threshold_sweep.py` is a stub — Phase 3 requires substantial extension, not just CLI wrapper.
- testingv1_feedback `testingv2_plan.md` covers broader Rohit feedback (HMM, curve fix); this testingv2 dir is threshold-validation-only scope.

---

## 2026-06-16 — Macro Regime Report inline edits + 6 new DB queries (testingv4)

**Task:** Run T2/T3/T4/T5/T6/T10 queries against `runic.db`, insert results inline in report at specified sections, add 8 Rohit text clarifications, create testingv4_status.md.

**Implementation assumptions:**
- `forward_returns` stores SPX returns as decimal percentages (e.g., 6.41 = 6.41%, not 0.0641). Verified from sample values and min/max range.
- T2 (9-state SPX tables) computed on combo-fire basis (dates when combo fires occurred in each regime state), not raw calendar-date SPX returns. This is the correct interpretation — regime-conditional combo returns, not unconditional SPX returns.
- T3 (TIGHT_* fires): 1,639 total rows; all 46 named-combo TIGHT_* fires are Combo A. No Combo B/D/E/F ever fired in TIGHT_* states. Full named-combo table (46 rows) included; unnamed fires summarized by sub-state.
- T4 (Combo E multi-horizon): spx_18m NOT in DB — documented with ⚠️. Used 9m as nearest proxy below 18m. CAPE breakdown uses subquery on `daily_readings.raw_value` for CAPE on the fire date.
- T5 (geo overlay): Used `macro_regime_log_v2.geo_overlay_v2` field (not legacy `geo_overlay`). Legacy `macro_regime_log` has all geo = NEUTRAL. Non-neutral data is only in v2 (3 episodes: COVID 2020, Ukraine 2022, tariff shock 2025).
- T6 (TWY_ROC): DGS2 not stored in DB. Computed as: DGS2 ≈ T10Y (^TNX Yahoo) − T10Y2Y_bps/100 (CURVE var_id in daily_readings). Minor discrepancy vs FRED DGS2 (~±0.07pp). April 2025 anchor: computed −0.632pp on Apr 4 vs report's −0.55pp on Apr 7 (Friday vs Monday + rounding).
- T10 (inversion episodes): 5 episodes, gap in 2006 treated as two separate episodes (7-week gap between Jul and Aug 2006 inversions). steepen_4wk_bps pulled from `meta_json` field of CURVE rows.

**Things deferred / left for future:**
- spx_18m: Not in DB. Would require extending the pipeline to compute and store 18-month SPX forward returns.
- TWY_ROC as stored var_id: Currently must be computed on-the-fly from ^TNX + CURVE. Should be stored as a daily_readings row (var_id = 'DGS2' or 'TWY_ROC') from weekly FRED pull.
- MODERATE CAPE Combo E bucket (25–30): n=127 historically but n=0 since 2018. Monitoring needed — if CAPE falls to 25–30, these thresholds would be most relevant.
- HMM anchor labelling and posterior threshold tuning: 0w median lead time; needs 6+ months of live emission vectors before December decision.

**Edge cases not handled:**
- T2 join: Some combo fires may be double-counted if multiple combos fired on the same date in the same liquidity state. This is by design (each combo fire is an independent observation).
- T6 TWY_ROC: Uses T10Y from Yahoo as proxy for Fed Funds rate context; not a direct DGS2 pull. FRED API would be more accurate.
- T3 TIGHT_* includes generic (unnamed) fires which share SPX forward returns with named fires if they occur on the same date. Summary table correctly separates by runic_combo.

**Key decisions made:**
- Kept all 1,639 T3 rows as summary + full named-combo detail (not truncated) per Rohit's "insert every row" instruction.
- T10 first-steepen-after defined as "after episode end" not "after episode trough" — steepening begins when the inversion ends and balance sheet dynamics change.
- Used weekly Friday alignment throughout T2/T3/T5 since macro_regime_log_v2 is a weekly Friday series.

**Caveats for next developer:**
- The report file now has ~54K chars (up from ~29K). Consider splitting into sub-documents if it grows further.
- T6 TWY_ROC band sweep uses Yahoo Finance ^TNX + CURVE from DB — requires internet access to refresh. The April 2025 values match the report's narrative anchor well.
- All T2 returns are on combo-fire basis, not buy-and-hold. Comparing to unconditional SPX returns requires stripping market drift.

---

### Task — Execute full testingv2 threshold validation experiment (P1–P4) (2026-06-16)

**Implementation assumptions:**
- Legacy percentile normalization: rows with `0 < unconditional_pctile <= 1.0` multiplied by 100 in-place on `runic.db` (220 rows across 9 variables).
- First-crossing uses 5 calendar-day cooldown (not trading-day) after each fire; hostile slice joins `macro_regime_log` + `macro_regime_log_v2` on event date (7-day lookback).
- Combo B leg replay requires simultaneous VIX level+pctile≥80, HY bps+pctile≥80, CFTC≤threshold on aligned `daily_readings` dates (not `combo_fires` ACTIVE rows).
- Benchmarks per user spec: 1m=+0.5%, 3m=+2.5%, 6m=+5%, 9m=+7.5%, 12m=+10% (differs from `metrics.py` default 1.25% for 1m).

**Key decisions:**
- Built `threshold_sweep_v2.py` with raw CONFIG bands per plan tables; SUMMARY prefers `CURRENT_RARE` band for baseline comparison.
- Extended `combo_threshold_sweep.py` with `run_all_combo_sweeps()`; separate CLI `combo_gate_sweep_v2.py`.
- Combo D uses `spx_1w` horizon key with 5 trading days (validated 5D per Rohit).
- Only WTI cleared all four success criteria (change_justified=true at 6M: WTI_down_15pct vs WTI_up_6pct).

**Things deferred:**
- Combo B combo_detector AND vs CONFIG OR for HY level/pctile — may explain n=0 for 3-of-3; align detector or document strictness.
- CPI threshold validation (n=1 at 0.20pp RARE since 1990).
- Hostile-regime null slices for sparse CAPE/VXTS events.

**Edge cases not handled:**
- Combo B 3-of-3 first-crossing n=0 for all gate variants; 2-of-3 produces n=12 with strong PW (+5.06% excess).
- HY best alternative (pctile_70plus) has high excess but hit rate 9.1% — correctly rejected by criteria.
- WTI justified change is directional (down-side collapse vs up-side spike), not a simple symmetric threshold tweak.

**Caveats for next developer:**
- Re-run `normalize_pctile_scale.py` is idempotent (0 rows after first run).
- `threshold_sweep_v2.py` ~227s runtime (Yahoo SPX fetch + 12 vars); combo sweeps ~20s.
- Report at `testing/macro_th_exp/testingv2/threshold_validation_report.md` + PDF (41KB).

---

### Task — Rohit feedback sectionwise answers document (2026-06-16)

**Implementation assumptions:**
- `feedback_sectionwise_details.md` is the authoritative question list; each TODO block gets an **Answer (2026-06-16):** block immediately below.
- Data pulled from v4 inline report edits (T2/T3/T4/T5/T6/T10 queries), `testingv2_report.md`, `threshold_validation_report.md`, and JSON artifacts in `regime_v2_experiments/`.
- First-person analyst voice (Divyanshu); no em dashes per report-creation skill.

**Key decisions:**
- Preserved section numbering from feedback doc (§1, §2, A1, A3, A4, A6, B1, B2, B3, C, F).
- PENDING items called out explicitly: i3 Invest cheatsheet compare (needs Rohit reference values), 18M forward returns (not in DB), WALCL 0.1/0.2/0.3 FM-event sweep, Parth web UI Combo A naming.
- B2 history window answer uses Rohit June 11 correction (VIX/HY/VXTS = full expanding, not rolling_3y) superseding June 6 B4 audit FAIL.

**Things deferred:**
- Google Drive Excel exports (inline tables provided; full JSON at `threshold_sweep_v2/` and `regime_v2_experiments/`).
- Formal B4 audit re-run with corrected expected-window map.

**Edge cases not handled:**
- Combo C n=4 at all horizons included for transparency despite statistical gate failure.
- TIGHT_TIGHTENING 3M anomalously positive due to 2009 recovery fires (noted in main report).

**Caveats for next developer:**
- i3 cheatsheet diff column blocked until Rohit reshare reference hit rates.
- Document is ~580 lines; send to Rohit as standalone file per his §10 format instruction.

---

### Task — Expand threshold_validation_report.md with full supporting data (2026-06-16)

**Implementation assumptions:**
- All appendix numbers sourced from JSON artifacts in `macro_intelligence/analysis/regime_v2_experiments/threshold_sweep_v2/` (12 variable sweeps + 4 combo sweeps + SUMMARY.json).
- SPX forward returns at 21/63/126/189/252 trading days; benchmarks 0.5/2.5/5.0/7.5/10.0% at those horizons.
- Primary validation horizon per variable follows SUMMARY.json (most 3M; WTI 6M; CAPE 12M).

**Key decisions:**
- Added top-level **Method, instruments, and test specification** plus **Instrument and test window reference** table (data source, percentile window, DB date range, row counts).
- Each of 12 variables gets **full sweep data** (CONFIG bands + current-band multi-horizon table + all bands × 5 horizons appendix).
- Combo B/F/E/D get separate gate-sweep detail sections with all tested variants.

**Things deferred:**
- 18M horizon (not in `forward_returns` schema).
- CPI full validation (n=1 at current RARE band).

**Edge cases not handled:**
- Combo B leg replay AND vs CONFIG OR for HY may explain n=0 for strict 3-of-3 (noted in report).

**Caveats for next developer:**
- Report is ~1,679 lines; PDF ~251 KB. Temp `_report_appendix_generated.md` removed after merge.

---

### Task — Contextual verdict columns for threshold validation §4a/§4b (2026-06-16)

**Implementation assumptions:**
- Verdicts are hand-authored per (variable, tier, side, band) in `_VERDICT_OVERRIDES`; generic fallback only when no override exists.
- Best alt selection unchanged: same-side bands only; bear ranked by hit then excess; bull by excess then hit; n≥5 for alts.
- Sparse bands (n<3) return Defer unless an override supplies a policy Keep CONFIG message.

**Key decisions:**
- Dropped hard gates (Δ≥2pp, hit≥60%) from verdict column and methodology table; replaced with combo-role + economic-meaning narrative.
- WTI down_15pct is the only "Consider" across all 12 variables (RARE and EXTREME down legs); symmetric up-leg stays CONFIG.
- CAPE high bear: keep CONFIG despite alt improving bear hit — PW excess on current band is misleading (SPX rallied; structural valuation not a 12M timer).

**Things deferred:**
- Hostile-regime check not embedded in per-row verdict text (still in appendix data).
- NFCI EXTREME rows use same ±0.3 SD bands as RARE in production — noted in verdict.

**Edge cases not handled:**
- CNH/CURVE extreme sparse rows use override Keep CONFIG even when best alt looks better on paper (n too small to retune policy extremes).

**Caveats for next developer:**
- Re-run `python3.12 scripts/generate_section4_tables.py` then patch report tables from `_section_4a_table.md` / `_section_4b_table.md` if sweep JSONs change.
- PDF regenerated at ~243 KB after verdict update.

---

### Task — Threshold validation v2 understanding doc (2026-06-16)

**Implementation assumptions:**
- Source spec = `threshold_validation_plan.md`; status = `threshold_validation_report.md` + `testingv2_status.md`.
- Follows create-understanding-doc skill: Q&A columns use Doubts to ask Rohit Sir (no Gap/sign-off language).
- User requested summary section at top listing all experiments and outcomes.

**Key decisions:**
- Grouped work as P1 (data), P2 (12-var sweep + §4a/b), P3 (combos B/F/E/D), P4 (report/CSVs).
- Highlighted only actionable change candidates: WTI down_15pct, Combo B 2-of-3, Combo F optional 5%.
- Consolidated 12 doubts from report §8 and per-section Q&A.

**Things deferred:**
- No PDF for understanding doc (skill: markdown only unless asked).
- Did not duplicate full appendix band tables — pointed to report.

**Caveats for next developer:**
- Update understanding doc if CONFIG changes or sweeps re-run; summary table is the quick entry point.

---

### Task — Rohit feedback sectionwise answers understanding doc (2026-06-16)

**Implementation assumptions:**
- Source spec = `feedback_sectionwise_details.md` (32 Rohit TODO blocks); status = `feedback_sectionwise_answers.md` + `testingv4_status.md`.
- Follows create-understanding-doc skill: Q&A columns use Doubts to ask Rohit Sir; no Gap/sign-off language.
- User requested summary section at top listing all experiments performed and outcomes.

**Key decisions:**
- Top summary table covers §1 horizon re-query, §2/B2 window audit, T2–T6/T10 DB tests, A1/A3/A4/A6/B1/C/F2 thematic answers, and 13k fires explanation.
- Mirrored major answer sections (horizons, liquidity, CAPE, geo, TWY, HMM, inversion) with plan vs status blocks and selective Q&A rows (not duplicating every inline table from answers doc).
- Cross-linked to testingv2 threshold validation understanding doc as separate workstream.
- Consolidated 15 doubts deduplicated from per-section Q&A.

**Things deferred:**
- No PDF for understanding doc (skill: markdown only unless asked).
- i3 cheatsheet compare remains blocked until Rohit reshare reference file.

**Edge cases not handled:**
- Combo C n=4 and thin geo slices flagged in doubts but not expanded with full fire lists (point to answers doc).

**Caveats for next developer:**
- Update summary table if testingv5 runs or pending items (18M, WALCL FM sweep) close.
- Output path: `testing/macro_th_exp/testingv1_feedback/understanding_and_research/`.

---

### Task — Nightly CAPE/CFTC source freshness + auto-refresh (2026-06-17)

**Implementation assumptions:**
- CAPE stale when `(report_date - source_date).days > cape_max_lag_days` (default 7); monthly Shiller data may still fail to improve after re-scrape.
- CFTC stale when latest Tuesday position in series is **older than** `expected_latest_cftc_tuesday(as_of)` (Tue positions published Fri = Tue + 3 calendar days).
- `ensure_cape_cftc_fresh` runs at start of every `load_all_series(as_of=...)` before CAPE/CFTC series are read into cache.

**Key decisions:**
- CAPE refresh: `fetch_cape_history()` re-scrapes multpl.com (not cache-only read).
- CFTC refresh: existing `refresh_cftc_zip_if_stale()` then `force_refresh_cftc_zip()` if still behind expected Tuesday.
- Audit exposed as JSON `source_freshness` on nightly payload; CAPE/CFTC `meta_json` stores `source_date`, `lag_days`, `expected_source_date` (CFTC).
- Variable dashboard `source_note` includes data-as-of date and lag for CAPE/CFTC.

**Things deferred:**
- Surfacing freshness in PDF variable table column (only footnote via source_note on CFTC/CAPE rows if renderer uses it).
- Auto-refresh for other slow variables (NFCI weekly, WALCL weekly).

**Edge cases:**
- CFTC 7-day lag on Tuesday report is **expected** (not stale) when source equals expected Tuesday.
- Historical `--date` runs refresh against that as_of's expected CFTC Tuesday, not today's ZIP only.

**Caveats:**
- `force_refresh_cftc_zip` downloads current calendar year ZIP; historical backfill dates cannot retrieve future CFTC rows.
- Smoke 2026-06-16: CAPE 2026-06-04 → 2026-06-16 after refresh; CFTC Jun 9 OK.

---

### 2026-06-18 — Upgrade Claude Narrative Prompt (Full Combo Coverage + Variable Significance)

**Task:** Rewrite `nightly_briefing.py` to produce a 600-750 word structured briefing covering all 7 combos and all 12 variables with significance context.

**Implementation decisions:**
- Embedded a 12-variable significance guide and a 7-combo significance guide directly in the SYSTEM prompt so Claude always has the correct thresholds and directional meaning, regardless of what context it was trained on.
- Changed mandatory output from 5 short paragraphs (380-450w) to 5 detailed sections (600-750w) with specific coverage requirements for each combo.
- Section 2 now requires Claude to cover ALL 7 combos A-G (including inactive/cancelled), stating which legs are met and which are missing with exact values vs thresholds.
- Section 3 requires walking through EXTREME/RARE variables first, then three numbered reasons the dominant signal wins.
- USER prompt enriched: passes `combo_status_rows` (all 7 rows including INACTIVE), explicit EXTREME/RARE tier lists, CFTC FM + RM percentile note, SSI multiplier, VIX bypass flag.
- `_template_briefing` fallback rewritten to produce a structured five-section output using `combo_status_rows`, variable tiers, analog details (3m/6m/12m), and regime dimensions — much more informative than the previous single-paragraph template.
- `narrative_max_tokens` raised from 1200 to 2200 in `CONFIG.yaml` to allow the longer output.

**Assumptions:**
- `combo_status_rows` is already built before `generate_nightly_briefing` is called (it is — built in `run_nightly` before narrative generation).
- `cftc_rm_pctile` key on the CFTC variable row is populated by `_variables_dashboard` when the DB has RM percentile data.

**Things deferred:**
- Leg-level variable values for inactive/watch combos are not passed to Claude — Claude must infer from the 12-variable dashboard which legs are met. A future improvement would pass per-combo leg detail (e.g. `{"B": {"vix_met": false, "hy_met": false, "cftc_met": true}}`).
- Prompt currently targets English text only; no multi-language support.

**Edge cases:**
- If `combo_status_rows` is empty (e.g. first run before `build_combo_status_rows` is populated), the USER prompt falls back to iterating `active_combos` and `watch_combos` only — watch combos merged in `_template_briefing` will not have leg detail.

**Caveats:**
- The SYSTEM prompt contains hardcoded thresholds (e.g. VIX 25, CAPE 28). If CONFIG.yaml thresholds are changed, the SYSTEM prompt must be updated manually to stay consistent.

---

### Task — Combo E horizon validation sweep 6M–18M T11 (2026-06-18)

**Implementation assumptions:**
- Population: all `combo_fires` with `runic_combo='E'` (n=508).
- Horizons: 126/189/252/315/378 NYSE trading days = 6/9/12/15/18M.
- Bear metrics use `probability_weighted_summary(bullish=False)`; bull up% table retained for continuity with T4.
- 6M/9M/12M prefer DB `forward_returns` when present; 15M/18M computed via Yahoo `^GSPC`.

**Key decisions:**
- **Keep 12M as CONFIG primary** — bear hit 18.9% with full n_mature=507; 6M only +0.8pp higher bear hit; 15M/18M lower bear hit and thinner samples.
- Report both bear-framing (validated direction) and SPX Up% diagnostic tables.
- Did not change `combo_hit_rates.E` in CONFIG (experiment validates existing choice).

**Things deferred:**
- Persist `spx_15m` / `spx_18m` in `forward_returns` schema and backfill pipeline.
- CAPE bucket breakdown at 15M/18M.

**Edge cases not handled:**
- Recent fires lack mature 15M/18M windows (n drops to 427/413).

**Caveats for next developer:**
- Re-run: `python3 scripts/combo_e_horizon_sweep.py`
- Artifact: `macro_intelligence/analysis/regime_v2_experiments/COMBO_E_horizon_sweep_6_18m.json`

---

### Task — Fix Combo C §1 horizon table immature forward returns (2026-06-18)

**Root cause:**
- Only 2 unique Combo C dates (Mar 2026) but 4 `combo_fires` rows (duplicate combo_ids).
- `forward_returns` had **stale immature** spx_3m/spx_6m (+16–19%) from pre-fix `forward_return_pct` bug; live compute returns NULL until windows mature.
- Bearish hit 0% and blank avg win were artifacts of counting immature positive returns as mature 3M/6M.

**Fix:**
- `scripts/combo_validated_horizons_table.py` — dedupe by date, Yahoo recompute, mature-only PW stats.
- Recomputed Combo C `forward_returns` in DB (spx_3m/6m/12m → NULL).
- Updated `feedback_sectionwise_answers.md` §1 and `testingv2_report.md` §1b with n_total/n_mature columns.

**Caveats:**
- Combo C 3M/6M metrics stay — until ~late Jun / Sep 2026 when windows mature.
- Re-run full table: `python3 scripts/combo_validated_horizons_table.py`

---

## 2026-06-18 — Task 2: Macro Intelligence API v1.3.0 (13 new endpoints)

**Task:** Create API endpoints for all macro intelligence functions relevant to the Runic frontend view.

**Assumptions:**
- Frontend view is `MindWealth_Macro_Runic_Latest.html` — 6 tabs: Overview, 12 Variables, 7 Named Combos, Combo Tracker, Analog Tables, Nightly Brief.
- All data is read from `runic_output.json` (primary) and `runic.db` (analog details, cancel state, CPI data).
- `use_claude=False` by default for run-nightly trigger to avoid LLM cost on API calls.
- `combo_status_rows` from the nightly payload may be null for combos not surfaced in that run.

**Architecture decisions:**
- Created `api/services/macro_service.py` as a dedicated service layer (separate from `reports_service.py`) since macro data access patterns are more complex (DB + JSON hybrid).
- Static metadata (COMBO_STATIC, VARIABLE_META) lives in the service file, not a YAML, since it's structural documentation-level data that rarely changes.
- `/macro/analogs/{combo_id}` reads from SQLite `combo_fires + forward_returns` tables rather than the nightly JSON because the JSON only contains analog_details for the dominant combo.
- DB helpers wrapped in try/except returning empty defaults — service remains available even when DB is missing.

**Things deferred/left for future:**
- Pagination for `/macro/analogs/{combo_id}` (currently hardcoded limit=10 from DB).
- Async version of `POST /macro/run-nightly` (currently synchronous — can hang for 2–3 min with Claude enabled).
- `/macro/combo-c/cancel` `friday_log` requires `combo_c_cancel_log` table — returns `[]` if table doesn't exist yet (schema may not have it).
- `progress_pct` in combo-f window computed from `duration_weeks / 26` — if `fire_date` is available in DB it uses that, else falls back to nightly JSON `combo_f_weeks_elapsed`.
- Variable metadata (sources, gates) is hardcoded in `_VARIABLE_META` dict — should ideally be driven from `CONFIG.yaml` variables list.

**Edge cases not handled:**
- Multiple simultaneous fires of the same combo (DB query takes only the latest row).
- Combo IDs passed in lowercase are normalized to uppercase — but path params like `/macro/combos/c` work.
- `analog_details` regime field may be empty `{}` when `macro_regime_json` column doesn't exist in older DB versions.
- `mtm_pct` for active combos (like F) comes from the nightly payload active combo dict — may be null if nightly run didn't compute it.

**Known gaps:**
- `GET /macro/combo-c/cancel` friday_log will be empty until `combo_c_cancel_log` table is populated by the nightly cancel checker (requires at least one Friday run with C active).
- `POST /macro/run-nightly` returns 502 on any nightly run error — the error message is propagated but may be cryptic for external callers.

**Test results:** 22/22 pytest pass. 22/23 curl pass (run-nightly excluded from batch curl).

---

## 2026-06-18 — Fix geo table, TIGHT_* unnamed, CSV exports, WALCL actual counts

**Task:** Four fixes to `feedback_sectionwise_answers.md` + create `csv_exports/` directory.

**1. Geo table (lines ~212-222) — root issue:**
- Prior table only showed "SPX up% 3m" for all combos. This is meaningless for **bearish combos** (A, D, E) because their signal correctness is SPX *down*, not SPX up.
- Re-queried 58-row geo dataset and added "Validated hit%" column: bullish combos (B, F) use SPX>0 as hit; bearish (A, D, E) use SPX<0.
- Key findings: Combo A in CRISIS = 0% bear hit (fired at Apr 2020 bottom, SPX recovered → correct miss). Combo E in ELEVATED_RISK = 68% bear hit. Combo F in ELEVATED_RISK = only 17% bull hit (Ukraine 2022 was poor for F).
- **Assumption:** `geo_overlay_v2` is the column in `macro_regime_log_v2.regime_json`; validated via DB query.

**2. TIGHT_* "unnamed" combo:**
- "unnamed" = `combo_fires` rows where `runic_combo IS NULL`. These are raw 2–3 variable pair events that triggered simultaneously at RARE/EXTREME bands but **did not meet the naming gate** (≥5 fires, ≥80% validated hit rate, clear mechanism). They are NOT unnamed versions of A–G.
- Only Combo A has named fires in any TIGHT_* state. B/C/D/E/F/G = zero TIGHT_* named fires.
- Updated table label from "unnamed" → "Generic pair fires (unnamed)" with explanatory note.
- **Deferred:** Consider whether to run naming-gate evaluation on the TIGHT_FLAT 52-event cluster (potentially worth naming if hit rate justifies).

**3. CSV exports directory:**
- Created `testing/macro_th_exp/testingv1_feedback/csv_exports/`
- `tight_liquidity_named_combo_46rows.csv` — all 46 Combo A TIGHT_* fires with 1m/3m/6m/9m/12m SPX.
- `geo_overlay_combo_fires_non_neutral.csv` — 58 named combo fires on CRISIS/ELEVATED_RISK days.
- `walcl_mom_threshold_distribution.csv` — actual WALCL threshold counts at ±0.1/0.2/0.3.

**4. WALCL "~est." → actual counts:**
- Prior table showed "~520 est." etc. — these were never computed; marked as estimates.
- Queried `daily_readings` (var_id='WALCL' joined NFCI) for NFCI-EASY Fridays (NFCI ≤ −0.3) from 2008-01-01. Total = 719 Fridays (prior table said 1,901 which was ALL Fridays, regardless of NFCI state).
- **Important:** The prior total of 1,901 was misleading — it mixed all NFCI states. The 1,901 covered all Fridays since 2008; the EASY_* states only apply to NFCI-EASY weeks (719).
- Actual counts: ±0.3% → IMPROVING=291, TIGHTENING=230, FLAT=198; ±0.2% → 309/273/137; ±0.1% → 335/309/75.
- **Deferred:** FM-event hit rate sweep at each threshold (does ±0.1% gate improve IMPROVING vs TIGHTENING signal discrimination?) — not yet run, flagged for next pass.

---

## 2026-06-19 — SSI API v1.4.0 (summary, history, multiplier)

### Task
Add dedicated SSI (Super Sentiment Index) API endpoints, update docs, commit and push.

### Assumptions
- `ssi.db` lives at path returned by `config_paths.SSI_DB`; table `ssi_daily` has columns: `date, ssi_level, ssi_percentile_5y, hyg_lqd, dbmf_beta, cnn_fg, vix_ratio, layer2_status, layer2_confirmed_count, ssi_multiplier, payload_json, created_at`
- `payload_json` column stores the full SSI payload dict; `inputs.layer2_votes` is a list of `{input, vote, signal, pctile}` dicts used for the per-input breakdown in `/ssi/summary`
- Posture thresholds: RISK_ON < -0.6, RISK_OFF > 0.85, NEUTRAL otherwise — matches existing `run_ssi_daily.py` logic
- `positioning.json` exists for signal thresholds; falls back gracefully if missing (multiplier endpoint still returns from DB)

### Architecture Decisions
- All three functions in `macro_service.py` open their own `sqlite3` connection (not shared) and close in `finally` — avoids holding a connection open during request lifecycle
- History endpoint clamps `days` server-side (1–90) rather than relying on query validation — prevents large accidental queries
- History series returned chronological (oldest → newest) for direct use in Recharts/Plotly without client-side reversal
- Multiplier endpoint intentionally lightweight — only reads 1 row from ssi_daily + positioning.json signals; avoids loading full payload_json for high-frequency polling

### Tests
- 10 new tests in `TestSSIEndpoints` class using mock patches (no real DB required)
- Tests cover: 200 OK, field presence, field values, 404 on missing DB, `days` clamping to 90, `days` param forwarding, series structure
- All 32 macro tests pass (pytest 5.08s)

### Deferred / Future
- `ssi_percentile_5y` in history only returns raw float; vote/signal breakdown per historical row not included (only in summary)
- No pagination for history — max 90 rows is sufficient given daily frequency and DB size (~13 rows at time of writing)
- `posture` field in summary computed server-side; could be stored in DB if thresholds change frequently
- Consider a `GET /macro/ssi/compare` endpoint for side-by-side comparison of two date ranges (deferred)

### Edge Cases Not Handled
- `payload_json` column could be NULL for older rows (falls back to empty inputs dict gracefully)
- If `positioning.json` is stale or has schema changes, `long_size_mult`/`short_size_mult` fall back to 1.0 without error
- History `days_available` < `days_requested` when DB has fewer rows than requested — handled and surfaced in response

### Push
- Committed to `docs/mindwealth-api-docs` as `1627656` (parent `4863c2c`)
- Pushed to `divsum127/mindwealth-api-docs` main branch using PAT (PAT removed from remote URL after push)

---

## 2026-06-23 — Fix dominant_reason for all combos

### Task
Refactor `dominant_reason` sentence generation so all 7 named combos produce accurate, status-aware text; backfill Combo C historical hit-rate data; comprehensive tests.

### Implementation assumptions
- Runner-up remains 2nd-highest `PRIORITY` active combo (unchanged rule).
- Hit-rate display uses `combo_hit_rate_stats()` as single source of truth (same as briefing table).
- Combo C historical analog dates (`2008-06-16`, `2022-06-09`, `2025-04-14`) seeded when `daily_readings` lacks WTI/CPI for old dates — flagged in `macro_regime.seed`.

### Key decisions
- Removed `"horizon fit"` claim; replaced with `"on configured priority rank"`.
- Missing HR (`n_obs=0`) → `"No mature hit-rate data at {label} horizon."` not `0%`.
- Duration clause only when `duration_weeks` is positive int; uses middle-dot before `started`.
- Combo G → `"Timing signal only (no validated hit rate)."`
- Deterministic sort: `(-priority, combo_letter)`.

### Things deferred
- Full 1068-Friday named backfill may still be running or incomplete on slow Yahoo pulls; script continues per-date on errors.
- PDF nightly step still requires `reportlab` in venv (JSON write succeeds without it).
- Historical Combo C detection via `detect_named_combos` for pre-2026 dates blocked until WTI/CPI backfill in `daily_readings` — seed dates are interim fix.

---

## 2026-06-24 — Combo D/E per-fire forward-return CSV export

### Task
User requested per-trigger SPX return tables for Combo D (1W–2M) and Combo E (monthly 1M–6M). Prior threshold-sweep batch (`threshold_sweep_v2/*.json`, `export_threshold_raw_returns.py`) held aggregate band stats, not per `combo_fires` date rows at these horizons.

### Implementation assumptions
- One row per distinct `trigger_date` in `combo_fires`; if multiple rows same date, keep highest-status row (ACTIVE > CONFIRMED > WATCH).
- Horizons use NYSE trading-day offsets via `forward_return_pct` (same as nightly engine).
- Combo D/E direction = bearish; `hit_*` columns = 1 when SPX return < 0.
- Mature returns only: `None` when forward window exceeds available ^GSPC history (last price 2026-06-23).

### Backtest period
- **Combo D:** 435 fires, 2010-12-10 → 2026-07-03; max bear hit **39.6% at 1W**.
- **Combo E:** 484 fires, 2010-09-24 → 2026-07-03; max bear hit **30.4% at 1M** (within 1M–6M band).

### Key decisions
- Output under existing `csv_exports/` tree for consistency with geo/tight-liquidity exports.
- Separate CSV per combo plus `combo_de_per_fire_meta.json` for period + horizon summaries.
- Re-run: `python3 scripts/export_combo_de_per_fire_returns.py`

### Things deferred
- E horizons beyond 6M (12M–18M) remain in `combo_e_horizon_sweep.py` artifact only.
- i3 cheatsheet side-by-side diff still blocked (no reference file in repo).

### Edge cases not handled
- `PARTIAL` status rarely seen in production — mapped to `"partial"` verb but not heavily tested live.
- Priority tie if CONFIG collides — tie-break by combo letter only.

### Verification
- `.venv/bin/python -m pytest tests/test_dominant_reason.py tests/test_dominant_priority.py tests/test_api_macro.py` → 52 passed.
- `raw_hit_rate("C", spx_6m, bearish)` → n_obs=3 after seed + forward backfill.
- `runic_output.json` dominant_reason: `Combo F active (week 12, MEDIUM · started 2026-04-03). 79% 6M hit rate. Outranks Combo E (19% 12M) on configured priority rank.`

---

### 2026-06-24 — Combo B WATCH legs 0/3 API fix

**Assumptions:** `confirmed_legs` on WATCH combos should list variables passing their gate today (same rules as ACTIVE fire). UI derives `legs_confirmed/total_legs` from `len(confirmed_legs)`.

**Decisions:** `watch_combos` changed from `["B"]` strings to dicts matching test fixture shape (`legs_confirmed`, `pending`, `confirmed_legs`). `combo_status_row.status` now `WATCH n/3` for readability.

**Edge cases:** If readings missing for a leg variable, leg list empty and combo may not enter WATCH at all (unchanged). Legacy string-only `watch_combos` still parsed via `_watch_combo_map`.

**Deferred:** Production `51.20.53.218:8506` still serves pre-fix JSON until API host reruns nightly / copies updated `runic_output.json`.

**Caveat:** As of 2026-06-23 data, B is **1/3** (CFTC only), not 2/3 — VIX 18.7 (<25, <80th pctile) and HY 265bps (<400, <80th pctile) fail. User expectation of 2/3 does not match current variable readings.

---

### 2026-06-25 — 298-combo promotion analysis (Item 15)

**Assumptions:** Primary horizon `spx_3m` per Part H CONFIG; promotion gate ≥5 fires and ≥80% hit; Step 7 stories treated as pending (all SKIPPED in JSON). Economic rationale drafted manually from variable semantics and fire-date eras, not Claude.

**Key decisions:** Collapse 62 signatures to thematic clusters; recommend 8 canonical signatures for Rohit review rather than promoting all 62. Tier 1 = multi-cycle mechanism + adequate unique dates; Tier 3 = defer 2024 CPI-only (3 unique Fridays) and 2026-forward clusters.

**Edge cases not handled:** v2 shadow regime re-tag not applied; hostile beta HR mostly null (no hostile fires in sample for many combos); duplicate fire dates in raw n_fires (direction permutations).

**Deferred:** Run `run_combo_discovery_pipeline.py --use-claude` on 8-signature shortlist; re-tag with v2 regimes before final promotion; Rohit 55% vs 60% hostile bar.

**Caveats:** `CFTC+VIX+VXTS` is same variable set as Combo D but generic engine infers bullish (post-washout) vs D's bearish framing. `291_combo_tests` was empty at start — populated from `combo_discovery_20260606.json` export.

---

### 2026-06-24 — Combo D & E threshold study

**Assumptions:** Episode = first Friday when gate crosses in-band, 5-day cooldown (matches rarity goal vs 435/484 weekly `combo_fires` rows). D primary horizon = 1W tactical; E primary = 12M structural. Target n band = 15–50 (plan asked 20–40; script used 15–50 for slightly wider search). Sweeps on Friday-aligned readings panel from 2007.

**Key decisions:** Separate D/E date calendars aligned by calendar date for sync/regime overlay. Regime from `regime_json.curve_regime_v2` in DB. Recommendations tiered: CONFIG_BASELINE, BEST_IN_TARGET_N, BEST_ANY_N.

**Findings:**
- No D variant reaches 80% bear @1W with n≥10; max ~57% (VXTS 1.18, CFTC 90, VIX 16, 2-of-3, n=78).
- E reaches 80%+ @12M only with n≤9 (e.g. CAPE 32, NFCI −0.20, CFTC 95, 3-of-3 → n=4, 100% bear @12M).
- CONFIG E @12M = 9% bear (bullish structural bias under current gates).
- D+E sync improves tactical 1W (CONFIG: 60% on 5 sync dates) but 12M stays bullish on sync subset.
- Regime: almost all events in STEEPENING; insufficient n in NORMAL for comparison.

**Deferred:** Apply winning thresholds to `CONFIG.yaml` and regenerate production `combo_fires` (user did not request CONFIG change). E horizons 1M–18M full band in separate prior sweep artifact.

**Caveat:** 80% bear hit + n=20–40 jointly infeasible for D from this data; recommend trade-off between hit rate and sample size explicitly when choosing production gates.

---

### 2026-06-24 — Combo D/E follow-up (production + sync overlay)

**Assumptions:** Case 1 drops 80% target; ranks n≥10 configs by `production_score` = primary bear hit − 0.15×|n−30| + 0.5 if avg SPX negative. Case 2 pairs top-40 D × top-40 E (1600 pairs); sync = same Friday for both episodes.

**Findings:** Max D @1W with n≥10 ≈ 57% (plateau). E @12M with n≥10 peaks at 66.7% (n=10 only); n=20–40 E best ≈ 37% @12M. Sync tactical: CONFIG +18pp @1W on 5 overlap dates; aggregate mean lift −2.8pp (45.8% pairs positive). Sync structural @12M mean 25.8% bear — 49% of pairs bullish (<30% bear); top tactical sync pairs often 0% bear @12M.

**Deferred:** Per-fire export for all 618 sync_n≥3 pairs (only top-5 pairs in CSV).

**Caveat:** Negative mean sync lift means D+E sync is not a universal amplifier — use as conditional tactical filter when both combos share tight gates, not as structural bear confirmation.

---

### 2026-07-03 — All combos A–G threshold study

**Assumptions:** First-crossing episodes, 5d cooldown; F on Fridays only; A uses pctile-band proxy for RARE legs (not full tier engine). Hit = SPX in combo direction.

**Key findings:** B CONFIG 77.8% @3M vs spec 87.5% (n=9 strict 3-of-3). F CONFIG 85.7% @6M beats spec. D/E CONFIG far below spec; sweeps find tighter gates (D 57.7% @1W, E 87.5% @12M at n=9). C n=1, G n=0 on CONFIG — sparse.

**Deferred:** Combo A full tier-engine replay; G vol-spike metric (used SPX bear @3W proxy).

**Caveat:** Spec hit rates from cheatsheet (~4–16 instances); episode replay n differs especially for B/C/G.


---

## 2026-07-03 — Macro scheduled-events API (v1.5.0)

**Design:** New routes only — `GET /macro/regime` and other existing macro endpoints unchanged. Intelligence blocks remain in nightly JSON and dedicated endpoints.

**Endpoints:** `pre-catalyst`, `post-regime`, `calendar?days=1-90`.

**Frontend:** `docs/api/frontend/macro-scheduled-events-integration.md` — Streamlit/HTML layout, labels, refresh cadence. Streamlit `runic_page.py` not yet updated.

**Tests:** `test_api_macro.py` asserts regime lacks new keys; 3 new endpoint tests + nightly JSON block test.

---

## 2026-06-30 — Pre/Post scheduled-event regime intelligence

**Assumptions:** Near-threshold = unconditional_pctile in [60,79] or [21,40]. Fragility HIGH when ≥4 vars and upcoming CPI/FOMC/NFP within 7 days. Post-event window = 48h from scheduled ET release time (CPI/NFP 08:30, FOMC 14:00). Yield deltas from FRED DGS2/DGS10/DGS30 daily closes; USD strength = USDCNH decline %. LIQUIDITY_SHOCK USD threshold default 0.5% (CONFIG `liquidity_shock.usd_strength_pct`).

**Transition priority:** LIQUIDITY_SHOCK → FISCAL_DOMINANCE_FEAR → CREDIBILITY_RESTORED → BEAR_FLATTEN → BULL_STEEPEN.

**Deferred:** `macro_event_snapshots` persistence table for backtest analogs; Investing.com FOMC/NFP without `INVESTING_HTTP_PROXY` (FRED release dates are primary).

**Edge cases:** HY OAS history short pre-2023; weekend/holiday events use trading-day anchors; regime_transition requires ≥2 variables crossing RARE/80th-20th boundaries.

**Caveat:** FOMC dates use FRED release_id 19 (FOMC Press Release); verify against Fed calendar if statement vs press-conference timing matters.

---

## 2026-06-25 — Fed cycle matrix formalisation + Claude temperature fix

**Fed cycle states (confirmed from code):**
- 7 raw states in `fed_cycle.py`: HIKING_EARLY, HIKING_LATE, CUTTING_EARLY, CUTTING_LATE, PAUSING, QE, QT
- QE gate: WALCL MoM > 1.0% OR hardcoded COVID window 2020-03-01 to 2021-06-30
- QT gate: WALCL MoM < −0.5% AND label would otherwise be PAUSING (cannot override hike/cut)
- HIKING_EARLY/LATE boundary: 6 months since cycle start (`cycle_early_months` config)

**What's actually in combo_fires.macro_regime (historical data gap):**
- Only 3 distinct labels: HIKING_LATE (807), CUTTING_LATE (717), QE (599)
- HIKING_EARLY, CUTTING_EARLY, PAUSING, QT do not appear — they were recorded under legacy labels at the time combo fires were computed. This means the hostile filter hits HIKING_LATE but misses any potential HIKING_EARLY fires in historical combos.

**4-state fed_cycle_v2 (formalised, not 3-state):**
- `collapse_fed_cycle_v2()` in `regime_v2_shadow.py` maps 7 → 4: TIGHTENING / PIVOTING / EASING / EASY
- PIVOTING only has n=27 Fridays in DB — practically a rounding error in analytics
- The 3×3 simplification discussed in planning (tightening/easing/pausing) would require merging PIVOTING→EASING and renaming EASY→PAUSING — neither is done

**Hit rate grouping (two systems):**
1. Binary HOSTILE: used in `threshold_sweep_v2.py` and `combo_discovery_pipeline.py`; defined in CONFIG.yaml as `hostile_fed_cycles: [HIKING_EARLY, HIKING_LATE, TIGHTENING]` and `hostile_curve_regimes: [INVERTED]`
2. 4-state slice: `fed_cycle_v2` used in `fm_events.py` for fm_events analytics (testingv2)

**No 28-cell or 9-cell matrix exists anywhere in the codebase.** Deferred: consider building a cross-product (fed_cycle_v2 × curve_regime_v2) analytics query if Rohit requests it.

**Claude temperature fix:**
- `call_claude()` in `_client.py` was missing `temperature` parameter — Anthropic API defaults to 1.0
- Fixed to `temperature=0.0` as default argument
- Determinism also requires pinned model version (handled via MACRO_CLAUDE_MODEL env var / CONFIG.yaml)
- All existing callers get temperature=0.0 without code changes; opt-in for non-deterministic via `temperature=1.0` kwarg

---

## 2026-06-30 — API security hardening (invite-only auth)

**Architecture:** Backend-centric auth in FastAPI. Nuxt/Streamlit are thin clients. Two gates: `X-API-Key` on all routes when `API_KEY` env set; JWT (`Bearer` or `mw_access_token` cookie) for human/chatbot routes.

**Assumptions:**
- `config/users.json` per clone (gitignored); dev admin bootstrapped as `admin@mindwealth.co`.
- Nuxt on `:8512` proxies `/api/v1/*` → FastAPI; sets httpOnly cookie on login/accept-invite.
- `INVITE_BASE_URL=http://51.20.53.218:8512` for invite links.
- Dev API `:8507` bound `0.0.0.0` with API key; Nuxt temporarily points to `:8507` until prod auth code is deployed.

**Deferred / prod rollout:**
- Commit + merge `chatbot-dev` → `chatbot-prod` + `prod-pull-and-restart.sh` before enabling `API_KEY` on prod `:8506`.
- Copy `API_KEY`, `JWT_SECRET`, bootstrap prod `users.json`; switch Nuxt `NUXT_API_BASE_URL` back to `:8506`.
- Streamlit gate defaults to `:8506` — set `MW_AUTH_API_BASE` + `API_KEY` in streamlit service env after prod deploy.
- Rate limits, LLM cost caps, IP allowlist on AWS SG (plan phase 2).
- Rotate keys in `MindWealth/constant.py` (called out in security plan).

**Edge cases not handled:**
- JWT expiry mid-session (1h); no refresh token in v1.
- Password reset flow — admin must resend invite.
- `TestClaudeOverlayFix` now mocks empty CSV path (was failing when real `claude_signals_report.csv` had rows).

**Key decisions:**
- `bcrypt` directly (not passlib) due to compat issues.
- `_configured_api_key()` reads `os.environ` when `API_KEY` key present, else module constant (test patch friendly).
- Chatbot sessions scoped by `owner_email`; `CHATBOT_REQUIRE_USER=true` default.

**Caveats:**
- Initial admin password stored once at `config/.bootstrap_admin_password` (chmod 600) — rotate after first login.
- Teammates need shared `API_KEY` for curl on `:8507` (and `:8506` after prod deploy).
- `DOCS_ENABLED=false` in dev `.env` disables Swagger.

---

## 2026-06-30 — Per-user activity logging

**Assumptions:** Opt-in per user via admin toggle (default off). Logs stored on server only (`activity_logs/`, gitignored). Chat logs user message preview (500 chars), not full LLM responses.

**File layout:**
```
activity_logs/
  admin_at_mindwealth_co/
    profile.json
    navigation.jsonl
    clicks.jsonl
    chat.jsonl
```

**Deferred:** Admin UI to browse/download logs; Streamlit click tracking; retention/rotation policy.

**Edge cases:** sendBeacon on tab close may drop events if cookie expired; logging disabled users get `written: 0` from ingest API.

**Caveats:** Set `ACTIVITY_LOGS_DIR` env to override default path. Toggle in admin PATCH `activity_logging_enabled`.

---

## 2026-06-30 — Dev → prod migration todos document

**Purpose:** Single living doc for `chatbot-dev` → `chatbot-prod` promotion; complements `prod-pull-and-details` skill.

**Rule change:** `.cursor/rules/mindwealth-ui-repository-rules.mdc` now requires updating `docs/dev_to_prod_migration_todos.md` on any task with prod deployment impact.

**Initial content:** Auth hardening + activity logging; documents Nuxt `NUXT_API_BASE_URL=:8507` as dev-only revert item.

---

## 2026-06-30 — API rate limiting

**Architecture:** FastAPI `RateLimitMiddleware` + slowapi `Limiter` on `app.state`. Identity key priority: JWT email → `X-API-Key` hash → client IP. Route rules in `api/rate_limit.py` (tiers 0–5). Nuxt defense-in-depth: `bff-auth.ts` + `bff-rate-limit.ts` on `/api/*` excluding `/api/v1` proxy.

**Assumptions:**
- In-memory `limits` storage (single worker); `RATE_LIMIT_ENABLED=false` in unit tests.
- POST bodies cached in middleware so login email bucket can parse JSON without breaking handlers.
- Read tier uses `30/10seconds;300/minute` for JWT users, `60/10seconds;600/minute` for API-key-only.

**Deferred:** Redis-backed storage for multi-worker; `CHATBOT_DAILY_MESSAGE_CAP`; nginx/AWS edge limits (documented in migration todos only).

**Edge cases:** Global IP + user ceilings stack with route tiers. Login hits email bucket (5/min) before IP (10/min). Health exempt from global IP cap only.

**Caveats:** Restart clears counters. Tune via `config/rate_limits.yaml` (admin/user roles) or `RATE_LIMIT_*` env overrides. Ship to prod with auth deploy.

---

## 2026-07-07 — Role-based rate limits

**Config file:** `config/rate_limits.yaml` — edit `admin` and `user` blocks; `shared` for login brute-force; `apikey` for key-only scripts.

**Admin:** High ceilings (e.g. read 200/10s + 3000/min, chat 30/min + 500/hr) for ops/testing.

**User:** Plan defaults — read 30/10s + 300/min (supports 15–25 parallel page loads); chat 3/min + 30/hr blocks LLM automation.

**Role detection:** JWT `role` claim (`admin` vs `user`). Identity keys include role prefix `user:admin:{email}` vs `user:user:{email}`.

**Deferred:** Full admin bypass flag (using high limits instead); per-user custom overrides in YAML.

---

## 2026-07-09 — Test suite + prod merge readiness

**Root causes fixed:**
- `.env` `API_KEY` leaked into pytest via `load_dotenv()` without override guard → `tests/conftest.py` forces empty key; `load_dotenv(override=False)` in `config_paths.py` / `chatbot/config.py` so explicit env (systemd, tests) wins.
- `combo_c_cancel` tests used shared SQLite without reset → `setUp` zeroes `combo_c_cancel` row.
- Deep-dive missing TSLA rows → `collapse_latest_per_function_interval` skipped when `date_filter_mode=entry_or_exit` (was inferring from empty user_message).
- Shortlist missing `function` → `enrich_record` now emits `function` and `interval`.
- Signals surface `enrich=false` tests obsolete (pipeline persists MasterSpec cols in CSV) → assert runtime-only fields absent (`conviction_score`, `mtm_pct`).

**Result:** 349 pytest passed on full suite (excluding slow integration tests).

**Prod merge:** Curated file list in `docs/dev_to_prod_migration_todos.md` Release A section; Nuxt BFF middleware still separate commit in `MindwealthUI_Vue`.

---

## 2026-06-30 — Release A git commit

**Commit:** `a1cd39f36` on `chatbot-dev`, pushed to `origin`.

**Staged scope:** 44 files only — auth, activity logging, rate limiting (`config/rate_limits.yaml`), test isolation/fixes, migration doc, bootstrap/invite scripts, systemd templates. Excluded macro/combo cross-function WIP, `monitored_trades.json`, threshold sweep artifacts.

**Security:** `config/.bootstrap_admin_password` added to `.gitignore` before commit.

**Next:** Merge `chatbot-dev` → `chatbot-prod`, prod `.env` (`JWT_SECRET`, `RATE_LIMIT_ENABLED`), bootstrap `config/users.json`, Nuxt BFF commit + deploy per migration doc.

---

## 2026-07-16 — F4 v2 steepening driver split (D3)

**Context:** Rohit reply PDF (`Reply of macro regime and threshold experiments report.pdf`) uses letter+number codes for experiment sections — e.g. **F4** = Part F steepening-of-inversion short grid; **B2** = dual percentile storage (unconditional + regime-conditioned); **D3** in the reply = new F4 v2 test (not the HMM “shift-timing” D3 in the original report).

**Implementation:** `scripts/f4_v2_steepening_driver_split.py` reuses F4 v1 event detection (`−50 bps trough`, `+15 bps/4wk steepen` on T10Y2Y), then classifies each fire’s 4-week DGS2/DGS10 moves: BULL (both fell), BEAR (both rose), TWIST (2Y↓ 10Y↑). HY widening = BAMLH0A0HYM2 4wk Δ>0; claims rising = ICSA 4wk Δ>0.

**Key results (n=17, −50/+15 cell):**
- Unconditional benchmark: **29.4%** of all weekly 3m windows SPX-down (not the fixed +2.5% drift proxy).
- Pooled F4 v1: **17.6%** SPX-down 3m — **below** baseline → no short edge.
- By driver: BEAR n=8 (12.5% down), BULL n=5 (20% down), TWIST n=3 (0% down).
- Hypothesis bucket BULL+HY widening: **n=0** (2000 classifies BEAR; 2023 BULL episodes lack concurrent HY widening).
- **Verdict:** split does not rescue F4; steepening-based short gate = NO per spec.

**Assumptions:** Yield driver uses same 4-week Friday window as spread steepening metric. HY series gaps pre-2010 leave some early episodes without HY tag.

**Deferred:** Wire F4 v2 into `run_all.py` Part F; add claims to operational “soft landing” classifier prompt; re-check 2000 yield classification vs economic narrative.

**Prod impact:** None (offline research JSON only).

---

## 2026-07-12 — Release B (macro + cross-function + analysis)

**Commits (chatbot-dev):** `03903169b` macro catalyst/calendar, `55e549085` cross-function exits, `1abfc8876` regime uplift export, `9136c3d8d` combo threshold artifacts, `6cbeaf747` docs/skill, `a577c1775` SSI snapshot.

**Prod merge:** `caff62630` on `chatbot-prod`; prod pull required `git checkout --` on drifted SSI CSVs before fast-forward.

**Excluded:** `monitored_trades.json` (runtime, per-environment).

**API verification:** 21 realistic GET endpoints on `:8506` all 200 (health, auth/me, new macro event routes, signals, portfolio/risk, chatbot with JWT, admin users). OpenAPI sweep: 55/64 GET pass; 9 expected failures (fake UUIDs, missing query params, wrong report dates).

**Deferred:** `94b61f7e6` smoke-script API_KEY fix on `chatbot-dev` only (not yet on prod).

---

## 2026-07-13 — Prod admin password reset

**Cause:** Release A prod bootstrap generated a new random password on prod — different from dev password user had been using.

**Fix:** Reset `admin@mindwealth.co` password hash on prod to match dev/original; synced prod `config/.bootstrap_admin_password`.

**Verified:** Login 200 on `:8506` and Nuxt `:8512`; `/auth/me` 200 with cookie.

---

## 2026-07-11 — Release A prod deploy

**Git:** `chatbot-prod` `1f84f86ad` (merge from `a1cd39f36`); conflict resolved in `scripts/mindwealth-api.service` (prod paths + `EnvironmentFile`).

**Prod runtime:** `.env` gained `API_KEY` (matches `NUXT_API_KEY`), `JWT_SECRET` (from dev), `RATE_LIMIT_ENABLED=true`, auth vars. `config/users.json` bootstrapped via prod venv; password in `config/.bootstrap_admin_password` (chmod 600, prod-only).

**Nuxt:** `presentation-prod` `7661255` — BFF auth + rate-limit middleware; `npm run build`; systemd `mindwealth-ui` now `After/Wants mindwealth-api`, `NUXT_API_BASE_URL=:8506`, `NUXT_PUBLIC_ADMIN_MODE=false`, `NUXT_AUTH_SESSION_MAX_AGE=28800`.

**Smoke tests (all pass):** health 401 without key / 200 with key; chatbot 401 without JWT; BFF 401 without cookie / 200 after login; `conviction_store` = prod path.

**Caveats:** `prod-pull-and-restart.sh` health curl needs `X-API-Key` now (script still curls bare — cosmetic failure). Rotate GitHub PAT if exposed in chat. Admin must change bootstrap password after first login.

---

## 2026-07-07 — v2 regime retag + Part H beta re-run

**Assumptions:** Hostile = TIGHTENING/HIKING fed or INVERTED curve from v2 shadow labels on each fire date.

**Results:** Retagged 13,160 fires; beta survivors 132→127 (−5 non-promo combos failed `beats_regime` or hostile HR=0%); all 62 promotion candidates retained. Eight-theme shortlist hostile HR now real (84–92% on T1).

**Deferred:** Step 7 Claude on shortlist; five promos with zero hostile fires still auto-pass hostile gate.

---

## 2026-07-16 — D4 B4 window audit re-run

**Assumptions:**
- B4 rule from `run_all.py`: structural set `{CAPE, NFCI, WALCL, CURVE, DXY}` → `full`; all others → `rolling_3y`.
- WALCL was changed to `full` in production nightly CONFIG on 2026-06-09; prior audit (2026-06-06/11) never re-run.

**Results:**
- 9/12 variables PASS; B4 `pass=false`.
- WALCL: configured `full`, expected `full` — **fixed, confirmed**.
- HY, VIX, VXTS: configured `full`, expected `rolling_3y` — **still FAIL**.
- Prior audit had 4 failures; current 3 (WALCL resolved).

**Short-gate impact:**
- VIX → combos B, D, G; VXTS → D, G; HY → B, G.
- Wrong windows shift unconditional pctile ranks and combo fire dates for B/D/G sweeps.

**Deferred / open:**
- Rohit 2026-06-11 feedback classifies HY/VIX/VXTS as structural (full) and WALCL MoM as flow (`rolling_3y`) — opposite of coded B4 rule. Needs sign-off before CONFIG patch.
- No CONFIG change applied in this task (audit-only).

**Artifacts:** `testing/macro_th_exp/D4_window_audit_rerun_2026-07-16.json`, `.md`

---

## 2026-07-16 — D5 Fed-cycle re-slicing (recalibrated D/E)

**Context:** Supersedes legacy named-combo-by-fed-cycle table (D 28% down n=452, E 20% down n=507) computed on production CONFIG @ uniform 3M. Recalibrated configs from combo_de threshold sweep (`case1_production_pareto.csv`).

**Configs:**
- D: `D_v1.18_c95_x13_l2` — VXTS≥1.18, CFTC≥95, VIX≤13, 2-of-3; horizons 1W (primary) + 2W.
- E: `E_cape32_nfci-0.15_cftc85_l3` — CAPE≥32, NFCI≤−0.15, CFTC≥85, 3-of-3; horizons 6M/9M/12M.

**Method:** Friday first-cross episodes, 5d cooldown, `fed_cycle_at_date()` legacy labels, bear hit = SPX forward return &lt; 0. Slices with n&lt;10 → CANNOT USE (hit rate not actionable).

**Results (a) — D CUTTING_LATE vs HIKING_LATE spread:**
| Horizon | CUTTING_LATE | HIKING_LATE | Spread | Legacy 3M spread |
|---------|--------------|-------------|--------|------------------|
| 1W | 92.3% (n=13) | 41.7% (n=24) | +50.6 pp | +24.9 pp |
| 2W | 69.2% (n=13) | 33.3% (n=24) | +35.9 pp | +24.9 pp |

Spread **survives** recalibration; magnitude **wider** than legacy at both horizons.

**Results (b) — per-fed sample sizes:**
- D: CUTTING_LATE n=13 USE; HIKING_LATE n=24 USE; QE n=9 **CANNOT USE**.
- E: overall n=10 USE (66.7% bear @ 6M/9M/12M); every fed slice **CANNOT USE** (HIKING_LATE n=5, CUTTING_LATE n=2, QE n=3).

**Caveats:**
- Recalibrated D n=46 vs legacy n=452 — tighter gate, different episode set.
- E n=10 overall — fed-conditioned E stats not reportable until more history.
- CFTC escalation alert is briefing overlay, not an extra detection filter in this run.
- B4 window mismatch (HY/VIX/VXTS) may shift pctile ranks vs post-B4-fix reruns.

**Artifacts:** `testing/macro_th_exp/D5_fed_cycle_reslice_2026-07-16.{csv,json,md}`, `D5_fed_cycle_per_fire_2026-07-16.csv`, `run_d5_fed_cycle_reslice.py`

---

## 2026-07-16 — D6 Quick answers to open macro regime doubts

**Source:** `Reply of macro regime and threshold experiments report.pdf`; section codes A1, A5, B2, F4, Part D map to PDF Parts A–F.

**Resolutions recorded:**
1. **A1 PIVOTING (n=27):** Merge into EASING for analytics/hit-rate slices only; keep PIVOTING in `macro_regime_log_v2` storage.
2. **A5 liquidity:** 9-state `{LEVEL}_{DIRECTION}` storage unchanged; analytics collapse to 2×2 for combo/FM tables (as report A5/A6 recommendation).
3. **A5 NEUTRAL:** Third level in classifier/nightly labels; fold NEUTRAL_* → EASY side for 4-way analytics slice.
4. **Combo C (n=4):** Briefing must not show actionable hit rate — display "insufficient episodes" until n≥5 at `spx_6m`; cancel watch (Part E) still allowed.
5. **HMM (Part D / B2):** Dec 2026 deployment target retained; prototype Risk-Off filter hurt B (−1.2 pp) and D (−1.9 pp) — HMM stays out of short-gating path (B/D/G) until walk-forward shows positive lift.

**Assumptions:**
- D6 supersedes earlier reply-PDF debate on keeping PIVOTING separate for analytics.
- Implementation deferred: `fed_cycle_v2_analytics()`, `collapse_liquidity_v2_analytics()`, Combo C `combo_metadata` min-n guard.

**Deferred (not in D6):** moderate FM drift strip; VIX suppressed 8.5% vs plan 50%; v2 rollback plan; SSI gate; B4 window spec (see D4).

**Prod impact:** None this task (documentation only).

**Artifacts:** `testing/macro_th_exp/D6_open_doubts_resolution_2026-07-16.{md,json}`

---

## 2026-07-16 — D6 implementation (analytics collapse + Combo C min-n)

**Changes:**
- `fed_cycle_v2_analytics()`: PIVOTING → EASING for slice tables only; storage unchanged.
- `collapse_liquidity_v2_analytics()`: 9→4 with NEUTRAL→EASY; optional `walcl_trend_4wk` / `nfci` for FLAT and NEUTRAL_TIGHTENING edge cases.
- `regime_value_for_analytics()` + `slice_by_regime(use_analytics_collapse=True)` for `fed_cycle_v2` and `liquidity_v2`.
- `combo_hit_rate_stats()`: if `n_obs &lt; min_episodes_for_hit_rate` (default 5, Combo C explicit in CONFIG), sets `insufficient_episodes=True`; `format_hit_rate_display` → `"insufficient episodes"`.
- `fm_events.collapse_from_json()` uses analytics fed collapse for experiment instance labels.

**Tests:** 26 passed (`test_regime_v2_experiments`, `test_combo_metadata`, `test_dominant_reason`).

**Prod impact:** CONFIG `combo_hit_rates.C.min_episodes_for_hit_rate: 5` merges to prod on next deploy; briefing PDF/HTML + API `hit_rate_stats` reflect insufficient-episodes string for thin combos.

---

---

## 2026-07-17 — B4 original-spec window fix pipeline

**Authoritative rule:** Original consolidated-plan B4 (structural → `full`: CAPE, NFCI, WALCL, CURVE, DXY; all others → `rolling_3y`). **Rejected** Rohit 2026-06-11 override (HY/VIX/VXTS full, WALCL rolling).

**CONFIG changes:** HY, VIX, VXTS `pctile_window: full` → `rolling_3y`. WALCL unchanged at `full`.

**Recompute:** 7,802 dates; 13,476 row updates; 3,428 pctile/tier changes in `daily_readings`.

**B4 audit:** pass=true; 0 mismatches. `B_twy_and_percentiles.json` refreshed (25,083 dual-pctile rows).

**Sweeps (post-fix panel):** `threshold_sweep_v2_b4_fix/` — B n=7 @100% 3M (VIX≥25); D prod gates n=46 / 56.5% bear @1W; G CONFIG baseline n=0.

**D6 re-slice:** `D6_regime_analytics_2026-07-17.*`

**Feedback backlog:** cheatsheet BLOCKED (no reference); liquidity PARTIAL (D6 CSVs); geo/regime_score PENDING.

**Prod impact:** CONFIG window change affects nightly percentile ranks for HY/VIX/VXTS on deploy; no combo gate threshold change in this task.

---

## 2026-07-17 — D6 smoke tests + regime analytics re-slice

**Smoke (`run_d6_smoke_tests.py`):** 8/8 PASS on dev DB — Combo C n=3 at 6M → insufficient episodes; briefing rows; `macro_service.get_combo_detail('C')`; FM fed slice has no PIVOTING bucket.

**Re-slice (`run_d6_regime_analytics_reslice.py`):** PIVOTING n=27 in storage, merged into EASING in analytics; liquidity 9→4 states; 4 CSVs + JSON/MD report.

**Artifacts:** `D6_smoke_tests_2026-07-17.{md,json}`, `D6_regime_analytics_2026-07-17.{md,json}`, `D6_fm_regime_slices_analytics_2026-07-17.csv`, `D6_combo_fed_cycle_analytics_2026-07-17.csv`, `D6_liquidity_*_2026-07-17.csv`

**Still open:** HMM prompt doc; README analytics vs storage; prod HTTP verify after deploy.

---

## 2026-07-17 — Combo E BEST PRODUCTION SCORE promotion + CFTC escalation

**Decision (Rohit):** Adopt case-1 best production score E gates (n≥10): CAPE≥32, NFCI≤−0.15, CFTC≥85, **3-of-3**. Prefer CFTC crowding over tighter NFCI (−0.4/−0.5) for needle-moving escalation.

**CONFIG before → after:**
| Field | Old | New |
|-------|-----|-----|
| min_of_three | 2 | **3** |
| cape_min | 28 | **32** |
| nfci_easy_max | −0.3 | **−0.15** |
| cftc_min_pctile | 80 | **85** |
| escalation | (none) | lookback 4wk, min rise +5 pctile → `ESCALATION_ALERT` |

**Behavior:**
- 3/3 → `CONFIRMED_3_OF_3`; if CFTC FM pctile rose ≥5 pts vs ~4 weeks prior → `ESCALATION_ALERT`
- 1–2 legs → `WATCH` (was previously CONFIRMED at 2/3)
- Briefing duration shows `CFTC ESCALATION (+X pctile)`; dominant reason includes escalation clause

**Caveats:**
- Combo D still on legacy CONFIG (1.10/85/18) — not promoted in this change
- Historical combo_fires / hit-rate DB still reflect old E fires until backfill replay
- Escalation uses `daily_readings` CFTC pctile as-of prior date; if history thin, alert stays false

**Tests:** `tests/test_combo_e_thresholds.py` — 5 passed with dominant reason suite

**Prod impact:** CONFIG + detector/briefing merge on next chatbot-dev → chatbot-prod deploy (see `dev_to_prod_migration_todos.md`).

---

## 2026-07-17 — Combo D BEST PRODUCTION SCORE promotion (2-of-3)

**Decision:** Promote D gates from `de_threshold_test_analysis.md` case #4 (confirmed by user after recommendation). E already on case #4 from earlier same day.

**CONFIG D before → after:**
| Field | Old | New |
|-------|-----|-----|
| vxts_min | 1.10 | **1.18** |
| cftc_min_pctile | 85 | **95** |
| vix_max | 18 | **13** |
| min_of_three | (implicit 3 / VXTS+VIX then CFTC) | **2** |
| primary / secondary | spx_1w | **spx_1w** / **spx_2w** |

**Detector:** True 2-of-3 via `evaluate_combo_d_legs`; ACTIVE when ≥2 legs; WATCH at 1; VIX gate aligned to **≤** (sweep validation).

**Caveats:** Historical `combo_fires` still old D gates until backfill replay. D still regime-dependent (CUTTING_LATE >> HIKING_LATE per D5).

**Tests:** `tests/test_combo_d_thresholds.py` — 6 passed.

---

## 2026-07-17 — D1 regime bucket feed (Ahil P3)

**Context:** Ahil P3 needs headline stats per regime. Divyanshu owns combo classification history. Sequence after D5 (fed-cycle re-slice on recalibrated D/E) to freeze ADVERSE definition. Report PDF section codes: **B2** = dual percentile storage; **F4** = steepening-of-inversion grid (not in bucket feed); **D5** = recalibrated D/E bear-hit validation.

**Implementation:** `run_d1_regime_bucket_feed.py` replays 446 Fridays (2018-01-01 → 2026-07-17):
- Gates from `macro_intelligence/CONFIG.yaml` (D: VXTS≥1.18/CFTC≥95/VIX≤13 2-of-3; E: CAPE≥32/NFCI≤−0.15/CFTC≥85 3-of-3)
- Dominant = CONFIG PRIORITY (C>B>F>E>D>G>A)
- **ADVERSE:** dominant C/D/E ACTIVE, G ACTIVE, A TIGHT_MONEY
- **MIXED:** conflicting ACTIVE bullish+bearish, or A CONTESTED
- **BENIGN:** else (incl. WATCH-only bearish legs)
- Combo C: sequential 4-Friday cancel replay (not live `combo_c_cancel.active`)
- Daily calendar forward-fill from last Friday

**v1.1 fixes:** v1.0 had C always-active (live DB flag) → 0 BENIGN Fridays; WATCH→MIXED over-classification.

**Output:** 2,149 daily rows — BENIGN 1,617 / ADVERSE 238 / MIXED 294. Fridays: 335 / 49 / 62.

**Assumptions:** F episode persistence uses `combo_fires` ≤ as_of (not fully re-simulated). B/C/F/G gates = CONFIG (not `combo_all_thresholds` alternate sweeps).

**Deferred:** API endpoint `GET /macro/combos/regime-bucket-history`; full combo_fires backfill replay; empirical MIXED threshold tuning.

**Prod impact:** None — CSV/JSON handoff under `testing/macro_th_exp/`.

---

## 2026-07-14 — Test 5 Regime Sharpe uplift (Ahil / Michele demo)

**Goal:** Show whether 5 Runic regime dimensions improve risk-adjusted returns on EW SPY/TLT/GLD/HYG.

**Not previously run:** `regime_backtest.py` only compared Combo B/D hit rates under HMM Risk-Off filter — not portfolio Sharpe.

**Implementation:**
- Script: `testing/5_regime_uplift/run_regime_sharpe_uplift.py`
- Regime source: `macro_regime_log_v2` (Friday v2 shadow), forward-filled daily
- Dimensions: fed_cycle_v2, curve_regime_v2, val_regime, geo_overlay_v2, liquidity_v2 (level bucket)
- Multipliers: v1 economic priors in `multiplier_spec.md`; product clipped [0.40, 1.00]; 1-day lag
- Portfolio: 25% each, monthly rebalance; overlay scales gross exposure (cash 0%)

**Results (2007-04-12 → 2026-07-13):**
- Baseline: Sharpe 0.885, CAGR 7.72%, vol 8.84%, max DD −22.63%
- Overlay: Sharpe 0.938, CAGR 6.39%, vol 6.85%, max DD −17.59%
- Sharpe uplift +0.053; CAGR −1.33pp (de-risking tradeoff)

**Michele narrative:** Regime layer improves Sharpe and drawdown at cost of raw return — risk-adjusted value proposition.

**Deferred:**
- Empirical multiplier calibration from dimension→SPX stats (overfit risk if done in-sample)
- Asset-specific tilts (e.g. boost TLT in INVERTED) vs gross scaling only
- Daily `build_regime_v2()` vs Friday forward-fill sensitivity
- EUR=X excluded per spec

**Prod impact:** None (testing artifacts only).

---

## 2026-07-19 — Backend API endpoint health audit

**Goal:** User reported dashboard “Avg Fwd win rate: Could not compute” / blank win-rate chart; verify whether MindWealth API backend is failing.

**Servers tested:**
- Prod API: `http://127.0.0.1:8506` — `mindwealth-api.service`, **v1.7.3**
- Dev API: `http://127.0.0.1:8507` — git clone reload, **v1.8.0**
- Nuxt BFF: `http://127.0.0.1:8512` — `mindwealth-ui.service`

**Prod sweep (97 routes, API key auth):**
- 55× HTTP 200
- 27× skipped (require JWT bearer — auth/chat/admin)
- 3× HTTP 404 — not deployed on prod yet: `GET /analytics/analyst/alerts`, `GET /analytics/analyst/brief`, `GET /overwatch/stream` (added in chatbot-dev v1.8.0)
- 3× client timeout at 10s — `POST /conviction/pipeline/daily`, `POST /macro/run-nightly`, `POST /signals/check-degradation` (long-running; not 5xx)
- 0× HTTP 5xx

**Dashboard-specific:**
- `GET /api/v1/analytics/performance` returns 200 with `avg_fwd_testing_win_rate: 57.85`, `avg_win_rate: 83.61`, 69 records when called directly.
- Nuxt `loadDashboard()` calls `loadPerformance()` in parallel with ~7 other backend calls. Journal shows bursts of `429 Too Many Requests` on performance, shortlist, sigma, runic/nightly, overlay-file (2026-07-19 ~17:27 UTC).
- When outstanding signals load but performance fetch returns null (429), BFF still returns partial dashboard: KPI shows `UNAVAILABLE_COMPUTE` (“Could not compute”) and `awaiting API aggregate`; win-rate chart omitted.
- Rate limit config (`config/rate_limits.yaml`): `apikey.read = 60/10seconds;600/minute`. Nuxt uses single `NUXT_API_KEY` for all BFF→API calls from localhost.

**Assumptions:**
- Screenshot API badge “v1.7.3” = prod `:8506`, not dev `:8507`.
- Endpoint sweep at 17:27 may have contributed to transient 429s; parallel dashboard simulation (10 calls) succeeded after cooldown.

**Deferred / recommendations:**
- Raise `apikey.read` burst limit or exempt `127.0.0.1` BFF from apikey bucket.
- Add BFF-side caching/dedup for dashboard bundle.
- Deploy chatbot-dev → chatbot-prod (v1.8.0) for analyst/overwatch routes.
- Frontend `PerformanceApiResponse` does not map `avg_fwd_testing_win_rate` (uses `avg_win_rate` = Latest Performance section); separate from “Could not compute” but affects label accuracy.

**Prod impact:** Investigation only; no git changes. v1.8 deploy would add 3 routes currently 404 on prod.
