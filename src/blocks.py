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


def daily_block_distance(feed_path, service_date: date) -> dict[str, float]:
    """Return {block_id: revenue km} for bus blocks running on service_date.

    Trip length is the largest shape_dist_traveled in stop_times.txt for that trip.
    Ferries (route_type 4) and trips without a block_id are excluded. Deadhead
    (empty running between trips or to/from the garage) is not in GTFS, so it is not counted.
    """
    with zipfile.ZipFile(feed_path) as zf:
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

        trip_length = defaultdict(float)
        for row in _read_table(zf, "stop_times.txt"):
            dist = (row.get("shape_dist_traveled") or "").strip()
            if dist and row["trip_id"] in trip_block:
                trip_length[row["trip_id"]] = max(trip_length[row["trip_id"]], float(dist))

    block_distance = defaultdict(float)
    for trip_id, block_id in trip_block.items():
        block_distance[block_id] += trip_length[trip_id]
    return dict(block_distance)
