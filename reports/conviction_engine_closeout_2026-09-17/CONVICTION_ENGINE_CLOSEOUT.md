# Conviction Engine close-out — 17 September 2026

## Outcome

The development-side work that can be completed safely without Rohit's policy choices is done.
Production was not changed, and the main development `conviction_store` was not bulk-recalculated
because one current classification rule would change SBUX from `compounder` to `income` without an
approved multi-segment/tie-break policy.

| State | Count | What it means |
|---|---:|---|
| Fixed and regression-tested in dev code | 6 | Dividend approval hold; HARD EXIT approval hold; neutral-result audit persistence; low-confidence CEO/moat gating; API model/usage provenance; truthful coverage reporting |
| Analysis/research completed | 7 | Dividend diff, P/E coverage and sensitivity, provider comparison, full classification dry run, HARD vs FULL EXIT trace, targeted NVDA/GOOGL run, local universe reconciliation |
| Rohit decisions still needed | 7 | Dividend approval method; short-history P/E policy; provider/commercial budget; telco/utility framework; exit semantics; multi-segment tie-break; agent model/budget |
| External/human follow-ups | 3 | Ahil live test, external Google Sheet parity, production release/recalculation |

## Fixes made

1. A dividend-cut candidate is now recorded for review but contributes **zero** to BQ unless
   `apply_dividend_cut_penalty=true` is explicitly approved.
2. The dividend HARD EXIT gate uses the same approval state, so an unapproved candidate cannot
   close a position.
3. A valid all-neutral auto calculation is no longer mistaken for a missing calculation. This
   preserves `capital_return_flags` and all approval/audit fields.
4. CEO and moat answers below 70% confidence are neutral both when first generated and when old
   stored answers are recalculated.
5. Agent calls now record the actual API model and token/tool usage. The model is configurable via
   `CONVICTION_AGENT_MODEL`.
6. The coverage report distinguishes `not_recorded`, `unavailable`, and `not_applicable`; it no
   longer describes every legacy record as a failed data fetch.

Verification: `164 passed` across the conviction engine, v2 fixes, and conviction API suites.

## Evidence generated

- [Dividend diff](./dividend_cut_diff.csv): 144 payer records examined; 11 candidate changes.
  BABA, BDL.NS, SPK.NZ, SUM.NZ and TD pass the local automation screen. BYDDY, FMCC, TWR.NZ and
  WIPRO.NS may contain special distributions; DBC and FXI are not equities. This is a review list,
  not approval: the current yfinance feed does not reliably label declared periods/specials.
- [P/E coverage](./pe_history_coverage.json): 136 scored equities; 109 have some P/E series, but
  only 18 have 20+ years. 118/136 (86.8%) therefore remain below the strict 20-year requirement.
- [Classification dry run](./classification_diff.json): all 197 records completed without errors.
  AVGO would change `cyclical → high_margin_hardware`; NA.TO would change `unknown → bank`.
  SBUX would also change `compounder → income`, exposing the unresolved tie-break problem.
- [Field coverage](./conviction_field_coverage.csv) and
  [universe earnings coverage](./conviction_universe_earnings.csv): most old records have not yet
  had the September fields recalculated; this is legacy state, not proof that all providers failed.
- Isolated [GOOGL](./targeted_store/GOOGL.json) and [NVDA](./targeted_store/NVDA.json) full runs:
  GOOGL = BQ 5, valuation tax -5, conviction 0, FS 52.5/moderate; NVDA = BQ 14, tax -6,
  conviction +8, FS 70/moderate-high. GOOGL's earlier provisional +2 was corrected to 0 because
  the CEO answer had only 55% confidence.

## P/E policy sensitivity

| Minimum history | Eligible equities | Additional vs 20y | Tax moves | FS moves |
|---:|---:|---:|---:|---:|
| 20 years | 18 | — | — | — |
| 15 years | 28 | 10 | 7 | 9 |
| 10 years | 34 | 16 | 9 | 15 |
| 5 years | 43 | 25 | 16 | 24 |
| 2 years | 46 | 28 | 16 | 26 |
| Any history | 108 | 90 | 42 | 79 |

Recommendation: retain 20 years for full-confidence percentile scoring; optionally allow 10–20
years as a clearly labelled provisional percentile; keep under 10 years neutral. Using every thin
series creates unstable percentiles and changes 79 FS scores.

## Provider research and recommendation

| Source | Best use | Constraint | Recommendation |
|---|---|---|---|
| SEC EDGAR | US filing facts and point-in-time fundamentals | US/SEC filers only | Keep as free Tier 1. No key required; real-time filing/XBRL APIs. |
| EODHD | Global fundamentals and dividend event metadata | Period/date fields can still be null; commercial use needs a quote | First paid pilot for dividend declared-period validation. Its JSON endpoint exposes declaration, record, payment and period/special metadata. |
| FMP | Long-history fundamentals plus product/geographic revenue segments | Global history needs Ultimate; display/redistribution needs an agreement | Second-choice pilot, strongest for multi-segment classification. |
| Alpha Vantage | General backup | Free plan is only 25 requests/day and commercial use requires contact | Do not build the production workflow around the free plan. |
| NZX | Authoritative NZ corporate actions | Quote/licensing and integration work | Use as the authoritative NZ fallback if EODHD coverage fails. |
| Tavily | Agent web search | Search evidence, not a structured financial truth source | Keep only for research dimensions, with usage logging and a budget. |

Current advertised personal prices are EODHD Fundamentals $59.99/month and All-in-One
$99.99/month; commercial/B2B use requires a quote. FMP advertises $19/$49/$99 monthly when
billed annually for Starter/Premium/Ultimate, with a separate display/licensing agreement. These
are evaluation prices, not approval to use personal licences commercially.

Sources: [EODHD corporate actions](https://eodhd.com/financial-apis/api-splits-dividends),
[EODHD pricing](https://eodhd.com/pricing),
[EODHD commercial licensing](https://eodhd.com/financial-apis/commercial-vs-personal-license-use),
[FMP pricing and coverage](https://site.financialmodelingprep.com/developer/docs/pricing),
[SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces),
[Alpha Vantage terms](https://www.alphavantage.co/terms_of_service/), and
[NZX data licensing](https://www.nzx.com/services/products-tools/data-connectivity/nzx-market-data/data-licensing).

## Other resolved analysis

- **HARD EXIT versus FULL EXIT:** the current engine executes both identically: 0% retained and
  both core and tactical layers cleared. Only the label/reason differs. Either collapse the UI to
  `EXIT` with a reason/severity, or Rohit must define different timing/urgency behaviour.
- **Telco/utilities:** they should be separate frameworks. January 2026 US sector data supports
  EV/EBITDA as a useful calibration input but does not justify blindly hard-coding a universal
  tier: telecom services were about 6.54x, wireless 8.97x, general utilities 13.73x and water
  14.14x on the positive-EBITDA table. Source: [Damodaran sector multiples](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/vebitda.html).
- **Agent run cost:** 136 equities × 5 dimensions = at least 680 model calls. If each dimension
  uses one web search, search fees alone are at least $6.80, plus tokens; multiple searches make
  that a floor, not a ceiling. The configured Sonnet 4.5 model is still active but has a “not
  sooner than 29 September 2026” retirement date, so a full run should wait for a replacement
  model validation. Sources: [Anthropic pricing](https://docs.anthropic.com/en/docs/about-claude/pricing)
  and [model status](https://docs.anthropic.com/en/docs/about-claude/model-deprecations).
- **“Tavela”:** confirmed by Rohit on 19 September 2026 to mean Tavily. Tavily remains a research
  search source, not an authoritative structured source for dividends or financial statements.
  Tavily currently offers 1,000 free credits/month and $0.008/credit pay-as-you-go:
  [Tavily pricing](https://docs.tavily.com/documentation/api-credits).
- **Universe parity:** the local signal universe has 195 symbols and every one has a store record;
  FUTU and T.TO are the two extra store records. External Google Sheet parity remains unverified
  because the connected Drive API returned 403 and the ticker-sheet ID is not recorded locally.

## Safe next sequence

1. Send the prepared Rohit mail and get the eight policy/budget decisions.
2. Run the [Ahil live test pack](./AHIL_LIVE_TEST_PACK.md); record whether users find the output
   useful, not merely whether the endpoint returns 200.
3. Pilot EODHD on the 11 dividend-diff names before approving any dividend penalty.
4. Apply the approved SBUX/multi-segment policy, then run the full dev-universe recalculation.
5. Perform the normal dev-to-prod release and production runtime-data recalculation only after
   review. Production remains untouched in this work.
