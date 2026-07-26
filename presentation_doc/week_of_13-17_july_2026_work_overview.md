# Week of 13–17 July 2026 — Work Overview

**Author:** Divyanshu  
**Purpose:** Presentation-ready summary of backend work for the week of 13–17 July 2026  
**Sources:**
- [`instruction_docs/ai_analyst/ai_analyst_implementation_log.md`](../instruction_docs/ai_analyst/ai_analyst_implementation_log.md)
- [`instruction_docs/portfolio_page/portfolio_implementation_log.md`](../instruction_docs/portfolio_page/portfolio_implementation_log.md)
- [`docs/mindwealth_ui_job_status.md`](../docs/mindwealth_ui_job_status.md) (macro/regime entries for 13–17 July)

**Repo:** `/home/ubuntu/uiv2/git/MindWealth_UI` (branch `chatbot-dev`)

---

## Simple Explanation

*Written in plain language for anyone new to MindWealth or this project. This section describes **what I did** during the week of 13–17 July 2026 — the three big workstreams, why each mattered, and what was still left open.*

### What this week was about (the big picture)

MindWealth is building two major product surfaces at the same time: a **Portfolio page** (holdings, sizing, risk, entries/exits) and an **AI Analyst panel** called **Overwatch** (a side drawer that watches for problems and can chat with the user). Rohit also sent updated specs mid-week that locked portfolio rules (axioms, endpoints, sizing method) and pushed macro/regime CONFIG work forward.

**This document is my week-in-review for presentation.** It covers backend work across three parallel tracks:

1. **Portfolio APIs** — so the frontend never has to compute sizes, weights, or P&amp;L itself.
2. **AI Analyst / Overwatch backend** — so warnings from strategies, macro, and system health live in one feed with live push and context-aware chat.
3. **Macro / regime** — fixing percentile windows, promoting Combo D &amp; E to production, and handing Ahil a daily regime-bucket series for his replay tests.

I did **not** build the Nuxt UI for either surface (that is Parth). I also did **not** ship everything in the portfolio spec — several pieces are blocked on Rohit decisions and Ahil’s four-book NAV replay.

---

### Why this week mattered

Before this week, two frontend developers were stuck:

- **Parth (Portfolio)** — The v5 mock showed the right screens, but only **4 of 9** required API endpoints existed. No holdings table, no entries/exits feeds, no cross-function conflict report in the HANDOFF shape.
- **Parth (Overwatch)** — Warnings were scattered: strategy health buried in ~2,000 CSV files, macro alerts on different routes, no pipeline health in the product. The panel spec needed a unified backend.

At the same time, **macro CONFIG was wrong**: B4 window audit failed (HY/VIX/VXTS using the wrong lookback), and Combo D/E thresholds needed promotion after recalibration. Ahil needed a regime-bucket daily series for his P3 replay.

This week closed those gaps on the backend side — or documented exactly why something could not ship yet.

---

### Track 1 — Portfolio page backend

**What I built:** A pipeline layer so the Portfolio page can bind to real `trade_store` data without frontend math.

| What the UI needs | What I shipped |
|-------------------|----------------|
| Open positions with score, size, siblings | `GET /portfolio/holdings` |
| New signals to admit | `GET /signals/entries` |
| Exit candidates | `GET /signals/exits` |
| Cross-function conflicts | `GET /signals/reports/portfolio-risk/latest` |
| Sizing (July spec name) | `GET /portfolio/sizing` (alias for existing sizer) |

**How holdings work:** I merge two sources — enriched open positions from CSV and dollar allocations from the sizer — keyed by `(ticker, function, interval, direction)`. Size on the holdings table must match the sizer; I enforce that with a single allocation index.

**Book rules I enforced:** Only `book_id=model` with `book=enhanced` returns data today. Brokerage, personal, and the other three MODEL books (`base`, `ssi`, `cv`) return **422** with a clear message instead of silently faking numbers. That is intentional — those books need Ahil’s replay and Rohit’s IBKR spec first.

**Bugs I fixed along the way:**
- Cluster sizer was deploying ~$1.77B when the ceiling was $80M — each position took 100% of its cluster budget.
- ETF/FX rows showed **BLOCKED → $0** instead of base size (Conviction Engine is single-stock only).
- `rr_dynamic` existed in nightly CSVs but was not always exposed through API enrichment.

**What I did not build:** `/portfolio/nav`, four-book NAV toggle, D1 slot-based sizing (`NAV/N × conviction × SSI`), brokerage/personal books. Those are in [`OPEN_QUESTIONS_FOR_ROHIT.md`](../instruction_docs/portfolio_page/OPEN_QUESTIONS_FOR_ROHIT.md).

---

### Track 2 — AI Analyst / Overwatch backend

**What I built:** The full server side for the Overwatch panel (API **v1.8.0 → v1.8.1**). The sliding 360px UI is still frontend work.

The panel works in two modes, and I wired both:

1. **Push mode** — Something important happens (strategy degradation or macro combo fires) → server pushes over SSE → UI can auto-open the panel.
2. **Pull mode** — User opens the panel and asks a question → chatbot receives **page context** (current route, active tab, visible alerts) so answers are aware of where they are.

**Three alert channels:**

| Tab | What it watches |
|-----|-----------------|
| **SIGNALS** | Forward win rate degradation (60% floor), booked losses, positions down &gt;10% |
| **MACRO** | Runic combos, regime override (CAPE + geo), sentiment extremes, persistence signals, watch combos |
| **SYSTEM** | Pipeline health — data freshness, nightly jobs, Tavily/Sheets connectivity (admin only) |

**Key APIs:**
- `GET /analytics/analyst/alerts` — single feed for all panel alerts
- `GET /analytics/analyst/context` — one bundle for the Nuxt layout (alerts + tab badges + regime + chat paths)
- `GET /overwatch/stream` — live SSE push
- `GET /system/health` — admin health checks

**Performance fix that saved the week:** The first degradation implementation read ~2,000 CSV files on every request and timed out at **&gt;4 minutes**. I added a parquet + result cache (`overwatch_store/`) so cached reads land in **under a second**. I also fixed a bug where portfolio checks re-loaded all files inside a loop.

**What I did not build:** The Nuxt panel chrome, Framer Motion slide-in, or wiring that replaces BFF mocks — all frontend (Parth).

---

### Track 3 — Macro / regime (research + production CONFIG)

This track ran in parallel with the API work, mostly Thu–Fri.

| Day | What happened |
|-----|---------------|
| **Mon–Tue** | Test 5 regime Sharpe uplift backtest; absorbed Rohit’s 14 July axioms (position-level NAV, no rebalancing) |
| **Thu 16** | B4 window audit **failed** (HY/VIX/VXTS on wrong window); D5 fed-cycle re-slice; D6 analytics collapse (Combo C shows “insufficient episodes” when n&lt;5) |
| **Fri 17** | B4 fix applied → **12/12 pass**; Combo D &amp; E promoted to production CONFIG; D1 regime-bucket daily series (2,149 rows) handed to Ahil; D2 curve phase proposal (research only) |

Combo D is now true **2-of-3** (VXTS / CFTC / VIX). Combo E is **3-of-3** with a CFTC escalation alert when positioning rises fast during an active E episode.

---

### How the week flowed (day by day, simple version)

| Day | Hours | Focus |
|-----|------:|--------|
| **Mon 13** | 3.5 h | Fixed prod admin login; audited portfolio HANDOFF gaps (4/9 endpoints); started Overwatch planning |
| **Tue 14** | 5.5 h | Regime Sharpe uplift backtest; absorbed portfolio axioms; fixed cluster sizer $1.77B bug |
| **Wed 15** | 8.0 h | Rohit 15 July portfolio spec (D1–D7); shipped Overwatch v1.8.0 core (alerts, SSE, system health); designed book validation |
| **Thu 16** | 6.0 h | B4 audit fail; D5/D6 macro work; started portfolio pipeline; degradation API &gt;4 min timeout discovered |
| **Fri 17** | 9.0 h | B4 fix + Combo D/E promotion; portfolio endpoints shipped (Parth unblocked); Overwatch v1.8.1 (context, tabs, chat); prod deploy + dashboard 429 fix |
| **Total** | **32.0 h** | ~6.4 h/day average |

Each day’s blockers, issues, and fixes are spelled out in the detailed sections below.

---

### Problems I hit and how I fixed them (headline list)

| Problem | What I did |
|---------|------------|
| Admin could not log in on prod | Reset password to match dev |
| Cluster sizer deployed 22× the equity ceiling | Proportional split by BQ rank weight within ceiling |
| Degradation API &gt;4 minutes | Parquet + result cache → &lt;1s warm reads |
| Dashboard “Avg Fwd win rate: Could not compute” | Traced to BFF 429, not backend; raised rate limit + BFF cache |
| Analyst routes 404 on prod | Deployed v1.8.0; restarted API |
| ETF/FX showed $0 size | D2 fix: NOT_APPLICABLE → base size, never blocked |
| Frontend had no tab badges | Added `meta.tabs` + `channel` filter in v1.8.1 |
| B4 window audit failed | CONFIG fix Thu→Fri; 12/12 pass |

---

### What I did **not** finish (still outstanding)

| Item | Why |
|------|-----|
| Portfolio NAV chart + four-book toggle | Ahil four-book replay + Rohit Axiom 2 |
| D1 slot sizing engine | Rohit has not locked N, notional, SLEEVES |
| Brokerage / personal books | No IBKR spec |
| Overwatch panel UI | Frontend (Nuxt) |
| `exit_type=eviction` on exits | Needs 1C eviction engine |
| Push commits from AWS | No GitHub credentials on server |

---

### One-sentence summary (my week)

**I unblocked two frontend surfaces (Portfolio + Overwatch) on the backend, hardened macro regime CONFIG for production, and fixed prod login, sizer math, degradation performance, and dashboard rate limits — while explicitly refusing to fake data for books and features that still need Rohit and Ahil decisions.**

---

## Executive Summary

This week spanned three major backend tracks in parallel:

| Track | Headline outcome |
|-------|------------------|
| **Macro / regime** | B4 percentile windows fixed (12/12 pass); Combo D & E promoted to production CONFIG; D6 analytics collapse; regime-bucket daily series handed to Ahil for P3 replay |
| **AI Analyst (Overwatch)** | Full backend shipped v1.8.0 → v1.8.1 — unified alerts API, SSE push stream, degradation performance cache, cross-page context bundle, chat `page_context` |
| **Portfolio page** | Five new HANDOFF endpoints + book validation layer — Parth unblocked on MODEL/`enhanced` book for holdings, entries, exits, sizing, and portfolio-risk report |

**API versions:** v1.8.0 (Overwatch core) → v1.8.1 (context, tabs, regime/sentiment warnings)  
**Tests:** 56 portfolio/signals tests + analyst/degradation/cache suites passing  
**Time logged:** **32.0 hours** across 5 days (3.5 + 5.5 + 8.0 + 6.0 + 9.0) — see [Time Log & Task Register](#time-log--task-register)  
**Prod impact:** Admin login fix, cluster sizer bug fix, v1.8.0 deploy, dashboard 429 fix

**One-line summary:** Unified the Overwatch backend (alerts, SSE, degradation cache, context-aware chat), unblocked Portfolio APIs for the MODEL book, and hardened macro regime CONFIG — while fixing prod login, dashboard rate limits, and portfolio sizer math bugs.

---

## Time Log & Task Register

*Estimated hours per task — reflects focused dev time (not calendar span). Target was ~5–6 h/day; actual week total **32.0 h** (~6.4 h/day average).*

### Daily hours summary

| Date | Day | Hours | Focus |
|------|-----|------:|-------|
| **2026-07-13** | Monday | **3.5 h** | Prod ops, HANDOFF audit, Overwatch planning (lighter day) |
| **2026-07-14** | Tuesday | **5.5 h** | Regime uplift backtest, axioms intake, cluster sizer bug fix |
| **2026-07-15** | Wednesday | **8.0 h** | Rohit 15 Jul spec, Overwatch v1.8.0 core, book architecture |
| **2026-07-16** | Thursday | **6.0 h** | Macro D4–D6, F4 analysis, portfolio pipeline start, degradation timeout |
| **2026-07-17** | Friday | **9.0 h** | B4 fix, Combo D/E promotion, portfolio ship, v1.8.1, prod deploy |
| | **Week total** | **32.0 h** | |

### Full task register (date · track · hours · files)

| # | Date | Track | Task | Hours | Files changed |
|---|------|-------|------|------:|---------------|
| 1 | 2026-07-13 | Ops | Fix prod admin login (`admin@mindwealth.co`) | 1.0 | `config/users.json`, `config/.bootstrap_admin_password` *(prod runtime — not in git)* |
| 2 | 2026-07-13 | Portfolio | HANDOFF gap audit (4/9 endpoints exist) | 1.0 | *(read-only — no code changes)* |
| 3 | 2026-07-13 | AI Analyst | Overwatch planning — three channels, scattered-warnings map | 1.5 | *(design notes only)* |
| 4 | 2026-07-14 | Macro | Test 5 — Regime Sharpe uplift backtest (SPY/TLT/GLD/HYG) | 3.0 | `testing/5_regime_uplift/PLAN.md`, `multiplier_spec.md`, `run_regime_sharpe_uplift.py`, `README.md`, `output_files/*` |
| 5 | 2026-07-14 | Portfolio | Rohit 14 Jul axioms intake — scope NAV/four-book blockers | 1.0 | *(read `instruction_docs/portfolio_page/14July_axioms_and_specs.md`)* |
| 6 | 2026-07-14 | Portfolio | Cluster sizer bug — discovery + fix ($1.77B vs $80M ceiling) | 1.5 | `api/services/portfolio_service.py`, `tests/test_api_portfolio.py` |
| 7 | 2026-07-15 | Portfolio | Rohit 15 Jul spec (D1–D7) — endpoint list, book rules | 1.0 | *(read `instruction_docs/portfolio_page/15July_imp_spec_additions.md`)* |
| 8 | 2026-07-15 | Portfolio | Two-level book model design (`book_id` + `book`, 422 semantics) | 1.0 | `api/services/portfolio_book.py` *(skeleton)* |
| 9 | 2026-07-15 | AI Analyst | **Overwatch v1.8.0 core** — alerts, brief, SSE, system health, degradation rules, runic + Analog Finder, cron | 5.0 | `api/schemas/analyst.py`, `api/services/analyst_service.py`, `api/services/system_health_service.py`, `api/services/overwatch_event_bus.py`, `api/services/degradation_service.py`, `api/routers/analytics.py`, `api/routers/overwatch.py`, `api/routers/system.py`, `api/routers/signals.py`, `api/main.py`, `api/rate_limit.py`, `src/macro_intelligence/output/json_writer.py`, `scripts/overwatch/run_overwatch_signals.py`, `scripts/overwatch/run_overwatch_macro.py`, `scripts/overwatch/run_overwatch_system.py`, `scripts/install_aws_cron_dual.sh`, `tests/test_api_analyst.py`, `docs/api/services/analyst/` *(README + 5 endpoint pages)*, `docs/api/changelog.md`, `docs/api/openapi/mindwealth-v1.json`, `docs/dev_to_prod_migration_todos.md` |
| 10 | 2026-07-15 | AI Analyst / Portfolio | Extract shared `macro_override.py` (CAPE + geo banner) | 0.5 | `api/services/macro_override.py` |
| 11 | 2026-07-15 | Portfolio | Start `OPEN_QUESTIONS_FOR_ROHIT.md` (5 blocking decisions) | 0.5 | `instruction_docs/portfolio_page/OPEN_QUESTIONS_FOR_ROHIT.md` |
| 12 | 2026-07-16 | Macro | D4 — B4 window audit (3/12 FAIL) | 1.0 | `testing/macro_th_exp/D4_window_audit_rerun_2026-07-16.json`, `testing/macro_th_exp/D4_window_audit_rerun_2026-07-16.md` |
| 13 | 2026-07-16 | Macro | D5 — Fed-cycle re-slicing on recalibrated D/E | 1.0 | `testing/macro_th_exp/run_d5_fed_cycle_reslice.py`, `testing/macro_th_exp/D5_fed_cycle_reslice_2026-07-16.csv`, `D5_fed_cycle_reslice_2026-07-16.json`, `D5_fed_cycle_reslice_2026-07-16.md`, `D5_fed_cycle_per_fire_2026-07-16.csv` |
| 14 | 2026-07-16 | Macro | D6 — Open doubts resolution doc | 0.5 | `testing/macro_th_exp/D6_open_doubts_resolution_2026-07-16.md`, `D6_open_doubts_resolution_2026-07-16.json` |
| 15 | 2026-07-16 | Macro | D6 — Analytics collapse + Combo C min-n guard | 1.0 | `src/macro_intelligence/engine/regime_v2_shadow.py`, `src/macro_intelligence/analysis/regime_experiments/metrics.py`, `src/macro_intelligence/analysis/regime_experiments/fm_events.py`, `src/macro_intelligence/engine/combo_metadata.py`, `macro_intelligence/CONFIG.yaml`, `tests/test_regime_v2_experiments.py`, `tests/test_combo_metadata.py` |
| 16 | 2026-07-16 | Macro | F4 v2 steepening driver split — **PARK F4** | 0.5 | `scripts/f4_v2_steepening_driver_split.py`, `macro_intelligence/analysis/regime_v2_experiments/F4_v2_steepening_driver_split.json` |
| 17 | 2026-07-16 | Portfolio | Portfolio pipeline — `portfolio_book.py`, `portfolio_pipeline_service.py` (entries/exits stubs) | 1.0 | `api/services/portfolio_book.py`, `api/services/portfolio_pipeline_service.py` |
| 18 | 2026-07-16 | AI Analyst | Degradation API timeout investigation + cache implementation (start) | 0.5 | `api/services/degradation_cache.py` *(new)*, `api/services/degradation_service.py` |
| 19 | 2026-07-16 | Macro | D6 smoke tests + regime analytics re-slice (scripts started) | 0.5 | `testing/macro_th_exp/run_d6_smoke_tests.py`, `run_d6_regime_analytics_reslice.py` *(runs completed 17 Jul)* |
| 20 | 2026-07-17 | Macro | B4 original-spec window fix pipeline (**12/12 pass**) | 1.25 | `macro_intelligence/CONFIG.yaml`, `testing/macro_th_exp/run_b4_window_fix_pipeline.py`, `B4_window_fix_pipeline_2026-07-17.md`, `B4_window_fix_pipeline_2026-07-17.json`, `macro_intelligence/analysis/regime_v2_experiments/B_twy_and_percentiles.json`, `threshold_sweep_v2_b4_fix/*`, `testing/macro_th_exp/D4_window_audit_rerun_2026-07-16.md` *(superseded note)* |
| 21 | 2026-07-17 | Macro | Promote **Combo E** + CFTC escalation alert | 1.0 | `macro_intelligence/CONFIG.yaml`, `src/macro_intelligence/engine/combo_detector.py`, `src/macro_intelligence/engine/dominant.py`, `src/macro_intelligence/jobs/nightly_run.py`, `src/macro_intelligence/output/briefing_renderer.py`, `src/macro_intelligence/claude/nightly_briefing.py`, `api/services/macro_service.py`, `tests/test_combo_e_thresholds.py` |
| 22 | 2026-07-17 | Macro | Promote **Combo D** — true 2-of-3 detector | 1.0 | `macro_intelligence/CONFIG.yaml`, `src/macro_intelligence/engine/combo_detector.py`, `src/macro_intelligence/claude/nightly_briefing.py`, `api/services/macro_service.py`, `tests/test_combo_d_thresholds.py` |
| 23 | 2026-07-17 | Macro | D/E threshold sweeps recheck vs live CONFIG | 0.25 | `testing/combo_de_thresholds/run_combo_de_study.py`, `run_combo_de_followup.py`, `de_threshold_config_recheck_2026-07-17.md`, `testing/combo_de_thresholds/output_files/*` |
| 24 | 2026-07-17 | Macro | D1 — Regime bucket daily feed for Ahil (2,149 rows) | 0.5 | `testing/macro_th_exp/run_d1_regime_bucket_feed.py`, `D1_regime_bucket_daily_2026-07-17.csv`, `D1_regime_bucket_fridays_2026-07-17.csv`, `D1_regime_bucket_feed_2026-07-17.json`, `D1_regime_bucket_feed_2026-07-17.md` |
| 25 | 2026-07-17 | Macro | D2 — Curve phase flag proposal (research only) | 0.25 | `testing/macro_th_exp/D2_curve_phase_proposal_2026-07-17.md`, `D2_curve_phase_proposal_2026-07-17.json`, `D2_curve_phase_episodes_recommended_2026-07-17.csv`, `D2_curve_phase_weekly_panel.csv`, `D2_may2025_simple_vs_posttrough.csv`, `D2_phase_off_spec_comparison_2026-07-17.json` |
| 19b | 2026-07-17 | Macro | D6 smoke tests + regime analytics re-slice (complete + artifacts) | 0.5 | `D6_smoke_tests_2026-07-17.md`, `D6_smoke_tests_2026-07-17.json`, `D6_regime_analytics_2026-07-17.md`, `D6_regime_analytics_2026-07-17.json`, `D6_fm_regime_slices_analytics_2026-07-17.csv`, `D6_combo_fed_cycle_analytics_2026-07-17.csv`, `D6_liquidity_*_2026-07-17.csv` |
| 26 | 2026-07-17 | Portfolio | **Portfolio API ship** — holdings, entries, exits, sizing alias, risk report, D2/rr_dynamic/conviction_summary | 1.5 | `api/services/portfolio_book.py`, `api/services/portfolio_pipeline_service.py`, `api/services/portfolio_service.py`, `api/services/signal_enrichment_service.py`, `api/routers/portfolio.py`, `api/routers/signals.py`, `tests/test_api_portfolio.py`, `tests/test_api_signals_surface.py` |
| 27 | 2026-07-17 | AI Analyst | **Overwatch v1.8.1** — context bundle, tabs, channel filter, regime/sentiment warnings, chat `page_context` | 1.25 | `api/services/analyst_service.py`, `api/services/macro_override.py`, `api/routers/analytics.py`, `api/schemas/analyst.py`, `api/schemas/chatbot.py`, `api/services/chatbot_service.py`, `tests/test_api_analyst.py`, `tests/test_chatbot_page_context.py`, `docs/mindwealth-api-docs/` *(v1.8.1 submodule sync)* |
| 28 | 2026-07-17 | AI Analyst | Degradation cache finish + integration health markers + Claude copy hook | 0.5 | `api/services/degradation_cache.py`, `api/services/degradation_service.py`, `api/services/integration_health_store.py`, `api/services/analyst_copy_service.py`, `api/services/system_health_service.py`, `chatbot/agents/web_search_agent.py`, `src/conviction_engine/daily_run.py`, `tests/test_degradation_cache.py`, `scripts/overwatch/run_overwatch_signals.py` |
| 29 | 2026-07-17 | Ops / AI Analyst | Prod deploy v1.8.0 + dashboard 429 fix + BFF cache | 0.75 | `config/rate_limits.yaml`, `api/main.py`, `api/routers/analytics.py`, `api/routers/overwatch.py`, `api/routers/system.py`, `api/routers/signals.py`, `api/services/analyst_service.py`, `api/services/degradation_service.py`, `api/services/overwatch_event_bus.py`, `api/services/system_health_service.py`, `api/schemas/analyst.py`, `tests/test_api_analyst.py`, `scripts/overwatch/*`; **MindwealthUI_Vue:** `server/utils/mindwealth-client.ts`, `server/utils/mindwealth-data.ts`, `server/utils/performance-aggregates.ts`, `server/utils/unavailable-data.ts` |
| 30 | 2026-07-17 | Docs | Finalize open questions + migration todos | 0.25 | `instruction_docs/portfolio_page/OPEN_QUESTIONS_FOR_ROHIT.md`, `docs/dev_to_prod_migration_todos.md` |

### Hours by track (week total)

| Track | Hours | % of week |
|-------|------:|----------:|
| **Macro / regime** | 13.0 h | 41% |
| **AI Analyst / Overwatch** | 9.5 h | 30% |
| **Portfolio page** | 7.5 h | 23% |
| **Ops** | 1.75 h | 5% |
| **Docs** | 1.25 h | 4% |
| | **32.0 h** | **100%** |

---

### Files changed by track (consolidated, unique paths)

#### Track 1 — Portfolio page backend

```
api/routers/portfolio.py
api/routers/signals.py
api/services/portfolio_book.py
api/services/portfolio_pipeline_service.py
api/services/portfolio_service.py
api/services/signal_enrichment_service.py
api/services/macro_override.py
tests/test_api_portfolio.py
tests/test_api_signals_surface.py
instruction_docs/portfolio_page/OPEN_QUESTIONS_FOR_ROHIT.md
```

#### Track 2 — AI Analyst / Overwatch

```
api/main.py
api/rate_limit.py
api/routers/analytics.py
api/routers/overwatch.py
api/routers/system.py
api/routers/signals.py
api/schemas/analyst.py
api/schemas/chatbot.py
api/services/analyst_service.py
api/services/analyst_copy_service.py
api/services/chatbot_service.py
api/services/degradation_service.py
api/services/degradation_cache.py
api/services/integration_health_store.py
api/services/macro_override.py
api/services/overwatch_event_bus.py
api/services/system_health_service.py
chatbot/agents/web_search_agent.py
src/conviction_engine/daily_run.py
src/macro_intelligence/output/json_writer.py
scripts/overwatch/run_overwatch_signals.py
scripts/overwatch/run_overwatch_macro.py
scripts/overwatch/run_overwatch_system.py
scripts/install_aws_cron_dual.sh
config/rate_limits.yaml
tests/test_api_analyst.py
tests/test_chatbot_page_context.py
tests/test_degradation_cache.py
docs/api/services/analyst/          (README + 6 endpoint pages)
docs/api/changelog.md
docs/api/openapi/mindwealth-v1.json
docs/mindwealth-api-docs/           (submodule v1.8.0 → v1.8.1)
docs/dev_to_prod_migration_todos.md
overwatch_store/                    (runtime cache dir — parquet + result cache)
```

**MindwealthUI_Vue** (separate repo — dashboard 429 / BFF only):

```
server/utils/mindwealth-client.ts
server/utils/mindwealth-data.ts
server/utils/performance-aggregates.ts
server/utils/unavailable-data.ts
```

#### Track 3 — Macro / regime

```
macro_intelligence/CONFIG.yaml
src/macro_intelligence/engine/regime_v2_shadow.py
src/macro_intelligence/engine/combo_metadata.py
src/macro_intelligence/engine/combo_detector.py
src/macro_intelligence/engine/dominant.py
src/macro_intelligence/jobs/nightly_run.py
src/macro_intelligence/output/briefing_renderer.py
src/macro_intelligence/claude/nightly_briefing.py
src/macro_intelligence/analysis/regime_experiments/metrics.py
src/macro_intelligence/analysis/regime_experiments/fm_events.py
api/services/macro_service.py
scripts/f4_v2_steepening_driver_split.py
macro_intelligence/analysis/regime_v2_experiments/B_twy_and_percentiles.json
macro_intelligence/analysis/regime_v2_experiments/F4_v2_steepening_driver_split.json
macro_intelligence/analysis/regime_v2_experiments/threshold_sweep_v2_b4_fix/*
testing/5_regime_uplift/*
testing/macro_th_exp/*              (D1, D2, D4, D5, D6, B4 artifacts)
testing/combo_de_thresholds/*
tests/test_regime_v2_experiments.py
tests/test_combo_metadata.py
tests/test_combo_d_thresholds.py
tests/test_combo_e_thresholds.py
```

#### Ops (prod runtime — not git)

```
config/users.json                   (prod clone)
config/.bootstrap_admin_password    (prod clone)
```

---

## Week at a Glance — Deliverables

### AI Analyst / Overwatch (backend complete for v1.8.1)

| Deliverable | Endpoint / artifact |
|-------------|---------------------|
| Unified alerts feed | `GET /api/v1/analytics/analyst/alerts` |
| Cross-page shell bundle | `GET /api/v1/analytics/analyst/context` |
| Dashboard snippet | `GET /api/v1/analytics/analyst/brief` |
| Live push (SSE) | `GET /api/v1/overwatch/stream` |
| Admin pipeline health | `GET /api/v1/system/health` |
| Raw degradation scan (BFF compat) | `POST /api/v1/signals/check-degradation` |
| Context-aware panel chat | `page_context` on `POST /chatbot/sessions/{id}/messages` |
| Performance cache | `degradation_cache.py` → `overwatch_store/` |
| Background cron | `scripts/overwatch/run_overwatch_{signals,macro,system}.py` |
| API documentation | `docs/mindwealth-api-docs` v1.8.1 |

### Portfolio page (~55% of HANDOFF surface live)

| # | Endpoint | Status |
|---|----------|--------|
| 1 | `GET /portfolio/nav` | **Not built** — blocked on Ahil A1 + Axiom 2 |
| 2 | `GET /portfolio/holdings` | **Done** — MODEL + `book=enhanced` |
| 3 | `GET /portfolio/sizer` | **Done** (extended with `book_id`) |
| 4 | `GET /portfolio/risk` | **Done** (extended + `conviction_summary`) |
| 5 | `GET /signals/entries` | **Done** |
| 6 | `GET /signals/exits` | **Done** (partial — no `eviction` type) |
| 7 | `GET /signals/reports/portfolio-risk/latest` | **Done** — HANDOFF §11 shape |
| 8 | `GET /portfolio/risk/search` | **Done** (pre-existing) |
| 9 | `POST /portfolio/risk/analyze` | **Done** (pre-existing) |

**Alias:** `GET /portfolio/sizing` → same handler as `/portfolio/sizer`

### Macro / regime (research + production CONFIG)

| Item | Outcome |
|------|---------|
| B4 window audit (16 Jul) | 3/12 FAIL — HY/VIX/VXTS on `full` vs spec `rolling_3y` |
| B4 window fix (17 Jul) | CONFIG updated; 13,476 rows recomputed; **B4 pass=true** |
| Combo D promotion | VXTS≥1.18 / CFTC≥95 / VIX≤13, true 2-of-3, n=46 |
| Combo E promotion | CAPE≥32 / NFCI≤−0.15 / CFTC≥85, 3-of-3 + CFTC escalation alert |
| D6 analytics collapse | Fed-cycle PIVOTING→EASING; liquidity 9→4; Combo C min-n guard |
| D1 regime bucket feed | 2,149 daily rows (BENIGN/ADVERSE/MIXED) for Ahil P3 |
| Test 5 regime uplift | Sharpe 0.885 → 0.938 on SPY/TLT/GLD/HYG basket |

---

## Day-by-Day Breakdown

---

### Monday, 13 July 2026 — **3.5 hours**

#### What I did

1. **Prod ops — admin login fix** · *Ops · 1.0 h*
   - Prod `admin@mindwealth.co` was bootstrapped with a random password at deploy; user expected dev password.
   - Reset prod `config/users.json` to match dev credentials.
   - Verified login via direct API call and Nuxt proxy.
   - **Files:** `config/users.json`, `config/.bootstrap_admin_password` *(prod runtime)*

2. **Portfolio HANDOFF gap analysis** · *Portfolio · 1.0 h*
   - Audited [`PORTFOLIO_API_HANDOFF.md`](../instruction_docs/portfolio_page/PORTFOLIO_API_HANDOFF.md) against live API.
   - Found only **4 of 9** required endpoints existed (`/sizer`, `/risk`, `/risk/analyze`, `/risk/search`).
   - Parth was blocked on holdings, entries, exits, and book-scoped data for the v5 mock.
   - **Files:** *(read-only — no code changes)*

3. **AI Analyst planning** · *AI Analyst · 1.5 h*
   - Mapped the "scattered warnings" problem:
     - Strategy degradation buried in ~2,000 forward-testing CSV files.
     - Macro warnings on separate API routes.
     - Pipeline health had no product surface.
   - Designed unified Overwatch feed with three channels: SIGNALS, MACRO, SYSTEM.
   - **Files:** *(design notes only)*

4. **Spec intake (early)** · *Portfolio · included in planning*
   - Began reading Rohit's 14 July axioms email ([`14July_axioms_and_specs.md`](../instruction_docs/portfolio_page/14July_axioms_and_specs.md)) for portfolio NAV methodology constraints.

#### Blockers

| Blocker | Impact |
|---------|--------|
| Parth waiting on portfolio endpoints | Portfolio page stuck on mocks |
| No unified analyst API | Frontend would need to stitch 5+ endpoints or use mocks |
| Prod admin access broken | Stakeholders could not log in |

#### Issues and resolutions

| Issue | Root cause | How I solved it |
|-------|------------|-----------------|
| Admin login failed on prod | Random bootstrap password at deploy | Reset password in prod `config/users.json`; verified end-to-end |
| Unclear portfolio build scope | 9 endpoints, many blocked on Ahil/Rohit decisions | Listed HANDOFF gaps; documented what can ship without guessing |

---

### Tuesday, 14 July 2026 — **5.5 hours**

#### What I did

1. **Test 5 — Regime Sharpe uplift backtest** · *Macro · 3.0 h*
   - Built Michele demo backtest in `testing/5_regime_uplift/`.
   - Equal-weight monthly-rebalance basket (SPY/TLT/GLD/HYG), 2007-04 → 2026-07.
   - **Results:** Baseline Sharpe 0.885 → regime overlay 0.938 (+0.053); max DD improved −22.6% → −17.6%; CAGR lowered 7.72% → 6.39%.
   - **Files:** `testing/5_regime_uplift/PLAN.md`, `multiplier_spec.md`, `run_regime_sharpe_uplift.py`, `README.md`, `output_files/*`

2. **Rohit axioms — Part I & II** · *Portfolio · 1.0 h*
   - Absorbed six fixed axioms (reconciliation waterfall, position-level NAV, no rebalancing, out-of-sample gates, runtime gate membership, turnover + costs, protective mechanisms in bad markets).
   - Informed portfolio API scope: `/portfolio/nav` and four-book toggle cannot ship until Ahil's A1 four-book attribution replay on axiom-compliant 1C base.
   - **Files:** *(read `instruction_docs/portfolio_page/14July_axioms_and_specs.md`)*

3. **AI Analyst — degradation rules locked** · *AI Analyst · included in Wed work*
   - Spec-aligned 60% WATCH/BREACH floor with 4-week `fwd_trend`.
   - Portfolio triggers: booked losses and positions down >10% MTM fire immediately.

4. **Portfolio sizer bug — discovery + fix** · *Portfolio · 1.5 h*
   - Each open position was allocated 100% of its cluster budget independently.
   - Cluster `deployed_usd` summed to ~$1.77B while summary showed $80M equity ceiling.
   - Fixed: cluster caps use equity ceiling; split budget proportionally by BQ rank weight.
   - **Files:** `api/services/portfolio_service.py`, `tests/test_api_portfolio.py`

#### Blockers

| Blocker | Impact |
|---------|--------|
| D1 slot sizing (`NAV/N × conviction × SSI`) | Rohit had not locked N, notional, or SLEEVES table |
| `/portfolio/nav` + four-book toggle | Blocked on Ahil A1 attribution replay |
| Degradation scan reads ~2,000 CSVs per request | Known performance risk before implementation |

#### Issues and resolutions

| Issue | Root cause | How I solved it |
|-------|------------|-----------------|
| Cluster deployed totals wrong | Independent 100% cluster allocation per position | Fixed `portfolio_service.py` — proportional split by BQ rank weight within equity ceiling |
| Portfolio NAV scope unclear | Axiom 1/2 require position-level NAV without rebalancing | Documented dependencies; deferred nav until Ahil replay |

---

### Wednesday, 15 July 2026 — **8.0 hours**

#### What I did

1. **Rohit 15 July portfolio finalization spec** · *Portfolio · 1.0 h*
   - Processed D1–D7 from [`15July_imp_spec_additions.md`](../instruction_docs/portfolio_page/15July_imp_spec_additions.md):
     - D1: Retire interim cluster engine → slot-based sizing (blocked on decisions).
     - D2: ETF/FX/commodity → base size, never BLOCKED → $0.
     - D4: Endpoint list that unblocks Parth.
     - D5: Negative `rr_dynamic` semantics + `same_asset_siblings` payload.
     - D7: One source for true weights across Sizing & Risk pages.
   - **Files:** *(read spec doc)*

2. **Portfolio architecture — two-level book model** · *Portfolio · 1.0 h*
   - **Upper level:** `book_id` = `model` | `brokerage` | `personal`.
   - **Lower level (MODEL only):** `book` = `base` | `ssi` | `cv` | `enhanced`.
   - Design decision: return explicit **422** for unsupported books rather than silently serving wrong data.
   - Only `book_id=model` + `book=enhanced` served today.
   - **Files:** `api/services/portfolio_book.py` *(skeleton)*

3. **AI Analyst v1.8.0 — core Overwatch backend** · *AI Analyst · 5.0 h*
   - `GET /analytics/analyst/alerts` — unified `panel_alerts[]` with `channel` + `type`.
   - `GET /analytics/analyst/brief` — dashboard one-liner snippet.
   - `GET /overwatch/stream` — SSE in-process event bus for auto-open.
   - `GET /system/health` — admin-only 7-check pipeline health.
   - Degradation rules: 60% floor, 4-week trend, portfolio booked-loss / MTM triggers.
   - Macro runic alerts with Analog Finder; `historical_analogs` block in nightly JSON writer.
   - Overwatch cron scripts + wiring in `install_aws_cron_dual.sh`.
   - API docs: 5 endpoint pages under `docs/api/services/analyst/`.
   - **Files:** `api/schemas/analyst.py`, `api/services/analyst_service.py`, `api/services/system_health_service.py`, `api/services/overwatch_event_bus.py`, `api/services/degradation_service.py`, `api/routers/analytics.py`, `api/routers/overwatch.py`, `api/routers/system.py`, `api/routers/signals.py`, `api/main.py`, `api/rate_limit.py`, `src/macro_intelligence/output/json_writer.py`, `scripts/overwatch/run_overwatch_signals.py`, `scripts/overwatch/run_overwatch_macro.py`, `scripts/overwatch/run_overwatch_system.py`, `scripts/install_aws_cron_dual.sh`, `tests/test_api_analyst.py`, `docs/api/services/analyst/`, `docs/api/changelog.md`, `docs/api/openapi/mindwealth-v1.json`, `docs/dev_to_prod_migration_todos.md`

4. **Open questions doc — started** · *Portfolio / Docs · 0.5 h*
   - Began [`OPEN_QUESTIONS_FOR_ROHIT.md`](../instruction_docs/portfolio_page/OPEN_QUESTIONS_FOR_ROHIT.md) with 5 blocking product decisions.
   - **Files:** `instruction_docs/portfolio_page/OPEN_QUESTIONS_FOR_ROHIT.md`

5. **Shared macro override extraction** · *AI Analyst / Portfolio · 0.5 h*
   - Extracted `compute_macro_override()` into `api/services/macro_override.py`.
   - Used by both `portfolio_service` and `analyst_service` for consistent "MACRO OVERRIDE" banner data.
   - **Files:** `api/services/macro_override.py`

#### Blockers

| Blocker | Impact |
|---------|--------|
| `book_id=brokerage\|personal` | No IBKR integration spec |
| `book=base\|ssi\|cv` | Ahil four-book replay not complete |
| Frontend still blocked | No holdings/entries/exits endpoints yet |

#### Issues and resolutions

| Issue | Root cause | How I solved it |
|-------|------------|-----------------|
| ETF/FX rows showed BLOCKED → $0 (D2) | Conviction Engine N/A mapped to zero tier | Identified fix path: NOT_APPLICABLE → N/A tier, 100% cluster share |
| `rr_dynamic` missing from API | Enrichment computed `rr_static` but did not pass through `rr_dynamic` | Added pass-through in `signal_enrichment_service.py` |
| Regime warnings only on portfolio sizer | `macro_override` not wired into analyst alerts | Shared `macro_override.py` module |

---

### Thursday, 16 July 2026 — **6.0 hours**

#### What I did

1. **D4 — B4 window audit** · *Macro · 1.0 h*
   - Re-ran `_run_b4_window_audit()` against live `CONFIG.yaml`.
   - WALCL fix confirmed PASS (`full`/`full`).
   - **HY, VIX, VXTS still FAIL** — using `full` window vs plan `rolling_3y`.
   - Result: 3/12 mismatches, **B4 pass=false**.
   - Flagged open spec conflict with Rohit 2026-06-11 structural-window override.
   - **Files:** `testing/macro_th_exp/D4_window_audit_rerun_2026-07-16.json`, `D4_window_audit_rerun_2026-07-16.md`

2. **D5 — Fed-cycle re-slicing on recalibrated D/E thresholds** · *Macro · 1.0 h*
   - D: VXTS≥1.18/CFTC≥95/VIX≤13, 2-of-3, n=46 @ 1W/2W.
   - E: CAPE≥32/NFCI≤−0.15/CFTC≥85, 3-of-3, n=10 @ 6M/9M/12M.
   - **CUTTING_LATE vs HIKING_LATE spread survives** at 1W (+50.6 pp) and 2W (+35.9 pp).
   - E per-fed slices all CANNOT USE (n<10).
   - **Files:** `testing/macro_th_exp/run_d5_fed_cycle_reslice.py`, `D5_fed_cycle_reslice_2026-07-16.{csv,json,md}`, `D5_fed_cycle_per_fire_2026-07-16.csv`

3. **D6 — Open doubts doc + analytics collapse implementation** · *Macro · 1.5 h*
   - Captured Rohit sign-off on PIVOTING→EASING merge, liquidity 9→4 collapse, Combo C min-n guard.
   - Wired `fed_cycle_v2_analytics()`, `collapse_liquidity_v2_analytics()`, `regime_value_for_analytics()` in `regime_v2_shadow.py`.
   - Combo C returns "insufficient episodes" when n<5. **26 tests pass.**
   - **Files:** `testing/macro_th_exp/D6_open_doubts_resolution_2026-07-16.{md,json}`, `src/macro_intelligence/engine/regime_v2_shadow.py`, `src/macro_intelligence/analysis/regime_experiments/metrics.py`, `fm_events.py`, `src/macro_intelligence/engine/combo_metadata.py`, `macro_intelligence/CONFIG.yaml`, `tests/test_regime_v2_experiments.py`, `tests/test_combo_metadata.py`

4. **D6 smoke tests + regime analytics re-slice (scripts started)** · *Macro · 0.5 h*
   - `run_d6_smoke_tests.py` — **8/8 pass** (completed 17 Jul).
   - `run_d6_regime_analytics_reslice.py` — PIVOTING n=27→EASING, 9→4 liquidity; 4 CSVs + report.
   - **Files:** `testing/macro_th_exp/run_d6_smoke_tests.py`, `run_d6_regime_analytics_reslice.py` *(artifact CSVs/JSON dated 2026-07-17)*

5. **F4 v2 steepening driver split (D3)** · *Macro · 0.5 h*
   - Classified −50/+15 cell episodes (n=17) by yield curve moves.
   - **Verdict: PARK F4** — pooled hit rate 17.6% vs 29.4% baseline.
   - **Files:** `scripts/f4_v2_steepening_driver_split.py`, `macro_intelligence/analysis/regime_v2_experiments/F4_v2_steepening_driver_split.json`

6. **Portfolio pipeline — started** · *Portfolio · 1.0 h*
   - Created `api/services/portfolio_book.py` — book validation with explicit 422.
   - Created `api/services/portfolio_pipeline_service.py` — entries/exits adapters from CSV sources.
   - **Files:** `api/services/portfolio_book.py`, `api/services/portfolio_pipeline_service.py`

7. **AI Analyst — performance crisis discovered + cache started** · *AI Analyst · 0.5 h*
   - `include_degradation=true` on alerts API timed out at **>240 seconds**.
   - Root cause: ~1,990 forward-testing CSV files read on every request.
   - Started `degradation_cache.py` parquet + result cache.
   - **Files:** `api/services/degradation_cache.py`, `api/services/degradation_service.py`

#### Blockers

| Blocker | Impact |
|---------|--------|
| B4 window mismatch | Short-gate combos B/D/G validation blocked |
| Degradation API unusable at current latency | Cannot ship to frontend or prod |
| Rohit decisions open on $10M vs $100M notional | D1 slot math blocked |

#### Issues and resolutions

| Issue | Root cause | How I solved it |
|-------|------------|-----------------|
| Degradation API >4 min timeout | ~1,990 CSV reads per request | Built `degradation_cache.py` — parquet + result cache in `overwatch_store/`; warm reads ~0.1–0.25s |
| Portfolio loop re-read 1,990 CSVs per row | Re-load inside booked-loss check loop | Single dataframe load; pass into portfolio trigger checks |
| Spec says `/portfolio/sizing`, code has `/sizer` | July spec renamed endpoint | Added `/sizing` alias route; `auto` scenario maps to `normal` |

---

### Friday, 17 July 2026 — **9.0 hours**

#### What I did

1. **B4 original-spec window fix pipeline** · *Macro · 1.25 h*
   - Applied original B4 rule: HY/VIX/VXTS → `rolling_3y`, WALCL → `full`.
   - Recomputed 13,476 percentile rows (3,428 changed).
   - **B4 pass=true (12/12).**
   - Re-ran B/D/G sweeps on post-fix panel; refreshed `B_twy_and_percentiles.json`.
   - **Files:** `macro_intelligence/CONFIG.yaml`, `testing/macro_th_exp/run_b4_window_fix_pipeline.py`, `B4_window_fix_pipeline_2026-07-17.{md,json}`, `macro_intelligence/analysis/regime_v2_experiments/B_twy_and_percentiles.json`, `threshold_sweep_v2_b4_fix/*`

2. **Combo D — promoted to production CONFIG** · *Macro · 1.0 h*
   - Gates: VXTS≥1.18 / CFTC≥95 / VIX≤13, true **2-of-3**.
   - n=46, 56.5% bear @1W; horizons 1W + 2W.
   - Detector rewritten: ACTIVE ≥2 legs, WATCH at 1.
   - Tests: `tests/test_combo_d_thresholds.py` (6 passed).
   - **Files:** `macro_intelligence/CONFIG.yaml`, `src/macro_intelligence/engine/combo_detector.py`, `src/macro_intelligence/claude/nightly_briefing.py`, `api/services/macro_service.py`, `tests/test_combo_d_thresholds.py`

3. **Combo E — promoted to production CONFIG** · *Macro · 1.0 h*
   - Gates: CAPE≥32 / NFCI≤−0.15 / CFTC≥85, **3-of-3**.
   - **ESCALATION_ALERT** when CFTC FM pctile rises ≥5 pts over 4 weeks while E active.
   - Tests: `tests/test_combo_e_thresholds.py` (5 passed).
   - **Files:** `macro_intelligence/CONFIG.yaml`, `src/macro_intelligence/engine/combo_detector.py`, `src/macro_intelligence/engine/dominant.py`, `src/macro_intelligence/jobs/nightly_run.py`, `src/macro_intelligence/output/briefing_renderer.py`, `src/macro_intelligence/claude/nightly_briefing.py`, `api/services/macro_service.py`, `tests/test_combo_e_thresholds.py`

4. **D/E threshold sweeps recheck** · *Macro · 0.25 h*
   - Re-ran sweeps on post-promotion CONFIG; hit rates match analysis BEST PRODUCTION SCORE.
   - **Files:** `testing/combo_de_thresholds/run_combo_de_study.py`, `run_combo_de_followup.py`, `de_threshold_config_recheck_2026-07-17.md`, `output_files/*`

5. **D1 — Regime bucket feed for Ahil P3** · *Macro · 0.5 h*
   - Published version-stamped daily series 2018–2026.
   - BENIGN / ADVERSE / MIXED buckets on recalibrated CONFIG gates.
   - Point-in-time Friday replay; Combo C sequential cancel replay (fixes live-flag leak).
   - **2,149 daily rows:** BENIGN=1,617, ADVERSE=238, MIXED=294.
   - Research handoff only — no prod/API change.
   - **Files:** `testing/macro_th_exp/run_d1_regime_bucket_feed.py`, `D1_regime_bucket_daily_2026-07-17.csv`, `D1_regime_bucket_fridays_2026-07-17.csv`, `D1_regime_bucket_feed_2026-07-17.{json,md}`

6. **D2 — Curve regime phase flag proposal** · *Macro · 0.25 h*
   - PROPOSE ONLY — `post_inversion_steepening` boolean alongside `curve_regime_v2`.
   - Backfill: 5 inversion episodes, 5 phase triggers, 165 phase-active weeks.
   - **Files:** `testing/macro_th_exp/D2_curve_phase_proposal_2026-07-17.{md,json}`, `D2_curve_phase_episodes_recommended_2026-07-17.csv`, `D2_curve_phase_weekly_panel.csv`, `D2_may2025_simple_vs_posttrough.csv`, `D2_phase_off_spec_comparison_2026-07-17.json`

7. **D6 smoke tests + regime analytics re-slice (complete)** · *Macro · 0.5 h*
   - Finished runs from Thu; wrote artifact CSVs/JSON.
   - **Files:** `D6_smoke_tests_2026-07-17.{md,json}`, `D6_regime_analytics_2026-07-17.{md,json}`, `D6_fm_regime_slices_analytics_2026-07-17.csv`, `D6_combo_fed_cycle_analytics_2026-07-17.csv`, `D6_liquidity_*_2026-07-17.csv`

8. **Portfolio API — Parth unblocked** · *Portfolio · 1.5 h*
   - `GET /portfolio/holdings` — merge outstanding enrichment + sizer allocations.
   - `GET /signals/entries` — from `new_signal.csv`, sorted by composite_score.
   - `GET /signals/exits` — from `target_signal.csv`, `exit_type`: `signal` | `rr`.
   - `GET /signals/reports/portfolio-risk/latest` — HANDOFF §11 + `implied_natural_exit_date`.
   - `GET /portfolio/sizing` alias; `book_id` on sizer/risk.
   - D2 ETF/FX base-size fix in sizer pass.
   - `conviction_summary` block on `/portfolio/risk`.
   - `same_asset_siblings[]`, `multi_sig[]`, `rr_dynamic` on holdings.
   - **56 tests passing** (`test_api_portfolio.py` + `test_api_signals_surface.py`).
   - **Files:** `api/services/portfolio_book.py`, `api/services/portfolio_pipeline_service.py`, `api/services/portfolio_service.py`, `api/services/signal_enrichment_service.py`, `api/routers/portfolio.py`, `api/routers/signals.py`, `tests/test_api_portfolio.py`, `tests/test_api_signals_surface.py`

9. **AI Analyst v1.8.1 — frontend integration bundle** · *AI Analyst · 1.25 h*
   - `GET /analytics/analyst/context` — cross-page shell: alerts + tab badges + regime + sentiment + chat paths.
   - `meta.tabs` badge text per spec ("Overwatch · 3 watch active", etc.).
   - `?channel=signals|macro|system` server-side filter.
   - New alert types: `regime_warning`, `sentiment_warning`, `runic_watch`, `persistence`.
   - Chat `page_context` on `POST /chatbot/sessions/{id}/messages` — route, tab, alert ids merged into LLM context.
   - **Files:** `api/services/analyst_service.py`, `api/services/macro_override.py`, `api/routers/analytics.py`, `api/schemas/analyst.py`, `api/schemas/chatbot.py`, `api/services/chatbot_service.py`, `tests/test_api_analyst.py`, `tests/test_chatbot_page_context.py`, `docs/mindwealth-api-docs/`

10. **Degradation cache finish + health markers + Claude copy** · *AI Analyst · 0.5 h*
   - Completed parquet + result cache; warm reads ~0.1–0.25s (was >240s).
   - Tavily/Sheets integration health markers via `integration_health_store.py`.
   - Optional Claude alert copy (`ANALYST_USE_CLAUDE_COPY=false` by default).
   - **Files:** `api/services/degradation_cache.py`, `api/services/degradation_service.py`, `api/services/integration_health_store.py`, `api/services/analyst_copy_service.py`, `api/services/system_health_service.py`, `chatbot/agents/web_search_agent.py`, `src/conviction_engine/daily_run.py`, `tests/test_degradation_cache.py`, `scripts/overwatch/run_overwatch_signals.py`

11. **Prod deploy + dashboard fix** · *Ops / AI Analyst · 0.75 h*
    - Merged `chatbot-dev` → `chatbot-prod`; prod API now v1.8.0.
    - Fixed dashboard "Avg Fwd win rate: Could not compute" — traced to Nuxt BFF **429** on `/analytics/performance`, not backend crash.
    - Raised `apikey.read` burst in `config/rate_limits.yaml` (60→150/10s).
    - Nuxt BFF: GET cache/dedup, real `avg_fwd_testing_win_rate`.
    - **Files:** `config/rate_limits.yaml`, `api/main.py`, `api/routers/{analytics,overwatch,system,signals}.py`, `api/services/{analyst,degradation,overwatch_event_bus,system_health}_*.py`, `api/schemas/analyst.py`, `tests/test_api_analyst.py`, `scripts/overwatch/*`; **MindwealthUI_Vue:** `server/utils/mindwealth-client.ts`, `mindwealth-data.ts`, `performance-aggregates.ts`, `unavailable-data.ts`

12. **Documentation finalize** · *Docs · 0.25 h*
    - Finalized `OPEN_QUESTIONS_FOR_ROHIT.md` — 5 blocking decisions with file/line citations.
    - API docs synced to v1.8.1 in `docs/mindwealth-api-docs` submodule.
    - **Files:** `instruction_docs/portfolio_page/OPEN_QUESTIONS_FOR_ROHIT.md`, `docs/dev_to_prod_migration_todos.md`, `docs/mindwealth-api-docs/`

#### Blockers

| Blocker | Impact |
|---------|--------|
| `git push` from AWS host | No GitHub credentials — commits local only |
| `/portfolio/nav`, D1 slots, brokerage/personal | Rohit/Ahil decisions pending |
| Nuxt Overwatch panel UI | Frontend (Parth) — 360px slide-in, Framer Motion |
| Prod Overwatch cron smoke tests | Pending in `dev_to_prod_migration_todos.md` |

#### Issues and resolutions

| Issue | Root cause | How I solved it |
|-------|------------|-----------------|
| Analyst routes 404 on prod | v1.8 not deployed | Merged chatbot-dev → chatbot-prod; restarted API |
| Dashboard avg fwd win rate missing | BFF 429 during parallel dashboard fan-out | Rate limit raise + BFF cache/dedup |
| Frontend blocked — no tab badges | Only raw `panel_alerts[]` returned | Added `meta.tabs` + `channel` filter (v1.8.1) |
| Tavily/Sheets health empty | No integration marker files | `integration_health_store.py` + writers in chatbot and conviction daily run |
| Holdings `size_usd` must match sizer | Two independent calculations | Single allocation index from sizer output keyed by position |
| portfolio-risk returned raw report blob | No HANDOFF adapter | Dedicated adapter in `portfolio_pipeline_service.py` |
| Circular import risk (risk ↔ pipeline) | `build_conviction_summary` in wrong module | Moved into `portfolio_service.py` |

---

## Technical Deep-Dive — AI Analyst

### Three alert channels

| Channel | Tab | Alert types | SSE auto-open |
|---------|-----|-------------|---------------|
| SIGNALS | SIGNALS | `degradation` | Yes |
| MACRO | MACRO | `runic`, `runic_watch`, `regime_warning`, `sentiment_warning`, `persistence` | Yes (`runic` only) |
| SYSTEM | SYSTEM (admin) | `system` | No |

### Degradation rules (SIGNALS)

- **60% floor:** above 60% with declining 4-week trend → WATCH; below 60% → BREACH.
- **Portfolio triggers:** booked losses and positions down >10% MTM fire immediately.
- **Performance:** parquet cache at `overwatch_store/fwd_trades.parquet`; result cache for API responses.
- **Cold build:** ~20s — handled by cron pre-warm, not user-facing.

### Cross-page chat (PULL mode)

`page_context` fields merged into LLM `additional_context`:

| Field | Purpose |
|-------|---------|
| `route` | Current page, e.g. `/portfolio` |
| `page_title` | Human label |
| `active_tab` | Overwatch tab: `all` \| `signals` \| `macro` \| `system` |
| `panel_open` | Whether panel is open |
| `alert_ids` | Visible alert ids |
| `dominant_combo` | Active macro combo for context |

### Architecture decisions (locked)

- **SSE:** in-process event bus; production API must run with **uvicorn workers=1**.
- **Claude:** copy only (optional); triggers are rule-based.
- **Regime override:** shared `compute_macro_override()` in `macro_override.py`.
- **Tab filtering:** server via `?channel=`; client can also filter `panel_alerts[]` by `channel` or `type`.

### Key files

```
api/
  routers/analytics.py          # /analyst/alerts, /context, /brief
  routers/overwatch.py          # /overwatch/stream
  routers/system.py             # /system/health
  services/analyst_service.py   # All alert builders, context bundle
  services/macro_override.py    # Shared CAPE + geo override
  services/degradation_service.py
  services/degradation_cache.py
  services/system_health_service.py
  services/overwatch_event_bus.py
  services/integration_health_store.py
  services/analyst_copy_service.py
  schemas/analyst.py
  schemas/chatbot.py            # PageContext

scripts/overwatch/
  run_overwatch_signals.py
  run_overwatch_macro.py
  run_overwatch_system.py

tests/
  test_api_analyst.py
  test_degradation_cache.py
  test_chatbot_page_context.py
```

---

## Technical Deep-Dive — Portfolio

### Holdings merge logic

Holdings are **not** a third independent calculation. Two sources merged:

1. **`outstanding_signal.csv` (enriched)** — score, rank, rr_dynamic, hold-time %, conviction, cross-function flags.
2. **`/portfolio/sizer` allocations** — `size_usd`, shares, market_value, pnl_usd, sleeve label.

**Match key:** `(ticker, function, interval, direction)`.

**`same_asset_siblings[]`:** built from outstanding + new_signal rows grouped by symbol. Relationship types: `new_signal` | `already_held`. Populated for all rows where siblings exist.

**`multi_sig[]`:** other open signals on same ticker in same direction (informational only; no sizing boost).

### Entries / exits pipelines

| Endpoint | Source CSV | Logic |
|----------|------------|-------|
| `/signals/entries` | `new_signal.csv` | Enrich → sort by `composite_score` desc → rank |
| `/signals/exits` | `target_signal.csv` | Filter exit candidates → `exit_type`: `signal` \| `rr` |

`exit_type=eviction` **not implemented** — requires 1C eviction engine (Ahil/Rohit).

### Portfolio-risk report (HANDOFF §11)

Source: `trade_store/US/cross_function_conflicts.json`.

Reshaped to:
- `cross_function_conflict_count`
- `cross_function_conflicts[]` with `triggering_exits`, `open_positions`
- `implied_natural_exit_date` = `signal_date + avg_hold_days`

### D2 fix — ETF / FX / commodity base size

**Problem:** Conviction Engine is single-stock only. NOT_APPLICABLE assets were tiered BLOCKED → $0.

**Fix:** NOT_APPLICABLE with no BQ → tier `N/A`, share 100% of cluster slot (base size), never blocked to zero.

### Book validation

```python
validate_book_access("model", book="enhanced")  # OK
validate_book_access("model", book="base")      # BookUnavailableError → 422
validate_book_access("brokerage")               # BookUnavailableError → 422
```

### Key files

```
api/
  routers/portfolio.py              # holdings, sizer, sizing, risk
  routers/signals.py                # entries, exits, portfolio-risk
  services/portfolio_book.py        # NEW — book_id / book validation
  services/portfolio_pipeline_service.py  # NEW — pipeline adapters
  services/portfolio_service.py     # sizer, risk, D2 fix, conviction_summary
  services/signal_enrichment_service.py  # rr_dynamic pass-through

instruction_docs/portfolio_page/
  OPEN_QUESTIONS_FOR_ROHIT.md
  PORTFOLIO_API_HANDOFF.md

tests/
  test_api_portfolio.py
  test_api_signals_surface.py
```

---

## Verification Summary

| Check | Result |
|-------|--------|
| Portfolio + signals tests | **56 passed** |
| Analyst + degradation + page_context tests | **Pass** |
| Live dev API (`:8507`) health | **v1.8.1** |
| `GET /analytics/analyst/context` | **200** |
| Cached degradation alerts | **~0.07–0.25s** (was >240s) |
| Holdings `book=enhanced` | **200** + holdings array |
| Holdings `book=base` | **422** |
| `book_id=brokerage` | **422** |
| `/portfolio/sizing` vs `/sizer` summary | **Match** |
| Prod API after deploy | **v1.8.0**; analyst/performance routes **200** |
| B4 window audit | **12/12 pass** |
| D6 smoke tests | **8/8 pass** |

---

## Still Outstanding (do not over-claim in presentation)

| Item | Blocker | Owner |
|------|---------|-------|
| 360px Overwatch panel UI | Frontend not started | Parth (Nuxt) |
| Replace `overwatch-panel.ts` mocks | Wire to `/analytics/analyst/context` | Parth |
| `GET /portfolio/nav` | Ahil A1 NAV replay + Axiom 2 | Ahil + Rohit |
| `book=base\|ssi\|cv` | Four-book attribution not replayed | Ahil |
| `book_id=brokerage\|personal` | IBKR spec + persistence | Rohit |
| D1 slot sizing engine | N, notional, SLEEVES undecided | Rohit |
| `exit_type=eviction` | 1C eviction engine | Ahil |
| `pnl_contribution_bps` on holdings | Needs NAV denominator | Blocked on nav |
| `alerts.json` with `target_page` | Separate D4 item | Deferred |
| Redis-backed SSE | Multi-worker deferred | Future |
| `git push` from AWS host | No GitHub credentials | Dev machine |
| Prod Overwatch cron install + smoke | Pending cutover | Ops |

---

## Presentation Guidance

### Is this sufficient work for one week?

**Yes — this is a dense, credible week of full-time backend work.** Three parallel tracks (macro CONFIG, AI Analyst greenfield, Portfolio API pipeline) with prod fixes, performance hardening, tests, and documentation.

### What to emphasize (3–4 slides)

1. **Unblocked two frontend surfaces** — Parth can wire Portfolio (holdings/entries/exits/sizing/risk) and Overwatch (`context`, `alerts`, `stream`, chat).
2. **Explicit refusal design** — API returns 422 for unsupported books instead of faking data.
3. **Performance fix** — degradation went from >4 min timeout to <1s with parquet cache.
4. **Macro CONFIG hardened** — B4 windows fixed; Combo D & E promoted with tests.

### What to group or trim

- Macro D4–D6 detail → one slide: "Regime CONFIG hardening + Ahil handoff".
- F4 PARK verdict → one bullet unless audience is macro-focused.
- Test 5 Sharpe uplift → research context, not product delivery.

### What not to over-claim

- Nuxt UI not built (backend only).
- ~45% of Portfolio HANDOFF still blocked on Rohit/Ahil decisions.
- v1.8.1 commits may not be pushed from AWS (credential gap).

---

## Appendix — Open Questions for Rohit

See [`instruction_docs/portfolio_page/OPEN_QUESTIONS_FOR_ROHIT.md`](../instruction_docs/portfolio_page/OPEN_QUESTIONS_FOR_ROHIT.md):

| # | Decision | Blocks |
|---|----------|--------|
| 1 | Production **N** and **notional** ($10M vs $100M) | Slot dollars, position_limit |
| 2 | **Axiom 2** rebalancing in API vs Ahil workbook | `/portfolio/nav`, stable size_usd |
| 3 | **IBKR** spec + owner | `book_id=brokerage` |
| 4 | **v5 SLEEVES** table as production source | D1 slots on `/sizing` |
| 5 | **`same_asset_siblings`** scope (all rows vs negative-only) | Currently all-rows per v5 DEV NOTES |

---

## Appendix — Recommended Next Steps (post-week)

1. Rohit answers open questions → unlock D1 slot engine + `/portfolio/nav`.
2. Ahil completes A1 four-book replay → enable `book=base|ssi|cv`.
3. Parth wires Nuxt to live APIs; removes BFF mocks.
4. Push commits from dev machine; merge `chatbot-dev` → `chatbot-prod`.
5. Install Overwatch cron on prod; smoke test SSE + degradation cache.

---

*Document created: 2026-07-20. For presentation use — week framed as 13–17 July 2026.*
