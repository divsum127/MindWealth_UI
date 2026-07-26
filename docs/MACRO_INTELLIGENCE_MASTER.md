# Macro Intelligence Agent — Complete Build Reference

**Author:** Divyanshu  
**Project period:** ~40 hours of active development (May–June 2026)  
**Status:** v3 verification GO — 2026-06-04  
**Config:** `macro_intelligence/CONFIG.yaml` | **Code:** `src/macro_intelligence/` + `src/sentiment_superindex/`

---

## Table of contents

1. [The idea — what this system does and why](#1-the-idea)
2. [The 12 macro variables — what each is and why it matters](#2-the-12-macro-variables)
   - [2b. Data sources reference — exact URLs and API locations for all 12 variables](#2b-data-sources-reference--all-12-variables)
   - [2c. Data gap status — current implementation coverage](#2c-data-gap-status--current-implementation)
3. [The 7 named combos A–G — what triggers them](#3-the-7-named-combos-a-g)
4. [How the system was implemented — file by file](#4-how-it-was-implemented)
5. [SSI — what it is and why we needed it](#5-ssi--sentiment-superindex)
6. [Every threshold — justification in plain language](#6-every-threshold-justified)
7. [40 hours — what went into what](#7-40-hours-time-breakdown)

---

## 1. The Idea

### What problem does this solve?

Divyanshu's firm runs a systematic trading strategy using MindWealth signals (TrendPulse, DeltaDrift, BandMatrix, etc.). These strategies fire when a stock looks technically good. But **even perfect technical signals fail during market-wide crises** — October 2022, COVID March 2020, the 2022 rate-hike cycle. The system needed a way to say:

> "Right now the macro environment is dangerous — **reduce your position sizes, override the VIX sizing rule, or pause entirely**."

That is the job of the **Macro Intelligence Agent**, codenamed **Runic**.

### What does it actually produce?

Every night the agent writes a JSON file called **`runic_output.json`**. The C++ trading engine reads this file when it wakes up. Key fields inside:

| Field | What it tells the C++ engine |
|-------|-------------------------------|
| `dominant_signal` | Which macro combo (if any) is active — e.g. "Combo E" means CAPE extreme + CFTC extreme + NFCI stress, all at once |
| `active_combos` | Full list of all combos currently detected |
| `ssi_multiplier` | Size multiplier from SSI — 1.2 means "increase size", 0.8 means "reduce" |
| `vix_bypass` | If `true`, the engine ignores VIX-based size reduction (because Combo B panic event = buy not reduce) |
| `spx_3m_hit_rate` | Historical success rate for this signal pattern |
| `analog_details` | The closest historical dates where the same pattern occurred and what happened next |
| `regime` | 5-dimensional market regime label (Fed cycle, curve regime, volatility, geo overlay, valuation) |
| `narrative` | Claude-generated plain-English briefing explaining what is happening |
| `pending_cpi_release` | True/false — if a CPI release is imminent, some combo logic changes |

### The specification

The system was built from three docs written by Divyanshu:

1. **`Divyanshu Instructions to Build Macro Intelligence agent.pdf`** — original brief
2. **`Divyanshu_Addendum_MacroAgent.docx`** — first revisions
3. **`28_May_2026_Divyanshu_Runic_Integration_Note_v3.docx`** — final binding spec (v3 wins over everything older)
4. **`Runic_Agent_Combo_Cheatsheet_v2.pdf`** — combo rule reference
5. **`SSI_OpenQuestions_DivyanshuTestList (1).docx`** — validation tests for SSI

---

## 2. The 12 Macro Variables

Every variable gets pulled from a public data source, stored in a SQLite database, and then assigned a **tier** (normal → RARE → EXTREME) based on configurable thresholds. Here is each variable in plain language.

---

### Variable 1 — NFCI: National Financial Conditions Index

**What it is:** A weekly index published by the Chicago Fed every Wednesday. It measures how **tight or loose financial conditions** are across the whole US economy — interest rates, credit availability, bank lending standards, all rolled into one number.

**Scale:** Negative = loose/easy (markets functioning well). Positive = tight/stressed. Zero = neutral/historical average.

**Why we use it:** It is one of the best early warning signals for credit crises. It was very elevated in 2008, early 2020, and 2022.

**Where it comes from:** FRED API, ticker `NFCI`. Data goes back to 1973.

**Thresholds:**

| Tier | Rule | Plain meaning |
|------|------|---------------|
| RARE | ≥ +0.3 or ≤ −0.3, OR 80th/20th percentile of full history | Conditions are meaningfully tighter or easier than normal |
| EXTREME | ≥ +0.8 or ≤ −0.8, OR 95th/5th percentile | Conditions are genuinely crisis-like or extremely accommodative |

**Paradigm used:** DUAL — can fire on either the tight side (stress) or the loose side (excessive ease).

**Used in combos:** A and E.

---

### Variable 2 — HY: High-Yield Credit Spreads (OAS)

**What it is:** The extra interest rate (in basis points — hundredths of a percent) that companies with weak credit ratings must pay over US Treasuries when they borrow. Called OAS (Option-Adjusted Spread).

**Why we use it:** When investors are scared, they demand a higher premium to lend to risky companies. Spreads **widen** in crisis and **tighten** when confidence returns. A reading of 400bps means risky companies are paying 4% extra vs the government.

**Where it comes from:** FRED API, ticker `BAMLH0A0HYM2`. Starts 1996.

**Thresholds:**

| Tier | Rule | Plain meaning |
|------|------|---------------|
| RARE | ≥ 400bps, OR 80th percentile of full history | Credit stress building |
| EXTREME | ≥ 500bps, OR 95th percentile | Major credit stress event |

**Used in combos:** A, B, F, G.

---

### Variable 3 — WALCL: Federal Reserve Balance Sheet

**What it is:** The total size of the Federal Reserve's balance sheet — how many assets the Fed holds (mainly US Treasuries and mortgage bonds it bought to support the economy). Published every Thursday.

**Why we use it:** When the Fed is growing its balance sheet (buying assets = "quantitative easing" / QE), it pumps money into markets — bullish. When it shrinks the balance sheet ("QT" = quantitative tightening), it removes liquidity — bearish.

**Where it comes from:** FRED API, ticker `WALCL`. Starts 2008 (before that the balance sheet barely moved).

**Thresholds:**

| Tier | Rule | Plain meaning |
|------|------|---------------|
| RARE | Month-over-month change ≥ ±0.8% | The Fed is meaningfully growing or shrinking |
| EXTREME | Month-over-month change ≥ ±2.0% | The Fed is doing something dramatic (emergency QE or fast tightening) |

**Paradigm used:** ROC (Rate of Change) — we care about the *direction and magnitude of change*, not the absolute level.

**Used in combos:** A, C.

---

### Variable 4 — CNH: USD/Chinese Yuan exchange rate (4-week change)

**What it is:** How many Chinese yuan (CNH = offshore yuan) one US dollar buys. We measure the **change over 4 weeks** (about 28 calendar days).

**Why we use it:** The yuan is China's currency. When China's economy weakens, or when there is global trade stress, the yuan often depreciates (takes more yuan to buy one dollar). This variable acts as a proxy for **China risk and global trade sentiment**.

**Where it comes from:** Yahoo Finance, ticker `USDCNH=X`. If Yahoo returns fewer than 100 data points (data gap), falls back to FRED `DEXCHUS`. Data starts 2010.

**Thresholds:**

| Tier | Rule | Plain meaning |
|------|------|---------------|
| RARE | 4-week change ≥ ±1.5% | Meaningful currency move |
| EXTREME | 4-week change ≥ ±3.5% | Sharp currency pressure |

**Used in combos:** A, C, G.

---

### Variable 5 — WTI: Oil Price (4-week change)

**What it is:** The price of West Texas Intermediate crude oil (the US benchmark). We measure the **change over exactly 28 calendar days**.

**Why we use it:** Oil is both a cause and a symptom of macro stress. A big oil spike means inflation pressure on consumers and companies; a big crash means recession fears. Combo C specifically fires when oil has spiked dramatically.

**Where it comes from:** Yahoo Finance, ticker `CL=F` (CME WTI crude oil continuous futures contract). Yahoo Finance continuous futures only go back to ~2000 (25-year limit). If Yahoo returns fewer than 100 bars, falls back to FRED `DCOILWTICO` (Crude Oil Prices: West Texas Intermediate — Cushing, Oklahoma; EIA data via FRED; starts 1986). History used: 1985-01-01 (FRED) / 2000-08-23 (Yahoo practical limit).

**Thresholds:**

| Tier | Rule | Plain meaning |
|------|------|---------------|
| RARE | 4-week change ≥ ±6% | Meaningful oil move |
| EXTREME | 4-week change ≥ ±10% | Dramatic oil shock |

**Used in combos:** C.

---

### Variable 6 — VIX: Volatility Index

**What it is:** Nicknamed the "fear gauge." The VIX measures how much volatility the options market is *expecting* in the S&P 500 over the next 30 days. A VIX of 15 = calm. VIX of 30+ = fear. VIX of 50+ = panic.

**Why we use it:** Extreme VIX readings mark turning points. VIX above 35 often signals capitulation — the moment when everyone who was going to sell has already sold. That is actually a *buy* signal in Combo B logic.

**Where it comes from:** Yahoo Finance, ticker `^VIX`. Starts 1990.

**Thresholds:**

| Tier | Rule | Plain meaning |
|------|------|---------------|
| RARE | ≥ 25, OR 80th percentile of full history | Fear is elevated |
| EXTREME | ≥ 35, OR 95th percentile | Panic / capitulation zone |

**Used in combos:** B, D, G.

---

### Variable 7 — VXTS: VIX Term Structure (Ratio)

**What it is:** The ratio of VIX3M (93-day implied volatility) divided by VIX (30-day implied volatility). This tells you whether short-term fear is higher or lower than long-term fear.

- **Ratio > 1** = normal (longer-dated vol is higher than near-term) — called "contango"
- **Ratio < 1** = inverted (near-term panic is *higher* than long-term) — called "backwardation", a sign of acute stress

**Example (today):** VIX ≈ 15.60, VIX3M ≈ 19.50 → ratio = 19.50 ÷ 15.60 = **1.25** → above 1.10 RARE threshold → Combo D WATCH leg confirmed.

**Why we use it:** When the ratio goes below 1, it means the market is more worried about *right now* than the future — classic panic pattern. Oct 7, 2025 had this. Conversely, a very high ratio (markets calm, low near-term vol) can signal complacency.

**Where it comes from:** Yahoo Finance — `^VIX3M` (CBOE 93-day implied volatility index) ÷ `^VIX` (30-day). Data starts 2007. Implemented in `yahoo_pull.vix_term_structure()`.

**Ticker detail:**
- **Primary:** `^VIX3M` — the CBOE 93-day VIX series. This is the correct numerator.
- **Fallback:** `^VXV` — an older equivalent 93-day series. Now **delisted** on Yahoo Finance; automatically tried if `^VIX3M` returns empty (useful for historical research only).
- Formula: `ratio = ^VIX3M close ÷ ^VIX close` (daily, aligned and forward-filled).

**Thresholds:**

| Tier | Condition | Plain meaning |
|------|-----------|---------------|
| RARE low | Ratio ≤ 0.95 | Mild backwardation / stress |
| RARE high | Ratio ≥ 1.10 | Elevated complacency |
| EXTREME low | Ratio ≤ 0.85 | Acute panic (near-term vol much higher than long-term) |
| EXTREME high | Ratio ≥ 1.20 | Very complacent term structure |

**Used in combos:** D, G.

---

### Variable 8 — CFTC: Futures Positioning (Fast Money net)

**What it is:** Every Friday at ~3:30pm ET, the US government's CFTC (Commodity Futures Trading Commission) publishes a report showing exactly how many long vs short positions different types of traders hold in S&P 500 futures.

We specifically track **Fast Money** (leveraged funds / hedge funds) — these are the most reactive traders. Their net position = long contracts minus short contracts.

We convert this into a **3-year rolling percentile** — so "5th percentile" means hedge funds are *more short* than 95% of the time in the past 3 years.

**Why we use it:** When Fast Money is extremely short (bottom 5–15th percentile), it's often a contrarian buy signal because everyone who could sell has already sold (short squeeze potential). When they are very long (85–95th+), it's a crowded trade.

**Where it comes from:** Downloaded directly from CFTC.gov — Traders in Financial Futures (TFF) report. We cache ZIP files in `macro_intelligence/data_cache/cftc/`.

**Thresholds:**

| Tier | Condition | Plain meaning |
|------|-----------|---------------|
| RARE short | ≤ 15th percentile | Hedge funds unusually short |
| RARE long | ≥ 85th percentile | Hedge funds unusually long |
| EXTREME short | ≤ 5th percentile | Extreme short — contrarian buy territory |
| EXTREME long | ≥ 95th percentile | Extreme long — crowded, fragile |

**Used in combos:** B, D, E, F.

---

### Variable 9 — CURVE: 10-Year minus 2-Year Yield Spread

**What it is:** The difference in interest rates between a 10-year US Treasury bond and a 2-year Treasury bond. Normally longer-dated bonds pay more interest (positive spread). When the curve **inverts** (2-year yields more than 10-year), it historically predicts recessions.

**Why we use it:** An inverted yield curve (spread below 0) is one of the most reliable recession predictors in history. We also track the **rate of change** — a rapid "steepening" (spread widening fast) often happens right as a recession is ending and policy pivots.

**Where it comes from:** FRED API, ticker `T10Y2Y`. Data goes back to 1976.

**Thresholds:**

| Tier | Condition | Plain meaning |
|------|-----------|---------------|
| RARE | Spread ≤ −30bps, OR 4-week steepening ≥ 15bps | Inversion / rapid pivot |
| EXTREME | Spread ≤ −80bps, OR steepening ≥ 40bps | Deep inversion or dramatic curve move |

**Used in combos:** A, E.

---

### Variable 10 — CPI: Inflation Surprise

**What it is:** The difference between the actual CPI (Consumer Price Index) inflation reading published by the BLS (Bureau of Labor Statistics) and what economists were forecasting (consensus). Called "CPI surprise." Published monthly.

- Positive surprise = inflation came in *higher* than expected → bearish (rate hike risk)
- Negative surprise = lower than expected → bullish

**Why we use it:** Markets don't react to the CPI number itself — they react to whether it was *better or worse than expected*. A surprise of +0.2pp (0.2 percentage points above consensus) is enough to spook bond markets.

**Where it comes from:** Two separate pulls merged together:
- **Actual MoM %:** BLS API (`api.bls.gov/publicAPI/v2/timeseries/data/`) → series `CUSR0000SA0` (All Urban Consumers CPI, seasonally adjusted). Published ~8:30am ET on the 2nd–3rd Tuesday each month. If BLS API is unreachable for 2+ calendar days (e.g. government shutdown), falls back to FRED `CPIAUCSL`.
- **Consensus estimate:** Scraped from **Trading Economics** (`tradingeconomics.com/united-states/inflation-rate-mom`) as the primary automated source. Investing.com (`investing.com/economic-calendar/`) is a secondary fallback — it requires the `INVESTING_HTTP_PROXY` environment variable because Cloudflare blocks datacenter IPs. Emergency cache: `macro_intelligence/data/cpi_consensus.csv` (manual CSV).
- **Release dates calendar:** FRED API `release/dates?release_id=10` to know when to expect a print.

**Thresholds:**

| Tier | Condition | Plain meaning |
|------|-----------|---------------|
| RARE | Surprise ≥ ±0.2pp | Meaningful miss or beat |
| EXTREME | Surprise ≥ ±0.4pp, OR two consecutive hot prints | Clearly hotter-than-expected inflation |

**Used in combos:** C.

---

### Variable 11 — GSR: Gold-to-Silver Ratio (4-week change)

**What it is:** The price of gold divided by the price of silver. When investors are scared, gold tends to hold up better than silver (because gold is the pure "safe haven" and silver is partially industrial). So a *rising* GSR = risk-off fear trade.

We measure the **4-week change** in this ratio.

**Why we use it:** It acts as a cross-asset stress indicator. When gold dramatically outperforms silver, it often confirms other risk-off signals (NFCI, HY, etc.).

**Where it comes from:** Yahoo Finance — `GC=F` (gold futures) ÷ `SI=F` (silver futures). Data starts 1968.

**Thresholds:**

| Tier | Condition | Plain meaning |
|------|-----------|---------------|
| RARE | 4-week GSR change ≥ ±5% | Meaningful flight to gold |
| EXTREME | 4-week change ≥ ±8% | Dramatic risk-off rotation |

**Used in combos:** A.

---

### Variable 12 — CAPE: Shiller PE / Cyclically-Adjusted P/E Ratio

**What it is:** A valuation measure for the US stock market, invented by economist Robert Shiller. It takes the S&P 500 price divided by *10-year average earnings* (adjusted for inflation). This smooths out the business cycle so you can see if stocks are genuinely expensive or cheap over the long run.

- CAPE of 15–20 = roughly fair value historically
- CAPE of 28+ = elevated valuation (like late 1990s or post-2013)
- CAPE of 35+ = extremely expensive (only seen briefly before major corrections)

**Why we use it:** The Runic system uses CAPE as a valuation stress input. A very high CAPE, combined with other stress signals, suggests the market is expensive *and* fragile.

**Where it comes from:** Scraped from `multpl.com` (which publishes Shiller's data publicly). Data goes back to 1881.

**Thresholds:**

| Tier | Condition | Plain meaning |
|------|-----------|---------------|
| RARE high | ≥ 28 | Elevated but not extreme — caution zone |
| RARE low | ≤ 16 | Very cheap by long-run standards |
| EXTREME high | ≥ 32 | Historically expensive |
| EXTREME low | ≤ 12 | Very rare bargain territory |

**Used in combos:** E.

---

## 2b. Data Sources Reference — All 12 Variables

This section is the single authoritative reference for every data source used in the system. For each variable it lists: the exact URL or API endpoint, the specific ticker/series/page, what fallback is used if the primary fails, the actual history available (not just the spec), and publication frequency.

---

### NFCI — National Financial Conditions Index

| Field | Detail |
|-------|--------|
| **Primary source** | St. Louis FRED API |
| **Primary API endpoint** | `https://api.stlouisfed.org/fred/series/observations?series_id=NFCI&api_key=<KEY>` |
| **FRED series ID** | `NFCI` |
| **FRED web page** | https://fred.stlouisfed.org/series/NFCI |
| **Fallback (no API key)** | FRED public CSV: `https://fred.stlouisfed.org/graph/fredgraph.csv?id=NFCI` |
| **Python library** | `fredapi.Fred.get_series("NFCI")` or `pandas.read_csv(url)` |
| **History start** | 1973-01-06 |
| **Publication frequency** | Weekly, every Wednesday morning (data for the week ending the prior Friday) |
| **Units** | Dimensionless index; 0 = historical average, negative = easy, positive = tight |

---

### HY — High-Yield Credit Spreads (ICE BofA OAS)

| Field | Detail |
|-------|--------|
| **Primary source** | St. Louis FRED API |
| **Primary API endpoint** | `https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&api_key=<KEY>` |
| **FRED series ID** | `BAMLH0A0HYM2` (ICE BofA US High Yield Index Option-Adjusted Spread) |
| **FRED web page** | https://fred.stlouisfed.org/series/BAMLH0A0HYM2 |
| **Fallback (no API key)** | FRED public CSV: `https://fred.stlouisfed.org/graph/fredgraph.csv?id=BAMLH0A0HYM2` |
| **History start** | 1996-12-31 |
| **Practical depth** | ICE BofA licensing restricts FRED API distribution to the most recent ~3 years only, regardless of API key. FRED displays the full series on the web, but programmatic access is capped. The system computes HY percentile on the available 3-year window. |
| **Publication frequency** | Daily (business days) |
| **Units** | Percent (e.g., 2.74 = 274 basis points OAS) |

---

### WALCL — Federal Reserve Balance Sheet

| Field | Detail |
|-------|--------|
| **Primary source** | St. Louis FRED API |
| **Primary API endpoint** | `https://api.stlouisfed.org/fred/series/observations?series_id=WALCL&api_key=<KEY>` |
| **FRED series ID** | `WALCL` (Assets: Total Assets: Total Assets: Wednesday Level) |
| **FRED web page** | https://fred.stlouisfed.org/series/WALCL |
| **Fallback (no API key)** | FRED public CSV: `https://fred.stlouisfed.org/graph/fredgraph.csv?id=WALCL` |
| **History start** | 2003-01-01 (practical; Fed balance sheet was static before 2008 QE era) |
| **Publication frequency** | Weekly, every Thursday afternoon (H.4.1 report for the Wednesday balance) |
| **Units** | Millions of US dollars |
| **Transformation used** | 4-week MoM % change (rolling window of 4 weekly observations, `pct_change(4) * 100`) |
| **Percentile window (June 2026)** | **Full history** from 2008-01-01 on the **MoM%** series (not absolute WALCL level) |

---

### CNH — USD/Offshore Yuan 4-Week Change

| Field | Detail |
|-------|--------|
| **Primary source** | Yahoo Finance via `yfinance` |
| **Yahoo ticker** | `USDCNH=X` (USD/Offshore Chinese Yuan — Hong Kong interbank rate) |
| **Yahoo Finance page** | https://finance.yahoo.com/quote/USDCNH=X/ |
| **Fallback trigger** | Yahoo returns fewer than 100 bars (often returns a single stale row — a known Yahoo Finance bug with FX tickers) |
| **Fallback source** | St. Louis FRED API, series `DEXCHUS` (China/U.S. Foreign Exchange Rate — People's Bank of China fixing) |
| **Fallback FRED page** | https://fred.stlouisfed.org/series/DEXCHUS |
| **History start** | 2010-01-01 (offshore CNH market started ~2010) |
| **Publication frequency** | Daily (business days) |
| **Units** | CNH per 1 USD (a higher number = weaker yuan / stronger dollar) |
| **Transformation used** | 28-calendar-day % change (`calendar_pct_change(28)`) — positive = USD strengthened vs CNH |

---

### WTI — West Texas Intermediate Oil (4-Week Change)

| Field | Detail |
|-------|--------|
| **Primary source** | Yahoo Finance via `yfinance` |
| **Yahoo ticker** | `CL=F` (CME WTI crude oil front-month continuous futures contract) |
| **Yahoo Finance page** | https://finance.yahoo.com/quote/CL=F/ |
| **Practical history depth** | Yahoo continuous futures go back to approximately 2000-08-23 (~25-year limit) |
| **Fallback trigger** | Yahoo returns fewer than 100 bars |
| **Fallback source** | St. Louis FRED API, series `DCOILWTICO` (EIA Crude Oil Prices: WTI — Cushing, Oklahoma) |
| **Fallback FRED page** | https://fred.stlouisfed.org/series/DCOILWTICO |
| **Fallback history** | 1986-01-02 |
| **Publication frequency** | Daily (business days) |
| **Units** | USD per barrel |
| **Transformation used** | 28-calendar-day % change (`calendar_pct_change(28)`) — positive = oil price rose |

---

### VIX — CBOE Volatility Index

| Field | Detail |
|-------|--------|
| **Primary source** | Yahoo Finance via `yfinance` |
| **Yahoo ticker** | `^VIX` (CBOE Volatility Index — 30-day implied S&P 500 volatility) |
| **Yahoo Finance page** | https://finance.yahoo.com/quote/%5EVIX/ |
| **Data provider** | CBOE Global Markets (Chicago Board Options Exchange) |
| **No fallback** | FRED does not host VIX. If Yahoo fails, this variable is unavailable. |
| **History start** | 1990-01-02 |
| **Publication frequency** | Daily (real-time during US market hours; close used) |
| **Units** | Annualised implied volatility (e.g., 21.51 = 21.51% expected 30-day move, annualised) |

---

### VXTS — VIX Term Structure Ratio (VIX3M ÷ VIX)

| Field | Detail |
|-------|--------|
| **Primary source** | Yahoo Finance via `yfinance` |
| **Yahoo ticker (numerator)** | `^VIX3M` (CBOE 93-day implied volatility index — the "3-month VIX") |
| **Yahoo Finance page** | https://finance.yahoo.com/quote/%5EVIX3M/ |
| **Yahoo ticker (denominator)** | `^VIX` (same as above) |
| **Fallback for numerator** | `^VXV` — the predecessor 93-day implied vol series (CBOE delisted it; useful only for pre-2007 research) |
| **Formula** | `ratio = ^VIX3M close ÷ ^VIX close` — aligned by date, forward-filled, no smoothing |
| **History start** | 2007-01-01 (^VIX3M launch date) |
| **Publication frequency** | Daily |
| **Units** | Ratio (dimensionless); > 1 = contango (normal), < 1 = backwardation (near-term stress) |

---

### CFTC — Fast Money Net Positioning (S&P 500 Futures)

| Field | Detail |
|-------|--------|
| **Primary source** | CFTC.gov — Traders in Financial Futures (TFF) report |
| **CFTC main page** | https://www.cftc.gov/MarketReports/TradersinFinancialFuturesReports/index.htm |
| **Bulk file (2006–2016)** | `https://www.cftc.gov/files/dea/history/fin_fut_txt_2006_2016.zip` → unzip to `F_TFF_2006_2016.txt` |
| **Annual files (2017+)** | `https://www.cftc.gov/files/dea/history/fut_fin_txt_{YEAR}.zip` → unzip to `f_fin_fut_{YEAR}.txt` |
| **Report type** | "Futures-Only" TFF (not the legacy CFTC-COT deacot file) |
| **Market filter** | Column `Market_and_Exchange_Names` contains **"S&P 500 Consolidated"** (preferred) — if not present, "S&P 500" excluding E-Mini, Micro, Dividend, and Adjusted Interest Rate contracts |
| **Fast Money (FM) columns** | `Lev_Money_Positions_Long_All` − `Lev_Money_Positions_Short_All` = FM net contracts |
| **Asset Manager (RM) columns** | `Asset_Mgr_Positions_Long_All` − `Asset_Mgr_Positions_Short_All` = RM net contracts |
| **Local cache** | ZIP files saved to `macro_intelligence/data_cache/cftc/` by `scripts/download_cftc_tff_zip.py` |
| **Publication schedule** | Every Friday at ~3:30pm ET (data as of that Tuesday). If delayed, published the following Tuesday. |
| **History start** | 2006-06-13 (TFF Traders in Financial Futures first available) |
| **Percentile window** | Rolling 3-year (156 weeks) — recalculated each Friday |

---

### CURVE — 10-Year minus 2-Year US Treasury Yield Spread

| Field | Detail |
|-------|--------|
| **Primary source** | St. Louis FRED API |
| **Primary API endpoint** | `https://api.stlouisfed.org/fred/series/observations?series_id=T10Y2Y&api_key=<KEY>` |
| **FRED series ID** | `T10Y2Y` (10-Year Treasury Constant Maturity Minus 2-Year Treasury Constant Maturity) |
| **FRED web page** | https://fred.stlouisfed.org/series/T10Y2Y |
| **Fallback (no API key)** | FRED public CSV: `https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10Y2Y` |
| **History start** | 1976-06-01 |
| **Publication frequency** | Daily (business days) |
| **Units** | Percent (e.g., 0.38 = 38 basis points). Negative = curve inverted. |
| **Transformations used** | (1) `spread_bps = T10Y2Y * 100` — level in basis points. (2) `steepen_4wk_bps = spread_bps.diff(20)` — 20-trading-day (≈4 calendar week) change in basis points, used for rapid-steepening detection. |

---

### CPI — Inflation Surprise (Actual minus Consensus)

| Field | Detail |
|-------|--------|
| **Actual MoM % source** | US Bureau of Labor Statistics (BLS) API |
| **BLS API endpoint** | `https://api.bls.gov/publicAPI/v2/timeseries/data/` (POST, JSON body with `seriesid: ["CUSR0000SA0"]`) |
| **BLS series** | `CUSR0000SA0` — CPI-U All Urban Consumers, All Items, Seasonally Adjusted, MoM % change |
| **BLS web page** | https://www.bls.gov/cpi/ → "CPI for All Urban Consumers (CPI-U)" → Table 1 |
| **Actual fallback** | FRED `CPIAUCSL` (CPI-U All Items SA from BLS via FRED): `https://fred.stlouisfed.org/series/CPIAUCSL` — triggered after 2+ calendar days without a fresh BLS pull |
| **Consensus estimate — PRIMARY** | **Trading Economics** web scraper: `https://tradingeconomics.com/united-states/inflation-rate-mom` |
| **Consensus estimate — SECONDARY** | **Investing.com** economic calendar: `https://www.investing.com/economic-calendar/` (POST to `/Service/getCalendarFilteredData`). **Only activates when env var `INVESTING_HTTP_PROXY` is set** — required because Cloudflare blocks AWS datacenter IPs. |
| **Consensus emergency cache** | Manual CSV: `macro_intelligence/data/cpi_consensus.csv` |
| **Release date calendar** | FRED release API: `https://api.stlouisfed.org/fred/release/dates?release_id=10` (release_id 10 = CPI) |
| **Publication schedule** | Monthly, typically 2nd–3rd Tuesday of the month at 8:30am ET; covers the prior calendar month |
| **Units** | Percentage points surprise = actual MoM% − consensus MoM% |

---

### GSR — Gold-to-Silver Ratio (4-Week Change)

| Field | Detail |
|-------|--------|
| **Primary source** | Yahoo Finance via `yfinance` (ratio computed locally) |
| **Gold ticker** | `GC=F` (CME COMEX Gold front-month continuous futures) |
| **Gold Yahoo page** | https://finance.yahoo.com/quote/GC=F/ |
| **Silver ticker** | `SI=F` (CME COMEX Silver front-month continuous futures) |
| **Silver Yahoo page** | https://finance.yahoo.com/quote/SI=F/ |
| **Formula** | `GSR = GC=F close ÷ SI=F close` (daily, aligned, no smoothing) |
| **No fallback** | FRED and Bloomberg do not provide real-time continuous gold/silver futures. If Yahoo fails, GSR is unavailable. |
| **Practical history depth** | Yahoo continuous futures start ~2000-08-30 (~25-year limit for GC=F and SI=F) |
| **Publication frequency** | Daily (business days) |
| **Units** | Ratio (ounces of silver per ounce of gold; e.g., 90 means gold costs 90× as much as silver) |
| **Transformation used** | 28-calendar-day % change (`calendar_pct_change(28)`) — positive = gold outperformed silver (risk-off) |

---

### CAPE — Shiller Cyclically-Adjusted P/E Ratio

| Field | Detail |
|-------|--------|
| **Primary source** | Web scrape from multpl.com (Robert Shiller's canonical public data distributor) |
| **Exact URL** | `https://www.multpl.com/shiller-pe/table/by-month` |
| **Exact page element** | The HTML `<table>` at that URL — first column = date (e.g., "Jun 1, 2026"), second column = CAPE value (e.g., "42.70") |
| **Local cache** | `macro_intelligence/data/cape_history.csv` — refreshed on each successful scrape; used as fallback if scrape fails |
| **No API fallback** | FRED does not host CAPE/Shiller PE. If multpl.com scrape fails and the cache is present, the cache is used. If both fail, CAPE is unavailable. |
| **Underlying data** | Robert Shiller (Yale), published monthly. Raw data also available at http://www.econ.yale.edu/~shiller/data/ie_data.xls (Excel) |
| **History start** | 1881-01-01 (Shiller's full earnings history) |
| **Publication frequency** | Monthly (updated once per month, typically mid-month, at the beginning of the following month on multpl.com) |
| **Units** | Ratio (P/E); e.g., 42.70 means the S&P 500 is priced at 42.7× its 10-year inflation-adjusted average earnings |

---

## 2c. Data Gap Status — Current Implementation

_Last audited: 2026-06-07. Only variables with remaining gaps are listed. Fully covered variables are omitted._

---

### Section 1 — SSI Variables

Variables computed into the daily SSI score. Data lives in CSV caches under `macro_intelligence/data/ssi/`.

| Variable | Spec Requires | Currently Have | Gap | Fixable? |
|----------|--------------|----------------|-----|----------|
| **CNN Fear & Greed** | 2011–2026 stock market index | 2018-02-01 → 2026-present · ~3,052+ rows (Alternative.me **crypto** F&G, not CNN stock market F&G) | Wrong index — cache is crypto sentiment, not CNN stock market F&G. Also missing 2011–2018. | Bloomberg CSV export only — no free source exists |

**Summary — SSI (6 total variables):**

| Status | Count | Variables |
|--------|-------|-----------|
| No gap | 5 | NAAIM, DBMF, HYG/LQD, Breadth, VIX sentiment |
| Gap — paid data only | 1 | CNN Fear & Greed |

---

### Section 2 — Runic DB Variables

Variables stored in `macro_intelligence/data/runic.db` → `daily_readings`. Used in the Runic nightly briefing, regime classification, and combo logic.

| Variable | Spec Requires | Currently Have | Gap | Fixable? |
|----------|--------------|----------------|-----|----------|
| **CFTC Fast Money (FM/RM)** | 2006–2026 | 2010-06-18 → 2026-present · ~840 rows | 2006–2010 missing (~4 years) | No — CFTC TFF format (FM/RM split) was introduced Sep 2009; earlier data physically does not exist |
| **HY Credit Spreads OAS** | 2006–2026 real OAS | 2023–2026 real (163 rows) + 1997–2026 BAA10Y proxy (R²=0.40) | Proxy explains only 40% of OAS variance. Understates blow-outs in 2008/2020/2022. 3yr percentile skewed in stress regimes. | Paid data only — Bloomberg terminal or ICE Direct |
| **CPI Surprise** | Enough history for 3yr percentile | 2024-01-12 → 2026-present · 27 rows | Only 27 months — 3yr percentile unreliable until mid-2027 | Partial — FRED CPI actuals back to 1947; consensus estimates (needed for "surprise") from Cleveland Fed (free) |

**Summary — Runic DB (12 total variables):**

| Status | Count | Variables |
|--------|-------|-----------|
| No gap | 9 | NFCI, HY (proxy acceptable), WTI, VIX, VXTS, GSR, CNH, WALCL, SPX, CAPE, Fed Cycle |
| Gap — fixable (partial) | 1 | CPI Surprise (extend consensus back to 2010 via Cleveland Fed) |
| Gap — paid data only | 1 | HY OAS real history (Bloomberg / ICE Direct) |
| Gap — structural/impossible | 1 | CFTC FM/RM pre-2010 (data does not exist) |

**Overall totals (18 variables across SSI + Runic DB):**

| Category | Total | No Gap | Gap — Fixable | Gap — Paid Data Only | Gap — Structural/Impossible |
|----------|-------|--------|---------------|---------------------|----------------------------|
| SSI | 6 | 5 | 0 | 1 (CNN F&G) | 0 |
| Runic DB | 12 | 9 | 1 (CPI Surprise) | 1 (HY OAS) | 1 (CFTC pre-2010) |
| **Total** | **18** | **14** | **1** | **2** | **1** |

---

## 3. The 7 Named Combos A–G

A **combo** fires when *multiple* variables signal stress simultaneously. A single variable being elevated is often noise; a *combination* is a real signal. The combo system was the core intellectual product in the specification.

**Key concept — percentile vs absolute:** Some combos use absolute levels ("VIX must be above 25"), some use percentiles ("CFTC must be in the bottom 15% of 3-year history"). Both approaches are valid and deliberately mixed.

---

### Combo A — Multi-variable Stress Confluence

**Rule:** At least **2 of these 4** variables must be simultaneously at RARE or EXTREME tier: NFCI, HY, WALCL, CNH.

**Direction vote:** The code determines if the fires are **EASY MONEY / BULLISH** (majority variables pointing toward liquidity ease / recovery), **FEARFUL** (majority pointing toward deterioration), or **CONTESTED** (evenly split). Internal code label: `EASY_MONEY` (renamed from `BRAVE` in June 2026 — "brave" miscommunicates euphoria conditions).

**Plain meaning:** "Multiple independent macro indicators are all flashing yellow/red at the same time." NFCI says conditions are tightening, credit spreads are widening, the Fed is changing its balance sheet, and the yuan is moving — these four variables cover different parts of the economy, so when 2+ align, it's meaningful.

**Implemented in:** `combo_detector._combo_a_direction_vote()` and the main `detect_named_combos()` function.

---

### Combo B — Maximum Capitulation

**Rule:** ALL of these must be true simultaneously:
1. VIX ≥ 25 **and** VIX ≥ 80th percentile of full history
2. HY OAS ≥ 400bps **and** HY ≥ 80th percentile of **full expanding history** from 1996 (FRED `BAMLH0A0HYM2` — values in %, so 4.0 = 400bps; dual abs + percentile, no 3y rolling)
3. CFTC Fast Money net positioning ≤ 15th percentile (hedge funds extremely short)

**Status strings:** CONFIRMED (all three), PENDING_CFTC_CONFIRM (CFTC data may be stale — it's released Friday afternoon and takes until Tuesday to fully confirm).

**Plain meaning:** "Panic-selling capitulation." All three indicators say: VIX is spiked → everyone is scared; credit is stressed → companies can't borrow cheaply; hedge funds are maximally short → everyone has already sold or is short. This is historically a **buy** signal — it fires near market bottoms.

**Special rule — `vix_bypass`:** When Combo B is active, the C++ engine ignores VIX-based position-size reduction. Normally, high VIX would make the system trade smaller. But during Combo B, the system should actually buy *more* (contrarian), not less — so VIX sizing is overridden.

**Reference date:** October 7, 2025 — VIX spiked to ~52 (well above 35), credit stressed, CFTC extreme short. Combo B fired.

---

### Combo C — Oil Shock CPI Risk (+ Cancel Rule)

**Rule:** ALL of these must be true:
1. WTI oil 4-week change ≥ **+10%** (large oil spike)
2. CPI surprise ≥ 0.2pp (inflation reading was hotter than expected)
3. Fed balance sheet (WALCL) is flat or not actively expanding

**Fire condition (June 2026 correction):** CPI **HOT surprise** required — `actual − consensus ≥ +0.2pp` (not cold surprise).

**Cancel rule:** Combo C cancels after **4 consecutive Fridays** where WTI 4wk change < +5% **and** the **governing CPI print** (most recent confirmed release, any week) shows `actual ≤ consensus`. PPI is **not** a CPI substitute in cancel logic (`ppi_cooling` is narrative-only). On cancel, briefing shows status **CANCELLED** with `cancel_date` (distinct from INACTIVE). Cancel check runs nightly and on Friday pull. Logic: `combo_c_cancel.py`.

**Plain meaning:** "Oil has spiked and inflation is hot — the Fed's hands are tied." This combo flags the scenario where the Fed *cannot* cut rates to help markets because oil-driven inflation is still running hot. Historically associated with stagflation risk.

**Reference event:** April–May 2026 — WTI rose ~50% in 4 weeks due to Iran conflict. Combo C fired.

---

### Combo D — Low-Vol Crowding

**Rule:** ALL of these:
1. VXTS ratio ≥ 1.10 (term structure in contango — near-term VIX unusually calm vs 3-month)
2. CFTC Fast Money positioning ≥ 85th percentile (hedge funds are *very* long)
3. VIX ≤ 18 (absolute low vol — everyone is complacent)

**Plain meaning:** "Markets are extremely calm and everyone is leaning the same way (long)." This is a precursor combo — it doesn't signal immediate danger, but it flags when conditions are ripe for a shock. A quiet market where everyone is positioned long is fragile: if anything bad happens, everyone sells at once.

**Reference:** The late-2021 environment. Low VIX, hedgies all long, term structure utterly calm.

---

### Combo E — Structural Bear Regime

**Rule:** At least **2 of these 3** must be true:
1. CAPE ≥ 28 (valuations expensive)
2. NFCI ≤ −0.3 (BUT financial conditions still easy, meaning the Fed is still accommodating despite expensive markets)
3. CFTC FM positioning ≥ 80th percentile (hedge funds crowded long)

**Status strings:** CONFIRMED (2 of 3), CONFIRMED_3_OF_3 (all three hit simultaneously).

**Plain meaning:** "The market is expensive, positioning is stretched, and money is still easy — this is a structurally fragile bull market." Combo E fires in environments like 2021-early 2022 or today's CAPE-elevated market. It's not a crash signal — it's a "reduce leverage, be cautious" signal.

**Hit rate horizon:** **12m** primary (bearish — % of fires with negative SPX_12m). Do not use 3m for E — misleading for slow structural signals.

**Confirmed legs:** Briefing exposes `confirmed_legs` (e.g. `CAPE, NFCI`) so readers see which of the 2-of-3 legs fired — E can confirm without CFTC when FM is at 5th percentile.

**Current state:** As of June 2026, CAPE is at ~42, CFTC FM is at the 5th percentile (extremely short), and NFCI is easy. Combo E confirms on CAPE + NFCI (2/3); CFTC leg is **not** active.

---

### Combo F — 50-Week MA Reclaim

**Rule:** ALL of these:
1. SPX (S&P 500) weekly close was ≥ **3%** higher than the 50-week moving average — the market meaningfully reclaimed a major technical level
2. CFTC FM positioning ≤ 50th percentile (hedge funds not yet fully long — still room to buy)
3. The reclaim happened within the past **26 weeks** (the combo has a 6-month lifecycle; it expires after that)
4. Invalidation: if SPX subsequently falls **back below** the 50-week moving average, Combo F is cancelled

**Validation date:** June 8, 2020 — the first reference date for this combo in the v3 spec (the post-COVID recovery reclaim).

**Plain meaning:** "The market has broken decisively above a major long-term support level, and positioning hasn't caught up yet." This is a momentum + mean-reversion setup. Hedge funds are still cautious (low positioning), so there is fuel for them to buy. Historically bullish.

**Hit rate horizon:** **6m** primary, 3m secondary (bullish).

**Duration display:** Week counter anchored to episode start (first F fire after last SPX below 50WMA week); briefing shows `started YYYY-MM-DD`.

**Reference:** March 30, 2026 — SPX reclaimed the 50-week MA with a +3%+ weekly gain. Combo F fired.

---

### Combo G — Vol Suppression + Credit Risk

**Rule:** ALL of these:
1. VXTS ratio ≤ 1.00 — **backwardation** (near-term vol exceeds long-term — stress, not just calm)
2. HY credit spreads 4-week change ≥ **+30 bps** (spreads *widening* at least 30bps in a month)
3. VIX ≤ 20 (absolute VIX still relatively low)

**Plain meaning:** "Hidden stress is building — the credit market is flashing warning signs even though the fear gauge (VIX) is not yet panicking." This is a leading-indicator combo. Credit often *leads* equity volatility by days or weeks. When spreads are widening but VIX is still calm, it means something bad is brewing.

**Implemented with:** `_hy_4wk_change_bps()` function calculates the actual basis-point change in HY OAS over the prior 28 calendar days.

**Hit rate:** No return hit rate — timing warning / leading indicator only. **Testable from 2007** (VXTS / VIX3M data inception). Pre-2007 B instances cannot be used for G→B cascade validation.

---

### The 298 Generic Combos

Beyond the 7 named combos, the system also computes **generic combos** — any pair or trio of variables that are simultaneously at RARE or EXTREME. There are 298 possible combinations of the 12 variables.

- On **Fridays** (via `run_macro_friday_pull.py`), all 298 are computed and the active ones are stored in the database.
- On **nightly runs**, the top ones (those that have historically fired ≥ 3 times with ≥ 60% SPX hit rate) are surfaced in `generic_combo_watch` in the JSON output.

---

### Dominant signal priority

When multiple combos fire at the same time, one is declared **dominant** using a fixed priority table:

| Priority | Combo | Rationale |
|----------|-------|-----------|
| 100 (highest) | C | Immediate oil/inflation risk overrides everything |
| 90 | B | Capitulation — strong reversal signal |
| 80 | F | Momentum — strong directional signal |
| 70 | E | Structural regime — sets the tone |
| 60 | D | Complacency warning |
| 50 | G | Credit leading indicator |
| 40 (lowest) | A | Multi-variable confluence |

Special: CONTESTED Combo A does *not* become dominant — it goes to the watch list instead.

---

## 4. How It Was Implemented

### Repository structure

```
MindWealth_UI/
├── macro_intelligence/              # data, config, DB, output files
│   ├── CONFIG.yaml                  # all thresholds and combo rules
│   ├── DATA_SOURCES.yaml            # 26 variables, sources, fallbacks
│   ├── SSI_CONFIG.yaml              # SSI layer weights and thresholds
│   └── data/runic.db                # SQLite history database
├── src/
│   ├── macro_intelligence/          # Python engine (32 modules)
│   └── sentiment_superindex/        # SSI engine (14 modules)
├── scripts/                         # CLI runners and maintenance
│   ├── run_macro_friday_pull.py
│   ├── run_macro_nightly.py
│   ├── run_ssi_daily.py
│   ├── backfill_forward_returns_only.py
│   ├── run_full_v3_verification.py
│   └── run_ssi_validation_suite.py
└── tests/                           # 20+ unit test files
```

### Every file and what it does

#### Data layer — `src/macro_intelligence/data/`

| File | What it does |
|------|-------------|
| `pull_all.py` | Master function `load_all_series()` — calls all 12 individual pullers, returns a dict of pandas Series; handles **CNH fallback** to `FRED:DEXCHUS` and **WTI fallback** to `FRED:DCOILWTICO` when Yahoo returns <100 bars |
| `fred_pull.py` | Pulls NFCI, HY, WALCL, CURVE from FRED API (or FRED CSV if no API key) using `fredapi` library |
| `yahoo_pull.py` | Pulls VIX, VXTS (`^VIX3M/^VIX`), WTI (`CL=F`), CNH (`USDCNH=X`), GSR (`GC=F/SI=F`), SPX from Yahoo Finance using `yfinance`; `calendar_pct_change(28)` computes exact 28-calendar-day returns |
| `cftc_pull.py` | Downloads CFTC TFF ZIP files, parses them using spec columns (`Lev_Money_Positions_Long/Short_All` for FM; `Asset_Mgr_Positions_Long/Short_All` for RM); market filter: `S&P 500 Consolidated`; functions `fetch_cftc_fast_money_net()` and `fetch_cftc_asset_manager_net()` |
| `bls_pull.py` | Pulls CPI actual from BLS API series `CUSR0000SA0`; fallback to `FRED:CPIAUCSL` if BLS unavailable for 2+ calendar days; `load_cpi_surprise_series()` computes actual minus consensus |
| `cpi_pull.py` | Orchestrates CPI collection — BLS + consensus; handles retry schedule |
| `investing_cpi_consensus.py` | Scrapes CPI consensus — **primary source is Trading Economics** (`tradingeconomics.com/united-states/inflation-rate-mom`). Investing.com is a secondary fallback that only activates when the `INVESTING_HTTP_PROXY` env var is set (Cloudflare blocks direct AWS IPs). Emergency last resort is `macro_intelligence/data/cpi_consensus.csv`. |
| `cape_scrape.py` | Scrapes current CAPE from `multpl.com`; falls back to local `cape_history.csv` cache if scrape fails |
| `retry_cache.py` | Caching and retry logic for data pulls that can fail transiently |

**Known data-layer limitations (confirmed by live testing):**

| Variable | Spec lookback | Actual data available | Reason | Impact |
|---|---|---|---|---|
| HY (`BAMLH0A0HYM2`) | 1996-01-01 | 2023-06-05 (3 years only) | ICE BofA licensing restricts FRED API distribution to ~3 years, even with an API key — this is a FRED platform restriction, not a code bug | Combo B uses absolute threshold (≥ 400 bps), so combo detection is unaffected. HY percentile rank is calculated on available 3-year window. |
| WTI (`CL=F`) | 1985-01-01 | 2000-08-23 (Yahoo futures limit) | Yahoo Finance continuous futures only go back ~25 years; FRED `DCOILWTICO` fallback (1986) fires automatically when Yahoo returns <100 bars | WTI uses rolling 3-year percentile — live readings unaffected |
| GSR (`GC=F/SI=F`) | 1968-01-01 | 2000-08-30 (Yahoo futures limit) | Same Yahoo futures depth limitation for gold and silver continuous contracts | GSR uses rolling 3-year percentile — live readings unaffected |

#### Engine layer — `src/macro_intelligence/engine/`

| File | What it does |
|------|-------------|
| `percentiles.py` | `percentile_rank(value, series)` — where does today's value sit in history? Returns 0–100. Used everywhere. |
| `combo_detector.py` | **Heart of the system.** `detect_named_combos()` runs the rules for A–G. `_combo_a_direction_vote()` returns EASY_MONEY/FEARFUL/CONTESTED. Combo B HY dual (400bps + 80th pctile). `_hy_4wk_change_bps()` for Combo G. `detect_all_combos()` for the 298 generics. |
| `combo_metadata.py` | Per-combo validated horizons, bullish/bearish direction, briefing display labels |
| `combo_c_cancel.py` | 4-Friday WTI + governing CPI cancel; stores `cancel_date`; briefing CANCELLED status |
| `dominant.py` | `resolve_dominant(active_combos)` — applies the priority table, returns single dominant signal or None |
| `hit_rates.py` | Queries `runic.db` forward returns; computes `spx_3m_hit_rate` and top-3 analog dates |
| `forward_returns.py` | Stores SPX returns 1w/2w/1m/3m/6m after each combo fire; `backfill_forward_returns()` fills history |
| `persistence.py` | Detects streak patterns (7-week grind, 3-week surge, VIX suppressed, etc.) |
| `vix_bypass.py` | `compute_vix_bypass(active_combos, ssi_confirmed_f)` — returns True when Combo B active or Combo F + SSI confirmed |
| `regime_rules.py` | `compute_regime_heuristic()` — fallback 5-dimension regime labels when Claude API unavailable |
| `prefilter.py` | Filters 298 generic combos to only those with ≥3 historical fires and ≥60% SPX hit rate |

#### Database — `src/macro_intelligence/db/`

| File | What it does |
|------|-------------|
| `schema.sql` | CREATE TABLE statements for 10 tables |
| `connection.py` | `get_connection()` / `init_db()` — single SQLite file in `macro_intelligence/data/runic.db` |
| `migrate.py` | Incremental schema migrations for v3 changes |

**Tables:** `variables`, `thresholds`, `daily_readings`, `signal_fires`, `combo_fires`, `forward_returns`, `rule_library`, `persistence_fires`, `macro_regime_log`, `threshold_review_log`

#### Claude / AI layer — `src/macro_intelligence/claude/`

| File | What it does |
|------|-------------|
| `_client.py` | Thin wrapper around Anthropic Python SDK |
| `regime_classifier.py` | Sends today's macro readings to Claude; asks for 5-dimension regime labels (Fed cycle, curve, geo, valuation, liquidity); falls back to `regime_rules.py` heuristics if no API key |
| `nightly_briefing.py` | Generates the BTIG-style narrative paragraph using Claude; includes Tavily news context for geo_overlay |
| `geo_news.py` | Calls Tavily API to fetch relevant geopolitical/macro headlines |

#### Jobs — `src/macro_intelligence/jobs/`

| File | What it does |
|------|-------------|
| `friday_pull.py` | Full Friday pipeline: pull all series → compute percentiles → run ALL 298 combos → persist → update CFTC status |
| `nightly_run.py` | Nightly pipeline: pull series → named combos only → Claude regime → Claude narrative → compute hit rates + analogs → write `runic_output.json` + briefing; also includes `generic_combo_watch` |
| `monthly_threshold_review.py` | Prompts for manual threshold review on first of month |

#### Output — `src/macro_intelligence/output/`

| File | What it does |
|------|-------------|
| `json_writer.py` | Assembles and writes `runic_output.json`; handles all fields including `pending_cpi_release` (wired to DB), `combo_c_cancel`, `analog_details`, `ppi_cooling` |
| `briefing_renderer.py` | Turns nightly output into BTIG-style HTML briefing |

#### Scheduled jobs — `scripts/`

| Script | When it runs | What it does |
|--------|-------------|-------------|
| `run_ssi_daily.py` | Weekdays 08:00 ET | SSI score → `positioning.json` |
| `run_macro_friday_pull.py` | Fridays 17:30 ET | Full Friday pull + all 298 combos |
| `run_macro_nightly.py` | Mon–Fri 18:00 ET | Named combos + Claude + JSON |
| `install_aws_cron.sh` | One-time | Sets up Linux cron on AWS `51.20.53.218` |

---

## 5. SSI — Sentiment SuperIndex

### Why do we need SSI?

The 12 macro variables above measure *fundamental* stress — credit, Fed policy, inflation, volatility. But they are mostly **weekly** signals that react slowly.

The C++ trading engine also needs a **daily, sentiment-based** size multiplier. Before entering a position, it should know: "Is the market in a fearful, neutral, or greedy state today?"

That is what SSI provides. It computes every weekday morning and writes `positioning.json`, which the nightly Runic job then reads.

### The SSI inputs (4 Layer 2 inputs + breadth inputs)

SSI uses a different set of inputs from Runic — deliberately, to avoid double-counting:

| Input | Layer | Why it is in SSI (not Runic) |
|-------|-------|------------------------------|
| **HYG/LQD ratio** | 2 | Same credit direction as HY OAS (Runic), but a *different instrument* — ETF price ratio vs bond spread. Kept in SSI, excluded from Runic. |
| **DBMF 21-day beta vs SPY** | 2 | CTA hedge fund proxy — different from CFTC futures positioning (Runic). |
| **CNN Fear & Greed** | 1 / 2 | Retail/sentiment survey — not in any Runic variable. |
| **VIX3M/VIX ratio** | 2 | Same VXTS ratio as Runic Combo D; used in SSI composite only. |
| **AAII Bull-Bear spread** | 1 | Weekly survey of individual investors |
| **NAAIM Exposure** | 1 | Weekly survey of registered investment advisors |
| **McClellan Oscillator** | 2 | Breadth indicator: advancing minus declining stocks |
| **% above 200-day MA** | 2 | What fraction of S&P 500 stocks are in uptrends |
| **NH/NL Ratio** | 2 | New highs as a share of new highs + new lows (`highs / (highs + lows)`, bounded 0–1) |
| **SKEW** | 2 | Options market tail-risk pricing |
| **DBMF** | 3 | CTA proxy (Layer 3 = positioning) |
| **CFTC FM + RM** | 3 | Same source as Runic CFTC, but SSI splits Fast Money and Real Money separately |

### How the SSI score is computed

1. Each Layer 2 input is converted to a **z-score** (standard deviations from its running mean) and **clipped at ±3**.
2. The four Layer 2 inputs are **weighted** and combined:
   - HYG/LQD: 30%
   - DBMF beta: 25%
   - CNN Fear & Greed: 25%
   - VIX ratio: 20%
3. This produces a **composite SSI level** between roughly −1 (extreme fear/risk-off) and +1 (extreme greed/risk-on).
4. The level is compared to the last 5 years of history to produce a **5-year percentile** (0–100).

### What the SSI output means

| SSI level / percentile | Interpretation | `ssi_multiplier` |
|------------------------|----------------|------------------|
| ≤ 20th percentile (very low) | Extreme fear / risk-off | **1.2** (increase size — buy fear) |
| 21st–79th percentile | Normal | **1.0** |
| ≥ 85th percentile (very high) | Extreme greed / risk-on | **0.8** or **1.2** for shorts |

### Layer 2 confirmation system

The four Layer 2 inputs also vote individually. If ≥ 2 of the 4 agree that conditions are stressed OR greedy (depending on direction), the status becomes "CONFIRMED" and the multiplier 1.2 is applied. If only 1 agrees: PARTIAL, multiplier 1.0. If none: UNCONFIRMED, multiplier 0.8.

---

## 6. Every Threshold Justified

This section covers every configurable threshold in `CONFIG.yaml` and `SSI_CONFIG.yaml`. For each one: what it is, why that number was chosen, and what evidence supports it.

A fuller threshold-justification document lives at: `docs/ssi_validation/SSI_THRESHOLD_JUSTIFICATION.md`

---

### 6.1 Macro variable thresholds (CONFIG.yaml)

#### Quick reference — spec vs implemented

The table below shows, for every variable, what the spec documents suggested and what was actually implemented. Most thresholds were taken verbatim from the spec. The one meaningful derivation is the WTI RARE threshold — the spec explicitly stated only the EXTREME level.

| Variable | Spec RARE | Implemented RARE | Spec EXTREME | Implemented EXTREME | Status |
|---|---|---|---|---|---|
| NFCI | ±0.3 / 80th–20th pctile | ±0.3 / 80th–20th pctile | ±0.8 / 95th–5th pctile | ±0.8 / 95th–5th pctile | ✅ Exact match |
| HY | 400 bps / 80th pctile | 400 bps / 80th pctile | 500 bps / 95th pctile | 500 bps / 95th pctile | ✅ Exact match |
| WALCL | ±0.8% MoM | ±0.8% MoM | ±2.0% MoM | ±2.0% MoM | ✅ Exact match |
| CNH | ±1.5% 4wk | ±1.5% 4wk | ±3.5% 4wk | ±3.5% 4wk | ✅ Exact match |
| WTI | *(not stated)* | **±6% 4wk** | ±10% 4wk | ±10% 4wk | ⚠️ RARE derived — see note |
| VIX | 25 / 80th pctile | 25 / 80th pctile | 35 / 95th pctile | 35 / 95th pctile | ✅ Exact match |
| VXTS | low 0.95 / high 1.10 | low 0.95 / high 1.10 | low 0.85 / high 1.20 | low 0.85 / high 1.20 | ✅ Exact match (v3) |
| CFTC | 15th / 85th pctile | 15th / 85th pctile | 5th / 95th pctile | 5th / 95th pctile | ✅ Exact match |
| CURVE | −30 bps / +15 bps/4wk | −30 bps / +15 bps/4wk | −80 bps / +40 bps/4wk | −80 bps / +40 bps/4wk | ✅ Exact match |
| CPI | 0.2 pp | 0.2 pp | 0.4 pp or 2× consecutive | 0.4 pp | ✅ Exact match |
| GSR | ±5% 4wk | ±5% 4wk | ±8% 4wk | ±8% 4wk | ✅ Exact match |
| CAPE | 28× / low 16× | 28× / low 16× | 32× / low 12× | 32× / low 12× | ✅ Exact match |

---

#### NFCI thresholds: RARE ±0.3 / EXTREME ±0.8

**Spec said:** `Runic_Methodology_Threshold_Justification.pdf` and the v3 integration note both explicitly state ±0.3 as the RARE absolute threshold and ±0.8 as EXTREME. The secondary percentile gates (80th/20th RARE, 95th/5th EXTREME) are also in the spec.

**Implemented:** Exactly as spec'd — both the absolute sd levels and the percentile fallbacks.

**Status: ✅ No modification.**

The NFCI scale is zero-centred (zero = historical average). The Chicago Fed's own documentation describes ±0.3 as "moderate deviation" and ±0.5+ as "significant." The choice of ±0.8 for EXTREME (rather than the round ±1.0) is justified because in past crises the NFCI rarely exceeds 2.0 even at peaks — the percentile gate (95th/5th) is the real statistical anchor; the absolute level is a sanity check. The percentile fallback (80th/95th and 20th/5th) provides a time-varying alternative: "top 5% of the past 50 years" is self-calibrating as the world changes.

---

#### HY credit spread thresholds: RARE 400 bps / EXTREME 500 bps

**Spec said:** `Runic_Agent_Combo_Cheatsheet_v2.pdf` explicitly states "HY ≥ 400 bps" as the Combo B entry level. The methodology document confirms 400 bps RARE and 500 bps EXTREME with 80th/95th percentile cross-checks. The v3 integration note cites Oct 2022 HY at ~580 bps as the historical example (an earlier May 26 email quoted ~614 bps — minor discrepancy, both above 500).

**Implemented:** Exactly as spec'd.

**Status: ✅ No modification.**

400 bps is one of the most widely cited credit stress markers: it corresponds historically to recessionary credit conditions. 500 bps+ has only occurred in 2008–2009 (GFC) and March 2020 (COVID). The cross-validation via 80th/95th percentile of the full 1996-present history provides a quantitative anchor — 400 bps has historically sat near the 80th percentile of the long-run OAS distribution.

---

#### WALCL ROC thresholds: RARE ±0.8% / EXTREME ±2.0%

**Spec said:** The methodology document specifies ±0.8% MoM as the RARE threshold and ±2.0% as EXTREME. Critically, the v3 integration note also defines the Combo C "WALCL flat" condition as MoM between −0.8% and +0.8% — which is identical to the RARE absolute threshold. This cross-referencing confirmed the number.

**Implemented:** Exactly as spec'd. The RARE threshold (±0.8%) also serves double duty: anything inside this band is "flat WALCL" for Combo C purposes.

**Status: ✅ No modification.**

The Fed's balance sheet grows or shrinks by small amounts most weeks. ±0.8% MoM is a meaningful signal that policy is actively changing direction. ±2.0% is crisis territory — emergency QE in March 2020 produced single-week jumps of 4–5%. The rolling 3-year percentile is primary; the absolute ROC serves as a sanity check when the rolling history is regime-distorted.

---

#### CNH thresholds: RARE ±1.5% / EXTREME ±3.5%

**Spec said:** The `SSI_OpenQuestions_DivyanshuTestList.docx` explicitly states "±1.5% RARE, ±3.5% EXTREME" for the USD/CNH 28-calendar-day change.

**Implemented:** Exactly as spec'd.

**Status: ✅ No modification.**

The CNH/USD rate is relatively stable in normal conditions. A 4-week move of 1.5% is historically unusual; 3.5% marks genuine stress — seen during the 2015 devaluation scare and the 2018–2019 trade war escalation. The 3-year rolling percentile supplements the absolute levels since the CNH float regime has evolved since 2010.

---

#### WTI thresholds: RARE ±6% / EXTREME ±10%

**Spec said:** `Runic_Agent_Combo_Cheatsheet_v2.pdf` explicitly states **"10% extreme"** for WTI 4-week change. The spec **did not specify a RARE level** — only the EXTREME entry condition for Combo C was stated.

**Implemented:** EXTREME ±10% exactly as spec'd. RARE ±6% was **derived** (not in any spec document).

**Status: ⚠️ EXTREME = exact match. RARE = derived addition.**

**Justification for 6%:** The spec defines Combo C entry at ≥10% (the EXTREME), which means by design the variable's EXTREME matches the combo entry. A separate RARE tier was needed for the general variable tier engine (which has NORMAL / RARE / EXTREME states). 6% was chosen because:
- Moderate oil disruptions (OPEC cuts, Iranian export reductions) typically produce 4–8% 4-week moves without a full supply shock;
- The 6% level sits at approximately the 80th percentile of the rolling 3-year distribution historically;
- It provides a graduated response — "noteworthy oil move" (RARE) vs "oil shock" (EXTREME / Combo C entry).

The Combo C combo rule still anchors at 10%, so this RARE addition has no effect on combo detection — it is purely for the `variables_dashboard` display.

---

#### VIX thresholds: RARE 25 / EXTREME 35

**Spec said:** `Runic_Agent_Combo_Cheatsheet_v2.pdf` explicitly anchors VIX ≥ 25 as the Combo B entry level. The methodology document specifies 25 RARE and 35 EXTREME in the variable tier table. The `vix_bypass` constant also anchors at 35.

**Implemented:** Exactly as spec'd.

**Status: ✅ No modification.**

These are the most widely cited VIX levels in professional market commentary. Below 15 = calm market. 20–25 = mildly elevated. 25+ = genuine fear. 35+ = panic (VIX spiked to ~52 during October 2025 and ~80+ during COVID March 2020). The Combo B rule anchors at 25 absolute for all three required legs; the `vix_bypass` bypass threshold is 35.

---

#### VXTS thresholds: RARE low 0.95 / high 1.10 — EXTREME low 0.85 / high 1.20

**Spec said:** The v3 integration note (`28_May_2026_Divyanshu_Runic_Integration_Note_v3.docx`) explicitly states all four levels: 0.95 (near-term stress onset), 1.10 (complacency onset), 0.85 (acute stress), 1.20 (extreme complacency). Earlier spec versions were less precise on the exact numbers.

**Implemented:** Exactly as v3 spec'd.

**Status: ✅ No modification (v3 was the authoritative source).**

The normal VIX3M/VIX ratio sits in the 1.05–1.15 range (longer-dated volatility is structurally higher than near-term). A ratio below 1.0 means near-term fear is higher than long-term fear — backwardation, a classic panic pattern. The four levels:
- **1.10 RARE high**: complacent market where near-term vol is unusually suppressed → Combo D WATCH
- **1.20 EXTREME high**: extreme complacency
- **0.95 RARE low**: onset of backwardation, near-term stress building → Combo G WATCH
- **0.85 EXTREME low**: acute panic (approximately what was seen Oct 7, 2025)

These were confirmed by the Oct 2022 case study: the ratio on Oct 13, 2022 was near 0.85, consistent with the Combo B capitulation event.

---

#### CFTC thresholds: RARE 15th / 85th pctile — EXTREME 5th / 95th pctile

**Spec said:** The original spec document uses "extreme washout" language for Combo B and explicitly states ≤ 15th percentile for the FM net leg. The combo cheatsheet and methodology document confirm the full RARE/EXTREME table: 15th/85th RARE, 5th/95th EXTREME.

**Implemented:** Exactly as spec'd.

**Status: ✅ No modification.**

The CFTC TFF series only goes back to 2006 reliably, so absolute net position levels are less meaningful than their historical percentile rank — a net of −100,000 contracts could be extreme in one period and normal in another depending on market size. 15th/85th captures the outer ~15% tail of the distribution (unusual, not extreme). 5th/95th is the true tail. During Oct 13, 2022 (the canonical Combo B case), FM net positioning was at the 5th percentile — the exact threshold that makes Combo B fire as ACTIVE rather than WATCH. Rolling 3-year window (156 weeks) is used to keep the percentile regime-relevant.

---

#### CURVE thresholds: RARE −30 bps / EXTREME −80 bps (spread); +15 bps / +40 bps per 4wk (steepening)

**Spec said:** The methodology document specifies −30 bps inversion as RARE and −80 bps as EXTREME for the 10Y-2Y spread. The steepening rate thresholds (15 bps/4wk RARE, 40 bps/4wk EXTREME) are in the addendum to the original build document.

**Implemented:** Exactly as spec'd, including both the spread level and the 4-week steepening rate.

**Status: ✅ No modification.**

A spread of −30 bps is mild inversion — meaningful but not historically unusual. −80 bps is deep inversion, matching the 2022–2023 cycle which preceded genuine recession fears. The steepening rate thresholds (15 bps/4wk, 40 bps/4wk) capture the *change*, not just the level — rapid steepening after deep inversion is historically a recession-transition signal (the curve un-inverts as short-end rates fall faster than long-end, often coinciding with Fed pivot). The `curve_features()` function computes `steepen_4wk_bps = spread_bps.diff(20)` (~4 weeks on daily data) to produce this meta-field.

---

#### CPI thresholds: RARE 0.2 pp / EXTREME 0.4 pp

**Spec said:** v3 integration note explicitly states: *"0.2pp RARE, 0.4pp or 2× consecutive EXTREME."* This was one of the clearest threshold calls in the entire spec corpus.

**Implemented:** 0.2pp RARE and 0.4pp EXTREME as spec'd. The "2× consecutive" rule is implemented as a secondary condition in Combo C logic (two back-to-back hot prints trigger even if the individual prints are below 0.4pp).

**Status: ✅ No modification.**

0.2pp CPI surprise (actual minus consensus) is the smallest amount that consistently produces a meaningful bond market reaction — below this, the miss is within the noise of consensus estimation. 0.4pp is a significant miss that typically moves 10-year yields by 10+ bps on release day. The two-consecutive rule catches sustained inflation drift that single prints might miss.

---

#### GSR thresholds: RARE ±5% / EXTREME ±8%

**Spec said:** The methodology document specifies ±5% 4-week change as RARE and ±8% as EXTREME for the gold/silver ratio. These were carried unchanged from the original build specification into CONFIG.yaml.

**Implemented:** Exactly as spec'd.

**Status: ✅ No modification.**

The gold/silver ratio (GSR) is slow-moving in normal conditions — it changes by 1–2% per month in quiet markets. A ±5% 4-week move marks a clear rotation between the metals, typically reflecting a shift in the safe-haven premium (gold rises more than silver in risk-off; silver outperforms gold in risk-on industrials rallies). ±8% is a meaningful flight-to-safety trade. The 3-year rolling percentile provides dynamic calibration because the absolute ratio level has trended significantly over decades.

---

#### CAPE thresholds: RARE 28× (high) / 16× (low) — EXTREME 32× (high) / 12× (low)

**Spec said:** The methodology document specifies 28× as the RARE high threshold ("caution zone") and 32× as EXTREME. The low-side thresholds (16× RARE, 12× EXTREME) are in the same document for completeness, capturing "historically cheap" valuations. These were based on Shiller's own commentary on the Cyclically Adjusted P/E.

**Implemented:** Exactly as spec'd.

**Status: ✅ No modification.**

28× is Shiller's informal "caution zone" — roughly the level at which long-run 10-year real returns historically begin to deteriorate below 5% annualised. 32× is "expensive by almost any historical measure outside the 1999–2000 tech bubble." Today's CAPE (as of June 2026) is ~42, sitting at the 99th percentile of all readings since 1881 — well above both thresholds. The low-side thresholds (16× / 12×) are primarily theoretical for the current environment but were included so the engine can signal "historically cheap" conditions symmetrically.

---

### 6.2 Combo-specific thresholds

The combo entry conditions were all taken directly from the spec documents. The table below shows the source document for each combo threshold and whether any clarification was needed.

| Combo | Key threshold | Spec source | Status |
|---|---|---|---|
| B | VIX ≥ 25, HY ≥ 400 bps, CFTC ≤ 15th pctile | Cheatsheet v2 + v3 | ✅ Exact match |
| C entry | WTI 4wk ≥ +10%, CPI surprise ≥ 0.2 pp, WALCL MoM between −0.8% and +0.8% | v3 note (clarified "flat" = ±0.8% MoM) | ✅ Exact match after v3 clarification |
| C cancel | WTI 4wk < +5% for 4 consecutive Fridays; CPI ≤ consensus | v3 note (explicit) | ✅ Exact match |
| D | VXTS ≥ 1.10, CFTC FM ≥ 85th pctile, VIX **strictly** < 18 | v3 note (v3 clarified strict < 18; 18.00 does not qualify) | ✅ Exact match after v3 clarification |
| E | CAPE ≥ 28, NFCI ≤ −0.3 (easy), CFTC FM ≥ 80th pctile; 2 of 3 → CONFIRMED | Methodology doc + v3 | ✅ Exact match |
| F | SPX 50WMA weekly reclaim ≥ +3%, CFTC ≤ 50th pctile, active ≤ 26 weeks | Methodology doc + v3 | ✅ Exact match |
| G | VXTS < 1.00, HY 4wk widen ≥ +30 bps, VIX ≤ 20 | v3 note | ✅ Exact match |

---

#### Combo B: VIX ≥ 25, HY ≥ 400 bps, CFTC ≤ 15th percentile

**Spec said / Implemented:** All three legs are verbatim from Cheatsheet v2 and confirmed in v3. No modification.

Three anchors from three completely different asset classes — equity volatility, credit, and speculative futures positioning. All must be true simultaneously. The intersection is what makes this a high-conviction buy signal: VIX 25 = mild-to-moderate fear (not yet full panic), HY 400 bps = credit stress confirmed and widespread, CFTC ≤ 15th = leveraged money already piled into shorts. The canonical historical case is October 13, 2022: VIX ~32, HY ~580 bps, CFTC at ~5th percentile — all three legs comfortably exceeded.

---

#### Combo C: WTI ≥ +10%, CPI surprise ≥ 0.2 pp, WALCL flat (±0.8% MoM)

**Spec said / Implemented:** v3 integration note is the authoritative source. The "+10% WTI" and "0.2pp CPI" were in the original cheatsheet. The exact definition of "WALCL flat" was ambiguous in early specs ("no major QE/QT") — the v3 note clarified it as MoM between −0.8% and +0.8%, which directly mirrors the WALCL RARE threshold. This clarification was applied without modification.

WTI +10% in 4 weeks = oil shock (not just noise). CPI ≥ 0.2pp surprise confirms the energy shock is already feeding into broader inflation. WALCL flat = the Fed is neither easing nor tightening significantly, meaning no monetary offset to the stagflation dynamic.

**Cancel rule: 4 clean Fridays below +5% WTI change**

**Spec said / Implemented:** v3 explicitly states: WTI 4wk change < +5% for 4 consecutive Fridays, AND CPI not hot (actual ≤ consensus). Counter resets to zero if any Friday fails either leg. Implemented exactly as spec'd in `combo_c_cancel.py`. The "+5% cancel level" is deliberately lower than the "+10% entry" — the combo stays active even if oil partially retreats, confirming the oil shock has truly resolved rather than just cooling temporarily.

---

#### Combo D: VXTS ≥ 1.10, CFTC FM ≥ 85th pctile, VIX strictly < 18

**Spec said:** v3 note clarified that VIX must be **strictly below 18** — 18.00 itself does not qualify. The VXTS and CFTC thresholds were in the original cheatsheet.

**Implemented:** Exactly as v3 spec'd, including the strict < 18 (not ≤).

All three legs point to the same thing: complacency. VXTS ≥ 1.10 = term structure shows no near-term worry. CFTC ≥ 85th pctile = leveraged funds heavily positioned long. VIX < 18 = equity implied vol has been suppressed. The simultaneous presence of all three describes the "crowded complacent market" that historically precedes a volatility shock.

---

#### Combo E: CAPE ≥ 28, NFCI ≤ −0.3 (easy), CFTC FM ≥ 80th pctile

**Spec said / Implemented:** All three thresholds and the "2 of 3 → CONFIRMED" rule are verbatim from the methodology document and confirmed in v3 (where v3 also clarified the status string should be `CONFIRMED`, not `PARTIAL`). No threshold modification.

Structural fragility combo — these three together say the market is expensive (CAPE ≥ 28), monetary conditions are still supporting that stretch (NFCI easy = FCI below −0.3), and positioning is extended (CFTC ≥ 80th). This combination doesn't predict timing of a reversal — it signals conditions are ripe. NFCI −0.52 (as of June 2026) well exceeds the −0.3 easy threshold (confirmed in v3: −0.52 fires the easy leg).

---

#### Combo F: SPX 50WMA reclaim ≥ +3%, CFTC ≤ 50th pctile, active ≤ 26 weeks

**Spec said / Implemented:** All three parameters are verbatim from the methodology document. The 3% threshold, 50th-percentile CFTC gate, and 26-week window are unchanged. The validation date (2020-06-08, +6.2% week, active window ends 2020-12-14) comes from v3 — it corrects an older date of 2020-06-29 that appeared in an early email.

The 3% threshold ensures the 50WMA reclaim is decisive — not a false breakout or a scratch at the moving average. The 50th-percentile CFTC gate ensures there is room for positioning to add — if leveraged funds are already fully long (above 50th percentile), the upside is reduced. The 26-week expiry causes the signal to age out naturally as market conditions evolve beyond the original recovery impulse.

---

#### Combo G: VXTS < 1.00, HY 4wk widen ≥ +30 bps, VIX ≤ 20

**Spec said / Implemented:** v3 integration note explicitly states all three thresholds. Earlier specs were less precise on the HY widening delta (some versions said "HY rising" without specifying bps). v3 clarified +30 bps as the threshold. Implemented exactly as v3 spec'd, including computing the HY 4-week change in bps from the raw OAS series (not just level).

The HY +30 bps/4wk threshold: 30 bps widening in one month is a meaningful credit deterioration signal (not noise). VXTS < 1.00 = backwardation, confirming near-term stress. VIX ≤ 20 = equity volatility hasn't panicked yet. The combination describes a state where credit markets are quietly deteriorating while equity vol remains suppressed — credit is *leading* equities. This is the setup before a full Combo B-style capitulation event.

---

### 6.3 SSI thresholds (SSI_CONFIG.yaml)

The SSI Open Questions document (`SSI_OpenQuestions_DivyanshuTestList.docx`) explicitly stated that most starting thresholds were **judgment-based, not backtested**. Before go-live, 16 experiments were defined to validate or reject each one. The validation run executed on 2026-06-04 covers 2015–2026 data. Full evidence is in `docs/ssi_validation/SSI_THRESHOLD_JUSTIFICATION.md` and numbered reports `01`–`14` in the same folder.

The table below summarises every threshold: what the spec originally suggested, what the experiments found, and the final production decision.

| Parameter | Spec / starting point | Experiment run | Finding | Final decision |
|---|---|---|---|---|
| Long gate (primary) | Percentile ≤ 20 | Test 1 | n=16, 81% win @ 3m, avg +4.1% | ✅ APPROVED — kept at 20 |
| Long gate (secondary) | Level ≤ −0.6 (symmetric) | Test 1 | n=0 fires (composite never reaches −0.6) | ✅ Kept as harmless backup; never primary |
| Short gate (primary) | Percentile ≥ 85 | Test 2 | n=7, 1w down 57%, but 3m SPX still +2.7% | ✅ APPROVED — compromise; 90 is alternative |
| Short gate (secondary) | Level ≥ +0.6 (original) | Test 2 | n=57, 3m SPX +5.7%, win rate 3.5% — shorts lose | ❌ REJECTED; replaced with ≥ 0.85 |
| Short level replacement | Level ≥ 0.85 | Test 2 | n=30, 3m avg less bad than 0.6 | ✅ APPROVED — replaces rejected 0.6 |
| Z-score clip | 3.0 | Test 9 | Percentile composite shown as future option | ✅ Z-score kept in production |
| History window | 5 years | Tests 1–2 | Consistent with "5y percentile" spec language | ✅ APPROVED (design) |
| Composite weights | 30/25/25/20 | Not swept | Design choice from spec — no dedicated weight study | ✅ APPROVED (design) |
| Layer 2 min votes | 2 of 4 | Test 10 | Vote count sweep did not change long-gate set in sample | ✅ APPROVED (design) |
| Layer 2 multipliers | 1.2 / 1.0 / 0.8 | Test 11 | Oct 2022 vix_bypass verified; full equity curve not run (waived) | ✅ APPROVED (design) |
| HYG/LQD vote | Percentile 70 / 30 | Test 8 | 4w drop <−1.5%: n=70 eps, median 3d to VIX>25 | ✅ APPROVED (design) |
| DBMF beta vote | 0.5 low / 1.2 high | Test 7 | Research threshold −0.10 (different scale); bands directionally consistent | ✅ APPROVED (design) |
| CNN F&G vote | ≤ 25 fear / ≥ 75 greed | Test 6 | Fear <20: n=3, longer horizons SPX positive. Greed >80: 0 crossings | ✅ APPROVED (design) — greed shorts need more data |
| VIX ratio vote | ≥ 1.05 stress / ≤ 0.95 calm | Test 11 | Same as composite; 1.05 is more sensitive than macro's 1.10 Combo D gate | ✅ APPROVED (design) |

---

#### Part A — Composite construction

**History window: 5 years (`history_years: 5`)**

The Open Questions spec anchored the design on "approximately 20th percentile of the 5-year distribution." Five years was chosen because it spans at least one full market cycle (COVID 2020, rate hike 2022, recovery 2023–2026) without going so far back that pre-QE regimes dominate the distribution. The `build_ssi_history_frame()` function uses this window consistently for both the daily composite level and the percentile gate calculations.

**Z-score clip: 3.0 (`zscore_clip: 3.0`)**

Each input (HYG/LQD ratio, DBMF beta, CNN Fear & Greed, VIX ratio) is first converted to a z-score (how many standard deviations above/below its rolling mean), then clipped at ±3 before weighting. The clip prevents a single extreme observation — like a COVID-style VIX spike — from pushing the composite to a value that dominates and masks the other inputs.

**What the spec originally asked:** Test 9 asked whether switching the entire composite from z-scores to percentile ranks (3-year rolling window) would be more robust during crises. Percentile ranks are less sensitive to fat-tailed distributions because they don't assume normality.

**What the experiment found:** The percentile composite was built in parallel and compared against the z-score composite during Feb–Apr 2020 and Sep–Dec 2022. Both versions produced similar signals at the key turning points, with the percentile version showing marginally better crisis-period sensitivity. However, no statistically significant improvement justified overriding the existing production system.

**Decision: Z-score clip kept at 3.0.** The percentile composite remains an experimental variant. Switching requires Rohit sign-off on `SIGNOFF.md` because it would change the absolute level of every day's SSI score and potentially invalidate historical level comparisons.

**Composite weights: HYG/LQD 30%, DBMF 25%, CNN 25%, VIX ratio 20%**

No dedicated weight sweep was run — weights were set by the spec's design intent and confirmed as `APPROVED (design)`.

| Input | Weight | Why this weight | Overlap note |
|---|---|---|---|
| HYG/LQD | 30% | Credit market leads equity stress; longest reliable history; spec treats HY widening as primary risk-off signal | Uses ETF ratio (not FRED OAS) — no overlap with Runic HY variable |
| DBMF beta | 25% | Systematic macro funds (CTAs) represent large position flows; 21-day beta vs SPY captures positioning shift | Not in Runic |
| CNN Fear & Greed | 25% | Fast-moving retail/survey sentiment; captures the "narrative fear" that precedes or follows credit moves | Not in Runic |
| VIX ratio | 20% | Flags vol term structure stress — the same dynamic that Runic VXTS watches | Slightly overlaps VXTS; deliberately underweighted to avoid double-counting |

Changing these weights would require a dedicated equity-curve study (out of scope for the Open Questions validation track). They are the production baseline until that study is run.

**Internal composite mapping (code constants, not YAML):**

The composite uses these internal conversion rules before weighting — they are slightly wider than the Layer 2 vote thresholds to allow the composite to react before a vote-crossing occurs:

| Input | Converts to ~−0.8 (risk-off) when | Converts to ~+0.8 (risk-on) when |
|---|---|---|
| CNN F&G | ≤ 25 (fear zone) | ≥ 75 (greed zone) |
| VIX ratio | ≥ 1.05 (mild backwardation) | ≤ 0.95 (contango / calm) |

---

#### Part B — Long and short entry gates

**Long gate — primary: `long_entry_pctile: 20`**

**Spec said:** "Approximately 20th percentile of the 5-year SSI distribution" — this exact language was in the Open Questions document as the intended long entry design.

**Test 1 results (2015–2026):**

| Percentile threshold | n events | 3m win % | Avg 3m SPX | Worst 3m |
|---|---|---|---|---|
| ≤ 10 | 5 | Very high | Very strong | — |
| **≤ 20** | **16** | **81%** | **+4.1%** | **−0.34%** |
| ≤ 25 | 19 | Lower | Lower avg | — |

The sweep clearly favoured ≤10 on average 3-month return, but with only 5 historical fires that level is too sample-sensitive to trust for production. ≤20 provides 16 events — enough to be statistically meaningful — with a strong edge (81% win, almost no downside in worst case).

**Decision: Kept at percentile ≤ 20.** This is the primary long gate.

---

**Long gate — secondary: `long_entry: −0.6`**

**Spec said:** The original symmetric spec had `long_entry: −0.6` paired with `short_entry: +0.6`. This was the starting point before any validation.

**Test 1 results:** n = 0 fires. The composite SSI score rarely reaches −0.6 in normal market conditions. The z-score composite with a clip of 3.0 and the chosen weights produces a daily level that typically ranges between about −0.5 and +0.5, reaching the extremes only in severe crises.

**Decision: Kept as a harmless secondary backup.** If the composite ever breaches −0.6, the long signal fires regardless of percentile. In practice this is a safety net for extreme crisis periods not well-represented in the 2015–2026 training window. It does not drive any of the validation statistics.

---

**Short gate — primary: `short_entry_pctile: 85`**

**Spec said:** The original spec implied symmetric ±0.6 and did not specify a separate percentile threshold for shorts. The Open Questions document (Part 1.1) explicitly flagged this: *"Tops are not symmetric to bottoms. +0.6 may fire too early."*

**Test 2 results — why +0.6 was rejected:**

| Level threshold | n events | 3m avg SPX | 3m win for short | Conclusion |
|---|---|---|---|---|
| ≥ 0.6 | 57 | +5.7% | **3.5%** | SPX keeps rising — short loses money |
| ≥ 0.85 | 30 | Lower but still positive | Moderate | Less bad, still bullish bias |
| ≥ 0.90 | 23 | Lower avg | Better short-term | Stricter |

**Test 2 results — percentile thresholds:**

| Percentile threshold | n events | 1w SPX down % | 3m avg SPX | Conclusion |
|---|---|---|---|---|
| ≥ 85 | 7 | **57%** | +2.7% | Short-term fade works; 3m still positive |
| ≥ 90 | 5 | Better 1w fade | Slightly better | Fewer fires, similar story |

The structural bull bias in the 2015–2026 sample means no percentile threshold produces a clean 3-month short signal — markets often keep grinding higher even after extreme greed readings. The 85th percentile does produce a consistent **short-term fade** (57% of the time SPX is lower 1 week later), which is the best that can be achieved with this data window.

**Decision: Kept at percentile ≥ 85.** This is a compromise between frequency (more fires than ≥90) and extremity (more selective than ≥80). Rohit may prefer ≥90 for a stricter short gate — that is the noted alternative.

---

**Short gate — secondary level: `short_entry: 0.85` (replaced the rejected 0.6)**

**Original spec:** `short_entry: +0.6` (symmetric with long −0.6).

**Why rejected:** 57 historical fires, 3m average SPX **+5.7%**, win rate for the short position **3.5%**. A rule that fires short when the market still goes up 96% of the time over 3 months is actively harmful.

**Replacement:** Level ≥ 0.85 — n=30, 3m average still positive but substantially lower than 0.6. Level ≥ 0.90 — n=23, stricter. The 0.85 level was chosen as the asymmetric complement to the long's −0.6 (both are rare, both are secondary to the percentile primary).

**Status: REJECTED for +0.6. APPROVED for 0.85 as secondary.**

---

#### Part C — Layer 2 multiplier logic

**Multipliers: CONFIRMED 1.2, PARTIAL 1.0, UNCONFIRMED 0.8**

Layer 2 does not change the direction of the trade (long/short). It adjusts **size**: 20% larger when ≥2 of 4 sentiment inputs confirm the direction, 20% smaller when none confirm it.

**Spec said:** The addendum specified "CONFIRMED (≥2 of 4): ×1.20, PARTIAL (1 of 4): ×1.00, UNCONFIRMED (0 of 4): ×0.80."

**Test 11 (Oct 2022 / vix_bypass):** Confirmed that when Combo B is active, the `vix_bypass` flag overrides the 0.8 multiplier so the trading engine does not reduce size at a capitulation bottom. This was the specific design requirement. Full 20-year equity-curve study was not run — waived on the sign-off basis that the design intent and the key edge case (Oct 2022) both work correctly.

**Decision: 1.2/1.0/0.8 kept as round symmetric bands.** These will be the starting point for any future equity-curve optimization.

**min_confirmed: 2 of 4 votes**

**Test 10:** For the 16 long-gate days in the sample (SSI percentile ≤ 20), changing the "minimum votes for CONFIRMED" between 1 and 4 did not substantially change the historical set because on those extreme bearish days, multiple indicators tended to confirm simultaneously. The 2-of-4 rule from the spec was not improved upon by the sweep.

---

#### Part C — Layer 2 individual vote thresholds

| Input | Risk-off vote when | Risk-on vote when | Test run | What it showed | Decision |
|---|---|---|---|---|---|
| HYG/LQD ratio | percentile ≤ 30 | percentile ≥ 70 | Test 8 | 4w drop <−1.5%: n=70 eps, median 3d to VIX>25 | ✅ Kept — percentile of level (not % change) |
| DBMF beta | ≤ 0.5 | ≥ 1.2 | Test 7 | Research −0.10 threshold = n≈29; bands consistent directionally | ✅ Kept — may align to −0.10 research threshold in v2 |
| CNN Fear & Greed | ≤ 25 | ≥ 75 | Test 6 | Fear <20: n=3, SPX positive at longer horizons. Greed >80: 0 crossings | ✅ Fear kept; greed needs more CNN history |
| VIX ratio | ≥ 1.05 (stress) | ≤ 0.95 (calm) | Test 11 | Consistent with composite; 1.05 fires earlier than macro's 1.10 Combo D threshold | ✅ Kept at 1.05 (intentionally more sensitive) |

**HYG/LQD: 70th / 30th percentile**

The production vote compares today's HYG/LQD ratio (high-yield ETF ÷ investment-grade ETF) to its own 5-year percentile distribution. ≤30th percentile = credit stress (risk-off vote); ≥70th percentile = credit calm (risk-on vote).

Test 8 studied a different threshold concept — the 4-week % change in the ratio (−1.0%, −1.5%, −2.0%, −3.0%) and measured how many days it took for VIX to spike above 25 after each episode. The −1.5% threshold produced n=70 stress episodes with a median lead time of 3 days to VIX>25 — confirming that HYG/LQD deterioration is a leading indicator of volatility. This validated the **direction** of the vote logic; the actual Layer 2 implementation uses the percentile of the level (not % change) because it is self-normalising without requiring a separate lookback period.

**DBMF beta: ≤ 0.5 / ≥ 1.2**

DBMF is a managed-futures ETF. Its 21-day rolling beta vs SPY measures how much CTAs are positioned with or against equities. The Layer 2 vote uses absolute beta bands: ≤0.5 = subdued equity beta (CTAs not positioned long), ≥1.2 = elevated beta (CTAs strongly long).

Test 7 studied a different threshold: when the beta crosses below −0.10 (CTAs actually net short equities). n≈29 episodes; 2-week forward SPX was mixed depending on the entry date. The Test 7 threshold (−0.10) is at a different point on the beta scale than the Layer 2 bands (0.5/1.2), which are absolute levels rather than negative-beta crossings. The bands are a `APPROVED (design)` choice with the noted alternative of aligning to the −0.10 research threshold in a future Layer 2 revision.

**CNN Fear & Greed: ≤ 25 / ≥ 75**

The Layer 2 vote uses the same 25/75 levels as the composite's internal CNN mapping. Test 6 studied explicit crossings (CNN crossing below 20, below 10, above 80, above 90). The fear side (crossing below 20) produced only n=3 episodes in the CNN history slice, but when fear was extreme, longer-horizon SPX outcomes were consistently positive — confirming CNN fear as a contrarian buy-the-dip signal. The greed side (>80) produced zero crossings in the available CNN data, which means the greed short vote from CNN alone is currently undervalidated. This is why the CNN greed vote is rated `APPROVED (design)` with a noted caveat: greed shorts need more CNN cache history before the threshold can be tightened below 75.

**VIX ratio: ≥ 1.05 / ≤ 0.95**

The Layer 2 VIX ratio vote uses the same thresholds as the internal composite mapping (1.05 for stress, 0.95 for calm). These are intentionally more sensitive than the macro/Runic VXTS thresholds used in combo detection (1.10 for Combo D, 0.95 for Combo G). The rationale: SSI is a daily sizing tool that should react to vol term structure changes before they become combo-relevant — the combo fires are relatively rare events, while SSI adjusts size every day. Using 1.05 instead of 1.10 means the SSI Layer 2 starts flagging vol stress slightly earlier, giving the position-sizing engine a head-start on rising near-term vol.

---

## 7. 40 Hours — Time Breakdown

Here is an honest accounting of how the ~40 active development hours were spent across the project.

---

### Phase 1 — Architecture and spec reading (≈4 hours)

**What happened:** Reading three dense specification documents (PDF + two DOCX) carefully enough to turn them into code. Identifying the 12 variables, understanding the CFTC data structure, mapping the combo rules, and understanding how the C++ engine would consume the output.

**Difficulty:** The hardest part was that specs were written in product language ("fire when spreads widen significantly") that had to be translated into precise numeric rules. Many numbers were spread across different documents; v3 superseded v2 in several places.

**Output:** Architecture design, `CONFIG.yaml` structure drafted.

---

### Phase 2 — Data pipeline (≈7 hours)

**What happened:** Building `pull_all.py`, `fred_pull.py`, `yahoo_pull.py`, `cftc_pull.py`, `bls_pull.py`, `cape_scrape.py`. Getting all 12 series to download reliably and consistently.

---

#### Hard part 1: CFTC ZIP files — column names shift between years, multiple contracts cause double-counting

The CFTC publishes futures positioning in two separate archive formats:

| Archive | URL | Years covered | Inner file |
|---|---|---|---|
| Bulk historical | `fin_fut_txt_2006_2016.zip` | 2006–2016 | `F_TFF_2006_2016.txt` |
| Annual files | `fut_fin_txt_{year}.zip` | 2017–present | `FinFutYY.txt` |

**Problem 1 — Column names change across years.** The CFTC did not keep column names consistent when they reformatted the TFF file layout. The same data field appears under at least two different names depending on the year:

| Logical field | Pre-2017 column name | 2017+ column name |
|---|---|---|
| Market name | `Market and Exchange Names` | `Market_and_Exchange_Names` |
| Trader type | `Traders Classification` / `Trader Classification` / `Traders-Classification` | `Traders_Classification` |
| Report date | `As of Date in Form YYYY-MM-DD` / `Report_Date` | `Report_Date_as_YYYY-MM-DD` |
| FM longs | `Lev Money Positions-Long-All` | `Lev_Money_Positions_Long_All` |
| FM shorts | `Lev Money Positions-Short-All` | `Lev_Money_Positions_Short_All` |
| RM longs | `Asset Mgr Positions-Long-All` | `Asset_Mgr_Positions_Long_All` |
| RM shorts | `Asset Mgr Positions-Short-All` | `Asset_Mgr_Positions_Short_All` |

The fix was a `_find_col()` helper that tries every known alias for a given field, checking for both exact match and substring match:

```python
def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for cand in candidates:
        for col in df.columns:
            if col.strip() == cand or cand.lower() in col.lower():
                return col
    return None
```

Every column lookup (`market_col`, `cat_col`, `long_col`, `short_col`, `date_col`) goes through this helper so the parser works on both old and new file formats without branching.

**Problem 2 — Multiple S&P 500 contracts cause bogus net positions if summed.** Inside the TFF file there are several rows that all contain "S&P 500" in the market name:

- `S&P 500 Stock Index - CHICAGO MERCANTILE EXCHANGE`
- `S&P 500 E-MINI - CHICAGO MERCANTILE EXCHANGE`
- `S&P 500 MICRO - CHICAGO MERCANTILE EXCHANGE`
- `S&P 500 CONSOLIDATED - CHICAGO MERCANTILE EXCHANGE`
- `S&P 500 DIVIDEND FUTURES`

If you naively filter `market_name.contains("S&P 500")` and sum all rows, you get a net position that is wildly wrong — sometimes −760,000+ contracts — because the E-MINI, MICRO, and CONSOLIDATED rows partially overlap each other (the Consolidated row is a synthetic row that already aggregates across contract sizes).

The fix was a two-stage `_market_mask()` function:

1. **Prefer the Consolidated row** — look for `"S&P 500 Consolidated"` first. If that row exists, use only that one row.
2. **If no Consolidated row exists** (some older file years omit it) — fall back to a broad `"S&P 500"` match, but **exclude** the E-MINI, MICRO, DIVIDEND, and ADJUSTED INT RATE contracts with a regex pattern `"E-MINI|MICRO|DIVIDEND|ADJUSTED INT RATE"`.

This ensures one clean row per date, never a double-counted sum.

**Problem 3 — The parser needs to handle both FM and RM from the same underlying file without re-downloading.** The bulk zip is ~80 MB and the annual zips are 5–20 MB each. Downloading twice would have been slow and brittle. The fix was a module-level `_TFF_RAW_CACHE` variable: the first call to `_download_frames()` loads all zips into memory as a single concatenated DataFrame; subsequent calls return the cached copy. `fetch_cftc_fast_money_net()` and `fetch_cftc_asset_manager_net()` both call `_download_frames()` and get the same object — one download, two parses.

---

#### Hard part 2: CPI surprise — three-layer fallback chain for actual + consensus

CPI surprise = actual MoM print minus economist consensus. Getting both sides required three separate data sources chained together:

**Layer 1 — BLS API v2 (actual).**
The BLS API (`https://api.bls.gov/publicAPI/v2/timeseries/data/`) returns the actual CPI level for series `CUSR0000SA0`. The function `fetch_bls_latest_mom_pct()` posts to this endpoint with a `registrationkey` (from `BLS_API_KEY` env variable) and computes MoM % from the two most recent data points:

```python
mom = (latest / prior - 1.0) * 100.0
```

If `BLS_API_KEY` is not set, the function returns `None` and the chain falls through.

**Layer 2 — FRED proxy for actual (if BLS unavailable for 2+ days).**
`try_fred_cpi_fallback_if_stale()` checks `data_pull_log` for the last successful BLS pull. If it was more than 2 calendar days ago, it falls back to `FRED:CPIAUCSL` and computes MoM from the two most recent monthly observations. This is stored as `source="FRED_PROXY"` — flagged so analysts know it is not the BLS official release number.

**Layer 3 — Consensus from Investing.com (scraped).**
Consensus is not available from BLS or FRED — it requires scraping a third-party source. The scraper in `investing_cpi_consensus.py` POSTs to Investing.com's internal filtered calendar API:

```
POST https://www.investing.com/economic-calendar/Service/getCalendarFilteredData
data: { country[]: 5, timeZone: 55, currentTab: "thisWeek" | "lastWeek", ... }
```

The response is a JSON object whose `"data"` key contains raw HTML for the calendar table. The scraper parses this with BeautifulSoup, locating rows where the event name matches any of:

```python
_CPI_PATTERNS = (
    r"cpi\s*\(?\s*mom",
    r"consumer price index\s*\(?\s*mom",
    r"core cpi\s*\(?\s*mom",
)
```

**The fragile part:** Investing.com changes its HTML structure periodically. The column cells use CSS class names like `"act"`, `"fore"`, `"prev"` for actual, forecast, and previous — but these class names are applied inconsistently across different table rows. The scraper uses `class_=lambda c: c and "act" in str(c)` pattern matching instead of fixed class names. Additionally, the date comes from two possible places: a `data-event-datetime` attribute on the `<tr>` tag (newer layout), or a preceding `<td class="theDay">` row (older layout). Both paths are handled. If neither works, the row is skipped.

If Investing.com scraping fails entirely (403, connection error, HTML structure change), the system falls back to a manually maintained `cpi_consensus.csv` file which operators update before each CPI release week. The `CPI_CONSENSUS_CSV` env variable points to this file.

All three sources funnel into the `pending_releases` SQLite table via `ingest_cpi_release(date, actual, consensus, source)`. The `load_cpi_surprise_series()` function then reads this table and returns the `surprise_pp = actual − consensus` series for use in Combo C detection.

---

#### Hard part 3: CAPE scraping from multpl.com — HTML table parsing with no API

CAPE (Shiller P/E) is not available from FRED or any financial API. The only free source is [multpl.com/shiller-pe/table/by-month](https://www.multpl.com/shiller-pe/table/by-month), which publishes a monthly HTML table.

The scraper (`cape_scrape.py`) uses `requests` + `BeautifulSoup`:

```python
soup = BeautifulSoup(resp.text, "lxml")
table = soup.find("table")
for tr in table.find_all("tr")[1:]:
    cells = [td.get_text(strip=True) for td in tr.find_all("td")]
    date_str, val_str = cells[0], cells[1]
    val = re.sub(r"[^\d.]", "", val_str)   # strip trailing asterisks, % signs
    rows.append({"date": pd.to_datetime(date_str), "cape": float(val)})
```

**The fragile part:** The value cells on `multpl.com` sometimes include footnote markers (`*`, `†`) or are formatted as `"37.52*"` where the asterisk indicates an estimated value. A naive `float()` conversion raises `ValueError`. The `re.sub(r"[^\d.]", "", val_str)` strip removes all non-digit, non-decimal characters before the conversion, making the parse robust to formatting noise.

A second problem: `multpl.com` blocks repeated scraper requests without browser-like headers. The scraper uses `BROWSER_HEADERS` (a shared constant in `scraper_utils.py` that mimics a Chrome user-agent with realistic `Accept-Language` and `Accept-Encoding` headers).

The first successful scrape writes the result to `macro_intelligence/data/cape_history.csv`. On subsequent runs, `load_cape_series()` checks if this local cache exists first — if it does, it skips the HTTP call entirely. This means a single successful scrape is enough for the rest of the production run. If both the scrape and the cache fail, `_fallback_cape()` returns an empty Series rather than crashing the pipeline.

---

#### Hard part 4: CNH fallback — Yahoo Finance returning a single stale bar

Yahoo Finance's `USDCNH=X` (USD/Chinese Yuan offshore) ticker is unreliable in a specific way: it does not return a 404 or error — it returns a DataFrame with a single row that reflects a stale price from days or weeks ago. This looks like valid data from the outside.

The initial code simply called `fetch_yahoo_close("USDCNH=X", "2010-01-01")` and trusted the result. The bug was subtle — the 4-week change calculation `calendar_pct_change(cnh, 28)` would produce a series with only one value (today vs 28 days ago, where both were the same stale price), giving a 0% change. This would silently suppress any CNH signal.

The fix was a length-based guard in `pull_all.py`:

```python
cnh = fetch_yahoo_close("USDCNH=X", "2010-01-01")
if len(cnh) < 100:
    # Yahoo often returns a single stale USDCNH=X bar; FRED DEXCHUS is the fallback.
    cnh = fetch_fred_series("DEXCHUS", "2010-01-01")
```

`FRED:DEXCHUS` (China/U.S. Foreign Exchange Rate) is the FRED equivalent of USD/CNH, going back to 2010. It is updated with a short lag but is far more reliable for bulk historical data. 100 bars was chosen as the threshold because any legitimate pull of USDCNH=X from 2010 to present should return 3,000+ bars — anything below 100 is definitionally stale or broken.

The same pattern was applied to WTI (`CL=F`): if Yahoo returns <100 bars, fall back to `FRED:DCOILWTICO`. This is the spec-specified fallback and was added in a subsequent fix after the data source audit.

---

#### Hard part 5: 28 calendar-day change — trading day count is wrong near thresholds

The original code in `yahoo_pull.py` used a standard pandas `pct_change` with a rolling lookback in trading bars:

```python
def rolling_pct_change(series: pd.Series, periods: int = 20) -> pd.Series:
    s = series.sort_index()
    return ((s / s.shift(periods)) - 1) * 100
```

`series.shift(20)` on daily data goes back 20 trading days. The problem: 20 trading days is approximately 4 calendar weeks, but the count varies because of weekends and holidays. In a holiday-heavy week (e.g. Thanksgiving week), `shift(20)` might look back 29 or 30 calendar days. In a normal week, it might be only 26–27 calendar days.

The v3 spec explicitly states the formula as "28 calendar days ago" — a precise date, not a bar count. Near Combo C's ±10% WTI threshold, a difference of 2–3 calendar days in the lookback window can be the difference between the combo firing and not firing. For example, if WTI spiked sharply 26 days ago, `shift(20)` would include that spike in the calculation, but `calendar_pct_change(28)` would not.

The new function:

```python
def calendar_pct_change(series: pd.Series, calendar_days: int = 28) -> pd.Series:
    """v3 ROC: percent change vs value N calendar days ago (not trading bars)."""
    s = series.sort_index()
    prior = s.reindex(s.index - pd.Timedelta(days=calendar_days), method="ffill")
    prior.index = s.index
    return ((s / prior) - 1) * 100
```

How it works:
1. For every date `d` in the index, compute `d − 28 days` (exact calendar subtraction using `pd.Timedelta`).
2. Use `.reindex(..., method="ffill")` to find the last available price on or before that exact date — because markets are closed on weekends, `method="ffill"` picks the prior Friday's close if the exact date falls on a weekend.
3. Re-attach the original index so the result aligns with today's dates.
4. Compute `(today / 28_days_ago − 1) × 100`.

This change was applied to all three variables that use 4-week ROC: `WTI`, `CNH`, and `GSR`. The `rolling_pct_change()` function was kept in place but is no longer used in the main pipeline — it is retained only for reference and internal testing.

---

### Phase 3 — Engine (percentiles, combos, dominant) (≈8 hours)

**What happened:** Building `percentiles.py`, `combo_detector.py` (the full A–G logic), `dominant.py`, `persistence.py`, `vix_bypass.py`.

**Hard parts:**
- **Combo A direction vote:** BRAVE/FEARFUL/CONTESTED logic required counting which direction each variable's fire implied
- **Combo F lifecycle:** 26-week expiry + 50-WMA invalidation + validation date 2020-06-08 (not 2020-06-29 as in an older email) + `_combo_f_weeks()` counter
- **Combo G HY widen:** The spec said "HY widen 30bps" but HY is stored as a level, not a recent change — had to compute `_hy_4wk_change_bps()` from raw OAS series
- **Combo C cancel:** 4 consecutive Fridays condition needed state tracking across runs (stored in DB)
- **Generic combos (298):** Had to implement `detect_all_combos()` iterating over all variable combinations without becoming too slow
- **Prefilter:** Only surface generics with ≥3 historical fires AND ≥60% hit rate — needed `prefilter.py` with DB queries

---

### Phase 4 — Database and backfill (≈5 hours)

**What happened:** Schema design, `connection.py`, building the backfill scripts, running backfill for 1,050 Fridays (2006–2026).

**Hard parts:**
- **Backfill hung** for ~5 hours on forward returns because of slow per-row NYSE calendar lookups. Fixed by building a **cached NYSE sessions index** (`_nyse_sessions()`) with binary search, reducing total time from ~5h to ~13 minutes.
- Forward returns: needed to compute SPX performance at 1w/2w/1m/3m/6m after each of the 15,072 combo fires — zero NULL gaps required in the final DB.
- Schema migrations: v3 added several new columns to `combo_fires` and `daily_readings` that needed incremental migration.

---

### Phase 5 — Claude AI integration (≈4 hours)

**What happened:** Building the regime classifier and narrative briefing using Anthropic's Claude API; Tavily news integration; heuristic fallbacks when API keys absent.

**Hard parts:**
- Structured JSON output from Claude (regime must return specific field names)
- Prompt engineering for the 150-token regime label and 500-token narrative
- Heuristic fallback (`_heuristic_regime`, `_heuristic_geo`) that works offline in CI/tests without real API access
- Briefing renderer: converting the raw JSON into BTIG-style HTML

---

### Phase 6 — SSI (Sentiment SuperIndex) (≈7 hours)

**What happened:** Building the entire SSI layer from scratch — 10 data series across 8 separate pullers, composite scoring engine, Layer 2 vote logic, `positioning.json` writer, `ssi.db`, and the daily 08:00 ET job.

---

#### SSI data sources — spec vs implementation audit

`DATA_SOURCES.yaml` defines 12 SSI variables (IDs 13–24, system = `ssi_layer1 / ssi_layer2 / ssi_layer3`), plus variable 7 (VXTS, `system: "macro+ssi"`) shared with Runic. The table below compares each spec entry against what is actually implemented.

**Key distinction — composite inputs vs. loaded-but-not-weighted:**
`SSI_CONFIG.yaml` defines weights for only 4 series: `hyg_lqd` (30%), `dbmf_beta` (25%), `cnn_fg` (25%), `vix_ratio` (20%). The remaining 6 series loaded by `pull_all.py` — AAII, NAAIM, pct_above_200dma, McClellan, SKEW, nh_nl_ratio — are loaded for validation analyses (the 15-test validation suite) but do **not** feed into the live composite score. The open questions spec lists four inputs by name; that is what was coded into the weights.

| Spec ID | Variable | Spec source / ticker | Spec layer | Implemented in | Actual source / ticker | Lookback: spec → code | In composite? | Match status |
|---------|----------|---------------------|------------|----------------|------------------------|------------------------|---------------|--------------|
| 7 | VXTS (vix_ratio) | Yahoo `^VIX3M ÷ ^VIX` | macro+ssi shared | `yahoo_inputs.vix_ratio_series()` | Yahoo `^VIX3M ÷ ^VIX` | 2007-01-01 → 2007-01-01 | ✅ Yes (20%) | ⚠️ Spec says one shared pull with Runic; code has two independent pulls (same tickers, different objects) |
| 13 | AAII | `aaii.com/files/surveys/sentiment.xls` (XLS download) | ssi_layer1 | `aaii_pull.fetch_aaii_spread()` | HTML scrape primary → XLS secondary → manual CSV | weekly | No (not in weights) | ⚠️ Pull method enhanced: spec says `requests_xls` direct download; XLS is 403'd on AWS, so HTML scrape of `sent_results` page added as primary path. URL matches. |
| 14 | NAAIM | `naaim.org` scrape or manual | ssi_layer1 | `naaim_pull.fetch_naaim_exposure()` | HTML table scrape of `naaim.org/programs/naaim-exposure-index/` + CSV cache | weekly | No | ✅ Match (both paths in spec) |
| 15 | CNN F&G | CNN scrape | ssi_layer1 | `cnn_fear_greed.load_cnn_series()` | CNN graphdata JSON API `production.dataviz.cnn.io/index/fearandgreed/graphdata` + CSV cache | daily | ✅ Yes (25%) | ✅ Match |
| 16 | PCT_ABOVE_200DMA | computed from spx_constituents_ma200 | ssi_layer1 | `pct_200dma_pull.fetch_pct_above_200dma()` + `sp500_breadth.py` | 500-constituent yfinance download, MA200 computed in-process | daily EOD | No | ✅ Match |
| 17 | MCCLELLAN | computed from `nyse_adv_decl` | ssi_layer2 | `mcclellan_pull.fetch_mcclellan_oscillator()` + `sp500_breadth.py` | **S&P 500** advance/decline, not NYSE | daily EOD | No | ⚠️ Discrepancy: spec says NYSE advance/decline; code uses S&P 500 universe. NYSE data requires a paid provider; S&P 500 universe is computable from yfinance at no cost. McClellan formula is identical — only the universe differs. |
| 18 | NH_NL_RATIO | Yahoo `^NAHGH ÷ ^NALOW`, fallback: stockcharts | ssi_layer2 | `nh_nl_pull.fetch_nh_nl_ratio()` + `sp500_breadth.py` | S&P 500 52-week high/low flags from same breadth frame | daily EOD | No | ⚠️ Discrepancy: spec says Yahoo tickers `^NAHGH`/`^NALOW` (NYSE new highs/lows). Yahoo rarely serves these tickers reliably. Code uses the in-process S&P 500 breadth computation — same concept, different universe (S&P 500 vs NYSE). |
| 19 | HYG_LQD | Yahoo `HYG ÷ LQD`, lookback 2007-01-01 | ssi_layer2 | `yahoo_inputs.hyg_lqd_ratio()` | Yahoo `HYG ÷ LQD` | 2007-01-01 → **2010-01-01** | ✅ Yes (30%) | ⚠️ Minor: lookback starts 3 years later than spec. Immaterial for live scoring (rolling 5-year window) but reduces validation history slightly. |
| 20 | SKEW | Yahoo `^SKEW`, lookback 1990-01-01 | ssi_layer2 | `skew_pull.fetch_skew()` | Yahoo `^SKEW` | 1990-01-01 → 1990-01-01 | No | ✅ Exact match |
| 21 | CFTC_FM | CFTC TFF, shared with var 8 | ssi_layer3 | `cftc_ssi.cftc_layer3_snapshot()` | Shared CFTC pull (FM columns) | rolling 3y | No (Layer 3 / dashboard) | ✅ Match |
| 22 | CFTC_RM | CFTC TFF, shared with var 8, dashboard only | ssi_layer3 | `cftc_ssi.cftc_layer3_snapshot()` | Shared CFTC pull (RM columns) | rolling 3y | No (dashboard only) | ✅ Match |
| 23 | GROSS_NET_DIV | derived from FM/RM | ssi_layer3 | `cftc_ssi.cftc_layer3_snapshot()` | FM_net − RM_net derived in-process | derived | No | ✅ Match |
| 24 | DBMF beta | Yahoo `DBMF + SPY`, 21d rolling beta, lookback 2015-01-01 | ssi_layer3 | `yahoo_inputs.dbmf_beta_vs_spy()` | Yahoo `DBMF + SPY`, 21-day rolling cov/var | 2015-01-01 → 2015-01-01 | ✅ Yes (25%) | ✅ Exact match |

**Summary of discrepancies:**

| # | Variable | Discrepancy | Severity | Impact |
|---|----------|-------------|----------|--------|
| 1 | VXTS / vix_ratio | Two independent Yahoo pulls instead of one shared pull | Low | Zero: same tickers, same result. Wasted one HTTP call. |
| 2 | AAII | HTML scrape added as primary; XLS is fallback (not primary as spec says) | Low | Positive: more reliable on AWS. URL matches spec. |
| 3 | McClellan | S&P 500 universe instead of NYSE universe | Medium | Moderate: S&P 500 advance/decline is a subset of NYSE. McClellan reading will differ from NYSE-based versions published by data vendors. Does not affect composite (not in weights). |
| 4 | NH/NL ratio | S&P 500 52-week highs/lows instead of Yahoo `^NAHGH`/`^NALOW` | Medium | Same as McClellan — different universe. Does not affect composite. |
| 5 | HYG_LQD lookback | 2010-01-01 vs spec 2007-01-01 | Low | 3 years less history for percentile baseline. No effect on live scoring. |

---

#### Hard part 1: The 8 data pullers — each one a different problem

The SSI `load_all_series()` in `src/sentiment_superindex/data/pull_all.py` assembles 10 series from 8 independent sources. Every single one had a different failure mode:

| Series | Source function | Website / API | What made it hard |
|--------|----------------|---------------|-------------------|
| `hyg_lqd` | `yahoo_inputs.hyg_lqd_ratio()` | Yahoo Finance (`yfinance`) — tickers `HYG`, `LQD` | Straightforward ratio pull. No special handling needed. |
| `dbmf_beta` | `yahoo_inputs.dbmf_beta_vs_spy()` | Yahoo Finance (`yfinance`) — tickers `DBMF`, `SPY` | Not a price series — a 21-day rolling regression beta (covariance ÷ variance) computed daily from return series |
| `cnn_fg` | `cnn_fear_greed.load_cnn_series()` | CNN internal JSON API: `https://production.dataviz.cnn.io/index/fearandgreed/graphdata` | Undocumented private endpoint; path has changed historically. Response is JSON with `fear_and_greed_historical` key containing timestamped score objects |
| `vix_ratio` | `yahoo_inputs.vix_ratio_series()` | Yahoo Finance (`yfinance`) — tickers `^VIX3M`, `^VIX` | Same tickers as Runic’s VXTS; SSI has its own independent pull. `^VIX3M` (93-day implied vol) divided by `^VIX` (30-day) |
| `aaii_spread` | `aaii_pull.fetch_aaii_spread()` | **Primary:** `https://www.aaii.com/sentimentsurvey/sent_results` (HTML scrape). **Fallback 1:** `https://www.aaii.com/files/surveys/sentiment.xls` (XLS download). **Fallback 2:** manually placed `aaii_sentiment.csv` | XLS URL returns HTTP 403 on AWS (AAII blocks datacenter IPs). Required adding HTML scrape of the public results page as the primary path |
| `naaim_exposure` | `naaim_pull.fetch_naaim_exposure()` | `https://www.naaim.org/programs/naaim-exposure-index/` (HTML table scrape) | Column name for the mean value varies across scrapes: `"NAAIM Number Mean/Average"`, `"NAAIM Number Mean Average"`, underscored variants. Fallback column finder needed |
| `pct_above_200dma` | `pct_200dma_pull.fetch_pct_above_200dma()` + `sp500_breadth.py` | Yahoo Finance (`yfinance`) — ~500 S&P 500 constituent tickers, downloaded in chunks of 40 | No external API provides this pre-computed. Must download all ~500 tickers, compute 200-day MA for each, count how many close above it per day |
| `mcclellan` | `mcclellan_pull.fetch_mcclellan_oscillator()` + `sp500_breadth.py` | Same yfinance bulk download (shares `_BREADTH_CACHE` with `pct_above_200dma` and `nh_nl_ratio`) | No API provides the McClellan oscillator. Must derive: EMA(19) − EMA(39) of **daily** net advances (see 2026-07-16 cumsum bug fix in Hard part 4) |
| `skew` | `skew_pull.fetch_skew()` | Yahoo Finance (`yfinance`) — ticker `^SKEW` (CBOE SKEW Index) | Straightforward single-ticker pull. CBOE publishes SKEW daily; Yahoo carries it reliably |
| `nh_nl_ratio` | `nh_nl_pull.fetch_nh_nl_ratio()` + `sp500_breadth.py` | Same yfinance bulk download (shares `_BREADTH_CACHE`) | Spec referenced Yahoo tickers `^NAHGH`/`^NALOW` (NYSE new highs/lows) which Yahoo serves unreliably. Used S&P 500 52-week high/low flags from the in-process breadth frame instead. Formula is `highs / (highs + lows)`, bounded 0–1 (see 2026-07-16 bug fix in Hard part 5) — an earlier version used `highs / lows` unbounded |

The key engineering constraint: all 10 series had to be loadable in one `load_all_series()` call, with caching so the daily job does not re-download on repeated calls, and with every individual pull silently degrading (returning an empty Series) rather than crashing the whole pipeline.

---

#### Hard part 2: AAII — XLS download blocked on AWS, two fallback paths required

AAII (American Association of Individual Investors) publishes a weekly bull/bear sentiment survey. The spec required the **bull minus bear spread** as an SSI input. AAII provides this as an XLS file at `https://www.aaii.com/files/surveys/sentiment.xls`.

**The AWS 403 problem:** On the production AWS server, any direct HTTP request to `aaii.com/files/surveys/sentiment.xls` returns HTTP 403 Forbidden. AAII actively blocks server/datacenter IP ranges. The same URL works fine from a laptop because it uses a residential IP.

This required a **three-path architecture**:

**Path 1 — HTML table scrape (preferred on AWS):**
The `_scrape_sent_results_table()` function scrapes `https://www.aaii.com/sentimentsurvey/sent_results` — the publicly visible HTML results page — instead of the locked XLS download URL. It parses the table with BeautifulSoup, looking for a `<table>` that has both "bullish" and "bearish" in its headers:

```python
for table in soup.find_all("table"):
    headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
    if "bullish" not in headers or "bearish" not in headers:
        continue
    # extract bull %, bear %, compute spread = bull - bear
```

The spread is extracted by finding the column index of "bullish" and "bearish" in the header, then iterating rows.

**Path 2 — Cached XLS (from prior laptop download):**
If a `aaii_sentiment.xls` file already exists in the local data cache (put there by a developer laptop), the `_load_xls()` path parses it with `pandas.read_excel()`. The `_parse_aaii_frame()` function is column-name agnostic — it looks for any column with "bull" or "bear" in its name, or a pre-computed "spread" column, to handle AAII's inconsistent XLS column layout.

**Path 3 — Manual CSV ingest:**
For production environments where neither path works reliably, `scripts/ingest_aaii_sentiment.py` accepts a manually downloaded CSV and calls `ingest_aaii_csv()` to merge it into the persistent cache at `aaii_sentiment.csv`. This is the production fallback. The validation suite (Test 16) flags this as a `WARN` if the cached data is more than 8 days old.

All three paths merge into a single `merge_series(cached, live)` call that fills the most recent date from whichever source has it.

---

#### Hard part 3: NAAIM — column names change between scrape runs

NAAIM (National Association of Active Investment Managers) publishes a weekly exposure index showing how much active managers are long equities (0–200 scale, where 100 = fully invested, 200 = 2× leveraged long). The scraper hits `https://www.naaim.org/programs/naaim-exposure-index/` and parses the HTML table.

**The problem:** The column name for the NAAIM mean value varies:
- Older page versions: `"NAAIM Number Mean/Average"`
- Newer page versions: `"NAAIM Number Mean Average"` (no slash)
- Some variants: `"Naaim_Number_Mean_Average"` (underscored)

The `parse_html_table_dates()` utility (in `scraper_utils.py`) takes a list of candidate `value_cols` and tries each one. The `_scrape_naaim()` function provides both:

```python
df = parse_html_table_dates(
    resp.text,
    value_cols=["naaim_number_mean/average", "naaim_number_mean_average"],
)
col = next((c for c in df.columns if "naaim" in c.lower() and "mean" in c.lower()), None)
```

The fallback column finder (`"naaim" in c.lower() and "mean" in c.lower()`) catches any future naming variation without requiring a code change.

---

#### Hard part 4: McClellan oscillator — has to be computed, not downloaded

The McClellan oscillator is a market breadth momentum indicator. It measures whether advancing stocks are accelerating or decelerating relative to declining stocks. No free API provides it as a pre-computed series — it must be built from raw breadth data.

**Formula:**
1. Compute daily `net_advances = advancers − decliners` for the S&P 500 universe.
2. Compute `EMA(19)` and `EMA(39)` **directly on the daily `net_advances` series** (no cumulative sum).
3. McClellan oscillator = `EMA(19) − EMA(39)`.

```python
def _classic_mcclellan(net_advances: pd.Series) -> pd.Series:
    net = net_advances.fillna(0)
    ema19 = net.ewm(span=19, adjust=False).mean()
    ema39 = net.ewm(span=39, adjust=False).mean()
    return (ema19 - ema39).dropna()
```

**2026-07-16 bug fix:** an earlier version of this function ran the EMAs on `net_advances.cumsum()` (the cumulative advance-decline line) instead of the daily series. That inflates the oscillator far outside its normal ±150 band — it produced **217.10** on 2026-07-16 (matching the dashboard's raw float `217.09514599086106`) against a correct value of **+12.16** for the same date. The classic McClellan formula EMAs the *daily* net-advances series, not its cumulative sum; a separate "Summation Index" (cumulative sum of the oscillator itself, not used here) is the indicator that legitimately operates on a running total. Fixed by dropping `.cumsum()`; `mcclellan_oscillator.csv` was rebuilt from scratch and `positioning.json` / API responses now round the display value to 2 decimals via `_round_display()` in `positioning.py`.

The input `net_advances` comes from `sp500_breadth.series_from_breadth("net_advances")` — which triggers the full S&P 500 breadth computation (see Hard part 5 below). The `mcclellan_oscillator.csv` cache means this full computation only runs once per day.

---

#### Hard part 5: % above 200DMA and breadth — downloading 500+ tickers in chunks

Both `pct_above_200dma` and `mcclellan` ultimately depend on `sp500_breadth.py`, which computes per-day breadth statistics across the full S&P 500 universe. This was the most computationally expensive component.

**The approach:** `sp500_universe.load_sp500_tickers()` returns the current ~500 S&P 500 ticker list (from Wikipedia or a cached snapshot). `_download_closes()` downloads all ~500 tickers from Yahoo Finance in **chunks of 40** to avoid hitting Yahoo's rate limits:

```python
for i in range(0, len(tickers), CHUNK_SIZE):   # CHUNK_SIZE = 40
    chunk = tickers[i : i + CHUNK_SIZE]
    data = yf.download(chunk, period="2y", interval="1d", threads=True, ...)
```

Each chunk returns a MultiIndex DataFrame (`price level × ticker`). The code extracts the `"Close"` level: `close = data["Close"]`.

Then for every qualifying symbol (those with ≥220 days of history), `compute_daily_breadth_stats()` computes in one vectorised pass:
- `pct_above_200dma`: `(close > close.rolling(200).mean()).sum() / count`
- `new_highs` / `new_lows`: 52-week high/low flags
- `advancers` / `decliners`: daily up/down flags for the McClellan net_advances input
- `nh_nl_ratio`: `new_highs / (new_highs + new_lows)`, bounded 0–1, `NaN` when both are 0

**2026-07-16 bug fix:** an earlier version computed `nh_nl_ratio = new_highs / new_lows` — a straight highs-over-lows ratio with no upper bound. When lows are small (e.g. 46 highs vs 1 low on 2026-07-16), that ratio blows up to **46.0** and reads like a raw high-count instead of a ratio. The correct formula, matching the spec's intent, is `highs / (highs + lows)`, which stays bounded in **[0, 1]** — the same date now correctly reads **0.979** (97.9% of highs+lows activity was new highs). Fixed in `compute_daily_breadth_stats()`; `nh_nl_ratio.csv` was rebuilt from scratch.

The result is a single `pd.DataFrame` with all breadth columns, cached as a module-level `_BREADTH_CACHE` so that `pct_200dma_pull`, `mcclellan_pull`, and `nh_nl_pull` all call `load_breadth_frame()` once and each extract their own column — one download, three outputs.

**The expensive step:** On first run (cold cache), downloading 500 tickers in 13 chunks of 40 takes approximately 45–60 seconds. Subsequent calls within the same process hit the `_BREADTH_CACHE` in-memory object at zero cost.

---

#### Hard part 6: DBMF beta — a rolling OLS regression, not a price

DBMF (iM DBi Managed Futures Strategy ETF) is used as a proxy for CTA/systematic trend-following positioning. The SSI does not use DBMF's price directly — it uses its **21-day rolling beta versus SPY** (daily returns regression).

```python
def dbmf_beta_vs_spy(window: int = 21, start: str = "2015-01-01") -> pd.Series:
    dbmf_ret = fetch_yahoo_close("DBMF", start).pct_change()
    spy_ret = fetch_yahoo_close("SPY", start).pct_change()
    aligned = pd.DataFrame({"dbmf": dbmf_ret, "spy": spy_ret}).dropna()
    cov = aligned["dbmf"].rolling(window).cov(aligned["spy"])
    var = aligned["spy"].rolling(window).var()
    beta = cov / var.replace(0, np.nan)
    return beta.rename("dbmf_beta")
```

When DBMF beta is near 0–0.5, CTAs have low equity exposure (trend-following elsewhere or flat). When beta is ≥1.2, CTAs are strongly following the equity trend. **A negative beta** (~−0.10 or lower) means CTAs are actively positioned against equities — this is the "CTAs short" research signal identified in Test 7 of the validation suite.

The reason this is distinct from a simple price or level: beta responds to the *correlation of daily moves*, not to price direction. DBMF can be trending up in price while its beta vs SPY is negative — that would mean DBMF is rising because it is short equities in a falling market. This makes beta a far better proxy for CTA positioning intent than price alone.

---

#### Hard part 7: `build_ssi_history` — computing composite level AND percentile in a single forward-only pass

The most algorithmically complex function in the SSI engine is `build_ssi_history()` in `ssi_score.py`. It needs to produce, for every date from 2015 to today:
1. The **SSI composite level** (weighted z-score combination of all 4 inputs)
2. The **5-year percentile** of that level against its own prior history

The naive approach — compute all levels first, then compute percentiles — would be fine for historical analysis. But it would produce **look-ahead bias**: today's percentile would be computed against future data. For the validation to be valid, each day's percentile must only use data available up to that day.

The solution is a **single forward-only loop**:

```python
for dt in idx:                                    # iterates from 2015-01-01 forward
    vals = {k: last_value_as_of(dt) for k, s in series.items()}
    score = weighted_zscore_at_dt(dt, vals)       # z-score uses history only up to dt
    levels.append((dt, score))
```

For each date `dt`, the z-score for each component is computed using `series[key].loc[:dt]` as the history window — only past data, never future. This makes the percentile calculation clean: once `levels` is built, the 5-year trailing percentile for any given day is simply `(prior_5yr_levels <= today_level).mean() * 100`.

The same forward-only pattern is used in `compute_ssi_at_date()` — the live daily scorer — so the production percentile is always comparable to the historically computed one.

The performance cost: with ~2,800 trading days from 2015 to 2026 and 4 component series, the full pass takes about 8–12 seconds on the production server. Acceptable for a daily job but too slow to run on every API call, which is why `build_ssi_history()` result is cached and the live `compute_ssi_at_date()` calls it once and stores the history.

---

#### Hard part 8: Layer 2 vote logic — four different measurement scales in one function

Layer 2 in `layer2.py` runs 4 votes and outputs CONFIRMED / PARTIAL / UNCONFIRMED + the size multiplier (1.2 / 1.0 / 0.8). Every input uses a **completely different measurement approach**, which meant four separate code branches in `evaluate_layer2()`:

**Vote 1 — HYG/LQD: percentile of level**
```python
pct = _pctile_in_history(hyg, series["hyg_lqd"].loc[:as_of_ts])
risk_on  = pct >= 70    # ratio at top 30% of own history
risk_off = pct <= 30    # ratio at bottom 30%
active   = risk_on or risk_off
```
This vote is scale-independent. The HYG/LQD ratio level changes over time as ETF prices evolve; comparing it to its own percentile history avoids the problem of an absolute threshold becoming stale. A ratio of 0.85 might be the 10th percentile in one year and the 50th in another depending on the credit cycle.

**Vote 2 — DBMF beta: absolute magnitude bands**
```python
low  = beta <= 0.5    # subdued equity beta (CTAs not committed long)
high = beta >= 1.2    # strong equity beta (CTAs following equity trend)
active = low or high
```
This uses absolute values, not percentile, because beta is already dimensionless (covariance divided by variance). The 0.5/1.2 thresholds represent natural anchor points: a beta below 0.5 means less than half of DBMF's daily moves are explained by SPY, indicating CTA positioning divergence from equities.

**Vote 3 — CNN Fear & Greed: direct level threshold**
```python
fear   = fg <= 25    # extreme fear zone
greed  = fg >= 75    # extreme greed zone
active = fear or greed
```
CNN Fear & Greed is already a normalised 0–100 scale published by CNN. It does not require further transformation — the 25 and 75 levels are the "extreme" zone boundaries on CNN's own public scale. Using a percentile of this series would add complexity without improving meaning since CNN already expresses the reading as a relative score.

**Vote 4 — VIX ratio: ratio threshold**
```python
stress      = vr >= 1.05    # near-term vol > long-term vol (mild backwardation)
complacency = vr <= 0.95    # long-term vol > near-term (contango, calm)
active = stress or complacency
```
The VIX ratio (VIX3M ÷ VIX, same computation as Runic's VXTS) is a pure ratio that is meaningful relative to 1.0 — the break-even between contango and backwardation. The 1.05 and 0.95 bands are deliberately more sensitive than Runic's Combo D/G thresholds (1.10/0.95), because SSI adjusts size daily while combos are infrequent events.

**The counting rule:**
```python
if confirmed >= 2:   status = "CONFIRMED";   mult = 1.2
elif confirmed == 1: status = "PARTIAL";     mult = 1.0
else:                status = "UNCONFIRMED"; mult = 0.8
```

Each of the four votes is a binary `active = True/False`. `confirmed` counts how many fired. ≥2 of 4 = CONFIRMED. The vote details (raw value, percentile where applicable, which direction it voted) are all stored in `vote_details` list and written to `positioning.json` so the C++ engine has full transparency about what drove the multiplier.

---

### Phase 7 — v3 verification and validation suite (≈5 hours)

**What happened:** Building `run_full_v3_verification.py`, traceability matrix, `audit_production_no_mocks.py`, v3 go/no-go report; plus the SSI 15-test validation suite.

**Hard parts:**
- No-mock audit: the original `audit_production_no_mocks.sh` exited with code 2 due to bash shell completion errors on the AWS host. Had to rewrite as a Python script.
- Traceability matrix: 46 rows covering every v3 requirement, with live probes
- SSI validation suite: 14 of 15 Divyanshu tests implemented and run; two tests (TP/SL, SBI breadth) required MindWealth adapter scripts

---

### Summary table

| Phase | Hours | Main deliverables |
|-------|-------|-------------------|
| Architecture + spec reading | 4 | `CONFIG.yaml`, design decisions |
| Data pipeline (12 variables) | 7 | All data pullers, CNH fallback, CFTC parser, BLS CPI |
| Engine (combos A–G, dominant, hit rates) | 8 | `combo_detector.py`, backfill, forward returns |
| Database + backfill | 5 | SQLite schema, 1,050 Friday backfill, 15,072 forward returns |
| Claude AI integration | 4 | Regime classifier, narrative briefing, heuristic fallback |
| SSI (14 inputs + Layer 2) | 7 | `positioning.json`, `ssi.db`, 14 pullers, validation |
| v3 verification + validation suite | 5 | Go/no-go report, 14 Divyanshu tests, threshold doc |
| **Total** | **≈40** | |

---

### The hardest individual problems

1. **CFTC column parsing** — Finding the right S&P 500 contract among dozens of contracts in the TFF report, excluding mini contracts, and mapping changing column names across years.

2. **Backfill performance** — 15,072 forward returns took 5 hours naively; brought down to 13 minutes with a cached NYSE sessions index and batch commits.

3. **Combo C cancel** — Had to persist "last 4 Friday WTI readings" across job runs in the database; state tracking for a stateful business rule.

4. **Asymmetric SSI short gate** — The original spec had ±0.6 symmetric. The Open Questions doc explains why this fires shorts too early. Took validation sweeps on 11 years of data to confirm and document.

5. **AAII in production** — The AAII website blocks the AWS server's IP. This means the SSI AAII input requires a weekly manual ingest step that isn't automated.

---

## Where to go from here

| Remaining task | Who | File |
|----------------|-----|------|
| Fill in Rohit sign-off answers | Rohit | `docs/plans/macro_intelligence_rohit_signoff.md` |
| Confirm JSON path for C++ on AWS | Ahil | `MACRO_INTEL_JSON_PATH` env var |
| Run `install_aws_cron.sh` on 51.20.53.218 | Ops | `scripts/install_aws_cron.sh` |
| Weekly AAII manual ingest | Ops | `scripts/ingest_aaii_sentiment.py` |
| Run SSI validation tests 5 and 15 | Divyanshu | `scripts/run_ssi_validation_suite.py` (without `--skip-mindwealth`) |
| Rohit approves SSI thresholds | Rohit | `docs/ssi_validation/SIGNOFF.md` |

---

*For threshold-justification detail, see [`docs/ssi_validation/SSI_THRESHOLD_JUSTIFICATION.md`](ssi_validation/SSI_THRESHOLD_JUSTIFICATION.md). For SSI experiments summary, see [`docs/ssi_validation/SSI_OPEN_QUESTIONS_SUMMARY.md`](ssi_validation/SSI_OPEN_QUESTIONS_SUMMARY.md). For the v3 go/no-go report, see `macro_intelligence/output/v3_go_no_go.md`.*

---

*Document generated 2026-06-05. Update alongside any CONFIG.yaml, combo rule, or SSI threshold change.*
