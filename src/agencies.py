"""The agencies the app knows about: where each one's raw feeds are, and how its block
distances and blocks are worked out. Every method is labelled, so answers can say when a
number is exact, estimated or inferred.
"""

from dataclasses import dataclass

# Distance methods: how each trip's length is found.
DISTANCE_METHODS = {
    "stop_times": "exact: shape_dist_traveled in stop_times.txt",
    "shapes": "exact: length of the trip's shape in shapes.txt, converted from metres to km",
    "straight_line": (
        "ESTIMATED: straight lines between consecutive stops, multiplied by a road factor "
        "calibrated on Dublin's exact shape distances"
    ),
}

# Block methods: how trips are grouped into one bus's day.
BLOCK_METHODS = {
    "gtfs": "published: the feed's block_id",
    "inferred": (
        "INFERRED: per route, a bus that arrives at a terminal takes the next trip leaving that "
        "terminal (same stop or within 400 m) at least 5 minutes later; otherwise a new bus "
        "starts. No interlining between routes."
    ),
}

# London's region file mixes TfL buses with airport, rail-replacement and county services and
# has no TfL flag, so "TfL" means these operators' London bus fleets. Approximate: a few
# commercial routes may be included and some small TfL contractors are left out.
TFL_OPERATORS = (
    "Arriva London",
    "Arriva London North",
    "Arriva London South",
    "Go Ahead London",
    "London Sovereign",
    "London Transit",
    "London United",
    "Metrobus",
    "Metroline Travel",
    "Stagecoach London",
    "Transport UK",
)


@dataclass(frozen=True)
class Agency:
    key: str
    name: str
    feeds: tuple[str, ...]  # raw GTFS zips, relative to the project root
    distance: str  # a DISTANCE_METHODS key
    blocks: str  # a BLOCK_METHODS key
    operators: tuple[str, ...] = ()  # keep only these agency_names (empty = all)
    days_ahead: int | None = None  # build only this many days from the build date
    calibrate_with: str | None = None  # agency whose exact distances set the road factor
    note: str = ""


AGENCIES = {
    "halifax": Agency(
        key="halifax",
        name="Halifax Transit",
        feeds=("data/raw/halifax.zip",),
        distance="stop_times",
        blocks="gtfs",
    ),
    "dublin": Agency(
        key="dublin",
        name="Dublin (Dublin Bus and Go-Ahead Ireland)",
        feeds=("data/raw/dublin_bus.zip", "data/raw/dublin_goahead.zip"),
        distance="shapes",
        blocks="gtfs",
    ),
    "london": Agency(
        key="london",
        name="London (TfL buses)",
        feeds=("data/raw/london_uk.zip",),
        distance="straight_line",
        blocks="inferred",
        operators=TFL_OPERATORS,
        days_ahead=28,
        calibrate_with="dublin",
        note="TfL buses approximated by operator; only the 28 days from the build date are built.",
    ),
}
DEFAULT_AGENCY = "halifax"


def get_agency(key):
    if key not in AGENCIES:
        raise ValueError(f"Unknown agency {key!r}; expected one of {sorted(AGENCIES)}")
    return AGENCIES[key]
