"""
Regression tests for the "conversation disappeared after refresh" bug.

``save_history()`` used to truncate the file in place and then ``json.dump``
without a ``default=`` hook. A pandas ``Timestamp`` surviving in assistant
metadata raised mid-dump, leaving the file half-written; the next
``load_history()`` hit a JSONDecodeError and silently reset the conversation to
``[]``, destroying a successfully answered exchange.

Observed in the journal as:
    Error saving history: Object of type Timestamp is not JSON serializable
    Error loading history: Expecting value: line 2271 column 23 (char 382382)
"""

import json
import sys
import uuid
from pathlib import Path

import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from chatbot.config import HISTORY_DIR  # noqa: E402
from chatbot.history_manager import HistoryManager  # noqa: E402


@pytest.fixture
def session_id():
    sid = f"pytest-history-{uuid.uuid4()}"
    yield sid
    for path in HISTORY_DIR.glob(f"{sid}*"):
        path.unlink(missing_ok=True)


def test_timestamp_metadata_does_not_corrupt_history(session_id):
    """The exact payload that used to truncate the file must round-trip."""
    manager = HistoryManager(session_id=session_id)
    manager.add_message("user", "based on signals from our model what should we buy")
    manager.add_message(
        "assistant",
        "answer text",
        {
            "route": "HYBRID",
            "as_of": pd.Timestamp("2026-08-14"),
            "full_signal_tables": {
                "entry": pd.DataFrame(
                    {"Symbol": ["FPH.NZ"], "Signal Date": [pd.Timestamp("2026-08-14")]}
                )
            },
        },
    )

    history_file = HISTORY_DIR / f"{session_id}.json"
    payload = json.loads(history_file.read_text(encoding="utf-8"))
    assert len(payload["conversation"]) == 2

    reloaded = HistoryManager(session_id=session_id)
    assert len(reloaded.conversation_history) == 2
    assert reloaded.conversation_history[0]["content"].startswith("based on signals")


def test_no_partial_file_left_behind(session_id):
    """A save must never leave a temp file or a quarantined copy on success."""
    manager = HistoryManager(session_id=session_id)
    manager.add_message("user", "hello")
    assert list(HISTORY_DIR.glob(f"{session_id}.corrupt-*")) == []
    assert list(HISTORY_DIR.glob(".history_*")) == []


def test_corrupt_file_is_quarantined_not_silently_erased(session_id):
    """A pre-existing corrupt file must be preserved for diagnosis."""
    history_file = HISTORY_DIR / f"{session_id}.json"
    history_file.write_text('{"metadata": {}, "conversation": [{"role": "user"', encoding="utf-8")

    manager = HistoryManager(session_id=session_id)
    assert manager.conversation_history == []

    quarantined = list(HISTORY_DIR.glob(f"{session_id}.corrupt-*"))
    assert len(quarantined) == 1, "corrupt history must be renamed aside, not dropped"
    assert "role" in quarantined[0].read_text(encoding="utf-8")
