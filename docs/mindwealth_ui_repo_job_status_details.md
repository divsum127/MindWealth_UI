# MindWealth UI — Job Status Details

Implementation detail log for MindWealth UI (`/home/ubuntu/uiv2/git/MindWealth_UI`).

This file captures minute-level implementation context for each completed task:
- Assumptions made
- Things deferred or left for future improvement
- Edge cases identified but not handled
- Architecture/design decisions and trade-offs
- Caveats for the next developer

---

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
