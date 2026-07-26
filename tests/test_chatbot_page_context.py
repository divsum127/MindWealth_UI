"""Chatbot page_context for Overwatch cross-page PULL mode."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.schemas.chatbot import ChatMessageRequest, PageContext
from api.services.chatbot_service import _merge_page_context


class TestChatbotPageContext(unittest.TestCase):
    def test_merge_page_context(self) -> None:
        body = ChatMessageRequest(
            message="What does Combo C mean for my book?",
            page_context=PageContext(
                route="/portfolio",
                page_title="Portfolio",
                active_tab="macro",
                panel_open=True,
                alert_ids=["runic-c", "regime-macro-override"],
                dominant_combo="C",
            ),
            additional_context="User is reviewing stress scenario.",
        )
        merged = _merge_page_context(body)
        self.assertIsNotNone(merged)
        assert merged is not None
        self.assertIn("User is reviewing stress scenario.", merged)
        self.assertIn("Route: /portfolio", merged)
        self.assertIn("Active tab: macro", merged)
        self.assertIn("runic-c", merged)


if __name__ == "__main__":
    unittest.main()
