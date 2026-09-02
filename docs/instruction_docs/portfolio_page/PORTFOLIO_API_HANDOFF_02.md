# Portfolio Backend API Handoff

**Purpose:** Make the current Portfolio page fully backend-dependent. Frontend must not use mocks, fallback datasets, inferred values, or portfolio calculations.

**API prefix:** `/api/v1`  
**Reporting currency:** USD unless `currency` says otherwise  
**Dates/times:** ISO 8601  
**Percentages:** Return percentage values as human percentages (`12.5` means `12.5%`, not `0.125`)  
**Missing values:** Use `null`; do not send fabricated zeroes  
**Book IDs:** `model | brokerage | personal`  
**Model valuation books:** `base | ssi | cv | enhanced`  
**Verified against live API:** `2026-07-22` (`NUXT_API_BASE_URL`)

---

## 0. Current fetch status — what frontend cannot get

Pass this section to backend first. These are the gaps blocking a complete Portfolio page.

### 0.1 Endpoints returning HTTP 404 (not implemented / not routed)

| Method | Endpoint | Example call | Blocks |
|---|---|---|---|
| GET | `/api/v1/portfolio/nav` | `?book_id=model&book=enhanced` | Portfolio **Overview** (NAV, chart, admission, attribution, contributions, risk snapshot, waterfall) |
| GET | `/api/v1/portfolio/nav` | `?book_id=brokerage` | Brokerage Overview |
| GET | `/api/v1/portfolio/nav` | `?book_id=personal` | Personal Overview |
| GET | `/api/v1/portfolio/holdings` | `?book_id=model&book=enhanced` | Overview holdings table |
| GET | `/api/v1/portfolio/holdings` | `?book_id=brokerage` | Brokerage Live P&L + holdings |
| GET | `/api/v1/portfolio/holdings` | `?book_id=personal` | Personal Live P&L + holdings |
| GET | `/api/v1/signals/entries` | `?book_id=model` | Overview pipeline **NEW ENTRIES** |
| GET | `/api/v1/signals/exits` | `?book_id=model` | Overview pipeline **NEW EXITS** |

Frontend shows “waiting for backend” / empty states for these. No mock or derived fill-in.

### 0.2 Live endpoints with missing fields

| Endpoint | Status | Missing / incomplete for UI |
|---|---|---|
| `GET /portfolio/sizer` | **200 live** | `pnl_rows[]` and cluster `positions[]` do not currently return `cross_function_exit`, `asset_class`, or `status`. UI needs these for cross-fn badges and P&L status. |
| `GET /portfolio/risk` | **200 live** | `conviction_summary` is not returned (`max_count`, `tactical_count`, `reduced_count`, `yield_trap_count`, `max_names`, `yield_trap_names`). Risk conviction panel stays `—`. Some breaches have `recommendation: null` (prefer a string or explicit `null` is OK, but action text is blank). |
| `GET /signals/reports/portfolio-risk/latest` | **200 live** | `open_positions[].implied_natural_exit_date` never present. Optional `book_id` query should be honored for book isolation. |
| `GET /portfolio/risk/search` | **200 live** | OK for current UI |
| `POST /portfolio/risk/analyze` | **200 live** | OK for current UI (`name` on positions is returned) |

### 0.3 What already works (frontend wired, pass-through only)

| Endpoint | Notes |
|---|---|
| `GET /portfolio/sizer?scenario=normal\|stress\|lowvol` | Ceiling, summary, clusters, allocations, pnl_rows, constraints, combos, macro_override. Scenarios `manual`/`auto` are **rejected by API** (`^(normal\|stress\|lowvol)$`) — UI only offers those three. |
| `GET /portfolio/risk?scenario=…` | Matrix, labels, breaches, cluster_weights, correlation_meta (incl. `age_days`) |
| `GET /portfolio/risk/search?q=` | Ticker typeahead |
| `POST /portfolio/risk/analyze` | User holdings analysis |
| `GET /signals/reports/portfolio-risk/latest` | Cross-function conflicts panel (minus `implied_natural_exit_date`) |

### 0.4 Backend priority to unblock Overview + brokerage/personal

1. **P0** Ship `GET /portfolio/nav` for `model` (+ `book`), `brokerage`, `personal` — full contract in §3.
2. **P0** Ship `GET /portfolio/holdings` for all three books — full contract in §4.
3. **P1** Ship `GET /signals/entries` and `GET /signals/exits` with required `book_id` — §5–6.
4. **P1** Add sizer fields `cross_function_exit`, `asset_class`, `status` on `pnl_rows` / positions.
5. **P1** Add `conviction_summary` on `GET /portfolio/risk`.
6. **P1** Add `implied_natural_exit_date` on conflict open legs; honor `book_id` on portfolio-risk report.

---

## 1. Required endpoints

| Priority | Method | Endpoint | Portfolio use | Live status (2026-07-22) |
|---|---|---|---|---|
| P0 | GET | `/portfolio/nav` | Overview, NAV chart, admission, attribution, contributions, risk snapshot | **404 — blocked** |
| P0 | GET | `/portfolio/holdings` | Holdings table and actual P&L | **404 — blocked** |
| P0 | GET | `/portfolio/sizer` | Model sizing/allocation and model P&L | **200 — wired** (field gaps in §0.2) |
| P0 | GET | `/portfolio/risk` | Correlation matrix, breaches, cluster weights | **200 — wired** (`conviction_summary` missing) |
| P1 | GET | `/signals/entries` | New Entries pipeline | **404 — blocked** |
| P1 | GET | `/signals/exits` | New Exits pipeline | **404 — blocked** |
| P1 | GET | `/signals/reports/portfolio-risk/latest` | Cross-function exit conflicts | **200 — wired** (`implied_natural_exit_date` missing) |
| P1 | GET | `/portfolio/risk/search` | User-portfolio ticker search | **200 — wired** |
| P1 | POST | `/portfolio/risk/analyze` | User-entered portfolio analysis | **200 — wired** |

All paths above use the `/api/v1` prefix.

## 2. Global rules

1. `book_id` is required wherever listed. Data, caches, joins, and time series must remain isolated by book.
2. `book` is required when `book_id=model`.
3. Reject `book` for `book_id=brokerage|personal`.
4. Brokerage values must come from IBKR/backend source of truth.
5. Personal values must come from persisted backend holdings.
6. Backend owns all sizing, ranking, score, attribution, P&L, FX conversion, exposure, risk, contribution, and summary calculations.
7. Frontend only formats and displays returned values.
8. Return empty arrays for valid requests with no rows. Return an error for unavailable/failed data; do not substitute sample data.
9. Recommended errors:
   - `400` invalid query/body
   - `401/403` unauthorized
   - `404` requested book or generated portfolio result not found
   - `422` valid request but unsupported book/scenario combination
   - `500/503` calculation or upstream data unavailable
10. Scenario query for sizer/risk must match `^(normal|stress|lowvol)$`. Do not advertise `manual`/`auto` unless those modes are implemented end-to-end.

---

## 3. `GET /api/v1/portfolio/nav`

> **Status: 404 on live API — Overview cannot load.** Implement this contract.

### Query

```text
book_id=model|brokerage|personal   required
book=base|ssi|cv|enhanced         required only for model
```

### Response

```json
{
  "book_id": "model",
  "book": "enhanced",
  "as_of": "2026-07-19T16:00:00Z",
  "currency": "USD",
  "nav": 102450000,
  "day_mtm_usd": 310000,
  "day_mtm_pct": 0.3,
  "since_go_live_pct": 8.4,
  "position_count": 18,
  "position_limit": 24,
  "deployed_pct": 71.2,
  "cash_pct": 28.8,
  "long_count": 14,
  "short_count": 4,
  "net_exposure_pct": 48.1,
  "gross_exposure_pct": 71.2,
  "realized_vol_pct": 11.8,
  "beta_sp500": 0.72,
  "best_month_pct": 4.1,
  "worst_month_pct": -2.8,
  "mtm": [
    {
      "date": "2026-07-18",
      "value": 102140000,
      "drawdown_pct": -0.4,
      "high_water_mark": 102550000
    }
  ],
  "closed": [],
  "base_mtm": [],
  "base_closed": [],
  "benchmark": [],
  "monthly_returns": [
    { "month": "2026-07", "return_pct": 1.2 }
  ],
  "attribution": [
    {
      "id": "base",
      "label": "BASE",
      "return_pct": 5.4,
      "description": "Base model contribution"
    }
  ],
  "waterfall_steps": [
    { "label": "Regime ceiling", "value": "80%", "tone": "default" },
    { "label": "SSI multiplier", "value": "0.90×", "tone": "amber" },
    { "label": "Final ceiling", "value": "72%", "tone": "gold", "final": true }
  ],
  "ceiling_marker_pct": 72,
  "stance": {
    "label": "CAUTIOUSLY DEPLOYED",
    "detail": "Credit haircut active"
  },
  "conviction_summary": {
    "max_count": 4,
    "tactical_count": 8,
    "reduced_count": 5,
    "yield_trap_count": 1,
    "max_names": ["SPY", "NVDA"],
    "yield_trap_names": ["XYZ"]
  },
  "risk_chips": [
    {
      "id": "correlation-breach",
      "icon": "⚠",
      "title": "Correlation breach",
      "body": "Global risk-on and semiconductors exceed correlation cap.",
      "target_view": "risk",
      "action_label": "VIEW RISK"
    }
  ],
  "top_contributors": [
    {
      "ticker": "NVDA",
      "function": "FractalTrack",
      "interval": "Weekly",
      "pnl_contribution_bps": 42
    }
  ],
  "top_detractors": [],
  "next_in": {
    "ticker": "MSFT",
    "function": "FractalTrack",
    "interval": "Weekly",
    "direction": "Long",
    "signal_or_entry_date": "2026-07-19",
    "score": 8.7,
    "forward_win_rate_pct": 68.2,
    "er_alpha_pct": 2.1,
    "rr_dynamic": 2.4,
    "hold_time_used_pct": 0,
    "detail": "Highest-ranked eligible candidate"
  },
  "next_out": null,
  "eviction_margin": 1.3,
  "eviction_margin_note": "Challenger score minus weakest holding score"
}
```

### Rules

- `mtm`, `closed`, `benchmark`, and optional base series points use `{ date, value, drawdown_pct, high_water_mark }`.
- `base_mtm`, `base_closed`, and `attribution` apply only to MODEL.
- `monthly_returns` must be backend-generated.
- `top_contributors` and `top_detractors` must be pre-ranked by backend. Do not expect frontend to derive Top 5 from holdings.
- `next_in`, `next_out`, and `eviction_margin` must be backend-ranked/calculated.
- Brokerage NAV, holdings value, prices, and P&L must match IBKR.

---

## 4. `GET /api/v1/portfolio/holdings`

> **Status: 404 on live API — Overview holdings + brokerage/personal P&L cannot load.**

### Query

Same query rules as `/portfolio/nav`.

### Response

```json
{
  "book_id": "model",
  "book": "enhanced",
  "as_of": "2026-07-19T16:00:00Z",
  "holdings": [
    {
      "id": "model-nvda-fractal-weekly",
      "ticker": "NVDA",
      "name": "NVIDIA Corporation",
      "function": "FractalTrack",
      "interval": "Weekly",
      "direction": "Long",
      "entry_date": "2026-06-12",
      "entry_price": 145.2,
      "current_price": 151.8,
      "entry_currency": "USD",
      "shares": 40000,
      "market_value": 6072000,
      "pnl_usd": 264000,
      "mtm_pct": 4.55,
      "score": 8.8,
      "rank": 1,
      "rr_dynamic": 2.3,
      "hold_time_used_pct": 35,
      "size_usd": 5808000,
      "conviction_tier": "MAX",
      "sleeve": "Semiconductors",
      "pnl_contribution_bps": 26,
      "same_asset_siblings": [
        {
          "symbol": "NVDA",
          "function": "Momentum",
          "interval": "Daily",
          "direction": "Long",
          "signal_date": "2026-07-19",
          "relationship": "new_signal",
          "forward_win_rate_pct": 64.5
        }
      ],
      "multi_sig": [
        {
          "function": "Momentum",
          "interval": "Daily",
          "direction": "Long",
          "signal_date": "2026-07-19",
          "forward_win_rate_pct": 64.5
        }
      ],
      "exit_ref": "Nearest natural exit: Momentum Daily",
      "cross_function_exit": false,
      "asset_class": "Equity",
      "status": "Open",
      "backtested_win_rate_pct": 67.4,
      "next_out": false
    }
  ]
}
```

### Rules

- `size_usd` must exactly match the corresponding position from `/portfolio/sizer`.
- Return actual `shares`, `market_value`, and `pnl_usd`; frontend will not calculate them.
- `same_asset_siblings` must include both `new_signal` and `already_held` relationships where applicable.
- MULTI-SIG is informational only. Do not apply an unapproved sizing/ranking boost.
- `cross_function_exit=true` must be propagated to surviving affected legs.

---

## 5. `GET /api/v1/signals/entries`

> **Status: 404 on live API — Overview NEW ENTRIES pipeline empty.**

### Query

```text
book_id=model|brokerage|personal   required
```

### Response

```json
{
  "book_id": "model",
  "as_of": "2026-07-19T16:00:00Z",
  "entries": [
    {
      "id": "entry-msft-fractal-weekly-2026-07-19",
      "ticker": "MSFT",
      "function": "FractalTrack",
      "interval": "Weekly",
      "direction": "Long",
      "signal_date": "2026-07-19",
      "score": 8.7,
      "rank": 1,
      "forward_win_rate_pct": 68.2,
      "detail": "Eligible for model admission"
    }
  ]
}
```

This must be the same source-of-truth feed used by Signals → New Entries.

---

## 6. `GET /api/v1/signals/exits`

> **Status: 404 on live API — Overview NEW EXITS pipeline empty.**

### Query

```text
book_id=model|brokerage|personal   required
```

### Response

```json
{
  "book_id": "model",
  "as_of": "2026-07-19T16:00:00Z",
  "exits": [
    {
      "id": "exit-xyz-momentum-daily-2026-07-19",
      "ticker": "XYZ",
      "function": "Momentum",
      "interval": "Daily",
      "direction": "Long",
      "signal_date": "2026-05-11",
      "score": 1.8,
      "rank": 18,
      "forward_win_rate_pct": 43.1,
      "detail": "Risk/reward exit triggered",
      "exit_type": "rr",
      "exit_price": 42.6,
      "closed_pnl_pct": -6.4,
      "conflict": true
    }
  ]
}
```

`exit_type` values: `signal | rr | eviction`.

---

## 7. `GET /api/v1/portfolio/sizer`

MODEL-only endpoint. This endpoint replaces all frontend/BFF sizing fallbacks.

> **Status: 200 live — wired.** Still missing on `pnl_rows[]` / cluster `positions[]`:
> `cross_function_exit`, `asset_class`, `status`.
> Scenario must be `normal|stress|lowvol` only.

### Query

```text
book_id=model                         recommended
scenario=normal|stress|lowvol         required
```

`manual` and `auto` are currently rejected by the live API validation pattern. Do not send them unless backend adds those modes.

### Response

```json
{
  "date": "2026-07-19",
  "as_of": "2026-07-19T16:00:00Z",
  "scenario": "normal",
  "scenarios_available": true,
  "ceiling": {
    "vix": 16.4,
    "vix_pct": 40,
    "vix_regime": "NORMAL",
    "val_regime": "EXTREME",
    "geo_overlay": "NEUTRAL",
    "regime_max_pct": 80,
    "ssi_multiplier": 1,
    "vix_level_mult": 1,
    "spx_trend_mult": 1,
    "spx_trend_meta": {
      "source": "market_data",
      "symbol": "SPX",
      "spx_price": 6900,
      "spx_ma200": 6500,
      "above_ma200": true
    },
    "hy_credit_mult": 0.9,
    "final_ceiling_pct": 72,
    "formula_text": "80% regime max × 1.00 VIX × 1.00 trend × 0.90 HY credit",
    "note": "HY credit haircut active.",
    "portfolio_notional": 100000000,
    "idle_cash_yield_pct": 3.5,
    "steps": [
      { "label": "Regime maximum", "value": "80%" },
      { "label": "HY credit", "value": "0.90×", "tone": "amber" }
    ]
  },
  "summary": {
    "deployed_usd": 72000000,
    "deployed_pct": 72,
    "cash_usd": 28000000,
    "cash_pct": 28,
    "idle_income_usd": 980000,
    "open_position_count": 18
  },
  "clusters": [
    {
      "id": "semiconductors",
      "label": "Semiconductors",
      "budget_usd": 15000000,
      "budget_pct": 15,
      "deployed_usd": 12000000,
      "deployed_pct": 12,
      "max_pct": 15,
      "positions": [
        {
          "ticker": "NVDA",
          "name": "NVIDIA Corporation",
          "investment_type": "Semiconductors",
          "cluster_id": "semiconductors",
          "function": "FractalTrack",
          "interval": "Weekly",
          "direction": "Long",
          "bq_score": 8.8,
          "size_tier": "MAX 100%",
          "allocation_usd": 5808000,
          "allocation_pct": 5.81,
          "flags": [],
          "blocked": false,
          "blocked_reason": null,
          "win_rate": 64.5,
          "win_rate_label": "Forward WR",
          "backtested_win_rate_pct": 67.4,
          "unscored": false
        }
      ]
    }
  ],
  "pnl_rows": [
    {
      "ticker": "NVDA",
      "name": "NVIDIA Corporation",
      "investment_type": "Semiconductors",
      "function": "FractalTrack",
      "interval": "Weekly",
      "direction": "Long",
      "entry_price": 145.2,
      "current_price": 151.8,
      "shares": 40000,
      "market_value": 6072000,
      "pnl_usd": 264000,
      "pnl_pct": 4.55,
      "bq_score": 8.8,
      "size_tier": "MAX 100%",
      "flags": [],
      "status": "Open",
      "blocked": false,
      "blocked_reason": null,
      "backtested_win_rate_pct": 67.4,
      "cross_function_exit": false,
      "asset_class": "Equity"
    }
  ],
  "constraints": [
    {
      "level": "ok",
      "title": "Cluster caps",
      "body": "All clusters are within budget."
    }
  ],
  "active_combos": [
    {
      "id": "C",
      "label": "COMBO C wk 11",
      "detail": "Entry haircut active"
    }
  ],
  "macro_override": {
    "active": true,
    "reasons": ["Valuation regime: EXTREME"]
  },
  "risk": {
    "available": true,
    "message": "Use /api/v1/portfolio/risk for full matrix."
  }
}
```

### Rules

- Backend must return final allocations. Frontend must never cap, scale, split, or normalize allocations.
- Sum of active `allocation_usd` must equal `summary.deployed_usd` within documented rounding tolerance.
- Every cluster must satisfy its budget and maximum.
- `cash_usd + deployed_usd` must equal `portfolio_notional`.
- Scenario changes must return scenario-specific ceiling, summary, cluster budgets, and allocations.
- `pnl_rows` must contain actual prices, shares, market value, and P&L.
- Flags and blocking decisions are backend-authored.
- **Gap today:** each `pnl_rows[]` / position should also include:
  - `cross_function_exit` (boolean)
  - `asset_class` (string, e.g. `Equity` / `Commodity`)
  - `status` (string, e.g. `Open`)
  These are currently absent on the live sizer payload.

---

## 8. `GET /api/v1/portfolio/risk`

> **Status: 200 live — wired.** Missing: `conviction_summary` object (counts + name lists). Risk conviction panel shows `—` until this ships.

### Query

```text
book_id=model                         recommended
scenario=normal|stress|lowvol         required
```

### Response

```json
{
  "date": "2026-07-19",
  "scenario": "normal",
  "labels": ["global_risk_on", "semiconductors", "bonds"],
  "matrix": [
    [1, 0.87, -0.31],
    [0.87, 1, -0.22],
    [-0.31, -0.22, 1]
  ],
  "correlation_meta": {
    "source": "daily_returns",
    "as_of": "2026-07-18",
    "proxies": {
      "global_risk_on": "SPY",
      "semiconductors": "SOXX",
      "bonds": "TLT"
    },
    "window_days": 252
  },
  "breaches": [
    {
      "pair": ["global_risk_on", "semiconductors"],
      "pair_labels": ["Global risk-on", "Semiconductors"],
      "rho": 0.87,
      "level": "action",
      "combined_weight_pct": 30,
      "combined_weight_usd": 30000000,
      "cap_pct": 20,
      "recommendation": "Reduce combined exposure by $10M."
    }
  ],
  "breach_threshold_watch": 0.75,
  "breach_threshold_action": 0.85,
  "cluster_weights": [
    {
      "cluster_id": "semiconductors",
      "label": "Semiconductors",
      "deployed_pct": 12,
      "max_pct": 15
    }
  ],
  "conviction_summary": {
    "max_count": 4,
    "tactical_count": 8,
    "reduced_count": 5,
    "yield_trap_count": 1,
    "max_names": ["SPY", "NVDA"],
    "yield_trap_names": ["XYZ"]
  }
}
```

### Rules

- Matrix must be square and match `labels.length`.
- Diagonal must be `1`.
- Matrix values must be in `[-1, 1]`.
- Each breach pair must reference IDs in `labels`.
- `cluster_weights` must match the selected sizer scenario.
- **Gap today:** include `conviction_summary` on every risk response:
  ```json
  "conviction_summary": {
    "max_count": 4,
    "tactical_count": 8,
    "reduced_count": 5,
    "yield_trap_count": 1,
    "max_names": ["SPY", "NVDA"],
    "yield_trap_names": ["XYZ"]
  }
  ```
- Prefer non-null `recommendation` strings on action-level breaches when a trim action exists.

---

## 9. `GET /api/v1/portfolio/risk/search`

### Query

```text
q=NVDA      required, non-empty
limit=20    optional, 1–100
```

### Response

```json
[
  {
    "symbol": "NVDA",
    "name": "NVIDIA Corporation",
    "source": "conviction_universe"
  }
]
```

Allowed `source`: `vt_book | conviction_universe | conviction_store`.

---

## 10. `POST /api/v1/portfolio/risk/analyze`

### Request

```json
{
  "holdings": [
    { "symbol": "SPY", "quantity": 120 },
    { "symbol": "QQQ", "quantity": 85 }
  ],
  "cash_usd": 38293
}
```

### Response

```json
{
  "total_notional_usd": 102500,
  "cash_usd": 38293,
  "position_count": 2,
  "positions": [
    {
      "symbol": "SPY",
      "quantity": 120,
      "live_price": 620,
      "notional_usd": 74400,
      "cluster_id": "global_risk_on",
      "cluster_label": "Global risk-on"
    }
  ],
  "cluster_weights": [
    { "cluster_id": "global_risk_on", "pct": 72.6 }
  ],
  "concentration_warnings": [
    {
      "cluster_id": "global_risk_on",
      "label": "Global risk-on",
      "user_pct": 72.6,
      "model_max_pct": 18,
      "action": "Reduce global risk-on concentration."
    }
  ],
  "correlation_breaches": [
    {
      "pair": ["global_risk_on", "semiconductors"],
      "pair_labels": ["Global risk-on", "Semiconductors"],
      "rho": 0.87,
      "user_combined_pct": 88,
      "recommendation": "Reduce combined correlated exposure."
    }
  ]
}
```

Backend must resolve live prices, notionals, clusters, weights, warnings, and recommendations.

---

## 11. `GET /api/v1/signals/reports/portfolio-risk/latest`

> **Status: 200 live — wired.** Missing on every `open_positions[]` row: `implied_natural_exit_date`.
> Please honor optional `book_id` so conflicts stay book-isolated.

### Query

```text
book_id=model|brokerage|personal   required for book isolation
```

### Response

```json
{
  "report_date": "2026-07-19",
  "cross_function_conflict_count": 1,
  "cross_function_conflicts": [
    {
      "symbol": "CL",
      "direction": "Long",
      "asset_class": "Commodity",
      "conflict": true,
      "triggering_exits": [
        {
          "function": "Momentum",
          "interval": "Daily",
          "exit_date": "2026-07-19",
          "exit_price": 68.4
        }
      ],
      "open_positions": [
        {
          "function": "FractalTrack",
          "interval": "Weekly",
          "mtm_pct": 4.8,
          "signal_date": "2026-06-03",
          "implied_natural_exit_date": "2026-08-12"
        }
      ]
    }
  ]
}
```

The backend must calculate `implied_natural_exit_date`; frontend will not estimate it.

---

## 12. Data consistency requirements

For identical `book_id`, valuation `book`, scenario, and `as_of`:

1. `/portfolio/nav.position_count` must match open `/portfolio/holdings` count.
2. `/portfolio/nav.deployed_pct` must match `/portfolio/sizer.summary.deployed_pct` for MODEL.
3. `/portfolio/holdings[].size_usd` must match `/portfolio/sizer.clusters[].positions[].allocation_usd`.
4. Holdings prices/P&L and sizer `pnl_rows` must agree.
5. `/portfolio/nav.top_contributors` and `top_detractors` must reconcile with holding contribution data.
6. `/portfolio/risk.cluster_weights` must agree with sizer cluster deployment.
7. Entries/exits must use the same feed as the Signals page.
8. Every response should expose an `as_of` or `date` identifying data freshness.

## 13. Definition of done

### Still open (cannot fetch today)

- [ ] `GET /portfolio/nav` returns 200 for model (+ `book`), brokerage, personal
- [ ] `GET /portfolio/holdings` returns 200 for model (+ `book`), brokerage, personal
- [ ] `GET /signals/entries?book_id=` returns 200
- [ ] `GET /signals/exits?book_id=` returns 200
- [ ] Sizer `pnl_rows` / positions include `cross_function_exit`, `asset_class`, `status`
- [ ] Risk response includes `conviction_summary`
- [ ] Conflict open legs include `implied_natural_exit_date`; report honors `book_id`
- [ ] Every endpoint enforces book isolation
- [ ] Brokerage NAV/holdings/prices/shares/MV/P&L come from IBKR
- [ ] Personal holdings come from persisted backend data

### Already satisfied on live API (frontend pass-through)

- [x] `GET /portfolio/sizer` for `normal|stress|lowvol` with ceiling/summary/clusters/pnl_rows
- [x] `GET /portfolio/risk` matrix, breaches, cluster_weights, correlation_meta
- [x] `GET /portfolio/risk/search`
- [x] `POST /portfolio/risk/analyze`
- [x] `GET /signals/reports/portfolio-risk/latest` conflict list (partial fields)
- [x] Frontend does not mock or invent portfolio numbers when APIs are missing

### Full acceptance (after gaps close)

- [ ] No response contains demonstration/sample values in production
- [ ] No required numeric field is replaced with `0` when unavailable
- [ ] Sizer allocations reconcile with summary and cluster caps
- [ ] Risk matrix passes shape/range validation
- [ ] Same-asset, MULTI-SIG, contribution, admission, and conflict fields are backend-generated
- [ ] Frontend can disable legacy Portfolio fallback and mock mode without losing any displayed data

## 14. Not required by current UI

Personal holding create/update/delete APIs are not called by the current Portfolio page. They will be needed before Personal becomes editable:

```text
POST   /api/v1/portfolio/personal/holdings
PATCH  /api/v1/portfolio/personal/holdings/{id}
DELETE /api/v1/portfolio/personal/holdings/{id}
```

Authentication, ownership, validation, and audit-history rules must be agreed before implementing these writes.
