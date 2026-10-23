import json
import logging
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

import main
from src.rate_limit import QuestionLimiter

FEEDBACK = {
    "agency": "london",
    "question": "How far does block 79-6 drive on 9 November 2026?",
    "answer": "Block 79-6 drives about 201.5 km (estimated).",
    "tool_calls": [{"name": "get_block_distance",
                    "input": {"agency": "london", "block_id": "79-6", "date": "2026-11-09"},
                    "result": "Block 79-6 drives 201.5 revenue km on 2026-11-09."}],
    "rating": "down",
    "comment": "Should say the\nblock is inferred",
}


@pytest.fixture
def client(monkeypatch):
    clock = lambda: datetime(2026, 10, 23, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(main, "feedback_limiter", QuestionLimiter(global_daily_cap=100, clock=clock))
    return TestClient(main.app)


def test_feedback_is_logged_as_one_json_line_without_ip(client, caplog):
    caplog.set_level(logging.INFO, logger="transit_ai.feedback")
    response = client.post("/feedback", json=FEEDBACK, headers={"X-Forwarded-For": "203.0.113.9"})
    assert response.status_code == 200
    [line] = [r.getMessage() for r in caplog.records if r.name == "transit_ai.feedback"]
    assert line.startswith("FEEDBACK ") and "\n" not in line
    logged = json.loads(line.removeprefix("FEEDBACK "))
    assert {k: logged[k] for k in ("agency", "question", "answer", "tool_calls", "rating")} == \
        {k: FEEDBACK[k] for k in ("agency", "question", "answer", "tool_calls", "rating")}
    assert logged["comment"] == "Should say the block is inferred"  # made one line
    assert logged["timestamp"].endswith("Z") and not logged["truncated"]
    assert "203.0.113.9" not in line and "testclient" not in line


def test_feedback_is_rate_limited_like_ask(client):
    for _ in range(5):
        assert client.post("/feedback", json=FEEDBACK).status_code == 200
    refused = client.post("/feedback", json=FEEDBACK)
    assert refused.status_code == 429 and "Retry-After" in refused.headers


def test_bad_feedback_is_rejected(client):
    assert client.post("/feedback", json={**FEEDBACK, "rating": "meh"}).status_code == 422
    assert client.post("/feedback", json={**FEEDBACK, "comment": "x" * 201}).status_code == 422
    assert client.post("/feedback", json={**FEEDBACK, "agency": "paris"}).status_code == 400
