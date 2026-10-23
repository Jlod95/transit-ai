import json
import logging
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import anthropic
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.agencies import AGENCIES, DEFAULT_AGENCY
from src.agent import AgentError, answer_question
from src.rate_limit import QuestionLimiter, RateLimitExceeded

MAX_QUESTION_LENGTH = 500
INDEX_PAGE = Path(__file__).parent / "static" / "index.html"

app = FastAPI(title="Transit AI")
limiter = QuestionLimiter(global_daily_cap=int(os.environ.get("DAILY_QUESTION_CAP", "100")))
# Feedback has its own counters with the same limits, so rating an answer never uses up a question.
feedback_limiter = QuestionLimiter(global_daily_cap=int(os.environ.get("DAILY_QUESTION_CAP", "100")))

# Feedback log lines are capped below 16 KB, where Docker splits a long log line in two.
MAX_FEEDBACK_ANSWER = 6000
MAX_FEEDBACK_TOOL_CALLS = 8
MAX_FEEDBACK_TOOL_RESULT = 600
MAX_COMMENT_LENGTH = 200


def make_logger(name):
    """A logger that writes one line per message to the console, timestamped in UTC."""
    log = logging.getLogger(name)
    if not log.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%SZ")
        formatter.converter = time.gmtime
        handler.setFormatter(formatter)
        log.addHandler(handler)
        log.setLevel(logging.INFO)
    return log


# One log line per /ask request. The question text is never logged by /ask.
logger = make_logger("transit_ai.ask")
# One line per piece of feedback: "FEEDBACK {json}". The visitor chose to send the question and
# answer with it; no IP address is logged.
feedback_logger = make_logger("transit_ai.feedback")


class AskRequest(BaseModel):
    question: str
    agency: str = DEFAULT_AGENCY


class FeedbackRequest(BaseModel):
    agency: str
    question: str = Field(max_length=MAX_QUESTION_LENGTH)
    answer: str = Field(max_length=50_000)
    tool_calls: list[dict] = Field(default_factory=list, max_length=50)
    rating: Literal["up", "down"]
    comment: str = Field(default="", max_length=MAX_COMMENT_LENGTH)


def client_ip(request: Request) -> str:
    """The visitor's IP address, as seen by Azure's proxy in front of the app.

    Behind a proxy, every request arrives from the proxy's own address, so the proxy adds
    the visitor's address to the X-Forwarded-For header. A visitor can send that header too,
    with any value they like, so only the last (rightmost) entry, the one added by the proxy,
    can be trusted. With no header (running locally), use the address that connected.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


@app.get("/", include_in_schema=False)
def index():
    """The demo page: a question box that calls /ask and shows the answer."""
    return FileResponse(INDEX_PAGE)


@app.get("/health")
def health():
    return {"status": "ok"}


# A plain "def" (not "async def") so FastAPI runs this slow, blocking call in a worker
# thread instead of holding up other requests while Claude thinks.
@app.post("/ask")
def ask(body: AskRequest, request: Request):
    """Ask the agent a question; returns its answer, the tool calls it made and the rounds used."""
    status, rounds, rate_limited = 200, None, False
    try:
        question = body.question.strip()
        if not question:
            raise HTTPException(status_code=400, detail="Question must not be empty.")
        if len(question) > MAX_QUESTION_LENGTH:
            raise HTTPException(
                status_code=400,
                detail=f"Question must be {MAX_QUESTION_LENGTH} characters or fewer "
                f"(got {len(question)}).",
            )
        if body.agency not in AGENCIES:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown agency {body.agency!r}; choose one of {', '.join(sorted(AGENCIES))}.",
            )

        try:
            limiter.check_and_record(client_ip(request))
        except RateLimitExceeded as e:
            rate_limited = True
            raise HTTPException(
                status_code=429,
                detail=e.message,
                headers={"Retry-After": str(e.retry_after_seconds)},
            )

        try:
            result = answer_question(question, body.agency)
        except AgentError as e:
            raise HTTPException(status_code=500, detail=f"The agent could not answer: {e}")
        except anthropic.APIError:
            raise HTTPException(status_code=502, detail="The Anthropic API request failed; try again.")
        rounds = result["rounds"]
        return {key: result[key] for key in ("answer", "tool_calls", "rounds")}
    except HTTPException as e:
        status = e.status_code
        raise
    except Exception:
        status = 500
        raise
    finally:
        logger.info(
            "/ask status=%s rounds=%s rate_limited=%s",
            status,
            rounds if rounds is not None else "-",
            "yes" if rate_limited else "no",
        )


def feedback_record(body: FeedbackRequest):
    """What one piece of feedback logs: everything the visitor sent, trimmed to fit one log line."""
    calls = [{"name": str(c.get("name", "")), "input": c.get("input", {}),
              "result": str(c.get("result", ""))[:MAX_FEEDBACK_TOOL_RESULT]}
             for c in body.tool_calls[:MAX_FEEDBACK_TOOL_CALLS]]
    return {
        "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "agency": body.agency,
        "question": body.question.strip(),
        "answer": body.answer[:MAX_FEEDBACK_ANSWER],
        "tool_calls": calls,
        "rating": body.rating,
        "comment": " ".join(body.comment.split()),  # one line
        "truncated": len(body.answer) > MAX_FEEDBACK_ANSWER
        or len(body.tool_calls) > MAX_FEEDBACK_TOOL_CALLS
        or any(len(str(c.get("result", ""))) > MAX_FEEDBACK_TOOL_RESULT for c in body.tool_calls),
    }


@app.post("/feedback")
def feedback(body: FeedbackRequest, request: Request):
    """Thumbs up or down on one answer, with an optional one-line comment, written to the log."""
    if body.agency not in AGENCIES:
        raise HTTPException(status_code=400, detail=f"Unknown agency {body.agency!r}.")
    try:
        feedback_limiter.check_and_record(client_ip(request))  # the IP is only counted, never logged
    except RateLimitExceeded as e:
        raise HTTPException(status_code=429, detail=e.message,
                            headers={"Retry-After": str(e.retry_after_seconds)})
    feedback_logger.info("FEEDBACK %s", json.dumps(feedback_record(body)))
    return {"status": "ok"}
