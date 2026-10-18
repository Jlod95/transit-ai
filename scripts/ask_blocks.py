"""Ask the Transit AI agent a question from the command line and watch each step.

Usage:
    python scripts/ask_blocks.py "How long is block 722145 in service on 14 October 2026?"
    python scripts/ask_blocks.py            (no question: asks a built-in example)

The agent itself lives in src/agent.py; this script only passes the question in and prints
progress as it happens.
"""

import sys
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).parent.parent))  # so "src" can be imported

from src.agent import AgentError, answer_question

DEFAULT_QUESTION = (
    "How far does block 722145 drive on 14 October 2026, "
    "and could a typical electric bus do that on one charge?"
)


def main():
    # Everything typed after the script name is the question.
    question = " ".join(sys.argv[1:]).strip() or DEFAULT_QUESTION
    try:
        answer_question(question, log=print)
    except AgentError as e:
        sys.exit(str(e))
    except anthropic.AuthenticationError:
        sys.exit("API key missing or invalid: check ANTHROPIC_API_KEY in .env")
    except anthropic.APIConnectionError:
        sys.exit("Could not reach the Anthropic API: check your internet connection")
    except anthropic.APIStatusError as e:
        sys.exit(f"API error {e.status_code}: {e.message}")


if __name__ == "__main__":
    main()
