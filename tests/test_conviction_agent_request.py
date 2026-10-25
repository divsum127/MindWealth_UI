"""CE-28: agent-dimension requests on a current model (no network)."""

from __future__ import annotations

import sys
import types

import pytest

from src.conviction_engine import agent_dims


def test_current_model_request_shape():
    opts = agent_dims._request_options("claude-opus-5-5", 1500)
    assert opts["max_tokens"] >= 16000  # thinking counts against max_tokens
    assert opts["tools"] == [{"type": "web_search_20260209", "name": "web_search"}]
    assert opts["extra_body"]["output_config"] == {"effort": agent_dims._DEFAULT_EFFORT}
    assert opts["extra_body"]["fallbacks"] == "default"
    assert opts["extra_headers"] == {"anthropic-beta": "server-side-fallback-2026-07-01"}
    assert "temperature" not in opts and "thinking" not in opts


def test_legacy_model_keeps_basic_request():
    opts = agent_dims._request_options("claude-sonnet-4-5-20250929", 1500)
    assert opts == {"max_tokens": 1500, "tools": [{"type": "web_search_20250305", "name": "web_search"}]}


def test_default_model_is_not_the_retired_snapshot():
    assert agent_dims._DEFAULT_MODEL != "claude-sonnet-4-5-20250929"


class _Resp:
    def __init__(self, stop_reason, text='{"score": 1}'):
        self.stop_reason = stop_reason
        self.model = "claude-opus-5-5"
        self.content = [types.SimpleNamespace(type="text", text=text)]
        self.usage = types.SimpleNamespace(input_tokens=10, output_tokens=5)


def _fake_anthropic(monkeypatch, response):
    calls = {}

    class _Messages:
        def create(self, **kwargs):
            calls.update(kwargs)
            return response

    class _Client:
        def __init__(self, **_):
            self.messages = _Messages()

    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=_Client))
    return calls


def test_refusal_is_not_a_score(monkeypatch):
    _fake_anthropic(monkeypatch, _Resp("refusal", text=""))
    with pytest.raises(ValueError, match="refusal"):
        agent_dims._call_claude_web_search(system="s", user="u")


def test_truncated_reply_is_not_a_score(monkeypatch):
    _fake_anthropic(monkeypatch, _Resp("max_tokens", text='{"score": '))
    with pytest.raises(ValueError, match="max_tokens"):
        agent_dims._call_claude_web_search(system="s", user="u")


def test_normal_reply_records_served_model(monkeypatch):
    calls = _fake_anthropic(monkeypatch, _Resp("end_turn"))
    result = agent_dims._call_claude_web_search(system="s", user="u")
    assert result["score"] == 1
    assert result["_api_model"] == "claude-opus-5-5"
    assert calls["model"] == agent_dims._DEFAULT_MODEL
