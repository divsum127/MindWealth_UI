# Corrections and open items from Rohit's 1 Sep 2026 reply

Recorded here because several of these correct statements that are wrong in the existing
notes, or in things I told him. Anyone reading the older documents should read this first.

Source: Rohit's 1 Sep 2026 reply on "checking your conviction engine implementation",
covering the 28 July consolidated note (attached to that mail; the appendix he refers to
is Section 13 of it).

---

## 1. Section 5.7 is wrong where it says the income and utility bucket works unchanged

His words: *"Also correct Section 5.7 while you're in there. It says the income and
utility bucket is already working unchanged. The MCY and SPK run showed both route to the
EV/revenue path where the tax contributes almost nothing. That row was wrong when it was
written."*

Confirmed in code. The valuation slice has a purpose-built module for exactly three
business types — bank (P/TBV vs ROE), high-margin hardware (EV/EBITDA), and SaaS (the
EV/Revenue tiers were calibrated on SaaS multiples). `income`, `compounder`, `cyclical`
and `unknown` all fall through to EV/Revenue tiers that were not built for them.

Measured on the two names:

| | EV/fwd rev | entry-multiple tax | total tax |
|---|---|---|---|
| MCY.NZ | 3.48x | 0.00 | −1.00 (all of it from the owner-earnings penalty) |
| SPK.NZ | null | 0.00 | 0.00 |

Addressed by the framework coverage flag (section F of his mail, §12 of the note), which
caps conviction where no module exists rather than letting a name present as high
conviction on machinery built for something else.

## 2. The v6 agentic dimensions were never running

I told him v6 "already runs" CEO quality, moat, macro tailwind, deal delay and
reinvestment runway. The code exists and is wired, but the switch defaults to skipped
(`skip_agent_dims`, overridden only by `CONVICTION_RUN_AGENT_DIMS=1`, which was set
nowhere). All 196 stored records carried **0.00 on all five**.

Worse, three separate fallbacks fabricated scores rather than reporting absence:

* a failed CEO or moat search returned `score_0_10 = 5.0`, which maps to **+1 BQ**;
* the moat agent used `_float_or_none(...) or 5.0`, so a genuine score of **0** — falsy —
  was also reported as 5.0;
* a below-confidence moat answer fell back to 5.0 rather than to unscored.

All three now return `None`, and `agent_dims_status` plus `agent_dim_provenance` record
which of `ran` / `agent_failed` / `not_run` / `manual` produced every agentic line.

A further bug sat underneath: the JSON parser called `json.loads` on the whole model
reply, so any prose preamble — which is normal with server-side web search — raised
"Expecting value: line 1 column 1" and the dimension was recorded as failed. That is why
four of five dimensions failed on the first run with a working API key.

## 3. There is no v6 document

His point stands: v6 exists only in code, which is why his Claude scored both names
against v5's nine dimensions. `ConvictionEngine_v6_Internal.pdf` in
`instruction_docs_2/` is an internal description, not the spec he holds.

## 4. `debt_purpose` — where it came from

He asked. It is `classify_debt_purpose()` in `bq_scoring.py`, feeding
`score_balance_sheet_v6()`. It is not from the July note; it came out of the 30 July
business-type reply (`Divyanshu_Business_Type_Reply 30 July_conviction doubts.pdf`) and
distinguishes debt raised for capex from debt raised to cover operations.

## 5. The hardware threshold that shipped is 40%, not 50%

`HIGH_MARGIN_HARDWARE_NET_MARGIN_THRESHOLD = 0.40`. His note argued against setting one
at all, and he is right that a cliff treats 39.9% and 40.1% differently for no reason. The
continuous form from §5.7 — raw EV/Revenue divided by net margin over a 20% base — now
drives the entry-multiple tax for every non-bank, non-hardware name, so the bucket
boundary no longer decides the answer. The threshold remains only as the business-type
label, which is what the tie-break question was really about.

## 6. ASX

There are **zero** `.AX` names in the store. My earlier "the whole NZX and ASX side" was
wrong. The store holds 115 US and other, 31 `.TO`, 17 `.NZ`, 15 `.NS`, 4 `.HK`, 2 `.KS`,
1 each of `.SI`, `.PA`, `.F`, plus 9 indices and the FX pairs.

The failure was never exchange-specific. It applies to any filer whose quarterly income
statement comes back empty from the feed, which is 78 of 196 names.

---

## Open, needing Rohit or a purchase

* **Dividend period attribution (C2).** Needs the period each declaration covers. The
  current feed returns an amount and an ex-date — no declaration date, no period label,
  no type code. Blocked on a data source, not on effort.
* **20-year P/E percentile (D).** Now mine, not Ahil's. Cannot be computed for a single
  name today. Needs a provider that carries point-in-time trailing EPS.
* **Specials classifier (C2).** Needs announcement text, same blocker as period labels.
* **Capital-intensive telco and utility spec (gap 2).** He is writing it; the framework
  coverage flag covers the exposure meanwhile.
