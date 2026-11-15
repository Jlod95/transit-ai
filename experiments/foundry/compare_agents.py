"""Compare your own agent loop with a Foundry prompt agent on two of the eight tools.

Usage:
    python experiments/foundry/compare_agents.py

One question, three columns, each run once:
  1. your loop (src/agent.py) on Claude Sonnet 5.5
  2. your loop on gpt-4.1-mini through OpenRouter (same model as column 3)
  3. a Foundry prompt agent on the project's gpt-4.1-mini deployment
All three get the same two tools (real names, identical descriptions and schemas, taken from
src/agent.py) and the same system prompt, and the tools run here, on this machine, in every
column. Prints tool calls, answers and per-round input/output tokens side by side, and saves
everything to experiments/foundry/results/.

The Foundry agent version is created for this run and deleted in a finally block. Your loop is
limited to the two tools by swapping src.agent.TOOLS in memory for the run only; src/ is not
edited. Needs ANTHROPIC_API_KEY, OPENROUTER_API_KEY, FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_MODEL
in .env, and `az login`. Paid calls: about $0.03 in total.
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).parent
PROJECT_ROOT = HERE.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(HERE))

from hello_foundry import read_settings

from evals.run import PRICE_PER_MTOK
from src import agent

TOOL_NAMES = ("get_block_distance", "get_fleet_size")
AGENCY = "halifax"
QUESTION = ("How far does Halifax block 722145 drive on 14 October 2026, and how many electric "
            "buses would Halifax need in winter?")
AGENT_NAME = "transit-ai-two-tools"
CLAUDE_MODEL = "claude-sonnet-5-5"
OPENROUTER_MODEL = "openrouter:openai/gpt-4.1-mini"
# US$ per million tokens (input, output): gpt-4.1-mini Global Standard, Azure retail price list.
FOUNDRY_PRICE_PER_MTOK = (0.40, 1.60)
RESULTS = HERE / "results"


def tool_specs(names=TOOL_NAMES):
    """Function-tool definitions for Foundry, copied from src/agent.py's TOOLS: same name,
    description and input schema, strict as in the original."""
    by_name = {t["name"]: t for t in agent.TOOLS}
    return [{"name": n, "description": by_name[n]["description"],
             "parameters": by_name[n]["input_schema"], "strict": True} for n in names]


def run_function_calls(output_items):
    """Run every function_call in a Responses output locally with src.agent.run_tool.

    Returns (function_call_output items to send back, [{"name", "input", "result"}])."""
    outputs, calls = [], []
    for item in output_items:
        if getattr(item, "type", None) != "function_call":
            continue
        tool_input = json.loads(item.arguments or "{}")
        result, _ = agent.run_tool(item.name, tool_input)
        outputs.append({"type": "function_call_output", "call_id": item.call_id, "output": result})
        calls.append({"name": item.name, "input": tool_input, "result": result})
    return outputs, calls


def run_own_agent(model):
    """Your loop (answer_question) with only the two tools, recording each round's tokens."""
    rounds = []
    original_tools, original_complete = agent.TOOLS, agent.complete

    def recording_complete(model_id, system, tools, messages):
        response = original_complete(model_id, system, tools, messages)
        rounds.append((response["usage"]["input_tokens"], response["usage"]["output_tokens"]))
        return response

    agent.TOOLS = [t for t in original_tools if t["name"] in TOOL_NAMES]
    agent.complete = recording_complete
    try:
        out = agent.answer_question(QUESTION, AGENCY, model=model)
    finally:
        agent.TOOLS, agent.complete = original_tools, original_complete
    return {"answer": out["answer"], "tool_calls": out["tool_calls"], "rounds": rounds,
            "cost_usd": out["usage"].get("cost_usd")}


def foundry_loop(client):
    """The same loop against the agent: tools run here; history stays on Foundry and each
    round sends only the new tool outputs plus previous_response_id."""
    rounds, calls = [], []
    response = client.responses.create(input=QUESTION)
    for _ in range(agent.MAX_ROUNDS):
        rounds.append((response.usage.input_tokens, response.usage.output_tokens))
        outputs, new_calls = run_function_calls(response.output)
        calls += new_calls
        if not outputs:
            return {"answer": response.output_text, "tool_calls": calls, "rounds": rounds}
        response = client.responses.create(input=outputs, previous_response_id=response.id)
    raise RuntimeError(f"Foundry agent gave no final answer after {agent.MAX_ROUNDS} rounds")


def run_foundry_agent(settings):
    """Create a prompt agent version, route the agent's endpoint to it, run the loop, and
    restore the endpoint and delete the version whatever happens (as in Microsoft's sample)."""
    from azure.ai.projects import AIProjectClient
    from azure.ai.projects.models import (
        AgentEndpointConfig,
        FixedRatioVersionSelectionRule,
        FunctionTool,
        PromptAgentDefinition,
        ProtocolConfiguration,
        ResponsesProtocolConfiguration,
        VersionSelector,
    )
    from azure.core.exceptions import HttpResponseError
    from azure.identity import DefaultAzureCredential

    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=settings["FOUNDRY_PROJECT_ENDPOINT"], credential=credential) as project,
    ):
        version = original_endpoint = None
        try:
            try:
                version = project.agents.create_version(
                    agent_name=AGENT_NAME,
                    definition=PromptAgentDefinition(
                        model=settings["FOUNDRY_MODEL"],
                        instructions=agent.system_prompt(AGENCY),
                        tools=[FunctionTool(**spec) for spec in tool_specs()],
                    ),
                )
            except HttpResponseError as e:
                # Stop here, before any paid call, and show the service's own words.
                raise SystemExit(f"Agent creation refused (HTTP {e.status_code}):\n{e.message}") from e
            print(f"Created Foundry agent {AGENT_NAME} version {version.version}")
            original_endpoint = project.agents.get(agent_name=AGENT_NAME).agent_endpoint
            project.agents.update_details(agent_name=AGENT_NAME, agent_endpoint=AgentEndpointConfig(
                version_selector=VersionSelector(version_selection_rules=[
                    FixedRatioVersionSelectionRule(agent_version=version.version, traffic_percentage=100)]),
                protocol_configuration=ProtocolConfiguration(responses=ResponsesProtocolConfiguration()),
            ))
            with project.get_openai_client(agent_name=AGENT_NAME) as client:
                return foundry_loop(client)
        finally:
            if original_endpoint is not None:
                project.agents.update_details(agent_name=AGENT_NAME, agent_endpoint=original_endpoint)
            if version is not None:
                project.agents.delete_version(agent_name=AGENT_NAME, agent_version=version.version, force=True)
                print(f"Deleted Foundry agent {AGENT_NAME} version {version.version}")


def cost(column, rounds):
    if column.get("cost_usd") is not None:
        return column["cost_usd"]
    price_in, price_out = column["price"]
    return (sum(i for i, _ in rounds) * price_in + sum(o for _, o in rounds) * price_out) / 1e6


def side_by_side(columns):
    """Rows of text, one column per run."""
    width = 46
    rows = [("", [c["label"] for c in columns])]
    most = max(len(c["rounds"]) for c in columns)
    for n in range(most):
        rows.append((f"round {n + 1} tokens", [
            f"{c['rounds'][n][0]:,} in / {c['rounds'][n][1]:,} out" if n < len(c["rounds"]) else ""
            for c in columns]))
    rows.append(("total tokens", [f"{sum(i for i, _ in c['rounds']):,} in / "
                                  f"{sum(o for _, o in c['rounds']):,} out" for c in columns]))
    rows.append(("cost", [f"${cost(c, c['rounds']):.4f}" for c in columns]))
    most_calls = max(len(c["tool_calls"]) for c in columns)
    for n in range(most_calls):
        rows.append((f"tool call {n + 1}", [
            f"{c['tool_calls'][n]['name']}({', '.join(f'{v}' for v in c['tool_calls'][n]['input'].values())})"
            if n < len(c["tool_calls"]) else "" for c in columns]))
    rows.append(("says 80.5 km", ["yes" if "80.5" in c["answer"] else "NO" for c in columns]))
    rows.append(("says 414 buses", ["yes" if "414" in c["answer"] else "NO" for c in columns]))
    lines = []
    for label, cells in rows:
        lines.append(f"{label:16} " + " ".join(f"{cell[:width]:{width}}" for cell in cells))
    return lines


def main():
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
    import os

    settings = read_settings(os.environ)
    print(f"Q ({AGENCY}): {QUESTION}\n")
    # Foundry first: if agent creation is refused, nothing else is paid for.
    columns = [{"label": f"Foundry agent · {settings['FOUNDRY_MODEL']}", "price": FOUNDRY_PRICE_PER_MTOK,
                **run_foundry_agent(settings)}]
    columns.insert(0, {"label": "Your loop · gpt-4.1-mini (OpenRouter)", **run_own_agent(OPENROUTER_MODEL)})
    columns.insert(0, {"label": "Your loop · Sonnet 5.5", "price": PRICE_PER_MTOK[CLAUDE_MODEL],
                       **run_own_agent(CLAUDE_MODEL)})

    print("\n".join(side_by_side(columns)))
    for c in columns:
        print(f"\n--- {c['label']} answer:\n{c['answer']}")

    RESULTS.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = RESULTS / f"{stamp}-compare-agents.json"
    out.write_text(json.dumps({"question": QUESTION, "agency": AGENCY, "tools": list(TOOL_NAMES),
                               "columns": columns}, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"\nSaved {out.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
