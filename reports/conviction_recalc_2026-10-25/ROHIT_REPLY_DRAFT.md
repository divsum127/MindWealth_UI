# Draft reply to Rohit sir — Conviction Engine (not sent)

Replies to: "Comments; Answers to the 4 questions - Re: conviction engine fixes and some doubts"
(24 Sep, msg 1a0d2e5829a0cf71), "Re: Making Claude more consistent with Payload" (14 Sep,
msg 1a09ef55720742c8) and the G3 ask in "Re: checking your conviction engine implementation"
(1 Sep, msg 1a05bedfe8ea89a8). Attach `conviction_store_diff.csv`,
`g1_pe_adjusted_eps_universe.csv` and `g2_empty_statement_fields.csv` from this folder
(attachments, not Drive links).

---

## Paragraph version

Sir, your 24 Sep decisions are now in the engine on dev and the whole store (198 records) has
been recalculated on them: SBUX stays a compounder with a mature/transitioning label, telcos and
regulated utilities show COVERAGE INCOMPLETE until your framework, SFTBY is treated as a holding
company, and P/E history now scores at 20+ years full, 10–20 provisional and under 10 neutral.
Per your 1 Sep G3 point, the attached CSV is the full list of what changes before anything goes
to prod; the biggest movers are expensive names with 30 years of P/E history (AAPL, WMT, SBUX)
now taking the P/E-percentile part of the valuation tax, and SBUX and GOOG picking up a buyback
penalty because both stopped repurchasing (Alphabet's Q2 10-Q confirms zero in H1 2026, which
answers your E4 question). On dividends, the specials gate you specified is built and five names
show a cut, of which I'd approve SPK.NZ and SUM.NZ now and hold the rest (reasons below) before
the penalty is switched on. Prod is still on the 20 Aug code with the old data, so conviction
scores and valuation tax on the live site should not be relied on until the merge and a prod
recalculation, which I'd propose for [date] once you've seen this list.

## Pointer version

1. **Your 24 Sep decisions, now on dev.** SBUX compounder (mature/transitioning); telcos
   (CNU.NZ, SPK.NZ, T.TO) and the regulated utility (BIPC.TO) → COVERAGE INCOMPLETE, 0% sizing;
   SFTBY → holding company; P/E history 20+ full / 10–20 provisional / under 10 neutral, with the
   years and source shown next to each percentile.
2. **G3 — what changes (1 Sep).** All 198 records recalculated, 0 errors; full list attached.
   Main movers: full-history names now carry the P/E-percentile tax (AAPL 7 → 4, WMT 6 → 0,
   SBUX −4.5 → −12.5); SBUX and GOOG take a buyback-suspension penalty because both stopped
   repurchasing. E4: GOOGL's trigger now fires (−2) on Alphabet's Q2 10-Q, "no repurchases" in H1 2026.
3. **Dividend cuts (1 Sep C3, 24 Sep A1).** Specials gate built as you set it (announcement
   retrieved, explicit type word, amount outlier — two of three classifies, otherwise review). The
   feed has no announcement text yet, so outliers go to review and any cut that touches one is
   held, not scored. Recommend approving SPK.NZ (16c vs 25c) and SUM.NZ (17c vs 24.5c). Hold:
   BABA (prior year includes the $1 special), BYDDY (drop matches the 2025 bonus issue),
   FMCC (to verify). TWR.NZ and WIPRO.NS are held automatically on special-looking payments.
   Penalty stays off until you approve.
4. **14 Sep — prod.** Prod runs the 20 Aug code and the store was never recalculated there, so
   conviction score, valuation tax and FS on the live site are on the old basis (e.g. PYPL still
   shows the July P/E issue). Proposed: merge + ops recalculation on [date], after your OK on (2)–(3).
5. **Your 24 Sep questions** — see the answers section below.
6. **Two-name agent test (NVDA, Google).** Ready, hard USD 5 cap, request-only as you said;
   running it next.

**Questions for you**
- Mixed businesses (your 21 Sep tie-break): the engine now reads each US filer's segment revenue
  from its 10-K. Five names straddle two business types: AVGO (semis 58% / infrastructure
  software 42%), MSFT (productivity 42% / cloud 42% / PC 16%), AMZN (retail 82% / AWS 18%), DIS
  (entertainment / parks / sports) and BRK-B (conglomerate). Shall I type each by its dominant
  segment (AVGO hardware, MSFT SaaS, AMZN compounder, DIS compounder) and keep BRK-B uncovered?
  For Infratil and Spark, which have no SEC filing, I need the segment split you'd like used.
- Yield-trap "watching" fires when either of the two conditions is met. The z-score leg alone
  catches low-yield growth names (25 today, including NVDA at a 0.47% yield). Should "watching"
  require the yield condition, so it only lists names close to an actual trap?
- Six names flipped type on fresh dividend data under the auto-rule (NVO, EIF.TO, EFN.TO,
  NOVA.F → income; TRI.TO, FSF.NZ → compounder). NVO is the SBUX case again (yield up because
  the price fell). Keep the rule, or override NVO like SBUX?

---

## Answers to the 24 Sep questions (short, for the body or as an attachment)

| Your question | Answer |
|---|---|
| "'across the store' means what?" | Every record in the conviction store at once: one global switch for the corrected dividend method, not a per-name approval. |
| "55 have conviction below +2 — BQ or conviction score?" | Conviction score. After today's recalculation it is 68 of 136 equities; BQ is 16 below 0, 38 from 0 to below 5, 82 at 5 or above. |
| "model-reported confidence … same as starting confidence?" | Yes, the same number: the confidence the model returns with its answer, before the code applies the source-count and opposing-evidence caps. |
| "evidence text: Where is this obtained from?" | Written by the model from the web pages its search returned; the URLs it used are stored next to it in `sources`. |
| "How is the assessment determined/done?" | The model scores 0–10 against the rubric in that dimension's prompt; if final confidence is 70% or more the code maps it: 8–10 → +2, 5–8 → +1, 3–5 → 0, below 3 → −1. Otherwise the dimension scores 0. |
| "Do you recall how we chose the caps?" | From your 24 May v5 brief, Part 3: fewer than 2 sources caps confidence at 0.35; evidence-against much longer than evidence-for caps it at 0.55; below 0.7 the score defaults to 0. |
| "what non-equity instruments / what usable payment history?" | The 144 included ETFs and other funds that pay distributions. Of the 136 equities, 111 currently pay a dividend. |
| "are 136 … computable as per the methodology i laid out?" | The 111 payers are computable on your declared-period basis except where the feed lacks the period label; where it does, the twelve months are built by covered period, and anything that looks like a special or a gap in the record is held for review rather than scored. |
| "Please share the 27 names" | Now 24 after the recalculation: BTI, C6L.SI, CEN.NZ, CVS, EBO.NZ, EFN.TO, EIF.TO, EMAMILTD.NS, FRW.NZ, GNE.NZ, INFY, JD, MCD, MCY.NZ, MEL.NZ, MFT.NZ, NKE, NOVA.F, NVO, PFE, PG, RHHBY, UPS, WIPRO.NS. |
| "what is this 'bear market replay'" | Running the engine as it would have scored the S&P 500 at past dates, including 2008 and 2022, using only data known on each date, to see whether low BQ names really did worse; that evidence decides whether HARD and FULL EXIT should merge. Not started yet: it needs historical index membership and point-in-time fundamentals. |
| "5.2 — we can discuss when we speak" | Noted for our next call. |

---

## Your 21 Sep ask: S&P 500 BQ distribution, today and in bear markets, and the HARD/FULL merge

Done as a point-in-time replay: every quarter-end 2010–2026, every S&P 500 member on that date
with SEC filings, scored on what was filed by that date (20,099 name-dates; coverage 24% of
members in 2010 rising to 93% now, because smaller filers only started XBRL in 2011). Full report:
`reports/sp500_pit_replay_2026-10-26/REPORT.md`.

- **Distribution:** today 15% of the index is below BQ 0, 57% between 0 and 5, 28% at 5 or above.
  At the 2020 low it was 21% / 58% / 21%; at the 2022 low 13% / 52% / 35%.
- **Merge HARD and FULL EXIT: yes.** Names the ladder would label HARD did no worse than FULL at
  3, 6 or 12 months (differences +0.3% to +0.7%, none significant).
- **Ladder cut points:** no BQ cut separates winners from losers reliably (best t = −1.4 at BQ 4),
  so I would not re-tune them; that also supports keeping conviction non-binding on SELL.
- **Where BQ does help:** from bear-market lows, BQ 5+ names beat the index by 3.1% over 3 months
  and 4.4% over 6 months (hit rate 62% and 57%); by 12 months low-BQ names catch up.

Not replayed (scored neutral): insider ownership, the agentic dimensions, the P/E-percentile tax.

---

## Other open points from your 1 Sep mail and WhatsApp (short answers)

| Where you asked | Answer |
|---|---|
| 1 Sep B: "tell me which path produced the GOOGL number" | B3, individually named one-off lines. Adjusted EPS 10.04 against the feed's higher figure, because large non-operating gains are excluded: adjusted P/E 31.6× vs raw 15.9×. SPK is on B1 (company-disclosed 11.9c), adjusted P/E 15.8× at today's price. |
| 1 Sep A: "just tell me what's in the code" (hardware) | A 40% net-margin cut-off decides whether a hardware name is valued on EV/EBITDA (high-margin hardware, AVGO now qualifies) or EV/Revenue (cyclical). The EV/Revenue side already uses your continuous margin-normalised form; per your E2 the 40% type cut-off should go too. Removing it moves the five high-margin hardware names (NVDA, TSM, AVGO, MU, 000660.KS) from EV/EBITDA to the continuous EV/Revenue — shall I make that change? Section 5.7 correction attached. |
| 1 Sep A: "Debt purpose classification … where that came from" | From your 24 May v5 brief, Part 4 (`classify_debt_purpose`). |
| 1 Sep E6: "what the engine is actually carrying versus what's on that sheet" | 55 of the 62 symbols on the watch sheet are in the store. Missing: CRWV, CDNS, SAMS.PA, SNPS, FISV (no signals yet, so never added), plus DX-Y.NYB and INR=X (index/FX, not scored). Business type for every record is in `e6_business_type_universe.csv`. |
| 1 Sep inline: "I DONT UNDERSTAND THIS COMMENT" (prod recalc by hand) | Prod data can only be rewritten by someone running the recalculation on the server; I can prepare and test it on dev, and the exact command plus a before/after check is in the deployment notes. |
| WhatsApp 21 Sep: IBKR "capped at +4 … Did I say that?" and BDGI.TO | That is your 1 Sep F rule: a business type with no purpose-built valuation module (compounder included) is capped at +4. The note only shows when the cap actually bites, which is why BDGI.TO (+1) never showed it. After today's recalculation IBKR sits at +4 without needing the cap. |
| 15 Jul D2: FX / ETF / commodity → "not applicable → base size" | Confirmed in the sizer: conviction not applicable maps to base size, never BLOCKED or $0. |
| 21 Jul: SSI-ceiling + conviction-tier feed for Ahil's four-book attribution | Built: base, +SSI, +conviction and combined books, served to Ahil's re-run. |
| WhatsApp 28 Sep: "Which portfolio is 'held'?" | None yet: that panel lists the top conviction signals, not holdings, and MTM is not wired. Which holdings should it read — your sheet, or the model book? FD shows "stable" on most rows because the rule needs 3 of 5 votes and 129 of 136 names get fewer. |

---

### Note for Divyanshu (not part of the reply)

- **[date]** is a placeholder. Prod promotion also needs the Nuxt build from Parth and the ops
  recalculation (agents may not write prod data). Don't commit to a date you can't control.
- The P/E-percentile tax "now applying" to full-history names comes from a stored
  `pe_history_insufficient` flag that was never reset after the July SEC rollout. Framed above
  as what changes, not as a mistake, per the reply guidance. Internal detail is in the job log.
- BABA, BYDDY and FMCC notes are my reading of the data (special in prior year, bonus-issue
  ratio, unusual payer). Worth a two-minute check before sending.
- The 16 Oct call notes record Rohit treating the engine as already "corrected"; this reply is
  the first time he sees the recalculated numbers.
