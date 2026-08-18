# CNN Fear & Greed — Put/Call Ratio Component API Evaluation

**Date:** 2026-07-29
**SUPERSEDED 2026-08-02:** The premise of this evaluation — reconstructing CNN's composite F&G
score from its 7 individual components because CNN's own API "confirmed no additional free depth
exists" (see below) — turned out to be based on an incomplete test. `scripts/backfill_cnn_
feargreed_free_sources.py` (2026-08-02) found that CNN's `graphdata` endpoint *does* return its
full real history when a start-date is appended to the URL path (`/graphdata/2020-07-14` returns
1519+ rows back to 2020-07-14, not the ~250-day window this evaluation observed when calling the
endpoint with no start-date suffix). Combined with a validated community wayback-reconstruction
for 2012-05-25→2020-07-13, this closes the composite-score gap directly and makes reconstructing
it component-by-component (this evaluation's approach) unnecessary. See
`docs/ssi_validation/cnn_fg_wayback_backfill_2026-08-02.md`. Kept below for provenance/history —
do not act on the "next step" recommendation at the bottom, it is no longer needed.

**Trigger:** Macro regime system fix-to-spec plan, work item 2, option 1 — "Evaluate a low/no-cost
third-party CBOE put/call ratio API (e.g. Equibles' free-tier endpoint) as a data source for the
P/C component back to ~2019 ... Needs an explicit go/no-go before starting."

**Recommendation (superseded, see above): CONDITIONAL GO — pending one free, 10-minute
verification step (see below). Do not start building the CNN 7-factor clone yet.**

## What was checked

### 1. CNN's own API — confirmed no additional free depth exists

Live-queried `production.dataviz.cnn.io/index/fearandgreed/graphdata` directly (2026-07-29). This
is the same endpoint the repo already uses (`src/sentiment_superindex/data/cnn_fear_greed.py`).
Confirmed the existing docstring's claim exactly — every series in the response, including the
raw components, is capped to ~250 trading days (~1 calendar year):

| Series (from CNN's own API) | Rows | Date range |
|---|---|---|
| `fear_and_greed_historical` (composite score) | 251 | 2025-07-29 → 2026-07-29 |
| `put_call_options` | 250 | 2025-07-29 → 2026-07-29 |
| `market_volatility_vix` | 251 | 2025-07-29 → 2026-07-29 |
| `junk_bond_demand` | 250 | 2025-07-29 → 2026-07-29 |
| `safe_haven_demand` | 250 | 2025-07-29 → 2026-07-29 |
| `stock_price_breadth` | 250 | 2025-07-29 → 2026-07-29 |

No hidden longer history in this endpoint — reconstructing any pre-2025 date genuinely requires
sourcing each of the 7 CNN components independently.

### 2. CBOE's own free bulk downloads — confirmed cut off at October 2019

`cboe.com/us/options/market_statistics/historical_data/` still publishes free bulk CSV downloads
for "Cboe Total/Index/Equity/ETP Volume and Put/Call Ratios," but every one of those files is
explicitly dated **11-01-2006 to 10-04-2019** — matching what was already known when this gap was
first flagged. Data after Oct 2019 requires either Cboe DataShop (paid) or a third-party API.

### 3. Equibles (candidate free/low-cost third-party API)

- Free tier: **100 requests/day, no credit card**, shared across REST API and MCP.
- Relevant endpoint: `GET https://api.equibles.com/v1/market/put-call-ratios` — daily CBOE total
  equity call volume, put volume, total volume, and P/C ratio. Paginated (`limit` up to 500,
  `offset`), ordered most-recent-first.
- **Critical unknown, not resolved by this evaluation:** Equibles' documentation states the
  companion VIX endpoint is "available back to 1990" explicitly, but makes **no equivalent
  depth claim for the put/call ratio endpoint**. Given CBOE's own free bulk files stop at
  Oct 2019, it is unconfirmed whether Equibles' P/C series:
  - (a) goes back further than Oct 2019 (e.g., they may source from a paid CBOE DataShop feed
    and resell/re-expose a longer history), or
  - (b) only starts from whenever Equibles began ingesting CBOE's live feed themselves (could be
    materially shorter than 2019+, defeating the purpose of this evaluation).
- This cannot be resolved from documentation alone — it requires an actual signed-up account and
  one paginated query (`?limit=500&offset=<N>` walked backward) to find the true earliest date.
  Free tier is more than sufficient for this single check (and for a full one-time historical
  pull afterward: at 500 rows/page, ~7 years of daily data is ~4 pages, well under the 100
  req/day cap).

## Even if Equibles' P/C history reaches back to 2019+, this alone does not unlock a CNN F&G clone

The CNN Fear & Greed Index is an equal-weighted average of **7** components. Put/call ratio is
only one:

| # | Component | Free source status |
|---|---|---|
| 1 | Market momentum (SPX vs 125-day MA) | ✅ Buildable free today — Yahoo/FRED SPX history is not gated |
| 2 | Stock price strength (NYSE 52-wk highs vs lows) | ⚠️ Not evaluated in this pass — needs its own free-source check |
| 3 | Stock price breadth (McClellan Volume Summation Index) | ⚠️ Not evaluated in this pass — needs NYSE daily advancing/declining volume, which may have its own paywall; historically the hardest of the 7 to source free |
| 4 | Put/call ratio (5-day avg) | 🔶 This evaluation — conditional go, pending depth verification |
| 5 | Market volatility (VIX vs 50-day MA) | ✅ Buildable free today — VIX has full free history via Yahoo |
| 6 | Safe haven demand (stock vs Treasury returns) | ✅ Buildable free today — SPX + Treasury yields both free |
| 7 | Junk bond demand (HY yield spread) | 🔴 Same `BAMLH0A0HYM2` licensing gap as work item 1 — bounded by the Model v2 proxy limitations documented in `hy_oas_recalibration_2026-07-29.md` |

So confirming Equibles' P/C depth only resolves component #4. Components #2 and #3 are unverified
(#3 in particular is the historically-hardest component — the plan's original framing that this
whole effort was "already deferred once as complex" still applies), and component #7 inherits the
still-open HY OAS proxy limitation. **Do not commit to building the full 7-factor clone based on
this evaluation alone** — it only clears one component of seven, and the highest-risk unknown
(McClellan breadth data availability) hasn't been checked yet.

## Recommended next step (cheap, before any further commitment)

1. Sign up for the Equibles free tier (no card required) and run one paginated query
   (`GET /v1/market/put-call-ratios?limit=500&offset=<N>`, walking `offset` upward) to find the
   actual earliest available date for the P/C ratio series.
2. If depth reaches materially before Oct 2019 (or even just cleanly covers 2019+): scope a small
   follow-up eval for component #3 (McClellan breadth / NYSE advance-decline volume) before
   deciding whether to build anything.
3. If depth does not reach 2019 (e.g., Equibles only has ~1-2 years like CNN's own API): this
   vendor doesn't solve the gap either — fall back to the plan's option 2 (keep the current honest
   crypto-proxy labeling, no further code change without paid data) and/or flag to Rohit alongside
   the HY OAS paid-data decision (same vendor category).

This step (signing up for a third-party account and making live test calls) was intentionally
**not** performed as part of this evaluation — it's a small but real external commitment (email
signup, third-party ToS) better made with explicit go-ahead rather than assumed.
