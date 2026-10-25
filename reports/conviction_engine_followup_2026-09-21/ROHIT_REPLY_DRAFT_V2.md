# Draft reply to Rohit sir, V2

**Subject:** Conviction Engine follow-up, answers and decisions after your reply

Hi sir,

I went through your reply point by point and checked the code, the earlier decisions, the current
development records and the evidence again...... I have kept your full exact reply below each point. In
the clarification section, I have then repeated each specific question immediately before my answer
so it is clear which answer relates to which part of your reply.

## Point 1: Possible dividend cut vs actual dividend cut

### What I originally wrote

> A possible dividend cut is recorded for review, but it does not reduce BQ and cannot trigger
> HARD EXIT until the dividend penalty is explicitly approved.

### Rohit sir's exact reply

> - "A possible dividend cut is recorded for review, but it does not
> reduce BQ and cannot trigger HARD EXIT until the dividend penalty is
> explicitly approved."--->>>>> what if its an actual dividend cut versus
> possible dividend cut? Yes a possible dividend cut neednt reduce BQ... OK.
> Yes naturally if its just "possible" it shouldnt trigger HARD EXIT. "until
> the dividend penalty is explicitly approved"--->>> what do you mean? We
> have to decide all this now. Dont we already have a dividend penalty in our
> calculation of FS..? or at some other stage?  have it in BQ at the moment?

### Question-by-question clarification

#### 1.1 Actual dividend cut versus possible dividend cut

> "what if its an actual dividend cut versus possible dividend cut?"

**My clarification:** A possible or unverified cut stays visible for review...... but contributes 0 to BQ
and cannot create the dividend HARD EXIT condition. It doesnt affect the score until verified. A source-verified actual cut can receive the
existing dividend penalty after the one-time corrected-method rollout is approved.

#### 1.2 Whether the penalty already exists, and whether it belongs in FS or BQ

> "Dont we already have a dividend penalty in our calculation of FS..? or at some other stage? have it in BQ at the moment?"

**My clarification:** Yes...... my wording made it sound like the penalty itself had not been decided,
but I checked the 30 July rule and the code. The penalty already exists in BQ, the business-quality
part of the score, not FS, the separate financial score. The rule is 0 for a cut up to 25%, then
-1 for 25% to 50%, -2 for 50% to 75% and -3 above 75%, with the combined buyback and dividend
penalty capped at -4.

For context, the calculation is:

`Dividend cut % = (previous declared annual DPS - current declared annual DPS) / previous declared annual DPS x 100`

A reduction of 25% or less is recorded but scores 0. A reduction above 25% and up to 50% scores
-1, above 50% and up to 75% scores -2, and above 75% scores -3. If the cut is an evidenced policy
reset and either coverage improves or leverage falls, with no distress signal, the penalty is
halved. If coverage deteriorates, coverage is below 1.0x, leverage rises, or there is no positive
evidence of improvement, the full penalty applies. DPS means declared dividend per share.

#### 1.3 What “explicitly approved” means

> "until the dividend penalty is explicitly approved"--->>> what do you mean? We have to decide all this now.

**My clarification:** What I mixed up was approval of the corrected method across the full store and
verification of one specific dividend event. I have now separated those on the dev page. Im not
suggesting that you manually approve every actual cut forever...... I only need you to confirm this
operating rule once, after which verified actual cuts can apply it automatically.

**Q1:** After the one-time rollout approval, should a source-verified actual dividend cut
automatically apply the existing BQ penalty, while an unverified cut remains visible but scores 0?

## Point 2: What the approval gate means for exits

### What I originally wrote

> The same approval gate is applied in the exit logic.

### Rohit sir's exact reply

> - "The same approval gate is applied in the exit logic." What do you
> mean? Are you saying we dont exit a trade based on some conviction engine
> attribute? sorry am not clear what approval gate you refer to and why it
> should be applied in the exit logic? Did i specify that by error? Or am i
> misunderstanding the logic you are using here?

### Question-by-question clarification

#### 2.1 What approval gate I was referring to

> "sorry am not clear what approval gate you refer to"

**My clarification:** I meant the one-time rollout hold on the corrected dividend-cut method...... plus
the requirement that an individual dividend event must be verified before it can affect the score.
i did not mean that every quant exit requires manual approval.

#### 2.2 Whether the gate stops us exiting a trade

> "Are you saying we dont exit a trade based on some conviction engine attribute?"

**My clarification:** No...... the quant model has to send a SELL first. Conviction doesnt create a SELL
by itself. The dividend gate only stops an unverified dividend event from converting that incoming
quant SELL into HARD EXIT. It does not block or cancel the original quant SELL.

#### 2.3 Why this appears in exit logic, and whether the logic itself is correct

> "why it should be applied in the exit logic? Did i specify that by error? Or am i misunderstanding the logic you are using here?"

**My clarification:** It appears there becuase the current implementation uses Conviction to modify
both incoming BUY and incoming SELL signals...... I have corrected the dev wording to make that explicit.
Whether Conviction should modify SELL execution at all is a separate product decision, which I have
set out with the current distribution and recommendation under Point 10.

## Point 3: Why neutral results need audit details

### What I originally wrote

> Neutral calculations now save their audit fields correctly.

### Rohit sir's exact reply

> - "Neutral calculations now save their audit fields correctly" - whats
> the point of this?

### Question-by-question clarification

#### 3.1 Why neutral calculations need audit fields

> "whats the point of this?"

**My clarification:** Several completly different cases were all appearing as the same 0...... A 0
could mean the evidence was genuinely neutral, confidence was below 70%, there were too few sources,
contrary evidence reduced confidence, or the record was old and never stored the new fields. I fixed
the audit trail so we can see why the result became 0 without changing the score. Neutral still
means no reward and no penalty. The extra fields only explain why.

## Point 4: How the 70% confidence rule works

### What I originally wrote

> CEO and moat agent answers below 70% confidence are treated as neutral.

### Rohit sir's exact reply

> - "CEO and moat agent answers below 70% confidence are treated as
> neutral." ---> "below 70%" -->> remind me how we decide the confidence. and
> if its a step function based and if so based on what attrubute? "treated as
> neutral" ---> what is neutral? in the sense that we dont penalize the
> company? Please show me the whoel formula again when we speak so i can make
> sure i am ok with this.

> 6. remind me how we decide ceo's score confidence? just the data the code
> sources? is there a protocol the codebase followe on finding data and at
> what point does the %age drop/ how does it change? step functiomn or
> soemthing else?

### Question-by-question clarification

#### 4.1 How confidence is decided and whether it is step-based

> "remind me how we decide the confidence. and if its a step function based and if so based on what attrubute?"

> "is there a protocol the codebase followe on finding data and at what point does the %age drop/ how does it change?"

**My clarification:** It is step-based...... but the percentage is not a statistically calibrated
probablity of being right. The model first reports a confidence number based on the evidence it
found. The code then applies these fixed rules in order:

1. Start with the model-reported confidence.
2. If there are fewer than two sources, cap confidence at 35%.
3. If the opposing-evidence text is more than 30 characters longer than the supporting-evidence
   text, cap confidence at 55%.
4. If final confidence is below 70%, the CEO or moat score contributes 0 BQ points.
5. If final confidence is at least 70%, convert the agent's 0-10 assessment into BQ points:
   8 to 10 gives +2, 5 to below 8 gives +1, 3 to below 5 gives 0, and below 3 gives -1.

#### 4.2 What “treated as neutral” means

> "what is neutral? in the sense that we dont penalize the company?"

**My clarification:** Neutral means that this dimension adds 0 and subtracts 0...... it doesnt mean
that the company has an average CEO or moat. It means that we do not have enough confidence to use
that assessment. For example, an 8/10 CEO score with 82% reported confidence would normally add +2
BQ points. If it has only one source, confidence is capped at 35%, so the CEO component becomes 0
instead.

#### 4.3 The complete BQ formula and how confidence affects it

> "Please show me the whoel formula again when we speak so i can make sure i am ok with this."

**My clarification:** The complete BQ calcuation currently used is a direct sum......

`BQ_RAW = revenue quality + growth trajectory + margin quality + balance sheet + ROIC versus WACC + gross-margin trend + debt-maturity risk + CEO quality + management capital allocation + competitive moat + macro tailwind + divergence signal + deal-delay risk + insider ownership + reinvestment runway + capital-return adjustment`

ROIC means return on invested capital and WACC means the estimated cost of that capital. The first
15 terms are the main BQ dimensions. The last term is the separate combined dividend-cut and
buyback-suspension adjustment, capped at -4. Each term is converted into small points, mostly
between -2 and +2, using its own thresholds. The important detail is that the components are simply
added. A missing or low-confidence component contributes 0 and the remaining components are not
reweighted.

The main component logic is:

| BQ component | Current scoring logic in plain English |
|---|---|
| Revenue quality | Rewards stronger gross margin and free-cash-flow margin, capped at +2 |
| Growth trajectory | Uses revenue growth and whether growth is accelerating, from -1 to +2 |
| Margin quality | Uses Rule of 40 for most businesses, distribution coverage for income names, and separate bank and cyclical rules |
| Balance sheet | Uses business-type debt thresholds, debt purpose and short-term maturity risk, generally -2 to +2 |
| ROIC versus WACC | Rewards ROIC above WACC and penalises a negative spread, from -2 to +2 |
| Gross-margin trend | +1 above a 2 percentage-point improvement, -1 below a 2 point deterioration, otherwise 0 |
| CEO, management allocation and moat | Maps the underlying 0-10 assessment into BQ points; the confidence gate applies to agent-produced CEO and moat scores |
| Macro, divergence and deal delay | Macro is -1 to +2, persistent positive divergence adds +2, and verified deal delay is 0 to -2 |
| Insider ownership and reinvestment runway | Insider ownership is -1, 0 or +2; runway is -1, 0 or +1 |
| Capital-return adjustment | Adds the dividend-cut and buyback-suspension penalties, with a combined floor of -4 |

BQ then feeds the other engine layers as follows:

`FS quality base = 50 + (BQ_RAW x 2.5)`

`FS score = clamp(FS quality base + daily valuation points, 0, 100)`

`Raw conviction = BQ_RAW + valuation tax`, where valuation tax can only be 0 or negative and is
capped at -10. Clamp here means the FS score cannot fall below 0 or rise above 100. FS can then
cap the usable conviction for a signal. I have made the reported confidence, each cap, final
confidence, evidence and component contribution visible on dev. On the call I will take you through
this complete chain so we can decide whether model-reported confidence, the text-length check, the
70% step, or the use of neutral for missing evidence should be improved.

## Point 5: What I meant by regression suite

### What I originally wrote

> The relevant regression suite passes with 164 tests.

### Rohit sir's exact reply

> - "The relevant regression suite passes with 164 tests." what do you
> mean "relevant regression suite" - explain with reference to context
> please... what is being regressed on what?

### Question-by-question clarification

#### 5.1 What “regression suite” means here

> "what is being regressed on what?"

**My clarification:** I used the wrong wording for this context...... I meant software regression tests,
not a statistical regression where one variable is regressed on another. Nothing is being regressed
against another variable. These tests rerun known Conviction Engine, API and website rules after a
code change to check that something which worked earlier hasnt broken.

#### 5.2 Which tests I meant by “relevant”

> "what do you mean 'relevant regression suite' - explain with reference to context please"

**My clarification:** After the latest changes, 169 targeted Conviction and API tests passed along
with 6 subtests...... all 64 UI tests passed and the website production build passed. The wider API suite
had 195 passes while the full repository had 1,038 passes and four unrelated existing signals or
sentiment-system test conditions, so none of those failures came from this Conviction work.

## Point 6: What not recorded means

### What I originally wrote

> For older records, some audit fields display not recorded rather than making assumptions.

### Rohit sir's exact reply

> - "For older records, some audit fields display not recorded rather than
> making assumptions" GIVE ME AN EXAMPLE SO I AM CLEAR WHAT AUDIT FIELDS
> DISPLAY NOT RECORDED AND WHY?

### Question-by-question clarification

#### 6.1 An example of fields that show “not recorded”

> "GIVE ME AN EXAMPLE SO I AM CLEAR WHAT AUDIT FIELDS DISPLAY NOT RECORDED"

**My clarification:** One example is `000660.KS`...... whose last full calculation was in Sep start.
Changes covering dividend rollout state, framework completeness, model usage, token usage
and search usage were added later, so that older calculation never recorded those fields.

#### 6.2 Why those fields say “not recorded”

> "AND WHY?"

**My clarification:** Saying false would wrongly claim that we checked the condition and it did not
happen...... Saying unavailble would wrongly claim that we tried to fetch it and failed. “Not recorded”
means the older calculation predates the field. Once we run an approved recalculation, the fields
will receive real values. I have also added this legacy-record explanation on the dev page.

## Point 7: Dividend universe, corrected method and paid data

### What I originally asked

I said I had rerun the dividend comparison across 144 payer records, that 11 records changed under
the corrected method, and asked whether I should request EODHD and FMP commercial quotes for a
limited pilot.

### Rohit sir's exact reply

> 1. "I reran the dividend comparison across 144 payer records" -->> DOES
> THIS MEAN YOU HAD 144 Global companies paying at least 1 year of dividend?
> "Eleven names changed under the corrected method:" - what does "name
> changed? mean?
> "whether a paid provider can supply both reliable dividend-period data and
> historical P/E inputs," - No problem checking both so long as its clear
> that we are not setting a condtion on the AND i e both being Yes. I say
> that because divideng and p/e are very different things and mean different
> things to valuation - most of the stocks we care about are growth style so
> we dont care about dividedn all that much really.
> What percentage of our stock are dividend yield stle stocks? apart from
> some nz and canadian names, i would argue none. So should we be going crazy
> about dividend and paying for it? P/E is different - we always care... for
> the same reasons above i e most stocks we care about are growth stocks ...
> Dividend stovks may come back in fashion and when markets are collpasing or
> over exuberant we do want to assess dividend yield (dividend correctly
> calculated  --- as per the long methodology/ discussion/ story i shared on
> how to do so in different situations blah blah-- divided by CURRENT price)
> to see if it sa sensible number

> "I have not approved a penalty for any of them. The current feed does not
> reliably identify the declared period or distinguish an ordinary dividend
> from a special distribution."--->> Isnt the second sentence a problem?
> Hadnt i suggested a detailed method here or am i smoking dope? :)

> " Option C: use no paid source. The 11 cases remain review-only and the
> dividend penalty stays disabled wherever the period cannot be verified."
> Where did you get 11 from? how many of these are USA versus rest of world
> equity names?
> Whether Option C is viable depends on the answer to these two questions i
> pose? and how reliable the dividend computed as per the methodology i had
> stated and that you aprtially/wholly espouse in this email --
> Remind me do we use trailing dividend always? I have forgotten what i
> speccd... because its been a long time.

### Question-by-question clarification

#### 7.1 Whether 144 meant 144 global one-year dividend payers

> "DOES THIS MEAN YOU HAD 144 Global companies paying at least 1 year of dividend?"

**My clarification:** No...... the 144 was the input set passed to that comparison job. I described it
poorly as payer records. It didnt mean 144 global companies each had one complete year of dividend
history. The current store contains 136 equities, of which 103 have a trailing paid dividend.

#### 7.2 What percentage of the universe is income-style, and whether paid dividend data is justified

> "What percentage of our stock are dividend yield stle stocks?"

> "So should we be going crazy about dividend and paying for it? P/E is different - we always care"

**My clarification:** Twenty-seven of the 136 equities are currently labelled income...... which is
roughly 20%. That clasification still needs some review. I agree that four ambiguous dividend cases
alone do not justify buying a broad paid provider. P/E is the stronger reason to evaluate one.

#### 7.3 What “11 names changed” meant, and their US versus non-US split

> "'Eleven names changed under the corrected method:' - what does 'name changed? mean?"

> "Where did you get 11 from? how many of these are USA versus rest of world equity names?"

**My clarification:** The corrected method produced a different comparision result for 11 records......
it does not mean all 11 are confirmed dividend cuts. Five are clean local candidates: BABA, BDL.NS,
SPK.NZ, SUM.NZ and TD. Four need verification because a special or stale distribution may be mixed
in: BYDDY, FMCC, TWR.NZ and WIPRO.NS. Two, DBC and FXI, are ETFs, so the company dividend-cut rule
should not apply. That leaves 9 equities and 2 ETFs. By issuer domicile, the 9 equities are 1 US and
8 non-US.

#### 7.4 Whether your dividend methodology was implemented, and whether trailing dividend is always used

> "Hadnt i suggested a detailed method here"

> "Remind me do we use trailing dividend always?"

**My clarification:** Yes...... you had specified a detailed method, and we dont always use trailing
dividend. Current yield uses the forward declared annual dividend when available. Trailing paid
dividend is retained as a cross-check. The five-year history uses trailing 12-month dividend divided
by each month-end price. Cut detection compares current declared annual DPS with previous declared
annual DPS. DPS means declared dividend per share.

Your method is implemented as far as the available data allows. The remaining problem is that
yfinance does not reliably identify declaration date, interim versus final dividend, or ordinary
versus special distribution. The calculation can therefore be correct while the event supplied to
it is still ambiguous.

For clarity, `current forward yield = current declared annual DPS / current price`. The historical
monthly series is `trailing 12-month DPS at that month / that month's closing price`. The current
yield z-score is `(current yield - five-year historical mean yield) / five-year historical standard
deviation`. A possible yield trap requires both a z-score above 1.5 and the current yield to be above
the market-specific threshold. The forward and trailing answers are both shown when the basis can
change that result. The current thresholds are 6% for the US/default market, 12% for New Zealand,
10% for Australia, 7% for Canada and 9% for the UK, with 2 percentage points added for banks. The
threshold is deliberately undefined for Korea, Japan and China rather than silently applying the US
rule.

#### 7.5 Whether dividend and P/E are an AND condition for choosing a provider

> "No problem checking both so long as its clear that we are not setting a condtion on the AND i e both being Yes."

**My clarification:** I agree...... dividend and P/E will be tested independently, not as an AND
condition. Since you have confirmed that I can check both, I will request commercial terms and sample
data from EODHD and FMP. I will test each provider seperately on the dividend cases and the missing
P/E names, then report whether either provider is useful for dividends, P/E, both or neither. This
comparison does not authorise a purchase or enable any dividend penalty.

**Action already confirmed:** I will request the quotes and sample data and run the limited
comparison. I will come back to you before any purchase or scoring change.

**Separate terminology correction already confirmed:** “Tavela” meant Tavily. Tavily is useful for
research and source discovery, but it is not an authoritative structured source for dividends or
financial statements.

## Point 8: US equity P/E history and the EPS question

### What I originally asked

I proposed using 20 or more years as full-confidence, 10 to 20 years as provisional and under 10
years as neutral.

### Rohit sir's exact reply

> 2. You wrote - " *A 15-year minimum covers 28 names, 10 years covers 34,
> and 5 years covers 43." *

> WHAT is the distribution for *US EQUITY NAMES* jave available p/e data n
> >=20, 20<n<=15, and so on...  ... n<5 20+ years for full confidence, 10–20
> years as provisional, and under 10 years as neutral.

> Is the answer different if we consider eps as our source instead of p/e
> direct noting we can always get price history for 15-20 years for every
> name...

### Question-by-question clarification

#### 8.1 Distribution of available P/E history for US-style equity names

> "WHAT is the distribution for US EQUITY NAMES jave available p/e data n >=20, 20<n<=15, and so on... ... n<5"

**My clarification:** I checked the 69 equities that the engine routes as US-style tickers...... this is
a reproducible listing-based group and includes some foreign companies listed in the US, so I dont
want to call it pure US domicile. The distribution is:

| Available P/E history | Number of equities |
|---|---:|
| At least 20 years | 18 |
| 15 to below 20 years | 10 |
| 10 to below 15 years | 6 |
| 5 to below 10 years | 5 |
| Under 5 years | 23 |
| No usable series | 7 |
| Total | 69 |

#### 8.2 Whether using EPS instead of direct P/E changes the answer

> "Is the answer different if we consider eps as our source instead of p/e direct"

**My clarification:** No...... becuase that is already how the engine builds historical P/E. For each
old date it divides the price at that date by the trailing EPS known at that date. It never pushes
today's EPS backwards. SEC supplies deep point-in-time EPS for 44 of the 69 names, yfinance supplies
17, and 8 have no source metadata. Price history is not the constraint. Historical point-in-time EPS
depth is.

The formula at each historical month is:

`Historical P/E = month-end price / latest positive trailing 12-month EPS known by that date`

Negative or zero EPS observations are excluded. The current P/E percentile is the percentage of
valid historical P/E observations at or below today's P/E. At the moment, fewer than 20 years marks
the history insufficient and sets that percentile contribution to neutral. My proposed tier changes
only this history-confidence gate, not the P/E formula itself.

When the history is eligible, the percentile contributes to FS as follows: below the 20th percentile
adds 10 FS points, the 20th to below the 40th adds 5, the 40th to below the 60th adds 0, the 60th to
below the 80th subtracts 5, and the 80th percentile or above subtracts 10. This is the valuation part
of FS, not a direct BQ component.

#### 8.3 The proposed full-confidence, provisional and neutral history rule

> "20+ years for full confidence, 10–20 years as provisional, and under 10 years as neutral."

**My clarification:** My suggestion is still 20 years or more as full-confidence, 10 to 20 as
clearly marked provisional and under 10 as neutral...... i have kept the strict 20-year rule active until
you confirm this. This decision changes the minimum history gate, not how P/E itself is calculated.

**Q2:** Should I use the tiered policy, 20 years or more full-confidence, 10 to 20 provisional and
under 10 neutral?

## Point 9: Starbucks classification

### What I originally asked

I asked whether dominant operating segment should be the default tie-break for mixed businesses,
with documented overrides, and whether SBUX should remain a compounder.

### Rohit sir's exact reply

> 3. yes to the first part of. your q in general

> for sbux specifically it is probably a mature compounded perhaps
> transitioning to an income style company...

> the word "compounder" relates to compound interest i imagine or compounded
> growth which reminds me of CAGR... Perhaps we look at teh last 10, 5 2
> years of cagr of starbucks and assess...

> let me know those numbers

### Question-by-question clarification

#### 9.1 The general mixed-business classification rule

> "yes to the first part of. your q in general"

**My clarification:** I have recorded your confirmation that dominant operating segment should be
the default tie-break for mixed businesses...... with a documnted override where the current transition
or economics make the default misleading.

#### 9.2 Starbucks' 10-year, 5-year and 2-year CAGRs

> "Perhaps we look at teh last 10, 5 2 years of cagr of starbucks and assess... let me know those numbers"

**My clarification:** I pulled the Starbucks figures from its SEC filings...... cagr means the average
yearly growth rate.

| Starbucks metric | 10-year CAGR | 5-year CAGR | 2-year CAGR |
|---|---:|---:|---:|
| Revenue | 6.85% | 9.60% | 1.67% |
| Diluted EPS | -1.10% | 15.59% | -32.52% |
| Free cash flow | -0.01% | 84.51% | -18.48% |
| Declared DPS | 13.68% | 14.78% | 6.50% |

For context, `CAGR = (ending value / starting value)^(1 / number of years) - 1`. It converts the
whole-period change into one compounded annual rate. It can be misleading when the starting year is
abnormally weak, which is why I have shown 10, 5 and 2 years instead of relying on one window. The
five-year EPS and cash-flow numbers look unusually strong because they start from the depressed
FY2020 base, while the last two years show clear operating deterioration and the dividend is still
growing.

#### 9.3 Whether Starbucks should be treated as a mature compounder or income-style company

> "for sbux specifically it is probably a mature compounded perhaps transitioning to an income style company"

**My clarification:** I agree with that description...... the evidence looks more like a mature or
transitioning compounder and doesnt really look like a clean income stock, especially with current stored yield only 2.59%.
My suggestion is to keep SBUX as compounder with a documented mature/transitioning override and
revisit it once we define a proper hybrid rule.

**Q3:** Do you confirm that SBUX should remain compounder with a mature/transitioning override for now?

## Point 10: Whether Conviction should modify quant exits

### What I originally asked

I asked whether HARD EXIT and FULL EXIT should be merged because both currently retain 0%, or
whether they should have different execution rules.

### Rohit sir's exact reply

> 4. A more fundamental q - why do we use the term EXIT ? dont we use
> teh conviction engine to edecide / modify entries from our normal quanty
> model? so its eitehr enter or annul enter? by Exit are you/the model
> seeking to annual an ENTRY?

> I ask this because i saw some chat earlier whic hsuggested teh con viction
> engine was being used on our quant model exit decisions.

> I can answder your q again based on this answer + based on the disribution
> lets say today and in past / bear markets on our body of names.. i dsay
> look look at all s and p 500 names and run the cionviciotn engine, what is
> the distrbiuton of BQ raw... then recommend whether we shd merge or no. I
> think the decision will be apparent based on the distribution, n'est-ce pas?

### Question-by-question clarification

#### 10.1 Why the engine uses EXIT language and whether it modifies quant SELLs

> "why do we use the term EXIT ? dont we use teh conviction engine to edecide / modify entries from our normal quanty model?"

> "i saw some chat earlier whic hsuggested teh con viction engine was being used on our quant model exit decisions."

**My clarification:** You spotted the main design issue correctly...... I checked the current flow and
Conviction is being used on both incoming BUY and incoming SELL signals. It doesnt create a SELL on
its own. The term EXIT appears because, after the quant model sends a SELL, Conviction can currently
pause it, reduce it, fully exit or hard-exit it.

#### 10.2 The exact current SELL logic

> "by Exit are you/the model seeking to annual an ENTRY?"

**My clarification:** No...... EXIT doesnt annul an earlier entry instruction. It is the current
Conviction treatment of a new SELL instruction received from the quant model.

For context, the current decision chain is `raw conviction = BQ_RAW + valuation tax`, followed by
any FS cap. For an incoming quant SELL, yield trap, weak FS or an uncovered verified dividend cut
forces HARD EXIT. Otherwise, when conviction is below +2, BQ below 0 gives HARD EXIT with 0%
retained, BQ from 0 to below 5 gives FULL EXIT with 0% retained, and BQ of 5 or more gives PARTIAL
EXIT with 50% retained. When conviction is at least +2, the existing short-term or long-term sell
table is used. None of this runs unless the quant model first sends a SELL.

For completeness, the current conviction-intact SELL table is:

| Incoming quant SELL | Short-term signal | Long-term signal |
|---|---|---|
| Conviction 8 or more | PAUSE SELL, retain 0% | PAUSE SELL, retain 70% |
| Conviction 5 to below 8 | PARTIAL EXIT, retain 0% | PARTIAL EXIT, retain 50% |
| Conviction 2 to below 5 | FULL EXIT, retain 0% | FULL EXIT, retain 0% |

The short-term labels can therefore differ while all three retain 0%. This is another reason I do
not want to present the labels as settled execution policy before we confirm the intended role of
Conviction on SELLs.

#### 10.3 Today's BQ distribution and what it says about merging HARD and FULL EXIT

> "run the cionviciotn engine, what is the distrbiuton of BQ raw... then recommend whether we shd merge or no."

**My clarification:** Across the 136 equities, 12 have BQ below 0, 40 are from 0 to below 5 and 84
are 5 or above...... Fifty-five currently have conviction below +2. If all 55 received a quant SELL,
the current ladder would produce 12 HARD EXIT, 28 FULL EXIT and 15 PARTIAL EXIT. HARD and FULL both
retain 0%, so 40 names would have different labels but the same practical action. I dont think we should merge
or refine those labels until we first decide whether Conviction should modify SELL execution at all.

#### 10.4 Past and bear-market distribution, including the requested S&P 500 study

> "based on the disribution lets say today and in past / bear markets on our body of names"

> "look at all s and p 500 names and run the cionviciotn engine"

**My clarification:** I cannot honestly give you the past and bear-market S&P 500 distribution from
the current store...... becuase our archive starts in May 2026 and contains signal subsets, not
point-in-time BQ snapshots for all 500 names. Using today's fundamentals on old prices would
introduce look-ahead bias, meaning we would be using information that was not known at the
historical date, so a valid replay needs historical membership, point-in-time fundamentals and a
rule for the five model-driven dimensions.

#### 10.5 My recommendation pending that historical evidence

> "then recommend whether we shd merge or no. I think the decision will be apparent based on the distribution"

**My clarification:** Given your 80% quant and 20% fundamental framing, my suggestion is to use
Conviction to modify entries and only show a non-binding fundamental warning on an incoming quant
SELL until a proper historical replay proves that changing exit execution adds value...... This differs
from the 1 September sell ladder, so i have not changed the behavior.

**Q4:** Should Conviction be entry-only with a warning on quant SELLs, or should it continue to
modify SELL execution?

**Q5:** Do you want me to scope the full point-in-time S&P 500 replay as a separate data and compute
project, or is the current 136-name distribution enough for this product decision?

## Point 11: Telco and regulated-utility counts

### What I originally asked

I asked whether telcos and regulated utilities should have separate frameworks or one shared
capital-intensive framework, while keeping both coverage-incomplete until the rules are ready.

### Rohit sir's exact reply

> 5.how many telcos usa , regulated utolities usa , telcos non usa, regulated
> utilities non usa do we have? once we have this info we can discuss and
> finalize on the call

### Question-by-question clarification

#### 11.1 The requested US and non-US counts

> "how many telcos usa , regulated utolities usa , telcos non usa, regulated utilities non usa do we have?"

**My clarification:** I checked the current universe using issuer domicile and industry metdata......

| Category | Count | Companies |
|---|---:|---|
| US telcos | 0 | None |
| US regulated utilities | 0 | None |
| Non-US telcos | 4 | CNU.NZ, SPK.NZ, T.TO and SFTBY |
| Non-US regulated utilities | 1 | BIPC.TO |

CEN.NZ, GNE.NZ, MCY.NZ and MEL.NZ are utilities, but they are renewable or independent-power
businesses rather than regulated utilities, so I did not include them in the regulated count.

#### 11.2 What I recommend before we finalise the frameworks on the call

> "once we have this info we can discuss and finalize on the call"

**My clarification:** Given the sample is only 4 telcos and 1 regulated utility...... my suggestion is to
keep both categories coverage-incomplete until you give the thresholds. Coverage-incomplete means
they remain neutral because the scoring framework is unfinished. I would still build seperate
frameworks because their regulation, leverage and cash-flow economics are different.

**Q6:** Should I keep both categories coverage-incomplete for now and build separate frameworks
after we finalise the thresholds on the call?

## Point 12: What the qualitative agents do and what they cost

### What I originally asked

I asked whether I could compare a cheaper and stronger model on NVDA and GOOGL before requesting
approval for a full-universe run.

### Rohit sir's exact reply

> 6.  agent etc - lets discuss on the call... i need to understand this
> better. what do you mean "compare suitable models"...

> we can take a decision very quicly on the call... i need to assess what the
> agent can / cant do, why we need it , my instinct is if its costly to not
> do it because we are not seeking fundamentel based decision making as a
> primary objective. i e fundamental is like 20% say and quanty is say 80% ...

### Question-by-question clarification

#### 12.1 What the agents can do and why we need them

> "i need to assess what the agent can / cant do, why we need it"

**My clarification:** The agents basically score five qualitative areas that statements alone do not fully
capture: CEO quality, competitive moat, macro tailwind, deal delay, and market size or reinvestment
runway...... they can search for evidence, record sources and contrary evidence, produce a score and
report confidence. They cannot make the primary trading decision or guarantee that a source is
correct...... they cant replace the quant model either. Their intended role is to support it, not
override it.

#### 12.2 What I mean by “compare suitable models”

> "what do you mean 'compare suitable models'"

**My clarification:** I mean running the same five questions for NVDA and GOOGL through Haiku 4.5
and Sonnet 5...... then comparing score agreement, source quality, missed contrary evidence, final
confidence and actual cost. its a small two-name test, not permission for a universe-wide run.

#### 12.3 Cost and the 80% quant versus 20% fundamental balance

> "my instinct is if its costly to not do it because we are not seeking fundamentel based decision making as a primary objective. i e fundamental is like 20% say and quanty is say 80%"

**My clarification:** The current default is Sonnet 4.5 and a full 136-equity run needs at least 680
model calls...... even with only one web search per dimension, search cost starts around USD 6.80 before
model tokens and repeat searches. The two old stored runs dont tell us the realised cost because
usage metering did not exist then.

The call count is `136 equities x 5 qualitative dimensions = 680 calls`. The USD 6.80 search estimate
is `680 searches / 1,000 x USD 10`, assuming only one search in each call. Model input and output
tokens, fetched pages, retries and any extra searches are additional, so USD 6.80 is a floor rather
than a full-run quote. My recommendation matches your instinct: leave these dimensions off by
default unless the small test shows useful extra information, and do not start the 680-call universe
run.

**Q7:** Should the five qualitative dimensions remain off by default? If you want a small proof
first, may I run the two-name model comparison with a hard USD 5 total cap?

## Decisions I still need from you

1. After rollout approval, should a verified actual dividend cut automatically receive the existing
   BQ penalty while an unverified cut scores 0?
2. Should P/E history use 20 years or more as full-confidence, 10 to 20 as provisional and under 10
   as neutral?
3. Should SBUX remain compounder with a mature/transitioning override?
4. Should Conviction be entry-only with a warning on quant SELLs, or continue modifying SELL
   execution?
5. Should I scope the full point-in-time S&P 500 replay as a separate project?
6. Should telcos and regulated utilities remain coverage-incomplete until we set separate rules?
7. Should qualitative agents stay off by default, with only the USD 5 two-name pilot first?

## What I have already fixed on dev

I have already corrected the confusing audit language on the development website on port 8514. It
now separates dividend rollout approval from event verification, states that Conviction never
creates a standalone exit, shows the confidence inputs and caps, explains old not-recorded fields
and shows the six P/E-history bands over the 136 equities.

The dev API is on v1.17.0 and the website is serving the live 197-record audit...... I have not changed
the scoring policy, bulk-recalculated the store, bought or enabled a provider, run the paid model
pass, changed SELL behavior or touched production.

Thanks,

Divyanshu
