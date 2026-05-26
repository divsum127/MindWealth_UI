"""
PriceDataAgent — fetch T+0 / T+1m / T+3m / T+6m prices via yfinance for Deep Research.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from chatbot.config import (
    ENABLE_DEEP_RESEARCH_PRICE_DATA,
    ENABLE_LLM_EVENT_DATE_EXTRACTION,
    STOCK_DATA_DIR,
)
from chatbot.tools.event_date_extractor import known_fallback_date
from chatbot.tools.llm_event_date_extractor import extract_event_date_from_web
from chatbot.tools.market_price_tool import (
    compute_post_event_returns,
    format_price_table_md,
    to_yfinance_symbol,
)

from .research_types import EvidenceStore, ResearchSubTask, SubTaskEvidence

logger = logging.getLogger(__name__)


class PriceDataAgent:
    def run(
        self,
        subtask: ResearchSubTask,
        store: EvidenceStore,
    ) -> tuple[SubTaskEvidence, Dict[str, Any]]:
        if not ENABLE_DEEP_RESEARCH_PRICE_DATA:
            return SubTaskEvidence(
                subtask_id=subtask.id,
                question=subtask.question,
                retrieval_mode="price_data",
                success=False,
                error="price_data disabled in config",
            ), {}

        seller = subtask.seller_ticker
        sold = subtask.sold_ticker
        event_date: Optional[str] = None
        months = tuple(subtask.price_offsets_months or [1, 3, 6])
        inferred_from: Optional[str] = None

        # Web discovery always wins over planner-pre-filled event_date
        if subtask.depends_on:
            event_date, seller, sold, inferred_from = self._resolve_from_dependencies(
                subtask, store, seller, sold
            )

        if not event_date and subtask.event_date:
            event_date = subtask.event_date
            inferred_from = "planner"

        if not event_date:
            event_date = known_fallback_date(subtask.precedent_name, sold)
            if event_date:
                inferred_from = "known_fallback"

        if not event_date:
            return SubTaskEvidence(
                subtask_id=subtask.id,
                question=subtask.question,
                retrieval_mode="price_data",
                success=False,
                error="No event_date — run dependent web discovery subtask first",
                summary="Missing event date for price computation",
            ), {"price_data": {"error": "no event_date"}}

        if seller:
            seller = to_yfinance_symbol(seller)
        if sold:
            sold = to_yfinance_symbol(sold)

        try:
            price_result = compute_post_event_returns(
                seller_ticker=seller,
                sold_ticker=sold,
                event_date=event_date,
                months=months,
                stock_data_dir=Path(STOCK_DATA_DIR),
            )
        except Exception as exc:
            logger.error("price_data computation failed for %s: %s", subtask.id, exc)
            return SubTaskEvidence(
                subtask_id=subtask.id,
                question=subtask.question,
                retrieval_mode="price_data",
                success=False,
                error=str(exc),
                summary=f"Price computation error: {exc}",
                inferred_event_date=event_date,
            ), {
                "price_data": {"error": str(exc), "event_date": event_date},
                "inferred_event_date": event_date,
            }

        ok = bool(
            (price_result.get("seller") and price_result["seller"].get("T0") is not None)
            or (price_result.get("sold") and price_result["sold"].get("T0") is not None)
        )

        formatted = format_price_table_md(
            price_result, precedent_name=subtask.precedent_name or subtask.id
        )
        summary = (
            f"Computed prices for {subtask.precedent_name or subtask.id} "
            f"from {price_result.get('event_date')}; source={price_result.get('data_source')}"
        )

        evidence = SubTaskEvidence(
            subtask_id=subtask.id,
            question=subtask.question,
            retrieval_mode="price_data",
            success=ok,
            summary=summary,
            formatted_context=formatted + "\n\n" + json.dumps(price_result, indent=2),
            price_data=price_result,
            facts_extracted=self._facts_from_price(price_result),
            inferred_event_date=event_date,
        )
        detail = {
            "price_data": price_result,
            "inferred_event_date": event_date,
            "inferred_from": inferred_from,
        }
        return evidence, detail

    def _resolve_from_dependencies(
        self,
        subtask: ResearchSubTask,
        store: EvidenceStore,
        seller: Optional[str],
        sold: Optional[str],
    ) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        for dep_id in subtask.depends_on:
            entry = store.get_entry(dep_id)
            if not entry:
                continue
            if entry.inferred_event_date:
                return (
                    entry.inferred_event_date,
                    entry.inferred_seller_ticker or seller or subtask.seller_ticker,
                    entry.inferred_sold_ticker or sold or subtask.sold_ticker,
                    "dependent_entry",
                )

        text_parts: List[str] = []
        source_dicts: List[Dict[str, Any]] = []

        for dep_id in subtask.depends_on:
            entry = store.get_entry(dep_id)
            if not entry:
                continue
            text_parts.append(entry.formatted_context or "")
            text_parts.append(entry.summary or "")
            for fact in entry.facts_extracted or []:
                text_parts.append(fact)
            for url in entry.sources or []:
                source_dicts.append({"title": "", "url": url, "content": ""})

        blob = "\n".join(text_parts)
        extraction = extract_event_date_from_web(
            question=subtask.question,
            sources=source_dicts,
            text_blob=blob,
            precedent_name=subtask.precedent_name,
            seller_ticker=seller or subtask.seller_ticker,
            sold_ticker=sold or subtask.sold_ticker,
            use_llm=ENABLE_LLM_EVENT_DATE_EXTRACTION,
        )

        event_date = extraction.event_date
        inferred_from = extraction.source if event_date else None

        if not seller:
            seller = extraction.seller_ticker or subtask.seller_ticker
        if not sold:
            sold = extraction.sold_ticker or subtask.sold_ticker
        if not extraction.seller_is_listed:
            seller = None

        if not seller and re.search(r"\b(IFT|Infratil)\b", blob, re.I):
            if "z energy" in (subtask.precedent_name or "").lower():
                seller = "IFT.NZ"
        if not sold and re.search(r"\b(Z Energy|ZEL)\b", blob, re.I):
            sold = "ZEL.NZ"
        if not sold and re.search(r"\b(Contact|CEN)\b", blob, re.I) and "origin" in (
            (subtask.precedent_name or "").lower()
        ):
            sold = "CEN.NZ"
        if not sold and re.search(r"\b(Air New Zealand|AIR)\b", blob, re.I) and "air" in (
            (subtask.precedent_name or "").lower()
        ):
            sold = "AIR.NZ"

        return event_date, seller, sold, inferred_from

    @staticmethod
    def _facts_from_price(price_result: Dict[str, Any]) -> List[str]:
        facts = []
        for role in ("seller", "sold"):
            leg = price_result.get(role)
            if not leg:
                continue
            t0 = leg.get("T0")
            ticker = leg.get("ticker", role)
            if t0 is not None:
                parts = [f"{ticker} T0={t0}"]
                for m in (1, 3, 6):
                    k = f"T+{m}m"
                    if leg.get(k) is not None:
                        parts.append(f"{k}={leg[k]} ({leg.get(f'pct_{m}m')}% vs T0)")
                facts.append(" ".join(parts))
        return facts[:10]
