# Portfolio Backend API Handoff

**Purpose:** Make the current Portfolio page fully backend-dependent. Frontend must not use mocks, fallback datasets, inferred values, or portfolio calculations.

**API prefix:** `/api/v1`  
**Reporting currency:** USD unless `currency` says otherwise  
**Dates/times:** ISO 8601  
**Percentages:** Return percentage values as human percentages (`12.5` means `12.5%`, not `0.125`)  
**Missing values:** Use `null`; do not send fabricated zeroes  
**Book IDs:** `model | brokerage | personal`  
**Model valuation books:** `base | ssi | cv | enhanced`

## 1. Required endpoints

| Priority | Method | Endpoint | Portfolio use |
|---|---|---|---|
| P0 | GET | `/portfolio/nav` | Overview, NAV chart, admission, attribution, contributions, risk snapshot |
| P0 | GET | `/portfolio/holdings` | Holdings table and actual P&L |
| P0 | GET | `/portfolio/sizer` | Model sizing/allocation and model P&L |
| P0 | GET | `/portfolio/risk` | Correlation matrix, breaches, cluster weights |
| P1 | GET | `/signals/entries` | New Entries pipeline |
| P1 | GET | `/signals/exits` | New Exits pipeline |
| P1 | GET | `/signals/reports/portfolio-risk/latest` | Cross-function exit conflicts |
| P1 | GET | `/portfolio/risk/search` | User-portfolio ticker search |
| P1 | POST | `/portfolio/risk/analyze` | User-entered portfolio analysis |

All paths above use the `/api/v1` prefix.

## 2. Global rules

1. `book_id` is required wherever listed. Data, caches, joins, and time series must remain isolated by book.
2. `book` is required when `book_id=model`.
3. `book` is ignored/optional for `book_id=personal` (no base/ssi/cv/enhanced concept there —
   §15). `book_id=brokerage` still returns 422 on every endpoint (§15 — Ask 3 deferred).
   `book_id=personal` is MODEL/Sizer/Risk-only rejected: only `/portfolio/nav` and
   `/portfolio/holdings` serve it (§14/§15).
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

---

## 3. `GET /api/v1/portfolio/nav`

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
  "mtm_daily": [
    {
      "date": "2026-07-18",
      "value": 102140000,
      "drawdown_pct": -0.4,
      "high_water_mark": 102550000
    }
  ],
  "closed": [],
  "closed_daily": [],
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

### Query

```text
book_id=model                         required
scenario=normal|stress|lowvol         required
```

If existing production behavior requires `manual|auto`, keep those modes backward-compatible, but the current Portfolio scenario UI requires `normal|stress|lowvol`.

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

---

## 8. `GET /api/v1/portfolio/risk`

### Query

```text
book_id=model                         required
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

### Query

```text
book_id=model|brokerage|personal   required
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

- [x] All nine endpoints return production data.
- [x] Every endpoint enforces book isolation.
- [x] MODEL supports all four valuation books on NAV (real per-book series, §15). Holdings/sizer
      live snapshot remains `enhanced`-only (D1 four-book live sizing still pending SLEEVES/N sign-off).
- [x] MODEL supports normal, stress, low-volatility, **and now auto/manual** scenarios (§15).
- [ ] Brokerage NAV, holdings, prices, shares, market value, and P&L come from IBKR. (Deferred — Ask 3, §15)
- [x] Personal holdings come from persisted backend data (§14/§15).
- [x] No response contains demonstration/sample values in production.
- [x] No required numeric field is replaced with `0` when unavailable (uses `null` + `data_status`/notes).
- [x] Sizer allocations reconcile with summary and cluster caps.
- [x] Risk matrix passes shape/range validation.
- [x] Same-asset, MULTI-SIG, contribution, admission, and conflict fields are backend-generated.
- [ ] Frontend can disable legacy Portfolio fallback and mock mode without losing any displayed data. (Frontend wiring — Parth)

## 14. Not required by current UI

Personal holding create/update/delete APIs are not called by the current Portfolio page. They will be needed before Personal becomes editable:

```text
POST   /api/v1/portfolio/personal/holdings
PATCH  /api/v1/portfolio/personal/holdings/{id}
DELETE /api/v1/portfolio/personal/holdings/{id}
```

Authentication, ownership, validation, and audit-history rules must be agreed before implementing these writes.

**Status (2026-07-22): implemented.** Section 14's own suggestion shipped as `POST`/`GET`/`DELETE
/api/v1/portfolio/personal/holdings` (upsert-by-ticker, not `{id}`-keyed — one lot per ticker)
plus `PUT /api/v1/portfolio/personal/cash`. `book_id=personal` on `/portfolio/nav` and
`/portfolio/holdings` now returns real data instead of 422 — see §15 below. No per-user
ownership/auth layer beyond the existing API key — single-tenant JSON store
(`config/personal_holdings.json`, gitignored), matches Rohit's own single-user use case.

---

## 15. Implementation status update — 2026-07-22 (Portfolio Backend Remaining Build)

Everything below is **live on `chatbot-dev`**, on top of the nine required endpoints above:

| Area | What shipped | Notes |
|------|---------------|-------|
| **Config layer** | `config/portfolio_policy.yaml` + `api/services/policy_service.py` | All five open Rohit decisions (notional, N, rebalance mode, eviction margin/freeze, sleeves) in one file, `status: interim\|confirmed` tagged |
| **Book-state history** | `scripts/run_portfolio_book_snapshot_daily.py` (cron) + `src/portfolio_nav/book_snapshot_store.py` | Captures per-position book state, regime bucket, and eviction decisions daily from first run forward — no backfill |
| **D1 slot sizing** | `api/services/sizing_engine.py`, behind `SIZING_ENGINE_VERSION=d1_slots` | NAV/N admission slots per sleeve; legacy % engine remains default until SLEEVES/N confirmed (Ask 1/4) |
| **Eviction engine (1C/A2/A3)** | `src/portfolio_nav/eviction_engine.py` | `exit_type=eviction` now populated on `/signals/exits` |
| **Axiom 2 rebalancing** | `rebalance_mode` param on `run_nav_engine()`, default `hold_original` from policy | Resolves §9's open Axiom 2 question — API follows the resolved research direction |
| **Four-book replay (A1)** | `src/portfolio_nav/four_book_engine.py` | `/portfolio/nav?book=base\|ssi\|cv\|enhanced` now real per-book series, not proxy; `cv`/`enhanced` limited to the conviction archive's window, disclosed via `data_status` |
| **AUTO/MANUAL scenarios** | `scenario=auto\|manual` on sizer/sizing/risk/nav/holdings | `auto` = real regime pick; `manual` = persisted user $ overrides via `/portfolio/sizing/manual-overrides` |
| **Alerts** | `GET /portfolio/alerts` | Correlation breaches, cross-function conflicts, DRIFT, negative R:R uncovered, evictions |
| **Regime history** | `GET /portfolio/regime-history` | From the book-snapshot store; empty until the daily job has run |
| **Personal book** | §14 endpoints + `book_id=personal` on nav/holdings | Live snapshot only — no historical NAV series (disclosed via `data_status`) |
| **Brokerage** | **No change** — still 422 everywhere | Explicitly deferred; blocked on Ask 3 (owner, IBKR API type, credentials) |

See `docs/mindwealth-api-docs/services/portfolio/` for full endpoint contracts and
`docs/mindwealth-api-docs/changelog.md` (v1.9.0) for the complete change list.
