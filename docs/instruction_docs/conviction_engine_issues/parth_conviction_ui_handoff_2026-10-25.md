# Conviction page — Nuxt changes for Parth (2026-10-25)

Backend for all of these is on dev API `:8507` (uncommitted on `chatbot-dev` as of 2026-10-25).
Repo: `/home/ubuntu/MindwealthUI_Vue`. Sheet: `mindwealth todos` → tab `conviction` (row = CE + 1).

## 1. Report-only wording (CE-11) — Rohit, WhatsApp 28 Sep

> "sizes (75%/40%/0%) and… 'BUY cancelled regardless of quant signal'. Your 14 Sept standing
> instruction was report-only until Ahil shows value… header says 'v5'… '15 dims · 7 auto + 8
> manual': what is manual?"

Rohit 26 Aug: "Nothing should gate the surfaces or the payload on the Conviction Engine until
Ahil has shown it improves portfolio results."

| File:line | Now | Change to |
|---|---|---|
| `pages/conviction/index.vue:13` | "Dividend yield exceeds threshold — BUY cancelled regardless of quant signal." | "Dividend yield exceeds threshold — the engine would cancel this BUY (report only; quant signal unchanged)." |
| `components/conviction/ConvictionDepthPanel.vue:37` | "Yield trap active — BUY cancelled. No override possible." | "Yield trap active — engine verdict CANCEL BUY (report only)." |
| `pages/index.vue:71` | "Modifies position sizing per signal." | "Reports a conviction verdict per signal (not applied to sizing until validated)." |
| `constants/regime-strip.ts:387`, `pages/index.vue:24`, `pages/index.vue:69` | "v5" | "v6" (the live engine is v6; there is no v6 document — it exists only in code) |
| `constants/terminal-configs.ts:204` | "BQ Score · 15 dims" / "7 auto + 8 manual" | "BQ Score · 15 dims" / "10 data + 5 agent (request-only)" — confirm the split with Divyanshu before shipping |

Anywhere the page shows `sizing_pct` as an action (75% / 40% / 0%), label it "engine sizing (report only)".

## 2. COVERAGE INCOMPLETE verdict (CE-07, CE-34)

New `business_type` values: `telco`, `regulated_utility`, `holding_company` (plus existing
`unknown`). Any of them → verdict `COVERAGE INCOMPLETE`, sizing 0. Today the label appears only
in `ConvictionAuditPanel.vue:222` and the sentiment mapper.

- Add a COVERAGE INCOMPLETE chip/colour in the conviction list row and the drawer header
  (distinct from CANCEL BUY: "we can't score this yet" vs "we scored it and said no").
- Show `business_type_label` when present (e.g. SBUX "mature/transitioning compounder",
  SFTBY "tech venture capital / holding company").

## 3. P/E history confidence (CE-02)

`GET /api/v1/conviction/tickers` rows now carry `pe_history_confidence` (`full` / `provisional`
/ `neutral`), `pe_history_years`, `pe_history_source`.

- Next to the P/E percentile: "Provisional — 15.2y history (sec_edgar)" when `provisional`;
  "Not scored — under 10y history" when `neutral`.

## 4. Any-ticker look-up (CE-33) — Rohit, mail 24 Sep

> "cant we have a field somewhere on teh cion iciton engien page where we just … specify any
> stock and ask for the score with soem systematic breakdown of it"

`GET /api/v1/conviction/lookup/{ticker}` (add `?refresh=true` to recompute a stored name).
Never writes the store. Response keys: `source` (`store` | `on_demand`), `applicable`,
`business_type(_label)`, `coverage_incomplete`, `conviction_score`, `bq_raw`, `bq_components`,
`valuation_tax` + `valuation_tax_breakdown.components`, `fs_score`, `fs_class`,
`fs_score_breakdown.components`, `yield_trap_breakdown`, `pe_history{confidence,years,source,percentile}`,
`agent_dims`, `if_buy_signal{verdict,sizing_pct}`, `report_only: true`.
On-demand look-ups take ~5–15 s (live fundamentals fetch); show a spinner.

## 5. Panels already backed by API fields (CE-37, CE-38)

- Yield-traps panel: fired vs watching — flags `yield_trap` vs `yield_trap_watching`
  (`yield_trap_breakdown.watching`).
- Engine Layers click-through: `valuation_tax_breakdown`, `fs_score_breakdown`
  (`fs_cap_breakdown` is not used in Vue today), `yield_trap_breakdown`.
- Section 6 nav: signal-row "BQ drill" → drawer BQ tab is missing; "FS page →" link.

## 6. Still to reproduce on 8514 (CE-36) — Rohit, WhatsApp 22 Sep

> "we cant be degrading if thr fwd test wr is 75%… cant see anything when i click tabs on
> left… Layer 2 not clickable"

Needs a rendered-page check on `:8514`, not source alone.

## 7. "Held positions" panel (CE-35) — Rohit, WhatsApp 28 Sep

> "Held positions show MTM '—', and FD shows '→ sta' for every row. Which portfolio is 'held'?"

Root cause (Nuxt): the panel is not fed from any portfolio. `server/utils/mindwealth-data.ts:1614`
takes the first six signal rows with conviction ≥ +2 and hard-codes `mtm: '—'` (line 1625).

- Until a holdings source is chosen, retitle it "Top conviction signals (not holdings)" and hide MTM.
- FD "→ sta" is accurate: the engine's five-vote rule needs 3 agreeing votes and 129 of 136
  equities are `stable` today. Showing the vote count (e.g. "stable · 2↑ 0↓") would carry more
  information than the bare arrow.
- Which portfolio counts as "held" is a decision for Rohit (options: his holdings sheet,
  `config/personal_holdings.json`, or the model book from the portfolio sizer).

## Update — 25 Oct: done on dev by Divyanshu's session (uncommitted on `ui-dev`)

Built and live on 8514. Files (conviction-only changes; review and commit):
`types/conviction.ts`, `utils/conviction-display.ts`, `utils/drift-terminology.ts`,
`server/utils/mindwealth-data.ts` (only the conviction / drift hunks — the SBI breadth hunks in
that file are someone else's work), `server/api/conviction/lookup/[ticker].get.ts` (new),
`components/conviction/{ConvictionLookupPanel (new),ConvictionDepthPanel,ConvictionRowDrawer,ConvictionPortfolioPanel,ConvictionStatusChips,ConvictionSignalsPanel}.vue`,
`components/FunctionDetailPopup.vue`, `pages/conviction/index.vue`, `pages/index.vue`,
`constants/regime-strip.ts` (one line: v5 → v6), `constants/terminal-configs.ts`,
`assets/css/main.css` (`.cvb-cov`, `.cv-bd-*.n`), `test/conviction-display.spec.ts` (new).

Covers §1–§5 and §7 above, plus: COVERAGE INCOMPLETE no longer maps to CANCEL; a missing P/E
percentile shows "Not scored" instead of 0th; "degrading" follows the backend drift floor
(forward WR < 61%), not the BT-vs-FWD gap.

Note: BFF routes check only that the `mw_access_token` cookie exists; conviction routes call the
backend with the server's key, so any cookie value passes. Pre-existing design, worth tightening.
