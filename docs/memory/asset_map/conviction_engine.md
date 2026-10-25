# Conviction engine — asset map

**Last verified:** 2026-10-25

Where every doc, module, script, store and test for the conviction engine lives,
and — the point of this file — **which of them is still true**.

Feature hub: [`docs/instruction_docs/conviction_engine_issues/_HUB.md`](../../instruction_docs/conviction_engine_issues/_HUB.md)

---

## 0. Read order (do not wander — start here)

1. [`docs/instruction_docs/conviction_engine_issues/rohit_1sep_corrections.md`](../../instruction_docs/conviction_engine_issues/rohit_1sep_corrections.md)
   — **read this first.** It corrects statements that are wrong in the older
   notes and in things we told Rohit. Anything it contradicts, it wins.
2. [`docs/instruction_docs/conviction_engine_issues/conviction_fixes_decisions.md`](../../instruction_docs/conviction_engine_issues/conviction_fixes_decisions.md)
   — what was decided and why, including the micro-decisions. Supersedes the
   open-questions file below.
3. [`docs/instruction_docs/conviction_engine_issues/conviction_fixes_open_questions.md`](../../instruction_docs/conviction_engine_issues/conviction_fixes_open_questions.md)
   — historical. Every question in it now has an answer in the decisions log.
4. `src/conviction_engine/engine.py` — the actual scoring path.

**Conflict rule:** `docs/instruction_docs/conviction_engine_issues/rohit_1sep_corrections.md`
> `docs/instruction_docs/conviction_engine_issues/conviction_fixes_decisions.md` > the 28 July
> consolidated note > `docs/instruction_docs/conviction_engine_issues/ce_developer_spec_latest.html`
> > anything else.
The HTML specs are illustrative mocks, not contracts.

---

## 1. Spec sources (what was asked)

| File | What it is | Trust |
|---|---|---|
| `docs/instruction_docs/conviction_engine_issues/Conviction_Engine_Consolidated_Note_Divyanshu_2026-07-28.docx` | The 11-page consolidated note. This is the "third document" Rohit thought was missing — it was attached to his own mail and has been in this folder since 29 July | Current, except §5.7 (see corrections doc §1) |
| `docs/instruction_docs/conviction_engine_issues/Divyanshu_Business_Type_Reply 30 July_conviction doubts.pdf` | Rohit's answers to our 11 open questions, plus a live-dashboard bug report | Current, except the flat Price/Book table (superseded — decisions §2) |
| `docs/instruction_docs/conviction_engine_issues/FS_Slice_Followup_Divyanshu.docx.pdf` | FS-score slice spec + 2 corrections to the 30 July reply | Current |
| `docs/instruction_docs/conviction_engine_issues/ConvictionEngine_v6_Internal.pdf` | Internal v6 write-up | **There is no v6 *document*** — v6 exists only in code. Do not promise Rohit a v6 doc (corrections §3) |
| `docs/instruction_docs/conviction_engine_issues/ce_developer_spec_latest.html` | Developer spec | Illustrative |
| `docs/instruction_docs/conviction_engine_issues/engine_layers_spec.html` | UI layer mock | Illustrative only — never a contract |

---

## 2. Status docs (what we concluded)

| Doc | Covers | Trust |
|---|---|---|
| `docs/instruction_docs/conviction_engine_issues/rohit_1sep_corrections.md` | Six corrections + the open/needs-purchase list | **Authoritative** as of 2026-09-01 |
| `docs/instruction_docs/conviction_engine_issues/conviction_fixes_decisions.md` | Rohit's 11 answers, the P/TBV supersession, FS-slice build, CRM dashboard bug, Macrotrends skip, micro-decisions, still-deferred list | Current |
| `docs/mindwealth_ui_job_status.md` | 19 entries classified to this feature; the four most recent are 2026-08-27 → 2026-09-03 | Current |
| `docs/mindwealth_ui_repo_job_status_details.md` | Assumptions, deferred items and caveats per entry | Current |

---

## 3. The five things most likely to be misremembered

| Claim you may have read | What is actually true | Source |
|---|---|---|
| "v6 already runs CEO quality, moat, macro tailwind, deal delay, reinvestment runway" | The code exists and is wired, but `skip_agent_dims` defaults to skipping. `CONVICTION_RUN_AGENT_DIMS=1` was set nowhere, so **all 196 stored records carried 0.00 on all five** | corrections §2 |
| "There is a v6 spec document" | There is not. v6 is code only. Rohit raised it on WhatsApp then self-corrected | corrections §3 |
| "The income / utility bucket works unchanged" | Wrong when written. `income`, `compounder`, `cyclical` and `unknown` all fall through to EV/Revenue tiers calibrated on SaaS. MCY.NZ and SPK.NZ both showed an entry-multiple tax of 0.00 | corrections §1 |
| "The hardware margin threshold is 50%" | It shipped at **40%** trailing TTM net margin | corrections §5 |
| "Telcos and utilities are capped at +4" | Since 24 Sep they are **not scored**: `telco`, `regulated_utility`, `holding_company` → COVERAGE INCOMPLETE, 0%. Renewable / IPP utilities stay `income` with the +4 cap | `config/conviction_business_type_overrides.json`, `scoring.detect_business_type` (2026-10-25) |
| "P/E percentile needs 20 years" | Tiers: 20y+ full, 10–20y provisional (scored, labelled), under 10y or no metadata neutral | `pe_history_core.pe_history_confidence` (2026-10-25) |
| "The payload carries pe_ttm / pe_ttm_adjusted" | Not until 2026-10-25: the overlay CSV is built from `SignalModification`, which lacked them | `engine._payload_fields` |
| "Rohit owes us a third document" | He does not. It is the 28 July note, byte-identical to our copy, already in this folder | `docs/instruction_docs/conviction_engine_issues/_HUB.md` decisions ledger |

---

## 4. Production code

| Module | Role |
|---|---|
| `src/conviction_engine/engine.py` | Orchestrates a ticker's score; PE neutrality on insufficient history; divergence; auto-fetch |
| `src/conviction_engine/scoring.py` | Valuation tax, conviction total, verdict tiers |
| `src/conviction_engine/bq_scoring.py` | The 15 BQ sub-components |
| `src/conviction_engine/fundamentals.py`, `src/conviction_engine/fundamentals_enriched.py` | Raw pull and the P/E, FCF and shares cascades |
| `src/conviction_engine/adjusted_eps.py`, `src/conviction_engine/adjusted_eps_sources.py` | Adjusted-EPS coverage |
| `src/conviction_engine/dividend_series.py`, `src/conviction_engine/dividend_yield.py` | Dividend cadence and yield-trap basis |
| `src/conviction_engine/bank_valuation.py` | Bank slice — P/TBV vs ROE (supersedes the flat Price/Book table) |
| `src/conviction_engine/agent_dims.py` | Moat, macro tailwind, reinvestment runway — model-backed, **off by default** |
| `src/conviction_engine/ceo_quality.py`, `src/conviction_engine/capital_allocation.py` | Dimensions 8 and 9 |
| `src/conviction_engine/fd_votes.py` | FD votes; sizing applied once, in `verdict_for_buy` |
| `src/conviction_engine/divergence.py` | `days_below_high`, bootstrapped from price history on first full recalc |
| `src/conviction_engine/ma_activity.py` | M&A search, confidence ≥ 0.7 |
| `src/conviction_engine/pe_history_core.py` | Shared P/E-history plumbing |
| `src/conviction_engine/pe_history_sec.py`, `src/conviction_engine/pe_history_sec_legacy.py` | SEC EDGAR path, plus the pre-2009 legacy-filing extension |
| `src/conviction_engine/pe_history_fmp.py` | FMP path — kept as fallback; paid-gated at 5y |
| `src/conviction_engine/data_coverage.py` | Framework-coverage flag — caps conviction where no module exists |
| `src/conviction_engine/tam_sourcing.py` | TAM for reinvestment runway |
| `src/conviction_engine/store.py`, `src/conviction_engine/db/connection.py`, `src/conviction_engine/db/schema.sql` | Per-ticker JSON store + the SQLite aux DB |
| `config/conviction_business_type_overrides.json` | Reviewed per-ticker business types (SBUX, SFTBY), read on every classification so they reach prod by merge |
| `src/conviction_engine/backtest.py`, `src/conviction_engine/daily_run.py`, `src/conviction_engine/dispatch.py` | Backtest, nightly run, routing |

**Serving surface:** `api/routers/conviction.py` → `api/services/conviction_service.py`
(incl. `GET /conviction/lookup/{ticker}`, never writes the store). Nuxt: `/home/ubuntu/MindwealthUI_Vue/pages/conviction/index.vue`,
`/home/ubuntu/MindwealthUI_Vue/components/conviction/`,
`/home/ubuntu/MindwealthUI_Vue/server/utils/mindwealth-data.ts` (`mapVerdict`, `tickerToDetail`).

---

## 5. Scripts

| Script | What it does |
|---|---|
| `scripts/run_conviction_engine_daily.py` | Nightly recalculation |
| `scripts/update_conviction_fundamentals.py` | Refresh fundamentals for the universe |
| `scripts/run_ma_activity_weekly.py` | Weekly M&A scan — needs `ANTHROPIC_API_KEY` for agent hits |
| `scripts/backtest_conviction_signals.py` | Backtest harness |
| `scripts/conviction_coverage_report.py` | Which tickers have which dimensions |
| `scripts/report_pe_history_coverage.py` | P/E-history depth per ticker — run this before quoting any percentile claim |
| `scripts/set_manual_pe_history.py` | Manual override for a ticker's P/E history |
| `scripts/dividend_cut_diff_report.py` | Dividend-cut diff for Rohit's approval — same `declared_annual_dividends()` the engine scores with |
| `scripts/conviction_store_diff.py` | Before/after diff of two store snapshots (G3 change list) |
| `scripts/conviction_universe_export.py` | G1 P/E + adjusted-EPS CSV and G2 empty-statement report |
| `scripts/conviction_agent_pilot.py` | Metered agent-dimension model comparison with a hard USD cap |

---

## 6. Data and stores

| Path | What | Note |
|---|---|---|
| `conviction_store/` | One JSON per ticker — the scored record the API serves | Runtime data, refreshed nightly |
| `src/conviction_engine/db/schema.sql` | `ma_activity` table DDL | SQLite (`conviction_aux.db`), **not** the PostgreSQL the spec asked for — same pattern as macro/SSI |

---

## 7. Tests

| File | Covers |
|---|---|
| `tests/test_conviction_engine.py` | Engine, BQ dims, `TestJuly2026FundamentalUpdates` |
| `tests/test_conviction_engine_v2_fixes.py` | The v2 fixes pass |
| `tests/test_api_conviction.py` | API contract |
| `tests/test_conviction_business_type_overrides.py`, `tests/test_conviction_pe_history_tiers.py`, `tests/test_conviction_dividend_specials.py`, `tests/test_conviction_payload_fields.py`, `tests/test_conviction_agent_request.py`, `tests/test_api_conviction_lookup.py` | 2026-10-25 changes |

```bash
.venv/bin/python -m pytest tests/test_conviction_engine.py tests/test_conviction_engine_v2_fixes.py tests/test_api_conviction.py -q
```

---

## 8. Traps

- **A P/E percentile computed off sparse points is not a history percentile.**
  PYPL ranked 83.33 off ~0.56 years of yfinance EPS and took the full −3.0 tax.
  Resolved 2026-10-25 by the tiers (under 10y → neutral). Also fixed: a stale
  `pe_history_insufficient=True` used to survive recalcs and kept the P/E tax off
  full-history names (AAPL, WMT, SBUX) — the flag is now set both ways.
- **Prod still has the old data.** Prod PYPL showed `last_full_recalc=None` on 2026-10-25;
  only an ops-run recalc fixes prod numbers.
- **"Fixed on dev" is not fixed.** The July-22 P/E fix sat uncommitted on
  `chatbot-dev` while prod kept serving the bug, and Rohit reasonably read that as
  "still broken". Check `docs/memory/PROD_QUEUE.md` before claiming any conviction
  fix is live.
- **The agent dimensions are off.** If a stored record shows 0.00 on moat / CEO /
  macro tailwind / reinvestment, that is the default switch, not a real score.
- **EV/Revenue is not a universal fallback.** Only bank, high-margin hardware and
  SaaS have purpose-built modules. Everything else lands on SaaS-calibrated tiers
  where the tax contributes almost nothing.
- **Dividend years are built by covered period**, specials excluded
  (`dividend_series.declared_annual_dividends`, 2026-10-25). Median-gap cadence
  is no longer used by the engine. A cut touching an unclassified outlier or a
  data gap is held, not scored.
- **The nightly Claude report reads the DEV store's overlays**
  (`/home/ubuntu/MindWealth/send_email.py:140`), so a dev recalc reaches Rohit's email.

---

## 9. Open decisions

Live in the hub's own tables — see the **Open questions** section of
[`_HUB.md`](../../instruction_docs/conviction_engine_issues/_HUB.md). Short version:
the C2 dividend period-attribution work and item D (point-in-time trailing EPS)
both likely need a **paid data provider**, and Rohit asked us to come back with a
shortlist and a price before he decides. The capital-intensive telco/utility
valuation spec is one he said he is writing; the framework-coverage flag caps
conviction meanwhile.

---

## 10. Coordinates outside the repo

| What | Where |
|---|---|
| Chat — 26 Aug implementation review (15 prompts) | `claude --resume 88dac147` |
| Chat — 1 Sep "share v6" WhatsApp follow-up | `claude --resume b2fcc1d0` |
| Mail — Rohit's 1 Sep reply | `msg:1a05bedfe8ea89a8` (the 28 July note is its attachment) |
| Prod queue | `docs/dev_to_prod_migration_todos.md` — conviction blocks pending since 27 Aug; prod on the 20 Aug merge |
| Job status | `docs/mindwealth_ui_job_status.md` — latest conviction entries 2026-10-25 |
| Sheet | `mindwealth todos` → tab `conviction` (51 CE rows); pending-write log `docs/instruction_docs/conviction_engine_issues/conviction_sheet_pending_updates.md` |
