"""Send one message to Claude and print the reply.

Usage:
    python scripts/hello_llm.py

Reads ANTHROPIC_API_KEY from the project's .env file. The key is never printed.
"""

import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

MODEL = "claude-opus-5-5"
ENV_FILE = Path(__file__).parent.parent / ".env"


def main():
    # Copy the variables in .env into this process's environment, where the SDK looks for them.
    load_dotenv(ENV_FILE)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit(f"ANTHROPIC_API_KEY not found: add it to {ENV_FILE} and save the file")

    try:
        client = anthropic.Anthropic()
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=2000,
            output_config={"effort": "low"},
            # If Claude's safety filters decline, retry on Anthropic's recommended fallback model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": "Say hello in one sentence"}],
        )
    except anthropic.AuthenticationError:
        sys.exit("API key missing or invalid: check ANTHROPIC_API_KEY in .env")
    except anthropic.APIConnectionError:
        sys.exit("Could not reach the Anthropic API: check your internet connection")
    except anthropic.APIStatusError as e:
        sys.exit(f"API error {e.status_code}: {e.message}")

    if response.stop_reason == "refusal":
        sys.exit("Claude declined to answer this request")

    # The reply is a list of content blocks; print the text ones.
    for block in response.content:
        if block.type == "text":
            print(block.text)


if __name__ == "__main__":
    main()
