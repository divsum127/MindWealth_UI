# Ahil live test pack — Conviction Engine

## Purpose

Test whether the engine helps an analyst make a clearer decision. This is not only an API smoke
test. Record what Ahil expected, what the engine showed, whether the explanation was credible, and
what decision changed.

## Before the session

- Use development only. Confirm the UI/API points at dev, not production.
- Do not enable a full-universe agent run. Use the isolated evidence records first.
- Keep dividend penalties unapproved.
- Show the source timestamp, framework-coverage state and all neutral/unknown fields.

## Cases

| Case | What to inspect | Expected result/question |
|---|---|---|
| NVDA | High-margin hardware, 20y P/E percentile, CEO/reinvestment evidence | Current isolated result: conviction +8, FS 70/moderate-high. Does the explanation add value beyond the raw signal? |
| GOOGL | Adjusted P/E, buyback suspension, low-confidence CEO/moat evidence | Current isolated result: conviction 0, FS 52.5/moderate. Confirm low-confidence CEO evidence adds zero. Also flag GOOGL/GOOG alias handling. |
| NA.TO | Bank detection and P/TBV-vs-ROE framework | Dry run changes unknown → bank. Confirm the bank explanation is understandable before recalculation. |
| AVGO | Semiconductor margin boundary | Dry run changes cyclical → high-margin hardware. Check whether this matches analyst judgement. |
| SBUX | Multi-segment/type tie-break | Auto logic wants compounder → income. Ask Ahil which classification best represents the economics and why. Do not commit the change in-session. |
| SPK.NZ | Dividend candidate and NZ data quality | Show the candidate but confirm it contributes zero until declared-period/special validation and approval. |
| Existing position exit | HARD EXIT/FULL EXIT | Demonstrate that both currently close core and tactical layers. Ask whether two labels help if execution is identical. |
| Unmapped telco/utility | Coverage-incomplete gate | Confirm a missing framework produces “coverage incomplete,” not a confident score. |

## Questions to record verbatim

1. Which three fields helped your decision most?
2. Which score or explanation did you distrust, and why?
3. Did any neutral/unknown field look like a real zero?
4. For NVDA and GOOGL, would the result change your sizing or only your confidence?
5. Should HARD EXIT and FULL EXIT have different execution, or one EXIT with a reason?
6. For SBUX, should classification follow the dominant operating business, revenue segment,
   investor thesis, or dividend profile?
7. Is the engine useful enough to justify paid data and agent-search costs?

## Acceptance record

For each case, capture: `pass/fail`, visible result, expected result, Ahil's comments, source/data
problem, logic problem, UI problem, and follow-up owner. The session is complete only when every
failure has an owner and no uncertain field is represented as a factual zero.
