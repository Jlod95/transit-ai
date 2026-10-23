"""Rubric judge: Claude Sonnet grades an answer Y/N on five criteria the code checks can't.

Usage:
    python evals/judge.py select   # pick 20 answers -> evals/judge/answers.md, my_labels.csv
    python evals/judge.py bias     # position-bias test: 10 pairwise comparisons, both orders
    python evals/judge.py run      # judge the 20 answers -> evals/judge/judge_labels.json
    python evals/judge.py agree    # agreement and Cohen's kappa: my_labels.csv vs the judge

select and agree make no API calls; bias and run are paid calls to JUDGE_MODEL. The judge sees
the question, the agency, every tool call with its output, and the answer; never the grader's
result or which model wrote it. No refusal fallback: every verdict comes from the same model.
"""

import csv
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import anthropic
from dotenv import load_dotenv

from evals.run import TASKS

JUDGE_MODEL = "claude-sonnet-5-5"
OUT = Path(__file__).parent / "judge"
RESULTS = Path(__file__).parent / "results"
RUNS = {
    "claude-haiku-5-5": "20261022T203940Z-all-k3-claude-haiku-5-5-regraded.json",
    "claude-sonnet-5-5": "20261022T204134Z-all-k3-claude-sonnet-5-5-regraded.json",
    "claude-opus-5-5": "20261022T204337Z-all-k3-claude-opus-5-5-regraded.json",
    "deepseek-v4.1-flash": "20261022T231239Z-all-k3-openrouter-deepseek-v4.1-flash-regraded.json",
}
CRITERIA = {
    "conclusion": "The conclusion is consistent with the tool numbers (no wrong inference, swapped "
                  "roles or wrong comparison drawn from correct numbers).",
    "answers_question": "It answers the question that was asked (the right agency, block, date "
                        "and quantity), not a different one.",
    "caveats": "The caveats the tool output calls for are present, judged by meaning, not keywords: "
               "estimated distances or inferred blocks, placeholder assumptions, data limits "
               "(e.g. deadhead excluded, dates outside the timetable). N if one is missing.",
    "no_misleading": "No misleading or unsupported claims: every figure and statement is backed by "
                     "the tool output or plainly marked as general knowledge, with no invented numbers.",
    "clear": "Clear enough for a transit planner to forward as it is, without rewriting.",
}
LABEL_COLUMNS = ["id", *CRITERIA, "note"]

# The 20 answers to label: (model, task id, attempt). Every model, both splits, passes and
# failures, including the DeepSeek Dublin "ID format" answer and the two Opus disclosure answers.
PICKS = [
    ("claude-haiku-5-5", "halifax-09-cost_co2", 1),
    ("claude-haiku-5-5", "dublin-06-fleet_size", 1),
    ("claude-haiku-5-5", "halifax-05-feasibility_winter", 1),
    ("claude-haiku-5-5", "london-01-block_distance", 1),
    ("claude-haiku-5-5", "halifax-13-abstain", 1),
    ("claude-sonnet-5-5", "halifax-06-design_day", 1),
    ("claude-sonnet-5-5", "dublin-02-block_duration", 1),
    ("claude-sonnet-5-5", "london-05-cost_co2", 1),
    ("claude-sonnet-5-5", "halifax-10-sources", 1),
    ("claude-sonnet-5-5", "london-07-outside_timetable", 1),
    ("claude-opus-5-5", "london-02-block_both", 3),
    ("claude-opus-5-5", "london-05-cost_co2", 3),
    ("claude-opus-5-5", "dublin-04-feasibility_winter", 3),
    ("claude-opus-5-5", "halifax-12-outside_timetable", 1),
    ("claude-opus-5-5", "dublin-07-charging", 1),
    ("deepseek-v4.1-flash", "dublin-08-not_running", 3),
    ("deepseek-v4.1-flash", "halifax-08-charging", 3),
    ("deepseek-v4.1-flash", "halifax-11-not_running", 1),
    ("deepseek-v4.1-flash", "halifax-07-fleet_size", 1),
    ("deepseek-v4.1-flash", "london-03-feasibility_summer", 1),
]
# Position-bias test: 10 tasks (5 dev, 5 held-out), each a pair of models' first attempts.
BIAS_PAIRS = [
    ("halifax-03-block_both", "claude-sonnet-5-5", "claude-haiku-5-5"),
    ("halifax-05-feasibility_winter", "claude-opus-5-5", "deepseek-v4.1-flash"),
    ("halifax-07-fleet_size", "claude-sonnet-5-5", "claude-opus-5-5"),
    ("halifax-09-cost_co2", "claude-haiku-5-5", "deepseek-v4.1-flash"),
    ("halifax-14-abstain", "claude-sonnet-5-5", "deepseek-v4.1-flash"),
    ("dublin-03-block_both", "claude-sonnet-5-5", "claude-haiku-5-5"),
    ("dublin-05-design_day", "claude-opus-5-5", "deepseek-v4.1-flash"),
    ("london-02-block_both", "claude-sonnet-5-5", "claude-opus-5-5"),
    ("london-04-design_day", "claude-haiku-5-5", "deepseek-v4.1-flash"),
    ("london-06-sources", "claude-sonnet-5-5", "deepseek-v4.1-flash"),
]
MAX_TOOL_RESULT = 4000  # characters of each tool output shown to the judge

SYSTEM = (
    "You review answers from a transit electrification assistant. The assistant answers a "
    "planner's question by calling tools that run tested code on public timetable data; the "
    "tool outputs are the ground truth. Judge only against the question and the tool outputs, "
    "not your own knowledge of the agency. Be strict: a planner may forward the answer as it is."
)


def tasks_by_id():
    return {t["id"]: t for t in map(json.loads, TASKS.read_text(encoding="utf-8").splitlines()) if t}


def record(model, task_id, attempt):
    run = json.loads((RESULTS / RUNS[model]).read_text(encoding="utf-8"))
    return next(r for r in run["records"] if r["task_id"] == task_id and r["attempt"] == attempt)


def key_numbers(result):
    """A short view of one tool output for a human: top-level scalars of a JSON result (or the
    titles of retrieved sources), else the text itself."""
    try:
        data = json.loads(result)
    except json.JSONDecodeError:
        return result[:400]
    if not isinstance(data, dict):
        return result[:400]
    if "results" in data:
        return "; ".join(f"{h.get('title')} ({h.get('publisher')}, {h.get('pages', '')})"
                         for h in data["results"])
    return ", ".join(f"{k}: {v}" for k, v in data.items()
                     if isinstance(v, (int, float, str)) and len(str(v)) <= 80)


def evidence(task, rec):
    """The question, agency and full tool outputs, as the judge sees them."""
    calls = "\n\n".join(
        f"Tool call {i}: {c['name']}({json.dumps(c['input'])})\nOutput:\n{c['result'][:MAX_TOOL_RESULT]}"
        for i, c in enumerate(rec["tool_calls"], 1)) or "(no tool calls)"
    return f"Agency: {task['agency']}\nQuestion: {task['question']}\n\n{calls}"


def ask_json(client, prompt, schema):
    response = client.messages.create(
        model=JUDGE_MODEL, max_tokens=4000, system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": schema}},
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("the judge declined")
    text = next(b.text for b in response.content if b.type == "text")
    usage = (response.usage.input_tokens, response.usage.output_tokens)
    return json.loads(text), usage


RUBRIC_SCHEMA = {
    "type": "object",
    "properties": {name: {"type": "object",
                          "properties": {"verdict": {"type": "string", "enum": ["Y", "N"]},
                                         "reason": {"type": "string"}},
                          "required": ["verdict", "reason"], "additionalProperties": False}
                   for name in CRITERIA},
    "required": list(CRITERIA), "additionalProperties": False,
}
PAIR_SCHEMA = {
    "type": "object",
    "properties": {"better": {"type": "string", "enum": ["A", "B"]}, "reason": {"type": "string"}},
    "required": ["better", "reason"], "additionalProperties": False,
}


def rubric_prompt(task, rec):
    criteria = "\n".join(f"({i}) {name}: {text}" for i, (name, text) in enumerate(CRITERIA.items(), 1))
    return (f"{evidence(task, rec)}\n\nAnswer to review:\n<answer>\n{rec['answer']}\n</answer>\n\n"
            f"For each criterion, give Y or N and a one-line reason.\n{criteria}")


def pair_prompt(task, rec_a, rec_b):
    return (f"{evidence(task, rec_a)}\n\nTwo answers to the same question, from the same tool "
            f"outputs:\n<answer_A>\n{rec_a['answer']}\n</answer_A>\n<answer_B>\n{rec_b['answer']}\n"
            "</answer_B>\n\nWhich answer is better for a transit planner: more correct, answers "
            "the question, right caveats, nothing misleading, clear? Pick A or B, with a one-line reason.")


def cost(usages):
    return sum(i * 2.00 + o * 10.00 for i, o in usages) / 1e6  # Sonnet 5.5 list price, US$


def select():
    tasks = tasks_by_id()
    order = list(range(len(PICKS)))
    random.Random(2026).shuffle(order)  # mix models so their answers don't come in runs
    lines = ["# Answers to label", "",
             ("Twenty agent answers, numbered 1-20. For each, fill in a row of `my_labels.csv` with "
             "Y or N per criterion (and a note if useful). The criteria:"), ""]
    lines += [f"- **{name}**: {text}" for name, text in CRITERIA.items()]
    mapping = []
    for number, index in enumerate(order, 1):
        model, task_id, attempt = PICKS[index]
        task, rec = tasks[task_id], record(model, task_id, attempt)
        mapping.append({"id": number, "model": model, "task_id": task_id, "attempt": attempt})
        lines += ["", "---", "", f"## {number}", "", f"**Agency:** {task['agency']}", "",
                  f"**Question:** {task['question']}", "", "**Key tool numbers:**", ""]
        lines += [f"- `{c['name']}({json.dumps(c['input'])})`: {key_numbers(c['result'])}"
                  for c in rec["tool_calls"]] or ["- (no tool calls)"]
        lines += ["", "**Answer:**", "", rec["answer"]]
    OUT.mkdir(exist_ok=True)
    (OUT / "answers.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    (OUT / "answers.json").write_text(json.dumps(mapping, indent=1) + "\n", encoding="utf-8", newline="\n")
    labels = OUT / "my_labels.csv"
    if labels.exists():
        print(f"Kept existing {labels.name} (not overwritten)")
    else:
        with labels.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, lineterminator="\n")
            writer.writerow(LABEL_COLUMNS)
            writer.writerows([[number] + [""] * (len(LABEL_COLUMNS) - 1) for number in range(1, 21)])
    print(f"Wrote {OUT.name}/answers.md, answers.json and my_labels.csv")


def bias():
    load_dotenv(ROOT / ".env")
    client, tasks = anthropic.Anthropic(), tasks_by_id()
    rows, usages = [], []
    for task_id, first, second in BIAS_PAIRS:
        task = tasks[task_id]
        recs = {m: record(m, task_id, 1) for m in (first, second)}
        picks = []
        for a, b in ((first, second), (second, first)):
            verdict, usage = ask_json(client, pair_prompt(task, recs[a], recs[b]), PAIR_SCHEMA)
            usages.append(usage)
            picks.append({"order": [a, b], "better": verdict["better"],
                          "winner": a if verdict["better"] == "A" else b, "reason": verdict["reason"]})
        flipped = picks[0]["winner"] != picks[1]["winner"]
        rows.append({"task_id": task_id, "pair": [first, second], "flipped": flipped, "verdicts": picks})
        print(f"  {task_id:32} {first} vs {second}: "
              f"{picks[0]['winner']} / {picks[1]['winner']}{'  FLIP' if flipped else ''}", flush=True)
    flips = sum(r["flipped"] for r in rows)
    first_wins = sum(p["better"] == "A" for r in rows for p in r["verdicts"])
    summary = {"model": JUDGE_MODEL, "pairs": len(rows), "flips": flips,
               "first_position_wins": first_wins, "comparisons": 2 * len(rows),
               "cost_usd": round(cost(usages), 4)}
    OUT.mkdir(exist_ok=True)
    (OUT / "position_bias.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=1) + "\n",
                                            encoding="utf-8", newline="\n")
    print(f"Verdict flipped with order in {flips}/{len(rows)} pairs; answer A (shown first) won "
          f"{first_wins}/{2 * len(rows)}; cost ${summary['cost_usd']:.2f}; wrote {OUT.name}/position_bias.json")


def run():
    load_dotenv(ROOT / ".env")
    client, tasks = anthropic.Anthropic(), tasks_by_id()
    mapping = json.loads((OUT / "answers.json").read_text(encoding="utf-8"))
    labels, usages = [], []
    for item in mapping:
        task = tasks[item["task_id"]]
        verdict, usage = ask_json(client, rubric_prompt(task, record(item["model"], item["task_id"],
                                                                     item["attempt"])), RUBRIC_SCHEMA)
        usages.append(usage)
        labels.append({"id": item["id"], **verdict})
        print(f"  {item['id']:2} " + " ".join(f"{name}={verdict[name]['verdict']}" for name in CRITERIA),
              flush=True)
    (OUT / "judge_labels.json").write_text(
        json.dumps({"model": JUDGE_MODEL, "cost_usd": round(cost(usages), 4), "labels": labels}, indent=1)
        + "\n", encoding="utf-8", newline="\n")
    print(f"Judged {len(labels)} answers for ${cost(usages):.2f}; wrote {OUT.name}/judge_labels.json")


def cohen_kappa(a, b):
    """Agreement between two Y/N raters beyond chance: (observed - expected) / (1 - expected)."""
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b, strict=True)) / n
    expected = sum((a.count(v) / n) * (b.count(v) / n) for v in ("Y", "N"))
    return 1.0 if expected == 1 else (observed - expected) / (1 - expected)


def agree():
    with (OUT / "my_labels.csv").open(encoding="utf-8", newline="") as f:
        mine = {int(row["id"]): row for row in csv.DictReader(f)}
    judge = {item["id"]: item for item in
             json.loads((OUT / "judge_labels.json").read_text(encoding="utf-8"))["labels"]}
    missing = [i for i, row in mine.items() if any(row[c].strip().upper() not in ("Y", "N") for c in CRITERIA)]
    if missing:
        raise SystemExit(f"my_labels.csv: rows {missing} need Y or N in every criterion column")
    lines = ["| Criterion | Agreement | Cohen's kappa | Disagreements (id: mine/judge) |", "|---|---|---|---|"]
    for name in CRITERIA:
        ids = sorted(mine)
        a = [mine[i][name].strip().upper() for i in ids]
        b = [judge[i][name]["verdict"] for i in ids]
        diffs = ", ".join(f"{i}: {x}/{y}" for i, x, y in zip(ids, a, b, strict=True) if x != y) or "-"
        agreement = sum(x == y for x, y in zip(a, b, strict=True))
        lines.append(f"| {name} | {agreement}/{len(ids)} | {cohen_kappa(a, b):.2f} | {diffs} |")
    report = "\n".join(lines) + "\n"
    (OUT / "agreement.md").write_text("# Judge vs my labels\n\n" + report, encoding="utf-8", newline="\n")
    print(report)


if __name__ == "__main__":
    commands = {"select": select, "bias": bias, "run": run, "agree": agree}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        raise SystemExit(__doc__)
    commands[sys.argv[1]]()
