"""Tests for the Tech AI multi-agent graph.

These tests use a fake supervisor and fake agents so they run without any LLM
API key or database. They verify the real routing and state-handling logic in
`backend/graph/nodes.py`.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.graph import nodes  # noqa: E402
from backend.graph.states import GeneralStates  # noqa: E402


@pytest.fixture
def fake_agents(monkeypatch):
    """Replace every LLM-backed agent with a deterministic fake."""
    calls = {}

    def make_supervisor(next_agent):
        def _supervisor(request, session_id):
            calls["supervisor"] = request
            return {
                "next_agent": next_agent,
                "agent_task": [{"description": f"task for {request}"}],
                "feedback": "",
                "approved": False,
                "retry_count": 0,
                "max_retry_count": 1,
            }
        return _supervisor

    def fake(name):
        def _agent(request, session_id, **kwargs):
            calls[name] = request
            return f"{name} answered: {request}"
        return _agent

    monkeypatch.setattr(nodes, "chat_supervisor_agent", make_supervisor("lesson_agent"))
    monkeypatch.setattr(nodes, "chat_lesson_agent", fake("lesson"))
    monkeypatch.setattr(nodes, "chat_research_agent", fake("research"))
    monkeypatch.setattr(nodes, "chat_doc_agent", fake("document"))
    monkeypatch.setattr(nodes, "chat_game_agent", fake("game"))
    monkeypatch.setattr(nodes, "chat_db_agent", fake("db"))
    monkeypatch.setattr(nodes, "chat_aget", fake("chat"))
    return calls, make_supervisor


def test_routing_node_sets_state():
    state = {"request": "Explain fractions", "session_id": "s1"}
    # direct call with a stubbed supervisor
    from unittest.mock import patch
    with patch.object(nodes, "chat_supervisor_agent", lambda request, session_id: {
        "next_agent": "research_agent",
        "agent_task": [{"description": "find facts"}],
        "feedback": "",
        "approved": False,
        "retry_count": 0,
        "max_retry_count": 2,
    }):
        out = nodes.routing_node(dict(state))
    assert out["next_agent"] == "research_agent"
    assert out["agent_task"] == [{"description": "find facts"}]
    assert out["max_retry_count"] == 2


def test_task_text_uses_task_description():
    state = {"request": "fallback", "agent_task": [{"description": "do X"}]}
    assert nodes._task_text(state) == "do X"


def test_task_text_falls_back_to_request():
    state = {"request": "the request", "agent_task": []}
    assert nodes._task_text(state) == "the request"


def test_running_task_dispatches_to_lesson(fake_agents):
    calls, _ = fake_agents
    state = {"request": "r", "session_id": "s", "next_agent": "lesson_agent",
             "agent_task": [{"description": "teach"}]}
    out = nodes.running_task_node(dict(state))
    assert out["answer"] == "lesson answered: teach"
    assert calls["lesson"] == "teach"


def test_running_task_dispatches_to_research(fake_agents, monkeypatch):
    calls, make_supervisor = fake_agents
    monkeypatch.setattr(nodes, "chat_supervisor_agent", make_supervisor("research_agent"))
    state = {"request": "r", "session_id": "s", "next_agent": "research_agent",
             "agent_task": [{"description": "find"}]}
    out = nodes.running_task_node(dict(state))
    assert out["answer"] == "research answered: find"


def test_running_task_defaults_to_chat(fake_agents):
    calls, _ = fake_agents
    state = {"request": "r", "session_id": "s", "next_agent": "unknown_agent",
             "agent_task": []}
    out = nodes.running_task_node(dict(state))
    assert out["answer"].startswith("chat answered")


def test_evaluator_approves_answer():
    out = nodes.evaluator_node({"answer": "hi"})
    assert out["approved_agent_answer"] is True


def test_build_graph_compiles():
    graph = nodes.build_graph()
    assert graph is not None
    assert hasattr(graph, "invoke")


def test_general_states_is_typed_dict():
    assert GeneralStates.__annotations__["request"] is str
