# Draft reply to Rohit

**Subject:** Conviction Engine follow-up: your questions, my clarifications, evidence and decisions

Hi sir,

Thanks for the detailed reply. I have reorganised my response point by point so that, for every
item, you can see:

1. what I originally wrote or asked;
2. what you replied and what clarification or evidence you requested;
3. my clarification and the evidence now available; and
4. the exact decision, if any, that is still required from you.

I also corrected the terminology on the development website where my earlier wording was
misleading. Those wording and audit changes do not alter any score.

---

## Point 1 — Possible dividend cut, actual dividend cut and where the penalty belongs

### What I originally wrote

> “A possible dividend cut is recorded for review, but it does not reduce BQ and cannot trigger
> HARD EXIT until the dividend penalty is explicitly approved.”

### Your reply and clarification required

**Rohit's exact reply:**

> - "A possible dividend cut is recorded for review, but it does not
> reduce BQ and cannot trigger HARD EXIT until the dividend penalty is
> explicitly approved."--->>>>> what if its an actual dividend cut versus
> possible dividend cut? Yes a possible dividend cut neednt reduce BQ... OK.
> Yes naturally if its just "possible" it shouldnt trigger HARD EXIT. "until
> the dividend penalty is explicitly approved"--->>> what do you mean? We
> have to decide all this now. Dont we already have a dividend penalty in our
> calculation of FS..? or at some other stage?  have it in BQ at the moment?

You agreed that a **possible** cut should not reduce BQ or trigger HARD EXIT, but asked:

- what happens when the cut is actual rather than merely possible;
- what “until explicitly approved” means;
- whether the penalty already exists; and
- whether the penalty belongs in FS or BQ.

### My clarification and evidence

The dividend-cut penalty already exists in **BQ**, not FS. Your 30 July specification is:

| Decline in declared annual DPS | BQ effect |
|---|---:|
| 0% to 25% | 0 |
| 25% to 50% | -1 |
| 50% to 75% | -2 |
| 75% to 100% | -3 |

The combined buyback-plus-dividend penalty is capped at -4.

My phrase “until explicitly approved” mixed up two different controls:

- **One-time methodology rollout:** approval to enable the corrected dividend method across the
  store after its source and universe differences have been reviewed.
- **Per-event verification:** evidence that a particular candidate is a genuine ordinary dividend
  cut rather than a special distribution, stale period or data attribution problem.

I did **not** mean that every real cut should require permanent manual approval. The clean operating
rule is:

- possible or unverified cut: display it for review, but score 0;
- source-verified actual cut: automatically apply your existing BQ tier after the corrected
  methodology has received its one-time rollout approval.

The dev audit now uses the separate labels **Dividend scoring rollout** and
**Dividend event verification**, so the two controls are no longer presented as the same thing.

### Decision required — Q1

Please confirm that, after the one-time rollout is approved, a source-verified actual cut should
automatically apply the existing BQ tier, while a possible or unverified cut remains visible but
scores 0.

---

## Point 2 — What the “same approval gate in exit logic” means

### What I originally wrote

> “The same approval gate is applied in the exit logic.”

### Your reply and clarification required

**Rohit's exact reply:**

> - "The same approval gate is applied in the exit logic." What do you
> mean? Are you saying we dont exit a trade based on some conviction engine
> attribute? sorry am not clear what approval gate you refer to and why it
> should be applied in the exit logic? Did i specify that by error? Or am i
> misunderstanding the logic you are using here?

You asked whether I was saying that we do not exit based on a Conviction Engine attribute, what the
approval gate was, why it belonged in exit logic, and whether that behavior came from your
specification or from my interpretation.

### My clarification and evidence

The Conviction Engine does **not** originate a standalone exit. It receives a normal quant signal
and may modify its treatment. The current implementation can modify both an incoming BUY and an
incoming SELL.

The dividend safety condition only means that an **unverified dividend candidate cannot escalate
an incoming quant SELL into HARD EXIT**. It does not stop the quant model from producing its SELL,
and it does not create an independent Conviction Engine exit.

I have corrected the dev page to state this plainly:

> Conviction modifies an incoming quant SELL only. It never creates a standalone exit.

Your latest reply raises the more fundamental product question of whether Conviction should modify
SELLs at all. I address that, with the current distribution, under Point 10.

---

## Point 3 — Why neutral calculations need audit fields

### What I originally wrote

> “Neutral calculations now save their audit fields correctly.”

### Your reply and clarification required

**Rohit's exact reply:**

> - "Neutral calculations now save their audit fields correctly" - whats
> the point of this?

You asked what the point of saving those fields is.

### My clarification and evidence

“Neutral” means the dimension contributes **0 to BQ**: it neither rewards nor penalises the
company. The audit detail is still necessary because several very different situations otherwise
look like the same zero:

- the evidence genuinely supports a neutral conclusion;
- the answer was below the 70% confidence threshold;
- too few sources were available;
- contrary evidence caused a confidence cap; or
- the record predates the audit field and was never recalculated.

Saving the audit trail lets us verify *why* the score was zero without changing the score. The dev
page now shows the reported confidence, any deterministic caps, source count, final confidence and
available supporting/opposing evidence.

---

## Point 4 — How the 70% CEO/moat confidence rule works and what neutral means

### What I originally wrote

> “CEO and moat agent answers below 70% confidence are treated as neutral.”

### Your reply and clarification required

**Rohit's exact reply:**

> - "CEO and moat agent answers below 70% confidence are treated as
> neutral." ---> "below 70%" -->> remind me how we decide the confidence. and
> if its a step function based and if so based on what attrubute? "treated as
> neutral" ---> what is neutral? in the sense that we dont penalize the
> company? Please show me the whoel formula again when we speak so i can make
> sure i am ok with this.

You returned to the same point later:

> 6. remind me how we decide ceo's score confidence? just the data the code
> sources? is there a protocol the codebase followe on finding data and at
> what point does the %age drop/ how does it change? step functiomn or
> soemthing else?

You asked:

- how confidence is decided;
- whether it is a step function and which attributes drive it;
- whether neutral means that the company is not penalised; and
- to see the full BQ formula again on the call.

You repeated the confidence question later when asking what data and source protocol the code uses
and when the percentage falls.

### My clarification and evidence

It is a rule-based confidence gate, not a statistically calibrated probability.

1. The model reports a starting confidence under the evidence prompt.
2. Python then applies deterministic checks:
   - fewer than two sources caps confidence at 35%;
   - if the opposing-evidence text is materially longer than the supporting evidence, confidence is
     capped at 55%;
   - final confidence below 70% makes the dimension contribute 0.
3. A neutral result means no reward and no penalty.

The opposing-evidence text-length test is crude. I have not changed that policy silently; I have
made its effect visible in the audit so we can review the starting confidence, cap, source count,
final confidence and evidence together. I will also walk through the full BQ formula on the call.

---

## Point 5 — What “the relevant regression suite passes” means

### What I originally wrote

> “The relevant regression suite passes with 164 tests.”

### Your reply and clarification required

**Rohit's exact reply:**

> - "The relevant regression suite passes with 164 tests." what do you
> mean "relevant regression suite" - explain with reference to context
> please... what is being regressed on what?

You asked what was being regressed on what, with reference to the context.

### My clarification and evidence

I meant **software regression tests**, not a statistical regression. These tests rerun known
Conviction Engine and API behaviors after a code change to ensure that an earlier working rule has
not been broken.

After the latest audit changes:

- 169 targeted Conviction/API tests passed, together with 6 subtests;
- all 64 UI tests passed;
- the Nuxt production build completed;
- the wider API suite had 195 passes and one unrelated failure; and
- the full repository suite reached 1,038 passes, with four unrelated existing signals/SSI test
  conditions.

The unrelated API failure is an NU shortlist row that is four calendar days old but reports
`days_elapsed=0`. It is a signals-surface issue, not a Conviction Engine failure.

---

## Point 6 — Example of an audit field showing “not recorded”

### What I originally wrote

> “For older records, some audit fields display not recorded rather than making assumptions.”

### Your reply and clarification required

**Rohit's exact reply:**

> - "For older records, some audit fields display not recorded rather than
> making assumptions" GIVE ME AN EXAMPLE SO I AM CLEAR WHAT AUDIT FIELDS
> DISPLAY NOT RECORDED AND WHY?

You asked for a concrete example of which fields show “not recorded” and why.

### My clarification and evidence

`000660.KS` last had a full calculation on 27 August. The newer September fields for dividend
rollout state, framework completeness and model/token/search usage did not exist at that time.

The audit therefore says **not recorded**. That is different from:

- `false`, which would assert that the condition was checked and did not occur; and
- `unavailable`, which would assert that a fetch was attempted but the data was unavailable.

After an approved recalculation, those fields will receive real values. The dev table now also
shows a legacy-record explanation rather than leaving “not recorded” unexplained.

---

## Point 7 — Dividend universe, corrected method and paid-provider question

### What I originally asked

I said that I had rerun the dividend comparison across 144 payer records, that 11 names changed
under the corrected construction, and asked whether I should request commercial quotes from EODHD
and FMP for a limited pilot.

### Your reply and evidence required

**Rohit's exact reply:**

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

You asked:

- whether 144 meant 144 global companies with at least one full year of dividends;
- what “11 names changed” meant;
- what proportion of the universe is actually dividend-yield style;
- whether dividend and P/E were being treated as an AND condition;
- whether paying for dividend data is justified for a growth-heavy universe;
- why the current feed limitation remains if you had already specified a detailed method;
- where the 11 cases came from and how many are US versus non-US equities; and
- whether the engine always uses trailing dividend.

You also said that P/E matters more broadly than dividends, while dividend yield still matters in
market stress or exuberance when calculated correctly against current price.

### My clarification and evidence

The 144 figure was the input set to the comparison job. It did **not** mean 144 global companies
with a complete one-year dividend record. It included non-equity instruments and records with
usable payment history.

The current store contains 136 equities:

- 103 have a trailing paid dividend: 75.7%;
- 27 are currently classified as `income`: 19.9%; and
- that 19.9% remains only a rough dividend-style proxy because some automatic classifications need
  review.

“Eleven names changed” means that the corrected construction changed the detected dividend result
for these records:

| Group | Names | Treatment |
|---|---|---|
| Clean local candidates | BABA, BDL.NS, SPK.NZ, SUM.NZ, TD | Can be verified from the available local history |
| Special/stale distribution verification needed | BYDDY, FMCC, TWR.NZ, WIPRO.NS | Keep review-only until the event type/period is verified |
| ETFs, not company dividend-cut cases | DBC, FXI | Exclude from the company cut rule |

That is 9 equities and 2 ETFs. By issuer domicile, the 9 equities are 1 US and 8 non-US. By listing
convention, they are 4 unsuffixed or US-listed equities and 5 local listings. Issuer domicile is the
cleaner basis for the final comparison.

The engine does not use trailing dividend for everything:

- current yield uses forward declared annual dividend when available;
- trailing paid dividend is retained separately as a cross-check;
- the five-year yield history uses trailing-twelve-month dividend divided by the price at each
  month-end, up to 60 observations; and
- cut detection is intended to compare current declared annual DPS with prior declared annual DPS.

Your detailed method is implemented as far as the current data allows. The remaining limitation is
the source metadata: yfinance does not reliably identify declaration date, interim/final period or
ordinary/special distribution type. The method can be correct while an input event is still
ambiguous.

Dividend and P/E are **not** being treated as an AND condition. Dividend alone does not justify a
broad paid provider for only four equity cases needing special-distribution verification. P/E depth
is the stronger reason to assess a paid source.

I have also recorded your confirmation that “Tavela” meant **Tavily**. Tavily can support research
and evidence discovery, but it is not an authoritative structured source for dividend events or
historical financial statements.

### Options and my suggestion

- **Option A — EODHD and FMP:** request commercial terms and sample output from both, test them
  independently on the 11 dividend records and the missing-P/E names, then recommend one, both or
  neither. This is my recommendation because it tests the two use cases separately.
- **Option B — EODHD only:** quicker for dividend-event metadata, but P/E/fundamental coverage may
  require a second provider later.
- **Option C — no paid source:** keep ambiguous cases review-only and leave their BQ effect at 0.

I will not purchase a plan or enable a penalty based on a personal-plan price.

### Decision required — Q2

May I request commercial quotes and sample output from both EODHD and FMP and run the limited,
independent comparison described above?

---

## Point 8 — US equity P/E coverage and whether EPS changes the answer

### What I originally asked

I proposed 20-plus years as full-confidence, 10 to 20 years as provisional, and under 10 years as
neutral.

### Your reply and evidence required

**Rohit's exact reply:**

> 2. You wrote - " *A 15-year minimum covers 28 names, 10 years covers 34,
> and 5 years covers 43." *

> WHAT is the distribution for *US EQUITY NAMES* jave available p/e data n
> >=20, 20<n<=15, and so on...  ... n<5 20+ years for full confidence, 10–20
> years as provisional, and under 10 years as neutral.

> Is the answer different if we consider eps as our source instead of p/e
> direct noting we can always get price history for 15-20 years for every
> name...

You asked for the detailed distribution specifically for **US equity names**, including the 20+,
15–20, 10–15, 5–10 and under-5-year bands. You also asked whether the answer changes if historical
EPS is used as the source because price history is generally available.

### My clarification and evidence

Using the engine's unsuffixed-ticker route as the reproducible operational “US” set gives 69
equities. This is a listing/routing definition and includes foreign ADRs; it is not pure issuer
domicile.

| Available P/E history | US-route equities |
|---|---:|
| 20 years or more | 18 |
| 15 to under 20 years | 10 |
| 10 to under 15 years | 6 |
| 5 to under 10 years | 5 |
| Under 5 years | 23 |
| No usable series | 7 |

Using EPS does not change the underlying answer because that is already how the engine constructs
historical P/E: at each historical date, it divides historical price by trailing EPS known at that
date. It does not apply today's EPS backwards.

SEC EDGAR supplies deep point-in-time EPS history for 44 of the 69 names; yfinance supplies 17; 8
currently have no source metadata. Historical price is widely available. Point-in-time EPS depth
is the limiting input.

The live dev audit also shows the six requested bands and source for the full 136-equity universe:
18 / 10 / 6 / 9 / 66 / 27.

### Options and my suggestion

- **Option A — strict:** 20+ years affects scoring; everything shorter remains neutral.
- **Option B — tiered:** 20+ years is full-confidence, 10–20 years is clearly labelled provisional,
  and under 10 years remains neutral. This is my recommendation.
- **Option C — all available history:** widest coverage, but unstable short-history percentiles can
  look more precise than they are.

### Decision required — Q3

Should 20+ years remain full-confidence, 10 to under 20 years become clearly labelled provisional
scoring, and under 10 years remain neutral? The strict 20-year rule remains active until confirmed.

---

## Point 9 — Starbucks classification and requested CAGR evidence

### What I originally asked

I asked whether dominant operating segment should be the default tie-break for multi-segment
companies, with documented overrides, and whether SBUX should remain `compounder`.

### Your reply and evidence required

**Rohit's exact reply:**

> 3. yes to the first part of. your q in general

> for sbux specifically it is probably a mature compounded perhaps
> transitioning to an income style company...

> the word "compounder" relates to compound interest i imagine or compounded
> growth which reminds me of CAGR... Perhaps we look at teh last 10, 5 2
> years of cagr of starbucks and assess...

> let me know those numbers

You said yes to the first part in general. For Starbucks, you suggested that it may be a mature
compounder transitioning toward an income-style company and asked for its 10-, 5- and 2-year CAGRs
before deciding.

### My clarification and evidence

Using Starbucks SEC filings:

| Metric | 10-year CAGR | 5-year CAGR | 2-year CAGR |
|---|---:|---:|---:|
| Revenue | 6.85% | 9.60% | 1.67% |
| Diluted EPS | -1.10% | 15.59% | -32.52% |
| Free cash flow | -0.01% | 84.51% | -18.48% |
| Declared DPS | 13.68% | 14.78% | 6.50% |

The five-year EPS and FCF CAGRs are flattered by the depressed FY2020 base. The two-year figures
show current operating deterioration, while the dividend continues to grow. Current stored yield
is 2.59%, which is not enough by itself to make Starbucks a classic income stock.

My recommendation is to keep SBUX as a `compounder` with a documented `mature/transitioning`
override, rather than automatically reclassify it as `income`. We can revisit it after defining a
formal mature-compounder or hybrid rule.

### Decision required — Q4

After seeing the CAGR evidence, do you confirm that SBUX should remain `compounder` with a
documented `mature/transitioning` override for now?

---

## Point 10 — Entry modification, quant SELL modification and historical BQ distribution

### What I originally asked

I asked whether HARD EXIT and FULL EXIT should be merged because both currently retain 0%, or
whether they should have different execution rules.

### Your reply and evidence required

**Rohit's exact reply:**

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

You raised the more fundamental question: why the Conviction Engine uses the word EXIT if its role
is to decide or modify entries from the normal quant model. You asked whether it is also being used
on quant exit decisions.

You said you would answer the label/execution question after seeing:

- today's BQ distribution;
- past and bear-market distributions; and
- preferably the distribution across all S&P 500 names.

### My clarification and evidence

The current implementation modifies both incoming BUY and incoming SELL signals. It never creates
an exit without an incoming quant SELL.

Current BQ distribution:

| BQ band | All 136 equities | 69 US-route equities |
|---|---:|---:|
| Below 0 | 12 | 6 |
| 0 to under 5 | 40 | 16 |
| 5 or more | 84 | 47 |

Across the 136 equities, 55 currently have conviction below +2. If each received a quant SELL, the
present ladder would label 12 HARD EXIT, 28 FULL EXIT and 15 PARTIAL EXIT. HARD and FULL both retain
0%, so 40 of those 55 names would currently have identical sizing but different reason codes.

I cannot honestly produce the requested historical/bear-market S&P 500 distribution from the
current store. The archive begins in May 2026 and contains signal subsets, not point-in-time BQ
snapshots for 500 constituents. A valid replay needs:

- historical index membership;
- point-in-time fundamentals;
- a policy for replaying or replacing the model-driven dimensions; and
- explicit prevention of look-ahead bias.

Using today's fundamentals against historical prices would not be valid evidence.

Given your approximate 80% quant / 20% fundamental framing, my recommendation is:

- use Conviction to modify entries; and
- on an incoming quant SELL, show a non-binding fundamental warning until a valid historical replay
  demonstrates that changing exit execution adds value.

This recommendation differs from the 1 September sell ladder, so I will not change it without your
confirmation.

### Decisions required

**Q5.** Should Conviction be entry-only plus a warning on quant SELLs, or should it continue to
modify quant SELL execution? If it continues to modify SELLs, I recommend one displayed `EXIT`
action with the present reason codes retained internally until HARD and FULL have genuinely
different execution.

**Q6.** Do you want the full point-in-time S&P 500 current/past/bear replay scoped as a separate
data-and-compute project, or is the current 136-name distribution enough for the product decision?

---

## Point 11 — Telco and regulated-utility counts

### What I originally asked

I asked whether you wanted separate telco and regulated-utility frameworks or one shared
capital-intensive framework, while keeping both coverage-incomplete until the rules are supplied.

### Your reply and evidence required

**Rohit's exact reply:**

> 5.how many telcos usa , regulated utolities usa , telcos non usa, regulated
> utilities non usa do we have? once we have this info we can discuss and
> finalize on the call

You asked how many US telcos, US regulated utilities, non-US telcos and non-US regulated utilities
are in the current universe, after which we can discuss and finalise the framework on the call.

### My clarification and evidence

Using issuer domicile and current industry metadata:

| Category | Count | Names |
|---|---:|---|
| US telcos | 0 | None |
| US regulated utilities | 0 | None |
| Non-US telcos | 4 | CNU.NZ, SPK.NZ, T.TO, SFTBY |
| Non-US regulated utilities | 1 | BIPC.TO |

CEN.NZ, GNE.NZ, MCY.NZ and MEL.NZ are utilities, but their metadata describes renewable or
independent-power businesses rather than regulated utilities, so I excluded them from the regulated
count.

My suggestion is to keep the 4 telcos and 1 regulated utility coverage-incomplete until you provide
the thresholds. When built, telco and regulated-utility frameworks should remain separate because
their regulation, leverage and cash-flow economics differ.

### Decision required — Q7

Given the current count, should both categories remain coverage-incomplete until you provide the
thresholds on the call, with separate frameworks built later?

---

## Point 12 — What the qualitative agents do, model comparison and cost

### What I originally asked

I asked whether I could run a controlled replacement-model comparison on NVDA and GOOGL before
requesting approval for a full-universe run.

### Your reply and clarification required

**Rohit's exact reply:**

> 6.  agent etc - lets discuss on the call... i need to understand this
> better. what do you mean "compare suitable models"...

> we can take a decision very quicly on the call... i need to assess what the
> agent can / cant do, why we need it , my instinct is if its costly to not
> do it because we are not seeking fundamentel based decision making as a
> primary objective. i e fundamental is like 20% say and quanty is say 80% ...

You said this should be discussed on the call and asked:

- what “compare suitable models” means;
- what the agent can and cannot do;
- why the agent is needed; and
- whether the cost is justified when fundamentals are roughly 20% and the quant model roughly 80%.

### My clarification and evidence

The five model-driven dimensions are:

1. CEO quality;
2. competitive moat;
3. macro tailwind;
4. deal delay; and
5. TAM/reinvestment runway.

Their purpose is to score qualitative evidence that structured financial statements do not fully
capture. They are not intended to override the quant model.

The current default is Sonnet 4.5. A full 136-equity pass requires at least 680 dimension calls.
With one search per dimension, the search component alone starts around USD 6.80 before model tokens
and repeated searches. The two old stored runs predate usage metering, so they cannot provide a
reliable realised per-name cost.

“Compare suitable models” means running the same two companies and the same five prompts through a
cheaper and a stronger model, then comparing:

- score agreement;
- evidence quality and provenance;
- missed contrary evidence;
- final confidence/caps; and
- actual token and search cost.

I would compare Haiku 4.5 with Sonnet 5 on NVDA and GOOGL under a hard USD 5 total cap. I would not
run the full 680-call universe before reviewing that result.

My recommendation, consistent with your 80/20 framing, is to leave the qualitative dimensions off
by default and run them only for specifically requested names unless the small pilot demonstrates
useful incremental information.

### Decision required — Q8

Should the five qualitative dimensions remain off by default? If you want evidence before deciding,
may I run the NVDA/GOOGL Haiku 4.5 versus Sonnet 5 comparison with a hard USD 5 total cap?

---

## Numbered decisions for your reply

For ease of reply, the remaining decisions are:

1. **Dividend event rule:** after one-time rollout approval, should a source-verified actual cut
   automatically apply the existing BQ tier, while possible/unverified cuts score 0?
2. **Provider comparison:** may I request EODHD and FMP commercial quotes/sample output and run the
   limited independent comparison?
3. **P/E history policy:** 20+ years full-confidence, 10–20 provisional, under 10 neutral?
4. **SBUX:** keep `compounder` with a documented `mature/transitioning` override?
5. **SELL behavior:** entry-only plus a warning on quant SELLs, or continue modifying quant SELL
   execution?
6. **Historical replay:** scope a separate point-in-time S&P 500 replay, or use the current 136-name
   distribution for the product decision?
7. **Telco/utilities:** keep coverage-incomplete until you provide thresholds, then build separate
   frameworks?
8. **Qualitative agents:** off by default, or first run the two-name comparison under a USD 5 cap?

## What is already available on dev

The clarified audit is live on the development website on port 8514 under
**Conviction → Safeguards & audit**. It now:

- separates dividend rollout approval from event verification;
- states that Conviction only modifies an incoming quant SELL and never creates a standalone exit;
- exposes reported confidence, caps, sources, final confidence and evidence;
- explains legacy `not recorded` fields; and
- shows six P/E-history bands over the 136-equity denominator.

Dev API 8507 is active on v1.17.0 and the UI is serving the live 197-record audit. Production
remains unchanged on API v1.12.0.

I have made only the safe terminology and audit-provenance changes. I have not bulk-recalculated the
shared store, enabled dividend scoring, bought or enabled a provider, changed the P/E policy,
changed SELL behavior, run the paid model pass or promoted anything to production.

Thanks,

Divyanshu
