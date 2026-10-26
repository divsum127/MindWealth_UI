"""SEC company facts, cut down to the concepts the BQ replay needs (CE-29).

One companyfacts download per CIK (raw JSON is 1–10 MB); only the concepts below are kept,
with their `filed` date so values can be read as they stood on any past date. Raw files
are not kept.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from src.conviction_engine.pe_history_sec import _get_with_backoff

CONCEPTS: dict[str, tuple[str, ...]] = {
    "revenue": ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet",
                "RevenuesNetOfInterestExpense"),
    "cost_of_revenue": ("CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold"),
    "gross_profit": ("GrossProfit",),
    "net_income": ("NetIncomeLoss",),
    "operating_income": ("OperatingIncomeLoss",),
    "pretax_income": ("IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
                      "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"),
    "income_tax": ("IncomeTaxExpenseBenefit",),
    "d_and_a": ("DepreciationDepletionAndAmortization", "DepreciationAndAmortization", "DepreciationAmortizationAndAccretionNet"),
    "cfo": ("NetCashProvidedByUsedInOperatingActivities",),
    "capex": ("PaymentsToAcquirePropertyPlantAndEquipment",),
    "buybacks": ("PaymentsForRepurchaseOfCommonStock",),
    "dividends_paid": ("PaymentsOfDividendsCommonStock", "PaymentsOfDividends"),
    "long_term_debt": ("LongTermDebt", "LongTermDebtNoncurrent"),
    "short_term_debt": ("LongTermDebtCurrent", "DebtCurrent", "ShortTermBorrowings"),
    "cash": ("CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"),
    "equity": ("StockholdersEquity",),
    "shares": ("WeightedAverageNumberOfDilutedSharesOutstanding", "WeightedAverageNumberOfSharesOutstandingBasic"),
}
FORMS = {"10-K", "10-K/A", "10-Q", "10-Q/A", "10-KT"}


def fetch_compact_facts(cik: str, cache_dir: Path) -> dict[str, Any] | None:
    path = cache_dir / f"CIK{cik}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            pass
    resp = _get_with_backoff(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json", timeout=60)
    if resp is None or resp.status_code != 200:
        return None
    raw = resp.json()
    gaap = (raw.get("facts") or {}).get("us-gaap") or {}
    compact: dict[str, list[dict[str, Any]]] = {}
    for key, names in CONCEPTS.items():
        rows: list[dict[str, Any]] = []
        for name in names:
            units = (gaap.get(name) or {}).get("units") or {}
            for unit, facts in units.items():
                if unit not in ("USD", "shares"):
                    continue
                for f in facts:
                    if f.get("form") not in FORMS or f.get("val") is None:
                        continue
                    rows.append({"start": f.get("start"), "end": f.get("end"), "val": float(f["val"]),
                                 "filed": f.get("filed"), "form": f.get("form"), "concept": name})
            if rows:
                break  # first concept that has data wins, so mixed definitions never blend
        compact[key] = rows
    out = {"cik": cik, "name": raw.get("entityName"), "facts": compact, "fetched_at": time.time()}
    cache_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out), encoding="utf-8")
    return out


def fetch_sic(cik: str, cache_dir: Path) -> str | None:
    path = cache_dir / f"SIC{cik}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8")).get("sic")
        except ValueError:
            pass
    resp = _get_with_backoff(f"https://data.sec.gov/submissions/CIK{cik}.json")
    sic = str(resp.json().get("sic") or "") if resp is not None and resp.status_code == 200 else None
    cache_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"sic": sic}), encoding="utf-8")
    return sic
