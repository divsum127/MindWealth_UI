Hi Divyanshu, Ahil,

Forwarding the May 18 spec below for reference. I need to confirm status and share four updates to that spec.

## FIRST: Status check

Ahil —  Please confirm if portfolio_sizer.py been created and tested? Perhaps you used it in the forced portfolio? Can you worh with Divyanshu and help with this please?
We need this running before the portfolio page goes live.

## FOUR UPDATES TO THE Mid-May SPEC

### UPDATE 1 — VIX percentile window: change from 1yr to 3yr

The May 13 spec (Step 1) says "Download one year of ^VIX." Please change this to **3 years**.

Why: the Signals/Runic page already uses a 3yr rolling percentile for VIX in combo detection (variable #6). Using 1yr in the portfolio sizer and 3yr in the combo engine creates inconsistent regime classifications. 3yr captures a full market cycle (bull + correction + recovery) without being distorted by a single extreme event. A 1yr window anchored to a VIX spike period would skew all subsequent percentiles.

Current reading with 3yr window: VIX 16.4 = approximately 40th percentile → Normal regime → 80% equity ceiling. (Using 1yr: ~48th percentile → also Normal. Same regime classification today, but they will diverge in transition periods.)

No other change to Step 1 logic.

---

### UPDATE 2 — Combo B/F bypass of the VIX multiplier (add to Step 2)

In Step 2 (SSI multipliers), add this critical exception rule **as a named constant and docstring in the code**:

```python
# CRITICAL RULE: VIX_REGIME_BYPASS
# When Combo B (Maximum Capitulation) is confirmed active, OR when
# Combo F (Recovery Window) is active AND SSI confirms (>=2 of 4 signals),
# the VIX level multiplier in Step 2 is BYPASSED entirely — treated as 1.00×
# regardless of the actual VIX reading.
#
# Historical basis: October 13, 2022 — VIX 33.6 would have triggered the
# 0.75× stress multiplier, cutting position size by 25% at the exact market
# bottom. Combo B was simultaneously confirmed. The multiplier would have
# been wrong. Combo B overrides it.
#
# April 2025: same pattern. VIX ~52, Combo B fired. SPX +25% from lows.
# Cutting size at VIX >35 when capitulation is confirmed is the opposite
# of the correct action.
#
# The bypass applies to the VIX LEVEL multiplier only (the ×0.50 / ×0.75
# values). The OAS credit multiplier and SPX trend multiplier still apply.
```

The full Step 2 multiplier table for reference:

**VIX level multiplier** (bypassed when Combo B or F active):

| VIX level | Multiplier |
|---|---|
| VIX < 15 (calm) | ×1.20 |
| VIX 15–25 (normal) | ×1.00 |
| VIX 25–35 (stress) | ×0.75 |
| VIX > 35 (crisis) | ×0.50 |
| Combo B confirmed OR (Combo F + SSI ≥2) | ×1.00 BYPASS |

**SPX trend multiplier:**

| Condition | Multiplier |
|---|---|
| SPX more than 5% above its 200-day average | ×1.00 |
| SPX below its 200-day average | ×0.80 |

**HY credit spread (OAS) multiplier:**

| OAS level | Multiplier |
|---|---|
| OAS < 300bp | ×1.00 |
| OAS 300–500bp | ×0.90 |
| OAS 500–700bp | ×0.80 |
| OAS > 700bp | ×0.70 |

Example (current): Normal regime (80%) × 1.00 VIX × 1.00 trend × 0.90 credit (318bp) = **72% final ceiling**.


### UPDATE 3 — Investment type budgets are % of TOTAL PORTFOLIO, not deployed equity

This is a clarification, not a code change — but it matters for how the scaling logic works in Step 5.

The CLUSTER_BUDGETS percentages (e.g. semiconductors: 12%) mean **12% of total portfolio = $12M on a $100M portfolio**. They are NOT 12% of the deployed equity amount.

When the equity ceiling constrains total deployment (e.g. to 72% = $72M), if all investment type budgets added up to $100M of signals, the system scales them proportionally so their sum ≤ $72M. Each budget's cap ($12M for semis) acts as an individual maximum — the overall ceiling is a separate second constraint.

In Stress regime: the CLUSTER_BUDGETS table has separate (lower) caps per investment type for the stress scenario. For example, semiconductors might drop from 12% to 8% in Stress (the exact stress values need to be confirmed and added to CLUSTER_BUDGETS — see the note below). The equity ceiling also drops to ~58%. Both constraints apply simultaneously.

**Action for Ahil:** please confirm the Stress and Low Vol versions of CLUSTER_BUDGETS are defined in the code, and share those values. The spec said "Three versions (low_vol / normal / stress)" but only provided the Normal example. We need the Stress and Low Vol tables.


### UPDATE 4 — Portfolio scaled to $100M

The worked example in the May 13 spec used $500,000. All UI, documentation, and client-facing output should now use **$100,000,000** as the reference portfolio size. The logic and percentages are identical — just update the dollar amounts in any worked examples or output formatting.


## REMINDER: KEY RULES FROM MAY 13 THAT REMAIN UNCHANGED

For Divyanshu's reference — these are not changing:

- Single function → entry decision. Multiple functions → size decision only (via MULTI-SIG flag, Step 8). We never require consensus to enter.
- Per-trade Sharpe not shown to clients. Client output table: Portfolio Sharpe (TO BE CALCULATED IT SHD COME TO SAY 2.9–3.0 AHIL PLEASE CHECK THIS), Win Rate, CAGR, Max Drawdown, Avg Holding Period, Peak Leverage (2×).
- NZ equities: VIX regime ceiling does NOT reduce NZ allocation. Model selects which NZ stocks to hold, not whether to hold them. In general the code should provide the option to enter assets that are outside of the vix regime ceiling - that one wants to hold in the same size regardless of vix regime.
- Yield trap hard zero: overrides all other scoring. No entry ever.


## HOW THE FULL SIZING FLOW WORKS (for shared reference)

To make sure we're all aligned on the end-to-end logic, here is the complete flow from a signal firing to a final dollar allocation, using NVDA as an example on a $100M portfolio in Normal regime:

**Step 1 — How much can we deploy at all?**
VIX at 40th percentile (3yr) → Normal regime → 80% equity ceiling maximum.

**Step 2 — SSI multipliers haircut that 80%:**
VIX level 16.4 (calm, 15–25 band) → ×1.00
SPX above 200-day average → ×1.00
HY credit spreads 318bp (300–500bp band) → ×0.90
Final: 80% × 1.00 × 1.00 × 0.90 = **72% equity ceiling** → $72M deployed, $28M cash earning 3.5% p.a. (~$980k/yr).

**Step 3 — Investment type budget:**
Semiconductors = 12% of $100M = **$12M maximum** for all semiconductor positions combined.

**Step 4 — Win rate ranking within the budget:**
NVDA win rate: 0.94. ASML win rate: 0.91. Two active signals.
NVDA's share of $12M = 0.94 ÷ (0.94 + 0.91) = 50.8% → **$6.10M base**.

**Step 5 — MULTI-SIG adjustment (if applicable):**
NVDA has FractalTrack AND DeltaDrift both firing LONG this week.
MULTI-SIG boosts NVDA's win rate score by 10% before the ranking calculation:
0.94 × 1.10 = 1.034. New split: 1.034 ÷ (1.034 + 0.91) = 53.2% → **$6.38M**.
(This is a larger dollar allocation within the same $12M budget — not a separate bonus on top.)

**Step 6 — Business Quality (BQ) score tier:**
NVDA BQ +9 → MAX tier → keeps 100% of its allocated amount: **$6.38M**.
(If BQ were +5, TACTICAL would apply → 75% → $4.79M. If +3, REDUCED → 40% → $2.55M.)

**Step 7 — Fundamental Divergence (FD) upsize/downsize:**
NVDA has FD+ (price fell 18% but business quality improved) → upsize allocation by +10 percentage points.
Instead of 100% of $6.38M, NVDA gets 110% → **$6.38M × 1.10 = $7.02M final allocation**.

**Summary:** $100M portfolio → 72% ceiling → $12M semis budget → NVDA wins $7.02M through win rate ranking, MULTI-SIG size boost, BQ MAX tier, and FD+ upsize.

Please confirm receipt and share portfolio_sizer.py status.

Best,
Rohit


---------- Forwarded message ---------
From: AHIL KHAN <ahilkhanjnv@gmail.com>
Date: Mon, 18 May 2026 at 08:56
Subject: Re: Portfolio Sizer v2 — Updated Spec (what you have vs what to add)
To: Rohit Malhotra <rohit.malhotra1@gmail.com>


yes sir i have seen this

On Mon, May 18, 2026 at 11:48 AM Rohit Malhotra <rohit.malhotra1@gmail.com> wrote:
hi confirm seen tx

On Fri, 15 May 2026 at 12:34, Rohit Malhotra <rohit.malhotra1@gmail.com> wrote:
Here are just the three additions to paste in:

INSERT after "What You Already Have" section, before Steps 1–9:

────────────────────────────────────────
ASSET SELECTION LOGIC — IMPORTANT CLARIFICATION
────────────────────────────────────────

We NEVER take a position purely because multiple functions have fired 
simultaneously on the same asset. The combined strategy data proved 
clearly that requiring multi-function consensus for entry reduces 
portfolio returns — every combined row was materially worse than 
standalone.

Single function → entry decision.
Multiple functions → size decision only (via Claude Shortlisted flag, 
Step 8).

Assets self-select by satisfying one function's entry conditions. 
You never select assets directly — they earn their way in via the 
function rules.
INSERT after Timeline, before sign-off:

────────────────────────────────────────
MAX DRAWDOWN — STUDY NEEDED PER FUNCTION
────────────────────────────────────────

Before client presentation we need max drawdown per function across 
these discrete periods. Start with Band Matrix:

Period 1:  Jan–Mar 2020      COVID crash
Period 2:  Mar–Dec 2020      V-shaped recovery
Period 3:  Jan–Dec 2021      Low vol / euphoria
Period 4:  Jan–Oct 2022      Rate hike bear market
Period 5:  Nov 2022–Dec 2023 Recovery + AI rally
Period 6:  Jan 2024–present  Forward test

Why: one continuous backtest blends regimes and masks best/worst 
behaviour. Band Matrix hypothesis: outperforms in period 4 (mean 
reversion works in bear/choppy), underperforms in periods 2–3 
(trending). If confirmed, this justifies the higher Band Matrix 
cluster budget in stress regime already in CLUSTER_BUDGETS.

Note: our max drawdown will likely be higher than institutional funds 
(they target 8–12% as primary constraint). We are building a high 
Sharpe product, not a low drawdown product. These numbers define our 
honest risk disclosure to clients.
INSERT in PS section as point 4:

4. Do not show per-trade Sharpe in any client-facing output. 
Per-trade Sharpe is low (~0.4) — this is expected and correct, it 
measures one trade in isolation. Portfolio Sharpe (~2.9–3.0) is what 
clients experience and is the right number. Client table shows: 
Portfolio Sharpe, Win Rate, CAGR, Max Drawdown, Avg Holding Period, 
Peak Leverage (2×).

---------- Forwarded message ---------
From: Rohit Malhotra <rohit.malhotra1@gmail.com>
Date: Wed, 13 May 2026 at 10:19
Subject: Portfolio Sizer v2 — Updated Spec (what you have vs what to add)
To: AHIL KHAN <ahilkhanjnv@gmail.com>


Hi Ahil,

Updating my earlier email with the final spec. Good news: your engine is solid and barely changes. You are adding one wrapper file — portfolio_sizer.py — that intercepts candidates_df before it reaches your existing allocation engine. Your simulation, tranche logic, idle cash, ranking, and output all stay exactly as they are.

────────────────────────────────────────
WHAT YOU ALREADY HAVE — NO CHANGES NEEDED
────────────────────────────────────────

✓  FUNCTION_CONFIG with all functions (FractalTrack, TrendPulse, DeltaDrift, SigmaShell, BandMatrix, PulseGauge, OscillatorDelta, BaselineDivergence)
✓  Signal ranking: Win Rate → CAGR → Sharpe → symbol → function_name (this is correct, keep it)
✓  5 parallel tranches, idle cash at 3.5% p.a.
✓  Core simulation engine (_simulate_coordinated_tranches_allocation)
✓  signals_cut_by_cluster_limit field already exists in your output — we are now activating the logic behind it
✓  Fundamental filter (PE / sector PE / profit) — this was a good placeholder. It is now RETIRED and replaced by the Conviction Engine score (see Step 6 below). Delete the apply_fundamental_filters call.

One note on your CAGR ranking: you are using absolute CAGR of the strategy. That is correct for now and fine to keep. A future v2 enhancement would be to ALSO CONSIDER CAGR DIFFERENCE (EG FOR LONG - relative to buy-and-hold of the same asset (to measure true alpha) — but that is not urgent. anD AM NOT EVEN SURE THAT WILL PERFORM BETTER :))

────────────────────────────────────────
WHAT TO ADD — portfolio_sizer.py (Steps 1–9)
────────────────────────────────────────

All of this goes into one new file. Your existing code calls it just before _simulate_coordinated_tranches_allocation() receives candidates_df.

Step 1 — VIX regime ceiling
Download one year of ^VIX from Yahoo Finance (you already pull Yahoo data). Calculate where today's VIX sits as a percentile of that year. This gives the base deploy ceiling:
   VIX ≤ 25th percentile (low_vol)  → max deploy 85%
   VIX 25th–75th percentile (normal) → max deploy 80%
   VIX ≥ 75th percentile (stress)    → max deploy 65%

Step 2 — SSI (Super Sentiment Index) multiplier on the ceiling
Three small adjustments to the ceiling from Step 1:
   VIX level:    calm (<15) → ×1.20 / normal (15–25) → ×1.00 / stress (25–35) → ×0.75 / crisis (>35) → ×0.50
   Trend:        SPX >5% above 200DMA → ×1.00 / below 200DMA → ×0.80
   Credit (HY):  OAS <300bp → ×1.00 / 300–500bp → ×0.90 / 500–700bp → ×0.80 / >700bp → ×0.70
Multiply all three together and apply to the ceiling.
Example: normal VIX (80%) × 1.00 × 0.90 (HY at 318bp) = 72% final ceiling.

Step 3 — CLUSTER_MAP dictionary
A simple Python dict assigning every ticker to a cluster. Example:
   'JPM': 'financials', 'GS': 'financials', 'NVDA': 'semiconductors', 'CNR.TO': 'canada_defensive'
Any ticker not in the map → 'uncategorised' (treated as isolated, which is fine for diversification).
SEE STEP 3 full list separately AT BOTTOM OF THIS EMAIL

Step 4 — CLUSTER_BUDGETS table
Three versions (low_vol / normal / stress). Each defines:
   - max % of total portfolio for that cluster
   - max signals allowed from that cluster simultaneously
Example for normal regime:
   global_risk_on: 18%, 3 signals max
   semiconductors: 12%, 3 signals max
   financials:     12%, 3 signals max
   commodities:    10%, 3 signals max
   canada_defensive: 10%, 3 signals max
   (remaining clusters share the balance)
Note: you already have signals_cut_by_cluster_limit in your output — this step activates the logic that populates it.

Step 5 — Apply cluster caps to candidates_df
Before passing to your simulation:
   - Assign each candidate its cluster from CLUSTER_MAP
   - Within each cluster, keep only the top N by win_rate_score (N from CLUSTER_BUDGETS for current regime)
   - Excess candidates go into signals_cut_by_cluster_limit (already in your output)
   - Scale all cluster dollar budgets proportionally so total ≤ final ceiling from Step 2

Step 6 — Replace PE filter with Conviction Engine score
Delete the _passes_fundamental_filters() call. Instead, call conviction_dispatch.py once per symbol:
   conviction_score < +2  → drop from candidates entirely (hard zero — stricter than PE filter)
   conviction_score ≥ +2  → keep, store score on candidate row for Step 7
   yield trap fires        → hard zero, overrides everything
Conviction Engine code is already built — this is just a one-line call per symbol.

Step 7 — Apply conviction score to sizing
After the cluster budget allocates a dollar amount per signal, apply the size modifier:
   conviction ≥ +8  → 100% of calculated allocation
   conviction ≥ +5  → 75%
   conviction ≥ +2  → 40%
   conviction < +2  → 0% (already excluded in Step 6, but belt-and-braces)

Step 8 — Claude Shortlisted flag
After candidates_df is built, scan for any ticker where 2+ different functions have both signalled the same direction in the same week. Flag those rows claude_shortlisted = True. In the cluster ranking (Step 5), boost their win_rate_score by 10% so they rank higher and receive a larger share of the cluster budget. These are not a separate trade type — same trade, more size, more conviction.

Step 9 — Per-asset drawdown hard zero
When the live portfolio is running, check each open position's current MTM against its entry price daily. If loss > 10% from entry → add to hard_zero_signals → excluded from next sizing run regardless of whether the function has fired an exit signal. This is the pod shop rule. Per-cluster drawdown (cluster collectively down >15% → reduce to 1 signal max) is v2 — do not build now.

────────────────────────────────────────
WORKED EXAMPLE — $500,000 portfolio, normal regime
────────────────────────────────────────

VIX at 48th percentile → normal → base ceiling 80%
SSI multiplier: VIX normal (1.00×) × trend bull (1.00×) × HY 318bp (0.90×) = 0.90
Final ceiling: 80% × 0.90 = 72%

Total deployable:  $500,000 × 72% = $360,000
Cash held:         $140,000 (earns 3.5% p.a.)

Cluster budgets (scaled to fit within $360,000):
   global_risk_on:    18% → $90,000  → 3 signals max
   semiconductors:    12% → $60,000  → 3 signals max
   financials:        12% → $60,000  → 3 signals max
   commodities:       10% → $50,000  → 3 signals max
   canada_defensive:  10% → $50,000  → 3 signals max

Within financials cluster ($60,000 budget):
   JPM — FractalTrack Monthly LONG  win_rate_score 0.97 → 40% share → $24,000
   GS  — TrendPulse Weekly LONG     win_rate_score 0.91 → 37% share → $22,200
   BAC — FractalTrack Daily LONG    win_rate_score 0.72 → 23% share → $13,800

   After Conviction Engine:
   JPM: score +6 → 100% → $24,000
   GS:  score +4 → 75%  → $16,650
   BAC: score +2 → 40%  → $5,520  (or cancel if <+2)

   Claude Shortlisted bonus:
   JPM has FractalTrack AND DeltaDrift both signalling LONG this week
   → win_rate_score boosted 10% in cluster ranking → JPM share increases
   → JPM allocation: $24,000 × 1.10 = $26,400

   Freed cash (from conviction discounts) returns to portfolio cash pool.

────────────────────────────────────────
DRAWDOWN RULES (implement in this order)
────────────────────────────────────────

v1 now — Per-asset: any position losing >10% from entry → exit immediately, do not wait for function exit signal. This is the standard pod shop rule.

v2 later — Per-cluster: if a cluster (e.g. semis) is collectively down >15% → reduce that cluster to 1 signal max until it recovers. Catches sector shocks (e.g. export controls hitting all semis at once).

Portfolio-wide drawdown ties into the VIX regime detection you already have — if portfolio draws down >8% from high-water mark, shift to stress regime budgets. This is essentially free once Steps 1–2 are done.

────────────────────────────────────────
TIMELINE
────────────────────────────────────────

Steps 1–5 (regime ceiling + cluster caps): by Thursday
Steps 6–7 (Conviction Engine integration): by Thursday
Steps 8–9 (Shortlisted flag + drawdown): by Friday
End-to-end test run on existing data: Friday

Happy to walk through any of this on a call. The core insight is simple: your engine is unchanged. portfolio_sizer.py just decides which candidates to pass to it, and in what amounts.

Best,
Rohit



STEP 3 FULL LIST -->>> CLUSTER_MAP = {

    # Global Risk-On
    'SPY': 'global_risk_on',
    '^GSPC': 'global_risk_on',
    'IWM': 'global_risk_on',
    'QQQ': 'global_risk_on',
    'VGT': 'global_risk_on',
    'XLY': 'global_risk_on',

    # Semiconductors
    'ASML': 'semiconductors',
    'TSM': 'semiconductors',
    'MU': 'semiconductors',
    'AVGO': 'semiconductors',
    'NVDA': 'semiconductors',
    'AMD': 'semiconductors',
    'ARM': 'semiconductors',

    # Financials
    'JPM': 'financials',
    'GS': 'financials',
    'BAC': 'financials',
    'TD': 'financials',
    'TD.TO': 'financials',
    'RY.TO': 'financials',
    'BNS.TO': 'financials',
    'BN.TO': 'financials',
    'NA.TO': 'financials',
    'IBKR': 'financials',
    'MA': 'financials',

    # Commodities
    'GDX': 'commodities',
    'SLV': 'commodities',
    'USO': 'commodities',
    'WPM': 'commodities',
    'WPM.TO': 'commodities',
    'CNQ.TO': 'commodities',
    'GLD': 'commodities',

    # Canada Defensive
    'PPL.TO': 'canada_defensive',
    'CNR.TO': 'canada_defensive',
    'ATD.TO': 'canada_defensive',
    'SJ.TO': 'canada_defensive',
    'XIU.TO': 'canada_defensive',
    'EFN.TO': 'canada_defensive',
    'MTY.TO': 'canada_defensive',
    'MX.TO': 'canada_defensive',
    'DOL.TO': 'canada_defensive',
    'BDGI.TO': 'canada_defensive',
    'TFII.TO': 'canada_defensive',
    'BYD.TO': 'canada_defensive',
    'TRI.TO': 'canada_defensive',
    'DOLD.TO': 'canada_defensive',

    # NZ Local
    'IFT.NZ': 'nz_local',
    'FPH.NZ': 'nz_local',
    'ATM.NZ': 'nz_local',
    'AIA.NZ': 'nz_local',
    'GNE.NZ': 'nz_local',
    'SUM.NZ': 'nz_local',
    'MEL.NZ': 'nz_local',
    'CEN.NZ': 'nz_local',
    'SPK.NZ': 'nz_local',
    'FSF.NZ': 'nz_local',

    # India
    'INFY': 'india',
    'PERSISTENT.NS': 'india',
    'TCS.NS': 'india',
    'WIPRO.NS': 'india',
    'NAUKRI.NS': 'india',
    'BEL.NS': 'india',
    'GRANULES.NS': 'india',
    'INDY': 'india',
    'INDA': 'india',
    'MAZDOCK.NS': 'india',

    # EM Asia
    'FXI': 'em_asia',
    'EEM': 'em_asia',
    'ACWX': 'em_asia',
    '3033.HK': 'em_asia',
    '000660.KS': 'em_asia',
    'ASHR': 'em_asia',
    '^STI': 'em_asia',

    # US Tech Large Cap
    'GOOG': 'us_tech_large',
    'AMZN': 'us_tech_large',
    'TSLA': 'us_tech_large',
    'META': 'us_tech_large',
    'MSFT': 'us_tech_large',
    'ORCL': 'us_tech_large',
    'BABA': 'us_tech_large',
    'JD': 'us_tech_large',
    'SFTBY': 'us_tech_large',

    # Healthcare
    'RHHBY': 'healthcare',
    'CVS': 'healthcare',
    'XLV': 'healthcare',
    'IHI': 'healthcare',
    'PPH': 'healthcare',

    # Consumer
    'NKE': 'consumer',
    'MAR': 'consumer',
    'MCD': 'consumer',
    'PG': 'consumer',
    'JETS': 'consumer',

    # Bonds / Rates
    '^TNX': 'bonds',
    'XLU': 'bonds',
    'TLT': 'bonds',

    # FX
    'NZDUSD=X': 'fx',
    'NZDCAD=X': 'fx',
    'USDCNH=X': 'fx',

    # Europe
    'MSE.PA': 'europe',

    # Japan
    # (SFTBY moved to us_tech_large as it trades on US markets)

}



PS - Three things


Any ticker from portfolio.csv or indianstake.csv that is NOT in this map will automatically go to 'uncategorised' — which is fine, it gets a default 10% cluster budget and is treated as isolated. So no signal is ever lost, it just doesn't benefit from cluster-level capping.
Some tickers appear in multiple possible clusters — e.g. INDY and INDA are ETFs tracking India but trade on US markets. Please put them in india since that's their exposure. 
 NZ tickers — use the names I already gave you. eg if we add more nz names to the asset list of approx 200, then auto-assign any .NZ suffix ticker not in the map to nz_local. Note that unlike other clusters, NZ capital must stay deployed in NZ equities at all times — the VIX regime ceiling does not reduce the NZ allocation. The model's job for NZ is selecting which stocks to hold, not whether to hold them.
