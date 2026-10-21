import logging
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

import main
from src.rate_limit import QuestionLimiter

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
QUESTION = {"question": "How far does block 722145 drive?"}


class FakeClock:
    """A clock that only moves when the test says so, so no test has to sleep."""

    def __init__(self):
        self.now = datetime(2026, 10, 18, 12, 0, 0, tzinfo=UTC)

    def __call__(self):
        return self.now

    def advance(self, **kwargs):
        self.now += timedelta(**kwargs)


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def client(monkeypatch, clock):
    """A test client with a fake agent (no API calls) and a fresh limiter on the fake clock."""
    calls = []

    agencies = []

    def fake_answer_question(question, agency="halifax"):
        calls.append(question)
        agencies.append(agency)
        return FAKE_RESULT

    monkeypatch.setattr(main, "answer_question", fake_answer_question)
    monkeypatch.setattr(main, "limiter", QuestionLimiter(global_daily_cap=100, clock=clock))
    test_client = TestClient(main.app)
    test_client.fake_calls = calls
    test_client.fake_agencies = agencies
    return test_client


def ask_from(client, ip):
    """Send a question that appears to come through Azure's proxy from this IP."""
    return client.post("/ask", json=QUESTION, headers={"X-Forwarded-For": ip})


def test_valid_question_returns_answer(client):
    response = client.post("/ask", json=QUESTION)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"answer", "tool_calls", "rounds"}
    assert body == FAKE_RESULT
    assert set(body["tool_calls"][0]) == {"name", "input", "result"}
    assert client.fake_calls == [QUESTION["question"]]


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


def test_sixth_question_in_a_minute_is_refused(client, clock):
    for _ in range(5):
        assert ask_from(client, "203.0.113.7").status_code == 200
        clock.advance(seconds=10)  # questions at 0, 10, 20, 30 and 40 seconds

    response = ask_from(client, "203.0.113.7")  # at 50 seconds
    assert response.status_code == 429
    # The first question (at 0 s) leaves the 60-second window 10 seconds from now.
    assert response.headers["Retry-After"] == "10"
    assert "5 questions per minute" in response.json()["detail"]
    assert "10 seconds" in response.json()["detail"]
    assert len(client.fake_calls) == 5  # the refused question never reached the agent

    # A different visitor is unaffected.
    assert ask_from(client, "198.51.100.9").status_code == 200


def test_minute_limit_resets_when_the_window_passes(client, clock):
    for _ in range(5):
        assert ask_from(client, "203.0.113.7").status_code == 200
    assert ask_from(client, "203.0.113.7").status_code == 429

    clock.advance(seconds=60)
    assert ask_from(client, "203.0.113.7").status_code == 200


def test_per_visitor_daily_limit_and_reset(client, clock):
    for _ in range(20):
        assert ask_from(client, "203.0.113.7").status_code == 200
        clock.advance(minutes=1)  # stay under the per-minute limit
    response = ask_from(client, "203.0.113.7")
    assert response.status_code == 429
    assert "20 questions per day" in response.json()["detail"]

    clock.now = datetime(2026, 10, 19, 0, 0, 1, tzinfo=UTC)  # just after midnight UTC
    assert ask_from(client, "203.0.113.7").status_code == 200


def test_global_daily_cap_and_reset(monkeypatch, client, clock):
    monkeypatch.setattr(main, "limiter", QuestionLimiter(global_daily_cap=3, clock=clock))
    for ip in ["10.0.0.1", "10.0.0.2", "10.0.0.3"]:
        assert ask_from(client, ip).status_code == 200

    response = ask_from(client, "10.0.0.4")  # a brand-new visitor, but the day's cap is used up
    assert response.status_code == 429
    assert response.json()["detail"] == "Daily demo limit reached, please try again tomorrow."

    clock.advance(days=1)
    assert ask_from(client, "10.0.0.4").status_code == 200


def test_spoofed_forwarded_entries_do_not_dodge_the_limit(client):
    # A visitor can put anything at the start of X-Forwarded-For; Azure's proxy adds the real
    # address at the end. Changing the fake part each time must not reset the limit.
    for n in range(5):
        response = ask_from(client, f"1.2.3.{n}, 203.0.113.7")
        assert response.status_code == 200
    assert ask_from(client, "9.9.9.9, 203.0.113.7").status_code == 429


def test_one_log_line_per_request_without_question_text(client, caplog):
    caplog.set_level(logging.INFO, logger="transit_ai.ask")
    client.post("/ask", json=QUESTION)
    client.post("/ask", json={"question": ""})
    lines = [r.getMessage() for r in caplog.records if r.name == "transit_ai.ask"]
    assert lines == [
        "/ask status=200 rounds=2 rate_limited=no",
        "/ask status=400 rounds=- rate_limited=no",
    ]
    assert all("722145" not in line for line in lines)


def test_rate_limited_request_is_logged(client, caplog):
    caplog.set_level(logging.INFO, logger="transit_ai.ask")
    for _ in range(6):
        ask_from(client, "203.0.113.7")
    lines = [r.getMessage() for r in caplog.records if r.name == "transit_ai.ask"]
    assert lines[-1] == "/ask status=429 rounds=- rate_limited=yes"


def test_agency_is_passed_to_the_agent(client):
    assert client.post("/ask", json=QUESTION).status_code == 200  # no agency: Halifax
    assert client.post("/ask", json={**QUESTION, "agency": "dublin"}).status_code == 200
    assert client.fake_agencies == ["halifax", "dublin"]


def test_unknown_agency_is_rejected(client):
    response = client.post("/ask", json={**QUESTION, "agency": "paris"})
    assert response.status_code == 400
    assert "Unknown agency" in response.json()["detail"]
    assert client.fake_calls == []
