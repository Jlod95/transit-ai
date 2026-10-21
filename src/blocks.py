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


def _block_durations(trip_block, starts, ends):
    """Minutes from each block's first departure to its last arrival.

    Times within a block only move forward, so the earliest departure and the latest
    arrival across its trips are the first trip's start and the last trip's end.
    """
    block_start, block_end = {}, {}
    for trip_id, block_id in trip_block.items():
        if trip_id in starts:
            block_start[block_id] = min(block_start.get(block_id, starts[trip_id]), starts[trip_id])
        if trip_id in ends:
            block_end[block_id] = max(block_end.get(block_id, ends[trip_id]), ends[trip_id])
    return {b: (block_end[b] - block_start[b]) / 60 for b in block_start}


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

    Raises BlockCoverageError if under 95% of that day's bus trips have a block_id, and
    MissingDistanceError if any of them has no shape_dist_traveled values, rather than
    silently leaving trips out or counting them as 0 km.
    """
    with zipfile.ZipFile(feed_path) as zf:
        trip_block = _bus_trip_blocks(zf, service_date)
        lengths, _, _ = _trip_lengths_and_times(zf, trip_block)
    return _block_distances(trip_block, lengths)


def daily_block_duration(feed_path, service_date: date) -> dict[str, float]:
    """Return {block_id: minutes} from first departure to last arrival, for bus blocks
    running on service_date. Uses the same trip filtering as daily_block_distance.
    """
    with zipfile.ZipFile(feed_path) as zf:
        trip_block = _bus_trip_blocks(zf, service_date)
        _, starts, ends = _trip_lengths_and_times(zf, trip_block)
    return _block_durations(trip_block, starts, ends)
