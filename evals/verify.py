"""Grade one agent run against one task, like an RL reward function, check by check.

Three checks, each reported separately:
- steps: every expected tool was called, with the expected key arguments.
- end_state: every oracle number appears in the final answer (within rounding), and any
  required statement is present (a citation, "doesn't run", "can't answer"...).
- unsupported: every number in the answer gets one of three levels:
    supported   - matches a tool output, the question, or the agent's context (tool
                  descriptions, system prompt, source entries), at the answer's own precision;
    derived     - a warning, not a failure: one general rule turns a supported number into it
                  (rounding to fewer significant figures; percent <-> fraction or complement to
                  100%, only for percentages; a unit conversion within the number's own unit
                  family, e.g. kWh <-> MWh, minutes <-> hours);
    unsupported - anything else: a failure.
  Dates, years, block IDs, URLs, list markers, small counts (0-10) are ignored.
A task passes only if every check passes.
"""

import json
import re

# A number, optionally with thousands separators and a scale word after it. It may follow
# a multiplication sign ("x1.425") but not other letters, so "CO2" isn't read as 2.
_NUMBER = re.compile(
    r"(?:(?<=[x×])|(?<![\w.]))([-−]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|[-−]?\d+(?:\.\d+)?)"
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


# Units an answer's number may carry, by family, and the conversion factors within each family.
# A conversion is only considered when the answer's number has a unit of that family, so a
# number can't be "explained" by an unrelated factor (e.g. 42.5 = 153 / 3.6 for a percentage).
_UNIT = re.compile(
    r"\s*-?\s*(%|per ?cent|kwh|mwh|gwh|mj|kw|mw|gw|km|miles?|mi|minutes?|mins?|min|"
    r"hours?|hrs?|h)(?![a-z])", re.IGNORECASE)
UNIT_FAMILIES = {
    "percent": ({"%", "percent", "per cent"}, ()),
    "energy": ({"kwh", "mwh", "gwh", "mj"}, (1000, 1e6, 3.6, 3600)),
    "power": ({"kw", "mw", "gw"}, (1000, 1e6)),
    "distance": ({"km", "mile", "miles", "mi"}, (1.609344, 1000)),
    "time": ({"min", "mins", "minute", "minutes", "h", "hr", "hrs", "hour", "hours"}, (60,)),
}
_PERCENT_KEY = re.compile(r'"[^"]*(?:pct|percent)[^"]*"\s*:\s*$', re.IGNORECASE)


def _unit_family(text, end):
    m = _UNIT.match(text, end)
    if not m:
        return None
    word = m.group(1).lower()
    return next((family for family, (words, _) in UNIT_FAMILIES.items() if word in words), None)


def parse_with_units(text):
    """[(value, half_unit, raw, unit_family)]; a JSON value under a "pct"/"percent" key counts
    as a percentage."""
    found = []
    for value, half_unit, start, raw in parse_numbers(text):
        family = _unit_family(text, start + len(raw))
        if family is None and _PERCENT_KEY.search(text[:start]):
            family = "percent"
        if family is None and start > 0 and text[start - 1] in "x×":
            family = "multiplier"  # written as "x1.425"
        found.append((value, half_unit, raw, family))
    return found


def _derivations(value, kind, answer_family):
    """(rule, number) pairs one general rule produces from a supported number, given what kind
    of number the answer is (a percentage, an amount in some unit, or a bare number)."""
    if answer_family == "percent":
        if kind == "percent":
            yield "complement to 100%", 100 - value  # 71.8% fit -> 28.2% don't
        if 0 < value < 1:
            yield "percent <-> fraction", value * 100  # 0.7125 -> 71.25%
            yield "complement to 100%", (1 - value) * 100
        if kind == "multiplier":
            yield "percent <-> fraction", abs(value - 1) * 100  # x1.425 -> 42.5% more
    elif kind == "percent":
        yield "percent <-> fraction", value / 100
        yield "percent <-> fraction", (100 - value) / 100
    if answer_family in UNIT_FAMILIES:
        for factor in UNIT_FAMILIES[answer_family][1]:
            yield "unit conversion", value * factor
            yield "unit conversion", value / factor


def _rounding_half_unit(raw, half_unit):
    """If the answer's number ends in zeros ("19,400"), the wider tolerance of rounding to fewer
    significant figures (here 50); None if it has none or would keep under 2 significant figures."""
    digits = re.match(r"[-−]?[\d,.]+", raw.strip()).group(0).replace(",", "").lstrip("-−")
    if "." in digits:
        return None
    significant = digits.rstrip("0")
    zeros = len(digits) - len(significant)
    if zeros == 0 or len(significant) < 2:
        return None
    return half_unit * 10 ** zeros


def tool_numbers(tool_calls):
    """(every number in every tool call's input and result, {number: "percent"/"multiplier"})."""
    numbers, kinds = set(), {}
    for call in tool_calls:
        for text in (json.dumps(call.get("input", {})), str(call.get("result", ""))):
            for value, _, _, family in parse_with_units(_URL.sub(" ", text)):
                numbers.add(value)
                if family in ("percent", "multiplier"):
                    kinds[value] = family
    return numbers, kinds


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


def classify(value, half_unit, raw, family, supported, kinds=None):
    """("supported", None, None), ("derived", rule, source number) or ("unsupported", None, None)."""
    if any(matches(value, half_unit, t) for t in supported):
        return "supported", None, None
    rounded = _rounding_half_unit(raw, half_unit)
    if rounded is not None:
        source = next((t for t in supported if matches(value, rounded, t)), None)
        if source is not None:
            return "derived", "rounding to fewer significant figures", source
    tolerance = rounded or half_unit
    for t in sorted(supported):
        for rule, candidate in _derivations(t, (kinds or {}).get(t), family):
            if matches(value, tolerance, candidate):
                return "derived", rule, t
    return "unsupported", None, None


def check_unsupported(task, answer, tool_calls, context=""):
    """Grade every number in the answer: supported, derived (warning) or unsupported (fail).

    context: the agent's tool descriptions, system prompt and source entries; numbers stated
    there count as supported."""
    supported, kinds = tool_numbers(tool_calls)
    for text in (_strip_ignored(task["question"]), _URL.sub(" ", context)):
        for value, _, _, family in parse_with_units(text):
            supported.add(value)
            if family in ("percent", "multiplier"):
                kinds[value] = family
    unsupported, derived = [], []
    for value, half_unit, raw, family in parse_with_units(
            _strip_ignored(answer, task.get("ignore_tokens", []))):
        if value.is_integer() and 0 <= value <= SMALL_COUNT and half_unit <= 0.5:
            continue
        if 1900 <= value <= 2100 and value.is_integer():
            continue  # a year
        level, rule, source = classify(value, half_unit, raw, family, supported, kinds)
        if level == "derived":
            derived.append({"number": raw.strip(), "rule": rule, "from": source})
        elif level == "unsupported":
            unsupported.append(raw.strip())
    return {"pass": not unsupported, "numbers": unsupported, "derived": derived}


def verify(task, result, context=""):
    """All checks for one run. result: {"answer", "tool_calls"} (or {"error"} if the run failed).
    context: the agent's tool descriptions, system prompt and source entries for this agency."""
    if result.get("error"):
        failed = {"pass": False, "error": result["error"]}
        return {"steps": failed, "end_state": failed, "unsupported": failed, "pass": False}
    checks = {
        "steps": check_steps(task, result["tool_calls"]),
        "end_state": check_end_state(task, result["answer"]),
        "unsupported": check_unsupported(task, result["answer"], result["tool_calls"], context),
    }
    checks["pass"] = all(c["pass"] for c in checks.values())
    return checks

