"""Ask Claude a question it can answer using our block-distance code as a tool.

Usage:
    python scripts/ask_blocks.py

Reads ANTHROPIC_API_KEY from the project's .env file and the feed from data/raw/halifax.zip.
Prints each step of the tool-use loop so you can follow it.
"""

import json
import os
import sys
from datetime import date
from pathlib import Path

import anthropic
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))  # so "src.blocks" can be imported when run as a script

from src.blocks import daily_block_distance

MODEL = "claude-opus-5-5"
HALIFAX_FEED = PROJECT_ROOT / "data" / "raw" / "halifax.zip"
MAX_ROUNDS = 5  # safety limit on API calls per run
QUESTION = (
    "How far does block 722145 drive on 14 October 2026, "
    "and could a typical electric bus do that on one charge?"
)

SYSTEM = (
    "You help assess whether Halifax Transit bus blocks could be run by battery-electric buses. "
    "Use the get_block_distance tool for block distances rather than guessing. "
    "When you estimate electric bus range, state the assumptions you used."
)

# What Claude is told about the tool: its name, what it does, and the inputs it takes.
TOOLS = [
    {
        "name": "get_block_distance",
        "description": (
            "Return the daily revenue distance in km for one Halifax Transit bus block on a "
            "given service date, from the GTFS schedule. Revenue km covers trips carrying "
            "passengers only; empty running to/from the garage (deadhead) is not included."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "block_id": {"type": "string", "description": "GTFS block_id, e.g. '722145'"},
                "date": {"type": "string", "description": "Service date as YYYY-MM-DD"},
            },
            "required": ["block_id", "date"],
            "additionalProperties": False,
        },
        "strict": True,
    }
]


def get_block_distance(block_id, date_text):
    """Run our tested code and return a short text result for Claude."""
    service_date = date.fromisoformat(date_text)
    distances = daily_block_distance(HALIFAX_FEED, service_date)
    if not distances:
        return f"No bus service in the feed on {date_text}; the feed may not cover that date."
    if block_id not in distances:
        return f"Block {block_id} does not run on {date_text}."
    return f"Block {block_id} drives {distances[block_id]:.1f} revenue km on {date_text}."


def run_tool(name, tool_input):
    """Return (result text, is_error) for one tool call from Claude."""
    if name != "get_block_distance":
        return f"Unknown tool: {name}", True
    try:
        return get_block_distance(tool_input["block_id"], tool_input["date"]), False
    except ValueError as e:
        return f"Invalid input: {e}", True


def main():
    load_dotenv(PROJECT_ROOT / ".env")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY not found: add it to .env and save the file")
    if not HALIFAX_FEED.exists():
        sys.exit(f"Feed not found: {HALIFAX_FEED}")

    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": QUESTION}]
    print(f"QUESTION: {QUESTION}\n")

    for round_number in range(1, MAX_ROUNDS + 1):
        print(f"--- Round {round_number}: sending conversation to Claude ---")
        try:
            response = client.beta.messages.create(
                model=MODEL,
                max_tokens=16000,
                system=SYSTEM,
                tools=TOOLS,
                messages=messages,
                output_config={"effort": "medium"},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.AuthenticationError:
            sys.exit("API key missing or invalid: check ANTHROPIC_API_KEY in .env")
        except anthropic.APIConnectionError:
            sys.exit("Could not reach the Anthropic API: check your internet connection")
        except anthropic.APIStatusError as e:
            sys.exit(f"API error {e.status_code}: {e.message}")

        # Keep Claude's whole reply in the conversation, exactly as it came back.
        messages.append({"role": "assistant", "content": response.content})

        for block in response.content:
            if block.type == "text" and block.text.strip():
                label = "FINAL ANSWER" if response.stop_reason == "end_turn" else "CLAUDE SAYS"
                print(f"{label}:\n{block.text}\n")

        if response.stop_reason == "end_turn":
            return
        if response.stop_reason == "refusal":
            sys.exit("Claude declined to answer this request")
        if response.stop_reason != "tool_use":
            sys.exit(f"Stopped unexpectedly (stop_reason={response.stop_reason})")

        # Claude asked for one or more tool calls: run each and send all results back together.
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                print(f"TOOL CALL:   {block.name}({json.dumps(block.input)})")
                result, is_error = run_tool(block.name, block.input)
                print(f"PYTHON SAID: {result}\n")
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,  # links this result to the call above
                        "content": result,
                        "is_error": is_error,
                    }
                )
        messages.append({"role": "user", "content": tool_results})

    sys.exit(f"Stopped after {MAX_ROUNDS} rounds without a final answer")


if __name__ == "__main__":
    main()
