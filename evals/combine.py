"""Combine several eval result files (e.g. one per model) into one markdown report.

Usage:
    python evals/combine.py OUT.md RESULT1.json RESULT2.json ...

Per model: pass@k and pass^k for dev and held-out separately (for a re-graded run, under the
original grader and the current one side by side), failed attempts by check type, average cost
and latency per attempt (one answered question), and cost per passed attempt.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

CHECKS = ("steps", "end_state", "unsupported")


SPLITS = ("dev (Halifax)", "held-out (Dublin, London)")
SPLIT_OF = {"halifax": SPLITS[0], "dublin": SPLITS[1], "london": SPLITS[1]}


def grades(records):
    """{grader label: [pass per record]}: every grader version a re-graded run keeps (see
    evals/regrade.py), or the original and current grade, or just the current one."""
    if all("grades" in r for r in records):
        return {label: [r["grades"][label] for r in records] for label in records[0]["grades"]}
    out = {}
    if all("checks_before" in r for r in records):
        out["v1"] = [r["checks_before"]["pass"] for r in records]
    out["v1.1" if out else "current"] = [r["pass"] for r in records]
    return out


def split_scores(records, passes, split):
    """(attempts passed, attempts, pass@k tasks, pass^k tasks, tasks) for one split."""
    by_task = defaultdict(list)
    for r, p in zip(records, passes, strict=True):
        if SPLIT_OF[r["agency"]] == split:
            by_task[r["task_id"]].append(p)
    attempts = [p for t in by_task.values() for p in t]
    return (sum(attempts), len(attempts), sum(any(t) for t in by_task.values()),
            sum(all(t) for t in by_task.values()), len(by_task))


def overview(paths):
    """One row per model: all 30 tasks, every grader version, cost per attempt and per pass."""
    rows, labels = [], None
    for path in paths:
        run = json.loads(Path(path).read_text(encoding="utf-8"))
        records, k = run["records"], run["stamp"]["k"]
        g = grades(records)
        labels = list(g)
        costs = [r["cost_usd"] or 0 for r in records]
        cells = []
        for passes in g.values():
            n_tasks = len({r["task_id"] for r in records})
            by_task = defaultdict(list)
            for r, p in zip(records, passes, strict=True):
                by_task[r["task_id"]].append(p)
            cells.append(f"{sum(passes)}/{len(passes)} · {sum(all(t) for t in by_task.values())}/{n_tasks}")
        passed = sum(list(g.values())[-1])
        rows.append(f"| {run['stamp']['model']} | " + " | ".join(cells) + f" | {disclosure(records)} | "
                    f"${sum(costs) / len(costs):.4f} | ${sum(costs) / passed:.4f} | ${sum(costs):.2f} |")
    head = ("| Model | " + " | ".join(f"{label}: attempts passed · pass^{k}" for label in labels)
            + f" | Disclosure ({labels[-1]}, separate) | Cost / attempt | "
            f"Cost / passed attempt ({labels[-1]}) | Total cost |")
    return [head, "|---" * (len(labels) + 5) + "|"] + rows


def disclosure(records):
    """"passed/applicable" for the separate disclosure check, or "n/a" for runs graded without it."""
    applicable = [r["checks"]["disclosure"] for r in records
                  if r["checks"].get("disclosure", {}).get("applies")]
    if not any("disclosure" in r["checks"] for r in records):
        return "n/a"
    return f"{sum(c['pass'] for c in applicable)}/{len(applicable)}"


def summarise(path):
    run = json.loads(Path(path).read_text(encoding="utf-8"))
    stamp, records = run["stamp"], run["records"]
    k = stamp["k"]
    g = grades(records)
    lines = [f"## {stamp['model']}", "",
             (f"Run `{Path(path).name}` · commit `{stamp['git_commit']}` · k={k} · "
             f"{stamp['timestamp']}"), "",
             "| Split | Tasks | " + " | ".join(f"{label} attempts | {label} pass@{k} | {label} pass^{k}"
                                              for label in g) + " |",
             "|---|---|" + "---|---|---|" * len(g)]
    for split in SPLITS:
        cells = []
        for passes in g.values():
            ok, n, at_k, all_k, tasks = split_scores(records, passes, split)
            cells.append(f"{ok}/{n} | {at_k}/{tasks} | {all_k}/{tasks}")
        lines.append(f"| {split} | {tasks} | " + " | ".join(cells) + " |")

    failed = {c: sum(not r["checks"][c]["pass"] for r in records) for c in CHECKS}
    costs = [r["cost_usd"] for r in records if r["cost_usd"] is not None]
    seconds = [r["seconds"] for r in records]
    passed = sum(r["pass"] for r in records)
    label = list(g)[-1]
    lines += ["", (f"| Failed attempts ({label}): steps | end state | unsupported numbers | "
              f"Avg cost / attempt | Cost / passed attempt | Avg latency / attempt | Total cost |"),
              "|---|---|---|---|---|---|---|",
              (f"| {failed['steps']} | {failed['end_state']} | {failed['unsupported']} | "
              f"${sum(costs) / len(costs):.4f} | ${sum(costs) / passed:.4f} | "
              f"{sum(seconds) / len(seconds):.1f} s | ${sum(costs):.2f} |"), ""]

    detail = []
    for r in records:
        for c in CHECKS:
            check = r["checks"][c]
            if check["pass"]:
                continue
            if "error" in check:
                why = f"run failed: {check['error'][:120]}"
            elif c == "steps":
                why = "missing " + "; ".join(str(m["name"]) for m in check["missing"])
            elif c == "end_state":
                why = "missing " + "; ".join(m["label"] for m in check["missing"])
            else:
                why = "unsupported: " + ", ".join(check["numbers"])
            detail.append(f"- `{r['task_id']}` #{r['attempt']} {c}: {why}")
    for r in records:
        c = r["checks"].get("disclosure", {})
        if c.get("applies") and not c["pass"]:
            detail.append(f"- `{r['task_id']}` #{r['attempt']} disclosure (separate): doesn't say "
                          + " or ".join({"estimat": "estimated", "infer": "inferred"}[m] for m in c["missing"]))
    lines += [f"<details><summary>Failure details ({label})</summary>", ""] + (detail or ["- none"])
    lines += ["", "</details>", ""]
    return "\n".join(lines)


def main(out, paths):
    body = ["# Model benchmark: all 30 tasks", "",
            ("pass@k: a task passes if any of its k attempts passes. pass^k: only if all k pass. "
            "Cost and latency are per attempt (one answered question). Re-graded runs show the "
            "grade under every grader version (v1, v1.1, v1.2) side by side; the answers are the same. "
            "Disclosure (v1.2, not part of the pass): London answers built on tool output flagged "
            "ESTIMATED / INFERRED must say distances are estimated and blocks inferred; shown as "
            "passed/applicable attempts. "
            "Cost per passed attempt = total cost / attempts passed."), ""]
    body += overview(paths) + [""]
    body += [summarise(p) for p in paths]
    Path(out).write_text("\n".join(body), encoding="utf-8", newline="\n")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
