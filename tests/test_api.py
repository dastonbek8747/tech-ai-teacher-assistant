"""Tests for the FastAPI layer."""
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import backend.main as main  # noqa: E402


@pytest.fixture
def client():
    return TestClient(main.app)


def test_index(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health(client):
    assert client.get("/health").json() == {"status": "healthy"}


def test_chat_rejects_empty_request(client):
    response = client.post("/chat", json={"request": "", "session_id": "s1"})
    assert response.status_code == 422


def test_chat_rejects_missing_session(client):
    response = client.post("/chat", json={"request": "hello"})
    assert response.status_code == 422


def test_chat_returns_agent_answer(client, monkeypatch):
    class FakeGraph:
        def invoke(self, state):
            return {**state, "next_agent": "chat_agent", "answer": "Salom!"}

    monkeypatch.setattr(main, "build_graph", lambda: FakeGraph())
    response = client.post("/chat", json={"request": "Salom", "session_id": "s1"})
    assert response.status_code == 200
    body = response.json()
    assert body["next_agent"] == "chat_agent"
    assert body["answer"] == "Salom!"


def test_chat_reports_agent_error_as_500(client, monkeypatch):
    class BoomGraph:
        def invoke(self, state):
            raise RuntimeError("LLM is down")

    monkeypatch.setattr(main, "build_graph", lambda: BoomGraph())
    response = client.post("/chat", json={"request": "hi", "session_id": "s1"})
    assert response.status_code == 500
    assert "LLM is down" in response.json()["detail"]
