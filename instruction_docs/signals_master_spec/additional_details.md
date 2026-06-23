The Y-axis composite in the BUBBLE GRAPHS for new signals, outstanding signals and claude signals - ALL DISCUSSED IN THE SIGNALS EMAIL DOCUMENTS - AKA quality composite has three components:
C1 — E[R] score (0 to 50 pts)
er_score = clip(E[R] / R_ref, 0, 1.0) × 50
Asset-class R_ref normalises across equity/ETF/crypto/bond/currency. Put differently, R_ref EXISTS TO MAKE E[R] scores normalised across asset classes. This rewards absolute expected return per trade. R_ref has been defined per asset class. All mentioned in the documents shared.
C2 — Signal alpha score (−15 to +15 pts)
alpha_score = clip(signal_alpha / 5%, −1.0, +1.0) × 15

LONG:  signal_alpha = E[R] − (bt_bh_cagr / 252 × bt_avg_hold_days)
SHORT: signal_alpha = E[R]  (compared to zero — conservative bar;
                              a short signal must earn positive E[R]
                              without credit for the drift headwind)
Note: bh = buy and hold, bt = backtested.
This is the more accurate "modified CAGR return". It is NOT CAGR_diff (strategy CAGR − B&H CAGR) i.e. what we have so far called CAGR Alpha. It is the per-trade version: E[R] minus what a random entry on the same asset would earn over the same hold window. It answers "does this signal beat random entry?" at the trade level, not the strategy level.
C3 — Sharpe score (−6 to +8 pts)
sharpe_score = clip((strategy_sharpe − 0.3) / 1.5, −0.3, +0.4) × 20
Asymmetric cap — penalises poor Sharpe but doesn't over-reward tiny-sample high Sharpes.
Total range: approximately −21 to +73 pts.
The key distinction on C2 — the earlier version of the composite used CAGR_diff (strategy vs B&H annual return) as C2. We replaced it with signal_alpha because CAGR_diff penalises signals unfairly when the asset compounds steadily between trades (cash gap cost). Signal_alpha strips that out and looks only at the quality of the individual entry window. CAGR_diff is now a diagnostic flag only — Gate A2d (Claude report only, not used in bubble chart scoring or filtering) — not a composite component.

changing the r ref table as what i put was too aggressive

Please note the formula for C2 holds for short positions as well. Earlier we may have used 0 for the older cagr difference formula that this has superceded…