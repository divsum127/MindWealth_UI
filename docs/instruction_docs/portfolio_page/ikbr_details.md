Ahil/Divyanshu,

Even as we push forward now on rules and specific targeted improvements in Sharpe, specifically by reducing portfolio vol  (ILL EXPLAIN WHY ON A CALL) lets start the IBKR API integration for live/simulated execution and fill reconciliation against our NAV workbook and cost-drag assumptions. Here's the plan.

Stack:
- TWS API via IB Gateway (headless, not full TWS) — running on the AWS server alongside the rest of the pipeline.
- Python wrapper: ib_async (maintained fork of ib_insync — same API surface, don't use ib_insync, it's stale).
- I've asked IBKR about account setup (new individual account vs. folder in an existing one); once that's resolved, both a paper and live account should be provisioned in parallel — same relationship, so no separate signup needed for paper.

How paper and live run in parallel:
- IB Gateway can run two separate instances (or one instance switching login), each pointed at its own account — paper on port 4002, live on port 4001 (Gateway) or 7497/7496 for TWS. We'll run paper continuously from day one on its own instance, not as a "before we go live" phase — it stays live alongside production once we go live, so we always have a side-by-side fills/latency benchmark.
- Practically: same codebase, account/port picked via a config flag/env var, so switching between paper and live is a one-line change, not a rebuild.

What I need from you:
1. Once Gateway is up, pull historical fills on paper and reconcile against the cost-drag numbers already baked into the NAV workbook — see where our assumed slippage/commission model over- or under-states real IBKR execution.
2. Sketch what data we need per trade from the API (fill price, timestamp, commission, exchange) to feed the existing NAV/backtest reconciliation pipeline without changing its structure.
3. Flag anything in the current cost model that assumes execution behavior IBKR's API can't actually confirm (e.g., partial fills, slippage on illiquid names) — this is a chance to tighten that assumption with real data instead of the current estimate.

Will loop you in once the account question is sorted. No urgency on IBKR's side blocking you — you can start on the data-mapping/reconciliation spec now if useful.

If you have an alternative approach please suggest