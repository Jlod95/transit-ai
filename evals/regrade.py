"""Re-grade a saved eval run with the current verifier. No API calls.

Usage:
    python evals/regrade.py evals/results/20261022T165735Z-dev-k1.json

Uses the agent context saved with the run; older runs saved none, so it is rebuilt from the
current code (only valid if the prompt and tools haven't changed since that run's commit).
Writes <name>-regraded.json and .md, and prints each attempt before and after.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from evals.run import CHECKS, TASKS, agent_context, report
from evals.verify import verify


def main(path):
    path = Path(path)
    run = json.loads(path.read_text(encoding="utf-8"))
    tasks = {t["id"]: t for t in map(json.loads, TASKS.read_text(encoding="utf-8").splitlines()) if t}
    contexts = run.get("contexts") or {}
    rebuilt = not contexts
    print(f"{'task':32} {'before':28} after")
    for record in run["records"]:
        task = tasks[record["task_id"]]
        if task["agency"] not in contexts:
            contexts[task["agency"]] = agent_context(task["agency"])
        before = record["checks"]
        result = {"error": record["error"]} if record.get("error") else record
        after = verify(task, result, contexts[task["agency"]])

        def label(checks):
            failed = [c for c in CHECKS if not checks[c]["pass"]]
            return "PASS" if not failed else "fail " + ",".join(failed)

        warn = after["unsupported"].get("derived", [])
        print(f"{record['task_id']:32} {label(before):28} {label(after)}"
              + (f"  (derived: {', '.join(d['number'] for d in warn)})" if warn else "")
              + (f"  (unsupported: {', '.join(after['unsupported']['numbers'])})"
                 if after["unsupported"].get("numbers") else ""))
        record["checks_before"] = before
        record["checks"] = after
        record["pass"] = after["pass"]
    run["contexts"] = contexts
    run["stamp"]["regraded"] = True
    run["stamp"]["context"] = "rebuilt from current code" if rebuilt else "saved with the run"
    out = path.with_name(path.stem + "-regraded")
    out.with_suffix(".json").write_text(json.dumps(run, indent=1) + "\n", encoding="utf-8", newline="\n")
    out.with_suffix(".md").write_text(report(run["stamp"], run["records"]), encoding="utf-8", newline="\n")
    passed = sum(r["pass"] for r in run["records"])
    print(f"After: {passed}/{len(run['records'])} pass; wrote {out.name}.json and .md")


if __name__ == "__main__":
    main(sys.argv[1])
