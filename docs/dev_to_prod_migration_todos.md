# Dev → Prod migration todos

Living checklist for moving **`chatbot-dev`** work from the git clone to **`chatbot-prod`** / production.

**Dev clone:** `/home/ubuntu/uiv2/git/MindWealth_UI` (branch `chatbot-dev`, API `:8507`)  
**Prod clone:** `/home/ubuntu/uiv2/prod/MindWealth_UI` (branch `chatbot-prod`, API `:8506`)  
**Nuxt UI:** `/home/ubuntu/MindwealthUI_Vue` (`:8512`) — **separate repo**, not deployed via `prod-pull-and-restart.sh`

Update this file **after every meaningful dev change** with what to merge, revert, copy, or configure for prod.

Reference deploy skill: `.cursor/skills/prod-pull-and-details/SKILL.md`

---

## Status legend

| Tag | Meaning |
|-----|---------|
| `[PENDING]` | Not yet on prod |
| `[DEV-ONLY]` | Intentional dev shortcut — **revert** before/at prod cutover |
| `[PROD-ACTION]` | Manual step on server after git merge (secrets, systemd, bootstrap) |
| `[DONE]` | Completed on prod (date in notes) |

---

## 2026-07-27 — Sizer `cross_function_exit`/`asset_class`/`status` fields + `_parse_signal_meta` interval fix (HANDOFF §7 / DATA_ISSUES §6, §11 gaps)

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`. Small, self-contained diff (2 service files + 2 test files) — does **not** need to be bundled with anything else, but note it lands on top of the still-`[PENDING]` 2026-07-22/24 entries below (all uncommitted on the same `chatbot-dev` tree as of this entry).

**Context:** analyzed `instruction_docs/portfolio_page/PORTFOLIO_API_HANDOFF_02.md` + `PORTFOLIO_DATA_ISSUES.md` per user request. Confirmed prod (`:8506`) genuinely 404s on `/portfolio/nav`, `/portfolio/holdings`, `/signals/entries`, `/signals/exits` — this is the *real* remaining Overview blocker, but it's a deploy gap (all of it already exists on `chatbot-dev`, most from earlier uncommitted sessions), not a new code change. See job status details 2026-07-27 for the full analysis (incl. why `:8507` "Squid 503" doesn't reproduce, and why the legacy-vs-`d1_slots` position-count issue is a known Rohit-gated decision, not a bug). **This migration entry only covers the two small code fixes actually made in this pass.**

| Path | Notes |
|------|--------|
| `api/services/portfolio_service.py` | new `_ASSET_CLASS_LABELS`, `_asset_class_label()`, `_cross_function_conflict_tickers()`; `sized_row` (backs both `pnl_rows[]` and `clusters[].positions[]`) now carries `cross_function_exit`/`asset_class`/`status` |
| `api/services/portfolio_pipeline_service.py` | `_parse_signal_meta()` interval fallback fix — plain `"Interval"` column now checked (was only compound `"Interval, Confirmation Status"` / lowercase `"interval"`), fixes `implied_natural_exit_date` always being `null` on `/signals/reports/portfolio-risk/latest` |
| `tests/test_api_portfolio.py` | **new** — `test_sizer_pnl_rows_have_cross_function_asset_class_status`, `test_asset_class_label_mapping` |
| `tests/test_api_signals_surface.py` | **new** — `test_parse_signal_meta_reads_plain_interval_column` |

**`[DEV-ONLY]` / runtime secret:** none — no new env vars, no new files outside git.

**Regression `[DONE]` 2026-07-27:**
```bash
.venv/bin/python -m pytest tests/test_api_portfolio.py tests/test_portfolio_backend_engines.py tests/test_api_signals_surface.py -q
# 153 passed
.venv/bin/python -m pytest tests/ -q
# 585 passed, 2 skipped, 1 failed (test_d6_smoke.py — pre-existing, unrelated git-conflict-marker
# SyntaxError in /home/ubuntu/MindWealth/testing.py, a different repo, not touched by this change)
```

**Smoke test `[PENDING]` — run after deploy to `:8506`:**
```bash
curl -s -H "X-API-Key: $KEY" "http://127.0.0.1:8506/api/v1/portfolio/sizer?scenario=normal" \
  | python3 -c "import json,sys; r=json.load(sys.stdin)['pnl_rows'][0]; print(r['cross_function_exit'], r['asset_class'], r['status'])"
# expect: <bool> <non-empty str> Open|Blocked

curl -s -H "X-API-Key: $KEY" "http://127.0.0.1:8506/api/v1/signals/reports/portfolio-risk/latest?book_id=model" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print([op.get('implied_natural_exit_date') for c in d['cross_function_conflicts'] for op in c['open_positions']])"
# expect: at least some non-null dates (was unconditionally all-null before this fix)
```

**Overview unblock — user confirmed, attempted, blocked on push credentials:** user asked to proceed with commit + push + merge + deploy. Committed the full accumulated `chatbot-dev` tree (279 files, commit `6bc1343e6` — includes this entry's 2 fixes plus everything else pending below) and pushed the `docs/mindwealth-api-docs` submodule successfully (`1026c45`, via SSH key `ahiliitb`). **`git push origin chatbot-dev` fails**: HTTPS has no credential helper/PAT configured (`could not read Username for 'https://github.com'`); the available SSH key authenticates as `ahiliitb`, which has push rights to the *legacy* `upstream` remote (`ahiliitb/MindWealth_UI`) but **not** the canonical `origin` (`divsum127/MindWealth_UI`) that prod's clone tracks — `permission denied`. Did not push to the wrong remote as a workaround (would fragment history and not unblock prod either way). **Next action needed from a human:** either (a) provide a valid GitHub PAT with write access to `divsum127/MindWealth_UI` for `chatbot-dev`, or (b) grant the `ahiliitb` deploy key/account write access on that repo, or (c) push commit `6bc1343e6` from a machine that already has working `divsum127` credentials. Once pushed, the merge-to-`chatbot-prod` + `prod-pull-and-restart.sh` steps below are unblocked and low-risk (same commands as every prior release in this file).

### Status: `[PENDING]` — code committed locally (`6bc1343e6`), push to `origin/chatbot-dev` blocked on credentials (2026-07-27)

---

## 2026-07-24 — FMP PE History Fix (replaces Macrotrends fallback, extends the 2026-07-22 "PE neutral" fix above)

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`. **Bundle with the still-pending 2026-07-22 "Fundamental Agent Update" entry above** — this depends on the same `engine.py`/`fundamentals_enriched.py`/`scoring.py` insufficient-history plumbing already staged there.

| Path | Notes |
|------|--------|
| `src/conviction_engine/pe_history_fmp.py` | **new** — `is_us_ticker()`, `fetch_pe_history_fmp()` (FMP `/stable/ratios` fetch, backoff, on-disk cache, `FMP_API_KEY` env-gated no-op) |
| `src/conviction_engine/fundamentals_enriched.py` | wire-in: calls FMP only when yfinance `insufficient_20y=True` + US ticker; tags `pe_history_meta.source` |
| `scripts/set_manual_pe_history.py` | **new** — non-US manual P/E entry CLI (CSV → `conviction_store/{TICKER}.json`, `source="manual"`) |
| `tests/test_pe_history_fmp.py` | **new** — 20 tests (module + wire-in, all mocked, no real network) |
| `tests/test_set_manual_pe_history.py` | **new** — 8 tests incl. full round trip through `daily_update`/`calculate_valuation_tax_components` |
| `.env.example` | **new placeholder** — `FMP_API_KEY=` (commented, with explanation) |

**`[DEV-ONLY]` / runtime secret — not in git:**
- `.env` (local, gitignored) has a commented `# FMP_API_KEY=` placeholder — **not a real key**. A real key must be provisioned separately by a human (free sign-up at financialmodelingprep.com) and added to **both** dev's and prod's `.env` — this is a brand-new runtime secret, not currently present anywhere.
- `conviction_store/pe_history_cache/` — new on-disk cache directory, created lazily on first successful FMP fetch. Not tracked in git (matches `conviction_store/` convention); safe to delete to force a re-fetch.

**`[PROD-ACTION]` at cutover:** add `FMP_API_KEY=` to prod `.env` once provisioned (see smoke test below); no systemd/service changes needed (module only activates on-demand from `full_recalculation`, not a new service).

**Regression `[DONE]` 2026-07-24:**
```bash
.venv/bin/python3 -m pytest tests/test_conviction_engine.py tests/test_api_conviction.py tests/test_pe_history_fmp.py tests/test_set_manual_pe_history.py -q
# 87 passed
.venv/bin/python3 -m pytest tests/ -q
# 560 passed, 2 skipped, 1 failed (test_d6_smoke.py — pre-existing, unrelated git-conflict-marker
# SyntaxError in /home/ubuntu/MindWealth/testing.py, a different repo, not touched by this change)
```

**Smoke test `[PENDING]` — blocked on `FMP_API_KEY` provisioning (human action required, not agent-completable):**
```bash
# 1. Confirm field-name assumption + basic connectivity against a real response:
.venv/bin/python3 -c "from src.conviction_engine.pe_history_fmp import fetch_pe_history_fmp; print(fetch_pe_history_fmp('PYPL', target_years=20))"
# expect: non-None dict, meta['source']=='fmp', meta['point_count']>0

# 2. Full recalc smoke test on PYPL + 2-3 other thin-history US names, confirm:
#    pe_history_meta.source == 'fmp', years_available up from ~0.5 to ~5 (free tier caveat:
#    insufficient_20y will likely STILL be True under PE_HISTORY_TARGET_YEARS=20 — expected,
#    not a bug, see plan's "Data source decision" caveat).
```

**Universe rollout `[PENDING]` — blocked on smoke test above + a business-provided priority non-US ticker list:**
- Once smoke test passes: full recalc across all 121 US tickers (single batch; well under FMP's 250-calls/day free-tier cap since FMP is only called for `insufficient_20y=True` tickers).
- Separately: get a prioritized list of ~15-20 non-US holdings from Rohit/Ahil, source P/E history per ticker from Gurufocus/TIKR/Screener.in, run `python scripts/set_manual_pe_history.py TICKER --csv path/to/pe_history.csv` for each.

**Open product decision carried over (unchanged from 2026-07-22 entry):** FMP's free tier is 5y EOD history, not 20-30y — this improves the worst cases but most tickers will still show `insufficient_20y=True` under the current `PE_HISTORY_TARGET_YEARS=20`. Shipped as the plan's "safe, additive" option; whether to lower the threshold (so a 5y FMP series drives a labeled lower-confidence percentile) or upgrade to FMP's paid Premium plan ($59/mo, true 20-30y) remains an open call for Rohit/Ahil. **Superseded below** — SEC EDGAR now sits ahead of FMP and gets most US tickers to ~15-19y for free with no key at all.

---

## 2026-07-24 — SEC EDGAR PE History pivot (supersedes FMP as primary fallback, same day as entry above)

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`. **Bundle with the still-pending 2026-07-22 "Fundamental Agent Update" and the FMP entry directly above** — same `fundamentals_enriched.py`/`engine.py`/`scoring.py` insufficient-history chain.

User explicitly asked for a free 20-30y solution after learning FMP's free tier caps at 5y. Researched + live-verified SEC EDGAR's own XBRL API (`data.sec.gov`) as the best free option: no key, no daily cap, ~17-19y real depth for large-caps (AAPL/MSFT to FY2007, NVDA to FY2008, PYPL to 2013). Now tried **before** FMP; FMP only runs if SEC returns nothing at all for a ticker.

| Path | Notes |
|------|--------|
| `src/conviction_engine/pe_history_core.py` | **new** — `compute_pe_history()`, `PE_HISTORY_TARGET_YEARS`, `PE_HISTORY_MAX_STORED_POINTS`, `_empty_pe_history_bundle()` extracted out of `fundamentals_enriched.py` (re-exported from there for backward compat) so `pe_history_sec.py` can reuse it without a circular import |
| `src/conviction_engine/pe_history_sec.py` | **new** — `get_cik_for_ticker()` (SEC bulk ticker map, cached), `build_quarterly_eps_series()` (first-filed dedup + Q4-plug reconstruction), `fetch_pe_history_sec()` (no API key needed, just a `User-Agent`) |
| `src/conviction_engine/fundamentals_enriched.py` | rewire: SEC EDGAR tried first when `insufficient_20y=True` + US ticker; FMP now only tried when SEC returns `None` outright |
| `tests/test_pe_history_sec.py` | **new** — 20 tests (dedup, Q4-plug math, CIK caching, mocked fetch paths, all no real network) |
| `tests/test_pe_history_fmp.py` | `TestFundamentalsEnrichedWireIn` rewritten (6 tests) to lock in SEC-first/FMP-only-on-`None` ordering |
| `.env.example` | **new optional var** — `SEC_EDGAR_USER_AGENT=` (module has a working built-in default; override recommended for prod so SEC has a real contact) |

**`[DEV-ONLY]` / runtime secret — not in git:**
- `SEC_EDGAR_USER_AGENT` is **optional** — unlike `FMP_API_KEY`, there is nothing to provision; the module works out of the box. Recommended to set a real contact email before high-volume/production use (SEC's own Fair Access policy asks for a real contact in the User-Agent, not a functional requirement).
- `conviction_store/pe_history_cache/{TICKER}_sec.json` — new cache files alongside the existing `{TICKER}.json` (FMP) ones in the same directory, created lazily. Not tracked in git; safe to delete individually to force a re-fetch for one ticker.

**`[PROD-ACTION]` at cutover:** optionally add `SEC_EDGAR_USER_AGENT=...` to prod `.env` with a real contact (not required — module works with its built-in default). No systemd/service changes needed.

**Regression `[DONE]` 2026-07-24:**
```bash
.venv/bin/python3 -m pytest tests/test_conviction_engine.py tests/test_api_conviction.py tests/test_pe_history_fmp.py tests/test_pe_history_sec.py tests/test_set_manual_pe_history.py -q
# 109 passed
.venv/bin/python3 -m pytest tests/ -q
# 581 passed, 2 skipped, 2 failed (both pre-existing/unrelated: test_d6_smoke.py's
# git-conflict-marker SyntaxError in /home/ubuntu/MindWealth/testing.py, a different repo;
# test_dominant_reason.py::test_live_f_e_reason_contract, a live-data-dependent
# macro_intelligence assertion unrelated to this change -- macro_intelligence/ untouched)
```

**Live smoke test `[DONE]` 2026-07-24 (manual, not part of automated suite — SEC needs no key so this was runnable immediately, unlike the FMP smoke test above):**
```bash
# Ran fetch_pe_history_sec() against the real data.sec.gov API with real yfinance price
# history for AAPL, PYPL, NVDA, MSFT. Results (years_available / eps_quarters):
#   AAPL 17.07y / 71q   PYPL 11.05y / 49q   NVDA 16.22y / 72q   MSFT 18.06y / 75q
# All still insufficient_20y=True under the strict 20y bar (real ceiling: XBRL only
# mandated from ~2009), but a dramatic improvement over the pre-fix yfinance baseline
# (~0.5-2y) and the FMP-only 5y cap.
```

**Universe rollout `[PENDING]` — NOT blocked on external provisioning (unlike the FMP-only plan above); just hasn't been triggered yet:**
- Run `full_recalculation` across all ~121 US tickers. Each ticker makes at most 2-3 SEC EDGAR calls (well within SEC's ~10 req/sec fair-use guidance), plus an FMP call only for the rare ticker SEC can't cover at all (still gated on `FMP_API_KEY`, which remains unprovisioned per the entry above — now lower priority since SEC covers most of the universe).
- Confirm `pe_history_meta.source == "sec_edgar"` lands across most of the US universe and `years_available` is up broadly; spot-check PYPL's `valuation_tax` stays neutral/low (the original bug this whole investigation started from).
- Non-US manual entry track unchanged/still blocked on a business-prioritized ~15-20 ticker list (see FMP entry above) — SEC EDGAR is US-GAAP only, doesn't help non-US tickers.

**Open caveat carried forward:** even with SEC EDGAR, most tickers will still show `insufficient_20y=True` under `PE_HISTORY_TARGET_YEARS=20` (real ceiling ~15-19y for large-caps that existed pre-2009, less for newer listings/spinoffs) — a genuine free 20-30y source does not exist for most companies (XBRL structured data simply didn't exist before ~2009). Whether to lower the threshold to better reflect what's actually achievable for free remains the same open product decision carried over from the previous two entries.

---

## 2026-07-24 — Super Sentiment dashboard layer-score display bug + 3dp precision bump (Nuxt-only, no API/backend change)

`[PENDING]` — **separate Nuxt repo, not this repo's script.** No `MindWealth_UI` files changed.

Two passes same day: (1) fix the 1dp rounding + negative-zero display bug → 2dp, then (2) user
asked to bump readability further → 3dp. Table below reflects the **final** state (3dp); the
intermediate 2dp step is superseded.

| Path (`MindwealthUI_Vue` repo) | Notes |
|------|--------|
| `server/utils/sentiment-mapper.ts` | `roundLayerScore()` 1dp → 2dp → **3dp** (`Math.round(score * 1000) / 1000`); new `formatSignedScore()` helper; `compositeFromApi()` composite display 1dp → 2dp → **3dp** with rounded-then-sign logic |
| `pages/sentiment.vue` | `formatLayerScore()` rounded-then-sign logic, 1dp → 2dp → **3dp** (`.toFixed(3)`, fallback `+0.000`) |

**Root cause (pass 1):** display-only bug, not a calc bug — composite `ssi_level` already
correctly equals the weighted mean of the 3 layer scores (verified `0.4×0.5871 + 0.35×0.0047 +
0.25×(-0.0318) = 0.2285`, matches exactly). 1dp rounding was too coarse to verify by eye, and
rounding a small negative layer score to 1dp could produce JS negative zero (`-0`), which
`score >= 0` treats as non-negative — so Layer 3's genuinely negative z-score showed `+0.0`
instead of `-0.03`.

**Pass 2:** pure readability request ("show upto 3 decimal places, would look better") — no
bug, just bumped 2dp → 3dp on the same 4 fields. The `-0`-safe rounded-then-sign logic from
pass 1 is decimal-place-agnostic and needed no changes.

**`[PROD-ACTION]`** at cutover: `npm run build` + restart the prod Nuxt UI service (whichever
host serves prod `MindwealthUI_Vue` — not `mindwealth-ui-dev`).

**Smoke tests:**
- `[DONE]` 2026-07-24 (pass 1, 2dp) — verified corrected formatting logic against live payload
  numbers via standalone Node script: `composite +0.23`, `layer1 +0.59`, `layer2 +0.00`,
  `layer3 -0.03` (math check: `0.4×0.59 + 0.35×0.00 + 0.25×(-0.03) = 0.2285 ≈ 0.23`, matches).
- `[DONE]` 2026-07-24 (pass 2, 3dp) — same live payload still current, re-verified via Node
  script: `composite +0.229`, `layer1 +0.587`, `layer2 +0.005`, `layer3 -0.032` (math check:
  `0.4×0.587 + 0.35×0.005 + 0.25×(-0.032) = 0.22855 ≈ 0.229`, matches). `npm run build` +
  `mindwealth-ui-dev` restart on `:8514` completed. Full browser verification blocked by
  dev-UI session auth not available in this shell — recommend the user hard-refresh the Super
  Sentiment page to visually confirm.
- `[PENDING]` prod Nuxt UI — same visual check after deploy.

---

## 2026-07-23 — SSI display-rounding policy (SKEW/NH-NL/HYG-LQD/VIX-ratio/DBMF-beta → 2dp)

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`

| Path | Notes |
|------|--------|
| `src/sentiment_superindex/engine/positioning.py` | `_display_decimals()`/`_CURRENCY_PAIR_KEYS` policy; `nh_nl_ratio`/`hyg_lqd`/`vix_ratio`/`dbmf_beta`/CFTC fields now 2dp (was 4dp) |
| `api/services/macro_service.py` | `_round2()` applied to `get_ssi_summary()` and `get_ssi_history()` legacy-input fields |
| `tests/test_ssi_display_rounding.py` | **new** |

**Separate Nuxt repo (`MindwealthUI_Vue`, not deployed via this repo's script):**
- `server/utils/sentiment-mapper.ts` — removed 3/4dp overrides for `nh_nl_ratio`/`hyg_lqd`/`vix_ratio`, vote sub-label now 2dp
- `components/runic/MacroSsiPanel.vue` — `inputRows.raw` now `.toFixed(2)` (was `.toFixed(3)`)
- Nuxt dev already rebuilt + `mindwealth-ui-dev` restarted on `:8514`; **prod Nuxt host needs its own `npm run build` + restart** at cutover

**`[PROD-ACTION]`** after deploy:
- No `ssi.db` backfill needed — rounding is applied at API-response time, not stored data.
- Re-run `scripts/run_ssi_daily.py` (or wait for the daily cron) to refresh `positioning.json` with 2dp values on prod.

**Smoke tests:**
- `[DONE]` 2026-07-23 dev `:8507` — `/analytics/sentiment/layers` and `/macro/ssi/summary` both return 2dp for `nh_nl_ratio`, `hyg_lqd`, `vix_ratio`, `dbmf_beta`, `skew`, `mcclellan`
- `[PENDING]` prod `:8506` — same check after merge/deploy

---

## 2026-07-22 — macro_intelligence Priority-1 audit fixes (T-01 Fed PAUSING, T-03 VIX spike)

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`. No runtime data
migration — pure classification-logic fixes, no backfill of historical `macro_regime_log`/
`daily_readings` rows written under the old buggy logic.

| Path | Notes |
|------|-------|
| `src/macro_intelligence/engine/fed_cycle.py` | `fed_cycle_at_date()` no longer resurrects a stale HIKING/CUTTING label during an active PAUSE |
| `src/macro_intelligence/engine/percentiles.py` | VIX tier escalates on `single_day_pct_change` alone (RARE ≥25%, EXTREME ≥40%) |
| `src/macro_intelligence/data/pull_all.py` | `_single_day_change_meta()` computes prior-close/spike-% for VIX, persisted in `meta_json` |
| `macro_intelligence/CONFIG.yaml` | VIX `rare`/`extreme` blocks gain `single_day_pct_change` thresholds |
| `tests/test_fed_cycle_fixtures.py`, `tests/test_macro_percentiles.py` | new regression tests |

**Smoke test** `[PENDING]`:
```bash
.venv/bin/python -c "from src.macro_intelligence.engine.fed_cycle import fed_cycle_at_date, clear_fed_cycle_cache; clear_fed_cycle_cache(); print(fed_cycle_at_date('$(date +%F)'))"
# expect ('PAUSING', 'FRED_DFF') while the Fed is actually on hold — not a stale CUTTING_LATE/HIKING_LATE
.venv/bin/python -m pytest tests/test_fed_cycle_fixtures.py tests/test_macro_percentiles.py -q   # expect 11 passed
```

### Status: `[PENDING]` merge/deploy only (code + 11 tests verified on dev 2026-07-22)

---

## 2026-07-22 — Daily personal-book snapshot job (`book_id=personal` NAV history)

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`, **then install
the new cron line on prod**.

**New files:**

| Path | Notes |
|------|-------|
| `scripts/run_personal_book_snapshot_daily.py` | Daily job — writes today's personal-book live snapshot to `book_snapshots.db` |

**Modified files:**

| Path | Notes |
|------|-------|
| `src/portfolio_nav/book_snapshot_store.py` | New `personal_book_snapshot_daily` table + write/read/earliest-date functions |
| `api/services/personal_book_service.py` | `get_personal_nav_history()`; `get_personal_nav_payload()` serves real `mtm`/`mtm_daily` once history exists |
| `scripts/install_aws_cron.sh` | Adds `run_personal_book_snapshot_daily.py` at 19:10 ET weekdays |
| `tests/test_portfolio_backend_engines.py`, `tests/test_api_portfolio.py` | new/updated tests |
| `docs/mindwealth-api-docs/services/portfolio/endpoints/personal-book.md` | documents the new history behavior |

### Prod runtime (not in git)

| Item | Action |
|------|--------|
| `portfolio_store/book_snapshots.db` (`personal_book_snapshot_daily` table) | Auto-created by the cron job on first run — starts empty on prod, no backfill possible, same as the model-book snapshot table |
| Cron | **Must re-run** `scripts/install_aws_cron.sh` on prod after merge — this adds a *new* cron line; simply pulling code does not install it |

### systemd / Nuxt

None — no systemd unit edits. `sudo systemctl restart mindwealth-api.service` after pull is sufficient; the cron install is the only extra manual step.

**Smoke test** `[PENDING]`:
```bash
cd /home/ubuntu/uiv2/prod/MindWealth_UI && .venv/bin/python scripts/run_personal_book_snapshot_daily.py   # manual first run so today isn't missed
crontab -l | grep run_personal_book_snapshot_daily   # confirm cron installed
curl -s -H "X-API-Key: $API_KEY" "http://127.0.0.1:8506/api/v1/portfolio/nav?book_id=personal" | jq '.data_status'   # expect live_from_snapshot_start after the manual run above
.venv/bin/python -m pytest tests/test_portfolio_backend_engines.py tests/test_api_portfolio.py -q   # expect 129 passed
```

### Status: `[PENDING]` merge/deploy + cron install (code + 129 tests verified on dev 2026-07-22; live-smoke-tested against dev's own store)

---

## 2026-07-22 — Move `resolve_auto_scenario()` thresholds into `portfolio_policy.yaml`

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`. Zero behavior
change (same threshold values, just relocated) — safe to merge alongside anything else.

| Path | Notes |
|------|-------|
| `config/portfolio_policy.yaml` | New `auto_scenario` block, `status: interim` (not yet Rohit-reviewed) |
| `api/services/policy_service.py` | `get_auto_scenario_thresholds()` / `get_auto_scenario_status()`; added to `policy_meta()` |
| `api/services/portfolio_service.py` | `resolve_auto_scenario()` reads thresholds from policy instead of hardcoding |
| `tests/test_portfolio_backend_engines.py` | new tests incl. a policy-driven-behavior regression |

### Dev-only / revert before prod

None — no dev-only shortcuts; same defaults ship to prod as-is.

**Smoke test** `[PENDING]`:
```bash
curl -s -H "X-API-Key: $API_KEY" "http://127.0.0.1:8506/api/v1/portfolio/sizer?scenario=auto" | jq '.policy_source.auto_scenario_thresholds'   # expect "interim"
.venv/bin/python -m pytest tests/test_portfolio_backend_engines.py -q -k "auto_scenario or AutoScenario"   # expect 6 passed
```

### Status: `[PENDING]` merge/deploy only (code + tests verified on dev 2026-07-22)

---

## 2026-07-22 — `_df_row`/`_df_ttm_sum` sort-order fix (fundamentals TTM/balance-sheet fields)

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`, **then run full
recalc on prod separately** (same pattern as the revenue-growth YoY fix below — this is its
direct follow-up, closing the "Deferred follow-up" item noted in that entry).

| Path | Notes |
|------|--------|
| `src/conviction_engine/fundamentals_enriched.py` | `_df_row()`/`_df_ttm_sum()` sort quarterly columns ascending before `iloc[]` indexing; same fix applied to the prior-year FCF/revenue block (`ocf_row`/`capex_row`/`rev_prior`) |
| `tests/test_conviction_engine.py` | new regression test with an explicit newest-first mock DataFrame |

**Runtime data — NOT in git, must regenerate on prod (not a file copy):**
- After merging the code fix, run on prod: `python3 scripts/run_conviction_engine_daily.py --fundamentals-mode full --overlay-reports virtual_trading_long.csv,virtual_trading_short.csv,new_signal.csv,outstanding_signal.csv`
- Rewrites `conviction_store/*.json` (193 tickers) — do **not** copy dev's files to prod (prod
  fetches its own live yfinance data independently).

**Smoke tests** `[PENDING]`:
- `GET /api/v1/conviction/tickers/AMZN` → `fcf_ttm` should reflect AMZN's real (currently
  negative, AI-capex-driven) TTM free cash flow, not the old ~$7.7B figure from the unsorted bug
- `.venv/bin/python -m pytest tests/test_conviction_engine.py -q` → expect 53 passed

### Status: `[PENDING]` merge/deploy only (code + full recalc verified on dev 2026-07-22)

---

## 2026-07-22 — Portfolio Backend Remaining Build — Phases 0-9

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`. Full 9-phase plan
(`portfolio_backend_remaining_build_ace8e43a.plan.md`) — config layer, D1 sizing, eviction engine,
Axiom 2 rebalance mode, four-book NAV replay, real AUTO/MANUAL scenarios, alerts, regime history,
personal book CRUD. See `docs/mindwealth-api-docs/changelog.md` v1.9.0 for the full change table.

### Git (chatbot-dev → chatbot-prod)

**New files:**

| Path | Notes |
|------|-------|
| `config/portfolio_policy.yaml` | 5 open Rohit decisions, `status: interim\|confirmed` |
| `api/services/policy_service.py` | Policy YAML reader + env overrides |
| `api/services/sizing_engine.py` | D1 NAV/N slot sizing (opt-in, `SIZING_ENGINE_VERSION`) |
| `src/portfolio_nav/eviction_engine.py` | 1C/A2/A3 pure decision functions |
| `src/portfolio_nav/four_book_engine.py` | BASE/SSI/CV/ENHANCED replay + attribution |
| `src/portfolio_nav/book_snapshot_store.py` | SQLite daily book-state/regime/eviction store |
| `scripts/run_portfolio_book_snapshot_daily.py` | Daily snapshot job |
| `api/services/manual_overrides_service.py` | MANUAL scenario $ override CRUD (JSON store) |
| `api/services/personal_book_service.py` | Personal book CRUD + live snapshot (JSON store) |
| `api/services/alerts_service.py` | Cross-page alert aggregator |
| `tests/test_portfolio_backend_engines.py` | 52 new unit tests |
| `docs/mindwealth-api-docs/services/portfolio/endpoints/get-alerts.md` | |
| `docs/mindwealth-api-docs/services/portfolio/endpoints/get-regime-history.md` | |
| `docs/mindwealth-api-docs/services/portfolio/endpoints/manual-overrides.md` | |
| `docs/mindwealth-api-docs/services/portfolio/endpoints/personal-book.md` | |

**Modified files:**

| Path | Notes |
|------|-------|
| `api/services/portfolio_service.py` | D1 sizing branch, `resolve_auto_scenario`, manual dispatch |
| `api/services/portfolio_pipeline_service.py` | `run_eviction_check`, eviction exit-type, `get_regime_history`, personal branch |
| `api/services/portfolio_book.py` | `book_id=personal` allowed on nav/holdings only |
| `api/routers/portfolio.py` | manual-overrides, alerts, regime-history, personal/* routes; `auto\|manual` scenario patterns |
| `src/portfolio_nav/ahil_nav_engine_core.py` | `rebalance_mode`/`n_target` params, `hold_original` logic |
| `src/portfolio_nav/ahil_nav_engine.py` | Policy resolution, real four-book wiring + attribution |
| `src/config_paths.py` | `PORTFOLIO_STORE_DIR`, `BOOK_SNAPSHOTS_DB`, `PERSONAL_HOLDINGS_JSON` |
| `scripts/install_aws_cron.sh` | Adds daily book-snapshot job |
| `.gitignore` | `portfolio_store/`, `config/personal_holdings.json`, `config/manual_sizing_overrides.json` |
| `tests/test_api_portfolio.py` | +22 integration tests |
| `instruction_docs/portfolio_page/OPEN_QUESTIONS_FOR_ROHIT.md` | Ask 3 status note (brokerage still deferred) |
| `instruction_docs/portfolio_page/PORTFOLIO_API_HANDOFF.md` | New §15 status section, §13 checkbox updates |
| `docs/mindwealth-api-docs/changelog.md`, `services/portfolio/README.md`, `endpoints/get-{nav,holdings,sizer,sizing,risk}.md` | v1.9.0 |
| `docs/mindwealth-api-docs/openapi/mindwealth-v1.json` | Re-exported |

### Dev-only / revert before prod

- `SIZING_ENGINE_VERSION` — **not set** (legacy sizing stays default). Leave unset on prod too
  until Rohit confirms SLEEVES table + N (Ask 1/4) — do **not** flip this at cutover by default.
- No other dev-only shortcuts — policy defaults (`hold_original` rebalance, $100M notional unless
  `PORTFOLIO_USE_RESEARCH_NOTIONAL=1`) are the same on dev and prod.

### Prod runtime (not in git)

| Item | Action |
|------|--------|
| `portfolio_store/book_snapshots.db` | Auto-created by the cron job on first run — starts empty on prod, no backfill possible |
| `config/personal_holdings.json` | Auto-created on first personal-book write; empty until a user adds holdings |
| `config/manual_sizing_overrides.json` | Auto-created on first MANUAL override write |
| Cron | Run `scripts/install_aws_cron.sh` (or re-run if already installed) to add the daily book-snapshot job |

### systemd / Nuxt

None — API-only change, no systemd unit edits. `sudo systemctl restart mindwealth-api.service` after pull is sufficient.

### Smoke tests `[PENDING]`

```bash
curl -s -H "X-API-Key: $API_KEY" "http://127.0.0.1:8506/api/v1/portfolio/sizer?scenario=auto" | jq '.auto_resolved_scenario,.auto_resolution_reason'
curl -s -H "X-API-Key: $API_KEY" "http://127.0.0.1:8506/api/v1/portfolio/nav?book_id=model&book=cv" | jq '.data_status'
curl -s -H "X-API-Key: $API_KEY" "http://127.0.0.1:8506/api/v1/portfolio/alerts" | jq '.alert_count'
curl -s -H "X-API-Key: $API_KEY" "http://127.0.0.1:8506/api/v1/portfolio/regime-history" | jq '.data_status'
curl -s -H "X-API-Key: $API_KEY" "http://127.0.0.1:8506/api/v1/portfolio/nav?book_id=personal" | jq '.data_status'
curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: $API_KEY" "http://127.0.0.1:8506/api/v1/portfolio/nav?book_id=brokerage&book=enhanced"   # expect 422
.venv/bin/python -m pytest tests/test_portfolio_backend_engines.py tests/test_api_portfolio.py -q   # expect 124 passed
```

### Status: `[PENDING]` merge/deploy only (code + 124 tests verified on dev 2026-07-22)

---

## 2026-07-22 — Conviction Engine revenue-growth YoY fix + full recalc

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`, **then run full recalc on prod separately**

| Path | Notes |
|------|--------|
| `src/conviction_engine/fundamentals_enriched.py` | `revenue_growth_yoy` / `gross_margin_trend`: sort yfinance quarterly columns ascending before `iloc[]` indexing (previous code assumed oldest-first; yfinance returns newest-first, inverting YoY sign) |

**Runtime data — NOT in git, must regenerate on prod (not a file copy):**
- After merging the code fix, run on prod: `python3 scripts/run_conviction_engine_daily.py --fundamentals-mode full --overlay-reports virtual_trading_long.csv,virtual_trading_short.csv,new_signal.csv,outstanding_signal.csv`
- This rewrites `conviction_store/*.json` (193 tickers), `conviction_store/daily/{date}/*`, `conviction_store/overlays/*` from live yfinance data — do **not** copy dev's `conviction_store/` files to prod (prod fetches its own live data independently, and dev/prod `bq_components` should each reflect their own fetch time).

**Smoke tests** `[PENDING]`:
- `GET /api/v1/conviction/tickers/AMZN` → `bq_raw` ≥ +5 (was +3.5), `bq_components.growth_trajectory` = +2 (was −1)
- `GET /api/v1/conviction/tickers/AAPL` → `bq_raw` ≥ +8 MAX tier (was 0.0 BLOCKED) — this was the most dramatic case, verify carefully post-merge
- Portfolio sizer picks up new tiers on next `update_trade_data.sh` run (VT overlay `max_conviction`/`tactical_plus` counts should rise vs pre-fix baseline)

**Deferred follow-up (not in this change, flagged for later):** `_df_row()` and `_df_ttm_sum()` in the same file have the same unsorted-quarter-order assumption for balance sheet / TTM cashflow fields (net_debt, FCF, EBITDA) — see `docs/mindwealth_ui_repo_job_status_details.md` 2026-07-22 entry for details. Needs a separate fix + recalc pass before it's fully resolved.

---

## 2026-07-22 — Claude shortlist live MTM refresh

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`

| Path | Notes |
|------|--------|
| `src/utils/mtm_pricing.py` | `refresh_dataframe_current_prices()` |
| `api/services/reports_service.py` | `get_shortlist_report()` calls refresh before enrich |
| `tests/test_mtm_pricing.py` | Unit test for stale→live MTM |

**Smoke tests** `[PENDING]`:
- `GET /api/v1/signals/shortlist` — MCHI/TLT/BRK-B `mtm_pct` non-zero; `days_elapsed` > 0
- Nuxt Claude Shortlisted cards show live MTM (not `0.0%` from report date)

---

## 2026-07-22 — Signals KPI counts fix (Nuxt)

`[PENDING]` — rebuild + restart Nuxt UI (`MindwealthUI_Vue`)

| Path | Notes |
|------|--------|
| `MindwealthUI_Vue/pages/signals.vue` | KPI from `/signals/counts`, not filtered table |
| `MindwealthUI_Vue/utils/signal-filters.ts` | `summaryWithCountBucket()` |
| `MindwealthUI_Vue/server/utils/mindwealth-data.ts` | BFF summary + dashboard counts |

**Smoke tests** `[PENDING]`:
- Outstanding + TrendPulse filter: KPI LONG **112**, SHORT **9**; table **55** rows; hint `55 of 121`
- NEW TODAY KPI: **7** (4L / 3S)
- New Signals: LONG **4**, SHORT **3**

---

## 2026-07-22 — New Signals page BFF fix (Nuxt)

`[PENDING]` — rebuild + restart Nuxt UI on host (`MindwealthUI_Vue` separate repo)

| Path | Notes |
|------|--------|
| `MindwealthUI_Vue/server/utils/mindwealth-data.ts` | `loadNewSignals` / `loadOutstandingSignals` use reports API first |

**Smoke tests** `[PENDING]`:
- Nav badge `NEW 7` matches New Signals table row count and KPI cards
- Outstanding Signals table loads when overlay POST unavailable

---

## 2026-07-22 — DRIFT ALERT trigger fix (email spec 5D)

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`

| Path | Notes |
|------|--------|
| `api/services/degradation_service.py` | Monthly-fall drift rules; DRIFT ALERT labels |
| `api/services/analyst_service.py` | Panel label strings |
| `api/services/analyst_copy_service.py` | Claude copy prompt wording |
| `api/routers/signals.py` | `/signals/check-degradation` docstring |
| `tests/test_api_analyst.py` | Drift rule unit tests |

**Smoke tests** `[PENDING]`:
- `GET /api/v1/analytics/analyst/alerts?include_degradation=true` — labels contain `DRIFT ALERT`, not `DEGRADATION`
- Combo with FWD ~70% and BT ~82% should **not** appear in `panel_alerts`
- Cron: `scripts/overwatch/run_overwatch_signals.py` completes; cache refresh

---

## 2026-07-21 — SSI 3-layer superindex composite

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`

| Path | Notes |
|------|--------|
| `src/sentiment_superindex/engine/superindex.py` | **new** — `build_layer1/2/3`, `build_superindex` |
| `src/sentiment_superindex/engine/ssi_score.py` | Composite via superindex |
| `src/sentiment_superindex/engine/positioning.py` | `layers` block; layer1/2/3 raw inputs |
| `src/sentiment_superindex/data/pull_all.py` | CFTC FM/RM/gross_net series |
| `src/sentiment_superindex/data/mcclellan_pull.py` | McClellan formula fix |
| `src/sentiment_superindex/data/sp500_breadth.py` | NH/NL ratio fix |
| `macro_intelligence/SSI_CONFIG.yaml` | 40/35/25 layer weights + inputs |
| `api/services/reports_service.py` | `composite.layers` in sentiment/layers |
| `tests/test_ssi_superindex.py` | **new** |

**`[PROD-ACTION]`** after deploy:
- Run SSI daily job or `build_positioning_payload` to refresh `positioning.json` and `ssi.db` (composite levels will shift).
- Delete stale CSV caches optional: `macro_intelligence/data/ssi/mcclellan_oscillator.csv`, `nh_nl_ratio.csv` (rebuilt on next pull).

**Smoke tests:**
- `[DONE]` 2026-07-21 dev `:8507` — `composite.ssi_level` 0.2173 = weighted layer scores
- `[PENDING]` prod deploy — same check on `:8506`

---

---

## 2026-07-22 — Fundamental Agent Update (conviction engine)

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`

| Path | Notes |
|------|--------|
| `src/conviction_engine/engine.py` | Auto-fetch fundamentals, divergence persistence, PE neutral, FD sizing fix |
| `src/conviction_engine/divergence.py` | **new** — `days_below_high` state |
| `src/conviction_engine/ceo_quality.py` | **new** — TSR vs SPY + new-CEO penalty |
| `src/conviction_engine/capital_allocation.py` | **new** — buyback float scoring |
| `src/conviction_engine/ma_activity.py` | **new** — M&A scan + store flags |
| `src/conviction_engine/db/schema.sql` | **new** — `ma_activity` table (SQLite aux DB) |
| `src/conviction_engine/fundamentals_enriched.py` | PE/FCF cascades, revenue YoY accel, shares TTM |
| `src/conviction_engine/agent_dims.py` | Adversarial moat + reinvestment TAM agent |
| `src/conviction_engine/fd_votes.py`, `scoring.py`, `bq_scoring.py` | FD vote fixes, reinvestment >10× threshold |
| `api/services/conviction_service.py` | `recalculate_ticker` → full enriched fetch |
| `scripts/run_ma_activity_weekly.py` | **new** — weekly M&A cron |
| `tests/test_conviction_engine.py` | `TestJuly2026FundamentalUpdates` |
| `docs/api/services/conviction/*` | API docs July 2026 fields |

**Runtime (prod, not in git):** `conviction_aux.db` created on first M&A scan; optional cron for `scripts/run_ma_activity_weekly.py`.

**Smoke tests `[PENDING]`:**

```bash
curl -s -X POST -H "X-API-Key: $API_KEY" http://127.0.0.1:8506/api/v1/conviction/tickers/PYPL/recalculate | jq '.bq_raw,.conviction_score,.days_below_high,.owner_earnings_yield'
.venv/bin/python -m pytest tests/test_conviction_engine.py tests/test_api_conviction.py -q
```

**Universe backfill `[PENDING]`:** full recalc all conviction tickers after deploy.

**⚠️ 2026-07-24 verification — confirmed live business-impact bug on prod, still `[PENDING]`:**
A stakeholder chat reported "Valuation Tax wrong for all assets, PYPL should be 0" — re-checked directly against `/home/ubuntu/uiv2/prod/MindWealth_UI/conviction_store/` (read-only) and confirmed this is exactly the "PE neutral" fix above, **not yet deployed**: prod PYPL shows `pe_percentile_20y=83.33` (ranked off only 8 points / 0.0–0.56y of history) → `pe_hist_percentile=-2.0` → `valuation_tax=-3.0`; dev PYPL (with the uncommitted fix) shows `pe_percentile_20y=null`, `pe_hist_percentile=0.0`, `valuation_tax=-1.0`. Prod-wide: 35/132 equities show a literal `0.0` percentile, 27 show `100.0`, 34 take the full `-3.0` PE-tax hit — all artifacts of the same insufficient-history ranking bug. `git status` on `chatbot-dev` confirms `engine.py`/`scoring.py` are **still uncommitted** — this fix hasn't even reached git yet, let alone `chatbot-prod`. **Raises priority of this entry** — recommend committing + merging + deploying before the next stakeholder review of conviction output.
- **New side-effect to resolve before/at deploy:** `PE_HISTORY_TARGET_YEARS=20` (`fundamentals_enriched.py`) means almost no yfinance ticker ever has "sufficient" history, so after this fix `pe_percentile_20y` is `None` for ~97% of the dev universe and the PE-percentile tax component fires for only 1 ticker (SONY) store-wide. This stops the false-positive taxing but effectively disables the mechanism for nearly everyone — needs a product decision (accept full neutrality vs. lower the minimum-history bar) before/soon after deploy, not silently shipped as-is without sign-off.
- **2026-07-24 addendum — the real spec'd fix was never built, "null it out" is a stopgap:** `ConvictionEngine_v5_FINAL.pdf` §10.2 explicitly specifies `fetch_pe_history_macrotrends(ticker, slug)`, auto-called inside `full_recalculation` whenever PE history is thin (<20 points) for a US ticker — pulling real multi-year PE history from Macrotrends instead of nulling the percentile. Confirmed **never implemented**: zero hits for `macrotrends`/`fetch_pe_history_macrotrends` anywhere in `src/`; explicitly listed as "Not implemented" in `docs/updates_and_fixes/conviction_engine_v6_updates.md` (table row + "Not done (follow-up)" list) and as an open gap in `/home/ubuntu/.cursor/plans/conviction_engine_v6_b411d996.plan.md` line 47. Recommend prioritizing this before/alongside the prod deploy — implementing the Macrotrends fetch would let most of the universe get a genuine percentile instead of permanent `None`, making the "lower the minimum-history bar" product decision above moot.

---

## 2026-07-22 — Portfolio NAV history (workbook ingest + nav_engine adapter)

`[PENDING]` — merge with portfolio HANDOFF slice above

| Path | Notes |
|------|--------|
| `src/portfolio_nav/` | **new** — workbook provider, engine adapter, stats, service |
| `config/portfolio_nav.yaml` | **new** — $10M research notional, workbook paths, proxy attribution |
| `api/services/portfolio_book.py` | `validate_nav_book_access()` — all MODEL books on `/portfolio/nav` |
| `api/services/portfolio_pipeline_service.py` | Merge history into `get_portfolio_nav()` |
| `tests/test_portfolio_nav.py` | **new** — workbook + stats unit tests |

**Smoke after deploy:**

```bash
curl -s -H "X-API-Key: $API_KEY" "http://127.0.0.1:8506/api/v1/portfolio/nav?book_id=model&book=enhanced" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('mtm',len(d.get('mtm',[])),'vol',d.get('realized_vol_pct'),'source',d.get('nav_series_source'))"
```

**nav_engine:** `[DONE on dev 2026-07-22]` — Ahil script ported; default `/portfolio/nav` source. Daily series: `mtm_daily[]` / `closed_daily[]` (912 trading days when engine active).

**Notional flip prep:** `[PENDING prod]` — set `PORTFOLIO_USE_RESEARCH_NOTIONAL=1` on API host after Rohit sign-off ($10M sizer). Default remains $100M.

**Smoke after deploy:**

```bash
curl -s -H "X-API-Key: $API_KEY" "http://127.0.0.1:8506/api/v1/portfolio/nav?book_id=model&book=enhanced" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('monthly',len(d.get('mtm',[])),'daily',len(d.get('mtm_daily',[])),'source',d.get('nav_series_source'),'notional',d.get('portfolio_notional_usd'))"
```

**Still blocked:** live four-book sizing on holdings/sizer, brokerage/personal, D1 slots.

---

## 2026-07-20 — Portfolio HANDOFF endpoints (unblocked slice)

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`

| Path | Notes |
|------|--------|
| `api/services/portfolio_book.py` | **new** — book_id / valuation-book validation |
| `api/services/portfolio_pipeline_service.py` | **new** — entries, exits, holdings, portfolio-risk HANDOFF adapter |
| `update_trade_data.sh` | **modified** — conviction pipeline now overlays VT long/short + outstanding (not just new_signal) |
| `api/services/portfolio_service.py` | D2 NaN fix + on-demand conviction merge for missing overlay tickers |
| `src/conviction_engine/scoring.py` | Expanded COMMON_ETFS (TLT, MCHI, EFA, bond ETFs) |
| `api/services/signal_enrichment_service.py` | Expose `rr_dynamic` in enrichment output |
| `api/routers/portfolio.py` | `/holdings`, `/sizing` alias, `book_id` on sizer/risk |
| `api/routers/signals.py` | `/entries`, `/exits`, HANDOFF `/reports/portfolio-risk/latest` |
| `tests/test_api_portfolio.py`, `tests/test_api_signals_surface.py` | New endpoint tests |

**Smoke tests after deploy:**

```bash
curl -s -H "X-API-Key: $API_KEY" "http://127.0.0.1:8506/api/v1/portfolio/holdings?book_id=model&book=enhanced" | python3 -c "import sys,json; d=json.load(sys.stdin); print('holdings',len(d.get('holdings',[])))"
curl -s -H "X-API-Key: $API_KEY" "http://127.0.0.1:8506/api/v1/signals/entries?book_id=model" | python3 -c "import sys,json; d=json.load(sys.stdin); print('entries',len(d.get('entries',[])))"
curl -s -H "X-API-Key: $API_KEY" "http://127.0.0.1:8506/api/v1/portfolio/sizer?scenario=normal" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); na=[p for c in d['clusters'] for p in c['positions'] if p.get('not_applicable')]; print('na_count',len(na),'blocked',sum(1 for p in na if p.get('blocked')),'sample',[(p['ticker'],p['allocation_usd']) for p in na[:3]])"
```

**Nuxt follow-up `[DONE on ui-dev branch]`:** `MindwealthUI_Vue` — `conviction n/a` label when `not_applicable`; dev UI on **:8514** (`mindwealth-ui-dev.service`, API **:8507**). Review on ac2 before push/merge to prod UI (:8512).

**Blocked on prod until Rohit/Ahil:** daily NAV from nav_engine, live four-book on holdings/sizer, `book_id=brokerage|personal`, D1 sleeve slots. (`/portfolio/nav` monthly series **unblocked** on dev.)

---

## 2026-07-18 — Portfolio cluster sizing fix

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`

| Path | Notes |
|------|--------|
| `api/services/portfolio_service.py` | Cluster budgets = % of equity ceiling ($80M); split budget across positions by BQ rank weight |
| `tests/test_api_portfolio.py` | `test_sizer_cluster_deployed_within_equity_ceiling` |

**Smoke test after deploy:**

```bash
curl -s -H "X-API-Key: $API_KEY" "http://127.0.0.1:8506/api/v1/portfolio/sizer?scenario=normal" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); cap=round(d['ceiling']['final_ceiling_pct']/100*d['ceiling']['portfolio_notional']); s=sum(c['deployed_usd'] for c in d['clusters']); print('cap',cap,'cluster_sum',s,'ok',s==cap and s==d['summary']['deployed_usd'])"
```

---

## Temporary dev-only config (revert for production)

These are **not** in git on the server; they live in **`/etc/systemd/system/`** and must be corrected when prod auth ships.

| Item | Current (dev testing) | Prod target | Status |
|------|----------------------|-------------|--------|
| Nuxt `NUXT_API_BASE_URL` | `http://127.0.0.1:8507` (dev API) | `http://127.0.0.1:8506` (prod API) | `[DONE]` 2026-07-11 |
| Nuxt systemd `After` / `Wants` | `mindwealth-api-dev.service` | `mindwealth-api.service` | `[DONE]` 2026-07-11 |
| Nuxt `NUXT_PUBLIC_ADMIN_MODE` | `true` | `false` (optional; admin comes from JWT role) | `[DONE]` 2026-07-11 |
| Prod API `:8506` | Still **pre-auth** code (no `X-API-Key` / JWT routes) | Auth-enabled code after merge + pull | `[DONE]` 2026-07-11 |
| Dev API `:8507` | Auth **enabled**, `0.0.0.0`, `.env` with keys | Keep as dev; no change | OK |

**Revert commands (after prod API has auth code):**

```bash
# Edit /etc/systemd/system/mindwealth-ui.service
#   NUXT_API_BASE_URL=http://127.0.0.1:8506
#   After=network.target mindwealth-api.service
#   Wants=mindwealth-api.service
#   NUXT_PUBLIC_ADMIN_MODE=false   # optional

sudo systemctl daemon-reload
sudo systemctl restart mindwealth-api mindwealth-ui
```

---

## 2026-06-30 — Auth & security hardening (invite-only login)

### 1. Git merge (MindWealth_UI)

`[DONE]` 2026-07-11 — merged `1f84f86ad` on `chatbot-prod`, prod pull + restart.

**New files (track in git):**

| Path |
|------|
| `api/routers/auth.py` |
| `api/schemas/auth.py` |
| `api/services/auth_service.py` |
| `api/routers/activity.py` |
| `api/schemas/activity.py` |
| `api/services/activity_log_service.py` |
| `src/auth/streamlit_gate.py` |
| `config/users.json.example` |
| `scripts/bootstrap_admin.py` |
| `scripts/invite_user.py` |
| `tests/test_api_auth.py` |
| `tests/test_activity_log.py` |

**Modified files (merge carefully):**

| Path | Notes |
|------|--------|
| `api/dependencies.py` | `require_api_key`, `get_current_user`, `require_admin`, `require_chatbot_user` |
| `api/main.py` | `auth` + `activity` routers; CORS `:8512`; `DOCS_ENABLED` |
| `api/routers/chatbot.py` | JWT required; session ownership; activity chat log hook |
| `api/services/chatbot_service.py` | Owner-scoped sessions/jobs |
| `chatbot/session_manager.py` | `owner_email` on sessions |
| `app.py` | `ensure_streamlit_login()` gate |
| `requirements.txt` | `bcrypt`, `python-jose[cryptography]`, `email-validator` |
| `scripts/mindwealth-api.service` | `EnvironmentFile=-.../.env`; prod paths in **installed** unit |
| `scripts/mindwealth-api-dev.service` | `EnvironmentFile`; `0.0.0.0:8507` |
| `.gitignore` | `config/users.json`, `activity_logs/` |
| `.env.example` | Auth env var comments |
| `tests/test_api_chatbot.py`, `tests/test_api_conviction.py`, `tests/test_api_integration.py` | API key / auth test fixes |

### 2. Runtime files — copy/create on prod (NOT in git)

`[DONE]` 2026-07-11 — prod `.env` updated; admin bootstrapped `admin@mindwealth.co`; password in `config/.bootstrap_admin_password` (prod only, chmod 600).

| File / dir | Action |
|------------|--------|
| `config/users.json` | **Create** via `scripts/bootstrap_admin.py` on prod (do not copy from dev) |
| `.env` | **Add** vars below to `/home/ubuntu/uiv2/prod/MindWealth_UI/.env` (generate **new** prod secrets or copy policy-approved keys) |
| `activity_logs/` | Auto-created when logging enabled; ensure directory writable |
| `config/.bootstrap_admin_password` | Dev-only helper; **do not** copy to prod |

**Required `.env` keys (prod API):**

```bash
API_KEY=<strong-random>              # same value as NUXT_API_KEY on :8512
JWT_SECRET=<strong-random>
USERS_FILE=config/users.json
INVITE_BASE_URL=http://51.20.53.218:8512
DOCS_ENABLED=false
CHATBOT_REQUIRE_USER=true
JWT_ACCESS_MINUTES=480               # 8h session; match Nuxt cookie
ACTIVITY_LOGS_DIR=activity_logs      # optional override
```

**Streamlit** (`mindwealth-streamlit.service` or env): add `API_KEY`, `MW_AUTH_API_BASE=http://127.0.0.1:8506` after prod auth deploy.

### 3. systemd — prod API

`[DONE]` 2026-07-11 — `prod-pull-and-restart.sh`; health 401 without key, 200 with `X-API-Key`.

- `WorkingDirectory=/home/ubuntu/uiv2/prod/MindWealth_UI`
- `EnvironmentFile=-/home/ubuntu/uiv2/prod/MindWealth_UI/.env`
- `ExecStart` → `0.0.0.0:8506` (already public; now requires `X-API-Key`)

Template in git: `scripts/mindwealth-api.service` (paths in template still point at git clone — **installed prod unit** uses prod paths).

```bash
cd /home/ubuntu/uiv2/prod/MindWealth_UI
bash scripts/prod-pull-and-restart.sh
# or: git pull origin chatbot-prod && .venv/bin/pip install -r requirements.txt && sudo systemctl restart mindwealth-api
```

### 4. Bootstrap prod admin

`[DONE]` 2026-07-11

```bash
cd /home/ubuntu/uiv2/prod/MindWealth_UI
USERS_FILE=config/users.json JWT_SECRET=... .venv/bin/python scripts/bootstrap_admin.py \
  --email admin@mindwealth.co --name "Admin"
```

### 5. Nuxt frontend (`/home/ubuntu/MindwealthUI_Vue`)

`[DONE]` 2026-07-11 — commit `7661255` on `presentation-prod`; Nuxt rebuilt; `mindwealth-ui` → `:8506`.

**Auth-related files to have in Nuxt tree:**

| Path | Purpose |
|------|---------|
| `server/routes/api/v1/[...].ts` | Proxy to FastAPI; JWT cookie on login |
| `composables/useAuth.ts` | Login, session, `useRequestFetch` |
| `middleware/auth.global.ts` | Route protection |
| `plugins/auth-session.ts` | Hydrate session on load |
| `plugins/activity-log.client.ts` | Page/click tracking when enabled |
| `composables/useActivityLog.ts` | Activity batching |
| `pages/login.vue`, `pages/accept-invite.vue`, `pages/admin/users.vue` | Auth UI |
| `components/UserMenu.vue` | Profile + sign out |
| `utils/api-error.ts`, `utils/copy-text.ts` | UX helpers |
| `nuxt.config.ts` | `authSessionMaxAge`, `apiKey`, `apiBaseUrl` |

**Nuxt prod systemd** (`/etc/systemd/system/mindwealth-ui.service`):

```ini
Environment="NUXT_API_BASE_URL=http://127.0.0.1:8506"
Environment="NUXT_API_KEY=<same as prod API_KEY>"
Environment="NUXT_AUTH_SESSION_MAX_AGE=28800"
Environment="NUXT_PUBLIC_ADMIN_MODE=false"
```

```bash
cd /home/ubuntu/MindwealthUI_Vue
npm run build
sudo systemctl restart mindwealth-ui
```

### 6. Post-deploy smoke tests

`[DONE]` 2026-07-11 — all checks pass (401/200 health, login, BFF 401/200, chatbot 401 without JWT).

```bash
# Prod API — key required
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8506/api/v1/health          # expect 401
curl -s -H "X-API-Key: $API_KEY" http://127.0.0.1:8506/api/v1/health                 # expect 200

# Login via Nuxt proxy
curl -s -c /tmp/c.jar -X POST http://127.0.0.1:8512/api/v1/auth/login \
  -H 'Content-Type: application/json' -d '{"email":"...","password":"..."}'
curl -s -b /tmp/c.jar http://127.0.0.1:8512/api/v1/auth/me

# Chatbot requires JWT
curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: $API_KEY" \
  -X POST http://127.0.0.1:8506/api/v1/chatbot/sessions -H 'Content-Type: application/json' -d '{}'  # 401
```

### 7. Security follow-ups (not blocking merge)

| Item | Status |
|------|--------|
| Rotate leaked keys in `MindWealth/constant.py` | `[PENDING]` |
| AWS SG: keep `8506`/`8507` open only with API key | OK |
| Share `API_KEY` with teammates securely for curl testing | `[PROD-ACTION]` |

---

## 2026-06-30 — Per-user activity logging

Bundled with auth deploy above.

| Area | Prod action |
|------|-------------|
| `activity_logging_enabled` on users | Admin toggles on `/admin/users`; stored in `config/users.json` |
| Log storage | `activity_logs/{email_slug}/navigation.jsonl`, `clicks.jsonl`, `chat.jsonl` |
| Nuxt plugin | `activity-log.client.ts` — only sends when `/auth/me` reports logging on |
| Chat logs | Written in `api/routers/chatbot.py` on message enqueue |

No extra prod steps beyond auth deploy + writable `activity_logs/`.

---

## 2026-06-30 — API rate limiting + Nuxt BFF defense-in-depth

Ship **with auth deploy** on prod `:8506`. Limits are identity-aware (`user:{email}` → `apikey:{hash}` → `ip:{ip}`) so Nuxt proxy traffic from `127.0.0.1` is not collapsed into one IP bucket.

### Git (MindWealth_UI — `chatbot-dev`)

`[DONE]` 2026-07-11 — merged with Release A on prod `:8506`.

| Path | Notes |
|------|--------|
| `api/rate_limit.py` | Middleware + slowapi limiter, 429 + `Retry-After` |
| `api/rate_limit_config.py` | Env-backed tier defaults |
| `api/main.py` | `RateLimitMiddleware`, exception handler |
| `requirements.txt` | `slowapi` |
| `tests/test_rate_limit.py` | Burst tests |
| `tests/api_test_helpers.py` | `disable_rate_limits()` for existing suites |
| `.env.example` | `RATE_LIMIT_*` vars |

### Git (Nuxt — `/home/ubuntu/MindwealthUI_Vue`)

| Path | Notes |
|------|--------|
| `server/utils/require-auth.ts` | Cookie gate helper |
| `server/middleware/bff-auth.ts` | 401 on `/api/*` without session (excludes `/api/v1` proxy) |
| `server/middleware/bff-rate-limit.ts` | 100/min per IP on BFF; 5/min on `POST /api/chat` |

Optional Nuxt env:

```bash
NUXT_BFF_RATE_LIMIT_PER_MINUTE=100
NUXT_BFF_CHAT_RATE_LIMIT_PER_MINUTE=5
```

### Prod runtime (not in git)

`[PROD-ACTION]` Add to prod API `.env` (after auth keys):

```bash
RATE_LIMIT_ENABLED=true
# Optional overrides — defaults match plan
RATE_LIMIT_READ_USER=30/10seconds;300/minute
RATE_LIMIT_CHAT_MESSAGES=3/minute;30/hour
RATE_LIMIT_LOGIN_PER_MINUTE=10/minute
```

`[PENDING]` Set `RATE_LIMIT_ENABLED=false` in test/CI only.

### Smoke tests (dev `:8507` + Nuxt `:8512`)

```bash
# Login IP bucket — expect 429 on 6th attempt (email bucket 5/min) or 11th (IP 10/min)
for i in $(seq 1 12); do curl -s -o /dev/null -w "%{http_code}\n" \
  -H "X-API-Key: $API_KEY" -H 'Content-Type: application/json' \
  -d '{"email":"admin@mindwealth.co","password":"wrong"}' \
  http://127.0.0.1:8507/api/v1/auth/login; done

# BFF without cookie — expect 401
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8512/api/dashboard

# BFF with cookie — expect 200 (after browser login)
# curl -b "mw_access_token=..." http://127.0.0.1:8512/api/dashboard
```

### Revert / disable

```bash
# Emergency disable API limits
RATE_LIMIT_ENABLED=false
sudo systemctl restart mindwealth-api-dev   # or mindwealth-api on prod
```

v1 uses **in-memory** counters (single uvicorn worker). Document Redis upgrade if multi-worker later.

### Status: `[DONE]` 2026-07-11 (prod `:8506` + Nuxt BFF on `:8512`)

### Curated commit — Release A (auth + rate limits + test fixes)

**Verified:** `349 passed` pytest on `chatbot-dev` (2026-07-09).

Stage **only** these paths for the prod-bound release (exclude macro combo sweeps, data CSV drift, unrelated WIP):

| Area | Paths |
|------|--------|
| Auth | `api/routers/auth.py`, `api/schemas/auth.py`, `api/services/auth_service.py`, `api/dependencies.py`, `config/users.json.example`, `scripts/bootstrap_admin.py`, `scripts/invite_user.py`, `src/auth/streamlit_gate.py`, `app.py` |
| Activity | `api/routers/activity.py`, `api/schemas/activity.py`, `api/services/activity_log_service.py` |
| Rate limits | `api/rate_limit.py`, `api/rate_limit_config.py`, `config/rate_limits.yaml`, `api/main.py`, `requirements.txt`, `.env.example` |
| Chatbot ownership | `api/routers/chatbot.py`, `api/services/chatbot_service.py`, `chatbot/session_manager.py` |
| Tests | `tests/conftest.py`, `tests/api_test_helpers.py`, `tests/test_api_auth.py`, `tests/test_activity_log.py`, `tests/test_rate_limit.py`, `tests/test_api_chatbot.py`, `tests/test_api_integration.py`, `tests/test_api_conviction.py`, `tests/test_api_macro.py`, `tests/test_api_portfolio.py`, `tests/test_api_signals_surface.py`, `tests/test_combo_c_cancel.py` |
| Bug fixes (ship with release) | `src/config_paths.py` (`load_dotenv(override=False)`), `chatbot/config.py`, `chatbot/smart_data_fetcher.py` (entry_or_exit collapse), `api/services/signal_enrichment_service.py` (`function`/`interval` on enrich) |
| Docs | `docs/dev_to_prod_migration_todos.md`, `.gitignore` (activity_logs, users.json) |
| Systemd templates | `scripts/mindwealth-api.service`, `scripts/mindwealth-api-dev.service` |

**Nuxt** (separate repo `/home/ubuntu/MindwealthUI_Vue`): commit `server/utils/require-auth.ts`, `server/middleware/bff-auth.ts`, `server/middleware/bff-rate-limit.ts`, then `sudo systemctl restart mindwealth-ui`.

**Do not stage** for this release unless intentional: `macro_intelligence/data/*`, `monitored_trades.json`, `testing/combo_all_thresholds/`, macro calendar scripts unless already merged separately.

### Merge order

1. Commit Release A on `chatbot-dev` → push
2. Merge `chatbot-dev` → `chatbot-prod`
3. Prod clone: `git pull` + `prod-pull-and-restart.sh`
4. Prod `.env`: `API_KEY`, `JWT_SECRET`, `RATE_LIMIT_ENABLED=true`
5. Bootstrap `config/users.json` on prod
6. Nuxt: commit BFF middleware → restart `mindwealth-ui` → revert `NUXT_API_BASE_URL` to `:8506`
7. Smoke tests (login, BFF 401, rate-limit curl in section above)

---

## 2026-07-21 — Combo D fed-cycle slices (QE n=9 USE)

### Git (chatbot-dev → chatbot-prod)

**Modified files:**
- `macro_intelligence/CONFIG.yaml` — `combo_hit_rates.D.fed_cycle_slices` (min_episodes=9, validated CUTTING_LATE/HIKING_LATE/QE @ 1W/2W)
- `src/macro_intelligence/engine/combo_metadata.py` — `combo_fed_cycle_slice_stats()`
- `api/services/macro_service.py` — `fed_cycle_slices` on `get_combo_detail`
- `tests/test_combo_metadata.py`

### Dev-only / revert before prod

None.

### Prod runtime

None — CONFIG + API field ship with git merge.

### Smoke tests `[PENDING]`

- [ ] `GET /api/v1/macro/combos/D` → `fed_cycle_slices.slices` includes QE with `verdict: USE`, 1W hit_rate 0.4444, avg_return 0.649
- [ ] Combo B/E detail → `fed_cycle_slices` null/absent

---

### Git (chatbot-dev → chatbot-prod)

**Modified files:**
- `src/macro_intelligence/engine/regime_v2_shadow.py` — `fed_cycle_v2_analytics`, `collapse_liquidity_v2_analytics`, `regime_value_for_analytics`
- `src/macro_intelligence/analysis/regime_experiments/metrics.py` — analytics collapse in `slice_by_regime`
- `src/macro_intelligence/analysis/regime_experiments/fm_events.py` — analytics fed labels
- `src/macro_intelligence/engine/combo_metadata.py` — min-n guard, `insufficient episodes` display
- `macro_intelligence/CONFIG.yaml` — `combo_hit_rates.C.min_episodes_for_hit_rate: 5`
- `tests/test_regime_v2_experiments.py`, `tests/test_combo_metadata.py`

**Research / verification (new):**
- `testing/macro_th_exp/run_d6_regime_analytics_reslice.py`
- `testing/macro_th_exp/run_d6_smoke_tests.py`
- `testing/macro_th_exp/D6_regime_analytics_2026-07-17.{md,json}` + 4 CSVs
- `testing/macro_th_exp/D6_smoke_tests_2026-07-17.{md,json}`

### Dev-only / revert before prod

None.

### Prod runtime

None — CONFIG change ships with git merge.

### Smoke tests `[DONE]` 2026-07-17

- [x] Combo C: `combo_hit_rate_stats` + briefing rows show `insufficient episodes` (n=3 at 6M, min=5)
- [x] API `macro_service.get_combo_detail('C')` → `insufficient_episodes: true`
- [x] FM `fed_cycle_v2` slice: no PIVOTING bucket; liquidity analytics ≤4 buckets
- [x] Artifacts: `testing/macro_th_exp/D6_smoke_tests_2026-07-17.{md,json}`

### Regime re-slice `[DONE]` 2026-07-17

- [x] `run_d6_regime_analytics_reslice.py` — PIVOTING n=27 merged into EASING; 9→4 liquidity
- [x] CSVs: `D6_fm_regime_slices_analytics_2026-07-17.csv`, `D6_combo_fed_cycle_analytics_2026-07-17.csv`, `D6_liquidity_*_2026-07-17.csv`

### Status: `[PENDING]` merge/deploy only (code + smoke on dev)

---

## 2026-07-17 — B4 window fix (HY/VIX/VXTS → rolling_3y)

### Git (chatbot-dev → chatbot-prod)
- [ ] Modified: `macro_intelligence/CONFIG.yaml` (`pctile_window` for HY, VIX, VXTS → `rolling_3y`)
- [ ] New: `testing/macro_th_exp/run_b4_window_fix_pipeline.py`
- [ ] New: `testing/macro_th_exp/B4_window_fix_pipeline_2026-07-17.{md,json}`
- [ ] New: `macro_intelligence/analysis/regime_v2_experiments/threshold_sweep_v2_b4_fix/*`
- [ ] Modified: `macro_intelligence/analysis/regime_v2_experiments/B_twy_and_percentiles.json`

### Dev-only / revert before prod
- None — intentional CONFIG alignment to original B4 spec.

### Prod runtime (not in git)
- [ ] After deploy: nightly run will use rolling_3y pctiles for HY/VIX/VXTS (ranks may shift vs pre-fix prod)
- [ ] Optional: one-time `run_b4_window_fix_pipeline.py` recompute on prod DB if shadow/backfill DB diverges

### Smoke tests `[PENDING]`
- [ ] `B4_window_audit` pass=true in Part B JSON
- [ ] Combo B/D detector still fires on recent dates with new pctile ranks
- [ ] Briefing HY/VIX/VXTS pctile columns reflect rolling_3y window

### Status: `[PENDING]` merge/deploy

---

## 2026-07-17 — Combo E BEST PRODUCTION SCORE + CFTC escalation alert

### Git (chatbot-dev → chatbot-prod)
- [ ] Modified: `macro_intelligence/CONFIG.yaml` (E: CAPE≥32, NFCI≤−0.15, CFTC≥85, min_of_three=3 + escalation keys)
- [ ] Modified: `src/macro_intelligence/engine/combo_detector.py`, `dominant.py`, `jobs/nightly_run.py`
- [ ] Modified: `src/macro_intelligence/output/briefing_renderer.py`, `claude/nightly_briefing.py`
- [ ] Modified: `api/services/macro_service.py` (E cheatsheet)
- [ ] New: `tests/test_combo_e_thresholds.py`

### Dev-only / revert before prod
- None — intended production gate change.

### Prod runtime (not in git)
- None for thresholds (CONFIG is in git). Optional: replay named-combo backfill so `combo_fires` / hit rates reflect new E gates.

### systemd / Nuxt
- [ ] After merge: `bash scripts/prod-pull-and-restart.sh` (or pip + `systemctl restart mindwealth-api.service`)

### Smoke tests `[PENDING]`
- [ ] Nightly / `detect_named_combos`: E only ACTIVE at 3/3 with new gates; 2/3 → WATCH
- [ ] With rising CFTC pctile history: status `ESCALATION_ALERT` + duration note
- [ ] API combo E cheatsheet shows 3-of-3 / CAPE 32 / NFCI −0.15 / CFTC 85

### Status: `[PENDING]`

---

## 2026-07-17 — Combo D BEST PRODUCTION SCORE + 2-of-3

### Git (chatbot-dev → chatbot-prod)
- [ ] Modified: `macro_intelligence/CONFIG.yaml` (D: VXTS≥1.18, CFTC≥95, VIX≤13, min_of_three=2; hit_rates D secondary spx_2w, E secondary spx_6m)
- [ ] Modified: `src/macro_intelligence/engine/combo_detector.py` (true 2-of-3 ACTIVE/WATCH)
- [ ] Modified: `src/macro_intelligence/claude/nightly_briefing.py`, `api/services/macro_service.py`
- [ ] New: `tests/test_combo_d_thresholds.py`

### Dev-only / revert before prod
- None.

### Prod runtime (not in git)
- Optional: replay D combo_fires backfill under new gates for hit-rate tables.

### systemd / Nuxt
- [ ] Same restart as E promotion above.

### Smoke tests `[PENDING]`
- [ ] D ACTIVE on any 2 of {VXTS≥1.18, VIX≤13, CFTC≥95}; WATCH at 1 leg
- [ ] Legacy-loose readings (VXTS 1.12 / VIX 17 / CFTC 86) do **not** fire D
- [ ] Briefing / API cheatsheet show new D gates + 1W primary

### Status: `[PENDING]`

---

## 2026-07-18 — AI Analyst backend (Overwatch)

### Git merge (`chatbot-dev` → `chatbot-prod`) `[PENDING]`

**New files:**

| Path |
|------|
| `api/schemas/analyst.py` |
| `api/services/analyst_service.py` |
| `api/services/system_health_service.py` |
| `api/services/overwatch_event_bus.py` |
| `api/routers/overwatch.py` |
| `api/routers/system.py` |
| `scripts/overwatch/run_overwatch_signals.py` |
| `scripts/overwatch/run_overwatch_macro.py` |
| `scripts/overwatch/run_overwatch_system.py` |
| `api/services/degradation_cache.py` | Parquet + result cache |
| `api/services/integration_health_store.py` | Tavily/Sheets markers |
| `api/services/analyst_copy_service.py` | Optional Claude copy |
| `tests/test_degradation_cache.py` | Cache perf tests |

**Modified files:**

| Path | Notes |
|------|--------|
| `api/services/degradation_service.py` | 60% watch/breach + weekly trend |
| `api/routers/analytics.py` | `/analyst/alerts`, `/analyst/brief` |
| `api/routers/signals.py` | Docstring aligned to spec |
| `api/main.py` | v1.8.0, register overwatch + system routers |
| `api/rate_limit.py` | SSE + system health rate rules |
| `src/macro_intelligence/output/json_writer.py` | `historical_analogs` block |
| `scripts/install_aws_cron_dual.sh` | Overwatch cron lines |
| `.gitignore` | `overwatch_store/` |
| `docs/api/openapi/mindwealth-v1.json` | OpenAPI export |
| `docs/mindwealth-api-docs/` | v1.8.2 portfolio HANDOFF docs — **pushed `1efaa09` 2026-07-22** |
| `api/routers/portfolio.py`, `portfolio_pipeline_service.py`, etc. | v1.8.2 portfolio HANDOFF — commit `2531daf9a` **local only** (push blocked) |
| `docs/api/changelog.md` | v1.8.0 entry |

### Prod runtime `[PROD-ACTION]`

| Item | Action |
|------|--------|
| `overwatch_store/alert_state.json` | Create `{}` on first deploy (auto-created by cron) |
| `.env` | Confirm `MINDWEALTH_TRADE_STORE`, `ANTHROPIC_API_KEY`, `TAVILY_API_KEY` |
| `config/users.json` | Admin JWT for SYSTEM tab |

### systemd `[PROD-ACTION]`

| Service | Change |
|---------|--------|
| `mindwealth-api.service` | Ensure **1 worker** (in-process SSE bus) |
| `mindwealth-api-dev.service` | Same |

### Cron `[PROD-ACTION]`

```bash
bash scripts/install_aws_cron_dual.sh
```

Adds: signals daily 19:00 ET, macro 18:30 ET Mon–Fri, system every 15m.

### Smoke tests `[PENDING]`

```bash
curl -s -H "X-API-Key: $KEY" http://127.0.0.1:8506/api/v1/analytics/analyst/alerts | jq '.count'
curl -s -H "X-API-Key: $KEY" -H "Authorization: Bearer $JWT" http://127.0.0.1:8506/api/v1/system/health | jq '.checks[].status'
curl -N -H "X-API-Key: $KEY" http://127.0.0.1:8506/api/v1/overwatch/stream
```

### Nuxt follow-up (separate repo)

- Point BFF `overwatch.get.ts` at `GET /analytics/analyst/alerts`
- Switch `useOverwatch.ts` to SSE proxy

### Status: `[PENDING]`

---

## Template for future entries

Copy for each new dev feature:

```markdown
## YYYY-MM-DD — Short title

### Git (chatbot-dev → chatbot-prod)
- [ ] New files: ...
- [ ] Modified files: ...

### Dev-only / revert before prod
- [ ] ...

### Prod runtime (not in git)
- [ ] `.env` keys: ...
- [ ] `config/...` create/copy: ...
- [ ] Bootstrap/migration scripts: ...

### systemd / Nuxt
- [ ] ...

### Smoke tests
- [ ] ...

### Status: [PENDING] | [DONE] YYYY-MM-DD
```

---

## Change log (this document)

| Date | Change |
|------|--------|
| 2026-07-27 | Sizer `pnl_rows`/`positions` gained `cross_function_exit`/`asset_class`/`status`; fixed `_parse_signal_meta` interval bug that made `implied_natural_exit_date` always `null` |
| 2026-07-22 | Fundamentals `_df_row`/`_df_ttm_sum` sort-order fix (TTM revenue/FCF/EBITDA/debt) + full 193-ticker recalc |
| 2026-07-22 | Moved `resolve_auto_scenario()` (D4 AUTO) thresholds into `portfolio_policy.yaml` |
| 2026-07-22 | Daily personal-book (`book_id=personal`) snapshot job — starts real NAV history going forward |
| 2026-07-22 | macro_intelligence Priority-1 audit fixes: Fed cycle PAUSING resurrection bug (T-01), VIX single-day spike detection (T-03) |
| 2026-07-22 | Portfolio Backend Remaining Build (Phases 0-9): policy config, D1 sizing, eviction engine, Axiom 2 rebalance, four-book NAV replay, AUTO/MANUAL scenarios, alerts, regime history, personal book CRUD |
| 2026-07-18 | AI Analyst backend: analyst alerts, system health, SSE, overwatch cron |
| 2026-07-16 | D6: analytics collapse helpers + Combo C min-n guard (`insufficient episodes`) |
| 2026-07-11 | Release A prod deploy: merge `chatbot-prod` `1f84f86ad`, prod env/bootstrap, Nuxt BFF `7661255`, smoke tests |
| 2026-06-30 | Initial auth + activity logging migration checklist; documented Nuxt → `:8507` dev shortcut |
