# MindWealth Signals MasterSpec — Implementation Status v2

**Date:** 2026-06-19
**Implemented by:** Divyanshu (AI-assisted implementation session)
**Reference:** `MindWealth_Signals_MasterSpec.pdf` + `additional_details.md`

---

## Summary

All tasks assigned to Divyanshu from the MindWealth Signals MasterSpec have been
implemented. The implementation spans four files plus a new test file.

---

## Completed Tasks

### A1 — Wire avg_loss numeric into enrich_signal_dict

**File:** `helper_functions/claude_lateness_metrics.py`

`parse_bt_avg_lose_return_pct()` was already defined (line ~178) but never called.
Now called inside `enrich_signal_dict()` and the result injected as
`bt_avg_lose_return_pct` (plain % float, e.g. −2.31).

---

### B1 — Asset class classification

**File:** `helper_functions/claude_lateness_metrics.py`

Added:
- `ASSET_CLASS_MAP` — exhaustive ticker → asset_class dict covering US equities,
  Canadian/NZ/Indian/Korean equities, equity ETFs, commodity ETFs, bond ETFs,
  crypto ETFs, indices, FX pairs, and crypto. ~90 explicit entries.
- `R_REF` — per-asset-class reference E[R] (%) for composite C1 scoring.
- `ER_GATE_MIN` — per-asset-class E[R] gate minimums for Gate A2a.
- `derive_asset_class(ticker)` — lookup + suffix fallback (`.NS`, `.TO`, `.NZ`,
  `^`, `-USD`, `=X`).
- Called in `enrich_signal_dict()` → `row["asset_class"]`.

---

### B2a — Expected Return E[R]

**File:** `helper_functions/claude_lateness_metrics.py`

Added `compute_er(win_rate_pct, bt_avg_win_pct, bt_avg_lose_pct, bt_max_loss_pct)`:
- Uses real avg_lose when available (A1); falls back to `−max_loss × 0.6` proxy.
- Added parse helpers: `_parse_win_rate()`, `_parse_bt_max_loss()`.
- Injected as `row["er"]`.

---

### B2b — random_window_return and signal_alpha_per_trade

**File:** `helper_functions/claude_lateness_metrics.py`

Added:
- `_parse_bt_bh_cagr()` — parses "CAGR of Buy and Hold [%]".
- `compute_random_window_return(bt_bh_cagr_pct, avg_hold_days)` → passive hold
  return over the same window = `(B&H_CAGR / 252) × avg_hold_days`.
- `signal_alpha_per_trade = er − random_window_return` (Long); `= er` for Short
  (conservative — no drift credit).
- Injected as `row["random_window_return"]` and `row["signal_alpha_per_trade"]`.

---

### B2c — rr_static and rr_dynamic alias

**File:** `helper_functions/claude_lateness_metrics.py`

Added:
- `compute_rr_static(bt_avg_win_pct, current_price, nearest_stop)` — uses BT avg
  win % as reward divided by %-distance to stop.
- `rr_dynamic` alias = `rr_to_nearest_support_stop` (already computed).
- Injected as `row["rr_static"]` and `row["rr_dynamic"]`.

---

### B2d — theoretical_entry_price and upside_remaining_pct

**File:** `helper_functions/claude_lateness_metrics.py`

Added:
- `_parse_first_pct()` — extracts first % token from slash-separated strings.
- `compute_theoretical_entry_price(function, signal_open, current_price, track_field,
  trendpulse_pct_field)`:
  - TRENDPULSE: back-calculates breakout price from current % move.
  - FRACTAL TRACK: uses first track level.
  - Others: signal open price.
- `compute_upside_remaining(direction, theoretical_entry, bt_avg_win_pct,
  current_price)` — % of BT avg win not yet realised.
- Injected as `row["theoretical_entry_price"]` and `row["upside_remaining_pct"]`.

---

### B2e — composite_score and timeliness_score

**File:** `helper_functions/claude_lateness_metrics.py`

Added:
- `_parse_sharpe()` — parses "Backtested Strategy Sharpe Ratio".
- `compute_composite_score(er, signal_alpha, sharpe, asset_class)`:
  - C1 = `min(max(er/R_ref, 0), 1) × 50`
  - C2 = `max(min(signal_alpha/5, 1), −1) × 15`
  - C3 = `max(min((sharpe−0.3)/1.5, 0.4), −0.3) × 20`
  - Range **−21 to +73** (NOT clamped to 0–100).
- `compute_timeliness_score(elapsed, cutoff)` — 0–100, linear.
- Injected as `row["composite_score"]` and `row["timeliness_score"]`.

---

### C/D — Updated GOOD_SIGNAL_QUERY composite formula and surface_json schema

**File:** `constant.py`

Changes:
1. **SIGNAL QUALITY COMPOSITE section** (lines ~707–723) replaced:
   - C2 now uses `signal_alpha_per_trade` (not `cagr_alpha`).
   - Score range explicitly stated as **−21 to +73** (not 0–100).
   - R_ref table added inline.
   - Passive-hold display flag added (annotate "passive-hold adequate" when
     `signal_alpha < 0.5 AND er > 0`).
   - Fallback formula retained for missing avg_win/avg_loss.
2. **surface_json schema** updated to include all new fields:
   `asset_class`, `random_window_return`, `signal_alpha_per_trade`, `rr_static`,
   `rr_dynamic`, `theoretical_entry_price`, `upside_remaining_pct`,
   `composite_score`. Field removed: `quality_score` → renamed `composite_score`.
3. **Gate A2d** updated: language now references `signal_alpha_per_trade`; falls
   back to CAGR alpha behaviour when field is absent.

---

### E1 — New gates A2a and A2e

**File:** `constant.py` (inside `GOOD_SIGNAL_QUERY`)

Added:
- **Gate A2a** (E[R] Minimum): inserted after Gate A2 (Win Rate gate). Hard
  exclude from Tier A when `er < ER_GATE_MIN[asset_class]`. Field absence ≠
  failure.
- **Gate A2e** (R:R ≥ 1.0): inserted after Gate A2d. Hard exclude when
  `rr_dynamic < 1.0` (or `rr_static < 1.0` if rr_dynamic absent). Field absence
  ≠ failure.

---

### F2 — Regime context in synthesis prompt

**File:** `send_email.py`

Added:
- `_RUNIC_OUTPUT_PATH` constant pointing to
  `.../macro_intelligence/output/runic_output.json`.
- `_fetch_regime_context(today_date_str)` function — best-effort fetches:
  - **VIX** via `yfinance.download("^VIX", period="2d")`.
  - **SSI** via `compute_sbi_breadth_stance(today_date_str)` (already in scope).
  - **Runic** active/watch combos from `runic_output.json`.
  Each source fails gracefully to "not available".
- Synthesis prompt prepended with `regime_context` block (verbatim REGIME
  CONTEXT section) before the existing synthesis instructions.

---

### G2 — BT WR footnote

**File:** `send_email.py`

Added:
- `BT_WR_FOOTNOTE` constant defined after the import block.
- `html_body += BT_WR_FOOTNOTE` appended in both:
  - `send_new_signal_mail()` (after `dataframe_to_two_html_table` call)
  - `send_outstanding_signal_mail()` (after `dataframe_to_four_html_tables` call)

---

### G1 — Portfolio universe guard

**File:** `virtual_trading.py`

Added:
- Import: `from helper_functions.claude_lateness_metrics import ASSET_CLASS_MAP`.
- Inside `add_trades_from_signal_data()`, before the `pd.concat` that opens a
  new position: if `symbol not in ASSET_CLASS_MAP`, emit a `logger.warning` with
  coverage note. Does **not** block the trade (per spec: "add it simultaneously").

---

### G3 — Verification smoke tests

**File:** `tests/test_signals_masterspec_g3.py` (new file)

Five pytest tests — all pass (5/5):
1. `test_iei_er_proxy_negative` — bond ETF with low WR → negative E[R].
2. `test_djia_upside_remaining` — TrendPulse signal 2.57% into the move → ~43%
   upside remaining (30–60% range).
3. `test_jets_signal_alpha_via_enrich` — full pipeline via `enrich_signal_dict`;
   positive signal alpha for JETS.
4. `test_rr_dynamic_alias` — `rr_dynamic` equals `rr_to_nearest_support_stop`.
5. `test_xiu_to_asset_class` — `XIU.TO` classified as `equity_etf`.

---

## Residual Gaps / Known Limitations

| Gap | Owner | Notes |
|-----|-------|-------|
| **A2/A3 Ahil tasks** | Ahil | B&H CAGR / conviction fields population in the signal pipeline |
| **Runic daily summary automation** | MindWealth UI team | `runic_output.json` is updated by UI pipeline; `_fetch_regime_context()` reads it best-effort; if the file is stale the date mismatch is not checked |
| **ASSET_CLASS_MAP completeness** | Ongoing | Tickers not in the explicit map fall back to suffix rules; new tickers need explicit entry for precise classification |
| **G3 integration tests** | Future | Unit tests use a stubbed `util` module; full integration tests require the complete MindWealth env (joblib, data.py) |
| **Gate A2a ER_GATE_MIN values** | Confirm with spec owner | Values set to R_ref × 0.2 approximation; spec Table C1 may differ |

---

## Files Changed

| File | Change type |
|------|-------------|
| `helper_functions/claude_lateness_metrics.py` | Extended (~+250 lines: new constants, 10 new functions, expanded enrich_signal_dict) |
| `constant.py` | Modified (~+40 lines: 3 new gates, updated composite formula, updated surface_json) |
| `send_email.py` | Modified (~+60 lines: BT_WR_FOOTNOTE, _fetch_regime_context, synthesis_prompt update) |
| `virtual_trading.py` | Modified (~+5 lines: ASSET_CLASS_MAP import, universe guard warning) |
| `tests/test_signals_masterspec_g3.py` | New file (5 smoke tests) |
