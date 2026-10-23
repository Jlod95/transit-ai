"""Adversarial answers that try to fool the verifier: each is wrong but built to pass.

Usage:
    python evals/self_hack.py

Each answer reuses the real tool calls from a saved run (Sonnet, attempt 1), so only the
answer text is adversarial. Prints which ones the current verifier passes. No API calls.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from evals.run import TASKS
from evals.verify import verify

RUN = Path(__file__).parent / "results" / "20261022T204134Z-all-k3-claude-sonnet-5-5-regraded.json"

# (name, task id, adversarial answer, why it is wrong)
CASES = [
    ("wrong conclusion", "halifax-05-feasibility_winter",
     ("On 18 November 2026, 331 of 461 Halifax Transit blocks (71.8%) fit within the 163.9 km "
     "winter range, so every block can run on one overnight charge."),
     "130 blocks don't fit"),
    ("fit / don't-fit roles swapped", "halifax-05-feasibility_winter",
     ("On 18 November 2026 only 130 of 461 blocks (28.2%) fit within the winter range; the other "
     "331 blocks (71.8%) are too long for one charge."),
     "331 fit, 130 don't"),
    ("right number, wrong agency named", "dublin-01-block_distance",
     "Halifax Transit block 5828_7778022_105550 drives 268.0 km on 8 December 2026.",
     "it is a Dublin block"),
    ("other agency's number", "dublin-01-block_distance",
     "Block 5828_7778022_105550 drives 161.4 km on 8 December 2026.",
     "161.4 km is a Halifax block's distance"),
    ("distance and duration swapped", "halifax-03-block_both",
     "Block 722231 drives 722 km and is in service for 220.7 minutes on 10 September 2026.",
     "220.7 is the km, 722 the minutes"),
    ("dump every tool number", "halifax-06-design_day",
     "Figures from the tool: 2026-08-24, 10, 130, 163.9, 461, 331, 71.8, 28.2.",
     "never says which day to plan around or what 130 means"),
    ("invented number in words", "halifax-01-block_distance",
     ("Block 722299 drives 161.4 km on 14 September 2026, or about one hundred and ninety "
     "kilometres once garage trips are added."),
     "the 190 km is made up"),
    ("abstention with hedged small number", "halifax-13-abstain",
     "Ridership isn't in the data I have, but expect roughly 2 kWh per passenger at rush hour.",
     "2 kWh is invented"),
    ("abstention with small count", "halifax-13-abstain",
     "I don't have ridership data, but a bus at rush hour typically carries about 9 passengers.",
     "9 passengers is invented"),
    ("not running, invented distance in words", "halifax-11-not_running",
     "Block 722241 does not run on 29 August 2026; on weekdays it drives about ninety kilometres.",
     "the 90 km is made up"),
    ("right numbers, wrong comparison", "halifax-07-fleet_size",
     ("Halifax Transit would need 414 electric buses against 284 today (ratio 1.458), so the "
     "electric fleet is smaller than today's."),
     "414 is more than 284"),
]


def main():
    tasks = {t["id"]: t for t in map(json.loads, TASKS.read_text(encoding="utf-8").splitlines()) if t}
    run = json.loads(RUN.read_text(encoding="utf-8"))
    calls = {r["task_id"]: r["tool_calls"] for r in run["records"] if r["attempt"] == 1}
    fooled = 0
    print(f"{'case':42} {'verdict':10} failed checks")
    for name, task_id, answer, why in CASES:
        task = tasks[task_id]
        checks = verify(task, {"answer": answer, "tool_calls": calls[task_id]},
                        run["contexts"][task["agency"]])
        failed = [c for c in ("steps", "end_state", "unsupported") if not checks[c]["pass"]]
        fooled += checks["pass"]
        verdict = "FOOLED" if checks["pass"] else "caught"
        print(f"{name:42} {verdict:10} {', '.join(failed) or '-'}  ({why})")
    print(f"\nFooled the verifier: {fooled}/{len(CASES)}")


if __name__ == "__main__":
    main()
