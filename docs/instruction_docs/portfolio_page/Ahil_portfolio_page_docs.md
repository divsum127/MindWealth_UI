# MindWealth Layer-1 Portfolio & Statistical Test Suite

A complete, newcomer-oriented reference for the equal-weight signal portfolio and the battery
of tests we run on it. Read top to bottom: it starts with the big picture, then data, then the
exact algorithm, then every test, then the file map.

---

## 0. TL;DR (one screen)

- We take trade signals produced by **9 proprietary strategies** ("Functions") on **179 tradable
  assets**, keep only the highest-quality signals (a **two-part quality gate**), and build a
  simulated **$10,000,000 equal-weight portfolio**.
- Each signal that is admitted becomes a position sized **1/N** of capital (N = how many are held
  at once). Longs and shorts are both 1/N. **No leverage, no fees, risk-free rate = 0%.**
- We then run a series of **single-knob experiments** ("Tests 1–6"): change exactly one thing
  (how many to hold, add shorts, add a stop-loss, etc.), hold everything else constant, and
  compare against a baseline on four numbers: **Sharpe, CAGR, Max Drawdown, Calmar**.
- Separately, we fill a client-facing **NAV workbook** (monthly $-NAV series) in two flavours:
  **Version A** (closed trades only) and **Version B** (all trades incl. still-open, marked to
  market).

---

## 1. What is this portfolio, exactly?

| Property | Value |
|---|---|
| Starting capital | $10,000,000 |
| Weighting | Equal weight — each open position = 1/N of NAV |
| Direction | Long **and** short; both sized 1/N |
| Leverage | None (gross exposure ≤ 100%) |
| Fees / slippage / commission | None (virtual simulation) |
| Risk-free rate | 0% (for Sharpe; shorts still earn a cash rebate — see §5) |
| Universe | 179 assets (the "stake" list) |
| Signal quality filter | Dual gate: forward win rate ≥ 60% **AND** backtested win rate ≥ 70% |
| Record type | Out-of-sample **forward** simulation (signals logged in real time) |
| Dense period | 2024 → 2026 (the real book); calendar reaches 2018 via a thin slow-interval tail |

It is a **Layer-1** book: pure equal-weight, no conviction sizing, no optimisation of weights.
Everything downstream (Sharpe, CAGR, drawdown) is derived from this one construction.

---

## 2. Data — where it comes from and how we fetch it

### 2.1 Trade signals (the input records)
- **Source:** CSV files under `trade_store/US/forward_testing/<STRATEGY>/**/*.csv`, one tree per
  strategy. Loaded by `load_all_strategy_trades()` in `portfolio_sharpe_analysis.py`.
- **Each row = one trade** with columns:
  `Function, Symbol, Signal (Long/Short), Interval (Daily/Weekly/Monthly/Quarterly/Yearly),
  Entry Date, Entry Price, Exit Date, Exit Price, Profit [%], Holding Period (days),
  Backtested Win Rate [%], Backtested Number of Trades, Avg Backtested Holding Period (days)`.
- **Open-trade detection** (`_load_trades_from_glob`): a trade is flagged `is_open = True` only if
  its exit date is the latest in its file **and** that date is within 14 days of the file's
  modification time (i.e. the script synthetically closed a still-running trade at the last bar).
  Otherwise `is_open = False`. This is what separates **Version A** (closed) from **Version B**
  (all) later.

### 2.2 Prices (for marking positions to market)
- **Source:** Yahoo Finance via `yfinance`. `fetch_daily_prices_for_trades()` calls
  `yf.download(...)` per symbol for daily closes; short rebate uses the 13-week T-bill yield
  **`^IRX`**, also from `yf.download`.
- **Caches** (so we don't refetch every run):
  - `stest_cache/prices.pkl` — windowed daily closes for the trade set (~181 series, 2017-12 → 2026-06).
  - `stest_cache/prices_full.pkl` — full-history OHLC (`period="max"`) used only by the Test 5
    backtest re-simulation. Stores `symbols_requested` so a missing ticker doesn't force a refetch.

### 2.3 Benchmark
- **`^GSPC`** (S&P 500) daily closes, cached, used for the Information Ratio / benchmark columns in
  the NAV workbook fixes.

---

## 3. The 9 strategies ("Functions")

Each strategy is a signal generator. It emits Long/Short signals at one or more intervals. Names
are internal aliases:

| Function | Notes |
|---|---|
| OSCILLATOR DELTA | High-frequency (Daily) long & short |
| TRENDPULSE | Daily/Weekly/Monthly long |
| BASELINEDIVERGENCE | Weekly long |
| FRACTAL TRACK | Weekly long; Weekly/Monthly short |
| BAND MATRIX | Daily/Weekly/Monthly long |
| DELTADRIFT | Daily/Weekly/Monthly long; Daily/Weekly short |
| SIGMASHELL | Daily long |
| PULSEGAUGE | Weekly long & short |
| ALTITUDE ALPHA | Slow intervals (Yearly/Weekly) long — the deep-history tail |

A **combo** = (Function, Interval, Direction). The book only uses the model-approved combos below.

---

## 4. The quality gates (how signals get admitted)

Two filters are applied in sequence (both in `stest_common.get_model_approved_trades()`):

### Gate 1 — Universe
Keep only trades whose `Symbol` is in the **179-asset stake list** (`data/stake.csv`).

### Gate 2 — Dual quality gate
1. **FWD ≥ 60% (combo membership):** the (Function, Interval, Direction) must be one of the
   **model-approved combos** — the `HIGH_WIN_RATE_COMBOS` set (forward win rate > 60%).
2. **BT ≥ 70% (per trade):** the individual trade's `Backtested Win Rate [%]` must be ≥ 70
   (`apply_dual_gate`, `BT_GATE_MIN = 70`).

**The 22 model-approved combos** (`portfolio_sharpe_analysis.py:HIGH_WIN_RATE_COMBOS`):

```
ALTITUDE ALPHA  Yearly  Long      DELTADRIFT      Daily    Short
ALTITUDE ALPHA  Weekly  Long      FRACTAL TRACK   Weekly   Long
BAND MATRIX     Daily   Long      FRACTAL TRACK   Monthly  Short
BAND MATRIX     Weekly  Long      FRACTAL TRACK   Weekly   Short
BAND MATRIX     Monthly Long      OSCILLATOR DELTA Daily   Long
BASELINEDIVERGENCE Weekly Long    OSCILLATOR DELTA Daily   Short
DELTADRIFT      Weekly  Long      PULSEGAUGE      Weekly   Long
DELTADRIFT      Daily   Long      PULSEGAUGE      Weekly   Short
DELTADRIFT      Monthly Long      SIGMASHELL      Daily    Long
DELTADRIFT      Weekly  Short     TRENDPULSE      Daily    Long
                                  TRENDPULSE      Weekly   Long
                                  TRENDPULSE      Monthly  Long
```

**Effect of the gate** (entry ≥ 2024-01-01):
- Version B: 4,510 → **4,027** trades (BT gate drops ~10.7%).
- Version A: 3,947 → **3,464** trades (drops ~12.2%).
- All 179 assets survive.

> NOTE: `HIGH_WIN_RATE_COMBOS` is a **hardcoded** list, not recomputed live from current forward
> data. This is the source of the "22 vs 19 approved combos" discrepancy and should be recomputed
> from live win rates when the universe changes. Two FRACTAL TRACK shorts currently show realized
> forward win rate ~46–47% (< 60%) despite being in the list.

---

## 5. Portfolio construction — the core algorithm

Implemented in `stest_common.simulate_capped` (admission) + `build_daily_return_series` (returns).

### 5.1 Admission with a simultaneous cap `N`
```
sort admitted-eligible trades by (Entry Date, Symbol)
active = []                          # exit dates of currently-open positions
for each trade in date order:
    active = [x for x in active if x > this.entry]   # free slots whose trades have exited
    if len(active) >= N:  skip this trade            # book full -> drop it
    else: admit; active.append(this.exit)
```
- **N caps CONCURRENT open positions, not unique assets.** The same asset can be held several
  times at once if different Function/Interval/Direction each fire — each is its own 1/N position.
  (Proof: `proof_simultaneous_n.py`.)
- A held trade leaves **only via its own exit date** (natural exit) — unless a test adds an
  earlier exit rule (stop-loss, R:R).
- `N = None` means "admit everything" (no cap).
- **Build-up ramp** (optional, Test 1 only): a one-time throttle of ≤ `ramp_per_day` new
  admissions per day until the book first reaches N; then the throttle turns off.

### 5.2 Daily equal-weight return
`build_daily_return_series` / `build_daily_returns_custom`:
```
for each day t:
    for each trade open on t:  compute its 1-day return r_i
    K_t = number of trades open on t
    portfolio_return_t = mean(r_i)        # equal weight = simple average
```
- **Long daily return** = price return.
- **Short daily return** = `-price_return + (IRX/360) × calendar_days` — you earn the **cash
  rebate** on the short proceeds (on calendar days), and lose/gain the negative of the price move.
- `excess_t = portfolio_return_t − rf_daily`, where `rf_daily = (1+IRX)^(1/252) − 1` (rf applied on
  trading days). Rebate (calendar) and rf (trading) run on separate schedules — never netted to 0.
- **This is a daily-rebalanced equal-weight book** (each day the portfolio is the equal average of
  whatever is open). It is *not* the "hold original $100/N to exit" scheme — see §11 caveats.

### 5.3 The Sharpe "clock"
- Portfolio metrics are only measured from the **first day K ≥ 30** (`MIN_SIMULTANEOUS_TRADES = 30`).
  Before 30 positions are simultaneously open, the book is too thin to be representative.
- If a cap `N < 30` can never reach 30 open, the clock never starts → that N is flagged
  `clock_reached = False` and excluded from the "best N" pick.

---

## 6. Metrics & formulas

All in `portfolio_sharpe_analysis.py` / `stest_common.py`. Annualisation factor = **252**.

| Metric | Formula |
|---|---|
| **Sharpe** | `mean(excess_daily) / std(excess_daily, ddof=1) × √252` |
| **CAGR** | `prod(1+daily_return)^(365.25 / days_elapsed) − 1` (calendar-day scaling) |
| **Max Drawdown** | `NAV = cumprod(1+r); min( NAV / running_max(NAV) − 1 )` |
| **Calmar** | `CAGR / |Max Drawdown|` |
| **E(R)** (per trade) | `win_rate × avg_win + (1−win_rate) × avg_loss` = mean(`Profit [%]`) |

### 6.1 Composite quality score (v4) — used by Tests 1B / 1C
`compute_composite_score(er, signal_alpha, sharpe, cagr_diff, avg_hold_days, asset_class)`:
```
er_ann    = er     × 252 / avg_hold_days      # annualise per-trade expectancy
alpha_ann = alpha  × 252 / avg_hold_days
C1 = clip(er_ann / r_ref,      0, 1) × 40      # expectancy vs asset-class reference return
C2 = clip(alpha_ann / alpha_clip, -1, 1) × 25  # signal alpha vs random-hold
C3 = clip((sharpe − 0.3) / 1.5, -0.3, 0.4) × 20
C4 = clip(cagr_diff / cagr_clip, -1, 1) × 10
score = C1 + C2 + C3 + C4                       # ~ -55 … 95
```
`r_ref`, `alpha_clip`, `cagr_clip` are per asset-class tables (`R_REF`, `ALPHA_CLIP`, `CAGR_CLIP`).

### 6.2 Reward:Risk (combo-level) — used by Tests 5/6
```
target = entry × (1 + avg_backtested_win)        [long]   / (1 − ..) [short]   # BT avg-exit price
stop   = entry × (1 + stop_frac),  stop_frac = −min(|avg BT loss|, 10%)         # Test-5 risk leg
Long  R:R(t) = (target − price_t) / (price_t − stop)
Short R:R(t) = (price_t − target) / (stop − price_t)
```
As price advances toward target, remaining reward shrinks → R:R falls.

---

## 7. The tests — inputs, method, outputs

**Common inputs:** the dual-gated trade set (Version B unless noted), the price cache, `^IRX`.
**Common outputs:** a `stest*.csv`, a `stest*.png`, and a section in the final PDF.
**Principle:** each test changes ONE knob and compares to a baseline. Tests are **not stacked**.

| Test | Knob changed | Runs on | Baseline | Output |
|---|---|---|---|---|
| **1A Optimal N** | Simultaneous cap N ∈ {20,40,60,80,100,120,all} | capped book | each other → best N (=80) | `stest1_optimal_n.csv` |
| **1A Build-up** | Fast-fill vs slow-ramp admission | capped book | steady-state | `stest1_buildup.csv` |
| **1B Quality threshold** | Min composite score (sweep) | floating-N | uncapped scored book | `stest1b_threshold.csv` |
| **1C Top-N re-rank** | Hold top-N by score, evict weakest when a better one arrives | capped book | fixed hold | `stest1c_topn.csv` |
| **2 Long/Short** | A: long-only · B: actual mix · C: shorts→cash | at optimal N | scenario B | `stest2_long_short.csv` |
| **3 Regime** | Trim exposure on adverse-regime days (deployment-scaling AND literal cut-N) | at optimal N | constant N | `stest3_regime.csv` |
| **4 Counts** | (diagnostic) daily long/short/combined open counts + short-dip episodes | full book | — | `stest4_outstanding_counts.csv`, `stest4_short_dips.csv` |
| **5 Stop-loss** | Apply a combo-level stop (avg BT loss, capped at 10%) | full book | natural exit | `stest5_*.csv` |
| **6 R:R exit** | Force-exit when live R:R < threshold (1.0…3.0) | full book | no R:R exit | `stest6_rr_exit.csv`, `stest6_overlap.csv` |

### 7.1 Test 1 details
- **1A** sweeps the simultaneous cap; reports Sharpe/CAGR/MaxDD/Calmar per N; picks the Sharpe-max
  among clock-comparable N. Result: **optimal N = 80** (written to `stest_optimal_n.txt`).
- **Build-up:** fast-fill ≈ full N in ~20–30 trading days vs a slower ramp; reports whether
  steady-state metrics move (at N=80–120 fast ≈ slow).
- **1B:** sweeps a minimum composite-score threshold; N floats with how many clear the bar.
  The reported threshold is the **Sharpe-max of an in-sample sweep** (carries in-sample-optimisation
  risk — walk-forward not yet applied).
- **1C:** continuous top-N by composite score; when a higher-scoring candidate arrives and the book
  is full, **evict the weakest current holding** (even before its natural exit). Reports
  **turnover% = evictions / admitted × 100** and the win/loss of evicted trades measured at eviction.

### 7.2 Test 3 regime detail
Adverse-day flag comes from `combo_classification_history.csv` (NOT VIX). Rule (matches the file's
`adverse_regime` column): adverse if dominant_combo ∈ {C,D,E} OR (G & ACTIVE) OR (A & FEARFUL).
Two trimming models reported side by side: **deployment-scaling** (deploy a fraction of capital on
adverse days, rest at rebate) and **literal cut-N** (shrink held book to 70/50/30% of N).

### 7.3 Test 5 detail
- Part A: close vs High(short)/Low(long) breach counting.
- Part B: **causal forward re-sim** — exit at the first day the stop is breached (not a clip),
  with gap-slippage flagging; reports per-combo which bound bound (avg-loss vs 10% cap).
- Plus a **backtest-ledger re-sim** on full-history prices → BT win rate & CAGR original vs
  stop-adjusted per combo.

---

## 8. The NAV workbooks (client deliverable)

Separate from the tests: a monthly $-NAV series that fills the client's Excel template
(`MindWealth_Ahil_NAV_Template.xlsx`). Built by a **position-level engine** (`nav_engine.py`) that
holds positions, marks them to market daily, rebalances all actives to 1/N on each new entry, and
redistributes a closed position's value to survivors on exit.

| File (in `~/Downloads`) | Meaning |
|---|---|
| `..._FILLED_GATED.xlsx` | **Version B** — ALL trades incl. still-open, marked to market |
| `..._FILLED_VersionA_GATED.xlsx` | **Version A** — closed trades only |
| `..._GATED_FIXED.xlsx` / `..._VersionA_GATED_FIXED.xlsx` | + 3 fixes: S&P 500 benchmark + Information Ratio, months-in-drawdown column, worst-DD duration/recovery |

- Window: **Jan-2024 → Jun-2026** (30 months), inception 2024-01-01. Intentional (that's where the
  dense book lives).
- Headline (dual-gated): **Version B** CAGR 13.9%, Sharpe 1.67, month-end MaxDD −5.5%;
  **Version A** CAGR 26.1%, Sharpe 2.46, month-end MaxDD −3.6%.
- **Drawdown caveat:** the workbook DD is **month-end sampled** → it smooths intramonth troughs.
  The same Version-B NAV has a **daily** peak-to-trough of −13.3% vs the −5.5% month-end figure.
  The stat-report DDs (−16…−30%) are daily and over a longer/thinner span — both are *portfolio*
  drawdown, just measured differently.

---

## 9. File map

### Code (all analysis scripts — core model code is never edited)
| File | Role |
|---|---|
| `portfolio_sharpe_analysis.py` | Trade loading, gates, price fetch, Sharpe/CAGR, `HIGH_WIN_RATE_COMBOS` |
| `stest_common.py` | Shared foundation: dual gate, `simulate_capped`, daily returns, metrics, composite score, regime loader, caches |
| `stest1_optimal_n.py` | Test 1A sweep + build-up + optimal-N pick |
| `stest1bc_quality.py` | Tests 1B (threshold) + 1C (top-N re-rank) |
| `stest2_long_short.py` | Test 2 scenarios A/B/C + E(R) |
| `stest3_regime.py` | Test 3 regime trimming (both models) |
| `stest4_outstanding_counts.py` | Test 4 daily counts + short dips |
| `stest5_stoploss.py` | Test 5 stop-loss (forward + backtest re-sim) |
| `stest6_rr_exit.py` | Test 6 R:R threshold exit |
| `nav_engine.py` | Position-level NAV engine (Version B) + template writer |
| `nav_version_a.py` | Version A (closed-only) NAV + A-vs-B comparison chart |
| `stest_nav_fixes.py` | NAV template fixes → `*_FIXED.xlsx` |
| `stest_report.py` | Builds the combined PDF report |
| `proof_simultaneous_n.py` | Standalone proof that N caps simultaneous holdings |

### Inputs
`trade_store/US/forward_testing/<STRATEGY>/**/*.csv`, `data/stake.csv`,
`combo_classification_history.csv`, Yahoo Finance (`yfinance`), the Excel template.

### Outputs
`stest*.csv`, `stest*.png`, `stest_optimal_n.txt`, `MindWealth_Stat_Tests_Report.pdf`,
`nav_*_GATED*.csv`, `~/Downloads/MindWealth_Ahil_NAV_FILLED_*GATED*.xlsx`, caches under `stest_cache/`.

---

## 10. How to run

```bash
# 1. Foundation (loads trades, applies gates, prints universe)
python3 stest_common.py

# 2. Tests (each writes its CSV/PNG)
python3 stest1_optimal_n.py        # writes stest_optimal_n.txt (used by 2 & 3)
python3 stest1bc_quality.py
python3 stest2_long_short.py
python3 stest3_regime.py
python3 stest4_outstanding_counts.py
python3 stest5_stoploss.py
python3 stest6_rr_exit.py

# 3. NAV workbooks
python3 nav_engine.py              # Version B (gated) + fills template
python3 nav_version_a.py           # Version A (gated) + A-vs-B chart
python3 stest_nav_fixes.py         # -> *_GATED_FIXED.xlsx

# 4. Combined PDF
python3 stest_report.py

# proof
python3 proof_simultaneous_n.py
```

First run fetches prices from Yahoo (slow); subsequent runs use `stest_cache/`.

---

## 11. Known caveats & open items

1. **Rebalancing mismatch.** Current code rebalances to equal weight (NAV engine on each entry;
   stat tests daily). The newer brief specifies **no rebalancing — hold original $100/N to exit**.
   Not yet switched; a decision item.
2. **Drawdown sampling.** NAV workbook DD is month-end (understates); stat-report DD is daily. A
   daily-DD row should be added to the workbook for an apples-to-apples "peak DD".
3. **FWD gate is hardcoded**, not recomputed live (22 vs 19 combos; two FRACTAL shorts < 60%).
4. **Tests are single-knob, not composed.** Because Tests 2/3 run at N=80 and Tests 5/6 on the full
   book, their improvements can't be added up — a combined "best-of" config is a separate run.
5. **In-sample threshold (1B).** The score threshold is Sharpe-maximised in-sample → needs
   walk-forward / out-of-sample validation.
6. **Time span.** Calendar reaches 2018 but 90% of trades are 2024+; the ≥30-simultaneous clock
   starts ~2023. Treat pre-2023 as a thin slow-interval tail, not a real track record.
7. **Label cleanups pending.** "Rolling CAGR" → "Annualised Return since Inception"; regime label
   "FEARFUL" → "BEARISH" (display only; the code still matches the classification file's value).

---

## 12. Work owed by Divyanshu — the exact Reward:Risk ("Proposed_RR") definition

**Where this surfaces in the code:** `stest6_rr_exit.py:7-8` documents the R:R we use as a
*placeholder* — the "revised Proposed_RR based on BT avg exit price", pending Divyanshu's exact
firm formula **`compute_rr_to_nearest_support_stop`**. The pending PDF section
(`stest_report.py:470`) states: *"If Divyanshu's exact Proposed_RR differs, swap the target/stop
definition and re-run — the harness is in place."*

**Why it matters:** the R:R number drives two things — **Test 6** (force-exit a held position when
live R:R drops below a threshold) and **Test 8** (R:R as a binary admission flag in 1C + optional
poor-R:R force-exit). Both currently run on a placeholder R:R; they cannot be considered final
until Divyanshu supplies the real definition.

### 12.1 What Divyanshu must deliver

1. **The exact target (reward leg).** Our placeholder = BT-avg-exit price
   `entry × (1 + avg_backtested_win)`. His `compute_rr_to_nearest_support_stop` implies the target
   should instead be the **nearest resistance/support level** (or whatever the firm formula uses).
   Provide: the precise rule and the data source for that level (per Symbol/Interval).
2. **The exact stop (risk leg).** Our placeholder = the Test-5 stop
   `entry × (1 + stop_frac)`, `stop_frac = −min(|avg BT loss|, 10%)`. His formula points to the
   **nearest support/stop level**, not the avg-loss stop. Provide: how that level is located
   (swing low, moving-average band, pivot, ATR multiple, etc.) and its inputs.
3. **The R:R expression** to plug into the harness, for both directions:
   - Long: `R:R = (target − price) / (price − stop)`
   - Short: `R:R = (price − target) / (stop − price)`
   Confirm this matches his `compute_rr_to_nearest_support_stop`, or give the exact replacement.
4. **The fallback for undefined R:R** (Rohit flagged this explicitly for Test 8). Many assets have
   **no clean support/stop level nearby** → R:R can't be computed cleanly. Divyanshu must specify
   the rule when the level is missing/unreliable, e.g.:
   - skip the R:R flag and keep the trade's natural handling, or
   - fall back to the avg-loss/10%-cap stop, or
   - exclude the trade from the R:R-gated variant.
   State which, and how "no clean level nearby" is detected (distance threshold to the level).
5. **Threshold(s) and mode.** Confirm the R:R cutoff(s) to test (e.g. 1.0×, and whether we sweep
   1.0–3.0), and for each usage:
   - **Test 6:** live-exit threshold (exit when R:R falls below it), vs natural-exit baseline.
   - **Test 8:** admission threshold (don't admit a new candidate whose R:R < threshold) AND,
     separately, whether to force-exit a held position on a poor-R:R flag — judged on Max DD /
     Calmar improvement without giving up the composite-score CAGR/Sharpe.

### 12.2 What is already built (so Divyanshu only supplies the formula)

- The exit/admission harness exists: `stest6_rr_exit.py` (`build_combo_legs`, `rr_exit_trade` with
  an entry-R:R guard, `overlap_with_test5`). Swapping in his target/stop definition is a localized
  change to how `target` and `stop` are computed — the sweep, metrics, overlap, and plotting all
  stay.
- Composite score (v4) remains the **sole** ranker/evictor in 1C; R:R layers on top as a flag only
  (per Rohit). No change to the ranking engine is needed from Divyanshu.

### 12.3 Hand-off format (suggested)

A short spec or a Python function with signature roughly:
```python
def compute_rr_to_nearest_support_stop(symbol, interval, direction, entry_price, as_of_date,
                                       price_history) -> tuple[float | None, float, float]:
    """Return (rr, target_price, stop_price); rr=None when no clean level nearby (fallback)."""
```
Given that, we wire it into `rr_exit_trade`, re-run Tests 6 and 8, and the report/plots regenerate
unchanged.
