import logging
import os
import time
from pathlib import Path

import anthropic
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.agencies import AGENCIES, DEFAULT_AGENCY
from src.agent import AgentError, answer_question
from src.rate_limit import QuestionLimiter, RateLimitExceeded

MAX_QUESTION_LENGTH = 500
INDEX_PAGE = Path(__file__).parent / "static" / "index.html"

app = FastAPI(title="Transit AI")
limiter = QuestionLimiter(global_daily_cap=int(os.environ.get("DAILY_QUESTION_CAP", "100")))

# One log line per /ask request, timestamped in UTC. The question text is never logged.
logger = logging.getLogger("transit_ai.ask")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%SZ")
    formatter.converter = time.gmtime
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class AskRequest(BaseModel):
    question: str
    agency: str = DEFAULT_AGENCY


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
