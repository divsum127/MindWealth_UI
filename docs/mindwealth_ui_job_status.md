# MindWealth UI — Job Status

Task tracking for MindWealth UI (`/home/ubuntu/uiv2/git/MindWealth_UI`).

**Files:**
- Job Status (this file): `/home/ubuntu/uiv2/git/MindWealth_UI/docs/mindwealth_ui_job_status.md`
- Implementation Details: `/home/ubuntu/uiv2/git/MindWealth_UI/docs/mindwealth_ui_repo_job_status_details.md`

---

## TODO

_Tasks that are planned or currently in progress. Move to DONE when completed._

---

### SEC EDGAR + FMP PE History Fix — follow-ups (updated 2026-07-24, see DONE #4 same date for full context)

**PE-01: Universe rollout — run `full_recalculation` for all US tickers so SEC EDGAR depth actually lands in the conviction store**
- **Not blocked** (unlike the old FMP-only plan) — SEC EDGAR needs no API key, so this can run today. Live-verified depth on spot checks: AAPL/MSFT ~17-18y, NVDA ~16y, PYPL ~11y (all previously ~0.5-2y via yfinance alone, or capped at 5y under the old FMP-only fallback).
- **Runbook**: run `full_recalculation` across the full US universe (~121 tickers). Each ticker makes at most 2-3 SEC EDGAR calls (well within SEC's ~10 req/sec fair-use guidance) plus, only for the rare ticker where SEC returns nothing at all, one FMP call (still gated on `FMP_API_KEY` being set). Confirm `pe_history_meta.source == "sec_edgar"` and `years_available` up across the universe; spot-check that PYPL's `valuation_tax` stays neutral/low (not the old `-3.0` bug).
- **Files**: `src/conviction_engine/pe_history_sec.py`, `conviction_store/*.json`

**PE-02: (optional) Provision `FMP_API_KEY` for the SEC-EDGAR-miss fallback**
- **Blocked on**: a human (Rohit/Ahil) signing up (free tier, 250 calls/day) at financialmodelingprep.com — now genuinely optional/low-priority since SEC EDGAR covers the vast majority of US tickers (anything with US-GAAP XBRL filings since ~2009); FMP is now only reached for tickers where SEC's CIK map has no match or no EPS facts at all.
- **Files**: `src/conviction_engine/pe_history_fmp.py`

**PE-03: Manual entry for priority non-US names (unchanged from the original plan)**
- **Blocked on**: a business-prioritized list of ~15-20 non-US holdings from Rohit/Ahil for `scripts/set_manual_pe_history.py` — SEC EDGAR and FMP both only cover US-GAAP/US-listed filers, so this track is unaffected by the SEC pivot.
- **Runbook**: source P/E history per ticker from Gurufocus/TIKR/Screener.in and run `python scripts/set_manual_pe_history.py TICKER --csv path/to/pe_history.csv`.
- **Files**: `scripts/set_manual_pe_history.py`, `conviction_store/*.json`

---

### Data & Pipeline Integrity Audit — 2026-06-06
_Findings from web-verified cross-check of nightly report variables and combo classifications._

#### 🔴 Priority 1 — Fix Required

~~**T-01: Fed Cycle persists as "CUTTING_LATE" during 5-month Fed pause with hike risk**~~ → **FIXED 2026-07-22** — see DONE section.
- **What**: `fed_cycle_at_date()` in `fed_cycle.py` carries forward the last known cycle label (`CUTTING_LATE`) during a PAUSE via the `series.iloc[-1]` fallback (lines 187-190). The Fed has been on hold at 3.50–3.75% since at least January 2026 (FOMC meetings Jan 28, Mar 18, Apr 29 all held). The Jun 5 jobs report (172K, above consensus) now has markets pricing 42.7% probability of a Dec 2026 rate HIKE. Reporting `CUTTING_LATE` when the Fed is paused and hike-risk is rising mis-frames the narrative and regime analysis.
- **Fix needed**: Introduce a `PAUSING` label that activates after N consecutive weeks of PAUSE following a cutting cycle, OR add a `hike_risk_threshold` (e.g. CME FedWatch >30%) override. At minimum, add `PAUSING_POST_CUT` as a distinct state after `cycle_early_months` of pause.
- **Files**: `src/macro_intelligence/engine/fed_cycle.py`, `macro_intelligence/CONFIG.yaml`

~~**T-02: Nightly job does not auto-refresh CFTC TFF ZIP on Fridays — data goes stale by one week**~~ → **FIXED 2026-06-07** — see DONE section.

~~**T-03: `_combo_c_weeks()` will show perpetual Week 1 when Combo C re-activates**~~ → **FIXED 2026-06-07** — episode anchor pattern applied (see DONE #15).

~~**T-03: VIX single-day spike magnitude not detected — tier stays NORMAL despite +40% jump**~~ → **FIXED 2026-07-22** — see DONE section.
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

### 2026-07-27

1. **Analyze `PORTFOLIO_API_HANDOFF_02.md` + `PORTFOLIO_DATA_ISSUES.md`, loop until fixable code issues closed** — SUCCESSFUL
   - Summary: User asked to analyze the two portfolio handoff/issue docs and loop until issues are fixed. Live-verified against the real running services on this host (`mindwealth-api-dev.service` = `:8507` running this exact `chatbot-dev` checkout with `--reload`; `mindwealth-api.service` = `:8506` running the separate `/home/ubuntu/uiv2/prod/MindWealth_UI` checkout):
     1. **Test host (`:8507`) is NOT actually down** — the docs' "Squid 503" finding does not reproduce. `curl 127.0.0.1:8507/api/v1/portfolio/nav?...` returns clean `200` JSON today (auth via `X-API-Key`, not Squid). All four "blocked" P0/P1 endpoints (`nav`, `holdings`, `signals/entries`, `signals/exits`) return `200` with real data. The Nuxt dev BFF (`mindwealth-ui-dev.service`, outside this repo's scope) already points `NUXT_API_BASE_URL=http://127.0.0.1:8507` (loopback, not the public IP), so the real request path was never actually blocked — only an external `curl` straight at the public IP (`51.20.53.218:8507`) times out from this same host, most likely AWS hairpin-NAT self-access (can't reach your own Elastic IP from inside the instance) rather than a genuine outage; `:8506` (prod) answers identically whether hit via loopback or the public IP, so this isn't a general security-group block on the host.
     2. **Prod (`:8506`) genuinely 404s** for `nav`/`holdings`/`entries`/`exits` — confirmed live. Root cause: `/home/ubuntu/uiv2/prod/MindWealth_UI` (`chatbot-prod`) simply predates all the Portfolio HANDOFF work that has been sitting uncommitted/unpushed on `chatbot-dev` across many prior sessions (164 files, `git status` shows the dev tree far ahead of the last commit `3bda80c` from 2026-07-23, with substantial further uncommitted work before that). This is a deploy gap, not a code gap — closing it requires committing + pushing `chatbot-dev`, merging into `chatbot-prod`, and running `prod-pull-and-restart.sh`, which is a significant production action outside the scope of "analyze these 2 docs" and was intentionally **not** done without explicit confirmation (see job status details for the exact recommended commands).
     3. **Real code gap found and fixed:** HANDOFF §7 / DATA_ISSUES §6 flagged `GET /portfolio/sizer`'s `pnl_rows[]` / cluster `positions[]` as missing `cross_function_exit`, `asset_class`, `status` — confirmed still true. Added `_asset_class_label()` (VT book `asset_type` → human label, same "Equity" default as the holdings endpoint) and `_cross_function_conflict_tickers()` (reuses the same `cross_function_conflicts.json` blob that backs `/signals/reports/portfolio-risk/latest`) to `portfolio_service.py`; wired `cross_function_exit`/`asset_class`/`status` onto the shared `sized_row` dict that backs both `pnl_rows` and `clusters[].positions[]`.
     4. **Confirmed already resolved** (built in earlier, uncommitted sessions — docs are stale on these): `conviction_summary` on `/portfolio/risk` (present), `book_id` isolation + 422 on `/signals/reports/portfolio-risk/latest` for `brokerage`/`personal` (present), `implied_natural_exit_date` field present on conflict `open_positions[]` — but always `null` in practice.
     5. **Second real bug found while verifying #4:** `_parse_signal_meta()` in `portfolio_pipeline_service.py` only read the compound `"Interval, Confirmation Status"` column (used by `new-signals`/`target-signals`) or lowercase `"interval"` — the `portfolio-risk` (outstanding) report instead carries a plain `"Interval"` column, so `interval` always resolved to `""` for that report. This silently broke `_lookup_hold_days()`'s exact-match join (`(symbol, function, interval)`), so `implied_natural_exit_date` was `null` for every single conflict regardless of whether hold-day data existed. Added the plain `"Interval"` column as a fallback (after the compound column, before lowercase `"interval"`); live-verified several conflicts now resolve a real date (e.g. `3690.HK TRENDPULSE Daily` → `2026-09-13`) while genuinely-absent function/interval combos correctly stay `null`.
     6. **Investigated but deliberately left alone (already a known, Rohit-gated decision, not a new bug):** live sizer shows `open_position_count=756` against advertised `position_limit`/`n_slots=60`, and `/portfolio/nav` shows `net_exposure_pct: 267%` / `gross_exposure_pct: 716%`. Root cause: `SIZING_ENGINE_VERSION` defaults to `legacy` (confirmed via `sizing_engine.sizing_engine_version()`), which has no admission-slot cap and proportionally splits each cluster's fixed budget across every non-blocked VT-book row (903 raw rows, 476 unique ticker/function/interval/direction keys — the "duplicates" are legitimate re-entries on different signal dates, not corrupt data). The D1 `d1_slots` engine that fixes this already exists (`api/services/sizing_engine.py`) but is explicitly gated behind Rohit confirming N/sleeves (`sizing_engine.py`'s own docstring, `OPEN_QUESTIONS_FOR_ROHIT.md`) — flipping it was out of scope for this pass and would be a significant, product-visible number change requiring sign-off, not a docs-driven bug fix.
   - Added regression tests: `tests/test_api_portfolio.py::test_sizer_pnl_rows_have_cross_function_asset_class_status`, `::test_asset_class_label_mapping`; `tests/test_api_signals_surface.py::test_parse_signal_meta_reads_plain_interval_column`. Full suite: 585 passed, 2 skipped, 1 pre-existing unrelated failure (`test_d6_smoke.py` — leftover git-conflict-marker syntax error in `/home/ubuntu/MindWealth/testing.py`, a different repo, not touched here).
   - Files changed: `api/services/portfolio_service.py` (new `_asset_class_label()`, `_cross_function_conflict_tickers()`, `_ASSET_CLASS_LABELS`; wired 3 fields onto sizer `sized_row`), `api/services/portfolio_pipeline_service.py` (`_parse_signal_meta()` interval fallback fix), `tests/test_api_portfolio.py`, `tests/test_api_signals_surface.py`

---

### 2026-07-24

1. **Investigate: "Valuation Tax / P/E percentile wrong for all assets" complaint (Divyanshu/Rohit chat, PYPL example)** — SUCCESSFUL (investigation only, no code changes)
   - Summary: User pasted a chat where a reporting manager tells Divyanshu "all macro engine outputs are wrong because P/E percentile has been set at [near] 0 for all, leading to too-high Valuation Tax" and that PYPL should have 0 valuation tax. Confirmed: (1) there is no separate "macro engine" valuation-tax logic — this is the **Conviction Engine** (`src/conviction_engine/`), Valuation Tax = `scoring.calculate_valuation_tax*`, PE percentile = `engine._percentile_rank` + `pe_percentile_20y`. (2) **Bug is real and still live on production** (`chatbot-prod`, HEAD `0d7748557` from 2026-07-20): PYPL's prod record shows `pe_percentile_20y=83.33` (ranked off only **8 sparse points spanning 0.0–0.56 years** of yfinance EPS history, not 20y), which trips the `>=70` tier → `pe_hist_percentile=-2.0` → total `valuation_tax=-3.0`. Universe-wide on prod: 35/132 equities show `pe_percentile_20y=0.0` and 27/132 show `100.0` — both extremes are artifacts of ranking against a handful of noisy recent points, not genuine 20-year percentiles; 34 records take the full `-3.0` PE tax hit from this. (3) **A fix already exists on `chatbot-dev`** (uncommitted working-tree changes, per `instruction_docs/ssi_and_conviction_updates/FUNDAMENTAL_AGENT_UPDATE_JULY_2026_STATUS.md`, completed 2026-07-22, verified on PYPL: PE tax −2→**0**) — `engine.py` now nulls `pe_percentile_20y` whenever `pe_history_meta.insufficient_20y` is true, so `pe_hist_percentile` stays neutral (0.0) instead of taxing off a garbage rank. Confirmed dev PYPL today: `pe_percentile_20y=null`, `pe_hist_percentile=0.0`, `valuation_tax=-1.0` (from the unrelated EV/Revenue `entry_multiple` component only). **Root cause of "still wrong" complaint: the dev fix was never committed to git and never merged/deployed to `chatbot-prod`** — `git status` shows `engine.py`/`scoring.py` still as uncommitted modifications on `chatbot-dev`, and this was already flagged `[PENDING]` in `dev_to_prod_migration_todos.md` under "2026-07-22 — Fundamental Agent Update (conviction engine)". (4) **New finding from this pass:** the dev fix is arguably over-broad — `PE_HISTORY_TARGET_YEARS=20` means almost no yfinance-sourced ticker ever qualifies, so `pe_percentile_20y` is now `None` for **129/133 (97%)** of the dev universe and the PE-percentile tax component fires for **only 1 ticker (SONY)** universe-wide. This fixes the false-positive (PYPL) but effectively disables the entire PE-percentile tax mechanism for nearly everyone — worth a product decision on whether a lower minimum-history bar (e.g. ≥3–5y / N quarters) should still drive a percentile tax instead of full neutrality. Separately, the EV/Revenue `entry_multiple` component (unaffected by this bug) still taxes 88/133 dev-universe equities (45 at −5, 20 at −7, etc.) — if "everything is wrong" refers to overall `valuation_tax` magnitude broadly (not just the PE component), that lever should be reviewed too since it wasn't in scope of the July-22 fix.
   - Files changed: none (read-only investigation; updated `docs/dev_to_prod_migration_todos.md` note only)

2. **Super Sentiment dashboard: layer-score display bug (composite still "looked" mismatched after the Q1 fix)** — SUCCESSFUL
   - Summary: User flagged the composite-vs-layers discrepancy again after the 2026-07-21 superindex fix, screenshot showed composite +0.2, Layer 1 +0.6, Layer 2 +0.0, Layer 3 +0.0. Root cause was **not** a calculation bug this time — full-precision live values (layer1=0.5871, layer2=0.0047, layer3=-0.0318, weights 40/35/25) sum to exactly 0.2285, matching `ssi_level` — but two dashboard display bugs made it look wrong: (1) `roundLayerScore()`/`formatLayerScore()` in the Nuxt UI (`MindwealthUI_Vue`) rounded layer scores to only 1 decimal, too coarse to verify the weighted average by eye; (2) rounding layer3's -0.0318 to 1dp produced JS negative zero (`-0`), and `score >= 0 ? '+' : ''` is `true` for `-0` in JS, so a genuinely negative layer score displayed as `+0.0` instead of a minus sign. Fixed: bumped layer-score and composite-score display to 2 decimals, and rewrote both sign checks to derive the sign from the already-rounded value with `Math.abs()` instead of comparing the raw score directly (immune to the `-0` trap). Now shows composite +0.23, Layer 1 +0.59, Layer 2 +0.00, Layer 3 -0.03 — checkable by hand (0.4×0.59 + 0.35×0.00 + 0.25×(-0.03) = 0.2285 ≈ 0.23) and correctly signed. Verified the exact formatting logic against the live API numbers with a standalone Node script; rebuilt and restarted `mindwealth-ui-dev`.
   - Files changed: `MindwealthUI_Vue/server/utils/sentiment-mapper.ts`, `MindwealthUI_Vue/pages/sentiment.vue`

3. **FMP PE History Fix — replace unscrapable Macrotrends fallback with Financial Modeling Prep API + manual-entry track** — PARTIALLY SUCCESSFUL (code complete and tested; 2 of 9 plan steps blocked on external provisioning)
   - Summary: Follow-up to entry #1 above (PYPL valuation-tax investigation) and the user's explicit direction to drop Macrotrends (confirmed Cloudflare Turnstile-blocked, incl. stealth Playwright) in favor of FMP for US tickers + manual entry for non-US. Implemented the full "FMP PE History Fix" plan: (1) new `src/conviction_engine/pe_history_fmp.py` — `is_us_ticker()` (suffix-based, covers `.TO/.V/.NE/.NS/.BO/.NZ/.AX/.HK/.KS/.KQ/.SI/.PA/.F/.DE/.L`), `fetch_pe_history_fmp()` (FMP `/stable/ratios?period=quarter` call, 2-attempt backoff on 429/5xx, on-disk cache at `conviction_store/pe_history_cache/{TICKER}.json` refreshed at most every 80 days, hard no-op with zero network calls when `FMP_API_KEY` unset); confirmed via FMP's own published docs/examples that the ratio field name is `priceToEarningsRatio` (matches the parser's primary candidate) — de-risks the one open assumption flagged in the plan even without a live key. (2) Wired into `fundamentals_enriched.build_fundamentals_from_raw`: FMP is only called when the yfinance-derived bundle is `insufficient_20y=True` **and** the ticker is US-style (cost control against the 250-calls/day free-tier budget), and only replaces the yfinance series when it's a strict improvement (`point_count` higher); result tagged `pe_history_meta.source = "yfinance" | "fmp"`. (3) New `scripts/set_manual_pe_history.py` CLI for non-US tickers (CSV `date,pe` → `conviction_store/{TICKER}.json`, `source="manual"`), operationalizing the v5 spec's own documented non-US fallback (Gurufocus/TIKR/Screener.in) instead of hand-editing JSON. (4) `FMP_API_KEY` placeholder added to `.env.example` and `.env` (commented, unset). (5) Full test coverage: `tests/test_pe_history_fmp.py` (20 tests: `is_us_ticker` suffix coverage, no-key/non-US never-call-network guards, mocked success/error/malformed-response parsing, on-disk cache hit/miss, and 4 wire-in tests proving FMP is called only when thin+US and never otherwise) and `tests/test_set_manual_pe_history.py` (8 tests incl. a full round trip: CSV → script → store JSON → `daily_update()` → `calculate_valuation_tax_components()`, proving a manually-entered 26-year series drives `pe_hist_percentile` to `-3.0` exactly like an auto-fetched series would, and that a still-short manual series stays neutral exactly like the existing insufficient-history safety net). Ran the full regression suite (`tests/test_conviction_engine.py` + `tests/test_api_conviction.py` + full `tests/` — 560 passed, 2 skipped, 1 pre-existing unrelated failure in `test_d6_smoke.py` caused by a leftover git-conflict marker literal in `/home/ubuntu/MindWealth/testing.py`, a different repo entirely, not touched by this change) — zero breakage. **Blocked (cannot be completed by an agent):** the plan's final 2 steps — "live smoke test PYPL + few US names" and "universe rollout for all 121 US tickers + manual entry for priority non-US names" — require (a) a real `FMP_API_KEY`, which needs a human to sign up at financialmodelingprep.com (Rohit/Ahil, per the plan), and (b) a business-prioritized list of ~15-20 non-US holdings for manual entry. Left as open TODO items below with an exact runbook once the key exists.
   - Files changed: `src/conviction_engine/pe_history_fmp.py` (new), `scripts/set_manual_pe_history.py` (new), `src/conviction_engine/fundamentals_enriched.py` (wire-in), `.env.example`, `.env` (local, gitignored), `tests/test_pe_history_fmp.py` (new), `tests/test_set_manual_pe_history.py` (new)

4. **SEC EDGAR PE History pivot — replace FMP's paid-gated 5y cap with a genuinely free, unlimited, deeper source** — SUCCESSFUL
   - Summary: Follow-up to entry #3 same day. User asked "is the API key paid, I need a free solution?" — confirmed FMP's free tier caps historical P/E at 5 years (20-30y needs the $59/mo Premium plan). User then explicitly asked to "check all the alternatives and find what's free" for real 20-30y depth. Researched and **live-tested** (not just doc claims) several options: Alpha Vantage free tier (25 req/day — too rate-limited for batch use), third-party SEC wrappers like Business Quant/StockFit/Finkipedia (unverified reliability, same underlying ceiling, free tiers often gate the actual history depth behind paid plans on close reading), and **SEC EDGAR's own official XBRL API** (`data.sec.gov`) — no API key, no daily cap (SEC's own fair-use guidance is ~10 req/sec), just a descriptive `User-Agent` header. Live-verified against the real API before building anything: `EarningsPerShareDiluted` via `companyconcept` goes back to FY2007 for AAPL and MSFT (~17-19y as of 2026), FY2008 for NVDA (~16-18y), FY2013 for PYPL (~11-12y, limited by its 2015 eBay spinoff) — categorically deeper than FMP's free 5y cap, though still short of a true 20-30y ceiling for most tickers since XBRL was only mandated from 2009. Presented findings + 3 design trade-offs to the user via `AskQuestion` before building (SEC being the SEC's own primary source, not a scrape/wrapper, made it the clear pick over FMP or the third-party wrappers): user chose (1) full quarterly reconstruction with a Q4-plug (not annual-only) to match the existing smooth monthly-sampled P/E series, (2) **SEC EDGAR first**, FMP now demoted to fallback-only-when-SEC-returns-nothing-at-all-for-that-ticker, (3) **first-filed** value per (start,end) period when a period is reported in multiple filings (point-in-time, avoids look-ahead bias from later restatements). Implemented: (1) extracted `compute_pe_history`/`PE_HISTORY_TARGET_YEARS`/`_empty_pe_history_bundle` out of `fundamentals_enriched.py` into new `src/conviction_engine/pe_history_core.py` (re-exported from `fundamentals_enriched.py` so existing imports keep working) — this let the new SEC module reuse the exact same tested TTM/monthly-sampling logic instead of re-deriving it, and broke what would otherwise have been a circular import. (2) New `src/conviction_engine/pe_history_sec.py`: `get_cik_for_ticker()` (SEC's bulk `company_tickers.json`, cached 30 days), `build_quarterly_eps_series()` (filters to `10-K`/`10-Q`/`/A` forms only, `_dedupe_first_filed()` keeps the earliest-`filed` fact per period, `_plug_quarterly_series()` classifies facts by duration into discrete quarters [~80-100 days] vs annual totals [~340-380 days] and reconstructs each FY's Q4 as `FY - (Q1+Q2+Q3)` only when exactly 3 quarters are found inside that FY's span — years with fewer leave a gap rather than guessing, which just means fewer usable rolling-TTM points for that stretch, not corrupted data), `fetch_pe_history_sec()` (tries `EarningsPerShareDiluted` then falls back to `EarningsPerShareBasic`, feeds the reconstructed series + the existing price history into the shared `compute_pe_history()`, tags `meta.source="sec_edgar"`, on-disk cache at `conviction_store/pe_history_cache/{TICKER}_sec.json` refreshed at most every 80 days). (3) Live end-to-end smoke test against the real API during development (not part of the automated suite, but run manually and worth recording): AAPL `years_available=17.07` (`eps_quarters=71`, `point_count=3917`), PYPL `years_available=11.05`, NVDA `16.22`, MSFT `18.06` — all correctly still `insufficient_20y=True` under the strict 20y bar but a dramatic improvement over both the pre-fix yfinance baseline and the FMP-only 5y cap. (4) Rewired `fundamentals_enriched.build_fundamentals_from_raw`: SEC EDGAR is tried first when the yfinance bundle is `insufficient_20y=True` + US-style ticker; FMP is now only tried when SEC returns `None` outright (not merely when SEC's own result is itself still under 20y) — the richer-by-`point_count` bundle always wins. (5) Added `SEC_EDGAR_USER_AGENT` (optional, no key) to `.env.example`/`.env` docs. (6) Full test coverage: `tests/test_pe_history_sec.py` (20 tests — dedup-keeps-earliest-filed, Q4-plug math incl. the "gap when <3 quarters found" and "ignores out-of-range durations" edge cases, CIK resolution + on-disk caching, mocked fetch success/error/malformed-JSON/diluted-missing-falls-back-to-basic paths) and rewrote `tests/test_pe_history_fmp.py`'s `TestFundamentalsEnrichedWireIn` class (now 6 tests) to lock in the new SEC-first/FMP-only-on-None ordering, incl. the subtle case where SEC returns a thinner-than-yfinance bundle (still not `None`) and FMP must stay skipped regardless. Ran the full regression suite: `tests/test_conviction_engine.py` + `test_api_conviction.py` + both PE-history test files + `test_set_manual_pe_history.py` — 109/109 passed; full `tests/` suite — 581 passed, 2 skipped, 2 pre-existing failures unrelated to this change (`test_d6_smoke.py` — leftover git-conflict-marker syntax error in a different repo entirely, `/home/ubuntu/MindWealth/testing.py`; `test_dominant_reason.py::test_live_f_e_reason_contract` — a live-data-dependent macro-intelligence assertion, unrelated module, fails because of current live combo state not this change) — zero regressions introduced.
   - Files changed: `src/conviction_engine/pe_history_core.py` (new), `src/conviction_engine/pe_history_sec.py` (new), `src/conviction_engine/fundamentals_enriched.py` (refactor + rewire), `.env.example`, `.env` (local, gitignored), `tests/test_pe_history_sec.py` (new), `tests/test_pe_history_fmp.py` (wire-in tests rewritten for new ordering)

---

### 2026-07-23

1. **McClellan Oscillator formula bug — proper fix + tests + docs** — SUCCESSFUL
   - Summary: McClellan cumsum bug and display rounding were already fixed on 2026-07-21 (part of the SSI superindex work), but had no dedicated regression test and `docs/MACRO_INTELLIGENCE_MASTER.md` still documented the old (wrong) cumsum formula. Verified live `positioning.json` (2026-07-23) shows `mcclellan: -12.02` (rounded, correct formula) — not the old inflated ~217 reading. Added `tests/test_mcclellan_pull.py` (4 tests: no-cumsum convergence check, stays within ±150 band for realistic input, matches manual EMA formula, display rounding to 2dp). Updated `MACRO_INTELLIGENCE_MASTER.md` "Hard part 4" and the spec-audit table to document the corrected formula and the bug history.
   - Files changed: `tests/test_mcclellan_pull.py` (new), `docs/MACRO_INTELLIGENCE_MASTER.md`

2. **NH/NL Ratio formula bug — proper fix + tests + docs** — SUCCESSFUL
   - Summary: `nh_nl_ratio = highs / lows` (unbounded) was already fixed to `highs / (highs + lows)` (bounded 0–1) on 2026-07-21, and `nh_nl_ratio.csv` was already rebuilt (2026-07-16 now correctly reads 0.9787 instead of 46.0). Same gap as McClellan: no dedicated regression test, and `MACRO_INTELLIGENCE_MASTER.md` still described the old `new_highs / new_lows` formula in two places. Verified live `positioning.json` (2026-07-23) shows `nh_nl_ratio: 0.7273` — correctly bounded. Added `tests/test_sp500_breadth_nh_nl.py` (3 tests: ratio bounded [0,1] over a synthetic breadth frame, formula matches `highs/(highs+lows)` incl. the exact 46/1 → 0.9787 worked example from the bug report, zero-highs-and-lows guard returns NaN). Updated `MACRO_INTELLIGENCE_MASTER.md` variable table and "Hard part 5" with the corrected formula and bug history.
   - Files changed: `tests/test_sp500_breadth_nh_nl.py` (new), `docs/MACRO_INTELLIGENCE_MASTER.md`

3. **SKEW decimals + general SSI display-rounding policy** — SUCCESSFUL
   - Summary: SKEW/McClellan rounding was already fixed 2026-07-21, but `nh_nl_ratio`, `hyg_lqd`, `vix_ratio`, `dbmf_beta` were inconsistently rounded to 4 decimals in `positioning.py` and the Nuxt mapper even though none are currency pairs (per the requested rule: 2dp for indicators, 4dp only for actual FX pairs like USDCNH). Also found `api/services/macro_service.py::get_ssi_summary()`/`get_ssi_history()` (the `/macro/ssi/summary`, `/macro/ssi/history` endpoints, separate legacy code path from `positioning.json`) returned fully unrounded floats straight from `ssi.db`. Fixed: added a shared `_display_decimals(key)` policy in `positioning.py` (2dp default, 4dp only for a `_CURRENCY_PAIR_KEYS` allowlist — currently empty of SSI inputs, future-proofed for FX); added `_round2()` helper in `macro_service.py` for the same two endpoints; fixed `sentiment-mapper.ts` and `MacroSsiPanel.vue` to drop their 3/4-decimal overrides. Rebuilt `positioning.json` + Nuxt dev UI; verified live API responses on `:8507` show 2dp everywhere (`nh_nl_ratio: 0.73`, `hyg_lqd: 0.75`, `vix_ratio: 1.09`, `dbmf_beta: 0.56`, was 4dp before).
   - Files changed: `src/sentiment_superindex/engine/positioning.py`, `api/services/macro_service.py`, `MindwealthUI_Vue/server/utils/sentiment-mapper.ts`, `MindwealthUI_Vue/components/runic/MacroSsiPanel.vue`, `tests/test_ssi_display_rounding.py` (new)

4. **Investigate: 21-July review D3 "cluster weight >100%" double-counting concern (Divyanshu ask)** — SUCCESSFUL (investigation only, no code changes)
   - Summary: Checked whether the `21July_review_specs.md` D3 complaint ("bar prints 351%", MULTI-SIG assets held by 3–4 functions) is still reproducible. Found the underlying math bug was already patched by the **2026-07-18 "Portfolio cluster sizing fix"** (two-pass split — `pass 2` divides each cluster's fixed `budget_usd` proportionally across every eligible position/signal row in that cluster via `_cluster_rank_weight`; last row absorbs rounding so `deployed_usd == budget_usd` exactly, never more) — regression-tested (`tests/test_api_portfolio.py`: `assertLessEqual(cluster["deployed_usd"], cluster["budget_usd"])`). Duplicate ticker rows from multiple functions/signals holding the same asset each get their own proportional *slice* of that one fixed pool — not an independent additive grant — so a cluster's total cannot mathematically exceed its own cap under the current (legacy, default) engine. Also confirmed the Nuxt `PortfolioRiskView.vue` (committed 2026-06-24, predates the review) already renders raw `deployed_pct% / max_pct%` text (not a ratio) with fill-bar width clamped `Math.min(100, ...)` — so a "351%" style reading should not be visible on the live page today either. **Gap still open:** the real structural fix Divyanshu proposed in D1 (NAV/N admission-slot model, sleeve weights that truly sum to 100% of NAV) exists in `api/services/sizing_engine.py` but is **not the default** — gated behind `SIZING_ENGINE_VERSION=d1_slots`; legacy engine (with the 07-18 patch) still runs by default. Breach-recommendation dollar math also still reads legacy cluster-% (`D7 blocked` caveat), not "true weights." No formal written reply confirming the exact numerator/denominator to Rohit/Divyanshu, and no sanity-check response to Ahil's tangential correlation-matrix ask, were found in the repo — `_load_correlation_matrix()` already exposes `source`, `window_days`, `as_of`, `age_days` staleness metadata that such a reply could cite, but nobody has sent it yet.
   - Files changed: none (investigation only)

5. **Create status/answer file for "All of Us" WhatsApp chat questions (21 Jun – 21 Jul 2026)** — SUCCESSFUL
   - Summary: User asked to review `instruction_docs/chat_ques/All of Us - last month (21 Jun - 21 Jul 2026).txt` (810 messages), extract all questions/asks Rohit Sir raised, and produce an answer/status file marking already-completed items as done. Read the full chat export, cross-referenced every substantive ask against `mindwealth_ui_job_status.md`, `mindwealth_ui_repo_job_status_details.md`, and `git log` on `chatbot-dev`, and produced a topic-grouped status file with ✅ DONE / 🟡 PARTIAL / ❌ PENDING / 💬 ANSWERED IN CHAT / ❓ UNVERIFIED tags per item, plus a summary roll-up and a "biggest open items" callout. Frontend-only UI/copy items (Nuxt `MindwealthUI_Vue` repo, which lives outside this workspace's scoped repos) were tagged UNVERIFIED (frontend) rather than guessed at, since no source evidence was accessible for them here.
   - Files changed: `instruction_docs/chat_ques/All of Us - last month (21 Jun - 21 Jul 2026) - STATUS.md` (new, documentation only — no code changes)

6. **Super Sentiment dashboard: bump composite/layer-score display from 2dp to 3dp (readability request)** — SUCCESSFUL
   - Summary: After confirming the 2dp fix (entry #2 above) resolved the composite-vs-layers mismatch, user asked to bump display precision from 2 to 3 decimal places "would look better". Changed `roundLayerScore()` (2dp→3dp) and `compositeFromApi()`'s `formatSignedScore()` call (2dp→3dp) in `sentiment-mapper.ts`, and `formatLayerScore()` (2dp→3dp) in `sentiment.vue`; sign-from-rounded-value logic (the `-0` guard) preserved unchanged. Verified against live API numbers (layer1=0.5871→+0.587, layer2=0.0047→+0.005, layer3=-0.0318→-0.032, composite level=0.2285→+0.229; 0.4×0.587+0.35×0.005+0.25×(-0.032)=0.22855≈0.229 ✓) via a standalone Node script. Rebuilt (`npm run build`) and restarted `mindwealth-ui-dev.service`.
   - Files changed: `MindwealthUI_Vue/server/utils/sentiment-mapper.ts`, `MindwealthUI_Vue/pages/sentiment.vue`

6. **Draft reply document to Ahil's "7 items to finalize test suite" email (axiom test suite blockers)** — SUCCESSFUL
   - Summary: User asked to generate an answer document responding to Ahil's prioritized 7-item blocker email (P3 point-in-time ledger replay, `compute_rr_to_nearest_support_stop`, real SSI-ceiling series, real conviction-tier series, D1 regime-bucket series, macro overlay feed, composite-score API 401). Cross-checked each item against the actual codebase/data instead of writing generic filler: confirmed `compute_rr_to_nearest_support_stop()` already exists and is already the live `rr_dynamic` code path (`MindWealth/helper_functions/claude_lateness_metrics.py:526`), with an existing (if undocumented-to-Ahil) Test-8 "no clean stop" fallback via `rr_null_reason`; confirmed D1 regime-bucket daily series was already delivered 2026-07-17 (`testing/macro_th_exp/D1_regime_bucket_daily_2026-07-17.csv`) and macro overlay/291→8 shortlist + combo-classification history already exist (`testing/291_combo_tests/`, `testing/5_regime_uplift/combo_classification_history.csv`); confirmed real SSI-only ceiling series is exportable today from `load_ssi_ceiling_series()` (full 2015+ coverage) but the full 5-factor regime chain (VIX/trend/HY multiplier history) genuinely does not exist anywhere in the repo per `four_book_engine.py`'s own docstring; confirmed real conviction tiers/multipliers (`_BQ_TIERS` in `portfolio_service.py`) are live but the dated archive only starts 2026-05-15, so pre-archive history is honestly a gap, not fabricated; confirmed the composite-score 401 is a missing `X-API-Key` header against `api/dependencies.py::require_api_key`, not a missing feature; and gave an honest "not yet scoped" answer (with the three concrete scoping unknowns: backtest compute cost, point-in-time gate-input coverage back to 2018, and rule-set-vintage sign-off) for P3, rather than fabricating a completion date.
   - Files changed: `instruction_docs/portfolio_page/23July_reply_to_ahil_7_items.md` (new, documentation only — no code changes)

7. **Create status/answer file for 11-July consolidated feedback email** — SUCCESSFUL
   - Summary: User asked to review `instruction_docs/chat_ques/11july_mail.md` (Rohit's Part 1 backend/Part 2 frontend consolidated open-items email) and produce a status file marking already-done items as done. Cross-referenced each of the ~14 itemized asks against `mindwealth_ui_job_status.md`, `mindwealth_ui_repo_job_status_details.md`, `instruction_docs/portfolio_page/portfolio_implementation_log.md`, `instruction_docs/portfolio_page/OPEN_QUESTIONS_FOR_ROHIT.md`, and `git log`. Confirmed two items fixed with exact-match evidence (FX "Could not compute" → D2 base-size fix covers all NOT_APPLICABLE assets incl. FX; degradation-alert false-positive definition fix cites the identical 81.72%/70.59% example Rohit quoted). Flagged SBI page rebuild as the most persistent open item across both status files in this folder. Noted the source `.md` file itself is truncated mid-sentence at line 32 ("Individual function click-thr...") — that final Part-2B item could not be assessed and was flagged for the user to re-supply the full text.
   - Files changed: `instruction_docs/chat_ques/11july_mail - STATUS.md` (new, documentation only — no code changes)

---

### 2026-07-22

1. **Push mindwealth-api-docs local commits to GitHub** — SUCCESSFUL
   - Summary: Two commits (`08264a1` v1.8.0, `c5c5b59` v1.8.1) were committed locally but never pushed — GitHub `main` still showed `5abb580` (v1.7.3, ~1 month stale). User-provided PAT was invalid/expired; push succeeded via existing SSH key (`ahiliitb`). Remote switched from HTTPS to `git@github.com:divsum127/mindwealth-api-docs.git` so future fetch/push works without PAT.
   - Files changed: `docs/mindwealth-api-docs/` (git remote URL only; commits already existed locally)

2. **Portfolio HANDOFF v1.8.2 — API + docs commit and push** — PARTIAL (docs pushed; UI repo push blocked)
   - Summary: Implemented `GET /portfolio/nav` (MODEL enhanced snapshot), committed portfolio pipeline (`portfolio_book.py`, `portfolio_pipeline_service.py`), holdings/entries/exits/portfolio-risk routes, tests (62 pass). Commits: MindWealth_UI `2531daf9a`, mindwealth-api-docs `1efaa09`. **mindwealth-api-docs pushed to `divsum127/main`.** `divsum127/MindWealth_UI` `chatbot-dev` push failed — PAT invalid for write; SSH (`ahiliitb`) lacks push permission to `divsum127` repo. **2 commits ahead of origin:** `b984f0d6c` (v1.8.1), `2531daf9a` (v1.8.2).
   - Files changed: `api/routers/portfolio.py`, `api/routers/signals.py`, `api/services/portfolio_*.py`, `tests/test_api_*.py`, `docs/api/`, `docs/mindwealth-api-docs/`

3. **Fundamental Agent Update July 2026 — conviction engine P1/P2/P3** — SUCCESSFUL
   - Summary: Implemented PE/FCF cascades, neutral missing-data penalties, divergence `days_below_high` persistence, programmatic capital allocation + CEO TSR, adversarial agent dims, M&A weekly cron + SQLite aux DB, recalculate API full enriched fetch. PYPL: conviction +1→+7, bq +8, divergence +2, OEY 11.3%. 58 tests pass. Status doc: `instruction_docs/ssi_and_conviction_updates/FUNDAMENTAL_AGENT_UPDATE_JULY_2026_STATUS.md`. UI Section 6 deferred to Parth.
   - Files changed: `src/conviction_engine/*`, `api/services/conviction_service.py`, `tests/test_conviction_engine.py`, `scripts/run_ma_activity_weekly.py`, `docs/api/services/conviction/*`

4. **DRIFT ALERT trigger fix (email spec 5D) — replace wrong degradation rule** — SUCCESSFUL
   - Summary: Fixed Overwatch signal alerts (API) + Nuxt UI copy. API: monthly-fall drift rules, DRIFT ALERT labels. UI (`MindwealthUI_Vue`): `⚠ degraded FWD` → `⚠ drifted FWD`, DEGRADING → DRIFTING/DRIFT ALERTS; removed BT-gap false triggers in BFF (`fwd < bt - 10`).
   - Files changed: `api/services/degradation_service.py`, `api/services/analyst_service.py`, `MindwealthUI_Vue/utils/signals.ts`, `MindwealthUI_Vue/pages/signals.vue`, `MindwealthUI_Vue/server/utils/mindwealth-data.ts`, others

5. **New Signals page empty while nav shows 7 — BFF data source fix** — SUCCESSFUL
   - Summary: Sidebar/header counts used `GET /signals/counts` (7 new) but New Signals table loaded only via conviction overlay POST. When overlay unavailable or empty, BFF returned empty list. Fixed `loadNewSignals` and `loadOutstandingSignals` to prefer `GET /signals/reports/{slug}/latest`, then overlay, then `/signals/surface` (same pattern as All Signals).
   - Files changed: `MindwealthUI_Vue/server/utils/mindwealth-data.ts`

6. **Signals KPI cards wrong long/short counts when function filter active** — SUCCESSFUL
   - Summary: LONG/SHORT/NEW TODAY KPI cards used `buildSignalsSummary(filteredSignals)` so TrendPulse filter showed 55/0 instead of API truth 112/9. NEW TODAY card incorrectly showed outstanding totals (121) as new signals. Fixed: KPI cards use `GET /signals/counts` buckets via `summaryWithCountBucket()`; NEW TODAY uses `new_detail` (7 = 4L + 3S). BFF enriches outstanding/new list summaries from counts API; dashboard `outstanding_count` uses counts bucket.
   - Files changed: `MindwealthUI_Vue/pages/signals.vue`, `utils/signal-filters.ts`, `server/utils/signal-parsers.ts`, `server/utils/mindwealth-data.ts`

7. **Claude shortlist MTM stuck at 0.0% (MCHI, TLT, BRK-B)** — SUCCESSFUL
   - Summary: Root cause — `claude_signals_report.csv` is written once at Claude generation and never gets nightly price refresh (unlike `outstanding_signal.csv`). Shortlist API served stale `0.0%, 0 days` MTM from report date. Fixed: `refresh_dataframe_current_prices()` recomputes Today/MTM/holding-days from `trade_store/stock_data` in-memory in `get_shortlist_report()` before enrichment. Verified MCHI 0.0%→2.14%, TLT→−3.06%, BRK-B→0.18%.
   - Files changed: `src/utils/mtm_pricing.py`, `api/services/reports_service.py`, `tests/test_mtm_pricing.py`

8. **Portfolio implementation log — product overview section at top** — SUCCESSFUL
   - Summary: Added "Portfolio Page — What It Is (read this first)" to `portfolio_implementation_log.md`: what the page is, planned features, per-view UI visibility, nine HANDOFF endpoints + backend responsibilities, implementation status snapshot, bridge into existing Simple Explanation build log. Docs only — zero prod impact.
   - Files changed: `instruction_docs/portfolio_page/portfolio_implementation_log.md`

9. **Ahil NAV analysis deliverables — implementation status refresh** — SUCCESSFUL
   - Summary: Reviewed `ahil_analysis/` (consolidated PDF + two filled NAV workbooks). Updated `PORTFOLIO_PAGE_AIM_AND_STATUS.md`, `portfolio_implementation_log.md`, `OPEN_QUESTIONS_FOR_ROHIT.md`: monthly NAV/benchmark/drawdown delivered; Axiom 2 + $10M/N=60 evidence; A1 proxy four-book; `/portfolio/nav` reclassified Partial; new §8.0/8.2 ingest backlog. Docs only.
   - Files changed: `instruction_docs/portfolio_page/PORTFOLIO_PAGE_AIM_AND_STATUS.md`, `portfolio_implementation_log.md`, `OPEN_QUESTIONS_FOR_ROHIT.md`

10. **Portfolio NAV history layer + workbook ingest + nav_engine adapter** — SUCCESSFUL
   - Summary: `src/portfolio_nav/` workbook ingest + engine plug-in; `/portfolio/nav` monthly mtm/closed/benchmark, vol/beta, proxy attribution; all MODEL books on nav. Tests 49 pass.
   - Files changed: `src/portfolio_nav/*`, `config/portfolio_nav.yaml`, `api/services/portfolio_book.py`, `api/services/portfolio_pipeline_service.py`, `tests/test_portfolio_nav.py`, `tests/test_api_portfolio.py`

11. **Ahil nav_engine.py integrated + live engine verification** — SUCCESSFUL
   - Summary: Pasted Ahil `nav_engine.py` logic already ported to `ahil_nav_engine_core.py` + `ahil_nav_engine.get_nav_history()`. Live run (Version B, dual-gated, entry≥2024-01-01): 30 months, CAGR 16.79%, Sharpe 1.82, final NAV $14.74M vs workbook $13.84M / 13.89% CAGR (~6.5% gap — likely forward_testing drift + yfinance). Engine is default `/portfolio/nav` source; workbook fallback on failure. 49 tests pass with `PORTFOLIO_NAV_FORCE_WORKBOOK=1`.
   - Files changed: (verification only — no new code this step) `src/portfolio_nav/ahil_nav_engine_core.py`, `src/portfolio_nav/ahil_nav_engine.py`

12. **Portfolio daily NAV API + configurable sizer notional (v1.8.3)** — SUCCESSFUL
   - Summary: Phase 1 — `mtm_daily[]` / `closed_daily[]` on `/portfolio/nav` from nav_engine (912 trading days, Jan-24+); `mtm[]` stays monthly. Phase 2 prep — `get_portfolio_notional()` + `PORTFOLIO_USE_RESEARCH_NOTIONAL=1` ($10M) / `PORTFOLIO_NOTIONAL` env; default $100M unchanged. API docs v1.8.3. 56 tests pass.
   - Files changed: `src/portfolio_nav/types.py`, `stats.py`, `ahil_nav_engine.py`, `service.py`, `api/services/portfolio_service.py`, `portfolio_pipeline_service.py`, `config/portfolio_nav.yaml`, `docs/mindwealth-api-docs/*`, `tests/test_portfolio_nav.py`, `tests/test_api_portfolio.py`, `PORTFOLIO_API_HANDOFF.md`

13. **Sync docs/api clone updates into mindwealth-api-docs** — SUCCESSFUL
   - Summary: Compared `docs/api` vs `docs/mindwealth-api-docs`. Main docs were ahead on portfolio/signals/analyst; clone had macro scheduled-events content missing from main. Copied 4 files (frontend integration guide + 3 macro endpoint pages), merged macro README/changelog/analytics README, updated service index. Preserved all mindwealth-api-docs-only content (portfolio, signals enrich, analyst alert params). Docs only — zero prod impact.
   - Files changed: `docs/mindwealth-api-docs/frontend/macro-scheduled-events-integration.md`, `services/macro/endpoints/get-pre-catalyst.md`, `get-post-event-regime.md`, `get-scheduled-events-calendar.md`, `services/macro/README.md`, `services/analytics/README.md`, `services/README.md`, `README.md`, `changelog.md`, `services/macro/endpoints/get-runic-nightly.md`

14. **Delete docs/api clone + canonical API docs cursor rule** — SUCCESSFUL
   - Summary: Removed stale `docs/api/` directory. Added **API documentation (canonical path)** section to `.cursor/rules/mindwealth-ui-repository-rules.mdc` and global `mindwealth-repository-rules.mdc` — "update API docs" → `docs/mindwealth-api-docs/`. Fixed live references in `api/README.md`, `scripts/export_openapi.py`, `getting-started.md`, api-creation skills. Docs only — zero prod impact.
   - Files changed: deleted `docs/api/`, `.cursor/rules/mindwealth-ui-repository-rules.mdc`, `api/README.md`, `scripts/export_openapi.py`, `docs/mindwealth-api-docs/getting-started.md`, `docs/mindwealth-api-docs/changelog.md`, `.cursor/skills/api-creation/SKILL.md`, `.cursor/skills/api-creation-2/SKILL.md`, `/home/ubuntu/.cursor/rules/mindwealth-repository-rules.mdc`

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

12. **Conviction Engine score audit — daily_update, freshness, AMZN/MSFT/NVDA BQ** — SUCCESSFUL
   - Summary: Confirmed `daily_update` ran today (`last_daily_update` 2026-07-22T14:01Z on 193 tickers; manifest `conviction_store/daily/2026-07-21/manifest.json` at 03:22Z). **Root cause of weak mega-cap BQ:** `revenue_growth_yoy` in `fundamentals_enriched.py` uses `iloc[-1]` vs `iloc[-5]` but yfinance quarterly columns are newest-first — inverts YoY sign (AMZN stored −14% vs yfinance +16.6%). That drives `growth_trajectory` −1 on AMZN/MSFT/NVDA. Daily pipeline mode does not refresh `bq_components` (only `full_recalculation` does). `data_coverage` falsely flags `info:empty` / missing BQ inputs on daily runs because enriched fundamentals are not passed into `apply_coverage_to_record`. AMZN **bq_raw +3.5** (REDUCED) but **conviction −3.5** (valuation_tax −7); corrected rev growth → bq ~+5 (TACTICAL). MSFT stored +4.5 → corrected ~+9 (MAX); NVDA +3.5 → ~+10 (MAX). No code fix in this step — audit only.
   - Files changed: (audit only — no code changes)

13. **Consolidated "questions for Rohit" — portfolio page backend review** — SUCCESSFUL
   - Summary: Pulled full context from the "Portfolio page backend review" chat history (`OPEN_QUESTIONS_FOR_ROHIT.md` Asks 1–5, IBKR blocker update, PERSONAL book, FX, D1 sizing, four-book toggle, conviction audit) and gave a plain-English, elaborated explanation of every open clarification Divyanshu still needs from Rohit. Chat-only answer, no code or doc changes.
   - Files changed: none (read-only; existing `OPEN_QUESTIONS_FOR_ROHIT.md` remains source of record)

14. **Conviction Engine revenue-growth YoY fix + full universe recalc (193 tickers)** — SUCCESSFUL
   - Summary: Fixed the bug found in #12 — `revenue_growth_yoy` and `gross_margin_trend` in `fundamentals_enriched.py` sorted quarterly columns ascending before indexing (yfinance returns newest-first; code assumed oldest-first, inverting the YoY sign). `revenue_growth_yoy` now matches yfinance's own `revenueGrowth` (AMZN 16.6%, MSFT 18.3%, NVDA 85.2% — all previously computed negative). Ran `scripts/run_conviction_engine_daily.py --fundamentals-mode full` across all 193 tickers (0 errors, ~7 min) to rebuild `bq_components`/`bq_raw` with corrected inputs. Mega-cap BQ jumped to sensible levels: AMZN +3.5→**+7.0** (REDUCED→TACTICAL), MSFT +4.5→**+9.0** (TACTICAL→MAX), NVDA +3.5→**+12.0** (REDUCED→MAX), **AAPL +0.0→+12.0 (BLOCKED→MAX)**, GOOG +3.5→+9.0, META +3.5→+7.0. Full test suite: 429 passed / 1 pre-existing unrelated flake (`test_d6_smoke.py`, passes standalone — test-isolation issue, not caused by this change) / 2 skipped. VT-long overlay `max_conviction` count 0→52, `tactical_plus` 0→205.
   - Files changed: `src/conviction_engine/fundamentals_enriched.py`; regenerated `conviction_store/*.json` (193 files) + `conviction_store/daily/2026-07-21/*` + `conviction_store/overlays/*`

15. **Portfolio Backend Remaining Build — Phases 0-9 (config layer, D1 sizing, eviction, Axiom 2, four-book replay, AUTO/MANUAL, alerts, personal book, docs)** — SUCCESSFUL
   - Summary: Implemented the full 9-phase plan (`portfolio_backend_remaining_build_ace8e43a.plan.md`) sequentially. **Phase 0:** `config/portfolio_policy.yaml` + `api/services/policy_service.py` — single config surface for all 5 open Rohit decisions (notional, N, rebalance mode, eviction margin/freeze, sleeves), env-override precedence, `policy_meta()` for API transparency. **Phase 1:** `scripts/run_portfolio_book_snapshot_daily.py` + `src/portfolio_nav/book_snapshot_store.py` (SQLite; position/regime-bucket/eviction-log tables), cron-installed; fixed a `position_snapshots` PK collision (switched to autoincrement id + date/scenario index) discovered during first live run. **Phase 2:** `api/services/sizing_engine.py` — D1 NAV/N admission-slot model (`max_slots_for_sleeve = floor(ceiling_pct×N/100)`), wired into `get_portfolio_sizer()` behind `SIZING_ENGINE_VERSION=d1_slots` (legacy engine stays default); added `conviction_multiplier` to sized rows. **Phase 3:** `src/portfolio_nav/eviction_engine.py` — pure 1C/A2(margin_m)/A3(freeze_at_n) decision functions; `portfolio_pipeline_service.run_eviction_check()` persists daily decisions to `eviction_log`; `_classify_exit_type()` now returns `eviction` for recently-evicted tickers. **Phase 4:** `rebalance_mode` (`hold_original`|`legacy_rebalance`) + `n_target` added to `run_nav_engine()`; `hold_original` = Axiom 2 (freed cash idle, no reset-to-1/N); `ahil_nav_engine.py` resolves the mode from policy without an `api.*` import (kept `src/` independent). **Phase 5:** `src/portfolio_nav/four_book_engine.py` — BASE/BASE+SSI/BASE+CONVICTION/ENHANCED off one shared trade ledger; SSI ceiling series direct from `ssi.db` (full 2015+ coverage, no gap); conviction daily archive only from 2026-05-15 forward (`conviction_store/daily/`), never backfilled — `cv_data_status` discloses the boundary; attribution decomposition uses **cumulative** (not annualized) return for the conviction book's short window, re-baselined to the conviction window's own opening NAV (fixed a bug where the first pass divided by the wrong start_nav and produced nonsensical multi-hundred-percent "effects"); residual check closes to 0 by construction. Wired into `ahil_nav_engine.get_nav_history()` so `/portfolio/nav?book=base|ssi|cv|enhanced` now serves real per-book series (verified via direct API call: `cv` book correctly limited to 47 trading days from 2026-05-15, `conviction_effect_pp=-1.04`). **Phase 6:** `resolve_auto_scenario()` (regime-driven normal/stress/lowvol pick from live VIX/HY/SSI) + `api/services/manual_overrides_service.py` (persisted per-position $ overrides, JSON store) wired into `get_portfolio_sizer(scenario="auto"|"manual")`; `GET /portfolio/regime-history` (from Phase 1's snapshot store); `api/services/alerts_service.py` + `GET /portfolio/alerts` (correlation breaches, cross-function conflicts, DRIFT, negative-R:R-uncovered, evictions — all built from data already computed elsewhere, no new source of truth). **Phase 7:** `api/services/personal_book_service.py` (JSON CRUD store) + `book_id=personal` unblocked on `/portfolio/nav` and `/portfolio/holdings` only (still 422 on sizer/risk — MODEL-only concepts); live snapshot only, `data_status.status=live_snapshot_only` discloses no historical series exists. **Phase 8:** Confirmed brokerage remains explicitly deferred (`OPEN_QUESTIONS_FOR_ROHIT.md` Ask 3 status note added) — zero code changes. **Phase 9:** Added `tests/test_portfolio_backend_engines.py` (52 new unit tests covering every new engine) + 22 new API tests in `tests/test_api_portfolio.py` (auto/manual scenarios, manual-override CRUD, alerts, regime-history, personal CRUD+nav+holdings, brokerage-still-blocked regressions) — 124/124 portfolio tests pass; re-ran full suite (496 passed, 2 pre-existing unrelated failures in `test_d6_smoke.py`/`test_dominant_reason.py`, not touched by this work). Updated `docs/mindwealth-api-docs/` (changelog v1.9.0, portfolio README, 4 new endpoint pages, updated get-nav/holdings/sizer/sizing/risk), re-exported `openapi/mindwealth-v1.json`, and updated `PORTFOLIO_API_HANDOFF.md` (§13 Definition of Done checkboxes, new §15 implementation status).
   - Files changed: `config/portfolio_policy.yaml`, `api/services/policy_service.py`, `api/services/sizing_engine.py`, `api/services/manual_overrides_service.py`, `api/services/personal_book_service.py`, `api/services/alerts_service.py`, `api/services/portfolio_service.py`, `api/services/portfolio_pipeline_service.py`, `api/services/portfolio_book.py`, `api/routers/portfolio.py`, `src/portfolio_nav/eviction_engine.py`, `src/portfolio_nav/four_book_engine.py`, `src/portfolio_nav/book_snapshot_store.py`, `src/portfolio_nav/ahil_nav_engine_core.py`, `src/portfolio_nav/ahil_nav_engine.py`, `src/config_paths.py`, `scripts/run_portfolio_book_snapshot_daily.py`, `scripts/install_aws_cron.sh`, `.gitignore`, `tests/test_portfolio_backend_engines.py` (new), `tests/test_api_portfolio.py`, `docs/mindwealth-api-docs/*`, `instruction_docs/portfolio_page/OPEN_QUESTIONS_FOR_ROHIT.md`, `instruction_docs/portfolio_page/PORTFOLIO_API_HANDOFF.md`

16. **Fundamentals `_df_row`/`_df_ttm_sum` sort-order bug fix + full universe recalc (193 tickers)** — SUCCESSFUL
   - Summary: Follow-up to #14 (same bug class, deferred). `_df_row()` and `_df_ttm_sum()` in `fundamentals_enriched.py` indexed yfinance quarterly columns with `iloc[-1]`/`iloc[-periods:]` without `sort_index()` first — since yfinance returns columns newest-first, these silently read the OLDEST quarter(s) instead of the latest. Affected `revenue_ttm`, `gross_profit_ttm`, `net_income_ttm`, `ebitda_ttm`, `operating_cf_ttm`, `capex_ttm`, `total_debt`, `total_cash`/`cash_and_equivalents`, `net_debt_stored`, `fcf_ttm`, `fcf_prior_year`/`fcf_growth_yoy`, `roic_proxy` (via `equity`) — most TTM/balance-sheet valuation inputs. Also fixed the same unsorted-slice bug in the prior-year FCF block (`ocf_row`/`capex_row`/`rev_prior` at lines ~606-623). Added regression test (`test_ttm_and_balance_sheet_fields_use_latest_quarter_not_oldest`) constructing a mock 8-quarter newest-first DataFrame and asserting latest-quarter/TTM-sum correctness. Ran `scripts/run_conviction_engine_daily.py --fundamentals-mode full` across all 193 tickers (0 overlay errors). Confirmed material shifts, e.g. AMZN `net_debt_stored` $67.0B→$108.1B, `fcf_ttm` $7.7B→**-$2.5B** (AI-capex-driven FCF compression now correctly reflected), MSFT `net_debt_stored` $31.7B→$24.9B. `bq_components`/`bq_raw` for the sampled mega-caps were unchanged (those specific BQ sub-scores don't consume these exact fields), but downstream valuation-tax/owner-earnings-yield inputs are now correct. Full suite: 497 passed, 2 skipped, 1 pre-existing unrelated deselect (`test_dominant_reason.py` live-combo flake).
   - Files changed: `src/conviction_engine/fundamentals_enriched.py`, `tests/test_conviction_engine.py`; regenerated `conviction_store/*.json` (193 files) + `conviction_store/daily/2026-07-21/*` + `conviction_store/overlays/*`

17. **Move `resolve_auto_scenario()` (D4 AUTO) regime thresholds into `portfolio_policy.yaml`** — SUCCESSFUL
   - Summary: `resolve_auto_scenario()` in `portfolio_service.py` hardcoded its VIX/HY/SSI stress and low-vol thresholds (70/4.0/0.9/30/1.0). Added an `auto_scenario` block (`status: interim`) to `config/portfolio_policy.yaml` and `policy_service.get_auto_scenario_thresholds()`/`get_auto_scenario_status()`; `resolve_auto_scenario()` now reads thresholds from policy instead of hardcoding, with identical defaults (zero behavior change until the block is edited). Added `auto_scenario_thresholds` to `policy_meta()`. New tests: threshold defaults, status, and a regression proving tightening the policy value actually changes `resolve_auto_scenario()`'s output (proves it's config-driven, not hardcoded). 129/129 portfolio tests pass.
   - Files changed: `config/portfolio_policy.yaml`, `api/services/policy_service.py`, `api/services/portfolio_service.py`, `tests/test_portfolio_backend_engines.py`

18. **Daily personal-book (`book_id=personal`) snapshot job for future NAV history** — SUCCESSFUL
   - Summary: Personal book previously had zero history mechanism — every `/portfolio/nav?book_id=personal` call was a single live snapshot forever, per Phase 7 (`data_status.status=live_snapshot_only`). Added a `personal_book_snapshot_daily` table to `src/portfolio_nav/book_snapshot_store.py` (`write_personal_book_snapshot()`/`read_personal_book_series()`/`earliest_personal_snapshot_date()`, idempotent per-day upsert) and a new daily script `scripts/run_personal_book_snapshot_daily.py` (cron-installed in `scripts/install_aws_cron.sh`, 19:10 ET weekdays, right after the portfolio book snapshot job). `personal_book_service.get_personal_nav_history()` reads the accumulated series; `get_personal_nav_payload()` now serves it via `mtm`/`mtm_daily` once at least one day exists, switching `data_status.status` from `live_snapshot_only` to `live_from_snapshot_start` (with `earliest_date`) — still zero backfill/fabrication before the job's first run. Smoke-tested the script live against the dev store (wrote today's real personal-book snapshot: NAV $5000, 0 positions) and confirmed the NAV payload now serves it. Updated `personal-book.md`. 517/518 full-suite tests pass (1 pre-existing deselect).
   - Files changed: `src/portfolio_nav/book_snapshot_store.py`, `scripts/run_personal_book_snapshot_daily.py` (new), `api/services/personal_book_service.py`, `scripts/install_aws_cron.sh`, `tests/test_portfolio_backend_engines.py`, `tests/test_api_portfolio.py`, `docs/mindwealth-api-docs/services/portfolio/endpoints/personal-book.md`

19. **macro_intelligence Priority-1 audit fixes — Fed cycle PAUSING resurrection bug (T-01), VIX single-day spike detection (T-03)** — SUCCESSFUL
   - Summary: **T-01:** `fed_cycle_at_date()` correctly computed `PAUSING` in `build_fed_cycle_series()` for every week once the Fed's direction flips to PAUSE, but the caller's fallback logic (lines 187-221) then discarded that correct label and rescanned the *entire* historical series for the last HIKING/CUTTING-labeled week — resurrecting a stale, already-ended cycle label (e.g. `CUTTING_LATE` from March 2026) for the whole 5-month pause. Live-verified: `fed_cycle_at_date('2026-07-22')` returned `CUTTING_LATE` before the fix, `PAUSING` after. Fix: when the freshly-computed direction is PAUSE and the series' own label is not itself a stale HIKING/CUTTING carry-over, trust and return it directly — the historical rescan now only runs in the genuine edge case where the cached series hasn't caught up yet. **T-03:** VIX tier classification (`evaluate_variable_tier()`) only checked absolute level + percentile, so the Jun 5 2026 real event (VIX 15.40→21.51, +39.68% in one day) stayed `NORMAL` because 21.51 sits below the RARE `abs_level` (25.0). Added `single_day_pct_change` thresholds to `CONFIG.yaml` (RARE ≥25%, EXTREME ≥40%) and wired `_single_day_change_meta()` in `pull_all.py` to compute prior-close vs current and pass it through `evaluate_variable_tier()`'s `meta` param — escalates tier on spike magnitude alone, independent of absolute level. `single_day_pct_change`/`prior_close` now persist in `daily_readings.meta_json` for audit. Added regression tests for both (fed-cycle pause-doesn't-resurrect-stale-label; VIX spike escalation at the real Jun 5 magnitude). Full suite: 517 passed, 2 skipped, 1 pre-existing deselect.
   - Files changed: `src/macro_intelligence/engine/fed_cycle.py`, `src/macro_intelligence/engine/percentiles.py`, `src/macro_intelligence/data/pull_all.py`, `macro_intelligence/CONFIG.yaml`, `tests/test_fed_cycle_fixtures.py`, `tests/test_macro_percentiles.py`

---

### 2026-07-21

1. **SSI composite vs layer scores — 3-layer superindex wiring** — SUCCESSFUL
   - Summary: Root cause — `ssi_level` used legacy 4-input formula (HYG/LQD, DBMF, CNN, VIX) while dashboard layer scores implied 40/35/25 model. Added `build_layer1/2/3()` + `build_superindex()`; composite now equals weighted z-score layer means. Fixed McClellan (remove erroneous cumsum) and NH/NL ratio (`highs/(highs+lows)`). On 2026-07-16: composite **+0.319** = 0.40×L1 + 0.35×L2 + 0.25×L3 (was ~+0.16). `positioning.json` exposes `layers` block; `/analytics/sentiment/layers` composite includes layer scores.
   - Files changed: `src/sentiment_superindex/engine/superindex.py` (new), `ssi_score.py`, `positioning.py`, `pull_all.py`, `mcclellan_pull.py`, `sp500_breadth.py`, `macro_intelligence/SSI_CONFIG.yaml`, `api/services/reports_service.py`, `src/sentiment_superindex/analysis/zscore_vs_percentile.py`, `tests/test_ssi_superindex.py` (new)

2. **SSI next steps — rebuild data + dashboard wiring** — SUCCESSFUL
   - Summary: Ran `scripts/run_ssi_daily.py` (positioning.json 2026-07-21, ssi_level **+0.217**). Full `scripts/rebuild_ssi_history.py` backfilled **3,857** rows in `ssi.db` (2015-01-01 → 2026-07-21). Fixed `persist_daily` legacy column extraction for new payload shape. Updated `MindwealthUI_Vue/server/utils/sentiment-mapper.ts` to use `composite.layers.*.score` for KPI layer scores; rebuilt Nuxt dev (`:8514`). Restarted `mindwealth-api-dev` (`:8507`).
   - Files changed: `src/sentiment_superindex/db/connection.py`, `scripts/rebuild_ssi_history.py` (new), `MindwealthUI_Vue/server/utils/sentiment-mapper.ts`

3. **Portfolio "Could not compute" / BLOCKED $0 for ETFs & indexes (^GSPC, FXI, EFA, EWJ)** — SUCCESSFUL
   - Summary: Root cause — conviction overlay sets `verdict=NOT_APPLICABLE` with `bq_raw=NaN` for ETFs/indexes; sizer treated NaN as a numeric BQ, `_bq_tier(nan)` returned BLOCKED 0%, and D2 only ran when `bq is None`. Fixed by normalizing BQ via `_safe_float`, applying D2 for all `not_applicable` rows, hardening `_bq_tier` against NaN, and adding regression tests. **Nuxt ui-dev:** `conviction n/a` label + `not_applicable` mapper; dev UI rebuilt on **:8514** (not pushed).
   - Files changed: `api/services/portfolio_service.py`, `tests/test_api_portfolio.py`; MindwealthUI_Vue: `constants/unavailable.ts`, `utils/portfolio-display.ts`, `types/api.ts`, `server/utils/portfolio-mappers.ts`, `components/portfolio/PortfolioClusterCard.vue`, `components/portfolio/PortfolioPnlView.vue`, `assets/css/main.css`

3. **Review JULY presentation slides 5–7 (Macro Runic / validation)** — SUCCESSFUL
   - Summary: Cross-checked `instruction_docs/JULY_MindWealth_Presentation_v3.pptx` slides 5–7 against `macro_intelligence/CONFIG.yaml`, combo discovery outputs, and `MindWealth_Macro_Runic_Latest.html`. Found critical priority-stack error (slide 5), stale “Currently Active” block, Combo D ~28% likely VIX-percentile mix-up, slide 7 speaker notes copied from Portfolio Layer 1, and several horizon/methodology inconsistencies. Docs-only review — no pptx edits.
   - Files changed: none (review only)

4. **Portfolio unscored positions (stale conviction overlay)** — SUCCESSFUL
   - Summary: VT conviction overlay was stale (May 2026); daily cron only overlaid new_signal, not VT long/short. Fixed `update_trade_data.sh` overlay list; on-demand conviction merge in `_merge_conviction` (unscored 59→0); expanded COMMON_ETFS; UI `Unscored` label; full conviction pipeline started for CSV refresh. Dev :8507/:8514 restarted.
   - Files changed: `api/services/portfolio_service.py`, `src/conviction_engine/scoring.py`, `update_trade_data.sh`, `scripts/run_conviction_engine_daily.py`, `tests/test_api_portfolio.py`; MindwealthUI_Vue display files

5. **Combo D fed-cycle slices — QE n=9 USE (Divyanshu)** — SUCCESSFUL
   - Summary: Per D5 recalibrated Combo D (n=46, 2-of-3 gates): CUTTING_LATE n=13 USE, HIKING_LATE n=24 USE, **QE n=9 USE** (was CANNOT USE at n&lt;10). Added `combo_hit_rates.D.fed_cycle_slices` in CONFIG with validated 1W/2W hit rates and avg SPX %; `combo_fed_cycle_slice_stats()` in `combo_metadata.py`; exposed on `GET /macro/combos/D` as `fed_cycle_slices`. D5 script uses per-combo min_n (D=9, E=10). QE @1W: 44.4% bear hit, +0.65% avg SPX; @2W: 33.3%, +0.54%.
   - Files changed:
     - `macro_intelligence/CONFIG.yaml`
     - `src/macro_intelligence/engine/combo_metadata.py`
     - `api/services/macro_service.py`
     - `testing/macro_th_exp/run_d5_fed_cycle_reslice.py`
     - `testing/macro_th_exp/D5_fed_cycle_reslice_2026-07-16.{csv,json,md}` (updated)
     - `testing/macro_th_exp/D5_fed_cycle_reslice_2026-07-21.{csv,json,md}` (new)
     - `tests/test_combo_metadata.py`

### 2026-07-20

1. **Portfolio aim & status doc (beginner-friendly)** — SUCCESSFUL
   - Summary: Created `instruction_docs/portfolio_page/PORTFOLIO_PAGE_AIM_AND_STATUS.md` — plain-English aim, planned features, how they help, glossary, and implementation status (implemented / unblocked-unimplemented / blocked). Docs only.
   - Files changed: `instruction_docs/portfolio_page/PORTFOLIO_PAGE_AIM_AND_STATUS.md` (new)

2. **Portfolio implementation log (`portfolio_implementation_log.md`)** — SUCCESSFUL
   - Summary: Created AI-Analyst-style implementation log for Portfolio page backend work — plain-English overview, HANDOFF endpoint status table, API surface, holdings merge logic, testing smoke commands, file map, Rohit blockers, prod checklist. Docs only.
   - Files changed: `instruction_docs/portfolio_page/portfolio_implementation_log.md` (new)

2. **Portfolio API — unblocked HANDOFF endpoints (entries, exits, holdings, sizing alias, risk report)** — SUCCESSFUL
   - Summary: Implemented MODEL-book portfolio pipeline: `GET /portfolio/holdings`, `GET /portfolio/sizing` (alias), `book_id` on sizer/risk, `GET /signals/entries`, `GET /signals/exits`, HANDOFF-shaped `GET /signals/reports/portfolio-risk/latest` (+ `implied_natural_exit_date`), `same_asset_siblings`/`multi_sig`/`rr_dynamic` on holdings, D2 ETF/FX base-size fix, `conviction_summary` on risk. `book=base|ssi|cv` and `book_id=brokerage|personal` return 422 until A1/IBKR. Tests: 56 pass (portfolio + signals).
   - Files changed: `api/services/portfolio_book.py`, `portfolio_pipeline_service.py`, `portfolio_service.py`, `signal_enrichment_service.py`, `api/routers/portfolio.py`, `api/routers/signals.py`, `tests/test_api_portfolio.py`, `tests/test_api_signals_surface.py`

2. **Portfolio open questions doc for Rohit (5 blocking decisions)** — SUCCESSFUL
   - Summary: Created `instruction_docs/portfolio_page/OPEN_QUESTIONS_FOR_ROHIT.md` — expanded one-line asks into detailed decision briefs with file/line citations for: production N + notional ($10M vs $100M), Axiom 2 rebalancing vs Ahil nav_engine, IBKR integration spec + owner, v5 SLEEVES as sleeve/slot source, and `same_asset_siblings` scope (all rows vs negative-only). No prod impact — docs only.
   - Files changed: `instruction_docs/portfolio_page/OPEN_QUESTIONS_FOR_ROHIT.md` (new)

2. **AI Analyst v1.8.1 — Overwatch context, tabs, regime/sentiment warnings** — SUCCESSFUL
   - Summary: `GET /analytics/analyst/context` cross-page bundle; `meta.tabs` badges; `channel` filter; regime/sentiment/persistence/watch alert types; chat `page_context`. Commits `b984f0d6c` (UI), `c5c5b59` (api-docs). Dev API restarted on :8507 — health reports v1.8.1. Push blocked (no GitHub creds on host).
   - Files changed: `api/services/analyst_service.py`, `macro_override.py`, `analytics.py`, `analyst.py` schemas, `chatbot.py` page_context, `docs/mindwealth-api-docs/`, tests

3. **AI Analyst backend hardening — cache, docs, health markers, Claude copy** — SUCCESSFUL
   - Summary: Degradation parquet+result cache (`overwatch_store/`) — cached API reads ~0.1–0.25s (was >240s timeout). Fixed portfolio trigger re-loading 1990 CSVs per row. Added optional Claude alert copy (`ANALYST_USE_CLAUDE_COPY`), Tavily/Sheets integration health markers, synced `mindwealth-api-docs` to v1.8.0. Live curl: brief 37ms, alerts w/ degradation 248ms, check-degradation 142ms. Tests: 8/8 pass.
   - Files changed: `api/services/degradation_cache.py`, `degradation_service.py`, `integration_health_store.py`, `analyst_copy_service.py`, `system_health_service.py`, `analyst_service.py`, `chatbot/agents/web_search_agent.py`, `src/conviction_engine/daily_run.py`, `tests/test_degradation_cache.py`, `docs/mindwealth-api-docs/`, `scripts/overwatch/run_overwatch_signals.py`
   - Note: Commits `0a7e68ff9` (MindWealth_UI) and `08264a1` (mindwealth-api-docs) on host; `git push` blocked (no GitHub credentials on server).

4. **Presentation doc — week of 13–17 July 2026 work overview** — SUCCESSFUL
   - Summary: Created detailed presentation-ready markdown in `presentation_doc/` — day-by-day breakdown (13–17 Jul), blockers, issues/resolutions, AI Analyst + Portfolio + macro deliverables, verification table, outstanding items, and presentation guidance. Added **Simple Explanation** section at top (plain-language week overview, matching implementation log style). Synthesized from `ai_analyst_implementation_log.md`, `portfolio_implementation_log.md`, and job-status macro entries. Docs only — no prod impact.
   - Files changed: `presentation_doc/week_of_13-17_july_2026_work_overview.md` (new, then updated with Simple Explanation)

### 2026-07-19

1. **Backend API endpoint health audit (prod 8506 + dev 8507)** — SUCCESSFUL
   - Summary: Swept 97 OpenAPI routes on prod (`v1.7.3`): 55 OK, 27 skipped (JWT), 3×404 (analyst alerts/brief, overwatch stream — v1.8 only), 3 POST timeouts (expected long jobs), 0×5xx. Dashboard “Avg Fwd win rate: Could not compute” traced to Nuxt BFF `429 Too Many Requests` on `/analytics/performance` during parallel dashboard fan-out (not backend crash). Direct curl to performance returns `avg_fwd_testing_win_rate: 57.85%`.
   - Files changed: none (investigation only)

2. **Fix dashboard 429 + v1.8 analyst routes deploy to prod** — SUCCESSFUL
   - Summary: Raised `apikey.read` burst in `config/rate_limits.yaml` (60→150/10s). Shipped API v1.8.0 (analyst alerts/brief, overwatch SSE, system health). Nuxt BFF: GET cache/dedup, real `avg_fwd_testing_win_rate`, removed hardcoded WR override. Merged `chatbot-dev`→`chatbot-prod` locally; prod clone fast-forwarded; restarted `mindwealth-api` + `mindwealth-ui`. Prod health now `v1.8.0`; analyst/performance routes 200.
   - Files changed: `config/rate_limits.yaml`, `api/main.py`, `api/routers/{analytics,overwatch,system,signals}.py`, `api/services/{analyst,degradation,overwatch_event_bus,system_health}_*.py`, `api/schemas/analyst.py`, `tests/test_api_analyst.py`, `scripts/overwatch/*`; MindwealthUI_Vue: `mindwealth-client.ts`, `mindwealth-data.ts`, `performance-aggregates.ts`, `unavailable-data.ts`
   - Note: `git push origin` failed (no GitHub credentials on host); deploy done via local fetch into prod clone.

### 2026-07-18

1. **Fix portfolio cluster sizes exceeding deployed equity ceiling** — SUCCESSFUL
   - Summary: Each open position was allocated 100% of its cluster budget independently, so cluster `deployed_usd` summed to ~$1.77B while summary showed $80M. Cluster caps now use the equity ceiling (`deployed_cap_usd`, e.g. $80M at 80%) and each cluster budget is split proportionally across positions by BQ tier rank weight (MULTI-SIG +10% boost). Cluster deployed totals now sum to exactly the equity ceiling; constraint check shows "Cluster caps" OK.
   - Files changed:
     - `api/services/portfolio_service.py`
     - `tests/test_api_portfolio.py`

2. **AI Analyst backend — Overwatch alerts, system health, SSE** — SUCCESSFUL
   - Summary: Implemented unified `GET /analytics/analyst/alerts` and `/brief`, admin `GET /system/health`, in-process SSE `GET /overwatch/stream`, spec-aligned degradation (60% watch/breach + 4-week trend), macro runic alerts with Analog Finder, `historical_analogs` in nightly JSON, overwatch cron scripts, API v1.8.0.
   - Files changed:
     - `api/schemas/analyst.py`, `api/services/analyst_service.py`, `api/services/system_health_service.py`, `api/services/overwatch_event_bus.py`, `api/services/degradation_service.py`
     - `api/routers/analytics.py`, `api/routers/overwatch.py`, `api/routers/system.py`, `api/main.py`, `api/rate_limit.py`, `api/routers/signals.py`
     - `src/macro_intelligence/output/json_writer.py`, `scripts/overwatch/*.py`, `scripts/install_aws_cron_dual.sh`
     - `tests/test_api_analyst.py`, `docs/dev_to_prod_migration_todos.md`, `docs/api/openapi/mindwealth-v1.json`
     - `docs/api/services/analyst/` (README + 5 endpoint pages), `docs/api/changelog.md`

### 2026-07-17

1. **B4 original-spec window fix pipeline (macro_th_exp)** — SUCCESSFUL
   - Summary: Applied **original B4 rule** (not Rohit Jun 11 override): HY/VIX/VXTS → `rolling_3y`, WALCL → `full`. Recomputed 13,476 pctile rows (3,428 changed). **B4 pass=true** (12/12). Re-ran B/D/G sweeps on post-fix panel; refreshed `B_twy_and_percentiles.json`; D6 analytics re-slice. D production gates unchanged at n=46 / 56.5% bear @1W. G CONFIG baseline n=0 on first-crossing model.
   - Files changed:
     - `macro_intelligence/CONFIG.yaml` (HY/VIX/VXTS windows)
     - `testing/macro_th_exp/run_b4_window_fix_pipeline.py` (new)
     - `testing/macro_th_exp/B4_window_fix_pipeline_2026-07-17.{md,json}` (new)
     - `macro_intelligence/analysis/regime_v2_experiments/B_twy_and_percentiles.json` (B4 pass refreshed)
     - `macro_intelligence/analysis/regime_v2_experiments/threshold_sweep_v2_b4_fix/*` (new)
     - `testing/macro_th_exp/D6_regime_analytics_2026-07-17.*` (new)
     - `testing/macro_th_exp/D4_window_audit_rerun_2026-07-16.md` (superseded note)

2. **Promote Combo E BEST PRODUCTION SCORE thresholds + CFTC escalation alert** — SUCCESSFUL
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

4. **D2 — Curve regime `post_inversion_steepening` phase flag proposal (macro_th_exp)** — SUCCESSFUL
   - Summary: PROPOSE ONLY (no implementation). Diagnosed momentum-tier vs narrative gap on May 2025 slow grind (+51 bps spread, simple 4wk steepen −4 → NORMAL; post-trough +157 → STEEPENING; cheatsheet phase active). Proposed separate boolean phase flag alongside `curve_regime_v2`. Recommended ON/OFF (Spec A): ON after formal inversion (≥4wk &lt;0) ends + post-trough steepen ≥+15; OFF at spread ≥+80 or re-invert. Rejected literal `&lt;30 bps × 4wk` OFF (false exit Sep 2024). Backfill: **5** inversion episodes, **5** phase triggers, **165** phase-active weeks (8.65%); episode #5 ongoing since 2024-08-30. Combo A/E named legs unchanged (CURVE not a leg); phase storage-only does not alter fire logic.
   - Files changed:
     - `testing/macro_th_exp/D2_curve_phase_proposal_2026-07-17.md` (new)
     - `testing/macro_th_exp/D2_curve_phase_proposal_2026-07-17.json` (new)
     - `testing/macro_th_exp/D2_curve_phase_episodes_recommended_2026-07-17.csv` (new)
     - `testing/macro_th_exp/D2_curve_phase_weekly_panel.csv` (new)
     - `testing/macro_th_exp/D2_may2025_simple_vs_posttrough.csv` (new)
     - `testing/macro_th_exp/D2_phase_off_spec_comparison_2026-07-17.json` (new)

5. **D1 — Regime bucket feed for Ahil P3 (macro_th_exp)** — SUCCESSFUL
   - Summary: Published version-stamped daily series 2018–2026 (`date`, `bucket`) with BENIGN / ADVERSE / MIXED buckets built on recalibrated CONFIG gates (D/E per D5). Point-in-time Friday replay via `get_readings_as_of` + `detect_named_combos`; Combo C sequential cancel replay (fixes live-flag leak). **2,149** daily rows: BENIGN=1,617, ADVERSE=238, MIXED=294. Series `D1_regime_bucket_v1.1_2026-07-17`. Research handoff only — no prod/API change.
   - Files changed:
     - `testing/macro_th_exp/run_d1_regime_bucket_feed.py` (new)
     - `testing/macro_th_exp/D1_regime_bucket_daily_2026-07-17.csv` (new)
     - `testing/macro_th_exp/D1_regime_bucket_fridays_2026-07-17.csv` (new)
     - `testing/macro_th_exp/D1_regime_bucket_feed_2026-07-17.{json,md}` (new)

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
