"""Grade one agent run against one task, like an RL reward function, check by check.

Three checks, each reported separately:
- steps: every expected tool was called, with the expected key arguments.
- end_state: every oracle number and date appears in the final answer (numbers matched by
  number_match(), the same function the unsupported check uses; dates by value, in any usual
  form), and required outcomes are shown structurally, with no accepted-phrase lists:
  "doesn't run" / "date not covered" = the tool said so and the answer gives no km or time;
  a citation = the answer names a document search_sources returned; an abstention = every
  number in the answer is backed by a tool output or the agent's context.
- unsupported: every number in the answer gets one of three levels:
    supported   - matches a tool output, the question, or the agent's context (tool
                  descriptions, system prompt, source entries), at the answer's own precision;
                  digits inside a tool output's field names count too
                  (block_error_p90_pct -> 90, as in "p90 error");
    derived     - a warning, not a failure: one general rule turns a supported number into it
                  (rounding to fewer significant figures; percent <-> fraction or complement to
                  100%, only for percentages; a unit conversion within the number's own unit
                  family, e.g. kWh <-> MWh, minutes <-> hours);
    unsupported - anything else: a failure.
  Dates, years, block IDs, URLs, list markers, small counts (0-10) are ignored.
A task passes only if those three checks pass. Reported beside them, not part of the pass:
- disclosure: when a tool flagged distances as ESTIMATED and blocks as INFERRED (London), the
  answer says both.
All text is normalise()d first: Unicode escapes decoded; typographic hyphens, minus signs and
no-break or thin spaces made plain; numbers in words turned into digits.
Units (eval-v1.3): an answer number only matches a source number whose unit agrees (220.7 km
doesn't back "220.7 minutes"); a unit written once covers a list before it ("234 and 203 km");
a bare number in the question or context can't back a number with a unit. IDs named in tool
calls are never quantities. A small count (0-10) is ignored only when bare and unhedged.
evals/self_hack.py holds adversarial answers that probe what this can and can't catch.
"""

import json
import re
from datetime import date

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
_FIELD_NAME = re.compile(r'"([A-Za-z_]\w*)"\s*:')  # a JSON key, e.g. "block_error_p90_pct":
_LIST_MARKER = re.compile(r"^\s*\d+[.)]\s", re.MULTILINE)
SMALL_COUNT = 10  # bare integers up to this are treated as prose ("5 longest", "2 tools")
# Typographic characters that stand for plain ones: hyphens and the minus sign become "-",
# no-break and thin spaces become " ". Tool results arrive JSON-escaped ("−"), so escapes
# are decoded first.
_PLAIN = str.maketrans({"‐": "-", "‑": "-", "‒": "-", "−": "-",
                        " ": " ", " ": " ", " ": " ", " ": " ",
                        " ": " ", " ": " "})
_ESCAPE = re.compile(r"\\u([0-9a-fA-F]{4})")


_WORD_VALUES = {w: i for i, w in enumerate(
    ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"])}
_WORD_VALUES.update({w: 10 * i for i, w in enumerate(
    ["twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"], start=2)})
_WORD_SCALES = {"hundred": 100, "thousand": 1000, "million": 10**6, "billion": 10**9}
_NUMBER_WORD = "|".join(list(_WORD_VALUES) + list(_WORD_SCALES))
_NUMBER_WORDS = re.compile(rf"\b(?:{_NUMBER_WORD})(?:(?:\s+and\s+|[\s-]+)(?:{_NUMBER_WORD}))*\b",
                           re.IGNORECASE)


def _words_to_number(match):
    """'one hundred and ninety' -> '190'; a lone scale word ('million') is left as it is."""
    words = re.split(r"[\s-]+", match.group(0).lower().replace(" and ", " "))
    if words[0] in _WORD_SCALES:
        return match.group(0)
    total = current = 0
    for word in words:
        if word in _WORD_VALUES:
            current += _WORD_VALUES[word]
        elif word == "hundred":
            current *= 100
        else:
            total, current = total + current * _WORD_SCALES[word], 0
    return str(total + current)


def normalise(text):
    """Text with Unicode escapes decoded, typographic hyphens, minus signs and spaces made plain,
    and numbers written in words turned into digits ("ninety kilometres" -> "90 kilometres")."""
    text = _ESCAPE.sub(lambda m: chr(int(m.group(1), 16)), str(text)).translate(_PLAIN)
    return _NUMBER_WORDS.sub(_words_to_number, text)


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
# One qualifying word may sit between a number and its unit ("161.4 revenue km").
_UNIT = re.compile(
    r"\s*-?\s*(?:[a-z]+\s+)?(%|per ?cent|kwh|mwh|gwh|mj|kw|mw|gw|km|kilometres?|kilometers?|"
    r"miles?|mi|minutes?|mins?|min|hours?|hrs?|h)(?![a-z])", re.IGNORECASE)
UNIT_FAMILIES = {
    "percent": ({"%", "percent", "per cent"}, ()),
    "energy": ({"kwh", "mwh", "gwh", "mj"}, (1000, 1e6, 3.6, 3600)),
    "power": ({"kw", "mw", "gw"}, (1000, 1e6)),
    "distance": ({"km", "kilometre", "kilometres", "kilometer", "kilometers", "mile", "miles", "mi"},
                 (1.609344, 1000)),
    "time": ({"min", "mins", "minute", "minutes", "h", "hr", "hrs", "hour", "hours"}, (60,)),
}
_PERCENT_KEY = re.compile(r'"[^"]*(?:pct|percent)[^"]*"\s*:\s*$', re.IGNORECASE)
# A JSON value's unit, from its key's suffix ("daily_km": 52983.0 is a distance).
_KEY_UNIT = re.compile(r'"[^"]*_(km|kwh|mwh|kw|mw|minutes|hours)"\s*:\s*$', re.IGNORECASE)
_KEY_FAMILY = {"km": "distance", "kwh": "energy", "mwh": "energy", "kw": "power", "mw": "power",
               "minutes": "time", "hours": "time"}
# An ID is never a quantity: JSON "..._id" values in tool calls are ignored wherever they appear.
_ID_VALUE = re.compile(r'"\w*_id"\s*:\s*"([^"]*)"')
_LIST_JOIN = re.compile(r"\s*(?:,|and|or|to|-|–)\s*", re.IGNORECASE)
# A hedge before a number marks it as an estimate, never as prose ("roughly 2", "about 9").
_HEDGE = re.compile(r"(?:about|around|roughly|approximately|approx\.?|nearly|almost|some|~|≈)\s*$",
                    re.IGNORECASE)


def compatible(answer_family, families):
    """An answer number's unit agrees with a source number's: either has no unit, or they match."""
    return (answer_family in (None, "multiplier") or not families or None in families
            or answer_family in families)


def _unit_family(text, end):
    m = _UNIT.match(text, end)
    if not m:
        return None
    word = m.group(1).lower()
    return next((family for family, (words, _) in UNIT_FAMILIES.items() if word in words), None)


def parse_with_units(text):
    """[(value, half_unit, raw, unit_family, start)]; a JSON value under a "pct"/"percent" key
    counts as a percentage, and one under a unit-suffixed key ("..._km") has that unit."""
    found = []
    for value, half_unit, start, raw in parse_numbers(text):
        family = _unit_family(text, start + len(raw))
        if family is None and _PERCENT_KEY.search(text[:start]):
            family = "percent"
        if family is None and (key := _KEY_UNIT.search(text[:start])):
            family = _KEY_FAMILY[key.group(1).lower()]
        if family is None and start > 0 and text[start - 1] in "x×":
            family = "multiplier"  # written as "x1.425"
        found.append((value, half_unit, raw, family, start))
    # A unit written once covers a list or range before it: "234 and 203 km", "8-10 h".
    for i in range(len(found) - 2, -1, -1):
        value, half_unit, raw, family, start = found[i]
        following = found[i + 1]
        if family is None and following[3] and _LIST_JOIN.fullmatch(text[start + len(raw):following[4]]):
            found[i] = (value, half_unit, raw, following[3], start)
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


def number_match(value, half_unit, raw, target):
    """How an answer's number matches a target, for every check alike: "exact" (the target at
    the answer's own precision), "rounded" (to fewer significant figures: "19,400" for 19,449)
    or None."""
    if matches(value, half_unit, target):
        return "exact"
    rounded = _rounding_half_unit(raw, half_unit)
    if rounded is not None and matches(value, rounded, target):
        return "rounded"
    return None


def tool_ids(tool_calls):
    """Every ID a tool call names (JSON "..._id" values in its input and result)."""
    return {m.group(1) for call in tool_calls
            for text in (json.dumps(call.get("input", {})), normalise(call.get("result", "")))
            for m in _ID_VALUE.finditer(text) if m.group(1)}


def _strip_tokens(text, tokens):
    for token in sorted(tokens, key=len, reverse=True):
        if token:
            text = text.replace(token, " ")
    return text


def tool_numbers(tool_calls, ignore_tokens=()):
    """(every number in every tool call's input and result, {number: "percent"/"multiplier"},
    {number: set of the unit families it appeared with}). IDs (JSON "..._id" values and the
    task's ignore_tokens) are not numbers."""
    numbers, kinds, families = set(), {}, {}
    for call in tool_calls:
        result = normalise(call.get("result", ""))
        for name in _FIELD_NAME.findall(result):
            for d in re.findall(r"\d+", name):
                numbers.add(float(d))
                families.setdefault(float(d), set()).add(None)
        for text in (json.dumps(call.get("input", {})), result):
            text = _strip_tokens(text, set(ignore_tokens) | tool_ids(tool_calls))
            for value, _, _, family, _ in parse_with_units(text):
                numbers.add(value)
                families.setdefault(value, set()).add(family)
                if family in ("percent", "multiplier"):
                    kinds[value] = family
    return numbers, kinds, families


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


BLOCK_TOOLS = ("get_block_distance", "get_block_duration")
# What our block tools say when they have no figure: the block doesn't run that day, or the
# date is outside the timetable they were built from.
NO_DATA = {"block_not_running": "does not run", "date_not_covered": "is outside the dates available"}


def _no_figure_reported(item, answer, tool_calls, ignore_tokens):
    """Structural check: a block tool, asked about this block (and date, if given), reported it
    has no figure, and the answer gives no distance or time (no number in km/miles or
    minutes/hours)."""
    reported = any(
        call["name"] in BLOCK_TOOLS
        and str(call.get("input", {}).get("block_id", "")) == item["block_id"]
        and str(call.get("input", {}).get("date", "")) == item.get("date", call.get("input", {}).get("date"))
        and NO_DATA[item["type"]] in normalise(call.get("result", ""))
        for call in tool_calls
    )
    figures = [raw for _, _, raw, family, _ in parse_with_units(_strip_ignored(answer, ignore_tokens))
               if family in ("distance", "time")]
    return reported and not figures


_MONTH_NUMBER = {name: i for i, names in enumerate(
    [("january", "jan"), ("february", "feb"), ("march", "mar"), ("april", "apr"), ("may",),
     ("june", "jun"), ("july", "jul"), ("august", "aug"), ("september", "sep", "sept"),
     ("october", "oct"), ("november", "nov"), ("december", "dec")], start=1) for name in names}
_ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DAY_MONTH = re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTHS})\b\.?(?:,?\s+(\d{{4}}))?", re.IGNORECASE)
_MONTH_DAY = re.compile(rf"\b({_MONTHS})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?:,?\s+(\d{{4}}))?", re.IGNORECASE)


def answer_dates(text, default_year):
    """Every date written in the text, in any of the usual forms; a date without a year is
    taken to be in default_year."""
    found = set()

    def add(year, month, day):
        try:
            found.add(date(int(year or default_year), month, int(day)))
        except ValueError:
            pass

    for y, m, d in _ISO_DATE.findall(text):
        add(y, int(m), d)
    for d, month, y in _DAY_MONTH.findall(text):
        add(y, _MONTH_NUMBER[month.lower()], d)
    for month, d, y in _MONTH_DAY.findall(text):
        add(y, _MONTH_NUMBER[month.lower()], d)
    return found


def _cites_source(item, answer, tool_calls):
    """Structural check: search_sources returned a passage from the document, and the answer
    names that document by its title, publisher or URL as the tool gave them."""
    lowered = answer.lower()
    for call in tool_calls:
        if call["name"] != "search_sources":
            continue
        try:
            results = json.loads(call.get("result", "")).get("results", [])
        except (json.JSONDecodeError, AttributeError):
            continue
        for hit in results:
            if hit.get("id", "").startswith(item["doc_id"] + "#") and any(
                    hit.get(key) and normalise(hit[key]).lower() in lowered
                    for key in ("title", "publisher", "url")):
                return True
    return False


def check_end_state(task, answer, tool_calls=(), context=""):
    """Oracle numbers and dates present, and required outcomes shown structurally."""
    answer = normalise(answer)
    missing = []
    ignore = set(task.get("ignore_tokens", [])) | tool_ids(tool_calls)
    numbers = parse_with_units(_strip_ignored(answer, ignore))
    _, _, families = tool_numbers(tool_calls, ignore)
    for item in task.get("oracle", []):
        if item["type"] == "number":
            # Same match as the unsupported check: precision or rounding, and the answer's unit
            # must agree with the unit the tool gave that number ("220.7 minutes" isn't 220.7 km).
            ok = any(
                all(any(number_match(v, h, raw, target) and compatible(family, families.get(target))
                        for v, h, raw, family, _ in numbers) for target in option)
                for option in item["accept"]
            )
        elif item["type"] == "date":
            target = date.fromisoformat(item["date"])
            ok = target in answer_dates(answer, target.year)
        elif item["type"] in NO_DATA:
            ok = _no_figure_reported(item, answer, tool_calls, ignore)
        elif item["type"] == "cites_source":
            ok = _cites_source(item, answer, tool_calls)
        elif item["type"] == "no_invented_figure":
            # Abstention: every number given is backed by a tool output or the agent's context.
            ok = check_unsupported(task, answer, tool_calls, context)["pass"]
        else:
            raise ValueError(f"unknown oracle type {item['type']}")
        if not ok:
            missing.append(item)
    return {"pass": not missing, "missing": missing}


def classify(value, half_unit, raw, family, supported, kinds=None, families=None):
    """("supported", None, None), ("derived", rule, source number) or ("unsupported", None, None).
    A source number only counts if its unit agrees with the answer's (families: number -> units)."""
    families = families or {}
    levels = {t: number_match(value, half_unit, raw, t) for t in supported
              if compatible(family, families.get(t))}
    if "exact" in levels.values():
        return "supported", None, None
    source = next((t for t, level in levels.items() if level == "rounded"), None)
    if source is not None:
        return "derived", "rounding to fewer significant figures", source
    tolerance = _rounding_half_unit(raw, half_unit) or half_unit
    for t in sorted(supported):
        for rule, candidate in _derivations(t, (kinds or {}).get(t), family):
            if rule == "unit conversion" and not compatible(family, families.get(t)):
                continue
            if matches(value, tolerance, candidate):
                return "derived", rule, t
    return "unsupported", None, None


def check_unsupported(task, answer, tool_calls, context=""):
    """Grade every number in the answer: supported, derived (warning) or unsupported (fail).

    context: the agent's tool descriptions, system prompt and source entries; numbers stated
    there count as supported."""
    ignore = set(task.get("ignore_tokens", [])) | tool_ids(tool_calls)
    supported, kinds, families = tool_numbers(tool_calls, ignore)
    for text in (_strip_ignored(normalise(task["question"]), ignore), _URL.sub(" ", normalise(context))):
        for value, _, _, family, _ in parse_with_units(text):
            supported.add(value)
            # A bare number in the question or context (a page number, a count) can't back an
            # answer number that has a unit; only a tool output's bare number can.
            families.setdefault(value, set()).add(family or "bare")
            if family in ("percent", "multiplier"):
                kinds[value] = family
    unsupported, derived = [], []
    text = _strip_ignored(normalise(answer), ignore)
    for value, half_unit, raw, family, start in parse_with_units(text):
        # A small bare count is prose ("the 5 longest"), unless it has a unit or a hedge
        # ("roughly 2 kWh", "about 9 passengers"): then it is a figure like any other.
        if (value.is_integer() and 0 <= value <= SMALL_COUNT and half_unit <= 0.5
                and family is None and not _HEDGE.search(text[:start])):
            continue
        if 1900 <= value <= 2100 and value.is_integer():
            continue  # a year
        level, rule, source = classify(value, half_unit, raw, family, supported, kinds, families)
        if level == "derived":
            derived.append({"number": raw.strip(), "rule": rule, "from": source})
        elif level == "unsupported":
            unsupported.append(raw.strip())
    return {"pass": not unsupported, "numbers": unsupported, "derived": derived}


def check_disclosure(answer, tool_calls):
    """When a tool flagged its distances as ESTIMATED and its blocks as INFERRED (London), the
    answer must say both: a word starting "estimat" and one starting "infer". Otherwise the
    check doesn't apply. Reported separately; not part of a task's pass."""
    flagged = [normalise(call.get("result", "")) for call in tool_calls]
    applies = any("ESTIMATED" in r for r in flagged) and any("INFERRED" in r for r in flagged)
    if not applies:
        return {"applies": False, "pass": True}
    lowered = normalise(answer).lower()
    missing = [word for word in ("estimat", "infer") if not re.search(rf"\b{word}", lowered)]
    return {"applies": True, "pass": not missing, "missing": missing}


def verify(task, result, context=""):
    """All checks for one run. result: {"answer", "tool_calls"} (or {"error"} if the run failed).
    context: the agent's tool descriptions, system prompt and source entries for this agency.
    pass covers steps, end_state and unsupported; disclosure is reported beside them."""
    if result.get("error"):
        failed = {"pass": False, "error": result["error"]}
        return {"steps": failed, "end_state": failed, "unsupported": failed,
                "disclosure": {"applies": False, "pass": True}, "pass": False}
    checks = {
        "steps": check_steps(task, result["tool_calls"]),
        "end_state": check_end_state(task, result["answer"], result["tool_calls"], context),
        "unsupported": check_unsupported(task, result["answer"], result["tool_calls"], context),
    }
    checks["pass"] = all(c["pass"] for c in checks.values())
    checks["disclosure"] = check_disclosure(result["answer"], result["tool_calls"])
    return checks
