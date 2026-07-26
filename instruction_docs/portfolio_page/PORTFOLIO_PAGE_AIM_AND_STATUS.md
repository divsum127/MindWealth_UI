# Portfolio Page — What We Are Building and Why

**Audience:** Anyone new to MindWealth, finance, or the codebase  
**Last updated:** 2026-07-22  
**Related docs:** [`spec_15July.md`](spec_15July.md) (product brief) · [`MindWealth_Portfolio_Unified_v5.html`](MindWealth_Portfolio_Unified_v5.html) (clickable mock) · [`portfolio_implementation_log.md`](portfolio_implementation_log.md) (technical build log) · [`OPEN_QUESTIONS_FOR_ROHIT.md`](OPEN_QUESTIONS_FOR_ROHIT.md) (decisions still open) · [`ahil_analysis/`](ahil_analysis/) (Ahil NAV workbooks + consolidated report, Jul 2026)

---

## 1. The aim — why this page exists

MindWealth is a system that watches many markets and assets (stocks, ETFs, currencies, commodities, etc.) and uses **automated rules** to suggest when to buy or sell. Those suggestions are called **signals**. Over time, signals become **open positions** (things the system is currently “holding” on paper) or **closed positions** (things that already exited).

Today, signal data lives on one part of the product (the **Signals** page), and portfolio-style information lives on another (older **Portfolio** screens). Numbers were sometimes calculated in the browser, sometimes copied from spreadsheets, and sometimes shown as placeholder mock data. That made it hard to trust what you see and hard to change a formula without breaking the UI.

**The aim of the new Portfolio page is:**

1. **One honest picture of the portfolio** — what we hold, how big each position is, how we are doing, and what might enter or exit next.
2. **One source of truth** — every number on screen comes from the **backend API** (the server). The website **displays**; it does not recalculate sizes, profit, or risk in the browser.
3. **Same story on Signals and Portfolio** — if the Portfolio page says “3 new entries today,” the Signals page shows the same 3 entries. No duplicate logic.
4. **Support three different “books”** — a simulated track record (MODEL), a real brokerage account (BROKERAGE), and a personal watchlist (PERSONAL), without mixing them up.
5. **Help humans decide faster** — surface conflicts (e.g. one strategy says exit Apple while another still holds Apple), sizing limits, and risk hotspots before they become surprises.

In short: we are building a **read-only command centre** for “what does our portfolio look like right now, under our rules, and what is changing?”

---

## 2. MindWealth in one paragraph (no finance background needed)

Imagine a team of analysts who each use a different recipe to spot trades:

- One recipe might look at **weekly trends**.
- Another might look at **daily momentum**.
- Another might use **macro conditions** (is the market fearful or calm?).

Each recipe is called a **function** (e.g. TrendPulse, FractalTrack). Each runs on a **timeframe** (Daily, Weekly, Monthly). Each trade is **long** (betting price goes up) or **short** (betting price goes down).

The system scores how good each live signal looks (**Signal Quality Score**). It also tracks how much profit is left vs how much risk remains (**reward-to-risk**, or R:R). Positions are grouped into **sleeves** (theme buckets like “US Tech” or “Commodities”) so we do not put too many eggs in one basket.

The Portfolio page turns all of that into a **dashboard** normal people can read.

---

## 3. What exactly we are creating

We are creating a **unified Portfolio section** in the MindWealth web app with:

| Piece | What it is |
|-------|------------|
| **New default tab: Overview** | Landing view — chart of portfolio value over time, summary stats, holdings table, pipeline of entries/exits |
| **Sizing & Allocation** (renamed from “Sized Allocations”) | How much dollar size each position gets, by theme sleeve, under different “what-if” scenarios |
| **Portfolio Risk** | How correlated holdings are, whether theme buckets are too full, conviction summary |
| **Live P&L** | Profit and loss on open positions, with **conflict cards** when strategies disagree |
| **Book selector** | Switch between MODEL / BROKERAGE / PERSONAL |
| **MODEL-only toggle** | Compare four sizing stories on the *same* trades (BASE, +SSI, +Conviction, ENHANCED) |
| **Backend APIs** | Server endpoints that compute and return all numbers the UI shows |
| **Signals menu updates** | “New Entries” and “New Exits” menus aligned with Portfolio pipeline |

The clickable design reference is **`MindWealth_Portfolio_Unified_v5.html`** — open it in a browser to see layout, colours, and interactions. The live Nuxt app will match those shapes once wired to APIs.

**Important rule:** Users only **toggle** views (which book, which scenario, group same asset on/off). They do not edit sizes or formulas on this page.

---

## 4. The three “books” (three portfolios, never mixed)

Think of three separate notebooks:

### MODEL book (simulated track record)

- The full research portfolio — many assets, multiple currencies, converted to US dollars.
- This is what we show prospective investors: “here is how our rules would have performed.”
- Supports the **four-way sizing toggle** (see below) because sizing here is a modelling choice.

### BROKERAGE book (real money at Interactive Brokers)

- The **actual** brokerage account.
- US stocks, US dollars only.
- Numbers must match **Interactive Brokers (IBKR)** exactly — the website does not calculate them.

### PERSONAL book (Rohit’s manual holdings)

- Holdings typed in by hand (ticker + shares).
- Useful for comparing personal investments to the model without pretending they are the same account.

**Why three books matter:** Showing brokerage cash in the model chart would be misleading. The product enforces **separate data paths** for each book.

---

## 5. The four MODEL sizing views (lower toggle — MODEL only)

On the same set of trades, we ask: *“What if we sized positions differently?”*

| View | Plain English |
|------|----------------|
| **BASE** | Equal size per slot — every position gets the same dollar weight; fully invested. |
| **BASE + SSI** | Same trades, but when macro “stress” says deploy less capital, **all** positions shrink equally and cash rises. |
| **BASE + CONVICTION** | Same trades, but stronger companies get larger sizes and weak ones get smaller (single stocks only). |
| **ENHANCED** | Both overlays together — how production settings aim to run. |

This toggle **only appears inside MODEL**. It does not apply to the real brokerage account (IBKR reports one number) or personal holdings (no firm sizing rules).

---

## 6. Features we are planning — explained simply

### 6.1 Overview — the new home for Portfolio

**What it shows**

- **NAV chart** — a line of total portfolio value over time (like a bank balance chart for the model book).
- **Pipeline ribbon** — three steps: **Entries** (new trades waiting) → **Holdings** (what we hold now) → **Exits** (trades that should leave).
- **Masthead stats** — long vs short count, how much is invested vs cash, “as of” date.
- **Top contributors / detractors** — which positions helped or hurt performance most recently.
- **Risk snapshot** — volatility, comparison to S&P 500, best and worst months.
- **Holdings table** — every open position with score, size, profit, theme sleeve, and special chips (see below).

**How it helps**

- One screen answers: *“How are we doing, what do we own, and what is about to change?”*
- No jumping between Signals, spreadsheets, and old portfolio tabs.

---

### 6.2 Holdings table — the centre of the Overview

**Planned behaviours**

| Feature | What it means for a non-expert |
|---------|-------------------------------|
| **Sort by Score** | Best-looking signals float to the top. |
| **Group same asset** | All rows for Apple (from different recipes) visually grouped together. |
| **⊕ NEW SIGNAL chip** | “We already hold this asset, and a *new* buy signal just appeared on it.” |
| **◔ HELD chip** | “This is a new entry idea, but we already hold that asset elsewhere.” |
| **MULTI-SIG chip** | Multiple strategies agree on the same asset — informational only. |
| **Negative R:R styling** | Amber warning: this signal’s typical holding period may be “used up” — not an error, but worth review. |
| **Cross-function exit badge** | One strategy exited while another still holds — potential conflict. |
| **Click row → detail drawer** | Same detail popup as on the Signals page. |

**How it helps**

- Surfaces **duplicate exposure** (many strategies on one stock) before it becomes a silent concentration risk.
- Makes **entry vs exit timing** visible when strategies disagree on the same ticker.

---

### 6.3 New Entries and New Exits (Signals + Portfolio)

**What they are**

- **New Entries** — fresh buy/sell signals that could enter the portfolio if a slot is free.
- **New Exits** — positions that should leave (rule-based exit, risk/reward exhausted, or strategy conflict).

**How it helps**

- Portfolio and Signals stay in sync — the pipeline ribbon and the Signals menu read the **same API feeds**.
- Operators see the **flow** of the book: what is coming in and going out today.

---

### 6.4 Sizing & Allocation

**What it shows**

- Total portfolio size (e.g. $100M model notional).
- **Equity ceiling** — macro rules may say “only deploy 72% in stocks today; rest in cash.”
- Per-**sleeve** bars (US Tech, Commodities, etc.) — true weight vs maximum allowed.
- **Slots per sleeve** — e.g. “US Tech: 7/7 slots FULL — next signal waits” (planned under new sizing engine).
- Per-position **SIZE** in dollars.
- Scenario buttons: **NORMAL / STRESS / LOW VOL / MANUAL / AUTO** — preview what sizes *would* be under calmer or stressed macro settings (preview only; live book changes only when real macro rules change).

**How it helps**

- Answers: *“Are we over-concentrated? If stress worsens tomorrow, how much would we shrink?”*
- Stops nonsensical displays like “350% deployed” — weights should read as real percentages of the book.

---

### 6.5 Portfolio Risk

**What it shows**

- **Correlation matrix** — which theme buckets move together (if Tech and Semiconductors rise together, that is higher correlation).
- **Breach warnings** — pairs that are too correlated *and* too large combined.
- **Conviction summary** — how many positions are full-size (MAX), reduced, or flagged as “yield trap.”
- **Enter My Portfolio** — user can paste their own holdings and compare concentration to the model.

**How it helps**

- Catches “hidden duplication” — two sleeves that look different but behave like one big bet.
- Supports risk conversations without exporting to Excel.

---

### 6.6 Live P&L and conflict cards

**What it shows**

- Open positions with live profit/loss.
- **Conflict cards at the top** when one strategy’s exit clashes with another’s open position on the same asset — shows exit price/date and every surviving leg, plus an estimated natural exit date for each leg.

**How it helps**

- Conflicts are visible **before** someone manually discovers them in a CSV.
- Especially important for commodities and multi-strategy names.

---

### 6.7 Agent slide-in (Overwatch alerts)

**What it is**

- A side panel that can auto-open when the system detects macro or strategy warnings relevant to the page you are on.

**How it helps**

- Connects Portfolio to the **AI Analyst / Overwatch** work — e.g. “Combo C active — new long entries haircut” while you are on Portfolio.

*(Backend analyst APIs exist; Portfolio-specific `alerts.json` with `target_page` is still planned.)*

---

### 6.8 Backend-only principles (why APIs matter)

| Principle | Benefit |
|-----------|---------|
| Server computes all sizes and P&L | Change formula once on server; UI updates everywhere |
| `book_id` on every request | Cannot accidentally blend model and brokerage numbers |
| Holdings `size_usd` = Sizer `allocation_usd` | Overview and Sizing always agree |
| Negative R:R shown as negative | Honest picture when a signal is past its typical holding window |

---

## 7. How the pieces fit together (simple diagram)

```
  Nightly data jobs
        │
        ▼
  trade_store CSVs  ──►  FastAPI (portfolio + signals endpoints)
        │                        │
        │                        ▼
        │                 Nuxt Portfolio UI (read-only display)
        │
        ├── outstanding_signal  →  Holdings
        ├── new_signal          →  Entries
        ├── target_signal       →  Exits
        └── cross_function_conflicts.json  →  Live P&L conflict cards
```

**User journey example**

1. Open Portfolio → Overview (MODEL, ENHANCED).
2. See NAV chart rising; pipeline shows 2 new entries.
3. Holdings table shows Amazon with a ⊕ NEW SIGNAL chip — a second strategy also wants Amazon.
4. Click row → drawer shows scores, exit reference, siblings.
5. Switch to Sizing → confirm Amazon’s dollar size matches Overview.
6. Switch to Risk → check if Tech sleeve is near its ceiling.

---

## 8. Implementation status (as of 2026-07-22)

This section splits work into four buckets:

- **Implemented** — built and tested in the dev API (`chatbot-dev`).
- **Unblocked by Ahil research (Jul 2026)** — Ahil delivered NAV workbooks + consolidated report; backend can ingest or replay — not wired to API yet.
- **Unblocked but not yet implemented** — specs are clear enough to build; work not done yet (often frontend wiring or remaining backend pieces).
- **Blocked** — cannot build correctly until product/research decisions or other teams finish dependencies.

---

### 8.0 Ahil analysis deliverables (Jul 2026) — what changed

**Location:** [`ahil_analysis/`](ahil_analysis/)

| File | What it contains |
|------|------------------|
| [`MindWealth_Consolidated_Report.pdf`](ahil_analysis/MindWealth_Consolidated_Report.pdf) | Full axiom-compliant test hand-off: reconciliation waterfall, eviction (1C) validation, A1 four-book **proxy** decomposition, shorts-in-bears evidence, deliverables + remaining blockers |
| [`MindWealth_Ahil_NAV_FILLED_GATED_FIXED_DAILYDD.xlsx`](ahil_analysis/MindWealth_Ahil_NAV_FILLED_GATED_FIXED_DAILYDD.xlsx) | **Version B (MTM / all positions)** — monthly NAV Jan-24 → Jun-26, S&P benchmark monthly returns, daily active-signal count (N), drawdown episodes, CAGR **13.9%**, true daily max DD **−13.3%** |
| [`MindWealth_Ahil_NAV_FILLED_VersionA_GATED_FIXED_DAILYDD.xlsx`](ahil_analysis/MindWealth_Ahil_NAV_FILLED_VersionA_GATED_FIXED_DAILYDD.xlsx) | **Version A (closed trades only)** — same structure; CAGR **26.1%**, true daily max DD **−13.1%** |

**Upstream inputs (MindWealth core `~/MindWealth`):** per `Ahil_portfolio_page_docs_2.md`, Ahil's NAV engine consumes `trade_store/US/forward_testing/` (9 strategies, ~1,990 trade CSVs) and `data/stake.csv`. The Portfolio API today uses MindWealth_UI `trade_store` (VT long/short, outstanding signals) — aligned with `~/MindWealth/trade_store/virtual_trading_*.csv`. The **filled NAV workbooks are outputs** — they are not stored in the core repo; only in `ahil_analysis/`.

**Key research conclusions (from consolidated report):**

| Topic | Ahil's finding | Impact on Portfolio page |
|-------|----------------|--------------------------|
| **Starting notional** | Workbooks use **$10,000,000** opening NAV (Jan-24) | Strong evidence for Ask 1 — API still hardcodes $100M until Rohit signs off |
| **N (slot cap)** | Tests at **N=60**, **80**, **120**; N=60 eviction pick retains ~101% OOS edge | N=60 is the primary production candidate; Rohit formal sign-off still ideal |
| **Axiom 2 (rebalancing)** | Axiom-compliant engine: **hold original weight to exit**, no rebalance | Research direction **resolved** — API `/portfolio/nav` and D1 sizer should follow this |
| **A1 four-book attribution** | Proxy decomposition: BASE **13.41%** → ENHANCED **17.71%** CAGR (+4.3pp); SSI **+1.63pp**, Conviction **+2.15pp**, interaction **+0.52pp** | Shape of four-book toggle is validated; **real** SSI ceiling + conviction tiers from API still required |
| **1C eviction** | Eviction mode improves Sharpe vs chrono at N=60; ~40% underwater under all methods | Supports `exit_type=eviction` on exits API — wiring still on backend |
| **NAV time series** | **Monthly** closing NAV + benchmark + drawdown episodes filled; daily active-N series ~900 days | Unblocks Overview **monthly** chart and risk block formulas — not full daily NAV line yet |
| **Old headline numbers** | Averaging trade returns overstated Sharpe/CAGR; position-level truth is lower | Sets honest investor-facing expectations |

**Still blocked on Divyanshu (per Ahil's own deliverables section):**

- P3 point-in-time replay harness — trade inputs live in `~/MindWealth/trade_store/US/forward_testing/` (~1,990 CSVs); `nav_engine.py` not in core repo on this server
- Test 6/8 exact R:R (`compute_rr_to_nearest_support_stop` + no-clean-stop fallback)
- Wire **real** SSI ceiling + conviction tier feeds into A1 (replace proxy inputs)
- Per-regime daily bucket API (macro tests)
- Composite-score API **401** — Ahil used ledger-only scores; live API auth must work for production parity

---

### 8.1 Implemented ✅

#### Backend APIs (Divyanshu — dev branch)

| Item | Status | Notes |
|------|--------|-------|
| `GET /portfolio/holdings` | Done | MODEL + `book=enhanced` only; score, rank, size, siblings, multi_sig, rr_dynamic |
| `GET /portfolio/nav` | **Done (interim)** | Monthly series + vol/beta/benchmark; nav_engine plug-in; all MODEL books on nav |
| `GET /portfolio/sizer` + `/portfolio/sizing` | Done | Ceiling, sleeves (interim cluster engine), scenarios, P&L rows |
| `GET /portfolio/risk` | Done | Correlation matrix, breaches, **conviction_summary** |
| `POST /portfolio/risk/analyze` | Done | Compare user holdings to model |
| `GET /portfolio/risk/search` | Done | Ticker autocomplete |
| `GET /signals/entries` | Done | Ranked new-signal feed |
| `GET /signals/exits` | Done | Exit candidates (`signal` / `rr` types; not `eviction` yet) |
| `GET /signals/reports/portfolio-risk/latest` | Done | Conflict cards shape + `implied_natural_exit_date` |
| Book validation (`book_id`, `book`) | Done | Unsupported books return clear **422** errors |
| D2 fix — ETF/FX base size | Done | No more `$0 BLOCKED` for non-stock assets |
| `rr_dynamic` in API enrichment | Done | Exposed on signal/holdings-related payloads |
| Automated tests | Done | 56 tests passing (portfolio + signals) |

#### Documentation

| Item | Status |
|------|--------|
| `PORTFOLIO_API_HANDOFF.md` | API contract for frontend |
| `OPEN_QUESTIONS_FOR_ROHIT.md` | Five blocking decisions documented |
| `portfolio_implementation_log.md` | Technical build log for developers |
| `ahil_analysis/` | Ahil NAV workbooks + consolidated axiom report (Jul 2026) |

#### Frontend (Parth — partial)

| Item | Status |
|------|--------|
| v5 HTML mock | Done (design reference) |
| Live Nuxt wire-up to new endpoints | **Not done** — layout can proceed; data binding waiting on integration |

---

### 8.2 Unblocked by Ahil research — backend ingest not done yet 📂

Ahil delivered the data; the API does not serve it yet. These are the **next backend tasks** now that workbooks exist:

| Item | Layer | What’s needed |
|------|-------|----------------|
| **Monthly NAV + benchmark series** | Backend | **Done** — `src/portfolio_nav/` workbook ingest; nav_engine adapter ready |
| **Closed vs MTM toggle** | Backend | **Done** — `mtm[]` + `closed[]` in `/portfolio/nav` response |
| **Risk block (vol, beta, best/worst month)** | Backend | **Done** — computed from ingested monthly returns |
| **Four-book on `/portfolio/nav`** | Backend | **Partial** — all 4 books return 200; proxy attribution until nav_engine |
| **Four-book on holdings/sizing** | Backend | Still **422** except `enhanced` until D1 + nav_engine |
| **`exit_type=eviction`** | Backend | Wire 1C eviction rules validated in consolidated report |
| **Exact R:R (Test 6/8)** | Backend | Implement `compute_rr_to_nearest_support_stop` per Ahil blocker list |

---

### 8.3 Unblocked but still unimplemented ⏳

These **can** be built without waiting for Rohit’s remaining open questions — but are **not finished** yet.

| Item | Layer | What’s needed |
|------|-------|----------------|
| **Wire Overview holdings table** | Frontend | Call `/portfolio/holdings?book_id=model&book=enhanced` |
| **Wire Overview nav snapshot** | Frontend | Call `/portfolio/nav` for masthead / waterfall (chart waits on 8.2 ingest) |
| **Wire pipeline ribbon (Entries / Exits)** | Frontend | Call `/signals/entries` and `/signals/exits` |
| **Wire Sizing page to `/portfolio/sizing`** | Frontend | Replace mocks; scenario query params |
| **Wire Live P&L conflict cards** | Frontend | Call `/signals/reports/portfolio-risk/latest` |
| **Rename “Sized Allocations” → “Sizing & Allocation”** | Frontend | Copy sweep per spec |
| **Signals menu: New Entries / New Exits** | Frontend | Same APIs as Portfolio |
| **`exit_ref` column on Outstanding Signals** | Backend + Frontend | Needs fuller exit-reference string (partial backend today) |
| **`pnl_contribution_bps` on holdings** | Backend | Needs since-go-live NAV path from ingested series |
| **API docs sync** | Docs | `docs/api/services/portfolio/` pages for new endpoints |
| **Prod deploy** | Ops | Merge `chatbot-dev` → `chatbot-prod`, restart API |

---

### 8.4 Blocked 🚫

| Item | Why blocked | Who / what unblocks |
|------|-------------|---------------------|
| **Daily NAV chart (full line)** | Ahil delivered **monthly** closes + drawdown episodes, not daily NAV points for chart | Divyanshu: extend ingest or run live replay; P3 harness |
| **Four-book toggle (production numbers)** | Proxy attribution exists; real SSI ceiling + conviction tiers not wired | Divyanshu feeds + Rohit sign-off on proxy vs live |
| **BROKERAGE book** | IBKR Gateway plan in `ikbr_details.md`; account pending | Rohit account provision + Gateway on AWS |
| **PERSONAL book** | No save/load API for manual holdings | Product spec for persistence |
| **D1 slot sizing** | SLEEVES table not signed off; API notional still $100M vs Ahil **$10M** | Rohit Ask 1 & 4 (Ahil strongly supports $10M / N=60) |
| **Sleeve “slots FULL” line on Sizing** | Part of D1 | Rohit SLEEVES table |
| **True-weight risk breaches (D7)** | Must share one weight source with new sizer | D1 first |
| **`same_asset_siblings` scope final rule** | D4 says negative-only; UI spec says all rows — implemented as all-rows pending confirmation | Rohit Ask 5 |
| **`alerts.json` + `target_page` for Portfolio** | Agent slide-in contract incomplete | Rohit / analyst integration |
| **MANUAL / AUTO scenario behaviour on API** | MANUAL exists in old UI; API contract thin | Product clarification |
| **Regime-bucket daily series API** | Ahil tests need it | Divyanshu macro bucket endpoint |
| **Live composite-score parity** | Score API returned 401 in Ahil's run | Fix API auth for research ↔ prod alignment |

**Summary:** Roughly **55–60%** of the API surface is live for MODEL/enhanced. Ahil's Jul 2026 deliverables **partially unblock** NAV chart (monthly), four-book shape, Axiom 2, and N/notional — but **ingestion + real overlay feeds** remain. Brokerage, personal book, and D1 slot engine are still the largest product blockers.

---

## 9. Who does what

| Role | Responsibility |
|------|----------------|
| **Rohit** | Product decisions, open questions (N, notional, sleeves, IBKR owner) |
| **Divyanshu** | Backend APIs, sizing/risk engine, endpoints |
| **Parth** | Nuxt UI — layout, wire-up, responsive behaviour |
| **Ahil** | NAV workbooks + axiom report delivered (Jul 2026); four-book proxy; Divyanshu ingests + wires real feeds |

---

## 10. Glossary (quick reference)

| Term | Simple meaning |
|------|----------------|
| **Signal** | A suggested trade from an automated rule |
| **Position / holding** | A signal that is currently open |
| **Entry** | A new signal that could enter the portfolio |
| **Exit** | A signal or rule saying a position should close |
| **NAV** | Total portfolio value (like account balance) |
| **Sizer / sizing** | How many dollars each position gets |
| **Sleeve** | Theme bucket (e.g. US Tech) with a max weight |
| **Slot** | One position “seat” in the portfolio (max N positions) |
| **SSI** | Macro overlay that may reduce how much capital is deployed |
| **Conviction** | Company-quality overlay that changes size for single stocks |
| **R:R (reward-to-risk)** | How much upside is left vs downside to a stop |
| **Cross-function conflict** | One strategy exited an asset another still holds |
| **Book (MODEL / BROKERAGE / PERSONAL)** | Which portfolio notebook you are viewing |

---

## 11. One-paragraph summary

We are rebuilding the Portfolio page so anyone can see—on one screen—what the model holds, how large each position is, what might enter or exit, and where risks or strategy conflicts hide. All numbers come from the server, not the browser. The design has four main views (Overview, Sizing, Risk, Live P&L) and three separate books (model, brokerage, personal). **Backend work has delivered holdings, entries, exits, sizing, risk, conflict reporting, and a partial `/portfolio/nav` snapshot for the model “enhanced” book.** Ahil’s July 2026 workbooks (in `ahil_analysis/`) filled monthly NAV, benchmark returns, and four-book **proxy** attribution — the next step is API ingestion and wiring real SSI/conviction feeds. **Brokerage (IBKR), personal book, daily NAV chart, and D1 slot sizing** still need engineering + Rohit sign-off on $10M/N=60 and SLEEVES. The frontend can wire everything already live on the API while chart/four-book features roll out as ingest completes.

---

*For technical endpoint details see [`portfolio_implementation_log.md`](portfolio_implementation_log.md). For open product decisions see [`OPEN_QUESTIONS_FOR_ROHIT.md`](OPEN_QUESTIONS_FOR_ROHIT.md). For Ahil NAV data see [`ahil_analysis/`](ahil_analysis/).*
