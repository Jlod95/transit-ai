"""The Transit AI agent: answers a question with Claude, using our block and fleet
feasibility code as tools.

answer_question() runs the tool-use loop and returns the answer plus every tool call made.
It is used by scripts/ask_blocks.py (command line) and the POST /ask endpoint in main.py.
Reads ANTHROPIC_API_KEY from the environment or the project's .env file, and the feed from
FEED_PATH (default data/raw/halifax.zip, relative to the project root).
"""

import json
import os
from datetime import date
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from src.blocks import MissingDistanceError, daily_block_distance, daily_block_duration
from src.feasibility import fleet_feasibility

PROJECT_ROOT = Path(__file__).parent.parent

MODEL = "claude-opus-5-5"
# A relative FEED_PATH is taken from the project root; an absolute one is used as is.
FEED_PATH_SETTING = os.environ.get("FEED_PATH", "data/raw/halifax.zip")
HALIFAX_FEED = PROJECT_ROOT / FEED_PATH_SETTING
MAX_ROUNDS = 5  # safety limit on API calls per run

SYSTEM = (
    "You help assess whether Halifax Transit bus blocks could be run by battery-electric buses. "
    "Use the tools for block distances and service times rather than guessing. "
    "For battery size, energy use and range, use only the numbers returned by "
    "get_fleet_feasibility, not your own estimates, and say clearly that these are "
    "placeholder assumptions that have not yet been sourced."
)

# The two single-block tools take the same inputs.
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
    except MissingDistanceError as e:
        return f"Feed data problem: {e}", True
    except ValueError as e:
        return f"Invalid input: {e}", True


class AgentError(Exception):
    """The agent could not produce an answer: missing setup, a refusal, or no final answer."""


def answer_question(question, log=None):
    """Answer one question and return {"answer", "tool_calls", "rounds"}.

    tool_calls lists every tool Claude asked for, as {"name", "input", "result"}.
    log, if given, is called with each progress line as it happens (the script passes print).
    Raises AgentError for setup problems or no answer; Anthropic API errors are passed through.
    """
    log = log or (lambda text: None)

    load_dotenv(PROJECT_ROOT / ".env")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise AgentError("ANTHROPIC_API_KEY not found: add it to .env and save the file")
    if not HALIFAX_FEED.exists():
        raise AgentError(f"Halifax feed not found at {FEED_PATH_SETTING} (set FEED_PATH)")

    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": question}]
    tool_calls = []
    log(f"QUESTION: {question}\n")

    for round_number in range(1, MAX_ROUNDS + 1):
        log(f"--- Round {round_number}: sending conversation to Claude ---")
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

        # Keep Claude's whole reply in the conversation, exactly as it came back.
        messages.append({"role": "assistant", "content": response.content})

        texts = [b.text for b in response.content if b.type == "text" and b.text.strip()]
        label = "FINAL ANSWER" if response.stop_reason == "end_turn" else "CLAUDE SAYS"
        for text in texts:
            log(f"{label}:\n{text}\n")

        if response.stop_reason == "end_turn":
            return {"answer": "\n\n".join(texts), "tool_calls": tool_calls, "rounds": round_number}
        if response.stop_reason == "refusal":
            raise AgentError("Claude declined to answer this request")
        if response.stop_reason != "tool_use":
            raise AgentError(f"Stopped unexpectedly (stop_reason={response.stop_reason})")

        # Claude asked for one or more tool calls: run each and send all results back together.
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                log(f"TOOL CALL:   {block.name}({json.dumps(block.input)})")
                result, is_error = run_tool(block.name, block.input)
                log(f"PYTHON SAID: {result}\n")
                tool_calls.append({"name": block.name, "input": block.input, "result": result})
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,  # links this result to the call above
                        "content": result,
                        "is_error": is_error,
                    }
                )
        messages.append({"role": "user", "content": tool_results})

    raise AgentError(f"Stopped after {MAX_ROUNDS} rounds without a final answer")
