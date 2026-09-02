# Fundamental Agent Update — July 2026 — Implementation Status

**Doc source:** `Fundamental Agent Update July 2026.pdf`  
**Completed:** 2026-07-22  
**Branch:** `chatbot-dev` (`/home/ubuntu/uiv2/git/MindWealth_UI`)

---

## Executive summary

All **P1 data/formula bugs** and **P2 missing BQ dimensions** from the July 2026 spec are implemented in the conviction engine. **P3 M&A persistence** is implemented (SQLite aux DB + weekly cron). **Section 6 UI wiring** remains deferred to Parth (Nuxt `MindwealthUI_Vue`).

**58 tests passing** (`test_conviction_engine` + `test_api_conviction`).

---

## P1 — Data & system bugs

| Item | Status | Notes |
|------|--------|-------|
| PE manual EPS cascade | **DONE** | `fundamentals_enriched.build_fundamentals_from_raw` — `trailingEps` → net income TTM / shares |
| Missing PE → neutral tax | **DONE** | `daily_update` nulls `pe_ttm`/`pe_percentile_20y` when EPS ≤ 0; no −2 worst-case penalty |
| FCF / OEY three-tier cascade | **DONE** | Annual `freeCashflow` → TTM cashflow sum → OCF − \|capex\| |
| Divergence `days_below_high` | **DONE** | `divergence_state` in conviction_store; bootstrap from price history on first full recalc |
| Divergence logging | **DONE** | `[divergence] {ticker}: price=…` in `src/conviction_engine/divergence.py` |

### PYPL verification (2026-07-22)

| Field | Before (buggy) | After fix |
|-------|----------------|-----------|
| `pe_ttm` | 0× | **10.48×** |
| `owner_earnings_yield` | 0% | **11.3%** |
| PE percentile tax | −2 | **0** (neutral) |
| `bq_raw` | ~+1 path | **+8.0** |
| `conviction_score` | +1 | **+7.0** |
| Divergence signal | 0 | **+2** (`days_below_high` bootstrapped 259) |
| Capital allocation | 0 | **+2** (7.1% float reduction) |
| Verdict (BUY long) | CANCEL BUY 0% | **TACTICAL BUY 75%** (score 7; MAX at ≥8) |

---

## P2 — Missing BQ dimensions & FD votes

| Dim | Status | Implementation |
|-----|--------|----------------|
| 8 CEO Quality | **DONE** | `ceo_quality.py` — TSR vs SPY; &lt;12mo tenure → −1 mechanical penalty |
| 9 Capital Allocation | **DONE** | `capital_allocation.py` — buyback % from quarterly shares |
| 10 Competitive Moat | **DONE** | Adversarial agent prompt in `agent_dims.py` (confidence &lt;0.7 → 0) |
| 11 Macro Tailwind | **DONE** | Existing agent + confidence rules |
| 15 Reinvestment Runway | **DONE** | TAM agent; `_score_reinvestment` threshold **&gt;10×** |
| 5 FD votes | **DONE** | `fd_votes.py` — revenue YoY accel, FCF YoY, buybacks, EPS revision store |
| FD sizing | **DONE** | Tier sizing in `verdict_for_buy` only; removed double `fd_sizing_adj` multiplier |

**Agent dimensions:** off by default. Enable: `CONVICTION_RUN_AGENT_DIMS=1` + `ANTHROPIC_API_KEY`.

---

## P3 — M&A feature flag

| Item | Status | Path |
|------|--------|------|
| `ma_activity` schema | **DONE** | `src/conviction_engine/db/schema.sql` (SQLite `conviction_aux.db`) |
| Weekly cron | **DONE** | `scripts/run_ma_activity_weekly.py` |
| conviction_store flags | **DONE** | `m_and_a_activity`, `m_and_a_bid_price`, `m_and_a_note` |
| Agent search | **DONE** | `ma_activity.py` (confidence ≥0.7) |

**Note:** Spec asked for PostgreSQL; repo uses SQLite for macro/SSI — same pattern here. Prod can mirror DDL to Postgres if required.

---

## P4 — UI (Parth)

| Item | Status |
|------|--------|
| Drawer "Full FS view →" → `/fs-depth` | **DEFERRED** — Nuxt repo |
| Signal row "BQ drill" → drawer BQ tab | **DEFERRED** |
| Signal row "FS page →" → `/fs` | **DEFERRED** |
| 15 BQ sub-components in store | **DONE** — `bq_components` always persisted |

---

## API & docs

| Area | Status |
|------|--------|
| `POST /conviction/tickers/{ticker}/recalculate` | **UPDATED** — full enriched fetch via `update_ticker_fundamentals` |
| `GET /conviction/tickers/{ticker}` | New fields: `days_below_high`, `divergence_state`, `m_and_a_*` |
| API docs | **UPDATED** — `docs/api/services/conviction/README.md`, `get-ticker.md`, `recalculate-ticker.md` |

---

## Audit assets

| Ticker | PE TTM | OEY | BQ raw | Conviction | Nonzero BQ dims |
|--------|--------|-----|--------|------------|-----------------|
| **PYPL** | 10.48 | 11.3% | 8.0 | 7.0 | 7 |
| **MSFT** | 23.70 | 2.6% | 4.5 | −0.5 | 6 |
| **KXS.TO** | 36.06 | 2.5% | 5.5 | 0.5 | 8 |

Canadian path (`KXS.TO`) pulls and computes without errors.

---

## Key files changed

- `src/conviction_engine/engine.py` — auto-fetch fundamentals, divergence, PE neutral, FD sizing fix
- `src/conviction_engine/fundamentals_enriched.py` — PE/FCF cascades, revenue YoY accel, shares TTM
- `src/conviction_engine/divergence.py` — **new**
- `src/conviction_engine/ceo_quality.py` — **new**
- `src/conviction_engine/capital_allocation.py` — **new**
- `src/conviction_engine/ma_activity.py` — **new**
- `src/conviction_engine/db/` — **new**
- `src/conviction_engine/agent_dims.py` — moat/reinvestment agents
- `src/conviction_engine/fd_votes.py`, `scoring.py`, `bq_scoring.py`
- `api/services/conviction_service.py`
- `tests/test_conviction_engine.py` — `TestJuly2026FundamentalUpdates`
- `scripts/run_ma_activity_weekly.py` — **new**

---

## Ops commands

```bash
# Full recalc one ticker
.venv/bin/python -c "from src.conviction_engine.fundamentals import update_ticker_fundamentals as u; print(u('PYPL', mode='full'))"

# Weekly M&A scan (needs ANTHROPIC_API_KEY for agent hits)
.venv/bin/python scripts/run_ma_activity_weekly.py

# Tests
.venv/bin/python -m pytest tests/test_conviction_engine.py tests/test_api_conviction.py -q
```

---

## Remaining / follow-up

1. **Parth UI** — Section 6 navigation handlers in Nuxt conviction drawer.
2. **CEO start dates** — populate `ceo_start_date` in conviction_store (SEC DEF14A) for TSR scoring on established CEOs.
3. **Agent dims on schedule** — optional quarterly cron with `CONVICTION_RUN_AGENT_DIMS=1` for moat/macro/reinvestment/CEO blend.
4. **Universe backfill** — run full recalc across conviction universe after deploy.
5. **PYPL → MAX CONVICTION** — at conviction 7.0 today; +1 from CEO penalty (−1) + reinvestment (+1) with agents, or revenue-accel FD positive → 85% tactical sizing at same tier.

---

## SSI scope

No SSI engine changes in this PDF. SSI (`src/sentiment_superindex/`) unchanged.
