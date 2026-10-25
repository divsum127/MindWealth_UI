#!/usr/bin/env python3
"""Two-name agent-dimension model comparison (Rohit 24 Sep 2026).

    "Reg 12.2 yes we can go ahead with teh test on nvda and google"
    "yes approve for 2 names and yes (request only("

Runs the five agentic dimensions for each ticker on each candidate model and writes the
results side by side with what the store currently holds. Read-only against
conviction_store. Spending is metered from each response's usage and the run stops
before any call that could take the total past ``--cap-usd`` (default 5).

    .venv/bin/python scripts/conviction_agent_pilot.py --out-dir reports/conviction_agent_pilot_YYYY-MM-DD
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from src.config_paths import CONVICTION_STORE_DIR  # noqa: E402
from src.conviction_engine import agent_dims  # noqa: E402

# USD per million tokens (input, output). Cache writes bill at 1.25x input, reads at 0.1x.
PRICES = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
}
WEB_SEARCH_USD = 10.00 / 1000
# Worst case for one dimension call, used only to decide whether the next call may start:
# 60k input tokens, the full 16k output, eight searches.
WORST_CALL_TOKENS = (60_000, 16_000, 8)
DIMENSIONS = (
    "macro_tailwind_detail",
    "ceo_quality_detail",
    "competitive_moat_detail",
    "deal_delay_detail",
    "reinvestment_runway_detail",
)


class BudgetExceeded(RuntimeError):
    pass


def call_cost(model: str, usage: dict[str, Any]) -> float:
    price_in, price_out = PRICES[model]
    return (
        usage.get("input_tokens", 0) * price_in
        + usage.get("cache_creation_input_tokens", 0) * price_in * 1.25
        + usage.get("cache_read_input_tokens", 0) * price_in * 0.1
        + usage.get("output_tokens", 0) * price_out
    ) / 1_000_000 + usage.get("web_search_requests", 0) * WEB_SEARCH_USD


def worst_call_cost(model: str) -> float:
    tokens_in, tokens_out, searches = WORST_CALL_TOKENS
    return call_cost(model, {"input_tokens": tokens_in, "output_tokens": tokens_out, "web_search_requests": searches})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tickers", default="NVDA,GOOG")
    parser.add_argument("--models", default="claude-opus-5-5,claude-sonnet-5-5")
    parser.add_argument("--cap-usd", type=float, default=5.0)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    unknown = [m for m in models if m not in PRICES]
    if unknown:
        parser.error(f"no price on file for {unknown}; add it to PRICES first")

    ledger: list[dict[str, Any]] = []
    spent = 0.0
    original_call = agent_dims._call_claude_web_search

    def metered_call(*, system: str, user: str, max_tokens: int = 1500) -> dict[str, Any]:
        nonlocal spent
        model = agent_dims._DEFAULT_MODEL
        if spent + worst_call_cost(model) > args.cap_usd:
            raise BudgetExceeded(f"next {model} call could exceed the ${args.cap_usd:.2f} cap (spent ${spent:.4f})")
        result = original_call(system=system, user=user, max_tokens=max_tokens)
        cost = call_cost(model, result.get("_api_usage") or {})
        spent += cost
        ledger.append({"model": model, "served_by": result.get("_api_model"), "usd": round(cost, 4), **(result.get("_api_usage") or {})})
        return result

    agent_dims._call_claude_web_search = metered_call
    results: dict[str, dict[str, Any]] = {}
    stopped = None
    try:
        for ticker in [t.strip().upper() for t in args.tickers.split(",") if t.strip()]:
            record = json.loads((Path(CONVICTION_STORE_DIR) / f"{ticker}.json").read_text(encoding="utf-8"))
            stored = record.get("manual_overrides") or {}
            results[ticker] = {"stored": {d: stored.get(d) for d in DIMENSIONS}}
            for model in models:
                agent_dims._DEFAULT_MODEL = model
                results[ticker][model] = agent_dims.run_agent_dimensions(
                    ticker,
                    str(record.get("company_name") or record.get("long_name") or ticker),
                    str(record.get("business_type") or "unknown"),
                    revenue_ttm=record.get("revenue_ttm"),
                    is_hardware_sector=record.get("business_type") == "high_margin_hardware",
                )
    except BudgetExceeded as exc:
        stopped = str(exc)
    finally:
        agent_dims._call_claude_web_search = original_call

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "pilot_results.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    (args.out_dir / "pilot_ledger.json").write_text(
        json.dumps({"spent_usd": round(spent, 4), "cap_usd": args.cap_usd, "stopped": stopped, "calls": ledger}, indent=2),
        encoding="utf-8",
    )

    print(f"Spent ${spent:.4f} of ${args.cap_usd:.2f} cap over {len(ledger)} calls" + (f" — STOPPED: {stopped}" if stopped else ""))
    for ticker, by_source in results.items():
        print(f"\n{ticker}")
        for dim in DIMENSIONS:
            cells = []
            for source, dims in by_source.items():
                detail = (dims or {}).get(dim) or {}
                cells.append(f"{source}: score {detail.get('score')} conf {detail.get('confidence')}")
            print(f"  {dim:28s} " + " | ".join(cells))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
