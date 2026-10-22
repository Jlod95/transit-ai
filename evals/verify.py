"""Grade one agent run against one task, like an RL reward function, check by check.

Three checks, each reported separately:
- steps: every expected tool was called, with the expected key arguments.
- end_state: every oracle number appears in the final answer (within rounding), and any
  required statement is present (a citation, "doesn't run", "can't answer"...).
- unsupported: numbers in the answer that don't match any tool output. Dates, years, block
  IDs, URLs, list markers, small counts (0-10) and numbers from the question are ignored.
A task passes only if every check passes.
"""

import json
import re

# A number, optionally with thousands separators and a scale word after it.
_NUMBER = re.compile(
    r"(?<![\w.])([-−]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|[-−]?\d+(?:\.\d+)?)"
    r"(?:\s?(million|billion|thousand|bn\b|M\b|B\b|k\b))?"
)
_SCALE = {"thousand": 1e3, "k": 1e3, "million": 1e6, "m": 1e6, "billion": 1e9, "bn": 1e9, "b": 1e9}
_MONTHS = ("january|february|march|april|may|june|july|august|september|october|november|"
           "december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec")
_DATES = [
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{_MONTHS})\.?,?\s+\d{{4}}\b", re.IGNORECASE),
    re.compile(rf"\b(?:{_MONTHS})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}\b", re.IGNORECASE),
    re.compile(rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{_MONTHS})\b", re.IGNORECASE),
    re.compile(rf"\b(?:{_MONTHS})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?\b", re.IGNORECASE),
]
_URL = re.compile(r"https?://\S+")
_LIST_MARKER = re.compile(r"^\s*\d+[.)]\s", re.MULTILINE)
SMALL_COUNT = 10  # bare integers up to this are treated as prose ("5 longest", "2 tools")


def parse_numbers(text):
    """[(value, half_unit)] for every number in text. half_unit is the rounding tolerance the
    number's own precision implies: "80.5" -> 0.05, "654 million" -> 500,000."""
    found = []
    for m in _NUMBER.finditer(text):
        digits, scale = m.group(1), (m.group(2) or "").lower()
        value = float(digits.replace(",", "").replace("−", "-"))
        decimals = len(digits.split(".")[1]) if "." in digits else 0
        factor = _SCALE.get(scale, 1)
        found.append((value * factor, 0.5 * 10 ** -decimals * factor, m.start(), m.group(0)))
    return found


def _strip_ignored(text, ignore_tokens=()):
    """Remove URLs, dates and list markers, and any given tokens (block IDs), from text."""
    text = _URL.sub(" ", text)
    for pattern in _DATES:
        text = pattern.sub(" ", text)
    text = _LIST_MARKER.sub(" ", text)
    for token in sorted(ignore_tokens, key=len, reverse=True):
        if token:
            text = text.replace(token, " ")
    return text


def matches(answer_value, half_unit, target, extra_tol=1e-9):
    """True if the answer's number is the target rounded to the answer's own precision."""
    return abs(answer_value - target) <= half_unit + abs(target) * 1e-9 + extra_tol


def _conversions(value):
    """The target and the unit changes an answer may reasonably make."""
    return {value, value / 1000, value * 1000, value * 100, value / 100, value / 60, value * 60}


def tool_numbers(tool_calls):
    """Every number in every tool call's input and result."""
    numbers = set()
    for call in tool_calls:
        for text in (json.dumps(call.get("input", {})), str(call.get("result", ""))):
            for value, _, _, _ in parse_numbers(_URL.sub(" ", text)):
                numbers.add(value)
    return numbers


def check_steps(task, tool_calls):
    """Every expected call made, with matching key arguments (strings compared case-insensitively)."""
    missing = []
    for expected in task.get("expected_calls", []):
        names = expected.get("name_any") or [expected["name"]]
        args = expected.get("args", {})
        ok = any(
            call["name"] in names
            and all(str(call.get("input", {}).get(k, "")).lower() == str(v).lower() for k, v in args.items())
            for call in tool_calls
        )
        if not ok:
            missing.append({"name": names if len(names) > 1 else names[0], "args": args})
    return {"pass": not missing, "missing": missing}


def check_end_state(task, answer):
    """Oracle numbers present (any accepted rendering) and required statements present."""
    missing = []
    numbers = parse_numbers(_strip_ignored(answer, task.get("ignore_tokens", [])))
    for item in task.get("oracle", []):
        if item["type"] == "number":
            ok = any(
                all(any(matches(v, h, target) for v, h, _, _ in numbers) for target in option)
                for option in item["accept"]
            )
        elif item["type"] == "phrase_any":
            lowered = answer.lower()
            ok = any(p.lower() in lowered for p in item["phrases"])
        elif item["type"] == "date_any":
            ok = any(d.lower() in answer.lower() for d in item["renderings"])
        else:
            raise ValueError(f"unknown oracle type {item['type']}")
        if not ok:
            missing.append(item)
    return {"pass": not missing, "missing": missing}


def check_unsupported(task, answer, tool_calls):
    """Numbers in the answer that no tool output (or the question) supports."""
    supported = set(tool_numbers(tool_calls))
    supported |= {v for v, _, _, _ in parse_numbers(_strip_ignored(task["question"]))}
    unsupported = []
    for value, half_unit, _, raw in parse_numbers(_strip_ignored(answer, task.get("ignore_tokens", []))):
        if value.is_integer() and 0 <= value <= SMALL_COUNT and half_unit <= 0.5:
            continue
        if 1900 <= value <= 2100 and value.is_integer():
            continue  # a year
        if any(matches(value, half_unit, c) for t in supported for c in _conversions(t)):
            continue
        unsupported.append(raw.strip())
    return {"pass": not unsupported, "numbers": unsupported}


def verify(task, result):
    """All checks for one run. result: {"answer", "tool_calls"} (or {"error"} if the run failed)."""
    if result.get("error"):
        failed = {"pass": False, "error": result["error"]}
        return {"steps": failed, "end_state": failed, "unsupported": failed, "pass": False}
    checks = {
        "steps": check_steps(task, result["tool_calls"]),
        "end_state": check_end_state(task, result["answer"]),
        "unsupported": check_unsupported(task, result["answer"], result["tool_calls"]),
    }
    checks["pass"] = all(c["pass"] for c in checks.values())
    return checks

