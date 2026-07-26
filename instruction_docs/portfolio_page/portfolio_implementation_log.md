# Portfolio Page — Implementation Log

**Specs:** [`PORTFOLIO_API_HANDOFF.md`](PORTFOLIO_API_HANDOFF.md) · [`spec_15July.md`](spec_15July.md) · [`15July_imp_spec_additions.md`](15July_imp_spec_additions.md)  
**UI mock:** [`MindWealth_Portfolio_Unified_v5.html`](MindWealth_Portfolio_Unified_v5.html)  
**Open decisions:** [`OPEN_QUESTIONS_FOR_ROHIT.md`](OPEN_QUESTIONS_FOR_ROHIT.md)  
**Ahil NAV deliverables (Jul 2026):** [`ahil_analysis/`](ahil_analysis/) — consolidated report + filled workbooks  
**API version:** v1.8.2 (portfolio routes ship with main API; `/portfolio/nav` snapshot added v1.8.2)  
**Work period:** 2026-07-18 → 2026-07-20  
**Repo:** `/home/ubuntu/uiv2/git/MindWealth_UI` (branch `chatbot-dev`)  
**Owner (backend):** Divyanshu (D1–D7 in July spec)  
**Related aim doc:** [`PORTFOLIO_PAGE_AIM_AND_STATUS.md`](PORTFOLIO_PAGE_AIM_AND_STATUS.md)

---

## Portfolio Page — What It Is (read this first)

*Plain-language overview of the product, what users will see, and what the backend must supply. The **Simple Explanation** section below walks through what I built and how.*

### What exactly is the Portfolio page?

The **Portfolio page** is a read-only **command centre** in the MindWealth web app. It answers one question in one place:

> *What does our portfolio look like right now — what we hold, how big each position is, how we are doing, what might enter or exit next, and where risk is building?*

MindWealth runs many automated **strategies** (called **functions**, e.g. TrendPulse) on different **timeframes** (Daily, Weekly). Each live idea is a **signal**; signals that are “in the book” become **open positions** (**holdings**). The Portfolio page turns that raw signal data into a dashboard normal people can read.

**Core product rule:** the website **displays** numbers; it **never** calculates sizes, weights, profit, risk, or attribution in the browser. Every figure comes from **FastAPI** on the server. If a formula changes, we change the API once and the UI re-renders.

**“One ledger, two windows”:** Portfolio and the **Signals** page read the **same feeds** for new entries and new exits. If Portfolio says “3 new entries today,” Signals shows the same 3.

**Design reference:** clickable mock [`MindWealth_Portfolio_Unified_v5.html`](MindWealth_Portfolio_Unified_v5.html). Live Nuxt UI (Parth) will match those shapes once wired to APIs.

---

### What features will it provide?

| Feature area | What it does |
|--------------|--------------|
| **Three books** | Switch between **MODEL** (simulated track record), **BROKERAGE** (real Interactive Brokers account), and **PERSONAL** (manual holdings) — never mixed |
| **Overview (new default tab)** | NAV chart, pipeline ribbon (Entries → Holdings → Exits), masthead stats, top contributors/detractors, risk snapshot, full holdings table |
| **Sizing & Allocation** | Dollar size per position and per theme **sleeve**, equity ceiling, scenario previews (NORMAL / STRESS / LOW VOL / MANUAL / AUTO) |
| **Portfolio Risk** | Correlation matrix, breach warnings, conviction summary, “Enter My Portfolio” comparison rail |
| **Live P&L** | Open-position profit/loss plus **conflict cards** when strategies disagree on the same asset |
| **MODEL-only four-way toggle** | Same trades, four sizing stories: **BASE**, **BASE+SSI**, **BASE+CONVICTION**, **ENHANCED** (production) |
| **Holdings intelligence** | Score sort, group same asset, ⊕ NEW SIGNAL / ◔ HELD / MULTI-SIG chips, negative R:R styling, cross-function exit badges, row → detail drawer |
| **Signals menu alignment** | “New Entries” and “New Exits” menus use the same API feeds as the Portfolio pipeline |
| **Agent slide-in** (planned) | Overwatch alerts that auto-open on the relevant page via `alerts.json` |

Users only **toggle** views (book, scenario, group same asset). They do not edit sizes or formulas on this page.

---

### What will be visible on the page (by view)

#### Upper level — book selector (all views)

| Book | Plain English | What shows |
|------|---------------|------------|
| **MODEL** | Simulated research portfolio (~179 assets, multi-currency → USD) | Full four tabs + four-way sizing toggle |
| **BROKERAGE** | Real IBKR account (US-listed, USD only) | Overview + Live P&L only; numbers from IBKR API, not calculated by us |
| **PERSONAL** | Rohit’s hand-entered holdings | Overview + Live P&L; FX-converted to USD |

#### Overview (MODEL — richest view)

| UI element | Content |
|------------|---------|
| **Four-way toggle** | BASE / +SSI / +Conviction / ENHANCED — swaps masthead, NAV chart, SIZE column, attribution strip |
| **Pipeline ribbon** | Entries count → Holdings count → Exits count; click Entries/Exits opens detail; Holdings scrolls to table |
| **NAV chart** | Gold NAV line, drawdown shading, high-water mark, optional S&P 500 benchmark, INCL. MTM / CLOSED TRADES ONLY toggle |
| **Masthead** | Long/short/net/gross, invested vs cash, as-of timestamp, “All figures USD · FX at daily close” (MODEL/PERSONAL) |
| **Top 5 contributors / detractors** | Basis points since go-live (`pnl_contribution_bps` per holding) |
| **Risk block (right rail)** | Realized vol, beta vs S&P, best month, worst month |
| **Holdings table** | Ticker, function, interval, direction, score, rank, R:R dynamic, hold-time %, conviction tier, sleeve, SIZE, P&L, chips, exit_ref |

#### Sizing & Allocation (MODEL only)

| UI element | Content |
|------------|---------|
| **Header strip** | Portfolio notional, equity ceiling, equities deployed, cash @ yield |
| **Sleeve rows** | Per-theme weight vs ceiling, slots used/available (when D1 ships), expandable position detail |
| **Summary rail** | Per-sleeve dollars, deployed bar, cash breakdown, constraint checks, BQ tier table, flag guide |
| **Scenario buttons** | NORMAL / STRESS / LOW VOL / MANUAL / AUTO + REFRESH SIZES — query param only; no frontend math |

#### Portfolio Risk (MODEL only)

| UI element | Content |
|------------|---------|
| **Conviction summary** (new) | MAX / tactical / reduced / yield-trap counts and names |
| **Correlation matrix** | 8×8 cluster matrix, ETF-proxy legend, cache tag |
| **Breach panel** | Pairs over correlation threshold with dollar recommendations |
| **Enter My Portfolio** | Unchanged — user holdings vs model |

#### Live P&L (all books that have positions)

| UI element | Content |
|------------|---------|
| **Conflict cards (top)** | Cross-function exits: triggering strategy, exit price/date, surviving legs + implied natural exit date |
| **Positions table** | Full P&L columns; ⚑ CROSS-FN EXIT badge on commodity legs when applicable |

#### Signals page (cross-linked)

| Change | Content |
|--------|---------|
| Menu rename | “New Signals” → **New Entries**; new **New Exits** below Claude Shortlisted |
| Outstanding table | New **exit_ref** column (same string as Portfolio drawer) |

---

### What the backend must provide (for the page to function)

The July spec and [`PORTFOLIO_API_HANDOFF.md`](PORTFOLIO_API_HANDOFF.md) define **nine portfolio-related endpoints**. The frontend binds to these; it does not recompute.

| # | Endpoint | Role on the page |
|---|----------|------------------|
| 1 | `GET /portfolio/nav` | Overview NAV chart, benchmark, vol/beta/best-worst month, attribution strip |
| 2 | `GET /portfolio/holdings` | Overview table, Live P&L rows, pipeline “Holdings” count |
| 3 | `GET /portfolio/sizing` | Sizing & Allocation (alias of `/portfolio/sizer`) |
| 4 | `GET /portfolio/risk` | Portfolio Risk matrix + conviction summary |
| 5 | `GET /signals/entries` | Pipeline “Entries”, New Entries menu |
| 6 | `GET /signals/exits` | Pipeline “Exits”, New Exits menu |
| 7 | `GET /signals/reports/portfolio-risk/latest` | Live P&L conflict cards |
| 8 | `GET /portfolio/risk/search` | Ticker autocomplete in Enter My Portfolio |
| 9 | `POST /portfolio/risk/analyze` | User portfolio vs model analysis |

**Cross-cutting backend responsibilities:**

| Responsibility | Why it matters |
|----------------|----------------|
| **`book_id` on every call** (`model` \| `brokerage` \| `personal`) | Prevents mixing simulated and real money |
| **`book` param on MODEL only** (`base` \| `ssi` \| `cv` \| `enhanced`) | Four NAV/sizing variants on the same trade list |
| **Holdings `size_usd` = sizer `allocation_usd`** | Overview SIZE column must match Sizing tab |
| **Enrichment** | Score, rank, `rr_dynamic`, conviction tier, siblings, multi_sig, exit_ref on every row |
| **Book validation** | Return **422** for unsupported books instead of silent wrong data |
| **Nightly data** | `trade_store` CSVs, conviction overlays, cross-function conflict JSON, correlation cache |

**Data flow (simple):**

```
Nightly jobs → trade_store CSVs + conviction overlays + conflict JSON
                        │
                        ▼
              FastAPI portfolio + signals routers
                        │
                        ▼
              Nuxt Portfolio UI (read-only display)
```

---

### Backend implementation status (snapshot — updated 2026-07-22)

| Area | Status | Notes |
|------|--------|-------|
| Holdings, entries, exits, portfolio-risk report | **Done** | MODEL + `book=enhanced` |
| Sizer, sizing alias, risk, analyze, search | **Done** (extended) | Interim cluster-% engine; `book_id`, conviction summary |
| Book validation (`portfolio_book.py`) | **Done** | `brokerage` / `personal` / `book=base\|ssi\|cv` → 422 |
| D2 ETF/FX base size, `rr_dynamic`, siblings, multi_sig | **Done** | Jul 2026 conviction overlay fixes |
| `GET /portfolio/nav` | **Done (interim)** | Monthly mtm/closed/benchmark from Ahil workbooks; nav_engine plug-in ready; all 4 MODEL books on nav |
| Ahil NAV workbooks (A1 data) | **Delivered** | [`ahil_analysis/`](ahil_analysis/) — monthly NAV Jan-24→Jun-26, benchmark, drawdown, proxy four-book; **not ingested** |
| Four-book toggle (`book=base\|ssi\|cv`) | **Partially unblocked** | Proxy attribution in consolidated report; API still 422 until real SSI/conviction wired |
| `pnl_contribution_bps`, vol/beta/best-worst month | **Not built** | Ahil monthly series exists — compute after ingest |
| `book_id=brokerage` | **Not built** | IBKR Gateway plan in [`ikbr_details.md`](ikbr_details.md); account pending |
| `book_id=personal` | **Not built** | Persistence spec pending |
| D1 slot sizing (`NAV/N × conviction × SSI`) | **Not built** | Ahil supports **$10M / N=60**; API still $100M; SLEEVES unsigned |
| `exit_type=eviction` | **Research done** | 1C validated in Ahil report; API not wired |
| Exact R:R (Test 6/8) | **Not built** | `compute_rr_to_nearest_support_stop` per Ahil blocker list |
| Nuxt Portfolio UI wire-up | **Frontend (Parth)** | Dev API `:8507`, dev UI `:8514` |

**Verdict:** Parth can wire **holdings, sizing, entries, exits, sizer/risk, conflict cards, and nav snapshot** on `book_id=model&book=enhanced`. **Monthly NAV chart** is the next backend win (ingest Ahil workbooks). Four-book production toggle and daily chart still need ingest + live feeds.

Open decisions: [`OPEN_QUESTIONS_FOR_ROHIT.md`](OPEN_QUESTIONS_FOR_ROHIT.md) — Ask 1 & 2 partially answered by Ahil (see § Ahil analysis below).

---

### Ahil analysis deliverables (Jul 2026) — impact on blockers

**Files:** [`ahil_analysis/MindWealth_Consolidated_Report.pdf`](ahil_analysis/MindWealth_Consolidated_Report.pdf) · [`MindWealth_Ahil_NAV_FILLED_GATED_FIXED_DAILYDD.xlsx`](ahil_analysis/MindWealth_Ahil_NAV_FILLED_GATED_FIXED_DAILYDD.xlsx) (Version B / MTM) · [`MindWealth_Ahil_NAV_FILLED_VersionA_GATED_FIXED_DAILYDD.xlsx`](ahil_analysis/MindWealth_Ahil_NAV_FILLED_VersionA_GATED_FIXED_DAILYDD.xlsx) (Version A / closed only)

**Upstream data (MindWealth core — `/home/ubuntu/MindWealth`):** Ahil's pipeline reads from here; the filled workbooks are **outputs**, not stored in core.

| MindWealth path | Role |
|-----------------|------|
| `trade_store/US/forward_testing/<STRATEGY>/**/*.csv` | Trade ledger input (~1,990 CSVs, 9 functions) — source for NAV replay per `Ahil_portfolio_page_docs_2.md` |
| `trade_store/virtual_trading_long.csv` / `short.csv` | VT book (904 + 354 rows) — same file shape the Portfolio API sizer uses via MindWealth_UI `trade_store` |
| `trade_store/portfolio_analysis_us.csv` | Per-function open/closed stats — **not** NAV series |
| `data/stake.csv` | ~199-symbol universe (179 gated in research) |

**Not in MindWealth on this server:** `nav_engine.py`, `stest_*.py`, `stest_cache/`, or the filled xlsx workbooks. Regenerating NAV from core requires Ahil's analysis scripts (or ingesting the xlsx deliverables in `ahil_analysis/`).

| Blocker (before) | After Ahil deliverable |
|------------------|------------------------|
| No NAV time series | **Monthly** closing NAV + S&P benchmark returns filled (Jan-24 → Jun-26, $10M start) |
| Axiom 2 unknown | **Resolved in research:** position-level, hold-original-weight to exit (no rebalance) |
| Ask 1 — $10M vs $100M | **Strong evidence for $10M** (workbook opening NAV); Rohit formal sign-off still needed vs UI $100M mock |
| Ask 1 — N=60 vs 80 | **N=60 primary** in tests (also 80, 120); eviction pick retains OOS edge |
| A1 four-book replay missing | **Proxy decomposition delivered:** BASE 13.41% → ENHANCED 17.71% CAGR (+SSI +1.63pp, +Conviction +2.15pp) |
| 1C eviction unproven | **Validated** — eviction mode beats chrono at N=60 in consolidated tests |
| Daily max drawdown understated | **Drawdown_Episodes** sheet + true daily max DD (~−13%) in both workbooks |
| Reconciliation / honest numbers | Waterfall explains old averaged-return inflation (Sharpe ~1.26 → ~0.67 position-level) |

**Still blocked (Ahil explicitly lists these on Divyanshu):**

- P3 point-in-time replay harness in core code
- Test 6/8 exact R:R (`compute_rr_to_nearest_support_stop`)
- A1 **production** numbers — replace proxy SSI/conviction with live API feeds
- Per-regime daily bucket endpoint
- Composite-score API 401 (Ahil used ledger-only scores)

**Recommended next backend steps:**

1. ~~Ingest `Monthly_NAV` + benchmark columns → extend `get_portfolio_nav()` series arrays~~ **Done** (`src/portfolio_nav/`)
2. Drop Ahil `nav_engine.py` into `src/portfolio_nav/ahil_nav_engine.py` implementing `get_nav_history()` — auto-bypasses workbook
3. Wire real SSI ceiling + conviction tiers → live four-book series (not proxy attribution)
4. Implement eviction exit_type on `/signals/exits` using 1C rules from research artifacts
5. Implement `compute_rr_to_nearest_support_stop` for Test 6/8

---

## Simple Explanation

*Starts here: what **I built** on the backend for the Portfolio page — how each piece works and why I built it. Read the overview above first for product context.*

### What I built (the big picture)

The Portfolio section is meant to show a simulated **MODEL book** (up to ~179 assets), a real **BROKERAGE** book (IBKR), and a **PERSONAL** book — with Overview, Sizing & Allocation, Portfolio Risk, and Live P&L views. The product rule is strict: **the frontend never computes sizes, weights, P&L, or attribution**. Everything must come from FastAPI.

**I implemented the backend slice that was unblocked without guessing** — new endpoints, book validation, signal pipeline adapters, holdings enrichment, `/portfolio/nav` snapshot (v1.8.2), and fixes to the existing sizer/risk stack. I did **not** build the Nuxt Portfolio UI (that is Parth). I also did **not** ingest Ahil's NAV workbooks, wire four-book live attribution, IBKR, or the D1 slot-based sizing engine — those are the next backend phase (documented above and in `OPEN_QUESTIONS_FOR_ROHIT.md`).

---

### Why I built it

Before this work:

- Only **4 of 9** HANDOFF endpoints existed (`/portfolio/sizer`, `/portfolio/risk`, `/portfolio/risk/analyze`, `/portfolio/risk/search`).
- Parth was **blocked** on live wiring — the v5 mock had shapes but no matching APIs for holdings, entries, exits, or book-scoped data.
- The sizer used an **interim cluster-% engine** (June spec), not the July D1 slot method.
- ETF/FX rows could show **BLOCKED → $0** instead of base size (D2 bug).
- `rr_dynamic` existed in nightly CSVs but was **not exposed** consistently through API enrichment.
- Cross-function exit conflicts existed as raw CSV + JSON blobs, not the clean HANDOFF §11 shape.

I built a **unified portfolio pipeline layer** so the frontend can bind to real data for everything that does not require unresolved product decisions.

---

### The three books (architecture I enforced)

The July brief defines two levels of switching:

| Level | Control | What I built |
|-------|---------|--------------|
| **Upper** | `book_id` = `model` \| `brokerage` \| `personal` | Validation in `portfolio_book.py`; `brokerage` and `personal` return **422** until IBKR/persistence specs exist |
| **Lower** (MODEL only) | `book` = `base` \| `ssi` \| `cv` \| `enhanced` | Only **`enhanced`** is served today; other three return **422** until Ahil A1 four-book replay |

This prevents silent wrong data: the API refuses to fake BASE/SSI/CV books or brokerage positions.

---

### What I shipped — endpoint by endpoint

#### Already existed (I extended)

| Endpoint | What was there | What I added |
|----------|----------------|--------------|
| `GET /portfolio/sizer` | Full cluster-budget sizer, ceiling, P&L | `book_id=model` param; D2 base-size fix for NOT_APPLICABLE assets |
| `GET /portfolio/risk` | Correlation matrix + breaches | `book_id=model`; `conviction_summary` block (HANDOFF §8) |
| `POST /portfolio/risk/analyze` | User portfolio vs model | Unchanged |
| `GET /portfolio/risk/search` | Ticker autocomplete | Unchanged |

#### New in this work

| Endpoint | Purpose |
|----------|---------|
| `GET /portfolio/holdings` | Open positions with score, rank, size, siblings, multi_sig, rr_dynamic |
| `GET /portfolio/sizing` | Alias for `/portfolio/sizer` (July spec name); `auto` → `normal` |
| `GET /signals/entries` | New Entries pipeline — same feed as Signals page |
| `GET /signals/exits` | New Exits pipeline — target_signal + exit classification |
| `GET /signals/reports/portfolio-risk/latest` | HANDOFF §11 shape + `implied_natural_exit_date` |

---

### How holdings work (the merge I built)

Holdings are **not** a third independent calculation. I merge two sources:

1. **`outstanding_signal.csv`** (enriched) — score, rank, rr_dynamic, hold-time %, conviction, cross-function flags  
2. **`/portfolio/sizer`** allocations — `size_usd`, shares, market_value, pnl_usd, sleeve label  

Match key: `(ticker, function, interval, direction)`.

**`same_asset_siblings[]`** — built from outstanding + new_signal rows grouped by symbol. Relationship types: `new_signal` | `already_held`. Populated for **all rows** where siblings exist (per `spec_15July.md` / v5 DEV NOTES, not D4 negative-only).

**`multi_sig[]`** — other open signals on the same ticker in the same direction (informational only; no sizing boost).

---

### How entries / exits work

| Endpoint | Source CSV | Logic |
|----------|------------|-------|
| `/signals/entries` | `new_signal.csv` | Enrich → sort by `composite_score` desc → rank |
| `/signals/exits` | `target_signal.csv` | Filter exit candidates (exit_fired, cross-fn conflict, negative rr_dynamic, exit date set) → `exit_type`: `signal` \| `rr` |

`exit_type=eviction` is **not** implemented — requires 1C eviction engine (Ahil/Rohit).

---

### Portfolio-risk report (cross-function conflicts)

Nightly job writes `trade_store/US/cross_function_conflicts.json`. I reshape it to HANDOFF §11:

- `cross_function_conflict_count`
- `cross_function_conflicts[]` with `triggering_exits`, `open_positions`
- **`implied_natural_exit_date`** = `signal_date + avg_hold_days` (D4 formula; hold days looked up from outstanding enrichment)

---

### D2 fix — ETF / FX / commodity base size

**Problem:** Conviction Engine is single-stock only. NOT_APPLICABLE assets (ETFs, FX, indexes) were sometimes tiered as **BLOCKED → $0**.

**Fix:** In `portfolio_service.py`, NOT_APPLICABLE with no BQ → tier `N/A`, share **100%** of cluster slot (base size), never blocked to zero.

---

### `rr_dynamic` exposure

**Problem:** Nightly CSV has `R:R Dynamic`; enrichment computed `rr_static` but did not always pass through `rr_dynamic`.

**Fix:** `signal_enrichment_service.py` now writes `rr_dynamic` on enriched records (from CSV or MindWealth `enrich_signal_dict` core path).

---

### Problems I hit and how I fixed them

| Problem | What I did |
|---------|------------|
| No `book_id` isolation | Added `portfolio_book.py` with explicit 422 for unsupported books |
| HANDOFF path `/portfolio/sizing` vs code `/portfolio/sizer` | Added `/sizing` alias route |
| Holdings `size_usd` must match sizer | Single allocation index from sizer output keyed by position |
| Portfolio-risk response was raw report shape | Dedicated HANDOFF adapter in `portfolio_pipeline_service.py` |
| Circular import risk (risk ↔ pipeline) | Moved `build_conviction_summary` into `portfolio_service.py` |
| `conviction_summary` missing on risk | Built from sizer `pnl_rows` tier counts |

---

### What I did **not** build (still outstanding)

| Item | Blocker | Doc |
|------|---------|-----|
| Monthly/daily NAV series in API | Ingest Ahil workbooks or P3 live replay | `ahil_analysis/*.xlsx` |
| `book=base\|ssi\|cv` production numbers | Real SSI/conviction feeds (proxy exists) | Consolidated report A1 section |
| `book_id=brokerage\|personal` | IBKR + personal persistence | HANDOFF §2, §13; `ikbr_details.md` |
| D1 slot sizing (`NAV/N × conviction × SSI`) | SLEEVES table; flip notional $100M→$10M | Ask 1, Ask 4 (Ahil: $10M, N=60) |
| `pnl_contribution_bps` on holdings | Since-go-live NAV path after ingest | HANDOFF §4 |
| `exit_type=eviction` | Wire 1C rules (research validated) | Ahil consolidated report |
| Test 6/8 exact R:R | `compute_rr_to_nearest_support_stop` | Ahil blocker list |
| True-weight breach math (D7) | Blocked on D1 | D7 L27 |
| `alerts.json` with `target_page` | Separate D4 item; analyst alerts exist but no `target_page` | D4 L21 |
| Nuxt Portfolio UI wire-up | Frontend (Parth) | `spec_15July.md` |

**Backend verdict:** Parth can wire **holdings, sizing, entries, exits, portfolio-risk conflicts, and existing sizer/risk** on `book_id=model&book=enhanced`. Overview NAV chart, four-book toggle, and brokerage/personal books remain blocked.

---

### One-sentence summary (my work)

**I built the portfolio API pipeline** — book validation, holdings merge with sizer, entries/exits feeds, cross-function risk report, rr_dynamic exposure, and D2 base-size fix — so the Portfolio page can run on real trade_store data without frontend math, while explicitly refusing unsupported books until Rohit and Ahil lock the remaining decisions.

---

## Part 1 — Concise Summary

### HANDOFF endpoint status (9 required)

| # | Endpoint | Status | Notes |
|---|----------|--------|-------|
| 1 | `GET /portfolio/nav` | **Partial** | v1.8.2 snapshot live; monthly series + benchmark in Ahil workbooks — ingest pending |
| 2 | `GET /portfolio/holdings` | **Done** | MODEL + `book=enhanced` only |
| 3 | `GET /portfolio/sizer` | **Done** (extended) | Interim cluster engine; `book_id` added |
| 4 | `GET /portfolio/risk` | **Done** (extended) | + `conviction_summary`, `book_id` |
| 5 | `GET /signals/entries` | **Done** | New |
| 6 | `GET /signals/exits` | **Done** | Partial — no `eviction` type |
| 7 | `GET /signals/reports/portfolio-risk/latest` | **Done** | HANDOFF §11 shape |
| 8 | `GET /portfolio/risk/search` | **Done** | Pre-existing |
| 9 | `POST /portfolio/risk/analyze` | **Done** | Pre-existing |

**Alias:** `GET /portfolio/sizing` → same handler as `/portfolio/sizer` (`auto` scenario maps to `normal`).

### What was implemented (files)

| Area | Deliverable |
|------|-------------|
| **Book validation** | `api/services/portfolio_book.py` — `book_id`, `book`, 422 for unsupported |
| **Pipeline adapters** | `api/services/portfolio_pipeline_service.py` — entries, exits, holdings, portfolio-risk |
| **Holdings merge** | Outstanding + new_signal enrichment + sizer allocation index |
| **Siblings / multi_sig** | Per-symbol grouping; `new_signal` / `already_held` relationships |
| **Portfolio-risk HANDOFF** | `implied_natural_exit_date` on open legs |
| **D2 base size** | NOT_APPLICABLE → N/A tier, 100% share, not $0 |
| **rr_dynamic** | Exposed in `signal_enrichment_service` output |
| **conviction_summary** | On `/portfolio/risk` from sizer tiers |
| **Sizing alias** | `/portfolio/sizing` per July spec |
| **Open questions doc** | `OPEN_QUESTIONS_FOR_ROHIT.md` — 5 blocking decisions |
| **Tests** | `test_api_portfolio.py`, `test_api_signals_surface.py` — **56 pass** |

### Architecture decisions (locked for now)

- **Single MODEL book served:** `book_id=model` + `book=enhanced` only; others → 422 with explicit message
- **Sizing engine:** interim **cluster-%** budget split (not D1 slots) until Rohit locks SLEEVES + N + notional
- **Siblings scope:** all rows where siblings exist (frontend brief + v5), not D4 negative-only
- **Holdings size source:** sizer `allocation_usd` must match HANDOFF §12 rule #3 within current engine
- **Notional:** `PORTFOLIO_NOTIONAL = 100_000_000` in code — conflicts with Ahil $10M / v5 mock (Ask 1)
- **Breach dollars on risk:** still cluster-% × notional (D7 true weights deferred)

### Problems faced and solved

| # | Problem | Solution |
|---|---------|----------|
| 1 | Parth blocked — no holdings API | `GET /portfolio/holdings` + pipeline merge |
| 2 | Spec says `/portfolio/sizing`, code had `/sizer` | Alias route |
| 3 | ETF/FX showed BLOCKED $0 | D2 fix in sizer pass |
| 4 | `rr_dynamic` missing from API enrichment | Pass through in `enrich_record()` |
| 5 | portfolio-risk returned CSV report blob | HANDOFF adapter + `book_id` query |
| 6 | No book isolation | `portfolio_book.py` |
| 7 | Risk missing conviction summary | `build_conviction_summary()` from pnl_rows |

### Verification

| Check | Result |
|-------|--------|
| `pytest tests/test_api_portfolio.py tests/test_api_signals_surface.py` | **56 passed** |
| Holdings `book=enhanced` | **200** + holdings array |
| Holdings `book=base` | **422** |
| `book_id=brokerage` | **422** |
| `/portfolio/sizing` vs `/sizer` summary | **Match** |

---

## Part 2 — Detailed Implementation

### 2.1 Background and scope

The Portfolio page (July 2026 brief) replaces mocks with backend-driven data across:

| View | Primary endpoints |
|------|-------------------|
| **Overview** | `/portfolio/nav`, `/portfolio/holdings`, `/signals/entries`, `/signals/exits` |
| **Sizing & Allocation** | `/portfolio/sizing` |
| **Portfolio Risk** | `/portfolio/risk`, `/portfolio/risk/analyze` |
| **Live P&L** | `/portfolio/holdings`, `/signals/reports/portfolio-risk/latest` |

**Backend delivered in this log:** holdings, sizing (alias), entries, exits, portfolio-risk HANDOFF, sizer/risk extensions, book validation, D2 + rr_dynamic fixes.

**Not delivered:** nav, four valuation books, brokerage, personal, D1 slots, nav attribution, eviction exits.

---

### 2.2 API surface

All paths prefixed with `/api/v1`.

#### Portfolio router (`api/routers/portfolio.py`)

| Method | Path | Query params | Purpose |
|--------|------|--------------|---------|
| GET | `/portfolio/holdings` | `book_id`, `book`, `scenario` | HANDOFF §4 holdings |
| GET | `/portfolio/sizer` | `book_id=model`, `scenario` | HANDOFF §7 sizer |
| GET | `/portfolio/sizing` | same + `auto` scenario | July spec alias |
| GET | `/portfolio/risk` | `book_id=model`, `scenario` | HANDOFF §8 risk |
| POST | `/portfolio/risk/analyze` | body | HANDOFF §10 |
| GET | `/portfolio/risk/search` | `q`, `limit` | HANDOFF §9 |

#### Signals router (`api/routers/signals.py`)

| Method | Path | Query params | Purpose |
|--------|------|--------------|---------|
| GET | `/signals/entries` | `book_id` | HANDOFF §5 |
| GET | `/signals/exits` | `book_id` | HANDOFF §6 |
| GET | `/signals/reports/portfolio-risk/latest` | `book_id` | HANDOFF §11 (registered **before** generic `/reports/{name}/latest`) |

#### Error behaviour

| Code | When |
|------|------|
| `400` | Invalid `book_id` / `book` string |
| `404` | Missing trade_store CSV |
| `422` | Valid request, unsupported book (`brokerage`, `personal`, `book=base\|ssi\|cv`) |
| `502` | Sizer/holdings computation failure |

---

### 2.3 `GET /portfolio/holdings` — response fields

| Field | Source |
|-------|--------|
| `ticker`, `function`, `interval`, `direction` | Outstanding CSV + enrichment |
| `score`, `rank` | `composite_score`; sort desc |
| `rr_dynamic`, `hold_time_used_pct` | Enrichment / CSV |
| `size_usd`, `shares`, `market_value`, `pnl_usd` | Sizer allocation for matching key |
| `conviction_tier` | Parsed from sizer `size_tier` |
| `sleeve` | Sizer cluster label |
| `same_asset_siblings[]` | Outstanding + new_signal by symbol |
| `multi_sig[]` | Same ticker, same direction, other functions |
| `exit_ref` | Cross-fn display, or negative R:R message |
| `cross_function_exit` | `cross_function_exit_triggered` |
| `pnl_contribution_bps` | `null` (needs NAV) |
| `next_out` | `false` (eviction engine N/A) |

**Example:**

```bash
curl -s -H "X-API-Key: $KEY" \
  "http://127.0.0.1:8507/api/v1/portfolio/holdings?book_id=model&book=enhanced" \
  | jq '{count: (.holdings|length), first: .holdings[0].ticker}'
```

---

### 2.4 `GET /signals/entries` and `/signals/exits`

**Entries** — one row per `new_signal.csv` line:

```json
{
  "book_id": "model",
  "as_of": "2026-07-17T16:00:00Z",
  "entries": [{
    "id": "entry-infy-trendpulse-daily-2026-07-17",
    "ticker": "INFY",
    "function": "TRENDPULSE",
    "interval": "Daily",
    "direction": "Long",
    "signal_date": "2026-07-17",
    "score": 75.4,
    "rank": 1,
    "forward_win_rate_pct": 77.48,
    "detail": "Eligible for model admission"
  }]
}
```

**Exits** — filtered `target_signal.csv`:

- `exit_type`: `signal` (exit fired / exit date set) or `rr` (negative `rr_dynamic`)
- `conflict`: cross-function exit flag
- `eviction`: not emitted yet

---

### 2.5 `GET /signals/reports/portfolio-risk/latest`

HANDOFF §11 response (no raw `records[]` wrapper):

```json
{
  "book_id": "model",
  "report_date": "2026-07-17",
  "cross_function_conflict_count": 13,
  "cross_function_conflicts": [{
    "symbol": "0700.HK",
    "direction": "Long",
    "asset_class": "equity",
    "conflict": true,
    "triggering_exits": [{ "function": "SIGMASHELL", "interval": "Daily", "exit_date": "2026-07-14", "exit_price": 456.2 }],
    "open_positions": [{
      "function": "DELTADRIFT",
      "interval": "Weekly",
      "mtm_pct": 1.85,
      "signal_date": "2026-06-07",
      "implied_natural_exit_date": "2026-07-27"
    }]
  }]
}
```

Data file: `trade_store/US/cross_function_conflicts.json` (also dated copies).

---

### 2.6 Sizer and risk (existing + changes)

#### Sizer (`portfolio_service.get_portfolio_sizer`)

- **Ceiling chain:** regime max × VIX × SPX trend × HY credit × SSI (capped haircut)
- **Allocation:** cluster budget % of equity ceiling → split by BQ rank weight within cluster
- **Scenarios:** `normal` (80% regime max), `stress` (65%), `lowvol` (85%); cluster budgets scaled per scenario
- **Notional:** `$100,000,000` constant (`PORTFOLIO_NOTIONAL`)

#### Risk (`portfolio_service.get_portfolio_risk`)

- 8×8 cluster correlation matrix (live/cache/fallback)
- Breach pairs ρ > 0.75 watch, > 0.85 action
- **`conviction_summary`** added:

```json
{
  "max_count": 4,
  "tactical_count": 8,
  "reduced_count": 5,
  "yield_trap_count": 1,
  "max_names": ["SPY", "NVDA"],
  "yield_trap_names": []
}
```

**Known gap (D7):** breach `recommendation` dollar amounts still use combined cluster-% × $100M — not true sleeve weights. UI should not change breach panel until D1 ships (per D7 note to Parth).

---

### 2.7 Book validation (`portfolio_book.py`)

```python
validate_book_access("model", book="enhanced")  # OK
validate_book_access("model", book="base")      # BookUnavailableError → 422
validate_book_access("brokerage")               # BookUnavailableError → 422
validate_model_only("model")                    # sizer/risk — rejects non-model book_id
```

---

### 2.8 Data sources

| Data | Path / loader |
|------|----------------|
| Open positions | `trade_store/US/*_outstanding_signal.csv` |
| New entries | `trade_store/US/*_new_signal.csv` |
| Exit targets | `trade_store/US/*_target_signal.csv` |
| VT book (sizer) | `virtual_trading_long.csv` / `virtual_trading_short.csv` |
| Conviction overlay | `conviction_store/.../virtual_trading_*_conviction.csv` |
| Macro ceiling | `runic_output.json`, SSI multiplier API |
| Cross-fn conflicts | `trade_store/US/cross_function_conflicts.json` |
| Correlation matrix | `macro_intelligence/output/portfolio_cluster_correlations.json` (7-day cache) |

---

### 2.9 Frontend integration guide (Nuxt / Parth)

```
┌─────────────────────────────────────────────────────────────────┐
│  Portfolio page — book selector (upper)                           │
│    MODEL → requires book=enhanced today (others → show 422 msg)   │
│    BROKERAGE / PERSONAL → not wired yet                           │
├─────────────────────────────────────────────────────────────────┤
│  Overview                                                         │
│    GET /portfolio/holdings?book_id=model&book=enhanced            │
│    GET /signals/entries?book_id=model                              │
│    GET /signals/exits?book_id=model                               │
│    GET /portfolio/nav  ← NOT AVAILABLE YET                        │
├─────────────────────────────────────────────────────────────────┤
│  Sizing & Allocation                                              │
│    GET /portfolio/sizing?book_id=model&scenario=normal|stress|...  │
├─────────────────────────────────────────────────────────────────┤
│  Portfolio Risk                                                   │
│    GET /portfolio/risk?book_id=model&scenario=...                 │
│    POST /portfolio/risk/analyze (unchanged)                       │
├─────────────────────────────────────────────────────────────────┤
│  Live P&L — conflict cards first                                  │
│    GET /signals/reports/portfolio-risk/latest?book_id=model       │
│    GET /portfolio/holdings (same as Overview)                     │
└─────────────────────────────────────────────────────────────────┘
```

| UI need | API field / endpoint |
|---------|----------------------|
| Holdings table sort by score | `holdings[].score`, `rank` |
| ⊕ NEW SIGNAL / ◔ HELD chips | `same_asset_siblings[].relationship` |
| MULTI-SIG chip | `multi_sig[]` |
| Negative R:R amber row | `rr_dynamic < 0` |
| SIZE column | `size_usd` (must equal sizer `allocation_usd`) |
| Sleeve bars (interim) | sizer `clusters[]` — true-weight slots pending D1 |
| Cross-fn conflict cards | `portfolio-risk/latest` → `cross_function_conflicts` |
| Four-book NAV toggle | **Blocked** — `/portfolio/nav` + `book=base\|ssi\|cv` |

---

### 2.10 Testing

| Suite | Coverage |
|-------|----------|
| `tests/test_api_portfolio.py` | Sizer, risk, analyze, search, **holdings**, sizing alias, conviction_summary |
| `tests/test_api_signals_surface.py` | **entries**, **exits**, portfolio-risk HANDOFF shape, enrichment |

**Smoke commands:**

```bash
# Holdings
curl -s -H "X-API-Key: $KEY" \
  "http://127.0.0.1:8507/api/v1/portfolio/holdings?book_id=model&book=enhanced" \
  | jq '.holdings | length'

# Entries
curl -s -H "X-API-Key: $KEY" \
  "http://127.0.0.1:8507/api/v1/signals/entries?book_id=model" \
  | jq '.entries | length'

# Cross-function conflicts
curl -s -H "X-API-Key: $KEY" \
  "http://127.0.0.1:8507/api/v1/signals/reports/portfolio-risk/latest?book_id=model" \
  | jq '.cross_function_conflict_count'

# Unsupported book → 422
curl -s -o /dev/null -w "%{http_code}" -H "X-API-Key: $KEY" \
  "http://127.0.0.1:8507/api/v1/portfolio/holdings?book_id=model&book=base"
```

---

### 2.11 File map (key paths)

```
api/
  routers/
    portfolio.py                    # holdings, sizer, sizing, risk, analyze, search
    signals.py                        # entries, exits, portfolio-risk HANDOFF route
  services/
    portfolio_book.py                 # NEW — book_id / book validation
    portfolio_pipeline_service.py     # NEW — entries, exits, holdings, risk report
    portfolio_service.py              # sizer, risk, D2 fix, conviction_summary
    signal_enrichment_service.py      # rr_dynamic pass-through
    reports_service.py                # CSV loaders (used by pipeline)

instruction_docs/portfolio_page/
  PORTFOLIO_API_HANDOFF.md            # API contract
  OPEN_QUESTIONS_FOR_ROHIT.md         # 5 blocking decisions
  portfolio_implementation_log.md     # this file
  MindWealth_Portfolio_Unified_v5.html

tests/
  test_api_portfolio.py
  test_api_signals_surface.py
```

---

### 2.12 Environment / constants

| Constant | Value | Notes |
|----------|-------|-------|
| `PORTFOLIO_NOTIONAL` | `100_000_000` | Conflicts with Ahil $10M — Ask 1 |
| `IDLE_CASH_YIELD_PCT` | `3.5` | Sizer cash income display |
| `_SCENARIO_REGIME_MAX` | normal 80%, stress 65%, lowvol 85% | Ceiling preview only per D1 |
| `_BREACH_RHO_WARN` / `ACTION` | 0.75 / 0.85 | Risk breaches |

---

### 2.13 Open decisions (Rohit) — blocks next phase

See [`OPEN_QUESTIONS_FOR_ROHIT.md`](OPEN_QUESTIONS_FOR_ROHIT.md):

| # | Decision | Blocks |
|---|----------|--------|
| 1 | Production **N** and **notional** ($10M vs $100M) | Slot dollars, position_limit |
| 2 | **Axiom 2** rebalancing in API vs Ahil workbook | `/portfolio/nav`, stable size_usd |
| 3 | **IBKR** spec + owner | `book_id=brokerage` |
| 4 | **v5 SLEEVES** table as production source | D1 slots on `/sizing` |
| 5 | **`same_asset_siblings`** scope (all rows vs negative-only) | Currently implemented as all-rows |

---

### 2.14 Recommended implementation order (after Rohit answers)

1. Lock N + notional → slot dollar math  
2. Lock rebalancing → build `/portfolio/nav` with Ahil  
3. Lock SLEEVES → rebuild sizer (D1) + D7 breach math  
4. IBKR connector → brokerage book  
5. Personal persistence API  

---

### 2.15 Spec gaps vs `PORTFOLIO_API_HANDOFF.md`

| HANDOFF item | Backend | Frontend |
|--------------|---------|----------|
| `/portfolio/nav` full payload | **Not built** | Overview chart blocked |
| Four MODEL books on nav/holdings | **422 except enhanced** | Toggle blocked |
| `book_id=brokerage\|personal` | **422** | Books blocked |
| D1 sleeve slots on sizer | **Not built** | Sizing bars interim |
| §12 cross-endpoint consistency with nav | **Partial** (holdings ↔ sizer only) | — |
| `pnl_contribution_bps` | **null** | Top 5 contributors blocked |
| `exit_ref` full ladder | **Partial** string | Drawer line partial |
| `alerts.json` + `target_page` | **Not built** | Agent slide-in |
| Holdings + entries + exits + risk report | **Done** | Parth can wire |
| Sizer + risk + analyze + search | **Done** | Parth can wire |

**Backend verdict:** ~**60%** of HANDOFF surface is live for MODEL/enhanced (up from ~55%). Ahil Jul 2026 deliverables unblock **monthly NAV ingest** and **four-book proxy shape**; remaining ~40% is ingest, live overlay feeds, D1 slots, IBKR/personal.

---

### 2.16 Prod merge checklist

1. Merge `chatbot-dev` → `chatbot-prod`  
2. `bash scripts/prod-pull-and-restart.sh` in prod clone  
3. Smoke tests in `docs/dev_to_prod_migration_todos.md` (2026-07-20 section)  
4. Parth: point Nuxt BFF at `:8506` holdings/sizing/entries/exits  
5. Do **not** enable four-book or brokerage UI until API returns 200 for those paths  

---

*Last updated: 2026-07-22 — Portfolio backend implementation log (Divyanshu); Ahil `ahil_analysis/` impact section added*
