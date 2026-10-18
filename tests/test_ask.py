import pytest
from fastapi.testclient import TestClient

import main

FAKE_RESULT = {
    "answer": "Block 722145 drives 80.5 km.",
    "tool_calls": [
        {
            "name": "get_block_distance",
            "input": {"block_id": "722145", "date": "2026-10-14"},
            "result": "Block 722145 drives 80.5 revenue km on 2026-10-14.",
        }
    ],
    "rounds": 2,
}


@pytest.fixture
def client(monkeypatch):
    """A test client where answer_question is replaced by a fake, so no API call is made."""
    calls = []

    def fake_answer_question(question):
        calls.append(question)
        return FAKE_RESULT

    monkeypatch.setattr(main, "answer_question", fake_answer_question)
    test_client = TestClient(main.app)
    test_client.fake_calls = calls
    return test_client


def test_valid_question_returns_answer(client):
    response = client.post("/ask", json={"question": "How far does block 722145 drive?"})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"answer", "tool_calls", "rounds"}
    assert body == FAKE_RESULT
    assert set(body["tool_calls"][0]) == {"name", "input", "result"}
    assert client.fake_calls == ["How far does block 722145 drive?"]


def test_empty_question_is_rejected(client):
    response = client.post("/ask", json={"question": "   "})
    assert response.status_code == 400
    assert response.json()["detail"] == "Question must not be empty."
    assert client.fake_calls == []  # the agent was never called


def test_too_long_question_is_rejected(client):
    response = client.post("/ask", json={"question": "x" * 501})
    assert response.status_code == 400
    assert "500 characters or fewer" in response.json()["detail"]
    assert client.fake_calls == []
