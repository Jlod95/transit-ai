"""Run the agent on eval tasks and grade every attempt.

Usage:
    python evals/run.py --split dev --k 1
    python evals/run.py --split heldout --k 5
    python evals/run.py --ids halifax-01-block_distance,halifax-06-design_day

Calls answer_question directly (not over HTTP, so the /ask rate limits don't apply); every
attempt is a real, paid API call. Writes evals/results/<time>-<split>-k<k>.json (every answer,
tool call and check) and a .md report next to it, stamped with the data and code used.
"""

import argparse
import hashlib
import json
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import anthropic

from config.assumptions import ASSUMPTION_SOURCES
from config.sources import FACT_CARDS
from evals.verify import verify
from src.agent import MODEL, TOOLS, AgentError, answer_question, system_prompt
from src.provenance import current_git_commit

TASKS = Path(__file__).parent / "tasks.jsonl"
RESULTS = Path(__file__).parent / "results"
# US$ per million tokens for MODEL at the time of writing (input, output); thinking counts as output.
PRICE_PER_MTOK = {"claude-opus-5-5": (4.00, 20.00)}
CHECKS = ("steps", "end_state", "unsupported")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_tasks(split, ids):
    tasks = [json.loads(line) for line in TASKS.read_text(encoding="utf-8").splitlines() if line]
    if ids:
        wanted = set(ids)
        return [t for t in tasks if t["id"] in wanted]
    return [t for t in tasks if split == "all" or t["split"] == split]


def agent_context(agency):
    """What the agent is told besides tool results: its system prompt, every tool description,
    and the source entries. Numbers stated here count as supported when grading."""
    parts = [system_prompt(agency)] + [t["description"] for t in TOOLS]
    parts.append(json.dumps(ASSUMPTION_SOURCES))
    parts += [text for _, _, text in FACT_CARDS]
    return "\n".join(parts)


def cost(usage):
    price_in, price_out = PRICE_PER_MTOK[MODEL]
    return (usage["input_tokens"] * price_in + usage["output_tokens"] * price_out) / 1e6


def run(tasks, k, contexts):
    records = []
    for task in tasks:
        for attempt in range(1, k + 1):
            started = time.perf_counter()
            try:
                out = answer_question(task["question"], task["agency"])
                result = {"answer": out["answer"], "tool_calls": out["tool_calls"]}
                usage = out["usage"]
            except (AgentError, anthropic.APIError, ValueError) as e:  # a failed attempt, not a crash
                result = {"error": f"{type(e).__name__}: {e}"}
                usage = {"input_tokens": 0, "output_tokens": 0}
            checks = verify(task, result, contexts[task["agency"]])
            records.append({
                "task_id": task["id"], "agency": task["agency"], "category": task["category"],
                "attempt": attempt, "pass": checks["pass"], "checks": checks,
                "seconds": round(time.perf_counter() - started, 1),
                "usage": usage, "cost_usd": round(cost(usage), 4), **result,
            })
            status = "PASS" if checks["pass"] else "fail " + ",".join(
                c for c in CHECKS if not checks[c]["pass"])
            print(f"  {task['id']:32} #{attempt} {status:28} ${cost(usage):.3f} {records[-1]['seconds']}s")
    return records


def stamp(split, k, ids):
    return {
        "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "split": "ids" if ids else split,
        "k": k,
        "model": MODEL,
        "git_commit": current_git_commit(),
        "tasks_sha256": sha256(TASKS),
        "summaries_sha256": {p.name: sha256(p) for p in sorted((ROOT / "data" / "summaries").glob("*.json"))},
        "sources_index_sha256": sha256(ROOT / "data" / "index" / "sources.json"),
    }


def report(stamp_, records):
    lines = [f"# Eval run: {stamp_['split']}, k={stamp_['k']}", ""]
    lines += [f"- {key}: `{value}`" for key, value in stamp_.items() if key != "summaries_sha256"]
    lines += [f"- summary {name}: `{h[:12]}`" for name, h in stamp_["summaries_sha256"].items()]
    passed = sum(r["pass"] for r in records)
    total_cost = sum(r["cost_usd"] for r in records)
    minutes = sum(r["seconds"] for r in records) / 60
    headline = (f"**Pass rate: {passed}/{len(records)} attempts ({100 * passed / len(records):.0f}%)**"
                f" · cost ${total_cost:.2f} · {minutes:.1f} min")
    lines += ["", headline, ""]

    lines += ["## By check", "", "| Check | Passed |", "|---|---|"]
    for check in CHECKS:
        n = sum(r["checks"][check]["pass"] for r in records)
        lines.append(f"| {check} | {n}/{len(records)} |")

    # Per task: pass@k = at least one of its k attempts passed; pass^k = all k passed.
    by_task = defaultdict(list)
    for r in records:
        by_task[(r["category"], r["task_id"])].append(r["pass"])
    by_category = defaultdict(list)
    for (category, _), results in by_task.items():
        by_category[category].append(results)
    k = stamp_["k"]
    lines += ["", "## By category", "",
              f"| Category | Attempts passed | pass@{k} (tasks) | pass^{k} (tasks) |", "|---|---|---|---|"]
    for category, tasks in sorted(by_category.items()):
        attempts = [p for results in tasks for p in results]
        lines.append(f"| {category} | {sum(attempts)}/{len(attempts)} | "
                     f"{sum(any(t) for t in tasks)}/{len(tasks)} | {sum(all(t) for t in tasks)}/{len(tasks)} |")
    all_tasks = [t for tasks in by_category.values() for t in tasks]
    lines.append(f"| **all** | {sum(r['pass'] for r in records)}/{len(records)} | "
                 f"{sum(any(t) for t in all_tasks)}/{len(all_tasks)} | "
                 f"{sum(all(t) for t in all_tasks)}/{len(all_tasks)} |")

    derived = [(r, d) for r in records for d in r["checks"]["unsupported"].get("derived", [])]
    lines += ["", f"## Derived numbers (warnings, not failures): {len(derived)}", ""]
    lines += [f"- `{r['task_id']}` #{r['attempt']}: {d['number']} ({d['rule']}, from {d['from']:g})"
              for r, d in derived]

    lines += ["", "## Failures by check type", ""]
    for check in CHECKS:
        failed = [r for r in records if not r["checks"][check]["pass"]]
        lines += [f"### {check} ({len(failed)})", ""]
        for r in failed:
            c = r["checks"][check]
            if "error" in c:
                detail = f"run failed: {c['error']}"
            elif check == "steps":
                detail = "missing " + "; ".join(f"{m['name']} {m['args']}" for m in c["missing"])
            elif check == "end_state":
                detail = "missing " + "; ".join(
                    f"{m['label']} ({m.get('accept') or m.get('renderings', [''])[0] if m['type'] != 'phrase_any' else 'phrase'})"
                    for m in c["missing"])
            else:
                detail = "unsupported numbers: " + ", ".join(c["numbers"])
            lines.append(f"- `{r['task_id']}` #{r['attempt']}: {detail}")
        lines.append("")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--split", choices=["dev", "heldout", "all"], default="dev")
    parser.add_argument("--k", type=int, default=1, help="attempts per task")
    parser.add_argument("--ids", default="", help="comma-separated task ids (overrides --split)")
    args = parser.parse_args()
    ids = [i for i in args.ids.split(",") if i]

    tasks = load_tasks(args.split, ids)
    print(f"Running {len(tasks)} tasks x k={args.k} on {MODEL}")
    stamp_ = stamp(args.split, args.k, ids)
    contexts = {agency: agent_context(agency) for agency in sorted({t["agency"] for t in tasks})}
    records = run(tasks, args.k, contexts)

    RESULTS.mkdir(exist_ok=True)
    name = f"{stamp_['timestamp'].replace(':', '').replace('-', '')}-{stamp_['split']}-k{args.k}"
    (RESULTS / f"{name}.json").write_text(
        json.dumps({"stamp": stamp_, "contexts": contexts, "records": records}, indent=1) + "\n",
        encoding="utf-8", newline="\n")
    (RESULTS / f"{name}.md").write_text(report(stamp_, records), encoding="utf-8", newline="\n")
    passed = sum(r["pass"] for r in records)
    print(f"Pass {passed}/{len(records)}; cost ${sum(r['cost_usd'] for r in records):.2f}; "
          f"wrote evals/results/{name}.json and .md")


if __name__ == "__main__":
    main()
