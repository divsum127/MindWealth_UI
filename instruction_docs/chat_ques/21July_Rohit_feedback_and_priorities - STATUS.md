# Status — Rohit email "Some feedback and priorities - additional to prior emails"

**Email:** Rohit Malhotra → Divyanshu, Ahil — Tue 21 Jul 2026 09:00 BST
**Gmail thread:** `19f83b17bff9295b` · follow-up `19fd9242e7219cf3` (Thu 6 Aug 2026 18:13 EDT — *"hi Divyanshu is all this done?"*)
**Audit date:** 2026-08-17
**Audited by:** direct code + live-API checks on dev (`:8507`, v1.10.8) and prod (`:8506`, v1.8.1), plus `docs/mindwealth_ui_job_status.md`, `git log`, Gmail MCP.

---

## Headline

**No, not all of it is done.** Of the 7 immediate priorities plus ~45 carried-over items from the earlier emails:

| Status | Count |
|---|---|
| ✅ Done and verified live | 14 |
| 🟡 Partial / done on dev only | 11 |
| ❌ Open | 21 |
| 💬 Answerable now (question, not build) | 6 |

**Biggest single problem is not any one task — it is the deploy gap.**
`chatbot-dev` is **23 commits ahead** of `origin/chatbot-prod`. Prod's last merge was **2026-07-26**; prod API is **v1.8.1** while dev is **v1.10.8**. Several fixes Rohit is asking about *are* done — but only on dev, so the live site he is looking at still shows the old broken behaviour. Hard proof below (PYPL).

---

## Legend

| Tag | Meaning |
|---|---|
| ✅ | Done, verified by code read or live API call |
| 🟡 | Partial, or done on dev but **not on prod** |
| ❌ | Not done |
| 💬 | A question — answer supplied here, no build needed |

---

## Part A — The 7 immediate priorities (21 July)

### 1. P3 — point-in-time signal-ledger replay ❌ OPEN

- Not started. No replay harness anywhere: `grep point_in_time|pit_replay|replay_harness` returns only an unrelated conviction test and the D1 feed's metadata string.
- `P3_scoping.md` does not exist in the repo, and no scoping date was ever committed.
- Rohit's ask — *"if there's a scoping reason this is taking longer than expected, tell me now"* — was **never answered**. This is the highest-value overdue reply in the whole thread.
- Rohit is also right that D1 does not substitute for it. D1 (`testing/macro_th_exp/D1_regime_bucket_daily_2026-07-17.csv`) was delivered 2026-07-17 and labels the day; P3 regenerates the ledger.
- **Three real scoping unknowns** (already recorded in job status, never sent): backtest compute cost for a 2018–2026 sweep; point-in-time gate-input coverage back to 2018; sign-off on which rule-set vintage the replay uses.

### 2. Real SSI-ceiling + Conviction-tier feed for A1 four-book attribution 🟡 PARTIAL

Built in `src/portfolio_nav/four_book_engine.py`; `/portfolio/nav?book=base|ssi|cv|enhanced` serves real per-book series. But it is **not the feed Rohit asked for**:

| Feed | State |
|---|---|
| SSI-only ceiling series | ✅ Real, full 2015+ coverage from `ssi.db` via `load_ssi_ceiling_series()` |
| Conviction tier series | 🟡 Real tiers (`_BQ_TIERS`), but the dated archive `conviction_store/daily/` **only starts 2026-05-15** — 47 trading days. Pre-2026-05 conviction history does not exist and was never backfilled. `cv_data_status` discloses this honestly. |
| Full 5-factor regime chain (regime max × VIX × trend × HY × SSI) | ❌ Does not exist historically anywhere in the repo — `four_book_engine.py`'s own docstring says so |

So Ahil can move off the VIX-adverse SSI proxy today, but the conviction half is still effectively a proxy before May 2026. **This is the honest answer Rohit needs and has not been given.**

### 3. `compute_rr_to_nearest_support_stop` + does live R:R Static use it? 💬 ANSWERABLE NOW — and the answer is **no**

Confirmed by reading the code:

- The function **exists and is live**: `MindWealth/helper_functions/claude_lateness_metrics.py:526`. It is the code path that produces **`rr_dynamic`** via `enrich_row()` at `:918`.
- The **"R:R Static"** field on the site is a **different function**: `compute_rr_static()` at `:755` — `bt_avg_win_pct / stop_distance_pct`. Different formula, different inputs.
  - Dynamic: reward = current → BT avg exit; risk = current → nearest stop.
  - Static: reward = BT avg win %; risk = stop distance %.
  - They share only `select_nearest_support_stop()`.
- **So the answer to Rohit's written-confirmation ask is: the live R:R Static field does NOT use this function. R:R Dynamic does.** Ahil should call the `rr_dynamic` path — one code path, per the axioms.
- The no-clean-stop **fallback already exists** but was never documented to Ahil: `rr_null_reason` at `:925-941` covers four cases, including *"price has breached all listed stop levels — signal is effectively stopped out"*.
- ❌ **Real blocker:** the function lives in the **MindWealth core repo**, not exposed over HTTP by the UI API. Ahil cannot call it remotely. Either export a batch CSV or add an endpoint.
- ⚠️ **New defect found while checking this:** `compute_bt_avg_exit_price(direction, signal_open, bt_avg_pct)` at `:915` anchors the BT exit price on **signal_open**, while `compute_theoretical_entry_price()`'s own docstring (`:780`) states *"signal_open ... is NOT the correct fallback."* This is bug 5A (open vs close price) still live inside the R:R chain.

### 4. The flagged bugs

| Bug | Status | Evidence |
|---|---|---|
| SSI composite ≠ weighted avg of layer z-scores | ✅ **Done** | `build_layer1/2/3()` + `build_superindex()` at `src/sentiment_superindex/engine/superindex.py:235-295`; live dev `ssi_level=0.432` reconciles |
| McClellan out of range / 14 dp | ✅ **Done** | live dev `mcclellan.raw = 7.3` (was 217); cumsum bug removed; regression test `tests/test_mcclellan_pull.py` |
| NH/NL showing raw count not 0–1 ratio | ✅ **Done** | live dev `nh_nl_ratio.raw = 0.95`; formula now `highs/(highs+lows)`; test `tests/test_sp500_breadth_nh_nl.py` |
| Conviction P/E percentile stuck at 0 → inflated Valuation Tax; **PYPL should show 0** | 🟡 **DEV ONLY — PROD STILL BROKEN** | see below |
| FX assets → BLOCKED/$0 instead of "not applicable → base size" | ✅ **Done** | `api/services/portfolio_service.py:871-878` — explicit D2 branch |
| Cluster-weight display showing 351% etc. | ✅ **Done** | live dev `/portfolio/sizing`: max sleeve **12.96%**, all sleeves sum ≈ 72%. Risk breaches now read "Reduce US Tech by ~$1,600,000" on 21.6% combined vs 20% cap — was $893,500,000 |

**PYPL — the hard proof of the deploy gap:**

```
dev  conviction_store/PYPL.json : valuation_tax = -1.0, pe_percentile_20y = None
prod conviction_store/PYPL.json : valuation_tax = -4.0, pe_percentile_20y = 100.0, conviction_score = 0.0
```

The fix shipped to dev on 2026-07-29 (job status PE-01a/PE-04). The **prod rollout (PE-01b) was never run** — it needs a human on the prod host, since an agent is forbidden from writing prod runtime data. **So what Rohit sees on the live site is still `-4.0`, exactly the bug he reported.**

Two follow-ons worth telling him:
- Even on dev, PYPL shows **−1.0**, not the **0** he said it should be. Needs his confirmation on which is right.
- **176 of 196** dev conviction records still have `pe_percentile_20y = null` — only 18 tickers have real ≥20y P/E history (SEC EDGAR + legacy filings). Null is honest, but the percentile is not yet usable universe-wide. Non-US names (India `.NS`, NZ `.NZ`, Canada) are blocked on a source decision — PE-03/05/06/07 in the TODO file.

### 5. Parth's blocking endpoints ✅ ALL SIX EXIST

| Endpoint | Where | State |
|---|---|---|
| `/portfolio/nav` | `api/routers/portfolio.py:45` | ✅ closed + MTM variants, all 4 books |
| `/portfolio/sizing` | `:150` | ✅ scenarios, true weights, P&L rows |
| `/portfolio/holdings` | `:77` | ✅ 96 rows live; score, rank, rr_dynamic, siblings, multi_sig |
| `/signals/entries` | `api/routers/signals.py:29` | ✅ |
| `/signals/exits` | `:47` | ✅ `exit_type` signal / rr / eviction |
| alerts.json via FastAPI with `type` + `target_page` | `api/services/alerts_service.py` → `GET /portfolio/alerts` | ✅ `target_page` present on every alert |

**But the payloads are not complete**, measured live on 96 holdings:

| Field | Nulls | Rohit's ask |
|---|---|---|
| `pnl_contribution_bps` | **96 / 96** | 4D — not delivered |
| `backtested_win_rate_pct` | **96 / 96** | — |
| `exit_ref` | **51 / 96** | 4B — partial |
| `hold_time_used_pct` | **36 / 96** | downstream of 5B `avg_hold_days` |
| `same_asset_siblings[].days_elapsed` | 9 null | 4A — mostly there |
| `ceiling_pct` / `slots_used` / `slots_free` on sleeves | all null | D1 slot model not exposed |

So: Parth is **unblocked to build**, but three of Rohit's Part-4 fields still return null.

### 🔴 NEW DEFECT FOUND — `pnl_usd` is direction-blind on every short

Not in Rohit's list. Found during this audit. Live on dev **and** prod.

`api/services/portfolio_service.py:985` computes `pnl_usd = market_value_usd - allocation_usd` — long-only maths. `direction` is in scope at `:960` and is not used. Meanwhile `mtm_pct` comes from the CSV's direction-aware "Realised/Unrealised Profit". Result: **for every short, the two fields carry opposite signs.**

```
BABA      Short  122.16 → 123.81   mtm_pct = -1.35   pnl_usd = +471.96    ← lost money, reported as gain
000660.KS Short  2187000 → 1645000 mtm_pct = +24.78  pnl_usd = -16617.50  ← made money, reported as loss
CNQ.TO    Short  55.89 → 66.41     mtm_pct = -18.82  pnl_usd = +8577.50   ← lost money, reported as gain
```

This propagates into `day_mtm_usd` (`portfolio_pipeline_service.py:722`) and the top-5 gainers / top-5 losers lists (`:742-746`) — so the **Live P&L page's winners and losers are inverted for every short position.** Client-visible. Should be fixed before the next demo.

### 6. VIX / VIX3M live data ❌ ROOT CAUSE FOUND — Rohit's complaint is still valid

Rohit saw 1.06 on the site vs ~1.01 elsewhere. Reproduced the same class of mismatch today:

```
prod nightly (2026-08-14):  VIX = 14.34000015258789   VXTS = 1.2880
Yahoo ^VIX close 2026-08-14: 14.25                     VIX3M/VIX = 1.2381
```

VIX3M matches; **VIX does not**, and the ratio inherits the error.

**Cause:** server timezone is **UTC** (`timedatectl` → `Etc/UTC`). `crontab` runs `run_macro_nightly.py` at **18:00 UTC = 14:00 ET** — **two hours before the 16:00 ET cash close** and 2h15m before VIX settlement. So VIX, VXTS, WTI, CNH and CURVE are all captured as **intraday prints, never official closes.** `run_ssi_daily.py` at 08:00 UTC = 04:00 ET is worse — before the US market even opens.

This is exactly Rohit's concern and it feeds Combo A/D/G thresholds directly. **Fix: move the nightly cron to ≥ 21:15 UTC (17:15 ET), or explicitly pin to the prior completed session's close.**

**"Check the live-ness for all macro variables"** — ❌ not done. `GET /macro/data/freshness` on prod returns `source_date = null` for **10 of 12** variables (NFCI, HY, WALCL, CNH, WTI, VIX, VXTS, CURVE, CPI, GSR). Only CFTC and CAPE carry a real source date. There is no per-variable freshness stamp to check.

Also: the raw VIX value `14.34000015258789` is a float32 artifact — the **8D rounding rule (2 dp, 4 dp for currency pairs) was applied to `/macro/ssi/*` only**, not to `/macro/runic/variables/current`.

### 7. Bond / fixed-income COT series (fast money / leveraged funds) ❌ NOT STARTED

`macro_intelligence/CONFIG.yaml:332-338` restricts CFTC to equity only:

```yaml
market_primary: "S&P 500 Consolidated"
market_filter:  "S&P 500"
market_exclude: "E-MINI|MICRO|DIVIDEND|ADJUSTED INT RATE"
```

No Treasury / bond-future series is pulled anywhere. The TFF ZIP already downloaded (`macro_intelligence/data_cache/cftc/`) **contains** the bond contracts, so this is a config + series-extension job, not a new data source. Classification filters (`fm_classification: "Lev Money|Leveraged Funds"`) already do what Rohit wants — they just point at the wrong market.

---

## Part B — carried-over items from the earlier emails ("CHECK IF YOU'VE DONE ALL THIS")

### Part 1 — blocking others

| Item | Status |
|---|---|
| 1A. Daily regime-bucket series 2018–2026, point-in-time, version-stamped | ✅ **Done** — `testing/macro_th_exp/D1_regime_bucket_daily_2026-07-17.csv` (+ Fridays file, JSON, MD), v1.1, Combo C cancel-logic replayed week by week. Rohit already acknowledged this. |
| 1B. Parth's endpoints | ✅ all six exist — see Priority 5 above (payload gaps noted) |
| 1C-i. Real R:R function | 🟡 exists, not exposed to Ahil — see Priority 3 |
| 1C-ii. Real SSI ceiling + conviction tier feed | 🟡 SSI real; conviction real only from 2026-05-15 |
| 1C-iii. Regime-bucket series + P3 replay setup | 🟡 D1 done; **P3 ❌** |
| 1C-iv. Composite-score API 401 | 🟡 **Root-caused, never actioned.** It is a missing `X-API-Key` header against `api/dependencies.py::require_api_key` — not a broken feature. The key exists in `.env`. **It was never handed to Ahil.** One email closes this. |

### Part 2 — one sizing engine

| Item | Status |
|---|---|
| `size = NAV/N × conviction × SSI ceiling`, sleeve caps as slots | 🟡 built as `api/services/sizing_engine.py` (D1 slot model, `max_slots_for_sleeve = floor(ceiling_pct × N / 100)`) but gated behind `SIZING_ENGINE_VERSION=d1_slots`; **legacy engine is still the default**, and `slots_used`/`slots_free` return null live |
| No bar over 100% | ✅ verified live — max sleeve 12.96% |
| Rename "Sized Allocations" → "Sizing & Allocation" | ❓ frontend (Parth) — not verifiable from these repos |
| Scenario buttons preview-only | ✅ `resolve_auto_scenario()`; scenarios do not mutate the book |
| Confirm chain order = regime max × VIX × trend × HY × SSI | 🟡 order is right, **but the ladder values are wrong**: job status records `portfolio_service._compute_ceiling` has the wrong VIX ladder, no Combo B/F bypass, SPX ×0.90 vs spec ×0.80, and different HY bands vs the Jun-18 spec |

### Part 3 — three books ✅ MOSTLY DONE

`book_id = model | brokerage | personal` enforced by `api/services/portfolio_book.py`; unsupported combinations return a clear 422. PERSONAL is live-snapshot only (`personal_book_service.py`). **BROKERAGE ❌ blocked** — IBKR account not provisioned (`ikbr_details.md`). Four-way valuation toggle is MODEL-only. ✅ correct.

### Part 4 — extra per-position fields

| Field | Status |
|---|---|
| 4A `same_asset_siblings`, both directions | ✅ present on all rows (9 `days_elapsed` nulls) |
| 4B `exit_ref` | 🟡 **51/96 null** |
| 4C `multi_sig[]` | ✅ populated on 34/96 |
| 4D `pnl_contribution` | ❌ **96/96 null** |
| 4D NAV benchmark + realized vol / beta / best-worst month | ✅ done in `/portfolio/nav` from ingested monthly series |

### Part 5 — bugs

| Item | Status |
|---|---|
| 5A. Entry price uses signal **open**, should use **close** | ❌ **still live** — `compute_bt_avg_exit_price(direction, signal_open, ...)` at `claude_lateness_metrics.py:915`, contradicting the sibling function's own docstring |
| 5B. `avg_hold_days` = N/A | 🟡 `hold_time_used_pct` null on **36/96** live holdings. Still breaks C1 annualisation for those rows (C1 divides 252 by avg_hold_days) |
| 5C. Negative dynamic R:R shown, never zeroed | ✅ `rr_dynamic` returns negative values live; siblings check wired |
| 5D. DRIFT (not DEGRADING) trigger rule | ✅ done — `degradation_service.py` + `analyst_service.py`; false `fwd < bt-10` trigger removed; UI copy renamed |
| 5E. Cluster bars > 100% | ✅ fixed — see above |

### Part 6 — one source for weights ✅ DONE

`/portfolio/risk` breaches now read from the same true-weight field: `combined_weight_pct = 21.6` vs `cap_pct = 20.0` → *"Reduce US Tech by ~$1,600,000."* The $893.5M / $619.45M nonsense is gone.
⚠️ Minor: the second breach (Semiconductors × US Tech, 15.84% vs 20% cap) is still tagged `level: "action"` with `recommendation: null` — 15.84% is under the cap, so it should not be an action.

### Part 7 — Conviction Engine check 🟡

`daily_update` runs; P/E history rebuilt from SEC EDGAR + pre-2009 legacy filings on dev. **Not spot-checked by hand for three names** as Rohit asked. Portfolio-positions and Contradictions tabs → frontend, unverified.

### Part 8 — SSI number checks ✅ ALL FOUR DONE (dev)

8A composite z-scores ✅ · 8B McClellan 7.3 ✅ · 8C NH/NL 0.95 ✅ · 8D rounding ✅ **for `/macro/ssi/*` only** — the Runic variables endpoint still leaks float32 noise (`14.34000015258789`).

### Part 9 — macro / Runic

| Item | Status |
|---|---|
| 9A-1. Fed-cycle re-slice on new D/E settings | ✅ `testing/macro_th_exp/D5_fed_cycle_reslice_2026-07-21.{md,json,csv}` — D spread widened to ~51 pts at 1W; QE and Combo E per-cycle slices correctly marked CANNOT USE |
| 9A-2. Regime bucket series | ✅ D1 |
| 9A-3. Curve-phase flag — **propose only** | ✅ `testing/macro_th_exp/D2_curve_phase_proposal_2026-07-17.md` + episodes CSV + weekly panel. **⚠️ Rohit says this was "never answered in either Analysis Thread doc" — so the artefact exists but was never sent to him.** |
| 9A-4. F4 v2 steepening split (BULL/BEAR/TWIST + 29.4% unconditional benchmark) | ✅ Rohit acknowledged it himself in this email |
| 9A-5. B4 window audit — HY/VIX/VXTS on rolling 3y | ✅ **Confirmed fixed.** `CONFIG.yaml`: HY `rolling_3y`, VIX `rolling_3y`, VXTS `rolling_3y`, CFTC `rolling_3y`. Only NFCI / WALCL / CURVE / CAPE are `full`, by design. Artefact: `D4_window_audit_rerun_2026-07-16.md`. **Also never confirmed back to Rohit.** |
| 9A-6. Settled decisions applied (PIVOTING→EASING, 9-state storage/4-state collapse, NEUTRAL→EASY, Combo C "insufficient episodes" at n=4, HMM out of short-gating) | ✅ per D6 docs |
| 9B-1. CFTC freshness tag | ✅ **Fixed and now follows Point A exactly** — live: `position_date 2026-08-04`, `release_date 2026-08-07`, `expected_release 2026-08-11`, `stale: true`. Honest as-of date, no interpolation. ⚠️ But the underlying data **is two releases behind** (should be as-of Tue 2026-08-12 from the Fri 2026-08-14 release) — the tag is correctly telling us the pull is stale |
| 9B-2. "SBI Composite" → "SSI" label | ✅ no `SBI Composite` string remains in any tracked file |
| 9B-3. Chatbot forgets earlier messages | ✅ `chatbot/history_manager.py` (per-session lock, rolling window) + `chatbot/memory_manager.py` `RollingMemoryLog` |
| 9B-4. Combo-culling output for the Macro page | ❌ **Data exists, no endpoint.** `testing/291_combo_tests/shortlist_tiered.csv`, `funnel_summary.json`, `promotion_candidates_62.csv`, `testing/5_regime_uplift/combo_classification_history.csv` — none served over the API. Parth still blocked |

### Part 10 — Overwatch: three quick answers 💬 ALL THREE ANSWERABLE NOW

1. **trade_store path — Rohit's assumption is wrong.** It is not `~/uiv2/MindWealth_UI/trade_store/`. Actual paths:
   - prod: `/home/ubuntu/uiv2/prod/MindWealth_UI/trade_store/`
   - dev: `/home/ubuntu/uiv2/git/MindWealth_UI/trade_store/`
   - core: `/home/ubuntu/MindWealth/trade_store/`
2. **Redis — not available.** No `redis-server`/`redis-cli` binary, service inactive, python `redis` module not installed. **But Parth does not need polling:** an in-process SSE stream already exists — `GET /overwatch/stream`, `media_type="text/event-stream"` (`api/routers/overwatch.py:25-39`) backed by `overwatch_event_bus.py`. **Answer: build against SSE, not 60-second polling. No Redis required.**
3. **`historical_analogs` in the nightly JSON — yes, already there.** `build_historical_analogs_block()` at `src/macro_intelligence/output/json_writer.py:92`, attached to the payload at `:217-218`.

### Part 11 — spec hygiene ❌ NOT DONE

`claude_prompt_modified.txt` **does not exist anywhere on this machine.** So "put every decision into that file" cannot have been done, and Gate A2d's discrepancy is unresolved: `instruction_docs/signals_master_spec/status.md:133` still records the per-interval CAGR floors (−15% / −20% / −25%) while the composite uses `CAGR_CLIP = 5%` equity. Rohit is right that this is live in the gate logic. **Needs his pick, then one file.**

### Part 12 — before handover (was due ~3 Aug) 🟡

| Deliverable | Status |
|---|---|
| `SYSTEM_DOCUMENTATION.md` | ✅ exists — `macro_intelligence/SYSTEM_DOCUMENTATION.md` |
| `CONFIG.yaml` (all sources / thresholds / models in one file) | ✅ `macro_intelligence/CONFIG.yaml` + `macro_intelligence/SSI_CONFIG.yaml` |
| `README_MAINTENANCE.md` | ✅ `macro_intelligence/README_MAINTENANCE.md` |
| Walkthrough call with Ahil + Rohit on every scheduled job | ❌ no record it happened |
| "Beta + directionality pass" written into a proper spec | ❌ not found in any spec file |
| Automatic monthly threshold review emailing suggested changes | ❌ `scripts/recalibrate_thresholds.py` exists but **is not in crontab** — no automation, no email, no one-click approve |

Note: all three docs sit under `macro_intelligence/`, i.e. they cover the macro system only — not the API, chatbot, portfolio engine, or Nuxt frontend. Rohit's ask was "how to restart **each part**".

### Other — Points A / B / C

| Point | Status |
|---|---|
| **A. CFTC reporting-lag display convention** | ✅ **Implemented exactly as specified.** Live payload carries `position_date` (Tue) and `release_date` (Fri) separately, `stale` flag, no interpolation, no smoothing |
| **B. R_ref cross-asset-class normalisation — is the real table wired?** | ✅ **YES — confirmed, not a placeholder.** `R_REF` dict at `MindWealth/helper_functions/claude_lateness_metrics.py:134`, looked up per asset class at `:871`: equity 50.0, equity_etf 56.0, commodity_etf 84.0, bond_etf 21.0, crypto_etf 210.0, index 42.0, currency 21.0, crypto 280.0. `C1 = clip(er_ann / r_ref, 0, 1) × 40` at `:875`. **One honest caveat Rohit should know: only `equity` is calibrated (80th percentile, June 2026). The other seven are marked "provisional" in the code comment** — so bond and FX signals are on a separate scale, but not yet an evidence-backed one |
| **C. Geo agent** | ⚪ Rohit deferred it himself |

---

## The 10 things to do first

1. **Merge `chatbot-dev` → `chatbot-prod` and deploy.** 23 commits, 22 days stale. Most "is this done?" answers become "yes, and now you can see it" the moment this lands.
2. **Run the prod conviction rollout (PE-01b).** Needs a human on the prod host. Until then Rohit's PYPL example still reads −4.0 on the live site.
3. **Fix `pnl_usd` sign for shorts** (`portfolio_service.py:985` — use `direction`). Live P&L winners/losers are currently inverted for every short.
4. **Move the nightly cron past the US close** (18:00 UTC → ≥ 21:15 UTC). This is the VIX/VXTS mismatch Rohit has now raised twice.
5. **Reply on P3 scoping** — the one thing he explicitly asked not to be told late.
6. **Send Ahil the `X-API-Key`.** Closes the 401 in one email.
7. **Add per-variable `source_date`** to `/macro/data/freshness` for the 10 nulls, so "live-ness" is checkable rather than asserted.
8. **Send Rohit the three Part-10 answers** (trade_store path — his assumption is wrong; no Redis but SSE already exists; historical_analogs already shipped). Parth is blocked on all three.
9. **Send the D2 curve-phase proposal and the B4 window-audit confirmation.** Both are done and sitting in `testing/macro_th_exp/` unsent — he has listed both as "never answered".
10. **Pick a Gate A2d floor** and create `claude_prompt_modified.txt`.

---

## Questions only Rohit can answer

1. **PYPL Valuation Tax** — he said it should be **0**; dev now produces **−1.0** (from −4.0). Which is right?
2. **Gate A2d** — per-interval CAGR floors (−15/−20/−25%) or the single ~4.5% floor? Pick one.
3. **Conviction history before 2026-05-15 does not exist.** Should A1 run BASE+CONVICTION on the 47-day window only, or should we backfill (and if so, from what)?
4. **Sizing engine default** — flip `SIZING_ENGINE_VERSION` to `d1_slots` in prod? Needs the SLEEVES ceiling table signed off first.
5. **Notional + N** — API still hardcodes $100M; Ahil's workbooks use $10M / N=60.
6. **Ceiling ladder** — code is SPX ×0.90, the Jun-18 spec says ×0.80; VIX ladder and HY bands also differ from spec. Which is authoritative?
