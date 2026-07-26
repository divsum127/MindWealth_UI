# Status File — 11 July Consolidated Feedback Email

Source: `instruction_docs/chat_ques/11july_mail.md` (Rohit's "Consolidating everything currently open across the platform" email — Part 1 backend/methodology for Divyanshu/Ahil, Part 2 frontend for Parth).

**Note on source file:** `11july_mail.md` is 32 lines and cuts off mid-sentence at the very last line ("Individual function click-thr..."). That final Part-2B item could not be assessed — its full text isn't available in the saved file.

## Legend

| Tag | Meaning |
|---|---|
| ✅ DONE | Confirmed fixed/implemented, with evidence cited |
| 🟡 PARTIAL | Some part done; decision/sign-off or remainder still open |
| ❌ PENDING | Not found done anywhere; still open |
| ❓ UNVERIFIED (frontend) | Likely a Parth/Vue-side fix; no record in the repos available here |
| ⚪ N/A | Not independently actionable / already answered by design |

---

## PART 1 — Backend / Methodology (Divyanshu, Ahil)

### 1. FX assets "Could not compute" → BLOCKED → $0 sizing
**Ask:** Most FX pairs (EURUSD, USDCHF, CAD=X, NZDCAD, GBPSGD, NZDUSD) show "Could not compute" on Sized Allocations — is this a missing BQ/conviction score for FX, or a sizing-formula gap? Fix or advise root cause.

✅ **DONE (root cause fixed, asset-class-agnostic).** Root cause: conviction overlay sets `verdict=NOT_APPLICABLE` with `bq_raw=NaN` for any non-single-stock asset (ETFs, indexes, **and FX**, since the Conviction Engine is single-stock only); the sizer's `_bq_tier(nan)` was returning `BLOCKED → 0%` instead of a base allocation. Fixed in `api/services/portfolio_service.py` — NaN BQ now normalized via `_safe_float`, D2 logic applies a **base size (100% of cluster slot share)** to all `not_applicable` rows instead of blocking them to zero, `_bq_tier` hardened against NaN. Documented explicitly in `instruction_docs/portfolio_page/portfolio_implementation_log.md` §"D2 fix — ETF / FX / commodity base size": *"NOT_APPLICABLE assets (ETFs, FX, indexes) were sometimes tiered as BLOCKED → $0... Fix: tier N/A, share 100% of cluster slot (base size), never blocked to zero."* Marked **Done** in that doc's status table. Job-status entry references the ETF/index example tickers (^GSPC, FXI, EFA, EWJ) specifically, but the fix itself is generic to any `NOT_APPLICABLE` verdict — so FX pairs go through the identical code path. Regression tests added in `tests/test_api_portfolio.py`.
Files: `api/services/portfolio_service.py`, `tests/test_api_portfolio.py`, MindwealthUI_Vue display files (`constants/unavailable.ts`, `utils/portfolio-display.ts`, `components/portfolio/PortfolioClusterCard.vue`, `PortfolioPnlView.vue`).

### 2. Cluster weight % unclear / possibly double-counted (351%, 270%, 196.8%)
**Ask:** Confirm exact numerator/denominator; rule out double-counting from assets held by 3–4 functions simultaneously. Ahil to sanity-check correlation matrix (lookback, source, staleness).

✅ **DONE (investigated and largely mitigated) / 🟡 one structural gap still open.** This exact question (with the same 351%/270%/196.8% figures) was independently re-raised in a later "21-July review" and formally investigated 2026-07-23 (see `docs/mindwealth_ui_repo_job_status_details.md`, "Investigate: cluster weight >100% double-counting concern"). Finding: the literal math bug was already patched **2026-07-18** — `get_portfolio_sizer()` Pass 2 splits each cluster's *fixed* `budget_usd` proportionally across every eligible position row via `_cluster_rank_weight`; duplicate-ticker rows (same asset, multiple functions) each get a bounded **slice of the one shared pool**, not an independent additive grant, so a cluster's total cannot mathematically exceed its own cap. Numerator = cluster's summed `allocation_usd`; denominator = `get_portfolio_notional()`. Regression test: `tests/test_api_portfolio.py::assertLessEqual(deployed_usd, budget_usd)`. Frontend (`PortfolioRiskView.vue`, committed 2026-06-24) already clamps the fill-bar to `Math.min(100, ...)`, so a literal ">100%" reading shouldn't render live today from either side.
**Still open:** the real structural fix (D1 NAV/N admission-slot model, sleeve weights that sum to true 100% of NAV) exists in `api/services/sizing_engine.py::compute_d1_sizing()` but is **not the default** — only active behind `SIZING_ENGINE_VERSION=d1_slots`; the legacy (07-18-patched) engine still runs by default. Breach-recommendation dollar math still reads legacy cluster-% figures, not "true weights" (flagged as "D7 blocked" elsewhere). Ahil's correlation-matrix sanity-check (source/window/staleness) — `_load_correlation_matrix()` already exposes `source`, `window_days`, `as_of`, `age_days` metadata, but no written reply to Ahil confirming this was found.

### 3. (Parth) Live P&L — can't scroll to see all 18 flagged Cross-Function Exit Conflicts
**Ask:** List appears cut off with no way to scroll; likely same root cause as signal-detail popup scroll bug.

❓ **UNVERIFIED (frontend).** No scroll/overflow-container fix found in either job-status doc. The underlying data feature (Cross-Function Exit Conflicts) is itself ✅ done (`feat(signals): cross-function exit conflicts in API and UI`, commit `55e549085`) — this is purely a container/overflow CSS issue on Parth's side. Grouped with item in Part 2-A below (same likely fix).

### 4. Overwatch — Degradation alerts using wrong definition (static >10pp BT-FWD gap instead of trend-based)
**Ask:** Confirm mis-implementation vs intentional flag; correct trigger to use FWD-over-time trend (orange: <61% + 2 consecutive months decline; red: <60% + 3 consecutive months decline), not a static gap.

✅ **DONE.** Fixed 2026-07-22, "DRIFT ALERT trigger fix (email spec 5D)" — job status entry explicitly cites this exact example (*"caused false positives when cumulative FWD was healthy (e.g. 70.59% vs BT 81.72%)"* — matches the mail's "81.72% BT vs 70.59% FWD" almost verbatim, confirming this is the fix for this exact complaint). Old `_is_declining_toward_floor` fired on any single weekly decline / static gap; rewritten to use the monthly-fall trend rule + correct floor thresholds. UI copy also updated (`⚠ degraded FWD` → `⚠ drifted FWD`, DEGRADING → DRIFTING/DRIFT ALERTS).
Files: `api/services/degradation_service.py`, `api/services/analyst_service.py`, `MindwealthUI_Vue/utils/signals.ts`, `pages/signals.vue`, `server/utils/mindwealth-data.ts`.

### 5. SBI page doesn't match either discussed spec
**Ask:** Live SBI page (Composite score, 3 functions, Long Signal %/Long Asset % breadth table) doesn't match the Daily SBI report. Ahil to rework the SBI rule; Divyanshu to confirm which spec it was actually built against.

❌ **PENDING.** No SBI-page rebuild or spec-reconciliation found in either job-status doc after this date. The only related artifact is `src/sentiment_superindex/analysis/sbi_short_validation.py` ("Test 15"), which validates SBI as one *input component* feeding the SSI composite (short-gate hit-rate testing) — not a rebuild of the live SBI page itself against the Daily SBI report format. This matches the pattern already seen in the WhatsApp chat status file (SBI backtest/page repeatedly flagged as unresolved through 24/06–29/06). **Still an open item as of the latest evidence available.**

### 6. Portfolio sizing methodology — reconcile with Jul 8 Test Suite results
**Ask:** Confirm whether live sizing (Conviction Engine BQ tier × SSI capital-deployment %) is live logic or placeholder pending the Optimal-N/quality-threshold findings (N=80 optimal, quality-threshold-50 nearly doubles Sharpe). Confirm: (a) live vs placeholder, (b) does BQ score relate to/duplicate `composite_score v4`, (c) timeline to substitute the Test-1 candidate.

🟡 **PARTIAL — explicitly still a pending decision, not silently dropped.** `instruction_docs/portfolio_page/OPEN_QUESTIONS_FOR_ROHIT.md` (5 blocking decisions doc) has a "Jul 2026 update" note: *"Ahil delivered NAV workbooks + consolidated report in `ahil_analysis/`. Ask 1 ($10M, N=60) and Ask 2 (Axiom 2 hold-to-exit) are partially answered... Rohit formal sign-off still required where UI mock ($100M) conflicts with research ($10M)."* So: analysis has been delivered (Ahil's workbooks), the live sizing engine today is confirmed to be the **legacy/placeholder engine** (D1 quality-threshold engine exists in code but is opt-in only, per item 2 above) — i.e. the direct answer to "(a)" is: **currently placeholder/legacy, not yet the Test-Suite-optimal engine**. (b) and (c) — no explicit written answer relating BQ score to `composite_score v4`, or a substitution timeline, found in the docs.

### 7. Reconciling Signals & Portfolio pages — one portfolio, rename "New Signals"→"New Entry Signals", add "New Exit Signals" below Claude Shortlisted
**Ask:** Should be exactly one portfolio driven by entries (via methodology/optimal-N) and exits (via R:R or standard exit). Rename Signals-page left-menu "New Signals" → "New Entry Signals"; add "New Exit Signals" just below Claude Shortlisted. Ahil/Rohit finalizing entry/exit selection methodology "in 1-2 days."

✅ **DONE (backend)** / ❓ **UNVERIFIED (frontend menu rename).** Backend: `GET /signals/entries` and `GET /signals/exits` are implemented and marked **Done** in `portfolio_implementation_log.md` (status table: item 5 "Done — New", item 6 "Done — Partial, no `eviction` type" yet). The doc explicitly documents the intended rename as spec: *"Menu rename: 'New Signals' → **New Entries**; new **New Exits** below Claude Shortlisted"* and *"'One ledger, two windows': Portfolio and the Signals page read the same feeds for new entries and new exits."* This is backend-ready and unblocked for Parth to wire up. Whether the actual frontend menu labels have been changed in the live `MindwealthUI_Vue` app is not confirmable from the repos available here — flag for a quick visual check. Note the 14/07 WhatsApp message (covered in the other status file) explicitly said the fuller "Portfolio Unified" page was still a design reference pending final methodology sign-off — that is a **separate, larger** ask than this simple two-menu-item rename, which itself looks unblocked.

### 8. Macro Runic — display fixes carried over from Jun 25 list

**8a. CFTC data freshness tag showing wrong/past date**
🟡 **PARTIAL.** Two CFTC fixes exist but both predate this email (dated 2026-06-06/07 in job status: "Permanent auto-refresh of CFTC TFF ZIP" and "CFTC data staleness investigation and fix"). Since Rohit is still flagging this as outstanding on 11 July — over a month after those backend fixes shipped — this looks like a **separate, UI-level display/copy bug** (the freshness *tag text* on the Macro Runic page, e.g. "expected Tue X · Lag Nd") rather than the underlying data pipeline, which was already fixed. No further fix dated after 11 July found. Treat as still open on the display side.

**8b. "SBI Composite" label still appearing instead of "SSI"**
🟡 **PARTIAL / likely mostly done.** This was raised repeatedly in the WhatsApp chat (23/06, 24/06 — "why do we still have long signal long asset on sbi... sbi composite instead do ssi despite me mentioning thrice") and is raised again here on 11/07 ("SBI Composite label still appearing instead of SSI **in at least one place**" — Rohit's own phrasing suggests it's now down to one residual spot, not the whole page). No commit/doc evidence of the final remaining occurrence being fixed after 11/07.

**8c. Chatbot not retaining conversational context**
❌ **PENDING / unclear.** Rohit himself says "I recall giving feedback here but can't recall if this is still an issue" — i.e. even he is unsure. No dedicated conversational-memory/context-retention fix found in the job status docs (the v1.8.1 "AI Analyst — Overwatch context, tabs" work added cross-**page** context bundling and `page_context`, which is a different thing from turn-to-turn chat memory). Needs a fresh check with the live chatbot to confirm either way.

**8d. Overwatch "Version Monitor" menu item — doesn't render distinct content**
⚪ **N/A / acknowledged as incomplete by design** — Rohit's own note says "AHIL TO COMPLETE DESIGN," i.e. this is known-incomplete pending Ahil's design, not a bug to hunt for. No evidence found that this was completed since.

### 9. Divyanshu — go through all feedback on macro intelligence agent / Notion doc and complete what's pending
⚪ **N/A (general instruction, not independently verifiable)** — this is an umbrella instruction rather than a discrete item; its sub-parts are effectively covered by the specific Macro Runic / Combo / DRIFT items already tracked as ✅ DONE elsewhere in this file and the companion WhatsApp status file (Combo D/E threshold work, DRIFT rule, CFTC auto-refresh, SSI 3-layer wiring all post-date 11/07 and represent substantial follow-through).

### 10. Signals page — function filter (Combined Performance) doesn't actually filter the table
**Ask:** Clicking a function in the left menu highlights it but table content doesn't change. Ahil to advise if this filter is actually needed.

❌ **PENDING / no answer captured.** A *related* but distinct bug — "Signals KPI cards wrong long/short counts when function filter active" — was fixed (job status, SUCCESSFUL: KPI cards now use `GET /signals/counts` buckets). That fix was about the **summary cards** miscounting when a filter is active, not about the **Combined Performance table** failing to filter at all, which is what this item describes. No evidence found that the table-filtering behavior itself was fixed, and no recorded reply from Ahil on whether the filter is even wanted.

---

## PART 2 — Frontend (Parth)

### A) Ready to build now

| Item | Status |
|---|---|
| Mobile: phone-nav mismatch (separate from tab-wrapping, which is confirmed OK) | ❓ UNVERIFIED (frontend) — no fix on record. |
| Signal detail popup can't scroll to see full content (grouped with Part-1 item 3, Live P&L scroll) | ❓ UNVERIFIED (frontend) — no scroll/overflow fix found in either doc; likely one shared CSS/container fix would close both this and Part-1 item 3. |
| X-axis label fix: "Price Window Remaining [%]" (Signals Today), "Time Window Remaining [%]" (Outstanding/Claude Optimized) — verify against v9 spec | ❓ UNVERIFIED (frontend) — same as the equivalent ask in the 21-Jun–21-Jul WhatsApp status file; no label-string evidence found in any tracked repo (pure Vue chart-copy work). |
| Confirm left-menu click behavior consistency: Signals menu should filter (see Part 1 item 10, itself unresolved), but Super Sentiment/Macro-Runic/Overwatch menus look like section navigation — confirm intended behavior per page | ❌ PENDING — this is explicitly a design-clarification request from Parth to Rohit ("or advise if you need clarity from me"); no written resolution found. Also blocked on Part 1 item 10 being resolved first for the Signals-page half of the question. |

### B) Blocked — waiting on backend

| Item | Status |
|---|---|
| "Individual function click-thr..." | ⚠️ **CANNOT ASSESS** — the source file `11july_mail.md` is truncated exactly at this line (ends mid-word, "click-thr"). Recommend re-checking the original email/Notion doc for the full text of this item (likely "click-through" to something, given the heading is "BLOCKED — WAITING ON BACKEND") and re-running this line item once the full ask is available. |

---

## Summary Roll-up

| Status | Count |
|---|---|
| ✅ DONE | 3 (FX sizing, degradation-definition fix, Signals/Portfolio entries+exits backend) |
| 🟡 PARTIAL | 4 (cluster weight, sizing-methodology sign-off, CFTC freshness tag, SBI Composite label residual) |
| ❌ PENDING | 4 (SBI page rebuild, chatbot context, Signals function-filter, left-menu behavior consistency) |
| ❓ UNVERIFIED (frontend) | 4 (Live P&L/popup scroll, mobile nav, x-axis labels, New Entries/Exits menu rename) |
| ⚪ N/A | 2 (Version Monitor — ack'd incomplete-by-design; general Divyanshu instruction) |
| ⚠️ Cannot assess | 1 (final item, source file truncated) |

**Headline:** of the 10 backend items in Part 1, the two loudest/most specific complaints — the FX "Could not compute" sizing bug and the degradation-alert false-positive definition — are both confirmed fixed with exact evidence (including the identical example numbers Rohit quoted: 81.72%/70.59%). The SBI page rebuild remains the single most persistent open item across *both* status files in this folder (WhatsApp chat: 23/06, 24/06, 29/06; this email: 11/07) — recommend prioritizing Ahil's SBI rule rework next. The Part-2 frontend items are almost all plausible-but-unconfirmed from this workspace; a live visual QA pass by Parth against this list (mobile nav, popup scroll, x-axis labels, New Entries/New Exits menu) would close most of the ❓ tags definitively.
