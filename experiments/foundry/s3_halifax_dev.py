"""S3: the 14 Halifax dev tasks on gpt-4.1-mini, your own loop vs a Foundry prompt agent.

Usage:
    python experiments/foundry/s3_halifax_dev.py --smoke          # 1 task, 1 attempt, both setups
    python experiments/foundry/s3_halifax_dev.py --k 3 --concurrency 3

Setups, same model (gpt-4.1-mini), same 8 tools (real names, identical descriptions and schemas
from src/agent.py), same system prompt, tools run on this machine, at most 5 model calls each:
  own      your loop (src.agent.answer_question) via OpenRouter; history resent every round
  foundry  a Foundry prompt agent on the project's deployment; history kept by Foundry
           (previous_response_id). One agent version for the run, deleted in a finally block.

Every attempt is graded by evals/verify.py exactly as evals/run.py does (frozen grader eval-v1.3,
imported, not changed), against the same agent context. Per round it records input, cached input
and output tokens. Cost is reported at list price (all input at the full rate), cache-priced
(cached input at the cached rate) and, where the provider reports it, as charged: OpenRouter
returns its charge per call; Foundry doesn't, so its "as charged" is the cache-priced figure,
computed, not billed. Stops starting new attempts once the list-price total passes $2.

src/ and evals/ are not edited: OpenRouter's usage is captured by wrapping
src.providers.parse_openrouter in memory for the run. Writes experiments/foundry/results/.
"""

import argparse
import hashlib
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).parent
PROJECT_ROOT = HERE.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(HERE))

from compare_agents import run_function_calls, tool_specs
from hello_foundry import read_settings

from evals.run import CHECKS, TASKS, agent_context, load_tasks
from evals.verify import verify
from src import agent, providers
from src.provenance import current_git_commit

AGENCY = "halifax"
DEV_TASKS = 14
SMOKE_TASK = "halifax-01-block_distance"
OPENROUTER_MODEL = "openrouter:openai/gpt-4.1-mini"
AGENT_NAME = "transit-ai-s3"
MAX_ROUNDS = 5
# US$ per million tokens for gpt-4.1-mini: OpenRouter's list and Azure's retail price list agree.
PRICE = {"input": 0.40, "cached_input": 0.10, "output": 1.60}
STOP_AT_USD = 2.00
GRADER = "eval-v1.3"
RESULTS = HERE / "results"

assert agent.MAX_ROUNDS == MAX_ROUNDS, "the own loop's round cap changed; S3 compares at 5 rounds"


def halifax_dev_tasks(smoke=False):
    """The 14 Halifax dev tasks (or just SMOKE_TASK); refuses to run on any other set."""
    tasks = [t for t in load_tasks("dev", []) if t["agency"] == AGENCY and t["split"] == "dev"]
    if len(tasks) != DEV_TASKS:
        raise SystemExit(f"Expected {DEV_TASKS} Halifax dev tasks, found {len(tasks)}")
    return [t for t in tasks if t["id"] == SMOKE_TASK] if smoke else tasks


# --- per-round usage and cost ---

def openrouter_round(usage):
    """One OpenRouter call's usage (its JSON "usage" object) as a round record."""
    details = usage.get("prompt_tokens_details") or {}
    return {"input_tokens": usage.get("prompt_tokens", 0),
            "cached_input_tokens": details.get("cached_tokens") or 0,
            "output_tokens": usage.get("completion_tokens", 0),
            "charged_usd": usage.get("cost")}


def foundry_round(usage):
    """One Foundry Responses call's usage object as a round record (no charge is reported)."""
    details = getattr(usage, "input_tokens_details", None)
    return {"input_tokens": usage.input_tokens,
            "cached_input_tokens": (getattr(details, "cached_tokens", None) or 0) if details else 0,
            "output_tokens": usage.output_tokens,
            "charged_usd": None}


def costs(rounds):
    """{"list_usd", "cache_priced_usd", "charged_usd"} for an attempt's rounds; charged_usd is
    None unless every round reported a charge."""
    tokens_in = sum(r["input_tokens"] for r in rounds)
    cached = sum(r["cached_input_tokens"] for r in rounds)
    tokens_out = sum(r["output_tokens"] for r in rounds)
    charged = [r["charged_usd"] for r in rounds]
    return {
        "list_usd": (tokens_in * PRICE["input"] + tokens_out * PRICE["output"]) / 1e6,
        "cache_priced_usd": ((tokens_in - cached) * PRICE["input"] + cached * PRICE["cached_input"]
                             + tokens_out * PRICE["output"]) / 1e6,
        "charged_usd": sum(charged) if rounds and all(c is not None for c in charged) else None,
    }


class Budget:
    """Running list-price total across both setups; no new attempt starts once it passes the cap."""

    def __init__(self, cap=STOP_AT_USD):
        self.cap, self.spent, self._lock = cap, 0.0, threading.Lock()

    def exceeded(self):
        with self._lock:
            return self.spent > self.cap

    def add(self, usd):
        with self._lock:
            self.spent += usd


# --- setup "own": your loop via OpenRouter, usage captured per thread ---

_capture = threading.local()


def _recording_parse(original):
    def parse(body):
        result = original(body)
        rounds = getattr(_capture, "rounds", None)
        if rounds is not None:
            rounds.append(openrouter_round(body.get("usage") or {}))
        return result
    return parse


def attempt_own(task):
    """(result for the grader, rounds) for one attempt of your loop."""
    _capture.rounds = []
    try:
        out = agent.answer_question(task["question"], AGENCY, model=OPENROUTER_MODEL)
        result = {"answer": out["answer"], "tool_calls": out["tool_calls"]}
    except (agent.AgentError, providers.ProviderError, ValueError) as e:  # failed attempt, not a crash
        result = {"error": f"{type(e).__name__}: {e}"}
    rounds, _capture.rounds = _capture.rounds, None
    return result, rounds


# --- setup "foundry": the same loop shape against a prompt agent ---

def api_errors():
    """Errors that make an attempt fail (as anthropic.APIError does in evals/run.py) rather
    than stop the run; the OpenAI and Azure packages are optional so the tests run without them."""
    errors = []
    try:
        from openai import APIError
        errors.append(APIError)
    except ImportError:
        pass
    try:
        from azure.core.exceptions import AzureError
        errors.append(AzureError)
    except ImportError:
        pass
    return tuple(errors)


def attempt_foundry(client, task):
    """(result for the grader, rounds) for one attempt against the agent: tools run here,
    history stays on Foundry, at most MAX_ROUNDS model calls."""
    rounds, calls = [], []
    try:
        response = client.responses.create(input=task["question"])
        for round_number in range(1, MAX_ROUNDS + 1):
            rounds.append(foundry_round(response.usage))
            outputs, new_calls = run_function_calls(response.output)
            calls += new_calls
            if not outputs:
                return {"answer": response.output_text, "tool_calls": calls}, rounds
            if round_number == MAX_ROUNDS:
                break
            response = client.responses.create(input=outputs, previous_response_id=response.id)
        return {"error": f"AgentError: Stopped after {MAX_ROUNDS} rounds without a final answer"}, rounds
    except api_errors() as e:  # an API failure is a failed attempt, as in evals/run.py
        return {"error": f"{type(e).__name__}: {e}"}, rounds


def foundry_agent(project, settings):
    """Create the agent version and route its endpoint to it; returns (version, original endpoint)."""
    from azure.ai.projects.models import (
        AgentEndpointConfig,
        FixedRatioVersionSelectionRule,
        FunctionTool,
        PromptAgentDefinition,
        ProtocolConfiguration,
        ResponsesProtocolConfiguration,
        VersionSelector,
    )

    version = project.agents.create_version(agent_name=AGENT_NAME, definition=PromptAgentDefinition(
        model=settings["FOUNDRY_MODEL"],
        instructions=agent.system_prompt(AGENCY),
        tools=[FunctionTool(**spec) for spec in tool_specs([t["name"] for t in agent.TOOLS])],
    ))
    original = project.agents.get(agent_name=AGENT_NAME).agent_endpoint
    project.agents.update_details(agent_name=AGENT_NAME, agent_endpoint=AgentEndpointConfig(
        version_selector=VersionSelector(version_selection_rules=[
            FixedRatioVersionSelectionRule(agent_version=version.version, traffic_percentage=100)]),
        protocol_configuration=ProtocolConfiguration(responses=ResponsesProtocolConfiguration()),
    ))
    return version, original


# --- running and grading ---

def graded(setup, model, task, attempt, result, rounds, seconds, context):
    checks = verify(task, result, context)
    return {
        "setup": setup, "model": model, "task_id": task["id"], "agency": task["agency"],
        "category": task["category"], "attempt": attempt, "pass": checks["pass"], "checks": checks,
        "seconds": round(seconds, 1), "rounds": rounds,
        "usage": {k: sum(r[k] for r in rounds) for k in ("input_tokens", "cached_input_tokens", "output_tokens")},
        **{f"cost_{k}": v for k, v in costs(rounds).items()},
        **result,
    }


def run_setup(setup, model, attempt_fn, tasks, k, concurrency, context, budget):
    def one(task, attempt):
        if budget.exceeded():
            return {"setup": setup, "task_id": task["id"], "attempt": attempt, "skipped": "budget"}
        started = time.perf_counter()
        result, rounds = attempt_fn(task)
        record = graded(setup, model, task, attempt, result, rounds, time.perf_counter() - started, context)
        budget.add(record["cost_list_usd"])
        status = "PASS" if record["pass"] else "fail " + ",".join(c for c in CHECKS if not record["checks"][c]["pass"])
        print(f"  {setup:8} {task['id']:32} #{attempt} {status:28} {len(rounds)} rounds "
              f"${record['cost_list_usd']:.4f}", flush=True)
        return record

    jobs = [(t, a) for t in tasks for a in range(1, k + 1)]
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        return [f.result() for f in [pool.submit(one, t, a) for t, a in jobs]]


def summary_lines(records, k):
    lines = []
    for setup in ("own", "foundry"):
        done = [r for r in records if r["setup"] == setup and "skipped" not in r]
        if not done:
            continue
        by_task = {}
        for r in done:
            by_task.setdefault(r["task_id"], []).append(r["pass"])
        failed = {c: sum(not r["checks"][c]["pass"] for r in done) for c in CHECKS}
        total = {key: sum(r[key] or 0 for r in done) for key in ("cost_list_usd", "cost_cache_priced_usd")}
        charged = [r["cost_charged_usd"] for r in done]
        charged_text = (f"${sum(charged):.4f} (reported by OpenRouter)" if all(c is not None for c in charged)
                        else f"${total['cost_cache_priced_usd']:.4f} (cache-priced: computed, not billed)")
        tokens = {key: sum(r["usage"][key] for r in done) for key in ("input_tokens", "cached_input_tokens", "output_tokens")}
        lines += [
            f"## {setup}: {done[0]['model']}", "",
            (f"- Attempts passed: {sum(r['pass'] for r in done)}/{len(done)}; "
            f"pass@{k} {sum(any(v) for v in by_task.values())}/{len(by_task)}, "
            f"pass^{k} {sum(all(v) for v in by_task.values())}/{len(by_task)}"),
            "- Failed attempts by check: " + ", ".join(f"{c} {n}" for c, n in failed.items()),
            (f"- Tokens: {tokens['input_tokens']:,} in (of which {tokens['cached_input_tokens']:,} cached), "
            f"{tokens['output_tokens']:,} out"),
            f"- Cost at list price: ${total['cost_list_usd']:.4f}; as charged: {charged_text}",
            "",
            "| Task | # | Result | Round tokens: in (cached) / out | List $ | Charged $ |",
            "|---|---|---|---|---|---|",
        ]
        for r in done:
            result = "PASS" if r["pass"] else "fail " + ",".join(c for c in CHECKS if not r["checks"][c]["pass"])
            per_round = "; ".join(f"{x['input_tokens']:,} ({x['cached_input_tokens']:,}) / {x['output_tokens']:,}"
                                  for x in r["rounds"])
            charged_cell = f"{r['cost_charged_usd']:.5f}" if r["cost_charged_usd"] is not None else "n/a"
            lines.append(f"| {r['task_id']} | {r['attempt']} | {result} | {per_round} | "
                         f"{r['cost_list_usd']:.5f} | {charged_cell} |")
        lines.append("")
    skipped = [r for r in records if "skipped" in r]
    if skipped:
        lines.append(f"Skipped {len(skipped)} attempts: the ${STOP_AT_USD:.2f} list-price stop rule was reached.")
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--smoke", action="store_true", help=f"only {SMOKE_TASK}, 1 attempt")
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--concurrency", type=int, default=3)
    args = parser.parse_args()
    k = 1 if args.smoke else args.k

    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
    settings = read_settings(os.environ)
    tasks = halifax_dev_tasks(smoke=args.smoke)
    context = agent_context(AGENCY)
    budget = Budget()
    stamp = {
        "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "experiment": "S3", "smoke": args.smoke, "k": k, "concurrency": args.concurrency,
        "tasks": [t["id"] for t in tasks], "grader": GRADER, "git_commit": current_git_commit(),
        "verify_sha256": hashlib.sha256((PROJECT_ROOT / "evals" / "verify.py").read_bytes()).hexdigest(),
        "tasks_sha256": hashlib.sha256(TASKS.read_bytes()).hexdigest(),
        "price_per_mtok": PRICE, "stop_at_usd": STOP_AT_USD, "max_rounds": MAX_ROUNDS,
    }
    print(f"S3: {len(tasks)} task(s) x k={k}, own via OpenRouter and Foundry agent, {args.concurrency} at a time")

    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    records = []
    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=settings["FOUNDRY_PROJECT_ENDPOINT"], credential=credential) as project,
    ):
        version = original = None
        try:
            version, original = foundry_agent(project, settings)
            print(f"Created Foundry agent {AGENT_NAME} version {version.version}")
            with project.get_openai_client(agent_name=AGENT_NAME) as client:
                records += run_setup("foundry", f"foundry:{settings['FOUNDRY_MODEL']}",
                                     lambda task: attempt_foundry(client, task),
                                     tasks, k, args.concurrency, context, budget)
        finally:
            if original is not None:
                project.agents.update_details(agent_name=AGENT_NAME, agent_endpoint=original)
            if version is not None:
                project.agents.delete_version(agent_name=AGENT_NAME, agent_version=version.version, force=True)
                print(f"Deleted Foundry agent {AGENT_NAME} version {version.version}")

    original_parse = providers.parse_openrouter
    providers.parse_openrouter = _recording_parse(original_parse)
    try:
        records = run_setup("own", OPENROUTER_MODEL, attempt_own, tasks, k, args.concurrency,
                            context, budget) + records
    finally:
        providers.parse_openrouter = original_parse

    report = [f"# S3: Halifax dev, gpt-4.1-mini, own loop vs Foundry agent ({'smoke' if args.smoke else 'full'})", ""]
    report += [f"- {key}: `{value}`" for key, value in stamp.items()] + [""] + summary_lines(records, k)
    RESULTS.mkdir(exist_ok=True)
    name = f"{stamp['timestamp'].replace(':', '').replace('-', '')}-s3-{'smoke' if args.smoke else f'k{k}'}"
    (RESULTS / f"{name}.json").write_text(
        json.dumps({"stamp": stamp, "context": context, "records": records}, indent=1) + "\n",
        encoding="utf-8", newline="\n")
    (RESULTS / f"{name}.md").write_text("\n".join(report) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(summary_lines(records, k)))
    print(f"List-price total ${budget.spent:.4f}; wrote experiments/foundry/results/{name}.json and .md")


if __name__ == "__main__":
    main()
