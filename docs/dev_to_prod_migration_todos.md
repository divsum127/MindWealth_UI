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

## 2026-08-18 — AI Analyst panel: audit defects FIXED on dev, awaiting prod cutover `[PENDING]`

**Committed + pushed 2026-08-18** (all as `divsum127`):

| Repo | Branch | SHA | Remote |
|------|--------|-----|--------|
| MindWealth_UI | `chatbot-dev` | `d624be4cf` | `divsum127/MindWealth_UI` |
| `docs/mindwealth-api-docs` | `main` | `1a4e0ac` | `divsum127/mindwealth-api-docs` |
| MindwealthUI_Vue | `ui-dev` | `f49ef8b` | `D-ParthChauhan/MindwealthUI_Vue` |

**API version bumped `1.10.9` → `1.11.0`** — the alerts response gained a type. Frontend and
backend must cut over together: a client that switches on `type` and does not know `position_risk`
will silently drop 237 of 249 alerts.

API docs updated on the submodule `main` and the pointer committed in the parent:
`changelog.md` (v1.11.0), `services/analyst/README.md`, `endpoints/get-analyst-alerts.md`,
`get-analyst-brief.md`, `get-overwatch-stream.md`, and a regenerated
`openapi/mindwealth-v1.json`.

**Also on the Nuxt side (not analyst-specific but shipped in `f49ef8b`):** `vitest` +
`@vue/test-utils` + `@vitejs/plugin-vue` + `happy-dom` + `vue-tsc` added as devDependencies, with
`test` / `test:watch` / `typecheck` scripts. `npm ci` on the prod Nuxt tree will pull these —
they are devDependencies only and do not enter the bundle. vitest is pinned to `^4` so it resolves
the same vite as Nuxt (7.x); vitest 2 shipped a nested vite 5 and broke the plugin's types.


Supersedes the audit entry below — those defects are now fixed on `chatbot-dev` + `ui-dev`.
**Nothing is deployed.** Backend and Nuxt changes must ship **together**: the panel renders a
`position_risk` alert type the current prod API does not emit.

### Backend — merge `chatbot-dev` → `chatbot-prod`

| File | Change |
|------|--------|
| `api/services/analyst_service.py` | New `position_risk` type + `_portfolio_to_panel_alert`; `above_floor` honours `floor_pct`; `_first_sentence()` brief fix; schedule in `meta`; split signals badge |
| `api/services/degradation_service.py` | Cache is floor-aware; portfolio alerts carry `entry_date`/`exit_date` |
| `api/services/overwatch_event_bus.py` | `bind_loop()` — lets a scan thread publish to live SSE subscribers |
| `api/schemas/analyst.py` | `position_risk` in the type literal; `OverwatchPanelPositionDetail`; `drift_count`/`position_count` on the badge |
| `api/main.py` | Starts/cancels the Overwatch scan loops in `lifespan` |
| **new** `api/services/overwatch_schedule.py` | Scan times, shared by the runner and `meta` |
| **new** `api/services/overwatch_runner.py` | In-process scan loops (replaces cron for SSE) |
| **new** `scripts/smoke_analyst.sh` | 12-assertion contract smoke test |
| **new** `tests/test_analyst_position_split.py`, `tests/test_overwatch_runner.py` | 21 tests |

### Nuxt — merge `ui-dev` → the prod Nuxt branch (`presentation-prod`)

`server/api/overwatch.get.ts`, `server/utils/overwatch-panel.ts`, `server/utils/mindwealth-data.ts`,
`server/utils/signal-parsers.ts`, `composables/useOverwatch.ts`, `composables/useClaudePanel.ts`,
`components/AnalystPanelInner.vue`, `components/analyst/AnalystAlertsView.vue`,
`components/analyst/AnalystMacroAlertCard.vue`, `types/api.ts`, `package.json`, plus **new**
`server/api/page-alerts.get.ts`, `composables/usePageAlerts.ts`,
`components/analyst/AnalystPositionRiskCard.vue`, `components/analyst/AnalystPageAlertCard.vue`,
`vitest.config.ts`, `test/*.spec.ts`, `test/fixtures/analyst-alerts.json`.

Note the prod Nuxt tree is `/home/ubuntu/MindwealthUI_Vue_prod` (branch `presentation-prod`,
currently `ba2bcfd`, 20 Jul) and is **22+ commits behind** `ui-dev`. This merge is not analyst-only.

### `[PROD-ACTION]` Host steps — required, in this order

1. **Warm the degradation cache after deploying the backend**, before the first panel load:
   `.venv/bin/python -c "from api.services.degradation_service import warm_degradation_cache; warm_degradation_cache()"`
   A cache written by the old code has no `entry_date`, so position-alert ids fall back and collide.
   Alternative: delete `overwatch_store/degradation_result.json` and let the first request rebuild it
   (slow — that request pays the full ~1,990-CSV scan).
2. **Confirm the API runs `--workers 1`.** `mindwealth-api.service` does today. The SSE bus is
   per-process; with N workers each client sees 1/N of alerts.
3. **Do NOT install the Overwatch crontab.** `scripts/install_aws_cron_dual.sh:40-42` is now redundant —
   the scans run inside the API. Leaving cron installed is safe (`alert_state.json` dedupes) but
   rebuilds the degradation cache twice a day for nothing. If cron is preferred, set
   `OVERWATCH_SCHEDULER=0` in the service environment — but note SSE will then deliver nothing,
   which is the pre-existing behaviour.
4. **Rebuild the prod Nuxt bundle in its own tree** — `cd /home/ubuntu/MindwealthUI_Vue_prod && npm ci && npm run build`, then `sudo systemctl restart mindwealth-ui.service`.
5. Optional: `ANALYST_USE_CLAUDE_COPY` is still absent from both `.env` files, so alert copy stays
   template-generated. If it is ever enabled, re-check the model id in `analyst_copy_service.py:72`
   (`claude-sonnet-4-5-20250929`) — a dead Claude model id was already retired elsewhere on 2026-08-17.

### `[PENDING]` Latent, pre-existing — running prod Nuxt process is from the old tree

`mindwealth-ui.service` was corrected on 2026-08-17 to `WorkingDirectory=/home/ubuntu/MindwealthUI_Vue_prod`
with an absolute `ExecStart`, but the **running** process (pid 1540211) predates that and still has
`cwd=/home/ubuntu/MindwealthUI_Vue`. Its next restart — planned or not — will switch www.mindwealth.co
to the prod checkout at `ba2bcfd` (20 Jul). Whoever restarts it should expect a visible content jump.
Verified today: the two `.output` trees have different inodes and different content, and the prod
bundle contains none of the analyst work, so a dev `npm run build` can no longer reach prod.

### Smoke tests

- [DONE 2026-08-18] `scripts/smoke_analyst.sh http://127.0.0.1:8507 $KEY` → **12/12 PASS** on dev.
- [PENDING] Same script against `http://127.0.0.1:8506` after the prod API deploy.
- [PENDING] Logged-in `GET :8512/api/overwatch` — assert `system_checks` has 7 named checks for an
  admin, one card per Combo, and `panel_alerts[].type` includes `position_risk`.
- [PENDING] Confirm `journalctl -u mindwealth-api` logs `overwatch scheduler started (3 loops)` on boot.

---

## 2026-08-18 — AI Analyst panel wiring audit: defects found, **nothing fixed yet** `[PENDING]`

Audit only — **no code changed in either repo**, so there is nothing to merge from this entry today.
Recorded here because every defect below is in code that **prod already runs**, so each fix will need a
`chatbot-dev` → `chatbot-prod` merge **plus** a `MindwealthUI_Vue` rebuild + restart, shipped together.

**Prod is affected the same way dev is.** These are not dev-only shortcuts.

### Backend files that will change when fixed (`chatbot-dev` → `chatbot-prod`)

| File | Defect |
|------|--------|
| `api/services/analyst_service.py:101` | Portfolio `profit_pct` (live MTM %) coalesced into the `fwd_wr` win-rate field — 237 of 249 alerts render "FWD WR −23.7%" and "BELOW 60% FLOOR" |
| `api/services/analyst_service.py:151` | `above_floor` hardcoded `>= 61.0`; the `floor_pct` argument is accepted and never read |
| `api/services/analyst_service.py:637` | `/analyst/brief` splits the narrative on the first `.` → snippet truncates mid-number (`"…with a 78."`) |
| `api/services/degradation_service.py:397` | `check_degradation(floor_pct=…)` returns the disk cache before the parameter reaches `_compute_degradation`, so `?floor_pct=` is inert |
| *(new)* `/analytics/analyst/fwd-trend` | P0 in `docs/AI_ANALYST_BACKEND_REQUIREMENTS.md` §5.2 — returns **404**, never implemented; 237/242 alerts have `fwd_trend: null` because of it |

### Nuxt files that will change when fixed (`MindwealthUI_Vue`, `ui-dev` → prod branch)

| File | Defect |
|------|--------|
| `components/analyst/AnalystMacroAlertCard.vue` | Never renders `alert.html` or `macro.historical_analogs` — the **Analog Finder block is invisible** despite the backend building it |
| `types/api.ts:371` | `OverwatchAlertType` omits `runic_watch` / `regime_warning` / `persistence` |
| `composables/useOverwatch.ts:36` | MACRO tab filter drops those 3 types; ALERTS badge counts 245 while ALL renders 249 |
| `composables/useOverwatch.ts:44` | ALL badge reads `'Overwatch · Claude triggered'` — **spec requires `'Overwatch · auto-triggered'`**; backend already returns the correct string |
| `server/api/overwatch.get.ts:31` | `include_system: 'false'` hardcoded — SYSTEM tab never calls the real `/system/health` |
| `server/api/overwatch.get.ts:17-20` | BFF still emits `runic-dominant-<combo>` alongside the backend's `runic-<combo>` → **Combo F card renders twice** |
| `server/utils/overwatch-panel.ts:125` | `buildSystemChecks()` hardcodes India CSV / Claude API / Tavily as `warn` + "unavailable"; "Google Sheets sync" just echoes `meta.data_updated_at` |
| `server/utils/overwatch-panel.ts:32-61` | Dead code (`parseForwardTestingRows` always returns `[]`) incl. a fabricated `fwdTrend` interpolation — delete rather than leave live-looking |
| `components/analyst/AnalystAlertsView.vue` | No cap/pagination — renders all 249 cards in a 360px column |

### Backend endpoints live on prod with **zero frontend consumers**

`GET /api/v1/analytics/analyst/context` · `GET /api/v1/analytics/analyst/brief` · `GET /api/v1/system/health` ·
`GET /api/v1/overwatch/stream` (SSE) · all `/analyst/alerts` query params (`channel`, `since`, `include_persistence`, `gap_threshold_pp`) ·
all chat presets (`analyze_asset`, `signal_insights`, `breadth_analysis`, `deep_research_enabled`).
Wiring these is `docs/AI_ANALYST_BACKEND_REQUIREMENTS.md` §6, still unstarted.

### Host / runtime actions needed (**not** git)

1. **Overwatch cron is not scheduled on any host** — `scripts/overwatch/run_overwatch_{signals,macro,system}.py` have no crontab entry and no systemd timer, on dev or prod.
2. **Scheduling them alone will not work.** `api/services/overwatch_event_bus.py:59` is an in-process asyncio bus; a cron process publishes into its own empty subscriber set. SSE needs Redis pub/sub (spec open question 2, never answered) or an in-API scheduler. Decide before wiring `EventSource` in Nuxt.
3. `ANALYST_USE_CLAUDE_COPY` is absent from dev `.env` (`ANTHROPIC_API_KEY` **is** set) — all alert copy is template. If Claude copy is wanted on prod, add the flag to the prod `.env` **and** confirm the model id in `analyst_copy_service.py:72` (`claude-sonnet-4-5-20250929`) is still valid — a dead Claude model id was already retired elsewhere on 2026-08-17.
4. `MindwealthUI_Vue/.env:1` still reads `NUXT_API_BASE_URL=http://51.20.53.218:8514` — points a Nuxt at itself. Harmless while systemd supplies the real value (`:8514`→`127.0.0.1:8507`, `:8512`→`127.0.0.1:8506`), but wrong for anyone running the app from a shell. Fix or delete the line.

### Smoke tests

- [PENDING] After any fix: `GET :8507/api/v1/analytics/analyst/alerts?include_system=false` — assert no `signal.fwd_wr < 0`, and that `type` distinguishes position-risk alerts from win-rate drift.
- [PENDING] `GET :8507/api/v1/analytics/analyst/brief` — assert the snippet does not end mid-number.
- [PENDING] Logged-in `GET :8514/api/overwatch` — assert exactly one card per Combo, and `system_checks` sourced from `/system/health`.

---

## 2026-08-18 — `POST /macro/run-nightly` could clobber the live snapshot (API 1.10.9) `[PENDING]`

Closes the half of the 2026-08-17 snapshot bug that the `persist` flag did **not** cover. `trigger_nightly_run()` passed any `as_of` into `run_nightly()`, which persists, so a single call like `{"as_of": "2024-09-18"}` reproduced the exact corruption over HTTP.

**Fix:** persist only when `as_of` is unset or equals today; response gains `persisted` and `persist_skipped_reason`, and `output_path` is `null` when skipped. Also isolated the runic schema test's DB writes via a throwaway `MACRO_INTEL_DB` copy.

### 1. Files to merge `chatbot-dev` → `chatbot-prod` (commit `40fda07de`)

| Path | Kind |
|---|---|
| `api/services/macro_service.py` | modified — `persist` guard in `trigger_nightly_run()` |
| `api/routers/macro.py` | modified — docstring documents the guard |
| `api/main.py` | modified — `API_VERSION` 1.10.8 → **1.10.9** |
| `tests/test_api_macro.py` | modified — `test_backdated_nightly_run_does_not_persist` |
| `tests/test_runic_output_schema.py` | modified — tmp-DB isolation in `setUp`/`tearDown` |
| `docs/mindwealth-api-docs` | submodule pointer → `1121b3e` (pushed to `divsum127/mindwealth-api-docs` `main`) |

**Careful when merging:** `api/services/macro_service.py` and `api/routers/macro.py` still carry **uncommitted work from other tasks** in this worktree (≈238 further lines). Only the hunks in `40fda07de` belong to this change.

- **Dev-only / revert:** none. **Runtime artifacts:** none. **`.env` / secrets:** unchanged. **systemd / Nuxt:** no change, no rebuild.
- **Response-shape change:** additive only (`persisted`, `persist_skipped_reason`); `output_path` becomes nullable. No Nuxt consumer reads this endpoint.

### 2. Smoke tests

- `[DONE 2026-08-18]` `pytest tests/ -q` → **818 passed, 4 skipped, 0 failed** (249s). The long-standing Monday-only `test_shortlist_mtm_not_stale_zero_for_aged_signals` failure is **gone** now that the 2026-08-17 pull landed.
- `[DONE 2026-08-18]` Live proof on dev `:8507`: `POST /macro/run-nightly {"as_of":"2024-09-18"}` → `persisted: false`, `output_path: null`, reason string present; `runic_output.json` mtime **unchanged**, `date` still `2026-08-17`, no `runic_briefing_2024-09-18.*` produced.
- `[DONE 2026-08-18]` `smoke-test-apis.sh` 11/11 PASS, dev reports **v1.10.9**, prod v1.8.1 isolated.
- `[PENDING]` After the prod merge: same backdated call against `:8506` must return `persisted: false`.

### Status: `[PENDING]` — done and verified on dev; prod merge outstanding.

---

## 2026-08-17 — Nuxt stamped report dates at midnight UTC (topbar read one evening early) `[PROD-ACTION]`

**Repo:** `MindwealthUI_Vue` (separate remote `D-ParthChauhan/MindwealthUI_Vue`), branch `ui-dev` @ `fe7ebf1`, author `divsum127`.

**Defect:** `server/utils/mindwealth-data.ts` built `data_updated_at.datetime` as `<report-date>T00:00:00Z` in three places (`metaFromSource()`, signals-list meta, shortlist meta). Midnight UTC renders as 8:00 PM the previous evening in `America/New_York`, so a 2026-08-14 report displayed as **Aug 13, 08:00 PM EDT**. The FastAPI `/api/v1/meta` was correct throughout (`2026-08-14T16:00:00-04:00`) and simply unused — `loadMeta()` derived meta from the overlay filename instead.

**Fix:** all three sites use the existing DST-safe `buildMarketCloseDataUpdatedAt()` (16:00 America/New_York); `loadMeta()` now calls the backend `/meta` and merges via `mergeApiMeta()`, keeping filename derivation as fallback.

### 1. Files to merge

| Path | Kind |
|---|---|
| `MindwealthUI_Vue/server/utils/mindwealth-data.ts` | modified — market-close stamps + backend `/meta` preference |

No `MindWealth_UI` code file changed. Docs updated here: `docs/mindwealth_ui_job_status.md` (entry 17), `docs/mindwealth_ui_repo_job_status_details.md`, this file.

- **Dev-only / revert:** none.
- **Runtime artifacts:** none. `.env` / secrets / `config/users.json` unchanged.
- **API:** no route, schema or response-shape change. No OpenAPI export, no docs-submodule commit.

### 2. `[PROD-ACTION]` — already half-applied, read before restarting prod UI

`mindwealth-ui-dev` (`:8514`) and `mindwealth-ui` (`:8512`, public `www.mindwealth.co`) share **one** `WorkingDirectory=/home/ubuntu/MindwealthUI_Vue` and **one** `.output`. The `npm run build` run for dev has **already replaced the bundle prod serves**; `:8512` keeps executing the previously-loaded code until it restarts, then picks this change up with no merge step.

Consequence: `sudo systemctl restart mindwealth-ui` deploys this fix to production. That is the intended outcome here, but treat any future dev build in this repo as a staged prod deploy.

### 3. Smoke tests

- `[DONE 2026-08-17]` `rg "T00:00:00Z"` across `server/ components/ pages/ composables/ utils/` → no matches.
- `[DONE 2026-08-17]` `npm run build` clean (Node 20); `mindwealth-ui-dev` restarted, active, `:8514` → 200.
- `[DONE 2026-08-17]` Render proof in Node: old stamp → `Aug 13, 08:00 PM EDT`, new stamp → `Aug 14, 04:00 PM EDT`.
- `[DONE 2026-08-17]` End-to-end BFF check on dev: `GET :8514/api/meta` → `datetime: 2026-08-14T16:00:00-04:00`, `data_source: live`.
- `[DONE 2026-08-17]` `smoke-test-apis.sh` all PASS; `pytest tests/test_api_*.py` 187 passed / 1 known failure; `mindwealth-ui-dev` journal clean.
- `[PENDING]` **Prod still serving the bug:** `GET :8512/api/meta` → `2026-08-14T00:00:00Z`. `www.mindwealth.co` will keep showing `Aug 13, 08:00 PM EDT` until `sudo systemctl restart mindwealth-ui`. Not done — needs the user's go-ahead (public deploy).
- `[PENDING]` Logged-in browser check on `:8514` (visual confirmation of the topbar string).

### Status: `[PROD-ACTION]` — dev verified end to end; prod fix is one restart away and awaiting go-ahead.

### Related follow-up (separate task, pre-existing)

`server/utils/require-auth.ts` `requireAuth()` checks only that the `mw_access_token` cookie exists, never that it is valid, while `mindwealth-client.ts` authenticates upstream with the server-side `NUXT_API_KEY`. Any fabricated cookie therefore reaches live BFF data on both `:8514` and public `:8512`. Not introduced by this change and not fixed here.

---

## 2026-08-17 — `pytest` clobbers the live `runic_output.json` (macro page date rollback) `[PENDING]`

**Fix applied on dev 2026-08-17** (see §1 below for the final shape — it differs from the originally proposed env-var monkeypatch). Dev snapshot restored and verified. Still `[PENDING]` for prod: the defective test file is in prod's tree and must be replaced by the merge.

**Defect:** `tests/test_runic_output_schema.py:34` calls `run_nightly(as_of="2024-09-18")`; `run_nightly` unconditionally persists at `src/macro_intelligence/jobs/nightly_run.py:262` → `write_runic_json()` → `json_output_path()` → the live, **gitignored** `macro_intelligence/output/runic_output.json` (plus `runic_briefing_<as_of>.html/pdf`). Running the suite rolls every runic-JSON-backed endpoint back to `date: 2024-09-18` (`/macro/status`, `/macro/regime`, `/macro/runic/*`, `/macro/overview/kpis`, `/macro/combos`, `/macro/combo-*`, `/macro/narrative`, `/macro/persistence`, `/macro/variables/heatmap`, `/macro/data/freshness`, `/macro/events/*`, `/portfolio/sizer`, `/portfolio/sizing`).

**Prod exposure today: none** — `pytest` is not run in `/home/ubuntu/uiv2/prod/MindWealth_UI`, and its `runic_output.json` is written only by the prod nightly cron (`0 18 * * 1-5`). The risk is latent: the first time anyone runs the suite there, the prod macro page silently reverts.

### 1. `[PENDING]` Files to merge `chatbot-dev` → `chatbot-prod` (fix written 2026-08-17)

| Path | Kind |
|---|---|
| `src/macro_intelligence/jobs/nightly_run.py` | modified — `run_nightly(..., persist: bool = True)`; `persist=False` returns the payload without calling `write_runic_json()` / `write_briefing()` |
| `tests/test_runic_output_schema.py` | modified — passes `persist=False`, plus new `test_nightly_does_not_touch_live_snapshot` asserting the live JSON's mtime is unchanged |

Chose the `persist` flag over the `MACRO_INTEL_JSON_PATH` tmpdir monkeypatch first proposed: `write_briefing()` has **no** env override (its dir comes from `CONFIG.yaml briefing.output_dir`), so the env route would have isolated the JSON and still emitted stray `runic_briefing_2024-09-18.html/pdf`. The optional `json_writer.py` date-monotonic guard was **not** implemented — it would block legitimate backfills, and with `persist=False` there is no remaining writer of a stale date.

Both production callers keep the default `persist=True` and are unchanged: `scripts/run_macro_nightly.py:23` (cron) and `api/services/macro_service.py:1197`.

Modified now (docs only): `docs/mindwealth_ui_job_status.md`, `docs/mindwealth_ui_repo_job_status_details.md`, this file.

- **Dev-only / revert:** none.
- **Runtime artifacts to create on prod:** none. `runic_output.json` is gitignored (`.gitignore:43`) and is regenerated by cron, never merged.
- **`.env` / secrets / `config/users.json`:** unchanged.
- **systemd / Nuxt:** no change, no rebuild. An API restart is **not** required — `macro_service._load_runic()` re-reads the JSON per request.

### 2. `[PROD-ACTION]` Recovery command (only if a prod snapshot is ever clobbered)

```bash
cd /home/ubuntu/uiv2/prod/MindWealth_UI && .venv/bin/python scripts/run_macro_nightly.py --no-claude
```

Deploy-step only; this is the same script prod cron already runs. Nothing else in the prod clone is to be written.

### 3. Smoke tests

- `[DONE 2026-08-17]` Dev restore — `.venv/bin/python scripts/run_macro_nightly.py --no-claude` → `runic_output.json` `date: 2026-08-17`, Combo F week 20 of 26, `runic_briefing_2026-08-17.html/pdf` regenerated.
- `[DONE 2026-08-17]` `curl -H "X-API-Key: $KEY" localhost:8507/api/v1/macro/status` → `date: 2026-08-17`. Same on `:8506` → `2026-08-17`. No API restart performed or needed.
- `[DONE 2026-08-17]` Regression proof — `pytest tests/test_runic_output_schema.py -q` → **2 passed**; live JSON mtime unchanged across the run (asserted by the new test itself).
- `[PENDING]` After the prod merge: `curl -s -H "X-API-Key: $KEY" localhost:8506/api/v1/macro/status | jq -r .date` → latest weekday, **not** `2024-09-18`.

### Status: `[PENDING]` — fix done and verified on dev; prod merge outstanding (prod exposure remains latent, not active).

---

## 2026-08-17 — SSI threshold experiments: analysis doc + CSV value exports `[PENDING]`

Analysis artifacts only. **No runtime, API, CONFIG, systemd or Nuxt surface is touched, and no threshold value changes.** Safe to merge with any batch.

### 1. `[PENDING]` New files to merge `chatbot-dev` → `chatbot-prod`

| Path | Kind |
|---|---|
| `scripts/export_ssi_validation_csvs.py` | new script (read-only over artifacts) |
| `testing/ssi_th_exp/SSI_THRESHOLD_EXPERIMENTS_ANALYSIS.md` | new analysis doc |
| `macro_intelligence/analysis/ssi_validation/csv/` | new dir — 50 CSVs + `INDEX.csv`, regenerable |

Modified: `docs/mindwealth_ui_job_status.md`, `docs/mindwealth_ui_repo_job_status_details.md`, this file.

- **Runtime artifacts to create on prod:** none.
- **`.env` / secrets / `config/users.json`:** unchanged.
- **systemd / Nuxt:** no change, no restart needed.
- The CSV dir is fully regenerable — if the merge is noisy, `.venv/bin/python scripts/export_ssi_validation_csvs.py` recreates it from the tracked JSON artifacts.

### 2. `[DONE]` 2026-08-17 — Two untracked status docs added to git **and** corrected

`testing/ssi_th_exp/SSI_EXPERIMENT_RESULTS.md` and `testing/ssi_th_exp/SSI_OPEN_QUESTIONS_STATUS.md` were the two most-cited SSI status docs and were **untracked** — they would not have merged to prod. Both are now staged and corrected in place: C-1…C-7 fixed inline and marked `[corrected 08-17]`, all artifact citations re-pointed to the newest file per stem, Tests 3–4 re-labelled SIGN-OFF HELD, Test 15 VOID-but-runnable, Test 6 STALE, and decision D-7 (`min_confirmed`) added. Staged, **not committed**.

### 3. `[PENDING]` Amend the staleness list before any re-run is authorised

`docs/ssi_validation/STALE_BACKTESTS_AFTER_CNN_HY_FIXES.md` buckets Tests 8/10/20/22 as stale "via `hyg_lqd`" from the HY OAS fix. SSI's `hyg_lqd` is a Yahoo ETF price ratio (`src/sentiment_superindex/data/yahoo_inputs.py:15`); HY OAS is consumed only under `src/macro_intelligence/`. No shared path — those tests are stale via `cnn_fg` in the composite gate instead. The list is the agreed gate for re-runs, so amend it before step 2–4 of its re-run order starts.

### 4. Smoke test `[DONE]` 2026-08-17

`.venv/bin/python scripts/export_ssi_validation_csvs.py` → exit 0, 23 artifact families, 50 CSVs + `INDEX.csv` (64 index rows). Three values hand-checked against source JSON (Test 3 `FM<10/RM>55` n_ep=21 / gap +0.4111; Test 22 prod cell n=160 / hit 41.25; Test 15 `n_short_entries=0`). Every path cited in the analysis doc resolves.

### 5. Robust test + dev deploy `[DONE]` 2026-08-17

- `pytest tests/` → **809 passed, 1 failed, 3 skipped**. The single failure is the pre-existing `test_shortlist_mtm_not_stale_zero_for_aged_signals` calendar-vs-trading-day bug (see §"Known pre-existing test failure" below) — unrelated to this change.
- `pytest tests/test_api_*.py` → 186 passed, same 1 pre-existing failure.
- Targeted `-k "ssi or cftc or staleness or layer2"` → **124 passed**.
- `smoke-test-apis.sh` → **all PASS**. Dev `:8507` v1.10.8, `conviction_store` = git clone, writable. Prod `:8506` v1.8.1 still isolated at the prod clone path — **prod service not restarted** (`ActiveEnterTimestamp` still 2026-08-02).
- Mock audit on the one changed `.py`: clean — no mocks, placeholders, `temporary`/`for now` markers, or clone-specific absolute paths. **No importers**, so zero runtime blast radius.
- Export re-run after the dev restart → byte-identical, 0-line diff vs the committed CSVs (deterministic).
- Pushed `chatbot-dev` → `divsum127/MindWealth_UI` @ `26c4dabeb`, author `divsum127`. `upstream` (`ahiliitb/*`) untouched.

**Known pre-existing test failure (not introduced here, do not treat as a regression):** `tests/test_api_signals_surface.py::test_shortlist_mtm_not_stale_zero_for_aged_signals` gates on **calendar** age (`>= 3` days) then asserts on `days_elapsed`, which is **trading** days sourced from the `Trading Days between Signal and Today Date` column in `trade_store`. All 10 failing records are dated **Fri 2026-08-14** and today is **Mon 2026-08-17**, so `days_elapsed=0` is correct. The guard's own docstring targets "0% MTM **with** 0 holding days", and `mtm_pct` is live and non-zero (1.77, 2.42, 8.04…), so the staleness it exists to catch is absent. **It will fail every Monday** for any Friday signal. Left unfixed by prior decision (`global_repo_todos.md` 2026-08-17 #2) — relaxing the assertion would weaken a genuine stale-MTM guard, so the fix needs a call on whether the gate should use trading-day age or additionally require `mtm_pct == 0`.

---

## 2026-08-17 — Nuxt frontend: prod and dev share ONE build dir; `www.mindwealth.co` outage post-mortem `[PENDING]`

Applies to the **Nuxt frontend repo** `/home/ubuntu/MindwealthUI_Vue`, not `MindWealth_UI`. Docs-only change in git here.

### 1. `[PENDING]` **`mindwealth-ui.service` (prod) and `mindwealth-ui-dev.service` share one working tree and one `.output`**

| Unit | Port | Public entry | `NUXT_API_BASE_URL` | WorkingDirectory |
|---|---|---|---|---|
| `mindwealth-ui.service` | 8512 | `www.mindwealth.co` (nginx) | `127.0.0.1:8506` (prod API v1.8.1) | `/home/ubuntu/MindwealthUI_Vue` |
| `mindwealth-ui-dev.service` | 8514 | `http://51.20.53.218` (nginx) | `127.0.0.1:8507` (dev API v1.10.8) | `/home/ubuntu/MindwealthUI_Vue` |

SSR byte sizes on both ports are **identical (115,614)** — they serve the same `.output`. Consequences:

- **`www.mindwealth.co` serves whatever the `ui-dev` branch last built.** There is no separate prod build. `presentation-prod` (`ba2bcfd`) is *not* what the public site runs.
- Any `npm run build` in that directory silently stages a public-site redeploy, applied at the next restart.
- A rebuild **without** an immediate restart breaks the live site's asset loading — Nitro serves hashed files from `.output/public`, and the running process references hashes the rebuild deleted.
- The only prod/dev isolation is the systemd `NUXT_API_BASE_URL` (8506 vs 8507). The repo's tracked `.env` (pointing at `:8514`) is **not** used by either service — systemd `Environment=` wins, and `.output` does not read `.env`.
- Action: give prod its own clone (or its own worktree + build dir) checked out to the intended prod branch, so a dev build cannot redeploy the public site. Until then, treat `npm run build` in that directory as a production action.

### 2. `[PENDING]` Deployed artifact is a mid-edit snapshot — clean rebuild wanted

Current `.output` (mtime `12:11:14` 2026-08-17) was built while another operator was mid-save on 6 files (written 12:09:48–12:10:31, later committed as `0921dd3`). The built bundle *does* contain `0921dd3`'s new symbols (`mapComboPriorityOrder`, `SIGMA_SOURCE_LABELS`, `demoted_for_low_n`, `model_barrier_basis`, `min_matured_episodes`), so it is not stale — but it is **not provably identical to any commit**.

- Action (restarts the public site — schedule it): with the tree clean at `0921dd3`, `npm run build` then `sudo systemctl restart mindwealth-ui.service mindwealth-ui-dev.service`, and re-verify `https://www.mindwealth.co/` → 200 plus one `/_nuxt/*.js` asset → 200.
- Note the `fetch-and-reload` skill builds from **`origin/main`**, not `ui-dev`, so it is not the right tool for this branch as configured.

### 3. `[DONE]` Outage post-mortem — 14m50s on `www.mindwealth.co` (2026-08-17)

`pkill -f ".output/server/index.mjs"`, intended for a local `:3007` smoke-test server, also matched **both** systemd Nuxt units (same entrypoint, same WorkingDirectory). Both exited cleanly at **12:14:06 UTC**; because the units are `Restart=on-failure` and a clean SIGTERM is not a failure, **systemd did not restart either** (`NRestarts=0`). Dev was started by another operator at 12:18:57; prod stayed down until `sudo systemctl start mindwealth-ui.service` at **12:28:56** — **14m50s public outage**. Restored and verified (`:8512` listening, `https://www.mindwealth.co/` → 200).

- **Standing rule:** never `pkill -f` a generic Node/Nitro entrypoint on this host. Stop test servers by PID or by port, and run `systemctl list-units | grep -i nuxt` **before** any pattern kill. Consider adding `Restart=always` to both units so a stray SIGTERM self-heals.

---

## 2026-08-17 — `MindwealthUI_Vue` `ui-dev` synced + pushed; public-repo API key exposure `[PENDING]`

Git ops in the **Nuxt frontend repo** (`/home/ubuntu/MindwealthUI_Vue`, remote `github.com/D-ParthChauhan/MindwealthUI_Vue`) — a separate repo that is **not** deployed by `scripts/prod-pull-and-restart.sh`. No `MindWealth_UI` code was touched.

**Git files to merge** (`chatbot-dev` → `chatbot-prod`): docs only — `docs/mindwealth_ui_job_status.md`, `docs/mindwealth_ui_repo_job_status_details.md`, `docs/dev_to_prod_migration_todos.md`. **Zero runtime, API, schema, systemd, or Nuxt impact for `MindWealth_UI`.**

Vue-side state: `ui-dev` was diverged (local `73e196a` vs remote `f99e9d4`); merged clean (`0502751`, 144 files, +19,240/−609) and pushed to `origin/ui-dev`. Build verified (`npm run build` exit 0), built server boots, auth gate and `/api/v1` proxy correct, all 10 upstream endpoints 200. Type errors 55 post-merge vs 56 pre-merge — merge introduced none.

### 1. `[PENDING]` **SECURITY — dev API key published in a public repo**

`.env` containing `NUXT_API_BASE_URL=http://51.20.53.218:8514` and `NUXT_API_KEY` is **tracked in git**, `.gitignore` does not exclude it, and it is already on `origin/ui-dev` via upstream commit `f99e9d4`. Repo visibility is **public** (`private: false`, GitHub API). The dev API key for `:8514` is world-readable and persists in history after any plain delete. Pre-existing — not introduced by the 2026-08-17 merge/push, which added no new exposure.

- Action (needs Parth coordination — rewrites `ui-dev`):
  1. **Rotate `NUXT_API_KEY`** on the API side; treat the current value as compromised. Check `api/dependencies.py::require_api_key` consumers before rotating.
  2. Add `.env` to `.gitignore`, then `git rm --cached .env`.
  3. Purge from history: `git filter-repo --path .env --invert-paths` (or BFG) + coordinated force-push.
- Also committed by `f99e9d4` and worth removing: `mindwealth-api-docs-main (2).zip` (128 KB binary) and `mindwealth-api-docs-main 7/` — a full duplicate of the API docs incl. a 9,498-line OpenAPI JSON. **This duplicates `docs/mindwealth-api-docs/` and is exactly the drift CLAUDE.md's "never create `docs/api/`" rule guards against.**

### 2. `[PENDING]` Authenticated render of the new portfolio views never tested

The merge brought in `PortfolioOverviewView.vue` (638 lines), `PortfolioNavChart.vue`, `PortfolioActualPnlView.vue`, `PortfolioContributionList.vue`, `PortfolioRailBlock.vue`, `PortfolioOverviewStat.vue`, a rewritten `ConvictionRowDrawer.vue` / `ConvictionSignalsPanel.vue`, and reshaped `server/utils/mindwealth-data.ts` / `portfolio-mappers.ts` / `types/api.ts`. All of it runs only behind a `mw_access_token` session; `config/users.json` stores bcrypt hashes, so no login was possible during verification. Build-time and endpoint-contract correctness confirmed; **render-time correctness is unverified.**

- Action: log in on the dev UI and click through Portfolio (overview / NAV / actual P&L / sized alloc / risk), Conviction (row drawer + signals panel), and Sentiment before any `presentation-prod` promotion.
- Related: `server/utils/mindwealth-data.ts:1618,1620` — `Property 'ticker'` and `Property 'direction'` do not exist on type `Signal` (possible runtime `undefined`); `:886` — `Cannot find name 'PerformanceRow'`. Pre-existing, unblocked by the build since Nitro does not typecheck.

### 3. `[PENDING]` `ui-dev` promotions still open

`ui-dev` is **11 commits ahead of `main`**; `presentation-prod` sits at `ba2bcfd`. Neither promotion was performed (user chose sync-only). Also: 6 files in the Vue working tree (`assets/css/main.css`, `components/runic/*.vue` ×3, `server/utils/runic-mappers.ts`, `types/api.ts`, +180 lines) are **uncommitted** from concurrent live editing — commit or stash before promoting.

### 4. Note on the required frontend follow-up from the AI Analyst fix

The chatbot 503 fix (job status 2026-08-17 #7) still needs its `MindwealthUI_Vue` client-side change (poll budget / 30 s GET cache). **Not addressed by this merge** — `DEEP_RESEARCH_TOTAL_TIMEOUT_SECONDS` 120 → 300 raises the server budget only; without the client change the 503 can still recur.

---

## 2026-08-17 — Rohit 21 Jul email audit: three live prod defects found `[PENDING]`

Documentation-only change in git (`instruction_docs/chat_ques/21July_Rohit_feedback_and_priorities - STATUS.md`), but the audit surfaced **three prod-affecting problems that need action outside a normal merge**.

**Git files to merge** (`chatbot-dev` → `chatbot-prod`):
- `instruction_docs/chat_ques/21July_Rohit_feedback_and_priorities - STATUS.md` (new)
- `docs/mindwealth_ui_job_status.md`, `docs/mindwealth_ui_repo_job_status_details.md`, `docs/dev_to_prod_migration_todos.md` (modified)

### 1. `[PENDING]` The merge itself is overdue — 23 commits, 22 days

`origin/chatbot-prod` is at `0fb433521` (2026-07-26); prod API reports **v1.8.1**, dev **v1.10.8**. Everything in the 2026-07-26 → 2026-08-17 window is invisible to Rohit. **Hard evidence:** `conviction_store/PYPL.json` reads `valuation_tax=-1.0` on dev and **`-4.0` / `pe_percentile_20y=100.0` on prod** — the exact bug Rohit reported on 21 Jul, still live on the site.

- Action: `bash scripts/prod-pull-and-restart.sh` after merge, then re-verify `/api/v1/health` reports the new version.

### 2. `[PROD-ACTION]` Conviction P/E rollout (PE-01b) — still never run

Merging the code is **not sufficient**. The prod `conviction_store/` records must be regenerated on the prod host (an agent may not write prod runtime data). Runbook already in the TODO section of `docs/mindwealth_ui_job_status.md`:

```bash
cd /home/ubuntu/uiv2/prod/MindWealth_UI
rm -f conviction_store/pe_history_cache/*_sec.json
python scripts/update_conviction_fundamentals.py --mode full --include-existing-records --pe-history-report
```

Sanity check: PYPL must move off `pe_percentile_20y=100.0` / `valuation_tax=-4.0`.

### 3. `[PENDING]` Code fix — `pnl_usd` is direction-blind on shorts (affects dev **and** prod)

`api/services/portfolio_service.py:985` computes `pnl_usd = market_value_usd - allocation_usd` without using `direction` (bound at `:960`). Every SHORT reports the opposite sign to `mtm_pct`. Verified live: BABA short `mtm_pct=-1.35` / `pnl_usd=+471.96`; 000660.KS short `mtm_pct=+24.78` / `pnl_usd=-16617.50`.

Propagates into `day_mtm_usd` (`portfolio_pipeline_service.py:722`) and the top-5 gainers/losers (`:742-746`) — **Live P&L winners and losers are inverted for shorts, client-visible.** Fix + regression test before the next demo.

### 4. `[PROD-ACTION]` Nightly cron fires before the US cash close

Server TZ is `Etc/UTC`. Both clones run `run_macro_nightly.py` at `0 18 * * 1-5` = **14:00 ET**, two hours before the 16:00 ET close and 2h15m before VIX settlement — so VIX / VXTS / WTI / CNH / CURVE are intraday prints, never official closes. Prod's 2026-08-14 nightly holds `VIX=14.34` vs Yahoo close `14.25`, `VXTS=1.288` vs `1.2381`. **This is the mechanical cause of the VIX mismatch Rohit reported and it feeds Combo A/D/G thresholds.**

- Action: move both crontab entries to **≥ `15 21 * * 1-5`** (21:15 UTC = 17:15 ET), or pin the pull explicitly to the prior completed session's close. `run_ssi_daily.py` at `0 8` (04:00 ET, pre-open) needs the same review.
- Applies to **both** the dev and prod crontab lines.

### 5. `[PENDING]` Freshness gap — 10 of 12 macro variables have no `source_date`

`GET /macro/data/freshness` on prod returns `source_date: null` for NFCI, HY, WALCL, CNH, WTI, VIX, VXTS, CURVE, CPI, GSR. Only CFTC and CAPE are stamped. Rohit asked to "check the live-ness for all macro variables" — there is currently nothing to check against.

### 6. `[PENDING]` 8D rounding rule not applied to the Runic variables endpoint

`_round2()` / `_display_decimals()` cover `/macro/ssi/summary` and `/macro/ssi/history` only. `/macro/runic/variables/current` still returns float32 noise (`VIX = 14.34000015258789`).

---

## 2026-08-18 — Chatbot vocabulary + macro data (audit gaps 5, 6, 8) `[PENDING]`

Closes the three routing/data gaps found in the usage audit. Same defect class as the NZ complaint: the assistant could not reach or name data we already compute.

**Git files to merge** (`chatbot-dev` → `chatbot-prod`), commit **`f694f73f8`**:
- `chatbot/agents/llm_router.py` — `_PLATFORM_VOCAB_RE` + `_MACRO_QUERY_RE` overrides, and demotion of platform-vocab questions out of CONVERSATIONAL
- `chatbot/macro_context.py` — **new**, SOURCE D (Runic regime, combos, SSI, portfolio risk)
- `chatbot/platform_context.py` — **new**, SOURCE E (signal-type taxonomy + live function list)
- `chatbot/chatbot_engine.py` — injects SOURCE D/E on the hybrid, internal **and** conversational paths
- `chatbot/config.py` — `ENABLE_MACRO_CONTEXT`, `MACRO_CONTEXT_BOOK_ID`, `ENABLE_PLATFORM_CONTEXT`
- `chatbot/tests/test_platform_and_macro_context.py` — **new**, 17 cases

`[PROD-ACTION]` restart `mindwealth-api.service` after merge — config and prompt wiring are read at process start. No new env keys required (all three default on). No API surface change, so no OpenAPI or docs-submodule update.

`[PROD-ACTION]` **Verify `API_PORT=8506` is set on the prod unit.** SOURCE D self-calls over HTTP and derives its base URL from `API_PORT`; the client's fallback is also `8506`, so this is a check rather than a change. Sharp edge worth knowing: any invocation *outside* the service (a shell script, a cron job) inherits no `API_PORT` and will silently query **prod** even when run from the dev clone.

**Smoke tests:**
- `[DONE]` 2026-08-18 — `pytest tests/ chatbot/tests -q` → **900 passed, 4 skipped**.
- `[DONE]` 2026-08-18 — "give me a short summry about claude report" → INTERNAL, extractor selects `claude_report`, answer summarises the real 2026-08-17 report (VIX 15.19, 72 signals). Previously CONVERSATIONAL asking whether Claude was a ticker.
- `[DONE]` 2026-08-18 — "What signal types exist?" → INTERNAL, `Platform Capabilities` in the flow, all five types selected, answer names TRENDPULSE / DELTADRIFT / FRACTAL TRACK / BASELINEDIVERGENCE / BAND MATRIX. Previously a textbook LONG/SHORT answer.
- `[DONE]` 2026-08-18 — "what is the current macro regime and which combo is dominant?" → **HYBRID** with a `Macro Overlay` step, leads with Combo F week 20 of 26 and the real regime components. Previously `WEB_RAG` contradicting our own engine.
- `[PENDING]` prod: repeat all three after merge + restart.

**Dev-environment hazard — `[DONE 2026-08-18]`, fixed.** `mindwealth-api-dev.service` ran uvicorn with `--reload`, so every file save restarted the API and killed in-flight chat answers (chat jobs run in worker threads inside that process, so a reload is indistinguishable from a crash). Three replays died this way while another session edited `api/`. `--reload` removed from the host unit **and** the tracked copy `scripts/mindwealth-api-dev.service` (commit `14adc93be`), `daemon-reload` + restart applied. Proof: touched `api/main.py`, `chatbot/config.py` and `api/services/analyst_service.py` mid-answer — **zero restarts**, answer completed at 125.6s / 16,271 chars. Prod never had `--reload`, so **no prod action is required**; the tracked file merges for consistency only.

---

## 2026-08-17 — "Could not reach the analyst" — permanent fix, **two repos, ship together** `[PENDING]`

**Both halves must deploy together.** The backend's 330s answer budget is only safe because the client now resumes a job by id instead of holding one socket open and 503-ing. Shipping the backend alone re-exposes the original failure.

**`MindWealth_UI`** (`chatbot-dev` → `chatbot-prod`), commit **`6c893e309`**:
- `api/jobs/store.py` — `JobStore.fail_orphaned()`
- `api/main.py` — lifespan calls it at startup
- `tests/test_api_chatbot.py` — 2 new cases

**`MindwealthUI_Vue`** (`ui-dev` → prod UI branch), commit **`bd18d42`**:
- `server/utils/mindwealth-client.ts` — never cache `/chatbot/*`; cache key carries a bearer-token fingerprint
- `server/utils/mindwealth-data.ts` — poll tolerates 8 consecutive failures; 45s handoff; empty-content jobs reported immediately
- `server/api/chat.post.ts` — returns `{pending, job_id}` instead of throwing 503
- `server/api/chat/job/[jobId].get.ts` — **new** resume route
- `composables/useClaudePanel.ts` — browser-side resume loop, job id persisted, error messages differentiated
- `types/api.ts` — `pending` / `job_id` on `ChatResponse`

`[PROD-ACTION]` prod host: `npm run build` **and** restart the prod UI service — a merge alone does not update the running bundle. Note the still-open finding that prod and dev share one Nuxt build dir.
`[PROD-ACTION]` restart `mindwealth-api.service` so `fail_orphaned()` runs and clears any jobs stranded by earlier restarts.

**Security note worth calling out separately:** the GET cache key had no caller identity, so user-scoped responses could be served across signed-in users for up to 30s. Fixed in the same commit. Prod carries this defect until the UI ships.

**Smoke tests:**
- `[DONE]` 2026-08-17 — through the Nuxt BFF on `:8514` with a real `mw_access_token`: NZ question `pending` at 45.1s → one resume poll → **5,501 chars at 60.1s, no 503**; signals+quality **7,647 chars at 57.8s**; short AAPL question **inline at 25.1s**.
- `[DONE]` 2026-08-17 — poll cadence in the API log went from **3 polls/30s apart** to **24 polls at ~2.5s** (the first patch was an anchored regex that silently matched nothing — caught by this check, not by review).
- `[DONE]` 2026-08-17 — `pytest tests/` **817 passed, 4 skipped, 0 failed**; `npm run build` clean; `smoke-test-apis.sh` 11/11.
- `[PENDING]` prod: after both deploys, send a long question and confirm no red banner, then hard-refresh mid-answer and confirm the answer still lands.

**Not fixed, reported:**
- `[PENDING]` **Macro questions still route to the web.** "What is the current macro regime / which combo is dominant" → `WEB_RAG`, answered "transitional, mixed signals" from web sources while Runic says Combo F dominant, week 20 of 26, TACTICAL EASY MONEY. Same defect class as the original NZ complaint. Needs macro wording in `_RECOMMENDATION_QUERY_RE` **and** a new SOURCE D runic feed — a data source, not a regex.
- `[PENDING]` Per-ticker questions ("how is AAPL doing") miss `_CONVICTION_RELEVANT_RE`, so no conviction/fundamentals block.
- `[PENDING]` History-restore-on-refresh (`useClaudePanel.ts:82`) and the hardcoded SYSTEM tab rows remain.

---

## 2026-08-17 — Dead Claude model id + permanent "CPI pending" flag `[PENDING]`

**Highest-value item in this file right now.** Prod has been serving **template** macro narratives, not Claude ones, for as long as `claude-sonnet-4-20250514` has been retired. Every Claude call outside the chatbot 404s and falls back silently.

**Git files to merge** (`chatbot-dev` → `chatbot-prod`), commit **`87b5f1a83`**:
- `src/macro_intelligence/claude/_client.py` — default model
- `macro_intelligence/CONFIG.yaml` — `claude.model` and `geo_model`
- `src/conviction_engine/agent_dims.py` — `_DEFAULT_MODEL`
- `api/services/analyst_copy_service.py` — `ANALYST_CLAUDE_MODEL` default
- `src/macro_intelligence/output/json_writer.py` — `_pending_cpi_release` strictly-forward window
- `.env.example`, `tests/test_pending_cpi_release.py` (new)

`[PROD-ACTION]` **`.env` edit required on prod — the merge alone is not enough.** Prod `.env` pins `MACRO_CLAUDE_MODEL=claude-sonnet-4-20250514`; the env var beats both the YAML and the code default, so without this edit prod keeps producing template briefings even after merging:
```
MACRO_CLAUDE_MODEL=claude-sonnet-4-5-20250929
```
`[PROD-ACTION]` after the merge + `.env` edit, re-run the nightly on prod so the live snapshot carries a real Claude narrative instead of the template one currently on the page: `.venv/bin/python scripts/run_macro_nightly.py`. Then restart `mindwealth-api.service`.

`[PROD-ACTION]` check for the same dead id anywhere else in the prod environment: `grep -rn "claude-sonnet-4-20250514" /home/ubuntu/uiv2/prod/MindWealth_UI --include=*.py --include=*.yaml` plus its `.env`.

**Smoke tests:**
- `[DONE]` 2026-08-17 — `call_claude()` returns a real completion (was `404 not_found_error`).
- `[DONE]` 2026-08-17 — regenerated `runic_briefing_2026-08-17`; narrative is **7,233 chars of genuine Claude analysis**, reports CPI surprise **−0.026pp "not hot"**, and no longer claims a pending release.
- `[DONE]` 2026-08-17 — `GET /macro/runic/nightly` on `:8507` → `date 2026-08-17`, `pending_cpi_release: false`.
- `[DONE]` 2026-08-17 — `pytest tests/ -q` → **814 passed / 1 known Monday-only failure / 3 skipped**; `smoke-test-apis.sh` **11/11 PASS**.
- `[PENDING]` prod: after the `.env` edit + nightly re-run, confirm the MACRO tab narrative is multi-section Claude prose and carries no "A CPI release is pending this week" sentence.

**Open, needs Rohit's decision — do not silently patch:**
- `[PENDING]` `bls_pull.try_bls_cpi_pull()` stamps `release_date = datetime.now()`, so `pending_releases` records "the day the nightly ran" rather than the real CPI release date (identical `actual` rows on 08-10, 08-11, 08-13, 08-14, 08-17). This feeds `fetch_cpi_surprise_series()` **and** `get_upcoming_event()`, which is why `pre_catalyst` reports a CPI catalyst at `days_to_event: 0` with `HIGH — REGIME SENSITIVE TO CATALYST` every single day. Fixing it changes the meaning of a table the surprise series depends on.
- `[PENDING]` Two independent Claude model constants (`chatbot/config.py` vs the macro/conviction/analyst defaults) with no shared source of truth — the reason half the product kept working while the other half silently degraded. Consolidate.
- `[PENDING]` **`MindwealthUI_Vue` hardcodes the SYSTEM tab** — `server/utils/overwatch-panel.ts:141-155` returns `India CSV pipeline`, `Claude API` and `Tavily` as literal `status:'warn', detail:'Could not fetch from server'`; the UI never calls `GET /system/health`. The tab has never reflected real service state. Backend endpoint is correct and ready to wire.
- `[PENDING]` The regenerated Claude narrative contradicts itself once ("CPI came in hot" vs "−0.026pp, not hot") — prompt-level issue, newly visible now that Claude output actually reaches the page.

---

## 2026-08-17 — Chat history endpoint 500 (pandas metadata) + India health check casing `[PENDING]`

**⚠️ Merge-ordering constraint — read before the entry below.** These two files must merge **together with** the AI Analyst entry below, never after it. Prod does not 500 on `GET /chatbot/sessions/{id}/history` today only because prod still has the history-corruption bug that hides the defect: corrupt file → `load_history` returns `[]` → nothing to serialize. Shipping the durability fix alone turns prod's **silent history wipe into a hard 500 on every chat open**.

**Git files to merge** (`chatbot-dev` → `chatbot-prod`), commit **`a0e84384b`**:
- `api/services/chatbot_service.py` — `_jsonable` / `_jsonable_message` sanitizer applied in `get_history` for both `display` modes
- `api/services/system_health_service.py` — `_india_datetime_json()` tries `India` and `INDIA`
- `tests/test_api_chatbot.py` — `TestHistorySerialization` regression guard

`[PROD-ACTION]` restart `mindwealth-api.service` after merge. No env key, no runtime artifact, no dev-only config, **no API surface change** (same routes, same field names — only the value types inside `metadata.full_signal_tables` change from unserializable objects to JSON records, so no OpenAPI or API-doc update).

**Smoke tests:**
- `[DONE]` 2026-08-17 — `pytest tests/test_api_chatbot.py -q` → **9 passed**; `pytest tests/ -q` → **811 passed / 1 known Monday-only failure / 3 skipped**.
- `[DONE]` 2026-08-17 — dev `:8507` restarted, `smoke-test-apis.sh` all PASS, prod `:8506` isolation intact.
- `[DONE]` 2026-08-17 — live HTTP with a minted admin token: history **200** with `display=true` (367 KB) and **200** raw; `GET /system/health` → Tavily `ok`, Claude API `ok`, India `4503.3h ago`.
- `[PENDING]` prod: after merge, open a chat that has fetched signals and hard-refresh — history must return 200, not 500.

**Findings recorded, not fixed here:**
- `[PROD-ACTION]` **India pipeline is 6 months stale** — `trade_store/INDIA/data_fetch_datetime.json` last written **2026-02-11**. The casing bug was masking this behind "path not found". Core-repo cron issue; needs an owner.
- `[PENDING]` **`GET /system/health` is admin-only** (`require_admin`) — 7 of the 9 users in `config/users.json` are role `user`, so the SYSTEM tab can only render as unknown/offline for them. Needs a product decision: non-admin-safe summary endpoint, or hide the tab for non-admins.
- `[PENDING]` **Nuxt sends no `book_id`** to `GET /portfolio/nav` and `GET /signals/reports/portfolio-risk/latest` → repeated 422s. `MindwealthUI_Vue`, out of scope.
- `[PENDING]` 87 × `GET /auth/me` 401 in 3h — expired/missing browser token; may be a token-lifetime issue or just a stale tab.

---

## 2026-08-17 — AI Analyst: recommendation routing + conviction feed + 503 + history durability

**Git files to merge** (`chatbot-dev` → `chatbot-prod`):

*New files:*
- `chatbot/conviction_context.py` — SOURCE C block builder
- `chatbot/tools/mindwealth_api_client.py` — localhost HTTP client for our own API
- `chatbot/ticker_resolver.py` — bare-symbol → canonical symbol resolution
- `chatbot/tests/test_recommendation_routing.py`, `chatbot/tests/test_history_durability.py`

*Modified:*
- `prompts/engine.py` — `ROUTER_SYSTEM` rules 9-10; `ROUTER_USER_TEMPLATE` gains `{today}`
- `chatbot/agents/llm_router.py` — `apply_recommendation_internal_override` + current date
- `chatbot/chatbot_engine.py` — `_build_conviction_block`, SOURCE C injection on both paths, `assets` added to fetch metadata
- `chatbot/unified_extractor.py` — full ticker universe in prompt (was truncated at 100), ticker resolution
- `chatbot/smart_data_fetcher.py` — base-symbol match fallback, `_mentions_closed_position` relaxes open-only
- `chatbot/history_manager.py` — atomic `default=str` writes, corrupt-file quarantine, per-session locks
- `chatbot/config.py` — conviction flags; `DEEP_RESEARCH_TOTAL_TIMEOUT_SECONDS` 120 → 300
- `api/jobs/runner.py` — persist failed turns to history
- `chatbot/prompt_changelog.json` — `LLM_ROUTER_SYSTEM` v3

`[PENDING]` merge. **`[PROD-ACTION]`** restart `mindwealth-api.service` after merge — `chatbot/config.py` and prompt changes are read at process start.

**New env keys — all optional, safe defaults, nothing to copy:**

| Key | Default | Note |
|-----|---------|------|
| `ENABLE_CONVICTION_CONTEXT` | `true` | set `false` to disable the SOURCE C feed |
| `MINDWEALTH_API_BASE_URL` | *(empty)* | empty → derived from `API_PORT`; set explicitly if `API_PORT` is ever unset |
| `CONVICTION_CONTEXT_TIMEOUT_SECONDS` | `8` | per-HTTP-call cap |
| `CONVICTION_CONTEXT_MAX_ROWS` | `25` | rows per SOURCE C section |
| `CONVICTION_BOOK_ID` | `model` | only book exposing Sizer entries/exits |
| `DEEP_RESEARCH_TOTAL_TIMEOUT_SECONDS` | **300** (was 120) | also the UI's poll budget — see below |

`[PROD-ACTION]` **Verify `API_PORT=8506` stays set on `mindwealth-api.service`.** The conviction client derives its base URL from it. It is currently set, and the fallback is also `8506`, so this is a check rather than a change — but if the base URL is ever wrong the conviction sections silently degrade to omitted (by design, they never raise).

`[PROD-ACTION]` **No API-key change needed, but note the coupling:** the client sends `X-API-Key` read from the `API_KEY` env of its own process, calling `optional_api_key` (which is an alias for `require_api_key`, `api/dependencies.py:38-53`). Same process, same key — self-consistent. If prod ever splits the key per service, this breaks.

**No dev-only shortcuts in this change.** Nothing to revert at cutover.

### ⚠️ Required frontend follow-up — NOT fixed by this merge

The chat UI lives in `/home/ubuntu/MindwealthUI_Vue` (branch `ui-dev`, GitHub `D-ParthChauhan/MindwealthUI_Vue`), a **separate repo outside CLAUDE.md's editable scope**. This task was scoped backend-only by the user, so these remain open:

1. `[PENDING]` **Job polling is cached for 30 s** — `server/utils/mindwealth-client.ts:13-14,50-56` caches *all* GETs for `GET_CACHE_MS = 30_000`, including `GET /chatbot/jobs/<id>`. The 2.5 s poll loop in `mindwealth-data.ts:1319-1347` therefore only reaches the API once per 30 s. **This is the true cause of "Could not reach the analyst"**: job `4326975d` completed at 147 s, but the cached "running" response from 01:52:54 was still being served at the 01:53:24 deadline. Raising the backend timeout to 300 widens the budget to ~330 s and makes this rare — **it does not fix it.** Fix: exclude job-poll paths from the cache.
2. `[PENDING]` **On budget exhaustion the client 503s and loses the answer** — `server/api/chat.post.ts:50-53` maps `null` to a 503; the job id is not surfaced, so the client cannot resume polling for an answer that is still coming (or already finished). Fix: return the job id and keep polling.
3. `[PENDING]` **History not restored on hard refresh** — `useClaudePanel.ts:82` guards `loadSessionHistory` behind `sessionId`, and `restoreSessionFromStorage()` is only called from `toggle()`. With the panel embedded, a refresh shows an empty chat until the panel is toggled. Server-side history is now durable, so this is purely a client restore gap.
4. `[PENDING]` **Orphan sessions** — `persistSession()` runs only on success (`useClaudePanel.ts:176`), so a first-message failure in a new session leaves the server-created session id unknown to the client.
5. `[PENDING]` **All failures render one generic string** — the blanket `catch` at `useClaudePanel.ts:191-200` cannot distinguish timeout from network loss from a 500, which is why a *successful* answer surfaced as "check your connection".

**Smoke tests:**
- `[DONE]` 2026-08-17 — dev `:8507` restarted, all modules import, `GET /chatbot/config` → `deep_research_total_timeout_seconds: 300`.
- `[DONE]` 2026-08-17 — SOURCE C built all 5 sections against live dev API (buy list 19 rows, exit list 14, signal quality, conviction score sheet 19, fundamentals for FPH.NZ/MFT.NZ).
- `[DONE]` 2026-08-17 — `pytest chatbot/tests` → **44 passed** (14 new). Bare `['FPH','MFT']` filter now returns **665 rows** (was 0). `Timestamp`-in-metadata history payload round-trips.
- `[PENDING]` **Live end-to-end LLM replay of both original questions** — declined during implementation (paid call). Run this on dev before prod merge and confirm `result.metadata.route == "HYBRID"`, `flow_steps` contain `Conviction Overlay`, and the answer quotes real `Signal Quality Composite Score` values.
- `[PENDING]` Manual UI check on `:8514` after the above.

**Robust test + dev deploy `[DONE]` 2026-08-17** (the fix above was written but left uncommitted and unverified against a restarted service; this closes that gap):

- Committed as **`3547f7950`** on `chatbot-dev`, author `divsum127`, 15 files. **`chatbot/agents/synthesis_agent.py` was added to the merge set** — it is not part of this fix (dated 2026-08-02) but imports `build_signal_data_source_legend` from `chatbot/smart_data_fetcher.py`, which was itself uncommitted; the pair must move together or prod lands a consumer without its producer.
- `[DONE]` `pytest chatbot/tests -q` → **44 passed**; `pytest tests/ -q` → **810 passed, 1 failed, 3 skipped**. The failure is the pre-existing Monday-after-a-Friday-signal `test_shortlist_mtm_not_stale_zero_for_aged_signals` guard already documented above — unrelated, not a regression from this change.
- `[DONE]` Mock audit over all 15 committed files — no unintended mocks, no placeholder data, no stale-source shortcuts.
- `[DONE]` **No HTTP surface change** — the conviction feed only *consumes* existing endpoints, so no router/schema edit, no OpenAPI re-export, no API-doc page, no docs-submodule commit. `api/jobs/runner.py` gained error-persistence only. (The dirty `api/routers/macro.py` in the tree belongs to a different task and was deliberately left uncommitted.)
- `[DONE]` `mindwealth-api-dev.service` restarted 19:54:43 UTC; `smoke-test-apis.sh` **all PASS** — dev `:8507` `status=ok` v1.10.8, `conviction_store` isolated to the git clone and writable; **prod `:8506` untouched and still isolated** (v1.8.1).
- `[DONE]` Re-verified **against the restarted process**: all five consumed endpoints return `200` with the `.env` `X-API-Key`; SOURCE C rebuilds **5/5 sections, 10,027 chars** with `FPH.NZ` at rank 1 of the exit list; the recommendation override on Rohit's exact sentence yields `(internal=True, web=True)` ⇒ HYBRID; `resolve_tickers(['FPH','MFT','FRE'])` → `['FPH.NZ','MFT.NZ']` + `FRE` correctly reported as outside the universe.
- `[DONE]` Nuxt untouched — no `MindwealthUI_Vue` file in this change, so no `npm run build` and no `mindwealth-ui-dev` restart. The five frontend items above stay `[PENDING]`.

---

## 2026-08-17 — Rohit 6 Aug email status audit (docs-only) + prod defect escalation

**Git files to merge** (`chatbot-dev` → `chatbot-prod`) — documentation only, zero runtime impact:
- `docs/mindwealth_ui_job_status.md`
- `docs/mindwealth_ui_repo_job_status_details.md`
- `docs/dev_to_prod_migration_todos.md` (this entry)

`[PENDING]` merge only. No systemd change, no runtime artifact, no dev-only config, no API surface change, no Nuxt rebuild.

**Why it is listed here anyway — the audit escalated one live prod defect:**

`[PROD-ACTION]` **The 2026-08-07 `vix_bypass` A6 fix is still not on prod (see the entry immediately below).** Prod `:8506` continues to publish `vix_bypass: true` while Combo B is INACTIVE, and the C++ sizing model reads `macro_intelligence/output/runic_output.json` **from disk** — so on prod, `size_mult` is being forced to `1.0` and the SSI multiplier is discarded on ordinary days. Rohit flagged this specifically in the 6 Aug email ("we may be switching off the one overlay showing real risk value, every ordinary day") because the SSI overlay is the strongest risk contributor in Ahil's decomposition (Sharpe 0.82 → 1.04, drawdown −17.09% → −13.41%). This is now **10 days** stale on prod. Merge + nightly rerun + API restart, in that order — the checklist is in the 2026-08-07 entry below.

**Also surfaced by the audit, tracked but not prod-blocking:**
- `[PENDING]` Jun 18 spec doc still records SPX-below-200DMA as ×0.80 while both dev and prod code run ×0.90 (`instruction_docs/portfolio_page/portfolio_sizer_v2_18June.md:65`, `:257`). Rohit's instruction was "adopt ×0.90 and update the spec" — the code half is already correct on both environments, so this is a doc fix, not a cutover risk.
- `[PENDING]` Combo dominance priority still `C(100) > B(90) > F(80) > E > D > G > A` (`testing/5_regime_uplift/README.md:30`) against Rohit's explicit "move B above C". Research-path file, not read by the live sizing chain — but D1 regime buckets derived from it will need regenerating whenever the swap lands.
- `[PENDING]` Analog tables still served on both environments (`GET /macro/analogs/{combo_id}`, `src/pages/runic_page.py:90-95`) with stub data — Rohit asked for it pulled from the nav until rebuilt. Removing it is a prod-visible surface change and needs its own entry when done.
- `[PROD-ACTION]` Composite-score `401` for Ahil is a credential handoff, not a deploy: `X-API-Key` against `api/dependencies.py::require_api_key`. No git change; key must be shared over a secure channel (never in git, chat or logs).

**Environment drift noted for the next cutover:** dev is **22 commits ahead** of `origin/chatbot-prod` as of 2026-08-17 (dev `3a634b468`, prod clone `64e17ca26` from 2026-08-02). Nuxt `:8514` (dev, `ui-dev`) and `:8512` (prod) are therefore different builds — this is the cause of the two environments disagreeing about whether Combo C is firing, which Rohit asked about directly.

**Smoke test `[DONE]`** 2026-08-17 dev `:8507` — `smoke-test-apis.sh` **PASS** (dev v1.10.8 `status=ok`, `conviction_store` isolated to the git clone and writable; prod `:8506` v1.8.1 isolation intact). `pytest tests/` → **771 passed, 1 failed, 3 skipped**. The single failure is **pre-existing and unrelated to this docs change**: `tests/test_api_signals_surface.py::test_shortlist_mtm_not_stale_zero_for_aged_signals` compares a signal's **calendar** age against `days_elapsed`, which is sourced from the CSV column `Trading Days between Signal and Today Date` (`api/services/signal_enrichment_service.py:415`). PLTR fired Fri 2026-08-14 and `chatbot/data/entry.csv` correctly records `0 days` of *trading* days as of Mon 2026-08-17, so the guard trips on any Friday signal over a weekend. Upstream data is right; the test's threshold is calendar-based. **Left unfixed pending sign-off** — making it trading-day-aware changes what the guard catches (its purpose is catching genuinely stale MTM), so it should not be relaxed silently.

---

## 2026-08-07 — vix_bypass A6 fix (Combo B only)

**Git files to merge** (`chatbot-dev` → `chatbot-prod`):
- `src/macro_intelligence/engine/vix_bypass.py`
- `src/macro_intelligence/output/json_writer.py`
- `src/macro_intelligence/jobs/nightly_run.py`
- `macro_intelligence/CONFIG.yaml`
- `api/services/macro_service.py`
- `src/macro_intelligence/output/briefing_renderer.py`
- `src/pages/runic_page.py`
- `tests/test_ssi_vix_regime_oct_2022.py`

**Runtime (prod host, not git):**
- [ ] `cd /home/ubuntu/uiv2/prod/MindWealth_UI && git pull origin chatbot-prod`
- [ ] `.venv/bin/python scripts/run_macro_nightly.py` (regenerates `macro_intelligence/output/runic_output.json` with `vix_bypass: false` when Combo B inactive)
- [ ] `sudo systemctl restart mindwealth-api.service`
- [ ] Verify: `jq '{date,vix_bypass,active: [.active_combos[].combo]}' macro_intelligence/output/runic_output.json`
- [ ] Verify API: `GET /api/v1/macro/status` → `vix_bypass: false`, `vix_bypass_banner: null` (current prod state: F+E active, B inactive)

**Smoke test `[DONE]`** 2026-08-07 dev `:8507` — API v1.10.7; `GET /macro/status` → `vix_bypass: false`, `vix_bypass_banner: null`; `pytest` 761 passed; `smoke-test-apis.sh` PASS. **Prod `[PENDING]`** — merge + nightly + API restart.

---

## 2026-08-07 — Sentiment Layer 1–4 sidebar detail panels + regime block

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`; re-run `run_ssi_daily.py`; Nuxt rebuild.

| Area | Files |
|------|--------|
| Regime block (Layer 4) | `src/sentiment_superindex/engine/regime_block.py`, `src/sentiment_superindex/engine/positioning.py` |
| Spark history API | `api/services/reports_service.py` |
| Tests | `tests/test_ssi_regime_block.py`, `tests/test_sentiment_spark_data.py` |
| Nuxt UI | `MindwealthUI_Vue/pages/sentiment.vue`, `components/sentiment/SentimentLayerDetail.vue`, `components/sentiment/SparkLine.vue`, `server/utils/sentiment-mapper.ts`, `types/api.ts` |

**`[PROD-ACTION]`** `python scripts/run_ssi_daily.py` after merge so `positioning.json` includes `regime`.

**Smoke test `[DONE]`** 2026-08-07 dev `:8507` — `GET /analytics/sentiment/layers` → `regime.size_mult=1.2`, `spark_data.layer1` length 60; Nuxt `:8514` rebuilt + `mindwealth-ui-dev` active; sidebar L1–L4 panel switch pending manual UI click check.

---

## 2026-08-12 — Row 46 staleness calibration complete (per-signal penalties + margin debt)

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`; `run_ssi_daily.py`.

| Area | Files |
|------|--------|
| Caps + per-signal penalties | `macro_intelligence/SSI_CONFIG.yaml`, `src/sentiment_superindex/config.py`, `data/staleness.py`, `engine/superindex.py` |
| Margin debt fetch | `src/sentiment_superindex/data/margin_debt_pull.py`, `data/pull_all.py` |
| Test 21 + tests | `analysis/staleness_decay_study.py`, `tests/test_ssi_staleness.py`, `tests/test_margin_debt_pull.py`, `docs/ssi_validation/21_staleness_decay.md` |

**`[PROD-ACTION]`** `python scripts/run_ssi_daily.py` after merge.

**Smoke test `[PENDING]`:** stale AAII at 2d → weight_multiplier 1.0 (no penalty); stale COT FM at 7d → 0.18; CNN &gt;3d dropped.

**Ahil `[PENDING]`** rows 32/65 portfolio re-run after CNN/HY OAS (not blocking Row 46 code).

---

## 2026-08-07 — SSI staleness calibration (MAX_STALE_DAYS 8/3/30 + Test 21)

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`; re-run `run_ssi_daily.py`.

| Area | Files |
|------|--------|
| Staleness caps | `macro_intelligence/SSI_CONFIG.yaml`, `src/sentiment_superindex/config.py` |
| Test 21 study | `src/sentiment_superindex/analysis/staleness_decay_study.py`, `scripts/run_ssi_validation_suite.py` |
| Tests / docs | `tests/test_ssi_staleness.py`, `docs/ssi_validation/21_staleness_decay.md` |

**`[PROD-ACTION]`** `python scripts/run_ssi_daily.py` after merge so live scoring uses weekly=8, daily=3, monthly=30.

**Smoke test `[PENDING]`:** AAII 6d stale still carries (penalty); 9d dropped. CFTC 7d stale carries. CNN missing &gt;3d dropped.

**Deferred `[DONE]` 2026-08-12:** Per-signal `weight_penalty_by_signal` wired (Test 21 values). Rohit sign-off still needed before prod cutover.

---

## 2026-08-07 — SSI staleness calibration (MAX_STALE_DAYS 8/3/30 + Test 21) — superseded by 2026-08-12 Row 46 complete entry above

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`; Nuxt rebuild.

| Area | Files |
|------|--------|
| Staleness meta | `src/sentiment_superindex/engine/positioning.py`, `src/sentiment_superindex/data/cftc_patterns.py` |
| Shared freshness util + component | `MindwealthUI_Vue/utils/signal-freshness.ts`, `MindwealthUI_Vue/components/SignalFreshnessAnnotation.vue` |
| Sentiment mapper + detail UI | `MindwealthUI_Vue/server/utils/sentiment-mapper.ts`, `MindwealthUI_Vue/components/sentiment/SentimentLayerDetail.vue`, `MindwealthUI_Vue/types/api.ts` |
| Runic variables notes | `MindwealthUI_Vue/utils/macro-variables.ts` |

**`[PROD-ACTION]`** `python scripts/run_ssi_daily.py` so `inputs_meta.*` includes `max_stale_days` and `layer3_cftc.release_date`.

**Smoke test `[DONE]` 2026-08-12:** Nuxt `npm run build` PASS; `SentimentLayerDetail` renders `SignalFreshnessAnnotation` on tiles with `freshness` from mapper.

**Dev deploy `[DONE]` 2026-08-12:** `mindwealth-api-dev` + `mindwealth-ui-dev` restarted; `smoke-test-apis.sh` PASS; `GET /api/v1/macro/sentiment/positioning` returns `inputs_meta.layer1.*.max_stale_days` and `layer3_cftc.release_date`. Browser visual check on Sentiment tiles `[PENDING]` (human).

---

## 2026-08-07 — SSI layer detail scoring transparency (z / weight / contribution)

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`; Nuxt rebuild.

| Area | Files |
|------|--------|
| Superindex scoring | `src/sentiment_superindex/engine/superindex.py` |
| Tests | `tests/test_ssi_superindex.py` |
| Vue mapper | `MindwealthUI_Vue/server/utils/sentiment-mapper.ts` |
| API docs | `docs/mindwealth-api-docs/services/analytics/endpoints/get-sentiment-layers.md` |

**`[PROD-ACTION]`** `python scripts/run_ssi_daily.py` so `positioning.json` includes `contribution` + `effective_weight` on each component.

**Smoke test `[DONE]`** 2026-08-07 dev `:8507` — `GET /analytics/sentiment/layers` → `aaii_spread.contribution=0.0374`, `effective_weight=0.4364`, contributions sum to `layer1.score=0.0177`; API v1.10.6; `pytest` SSI/sentiment 29/29; full suite 759 passed (1 flaky `test_ssi_regime_block` in full run, passes isolated); `smoke-test-apis.sh` PASS; `run_ssi_daily.py` refreshed `positioning.json`; Nuxt `:8514` rebuilt + `mindwealth-ui-dev` active.

---

## 2026-08-07 — Layer 3 CFTC pattern flags (display + Overwatch, not sizing)

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`; Nuxt rebuild.

| Area | Files |
|------|--------|
| CFTC patterns | `src/sentiment_superindex/data/cftc_patterns.py`, `gross_net_flag.py`, `cftc_ssi.py` |
| Positioning + API | `src/sentiment_superindex/engine/positioning.py`, `api/services/reports_service.py`, `api/services/analyst_service.py` |
| Tests | `tests/test_cftc_patterns.py`, `tests/test_layer3_flags.py` |
| Nuxt | `MindwealthUI_Vue/server/utils/sentiment-mapper.ts`, `pages/sentiment.vue`, `constants/regime-strip.ts`, `server/api/overwatch.get.ts`, `composables/useOverwatch.ts`, `components/analyst/*`, `types/api.ts` |

**`[PROD-ACTION]`** `python scripts/run_ssi_daily.py` so `positioning.json` / `ssi.db` include `squeeze_setup`, `liquidity_exit`, `gross_net_divergence_active` on `layer3_cftc`.

**Smoke test `[PENDING]`:** `GET /analytics/sentiment/layers` → `layer3_flags.liquidity_exit` true when RM&lt;30 &amp; FM&gt;60; Sentiment page shows gold banner + Layer 3 ACTIVE rows; Overwatch MACRO tab shows `sentiment_warning` CFTC alert. Thresholds unvalidated until Rohit grid sign-off.

**🚫 `[MERGE-BLOCKER]` (added 2026-08-17)** — **do not promote this block to prod.** Sign-off is **HELD** on both patterns: §6 of `docs/ssi_validation/CFTC_PATTERN_THRESHOLD_REPORT_FOR_ROHIT_20260811.md` is unsigned, and the wired values (`CONFIG.yaml:344-345` — squeeze FM&lt;20/RM&gt;45, liquidity RM&lt;30/FM&gt;60) are the cells the 11 Aug re-run scores at **negative mean−median gap** (FM&lt;20/RM&gt;45 = −1.99% at 12w, i.e. market beta). Prod is currently clean (`cftc_patterns.py` absent from the prod clone), so the exposure only opens on merge + the `run_ssi_daily.py` PROD-ACTION above. Either hold the whole block, or merge the code with the pattern detector feature-flagged off until Rohit signs §6.

---

## 2026-08-04 — CFTC fm_pctile true rank audit (docstrings + tests)

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`.

| Area | Files |
|------|--------|
| Percentile engine | `src/macro_intelligence/engine/percentiles.py` |
| CFTC pull (diagnostic helper + docstrings) | `src/macro_intelligence/data/cftc_pull.py` |
| Tests | `tests/test_macro_percentiles.py` |

**Notes:** No formula change — `_rolling_pctile()` already used true `percentile_rank()`. This batch adds explicit docstrings, `describe_cftc_pctile_window()` diagnostic, and regression tests (rank ≠ min–max under outliers).

**Smoke tests:** `[DONE]` 2026-08-07 — `pytest tests/test_macro_percentiles.py` 11 passed; full suite 753 passed; `smoke-test-apis.sh` PASS on `:8507`.

---

## 2026-08-04 — Layer 1 `pct_above_200dma` history contamination fix

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`.

| Area | Files |
|------|--------|
| SSI metadata | `src/sentiment_superindex/engine/positioning.py` |
| Tests | `tests/test_ssi_display_rounding.py` |

**`[PROD-ACTION]`** After deploy on prod host:
```bash
cd /home/ubuntu/uiv2/prod/MindWealth_UI
python scripts/rebuild_ssi_history.py          # ~32 min; recomputes 3,173 dates
sqlite3 macro_intelligence/data/ssi/ssi.db \
  "DELETE FROM ssi_daily WHERE json_extract(payload_json, '\$.layers.layer1.components.pct_above_200dma') IS NOT NULL;"
python scripts/run_ssi_daily.py
```

**Smoke test `[PENDING]`:**
- `GET /api/v1/analytics/sentiment/layers` → `inputs_meta.layer1` has no `pct_above_200dma`; `inputs.layer2.pct_above_200dma` populated.
- `ssi.db`: zero rows with `pct_above_200dma` in `layers.layer1.components`.

**Retroactive warning:** All `layer1_score` / composite percentiles derived from pre-fix `ssi.db` history were inflated by 200DMA in Layer 1 (~mean |Δ| 0.10 on layer1).

---

## 2026-08-04 — SSI VERIFY pointers 1–5 (completion plan)

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`; rebuild/restart Nuxt prod.

| Area | Files |
|------|--------|
| API / SSI | `src/sentiment_superindex/engine/layer2.py`, `positioning.py`, `data/cftc_patterns.py`, `data/cftc_ssi.py`, `macro_intelligence/data/cftc_pull.py`, `macro_intelligence/CONFIG.yaml`, `api/services/macro_service.py`, `api/services/analyst_service.py`, `tests/test_ssi_layer2.py`, `tests/test_cftc_patterns.py`, `tests/test_positioning_cftc_meta.py`, `tests/test_ssi_display_rounding.py` |
| Nuxt (separate repo) | `MindwealthUI_Vue/server/utils/sentiment-mapper.ts`, `utils/signal-freshness.ts`, `utils/macro-variables.ts`, `components/runic/MacroSsiPanel.vue`, `components/runic/RunicBriefPanel.vue`, `types/api.ts`, `server/utils/runic-mappers.ts` |
| API docs | `docs/mindwealth-api-docs/changelog.md`, `services/analytics/endpoints/get-sentiment-layers.md` |

**`[PROD-ACTION]`** `python scripts/run_ssi_daily.py` after API deploy (refreshes `ssi_multiplier` from 6-gate sizing + CFTC pattern fields in `positioning.json` / `ssi.db`).

**Smoke tests `[DONE]` 2026-08-04 (dev):**
- pytest targeted SSI: 64 pass; **full suite: 753 passed, 2 skipped**
- `smoke-test-apis.sh`: PASS (dev `:8507` version **1.10.5**, conviction_store isolated)
- Live `GET /analytics/sentiment/layers`: 6 gate keys (no dbmf/cnn); `layer3_cftc.data_freshness` + `inputs_meta.layer3_cftc` present; L2 `UNCONFIRMED` / mult `0.8` from 6-gate sizing
- Live `GET /macro/ssi/summary`: `layer2_gate_label` + 6-gate `inputs` keys
- `run_ssi_daily.py` refreshed `positioning.json` + `ssi.db`
- Nuxt: `mindwealth-ui-dev` restarted (prior `npm run build` OK)
- **Note:** `nh_nl_ratio` raw/norm `null` on 2026-08-04 live payload (upstream series gap — pre-existing data, not deploy regression)

**Smoke tests `[PENDING]` (prod):** Sentiment page COT two lines; MacroSsiPanel `layer2_gate_label`; `GET /analytics/sentiment/layers` JSON shape on `:8506`.

**Google Sheet:** rows C67–C71 — update to Completed pending explicit user OK to write sheet.

---

## 2026-08-04 — SSI Layer 2 directional gate counts (CRITICAL)

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`; rebuild/restart Nuxt.

| Area | Files |
|------|--------|
| API / SSI | `src/sentiment_superindex/engine/layer2.py`, `positioning.py`, `api/services/reports_service.py`, `tests/test_ssi_layer2.py`, `tests/test_sentiment_layers_gate_votes.py` |
| Nuxt (separate repo) | `MindwealthUI_Vue/server/utils/sentiment-mapper.ts` |

**`[PROD-ACTION]`** `python scripts/run_ssi_daily.py` (or rely on API `_ensure_layer2_gate_votes` backfill on next `GET /analytics/sentiment/layers`).

**Smoke test `[DONE]`** 2026-08-04 dev `:8507` — `GET /analytics/sentiment/layers` returns `layer2_gate_conf_long=3`, `layer2_gate_conf_short=0`, `layer2_gate_direction=LONG_CONFIRMED`, `layer2_gate_label` set; `pytest tests/test_ssi_layer2.py tests/test_sentiment_layers_gate_votes.py` 8/8; full suite 753 passed; `smoke-test-apis.sh` PASS; Nuxt `:8514` rebuilt + `mindwealth-ui-dev` active.

---

## 2026-08-04 — NH Share gate row shows z-score not raw share

`[DONE]` 2026-08-04 — Nuxt rebuild + `mindwealth-ui-dev` restart (`MindwealthUI_Vue`). Backend gate logic unchanged.

| Area | Files |
|------|--------|
| Nuxt | `MindwealthUI_Vue/server/utils/sentiment-mapper.ts` — norm-gated Layer 2 rows display `norm` (aligned z) so badge direction matches printed value |
| Tests | `tests/test_ssi_layer2.py` — nh_nl raw-high/norm-negative → bearish gate |

**Smoke test `[DONE]` 2026-08-04:** Live API `nh_nl_ratio` gate `raw=0.571`, `norm=-0.598`, `signal=bearish`. Post-rebuild `mapSentimentLayers()` → NH Share row **`-0.60 ✓ bearish`** (not `+0.57 ✓ bearish`). Build `.output/server/index.mjs` 2026-08-04T09:33:30Z; `mindwealth-ui-dev` active on `:8514`.

---

## 2026-08-04 — SSI partial layer signal coverage UI

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`; rebuild/restart Nuxt (`mindwealth-ui-dev` or prod UI service).

| Area | Files |
|------|--------|
| API / SSI | `src/sentiment_superindex/engine/positioning.py`, `tests/test_ssi_superindex.py` |
| Nuxt (separate repo) | `MindwealthUI_Vue/server/utils/sentiment-mapper.ts`, `pages/sentiment.vue`, `types/api.ts` |

**`[PROD-ACTION]`** After API deploy: `python scripts/run_ssi_daily.py` so `positioning.json` includes `layers.*.signal_coverage`.

**Smoke test `[DONE]`** 2026-08-04 dev `:8507` — `GET /analytics/sentiment/layers` → `positioning.layers.layer1.signal_coverage.weights_renormalized=true`, `available_count=3`, `configured_count=4` (today `naaim_exposure` expired, not put/call); `run_ssi_daily.py` refreshed `positioning.json`; `pytest` SSI/sentiment 17/17 + API 174/174; `smoke-test-apis.sh` PASS; Nuxt `:8514` rebuilt + `mindwealth-ui-dev` active.

---

## 2026-08-02 — Conviction Engine Fixes v2 (bank/hardware business types, coverage-incomplete gate, FS-score slice rebuild, CRM bug fix)

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`. Pure application code, **no new `.env`/secrets/config needed**. After merge, prod's existing `conviction_store/*.json` records will keep using their old `business_type`/`fs_score`/`valuation_tax` values until each ticker's next full recalculation — run the classification-only pass (cheap) or a full universe recalc (thorough) as a `[PROD-ACTION]` follow-up:

```bash
cd /home/ubuntu/uiv2/prod/MindWealth_UI
# Cheap option: classify-only, auto-queues full recalc ONLY for tickers that flip into
# bank / high_margin_hardware / coverage_incomplete (see item 12 of the plan):
.venv/bin/python scripts/run_universe_classification_pass.py
# Thorough option: full recalc for every ticker (also picks up the FS-score-slice
# rebuild, the growth-fragility/floor bugfix, and adjusted-EPS for ALL tickers, not
# just the 3 flipped buckets — recommended once, to fully retire the pre-fix formulas
# universe-wide; the classification pass alone leaves non-flipped tickers on the old
# FS-score/valuation-tax numbers until their own natural recalc cadence):
.venv/bin/python scripts/update_conviction_fundamentals.py --mode full --include-existing-records
```

| Path | Notes |
|------|-------|
| `src/conviction_engine/models.py` | **modified** — `BANK`/`HIGH_MARGIN_HARDWARE` business types, `KNOWN_BUSINESS_TYPES`, new record fields, `SignalModification.coverage_incomplete` |
| `src/conviction_engine/scoring.py` | **modified** — bank/hardware detection + valuation-tax substitutions, universal floor/fragility bugfixes, rebuilt `fs_score_breakdown()`, `coverage_incomplete` hard gate, KR/JP/CN undefined yield-trap thresholds |
| `src/conviction_engine/engine.py` | **modified** — wires all of the above into `daily_update()`/`full_recalculation()`/`modify_signal()`/`run_daily_universe()` |
| `src/conviction_engine/agent_dims.py` | **modified** — G2 source exclusion for hardware/semi sector, new deal-delay agent, TAM three-tier sourcing prompt |
| `src/conviction_engine/capital_allocation.py` | **modified** — standalone buyback-suspension/dividend-cut tiered penalty flags |
| `src/conviction_engine/fundamentals_enriched.py` | **modified** — bank/hardware fundamentals fetch, capital-return flags wiring, adjusted-EPS wiring, Tier 2 non-US PE-history fallback wiring |
| `src/conviction_engine/fundamentals.py` | **modified** — new classification-only universe diff pass (`classify_universe_diff`/`run_universe_classification_pass`) |
| `src/conviction_engine/bq_scoring.py` | **modified** — `score_deal_delay_risk()` prefers live agent detail over legacy binary flag |
| `src/conviction_engine/pe_history_core.py` | **modified** — `reconstruct_quarterly_eps_from_net_income()` Tier 2 fallback |
| `src/conviction_engine/bank_valuation.py` | **new** — efficiency-ratio margin quality, equity/assets balance sheet, P/TBV-vs-ROE valuation tax + FS slice |
| `src/conviction_engine/adjusted_eps.py` | **new** — trailing effective-tax-rate adjusted EPS + materiality-gated adjusted PE |
| `src/conviction_engine/tam_sourcing.py` | **new** — SEC XBRL `RevenueRemainingPerformanceObligation` Tier 1 TAM fetch |
| `scripts/run_universe_classification_pass.py` | **new** CLI — see prod-action commands above |
| `src/pages/conviction_engine_page.py` | **modified** — FS-cap/yield-trap breakdown display + agentic-dimension sourcing transparency (Streamlit UI, dev-only tool, no prod-user-facing impact) |
| `api/schemas/conviction.py` | **modified** — `SignalModificationResponse.coverage_incomplete` field |
| `instruction_docs/conviction_engine_issues/conviction_fixes_decisions.md` | **new** — decisions/rationale log, docs only |
| `tests/test_conviction_engine_v2_fixes.py` | **new** — 49 tests |
| `tests/test_conviction_engine.py` | **modified** — 1-field fixture fix (`test_fs_cap_differs_by_timeframe`) |

**Parth's Vue frontend (separate repo, not in this migration's scope but flagged for him):** new `COVERAGE INCOMPLETE` verdict string needs a color/label case; `yield_trap_breakdown.fired` vs `.watching` and `run_daily_universe()`'s `yield_trap_watching` alert-map flag are now available to reconcile the Yield-Traps panel's count-vs-list display; `fs_cap_breakdown`/`valuation_tax_breakdown` are on every record returned by `GET /conviction/tickers/{ticker}` for the Engine Layers click-through panels shown in `engine_layers_spec.html`.

**Smoke test `[DONE]` 2026-08-02:** dev `:8507` — `smoke-test-apis.sh` all PASS; `GET /conviction/tickers/JPM` shows `business_type=bank` + `bank_ptbv_detail`; `POST /conviction/signals/evaluate` on `BRK-B` returns `COVERAGE INCOMPLETE` + `coverage_incomplete=true`; `GET /conviction/alerts/daily` includes `coverage_incomplete`/`yield_trap_watching` flags. Full dev recalc already run: 195/195, 0 errors.

---

## 2026-08-02 — Layer 2 gate votes (McClellan confirm badge)

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`; `scripts/run_ssi_daily.py`; Nuxt rebuild + restart `mindwealth-ui-dev`.

| Path | Notes |
|------|-------|
| `src/sentiment_superindex/engine/layer2.py` | `evaluate_layer2_gates()` — 6-input gate votes |
| `src/sentiment_superindex/engine/positioning.py` | `inputs.layer2_gate_votes`, `layer2_gate_confirmed_count` |
| `api/services/reports_service.py` | `_ensure_layer2_gate_votes()` backfill when positioning.json stale |
| `macro_intelligence/SSI_CONFIG.yaml` | `layer2.gate_z_min: 0.5` |
| `tests/test_ssi_layer2.py` | Gate vote regression (McClellan included) |
| `tests/test_sentiment_layers_gate_votes.py` | API backfill regression |
| `MindwealthUI_Vue/server/utils/sentiment-mapper.ts` | Inline ✓/✗ on all 6 Layer 2 rows; NH label → `NH Share (NH/(NH+NL))` |
| `docs/mindwealth-api-docs/services/analytics/endpoints/get-sentiment-layers.md` | Field reference for gate votes |

**Smoke:** `[DONE]` 2026-08-02 dev `:8507` — `GET /analytics/sentiment/layers` returns `layer2_gate_votes` length 6 (`mcclellan` … `pct_above_200dma`), `layer2_gate_confirmed_count=3`; `pytest tests/test_sentiment_layers_gate_votes.py` 4/4; `smoke-test-apis.sh` PASS; Nuxt `:8514` rebuilt + `mindwealth-ui-dev` active.

---

## 2026-08-04 — Weekly staleness cap 5→10 (Super Sentiment unavailable fix)

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`; rerun `scripts/run_ssi_daily.py`.

| Path | Notes |
|------|-------|
| `macro_intelligence/SSI_CONFIG.yaml` | `staleness.max_stale_days.weekly` **5 → 10** |
| `src/sentiment_superindex/config.py` | Default `MAX_STALE_DAYS["weekly"]` **10** |
| `src/sentiment_superindex/engine/positioning.py` | `_layer3_display_value()` CFTC snapshot fallback |
| `tests/test_ssi_staleness.py` | CFTC 7d carry regression; align weekly ffill 10d |

**Smoke test `[DONE]`** 2026-08-04 dev `:8507` — `GET /analytics/sentiment/layers` → `layer3.cftc_fm_net=-302372`, `naaim_exposure=79.7`; `mapSentimentLayers()` 0 unavailable; `pytest test_ssi_staleness test_sentiment_layers_gate_votes` 13/13; `smoke-test-apis.sh` PASS; `mindwealth-api-dev` restarted.

---

## 2026-08-04 — SSI staleness policy wired to live scoring (MAX_STALE_DAYS / STALE_WEIGHT_PENALTY)

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`; rerun `scripts/run_ssi_daily.py`.

| Path | Notes |
|------|-------|
| `macro_intelligence/SSI_CONFIG.yaml` | New `staleness.max_stale_days` (weekly **10** / daily 1 / monthly 25) + `weight_penalty: 0.8` |
| `src/sentiment_superindex/config.py` | `MAX_STALE_DAYS`, `STALE_WEIGHT_PENALTY`, `SSI_INPUT_CADENCE`, `staleness_policy()` |
| `src/sentiment_superindex/data/staleness.py` | **new** — `observation_as_of`, `effective_input_weights` |
| `src/sentiment_superindex/engine/superindex.py` | Live scoring uses staleness caps + weight penalty |
| `src/sentiment_superindex/data/alignment.py` | Cadence-aware default ffill limits from config |
| `src/sentiment_superindex/data/pull_all.py` | `values_as_of` aligned to staleness policy |
| `tests/test_ssi_staleness.py` | **new** regression (monthly 25d, AAII penalty renorm) |

**Smoke test `[PENDING]`:** `build_superindex(today)` → stale AAII mid-week shows `signal_coverage.stale` includes `aaii_spread` and `effective_weights.aaii_spread` < nominal 0.30; monthly `align_to_daily(..., cadence="monthly")` carries 25 rows not 5.

---

## 2026-08-04 — Put/Call Layer 1 restore + spec weights (30/35/20/15)

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`; rerun SSI daily; rebuild Nuxt UI.

| Path | Notes |
|------|-------|
| `src/sentiment_superindex/data/put_call_pull.py` | **new** — CBOE total P/C CSV + CNN gap fill; 10-week EMA |
| `macro_intelligence/data/ssi/put_call_ema.csv` | **new** runtime cache (commit or bootstrap on deploy host) |
| `macro_intelligence/data/ssi/put_call_ratio_raw.csv` | **new** raw cache |
| `macro_intelligence/SSI_CONFIG.yaml` | `put_call_ema` in layer1; `layer1_input_weights` 30/35/20/15 |
| `src/sentiment_superindex/data/pull_all.py` | `fetch_put_call_ema()` |
| `src/sentiment_superindex/engine/superindex.py` | Spec-weight Layer 1 composite + `signal_coverage` |
| `macro_intelligence/DATA_SOURCES.yaml` | `PUT_CALL_EMA` var |
| `tests/test_put_call_pull.py`, `tests/test_ssi_superindex.py` | Regression incl. missing-P/C renormalization |
| `MindwealthUI_Vue/server/utils/sentiment-mapper.ts` | Layer 1 header "N of 4 signals"; Put/Call row always shown |

**Smoke test `[PENDING]`:** `GET /api/v1/analytics/sentiment/layers` → `positioning.layers.layer1.components.put_call_ema.raw` populated; `signal_coverage.available_count == 4`; Sentiment Layer 1 header not "3 weekly inputs".

**Smoke test `[DONE]`** 2026-08-04 dev `:8507` — `put_call_ema.raw` ≈ 0.766; `signal_coverage.configured_count=4`; `nominal_weights` 30/35/20/15; `pytest tests/test_ssi_superindex.py tests/test_put_call_pull.py tests/test_ssi_staleness.py` 20/20; full `pytest tests/` 753 passed; `smoke-test-apis.sh` PASS (dev v1.10.5). NAAIM may show `expired` when `stale_days > 5` (weekly cap) — separate staleness policy, not Put/Call fetch failure.

---

## 2026-08-02 — AAII weekly cadence metadata (Sentiment Layer 1)

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`; deploy Vue `ui-dev` for label change.

| Path | Notes |
|------|-------|
| `src/sentiment_superindex/engine/positioning.py` | New `inputs_meta.layer1` (`cadence`, `as_of`, `schedule_et`, `stale_days`, AAII `source`) |
| `tests/test_ssi_display_rounding.py` | Regression for AAII weekly `as_of` |
| `MindwealthUI_Vue/server/utils/sentiment-mapper.ts` | Layer 1 sub-label: `Weekly (Thu) · as of YYYY-MM-DD` instead of `Live` |

**`[PROD-ACTION]`** After deploy: `python scripts/run_ssi_daily.py` to refresh `positioning.json` with `inputs_meta`.

**Smoke test `[PENDING]`:** `GET /api/v1/analytics/sentiment/layers` → `positioning.inputs_meta.layer1.aaii_spread.cadence == "weekly"`, `as_of` is latest Thursday; Sentiment page AAII row sub-label shows `Weekly`, not `Live`.

---

## 2026-08-02 — Move % Above 200DMA to SSI Layer 2

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`. SSI layer grouping fix; rerun SSI daily job after deploy so `positioning.json` reflects new layer components.

| Path | Notes |
|------|-------|
| `macro_intelligence/SSI_CONFIG.yaml` | `pct_above_200dma` moved layer1 → layer2 |
| `src/sentiment_superindex/engine/superindex.py` | `DEFAULT_LAYER_INPUTS` layer assignment |
| `src/sentiment_superindex/engine/positioning.py` | Display inputs bucket `inputs.layer2` |
| `macro_intelligence/DATA_SOURCES.yaml` | `PCT_ABOVE_200DMA.system` → `ssi_layer2` |
| `docs/mindwealth-api-docs/services/analytics/endpoints/get-sentiment-layers.md` | Example payload |
| `tests/test_ssi_superindex.py` | Layer assignment regression |
| `tests/test_ssi_display_rounding.py` | Display bucket regression |

| `api/main.py` | `API_VERSION` → `1.10.3` |
| `docs/mindwealth-api-docs/changelog.md` | v1.10.3 layer-assignment fix note |
| `docs/mindwealth-api-docs/openapi/mindwealth-v1.json` | Regenerated |

**`[PROD-ACTION]`** After deploy: `python scripts/run_ssi_daily.py` (or wait for cron) to refresh `macro_intelligence/output/positioning.json`.

**Smoke test `[DONE]`** 2026-08-02 dev `:8507` — `GET /analytics/sentiment/layers`: `pct_above_200dma` under `positioning.inputs.layer2` only (value 67.86); `positioning.layers.layer2.components.pct_above_200dma` populated; `pytest tests/test_ssi_superindex.py tests/test_ssi_display_rounding.py tests/test_sentiment_layers_gate_votes.py` 14/14; full `pytest tests/` 721 passed; `smoke-test-apis.sh` PASS (dev version 1.10.3).

---

## 2026-07-31 — Fix: chatbot pulls in wrong web "resistance" levels for signal queries

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`. Chatbot/prompt-only; no new `.env` keys, no systemd or API route changes.

| Path | Notes |
|------|-------|
| `chatbot/agents/llm_router.py` | New `_INTERNAL_LEVEL_QUERY_RE` / `_WEB_ONLY_SIGNAL_RE` regexes + `apply_internal_level_override()` pure function; wired into `LLMRouter.route()` to force `needs_web_search=False` for entry/exit/target/stop/resistance/pivot/F-Stack queries unless genuine web-only wording (news/earnings/macro) is also present |
| `prompts/engine.py` | `ROUTER_SYSTEM` rule 8 added (internal-only for level/resistance/take-profit/stop-loss questions); new `SYNTHESIS_INSTRUCTIONS_LEVELS_GUARD` block, unconditionally wired into `build_synthesis_instructions()` |
| `chatbot/chatbot_engine.py` | `_TARGETS_STOP_QUERY_RE` widened (adds `resistance`, `support level`, `entry level`, `exit level`, `recent entry`, `recent exit`, `pivot`) |
| `chatbot/smart_data_fetcher.py` | Duplicate `_TARGETS_STOP_QUERY_RE` widened identically (kept in sync with the copy above) |
| `tests/test_llm_router_guardrails.py` | **new** — 13 tests (6 with subtests) covering the override, non-override cases, and both widened regex copies |

**`[DEV-ONLY]` / config note:** none — pure logic/prompt change, no dev-only shortcuts or hardcoded `:8507`-style URLs introduced.

**Prod runtime action needed:** none beyond the standard git merge + `prod-pull-and-restart.sh` (no new secrets, no DB/CSV migration).

**Smoke test `[DONE 2026-07-31, dev only]`:** Replayed Rohit's exact query "recent exit levels and entry levels for Google and NVDA" directly against `ChatbotEngine.smart_followup_query` on dev (real OpenAI + Tavily clients). Router log showed `conv=False internal=True web=False`, `route=INTERNAL`; response metadata `web_search_used=false`, `web_sources=[]` — no web search executed, so no web "Resistance Levels Context" section can appear. Fetched entry columns included `Targets (...)` and `Stop Loss (...)`. **`[PENDING]` re-run same smoke test on prod after this merge + restart** to confirm identical routing behavior there.

**Known unrelated blocker found during this smoke test (separate from this fix, also needs prod verification before/at cutover):** dev's `.env` `ANTHROPIC_API_KEY` / `CLAUDE_API_KEY` currently point at an Anthropic account with insufficient credit (`Your credit balance is too low to access the Anthropic API`), which blocks all chatbot final-answer generation in dev right now. Confirm prod's Anthropic key/account has available credit before relying on prod smoke-test output; if prod shares the same billing account this will also block prod chatbot answers until a human tops up/rotates the key.

---

## 2026-07-30 — Chatbot Signal Data Source labels on entry rows

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`. Chatbot-only; no API route or systemd changes.

| Path | Notes |
|------|-------|
| `chatbot/smart_data_fetcher.py` | `Signal Data Source` column on entry rows; `build_signal_data_source_legend()` |
| `chatbot/chatbot_engine.py` | Legend injected into smart_query prompt |
| `chatbot/agents/synthesis_agent.py` | Legend injected into synthesis prompt |
| `tests/test_smart_data_fetcher_dates.py` | Updated tests |

**Smoke test `[PENDING]`:** Ask chatbot "outstanding signals for NVDA" — JSON context rows should include `Signal Data Source` field; legend block should state only `outstanding` = UI page.

---

## 2026-07-29 — Macro Regime System Fix-to-Spec Plan (HY OAS recalibration, CNN F&G evaluation, regime-history bridge)

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`. All-code/docs/data-recalibration change; no new runtime secrets or `.env` keys required. Safe to bundle with other pending `chatbot-dev` entries below.

**Context:** full plan implementation — see job status 2026-07-29 entry #7 and job status details same date for the complete breakdown. Three in-scope items: HY OAS proxy recalibration, HY-consumer proxy-tier audit, and a new historical regime-history API bridge for Ahil's backtest engine.

| Path | Notes |
|------|-------|
| `scripts/recalibrate_hy_oas_proxy.py` | **new** — one-off/rerunnable script that recalibrated all `PROXY`-tier `HY` rows in `runic.db` (`daily_readings` table) to the new VIX-amplified Model v2. **Already run against dev's `runic.db`** — this is a data-layer change, not a git-file merge in the usual sense. Prod's `runic.db` (or equivalent nightly-refreshed DB) needs this script run once against it too, or needs to inherit the recalibrated rows via whatever the normal `runic.db` sync/copy mechanism is — confirm with whoever owns the prod nightly-data refresh path before assuming a plain `git merge` covers this (the DB itself is very likely **not** tracked in git). |
| `src/macro_intelligence/output/regime_feed_export.py` | **new** — maintained regime feed module backing the new API endpoint |
| `api/routers/macro.py` | new `GET /macro/regime/history` route |
| `api/services/portfolio_service.py` | `_compute_ceiling` now returns `hy_tier`/`hy_is_proxy`; `hy_note` gets a `[PROXY: ...]` suffix when applicable — **additive fields only, no existing response field changed shape**, safe non-breaking merge |
| `src/macro_intelligence/engine/combo_detector.py` | docstring-only changes (documents 2 known HY-PROXY blind spots), **zero logic change** — trivially safe to merge |
| `src/portfolio_nav/four_book_engine.py` | 4 new standalone functions (`load_vix_mult_series`, `load_spx_trend_mult_series`, `load_hy_mult_series`, `load_full_ceiling_chain_series`) + docstring update; **not wired into any existing endpoint**, so zero behavior change to anything currently live |
| `tests/test_api_macro.py` | 2 new tests (`test_regime_history`, `test_regime_history_empty_range`) |
| `docs/ssi_validation/*.md` (4 new files), `docs/plans/*.md` (3 new files), `docs/MACRO_INTELLIGENCE_MASTER.md`, `docs/ssi_validation/data_gap_report_2026-06-06.md` | docs only |
| `docs/mindwealth-api-docs/services/macro/endpoints/get-regime-history.md`, `services/macro/README.md`, `changelog.md` (`v1.10.0`) | API docs — also mirrored to the separate `mindwealth-api-docs` GitHub repo per that repo's own publish step, not yet pushed there (only committed/updated in this working copy so far) |

**`[DEV-ONLY]` / config note:** none — no dev-only shortcuts, feature flags, or hardcoded `:8507`-style URLs introduced by this change.

**Two items intentionally NOT deployed anywhere yet (awaiting Rohit sign-off, tracked separately, not a deploy blocker for the rest):**
- `docs/plans/regime_source_of_truth_decision_2026-07-29.md` — `macro_regime_log_v2` is not yet designated the production regime source; new code ships tagged `regime_source="macro_regime_log_v2"` so this is safe to deploy either way.
- `docs/plans/multiplier_signoff_request_2026-07-29.md` — dimension-multiplier table ships tagged `multiplier_version="v1_illustrative_unsigned"`; no production code path consumes it yet (only the new history endpoint and the pre-existing Test 5 script), so this is also safe to deploy pending sign-off.

**Smoke tests** `[PENDING]`:
- `GET /api/v1/macro/regime/history?start=2020-01-01&end=2020-01-10` on prod returns 200 with 5-10 rows, each tagged `regime_source`/`multiplier_version`.
- `GET /api/v1/portfolio/nav` (or any endpoint touching `_compute_ceiling`) on prod still returns 200 with the existing response shape plus the new `hy_tier`/`hy_is_proxy` keys — confirm nothing downstream (Nuxt BFF) chokes on the two new keys.
- Confirm prod's `runic.db` `daily_readings` HY rows reflect the Model v2 recalibration (spot-check a known PROXY-era date, e.g. `2022-06-13`, for a wider/more-stressed raw value than the old flat-linear proxy) — **only after** the data-layer question above (script rerun vs DB sync) is resolved with the DB owner.

---

## 2026-07-31 — New Signals SIGNAL DATE timezone display fix (Nuxt BFF)

`[PENDING]` — rebuild + restart Nuxt UI on host (`MindwealthUI_Vue` separate repo)

| Path | Notes |
|------|--------|
| `MindwealthUI_Vue/utils/signals.ts` | `formatSignalDate()` — parse YYYY-MM-DD as calendar date, not UTC midnight |

**Smoke tests** `[PENDING]`:
- New Signals: header report date and SIGNAL DATE column show same trading day (e.g. both Jul 28 in US Eastern)
- Outstanding / All Signal tables show correct signal dates

---

## 2026-07-29 — Conviction page timestamp alignment (Nuxt BFF)

`[PENDING]` — rebuild + restart Nuxt UI on host (`MindwealthUI_Vue` separate repo)

| Path | Notes |
|------|--------|
| `MindwealthUI_Vue/server/utils/mindwealth-data.ts` | `loadConviction()` `asOf` now uses `loadMeta().data_updated_at.date` (matches top bar) instead of `max(last_daily_update, overlay date)` |

**Smoke tests** `[PENDING]`:
- On `/conviction`, top-bar date and regime-strip `SOURCE … as of YYYY-MM-DD` refer to the same trading day
- After conviction daily cron runs mid-day, strip date does not jump ahead of header until trade-store batch updates

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

**Overview unblock — DONE:** user asked to proceed with commit + push + merge + deploy. Committed the full accumulated `chatbot-dev` tree (279 files, commit `6bc1343e6`) and pushed `docs/mindwealth-api-docs` (`1026c45`, SSH `ahiliitb`). `git push origin chatbot-dev` initially failed (no HTTPS credential helper; SSH key `ahiliitb` lacks write access to canonical `divsum127/MindWealth_UI`). User supplied a GitHub PAT with write access; used it for a single one-off `git push https://<PAT>@github.com/divsum127/MindWealth_UI.git chatbot-dev` (never persisted to git config/remote) — succeeded (`a5b6a960f`). Merged `chatbot-dev` → `chatbot-prod` locally (clean, zero conflicts, commit `2d922fe3f`), pushed to `origin/chatbot-prod`, then ran `scripts/prod-pull-and-restart.sh` in the prod clone (`/home/ubuntu/uiv2/prod/MindWealth_UI`) — fast-forwarded to `2d922fe3f`, `pip install` (no new deps), `systemctl restart mindwealth-api.service` restarted cleanly. **Live-verified on prod (:8506):** `/health` ok + isolated conviction_store; `/portfolio/nav?book_id=model&book=base` now returns full payload (previously 404 — headline blocker closed); `/portfolio/sizer` carries `cross_function_exit`/`asset_class`/`status`; `/signals/reports/portfolio-risk/latest` resolves real `implied_natural_exit_date` values. `smoke-test-apis.sh` all `PASS`.

### Status: `[DONE]` — deployed to prod, live-verified 2026-07-27

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

**Universe rollout — dev `[DONE]` 2026-07-29, prod `[PENDING — requires human/ops action, not agent-executable]`:**
- **Dev**: ran `python scripts/update_conviction_fundamentals.py --mode full --include-existing-records --pe-history-report` — refreshed all 193 dev `conviction_store` records, zero fetch errors. 32 equities now carry ≥10y real P/E history (MSFT/ADBE/GS/JPM/MCD/NKE/ORCL/PG/UPS ~17y, AAPL 190pts, NVDA 178pts, PYPL 133pts). PYPL's original bug confirmed fixed on dev: `pe_hist_percentile` −3.0→0.0, `valuation_tax` −4.0→−1.0. One known remaining edge case: `SONY` (bare ticker misclassified as US by `is_us_ticker()`, but is a Japanese 20-F filer with no SEC XBRL EPS data — falls through to the old thin yfinance path, still shows the pre-fix bug pattern). See job-status-details 2026-07-29 entry for full root-cause.
- **Prod**: **NOT run, and cannot be run by an agent** — `conviction_store/` writes are explicitly forbidden runtime-data edits under the prod-clone repo rule (same category as `.env`/`secrets.toml`), regardless of how routine the action is. Prod is still on stale data (171/193 records predate the fix as of the 2026-07-29 status check). **Runbook for whoever runs it (human/ops, directly on the prod host):**
  ```bash
  cd /home/ubuntu/uiv2/prod/MindWealth_UI
  python scripts/update_conviction_fundamentals.py --mode full --include-existing-records --pe-history-report
  ```
  Sanity-check afterward: `PYPL.json`'s `pe_percentile_20y` should move off `100.0` and `valuation_tax` off `-4.0`, same shift verified on dev. Expect this to take several minutes with no console output until the batch completes (normal — network-bound on yfinance + SEC EDGAR calls per ticker, confirmed via live socket inspection during the dev run, not a hang).
- Non-US manual entry track unchanged/still blocked on a business-prioritized ~15-20 ticker list (see FMP entry above) — SEC EDGAR is US-GAAP only, doesn't help non-US tickers.

**Open caveat carried forward:** even with SEC EDGAR, most tickers will still show `insufficient_20y=True` under `PE_HISTORY_TARGET_YEARS=20` (real ceiling ~15-19y for large-caps that existed pre-2009, less for newer listings/spinoffs) — a genuine free 20-30y source does not exist for most companies (XBRL structured data simply didn't exist before ~2009). Whether to lower the threshold to better reflect what's actually achievable for free remains the same open product decision carried over from the previous two entries.

**New follow-up from the 2026-07-29 rollout:** `SONY`-style bare-ticker foreign filers silently fall through `is_us_ticker()`'s suffix heuristic and keep the pre-fix bug — needs either an explicit exception list in `is_us_ticker()` or manual-entry routing via `scripts/set_manual_pe_history.py`. Only 1 instance found in the current 193-ticker universe; not fixed in this pass.

---

## 2026-07-29 — SEC pre-2009 legacy-filing PE-history extension (EX-27 + Selected Financial Data; extends the SEC EDGAR entry directly above, same day)

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`. **Bundle with the SEC EDGAR pivot entry directly above and the still-pending 2026-07-22 "Fundamental Agent Update"** — same `fundamentals_enriched.py`/`engine.py`/`scoring.py` insufficient-history chain, this is an additive extension to `pe_history_sec.py`'s fetch path, not a separate system.

User was told even the best-covered dev tickers only reached ~17y from XBRL alone (XBRL only mandated from ~2009) and explicitly asked to research free alternatives for real 20-30y depth. Live-tested Alpha Vantage (30y depth, but free-tier ToS explicitly excludes investment-advisor/money-manager research use — rejected on legal grounds, not technical), Finnhub (paid-only for historical fundamentals), stockanalysis.com (5y free / 10y paid — worse than SEC already). User chose to invest in a pre-2009 EDGAR full-text extractor over the other 3 options (accept ceiling / pay vendor / Alpha Vantage commercial license).

| Path | Notes |
|------|--------|
| `src/conviction_engine/pe_history_sec_legacy.py` | **new** — `parse_ex27_annual_eps()` (1994-2001 tag-delimited Financial Data Schedule exhibit), `parse_selected_financial_data()` (Item 6 5-year comparative table, bridges 2001→XBRL start), `_list_all_10k_filings()` (paginated `submissions/CIK{cik}.json`), `fetch_legacy_annual_eps()` (orchestration, 365-day disk cache, 12-filing/ticker cap) |
| `src/conviction_engine/pe_history_core.py` | refactor: `compute_pe_history()` split into `_rolling_ttm_from_quarterly()` + `_pe_from_ttm_series()` (zero behavior change, existing tests pass unmodified); **new** `compute_pe_history_with_legacy_annual()` merges pre-2009 annual points (already TTM by construction) with the modern rolling-TTM series, legacy points restricted to strictly before modern coverage starts; **`PE_HISTORY_MAX_STORED_POINTS` raised 240→360** — needed so the deeper real coverage this extension produces isn't silently truncated back to a 20y stored/ranked window |
| `src/conviction_engine/pe_history_sec.py` | `_try_legacy_extension()` — called only when the XBRL-only bundle is still `insufficient_20y`; broad `try/except` so a legacy-parsing failure can never regress a ticker below its already-working XBRL-only result; tags `pe_history_meta.source = "sec_edgar+legacy"` when it contributes |
| `tests/test_pe_history_sec_legacy.py` | **new** — 32 tests (EX-27 parsing incl. zero-diluted fallback + bank-holding-co. variant, Selected Financial Data table parsing incl. accounting-change-line skip, SGML extraction, filing pagination, full orchestration — all network mocked) |
| `tests/test_pe_history_sec.py` | `TestLegacyExtension` (+4 tests) — gating logic in isolation |
| `tests/test_conviction_engine.py` | `TestPeHistoryWithLegacyAnnual` (+4 tests) — core merge function, incl. empty-series tz edge case and overlap dedup |

**`[DEV-ONLY]` / runtime — not in git:** no new env vars. New cache files `conviction_store/pe_history_cache/{TICKER}_sec_legacy.json` alongside the existing `{TICKER}_sec.json` (XBRL) cache files, created lazily, 365-day TTL (legacy filings never change). Not tracked in git; safe to delete individually to force a re-fetch for one ticker (relevant if a stale/empty cache is ever suspected — hit exactly this during development for MSFT, see job-status-details for the debugging story).

**`[PROD-ACTION]` at cutover:** none beyond the code merge — no new env vars, no systemd/service changes.

**Regression `[DONE]` 2026-07-29:**
```bash
.venv/bin/python3 -m pytest tests/test_conviction_engine.py tests/test_api_conviction.py tests/test_pe_history_fmp.py tests/test_pe_history_sec.py tests/test_pe_history_sec_legacy.py tests/test_set_manual_pe_history.py -q
.venv/bin/python3 -m pytest tests/ -q
# 627 passed, 2 skipped, 1 failed (pre-existing/unrelated: test_d6_smoke.py's
# git-conflict-marker SyntaxError in /home/ubuntu/MindWealth/testing.py, a different repo,
# first documented 2026-07-24/27)
```

**Live smoke test `[DONE]` 2026-07-29 (manual, real network against real SEC filings):**
```bash
# fetch_pe_history_sec() with the legacy extension active, real data.sec.gov + yfinance:
#   MSFT 18.08y -> 32.08y   JPM 17.06y -> 31.57y   GS 17.07y -> 26.67y (correctly stops
#   at GS's 1999 IPO)   PG 17.06y -> 32.08y   NKE 17.14y -> 31.16y
# PYPL (2015 spinoff, no pre-2009 filings exist): unchanged, no legacy contribution --
#   expected, not an error.
# Spot-checked MSFT FY1997 EX-27 EPS-DILUTED=2.63 against Microsoft's own contemporaneous
# IR figures -- exact match. Apparent EPS discontinuity across the 1996 2-for-1 split
# boundary confirmed to be the known split adjustment, not a parsing bug.
```

**Universe rollout — dev `[DONE]` 2026-07-29 (corrected after catching a stale-cache bug on the first pass), prod `[PENDING — requires human/ops action, not agent-executable]`:**
- **Dev**: ran `update_conviction_fundamentals.py --mode full --include-existing-records --pe-history-report`. **First pass reported only 5 extended tickers** (MSFT/JPM/GS/PG/NKE) — investigated because that suspiciously matched exactly the 5 tickers manually re-fetched during live validation minutes earlier, not a fresh universe-wide result. **Root cause**: `fetch_pe_history_sec()`'s on-disk XBRL cache (`{TICKER}_sec.json`, 80-day TTL) returns early on a cache hit, *before* reaching the new `insufficient_20y` → legacy-extension gate — 42 tickers still had valid unexpired caches from the 2026-07-24 rollout above, so the brand-new legacy code silently never ran for them (no error, identical `"status": "updated"` either way). **Fix**: `rm -f conviction_store/pe_history_cache/*_sec.json` (all 42; left `*_sec_legacy.json` alone, those cache immutable historical filing content) then reran the same command. **Corrected result**: 193/193 updated, 0 errors, **18 tickers** now `sec_edgar+legacy` — AAPL 31.83y, ADBE 31.67y, BAC 31.57y, CSCO 31.0y, CVS 31.57y, GS 26.67y, JPM 31.57y, MAR 25.58y, MCD 31.57y, MSFT 32.08y, MU 31.91y, NKE 31.16y, NVDA 27.49y, PFE 31.57y, PG 32.08y, SBUX 29.83y, UPS 26.58y, WMT 31.49y. `sufficient_20y_count` 0→18 (13.5%), `insufficient_20y_count` 133→115 (86.5%), "15-20y" bucket 22→9. `pe_percentile_20y` now populated for all 18 for the first time (e.g. AAPL 100.0, WMT 97.22, NVDA 95.39). PYPL unaffected as expected (`source=yfinance`, `0.57y`, `valuation_tax=-1.0` — already-fixed neutral value, unrelated SEC-empty-facts quirk documented above).
- **MANDATORY pre-step for prod, learned from the dev bug above**: before running prod's `full_recalculation`, run `rm -f conviction_store/pe_history_cache/*_sec.json` first if prod's `pe_history_cache/` directory already has any XBRL-era cache files in it (e.g. from a previous partial/earlier rollout) — otherwise prod will silently repeat the exact same false-negative first pass dev just hit. If prod has never run any PE-history rollout before, this is a no-op (empty/nonexistent dir) and can be skipped.
- **Prod**: **NOT run, and cannot be run by an agent** — same `conviction_store/` runtime-write restriction as the entry above. Full runbook:
  ```bash
  cd /home/ubuntu/uiv2/prod/MindWealth_UI
  rm -f conviction_store/pe_history_cache/*_sec.json   # see mandatory pre-step above
  python scripts/update_conviction_fundamentals.py --mode full --include-existing-records --pe-history-report
  ```
  Should run **after** this code is merged to `chatbot-prod`, in the same pass as (or immediately after) the still-pending XBRL-only rollout from the entry above — no need for prod to do two separate `full_recalculation` passes if both merges land together. Sanity-check: `sufficient_20y_count` in the `--pe-history-report` output should land near dev's 18/193 (13.5%), not 0 or 5 (the two "looks-plausible-but-wrong" numbers dev hit before the fix).

**Open caveat carried forward, refined:** the pre-2009 legacy extension helps specifically large-cap tickers that (a) existed and filed with the SEC before 2001-06-15 (EX-27 era) or before ~2009 (Selected Financial Data bridge), and (b) are already close to the 20y bar from XBRL alone — confirmed on dev at 18/193 tickers (13.5%), roughly in line with the ~20-30 candidate estimate from the previous entry. It does **not** help newer listings/spinoffs (PYPL, and most of the universe) — those remain capped at whatever their own IPO/spinoff date + XBRL start allows. A handful of long-tenured filers that intuitively should have qualified (AMD 15.59y, ORCL 17.16y, AVGO 8.74y) did not extend on this pass — not investigated further, flagged as a genuine open item (possibly the 12-filing/ticker cap in `fetch_legacy_annual_eps()`, possibly real gaps in their indexed filing history) rather than a repeat of the cache bug above (their caches were fresh-fetched in the corrected pass, same as the 18 that did extend). The "lower the 20y threshold" product decision from the previous two entries is now less urgent for the 18 tickers this extension reaches, but remains fully open for everyone else (86.5% of the dev universe is still `insufficient_20y`).

**New hard operational rule, added 2026-07-29 (applies to all future PE-history code changes, not just this one):** on-disk PE-history caches (`conviction_store/pe_history_cache/*_sec.json` and any future equivalents) are keyed only on data age (80-day TTL), not code version. Any change to fetch/computation *logic* must be paired with purging the relevant cache files before the next `full_recalculation`, or stale caches will silently serve results computed under the old logic with zero visible signal that anything is wrong (identical `"status": "updated"` in the output either way) — exactly what happened on this rollout's first pass.

---

## 2026-07-29 — Canada MJDS/IFRS PE-history extension for dual-listed TSX names (extends the two SEC EDGAR entries directly above, same day)

`[PENDING]` — merge `chatbot-dev` → `chatbot-prod` → `prod-pull-and-restart.sh`. **Bundle with the two SEC EDGAR entries directly above** — same `pe_history_sec.py`/`fundamentals_enriched.py` chain, purely additive (a new allowlist-gated code path, zero change to existing US-ticker behavior). No new env vars, no new runtime secrets.

User asked for a solution to close the PE-history gap for the ~86.5%-still-insufficient dev universe, most of which is non-US. Live research found 6 major TSX names (TD, RY, BNS, CNQ, TRI, BN) are dual-listed on a US exchange and file `40-F`/`6-K` with the SEC under the MJDS regime, with real `ifrs-full`-taxonomy EPS data SEC's API already serves — just never previously checked by this codebase (which only looked at `us-gaap` + `10-K`/`10-Q`).

| Path | Notes |
|------|--------|
| `src/conviction_engine/pe_history_sec.py` | **new**: `FOREIGN_PRIVATE_ISSUER_ALIASES` (manually-verified `{"TD.TO": {"sec_ticker": "TD", "currency": "CAD"}, ...}` allowlist — 4 entries: TD.TO/RY.TO/BNS.TO/CNQ.TO), `_fetch_foreign_private_issuer()`, `_build_annual_only_eps_series()` (for CNQ, which has zero quarter-duration facts), currency-aware `_fetch_concept_facts(..., taxonomy=, currency=)`, `_FPI_VALID_FORMS = {"40-F","40-F/A","6-K"}`, `_FPI_EPS_TAXONOMY_CONCEPTS` (ifrs-full diluted/basic). Checked *before* the `is_us_ticker()` gate in `fetch_pe_history_sec()` since `.TO` tickers otherwise fail that check immediately. |
| `src/conviction_engine/pe_history_core.py` | Minor: filter empty series before `pd.concat` in `compute_pe_history_with_legacy_annual()` (fixes a `FutureWarning` surfaced during this work's live validation; zero behavior change) |
| `src/conviction_engine/fundamentals_enriched.py` | Call-site gate: `if pe_bundle["meta"].get("insufficient_20y") and ticker and (is_us_ticker(ticker) or is_fpi_alias):` — without this, the alias list in `pe_history_sec.py` would exist but never be reached from the real pipeline (only from tests calling `fetch_pe_history_sec()` directly) |
| `tests/test_pe_history_sec.py` | **+11 tests**: `TestForeignPrivateIssuerAlias` (8 — quarterly path, annual-only path, diluted→basic fallback, currency-mismatch-returns-None, cache round-trip, non-aliased-`.TO`-ticker regression guard), `TestBuildAnnualOnlyEpsSeries` (3) |

**Deliberately NOT a blanket "any bare foreign ticker" rule** — SEC's ticker→CIK map has real collisions (bare "NA"/"SJ" resolve to unrelated OTC shell companies, not National Bank of Canada/Stella-Jones); every allowlist entry was individually name-verified via a live `companyconcept` fetch before being added. **TRI.TO/BN.TO deliberately excluded** despite having real SEC IFRS data — both report EPS in USD only but trade in CAD on the TSX, and this codebase has no FX-conversion capability yet (see PE-05 in job-status TODO for the follow-up if pursued).

**Regression `[DONE]` 2026-07-29:**
```bash
.venv/bin/python3 -m pytest tests/test_pe_history_sec.py -q   # 34 passed
.venv/bin/python3 -m pytest tests/ -q
# 637 passed, 2 skipped, 1 failed (pre-existing/unrelated: test_d6_smoke.py,
# passes standalone, zero references to pe_history/conviction_engine in that file)
```

**Live smoke test `[DONE]` 2026-07-29 (manual, real network against real SEC + yfinance):**
```bash
# fetch_pe_history_sec() with the Canada MJDS alias active:
#   TD.TO/RY.TO/BNS.TO: 0.48-0.83y -> 7.74y each (source=sec_edgar_40f)
#   CNQ.TO: 0.57y -> 8.57y (source=sec_edgar_40f, annual-only path)
```

**Universe rollout — dev `[DONE]` 2026-07-29, prod `[PENDING — requires human/ops action, not agent-executable]`:**
- **Dev**: ran `update_conviction_fundamentals.py --mode full --tickers "TD.TO,RY.TO,BNS.TO,CNQ.TO" --include-existing-records --pe-history-report`. **Gotcha**: `--include-existing-records` reprocesses the *entire* store regardless of `--tickers` (confirmed by reading `discover_universe()`'s call site) — this run touched all 193 records, not just the 4 named. Harmless here (verified via before/after distribution-bucket counts matching the expected ±4 shift exactly, spot-checked AAPL/MSFT/PYPL unchanged) but worth knowing for future targeted reruns — omit `--include-existing-records` if you want to touch *only* the named tickers. On-disk confirmed: TD.TO/RY.TO/BNS.TO/CNQ.TO all now `source=sec_edgar_40f` with the expected years.
- **Prod**: **NOT run, cannot be run by an agent** — same restriction as the entries above. Bundle into the same prod `full_recalculation` pass as PE-01b (no need for a separate rollout — this is additive to the same script/command).

**Not pursued this pass (see job-status TODO PE-05/PE-06/PE-07 for the decision points):**
- TRI.TO/BN.TO (Canada, FX conversion needed)
- SEDAR+ for the other ~24 Canada-only names — **researched and ruled out**: SEDAR+ is PDF-only, no XBRL, no official API; would need a bespoke per-issuer PDF parser with no structured schedule to lean on, worse effort/value than the SEC EX-27 extractor. Manual entry (PE-03) is the realistic path for these.
- India NSE/BSE — **researched, decision deferred to user**: NSE's real XBRL data sits behind Akamai bot-protection needing manual cookie refresh (same risk class that ruled out Macrotrends) and only covers 2024+ even if bypassed; BSE's structured data is paid-only via Deutsche Börse.
- New Zealand NZX — **researched in an earlier pass, decision deferred to user**: NZXplorer has real structured data but its free-tier ToS bars the bulk/production use this integration would need; paid tier (~$29/mo) or manual entry (PE-03) are the options.

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

`[DONE]` — deployed 2026-07-31 via local merge + prod fetch (remote push blocked; see deploy note)

| Path | Notes |
|------|--------|
| `src/utils/mtm_pricing.py` | `refresh_dataframe_current_prices()`, `refresh_claude_shortlist_trade_store_csv()` |
| `api/services/reports_service.py` | `get_shortlist_report()` calls refresh before enrich |
| `chatbot/convert_signals_to_data_structure.py` | Nightly refresh of latest `claude_signals_report.csv` |
| `src/pages/text_file_page.py` | Streamlit Claude page refreshes MTM on load |
| `tests/test_mtm_pricing.py` | Unit tests for in-memory + trade_store refresh |
| `tests/test_api_signals_surface.py` | Guard: aged shortlist signals must not show 0d / 0% MTM |

**Smoke tests** `[DONE]` (API, 2026-07-22):
- `GET /api/v1/signals/shortlist` — MCHI/TLT/BRK-B `mtm_pct` non-zero; `days_elapsed` > 0

**Smoke tests** `[PENDING]` (after next prod deploy):
- Nightly `convert_signals_to_data_structure.py` updates `*_claude_signals_report.csv` on disk
- Streamlit Claude page shows live MTM

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

## 2026-08-17 — Sheet-reply truth audit: live feed defects + dev/prod SSI gap

Investigation only — **no git files to merge from this entry**. It records prod-affecting state found while verifying the 45 `v2_TODOs` replies against dev `:8507` / `:8514`.

### Git (chatbot-dev → chatbot-prod)

None from this audit. The SSI surfaces below are already covered by earlier entries (six-gate votes, `signal_coverage`, freshness annotations, Layer 4 panel, `vix_bypass` A6).

### Live data-feed defects `[PROD-ACTION]` — affect dev **and** prod equally

| # | Defect | Evidence | Effect on the page |
|---|--------|----------|--------------------|
| 1 | **NAAIM scrape returns 0 rows** | `_scrape_naaim()` → empty; `macro_intelligence/data/ssi/naaim_exposure.csv` last row `2026-07-29`; `stale_days=19` | Layer 1 runs **3 of 4**, weights renormalised (AAII 46.2% vs nominal 30%) |
| 2 | **`vix_ratio` NULL since 2026-08-04** | `ssi.db.ssi_daily.vix_ratio` null every date after 4 Aug; `vix_ratio_series()` called directly still returns `0.798` today | `VIX Term Structure | unavailable`; Layer 2 runs **5 of 6** |
| 3 | **CFTC one release behind while data is on disk** | `fetch_cftc_fast_money_net()` → `2026-08-11 = -286,505`; API/positioning still `2026-08-04 = -333,099`, `stale_days=13` | All three CFTC inputs dropped; **Layer 3 = DBMF at 100% weight**; tile reads `Waiting for Friday release` and `next release Fri 14 Aug` (past) |

Likely cause for #3: SSI cron is `0 8 * * 1-5` (04:00 ET) but the TFF ZIP for the Friday 15:30 ET release is refreshed later the same morning (`fut_fin_txt_2026.zip` mtime 10:56 today), so `positioning.json` is written before the new week exists. Fix is scheduling/ordering, not parsing.

No error for #1 or #2 appears in `macro_intelligence/logs/ssi_daily.log` — the pulls fail silently to cache. **Any health check must call the pull functions, not read the log.**

### Dev/prod divergence to resolve before quoting numbers to Rohit

- **CFTC percentile mismatch:** identical `fm_net = -333,099` ranks `fm_pctile 52.9 / rm_pctile 55.5` on dev `:8507` but `87.1 / 35.5` on prod `:8506`. One window is wrong; diff the two `cftc_positioning` tables before either figure is used.
- **Prod payload is missing** `signal_coverage`, `layer2_gate_label` / `conf_long` / `conf_short`, `regime`, `inputs_meta.layer3_cftc` and `spark_data`. Consequence: the "running on N of M · weights renormalised" disclosure and the long/short vote split (sheet rows 35/36/39) **do not exist on the live site**, so those rows cannot be closed on the strength of dev.

### Nuxt follow-up (separate repo `MindwealthUI_Vue`, `ui-dev`)

- Sheet row 72 promised a **stale-date banner + clearer labeling on the SSI page**; not built. Sentiment stamps the topbar from `signal_report_date` (14 Aug) while the SSI body is 17 Aug, with nothing explaining the split.
- CFTC raw rows show 13-day-old values with no freshness marker (only the `COT data` row has one).
- `buildCotFreshnessAnnotation` prints `next_release` verbatim with no future-date check → `next release Fri 14 Aug`.
- Cosmetic: duplicated `z` in Layer 2 sub-lines; `83th` / `53th` / `55th` ordinals; Sentiment `meta.source_files` still `2026-05-12_*`; dead `pct_above_200dma` key in `LAYER1_LABELS`.

### Smoke tests `[PENDING]`

```bash
curl -s -H "X-API-Key: $KEY" http://127.0.0.1:8506/api/v1/analytics/sentiment/layers | jq '.positioning.layers.layer1.signal_coverage, .positioning.layer2_gate_label'
curl -s -H "X-API-Key: $KEY" http://127.0.0.1:8506/api/v1/analytics/sentiment/layers | jq '.positioning.inputs.layer3_cftc | {fm_net, fm_pctile, position_date, stale}'
.venv/bin/python -c "from src.sentiment_superindex.data.naaim_pull import _scrape_naaim; print(len(_scrape_naaim()))"
```

### Status: `[PENDING]`

---

## 2026-08-18 — Landing page public BFF route (`/api/landing-stats`) — Nuxt repo

**Repo:** `/home/ubuntu/MindwealthUI_Vue` (branch `ui-dev`) — **separate repo**, not `chatbot-dev` → `chatbot-prod`. No files in `MindWealth_UI` change.

**Why:** the Nitro auth gate (commit `7661255`) shipped `isPublicBffPath()` as `return false`, so the public landing page's SSR calls to `/api/performance` and `/api/runic/nightly` returned 401 and all four hero tiles rendered "Could not fetch from server". **Prod `:8512` (www.mindwealth.co) is affected identically.**

### Files to ship (Nuxt repo, currently uncommitted)

| File | Change |
|------|--------|
| `server/api/landing-stats.get.ts` | **new** — public scalars-only route (5 numbers), in-process cache 5 min live / 30 s unavailable |
| `server/utils/require-auth.ts` | `isPublicBffPath()` allowlists `/api/landing-stats` only |
| `composables/useLandingStats.ts` | reads `/api/landing-stats` instead of `/api/performance` + `/api/runic/nightly` |
| `types/api.ts` | adds `LandingStatsResponse` |

### Deploy steps

1. Commit + push on `ui-dev` (not done yet).
2. `npm run build` in `/home/ubuntu/MindwealthUI_Vue` (Node 20 via nvm).
3. `sudo systemctl restart mindwealth-ui.service` (prod `:8512`).
4. Smoke: `curl -s http://127.0.0.1:8512/api/landing-stats` → 200 with `data_source":"live"`; `curl -o /dev/null -w "%{http_code}" http://127.0.0.1:8512/api/performance` → **401**; `curl -s http://127.0.0.1:8512/ | grep -c "Could not fetch from server"` → **0**.

### Status

- Dev `:8514` — `[DONE]` 2026-08-18. Built, restarted, verified: landing-stats 200 live (`avg_win_rate 75.92`, `avg_cagr 11.9`, `function_count 9`, `macro_combo_count 7`), gated routes still 401, landing HTML clean.
- Prod `:8512` — `[PENDING]`. Not restarted; awaiting go-ahead.

### ⚠️ Deploy hazard found while doing this

`mindwealth-ui-dev.service` and `mindwealth-ui.service` share **one** `WorkingDirectory` (`/home/ubuntu/MindwealthUI_Vue`) and therefore **one `.output`**. Building for dev overwrites the prod bundle on disk; prod only keeps serving old code until its process restarts. Any restart — including systemd's `Restart=on-failure` — promotes whatever dev last built, unreviewed. Prod needs its own checkout or its own build output. `[PENDING]` — separate task.

### Env / systemd / secrets

None. No `.env`, no new env var, no unit-file change, no runtime file to copy.

---

## 2026-08-18 — SSI resilience, coverage gate, CFTC completeness, regime feed (W1–W7)

Fixes the 8 findings from the sheet-reply truth audit. **This is a live sizing path** — the
coverage gate can change `ssi_multiplier`, and the CFTC fix changes published percentiles on prod.

### Git (chatbot-dev → chatbot-prod)

**New files**

- `src/sentiment_superindex/data/yahoo_cache.py` — per-ticker close cache with provenance
- `src/sentiment_superindex/data/pull_guard.py` — pull failure/empty logging
- `src/sentiment_superindex/data/cboe_indices.py` — CBOE primary source for VIX / VIX3M / SKEW
- `tests/test_ssi_feed_health.py`

**Modified**

- `macro_intelligence/SSI_CONFIG.yaml` — **new `coverage:` block (required)**
- `src/sentiment_superindex/config.py` — YAML is now the only source; `staleness_policy()` **raises** if the block is missing
- `src/sentiment_superindex/engine/{superindex,positioning,regime_block}.py`
- `src/sentiment_superindex/data/{yahoo_inputs,naaim_pull,put_call_pull,cnn_fear_greed,sp500_breadth,margin_debt_pull,cftc_patterns,pull_all,alignment}.py`
- `src/sentiment_superindex/jobs/daily_run.py`, `scripts/run_ssi_daily.py` (exit 2 when degraded)
- `src/macro_intelligence/data/{cftc_pull,retry_cache}.py`
- `src/macro_intelligence/{output/regime_feed_export.py,jobs/friday_pull.py,analysis/regime_experiments/shadow_backfill.py}`
- `src/portfolio_nav/four_book_engine.py`
- `api/routers/macro.py`, `api/services/{reports_service,macro_service,analyst_service}.py`
- `scripts/export_data_validation.py`

### ⚠ Blocking prerequisite

`SSI_CONFIG.yaml` on prod currently has **no `staleness:` block** and prod's `config.py` has no
`staleness_policy()` at all. After this merge the SSI job **will raise** unless the YAML lands
with it. That is intentional — scoring on a silent code default is what caused the drift. Confirm
`macro_intelligence/SSI_CONFIG.yaml` merged cleanly **before** running the daily job.

### Prod runtime (not in git)

- **CFTC zip cache: no manual action.** Prod holds only `fut_fin_txt_2026.zip`, which is why its
  percentiles rank against ~31 weekly prints (87.1st) where dev uses 156 (52.9th). The
  `_download_frames` completeness fix makes prod **fetch the missing years itself on first run**.
  Expect the first post-deploy run to download ~10 zips (~5 MB) and take longer than usual.
- Expect `fm_pctile` / `rm_pctile` on prod to **change materially** at that point. That is the bug
  being fixed, not a regression — but it is visible, so it is worth telling Rohit before deploy.

### systemd / Nuxt

```bash
sudo systemctl restart mindwealth-api.service
```

Nuxt prod is now a **separate tree** (`/home/ubuntu/MindwealthUI_Vue_prod`, branch
`presentation-prod`, port 8512) — a dev build no longer overwrites the prod bundle, so the Vue
changes need their own merge into that branch plus `npm run build` and a
`mindwealth-ui.service` restart.

### Smoke tests `[PENDING]`

```bash
cd /home/ubuntu/uiv2/prod/MindWealth_UI && .venv/bin/python scripts/run_ssi_daily.py; echo "exit=$?"
```

```bash
curl -s -H "X-API-Key: $KEY" http://127.0.0.1:8506/api/v1/analytics/sentiment/layers | jq '{mult: .composite.ssi_multiplier, ok: .composite.coverage_ok, policy: .staleness_policy.max_stale_days, l2: .positioning.layers.layer2.signal_coverage.available_count}'
```

```bash
curl -s -H "X-API-Key: $KEY" http://127.0.0.1:8506/api/v1/analytics/sentiment/layers | jq '.positioning.inputs.layer3_cftc | {fm_net, fm_pctile, position_date}'
```

Expect `fm_pctile` on prod to match dev for the same `fm_net` once the zip backfill completes.

### Follow-ups

- **NAAIM has no free source** (public feed moved behind a login 2026-08). Layer 1 runs 3 of 4 on
  both clones until Rohit picks: membership, manual entry, or re-specced weights.
- Coverage thresholds in `SSI_CONFIG.yaml` are **proposed defaults pending sign-off**.
- Trading-day vs calendar-day staleness for daily inputs — open question for Rohit (his C43).
- FRED `BOGZFL224066003Q` 404s for margin debt (no layer uses it).

### Status: `[PENDING]` — not committed or deployed; the dev working tree carries unrelated pre-existing changes, so the commit/merge is the user's call.

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
| 2026-08-18 | SSI resilience + coverage gate + CFTC zip completeness + regime feed currency; **SSI_CONFIG.yaml `staleness:` block is now a hard prerequisite on prod** |
| 2026-08-17 | Sheet-reply truth audit: 3 silent live feed defects (NAAIM scrape, `vix_ratio`, CFTC one release behind), dev/prod CFTC percentile mismatch, prod missing `signal_coverage` + gate label |
| 2026-08-17 | Logged `pytest` → `run_nightly(as_of="2024-09-18")` clobbering the live `runic_output.json`; prod latent, fix pending |
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
