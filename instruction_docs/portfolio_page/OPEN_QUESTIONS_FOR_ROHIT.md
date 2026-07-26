# Open Questions for Rohit — Portfolio API / UI Alignment

**Prepared:** 2026-07-20 · **Updated:** 2026-07-22 (Ahil `ahil_analysis/` deliverables)  
**Author context:** Divyanshu (portfolio backend engine + API, D1–D7)  
**Purpose:** Lock five blocking product decisions before implementing `/portfolio/nav`, `/portfolio/holdings`, `/portfolio/sizing`, and sibling enrichment.

> **Jul 2026 update:** Ahil delivered NAV workbooks + consolidated report in [`ahil_analysis/`](ahil_analysis/). **Ask 1** ($10M, N=60) and **Ask 2** (Axiom 2 hold-to-exit) are **partially answered** — see notes in each Ask below. Rohit formal sign-off still required where UI mock ($100M) conflicts with research ($10M).

**Related specs:**
- `15July_imp_spec_additions.md` — D1–D7 backend tasks
- `spec_15July.md` — unified Portfolio UI brief (Parth)
- `14July_axioms_and_specs.md` — Axioms 0–6
- `PORTFOLIO_API_HANDOFF.md` — API contract
- `Ahil_portfolio_page_docs.md` — Ahil Layer-1 research + NAV engine
- `MindWealth_Portfolio_Unified_v5.html` — authoritative UI mock (v5)
- `portfolio_sizer_v2_18June.md` — June cluster-budget sizer (legacy)

---

## Ask 1 — Production **N** and **notional** ($10M vs $100M)

> **Ahil update (Jul 2026):** Both filled NAV workbooks open at **$10,000,000** (Jan-24). Consolidated report tests **N=60** as primary (also 80, 120). Eviction at N=60 retains ~101% OOS edge. **Recommendation pending Rohit:** adopt $10M + N=60 for API/D1, or keep $100M UI mock for investor-facing display only.

### Why this blocks implementation

D1 sizing formula is `size = NAV/N × conviction × SSI`. Every dollar amount, slot size, sleeve weight %, and breach recommendation depends on both **N** (simultaneous position cap) and **starting NAV**. Current API hardcodes `$100M` in `api/services/portfolio_service.py` (`PORTFOLIO_NOTIONAL = 100_000_000`); specs disagree on both numbers.

### What each doc says

#### $100,000,000 (UI / API handoff)

| Source | Reference | Quote / detail |
|--------|-----------|----------------|
| `spec_15July.md` | L12 | Sizing header strip: *"$100,000,000 portfolio · equity ceiling · equities deployed · cash @ yield"* |
| `mindwealth_portfolio_v4.html` | L425, L660 | Mock uses `$100,000,000` portfolio, `$72M` deployed |
| `portfolio_sizer_v2_18June.md` | L94 | *"All UI, documentation, and client-facing output should now use **$100,000,000**"* |
| `PORTFOLIO_API_HANDOFF.md` | L65, L70 | Example nav `102450000` on ~$100M book; `position_limit: 24` |
| `15July_imp_spec_additions.md` | D7 L27 | Breach example on *"$100,000,000 portfolio"* |

#### $10,000,000 (Ahil research + v5 mock)

| Source | Reference | Quote / detail |
|--------|-----------|----------------|
| `Ahil_portfolio_page_docs.md` | L13, L29 | *"simulated **$10,000,000** equal-weight portfolio"*; table `Starting capital \| $10,000,000` |
| `MindWealth_Portfolio_Unified_v5.html` | L662–687 | All four `MODES` charts start at `$10.0M → $10.68M` |
| `15July_imp_spec_additions.md` | D1 L15 | Worked example: *"$10,000,000 portfolio, **N=60** → every position $166,667"* |

#### N — which value?

| N | Source | File / line |
|---|--------|-------------|
| **80** (optimal from Test 1A) | Ahil Sharpe-max pick | `Ahil_portfolio_page_docs.md` L228–240 |
| **60** | D1 example, A1/A2 attribution tests, v5 Sharpe label | `15July_imp_spec_additions.md` L7, L9, L15; v5 L325 *"N=60 · pending final candidate"* |
| **120** | A1 churn / attribution replay | `15July_imp_spec_additions.md` L7, L9 |
| **58** (current open count in mock) | v5 footer | `MindWealth_Portfolio_Unified_v5.html` L580 *"OPEN · 58"* |
| **24** | HANDOFF nav example | `PORTFOLIO_API_HANDOFF.md` L69–70 `position_count: 18`, `position_limit: 24` |

**Axiom 2** uses generic *"$100/N"* (percent language, not dollars) — `14July_axioms_and_specs.md` L23–24.

### What Divyanshu cannot do without a decision

- Set `PORTFOLIO_NOTIONAL` in API
- Compute `NAV/N` slot dollars
- Map sleeve ceilings to max slots (D1: US Tech 12% → 7 slots **at N=60**)
- Align API `position_limit` with UI masthead / v5 holdings (*"rank 58 of 58"* — v5 L891)

### Questions for Rohit

1. Is the **live MODEL book** notional **$100M** (UI) or **$10M** (Ahil/v5 research mock)?
2. Is production **N** fixed at **60**, **80**, or **dynamic** (= current open count, e.g. 58)?
3. Should Ahil's Test 1A result (**N=80**) override the July brief's **N=60** example for the API?
4. Is `position_limit` in `/portfolio/nav` a fixed cap (24? 60? 80?) or derived from open holdings?

---

## Ask 2 — **Rebalancing:** adopt Axiom 2 (hold slot) in API before Ahil workbook alignment?

> **Ahil update (Jul 2026):** Consolidated report axioms state **hold-original-weight to exit, no rebalance** (Axioms 1–2). Reconciliation waterfall quantifies the old rebalanced/averaged construction as the source of inflated Sharpe/CAGR. **Research direction resolved** — API and D1 sizer should follow Axiom 2. Workbook presentation notes still mention "1/N rebalanced on each new entry" for Layer-1 equal-weight labelling; production ENHANCED book should use position-level hold-orig per axiom-compliant engine.

### Why this blocks implementation

NAV series, per-position `size_usd`, P&L, and four-book attribution all depend on whether a position keeps its **original slot dollars** until exit, or gets **re-equalized** when others enter/exit. Ahil's current NAV engine and Divyanshu's future API may produce different numbers for the same trades.

### What each doc says

#### Axiom 2 — hold original weight, no rebalancing (`14July_axioms_and_specs.md`)

- **L23–24:** *"NEVER TRIM OR TOP UP A POSITION. HOLD ORIGINAL WEIGHT TO EXIT."*
- *"No reset-to-1/N on entry. No spreading a closed position's money across survivors."*
- *"(The NAV workbooks do both today.)"*
- Exited cash sits idle until next admitted signal takes the slot

#### Axiom 0 waterfall (`14July_axioms_and_specs.md` L14)

- Step 3 explicitly isolates rebalancing effect: *"hold-original-weight instead of any rebalancing"*

#### D1 — slot-based sizing (`15July_imp_spec_additions.md` L15)

- *"size = NAV/N × Conviction × SSI"*, sleeve admission slots
- Implies fixed slot at entry, not daily re-equalization

#### Ahil — current implementation rebalances (`Ahil_portfolio_page_docs.md`)

- **L173–174 (§5.2):** stat tests use *"daily-rebalanced equal-weight book"*
- **L268–270 (§8):** `nav_engine.py` *"rebalances all actives to 1/N on each new entry, and redistributes a closed position's value to survivors on exit"*
- **L352–354 (§11 caveat #1):** *"The newer brief specifies **no rebalancing — hold original $100/N to exit**. **Not yet switched**; a decision item."*

#### v5 four-book mock (`MindWealth_Portfolio_Unified_v5.html` L663, L688)

- BASE book: *"equal weight 1/N, fully deployed"* — doesn't specify rebalancing rule explicitly

### What Divyanshu cannot do without a decision

- Build `/portfolio/nav` daily MTM series that matches Ahil A1 attribution replay
- Ensure `size_usd` on `/holdings` stays stable between entries/exits (HANDOFF L241: must match sizer)
- Reconcile with Ahil until one construction rule is chosen

### Questions for Rohit

1. Confirm API must implement **Axiom 2** (hold slot to exit) even if Ahil's `nav_engine.py` has not switched yet?
2. Should Divyanshu **wait** for Ahil to update `nav_engine.py` before shipping NAV endpoints, or ship Axiom-2 API now and accept temporary mismatch with workbooks?
3. For **SSI overlay** (A1 L7): when ceiling drops, is the rule *uniform scale of all positions* (A1) without re-splitting across survivors — and does that count as "rebalancing" under Axiom 2?

---

## Ask 3 — **IBKR integration spec + owner**

### Why this blocks implementation

`book_id=brokerage` is required on multiple endpoints. Specs say IBKR is source of truth but provide **no technical integration details**. Divyanshu cannot build brokerage `/nav` or `/holdings` without knowing API, auth, and field mapping.

### What each doc says

#### Frontend / product (`spec_15July.md`)

- **L25:** *"**BROKERAGE** — the real Interactive Brokers account. US-listed, USD-denominated only… **IBKR is the source of truth** for this book: NAV, positions, and P&L come **directly from the IBKR API**. The frontend **never computes** anything for this book."*
- **L29:** *"every endpoint takes a `book_id` parameter (`model \| brokerage \| personal`)"* — three **separate data-fetch paths**
- **L33:** `/portfolio/nav?book_id=model|brokerage|personal`
- **L36:** Brokerage gets simpler Overview + Live P&L only (no Sizing / Portfolio Risk)

#### API handoff (`PORTFOLIO_API_HANDOFF.md`)

- **L10:** Book IDs `model | brokerage | personal`
- **L34:** *"Brokerage values must come from **IBKR/backend** source of truth."*
- **L167:** *"Brokerage NAV, holdings value, prices, and P&L must **match IBKR**."*
- **L698 (DoD):** *"Brokerage NAV, holdings, prices, shares, market value, and P&L come from **IBKR**."*

#### Link to MODEL BASE book (`15July_imp_spec_additions.md` A1 L7)

- *"the **BASE book is the one the Interactive Brokers API will connect to** — it is the first-class citizen."*
- Unclear if IBKR feeds **upper-level `book_id=brokerage`** only, or also MODEL `book=base` valuation toggle

#### Ahil doc (`Ahil_portfolio_page_docs.md` L35)

- IBKR mentioned only for **cost model** (15 bps round trip) — not live API

#### v5 mock

- Only **MODEL BOOK** toggle mocked (`MindWealth_Portfolio_Unified_v5.html` L303) — no brokerage UI wireframe

### What is completely missing from all docs

- IBKR API type (Client Portal, TWS, Flex Query, etc.)
- Account ID / credentials / host setup
- Field mapping: IBKR position → HANDOFF holdings shape (`shares`, `market_value`, `pnl_usd`, etc.)
- Sync cadence (real-time vs EOD)
- Error handling when IBKR unavailable
- **Owner:** Divyanshu vs Ahil vs ops

### Questions for Rohit

1. Who owns IBKR connector build — **Divyanshu**, **Ahil**, or external?
2. Which IBKR API and account should we target first?
3. Does IBKR feed **`book_id=brokerage`** only, or also MODEL **`book=base`** (A1 L7)?
4. Is brokerage **in scope for v1 API**, or can Divyanshu ship MODEL-only first with `book_id=brokerage` returning 501/422 until spec exists?
5. Any existing IBKR credentials / sandbox on the server?

### Status (2026-07-22) — explicitly deferred, no code this pass

Question 4's fallback is what the API implements today and continues to implement:
`book_id=brokerage` returns **422** on every endpoint (`api/services/portfolio_book.py::BookUnavailableError`,
detail: *"IBKR integration is pending product spec (Phase 8)."*). PERSONAL was unblocked this
pass (CRUD + NAV/holdings, see Phase 7 in `mindwealth_ui_job_status.md`) — BROKERAGE remains the
only book still gated, purely on questions 1–5 above (no IBKR API type, credentials, or owner
decided). Nothing to build until Rohit answers; revisit this section, not the code, when he does.

---

## Ask 4 — Confirm v5 **`SLEEVES`** table is production sleeve/slot source?

### Why this blocks implementation

D1 replaces old cluster-% engine with **sleeve ceilings + admission slots**. `/portfolio/sizing` must return `true weight`, `ceiling`, `slots used/available` per sleeve (D4 L21, `spec_15July.md` L33, L37). Divyanshu needs one authoritative table — v5 JS, June `CLUSTER_BUDGETS`, or something new.

### What each doc says

#### D1 slot method (`15July_imp_spec_additions.md` L15)

- US Tech example only: ceiling **12%** → **max 7 slots** at N=60
- 8th US Tech signal **waits** — not resized, not blocked to $0
- Vocabulary: **"sleeve"** for budgets; **"cluster"** for correlation only (D3 L19)

#### D4 endpoint requirement (`15July_imp_spec_additions.md` L21)

- `/portfolio/sizing` → *"sleeve aggregates: true weight, ceiling, **slots used/available**"*

#### `spec_15July.md`

- **L37:** *"true-weight sleeve bars vs ceilings… a **slots line per sleeve** with a **FULL** state"*

#### v5 `SLEEVES` constant (`MindWealth_Portfolio_Unified_v5.html` L918–920, L930–938)

```javascript
// [name, deployed%, ceiling%, slots_used]
['Global risk-on',16.7,18,10], ['US Tech',11.7,12,7], ['Financials',10.0,12,6], ...
```

- Slot line: *"7/7 SLOTS · FULL — NEXT SIGNAL WAITS"* (L937–938)
- Footer L581: *"**ALL NUMBERS ILLUSTRATIVE** UNLESS TAGGED"*
- L597: *"**NZ Core sleeve excluded** from overlay math (fixed allocation, outside ceiling)"*

#### June legacy table (`portfolio_sizer_v2_18June.md` L268–278)

- Old `CLUSTER_BUDGETS`: `global_risk_on: 18%, 3 signals max`, etc.
- **L87–89:** Stress/Low Vol tables **"need to be confirmed"** — *"Action for **Ahil**"*
- Superseded in intent by D1 but still only complete cluster list in repo

#### Current API (`api/services/portfolio_service.py`)

- Different cluster names/budgets (9 clusters, % of deployed cap) — not D1 slot model

#### D7 (`15July_imp_spec_additions.md` L27)

- Example: US Tech **11.7%** true weight vs **12%** ceiling — matches v5 `SLEEVES` row

### Gaps in v5 table vs D1

- v5 has 9 sleeves; June doc had more (incl. `nz_local`, `em_asia`, etc.)
- NZ Core exclusion (v5 L597) not in `SLEEVES` array
- Stress scenario: v5 `SCEN` L921 uses `k=0.625` (50% ceiling) — differs from v4's 58% and June stress notes
- Slot max formula in v5: `Math.floor(sl[2]*k/1.67)` (L934) — ties to 1.67% = 100/60, but N not locked

### Questions for Rohit

1. Is the v5 `SLEEVES` array (L918–920) the **signed-off production table**, or illustrative only?
2. Please publish **complete sleeve list** including NZ Core rule (v5 L597) and any excluded sleeves.
3. Confirm **max slots per sleeve** formula: `floor(sleeve_ceiling_pct / (100/N))` as in D1 US Tech example?
4. Provide **STRESS / LOW VOL** sleeve ceilings (Ahil confirm still open per `portfolio_sizer_v2_18June.md` L87–89).
5. Should June `CLUSTER_BUDGETS` / `CLUSTER_MAP` be **retired** entirely for sizing (kept only for correlation risk)?

---

## Ask 5 — **`same_asset_siblings`:** does v5 rule (all rows) supersede D4 (negative-only)?

### Why this blocks implementation

`/portfolio/holdings` must include `same_asset_siblings[]`. UI uses it for **⊕ NEW SIGNAL** and **◔ HELD** chips on **every** relevant row (v5), but July D4 says populate **only when R:R negative**. Different payloads → different frontend behavior.

### What each doc says

#### D4 — negative R:R only (`15July_imp_spec_additions.md` L21)

- *"**whenever a position's dynamic Reward-to-Risk is negative**, include a `same_asset_siblings` array — every other live or recent signal on the same asset with its function, interval, backtested average hold days, days elapsed, and dynamic Reward-to-Risk"*

#### D5 — rationale for negative case (`15July_imp_spec_additions.md` L23)

- When R:R negative → check siblings; longer hold on another function/interval may mean scope remains on asset
- Surfaces exit/eviction candidates (Ahil Tests 6/8)

#### `spec_15July.md` L33 (July frontend brief)

- *"`same_asset_siblings` array (**populates for every position and signal, both directions** — drives the chips in section 4)"*

#### `spec_15July.md` L35 (Overview holdings behavior)

- *"rows gain a **⊕ NEW SIGNAL** chip when a fresh signal exists on a held asset, and a **◔ HELD** chip when a new entry's asset is already held — **both from `same_asset_siblings`**"*

#### v5 DEV NOTES — explicit override (`MindWealth_Portfolio_Unified_v5.html` L601)

- *"`same_asset_siblings` now populates for **ALL rows both directions** (drives ⊕ NEW / ◔ HELD chips)"*

#### v5 holdings mock (`MindWealth_Portfolio_Unified_v5.html` L806–814, L826)

- AMZN row 1: `rr:-0.55`, `chipNew:true`, `sib:` NEW same-direction signal text
- AMZN row 2: `rr:2.9`, `chipHeld:true`, `sib:` Same asset already HELD text
- CSCO: negative R:R + sibling with longer hold (scope remains)
- ETH-USD: negative R:R, `sib:` no other live signals

#### HANDOFF shape (`PORTFOLIO_API_HANDOFF.md` L208–217, L243)

- Example includes `"relationship": "new_signal"`
- Rule: *"must include both `new_signal` and `already_held` relationships **where applicable**"* — doesn't say "only when R:R negative"

#### v5 negative R:R semantics (L612–615)

- Negative R:R = reward exhausted; drawer shows SAME-ASSET CHECK — but chips need siblings on **positive-R:R rows too** (AMZN TRENDPULSE L811–814)

### What Divyanshu cannot do without a decision

- Implement conditional vs universal sibling enrichment in holdings pipeline
- Power Signals page `exit_ref` + Outstanding column consistently
- Match Parth's chip logic in v5

### Questions for Rohit

1. Confirm **v5 L601 supersedes D4 L21**: populate `same_asset_siblings` on **every** holding row where siblings exist, not only when `rr_dynamic < 0`?
2. Required **`relationship`** values: `new_signal` | `already_held` (HANDOFF L215, L243) — any others?
3. For rows with **no siblings**, return `[]` or omit field?
4. Should siblings include **recent closed** signals or **live + recent only** (D4 says "live or recent")?
5. Does **`multi_sig[]`** (v5 L601, HANDOFF L218–227) stay separate from `same_asset_siblings`? (v5 treats MULTI-SIG as agreeing signals on same asset — informational only)

---

## Summary table

| # | Decision needed | Key conflicting files |
|---|-----------------|----------------------|
| 1 | Notional + N | `spec_15July.md` L12 ($100M) vs `Ahil_portfolio_page_docs.md` L29 ($10M) vs v5 L580 (58 open) vs Ahil L240 (N=80) |
| 2 | Rebalancing rule | `14July_axioms_and_specs.md` L23 vs `Ahil_portfolio_page_docs.md` L352–354 |
| 3 | IBKR spec + owner | `spec_15July.md` L25 vs no technical doc anywhere |
| 4 | Sleeve/slot table | v5 L918–920 (illustrative) vs D1 L15 (one example) vs `portfolio_sizer_v2_18June.md` L268–278 (legacy) |
| 5 | `same_asset_siblings` scope | `15July_imp_spec_additions.md` D4 L21 vs `spec_15July.md` L33/L35 vs v5 L601 |

---

## Suggested resolution order (after Rohit answers)

1. Lock **N + notional** → enables slot dollar math
2. Lock **rebalancing rule** → enables NAV + holdings `size_usd`
3. Lock **SLEEVES table** → enables `/portfolio/sizing`
4. Lock **siblings scope** → enables holdings enrichment + UI chips
5. IBKR can ship later if MODEL-only v1 is acceptable
