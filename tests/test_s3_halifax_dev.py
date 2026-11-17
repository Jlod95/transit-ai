"""experiments/foundry/s3_halifax_dev.py, offline: task selection, cached-token capture, the
three cost figures, the stop rule, and the Foundry loop's grader result shape and 5-round cap.
No Azure packages, sign-in or network needed (tools read the committed Halifax summary)."""

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).parent.parent / "experiments" / "foundry" / "s3_halifax_dev.py"
sys.path.insert(0, str(SCRIPT.parent))
spec = importlib.util.spec_from_file_location("s3_halifax_dev", SCRIPT)
s3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s3)


def test_only_the_14_halifax_dev_tasks():
    tasks = s3.halifax_dev_tasks()
    assert len(tasks) == 14
    assert {t["agency"] for t in tasks} == {"halifax"} and {t["split"] for t in tasks} == {"dev"}
    assert [t["id"] for t in s3.halifax_dev_tasks(smoke=True)] == ["halifax-01-block_distance"]


def test_openrouter_usage_with_and_without_cache_details():
    full = {"prompt_tokens": 1849, "completion_tokens": 155, "cost": 0.0005,
            "prompt_tokens_details": {"cached_tokens": 1792}}
    assert s3.openrouter_round(full) == {"input_tokens": 1849, "cached_input_tokens": 1792,
                                         "output_tokens": 155, "charged_usd": 0.0005}
    assert s3.openrouter_round({"prompt_tokens": 752, "completion_tokens": 69})["cached_input_tokens"] == 0


def test_foundry_usage_with_and_without_cache_details():
    cached = SimpleNamespace(input_tokens=1608, output_tokens=255,
                             input_tokens_details=SimpleNamespace(cached_tokens=1024))
    assert s3.foundry_round(cached) == {"input_tokens": 1608, "cached_input_tokens": 1024,
                                        "output_tokens": 255, "charged_usd": None}
    bare = SimpleNamespace(input_tokens=752, output_tokens=69, input_tokens_details=None)
    assert s3.foundry_round(bare)["cached_input_tokens"] == 0


def test_cost_at_list_price_cache_priced_and_charged():
    # The 15 Nov OpenRouter run: 2,601 in (1,792 cached), 224 out; OpenRouter charged $0.0008612.
    rounds = [{"input_tokens": 752, "cached_input_tokens": 0, "output_tokens": 69, "charged_usd": 0.0003},
              {"input_tokens": 1849, "cached_input_tokens": 1792, "output_tokens": 155, "charged_usd": 0.0005612}]
    c = s3.costs(rounds)
    assert c["list_usd"] == pytest.approx(0.0013988)
    assert c["cache_priced_usd"] == pytest.approx(0.0008612)
    assert c["charged_usd"] == pytest.approx(0.0008612)
    assert s3.costs([{**rounds[0], "charged_usd": None}])["charged_usd"] is None  # Foundry: not reported


def test_budget_stops_new_attempts_past_the_cap():
    budget = s3.Budget(cap=2.0)
    budget.add(1.99)
    assert not budget.exceeded()
    budget.add(0.02)
    assert budget.exceeded()


class FakeClient:
    """Stands in for the agent's OpenAI client: returns queued responses, remembers requests."""

    def __init__(self, responses):
        self.queue, self.requests = list(responses), []
        self.responses = SimpleNamespace(create=self.create)

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return self.queue.pop(0)


def usage(n_in, n_out, cached=0):
    return SimpleNamespace(input_tokens=n_in, output_tokens=n_out,
                           input_tokens_details=SimpleNamespace(cached_tokens=cached))


def tool_call_response(response_id):
    args = {"agency": "halifax", "block_id": "722145", "date": "2026-10-14"}
    return SimpleNamespace(id=response_id, usage=usage(2000, 60), output=[SimpleNamespace(
        type="function_call", name="get_block_distance", call_id=f"call_{response_id}",
        arguments=json.dumps(args))])


def test_foundry_attempt_gives_the_grader_its_usual_shape():
    final = SimpleNamespace(id="r2", usage=usage(3000, 120, cached=1792), output_text="80.5 km.",
                            output=[SimpleNamespace(type="message")])
    client = FakeClient([tool_call_response("r1"), final])
    result, rounds = s3.attempt_foundry(client, {"question": "How far does block 722145 drive?"})
    assert result["answer"] == "80.5 km."
    assert [c["name"] for c in result["tool_calls"]] == ["get_block_distance"]
    assert "80.5 revenue km" in result["tool_calls"][0]["result"]
    assert [r["cached_input_tokens"] for r in rounds] == [0, 1792]
    # Round 2 sends only the tool output and points at the stored response.
    assert client.requests[1]["previous_response_id"] == "r1"
    assert client.requests[1]["input"][0]["call_id"] == "call_r1"


def test_foundry_attempt_stops_after_five_rounds():
    client = FakeClient([tool_call_response(f"r{n}") for n in range(1, 7)])
    result, rounds = s3.attempt_foundry(client, {"question": "loop forever"})
    assert result == {"error": "AgentError: Stopped after 5 rounds without a final answer"}
    assert len(rounds) == 5 and len(client.requests) == 5
