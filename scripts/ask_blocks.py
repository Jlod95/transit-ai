"""Ask Claude a question it can answer using our block distance, duration and fleet
feasibility code as tools.

Usage:
    python scripts/ask_blocks.py "How long is block 722145 in service on 14 October 2026?"
    python scripts/ask_blocks.py            (no question: asks a built-in example)

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

from src.blocks import daily_block_distance, daily_block_duration
from src.feasibility import fleet_feasibility

MODEL = "claude-opus-5-5"
HALIFAX_FEED = PROJECT_ROOT / "data" / "raw" / "halifax.zip"
MAX_ROUNDS = 5  # safety limit on API calls per run
DEFAULT_QUESTION = (
    "How far does block 722145 drive on 14 October 2026, "
    "and could a typical electric bus do that on one charge?"
)

SYSTEM = (
    "You help assess whether Halifax Transit bus blocks could be run by battery-electric buses. "
    "Use the tools for block distances and service times rather than guessing. "
    "For battery size, energy use and range, use only the numbers returned by "
    "get_fleet_feasibility, not your own estimates, and say clearly that these are "
    "placeholder assumptions that have not yet been sourced."
)

# Both tools take the same inputs.
BLOCK_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "block_id": {"type": "string", "description": "GTFS block_id, e.g. '722145'"},
        "date": {"type": "string", "description": "Service date as YYYY-MM-DD"},
    },
    "required": ["block_id", "date"],
    "additionalProperties": False,
}

# What Claude is told about each tool: its name, what it does, and the inputs it takes.
# The descriptions say what each one measures, its unit, and when NOT to use it.
TOOLS = [
    {
        "name": "get_block_distance",
        "description": (
            "DISTANCE: how many kilometres one Halifax Transit bus block drives on a given "
            "service date, from the GTFS schedule. Use for questions about how far a bus "
            "travels, mileage, or range/battery needs. Returns revenue km only (trips carrying "
            "passengers); empty running to/from the garage (deadhead) is not included. "
            "Does not give times; use get_block_duration for how long the bus is in service."
        ),
        "input_schema": BLOCK_INPUT_SCHEMA,
        "strict": True,
    },
    {
        "name": "get_block_duration",
        "description": (
            "TIME IN SERVICE: how long one Halifax Transit bus block is in service on a given "
            "service date, from the first trip's first departure to the last trip's last "
            "arrival, in hours and minutes. Use for questions about how long a bus is out, "
            "its working day, start/end span, or time available for charging. Includes layovers "
            "between trips; excludes garage pull-out/pull-in. Does not give distance; use "
            "get_block_distance for how far the bus drives."
        ),
        "input_schema": BLOCK_INPUT_SCHEMA,
        "strict": True,
    },
    {
        "name": "get_fleet_feasibility",
        "description": (
            "WHOLE FLEET ON ONE CHARGE: for every Halifax Transit bus block on a service date, "
            "checks whether its daily distance fits within one full battery charge in the given "
            "season. Use for fleet-wide questions such as how many or what share of blocks an "
            "electric bus could run, or which blocks are hardest. Returns the range used (km), "
            "block counts within/over range, % within range, the 5 longest blocks with km, and "
            "the assumptions. Range = nominal battery kWh x usable fraction / kWh per km. Only "
            "80% of the nominal battery is counted as usable: industry practice keeps a 20% "
            "reserve, since routinely discharging below it speeds up battery wear and leaves no "
            "margin for delays and cold. Battery size and kWh per km are placeholders, not yet "
            "sourced. Assumes one "
            "overnight charge and no daytime charging; uses revenue km only, so it is optimistic. "
            "For one specific block, use get_block_distance or get_block_duration instead."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Service date as YYYY-MM-DD"},
                "season": {
                    "type": "string",
                    "enum": ["summer", "winter"],
                    "description": "Season for energy use; winter uses more (heating)",
                },
            },
            "required": ["date", "season"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


def lookup_block(block_values, block_id, date_text):
    """Return (value, None) for the block, or (None, message) if it isn't running."""
    if not block_values:
        return None, f"No bus service in the feed on {date_text}; the feed may not cover that date."
    if block_id not in block_values:
        return None, f"Block {block_id} does not run on {date_text}."
    return block_values[block_id], None


def get_block_distance(block_id, date_text):
    """Run our tested code and return a short text result for Claude."""
    distances = daily_block_distance(HALIFAX_FEED, date.fromisoformat(date_text))
    km, message = lookup_block(distances, block_id, date_text)
    if message:
        return message
    return f"Block {block_id} drives {km:.1f} revenue km on {date_text}."


def get_block_duration(block_id, date_text):
    """Run our tested code and return a short text result for Claude."""
    durations = daily_block_duration(HALIFAX_FEED, date.fromisoformat(date_text))
    minutes, message = lookup_block(durations, block_id, date_text)
    if message:
        return message
    hours, mins = divmod(round(minutes), 60)
    return f"Block {block_id} is in service for {hours} h {mins} min on {date_text}."


def get_fleet_feasibility(date_text, season):
    """Run the fleet check and return its summary as JSON text for Claude."""
    result = fleet_feasibility(HALIFAX_FEED, date.fromisoformat(date_text), season)
    if result["total_blocks"] == 0:
        return f"No bus service in the feed on {date_text}; the feed may not cover that date."
    return json.dumps(result)


# Each tool name, and how to call its Python function with Claude's inputs.
TOOL_FUNCTIONS = {
    "get_block_distance": lambda i: get_block_distance(i["block_id"], i["date"]),
    "get_block_duration": lambda i: get_block_duration(i["block_id"], i["date"]),
    "get_fleet_feasibility": lambda i: get_fleet_feasibility(i["date"], i["season"]),
}


def run_tool(name, tool_input):
    """Return (result text, is_error) for one tool call from Claude."""
    if name not in TOOL_FUNCTIONS:
        return f"Unknown tool: {name}", True
    try:
        return TOOL_FUNCTIONS[name](tool_input), False
    except ValueError as e:
        return f"Invalid input: {e}", True


def main():
    load_dotenv(PROJECT_ROOT / ".env")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY not found: add it to .env and save the file")
    if not HALIFAX_FEED.exists():
        sys.exit(f"Feed not found: {HALIFAX_FEED}")

    # Everything typed after the script name is the question.
    question = " ".join(sys.argv[1:]).strip() or DEFAULT_QUESTION

    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": question}]
    print(f"QUESTION: {question}\n")

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
