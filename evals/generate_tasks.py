"""Generate evals/tasks.jsonl from templates, with a fixed random seed.

Usage:
    python evals/generate_tasks.py

Block IDs and dates are picked from the committed summaries, and every oracle number is taken
from the output of our own tool functions for that exact question: never typed by hand.
Splits: dev = Halifax; heldout = Dublin and London.
"""

import json
import random
import re
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.agencies import get_agency
from src.agent import run_tool, summary_for

SEED = 2026
OUT = Path(__file__).parent / "tasks.jsonl"
NOT_RUNNING_PHRASES = ["does not run", "doesn't run", "not run", "isn't running", "is not running",
                       "not in service", "no service", "doesn't operate", "does not operate",
                       "not operating", "isn't scheduled", "is not scheduled", "not scheduled"]
OUTSIDE_PHRASES = ["outside", "not covered", "doesn't cover", "does not cover", "only covers",
                   "beyond", "isn't covered", "is not covered", "not available", "no data"]
ABSTAIN_PHRASES = ["can't", "cannot", "can not", "don't have", "do not have", "not available",
                   "no data", "unable", "isn't available", "is not available", "doesn't include",
                   "does not include", "doesn't contain", "does not contain", "not in the data",
                   "no information", "don't hold", "do not hold", "not something"]


def call(name, **args):
    text, is_error = run_tool(name, args)
    if is_error:
        raise RuntimeError(f"{name}{args} failed: {text}")
    return text


def number(label, *options):
    """An oracle number: any one of the options (each a list of values) must appear."""
    return {"type": "number", "label": label, "accept": [list(o) for o in options]}


def say(d):
    return f"{d.day} {d:%B %Y}"


def date_renderings(iso):
    d = date.fromisoformat(iso)
    return [iso, say(d), f"{d:%B} {d.day}, {d.year}", f"{d:%B} {d.day}", f"{d.day} {d:%B}",
            f"{d:%b} {d.day}", f"{d.day} {d:%b}"]


class Builder:
    def __init__(self, seed):
        self.rng = random.Random(seed)
        self.tasks = []

    def add(self, agency, category, question, expected_calls, oracle, ignore_tokens=()):
        split = "dev" if agency == "halifax" else "heldout"
        n = sum(1 for t in self.tasks if t["agency"] == agency) + 1
        self.tasks.append({
            "id": f"{agency}-{n:02d}-{category}",
            "agency": agency,
            "split": split,
            "category": category,
            "question": question,
            "expected_calls": expected_calls,
            "oracle": oracle,
            "ignore_tokens": list(ignore_tokens),
        })

    # --- picking real data from the committed summaries ---

    def service_dates(self, agency):
        return sorted(summary_for(agency)["by_date"])

    def pick_date(self, agency, weekday=True):
        dates = [d for d in self.service_dates(agency) if (date.fromisoformat(d).weekday() < 5) == weekday]
        return self.rng.choice(dates)

    def pick_block(self, agency, iso):
        blocks = summary_for(agency)["by_date"][iso]["blocks"]
        typical = sorted(b for b, v in blocks.items() if 40 <= v["km"] <= 300)
        return self.rng.choice(typical)

    # --- templates ---

    def block_distance(self, agency):
        iso = self.pick_date(agency)
        block = self.pick_block(agency, iso)
        text = call("get_block_distance", agency=agency, block_id=block, date=iso)
        km = float(re.search(r"drives ([\d.]+) revenue km", text).group(1))
        self.add(agency, "block_distance",
                 f"How far does block {block} drive on {say(date.fromisoformat(iso))}?",
                 [{"name": "get_block_distance", "args": {"agency": agency, "block_id": block, "date": iso}}],
                 [number("km", [km])], [block])

    def _duration_oracle(self, text):
        hours, mins = map(int, re.search(r"(\d+) h (\d+) min", text).groups())
        total = hours * 60 + mins
        return number("duration", [hours, mins], [total], [total / 60])

    def block_duration(self, agency):
        iso = self.pick_date(agency)
        block = self.pick_block(agency, iso)
        text = call("get_block_duration", agency=agency, block_id=block, date=iso)
        self.add(agency, "block_duration",
                 f"How long is block {block} in service on {say(date.fromisoformat(iso))}?",
                 [{"name": "get_block_duration", "args": {"agency": agency, "block_id": block, "date": iso}}],
                 [self._duration_oracle(text)], [block])

    def block_both(self, agency):
        iso = self.pick_date(agency)
        block = self.pick_block(agency, iso)
        args = {"agency": agency, "block_id": block, "date": iso}
        km = float(re.search(r"drives ([\d.]+) revenue km", call("get_block_distance", **args)).group(1))
        self.add(agency, "block_both",
                 f"Give me the distance and the service time for block {block} on "
                 f"{say(date.fromisoformat(iso))}.",
                 [{"name": "get_block_distance", "args": args}, {"name": "get_block_duration", "args": args}],
                 [number("km", [km]), self._duration_oracle(call("get_block_duration", **args))], [block])

    def fleet_feasibility(self, agency, season):
        iso = self.pick_date(agency)
        r = json.loads(call("get_fleet_feasibility", agency=agency, date=iso, season=season))
        name = get_agency(agency).name
        self.add(agency, f"feasibility_{season}",
                 f"How many {name} blocks could run on one overnight charge in {season} on "
                 f"{say(date.fromisoformat(iso))}?",
                 [{"name": "get_fleet_feasibility", "args": {"agency": agency, "date": iso, "season": season}}],
                 [number("blocks within range", [r["within_range"]]),
                  number("% within range", [r["pct_within_range"]])])

    def design_day(self, agency, season):
        r = json.loads(call("get_design_day", agency=agency, season=season))
        name = get_agency(agency).name
        self.add(agency, "design_day",
                 f"Which day should {name} plan its electric fleet around in {season}, and how many "
                 f"blocks would be too long for one charge that day?",
                 [{"name": "get_design_day", "args": {"agency": agency, "season": season}}],
                 [{"type": "date_any", "label": "design day", "renderings": date_renderings(r["design_day"])},
                  number("blocks over range", [r["blocks_over_range"]])])

    def fleet_size(self, agency, season):
        r = json.loads(call("get_fleet_size", agency=agency, season=season))
        name = get_agency(agency).name
        self.add(agency, "fleet_size",
                 f"How many electric buses would {name} need in {season}, compared with today, and "
                 f"what is the replacement ratio?",
                 [{"name": "get_fleet_size", "args": {"agency": agency, "season": season}}],
                 [number("buses today", [r["buses_needed_today"]]),
                  number("electric buses", [r["electric_buses_needed"]]),
                  number("ratio", [r["replacement_ratio"]])])

    def charging(self, agency, season):
        r = json.loads(call("get_charging_needs", agency=agency, season=season))
        name = get_agency(agency).name
        self.add(agency, "charging",
                 f"How much energy and peak depot power would {name}'s electric fleet need to charge "
                 f"overnight in {season}?",
                 [{"name": "get_charging_needs", "args": {"agency": agency, "season": season}}],
                 [number("overnight energy", [r["overnight_energy_mwh"]], [r["overnight_energy_kwh"]]),
                  number("peak power", [r["peak_depot_power_mw"]], [r["peak_depot_power_kw"]])])

    def cost_and_co2(self, agency, season):
        r = json.loads(call("get_cost_and_co2", agency=agency, season=season))
        name = get_agency(agency).name
        self.add(agency, "cost_co2",
                 f"Roughly what would electrifying {name}'s buses cost, and how much CO2 would it save "
                 f"each year? Assume {season} energy use.",
                 [{"name": "get_cost_and_co2", "args": {"agency": agency, "season": season}}],
                 [number("capital cost", [r["capital_cost"]]),
                  number("CO2 saved (t/yr)", [r["annual_co2_saved_tonnes"]])])

    def sources(self, agency, question, query, doc_id, number_pattern=None):
        r = json.loads(call("search_sources", query=query, k=5))
        hit = next(x for x in r["results"] if x["id"].startswith(doc_id + "#"))
        oracle = [{"type": "phrase_any", "label": "cites the source",
                   "phrases": [hit["title"], hit["publisher"]]}]
        if number_pattern:
            oracle.append(number("figure from the source",
                                 [float(re.search(number_pattern, hit["text"]).group(1))]))
        self.add(agency, "sources", question, [{"name": "search_sources"}], oracle)

    def not_running(self, agency):
        dates = self.service_dates(agency)
        for _ in range(200):
            iso = self.pick_date(agency)
            block = self.pick_block(agency, iso)
            off = [d for d in dates if block not in summary_for(agency)["by_date"][d]["blocks"]]
            if off:
                other = self.rng.choice(off)
                text = call("get_block_distance", agency=agency, block_id=block, date=other)
                assert "does not run" in text, text
                self.add(agency, "not_running",
                         f"How far does block {block} drive on {say(date.fromisoformat(other))}?",
                         [{"name_any": ["get_block_distance", "get_block_duration"],
                           "args": {"agency": agency, "block_id": block, "date": other}}],
                         [{"type": "phrase_any", "label": "says it doesn't run",
                           "phrases": NOT_RUNNING_PHRASES}], [block])
                return
        raise RuntimeError(f"no not-running case found for {agency}")

    def outside_timetable(self, agency):
        stamp = summary_for(agency)["stamp"]
        after = date.fromisoformat(stamp["calendar_end"]) + timedelta(days=self.rng.randint(30, 90))
        block = self.pick_block(agency, self.pick_date(agency))
        self.add(agency, "outside_timetable",
                 f"How far does block {block} drive on {say(after)}?",
                 [{"name_any": ["get_block_distance", "get_block_duration"],
                   "args": {"agency": agency, "block_id": block, "date": after.isoformat()}}],
                 [{"type": "phrase_any", "label": "says the date isn't covered", "phrases": OUTSIDE_PHRASES}],
                 [block])

    def abstain(self, agency, question):
        self.add(agency, "abstain", question, [],
                 [{"type": "phrase_any", "label": "says it can't answer", "phrases": ABSTAIN_PHRASES}])


def build():
    b = Builder(SEED)
    # Dev: Halifax (14).
    b.block_distance("halifax")
    b.block_duration("halifax")
    b.block_both("halifax")
    b.fleet_feasibility("halifax", "summer")
    b.fleet_feasibility("halifax", "winter")
    b.design_day("halifax", "winter")
    b.fleet_size("halifax", "winter")
    b.charging("halifax", "winter")
    b.cost_and_co2("halifax", "winter")
    b.sources("halifax", "According to published sources, how many kilograms of CO2 does burning a "
              "litre of diesel release?", "kg of CO2 per litre of diesel", "nrcan_fuel_co2_factsheet",
              r"([\d.]+) kg of CO2")
    b.not_running("halifax")
    b.outside_timetable("halifax")
    b.abstain("halifax", "What is the average number of passengers on a Halifax Transit bus at rush hour?")
    b.abstain("halifax", "How much does a Halifax Transit bus driver earn per hour?")
    # Held out: Dublin (8).
    b.block_distance("dublin")
    b.block_duration("dublin")
    b.block_both("dublin")
    b.fleet_feasibility("dublin", "winter")
    b.design_day("dublin", "summer")
    b.fleet_size("dublin", "summer")
    b.charging("dublin", "winter")
    b.not_running("dublin")
    # Held out: London (8).
    b.block_distance("london")
    b.block_both("london")
    b.fleet_feasibility("london", "summer")
    b.design_day("london", "winter")
    b.cost_and_co2("london", "winter")
    b.sources("london", "What does TfL's bus action plan say about when London's bus fleet will be "
              "fully zero-emission?", "London zero-emission bus fleet target year", "tfl_bus_action_plan_2022")
    b.outside_timetable("london")
    b.abstain("london", "How many London buses broke down last winter?")
    return b.tasks


if __name__ == "__main__":
    tasks = build()
    OUT.write_text("".join(json.dumps(t) + "\n" for t in tasks), encoding="utf-8", newline="\n")
    by_split = {s: sum(1 for t in tasks if t["split"] == s) for s in ("dev", "heldout")}
    print(f"Wrote {OUT}: {len(tasks)} tasks {by_split}")
