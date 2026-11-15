"""experiments/foundry/compare_agents.py, offline: the Foundry tool definitions match src/agent.py
exactly, and function calls from a Responses output run locally. No Azure packages, sign-in or
network needed (the tools read the committed Halifax summary)."""

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from src.agent import TOOLS

SCRIPT = Path(__file__).parent.parent / "experiments" / "foundry" / "compare_agents.py"
sys.path.insert(0, str(SCRIPT.parent))  # for its `from hello_foundry import read_settings`
spec = importlib.util.spec_from_file_location("compare_agents", SCRIPT)
compare_agents = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compare_agents)


def test_foundry_tools_are_the_real_tools_unchanged():
    specs = compare_agents.tool_specs()
    originals = {t["name"]: t for t in TOOLS}
    assert [s["name"] for s in specs] == ["get_block_distance", "get_fleet_size"]
    for s in specs:
        assert s["description"] == originals[s["name"]]["description"]
        assert s["parameters"] == originals[s["name"]]["input_schema"]
        assert s["strict"] is True


def test_function_calls_run_locally_and_answer_by_call_id():
    args = {"agency": "halifax", "block_id": "722145", "date": "2026-10-14"}
    output = [
        SimpleNamespace(type="message", content="thinking aloud"),  # not a tool call: ignored
        SimpleNamespace(type="function_call", name="get_block_distance", call_id="call_1",
                        arguments=json.dumps(args)),
    ]
    outputs, calls = compare_agents.run_function_calls(output)
    assert outputs == [{"type": "function_call_output", "call_id": "call_1", "output": calls[0]["result"]}]
    assert calls[0]["name"] == "get_block_distance" and calls[0]["input"] == args
    assert "80.5 revenue km" in calls[0]["result"]


def test_no_function_calls_means_final_answer():
    assert compare_agents.run_function_calls([SimpleNamespace(type="message")]) == ([], [])
