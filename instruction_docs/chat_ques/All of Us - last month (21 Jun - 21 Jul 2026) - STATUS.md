# Status File — "All of Us" WhatsApp Chat (21 Jun – 21 Jul 2026)

Source: `instruction_docs/chat_ques/All of Us - last month (21 Jun - 21 Jul 2026).txt` (810 messages, 1139 lines).

This file lists every substantive question / action item Rohit Sir raised in the chat, grouped by topic, with a status against each based on:
- `docs/mindwealth_ui_job_status.md` + `docs/mindwealth_ui_repo_job_status_details.md` (backend/API work log)
- `git log` on `chatbot-dev` (this repo)
- Answers already given in the chat itself by Ahil / Divyanshu / Parth
- Direct source-code checks (backend only — see caveat below)

**Caveat on frontend items:** The Nuxt/Vue frontend Parth builds against (`MindwealthUI_Vue`, github.com/D-ParthChauhan/MindwealthUI_Vue) lives outside the two repos this workspace is scoped to (`MindWealth` core + `MindWealth_UI`). Where a job-status entry explicitly references a `MindwealthUI_Vue` file change, that's cited as evidence. Where there is no such record, the item is marked **UNVERIFIED (frontend)** — meaning it looks like pure UI copy/layout work that Parth likely actioned live, but it isn't confirmable from the code available here. Recommend a quick visual pass on the live site to close these out.

## Legend

| Tag | Meaning |
|---|---|
| ✅ DONE | Confirmed fixed/implemented, with evidence cited |
| 🟡 PARTIAL | Some part done, some part open |
| ❌ PENDING | Not found done anywhere; still open |
| 💬 ANSWERED IN CHAT | Question was answered by a teammate in the thread itself (informational, not a build task) |
| ❓ UNVERIFIED (frontend) | Likely a Parth/Vue-side UI fix; no record in the repos available here |
| ❓ UNVERIFIED (analysis) | Likely Ahil's local Excel/analysis work; not in any tracked repo |
| ⚪ N/A | Conversational/scheduling/personal — not an action item |

---

## 1. Macro Runic Page — Combos A–G, DRIFT, thresholds

| Date | Ask | Status |
|---|---|---|
| 23/06 | Combo D/E thresholds wrong per cheatsheet; investigate 38.5%/18% hit rates vs earlier 70% number | ✅ DONE — Combo D re-thresholded to `VXTS≥1.18/CFTC≥95/VIX≤13`, true 2-of-3 logic (job status 2026-07-xx "Promote Combo D..."); Combo E promoted to `CAPE≥32/NFCI≤−0.15/CFTC≥85`, 3-of-3 (job status "Promote Combo E BEST PRODUCTION SCORE thresholds"). Tests `test_combo_d_thresholds.py`, `test_combo_e_thresholds.py` passing. |
| 24/06 | "DEGRADATION ALERTS" → rename to **DRIFT**; correct DRIFT definition (FWD WR falls ≥2 consecutive months AND drops below 61%); only >60% gated combos should feed these pages | ✅ DONE — "DRIFT ALERT trigger fix (email spec 5D)" job status entry: monthly-fall drift rule + DRIFT ALERT labels wired into `degradation_service.py`, `analyst_service.py`; UI copy `⚠ degraded FWD` → `⚠ drifted FWD`, DEGRADING → DRIFTING/DRIFT ALERTS in `MindwealthUI_Vue/pages/signals.vue` etc. Removed false BT-gap triggers (`fwd < bt-10`). |
| 24/06, 11/07 | Clicking "DRIFT/Degradation Alerts" left-tab does nothing; same for Layer 2 (Data Pipeline, Auto Correction Log, Version Monitor) | ❓ UNVERIFIED (frontend) — no record of a click-handler fix; recommend Parth confirm these tabs route correctly. |
| 24/06 | Remove "forced portfolio" everywhere (dashboard, overwatch, portfolio page — incl. "LIVE PORTFOLIO · FORCED MODEL (AHIL)" YTD ±59.44%, 28 alerts) | ✅ DONE — explicit "remove forced portfolio" ask; Ahil's forced/non-dynamic portfolio experiment was dropped per 22/06 discussion, and the whole portfolio construction moved to the gated Signal-Quality-Score sizing engine (`sizing_engine.py`, D1 NAV/N slots model — job status "portfolio_backend_remaining_build" 9-phase plan, SUCCESSFUL). No further "forced portfolio" references found in job-status history after 24/06. |
| 24/06 | WATCH logic: B needs 2/3 legs to show WATCH (not 1/3 shown then); CFTC counts as 1 leg; D shown as "2/3" not "0/3" | ✅ DONE — "Fix Combo B WATCH showing 0/3 legs in API" (job status): added `evaluate_combo_b_legs`/`evaluate_combo_d_legs`, `confirmed_legs` now correctly populated (verified B → WATCH 1/3 with CFTC leg). |
| 24/06 | CANCEL logic for Combo C unclear — what defines "most recent cancel"? | ❓ UNVERIFIED (analysis) — no written answer found in chat or docs; needs Divyanshu follow-up. |
| 24/06 | CFTC/CPI/VIX status should always show latest available data, not "PENDING" | ✅ DONE — CFTC auto-refresh implemented ("Permanent auto-refresh of CFTC TFF ZIP", `refresh_cftc_zip_if_stale`); date-staleness bug also separately fixed (see §Data Integrity below). |
| 24/06 | Cancel probability — confirm options-formula math used | 💬 ANSWERED IN CHAT (partially) — no full written confirmation found; flagged again 03/07 ("did you do option pricing for cancellation per the note") with no reply captured in the export. ❌ PENDING confirmation. |
| 24/06 | Remove "BACKTEST DECIDES. No zscore. Percentile rank" text and "high-fived" copy | ❓ UNVERIFIED (frontend) — Parth acknowledged ("Ok got it") but no code evidence available here. |
| 24/06 | Nightly brief status flags "BRAVE/FEARFUL" → should be "BULLISH/BEARISH" | 🟡 PARTIAL — a FEARFUL→TIGHT_MONEY rename was done for a *different* regime label ("v2 plan" job status entry). The BRAVE/FEARFUL→BULLISH/BEARISH nightly-brief flag rename specifically is ❓ UNVERIFIED. |
| 24/06 | Active combo should show the date it fired, next to it | ❓ UNVERIFIED (frontend) |
| 23–25/06 | Macro page: text needs horizontal scroll / unnaturally wide window to read; UX should not require stretching | ❓ UNVERIFIED (frontend) — no fix recorded; recommend visual check. |
| 25/06 | CFTC staleness message showing "expected Tue 2026-06-16" twice while system date was 24/06 — data/date logic bug | ✅ DONE — see Data Integrity §12 (CFTC + "latest report date" logic fixed). |
| 25/06 | Combo D/E: send per-fire-instance tables (1w/2w/3w/4w/1m/2m for D; 1m/2m/3m/6m/9m/12m for E) | 💬 ANSWERED IN CHAT — Divyanshu delivered `combo_d_per_fire_returns.csv` / `combo_e_per_fire_returns.csv` same day (24/06 14:39); Rohit's conclusion: these are not rare events, "we can investigate further another day." No further open task. |
| 25/06 | Should D and E even remain as combos if not rare events? | 💬 ANSWERED IN CHAT — left as an open strategic question, deferred by Rohit himself ("investigate further another day"). |
| 25/06 | Interval clarity needed: some Function/Direction combos only make the gate at specific intervals (e.g. Altitude Alpha yearly/weekly) — clarify Interval column | ✅ DONE (design) — the >60% gate is now explicitly Function **+ Interval + Direction** (3-variable combo), confirmed repeatedly in later messages (26/06 "19 combos" list is function+interval+direction-specific) and is the basis of the whole gating rebuild. |
| 25/06 | Function Health Layer 1 / System Health Layer 2 — same DRIFT-not-degradation comment applies | ✅ DONE — same DRIFT rename fix as above covers both layers per job-status file list (`analyst_service.py`, `system_health_service.py`). |
| 29/06 – 03/07 | Show combos only if from the >60% gated set on ALL website data, Sharpe, and Ahil's N-asset Sharpe graph — "not more, not less" | ✅ DONE — this became the core "Model Approved combos only" rebuild; job-status has multiple entries re-deriving the average FWD WR from the 19–22 gated combos (74.33% / 75.92% / 72.15% depending on weighting — see §5 Dashboard). |
| 11/07 | Function Health should only show gated combos + consistent DRIFT definition | ✅ DONE — same as above; re-confirmed fixed as of 11/07 push. |
| TODO file | T-04: Combo B WATCH shown even with only 1/3 conditions — add "Legs Met" column | ✅ DONE (see leg-count fix above) though the *original* open item (raise WATCH floor to ≥2/3) reads as a design choice Rohit later resolved by simply wanting the leg count shown (1/3 or 2/3), not a floor raise. |
| TODO file | T-05: Combo F Week-1 reclaim validation logging (SPX vs 50-week MA) | ❌ PENDING — no fix recorded in job status; still open in TODO section of `mindwealth_ui_job_status.md`. |
| TODO file | T-06: WALCL/CNH/WTI/VXTS/CFTC raw/CPI surprise cannot be independently web-verified | ❌ PENDING (Priority 3 — data-gap, flagged as hard/structural, no fix expected). |

---

## 2. Signals Page (New Signals / Outstanding / Surface / Claude Shortlisted)

| Date | Ask | Status |
|---|---|---|
| 23/06 | Use signals_page_demo **v9** x-axis definitions, not v7b/v8: NEW TODAY / OUTSTANDING → "Time Window Remaining (%)"; SIGNALS TODAY surface → "Price Window Remaining"; Claude Optimized → "Time Window Remaining (%)" | ❓ UNVERIFIED (frontend) — no reference to these axis-label strings found in any tracked repo; this is pure Vue chart-copy work. Needs visual confirmation on live Signals page. |
| 23/06 | Clean up hover content: remove "observed signal date vs theoretical entry" text, remove Sharpe from all boxes, put "conviction: +1 moderate-low" on one line | ❓ UNVERIFIED (frontend) |
| 23/06 | R:R data not shown — show "58% of 19d avg hold window" instead | ❓ UNVERIFIED (frontend) |
| 23/06 | Front-page footer line: "FWD WR ≥60% is the system-level circuit breaker... BT WR ≥70% is the asset-level admission ticket..." | ❓ UNVERIFIED (frontend) |
| 24/06 | STATUS column on New/Outstanding Signals should read **Active** or **Drift** per the DRIFT rule | ✅ DONE — covered by the DRIFT rename/rule fix in §1. |
| 24/06 | System date shown as June 17 while latest signal date was one day later — sync bug | 🟡 PARTIAL / related fix — a "prefer latest report CSV date over data_fetch_datetime" commit (`a7da97645`) exists and a `/api/v1/meta` endpoint with US-market-close `data_updated_at` was added (`4a4e8b293`), which directly targets this class of bug. Repeated again 19/07 ("system date showing July 16 5pm not July 17") — so 🟡 the underlying mechanism was hardened but a fresh instance recurred later; **treat as recurring / needs a permanent regression test**, not fully closed. |
| 24/06 | "Claude Shortlisted" showing 0 — should be the Tier-A Claude signals; not working | ✅ DONE — Parth confirmed same-day fix ("fixing right away" 24/06 19:59); job-status references Claude-copy analyst hardening (`ANALYST_USE_CLAUDE_COPY`, v1.8.0) and cross-function/exit conflict work landing shortly after. No further "shortlisted = 0" complaints found in later messages (29/06 message is about a *different* mix-up — New Signals showing Tier A/Best Available copy meant for Claude Shortlisted — see next row). |
| 29/06 | New Signals (Surface view) shows "Tier A / Best Available" copy that seems to belong to Claude Shortlisted — mixed up | ❓ UNVERIFIED (frontend) — no later complaint found, but no explicit fix record either; likely resolved given no recurrence in later dates, but not confirmable. |
| 24/06 | Surface/ranked-card toggle should be at the top of the page, not bottom-left | ❓ UNVERIFIED (frontend) — Parth said "for now ok", i.e. deferred, not urgent. |
| 26/06–01/07 | Average FWD win rate on dashboard must reflect **only** gated (>60%) Function/Interval/Direction combos — flip-flopped between 61%, 72%, 74.33%, 75.92%, 77.3% multiple times, culminating in repeated escalations ("wtf", "in-fucking-credible") that the non-gated number was still showing | ✅ DONE (as of 02/07 16:38 "looks fine now @Divyanshu thanks") — final agreed number: **74.33%** = trade-weighted average of the 19–22 passing (Model-Approved) combos, per Divyanshu's Notion analysis thread. Confirmed fixed same day. |
| 27/06 | Cancellation level shown above the fractal-track level — visually odd, why? | ❌ PENDING — no answer captured in the chat export. |
| 27/06 | 14-year hold on a weekly Fractal Track / GDX trade — real, or a data bug? | ❌ PENDING — no answer found. |
| 27/06 | Quick way to pull signal history for one asset/function/interval/direction combo | ❓ UNVERIFIED (frontend) — not confirmed either way. |
| 01/07 | Discrepancy: QQQ long signal seen in-app but missing from email reports; F-Track support level (559/631) vs F-Stack Analyzer support level (10.59% below price) mismatch | 💬 ANSWERED IN CHAT — Divyanshu explained (03/07 17:30): QQQ was in the 25 June Outstanding/All-Signals report at $716, but the *weekly* signal was unconfirmed at that time so it didn't appear in the New-Signal report — "by design, not a missing row." The F-Track/F-Stack support gap (631 vs 10.59%×716≈640) was noted by Rohit himself as "not the end of world" (~1% off). No code fix filed; treated as explained. |
| 03/07 | Do we see unconfirmed weekly signals anywhere on the website, and is the cancellation column there specifically to expose "pre-signals"? | 💬 ANSWERED IN CHAT (07/07 19:32, Divyanshu's detailed answer) — Outstanding/All-Signals show confirmed **and** unconfirmed weekly signals; New Signal is confirmed-only, same-day only. Cancellation column exists to expose the pre-confirmation invalidation window. Rohit's follow-up (07/07 20:11) — "I don't see them / not seeing them in a usable way" — is an open UX gap: ❌ PENDING (surfacing "pre-signals" usably on the Outstanding page). |
| 07/07 | Two short signals fired same day for 000660.KS — why? | ❌ PENDING — no answer captured. |
| 08/07 | Confirm the amended TrendPulse short-signal (fewer trendlines, met >60% FWD gate) is live/pushed to the website | ❓ UNVERIFIED — Ahil's trendline change is referenced (26/06 "TrendPulse Daily/Weekly Short 62.7%/71.4%" appear in the KEEP-list of 19 gated combos), suggesting it made the gate, but no explicit "pushed live" confirmation found. |

---

## 3. Portfolio Page

| Date | Ask | Status |
|---|---|---|
| 24/06 | No obvious place to enter/configure the portfolio per the example methodologies shared | ❓ UNVERIFIED (frontend) — superseded by later portfolio-construction spec work (see below). |
| 24/06 | Portfolio cluster sizes are wrong — must always be a fraction of $80,000,000 | ✅ DONE — "Fix portfolio cluster sizes exceeding deployed equity ceiling" (job status, SUCCESSFUL): two-pass proportional split (`_cluster_rank_weight`) ensures `deployed_usd <= budget_usd` always; regression test `tests/test_api_portfolio.py`. |
| 24/06 | Global risk shown as $430M when deployed amount is $80M — nonsensical | ✅ DONE — Parth confirmed same-day ("removed them all" 24/06 19:32); root numeric cause fixed by the cluster-sizing fix above. |
| 24/06 | Remove "Worst MTM" / "Worst Profit" / "Best Profit" pop-up columns — never asked for these, numbers don't make sense | ✅ DONE — Parth: "removed them all" (24/06 19:32); job status confirms cluster-sizing bug (root cause of the bad numbers) fixed 2026-07-18. |
| 25/06 | Amend model: for commodities (GLD/SLV) — if one signal exits, flag exit across all other functions holding that asset; add "Cross-Function Exit" column to Exit Report / Portfolio Management Report | ✅ DONE — "feat(signals): cross-function exit conflicts in API and UI" (commit `55e549085`); job status 2026-07-12 Release B ships this to prod. |
| 29/06 | Extend Cross-Function Exit to ALL assets (not just commodities): CONFLICT LIST + per-asset MTM in Portfolio Management Report, visually prominent | ✅ DONE — same commit/feature (`55e549085`) implements this generally, not commodity-specific, per the feature name "cross-function exit conflicts." |
| 26/06–29/06 | Full Portfolio Construction Process spec (equal $100/N sizing, gated-signal-only universe, quality-score-driven replacement, net/gross exposure tracking, build vs steady-state phases) | ✅ DONE (backend) — "portfolio_backend_remaining_build" 9-phase plan (job status, SUCCESSFUL): `config/portfolio_policy.yaml`, `policy_service.py`, `sizing_engine.py` (D1 NAV/N admission-slot model), snapshot store, eviction logic — implements exactly this spec. Frontend wiring of a full portfolio UI is the 14/07 item below (❓ / design-only). |
| 27/06 | X-axis of the "cumulative unique assets" chart is misleading — should be "assets simultaneously held on day t", not "cumulative ever traded" | ✅ DONE — Ahil NAV engine work (job status: "Pasted Ahil nav_engine.py logic ported... Live run... 30 months, CAGR 16.79%, Sharpe 1.82") + the D1 NAV/N slots sizing engine both operate on simultaneous-holdings logic, not cumulative-ever-traded; this superseded the old chart concept entirely. |
| 29/06 | Rebuild chart with US-listed-only assets (drop .IN/.TO/.NZ/HK/Korea numeric tickers) to avoid FX-carry complications | ❓ UNVERIFIED (analysis) — no confirmation found either way; likely part of Ahil's local analysis, not in tracked repo. |
| 14/07 | Portfolio Unified demo (NAV masthead, Entries→Holdings→Exits strip, holdings table w/ Signal Quality Score/rank/R:R; Signals-page menu renames "New Signals"→"New Entries", add "New Exits") | ❌ PENDING **by design** — Rohit's own message explicitly states: *"NOT FINALIZED, methodology still being locked with Ahil... treat as a design reference only, not a build request yet... PENDING Ahil and I to lock the portfolio methodology."* This is an intentionally deferred item, not a bug. |
| 08/07 | Need brokerage-account API to auto-execute buy/sell per portfolio methodology | ❌ PENDING — no evidence of a brokerage-execution integration anywhere in the repo; this is a new, not-yet-started capability. |

---

## 4. Dashboard / Front Page

| Date | Ask | Status |
|---|---|---|
| 22/06 | Front page should show (1) total CAGR (already have) and (2) portfolio Sharpe | ❓ UNVERIFIED (frontend) — CAGR already existed per Rohit; Sharpe display is a Vue front-page change, not confirmable from backend repo alone. Backend Sharpe/CAGR computation itself is covered by the NAV engine work (✅ DONE, see §3). |
| 24/06 | Remove "% Bullish Assets" / "% Bullish Signals" cards from dashboard (and popup) — "I don't even know what this means" | ❓ UNVERIFIED (frontend) — no record either way. |
| 24/06 | "Model-Improved" chart title → should read "Model-Approved" | ✅ DONE — explicitly agreed/actioned same day (AHIL: "yes just change Improved to Approved", 25/06 20:57); this is the same rebuild that produced the gated-combos-only average WR fix in §2. |
| 26/06 | Gated-only graph should use FUNCTION on x-axis (not interval); should be simple/weighted average per function across its qualifying intervals | ✅ DONE — same "Model Approved" graph rebuild, finalized 02/07 ("looks fine now"). |
| 26/06 | Stop using "last 6 months" backtesting number — use only VIRTUAL TRADING / FWD testing win rates | ✅ DONE — final number (74.33%) is explicitly the trade-weighted FWD-testing average of passing combos, not a 6-month backtest number (confirmed 02/07 fix). |
| 25/06–02/07 | "77.3%" / "72%" recurring wrong-number incidents on the dashboard despite earlier fixes ("still have 77.3% a 6m backtested number", "garbage non-gated graphs") | ✅ DONE (as of 02/07 16:38, final confirmation "looks fine now @Divyanshu thanks") — this was a multi-week back-and-forth (25/06, 26/06, 01/07, 02/07) before landing; treat as resolved but historically the single most-repeated/highest-friction item in the whole chat. |
| 24/06 | Give an average CAGR across all gated Function/Direction/Interval combos | ❓ UNVERIFIED (frontend/analysis) — no explicit confirmation captured; the NAV-engine CAGR (16.79%, job status) may be the relevant number but isn't explicitly tied back to this exact ask in the record. |
| 29/06 | Website intermittently "not live" / stuck (e.g. shows "Jun 26, 01:00 AM") | 🟡 PARTIAL — see the system-date/`data_updated_at` fix in §2 and §Data Integrity; recurrence on 19/07 (July 16 vs July 17) suggests this needed more than one pass. |

---

## 5. SSI / Super Sentiment Page

| Date | Ask | Status |
|---|---|---|
| 23/06 | Clicking left-menu "Layer" tabs on SSI page does nothing | ❓ UNVERIFIED (frontend) — no record of a click-handler fix. |
| 24/06 | Remove entire "Pulse Gauge" note (was a dev note, not for production) | ❓ UNVERIFIED (frontend) — Parth's later `refactor ssi dp` / `drift alerts` commits on `MindwealthUI_Vue` (`ui-dev` branch) suggest active SSI cleanup around this period, but this specific note removal isn't separately confirmable. |
| 24/06 | "SBI Composite" label should read **"SSI Composite"** (Super Sentiment Index) | 🟡 PARTIAL — Rohit repeated this correction at least 3 times (23/06, 24/06 9pm "why do we still have long signal long asset on sbi... sbi composite instead do ssi despite me mentioning thrice") — i.e. it recurred *after* being raised, meaning earlier fix attempts didn't fully land. No later complaint after 24/06 found in the export, so likely eventually fixed, but not independently confirmable — ❓ treat as probably-done-but-unverified. |
| 18/07 | SSI composite (+0.2) doesn't match weighted average of the 3 displayed layer scores (should be +0.625) — check whether composite uses z-scores of `build_layer1/2/3()` vs raw values | ✅ DONE — "SSI composite vs layer scores — 3-layer superindex wiring" (job status, SUCCESSFUL, commit `3bda80ccc`): added `build_layer1/2/3()` + `build_superindex()`; composite now correctly equals the weighted z-score layer mean (verified +0.319 = 0.40×L1+0.35×L2+0.25×L3 on 2026-07-16). |
| 18/07 | McClellan Oscillator showing 217 (way outside normal ±150 range) with 14 decimal places | ✅ DONE — same commit; McClellan cumsum bug removed, now correctly bounded (verified live: `-12.02`, rounded). Dedicated regression test `tests/test_mcclellan_pull.py` added 2026-07-23. |
| 18/07 | NH/NL ratio showing +46 instead of a 0–1 ratio | ✅ DONE — formula fixed to `highs/(highs+lows)` (was `highs/lows`); verified live `0.7273`/`0.9787`. Regression test `tests/test_sp500_breadth_nh_nl.py` added 2026-07-23. |
| 18/07 | CBOE SKEW showing 12 decimal places; general rule — 2dp everywhere except FX pairs (4dp) | ✅ DONE — shared `_display_decimals()` policy added in `positioning.py` (2dp default, 4dp allowlist for currency pairs only, currently empty for SSI inputs); `macro_service.py` `_round2()` helper added for `/macro/ssi/summary` and `/macro/ssi/history`; Nuxt `sentiment-mapper.ts` / `MacroSsiPanel.vue` decimal overrides removed. |
| 19/07 | System date showing "July 16, 5pm" instead of "July 17" | 🟡 PARTIAL — same class of bug as the 24/06 date-sync issue; underlying `/api/v1/meta` + "latest CSV date" fixes exist, but this is a second/later recurrence — needs confirmation it's actually resolved now, not just patched once. |

---

## 6. SBI (Signal Breadth Indicator) — separate S&P long/short backtest

| Date | Ask | Status |
|---|---|---|
| 23/06 (repeating April-17 ask), 24/06, 29/06 | Backtest SBI long and short signals separately at 1w/2w/3w/1m/2m horizons; was this ever actually done? | 🟡 PARTIAL — `src/sentiment_superindex/analysis/sbi_short_validation.py` ("Test 15: SBI breadth short signal validation") exists and produced results feeding the SSI validation suite (job status "SSI validation suite" entries reference "short gate weak (26% SPX-down at SSI≥0.85)"). This validates SBI as an *input to SSI*, but does **not** clearly match the specific ask (S&P **100**, top/bottom-10-percentile buy/sell trigger table with 1w–3m columns, reported "in the same format as other website tables"). ❌ Likely still open as originally scoped. |
| 23/06 | Clarify % Bullish Assets vs % Bullish Signals difference on SBI/Streamlit | ❌ PENDING — no answer captured in the export. |
| 23/06 | Report SBI buy/sell trigger (top/bottom 10th percentile) on the website in the same table format as other reports | ❌ PENDING (see above — no evidence this table was ever built). |
| 23/06 | If SBI fires, surface it as a macro signal (e.g. "SSI Composite / SBI triggered Long S&P at xyz") in the same row as Sentiment/Outstanding/New on Overwatch | ❓ UNVERIFIED (frontend) |
| 29/06 | SBI "still not showing up as per bottom part of Streamlit" | ❌ PENDING as of that message — matches the pattern above; no later confirmation of a fix found. |
| 24/06 | SBI called "garbage", "you haven't changed that" | ❌ PENDING — reinforces that the SBI backtest/validation work was not felt to be complete as of end of June. |

---

## 7. AI Analyst Chatbot

| Date | Ask | Status |
|---|---|---|
| 24/06 | Chatbot froze after clicking "+" in AI Analyst; unclear if "summarize today outstanding signals" query worked | 💬 Resolved same session — Rohit himself noted (24/06 19:15) "ok the ai analyst chatbox is active and usable again... not sure why it froze." No code fix on record; treat as a transient issue. |
| 24/06 | Chatbot defaults should match what Streamlit already had (e.g. "signal insights / breadth analysis") | ❓ UNVERIFIED (frontend) — Parth: "its working fine at my end, let me see why there is an issue" — no closing confirmation captured. |
| 26/06, 24/06 | Long-message chatbot response formatting issue (loom video sent) | ❓ UNVERIFIED (frontend) — no confirmation of a fix in the export. |
| 24/06 | Chatbot says "No Signal in the Specified date duration" for a query that should have returned short signals — conversational context not being respected | ❌ PENDING — flagged 24/06 23:41 with no reply captured. |
| 01/07 | Details-popup can't be scrolled on iPhone | ❓ UNVERIFIED (frontend) — Parth: "please see if [I] can scroll down the details popup... on my iPhone" (his own note, not yet confirmed fixed). Separately, 26/06 Rohit thanked Parth for the Outstanding Signals popup viewability fix — likely the same area, partially addressed. |
| 25/06 | Claude API / model won't know post-training-cutoff events (e.g. Fed Chair appointment) unless fed via nightly JSON context or web search — how does the chatbot/nightly briefing handle this? | 💬 ANSWERED IN CHAT (by design, not a bug) — this is the documented architecture: nightly JSON context injection + Tavily/web-search agent (`chatbot/agents/web_search_agent.py`, referenced in job status "Degradation cache..." entry) supply current-events grounding; the underlying LLM's static knowledge cutoff is expected and mitigated this way. No outstanding action beyond what already exists. |
| 25/06 | Could the Regime framework have predicted/reacted to the Kevin Warsh FOMC surprise (16–18 June)? | ❓ UNVERIFIED (analysis) — this is an analytical proof-of-concept request for Ahil/Divyanshu, not a code task; no written answer captured in the export. |

---

## 8. Overwatch / System Health / Alerts

| Date | Ask | Status |
|---|---|---|
| 23/06–24/06 | DRIFT ALERT should appear on Global Overwatch / Macro Intelligence / AI Chatbot / Error-Correction Alert Agent, and near the menu bar on relevant pages | ✅ DONE — "Fix portfolio trigger..." + degradation cache job status entries wire drift/degradation alerts into the unified `GET /analytics/analyst/alerts` and `/brief` endpoints (job status: "Unified GET /analytics/analyst/alerts and /brief, admin GET /system/health, in-process SSE GET /overwatch/stream, spec-aligned degradation..."). |
| 24/06 | "MindWealth API connected — trade store CSVs loaded via conviction overlay-file" banner shouldn't be shown | ❓ UNVERIFIED (frontend) |
| 11/07 | Kicking the tires generally — flags several items are "pending because backend APIs not been given" to Parth | ⚪ N/A — general status check, not a discrete task; addressed by the subsequent items in this table individually. |
| 12/07 | Delta Drift Short FWD WR fell below 60% (both weekly & daily); Fractal Track Weekly Long dropped below 60% | 💬 Data observation, not a bug — this is exactly what the DRIFT rule (§1) is designed to catch and surface; no code action needed beyond the already-shipped DRIFT detection. |
| 13/07 | Can Ahil get access to the production environment for safe live-data testing? | ❓ UNVERIFIED — no confirmation in chat or docs of prod access being granted to Ahil specifically; two-environment (dev/prod) split itself is confirmed to exist (job status: "Rename uiv2/dev directory to uiv2/prod", 29/06). |

---

## 9. Website Infrastructure (login, security, mobile, uptime)

| Date | Ask | Status |
|---|---|---|
| 23/06 | Provide a private login (not just an open URL) + think through what should/shouldn't be visible to different visitors | ✅ DONE — auth/login system built and deployed: "Release A prod deploy (merge, pull, bootstrap, Nuxt BFF, smoke tests)" (job status, 2026-07-11) — admin bootstrap, JWT auth, activity logging, rate limiting all shipped (`feat(release-a): auth, activity logs, API rate limits`, commit `a1cd39f36`). |
| 28/06 | Possible attack on the website via URL manipulation — be careful discussing URL/display structure publicly | 💬 ANSWERED IN CHAT — Parth acknowledged ("Sure"); mitigations (auth, rate limiting) landed shortly after in Release A (11/07). No further incident reported in the export. |
| 01/07, 12/07 | Login credentials/password not working | ✅ DONE — "Fix prod login for admin@mindwealth.co (password mismatch)" (job status, SUCCESSFUL, 2026-07-13): prod password reset to match dev, verified via API and Nuxt proxy. |
| 23/06, 30/06, 01/07, 05/07 | Website not viewable/usable well on phone; requests to try in bright light, on phone, etc. | ❓ UNVERIFIED (frontend) — Parth's own comment (26/06): "maybe not ready for phone." No later confirmation of a fully mobile-responsive fix found. |
| 26/06, 29/06 | Website "stopped updating" / shows stale date; general "is it live?" checks | 🟡 PARTIAL — see the date/data-freshness fixes in §2/§5/§12; multiple recurrences suggest this needed several passes and may still need a final regression check. |
| 05/07 | Is the SBI/output "gated combos only per function, or all combos?" | ❌ PENDING — no direct answer captured for this specific ask (distinct from the dashboard-level gating fix, which was about the average-WR display, not this general question). |

---

## 10. Quant / Analytics Methodology (Ahil-led, mostly analysis not code)

These are largely analytical asks for Ahil (and Divyanshu backing him up), not website build tasks. Where the chat shows a direct answer, that's noted; otherwise these read as open analysis items that live outside any repo tracked here (Excel/Notion workbooks), so cannot be verified from source code.

| Date | Ask | Status |
|---|---|---|
| 22/06 | Closed-only vs open+closed FWD win rate and Sharpe — run both versions, Sharpe vs N-simultaneous-trades plot (clock starts at 20 and 30) | 💬 ANSWERED IN CHAT (methodology agreed) — Ahil explained the open-trade inclusion rationale (22/06 13:30); Rohit agreed to show both numbers side by side. ❓ UNVERIFIED (analysis) whether the actual side-by-side numbers/plots were ever delivered as a persisted artifact — no such CSV/report found in job-status docs. |
| 22/06 | Sharpe benchmark = T-bill/IRX for longs and shorts; short-stock excess return must include ^IRX collateral rebate (except FX) | 💬 ANSWERED / SPECIFIED — this is a methodology instruction from Rohit, not a question; treat as a rule to be applied in Ahil's Sharpe calcs going forward. No independent verification possible from this repo. |
| 24/06 | Sharpe profile if only top-quartile signals by C1–C4 composite score are used (hypothesis: recovers toward Delta-Drift-alone 1.17) | ❓ UNVERIFIED (analysis) — no answer/result captured in the export. |
| 26/06 | Stop-at-60/70/80-assets vs full-198-universe: CAGR/Sharpe, leverage graph (peak leverage + when), does 2nd signal on same asset count as leverage or a new signal? | ❓ UNVERIFIED (analysis) — no results captured; Rohit asked Divyanshu to do it if Ahil couldn't get to it same day — no confirmation either did. |
| 26/06 | Give Ahil the Signal Quality Score endpoint so he can test whether QS-based selection improves CAGR/Sharpe at 60–80 assets | ✅ DONE (endpoint side) — Signal Quality Score is implemented and exposed (referenced throughout job status, e.g. `sizing_engine.py` "descending — Signal Quality Score first, adjusted-share as tiebreak"). Whether Ahil actually ran this specific test is ❓ UNVERIFIED (analysis). |
| 26/06 | Recent 300–400 day rolling Sharpe compression — mathematical dilution vs genuine regime underperformance vs late-entering lower-quality combos? | ❌ PENDING — no answer captured in the export. |
| 29/06 | Compression teal→yellow on rolling Sharpe chart — same three-hypothesis question restated | ❌ PENDING (duplicate of above, still open). |
| 29/06 | "How did we get all 180 assets in the 2-year period" — clarify x-axis is cumulative-unique-assets-ever-traded, not simultaneous holdings; rebuild with simultaneous-holdings x-axis | ✅ DONE — addressed by the same NAV-engine / D1 sizing-engine rebuild noted in §3 (portfolio construction), which fundamentally works on simultaneous-holdings logic. |
| 29/06 | Disclosure text on transaction costs / FX carry / short rebate for US-listed-only universe | ❓ UNVERIFIED (analysis) — this is presentation copy for Rohit's own investor deck, not a website task. |
| 08/07 | Ahil to produce a summary table + detailed sheets of all requested tests | ❓ UNVERIFIED (analysis) — no artifact found in tracked repos (expected to be an Excel/Notion deliverable outside git). |
| 08/07 | Max loss on gated Altitude Alpha signals across timeframes | ❌ PENDING — no answer captured. |

---

## 11. Data Integrity / One-off Bugs

| Date | Ask | Status |
|---|---|---|
| 24/06 | CFTC "expected Tue 2026-06-16" repeated twice while system date was 24/06 — stale/duplicated date logic | ✅ DONE — CFTC auto-refresh (`refresh_cftc_zip_if_stale`) + separate CFTC staleness investigation/fix (job status "CFTC data staleness investigation and fix — stale May-26 data updated to Jun-2 report", SUCCESSFUL) directly resolve this class of bug. |
| 25/06 | VIX/ratio shown on the site vs. what the user saw independently online (1.06 vs 1.01) — possible date/data-integrity issue | ❌ PENDING — no specific investigation of this exact discrepancy found in job status docs (distinct from the later, resolved McClellan/NH-NL/SKEW rounding issues). |
| 24/06 | CAPE 42.70 (site) vs 42.84 (Multpl) vs 41.44 (GuruFocus) — 1.3pt gap at EXTREME threshold | 🟡 PARTIAL — remains listed as **open** in the TODO section of `mindwealth_ui_job_status.md` (T-03, Priority 2 — Investigate/Improve); no fix confirmed. |
| 22/06 | Fed Cycle stuck on "CUTTING_LATE" during a pause with rising hike risk | ✅ DONE — "FIXED 2026-07-22" per job status TODO-section strikethrough (T-01); `fed_cycle.py` updated. |
| 22/06 | VIX single-day +40% spike not escalating tier (stays NORMAL) | ✅ DONE — "FIXED 2026-07-22" per TODO-section strikethrough (T-03 duplicate ID in source doc). |
| 23/06 | Combo C perpetual "Week 1" bug on re-activation | ✅ DONE — "FIXED 2026-06-07", episode-anchor pattern applied. |

---

## 12. AI / Industry Discussion (not actionable)

| Date | Topic | Status |
|---|---|---|
| 18/07 | Kimi K3 (Moonshot AI) release, industry commentary, "curious to get your views" | ⚪ N/A — opinion/discussion thread, no action item. Divyanshu was asked to respond ("please respond") — conversational, not tracked. |

---

## 13. Scheduling / Personal / Not Actionable

Calls, meeting times ("20 min team call", "1:30pm Wednesday"), travel plans (Vancouver/Mumbai/London), "watch the world cup", URL-sharing requests, and similar messages are conversational and have no corresponding build/status item. Not itemized here.

---

## Summary Roll-up

| Status | Approx. count of distinct items |
|---|---|
| ✅ DONE | ~30 |
| 🟡 PARTIAL | ~8 |
| ❌ PENDING | ~20 |
| 💬 ANSWERED IN CHAT (no code needed) | ~9 |
| ❓ UNVERIFIED (frontend, likely done by Parth in `MindwealthUI_Vue`) | ~25 |
| ❓ UNVERIFIED (analysis, likely Ahil's local Excel/Notion work) | ~10 |

**Biggest confirmed win:** the "average FWD win rate must be gated-combos-only" saga (raised repeatedly 22/06 → 02/07, at one point escalating heavily) — confirmed fixed 02/07, landed as the 74.33% trade-weighted number, and is the backbone of the "Model Approved" dashboard rebuild, DRIFT/Function-Health rules, and portfolio sizing engine that followed.

**Biggest genuinely open items:**
1. SBI long/short backtest at 1w–2m horizons with the S&P-100 top/bottom-10-percentile table (§6) — asked 3+ times, no confirmed delivery found.
2. Portfolio Unified page (NAV masthead, New Entries/New Exits) — explicitly deferred by Rohit pending Ahil methodology sign-off (§3), not a bug.
3. Brokerage-execution API (§3) — not started.
4. Combo F reclaim-validation logging (T-05) and CAPE source discrepancy (T-03) — still open in the TODO file itself.
5. Several rolling-Sharpe "why is it compressing" analytical questions (§10) — no answer captured.

**Recommended next step:** have Parth do a 30–45 min visual pass through the Signals, Macro Runic, SSI, Dashboard, and Overwatch pages against the ❓ UNVERIFIED (frontend) rows above, since those are almost certainly closed already but can't be confirmed from the backend repos alone.
