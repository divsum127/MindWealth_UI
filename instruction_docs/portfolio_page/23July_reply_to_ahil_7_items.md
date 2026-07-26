# Reply to Ahil — the 7 blockers, in order

**Date:** 2026-07-23
**From:** Divyanshu
**Re:** "What I need from you to finalize the test suite — 7 items, prioritized"
**Related:** [`PORTFOLIO_PAGE_AIM_AND_STATUS.md`](PORTFOLIO_PAGE_AIM_AND_STATUS.md) §8.0 · [`portfolio_implementation_log.md`](portfolio_implementation_log.md) · [`Ahil_portfolio_page_docs.md`](Ahil_portfolio_page_docs.md) §12

---

## Status at a glance

| # | Item | Status today | What ships now | What's still a real gap |
|---|------|---------------|-----------------|--------------------------|
| 1 | P3 — PIT signal-ledger replay | ❌ Not started | Scoping only (below) | Full Daily-interval backtest re-run, 2018–2026, all functions |
| 2 | `compute_rr_to_nearest_support_stop` | ✅ Already exists & already live | Function + confirmation, today | Test-8 "no clean stop" fallback needs a policy decision from you/Rohit |
| 3 | SSI-ceiling daily series | 🟡 SSI-only: ready now | `SSI_ceiling_daily_2018_2026.csv`, today | Full chain (regime×VIX×trend×HY×SSI) history doesn't exist anywhere — separate build |
| 4 | Conviction-tier per position | 🟡 Live tiers real, history sparse | Tiers + formula, today | Archive only starts 2026-05-15 — no fabricated pre-May history |
| 5 | D1 regime-bucket daily series | ✅ Already delivered 2026-07-17 | File path below | None — just point you to it, which is literally the ask |
| 6 | Macro overlay feed (291→8) | ✅ Already delivered | File paths below | None |
| 7 | Composite-score API 401 | 🟡 Not a bug — a missing header | Key handoff, today (out-of-band) | None once you have the key |

Four of seven are effectively done or shippable today. The two real open items are #1 (needs a scoping conversation, flagged honestly below) and the Test-8 fallback policy inside #2.

---

## 1. P3 — point-in-time signal-ledger replay

I'm not going to pretend this is smaller than it is — it's the big one, and it's genuinely not scoped yet. Here's what I know and what I don't.

**What exists today:** `trade_store/US/forward_testing/<STRATEGY>/**/*.csv` (~1,990 trade CSVs, 9 strategies) — this is the **live forward-testing ledger**, and for Daily-interval signals it only starts around 2024, because Daily-interval signal generation itself only went live around then. Pre-2024 Daily rows aren't missing data — they're rows that were never generated, because nothing was running the Daily gate stack against those historical dates.

**What "regenerate point-in-time" actually means:** re-running the full signal-generation + gate-evaluation stack for every function × Daily interval × ~180 symbols × every trading day from 2018–2026, using only the data that would have been available as of that date (no forward-looking macro combo state, no forward-looking price data past the as-of date). That's a backtest re-run, not a data export.

**Three things I need to scope before I can give you a real date, and I'd rather flag them now than slip silently:**

1. **Compute cost / runtime** — 9 functions × Daily × ~180 symbols × ~2,000 trading days is a non-trivial backtest matrix. I haven't sized this yet.
2. **Point-in-time gate inputs** — the Daily strategies gate off macro combo state (VIX, HY spreads, CFTC, etc.). I need to confirm those inputs have clean point-in-time history back to 2018 at the same granularity the gates need, not just the daily bucket-level series in item #5.
3. **Rule-set vintage** — if a function's Daily-interval logic was revised at some point (parameters, gate thresholds), "as if it had always run" requires picking one fixed rule version for the whole 2018–2026 replay. That's a product call (probably needs Rohit's sign-off on which vintage), not something I should decide silently, because it changes what the backtest actually represents.

**Next step:** I'll come back with a scoping estimate (rows/day cost, gate-input coverage check, and the rule-vintage question flagged to Rohit) — targeting **[fill in date — need to check backtest infra capacity first]**. I'm calling this out explicitly rather than guessing a date and missing it, since you said you'd rather know now.

---

## 2. `compute_rr_to_nearest_support_stop` — confirmed, one code path

Good news — this already exists, it's already live, and it's the exact same function the live report calls. Confirming in writing, as you asked:

**Yes — one code path.** `rr_dynamic` on the live API/report is populated from this exact function:

```430:526:MindWealth/helper_functions/claude_lateness_metrics.py
def compute_rr_to_nearest_support_stop(
    direction: str,
    current_price: Optional[float],
    bt_avg_exit_price: Optional[float],
    nearest_stop: Optional[float],
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Return (rr_ratio, proposed_reward, risk_to_nearest_stop).

    R:R measured from current price to BT average exit price vs current price to stop:
      Long:  reward = BT_Avg_Exit_Price - current_price
             risk   = current_price - nearest_support_stop
      Short: reward = current_price - BT_Avg_Exit_Price
             risk   = nearest_support_stop - current_price
    """
```

Called at `enrich_signal_dict()` (same file, ~line 918) with the row's own `current_price`, `bt_avg_exit_price` (derived from `Signal Open Price × (1 + BT avg return %)`), and `nearest_stop` (from `select_nearest_support_stop()`, same file, ~line 448 — picks the closest protective stop on the correct side of price from the row's stop-level list, plus any cancellation level). The result is written to `row["rr_dynamic"]` and surfaced on `/signals/entries`, `/portfolio/holdings`, and the report payload.

**One clarification on the target leg — the function name is legacy, not literal.** The reward/target leg is **not** "nearest resistance/support" — it's the **BT-average-exit price** (`entry × (1 + avg_backtested_win)`, same shape as your placeholder). The risk/stop leg **is** the nearest protective stop level. So: your placeholder's target formula and the live formula's target are actually the same idea (BT avg exit), not different — the discrepancy you're seeing (35% OOS retention, exits young winners) is more likely in how `nearest_stop` is sourced/parsed than in the target definition. Worth comparing your stop inputs against `select_nearest_support_stop()`'s source column directly before assuming the target leg is the problem.

**For both directions, confirming your harness formula matches:**
- Long: `rr = (bt_avg_exit_price − current_price) / (current_price − nearest_stop)` ✅ matches your Long expression once "target" = BT-avg-exit
- Short: `rr = (current_price − bt_avg_exit_price) / (nearest_stop − current_price)` ✅ matches

**Test 8 fallback — already partially built, but needs your policy call.** When no valid stop level is found, the live code already returns `rr = None` (not a crash, not a fabricated number) with a machine-readable reason in `row["rr_null_reason"]`:

```921:939:MindWealth/helper_functions/claude_lateness_metrics.py
    if rr is None:
        if bt_avg_exit is None and signal_open is not None and signal_open > 0:
            rr_null_reason = "bt_avg_return_pct unavailable — cannot compute BT exit price"
        elif bt_avg_exit is None:
            rr_null_reason = "Signal Open Price is zero/missing — cannot compute BT exit price"
        elif nearest_stop is None:
            if _detect_stopped_out(row, direction, current_price):
                rr_null_reason = "Price has breached all listed stop levels — signal is effectively stopped out; no valid protective stop remains below current price"
            else:
                rr_null_reason = "No valid stop level found below current price"
        else:
            rr_null_reason = "rr calculation failed (check stop/exit prices)"
```

That already matches option (a) on your list — **skip the R:R flag, keep the trade's natural handling** — rather than a numeric fallback. I'd recommend keeping it that way for consistency with the live product (an honest "we don't know" beats a synthetic number), but if Test 8 needs a *continuous* R:R series with no gaps for the harness, tell me and I'll add a documented numeric fallback (e.g. your Test-5 stop_frac = `−min(|avg BT loss|, 10%)`) as an explicit second return value, distinct from the primary `None`.

**Bottom line:** swap-in is genuinely a one-line change on your side — call the same function, same signature, with your historical `current_price`/`nearest_stop`/`bt_avg_exit_price` snapshot. Nothing new to build unless you want the numeric fallback above.

---

## 3. Real SSI-ceiling daily series

**Partial — the SSI leg alone is ready today; the full chain is a separate, real gap.**

What's genuinely live and complete: `macro_intelligence/data/ssi/ssi.db` has full **2015+** daily SSI coverage (3,858 rows, no gap), already used by `load_ssi_ceiling_series()`:

```70:78:MindWealth_UI/src/portfolio_nav/four_book_engine.py
def load_ssi_ceiling_series(*, ssi_db_path: Path | None = None) -> pd.Series:
    """Date-indexed SSI ceiling fraction (0-1), capped at 1.0 (haircut-only, never inflates)."""
```

I can export `SSI_ceiling_daily_2018_2026.csv` (one row/day, SSI-only ceiling fraction, version-stamped) from this today — no new build needed. That directly replaces your "VIX>75th pct → 70%" proxy with the real SSI leg.

**What's genuinely missing — flagging honestly, not just "proxy until this lands":** the *live* ceiling is `regime_max × VIX × trend × HY credit × SSI`, computed only in `_compute_ceiling()` in `portfolio_service.py` for **today's date**. The `four_book_engine.py` module docstring is explicit about the gap:

```28:32:MindWealth_UI/src/portfolio_nav/four_book_engine.py
**Scoping note:** "deployment ceiling" here uses the SSI multiplier only (capped at 1.0, same
haircut-only rule as ``api/services/portfolio_service.py::_compute_ceiling``), not the full
live regime chain (regime max × VIX × trend × HY × SSI). VIX/trend/HY multipliers have no
historical daily series stored anywhere in this repo — reconstructing one is a separate,
tracked gap ...
```

So: I can give you the real **SSI-only** ceiling series now (better than your current proxy). If A1 needs the **full 5-factor chain** historically, that's a separate backfill of VIX/trend/HY multiplier history that doesn't exist yet anywhere in this repo — let me know if you need that scoped alongside #1, since it has the same "does clean point-in-time history exist that far back" question.

---

## 4. Real Conviction-tier per position

**Partial — live tiers and multipliers are real (not proxied); history before 2026-05-15 doesn't exist and I won't fabricate it.**

The real production tiers, with the actual multipliers (not your quartile proxy):

```111:117:MindWealth_UI/api/services/portfolio_service.py
_BQ_TIERS: list[tuple[float, str, float]] = [
    (8.0,  "MAX",     1.00),
    (5.0,  "TACTICAL", 0.75),
    (2.0,  "REDUCED",  0.40),
    (-99,  "BLOCKED",  0.00),
]
```

Non-equities (ETF/FX/index/commodity) already resolve to `"N/A"` at base share `1.00` — never `BLOCKED`/`$0` — this was the D2 fix you'll see referenced elsewhere in the docs.

**The real gap:** `conviction_store/daily/` (the dated conviction-tier archive) only starts **2026-05-15** — 31 dates as of this writing. `four_book_engine.py` is explicit that BASE+CONVICTION and ENHANCED are only computed from that date forward, and pre-archive trades are **excluded, not backfilled with a fabricated tier**:

```19-26:MindWealth_UI/src/portfolio_nav/four_book_engine.py
**Historical gap handling (core ask, do not violate):** the conviction daily overlay archive
(``conviction_store/daily/``) only starts 2026-05-15 — 31 dates as of this writing. SSI has
full 2015+ coverage ... So: BASE+CONVICTION and ENHANCED are only computed from the conviction
archive's earliest snapshot date forward — never backfilled/fabricated for dates before that.
```

**What I can ship today:** the real dated conviction multiplier per single-name equity from 2026-05-15 forward, in the format you asked for (ticker, date, multiplier, tier label, `"N/A" → 1.0`for non-equities). **What I can't ship:** conviction tiers for 2018 – May 2026, because the archive simply doesn't go back that far — computing it retroactively means re-running the conviction scoring engine historically, which is the same category of ask as #1 (needs its own scoping, same point-in-time-inputs question). Tell me if A1 needs that backfill scoped now or if the from-2026-05-15-forward slice is enough for a first honest ENHANCED number.

---

## 5. D1 regime-bucket daily series — already delivered, here's the file

This one's genuinely done — I should have pointed you to it already instead of leaving it as a TODO on your list. Delivered **2026-07-17**, version-stamped `D1_regime_bucket_v1.1_2026-07-17`:

```
testing/macro_th_exp/D1_regime_bucket_daily_2026-07-17.csv       # 2,149 daily rows, 2018-01-01 → 2026-07-17
testing/macro_th_exp/D1_regime_bucket_fridays_2026-07-17.csv     # 446 Friday evaluation rows
testing/macro_th_exp/D1_regime_bucket_feed_2026-07-17.json
testing/macro_th_exp/D1_regime_bucket_feed_2026-07-17.md         # spec + bucket rules + caveats
```

Bucket counts (daily): BENIGN 1,617 / ADVERSE 238 / MIXED 294. Point-in-time discipline: each Friday runs `get_readings_as_of(date)` + `detect_named_combos()` against the **recalibrated** `CONFIG.yaml` gates (post-D5); Mon–Thu forward-fills the last Friday's bucket (`is_forward_filled=true`); percentiles are as-of that date, not full-sample. Two caveats worth reading before you wire it in: Combo C uses a sequential 4-Friday replay (not the live cancel flag), and WATCH-only D/E legs classify as BENIGN unless the dominant combo is adverse — both documented in the `.md` file above.

Agreed this is not P3 — it labels the day, doesn't fix the ledger. Both still needed, as you said.

---

## 6. Macro overlay feed (291→8 shortlist + combo classification)

Also already delivered, lower priority per your own ranking but no reason to make you re-ask:

```
testing/291_combo_tests/shortlist_tiered.csv                          # 298→62 candidates → 8-theme shortlist
testing/291_combo_tests/ANALYSIS_REPORT*.md                           # methodology + kept/dropped rationale
testing/5_regime_uplift/combo_classification_history.csv              # daily adverse-regime flag per combo
testing/5_regime_uplift/combo_classification_history_fridays.csv      # Friday-only slice
```

`export_combo_classification_history.py` is the generator if you need it re-run with a different as-of date or threshold set. Let me know if the shortlist needs a fresher cut than what's in `shortlist_tiered.csv` — happy to re-run.

---

## 7. Composite-score API 401 — not a missing feature, a missing header

This one's on me to just hand you the key, not build anything. The auth check is a simple shared-secret header:

```37:49:MindWealth_UI/api/dependencies.py
async def require_api_key(
    x_api_key: Annotated[str | None, Header(alias=API_KEY_HEADER)] = None,
) -> None:
    """Require X-API-Key when API_KEY env is set (or REQUIRE_API_KEY forces it)."""
    ...
    if not x_api_key or x_api_key != key:
        raise HTTPException(status_code=401, ...)
```

`/signals/entries` (where `composite_score` lives) sits behind this same dependency. Your 401 almost certainly means requests weren't sending `X-API-Key: <key>`, or were sending the wrong value. I'll send you the current dev key over a secure channel (not pasting it into this doc) — or, if you'd rather have a dedicated key tied to your own identity for audit trail, tell me and I'll cut one instead of sharing the shared dev key. Either way this removes the look-ahead concern on combo-level scoring without any code change.

---

## Priority commitment, mirrored back

Agreed on your ordering. To restate what's actually still work on my side, stripped of the items that turned out to already be done:

1. **#1 P3** — real, unscoped, biggest open item. Scoping estimate incoming (see §1 above for exactly what I'm checking).
2. **#2 R:R** — done; only open sub-item is the Test-8 numeric-fallback policy call (your call, not a build blocker on my side).
3. **#3/#4 SSI + Conviction** — real feeds ship today for the windows that exist honestly (SSI: 2015+; Conviction: 2026-05-15+). Full-history backfill for both is a new scoping conversation, same shape as #1.
4. **#5 D1** — already in your hands as of 2026-07-17, just needed pointing at.
5. **#6/#7** — already delivered / a five-minute credential handoff.

Send me confirmation on the Test-8 fallback policy and whether you need the SSI/Conviction full-history backfill scoped now, and I'll fold that into the same P3 scoping pass so you get one combined timeline instead of three separate ones.
