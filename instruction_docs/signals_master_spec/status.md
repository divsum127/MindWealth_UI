# MindWealth Signals MasterSpec — Implementation Status

**Spec document:** `MindWealth_Signals_MasterSpec.pdf` (June 2026, Rohit → Divyanshu / Ahil)  
**Additional context:** `additional_details.md` (revised composite formula, R_ref table, C2 signal_alpha definition)  
**Last checked:** 2026-06-19  

---

## Summary

| Section | Task | Owner | Status |
|---------|------|-------|--------|
| A1 | Average loss return per trade — new column in backtester output | Divyanshu | **IN PROGRESS (local, uncommitted)** |
| A2 | OscillatorDelta entry timing test (3 scenarios) | Ahil | **NOT STARTED** |
| A3 | IBKR B&H CAGR window confirmation | Ahil | **NOT STARTED** |
| B1 | Asset class classification field (`asset_class`) | Divyanshu | **NOT STARTED** |
| B2 | Computed quality fields: E[R], signal_alpha, rr_static, rr_dynamic, theoretical_entry_price, upside_remaining_pct | Divyanshu | **NOT STARTED** |
| C | Quality composite formula update (C2 → signal_alpha, revised sharpe clip, −21 to +73 range) | Divyanshu | **PARTIALLY DONE** (old formula still in GOOD_SIGNAL_QUERY) |
| D | CAGR_diff demoted to diagnostic flag only | Divyanshu | **PARTIALLY DONE** (documented in prompt, not enforced in scoring code) |
| E1 | Gate A2a (E[R] ≥ asset-class min) | Divyanshu | **NOT STARTED** |
| E1 | Gate A2e (rr ≥ 1.0) | Divyanshu | **NOT STARTED** |
| E1 | Gates A2b, A2c, A2d | Divyanshu | **PARTIALLY DONE** (A2b, A2d in GOOD_SIGNAL_QUERY; A2c in conviction engine) |
| F | Claude daily JSON payload — full per-signal fields (Section F1) | Divyanshu | **PARTIALLY DONE** |
| F | Regime context in Claude payload (Section F2: runic_combo_active, ssi_value, vix_level) | Divyanshu | **NOT STARTED** |
| G1 | Portfolio universe constraint | Divyanshu | **NOT STARTED** |
| G2 | BT WR footnote in Outstanding and New Signals reports | Divyanshu | **NOT STARTED** |
| G3 | Verification tests (IEI proxy, DJI upside_remaining, JETS gate, rr_dynamic daily recompute, XIU.TO class) | Divyanshu | **NOT STARTED** |

---

## Detailed Status

---

### A1 — Average Loss Return Per Trade *(Divyanshu)*

**Status: IN PROGRESS — local uncommitted changes exist**

What is done (local, not committed, not in last nightly run):

- **`util.py`** — `calculate_trades_summary()` now returns `(max_lose, min_lose, avg_lose)`. Result dict emits `"Lose Trade Return [%] (Max/Min/Avg)"`.
- **`util.py`** — `calculate_trade_durations()` now also returns `(max_duration_all, avg_duration_all, min_duration_all)` for all-trades holding period. Result dict emits `"Holding Period (All Trades) [days] (Max/Min/Avg)"`.
- **11 helper function files** (`trendline.py`, `sigma.py`, `bollinger.py`, `distance.py`, `fib_ret.py`, `horizonal.py`, `math_algo.py`, `divergence_comp.py`, `general_divergence.py`, `new_high.py`, `sentiment.py`) — all map `"Lose Trade Return [%] (Max/Min/Avg)"` into the standardised column `"Backtested Return [%] (Lose Trades) (Max/Min/Avg)"`.
- **`send_email.py`** — `get_common_column()` passes `"Backtested Returns (Lose Trades) [%] (Max/Min/Avg)"` through to the Claude payload dict; `claude_box_prompt()` calls `enrich_signal_dict()` per signal before building the JSON.
- **`helper_functions/claude_lateness_metrics.py`** (new file, untracked) — defines `BT_LOSE_RETURNS_KEY`, `parse_bt_avg_lose_return_pct()`, `HOLDING_ALL_TRADES_KEY`, `parse_avg_holding_days()`, `enrich_signal_dict()`.
- **`constant.py`** — `GOOD_SIGNAL_QUERY` `<surface_json>` example now includes `avg_win`, `avg_loss`, `expected_return`, `avg_hold_all_trades`.

**What is NOT done yet:**
- None of the above is committed to git.
- `signal_data_long.csv` (last written 2026-06-18 01:23 UTC) still has **no** `"Backtested Returns (Lose Trades)..."` column — changes ran after the nightly cron.
- `parse_bt_avg_lose_return_pct()` exists in `claude_lateness_metrics.py` but is **not called** inside `enrich_signal_dict()` — so `avg_loss` is never injected as a numeric field into the per-signal JSON Claude receives. Only the raw string column is forwarded.
- `E[R]` is not computed in Python and added as a computed field to the payload; the prompt instructs Claude to derive it, which is fragile.

---

### A2 — OscillatorDelta Entry Timing Test *(Ahil only)*

**Status: NOT STARTED**

No code, output files, or test results found for the 3-scenario entry lag study.  
Required: identify asset with most OscillatorDelta trades, run scenarios A/B/C, produce win rate / avg win / avg loss / median return for each, and confirm whether the thick-line end equals theoretical divergence end.

---

### A3 — IBKR B&H CAGR Window Confirmation *(Ahil only)*

**Status: NOT STARTED**

No confirmation found. The report shows IBKR TrendPulse Daily B&H CAGR = 27.95%. Ahil must confirm this is computed over the same 4-year window as the strategy backtest.

---

### B1 — Asset Class Classification *(Divyanshu)*

**Status: NOT STARTED**

The `ASSET_CLASS_MAP` and `derive_asset_class()` function from the spec exist only in the spec PDF. No implementation found in `MindWealth/` or `MindWealth_UI/`. The field `asset_class` does not appear anywhere in:
- `util.py`, `send_email.py`, `constant.py`
- any helper function
- the Claude payload / `<surface_json>` schema

**Blocker for:** B2 (E[R] uses R_ref per asset class), C1 (er_score normalisation), Gate A2a.

---

### B2 — Computed Quality Fields *(Divyanshu)*

**Status: NOT STARTED**

None of the following are computed in code and added to the per-signal payload:

| Field | Status |
|-------|--------|
| `er` (E[R]) | Not computed in Python. Prompt has old fallback formula using `win_rate` only. |
| `signal_alpha_per_trade` | Not computed anywhere. |
| `random_window_return` | `avg_duration_all` added to output (A1), but division by 252 × bt_bh_cagr never done. |
| `rr_static` | Not computed. `rr_to_nearest_support_stop` in `claude_lateness_metrics.py` computes a dynamic RR but not the static one. |
| `rr_dynamic` | `rr_to_nearest_support_stop` in `enrich_signal_dict()` is a dynamic RR — partially covers this, but field name differs from spec. |
| `theoretical_entry_price` | Not computed for any function. |
| `upside_remaining_pct` | Not computed. |
| `asset_class` | See B1. |
| `bt_avg_loss_return` (numeric) | `parse_bt_avg_lose_return_pct()` exists but is not called in `enrich_signal_dict()`. |
| `composite_score` | Not computed. |

---

### C — Quality Composite Formula Update *(Divyanshu)*

**Status: PARTIALLY DONE**

The `GOOD_SIGNAL_QUERY` in `constant.py` still uses the **old composite formula** (C2 = `cagr_alpha / 10 × 30`, forced 0–100). The spec's revised formula is:

```
C1: er_score   = clip(er / R_ref, 0, 1.0) × 50        (asset-class R_ref)
C2: alpha_score = clip(signal_alpha / 5%, −1.0, +1.0) × 15  (NOT cagr_diff)
C3: sharpe_score = clip((sharpe − 0.3) / 1.5, −0.3, +0.4) × 20
Range: −21 to +73  (NOT forced 0–100)
```

The `additional_details.md` makes this explicit. The old C2 (`cagr_alpha/10 × 30`, range −15 to +15) and old forced 0–100 scaling are still in production code.

**What needs updating:**
- `constant.py` → `GOOD_SIGNAL_QUERY` → section `SIGNAL QUALITY COMPOSITE` (lines ~707–715)
- The `<surface_json>` field `quality_score` computed by Claude uses old formula
- R_ref per asset class table needs to be added (requires B1 first)

---

### D — CAGR_diff Demotion *(Divyanshu)*

**Status: PARTIALLY DONE**

- `GOOD_SIGNAL_QUERY` includes Gate A2d language about CAGR_diff thresholds (daily −15%, weekly −20%, monthly −25%).
- The passive-hold flag (CAGR_diff negative + signal_alpha positive) is described in the prompt.
- **Not done:** Gate A2d uses old terminology ("CAGR alpha") not "CAGR_diff". The `signal_alpha_per_trade` field it depends on is not computed, so the gate cannot actually fire correctly.

---

### E1 — Gate Updates *(Divyanshu)*

**Status: PARTIALLY DONE**

| Gate | Status |
|------|--------|
| A2a: E[R] ≥ asset-class minimum | NOT DONE — E[R] not computed, asset_class not added |
| A2b: Fwd WR ≥ 60% | DONE — in GOOD_SIGNAL_QUERY |
| A2c: Conviction ≥ min | DONE — conviction engine integrated |
| A2d (nuanced): CAGR_diff hard disqualifier | PARTIALLY DONE — in prompt, but signal_alpha missing |
| A2e: rr ≥ 1.0 | NOT DONE — not in prompt or code |

---

### F — Claude Daily JSON Payload *(Divyanshu)*

**Status: PARTIALLY DONE**

**Present in payload today:**

- `symbol`, `function`, `interval`, `direction`, `signal_date`, `signal_price`
- `current_price`, `days_elapsed`, `mtm_pct`
- `bt_wr` (as win rate string), `fwd_wr`
- `bt_avg_win_return` (as string field `Backtested Returns(Win Trades) [%] (Max/Min/Avg)`)
- `bt_avg_loss_return` (partially — string column added, numeric parse not injected)
- `bt_max_loss`, `bt_strategy_sharpe`, `bt_strategy_cagr`, `bt_bh_cagr`, `cagr_diff`
- `nearest_target_price`, `nearest_stop_price` (string format)
- `entry_anchor`, `T1`, `T1_type`, `progress`, `rr_to_nearest_support_stop` (dynamic), `lateness_gate`, `lateness_gate_reason`, `time_lateness_flag` ← added by `enrich_signal_dict()`

**Missing from payload (per F1 spec):**

- `theoretical_entry_price` (per function — none of the 5 function-specific formulae implemented)
- `upside_remaining_pct`
- `er` (numeric, pre-computed)
- `signal_alpha_per_trade`
- `composite_score`
- `rr_static` (only dynamic rr present)
- `rr_dynamic` (present but named differently: `rr_to_nearest_support_stop`)
- `asset_class`
- `bt_avg_hold_days` (numeric — string form present via `Holding Period (All Trades) (days)`)
- `conviction_bq_score`, `conviction_fs_class` (conviction scores are computed in the conviction engine but not injected into the per-signal Claude payload)

**F2 — Regime context (per daily run):**

- `runic_combo_active`, `runic_on_watch`, `ssi_value`, `vix_level` — **NONE present** in the `send_email.py` Claude payload assembly. The Runic engine exists in `MindWealth_UI` but its daily output is not forwarded to the Claude email prompt.

---

### G1 — Portfolio Universe Constraint *(Divyanshu)*

**Status: NOT STARTED**

No enforcement found that a newly opened portfolio position must be in the ~200-asset model universe. The virtual trading module exists but the check is absent.

---

### G2 — BT WR Footnote *(Divyanshu)*

**Status: NOT STARTED**

The footnote text (*"BT WR is backtested across the full historical period..."*) does not appear in `send_outstanding_signal_mail()`, `send_new_signal_mail()`, or any email-building function.

---

### G3 — Verification Tests *(Divyanshu)*

**Status: NOT STARTED**

None of the 5 verification tests listed in Section G3 have been run:

1. IEI E[R]_proxy should be negative (≈ −0.05%)
2. ^DJI upside_remaining_pct ≈ 40%
3. JETS signal_alpha ≈ +0.19% + CAGR_diff = −21.09% → Gate A2d disqualifier
4. rr_dynamic recomputed from current_price daily when days_elapsed > 0
5. XIU.TO asset_class = `equity_etf` (not `equity`)

---

## Priority Order (Suggested)

1. **Commit A1 changes** — code is done, just needs committing and a cron cycle to verify `avg_loss` flows end-to-end into the CSV and Claude payload.
2. **B1 (asset_class)** — unblocks B2, C, Gate A2a, G3-test-5.
3. **B2 — compute E[R] and signal_alpha_per_trade** in `enrich_signal_dict()` — these two fields unlock the correct C composite, Gate A2a, and Gate A2e.
4. **Update GOOD_SIGNAL_QUERY** composite formula (C section) to match spec (C2 = signal_alpha, range −21 to +73, per-class R_ref).
5. **Add rr_static** alongside existing rr_dynamic in `enrich_signal_dict()`.
6. **Add theoretical_entry_price** per function (5 cases: TrendPulse, FractalTrack, OscillatorDelta pending A2, others = signal_price).
7. **Add upside_remaining_pct** once theoretical_entry_price is computed.
8. **Add Gate A2e** (rr ≥ 1.0) to GOOD_SIGNAL_QUERY.
9. **Wire F2 regime context** (Runic combo active / on_watch + SSI + VIX) into Claude payload in `send_email.py`.
10. **G2 footnote**, **G1 universe check**, **G3 tests** can be done in parallel.
11. **A2 / A3** — Ahil items, independent track.

---

*This file auto-documents spec implementation status. Update when tasks complete.*
