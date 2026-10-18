import anthropic
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.agent import AgentError, answer_question

MAX_QUESTION_LENGTH = 500

app = FastAPI(title="Transit AI")


class AskRequest(BaseModel):
    question: str


@app.get("/health")
def health():
    return {"status": "ok"}


# A plain "def" (not "async def") so FastAPI runs this slow, blocking call in a worker
# thread instead of holding up other requests while Claude thinks.
@app.post("/ask")
def ask(request: AskRequest):
    """Ask the agent a question; returns its answer, the tool calls it made and the rounds used."""
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question must not be empty.")
    if len(question) > MAX_QUESTION_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Question must be {MAX_QUESTION_LENGTH} characters or fewer "
            f"(got {len(question)}).",
        )
    try:
        return answer_question(question)
    except AgentError as e:
        raise HTTPException(status_code=500, detail=f"The agent could not answer: {e}")
    except anthropic.APIError:
        raise HTTPException(status_code=502, detail="The Anthropic API request failed; try again.")
