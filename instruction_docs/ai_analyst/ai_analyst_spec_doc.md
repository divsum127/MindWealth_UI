This email replaces all earlier versions. Please discard anything sent before on this topic. Everything below has been reviewed and corrected.

---

WHAT THE AI ANALYST PANEL IS

A floating panel (360px wide) that slides in from the right edge of every page in MindWealth. It has two modes:

  PUSHED — the Overwatch Agent detects a condition and automatically opens the panel on the relevant tab
  PULL  — the user clicks the panel trigger button (fixed bottom-right, gold, 48px circle) and asks a question manually

The Overwatch Agent is a Python background process (cron + event triggers). It watches three alert channels and pushes results via SSE. The Claude API is used only to write the natural-language alert message — it does not trigger anything. The badge text on the panel reads 'Overwatch · auto-triggered', not 'Claude triggered'.

Filter tabs: ALL | SIGNALS | MACRO | SYSTEM
ALL shows everything active. Each other tab shows only that channel's content.
The SYSTEM tab is hidden entirely from non-admin users (check isAdmin from JWT).

---

CHANNEL 1 — SIGNALS (Degradation Watch)

What it monitors:
  For every (asset / function / interval / direction) combo in the model, track the live forward win rate over time.
  We have this data in the daily report. Monitor weekly or monthly per combo depending on historical sensitivity.

Trigger logic:
  - FWD win rate >= 60%: no alert. Full stop. The relationship between BT rate and FWD rate is irrelevant.
  - FWD win rate declining toward 60%: fire a DEGRADATION WATCH alert
  - FWD win rate below 60%: fire a stronger alert (DEGRADATION BREACH)
  - Any booked loss on a portfolio position: flag immediately
  - Any live MTM below -10% on a portfolio position: flag immediately
  - On any loss event: run pattern analysis — group exits-at-loss by asset / function / both and classify the story

Panel message format:
  '[Strategy] / [Direction] / [Interval]: FWD win rate [X]% — [above/approaching] 60% floor.'
  'Trend: [n1] → [n2] → [n3] → [n4] (last 4 weeks).'
  'Recommend: [action].'

The message includes a 4-bar mini chart showing the weekly trend, coloured emerald → gold → ruby as it approaches 60%.

Label: 'AI ANALYST · OVERWATCH AUTO-TRIGGERED · DEGRADATION WATCH'
Left border colour: ruby #ff4d6d
Panel auto-opens on: SIGNALS tab

---

CHANNEL 2 — MACRO (Runic Signals + Analog Finder)

THE 12 MACRO VARIABLES
(Rohit note: I am not certain which version of this list was previously sent. Please use this as the definitive version.)

  #   Variable              FRED / Yahoo ticker       Runic Combos fed
  1   HY Spreads            FRED: BAMLH0A0HYM2        A, A+, B, G
  2   NFCI                  FRED: NFCI                C
  3   Fed Balance Sheet     FRED: WALCL               A
  4   USD/CNH               Yahoo: USDCNH=X           C
  5   WTI Oil               Yahoo: CL=F               C
  6   VIX                   Yahoo: ^VIX               D, G
  7   VIX3M Ratio           Yahoo: ^VIX3M             D, G
  8   CFTC COT              Weekly CFTC parse         B, D, E, F
  9   10Y-2Y Yield Curve    FRED: T10Y2Y              A, C
  10  CPI Surprise          Investing.com free scrape C
  11  Gold/Silver Ratio     Yahoo: GC=F / SI=F        C
  12  CAPE P/E              Shiller public dataset    E

Almost everything is free. The only borderline dependency is CPI consensus — use Investing.com economic calendar as the free approximation (confirmed in April 22 spec).

THE 8 RUNIC COMBO ARCHETYPES

  A   Liquidity Risk-On   HY spreads + DBMF + CNN F&G                  RARE on 2+
  A+  Early Warning       HY widening + DBMF short equity (both neg z)  RARE on both
  B   Capitulation        COT FM + McClellan + NH/NL + CNN + HY         EXTREME on 3+
  C   Stagflation         NFCI + USD/CNH + WTI + CPI surprise           RARE on 2+
  D   FOMO Top            Put/Call EMA + COT FM + CNN + VIX TS ratio    RARE on 2+; EXTREME on 1
  E   Valuation Top       COT RM pct + NAAIM + CAPE P/E                 RARE on both
  F   Recovery            COT + HY compressing + % above 200DMA        RARE to NORMAL transition
  G   Hidden Stress       VIX TS backwardation + HY widening + DBMF     RARE on VIX TS + any 1 other

IMPORTANT — definition of RARE:
  RARE does not mean a single-day spike above a z-score threshold. It means persistent/unusual.
  - Weekly signals (AAII, NAAIM, COT): 2+ consecutive weeks above threshold
  - Daily signals (VIX TS, HY spreads): 3+ consecutive trading days above threshold
  Implement as a rolling minimum: rare_persistent = (z_score > 1.0).rolling(N).min().astype(bool)

SSI INTEGRATION NOTE:
  The SSI sub-indices (AAII, Put/Call, NAAIM, COT, McClellan, NH/NL, CNN F&G, HYG/LQD, DBMF, VIX TS ratio) overlap directly with several combo variables. The SSI's positioning.json extreme_map block is the sentiment input to the combo engine. The SSI also serves as the regime sizing condition for BandMatrix and DeltaDrift — do not touch that existing logic.

ECONOMIC SURPRISE EXAMPLE (correct format — hard data only, no analyst commentary):
  'US Q3 GDP: +1.2% vs +2.4% consensus — 3rd consecutive downside miss.
   Historically precedes SPX drawdown in 4/5 analog instances. SSI: 26 — Fear zone.'

ANALOG FINDER — included automatically in every Runic alert:
  When a combo fires, the macro agent looks up historical dates when the same combo was active and calculates SPX forward returns at 1M / 3M / 6M. The panel shows up to 5 instances plus a summary row (median 3M / worst / best / hit rate). This is displayed in a blue-bordered block directly below the Runic Signal block.
  Label: 'ANALOG FINDER · COMBO [X] HISTORICAL MATCHES'
  The macro_intelligence_agent.py must write a historical_analogs block to its nightly JSON output for this to work — see Question 3 below.

Label: 'AI ANALYST · OVERWATCH AUTO-TRIGGERED · RUNIC SIGNAL · COMBO [X]'
Left border colour: gold #C5A059
Footer strip: 'TAVILY ACTIVE · INTERNAL DATA PRIORITY · ONCE PER PAGE VISIT'
Panel auto-opens on: MACRO tab

---

CHANNEL 3 — SYSTEM (Admin only)

Checks every 15 minutes via cron:
  - US CSV pipeline: last modified time vs expected update interval
  - India CSV pipeline: same
   - Claude API: connectivity check
  - Tavily: last successful search timestamp + latency
  - Google Sheets: last sync timestamp
  - Macro agent: last nightly run timestamp
  - SSI JSON write: last write timestamp

Colour logic: emerald = ok, gold = warning (>2x expected latency or interval), ruby = failed
Admin-only: entire tab hidden if isAdmin === false in JWT
No auto-open. User pulls this manually.
Label: 'SYSTEM HEALTH · INTERNAL MONITOR'

---

AUTO-OPEN LOGIC (React)

```javascript
// useOverwatch hook — SSE listener
useEffect(() => {
  const es = new EventSource('/api/overwatch/stream');
  es.onmessage = (e) => {
    const alert = JSON.parse(e.data);
    setAlerts(prev => [alert, ...prev]);
    if (alert.type === 'degradation') {
      setPanelOpen(true);
      setActiveTab('signals');  // open on SIGNALS, not ALL
    } else if (alert.type === 'runic') {
      setPanelOpen(true);
      setActiveTab('macro');    // open on MACRO, not ALL
    }
    // system alerts: no auto-open
  };
  return () => es.close();
}, []);
```

Header badge text per tab:
```javascript
const badgeText = {
  all:     'Overwatch · auto-triggered',
  signals: `Overwatch · ${signalAlerts.length} watch active`,
  macro:   `Overwatch · Combo ${activeCombo} firing`,
  system:  'System monitor · admin only'
}[activeTab];
```

---

WHAT THE PANEL LOOKS LIKE (for Parth)

Position: fixed, right: 0, top: 0, height: 100vh, width: 360px, z-index: 9999
Background: #000000
Slide animation: translateX(360px to 0), 220ms ease-out, Framer Motion
Backdrop: rgba(0,0,0,0.4) overlay to the left of the panel, click closes
Trigger button: fixed bottom-right, 48px circle, background rgba(197,160,89,0.15), border 1px solid #C5A059, pulses gold when alert pending

Typography inside panel:
  Labels: DM Mono, 9px, letter-spacing 0.1em, color #3a3a3a
  Alert text: DM Mono, 11px, line-height 1.75, color #999
  Numbers/values: Cormorant Garamond, 12–16px
  Input bar: DM Mono, 11px, color #252525 placeholder

Color encoding:
  Degradation Watch border: #ff4d6d (ruby)
  Runic Signal border: #C5A059 (gold)
  Analog Finder border: #4A9EFF (blue)
  System Health border: #252525 (near-black)
  Positive values: #2de08a (emerald)
  Negative values: #ff4d6d (ruby)

---

THREE OPEN QUESTIONS — please respond before starting the build

1. Divyanshu: confirm the trade_store path on AWS server
   Current assumption: ~/uiv2/MindWealth_UI/trade_store/
   Please confirm or correct.

2. Divyanshu: is Redis available on the AWS server?
   If yes: use SSE pub/sub via Redis
   If no: use polling fallback (EventSource polling every 60 seconds)
   This determines how the useOverwatch hook is built.

3. Both: the Analog Finder requires macro_intelligence_agent.py to write a
   historical_analogs block to its nightly JSON output.
   Divyanshu — is this in the build plan from the April 22 spec, or does it need to be added?
   If it needs to be added, the JSON schema for that block is:
   {
     "historical_analogs": {
       "combo": "D+G",
       "instances": [
         { "date": "2024-06", "description": "Yen carry unwind", "spx_3m": -16.0 },
         ...
       ],
       "summary": { "median_3m": -8.4, "worst": -19.0, "best": 18.0, "hit_rate": 0.80 }
     }
   }