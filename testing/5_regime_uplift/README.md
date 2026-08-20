# Test 5 — Regime Sharpe Uplift (Ahil)

Demonstrates whether the Runic **5 regime dimensions** improve risk-adjusted returns on an equal-weight **SPY / TLT / GLD / HYG** benchmark.

| Doc | Purpose |
|-----|---------|
| [PLAN.md](PLAN.md) | Experiment spec |
| [regime_dimension_multipliers_v1_unsigned.md](regime_dimension_multipliers_v1_unsigned.md) | v1 dimension → multiplier table |
| [output_files/REPORT.md](output_files/REPORT.md) | **Michele-ready results** |
| [run_regime_sharpe_uplift.py](run_regime_sharpe_uplift.py) | Backtest script |

**Latest result (2026-07-14):** Baseline Sharpe **0.885** → overlay **0.938** (**+0.053**). CAGR lower (6.39% vs 7.72%) but max drawdown improved (−17.6% vs −22.6%) — de-risking story.

```bash
.venv/bin/python testing/5_regime_uplift/run_regime_sharpe_uplift.py
```

---

# Test 3 — Adverse regime conditioning flag

## File

`combo_classification_history.csv` — daily series (forward-filled from Friday Runic evaluations).

## Dominant combo rule

`CONFIG_PRIORITY_v1` — fixed rank from `macro_intelligence/CONFIG.yaml`:

`C(100) > B(90) > F(80) > E(70) > D(60) > G(50) > A(40)`

Eligible statuses: `ACTIVE`, `PARTIAL`, `CONFIRMED`, `CONFIRMED_3_OF_3` (not `WATCH`).

## Adverse regime rule

`adverse_regime = true` when:

- `dominant_combo` in `{C, D, E}`, or
- `dominant_combo = G` and status is ACTIVE-class, or
- `dominant_combo = A` and `resolved_intent = FEARFUL` (from `a_vote` / `TIGHT_MONEY` in DB)

Otherwise `false` (including no dominant, WATCH-only days, `B`/`F`, `A` BRAVE).

## Columns

| Column | Description |
|--------|-------------|
| `date` | Calendar date (`daily_readings` universe) |
| `dominant_combo` | Winning named combo letter, or blank |
| `dominant_status` | Status of dominant combo |
| `design_intent` | BEARISH / BULLISH / CAUTIONARY / FEARFUL / BRAVE / NEUTRAL |
| `resolved_intent` | Combo A vote when relevant |
| `adverse_regime` | `true` / `false` — Test 3 conditioning flag |
| `active_combos` | `;`-separated ACTIVE-class combos on evaluation Friday |
| `watch_combos` | `;`-separated WATCH combos on evaluation Friday |
| `evaluation_date` | Friday when combo state was last evaluated |
| `is_forward_filled` | `true` if date is after evaluation Friday (carry-forward) |
| `dominant_rule` | `CONFIG_PRIORITY_v1` |

## Regenerate

```bash
cd /home/ubuntu/uiv2/git/MindWealth_UI
.venv/bin/python scripts/export_combo_classification_history.py
```

Fridays only (no forward-fill):

```bash
.venv/bin/python scripts/export_combo_classification_history.py --fridays-only \
  --out testing/5_regime_uplift/combo_classification_history_fridays.csv
```

## Caveat

Dominant tie-break pending Divyanshu confirmation (fixed PRIORITY vs nearest-term horizon).
