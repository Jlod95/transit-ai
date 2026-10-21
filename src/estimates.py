"""Distances and blocks for feeds that don't publish them.

- shape_lengths_km: trip length from shapes.txt (exact, but stored in metres by some feeds).
- straight_line_km: an ESTIMATE from straight lines between consecutive stops.
- chain_trips: INFERRED blocks, by chaining trips at terminals.

Summaries built with these record the method used, so answers can label the numbers.
"""

import math
from collections import defaultdict

from src.blocks import _read_table, gtfs_time_to_seconds

TURNAROUND_SECONDS = 300  # a bus needs at least 5 minutes at a terminal before its next trip
SAME_TERMINAL_KM = 0.4  # stops this close count as the same terminal (e.g. either side of a road)


def metres_to_km(metres):
    return metres / 1000


def haversine_km(a, b):
    """Great-circle distance in km between two (lat, lon) points."""
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def straight_line_km(points):
    """Sum of straight-line distances between consecutive (lat, lon) points."""
    return sum(haversine_km(points[i], points[i + 1]) for i in range(len(points) - 1))


def shape_lengths_km(zf, unit_to_km=metres_to_km):
    """{shape_id: km}: each shape's largest shape_dist_traveled, converted to km."""
    longest = {}
    for row in _read_table(zf, "shapes.txt"):
        value = (row.get("shape_dist_traveled") or "").strip()
        if value:
            longest[row["shape_id"]] = max(longest.get(row["shape_id"], 0.0), float(value))
    return {shape: unit_to_km(value) for shape, value in longest.items()}


def stop_coords(zf):
    return {
        row["stop_id"]: (float(row["stop_lat"]), float(row["stop_lon"]))
        for row in _read_table(zf, "stops.txt")
        if (row.get("stop_lat") or "").strip() and (row.get("stop_lon") or "").strip()
    }


def walk_trips(zf, trip_ids, coords):
    """One pass over stop_times for the given trips.

    Returns {trip_id: (first_stop, last_stop, start_seconds, end_seconds, straight_km)}.
    Rows within a trip may be out of order (London's are), so each trip's rows are collected
    and sorted by stop_sequence; but each trip's rows must be together, which is checked.
    """
    walks = {}
    done = set()
    current, rows = None, []

    def finish():
        if current is None or not rows:
            return
        rows.sort()
        stops = [stop for _, stop, _, _ in rows]
        departures = [gtfs_time_to_seconds(d) for _, _, d, _ in rows if d]
        arrivals = [gtfs_time_to_seconds(a) for _, _, _, a in rows if a]
        if not departures or not arrivals:
            return  # no usable times; the trip is reported as missing later
        points = [coords[s] for s in stops if s in coords]
        walks[current] = (stops[0], stops[-1], min(departures), max(arrivals), straight_line_km(points))

    for row in _read_table(zf, "stop_times.txt"):
        trip_id = row["trip_id"]
        if trip_id != current:
            finish()
            if trip_id in done:
                raise ValueError(f"stop_times.txt rows for trip {trip_id} are not together")
            if current is not None:
                done.add(current)
            current, rows = trip_id, []
        if trip_id in trip_ids:
            rows.append((
                int(row["stop_sequence"]),
                row["stop_id"],
                (row.get("departure_time") or "").strip(),
                (row.get("arrival_time") or "").strip(),
            ))
    finish()
    return walks


def chain_trips(trips, same_place=lambda a, b: a == b, turnaround=TURNAROUND_SECONDS):
    """Infer which trips one bus drives, by chaining them at terminals.

    trips: list of (trip_id, start_place, end_place, start_seconds, end_seconds).
    Trips are taken in departure order. A bus waiting at the trip's start place, having
    arrived at least `turnaround` seconds earlier, takes it (the one that has waited longest);
    otherwise a new bus starts. Returns a list of buses, each a list of trip_ids in order.
    """
    buses = []  # each: [trip_ids, place, free_at]
    for trip_id, start, end, dep, arr in sorted(trips, key=lambda t: (t[3], t[0])):
        waiting = [b for b in buses if same_place(b[1], start) and b[2] + turnaround <= dep]
        if waiting:
            bus = min(waiting, key=lambda b: b[2])
        else:
            bus = [[], None, None]
            buses.append(bus)
        bus[0].append(trip_id)
        bus[1], bus[2] = end, arr
    return [bus[0] for bus in buses]


def infer_blocks(trip_info, route_names, coords):
    """{trip_id: block_id} by chaining each route's trips; block ids look like "25-3".

    trip_info: {trip_id: (route_id, first_stop, last_stop, start_s, end_s)}.
    """
    by_route = defaultdict(list)
    for trip_id, (route_id, first, last, dep, arr) in trip_info.items():
        by_route[route_id].append((trip_id, first, last, dep, arr))

    def near(a, b):
        return a == b or (a in coords and b in coords and haversine_km(coords[a], coords[b]) <= SAME_TERMINAL_KM)

    trip_block = {}
    for route_id, trips in by_route.items():
        for n, bus in enumerate(chain_trips(trips, same_place=near), start=1):
            for trip_id in bus:
                trip_block[trip_id] = f"{route_names[route_id]}-{n}"
    return trip_block


def road_factor_from(exact_km, straight_km):
    """Factor that makes straight-line totals match exact totals, from paired trip lengths."""
    pairs = [(e, s) for e, s in zip(exact_km, straight_km) if s > 0.5]
    return sum(e for e, _ in pairs) / sum(s for _, s in pairs)
