# Macro Intelligence Agent (Runic v2.2) — Open Questions & Alignment Gaps

**Purpose:** Capture everything that is ambiguous, missing, or only partially implemented so Divyanshu can review with Rohit (and Ahil where noted) before production go-live.

**Related docs:**
- Build plan: `.cursor/plans/macro_intelligence_agent_7469f641.plan.md` (do not edit unless updating the plan itself)
- Spec corpus: `macro_intelligence_docs/` (primary) and copies under `docs/api/`
- Implementation: `src/macro_intelligence/`, `macro_intelligence/CONFIG.yaml`
- Maintenance: `macro_intelligence/SYSTEM_DOCUMENTATION.md`, `macro_intelligence/README_MAINTENANCE.md`

**Last updated:** 2026-05-29 (added §15 — Integration Note v3, May 28)

---

## Executive summary

The Runic Agent v2.2 is **implemented as a working scaffold**: data pulls, SQLite schema, named combos A–G (simplified rules), persistence streaks, nightly JSON, Streamlit page, gate unit tests, and Claude hooks (with heuristic fallback).

It is **not yet production-complete** relative to the full PDF/DOCX specification. Several items are architectural (paths, SSI ownership), several are data-feed (FRED key, CPI, CFTC), and several are engine features (Combo C cancel, full backfill, signal_fires population, BTIG-formatted report).

**Use this document in a single meeting** to lock v1 scope, paths, owners, and release criteria.

---

## 1. C++ integration and JSON contract

### What the spec says

| System | Output file | Write schedule | Consumer |
|--------|-------------|----------------|----------|
| SSI (separate) | `positioning.json` | 08:00 ET daily | C++ at market open |
| Runic (this build) | `runic_output.json` | 21:00 ET Mon–Fri | C++ at market open |

Addendum A6 — C++ pseudocode:

```cpp
auto ssi   = read_json("positioning.json");
auto runic = read_json("runic_output.json");
float size_mult = 1.0f;
if (!runic["vix_bypass"].get<bool>()) {
    size_mult = ssi["signals"]["long"]["size_mult"].get<float>();
}
```

When `vix_bypass == true` (Combo B active), **do not reduce size** via the VIX/SSI multiplier — prevents the “Dalio Oct 2022” error (cutting size at the market bottom).

### What we implemented

- Default path: `macro_intelligence/output/runic_output.json` (override via `MACRO_INTEL_JSON_PATH`)
- JSON includes `vix_bypass`, `ssi_multiplier`, `regime`, `active_combos`, `narrative`, etc.
- `ssi_multiplier` reads optional `SSI_POSITIONING_JSON`; **defaults to 1.0** if missing

### Gaps / questions for manager

1. **Absolute production path** for both JSON files on the MindWealth/C++ host.
2. Confirm C++ field names match exactly (`vix_bypass` vs `vix_regime_bypass`, nested `ssi` structure).
3. Who deploys/copies JSON across machines if Python runs on a different host than C++?
4. Atomic write semantics — we use temp file + rename; confirm C++ handles partial reads (e.g. read only if mtime stable).

**Decision needed:** Path map + schema sign-off from C++ owner.

---

## 2. SSI vs Runic — scope and ownership

### What the spec says

- **Two independent Python systems**, each writing one JSON file.
- **SSI Confidence Multiplier** (after a combo fires):
  - CONFIRMED (≥2 of 4): ×1.20
  - PARTIAL (1 of 4): ×1.00
  - UNCONFIRMED (0 of 4): ×0.80
- Four SSI inputs: VIX/VIX3M ratio, HYG/LQD ratio, DBMF 21d beta vs SPY, CNN Fear & Greed
- **Overlap rules (critical):**
  - HY OAS (FRED) → Runic only
  - HYG/LQD → SSI only
  - VXTS → Runic combos D/G only; **exclude from SSI Layer 2** to avoid double-counting

Combo F: VIX bypass also when **SSI confirms** (≥2 of 4) — ties Runic to SSI readiness.

### What we implemented

- Runic only; SSI is a **read stub** for `ssi_multiplier`
- No SSI agent in this repo
- SSI open-questions doc (15 tests) is **out of scope** for Runic v1 except as future input

### Gaps / questions for manager

1. **Who builds SSI?** (Ahil? separate repo? same repo later?)
2. Timeline for real `positioning.json` — Runic cannot apply SSI multiplier logic until then.
3. Confirm **Combo F bypass** requires SSI confirmation — implement in C++ only, or should Runic set `vix_bypass` when F + SSI confirmed?
4. Is the **15-test SSI validation grid** (Part 9 of SSI doc) a prerequisite for go-live or parallel workstream?

**Decision needed:** RACI matrix: Runic vs SSI vs C++ vs UI (Parth).

---

## 3. Data sources and credentials

### Variable pull matrix (from spec + Friday pull list)

| # | Variable | Source | Implementation status |
|---|----------|--------|------------------------|
| 1 | NFCI | FRED | Implemented; full history needs `FRED_API_KEY` for API |
| 2 | HY OAS | FRED BAMLH0A0HYM2 | Implemented; public CSV ~3y without API key |
| 3 | WALCL MoM | FRED | Implemented |
| 4 | USD/CNH 4wk | Yahoo USDCNH=X | Implemented |
| 5 | WTI 4wk | Yahoo CL=F | Implemented |
| 6 | VIX | Yahoo ^VIX | Implemented |
| 7 | VIX3M/VIX | Yahoo ^VIX3M, ^VIX | Implemented (from 2007) |
| 8 | CFTC Fast Money | CFTC TFF zip | Best-effort parser; **needs Friday validation** |
| 9 | 10Y-2Y | FRED T10Y2Y | Implemented |
| 10 | CPI surprise | BLS vs consensus | **Manual CSV cache only** |
| 11 | GSR 4wk | Yahoo GC/SI | Implemented |
| 12 | CAPE | multpl.com | Scrape + `cape_history.csv` cache |

### Percentile windows (addendum A4b)

Not all variables use a 3-year rolling window. Example:

| Variable | History for percentile |
|----------|------------------------|
| NFCI, CAPE, 10Y-2Y | Full history (from listed start year) |
| VIX | 1990+ |
| VIX3M/VIX | 2007+ |
| HY OAS | 1996+ |
| CFTC | 2006+ |
| WTI, GSR, CNH, WALCL, CPI | 3-year rolling |

**UI should show these start dates** so users do not compare a “95th percentile VIX” (since 1990) with “95th percentile CAPE” (since 1881) as equivalent evidence.

### Gaps / questions for manager

1. **`FRED_API_KEY`** — will ops provide for production? Required for Oct 2022 HY validation on full history.
2. **CPI consensus** — official vendor (Investing.com, Bloomberg, internal)? Who updates on release days?
3. **CFTC column names** — confirm Lev_Money / Asset_Mgr columns for S&P futures in current TFF files.
4. **`Macro_Intelligence_Agent_Spec.xlsx`** — still missing; do variable IDs match `CONFIG.yaml`?
5. **Scraper failure policy** — fail the Friday job loudly vs last-known-good?

**Decision needed:** Approved data vendor list + API key provisioning.

---

## 4. Signal engine — spec vs implementation

### 4.1 Named combos A–G

| Combo | Spec intent | Implementation notes |
|-------|-------------|----------------------|
| **A** | ≥2 of 4 (FCI, HY, WALCL, CNH) at RARE+; FCI+HY direction aligned | Simplified: counts RARE+ legs only; **direction alignment not fully coded** |
| **B** | ALL: VIX>25, HY>400bps, CFTC<15th; WATCH if 1–2 | Fire + WATCH implemented; gate tests pass |
| **C** | WTI +10% 4wk, CPI hot, WALCL flat; duration buckets; **cancel rule** | Fire + duration bucket partial; **cancel NOT implemented** |
| **D** | VXTS>1.10, CFTC>85th, VIX<18; tactical | Partial/WATCH logic present |
| **E** | 2 of 3: CAPE>28, NFCI easy, CFTC>80th | Implemented (PARTIAL vs ACTIVE) |
| **F** | 50WMA reclaim +3% weekly, CFTC≤50th, 26-week window | Detection + tests; **weeks elapsed / expiry weak** |
| **G** | VXTS<1.0, HY widen 30bps/4wk, VIX<20 | Simplified (HY widening not fully from OAS delta) |

### 4.2 298 unnamed combos

- Spec: 12C1 + 12C2 + 12C3 = 298 combinations; auto-discover at runtime.
- Pre-filter (addendum A4c): store all fires; surface only if **≥3 historical fires AND ≥60% hit rate** (`spx_3m` complete); else `BELOW_GATE`.
- Monthly: unnamed combos with ≥75% hit rate → candidate for Claude naming.

**Gap:** Generic combo enumeration exists; pre-filter and `BELOW_GATE` persistence are **not fully wired** to nightly output and Claude calls.

### 4.3 Persistence engine (addendum A1)

Rules: `7WK_GRIND`, `3WK_SURGE`, `VIX_SUPPRESSED`, `HY_GRIND_TIGHT`, `FCI_EASING_STREAK`, `OIL_VOLATILE`.

- Table `persistence_fires` + weekly scan: **implemented**
- JSON `persistence_signals`: **included in nightly output**
- **Not implemented:** join persistence × combo_fires for “persistence combos”

### 4.4 `signal_fires` table

Spec: per-variable RARE/EXTREME crossings with `direction` (UP/DOWN), `weeks_in_tier`.

- Schema: **yes**
- Writer module: **no** — daily_readings exist but signal_fires is not populated

### 4.5 VIX_REGIME_BYPASS

- Constant + `compute_vix_bypass()` + JSON field: **yes**
- Documented in `CONFIG.yaml`: **yes**
- Combo F + SSI confirm path: **partial** (flag only if SSI external logic exists)

### Questions for manager

1. v1 go-live: **named combos only** or full 298 + pre-filter?
2. **Combo C cancel** — required for v1? (affects whether Combo C stays ACTIVE when oil falls)
3. **Combo A direction alignment** — exact definition (both tightening vs both easing)?
4. Should **Combo G** use HY OAS 4-week change in bps (spec) vs proxy from level?

---

## 5. Claude API integration

### Two call sites (spec §5)

| Call | Purpose | Implementation |
|------|---------|----------------|
| Regime classifier | 5 JSON dimensions per fire date | `regime_classifier.py`; heuristic map for 5 validation dates |
| Nightly briefing | 200–250 words, 4-part structure | `nightly_briefing.py`; template fallback without API key |

### Validation dates (must pass before 400-date backfill)

| Date | Expected (fed / curve / geo / val) |
|------|-------------------------------------|
| 2022-10-13 | HIKING_LATE / INVERTED / SANCTIONS / ELEVATED |
| 2020-03-23 | QE / NORMAL / PANDEMIC / ELEVATED |
| 2020-06-29 | QE / NORMAL / PANDEMIC / ELEVATED |
| 2015-12-16 | HIKING_EARLY / NORMAL / NEUTRAL / ELEVATED |
| 2024-09-18 | CUTTING_EARLY / STEEPENING / NEUTRAL / EXTREME |

Tests: `tests/test_regime_classifier_fixtures.py` (heuristic mode).

### Gaps

1. Model string: spec **`claude-sonnet-4-6`** vs code default **`claude-sonnet-4-20250514`** — confirm billing/console name.
2. **Batch backfill** ~400 regime labels — not automated; cost target <$0.50.
3. Nightly narrative does not yet emit **PDF/HTML matching BTIG sample layout** (tables for combo status, variable dashboard).
4. Should **dominant signal** be rule-based (current) or Claude-chosen each night?

**Decision needed:** Claude budget approval + model ID + narrative format owner (product vs eng).

---

## 6. Hit rates, forward returns, and backfill

### Definitions (methodology doc)

- **Forward return** = realized SPX (^GSPC) return after fire date D at 5/21/63/126 **trading days** (not calendar).
- **Hit rate (bullish combo)** = % of fires where `spx_3m > 0`, denominator only rows where `spx_3m IS NOT NULL`.
- **Regime-adjusted:** e.g. `fed_cycle LIKE 'CUT%'` for “91% in cutting cycle” vs “68% hiking” (Combo B).

### Implementation

- `forward_returns.py` + `hit_rates.py`: **implemented**
- `backfill_macro_history.py`: **exists, not run to completion**
- Current `runic_output.json` often shows `analog_dates: []`, `spx_3m_hit_rate: null` until backfill

### Gate tests (mandatory per spec)

| Test | Requirement | Test file |
|------|-------------|-----------|
| Combo B | Oct 13, 2022 conditions | `tests/test_combo_b_oct_2022.py` |
| Combo F | Jun 29, 2020 conditions | `tests/test_combo_f_jun_2020.py` |

Live historical assertions may use documented fallbacks when FRED CSV history is truncated.

### Questions for manager

1. Is **full backfill 1990–2026** a release gate or post-launch batch job?
2. Acceptable **hit rate tolerance** vs cheat sheet (B ~87%, F ~78%) on first backfill?
3. Who validates **May 26, 2026 live state** in cheat sheet vs production output?

---

## 7. Nightly JSON schema

### Required fields (spec §6 + addendum)

Present in implementation: `date`, `regime`, `dominant_signal`, `dominant_reason`, `brave_fearful`, `active_combos`, `watch_combos`, `persistence_signals`, `ssi_multiplier`, `vix_bypass`, `analog_dates`, `spx_3m_*`, `combo_f_*`, `narrative`, `variables_dashboard`.

### Sample briefing sections (PDF)

1. Dominant signal one-liner  
2. Combo status table (ACTIVE / PARTIAL / WATCH, duration, hit rate)  
3. Current regime state  
4. 200–250 word briefing (4 paragraphs)  
5. Live variable dashboard (12 rows)  
6. System recommendation  

Streamlit page shows subset; **no PDF generator** yet.

---

## 8. UI, API, and documentation

| Surface | Spec / plan | Status |
|---------|-------------|--------|
| Streamlit Runic page | Yes | `src/pages/runic_page.py`, nav in `app.py` |
| FastAPI `/api/v1/...` | Optional in plan | **Not built** |
| Conviction engine link | Unclear | **Separate** — per-ticker `macro_tailwind` vs market Runic |
| `docs/api/` copies of PDFs | Exists | Risk of **drift** vs `macro_intelligence_docs/` |

**Questions:**

1. Is FastAPI required for v1 (mobile, external consumers)?
2. Should conviction UI show `vix_bypass` / dominant combo?
3. Single **source of truth** for spec PDFs?

---

## 9. Operations and handoff (addendum A5–A7)

### Schedules

| Job | Cron (CONFIG.yaml) | Notes |
|-----|-------------------|--------|
| Friday pull | `0 18 * * 5` | After CFTC ~3:30pm ET — confirm TZ |
| Nightly JSON | `0 21 * * 1-5` | 21:00 ET per spec |
| Monthly threshold review | 1st of month | Scaffold only |

### Deliverables by July 25 (addendum)

- [x] `SYSTEM_DOCUMENTATION.md`
- [x] `README_MAINTENANCE.md`
- [x] `CONFIG.yaml` (thresholds, URLs, model)
- [ ] Handoff call with Rohit + Ahil — **scheduling**
- [ ] Automated threshold review → email + approval link — **stub only**

### SQLite → Postgres

Schema designed for connection-string swap later. **No migration timeline** from manager yet.

**Questions:**

1. Cron timezone: **ET on host** or UTC?
2. Who is on-call if Friday CFTC pull fails?
3. Postgres cutover date?

---

## 10. Relationship to Conviction Engine

| | Conviction `macro_tailwind` | Runic Agent |
|---|---------------------------|-------------|
| Scope | Per-ticker company macro | Market-wide regime |
| Storage | `conviction_store` JSON | `runic.db` + `runic_output.json` |
| Claude | Web search per company | Regime + narrative per market |
| Consumer | BQ scoring overlay | C++ position sizing |

**No integration** by design in v1. Confirm product does not expect merged UI.

---

## 11. SSI validation tests (parallel — reference)

From SSI Open Questions Part 9 — **not Runic v1** unless assigned:

1. SSI entry threshold sweeps (long/short)  
2. SQUEEZE / LIQUIDITY EXIT grids  
3. TP/SL optimization  
4. CNN F&G forward returns  
5. DBMF beta threshold  
6. HYG/LQD definition  
7. Z-score vs percentile for SSI  
8. Layer 2 confirmation threshold  
9. **VIX regime multiplier A/B (must include Oct 2022)**  
10. Bollinger + SSI  
11. Stochastic + McClellan  
12. Gross/net divergence revised  
13. SBI short signal validation  

Track under future `macro_intelligence/analysis/ssi_validation/` if approved.

---

## 12. Recommended v1 scope tiers

Use this in the meeting to cut scope:

### Tier A — Must have for C++ go-live

- [ ] Production paths for `runic_output.json` + schema sign-off  
- [ ] Friday pull stable for 12 variables (with agreed fallbacks)  
- [ ] Named combos B, F gate tests passing in CI  
- [ ] Nightly JSON with `vix_bypass`, `regime`, `dominant_signal`, `active_combos`  
- [ ] `FRED_API_KEY` in production  

### Tier B — Should have soon after

- [ ] Full historical backfill + hit rates on DB  
- [ ] Combo C cancel logic  
- [ ] `signal_fires` population  
- [ ] Regime backfill on `combo_fires.macro_regime`  
- [ ] Real SSI `positioning.json` integration  

### Tier C — Phase 2

- [ ] 298-combo pre-filter + Claude only on gated combos  
- [ ] BTIG-style PDF/HTML report  
- [ ] FastAPI endpoints  
- [ ] Monthly threshold auto-approval workflow  
- [ ] Postgres migration  

---

## 13. Meeting checklist (copy-paste)

```
[ ] runic_output.json absolute path: _______________________
[ ] positioning.json absolute path: _______________________
[ ] SSI owner: __________  Runic owner: __________  C++ owner: __________
[ ] FRED_API_KEY provisioned: Y / N
[ ] CPI consensus source: _______________________
[ ] v1 scope tier: A only / A+B / full spec
[ ] Combo C cancel in v1: Y / N
[ ] Full backfill release gate: Y / N
[ ] Claude model ID confirmed: _______________________
[ ] Cron timezone: ET / UTC
[ ] FastAPI in v1: Y / N
[ ] Spec PDF canonical folder: macro_intelligence_docs / docs/api
[ ] Handoff date with Ahil: _______________________
```

---

## 14. Implementation reference (for reviewers)

| Area | Path |
|------|------|
| Config | `macro_intelligence/CONFIG.yaml` |
| DB schema | `src/macro_intelligence/db/schema.sql` |
| Combo engine | `src/macro_intelligence/engine/combo_detector.py` |
| Nightly job | `src/macro_intelligence/jobs/nightly_run.py` |
| Friday job | `src/macro_intelligence/jobs/friday_pull.py` |
| JSON writer | `src/macro_intelligence/output/json_writer.py` |
| Streamlit | `src/pages/runic_page.py` |
| Tests | `tests/test_combo_b_oct_2022.py`, `tests/test_combo_f_jun_2020.py`, etc. |

---

## 15. Integration Note v3 (May 28, 2026) — precedence & deltas

**Source:** `macro_intelligence_docs/28_May_2026_Divyanshu_Runic_Integration_Note_v3.docx`

**Rule:** Where v3 conflicts with the May 26 email or addendum, **v3 wins**.

### What v3 clarifies (aligned with prior docs)

| Topic | v3 resolution |
|-------|----------------|
| Architecture | Python/SQL = all logic; Claude = geo, narrative, naming only; Tavily = news context (not LLM) |
| WALCL “flat” for Combo C | MoM between −0.8% and +0.8% counts as flat/shrinking leg |
| Combo D VIX | Strictly **&lt; 18** (18.00 does not qualify) |
| Combo E NFCI | −0.52 **does** fire easy leg (RARE); E = **CONFIRMED 2/3** not PARTIAL when CAPE + NFCI met |
| Combo C cancel | WTI 4wk **&lt; +5%** for **4 consecutive Fridays**; CPI “not hot” = actual ≤ consensus; no release that week → CPI leg passes; counter resets on any fail |
| Combo F vs D/B | D does not cancel F; B while F active = reinforcing add if SPX above F fire price |
| CFTC lag | Friday TFF = Tuesday positions; flag **PENDING_CFTC_CONFIRM** until confirmed |
| GSR | Yahoo **GOLD** ÷ **SI=F**; rollover flags on silver/WTI windows |
| Deployment | JSON to **AWS 51.20.53.218** after Ahil C++ daily run (~5pm ET) |

### Conflicts between v3 and older specs / current code

| Item | May 26 / addendum / code | v3 (wins) | Action |
|------|--------------------------|-----------|--------|
| Combo F validation date | **2020-06-29** (tests, addendum) | **2020-06-08** (+6.2% week, expiry 2020-12-14) | Update tests & backfill anchor |
| Combo F live example | Cheat sheet **Mar 30, 2026** | Not repeated in v3 | Confirm which fire date is canonical for “active F” |
| HY Oct 2022 test | ~614 bps in May 26 spec | **~580 bps** in v3 | Widen test tolerance or use band |
| Percentile for combo detection | Mixed: full vs 3yr per variable (A4b) | **Layer 1 unconditional full history** for combo detection; Layer 2 regime-conditioned stored separately | Refactor `percentiles.py`; DB columns `unconditional_pctile`, `regime_pctile` |
| Friday checklist NFCI/HY | v3 §5 still says “3yr pctile” | §3 says full-history unconditional for detection | **Internal v3 inconsistency** — ask Rohit which line is correct |
| WTI 4wk formula | % change `(today/28d ago - 1)*100` | `(today − 28cd ago) ÷ 28cd ago` (ratio, not %?) | Clarify if result is ratio or percent |
| GSR tickers | CONFIG: **GC=F / SI=F** | **GOLD / SI=F** | Change puller + backfill cross-check FRED DCOILWTICO for WTI |
| CAPE fallback | multpl.com only in code | **FRED MULTPL_CAPE** secondary | Implement fallback series |
| Schedule | Nightly **21:00 ET** Mon–Fri | Write JSON **~5pm ET Friday** on AWS after C++ | Reconcile cron vs one sequential daily pipeline |
| CPI source | BLS + Investing.com consensus | **CPIAUCSL** (actual) + consensus | Wire `pending_releases` + PPI in cancel logic |

### v3 schema / JSON fields not in current implementation

- `combo_fires`: `combo_legs_confirmed`, `cftc_status`, `gsr_4wk_pct`, `gsr_modifier`
- `combo_c_cancel`: `wti_potential_week` (0–4)
- `pending_releases` table
- Regime `*_source` fields (e.g. `curve_regime_source: T10Y2Y`)
- JSON statuses: `CONFIRMED_3_OF_3`, `PENDING_CFTC_CONFIRM`, `CONTESTED` (Combo A)
- `pending_cpi_release` on JSON
- `recalibrate_thresholds.py --confirm` (annual cron) — **file missing**

### v3 logic not implemented

- Combo A BRAVE/FEARFUL direction vote (4 legs + GSR modifier; CONTESTED if tie)
- Combo C cancel engine (4-Friday counter + PPI)
- CFTC **Asset_Mgr** percentile separate from Lev_Money
- Auto-discovery “runs whenever nightly data available” (not only Friday)
- Tavily for narrative context
- Full backfill four artifacts + regime geo batch
- Futures rollover manual review flags

---

*End of document.*
