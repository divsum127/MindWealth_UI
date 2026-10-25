# Scope — point-in-time S&P 500 BQ replay (CE-29)

Rohit, 21 Sep 2026 (msg 1a0c341380f3954b): "look at all s and p 500 names and run the cionviciotn
engine, what is the distrbiuton of BQ raw... then recommend whether we shd merge or no." Also
"based on the disribution lets say today and in past / bear markets on our body of names".
24 Sep: "remind me what is thius 'bear market replay'".

## Question it answers

At past dates, did names the engine would have scored low on Business Quality (BQ) actually do
worse over the next 3, 6 and 12 months? And do HARD EXIT and FULL EXIT names behave differently
enough to keep separate labels? Until this exists, conviction stays non-binding on SELL.

## Design

| Piece | Choice | Why |
|---|---|---|
| Universe | S&P 500 members **as of each test date** (historical constituent list) | Today's members only would be survivorship-biased |
| Test dates | Quarter-ends 2010–2026 (~64 dates) | SEC XBRL depth starts ~2009; quarterly matches the fundamentals cadence |
| Bear windows reported separately | 2011, 2015–16, 2018 Q4, 2020, 2022 | Rohit's "past / bear markets" ask |
| Fundamentals | SEC XBRL company facts, keeping only values **filed on or before** each test date | Point-in-time; the engine's P/E history already does this for EPS |
| Prices | Daily closes incl. delisted names | Forward returns and valuation inputs |
| Agentic dimensions | Excluded (neutral 0), stated as such | Web search cannot be replayed point-in-time; also keeps cost at zero |
| Valuation tax | Computed from point-in-time price and fundamentals | Same code path as live |
| Output | BQ distribution per date; forward 3/6/12m return and hit rate by BQ bucket and by HARD / FULL / PARTIAL label, excess over the S&P 500 | Feeds the merge / no-merge recommendation |

## Data to source

1. Historical S&P 500 membership with add/drop dates (public reconstructions exist; must be
   spot-checked against known changes).
2. Price history for delisted members (yfinance drops many; needs a second free source or a paid one).
3. SEC company facts for revenue, net income, FCF inputs, debt, equity, shares — already
   partly fetched by `pe_history_sec.py`; extend to the other BQ inputs with the `filed` date gate.

## Effort and cost

- Build: about 5–8 working days (membership + price sourcing 2, point-in-time fundamentals
  adapter 2–3, replay runner + report 1–2, validation 1).
- Run: ~32,000 name-dates, local compute only; no model API cost because agent dimensions are excluded.
- Risk: delisted-price coverage. If it is thin, results will flatter low-BQ names that failed.

## Known limits (to state with the results)

- Non-US names and agentic dimensions are out of scope.
- Classification uses today's sector labels for past dates (mild look-ahead, same as the CFTC note).
- BQ components that depend on manual overrides cannot be replayed and are scored neutral.

## Deliverable

A short report with the BQ distribution today and at each bear trough, forward-return tables by
bucket and label, and a one-line recommendation on merging HARD and FULL EXIT, plus the CSVs.
