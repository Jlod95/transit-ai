"""Daily distance and duration per block from a GTFS feed.

A "block" is the chain of trips one vehicle drives in a day. Summing the length of each
trip in a block gives the revenue distance that vehicle covers, which is the starting point
for checking whether a battery-electric bus could run it.

The work is split into small steps shared by the daily functions below and by
src/summaries.py, so trip filtering, trip lengths and trip times are defined once.

Uses only the Python standard library.
"""

import csv
import io
import zipfile
from collections import defaultdict
from datetime import date
from pathlib import Path

# GTFS route types that are buses: 3 (bus) and the extended bus range 700-799.
BUS_ROUTE_TYPES = {"3"} | {str(n) for n in range(700, 800)}
MIN_BLOCK_COVERAGE = 0.95
# Plausible average speed of one bus trip (its distance / its scheduled duration). A trip outside
# this range points to a data error: 0 km, a distance in the wrong unit (metres read as km),
# or a wrong schedule.
MIN_TRIP_SPEED_KMH = 3
MAX_TRIP_SPEED_KMH = 70  # 60 flagged rural intercity trips (Dublin route 120D, 61.4 km/h)
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


class MissingDistanceError(Exception):
    """Some bus trips running on the date have no shape_dist_traveled values at all.

    missing maps each affected trip_id to its block_id.
    """

    def __init__(self, missing):
        self.missing = missing
        listed = ", ".join(f"trip {t} (block {b})" for t, b in sorted(missing.items())[:10])
        more = f" and {len(missing) - 10} more" if len(missing) > 10 else ""
        super().__init__(
            f"{len(missing)} bus trip(s) have no shape_dist_traveled, so their block distances "
            f"would be wrong: {listed}{more}"
        )


class BlockCoverageError(Exception):
    """Too few of the bus trips running on a date have a block_id to trust per-block results."""

    def __init__(self, with_block, total):
        self.with_block = with_block
        self.total = total
        self.pct = 100 * with_block / total
        super().__init__(
            f"Only {self.pct:.1f}% of bus trips ({with_block:,} of {total:,}) have a block_id; "
            f"at least {MIN_BLOCK_COVERAGE:.0%} is needed, otherwise the trips without one "
            f"would be silently left out of every block."
        )


class TripSpeedError(Exception):
    """Some bus trips have an implausible average speed (distance / scheduled duration).

    problems maps each affected trip_id to {"block", "km", "minutes", "kmh"}.
    """

    def __init__(self, problems, min_kmh=MIN_TRIP_SPEED_KMH, max_kmh=MAX_TRIP_SPEED_KMH):
        self.problems = problems
        def describe(trip_id, p):
            speed = "infinite" if p["kmh"] is None else f"{p['kmh']:.1f}"
            return f"trip {trip_id} (block {p['block']}: {p['km']:g} km in {p['minutes']:g} min = {speed} km/h)"

        listed = ", ".join(describe(t, p) for t, p in sorted(problems.items())[:10])
        more = f" and {len(problems) - 10} more" if len(problems) > 10 else ""
        super().__init__(
            f"{len(problems)} bus trip(s) have an average speed outside {min_kmh}-{max_kmh} km/h, "
            f"which points to a wrong distance or schedule: {listed}{more}"
        )


def trip_speed_problems(trip_block, lengths, starts, ends,
                        min_kmh=MIN_TRIP_SPEED_KMH, max_kmh=MAX_TRIP_SPEED_KMH):
    """{trip_id: {"block", "km", "minutes", "kmh"}} for trips whose km / scheduled hours is
    outside min_kmh-max_kmh. A trip scheduled to take 0 minutes is flagged (kmh None: infinite);
    a trip without a distance or times can't be checked here and is skipped."""
    problems = {}
    for trip_id, block_id in trip_block.items():
        if trip_id not in lengths or trip_id not in starts or trip_id not in ends:
            continue
        km, seconds = lengths[trip_id], ends[trip_id] - starts[trip_id]
        kmh = km / (seconds / 3600) if seconds > 0 else None
        if kmh is None or not min_kmh <= kmh <= max_kmh:
            problems[trip_id] = {"block": block_id, "km": round(km, 3), "minutes": round(seconds / 60, 1),
                                 "kmh": None if kmh is None else round(kmh, 1)}
    return problems


def check_trip_speeds(trip_block, lengths, starts, ends,
                      min_kmh=MIN_TRIP_SPEED_KMH, max_kmh=MAX_TRIP_SPEED_KMH):
    """Raise TripSpeedError if any trip's average speed is implausible (see trip_speed_problems)."""
    problems = trip_speed_problems(trip_block, lengths, starts, ends, min_kmh, max_kmh)
    if problems:
        raise TripSpeedError(problems, min_kmh, max_kmh)


def _read_table(zf, name):
    """Yield rows of a GTFS file in the zip as dicts; yields nothing if the file is missing."""
    for member in zf.namelist():
        if Path(member).name == name:
            with zf.open(member) as raw:
                text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
                yield from csv.DictReader(text)
            return


def _load_calendar(zf):
    """Return (calendar rows, {date "YYYYMMDD": [(service_id, exception_type)]})."""
    calendar = list(_read_table(zf, "calendar.txt"))
    exceptions = defaultdict(list)
    for row in _read_table(zf, "calendar_dates.txt"):
        exceptions[row["date"]].append((row["service_id"], row["exception_type"]))
    return calendar, exceptions


def _services_on(calendar, exceptions, service_date):
    """Return the service_ids that run on service_date."""
    day = service_date.strftime("%Y%m%d")
    weekday = WEEKDAYS[service_date.weekday()]

    # Regular weekly pattern: inside the date range and running on this day of the week.
    active = {
        row["service_id"]
        for row in calendar
        if row["start_date"] <= day <= row["end_date"] and row[weekday] == "1"
    }
    # One-off exceptions for this exact date: 1 = service added, 2 = service removed.
    for service_id, exception_type in exceptions.get(day, []):
        if exception_type == "1":
            active.add(service_id)
        elif exception_type == "2":
            active.discard(service_id)
    return active


def _bus_trips(zf):
    """Return {trip_id: (service_id, block_id)} for every bus trip in the feed.

    Only routes whose route_type is a bus type are kept, so rail, metro, trams, ferries,
    cable cars and coaches are left out. block_id is "" when the trip has none.
    """
    bus_routes = {
        row["route_id"]
        for row in _read_table(zf, "routes.txt")
        if (row.get("route_type") or "").strip() in BUS_ROUTE_TYPES
    }
    return {
        row["trip_id"]: (row["service_id"], (row.get("block_id") or "").strip())
        for row in _read_table(zf, "trips.txt")
        if row["route_id"] in bus_routes
    }


def _blocks_for_services(bus_trips, services):
    """Return {trip_id: block_id} for bus trips in the given services.

    Raises BlockCoverageError if fewer than 95% of those trips have a block_id, instead of
    silently dropping the ones without.
    """
    running = {t: b for t, (s, b) in bus_trips.items() if s in services}
    trip_block = {t: b for t, b in running.items() if b}
    if running and len(trip_block) / len(running) < MIN_BLOCK_COVERAGE:
        raise BlockCoverageError(len(trip_block), len(running))
    return trip_block


def _bus_trip_blocks(zf, service_date):
    """Return {trip_id: block_id} for bus trips running on service_date (with the coverage check)."""
    calendar, exceptions = _load_calendar(zf)
    return _blocks_for_services(_bus_trips(zf), _services_on(calendar, exceptions, service_date))


def _trip_lengths_and_times(zf, trip_ids):
    """One pass over stop_times.txt for the given trips.

    Returns (lengths, starts, ends): each trip's largest shape_dist_traveled, its earliest
    departure and its latest arrival in seconds. Trips with no distance value are absent from
    lengths. Stops between timepoints may have blank times; those are skipped.
    """
    lengths, starts, ends = {}, {}, {}
    for row in _read_table(zf, "stop_times.txt"):
        trip_id = row["trip_id"]
        if trip_id not in trip_ids:
            continue
        dist = (row.get("shape_dist_traveled") or "").strip()
        if dist:
            lengths[trip_id] = max(lengths.get(trip_id, 0.0), float(dist))
        departure = (row.get("departure_time") or "").strip()
        if departure:
            seconds = gtfs_time_to_seconds(departure)
            starts[trip_id] = min(starts.get(trip_id, seconds), seconds)
        arrival = (row.get("arrival_time") or "").strip()
        if arrival:
            seconds = gtfs_time_to_seconds(arrival)
            ends[trip_id] = max(ends.get(trip_id, seconds), seconds)
    return lengths, starts, ends


def _block_distances(trip_block, lengths):
    """Sum trip lengths per block, raising MissingDistanceError if any trip has no length."""
    missing = {t: b for t, b in trip_block.items() if t not in lengths}
    if missing:
        raise MissingDistanceError(missing)
    block_distance = defaultdict(float)
    for trip_id, block_id in trip_block.items():
        block_distance[block_id] += lengths[trip_id]
    return dict(block_distance)


def _block_spans(trip_block, starts, ends):
    """{block_id: (first departure, last arrival)} in seconds after the service day's midnight.

    Times within a block only move forward, so the earliest departure and the latest
    arrival across its trips are the first trip's start and the last trip's end.
    """
    block_start, block_end = {}, {}
    for trip_id, block_id in trip_block.items():
        if trip_id in starts:
            block_start[block_id] = min(block_start.get(block_id, starts[trip_id]), starts[trip_id])
        if trip_id in ends:
            block_end[block_id] = max(block_end.get(block_id, ends[trip_id]), ends[trip_id])
    return {b: (block_start[b], block_end[b]) for b in block_start}


def _block_durations(trip_block, starts, ends):
    """Minutes from each block's first departure to its last arrival."""
    return {b: (end - start) / 60 for b, (start, end) in _block_spans(trip_block, starts, ends).items()}


def gtfs_time_to_seconds(text):
    """Convert a GTFS time like "26:01:00" to seconds after midnight at the start of the
    service day. Hours can be 24 or more for trips after midnight, and are not wrapped to 0.
    """
    hours, minutes, seconds = (int(part) for part in text.strip().split(":"))
    return hours * 3600 + minutes * 60 + seconds


def daily_block_distance(feed_path, service_date: date) -> dict[str, float]:
    """Return {block_id: revenue km} for bus blocks running on service_date.

    Trip length is the largest shape_dist_traveled in stop_times.txt for that trip. Only bus
    route types count. Deadhead (empty running between trips or to/from the garage) is not
    in GTFS, so it is not counted.

    Raises BlockCoverageError if under 95% of that day's bus trips have a block_id,
    MissingDistanceError if any of them has no shape_dist_traveled values, and TripSpeedError
    if any trip's distance / scheduled duration is outside MIN_TRIP_SPEED_KMH-MAX_TRIP_SPEED_KMH,
    rather than silently leaving trips out or counting wrong distances.
    """
    with zipfile.ZipFile(feed_path) as zf:
        trip_block = _bus_trip_blocks(zf, service_date)
        lengths, starts, ends = _trip_lengths_and_times(zf, trip_block)
    distances = _block_distances(trip_block, lengths)
    check_trip_speeds(trip_block, lengths, starts, ends)
    return distances


def daily_block_duration(feed_path, service_date: date) -> dict[str, float]:
    """Return {block_id: minutes} from first departure to last arrival, for bus blocks
    running on service_date. Uses the same trip filtering as daily_block_distance.
    """
    with zipfile.ZipFile(feed_path) as zf:
        trip_block = _bus_trip_blocks(zf, service_date)
        _, starts, ends = _trip_lengths_and_times(zf, trip_block)
    return _block_durations(trip_block, starts, ends)
