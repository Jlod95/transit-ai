"""Daily distance per block from a GTFS feed.

A "block" is the chain of trips one vehicle drives in a day. Summing the length of each
trip in a block gives the revenue distance that vehicle covers, which is the starting point
for checking whether a battery-electric bus could run it.

Uses only the Python standard library.
"""

import csv
import io
import zipfile
from collections import defaultdict
from datetime import date
from pathlib import Path

FERRY_ROUTE_TYPE = "4"
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


def _read_table(zf, name):
    """Yield rows of a GTFS file in the zip as dicts; yields nothing if the file is missing."""
    for member in zf.namelist():
        if Path(member).name == name:
            with zf.open(member) as raw:
                text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
                yield from csv.DictReader(text)
            return


def _active_service_ids(zf, service_date):
    """Return the service_ids that run on service_date."""
    day = service_date.strftime("%Y%m%d")
    weekday = WEEKDAYS[service_date.weekday()]

    # Regular weekly pattern: inside the date range and running on this day of the week.
    active = {
        row["service_id"]
        for row in _read_table(zf, "calendar.txt")
        if row["start_date"] <= day <= row["end_date"] and row[weekday] == "1"
    }

    # One-off exceptions for this exact date: 1 = service added, 2 = service removed.
    for row in _read_table(zf, "calendar_dates.txt"):
        if row["date"] == day:
            if row["exception_type"] == "1":
                active.add(row["service_id"])
            elif row["exception_type"] == "2":
                active.discard(row["service_id"])
    return active


def _bus_trip_blocks(zf, service_date):
    """Return {trip_id: block_id} for bus trips with a block_id running on service_date.

    Ferries (route_type 4) and trips without a block_id are excluded.
    """
    ferry_routes = {
        row["route_id"]
        for row in _read_table(zf, "routes.txt")
        if row["route_type"] == FERRY_ROUTE_TYPE
    }
    services = _active_service_ids(zf, service_date)

    trip_block = {}
    for row in _read_table(zf, "trips.txt"):
        block_id = (row.get("block_id") or "").strip()
        if block_id and row["service_id"] in services and row["route_id"] not in ferry_routes:
            trip_block[row["trip_id"]] = block_id
    return trip_block


def gtfs_time_to_seconds(text):
    """Convert a GTFS time like "26:01:00" to seconds after midnight at the start of the
    service day. Hours can be 24 or more for trips after midnight, and are not wrapped to 0.
    """
    hours, minutes, seconds = (int(part) for part in text.strip().split(":"))
    return hours * 3600 + minutes * 60 + seconds


def daily_block_distance(feed_path, service_date: date) -> dict[str, float]:
    """Return {block_id: revenue km} for bus blocks running on service_date.

    Trip length is the largest shape_dist_traveled in stop_times.txt for that trip.
    Ferries (route_type 4) and trips without a block_id are excluded. Deadhead
    (empty running between trips or to/from the garage) is not in GTFS, so it is not counted.

    Raises MissingDistanceError if any of those bus trips has no shape_dist_traveled values,
    rather than silently counting it as 0 km.
    """
    with zipfile.ZipFile(feed_path) as zf:
        trip_block = _bus_trip_blocks(zf, service_date)

        trip_length = {}
        for row in _read_table(zf, "stop_times.txt"):
            dist = (row.get("shape_dist_traveled") or "").strip()
            if dist and row["trip_id"] in trip_block:
                trip_length[row["trip_id"]] = max(trip_length.get(row["trip_id"], 0.0), float(dist))

    missing = {t: b for t, b in trip_block.items() if t not in trip_length}
    if missing:
        raise MissingDistanceError(missing)

    block_distance = defaultdict(float)
    for trip_id, block_id in trip_block.items():
        block_distance[block_id] += trip_length[trip_id]
    return dict(block_distance)


def daily_block_duration(feed_path, service_date: date) -> dict[str, float]:
    """Return {block_id: minutes} from first departure to last arrival, for bus blocks
    running on service_date.

    Times within a block only move forward, so the earliest departure and the latest
    arrival across all its stop times are the first trip's start and the last trip's end.
    Uses the same trip filtering as daily_block_distance.
    """
    with zipfile.ZipFile(feed_path) as zf:
        trip_block = _bus_trip_blocks(zf, service_date)

        block_start = {}
        block_end = {}
        for row in _read_table(zf, "stop_times.txt"):
            block_id = trip_block.get(row["trip_id"])
            if block_id is None:
                continue
            # Stops between timepoints may have blank times; skip those.
            departure = (row.get("departure_time") or "").strip()
            arrival = (row.get("arrival_time") or "").strip()
            if departure:
                start = gtfs_time_to_seconds(departure)
                block_start[block_id] = min(block_start.get(block_id, start), start)
            if arrival:
                end = gtfs_time_to_seconds(arrival)
                block_end[block_id] = max(block_end.get(block_id, end), end)

    return {block_id: (block_end[block_id] - block_start[block_id]) / 60 for block_id in block_start}
