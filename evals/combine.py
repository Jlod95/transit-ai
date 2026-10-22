"""Combine several eval result files (e.g. one per model) into one markdown report.

Usage:
    python evals/combine.py OUT.md RESULT1.json RESULT2.json ...

Per model: pass@k and pass^k for dev and held-out separately, failed attempts by check type,
average cost and latency per attempt (one answered question).
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

CHECKS = ("steps", "end_state", "unsupported")


def summarise(path):
    run = json.loads(Path(path).read_text(encoding="utf-8"))
    stamp, records = run["stamp"], run["records"]
    split_of = {"halifax": "dev (Halifax)", "dublin": "held-out (Dublin, London)",
                "london": "held-out (Dublin, London)"}
    by_task = defaultdict(list)
    for r in records:
        by_task[(split_of[r["agency"]], r["task_id"])].append(r["pass"])
    lines = [f"## {stamp['model']}", "",
             (f"Run `{Path(path).name}` · commit `{stamp['git_commit']}` · k={stamp['k']} · "
             f"{stamp['timestamp']}"), "",
             f"| Split | Tasks | Attempts passed | pass@{stamp['k']} | pass^{stamp['k']} |",
             "|---|---|---|---|---|"]
    for split in ("dev (Halifax)", "held-out (Dublin, London)"):
        tasks = [v for (s, _), v in by_task.items() if s == split]
        attempts = [p for t in tasks for p in t]
        lines.append(f"| {split} | {len(tasks)} | {sum(attempts)}/{len(attempts)} | "
                     f"{sum(any(t) for t in tasks)}/{len(tasks)} | {sum(all(t) for t in tasks)}/{len(tasks)} |")

    failed = {c: sum(not r["checks"][c]["pass"] for r in records) for c in CHECKS}
    costs = [r["cost_usd"] for r in records if r["cost_usd"] is not None]
    seconds = [r["seconds"] for r in records]
    lines += ["", ("| Failed attempts: steps | end state | unsupported numbers | Avg cost / attempt | "
              "Avg latency / attempt | Total cost |"), "|---|---|---|---|---|---|",
              (f"| {failed['steps']} | {failed['end_state']} | {failed['unsupported']} | "
              f"${sum(costs) / len(costs):.4f} | {sum(seconds) / len(seconds):.1f} s | ${sum(costs):.2f} |"), ""]

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
    lines += ["<details><summary>Failure details</summary>", ""] + (detail or ["- none"])
    lines += ["", "</details>", ""]
    return "\n".join(lines)


def main(out, paths):
    body = ["# Model benchmark: eval-v1 harness, all 30 tasks", "",
            ("pass@k: a task passes if any of its k attempts passes. pass^k: only if all k pass. "
            "Cost and latency are per attempt (one answered question)."), ""]
    body += [summarise(p) for p in paths]
    Path(out).write_text("\n".join(body), encoding="utf-8", newline="\n")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
