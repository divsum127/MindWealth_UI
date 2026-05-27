# Conviction Engine v6 — Updates & Fixes

This document summarizes implementation work aligned with **ConvictionEngine_v6_Internal.pdf** and the backend brief (feature-store tiers, 5-vote fundamental direction, valuation tax breakdown, debt-purpose balance sheet, yield-trap gate, Streamlit v6 scorecard).

For day-to-day operations, see [conviction_engine_fundamentals.md](../documentation/conviction_engine_fundamentals.md). For REST fields, see [Conviction API](../api/services/conviction/README.md) and [get-ticker](../api/services/conviction/endpoints/get-ticker.md).

---

## Scope

| Area | Status |
|------|--------|
| Core scoring (BQ, valuation tax, FD, yield trap) | Implemented |
| New Python modules (`bq_scoring`, `fd_votes`, `agent_dims`) | Implemented |
| Streamlit Conviction Engine page (v6 scorecard) | Implemented |
| API docs / changelog (partial) | Updated |
| Earnings cron, Macrotrends PE, SEC/SEDI, portfolio_store | Not implemented |
| Full universe backfill | Manual — run when ready |

---

## Backend — scoring & store

### Business quality (15 dimensions)

- **`bq_components`** remain stored per ticker in `conviction_store/{TICKER}.json` (all 15 keys).
- **Manual analyst scores** (CEO, mgmt allocation, moat): fixed mapping from 0–10 → BQ points (`8–10` → +2, `5–7` → +1, `3–4` → 0, `0–2` → −1). Previously `compute_bq_components_auto` could treat raw scores as BQ points.
- **Debt purpose** (`financial_engineering` | `capex_cycle` | `operational`) via [`src/conviction_engine/bq_scoring.py`](../../src/conviction_engine/bq_scoring.py); persisted as **`debt_purpose`**.
- **Balance sheet** uses debt-purpose rules (e.g. net cash → +2 for financial engineering).
- **Cyclical `margin_quality`**: normalized FCF / growth proxy for cyclical type.
- **Auto divergence signal**: price ≤ 85% of 52W high for ≥60 days and `fd_direction` ≠ negative (when price history available); manual override still supported.
- **`revenue_accelerating`**: computed from last 3 quarterly revenue prints in `build_fundamentals_from_raw`.

### Fundamental direction (5 votes)

- New [`src/conviction_engine/fd_votes.py`](../../src/conviction_engine/fd_votes.py): majority of 5 votes → `positive` | `stable` | `negative`.
- Votes: revenue acceleration, gross margin trend, FCF YoY (when `fcf_growth_yoy` present), EPS revisions vs stored prior, share count change TTM.
- Persisted: **`fd_votes`** (per-vote result + rationale), **`fd_direction`**, **`fd_sizing_adj`** (+0.10 / 0 / −0.15).
- BUY sizing in `modify_signal` multiplies base sizing by `(1 + fd_sizing_adj)` when applicable.

**Note:** FCF and EPS revision votes often stay `stable` until `fcf_growth_yoy` and `eps_estimate_prior` are populated on recurring full recalcs.

### Valuation tax (v6)

- [`calculate_valuation_tax_components`](../../src/conviction_engine/scoring.py): `entry_multiple`, `pe_hist_percentile`, `growth_multiple_fragility`, `business_type_relief`, `deal_delay_signal`, `market_regime_beta`, `oey_penalty`.
- Total capped to **[-10, 0]** with **type-specific minimum penalty triggers** (saas 4×, compounder 3×, income 6×, cyclical none).
- Stored: **`valuation_tax_breakdown`** `{ components, total }`; **`valuation_tax`** = total.

### Yield trap

- Unchanged rule: **both** required — z-score **> 1.5** vs 5Y own history **and** yield **≥** market threshold (NZ 12%, AU 10%, CA 7%, UK 9%, default 6%).
- **`yield_trap_mkt_threshold`** stored on each record.
- SELL → **HARD EXIT**; BUY → **CANCEL BUY** (hard gate before verdict tiers).

### Signal modifier warnings

- **`TRAILING_STOP_WARNING`**: short BUY + `long_position_near_stop` → CANCEL BUY (unchanged).
- **`TACTICAL_ADD_WARNING`**: short BUY + open core + post-FS-cap conviction &lt; 2 → CANCEL BUY (new).

### Claude agent dimensions (optional)

- [`src/conviction_engine/agent_dims.py`](../../src/conviction_engine/agent_dims.py): macro tailwind, CEO quality, competitive moat via Anthropic web search.
- **Off by default** on `full_recalculation`. Enable with:
  ```bash
  export ANTHROPIC_API_KEY=...
  export CONVICTION_RUN_AGENT_DIMS=1
  ```
- Semaphore limits concurrent agent calls (max 4).

### Overlay / API payload

- **`fd_direction`** added to `SignalModification` and daily overlay CSVs (after **Rebuild**).
- Existing overlay columns: `conviction_raw`, `valuation_tax`, `bq_raw`, `verdict`, `sizing_pct`, etc.

---

## Streamlit UI

File: [`src/pages/conviction_engine_page.py`](../../src/pages/conviction_engine_page.py)

### Ticker Detail

- **Financial strength** shows readable label (e.g. “Moderate low”) with `fs_class` in tooltip.
- **v6 scorecard** expander (default open): FD direction, FD sizing adj, P/E percentile, OEY, revenue accelerating, debt purpose, 15-row BQ table, FD votes table, valuation tax breakdown, optional macro agent JSON.
- **Yield trap diagnostics**: documents z **>** 1.5 and yield **≥** `yield_trap_mkt_threshold`.

### Signal Overlay

- Table prefers **`conviction_raw`**, **`valuation_tax`**, **`fd_direction`** when present in archived CSV ([`formatting.display_columns`](../../src/conviction_engine/formatting.py)).

**Note:** Overlays archived before this change lack `fd_direction` until you click **Rebuild** on a report date.

---

## Tests

- [`tests/test_conviction_engine.py`](../../tests/test_conviction_engine.py): `TestV6Scoring` (manual BQ mapping, debt purpose, FD votes majority, yield at threshold).
- **51** tests pass (`test_conviction_engine` + `test_api_conviction`).

---

## How to verify

### Refresh one ticker (full v6 fields)

```bash
cd /path/to/MindWealth_UI
.venv/bin/python -c "
from src.conviction_engine.engine import full_recalculation
r = full_recalculation('T.TO', overrides={'skip_agent_dims': True})
print('fd_direction', r.get('fd_direction'))
print('debt_purpose', r.get('debt_purpose'))
print('valuation_tax_breakdown', r.get('valuation_tax_breakdown'))
print('yield_trap', r.get('yield_trap_warning'))
"
```

### Daily overlay + UI

```bash
.venv/bin/python scripts/run_conviction_engine_daily.py --report-date YYYY-MM-DD
```

Open **Conviction Engine** in Streamlit → pick report date → **Rebuild** if needed → **Ticker Detail** / **Signal Overlay**.

### Yield trap CLI

```bash
.venv/bin/python scripts/verify_yield_trap.py T.TO
```

---

## Files touched (main)

| File | Role |
|------|------|
| `src/conviction_engine/bq_scoring.py` | Debt purpose, divergence, balance sheet v6 |
| `src/conviction_engine/fd_votes.py` | 5-vote FD |
| `src/conviction_engine/agent_dims.py` | Optional Claude web-search dims |
| `src/conviction_engine/scoring.py` | Valuation tax components, manual score mapping, yield trap `>=` |
| `src/conviction_engine/fundamentals_enriched.py` | BQ auto path, fundamentals extras |
| `src/conviction_engine/engine.py` | Wire FD, breakdown, warnings, agents |
| `src/conviction_engine/models.py` | Default record fields |
| `src/pages/conviction_engine_page.py` | v6 Streamlit scorecard |
| `src/conviction_engine/formatting.py` | Overlay column order |
| `docs/api/changelog.md` | API v1.1 conviction notes |
| `docs/api/services/conviction/*` | Endpoint / README updates |

---

## Not done (follow-up)

- Monthly cron + `check_earnings_triggers()` / `earnings_date` on store
- Macrotrends auto-fetch for thin US P/E history
- SEC EDGAR / SEDI insider; deal-delay and TAM agents
- `portfolio_store` and contradictions tab API (Parth frontend)
- `TACTICAL_ADD_WARNING` in `alert_map` / daily report text
- Full refresh of `conviction_engine_fundamentals.md` for v6 narrative
- Re-export `docs/api/openapi/mindwealth-v1.json`
- Universe-wide `--mode full` backfill after deploy

---

## Related prior work

Yield-trap calendar alignment and dividend 5Y stats (pre-v6): see **Yield trap — implementation** in [conviction_engine_fundamentals.md](../documentation/conviction_engine_fundamentals.md).
