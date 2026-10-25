# Draft email to Rohit

**Subject:** Conviction Engine: fixes live on dev, audit complete and six inputs needed

Hi Rohit,

I have completed another end-to-end review of the Conviction Engine against your 26 August mail,
your A to G reply of 1 September, your 10 September follow-up about testing with Ahil, the current
code, and all 197 development records. I have also checked the old discussions and task list so I
do not ask you again for points you have already answered.

Two earlier points are now closed:

- You confirmed that "Tavela" meant Tavily. I will use Tavily only for research and discovery, not
  as the authoritative source for dividends or financial statements.
- Your 1 September mail says the ticker list is attached as a Google Sheet. I will retrieve that
  attachment from the existing thread and complete the parity check. You do not need to resend it
  unless the attachment is inaccessible.

## What I found and what I have fixed

The immediate issue was not just missing data. Some incomplete or low-confidence data could affect
scores or exit labels before we had approved the underlying policy. I have therefore made the
development engine safer without changing your intended policy:

- A possible dividend cut is recorded for review, but it does not reduce BQ and cannot trigger
  HARD EXIT until the dividend penalty is explicitly approved.
- The same approval gate is applied in the exit logic.
- Neutral calculations now save their audit fields correctly.
- CEO and moat agent answers below 70% confidence are treated as neutral.
- Model, token and tool usage are now logged, and the agent model is configurable.
- Coverage reporting now distinguishes not recorded, unavailable and not applicable.

The relevant regression suite passes with 166 tests. I have not changed production, and I have not
bulk-recalculated the shared development store because the unresolved classification rule would
change SBUX.

## Development website is ready for verification

I have now integrated the engine fixes and their audit data into the development website on port
8514. You can open the Conviction page and select **Safeguards & audit** to verify the changes.

That view reads the live development API rather than a mock and currently covers all 197 stored
records. It shows:

- whether the dividend penalty and dividend HARD EXIT approval gates are active;
- low-confidence CEO and moat answers, whether they were neutralised, and records that still need
  recalculation;
- framework-completeness caps and the current P/E-history coverage bands;
- statement availability and adjusted-EPS provenance; and
- agent model and usage-metering status.

The final development checks passed: 166 Conviction tests, 195 API tests and 63 UI tests, as well as
the UI production build. I also verified the page in the browser with all 197 rows loaded and no
page or console errors. The development API is running on port 8507 with version 1.16.0, the UI is
running on port 8514, and production remains unchanged and isolated.

For older records, some audit fields display **not recorded** rather than making assumptions. This
is intentional: the safety gates are active now, while the remaining records will receive the new
audit fields when we perform the approved recalculation.

Below are the six remaining inputs, with the evidence, options and my recommendation for each.

## 1. Dividend validation and paid data provider

Your earlier direction was clear: do not enter the dividend changes manually, first check whether a
paid provider can supply both reliable dividend-period data and historical P/E inputs, then show you
the corrected differences before any score is changed.

I reran the dividend comparison across 144 payer records. Eleven names changed under the corrected
method:

- Clean local automation candidates: BABA, BDL.NS, SPK.NZ, SUM.NZ and TD.
- Need provider or manual review because a special distribution may be mixed in: BYDDY, FMCC,
  TWR.NZ and WIPRO.NS.
- Not equities, so the company dividend-cut rule should not apply: DBC and FXI.

I have not approved a penalty for any of them. The current feed does not reliably identify the
declared period or distinguish an ordinary dividend from a special distribution.

The provider research completed on 17 September gave these practical options:

- **Option A: request commercial terms from both EODHD and FMP.** EODHD is the stronger first pilot
  for dividend validation because its response includes declaration, record and payment dates plus
  labels such as Quarterly, Final, Interim and Special. FMP is useful as a comparison and is
  stronger for historical fundamentals and business-segment data. Both require commercial-use
  confirmation.
- **Option B: request an EODHD quote only.** This is quicker for the immediate dividend problem,
  but may leave the P/E and segment-data questions requiring a second provider later.
- **Option C: use no paid source.** The 11 cases remain review-only and the dividend penalty stays
  disabled wherever the period cannot be verified.

The public prices visible during the research were USD 59.99 per month for EODHD Fundamentals and
USD 99.99 for its All-in-One personal plan, but these are not commercial MindWealth terms. A quote
is still required.

**My recommendation:** request commercial quotes from both providers, pilot EODHD first on these 11
names, and use FMP as the comparison or fallback. Even after provider validation, I will show you
the ticker-by-ticker diff and obtain approval before enabling any penalty.

**Question 1:** Should I request commercial quotes from both EODHD and FMP and prepare the limited
11-name dividend pilot, with EODHD tested first?

## 2. P/E history policy

You have already specified the essential rule: historical valuation must use the trailing EPS that
was known at each historical date, not today's EPS applied backwards. I agree, because applying
today's EPS backwards would make the historical percentile invalid.

The coverage problem is material:

- 136 equities are currently scored.
- 109 have some usable P/E history.
- Only 18 have at least 20 years of history.
- 118 of 136 names, or 86.8%, are below the strict 20-year requirement.
- A 15-year minimum covers 28 names, 10 years covers 34, and 5 years covers 43.

The options are:

- **Option A: strict 20-year rule.** Only 18 names receive a historical P/E percentile. All other
  names remain neutral.
- **Option B: confidence tiers.** Use 20 or more years as full-confidence, 10 to 20 years as a
  clearly labelled provisional percentile, and less than 10 years as neutral.
- **Option C: use every available history length.** This gives the widest coverage, but short
  histories can create unstable and misleading percentiles.

**My recommendation:** Option B. It preserves the 20-year standard, uses genuinely available
historical data where it is reasonably deep, and clearly discloses lower confidence instead of
pretending all histories are equal.

**Question 2:** May I implement 20-plus years as full-confidence, 10 to 20 years as provisional,
and under 10 years as neutral?

## 3. Multi-segment company classification and SBUX

The full dry run across 197 records shows that the new rules correctly move AVGO from cyclical to
high-margin hardware and NA.TO from unknown to bank. However, the same automatic logic moves SBUX
from compounder to income. This exposes the tie-break question you raised for companies that span
more than one bucket, such as Infratil or Spark.

The options are:

- **Option A: dominant operating segment.** Classify by the main operating business or revenue
  source, with a documented manual override for genuinely ambiguous cases.
- **Option B: investment thesis.** Classify by why MindWealth owns the company, even if the current
  revenue mix points elsewhere.
- **Option C: fixed priority order.** When several rules match, always apply a predefined hierarchy
  of company types. This is easy to automate but can misclassify unusual businesses.

**My recommendation:** Option A, with an explicit thesis-based override where the operating data is
ambiguous. I would keep SBUX as compounder through a documented override rather than let a mechanical
income rule change its treatment.

**Question 3:** Should dominant operating segment be the default tie-break, with documented manual
overrides, and should SBUX remain compounder?

## 4. HARD EXIT versus FULL EXIT

Your defined score rules are already clear:

- Conviction below +2 and `bq_raw` below 0 gives HARD EXIT with reason `QUALITY_COLLAPSE`.
- Conviction below +2 and `bq_raw` from 0 to +4 gives FULL EXIT with reason `NORMAL_TECHNICAL`.

The unresolved part is execution. In the current model both outcomes retain 0% and clear the core
and tactical layers, so they are functionally identical apart from the label and reason.

The options are:

- **Option A: one EXIT action with different reason and severity fields.** This preserves the
  diagnostic distinction without pretending the execution is different.
- **Option B: separate execution.** For example, HARD EXIT sells in the same session while FULL
  EXIT is worked over a defined number of sessions or at a limit. This requires the exact execution
  rule and timing.
- **Option C: keep both labels with identical 0% execution.** This preserves the current output but
  leaves two names for the same model action.

**My recommendation:** Option A for now. Keep `QUALITY_COLLAPSE` and `NORMAL_TECHNICAL` as distinct
reasons, but use one EXIT action until Ahil's work establishes a real sizing or execution difference.

**Question 4:** Should I collapse HARD EXIT and FULL EXIT into one EXIT action for now, or do you
want separate execution? If separate, what timing should apply to each?

## 5. Telco and utility framework

In your 1 September reply you said you would think through the capital-intensive telco and utility
specification and that I should not wait for it. I have followed that direction. These names stay
under the coverage-incomplete cap, so the engine does not award false confidence while the framework
is missing.

The research supports separate telco and regulated-utility frameworks because their leverage,
capital intensity, regulation and cash-flow economics differ. EV/EBITDA can be one calibration
input, but it is not a complete framework on its own.

The practical options are:

- **Option A: separate telco and regulated-utility rules.** This is my recommendation.
- **Option B: one shared capital-intensive infrastructure framework.** Simpler, but less precise.
- **Option C: keep both categories coverage-incomplete until more evidence is available.** Safest
  as an interim state and already enforced.

**My recommendation:** retain Option C as the temporary safety rule, then implement Option A when
your framework is ready. I will not invent thresholds.

**Question 5, when ready:** Please send the telco and utility rules and confirm whether you want two
separate frameworks or one shared framework. This does not block the other safety work.

## 6. Agent model, pilot and full-run budget

I ran isolated calculations without changing the shared store:

- NVDA: conviction +8, FS 70, moderate-high.
- GOOGL: conviction 0, FS 52.5, moderate. The earlier provisional +2 included a CEO score based on
  only 55% confidence; the corrected gate makes that dimension neutral.

The Ahil test pack now covers NVDA, GOOGL, NA.TO, AVGO, SBUX, SPK.NZ, exit behaviour and a
coverage-incomplete telco or utility case.

A full pass is not a small call: 136 equities multiplied by five agent dimensions means at least
680 model calls. With one search per dimension, search charges alone start at USD 6.80, before model
tokens and any repeated searches. I now log the actual tokens, searches and model for every run, so
we can measure cost instead of relying on a rough estimate. The currently pinned model also needs a
validated replacement before it is retired.

The options are:

- **Option A: controlled replacement-model pilot.** Compare suitable models on NVDA and GOOGL,
  impose a hard pilot cap, report quality and actual cost, then ask for approval for the full run.
- **Option B: keep agent dimensions limited to specifically requested names.** Lowest cost, but no
  complete universe coverage.
- **Option C: run the full universe immediately with a fixed ceiling.** Fastest, but risks paying
  for a model before we have validated its output consistency.

**My recommendation:** Option A. I will select the compatible shortlist, run only the two-name pack,
and return with the measured per-name cost and a specific full-universe budget. You do not need to
choose a technical model ID blindly.

**Question 6:** May I run the controlled model comparison, and what hard spending ceiling should I
use for that pilot? After that result, I will ask separately before any 680-call full pass.

## Decisions and next steps

To make the reply easy, you can answer using Q1 to Q6:

1. **Q1, provider pilot:** Request commercial quotes from EODHD and FMP, with EODHD as the first
   11-name dividend pilot?
2. **Q2, P/E history:** Use 20-plus years as full-confidence, 10 to 20 as provisional, and under 10
   as neutral?
3. **Q3, classification:** Use dominant operating segment plus documented overrides, and keep SBUX
   as compounder?
4. **Q4, exits:** Use one EXIT action with separate reason codes, or define different HARD EXIT and
   FULL EXIT execution?
5. **Q5, telco and utilities:** Use separate frameworks when your rules are ready?
6. **Q6, agent pilot:** Approve the two-name replacement-model pilot and specify its spending
   ceiling?

You can verify the safety changes now on the development website at port 8514 under **Conviction →
Safeguards & audit**. Once Q1 to Q6 are confirmed, I can finish the controlled development
recalculation, test the resulting score changes with Ahil, show you the final ticker-by-ticker
differences, and then take the approved changes through the normal production release process.
Production remains untouched.

Regards,  
Divyanshu
