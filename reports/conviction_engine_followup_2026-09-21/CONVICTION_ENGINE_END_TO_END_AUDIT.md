# Conviction Engine follow-up audit after Rohit's 21 September reply

I rechecked Rohit's latest reply against the earlier mails, the July decision record, the todo sheet, the current implementation, all 197 development records and the live dev test surface. The main result is that several points which sounded undecided are already specified. The remaining blockers are narrower and should be taken to the call as explicit decisions.

## What is clear now

| Topic | Evidence | Answer | Status |
|---|---|---|---|
| Actual dividend cut penalty | Rohit's 30 July Q6 answer specifies 0 for a 0 to 25% decline, -1 for 25 to 50%, -2 for 50 to 75%, -3 for 75 to 100%, with the combined buyback plus dividend penalty capped at -4. The code implements this in `src/conviction_engine/capital_allocation.py:87-193`. | The penalty already exists as a standalone BQ component. It is not part of FS. | Already decided |
| Possible versus actual cut | The current feed lacks declaration date, declared period and distribution type. The code therefore stores a candidate but suppresses its score through `apply_dividend_cut_penalty` in `fundamentals_enriched.py:432-450`. | A possible or unverified cut stays at 0. A source-verified actual cut should use the existing BQ tiers automatically once the rollout is enabled. | Mechanics clear, rollout decision needed |
| Exit behavior | `engine.py:756-793` calls the sell ladder only when the incoming technical signal is `SELL`. | The Conviction Engine does not create an exit on its own. It currently modifies both quant BUY and quant SELL signals. | Current behavior clear, desired behavior reopened |
| Neutral score | The confidence module sets the dimension score to 0 when final confidence is below 0.70. `score_manual(None)` also contributes 0 to BQ. | Neutral means no reward and no penalty for that dimension. It does not mean the company is good or bad. | Already implemented |
| Confidence | The 24 May todo row says to use prompt confidence rules, Python source-count validation and mandatory `evidence_against`. Current code caps confidence at 0.35 with fewer than two sources and at 0.55 when the opposing text is materially longer, then makes anything under 0.70 neutral. | This is a stepwise rule applied to a model-reported starting confidence. It is not a statistically calibrated probability. | Implemented, transparency can improve |
| “Regression suite” | Current run on 21 September: 166 targeted Conviction tests passed in 11.03 seconds. | This means software regression tests checking that earlier behavior remains correct after a code change. Nothing is statistically regressed on anything. | Wording corrected |
| “Not recorded” | `000660.KS` last had a full calculation on 27 August. Its September dividend, framework and model-usage audit fields do not exist in the stored JSON. | `not_recorded` means the legacy record predates the new field. It does not mean false, zero or provider unavailable. | Display is truthful, explanation needed in UI |

The earlier phrase “until the dividend penalty is explicitly approved” was poor wording. There are two different approvals:

| Approval | What it should mean | What it should not mean |
|---|---|---|
| One-time rollout approval | Rohit accepts the corrected source and declared-period methodology, after seeing the universe diff. | Manually approving every cut forever. |
| Per-event verification | The data identifies a genuine ordinary declared annual DPS cut rather than a special distribution, stale observation or ETF payout. | Re-deciding the already specified -1, -2 and -3 tiers. |

The current `apply_dividend_cut_penalty` per-record flag mixes these two ideas. I would replace it with one global rollout setting plus an event state of `candidate_unverified`, `verified_cut` or `rejected_candidate`.

## Dividend questions, with the counts reconciled

The “144 payer records” in the earlier mail was the dividend-diff job's input set, not “144 global companies with at least one full year of dividends.” It included non-equity instruments and any record with usable payment history. The live scored equity universe has a different denominator.

| Measure | Count | Percentage of 136 equities | Definition |
|---|---:|---:|---|
| Scored equities | 136 | 100.0% | Current stored equity records |
| Equities with a trailing paid dividend | 103 | 75.7% | `dividend_yield_trailing > 0` |
| Equities currently labelled `income` | 27 | 19.9% | Stored business-type label |
| Dividend-diff inputs | 144 | Not comparable | Payer records examined by the correction report, including ETFs |
| Changed under corrected construction | 11 | 8.1% if compared with equities, but this mixes instruments | 9 equities plus 2 ETFs |

The best current proxy for “dividend yield style” is 27 of 136, or 19.9%, but this is not a reliable investment-style census. Several current `income` labels are automatic and should be audited before presenting 19.9% as an investment conclusion.

| Candidate group | Tickers | Count | Treatment now |
|---|---|---:|---|
| Clean local automation candidates | BABA, BDL.NS, SPK.NZ, SUM.NZ, TD | 5 | Candidate only until the rollout is approved |
| Special or stale distribution needs verification | BYDDY, FMCC, TWR.NZ, WIPRO.NS | 4 | Do not score from the present feed |
| Non-equity | DBC, FXI | 2 | Exclude from the company dividend-cut rule |

For the 9 equity candidates, issuer domicile gives 1 US company and 8 non-US companies. Listing convention gives a different answer: 4 unsuffixed or US-listed equities and 5 local-exchange-suffixed equities. The reply should state issuer domicile so “US” is not ambiguous.

The current dividend method is not “trailing dividend always.”

| Use | Current basis |
|---|---|
| Current yield and yield-trap input | Forward declared annual dividend when available |
| Cross-check | Trailing paid dividend stored separately |
| Five-year yield distribution | Month-end twelve-month dividend divided by that month's price, up to 60 observations |
| Cut detection target | Current declared annual DPS versus prior declared annual DPS |
| Current fallback limitation | Payment-spacing coverage is used when declared-period labels are unavailable; specials cannot always be separated |

The provider decision does not need an AND condition. P/E and dividends should be evaluated independently.

| Provider question | Evidence | My suggestion |
|---|---|---|
| Dividend justification | Only 4 of the 9 equity candidates need provider or manual special-distribution verification. | Dividend alone does not justify a broad paid subscription. |
| P/E justification | 51 of 69 unsuffixed equity names have less than 20 years or no usable series. | Long point-in-time EPS history is the stronger commercial case. |
| EODHD | Public personal plans list Fundamentals at $59.99/month and All-in-One at $99.99/month; commercial use needs a quote. | Ask for a sample and commercial quote because it has the more explicit global and corporate-action proposition. |
| FMP | Public annual-billed plans list Starter at $22/month, Premium at $59/month and Ultimate at $149/month; display or redistribution terms are separate. | Ask for a sample and commercial quote, especially for US, UK and Canada history. |

I would request both quotes and sample output, then buy neither until the 11 dividend names and missing-P/E names are tested. One provider can pass one use case and fail the other.

## US P/E history and what the code actually calculates

The current engine does not consume a vendor's present-day P/E and carry it backwards. `pe_history_core.py:165-184` divides each historical close by trailing twelve-month EPS known at that date. SEC EDGAR is the main deep-history EPS source for US filers; yfinance is used where SEC filing history is not available.

“US equity names” needs a definition. The current routing proxy is an unsuffixed ticker, which includes foreign ADRs such as ASML, BABA and NVO. Under that operational definition there are 69 names.

| Available P/E span | Unsuffixed equity count | Percentage |
|---|---:|---:|
| 20 years or more | 18 | 26.1% |
| 15 to under 20 years | 10 | 14.5% |
| 10 to under 15 years | 6 | 8.7% |
| 5 to under 10 years | 5 | 7.2% |
| Under 5 years | 23 | 33.3% |
| No usable series | 7 | 10.1% |
| Total | 69 | 100.0% |

| Source among the 69 | Count |
|---|---:|
| SEC EDGAR plus legacy filing extension | 18 |
| SEC EDGAR | 26 |
| yfinance EPS reconstruction | 17 |
| No source metadata | 8 |

Among the 44 SEC-routable filers, 18 have 20 or more years, 10 have 15 to under 20, 6 have 10 to under 15, 5 have 5 to under 10 and 5 have under 5. Historical price is not the limiting input. Point-in-time EPS depth is.

The practical answer to Rohit's EPS question is therefore: we already use EPS plus price. A direct P/E provider would only help if its ratio is itself point-in-time and auditable. I would keep the strict 20-year scoring rule active until he confirms whether 10 to 20 years may be used as provisional evidence.

## Starbucks, with the requested 10, 5 and 2 year CAGRs

I reconstructed the figures from Starbucks' SEC Companyfacts. Free cash flow is operating cash flow less capital expenditure, and declared DPS is the annual declared dividend per share.

| Metric | FY2015 | FY2020 | FY2023 | FY2025 | 10-year CAGR | 5-year CAGR | 2-year CAGR |
|---|---:|---:|---:|---:|---:|---:|---:|
| Revenue | $19.163bn | $23.518bn | $35.976bn | $37.184bn | 6.85% | 9.60% | 1.67% |
| Diluted EPS | $1.82 | $0.79 | $3.58 | $1.63 | -1.10% | 15.59% | -32.52% |
| Free cash flow | $2.445bn | $0.114bn | $3.675bn | $2.442bn | -0.01% | 84.51% | -18.48% |
| Declared DPS | $0.68 | $1.23 | $2.16 | $2.45 | 13.68% | 14.78% | 6.50% |

The 5-year EPS and FCF CAGRs are flattered by the depressed FY2020 base. The 2-year numbers show current operational deterioration, while dividend growth is still positive. The current stored yield is 2.59%, which is not enough on its own to make Starbucks a classic yield stock.

My recommendation is to keep SBUX as `compounder` with a documented `mature/transitioning` override. I would not auto-move it to `income` until there is a defined hybrid rule. This is also consistent with the current one-off review flag, where one-offs equal 20.62% of trailing net income and make the raw FY2025 comparison less clean.

## What EXIT means and what the current BQ distribution says

The present flow is:

| Input from quant model | What the Conviction Engine does |
|---|---|
| BUY | Confirms, reduces, cancels or marks coverage incomplete |
| SELL | Pauses, partially exits, fully exits or hard-exits according to conviction, BQ and hard gates |
| No technical signal | Does not independently create an entry or exit |

Rohit's 1 September mail explicitly specified a sell ladder, but his 21 September reply asks whether that architecture is intended at all. The newer message reopens the decision. We should not merge labels until this more basic question is answered.

| Current equity universe | All 136 equities | 69 unsuffixed equities |
|---|---:|---:|
| BQ minimum | -5.0 | -2.5 |
| BQ median | 6.0 | 6.0 |
| BQ mean | 5.57 | 5.94 |
| BQ maximum | 13.0 | 12.0 |
| BQ below 0 | 12 | 6 |
| BQ 0 to under 5 | 40 | 16 |
| BQ 5 or more | 84 | 47 |
| Conviction below +2 | 55 | 27 |

If the current sell ladder were applied to an incoming SELL across the 55 low-conviction names, 12 would be `HARD EXIT`, 28 `FULL EXIT`, and 15 `PARTIAL EXIT`. The other 81 have conviction of at least +2. Both HARD and FULL currently retain 0%, so for 40 names the execution size is identical and only the reason differs.

The requested current, past and bear-market distribution for all S&P 500 names does not exist in the current data. The daily archive covers May to September 2026 and contains signal subsets, not full-universe point-in-time BQ snapshots. A valid answer requires a 500-name universe, point-in-time historical fundamentals, a replay date set and a policy for the paid qualitative dimensions. Running present fundamentals against old prices would produce lookahead bias.

Given Rohit's stated 80% quant and 20% fundamental intent, my current preference is entry modification plus a non-binding sell warning until the historical replay shows that a fundamentals-based sell modifier adds value. That would be a policy change from the 1 September ladder and therefore needs his confirmation.

## Telco and regulated-utility counts

I counted only explicit `Telecom Services` and regulated-utility industries. Renewable and independent-power names are shown seperately because they are not regulated utilities.

| Category by issuer domicile | Count | Tickers |
|---|---:|---|
| US telcos | 0 | None |
| US regulated utilities | 0 | None |
| Non-US telcos | 4 | CNU.NZ, SPK.NZ, T.TO, SFTBY |
| Non-US regulated utilities | 1 | BIPC.TO |
| Other utilities, not regulated | 4 | CEN.NZ, GNE.NZ, MCY.NZ, MEL.NZ |

This is a small portfolio-specific sample. A separate framework for telco and regulated utilities is still intellectually cleaner, but the current counts do not justify rushing two full calibrations before Rohit sets the rules.

## CEO confidence, qualitative dimensions and cost

The confidence path is stepwise:

| Step | Current rule | Effect |
|---|---|---|
| Starting value | The model returns confidence using anchored prompt instructions | Starting value only |
| Source validation | Fewer than 2 sources | Cap at 0.35 |
| Opposing evidence check | `evidence_against` text is more than 30 characters longer than `evidence_for` | Cap at 0.55 |
| Neutral threshold | Final confidence below 0.70 | Dimension score becomes 0 |
| BQ treatment | Score 0 or unavailable | No reward and no penalty |

The source-count cap is defensible. The text-length comparison is crude because character count is not evidence quality. I would expose the starting confidence, caps applied, final confidence, source count and the actual for/against evidence in the UI, then replace the length heuristic with a source-quality rubric after the call.

There are five current model-driven dimensions per equity: CEO quality, moat, macro tailwind, deal delay and TAM/runway. A 136-equity pass therefore needs at least 680 calls. At one web search per call, the search floor is $6.80 before model tokens or repeat searches.

| Model option | Current public input/output price per million tokens | Use in this project |
|---|---:|---|
| Claude Haiku 4.5 | $1 / $5 | Low-cost comparison candidate |
| Claude Sonnet 4.5 and 4.6 | $3 / $15 | 4.5 is current code default, but near its tentative retirement window |
| Claude Sonnet 5 | $2 / $10 | Better replacement candidate for a small quality comparison |
| Web search | $10 per 1,000 searches | At least $0.01 per one-search call |

No existing run contains usable cost totals because the two stored model runs predate the new metering fields. The metered model-run count is therefore 0, which is an audit gap rather than proof of zero cost.

My suggestion is to leave these dimensions off by default and run them only on specifically requested names. If Rohit wants proof before deciding, compare Haiku 4.5 and Sonnet 5 on NVDA and GOOGL across the same five dimensions, with a $5 hard cap. Do not run 680 calls before that.

## What is fixed on dev and what today's checks found

| Item | Current evidence | State |
|---|---|---|
| Dividend candidate cannot alter BQ by default | `apply_dividend_cut_penalty` defaults false | Live on dev |
| Unapproved candidate cannot force dividend HARD EXIT | Exit checks `dividend_cut_penalty_applied is True` | Live on dev |
| Low-confidence result becomes neutral | Final confidence below 0.70 sets score to 0 | Live on dev |
| Neutral results retain audit detail | Audit endpoint exposes low-confidence and legacy states | Live on dev |
| Dev audit page | 197 records, API 8507 and UI 8514 active | Live on dev |
| Targeted Conviction tests rerun 21 September | 166 passed in 11.03s | Pass |
| UI tests rerun 21 September | 63 passed across 7 files | Pass |
| Broad API suite rerun 21 September | 194 passed, 1 failed | One unrelated failure |
| Broad API failure | NU shortlist signal age 3 days had `days_elapsed=0` | Signals-surface issue, not Conviction |
| Production | API 8506 and UI 8512 not changed by this audit | Untouched |

The earlier statement “195 API tests pass” was true on the prior run. Today's rerun is 194 pass and 1 failure because live shortlist data now exposes an NU holding-days issue. I would track that as a separate signals-surface fix and not hide it in a Conviction close-out.

## Updates I would make without waiting for policy choices

| Priority | Update | Why it is safe |
|---:|---|---|
| 1 | Rename the dividend audit language to distinguish global rollout approval from per-event source verification | Corrects misleading wording without changing scores |
| 2 | Show that SELL outcomes are modifiers of an incoming quant SELL, not independent CE exits | Corrects UI meaning without deciding entry-only versus entry-and-exit |
| 3 | Display starting confidence, caps applied, final confidence, source count and evidence for/against | Explains the current calculation rather than changing it |
| 4 | Add a `legacy record, field added after last full calculation` explanation to `not_recorded` | Prevents false interpretation |
| 5 | Split P/E coverage into 20+, 15 to 20, 10 to 15, 5 to 10, under 5 and no series, with source | Matches Rohit's requested view |
| 6 | Store issuer domicile separately from ticker/listing convention | Makes US versus non-US counts reproducible |
| 7 | Record SBUX's `mature/transitioning compounder` override and reason without bulk reclassification | Preserves the existing category while documenting the exception |
| 8 | Correct the dividend code comment that says “any cut counts” although 0 to 25% scores 0 | Documentation fix only |
| 9 | Investigate the NU `days_elapsed=0` API test failure separately | Current broad-suite regression unrelated to Conviction |

## Work that remains decision-dependent

| Work | What blocks it | Default until answered |
|---|---|---|
| Enable verified dividend penalties | Confirm one-time rollout and event-verification semantics | Candidates recorded, BQ effect 0 |
| Use 10 to 20 year P/E history | Rohit has not approved provisional scoring | Strict 20-year rule |
| Use Conviction on SELL signals | Latest reply reopens entry-only versus sell modification | Preserve current code, no semantic merge |
| Merge HARD and FULL labels | Depends on whether the sell modifier remains | Keep labels and reason codes |
| Telco and utility scoring | Thresholds not supplied | Coverage incomplete |
| Universe model run | Purpose, model and spend not approved | Off by default |
| Historical S&P 500 BQ study | Needs scope, point-in-time data and budget | Do not approximate with lookahead |
| Production promotion and bulk recalculation | Requires policy decisions, review and normal release | Dev only |

## Evidence trail

| Source | What it supports |
|---|---|
| Rohit, “Re: conviction engine fixes and some doubts,” 21 Sep 2026, Gmail message `1a0c341380f3954b` | Latest questions and 80/20 direction |
| Rohit, “Re: checking your conviction engine implementation,” 1 Sep 2026, Gmail message `1a05bedfe8ea89a8` | Declared-period dividend method, month-end yield series, sell ladder, audit display and telco deferral |
| Rohit's 24 May todo row, `v2_TODOs!A6:I6` | Confidence below 0.70 becomes neutral, source-count validation and mandatory opposing evidence |
| `docs/instruction_docs/conviction_engine_issues/Divyanshu_Business_Type_Reply 30 July_conviction doubts.pdf`, Q6 | Dividend tiers and combined -4 cap |
| `docs/instruction_docs/conviction_engine_issues/conviction_fixes_decisions.md:48-58` | Local provenance of the July decision |
| `reports/conviction_engine_closeout_2026-09-17/dividend_cut_diff.csv` | 144 input records and 11 changed candidates |
| `reports/conviction_engine_closeout_2026-09-17/pe_history_coverage.json` | Full 136-equity P/E coverage |
| [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) and [Starbucks Companyfacts](https://data.sec.gov/api/xbrl/companyfacts/CIK0000829224.json) | Point-in-time US filing data and SBUX figures |
| [EODHD pricing](https://eodhd.com/pricing) and [commercial licensing](https://eodhd.com/financial-apis/commercial-vs-personal-license-use) | Public plan prices and commercial-use requirement |
| [FMP pricing](https://site.financialmodelingprep.com/developer/docs/pricing) | Public plan and coverage claims |
| [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing) and [model deprecations](https://docs.anthropic.com/en/docs/about-claude/model-deprecations) | Current model/search prices and retirement windows |

## My doubts and questions

1. Should a source-verified actual dividend cut automatically apply the already approved BQ tier once the global rollout is enabled, with no per-event manual approval?
2. Should 10 to under 20 years of P/E history affect scoring as provisional evidence, or remain display-only while the strict 20-year rule stays active?
3. Is the intended product entry-only, or may the Conviction Engine also modify a quant SELL? This must be answered before discussing HARD versus FULL label merging.
4. Does Rohit want the historical S&P 500 replay enough to justify a seperate point-in-time data and compute project, or is the current 136-name distribution sufficient for the product decision?
5. Should telcos and regulated utilities remain coverage-incomplete until he supplies thresholds, given there are only 4 and 1 respectively in the current universe?
6. Should the five qualitative dimensions stay off by default, with a $5 two-name model comparison only if he wants evidence of incremental value?
