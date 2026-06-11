# Macro Intelligence Agent (Runic v2.2) — Questions for Rohit

**Prepared for:** Divyanshu  
**Purpose:** Get clear answers before more coding or go-live  
**Language:** Plain English — no jargon where avoidable  
**Sources:** May 26 build spec, Addendum, Cheat sheet, Integration Note v3 (May 28), current code in `src/macro_intelligence/`

**Rule from v3:** If an older email disagrees with the May 28 Integration Note, **the May 28 note wins**.

---

## How to use this document

1. Send Rohit the **“Short list”** section first (15 questions) if time is limited.  
2. For **everything missing** (explained from scratch, no jargon assumed), read **Section 12 — Missing things** (~30 items with “what it is / spec / today / why / questions”).  
3. Use the **detailed sections** in a call — each question explains *why it matters*.  
4. Write answers in the **Answer** lines so the team has one record.

---

## Short list (send these first)

1. What is the exact folder path for `runic_output.json` on the AWS server (51.20.53.218)?  
2. Should the Python job run at **5pm ET after Ahil’s C++ job**, or still at **9pm ET** — or both?  
3. Combo F test date: **June 8, 2020** (v3) or **June 29, 2020** (May 26 email)?  
4. For combo signals, do we use **full history** percentiles for every variable, or **3-year rolling** for some (oil, CNH, etc.)?  
5. Friday checklist says “3-year percentile” for NFCI — is that only for display, while detection uses full history?  
6. When Combo B might fire on Friday but CFTC data is 3 days old — should `vix_bypass` be **on or off** until Tuesday?  
7. Is **Combo C cancel logic** (4 clean Fridays + CPI check) required before go-live?  
8. Is **full historical backfill** (35 years) a release requirement or can it run after launch?  
9. Who provides **FRED API key**, **Tavily key**, and **CPI consensus** data?  
10. GSR: confirm we use Yahoo **GOLD** (not gold futures GC=F) divided by **SI=F**?  
11. Is **SSI / positioning.json** built by someone else — who and when?  
12. Combo E today: should status be **CONFIRMED (2 of 3)** not **PARTIAL** when CAPE is extreme and NFCI is easy?  
13. Is **Tavily news** needed in v1 for the nightly written briefing?  
14. Mar **30, 2026** Combo F in the cheat sheet — is that still a real reference date for testing live output?  
15. What is the minimum **v1 go-live checklist** (Tier A only vs full v3)?

---

## 1. Files, servers, and timing

### Q1.1 — Where should the JSON file live?

**Question:** On the AWS server (IP 51.20.53.218), what is the **full path** where `runic_output.json` must be written?  
Example: `/home/ubuntu/MindWealth/runic_output.json` or something else?

**Why it matters:** The C++ trading engine reads this file. If the path is wrong, the agent can run successfully but **trading will not see it**.

**Answer:** _______________________________________________

---

### Q1.2 — When should the Python job run?

**Question:** The May 26 spec says write JSON at **9:00 PM ET Monday–Friday**. The May 28 note says write to AWS **after Ahil’s C++ daily run (~5:00 PM ET)**, once per day. Which schedule is correct for v1?

**Why it matters:** Wrong timing means stale data or overwriting files while C++ is still running.

**Answer:** _______________________________________________

---

### Q1.3 — Who runs what on the server?

**Question:** Will **you (Divyanshu)** deploy and run the Python cron on 51.20.53.218, or does **Ahil** run it? Who restarts it if it crashes?

**Why it matters:** Handoff doc says Ahil must restart jobs independently by July 25.

**Answer:** _______________________________________________

---

### Q1.4 — Same machine or copy files?

**Question:** Does Python run on the **same server** as C++, or does someone **copy** the JSON from another machine?

**Why it matters:** Affects how we set paths and permissions.

**Answer:** _______________________________________________

---

### Q1.5 — SSI file path

**Question:** Where will `positioning.json` (SSI system) live on the server? Same folder as Runic JSON?

**Why it matters:** Runic reads `ssi_multiplier` from SSI when that file exists. C++ reads both at market open.

**Answer:** _______________________________________________

---

## 2. SSI vs Runic — who builds what

### Q2.1 — Who owns SSI?

**Question:** Is the **SSI (Sentiment SuperIndex)** agent being built by another person or team? Is it in scope for Divyanshu?

**Why it matters:** Runic currently uses `ssi_multiplier = 1.0` as a placeholder until SSI exists.

**Answer:** _______________________________________________

---

### Q2.2 — When will SSI be real?

**Question:** What is the target date for a real `positioning.json` with multiplier values (1.0 / 1.2 / 0.8)?

**Why it matters:** Combo F can affect position size when SSI “confirms” — that link is not live yet.

**Answer:** _______________________________________________

---

### Q2.3 — Double-counting credit and VIX

**Question:** Please confirm: **HY spreads (FRED)** are only for Runic; **HYG/LQD ratio** is only for SSI; **VIX term structure** is only for Runic (not in SSI Layer 2). Is that still the rule?

**Why it matters:** Using the same signal twice would inflate confidence incorrectly.

**Answer:** _______________________________________________

---

## 3. Data sources and API keys

### Q3.1 — FRED API key

**Question:** Will the company provide a **FRED_API_KEY** for production? Without it, free CSV downloads may only give ~3 years of history, which breaks old tests (e.g. October 2022 HY spreads).

**Why it matters:** Hit rates and gate tests need long HY/VIX/NFCI history.

**Answer:** _______________________________________________

---

### Q3.2 — CPI and PPI “surprise”

**Question:** For CPI (and PPI in Combo C cancel), what is the **approved source** for:
- actual number (BLS? FRED CPIAUCSL?)
- consensus forecast (Investing.com? Bloomberg? manual spreadsheet?)

**Why it matters:** Combo C needs “hot CPI” vs “not hot.” Today we only have a manual CSV file.

**Answer:** _______________________________________________

---

### Q3.3 — No CPI release that week

**Question:** v3 says: if **no CPI/PPI** is published that week, the CPI leg of Combo C cancel **passes automatically**. Is that correct?

**Why it matters:** Affects whether Combo C stays active or cancels.

**Answer:** _______________________________________________

---

### Q3.4 — CFTC report format

**Question:** Can someone confirm the **exact column names** in the CFTC TFF file for S&P futures — both **Leveraged Money** and **Asset Manager** positions? Should we use **both** separately (v3 says yes)?

**Why it matters:** Wrong columns mean wrong “extreme positioning” signals for combos B, D, E, F.

**Answer:** _______________________________________________

---

### Q3.5 — CFTC is 3 days late on Friday

**Question:** The Friday CFTC report reflects **Tuesday** positions. v3 says flag combos as **PENDING_CFTC_CONFIRM** on Friday. Should we still show Combo B as “maybe active” or wait until Tuesday to call it active?

**Why it matters:** Affects `vix_bypass` and trader-facing JSON on Friday evening.

**Answer:** _______________________________________________

---

### Q3.6 — Gold and silver tickers (GSR)

**Question:** For Gold/Silver ratio we should use Yahoo **GOLD** (spot) ÷ **SI=F** (silver futures), not **GC=F** (gold futures). Correct?

**Why it matters:** Current code uses GC=F; v3 explicitly says GOLD.

**Answer:** _______________________________________________

---

### Q3.7 — Oil futures rollovers

**Question:** When the 4-week oil window crosses a **futures rollover**, v3 says **flag for manual review**. Should the engine **pause** Combo C on that week, or only add a warning in JSON/logs?

**Why it matters:** Bad oil % change can falsely fire or cancel Combo C.

**Answer:** _______________________________________________

---

### Q3.8 — CAPE if multpl.com fails

**Question:** If multpl.com scrape fails, should we fall back to **FRED MULTPL_CAPE**? Does that series exist on our FRED account?

**Why it matters:** Combo E depends on CAPE level.

**Answer:** _______________________________________________

---

### Q3.9 — Tavily for news

**Question:** Is **Tavily** (web news) required in v1 to help write the nightly briefing? If yes, who provides the API key and what topics (Iran, CPI, Fed, etc.)?

**Why it matters:** v3 lists Tavily; it is not built yet.

**Answer:** _______________________________________________

---

### Q3.10 — Missing Excel spec

**Question:** The original email mentioned **Macro_Intelligence_Agent_Spec.xlsx**. We do not have it in the repo. Is the cheat sheet + PDF + v3 note enough, or should we get the xlsx?

**Why it matters:** Variable IDs and thresholds might differ in the spreadsheet.

**Answer:** _______________________________________________

---

## 4. Percentiles and “extreme” logic

### Q4.1 — Full history vs 3-year window

**Question:** For **detecting combo fires**, should every variable use **full available history** (e.g. VIX since 1990, CAPE since 1881), OR do some variables still use a **rolling 3-year** window (oil, CNH, GSR, WALCL, CPI)?

**Why it matters:** v3 Section 3 says full history for combo detection; older addendum said mixed windows; our code uses mixed.

**Answer:** _______________________________________________

---

### Q4.2 — Contradiction inside v3 Friday list

**Question:** v3 Section 5 Friday checklist says compute **“3yr percentile”** for NFCI and HY. v3 Section 3 says combo detection uses **full-history unconditional** rank. Which is correct for Friday’s NFCI/HY step?

**Why it matters:** Same document gives two different rules — we need one answer.

**Answer:** _______________________________________________

---

### Q4.3 — Two percentile columns

**Question:** Should we store **two** ranks per variable per day?
1. **Unconditional** — vs all history  
2. **Regime** — vs history only when Fed cycle matches today  

And use **unconditional** for firing combos, **regime** for conviction modifier in JSON?

**Why it matters:** v3 requires both; we only store one field today (`pctile_rank_3yr`).

**Answer:** _______________________________________________

---

### Q4.4 — Regime history too short

**Question:** If “regime-conditioned” history has **fewer than 50** data points, v3 says use unconditional rank instead. Should we **log** when that happens so users know?

**Why it matters:** Transparency on the Runic UI page.

**Answer:** _______________________________________________

---

### Q4.5 — WTI 4-week formula

**Question:** For WTI 4-week change, is the formula:
- **Percent change:** `(price today / price 28 days ago - 1) × 100`, or  
- **Ratio:** `(price today - price 28 days ago) / price 28 days ago` (same thing as percent?), or  
- Something else?

**Why it matters:** v3 wording uses “÷ 28cd ago” — we need one formula in code.

**Answer:** _______________________________________________

---

## 5. Named combos — rules and status words

### Q5.1 — Combo B and VIX bypass on Friday

**Question:** When Combo B is **PENDING_CFTC_CONFIRM** on Friday (CFTC not final), should `vix_bypass` in JSON be **true**, **false**, or **unknown** until Tuesday?

**Why it matters:** C++ uses this to avoid cutting position size at bottoms.

**Answer:** _______________________________________________

---

### Q5.2 — Combo B test numbers

**Question:** October 13, 2022 test: v3 says HY OAS **~580 bps**; older spec said **~614 bps**. Both are above 400 bps threshold. Should the test accept **either**, or must we match one exact number?

**Answer:** _______________________________________________

---

### Q5.3 — Combo F fire date (important)

**Question:** Which date is the **official** Combo F validation example?
- **June 8, 2020** (v3 — +6.2% weekly gain, expiry Dec 14, 2020)  
- **June 29, 2020** (May 26 email — +5.1% week)  
- **March 30, 2026** (cheat sheet — live example)

**Why it matters:** Our unit tests still use June 29; v3 says June 8. Code and tests must match your answer.

**Answer:** _______________________________________________

---

### Q5.4 — Combo F “prior break”

**Question:** Before the 50-week moving average reclaim, is **one** weekly close below the 50-week MA enough to qualify? No minimum number of weeks underwater?

**Answer:** _______________________________________________

---

### Q5.5 — Combo F when D or B also active

**Question:**  
- If **Combo D** and **Combo F** are both active: “tighten stops, no new longs, hold core” — is that **text in the briefing only**, or **new JSON fields** for C++?  
- If **Combo B** fires while **Combo F** is active and SPX is still above the F entry price: treat as **add signal** — does C++ need a flag?

**Answer:** _______________________________________________

---

### Q5.6 — Combo E status (May 28, 2026 example)

**Question:** When CAPE is extreme and NFCI is **−0.52** (easy, below −0.3), v3 says Combo E is **CONFIRMED (2 of 3)**, not PARTIAL. Should our JSON use statuses like:
- `CONFIRMED` (2 of 3)  
- `CONFIRMED_3_OF_3` (when CFTC confirms on Friday)  
- `PARTIAL` (only 1 leg)?  

Please list **all status strings** you want in JSON and UI.

**Answer:** _______________________________________________

---

### Q5.7 — Combo D and VIX = 18

**Question:** VIX must be **strictly less than 18** (so 18.00 does **not** count). Confirm?

**Answer:** _______________________________________________

---

### Q5.8 — Combo C cancel (full rule)

**Question:** Please confirm Combo C **turns off** only when **both** are true for **4 Fridays in a row**:
1. WTI 4-week change is **below +5%** (can be negative or +4.9%)  
2. CPI/PPI was **not hot** (actual ≤ consensus), OR no release that week  

If **any** Friday fails either rule, counter **resets to zero**. Correct?

**Answer:** _______________________________________________

---

### Q5.9 — Combo A direction (BRAVE vs FEARFUL)

**Question:** Combo A needs a **direction vote** across four legs (NFCI, HY, WALCL, CNH) with placeholder rules in v3. If vote is tied, log **CONTESTED** and **do not fire Combo A**. Is that required for v1, or OK to ship with a TODO until backfill?

**Answer:** _______________________________________________

---

### Q5.10 — GSR ±5% for Combo A+

**Question:** Gold/Silver ratio 4-week change **above +5%** = fearful amplifier; **below −5%** = brave amplifier. v3 says threshold is **not yet backtested**. OK for v1 with TODO?

**Answer:** _______________________________________________

---

## 6. Unnamed combos (291 auto-discovered)

### Q6.1 — When to run all 298 combos

**Question:** Should the full combo loop run **every night** when data is available, or **only on Friday** after the full 12-variable pull?

**Why it matters:** v3 says “whenever nightly data is available”; older spec emphasized Friday alignment with CFTC.

**Answer:** _______________________________________________

---

### Q6.2 — Pre-filter before Claude

**Question:** Unnamed combos need **at least 3 past fires** and **≥60% hit rate** (3-month SPX up) before they appear in the briefing or go to Claude. Store weak combos as **BELOW_GATE** but hide from users. Correct?

**Answer:** _______________________________________________

---

### Q6.3 — Naming new combos

**Question:** Monthly, combos with ≥75% hit rate get sent to Claude for **naming**. Who approves new names before they go live?

**Answer:** _______________________________________________

---

## 7. Historical backfill

### Q7.1 — Is backfill required before go-live?

**Question:** Must we finish the **one-time historical backfill** (combo fires, forward returns, regime labels, percentiles) before production, or can we go live with **forward-only** data and backfill in parallel?

**Answer:** _______________________________________________

---

### Q7.2 — What backfill must include

**Question:** Confirm backfill must populate:
1. Every historical **combo fire** (298 logic over history)  
2. **SPX returns** 1w/1m/3m/6m after each fire  
3. **Regime labels** (5 dimensions) — including ~400 Claude calls for geo  
4. **Unconditional and regime percentiles** per variable per day  

Anything missing from this list?

**Answer:** _______________________________________________

---

### Q7.3 — Hit rate targets

**Question:** After backfill, if Combo B hit rate is not exactly **87%** or Combo F not **78%**, is that a blocker or acceptable first pass?

**Answer:** _______________________________________________

---

### Q7.4 — Where does the database live?

**Question:** Is SQLite `runic.db` on the **same AWS server**, or only on the dev machine? Size estimate for 35 years?

**Answer:** _______________________________________________

---

## 8. Claude API and nightly briefing

### Q8.1 — Model name

**Question:** Confirm production model string: **claude-sonnet-4-6** or another ID from the Anthropic console?

**Answer:** _______________________________________________

---

### Q8.2 — Who writes the briefing style?

**Question:** The nightly note must match the **sample PDF** (tables + 200–250 words). Is matching **Streamlit layout** enough for v1, or is a **PDF export** required?

**Answer:** _______________________________________________

---

### Q8.3 — Who picks “dominant signal”?

**Question:** When Combo C and Combo F are both active, v3 example says **C dominates** for tactical view. Should dominance stay **fixed rules in Python**, or should **Claude decide** each night?

**Answer:** _______________________________________________

---

### Q8.4 — Regime classifier on old dates

**Question:** For ~400 historical dates, we call Claude once for **geo_overlay** only (cheap batch). Fed/cycle/valuation can come from rules + FRED. OK?

**Answer:** _______________________________________________

---

## 9. UI, API, and Conviction Engine

### Q9.1 — FastAPI

**Question:** Do we need **REST API endpoints** (e.g. `/api/v1/macro/latest`) in v1, or is **JSON file + Streamlit page** enough?

**Answer:** _______________________________________________

---

### Q9.2 — Link to Conviction Engine

**Question:** Should the **Conviction Engine** page show Runic data (e.g. `vix_bypass`, dominant combo), or keep them **completely separate** as v3 suggests?

**Answer:** _______________________________________________

---

### Q9.3 — Canonical spec folder

**Question:** Spec PDFs exist in both `macro_intelligence_docs/` and `docs/api/`. Which folder is the **single source of truth**?

**Answer:** _______________________________________________

---

## 10. v1 scope — what must ship

### Q10.1 — Minimum go-live package

**Question:** Please mark each as **Must have v1** / **Can wait**:

| Item | v1? (Y/N) |
|------|-----------|
| Friday 12-variable pull + SQLite | |
| Named combos A–G (simplified OK?) | |
| Combo C cancel logic | |
| Combo A direction vote | |
| Full 298 combos + BELOW_GATE filter | |
| Dual percentiles (unconditional + regime) | |
| Historical backfill complete | |
| `runic_output.json` on AWS | |
| Real SSI `positioning.json` | |
| Tavily in narrative | |
| Gate tests Oct 2022 B + Jun 2020 F | |
| Streamlit Runic page | |
| PDF nightly report | |
| `recalibrate_thresholds.py` annual job | |
| Monthly threshold review email | |

**Answer:** (fill table in meeting)

---

### Q10.2 — Deadline and handoff

**Question:** What is the **hard deadline** for v1 on AWS? Is the **July 25** handoff to Ahil still firm?

**Answer:** _______________________________________________

---

## 11. Operations when things break

### Q11.1 — If Friday CFTC download fails

**Question:** Should the job **stop** (no JSON update), **use last week’s CFTC**, or **run without CFTC-dependent combos**?

**Answer:** _______________________________________________

---

### Q11.2 — If Claude API is down

**Question:** OK to use **template narrative** and **rule-based regime** until API returns?

**Answer:** _______________________________________________

---

### Q11.3 — If one Yahoo ticker fails

**Question:** Skip that variable for the day, or fail the entire run?

**Answer:** _______________________________________________

---

## 12. Missing things — detailed guide (files, data, code, fallbacks)

### What this section is for

The **Macro Intelligence Agent** (also called the **Runic Agent**) is a Python program that:

1. Downloads **12 macro economic indicators** (VIX, oil, credit spreads, Fed balance sheet, etc.) from public data sources.
2. Decides when the market is in an **extreme macro state** using rules called **combos** (labeled A through G, plus hundreds of auto-detected combinations).
3. Saves history in a **SQLite database** file (`macro_intelligence/data/runic.db`).
4. Writes one **JSON file** (`runic_output.json`) that the **C++ trading engine** reads to adjust position sizing and risk.
5. Optionally calls **Claude (Anthropic API)** to write a human-readable **nightly briefing** and to label geopolitical **regime** (war, pandemic, etc.).

**This section lists everything the specifications require that we do not yet have** — or only have partly. You do not need prior finance or coding knowledge to use it; each item explains terms the first time they appear.

**How to read each entry**

- **What it is** — plain definition  
- **What the spec says** — what Rohit’s documents require  
- **What exists today** — what is actually in the MindWealth_UI repo  
- **Why it matters** — what breaks if we never get it  
- **Questions for Rohit** — what you need from your manager  

**Status legend**

| Status | Meaning |
|--------|---------|
| **Missing** | Not in the repo, or not implemented at all |
| **Partial** | Some code exists but does not meet the spec |
| **Wrong** | Something exists but does not match v3 (May 28 note) |
| **Unclear** | Spec mentions it but does not give enough detail to build |

**Where things live in the repo (for your reference)**

| Path | What it is |
|------|------------|
| `macro_intelligence_docs/` | PDF/DOCX specifications from Rohit |
| `macro_intelligence/CONFIG.yaml` | Threshold numbers and data source tickers |
| `src/macro_intelligence/` | Python source code for the agent |
| `macro_intelligence/data/runic.db` | SQLite database (created when jobs run) |
| `macro_intelligence/output/runic_output.json` | Output file for C++ (created by nightly job) |
| `scripts/run_macro_friday_pull.py` | Command to run Friday data collection |
| `scripts/run_macro_nightly.py` | Command to build nightly JSON + briefing |

---

### 12.A — Missing documents and reference files

These are **written specifications, samples, or runbooks** — not program code. Without them, we guess column names, paths, and data formats.

---

#### 12.A.1 — `Macro_Intelligence_Agent_Spec.xlsx`

**What it is:** An Excel spreadsheet Rohit listed in the original May 26 email as attachment #5: “original variable list.” It likely contains the **official list of 12 variables**, IDs, thresholds, and combo slot assignments in tabular form.

**What the spec says:** “Read all attachments before writing a single line of code,” including this xlsx.

**What exists today:** **Missing** from the repository. We only have:

- `Divyanshu Instructions to Build Macro Intelligence agent.pdf`
- `Divyanshu_Addendum_MacroAgent.docx`
- `28_May_2026_Divyanshu_Runic_Integration_Note_v3.docx`
- `Runic_Agent_Combo_Cheatsheet_v2.pdf`
- Others in `macro_intelligence_docs/`

**Why it matters:** If the Excel file disagrees with the cheat sheet (different variable IDs, different thresholds), we may build the wrong logic and only discover it after go-live.

**Questions for Rohit:**

1. Please upload **`Macro_Intelligence_Agent_Spec.xlsx`** to the repo or shared drive.  
2. If it is obsolete, confirm in writing: **“The cheat sheet + v3 note replace the xlsx.”**  

**Answer:** _______________________________________________

---

#### 12.A.2 — Sample nightly briefing template (BTIG-style PDF)

**What it is:** The **exact layout** traders expect for the nightly macro note: title block, combo status table (ACTIVE / PARTIAL / WATCH), regime table, 200–250 word narrative, 12-row variable dashboard, one-line recommendation.

**What the spec says:** Claude’s nightly output must match `Runic_Sample_Nightly_Intelligence Briefing.pdf` in `macro_intelligence_docs/`.

**What exists today:** **Partial.** We have the **sample PDF** for humans to read. We do **not** have:

- An HTML/PDF **generator** in code  
- A fixed JSON structure that maps 1:1 to each table row in the PDF  
- Branding/fonts/BTIG layout assets  

The Streamlit page (`src/pages/runic_page.py`) shows a **simplified** view, not the full PDF layout.

**Why it matters:** Product may expect a downloadable PDF identical to the sample; today they only get JSON + a basic web page.

**Questions for Rohit:**

1. Is **PDF export** required for v1, or is Streamlit + JSON enough?  
2. If PDF is required, is there a **Word/InDesign template** or only the sample PDF?  

**Answer:** _______________________________________________

---

#### 12.A.3 — CFTC TFF column map (Commitments of Traders)

**What it is:** The **CFTC** (U.S. Commodity Futures Trading Commission) publishes weekly files called **TFF** (Traders in Financial Futures) that show how hedge funds, banks, and other groups are positioned in futures (including S&P 500). Variable #8 in Runic uses **net speculative positioning** from the **Leveraged Money** and **Asset Manager** columns.

**What the spec says (v3):** Pull from `CFTC.gov` — columns `Lev_Money_Positions` and `Asset_Mgr_Positions` (or similar). Compute **3-year percentile rank** for each column **separately**. Friday report ~3:30 PM ET reflects **Tuesday** positions → flag `PENDING_CFTC_CONFIRM` until confirmed.

**What exists today:** **Partial / risky.** File `src/macro_intelligence/data/cftc_pull.py` downloads annual zip files and searches for column names containing “Lev Money” and “S&P 500.” This has **not been validated** against a real Friday file Rohit approves.

**Why it matters:** Wrong column = wrong “extreme short” signal → Combo B, D, E, F fire incorrectly → trading engine gets wrong `vix_bypass` and risk signals.

**Questions for Rohit:**

1. Provide one **real CFTC TFF file** (or screenshot of header row) for S&P 500 e-mini.  
2. Confirm we need **two separate percentiles** (Leveraged Money net AND Asset Manager net), not one blended number.  
3. Confirm Friday JSON should show **`PENDING_CFTC_CONFIRM`** for combos that need CFTC when data is stale.  

**Answer:** _______________________________________________

---

#### 12.A.4 — CPI and PPI “surprise” data process

**What it is:**

- **CPI** = Consumer Price Index (inflation print).  
- **PPI** = Producer Price Index.  
- **Surprise** = `actual released number minus economist consensus forecast`, in **percentage points** (e.g. +0.3 pp hot).  
- Combo **C** (stagflation / energy shock) uses a hot CPI surprise as one of its three legs.  
- Combo **C cancel** uses “CPI not hot” as one of two legs to turn the signal off.

**What the spec says:** Actual from **BLS.gov**; consensus from **Investing.com** economic calendar. Store in new table `pending_releases`. If **no CPI/PPI published that week**, the CPI cancel leg **passes automatically** (v3).

**What exists today:** **Missing automation.**

- File: `macro_intelligence/data/cpi_surprises.csv` — **manual** CSV you edit by hand.  
- No scraper for BLS or Investing.com.  
- **PPI** not implemented at all.  
- Combo C cancel logic **not coded**, so CPI data is barely used.

**Why it matters:** Without a reliable weekly CPI/PPI process, Combo C may never fire correctly or never cancel when inflation cools.

**Questions for Rohit:**

1. Who will enter **consensus and actual** each release day (you, ops, automated vendor)?  
2. Is there a **paid API** (Bloomberg, Refinitiv, etc.) already licensed by the firm?  
3. Should **PPI** count the same as CPI for the cancel rule?  
4. Confirm: **no release that week = CPI leg passes** for cancel purposes.  

**Answer:** _______________________________________________

---

#### 12.A.5 — AWS server deployment runbook (51.20.53.218)

**What it is:** **AWS** = Amazon cloud server. v3 says production JSON is written to server IP **51.20.53.218**, **after Ahil’s C++ daily job finishes (~5:00 PM Eastern Time)**. A **runbook** is step-by-step instructions: how to SSH login, where files go, how to schedule cron, where logs are, who to call if it fails.

**What the spec says:** “Write the nightly JSON to the agreed filepath on the AWS server … sequential once-daily process.”

**What exists today:** **Missing.**

- No document with **full file path** (e.g. `/home/ubuntu/.../runic_output.json`).  
- No confirmed **SSH username**, key, or sudo rights for Divyanshu.  
- No installed **cron** on that server in repo instructions.  
- CONFIG still says `21:00 ET` cron — **conflicts** with v3 “~5pm after C++”.

**Why it matters:** Code can work on your laptop while **production trading never sees the file**.

**Questions for Rohit:**

1. Exact **directory path** for `runic_output.json` on 51.20.53.218.  
2. Exact **directory path** for `runic.db` (same server or different?).  
3. **SSH access** for Divyanshu — username, key, who provisions.  
4. Final schedule: **5pm after C++ only**, or also 9pm, or Mon–Fri vs Friday only?  
5. Does **Ahil** deploy Python, or Divyanshu, or DevOps?  

**Answer:** _______________________________________________

---

#### 12.A.6 — SSI system documentation and sample `positioning.json`

**What it is:**

- **SSI** = Sentiment SuperIndex — a **separate** Python agent (not built in your repo yet).  
- It writes **`positioning.json`** with a field like `ssi_multiplier` (1.0, 1.2, 0.8) based on four sentiment inputs (VIX term structure, HYG/LQD, DBMF beta, CNN Fear & Greed).  
- **Runic does not compute SSI**; it may **read** SSI’s output to fill `ssi_multiplier` in `runic_output.json`.  
- **C++** reads **both** JSON files at market open.

**What the spec says:** SSI and Runic are independent. Do not double-count HY spreads (FRED in Runic, HYG/LQD in SSI). Full test list is in `SSI_OpenQuestions_DivyanshuTestList (1).docx`.

**What exists today:** **Missing.**

- No `positioning.json` example in repo.  
- Code defaults `ssi_multiplier` to **1.0** if file absent (`src/macro_intelligence/output/json_writer.py`).  
- No SSI Python code in MindWealth_UI.  
- 15 SSI validation tests **not started** (separate workstream).

**Why it matters:** Until SSI exists, conviction/multiplier behavior in production is **neutral (1.0)** even when spec describes 1.2 / 0.8 rules.

**Questions for Rohit:**

1. Who owns **SSI** and what is the delivery date?  
2. Provide **sample `positioning.json`** with real field names C++ expects (including nested `signals.long.size_mult` if used).  
3. Full path on AWS for `positioning.json`.  
4. Should Divyanshu build SSI, or only Runic?  

**Answer:** _______________________________________________

---

### 12.B — Missing scripts, programs, and automated jobs

A **script** is a command you run (e.g. `python scripts/run_macro_nightly.py`). Below is each **named** job in the spec that is missing or incomplete.

---

#### 12.B.1 — `recalibrate_thresholds.py` (annual threshold review)

**What it is:** A command-line tool mentioned in v3: `python recalibrate_thresholds.py --confirm`. Once per year it would re-check whether combo thresholds (e.g. “VIX > 25”) are too loose or too tight using all data in `combo_fires` + `forward_returns`, suggest changes, and store results in `threshold_review_log`.

**What the spec says:** Automated monthly/annual review so thresholds do not need manual tuning after Divyanshu leaves (addendum A5). v3 adds annual cron + manual CLI trigger.

**What exists today:** **Missing file entirely.** Related: `src/macro_intelligence/jobs/monthly_threshold_review.py` is a **minimal stub** (no email, no Claude suggestions, no approval links).

**Why it matters:** Without this, threshold drift is invisible until trading performance degrades.

**Questions for Rohit:**

1. Required for **v1** or year-one maintenance only?  
2. Should suggested changes auto-apply after Rohit clicks approve, or always manual CONFIG.yaml edit?  

**Answer:** _______________________________________________

---

#### 12.B.2 — Tavily news integration

**What it is:** **Tavily** is a web search API service. v3 lists it under “Tavily / scheduled jobs” for **real-time news context** for the narrative — **not** for combo math (combo math must stay Python/SQL only).

**What the spec says:** Use Tavily for narrative context; do not use LLM for variable pulls or combo detection.

**What exists today:** **Missing.** No Tavily API key, no module, no injection into `nightly_briefing.py`. Chatbot elsewhere in repo uses Tavily for a different feature — not wired to Runic.

**Why it matters:** Nightly briefing may lack timely references (e.g. “Iran deal”, “Fed speaker”) that the sample PDF implies.

**Questions for Rohit:**

1. Is Tavily **required for v1**?  
2. Provide **API key** and list of **search queries** or topics.  
3. Max **cost per month** acceptable?  

**Answer:** _______________________________________________

---

#### 12.B.3 — Combo C cancel checker (Friday job step)

**What it is:** After Combo C is **ACTIVE**, v3 defines when it turns **off**:

- **WTI leg:** 4-week oil change **below +5%** for **4 consecutive Fridays** (can be negative; up to +4.99% still counts as “below +5% gate”).  
- **CPI leg:** actual ≤ consensus (“not hot”), OR no CPI/PPI that week → pass.  
- If **any** Friday fails either leg → counter **resets to zero**.  
- Track progress in `wti_potential_week` (0–4) in table `combo_c_cancel`.

**What the spec says:** Friday checklist step: “Run Combo C cancel check — if C active …”

**What exists today:** **Missing.** Combo C **fire** logic exists in `combo_detector.py`. **Cancel**, `combo_c_cancel` table, `wti_potential_week`, and `pending_cpi_release` in JSON are **not implemented**.

**Why it matters:** Cheat sheet (May 26) says oil has cooled and cancel is “approaching” — without cancel logic, JSON may show Combo C **ACTIVE** forever.

**Questions for Rohit:**

1. Confirm cancel rules above are **final for v1**.  
2. Is cancel a **go-live blocker**?  

**Answer:** _______________________________________________

---

#### 12.B.4 — Combo A BRAVE / FEARFUL direction voter

**What it is:** Combo **A** = “Global Liquidity / FCI Regime.” It needs a label **BRAVE** (risk-on liquidity) or **FEARFUL** (risk-off), not just “combo fired.” v3 defines a **vote** across four inputs with placeholder rules:

| Input | BRAVE (example) | FEARFUL (example) |
|-------|-----------------|-------------------|
| NFCI | ≤ −0.3 (easy) | ≥ +0.3 (tight) |
| HY OAS | 4wk tightening ≤ −20 bps | widening ≥ +20 bps |
| WALCL | MoM ≥ +0.8% (QE) | MoM ≤ −0.8% (QT) |
| USD/CNH | 4wk ≤ −1.5% | 4wk ≥ +1.5% |

**Vote rule:** If ≥2 brave and brave > fearful → **BRAVE**. If ≥2 fearful and fearful > brave → **FEARFUL**. Else → **CONTESTED** → **do not fire Combo A**; log `CONTESTED` in `combo_fires`.

**GSR modifier (A+):** If gold/silver ratio 4wk change **> +5%** → `FEARFUL_AMP`; **< −5%** → `BRAVE_AMP` (amplifier on Combo A, not a separate combo).

**What exists today:** **Missing.** Combo A fires if ≥2 of 4 variables are RARE+ without direction vote. No `CONTESTED` status. No GSR modifier fields.

**Why it matters:** Trading may treat “Combo A” without knowing if liquidity supports risk-on or risk-off.

**Questions for Rohit:**

1. Is direction vote **v1 required** or post-backfill TODO acceptable?  
2. Confirm **±20 bps** HY placeholder until backtest.  

**Answer:** _______________________________________________

---

#### 12.B.5 — Futures rollover flagger (WTI and silver)

**What it is:** **Futures contracts** (WTI oil `CL=F`, silver `SI=F`) expire monthly; price **jumps** on rollover day. A 4-week change can look like a huge move because of **contract switch**, not real market move.

**What the spec says:** Flag any 4-week window that contains a silver or WTI rollover; **review manually** (v3 §2).

**What exists today:** **Missing.** No calendar of rollover dates, no warning in JSON/logs.

**Why it matters:** False Combo C fire or false cancel on bad oil math.

**Questions for Rohit:**

1. Should engine **block** signals on rollover weeks or only **warn** in JSON?  
2. Who performs manual review — you daily, or Rohit weekly?  

**Answer:** _______________________________________________

---

#### 12.B.6 — Full historical backfill (35+ years)

**What it is:** A **one-time** (then incremental) process to run the engine backwards from ~1990 (or earliest data) to today and fill:

1. **`combo_fires`** — every date each combo would have triggered  
2. **`forward_returns`** — SPX return 1w/1m/3m/6m after each fire  
3. **`macro_regime_log`** — five regime labels per date (geo often via Claude batch ~400 calls)  
4. **`daily_readings`** with **`unconditional_pctile`** and **`regime_pctile`** per variable per day  

**What the spec says:** “Historical backfill” is how hit rates (e.g. “Combo B 87%”) become **real** instead of guesses. Geo backfill ~$0.50 total API cost.

**What exists today:** **Partial.**

- Script exists: `scripts/backfill_macro_history.py`  
- **Not run** to completion on full history  
- No `unconditional_pctile` / `regime_pctile` columns in DB  
- `analog_dates` and `spx_3m_hit_rate` in live JSON are often **empty/null**

**Why it matters:** UI and JSON cannot show trustworthy hit rates or “closest historical analog” until backfill finishes.

**Questions for Rohit:**

1. Is backfill **blocking go-live**?  
2. Run on **AWS** or developer laptop? Expected **runtime** (hours/days)?  
3. Who pays for **Claude geo batch** on ~400 dates?  

**Answer:** _______________________________________________

---

#### 12.B.7 — PDF / HTML nightly report generator

**What it is:** Program that outputs a formatted report matching the sample PDF (not just JSON).

**What exists today:** **Missing** (see 12.A.2).

**Answer:** _______________________________________________

---

### 12.C — Missing database tables and columns (SQLite)

**What SQLite is:** A single file database (`runic.db`) storing time series and combo history. The C++ engine does **not** read SQLite — only JSON. SQLite is for **research, hit rates, and UI history**.

---

#### 12.C.1 — Table `signal_fires` (no data written)

**What it is:** One row each time a **single** variable crosses into **RARE** or **EXTREME** (with direction UP/DOWN and weeks in tier).

**Spec:** Addendum A2 — store direction for future v2 hit rates.

**Today:** Table defined in `schema.sql`. **No Python code inserts rows.**

**Question:** Do we need this table for v1, or is `daily_readings` enough?

**Answer:** _______________________________________________

---

#### 12.C.2 — Table `rule_library` (empty)

**What it is:** Pre-validated named rules with hit rates (e.g. “Combo B bullish 3m hit rate 87%”).

**Today:** Table exists, **never populated**.

**Answer:** _______________________________________________

---

#### 12.C.3 — Table `thresholds` (empty)

**What it is:** DB copy of RARE/EXTREME thresholds per variable. Today thresholds live only in **`macro_intelligence/CONFIG.yaml`**, not in SQL.

**Answer:** _______________________________________________

---

#### 12.C.4 — v3 columns missing on `combo_fires`

| Column | What it stores |
|--------|----------------|
| `combo_legs_confirmed` | For Combo E: `2` or `3` legs confirmed |
| `cftc_status` | `CONFIRMED` vs `PENDING_3DAY_LAG` |
| `gsr_4wk_pct` | Gold/silver ratio 4-week % change at fire date |
| `gsr_modifier` | `FEARFUL_AMP`, `BRAVE_AMP`, or `NEUTRAL` |
| `var1_direction`, `var2_direction`, `var3_direction` | v3 A2 — UP/DOWN per variable (schema may lack these — verify) |

**Today:** **Not in schema** / not written.

**Answer:** _______________________________________________

---

#### 12.C.5 — Table `combo_c_cancel` (entire table missing)

**What it is:** Tracks Combo C cancel progress, especially `wti_potential_week` (0–4 consecutive clean Fridays).

**Today:** **Table not created** in schema.

**Answer:** _______________________________________________

---

#### 12.C.6 — Table `pending_releases` (entire table missing)

**What it is:** Stores each CPI/PPI release: actual, consensus, surprise, which Friday applied it.

**Today:** **Table not created**; manual CSV only.

**Answer:** _______________________________________________

---

#### 12.C.7 — Dual percentile columns on `daily_readings`

**What it is (important — v3 changed the rules):**

- **`unconditional_pctile`** — today’s value vs **all history** since variable inception (VIX from 1990, CAPE from 1881, etc.). Used for **combo detection**.  
- **`regime_pctile`** — today’s value vs history only when **`fed_cycle`** matches today (e.g. only “cutting” years). Used for **conviction modifier** and regime-adjusted stats. If &lt; 50 regime days → fall back to unconditional and log.

**Today:** Only one column `pctile_rank_3yr` (name is misleading — not always 3-year).

**Answer:** _______________________________________________

---

#### 12.C.8 — `macro_regime` JSON on each `combo_fires` row

**What it is:** When a combo fires, store `{"fed_cycle":"...","curve_regime":"...", ...}` on that row for later SQL (“hit rate in cutting cycles only”).

**Today:** Column exists sometimes; **not consistently filled** on fire.

**Answer:** _______________________________________________

---

### 12.D — Missing fields in `runic_output.json`

**What JSON is:** The nightly file the trading engine reads. Example path: `macro_intelligence/output/runic_output.json`.

Below: each **missing or incomplete field**, what it means, and who consumes it.

---

#### 12.D.1 — `pending_cpi_release`

**Meaning:** CPI was released after the engine ran; apply surprise to **next** Friday’s Combo C cancel check.

**Today:** **Missing.**

**Answer:** _______________________________________________

---

#### 12.D.2 — `cftc_status` / `PENDING_CFTC_CONFIRM`

**Meaning:** On Friday, Combo B/D/E/F that need CFTC may be provisional until Tuesday-aligned data arrives.

**Today:** **Missing.**

**Answer:** _______________________________________________

---

#### 12.D.3 — Combo status strings: `CONFIRMED`, `CONFIRMED_3_OF_3`, `PARTIAL`, `CONTESTED`, `WATCH`

**Meaning (example Combo E):**

- **PARTIAL** = only 1 of 3 legs (old spec mistake).  
- **CONFIRMED** = 2 of 3 (v3: CAPE extreme + NFCI easy).  
- **CONFIRMED_3_OF_3** = CFTC also >80th percentile on Friday.  

**Today:** Code uses `ACTIVE`, `PARTIAL`, `WATCH` only — not v3 full set.

**Answer:** _______________________________________________

---

#### 12.D.4 — Regime `_source` fields

**Meaning:** e.g. `"curve_regime_source": "T10Y2Y"` so UI shows **which data series** set the label.

**Today:** **Missing.**

**Answer:** _______________________________________________

---

#### 12.D.5 — Per-variable `unconditional_pctile` and `regime_pctile` in dashboard

**Meaning:** Sample PDF shows percentile per variable; v3 wants **two** ranks exposed.

**Today:** `variables_dashboard` has one `pctile_3yr` field only.

**Answer:** _______________________________________________

---

#### 12.D.6 — `gsr_modifier` on combo / global context

**Meaning:** `FEARFUL_AMP` / `BRAVE_AMP` / `NEUTRAL` for Combo A+.

**Today:** **Missing.**

**Answer:** _______________________________________________

---

#### 12.D.7 — `combo_c_cancel` / `wti_potential_week` in JSON

**Meaning:** Traders see “week 2 of 4 toward Combo C cancel.”

**Today:** **Missing.**

**Answer:** _______________________________________________

---

#### 12.D.8 — Rich combo table (hit rate, avg return, duration) like sample PDF

**Meaning:** Each active combo row shows 3m hit rate, avg 3m SPX return, duration bucket — from backfill.

**Today:** Partial fields; often null without backfill.

**Answer:** _______________________________________________

---

#### 12.D.9 — Approved JSON schema document

**Question:** Please provide one **master list** of every JSON key, type, and allowed enum values for C++, Python, and Streamlit.

**Answer:** _______________________________________________

---

### 12.E — Missing engine logic (detailed)

---

#### 12.E.1 — Full 298-combo loop with `BELOW_GATE` filter

**What it is:**

- **298 combos** = all combinations of the 12 variables at RARE/EXTREME at the same time (singles + pairs + triples).  
- **7 named** (A–G) have special rules.  
- **291 unnamed** are auto-discovered.  
- v3: unnamed combo only surfaces if **≥3 historical fires** and **≥60%** 3-month SPX hit rate; else tag **`BELOW_GATE`** (store but hide from briefing/Claude).

**Today:** Generic combos generated in `detect_generic_combos()` but **not** fully integrated into nightly gating or Claude cost control.

**Answer:** _______________________________________________

---

#### 12.E.2 — Regime-adjusted hit rate SQL

**What it is:** Example: “Combo B hit rate **only in Fed cutting cycles**” = filter `macro_regime.fed_cycle` LIKE `CUT%`.

**Today:** Function `hit_rates.py` exists; **data sparse** without backfill + regime on rows.

**Answer:** _______________________________________________

---

#### 12.E.3 — Analog date finder

**What it is:** Closest past dates when similar combos/regime fired, with forward returns (e.g. June 2008, June 2022).

**Today:** `find_analog_dates()` often returns **[]** empty.

**Answer:** _______________________________________________

---

#### 12.E.4 — Dominant signal resolver (C vs F vs E)

**What it is:** When multiple combos active, one **dominant** drives narrative and `brave_fearful` label (e.g. `TACTICAL_FEARFUL_STRATEGIC_BRAVE`).

**Today:** Simple rules in `dominant.py` — may not match cheat sheet May 26 live example.

**Answer:** _______________________________________________

---

#### 12.E.5 — Combo F — wrong test date and incomplete lifecycle

**What it is:**

- v3 validation: **June 8, 2020** (+6.2% week), 26-week window ends **Dec 14, 2020**.  
- May 26 email said **June 29, 2020**.  
- Cheat sheet: **March 30, 2026** active F week 8.  

**Today:** Tests use **June 29**. Week counter often **null**. Invalidate F if SPX below 50WMA reclaim — **not coded**.

**Answer:** _______________________________________________

---

#### 12.E.6 — Combo F + D + B interaction rules

**What it is (v3):**

- D + F: tighten stops, no new longs, hold core — narrative/policy.  
- B + F while SPX above F entry: **reinforcing add**, not cut size.  

**Today:** **Not in JSON** for C++.

**Answer:** _______________________________________________

---

#### 12.E.7 — GSR ticker: `GOLD` vs `GC=F`

**What it is:** v3 requires Yahoo ticker **`GOLD`** (spot gold). Code uses **`GC=F`** (gold futures) in `yahoo_pull.py` / CONFIG.

**Today:** **Wrong** per v3.

**Answer:** _______________________________________________

---

#### 12.E.8 — WTI 4-week formula

**What it is:** v3: `(today − price 28 calendar days ago) ÷ price 28 days ago` (document as percent change for thresholds).

**Today:** ~20 **trading** days in `rolling_pct_change` — not identical to 28 **calendar** days.

**Answer:** _______________________________________________

---

#### 12.E.9 — HY 4-week change for Combo A/G

**What it is:** Combo A direction needs HY **widening/tightening in bps over 4 weeks**, not just level >400 bps.

**Today:** Level-based HY for Combo B; **4wk HY delta** for A/G **missing**.

**Answer:** _______________________________________________

---

#### 12.E.10 — CFTC Asset Manager separate percentile

**What it is:** Two percentiles — fast money (lev) and slow money (asset mgr).

**Today:** Parser tries to find lev money; **asset mgr separate percentile not implemented**.

**Answer:** _______________________________________________

---

### 12.F — Missing data sources, API keys, and credentials

Each row: what you need to download or authenticate.

| Item | What it is | Spec source | Today | If missing, what happens |
|------|------------|-------------|-------|-------------------------|
| **FRED_API_KEY** | Free API key from Federal Reserve Economic Data (St. Louis Fed) for NFCI, HY OAS, WALCL, T10Y2Y, optional CAPE | v3 §2 primary | Not in prod `.env` | Fallback CSV ~**3 years** only — breaks long backtest |
| **ANTHROPIC_API_KEY** | Pays for Claude regime + narrative | v3 § Claude | Optional locally | Template text + hardcoded regime map for 5 dates |
| **TAVILY_API_KEY** | Web news search API | v3 architecture | Missing | No news in briefing |
| **SSI_POSITIONING_JSON** | Path to SSI output file | Addendum A6 | Missing | `ssi_multiplier` = 1.0 always |
| **MACRO_INTEL_JSON_PATH** | Override output path | Config | Default local path only | C++ may read wrong file on AWS |
| **MACRO_INTEL_DB** | Override DB path | Config | Default local | — |
| Yahoo **GOLD** | Spot gold ticker | v3 | Using **GC=F** | Wrong GSR |
| FRED **MULTPL_CAPE** | CAPE series ID on FRED | v3 fallback | Not coded | multpl failure = no CAPE |
| FRED **DCOILWTICO** | Continuous WTI | v3 cross-check | Not coded | Rollover noise on CL=F |
| **BLS CPI actual** | Official inflation release | v3 | Manual CSV | Combo C broken |
| **Investing.com consensus** | Forecast number | v3 | Missing | Cannot compute surprise |
| **PPI** | Producer prices | v3 cancel context | Missing | Cancel incomplete |
| **multpl.com** | CAPE website scrape | v3 primary | Scrape + cache | Monthly only; fragile |
| **CFTC zip files** | Weekly positioning | v3 | Untested parser | CFTC combos unreliable |

**Question:** Provide filled `.env.example` with every key and who owns each subscription.

**Answer:** _______________________________________________

---

### 12.G — Missing fallback policies (what to do when data fails)

A **fallback** is the rule when the primary data source fails.

| # | Situation | What v3 says | What code does now | What we need Rohit to decide |
|---|-----------|--------------|-------------------|------------------------------|
| 1 | No FRED API key | Prefer FRED API | Downloads short CSV | Blocker or OK for v1? |
| 2 | No CPI this week | CPI cancel leg **passes** | Not implemented | Confirm |
| 3 | No PPI this week | Unclear | Nothing | Same as CPI? |
| 4 | CFTC download fails | Not specified | Empty/error | Stop JSON? Use last week? Skip CFTC combos? |
| 5 | multpl.com down | Use FRED MULTPL_CAPE | Cache/old file | Keep last CAPE how many days? |
| 6 | Claude API down | Not specified | Template briefing | OK for prod? |
| 7 | Regime sample &lt; 50 days | Use unconditional | Not implemented | Log warning in JSON? |
| 8 | One Yahoo ticker fails | Not specified | May error partially | Skip that variable only? |
| 9 | SSI file missing | Not specified | multiplier 1.0 | Correct until SSI live? |
| 10 | WTI/SI rollover week | Manual review | No flag | Block combo or warn only? |
| 11 | Friday CFTC pending | `PENDING_CFTC_CONFIRM` | Not in JSON | Show pending; `vix_bypass` on or off? |
| 12 | Partial Friday pull (e.g. 9/12 vars) | Not specified | May write incomplete JSON | Fail entire job? |
| 13 | SQLite locked/corrupt | Not specified | Job crash | Alert who? |
| 14 | AWS disk full | Not specified | Write fails | — |

**Master question:** Default policy = **fail loud** (do not update JSON) or **best-effort** (publish with `warnings: [...]` array)?

**Answer:** _______________________________________________

---

### 12.H — Missing tests and validation (detailed)

**What unit tests are:** Automated checks in `tests/test_*.py` that run on every code change.

| Test | Spec requirement | Current state | Gap |
|------|------------------|---------------|-----|
| Combo B Oct 13, 2022 | VIX 33.6, HY >400, CFTC <15th; `vix_bypass` | Logic tests pass; live HY needs FRED | v3 HY ~580 vs old ~614 |
| Combo F date | **Jun 8, 2020** (v3) | Tests use **Jun 29, 2020** | **Wrong date** |
| Combo F Mar 30, 2026 | Cheat sheet live example | No test | — |
| 5 regime dates | Oct 2022, Mar/Jun 2020, Dec 2015, Sep 2024 | Heuristic only | Claude live test optional |
| Backfill hit rate B ~87% | After backfill | Never run | — |
| Backfill hit rate F ~78% | After backfill | Never run | — |
| Friday all 12 variables | v3 checklist | No integration test | — |
| CFTC real file parse | v3 | No test file | — |
| JSON schema validation | C++ needs stable shape | None | — |
| `BELOW_GATE` filter | v3 pre-filter | None | — |
| Combo C cancel counter | 4 Fridays | None | — |

**Questions:**

1. Update all tests to **June 8, 2020**?  
2. Minimum tests before AWS deploy?  

**Answer:** _______________________________________________

---

### 12.I — Missing operations, monitoring, and handoff

| Item | Explanation | Status |
|------|-------------|--------|
| **Cron on AWS** | Scheduled automatic run (Linux cron). Friday pull + nightly JSON. | Not documented as installed |
| **Log files** | Where stdout/errors go on server. | Missing |
| **Alerts** | Email/Slack if job fails. | Missing |
| **Monthly email review** | v3 A5 — threshold suggestions to Rohit. | Stub only |
| **Approval links** | One-click approve threshold changes. | Missing |
| **Ahil handoff** | Ahil must restart jobs after July 25. | Not confirmed |
| **Postgres plan** | Move from SQLite to Postgres/RDS later. | No timeline |
| **FastAPI endpoints** | HTTP API for macro JSON (optional in plan). | Not built |
| **Version pinning** | Python package versions on server. | requirements.txt exists; server install unclear |

**Question:** If job fails Friday 4pm, who is paged?

**Answer:** _______________________________________________

---

### 12.J — Master checklist for Rohit (mark each item)

Ask Rohit to write **Provide**, **Not v1**, or **Later** next to each line.

**Documents & access**

- [ ] `Macro_Intelligence_Agent_Spec.xlsx`  
- [ ] CFTC sample file + column names  
- [ ] CPI/PPI actual + consensus process  
- [ ] AWS SSH + exact paths on 51.20.53.218  
- [ ] Sample `positioning.json` + SSI owner  
- [ ] Approved `runic_output.json` field list  
- [ ] BTIG PDF template (if required)  

**API keys & env**

- [ ] `FRED_API_KEY`  
- [ ] `ANTHROPIC_API_KEY` (billing enabled)  
- [ ] `TAVILY_API_KEY` (if v1)  
- [ ] `.env.example` for production  

**Code & logic (blockers?)**

- [ ] Historical backfill before go-live  
- [ ] Combo C cancel (4 Fridays + CPI/PPI)  
- [ ] Dual percentiles (unconditional + regime)  
- [ ] Combo A direction vote + CONTESTED  
- [ ] Fix Combo F test → **June 8, 2020**  
- [ ] Switch GSR to Yahoo **GOLD**  
- [ ] CFTC pending + Asset Mgr percentile  
- [ ] `recalibrate_thresholds.py`  
- [ ] Tavily in narrative  

**Database**

- [ ] Add v3 tables: `pending_releases`, `combo_c_cancel`  
- [ ] Add v3 columns on `combo_fires`, `daily_readings`  
- [ ] Populate `signal_fires` (Y/N)  

**Policy**

- [ ] Fail loud vs best-effort JSON  
- [ ] 5pm after C++ vs 9pm schedule  
- [ ] `vix_bypass` when CFTC pending  

**Rohit’s notes:** _______________________________________________

---

## Meeting notes (fill in during call)

| Topic | Decision |
|-------|----------|
| JSON path on AWS | |
| Run time (5pm vs 9pm) | |
| Combo F date | |
| Percentile windows | |
| v1 scope tier | |
| SSI owner | |
| Backfill gate | |
| FRED / Tavily keys | |
| Missing items (Section 12) | |

**Attendees:** _______________  
**Date:** _______________

---

## Related documents

- [macro_intelligence_open_questions.md](./macro_intelligence_open_questions.md) — technical gap analysis  
- [macro_intelligence_docs/28_May_2026_Divyanshu_Runic_Integration_Note_v3.docx](../../macro_intelligence_docs/28_May_2026_Divyanshu_Runic_Integration_Note_v3.docx) — latest spec (takes precedence)  
- [macro_intelligence/SYSTEM_DOCUMENTATION.md](../../macro_intelligence/SYSTEM_DOCUMENTATION.md) — how to run jobs today  

---

*End of questions document.*
