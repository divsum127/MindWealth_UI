# Correction to Section 5.7 — Conviction Engine Consolidated Note (28 Jul 2026)

Requested by Rohit, 1 Sep 2026 (msg 1a05bedfe8ea89a8, section F):

> "Also correct Section 5.7 while you're in there. It says the income and utility bucket is
> already working unchanged. The MCY and SPK run showed both route to the EV/revenue path
> where the tax contributes almost nothing. That row was wrong when it was written."

## What Section 5.7 said

The income and utility bucket was listed as working unchanged.

## What is true

- **It was not working.** Income names (including utilities and telcos) were valued on the
  EV/Revenue tiers, which were calibrated on SaaS multiples. Capital-intensive businesses sit
  far below those tiers, so the valuation tax contributed almost nothing and the score read as
  conviction. MCY.NZ and SPK.NZ showed this on 26 Aug.
- **Interim fix (1 Sep, F):** any business type without a purpose-built valuation module is
  capped at conviction +4. Only banks (P/TBV vs ROE), high-margin hardware (EV/EBITDA) and SaaS
  have one.
- **Policy since 24 Sep:** telcos and regulated utilities are **not covered** until Rohit's
  framework exists ("till i do, keep as not covered."). On dev (25 Oct) they gate as COVERAGE
  INCOMPLETE with 0% sizing: CNU.NZ, SPK.NZ, T.TO (telcos), BIPC.TO (regulated utility).
- **Still income-typed:** renewable and independent power producers (MCY.NZ, MEL.NZ, CEN.NZ,
  GNE.NZ), which are not regulated. They carry the +4 cap and the margin-normalised EV/Revenue
  from Section 5.7's own continuous formula (raw EV/Rev ÷ net margin over 20%, no bucket gate).
  Whether they belong in the telco/utility framework is a question for Rohit.

## Section 5.7's other content

The continuous margin-normalised EV/Revenue described there is implemented
(`scoring.margin_normalised_ev_rev`), per Rohit's E2 instruction to use it for every name with no
bucket gate. One cliff remains: a 40% net-margin cut-off still decides which hardware names are
typed `high_margin_hardware` (valued on EV/EBITDA) versus `cyclical` (EV/Revenue). Rohit's E2
asked for no threshold at all, so removing this cut-off is open work, not done.
