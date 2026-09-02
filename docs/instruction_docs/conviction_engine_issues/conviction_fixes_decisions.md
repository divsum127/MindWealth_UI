# Conviction Engine Fixes v2 — Decisions Log

Source docs: [Divyanshu_Business_Type_Reply 30 July_conviction doubts.pdf](Divyanshu_Business_Type_Reply%2030%20July_conviction%20doubts.pdf)
(Rohit's answers to our 11 open questions, plus a live-dashboard bug report),
[FS_Slice_Followup_Divyanshu.docx.pdf](FS_Slice_Followup_Divyanshu.docx.pdf) (FS-score
slice spec + 2 corrections to the 30 July reply), [engine_layers_spec.html](engine_layers_spec.html)
(illustrative UI mock), [Conviction_Engine_Consolidated_Note_Divyanshu_2026-07-28.docx](Conviction_Engine_Consolidated_Note_Divyanshu_2026-07-28.docx)
(original 28 July note). Supersedes [conviction_fixes_open_questions.md](conviction_fixes_open_questions.md)
now that every question there has an answer.

This log records what was decided, why, and every implementation-level micro-decision
made while building it — for the next developer to understand the reasoning without
re-reading all four source documents.

---

## 1. Rohit's 11 answers (30 July reply) — summarized

**Q1 — How much business-type work do we build?** Build `bank` and `high_margin_hardware`
fully. Insurers and deep-value get `coverage_incomplete` only, revisit later ("post this
project"). REITs and biotech dropped entirely — REIT has no interest from Rohit; the only
live biotech example (`IBB`) is an ETF, caught by the existing asset-type gate before
business-type logic ever runs, so zero code needed. Banks don't map onto any of the 4
existing type substitutions (no FCF the same way, no EV/Revenue anyone uses, "debt" is
deposits) — full parallel calibration given (margin_quality → efficiency ratio,
balance_sheet → equity/assets, OEY → net income/market cap, WACC = 9%, yield-trap +2pp).
*Superseded in part* — see the "important supersession" below re: the flat Price/Book
valuation-tax table given in this answer.

**Q2 — Margin cutoff for `high_margin_hardware`?** 40% trailing TTM net margin, recomputed
every quarterly `full_recalculation` (not cached/static — margin can cross the line
between quarters). G2 dropped as a competitive-moat source for hardware/semi names (it
measures software UX satisfaction, not chip competitiveness).

**Q3 — Should the G2 exclusion follow the new bucket or the raw sector?** Raw sector.
A 25%-margin chip company is just as poorly served by G2 as a 55%-margin one. Keyed off
sector/industry tokens directly, at the same point `detect_business_type()` reads them —
independent of whether the name clears the 40% `high_margin_hardware` threshold.

**Q4 — What happens to the verdict when coverage is incomplete?** A third hard gate,
distinct from `CANCEL BUY`/`FS=weak`. New verdict string `"COVERAGE INCOMPLETE"` — same
0% sizing, different label, because "we evaluated this and said no" and "we haven't built
a reliable way to score this business type yet" are different messages. Fires whenever
`detect_business_type()` can't map a ticker to one of the 6 calibrated types, instead of
silently falling through to `compounder`/`cyclical`. Needs a new color/label case on
Parth's Vue dashboard (flagged, not built here — out of this repo's scope).

**Q5 — What counts as a buyback suspension?** Scaled, not binary — standalone penalty
flag, structurally separate from `mgmt_capital_allocation` (same pattern as Altman Z being
its own flag rather than folded into `balance_sheet`, to avoid double-counting). Trigger
requires prior-period buyback spend > $100M. Tiered by period-over-period decline:
0-25% → no trigger; 25-50% → -1; 50-75% → -2; 75-100% (near/full) → -3. Spend-based,
distinct from the existing share-count-based buyback vote inside `fd_direction` (that vote
keeps running unchanged).

**Q6 — What size dividend cut triggers a recalc?** Same tier structure as Q5, applied to
declared annual DPS decline vs. the prior declared annual rate. If both flags fire in the
same quarter, cap the *combined* penalty at -4 total, not -6.

**Q7 — Where does the revenue-miss trigger get its expected number?** yfinance's analyst
revenue-estimate field — same pattern already used for the EPS-estimate `fd_direction`
vote, zero new data source. Trigger `full_recalculation()` on a >10% miss vs. consensus.
No new scoring dimension — `growth_trajectory` and the `fd_direction` Revenue vote already
pick up the consequence once recalculation reruns.

**Q8 — Does the supply-constraint flag move the score?** No — information only. Lands in
the rationale string the same way TAM sourcing citations already do.

**Q9 — What tax rate for adjusted EPS?** The company's own trailing effective tax rate
(trailing-4Q tax provision ÷ trailing-4Q pretax income), not a flat 21%/25% — both figures
already available in the same `income_stmt` pull made for every other BQ dimension.

**Q10 — Should adjusted PE always replace raw PE?** Materiality gate: substitute only when
one-off items exceed 5% of trailing net income (Divyanshu's own suggestion, confirmed).
Otherwise raw PE stays in the percentile calc untouched.

**Q11 — How much of the universe gets rerun?** Cheaper two-step approach: (1) a
classification-only pass — just the `detect_business_type()` sector/industry read, no
full financials pull — across the whole ~193-ticker universe, same cost profile as the
existing daily runner; (2) diff against each ticker's currently-stored `business_type`,
only queue tickers that actually flip into `bank`/`high_margin_hardware`/
`coverage_incomplete` for a full `full_recalculation()`. Same migration discipline as the
PE-history rollout.

---

## 2. Important supersession — P/TBV-vs-ROE over the flat Price/Book table

The 30 July reply's Q1 answer gave a simple flat Price/Book tier table for the bank
valuation-tax substitution (Tier 1 ≥1.5x, Tier 2 ≥2.0x, Tier 3 ≥2.5x, floor ≥3.0x). The
follow-up FS-slice doc **explicitly supersedes this**: *"this supersedes the simpler P/B
tiers I gave in yesterday's Q1 answer — use the consolidated note's method, it's the more
rigorous one."* Built the **P/TBV vs. ROE excess-return model**
(`fair P/TBV = (ROE − g) / (Cost of Equity − g)`, `g = 3%` sustainable growth,
`Cost of Equity = 9%`) from the original 28 July note's Section 5.7 instead — see
`bank_valuation.py`. The flat table was never built.

---

## 3. Two corrections from the FS-slice follow-up (both were actually already-correct specs)

1. **`growth_multiple_fragility`**: Rohit initially flagged this as unspecced in the 30
   July reply, then corrected himself — Section 5.3 of the consolidated note gives it as
   `EV/fwd rev ≥ 4× AND revenue_growth ≥ 15% → -2.0`, universal across business types.
   The pre-fix code had the wrong condition (`ev_rev >= tiers[-1] AND revenue_growth < 5%
   → -1.0`) — fixed to match spec, not a design change.
2. **The -5 floor**: also initially flagged as internally inconsistent, then corrected —
   the rule is universal (`ev_rev ≥ 4× → entry_multiple floored at -5`, any business
   type), **except** `high_margin_hardware`, which is exempt (the floor's rationale —
   "execution and multiple maintenance must both go right" — doesn't hold when the
   multiple is backed by current profit rather than a growth story). The pre-fix code had
   a per-type `min_penalty_trigger` list instead of this universal rule — replaced.

---

## 4. FS-score daily valuation slice — built from scratch, per the follow-up spec

The original spec only ever gave `fs_quality_base = 50 + (BQ_RAW × 2.5)` plus one worked
example (TELUS) — no general point-value table for the "daily valuation slice"
(PE percentile / OEY / EV-fwd-rev) existed anywhere before this pass. Two design
constraints from the follow-up, both honored in `fs_score_breakdown()` (`scoring.py`):

- **Symmetric, not penalty-only** — valuation tax is always ≤0, but the slice must not
  be, or a cheap high-quality business gets pushed into a lower FS class than it deserves.
- **OEY direction is inverted vs. PE/EV-rev** — high OEY = cheap = positive; low PE
  percentile / low EV-rev = cheap = positive. Easy to get backwards, called out explicitly
  in code comments where this could bite.

Point tables (self-calibrating, one table for all business types except the bank/hardware
row substitutions):

| PE percentile | Points | OEY vs. type threshold | Points | EV/fwd-rev tier | Points |
|---|---|---|---|---|---|
| < 20th | +10 | ≥ 1.5× "strong" | +10 | Below Tier 1 | +10 |
| 20th–40th | +5 | ≥ "strong" | +5 | At Tier 1 | +5 |
| 40th–60th | 0 | between strong/expensive | 0 | At Tier 2 | 0 |
| 60th–80th | −5 | ≤ "expensive" | −5 | At Tier 3 | −5 |
| > 80th | −10 | ≤ 0.5× "expensive" | −10 | Tier 4+ | −10 |

For `bank` tickers, the EV/fwd-rev row is replaced by the same P/TBV-vs-ROE model used for
the valuation-tax substitution (item 2), not a separate table. For `high_margin_hardware`,
EV/forward-EBITDA tiers substitute for EV/fwd-rev.

**Worked regression case (CRM, from the follow-up doc, used as the pinned test in
`tests/`)**: BQ +8 → `fs_quality_base` 70. PE 91st pctile → −10. OEY 1.8% (saas
strong=5%/expensive=1%, between the two) → 0. EV/rev 9.2× (saas Tier 3) → −5. Slice total
−15 → `fs_score` 55 → `moderate_high` → **no cap** → conviction stays +3 → `REDUCED BUY`.
This is the exact case that motivated the CRM bug investigation below.

---

## 5. CRM live-dashboard bug — investigation outcome

Reported symptom: displayed conviction `+1 / CANCEL BUY`, but the drawer showed
`BQ +8, tax −5 → +3` (which should be `REDUCED BUY`). Rohit's hypothesis: either
`fs_class` was reading as `weak` somewhere in the cap-time pipeline while the drawer
pulled a different (possibly stale) `fs_class`, or the cap logic was hard-applying the
weak-tier formula regardless of the real class.

**Root cause, confirmed by tracing the live `CRM.json` record through the rebuilt
pipeline**: before this pass, `calculate_fs_score()` used ad hoc thresholds that didn't
match any specced table (there wasn't one to match) — it's entirely plausible that ad hoc
formula produced a `weak`/`moderate_low` classification for a case the corrected formula
(item 4 above) classifies as `moderate_high`, triggering `apply_fs_cap()`'s weak-tier cap
(`min(conviction, +1)` on a long signal) incorrectly. Separately, and just as importantly:
`fs_score`/`fs_class`/`valuation_tax` were previously three independently-settable fields
on the record with no structural guarantee they were derived from the same breakdown
computation at the same time — exactly the class of bug that can make a "drawer" view and
a "cap-time" view diverge if one was written by a different code path or an earlier
`daily_update()` call than the other.

**Fix, structural not just numerical**: `fs_score_breakdown()` now returns
`{"components": {...}, "total": ...}` in one call; `daily_update()` sets
`record["fs_cap_breakdown"] = fs_score_breakdown(record)` and
`record["fs_score"] = record["fs_cap_breakdown"]["total"]` from that single call result —
same pattern already used for `valuation_tax_breakdown`/`valuation_tax`. `modify_signal()`
always calls `daily_update(..., save=False)` immediately before reading `fs_class` for
`apply_fs_cap()`, so the class used at cap-time is always the one just computed, never a
separately-cached or differently-timed value. Traced against the live CRM record
(`.venv/bin/python3` REPL session, 2026-08-02) post-fix: `fs_score` 90.0 (post-rebuild
formula, current live data — different from the follow-up doc's illustrative 55, since
market data moves daily), `fs_class` `strong`, `conviction_score` 5.0, identical between
the persisted record and a fresh `daily_update(save=False)` recompute inside
`modify_signal()` — no divergence. The illustrative follow-up-doc numbers (BQ+8/tax-5,
fs_score 55) are pinned as an explicit synthetic-record regression test instead of relying
on live data that changes daily.

---

## 6. Macrotrends Tier-1 skip (item 16) — why the follow-up's Tier 1 was not built

The follow-up's 3-tier PE-history plan for non-US tickers listed Tier 1 as "retry
`fetch_pe_history_macrotrends()` for every ticker, drop the US-only gate, let it fail
naturally." This was **not built** — Macrotrends was already confirmed dead as of
2026-07-24 (documented in `pe_history_fmp.py`'s own docstring): it sits behind an
unbeatable Cloudflare Turnstile challenge, which is *why* FMP replaced it as the first
fallback in the first place. Re-attempting a call known to hang/fail for every non-US
ticker would add latency for zero benefit. Tiers 2 and 3 (the actually-new, actually-sound
parts) were built instead:

- **Tier 2**: `reconstruct_quarterly_eps_from_net_income()` (`pe_history_core.py`) — when
  a ticker's `quarterly_income_stmt` has no direct `"Diluted EPS"`/`"Basic EPS"` row at
  all (common for many non-US filers, not just a depth problem), reconstruct
  `Net Income ÷ Diluted-or-Basic Average Shares` per quarter across the full available
  window and feed that into the same `compute_pe_history()` machinery every other source
  uses. This is the gap that mattered in practice — the pre-existing code already ran
  `compute_pe_history()` against whatever EPS row it found, for every ticker regardless of
  market, but silently produced *nothing* (`pe_20y_array` unset, no `pe_history_thin` flag
  even) when neither EPS row existed.
- **Tier 3**: `pe_history_thin=True` + `pe_history_years` — already built in the prior
  session, confirmed still correct and left unchanged.

---

## 7. "Tavela" — open item, not resolved, interim proposal recorded

Rohit's note asks whether to "Use Tavela?" for CEO-tenure and insider-ownership sourcing
for non-US names (WIPRO.NS, BPCL.NS, PERSISTENT.NS, 005930.KS, 000660.KS) where DEF14A
(US) and SEC EDGAR/SEDI (US/Canada) don't apply. **This was not resolved** — there isn't
enough information to determine whether "Tavela" is a specific data vendor, a typo for
another product, or something else, and no code was built against an unverified guess.

**Interim proposal, recorded as a decision rather than a blocker**: reuse the existing
Claude web-search agent pattern (already used for `ceo_quality`/`competitive_moat`/
`macro_tailwind`) for these two dimensions in non-US markets too, since no structured
filing API covers them today. Not implemented in this pass (out of the explicit 22-item
scope Rohit signed off on) — flagged here so it isn't lost, and so the next developer
knows to ask Rohit directly what "Tavela" refers to before building anything named after
it.

---

## 8. Implementation-level micro-decisions

These are choices made during implementation that weren't fully pinned down by either
source document — recorded so the next developer knows they were deliberate, not
oversights.

- **Bank detection keyword list** (`scoring.py` `BANK_SECTOR_TOKEN`/`BANK_INDUSTRY_TOKENS`):
  `sector == "financial services"` (case-insensitive substring match) AND `industry`
  contains `"bank"` or `"banks"`. This deliberately excludes insurers
  (`INSURER_INDUSTRY_TOKENS = ("insurance",)`, routed to `coverage_incomplete` instead),
  asset managers, and capital-markets firms that also sit in "Financial Services" but
  aren't banks — Rohit's spec named "Commercial/Regional/Diversified Banks" GICS
  sub-industries specifically.
- **Hardware/semiconductor sector token list** (`HARDWARE_SECTOR_TOKENS`):
  `semiconductor`, `hardware`, `electronic equipment`, `computer hardware`,
  `communication equipment` — broad enough to catch yfinance's actual `sector`/`industry`
  string variants without false-positiving on adjacent tech categories (software,
  internet). Used for both the `high_margin_hardware` business-type test (gated
  additionally on the 40% margin) and the G2-exclusion source-hygiene fix (item 6,
  ungated on margin) via the shared `is_hardware_or_semiconductor_sector()` helper.
- **Adjusted-EPS tax-rate fallback edge case**: flat 21% only fires when trailing pretax
  income is zero, negative, or missing (documented in `adjusted_eps.py` as "not a live-data
  gap" — it's a real edge case for loss-making companies where an effective-tax-rate ratio
  is meaningless, not a workaround for missing data). Also guards against a computed rate
  outside `[0%, 60%]` (data-quality sanity bound) falling back to the same flat rate.
- **`coverage_incomplete` precedence vs. `yield_trap`**: checked *before* yield_trap in
  `verdict_for_buy`/`verdict_for_sell`, since an uncalibrated business type means the
  yield-trap market threshold itself may not be meaningful for that ticker either — no
  explicit ordering given by Rohit, this was the most defensible default.
- **`buyback_suspension`/`dividend_cut`/`revenue_miss` recalc triggers are surfaced, not
  auto-fired**: these flags are computed and stored at `full_recalculation` time, then
  re-surfaced by `run_daily_universe()`'s alert map on every subsequent daily pass (as
  `*_needs_recalc` flags) for manual review/queueing — matching the precedent already set
  for `pe_history_insufficient`, rather than having the lightweight daily pass
  automatically kick off an expensive full re-fetch. Rohit's spec says these should
  "serve as new full_recalculation auto-triggers" but doesn't specify the *mechanism*
  (immediate vs. queued); queued-for-review was chosen to avoid an unbounded fan-out of
  expensive full pulls triggered by a cheap daily pass.
- **Deal-delay agent auto-populates flags, but never overrides an explicit human override**:
  `compute_deal_delay_agent()`'s result only sets `manual_overrides["deal_delay_flag"]` /
  `["supply_constraint_flag"]` when that key isn't already present in `manual_overrides` —
  a human-set override always wins over the agent's own confidence-gated finding.
- **TAM three-tier sourcing threading**: Tier 1 (SEC XBRL revenue backlog,
  `tam_sourcing.py`) is fetched mechanically first and passed into the Tier-2/3 agent
  prompt as context, not treated as a fully independent dimension — for companies that
  don't publish a TAM figure (the note's own GOOGL example), the backlog is the best
  available structured demand proxy, and threading it into the prompt lets the agent use
  it as a fallback basis rather than leaving the whole dimension blank.
- **`revenue_backlog_detail`/`independent_tam_usd` are additive metadata on
  `reinvestment_runway_detail`**, not new top-level record fields — kept the existing
  `manual_overrides["reinvestment_runway_detail"]` storage location so no schema/API
  change was needed to expose the richer three-tier data; UI transparency
  (`conviction_engine_page.py`) reads the nested fields directly.

---

## 9. Still genuinely open / deferred (not built this pass)

- **Multi-segment tie-break rule** — which `business_type` wins when a company spans two
  GICS buckets. No rule given by either source doc; documented as a known gap.
- **CEO tenure / insider ownership sourcing for non-US names** — see "Tavela" above.
- **Insurer and deep-value business types** — `coverage_incomplete` flag only, no real
  valuation module, per Rohit's explicit "post this project" framing.
- **REIT and biotech** — dropped entirely, no code, per Rohit's explicit direction.
- **Parth/Vue dashboard items** (flagged, not built — separate frontend repo): new
  `COVERAGE INCOMPLETE` color/label case; stale sidebar copy ("7 auto + 8 manual" should
  say all 15 auto); Yield-Traps panel count-vs-list mismatch (now fixable on his side —
  the API/record now exposes `yield_trap_breakdown.fired` vs. `.watching` and
  `run_daily_universe()`'s alert map emits a distinct `yield_trap_watching` flag);
  Business Types panel "Unknown · 1" (now the live test case for the `coverage_incomplete`
  gate); the three Engine Layers click-through panels (Valuation Tax / FS Cap / Yield
  Trap) — the row-level breakdown data (`valuation_tax_breakdown`, `fs_cap_breakdown`,
  `yield_trap_breakdown`) is now on every record and returned by
  `GET /conviction/tickers/{ticker}`, so Parth has what he needs to build the click-through
  UI shown in `engine_layers_spec.html`; this repo does not touch the Nuxt/Vue frontend.
