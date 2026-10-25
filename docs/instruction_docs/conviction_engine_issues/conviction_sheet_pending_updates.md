# Conviction tab — pending sheet updates and progress log

Running log while the CE to-dos are worked. **Nothing below is written to the sheet yet.**
The user reviews this file and approves one batch write at the end
(spreadsheet `mindwealth todos`, tab `conviction`; row = CE number + 1).

Columns: F = Status, G = Questions to Rohit sir, H = Temp status.

## Already written (2026-10-25, user-confirmed)

19 rows (F/H): CE-01, 02, 03, 04, 05, 07, 09, 14, 15, 16, 17, 19, 22, 26, 28, 33, 41, 42, 50.

Second batch, 37 cells (user-confirmed, read back 37/37): CE-06, 10, 11, 12, 13, 14, 18, 20, 21, 28, 29, 31, 32, 34, 35, 37, 38, 39, 43, 48, 51.

<details><summary>Second batch as written</summary>

| Row | CE | Column | Previous | Written |
|---|---|---|---|---|
| 29 | CE-28 | F | Inprogress | Pending from Rohit sir |
| 29 | CE-28 | G | (empty) | Model choice: Sonnet 5.5 matches Opus 5.5 on 9 of 10 values at about 1/3 cost. Switch the default? Review the opposing-evidence length cap before wider runs? |
| 29 | CE-28 | H | Moved to claude-opus-5-5; NVDA/GOOG pilot ready ($5 cap), not run. | Pilot run 25 Oct: $3.50 of $5. NVDA +2 (Opus) / +3 (Sonnet), GOOG 0 / 0. Report: reports/conviction_agent_pilot_2026-10-25/ |
| 11 | CE-10 | F | Not started | Inprogress |
| 11 | CE-10 | H | (empty) | Dev: market_cap, pe_ratio, fundamental_anomaly_flag (+reasons) in overlay and core payload map. Also fixed: pe_ttm / pe_ttm_adjusted / one-off fields never reached the overlay. Live from next nightly. |
| 13 | CE-12 | F | Not started | Inprogress |
| 13 | CE-12 | H | Verify first. | Verified on dev: sizer maps conviction N/A (ETF/FX/index/commodity) to base size, never BLOCKED (portfolio_service.py:896; 2 tests). Prod pending. |
| 12 | CE-11 | F | Not started | Inprogress |
| 12 | CE-11 | H | (empty) | All report-only/v5/"7 auto + 8 manual" copy is in the Nuxt repo; exact file:line fixes handed to Parth (docs/instruction_docs/conviction_engine_issues/parth_conviction_ui_handoff_2026-10-25.md §1). |
| 35 | CE-34 | H | (empty) | Backend types ready (telco/regulated_utility/holding_company + business_type_label); chip spec in Parth hand-off §2. |
| 38 | CE-37 | H | (empty) | API fields exist; panel spec in Parth hand-off §5. |
| 39 | CE-38 | H | Partly done. | Partly done; BQ drill link spec in Parth hand-off §5. |
| 36 | CE-35 | F | Not started | Pending from Rohit sir |
| 36 | CE-35 | G | (empty) | Which portfolio is "held": your holdings sheet, personal holdings file, or the model book? |
| 36 | CE-35 | H | (empty) | Root cause: panel is fed from top-conviction signals, not holdings; MTM hard-coded "—". FD "stable" is real (3-of-5 rule; 129/136 stable). Fix spec in Parth hand-off §7. |
| 14 | CE-13 | F | Not started | Inprogress |
| 14 | CE-13 | H | (empty) | Answer drafted: +4 cap is the 1 Sep F rule for types with no valuation module; note shows only when the cap bites (BDGI.TO +1). IBKR now +4 uncapped. |
| 19 | CE-18 | F | Not started | Inprogress |
| 19 | CE-18 | H | (empty) | Answer drafted: hardware = net margin ≥ 40%; debt purpose from Rohit's 24 May v5 brief Part 4. |
| 21 | CE-20 | F | Not started | Inprogress |
| 21 | CE-20 | H | (empty) | Business-type universe CSV + watch sheet comparison (55/62 in store; missing CRWV, CDNS, SAMS.PA, SNPS, FISV) in reports/conviction_recalc_2026-10-25/. |
| 32 | CE-31 | F | Not started | Inprogress |
| 32 | CE-31 | H | Verify first. | Verified built: four-book engine (base/+SSI/+conviction/combined) + API for Ahil's re-run. Answer in reply draft. |
| 33 | CE-32 | H | Likely stale; confirm. | Superseded: Rohit 6 Aug "Conviction sizing: accept as implemented." Close after reply. |
| 40 | CE-39 | F | Not started | Inprogress |
| 40 | CE-39 | H | Verify first. | Contradictions tab is wired to daily alerts; positions panel = CE-35 (no holdings source). |
| 44 | CE-43 | F | Not started | Inprogress |
| 44 | CE-43 | H | (empty) | Answer drafted (prod recalc is ops-only). Field-definitions rewrite + tagging Ahil still to do. |
| 49 | CE-48 | F | Not started | Completed |
| 49 | CE-48 | H | Verify first. | Verified 25 Oct: git push --dry-run authenticates; credentials work (migration note was stale). |
| 52 | CE-51 | H | Verify first. | M&A flag built (ma_activity.py + weekly script) but not scheduled in crontab; earnings-call LLM module not built; KXS/MSFT audit no record; v5 Part 8 questions stale. |
| 15 | CE-14 | H | Verified on dev: B1–B4, source field, 20% size cap. GOOGL path in reply. | Verified on dev; GOOGL path answered in reply (B3, adj P/E 31.6× vs 15.9×). |
| 22 | CE-21 | F | Not started | Inprogress |
| 22 | CE-21 | H | (empty) | Correction written (docs/instruction_docs/conviction_engine_issues/consolidated_note_2026-07-28_section_5_7_correction.md); attach to reply. Remaining 40% hardware cut-off flagged to Rohit (E2 says no threshold). |
| 30 | CE-29 | F | Not started | Inprogress |
| 30 | CE-29 | H | Committed 23 Sep. | Scope written (sp500_point_in_time_bq_replay_scope.md): quarterly 2010–26, PIT SEC facts, ~5–8 days build, no API cost. Build not started. |
| 7 | CE-06 | H | (empty) | Documented overrides done via config/conviction_business_type_overrides.json; automatic dominant-segment detection needs segment revenue data (SEC segment XBRL) — not built. |

</details>

Third batch, 60 cells (user-confirmed, read back 60/60): dev-done rows → Completed in the `macro_tasks` format — CE-01, 02, 03, 05, 10, 12, 14, 17, 19, 22, 26, 31. H and the first line of J carry "prod pending merge" (CE-12 and CE-31 are already live on prod). K written with line breaks between sections.

<details><summary>Third batch as written</summary>

| Row | CE | Column | Previous | Written |
|---|---|---|---|---|
| 2 | CE-01 | F | Inprogress | Completed |
| 2 | CE-01 | H | (current temp status) | Done on dev, prod pending merge. |
| 2 | CE-01 | J | (empty) | Done on dev, prod pending merge. SBUX now stays a compounder, labelled mature/transitioning, and the override is kept in a reviewed config file so every full recalculation keeps it. |
| 2 | CE-01 | K | (empty) | Visible issue / - The dividend-yield rule would reclassify SBUX as income on the next full recalculation. / Root cause (what I found) / - No persisted override existed for a reviewed business-type decision. / Fix (what I did) / - Added config/conviction_business_type_overrides.json (SBUX, with your 24 Sep wording and source) read on every classification. / Verified / - Full dev recalc 25 Oct: SBUX compounder, label shown in the API. / Remaining / - Prod promotion pending. |
| 2 | CE-01 | L | (empty) | 2026-10-25 |
| 3 | CE-02 | F | Inprogress | Completed |
| 3 | CE-02 | H | (current temp status) | Done on dev, prod pending merge. |
| 3 | CE-02 | J | (empty) | Done on dev, prod pending merge. P/E history now scores 20+ years full, 10 to 20 years provisional with years and source shown, and under 10 years neutral. |
| 3 | CE-02 | K | (empty) | Visible issue / - Engine ran a strict 20-year rule; names with 10–20 years got no P/E percentile at all. / Root cause (what I found) / - Only one gate existed; a stale insufficient flag also kept full-history names (AAPL, WMT, SBUX) out of the P/E tax. / Fix (what I did) / - Three tiers per your 21 Sep policy; the flag is now reset both ways; no metadata scores neutral. / Verified / - Dev recalc: 18 full, 16 provisional, rest neutral; audit API reports the tiered policy. / Remaining / - Prod promotion pending. |
| 3 | CE-02 | L | (empty) | 2026-10-25 |
| 4 | CE-03 | F | Inprogress | Completed |
| 4 | CE-03 | H | (current temp status) | Done on dev, prod pending merge. |
| 4 | CE-03 | J | (empty) | Done on dev, prod pending merge. Specials are classified in the ingest using your two-of-three gate, and a cut that touches an unclassified outlier or a gap in the record is held, not scored. |
| 4 | CE-03 | K | (empty) | Visible issue / - Specials and frequency changes could corrupt the dividend-cut comparison. / Root cause (what I found) / - No ingest classifier; the cut used median-gap cadence. / Fix (what I did) / - Two-of-three gate (announcement retrieved, type word, amount outlier vs own trailing median); declared annual amounts by covered period with specials excluded; data-gap detection. / Verified / - PPL.TO frequency change not flagged; TD data hole held; tests pass. / Remaining / - Announcement text source needed for the first two legs (CE-23). Prod promotion pending. |
| 4 | CE-03 | L | (empty) | 2026-10-25 |
| 6 | CE-05 | F | Inprogress | Completed |
| 6 | CE-05 | H | (current temp status) | Done on dev, prod pending merge. |
| 6 | CE-05 | J | (empty) | Done on dev, prod pending merge. SFTBY is now treated as a holding company and shows COVERAGE INCOMPLETE rather than counting as a telco. |
| 6 | CE-05 | K | (empty) | Visible issue / - SFTBY was counted as a telco. / Root cause (what I found) / - yfinance lists it as Telecom Services. / Fix (what I did) / - Holding-company override in the reviewed config, citing your 24 Sep remark. / Verified / - Dev recalc: holding_company, COVERAGE INCOMPLETE. / Remaining / - Prod promotion pending. |
| 6 | CE-05 | L | (empty) | 2026-10-25 |
| 11 | CE-10 | F | Inprogress | Completed |
| 11 | CE-10 | H | (current temp status) | Done on dev, prod pending merge. |
| 11 | CE-10 | J | (empty) | Done on dev, prod pending merge. Market cap, P/E and a fundamental anomaly flag now go into the nightly payload from the Conviction Engine. |
| 11 | CE-10 | K | (empty) | Visible issue / - Payload lacked market_cap, pe_ratio and an anomaly flag (26 Aug G1(a)). / Root cause (what I found) / - Fields were never written to the overlay; raw and adjusted P/E were missing from it too. / Fix (what I did) / - Added the fields to the overlay rows and the payload map; flag fires on P/E < 5 or > 80, negative book value, net income larger than revenue. / Verified / - 23 Oct signal file: fields present, 3 of 26 flagged. / Remaining / - Prod promotion pending; first nightly after deploy fills them. |
| 11 | CE-10 | L | (empty) | 2026-10-25 |
| 13 | CE-12 | F | Inprogress | Completed |
| 13 | CE-12 | H | (current temp status) | Done on dev and prod (already live). |
| 13 | CE-12 | J | (empty) | Done, live on dev and prod. FX, ETF, index and commodity names map to not applicable and base size in the sizer, never BLOCKED or zero. |
| 13 | CE-12 | K | (empty) | Visible issue / - Non-equities risked BLOCKED → $0 sizing (15 Jul D2). / Root cause (what I found) / - Already handled in the sizer. / Fix (what I did) / - None needed; verified. / Verified / - portfolio_service.py base-size path; 2 tests; same code on prod. / Remaining / - None. |
| 13 | CE-12 | L | (empty) | 2026-10-25 |
| 15 | CE-14 | F | Inprogress | Completed |
| 15 | CE-14 | H | (current temp status) | Done on dev, prod pending merge. |
| 15 | CE-14 | J | (empty) | Done on dev, prod pending merge. Adjusted EPS follows your B1 to B4 order with the source recorded, SPK is on its disclosed 11.9c, and more than 20% unidentified income caps size, not score. |
| 15 | CE-14 | K | (empty) | Visible issue / - Adjusted EPS hierarchy, SPK figure and GOOGL path (1 Sep B). / Root cause (what I found) / - Built on dev earlier; not confirmed to you. / Fix (what I did) / - Verified B1–B4 with adjusted_eps_source, the 20% size cap, and GOOGL's path (B3; adjusted P/E 31.6× vs 15.9× raw). / Verified / - Dev store after 25 Oct recalc. / Remaining / - Prod promotion pending. |
| 15 | CE-14 | L | (empty) | 2026-10-25 |
| 18 | CE-17 | F | Inprogress | Completed |
| 18 | CE-17 | H | (current temp status) | Done on dev, prod pending merge. |
| 18 | CE-17 | J | (empty) | Done on dev, prod pending merge. The deal-delay tax now applies only at 4x forward revenue or above. |
| 18 | CE-17 | K | (empty) | Visible issue / - Deal-delay tax should apply only at EV/forward revenue ≥ 4x (1 Sep C5). / Root cause (what I found) / - Built on dev earlier. / Fix (what I did) / - Verified the 4x gate in scoring. / Verified / - Code and dev recalc. / Remaining / - Prod promotion pending. |
| 18 | CE-17 | L | (empty) | 2026-10-25 |
| 20 | CE-19 | F | Inprogress | Completed |
| 20 | CE-19 | H | (current temp status) | Done on dev, prod pending merge. |
| 20 | CE-19 | J | (empty) | Done on dev, prod pending merge. G2 is excluded for hardware and semis with search-first sourcing, the supply-constraint flag is separate from deal delay, and the GOOGL buyback trigger now fires on real data. |
| 20 | CE-19 | K | (empty) | Visible issue / - E3 sourcing, E4 GOOGL buyback trigger, E5 supply flag (1 Sep). / Root cause (what I found) / - Built on dev; GOOGL's trigger could not fire earlier for lack of prior-year data. / Fix (what I did) / - Verified all three. / Verified / - GOOG buyback penalty −2 matches Alphabet's Q2 2026 10-Q (no repurchases in H1). / Remaining / - Prod promotion pending. |
| 20 | CE-19 | L | (empty) | 2026-10-25 |
| 23 | CE-22 | F | Inprogress | Completed |
| 23 | CE-22 | H | (current temp status) | Done on dev, prod pending merge. |
| 23 | CE-22 | J | (empty) | Done on dev, prod pending merge. SONY no longer shows the old 100th-percentile P/E, and each record now stores the issuer's country separately from the ticker. |
| 23 | CE-22 | K | (empty) | Visible issue / - SONY kept pe_percentile 100 / P/E tax −3 on a thin series. / Root cause (what I found) / - Records without P/E history metadata kept a stale percentile. / Fix (what I did) / - No metadata scores neutral; issuer_country stored. / Verified / - SONY neutral, tax 0, Japan. / Remaining / - Prod promotion pending. |
| 23 | CE-22 | L | (empty) | 2026-10-25 |
| 27 | CE-26 | F | Inprogress | Completed |
| 27 | CE-26 | H | (current temp status) | Done on dev, prod pending merge. |
| 27 | CE-26 | J | (empty) | Done on dev, prod pending merge. All 198 records were recalculated on dev with no errors, and the full before-and-after list is ready for you before anything goes to prod. |
| 27 | CE-26 | K | (empty) | Visible issue / - Dev store last fully recalculated 27 Aug; you asked for the change list before prod (1 Sep G3). / Root cause (what I found) / - Recalc waited on SBUX, P/E and dividend decisions. / Fix (what I did) / - Full recalc after those changes; diff of every scoring field. / Verified / - 198/198 updated, 0 errors; reports/conviction_recalc_2026-10-25/. / Remaining / - Send the list; prod recalc is an ops step. |
| 27 | CE-26 | L | (empty) | 2026-10-25 |
| 32 | CE-31 | F | Inprogress | Completed |
| 32 | CE-31 | H | (current temp status) | Done on dev and prod (already live). |
| 32 | CE-31 | J | (empty) | Done, live on dev and prod. The SSI ceiling and conviction tiers feed Ahil's four-book attribution: base, with SSI, with conviction, and combined. |
| 32 | CE-31 | K | (empty) | Visible issue / - Feed for Ahil's four-book attribution (21 Jul, chased 6 and 22 Aug). / Root cause (what I found) / - Built on dev. / Fix (what I did) / - Verified the four-book engine and its API. / Verified / - src/portfolio_nav/four_book_engine.py; same file on prod. / Remaining / - None. |
| 32 | CE-31 | L | (empty) | 2026-10-25 |

</details>

## Pending batch

_Loop batch (25 Oct) — Nuxt dev branch, built and live on 8514; Nuxt files left uncommitted on `ui-dev` (that checkout also holds others' uncommitted work)._

| Row | CE | Column | Current | Proposed |
|---|---|---|---|---|
| 12 | CE-11 | F | (current) | Completed |
| 12 | CE-11 | H | (current) | Done on dev (8514), prod pending merge. |
| 12 | CE-11 | J | (empty) | Done on dev, prod pending merge. Report-only wording is in: the yield-trap banner and depth panel say the engine would cancel (quant signal unchanged), the home page says it reports a verdict rather than modifying sizing, v5 is now v6, the dims read 10 data + 5 agent (request-only), and the sizing list is labelled report only. |
| 12 | CE-11 | L | (empty) | 2026-10-25 |
| 34 | CE-33 | F | (current) | Completed |
| 34 | CE-33 | H | (current) | Done on dev (8514), prod pending merge. |
| 34 | CE-33 | J | (empty) | Done on dev, prod pending merge. The conviction page has a Score any ticker view: type a symbol and get the full breakdown (BQ components, valuation tax, FS, P/E history, verdict if a BUY fired). Stored names are read as stored; others are fetched live and never added to the store. |
| 34 | CE-33 | L | (empty) | 2026-10-25 |
| 35 | CE-34 | F | (current) | Completed |
| 35 | CE-34 | H | (current) | Done on dev (8514), prod pending merge. |
| 35 | CE-34 | J | (empty) | Done on dev, prod pending merge. COVERAGE INCOMPLETE now has its own grey badge and breakdown bucket; before this, the page mapped it to CANCEL, which is why CNU.NZ read CANCEL on 28 Sep. The reviewed business-type label (e.g. mature/transitioning compounder) shows in the drawer. |
| 35 | CE-34 | L | (empty) | 2026-10-25 |
| 37 | CE-36 | F | (current) | Inprogress |
| 37 | CE-36 | H | (current) | Degrading rule fixed on dev; tab click-through needs a logged-in check on 8514. |
| 38 | CE-37 | F | (current) | Completed |
| 38 | CE-37 | H | (current) | Done on dev (8514), prod pending merge. |
| 38 | CE-37 | J | (empty) | Done on dev, prod pending merge. The yield-trap card now separates fired from watching (1 of 2 conditions); the Engine Layers views were already wired to the API breakdowns. |
| 38 | CE-37 | L | (empty) | 2026-10-25 |
| 39 | CE-38 | F | (current) | Completed |
| 39 | CE-38 | H | (current) | Done on dev (8514), prod pending merge. |
| 39 | CE-38 | J | (empty) | Done on dev, prod pending merge. Each signal row has BQ drill (opens the drawer on the BQ tab) and FS → (full financial-strength view). |
| 39 | CE-38 | L | (empty) | 2026-10-25 |
| 40 | CE-39 | F | (current) | Completed |
| 40 | CE-39 | H | (current) | Done on dev (8514), prod pending merge. |
| 40 | CE-39 | J | (empty) | Done on dev, prod pending merge. Contradictions come from the daily alerts; the former Portfolio positions panel is now titled Top conviction signals (not holdings) with MTM hidden until a holdings source is chosen (CE-35). |
| 40 | CE-39 | L | (empty) | 2026-10-25 |
| 37 | CE-36 | H | (current) | Fixed on dev: "degrading" now follows the backend drift rule (forward WR below 61%), never the BT-vs-FWD gap, in function health, the sidebar and the function popup — a 75% forward WR no longer reads degrading. Tab routing checked in code; a logged-in click-through on 8514 still to confirm. |
| 44 | CE-43 | F | Inprogress | Completed |
| 44 | CE-43 | H | (current) | Done on dev, prod pending merge. |
| 44 | CE-43 | J | (empty) | Done. Parked payload field definitions rewritten against the current Nuxt site and today's fields (MindWealth/instruction_docs_2/signals_master_spec/pending_prompt_merge.md); prod-recalc comment answered in the reply; WhatsApp tag for Ahil drafted (reports/conviction_recalc_2026-10-25/AHIL_WHATSAPP_DRAFT.md) for you to send. |
| 44 | CE-43 | L | (empty) | 2026-10-25 |
| 51 | CE-50 | F | Inprogress | Completed |
| 51 | CE-50 | H | (current) | Done (docs only, no prod step). |
| 51 | CE-50 | J | (empty) | Done. Conviction hub decisions ledger and open questions updated for 21/24 Sep; asset map re-verified 25 Oct (87 paths, 0 failing; P/E, dividend and coverage traps rewritten); memory layer re-synced; stale PAT note corrected in the migration doc. |
| 51 | CE-50 | L | (empty) | 2026-10-25 |

## Progress log

- 2026-10-25 — CE-28 pilot run ($3.50 of $5): report `reports/conviction_agent_pilot_2026-10-25/SUMMARY.md`.
- 2026-10-25 — CE-10 done on dev (UI engine overlay fields + core `send_email.py` lookup map). Found: payload P/E fields were never in the overlay CSV; fixed in the same change.
- 2026-10-25 — CE-12 verified already built and tested on dev; nothing to change.
- 2026-10-25 — CE-11/34/37/38: Vue-side only; Parth hand-off note written (Nuxt repo is outside the editable scope).
- 2026-10-25 — CE-35 diagnosed (Nuxt: no holdings source, MTM hard-coded; FD stable is genuine). Needs Rohit's choice of holdings source.
- 2026-10-25 — Verified CE-31 (built), CE-39 (alerts wired), CE-48 (push auth OK), CE-51 (M&A built not scheduled; earnings-call not built). CE-20 report + watch-sheet comparison. Answers for CE-13/14/18/20/31/35/43 added to the reply draft.
- 2026-10-25 — CE-21 Section 5.7 correction written; CE-29 replay scope written; CE-06 override mechanism noted; migration doc PAT note corrected (push auth works).
- 2026-10-25 — Second batch written to the sheet (37 cells, user-confirmed). Tab now: 32 Inprogress, 11 Not started, 5 Pending from Rohit sir, 2 Pending from Ahil, 1 Completed.
- 2026-10-25 — Third batch written (60 cells, 12 rows → Completed, dev-done with prod pending). Tab now: 13 Completed, 20 Inprogress, 11 Not started, 5 Pending from Rohit sir, 2 Pending from Ahil.
- 2026-10-25 — Loop iteration 1: Nuxt dev changes for CE-11/33/34/36/37/38/39 built and live on 8514 (`npm run build`, dev UI restarted; 143 Nuxt tests pass; no new type errors). Found and fixed: COVERAGE INCOMPLETE mapped to CANCEL in the UI; missing P/E percentile shown as 0th; "degrading" used the BT-vs-FWD gap the backend spec rules out. Nuxt changes uncommitted on `ui-dev` (mixed with others' WIP).
- 2026-10-25 — CE-43: parked field definitions updated (overlay gap, coverage_incomplete, 25 Oct fields, Nuxt path); Ahil WhatsApp drafted.
- 2026-10-25 — CE-50: asset map updated + verified (0 failing), memory sync run (hubs regenerated; ledger rows kept).
