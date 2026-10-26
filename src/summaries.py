"""Pre-computed block summaries for one agency's feed(s), stamped with the feeds they came from.

A timetable has only a handful of distinct days: on most dates the same set of services runs
(every ordinary weekday, every Saturday...). So instead of re-reading the whole feed for each
question, build_summary() groups the dates that run an identical set of bus services, works
out every block's distance and duration once per group, and stores the results.

The summary stores distances and durations, not pass/fail against a battery range, so changing
the battery assumptions never needs a rebuild: the range is applied when a question is asked.
"""

import hashlib
import json
import zipfile
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from src.agencies import BLOCK_METHODS, DISTANCE_METHODS
from src.blocks import (
    MissingDistanceError,
    _block_distances,
    _block_spans,
    _blocks_for_services,
    _bus_trips,
    _load_calendar,
    _read_table,
    _services_on,
    _trip_lengths_and_times,
    check_trip_speeds,
)
from src.estimates import infer_blocks, road_factor_from, shape_lengths_km, stop_coords, walk_trips


def file_sha256(path):
    """SHA-256 of the file's bytes: identical files always give the identical hash."""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _calendar_span(calendar, exceptions):
    """First and last date mentioned anywhere in calendar.txt or calendar_dates.txt."""
    starts = [row["start_date"] for row in calendar] + list(exceptions)
    ends = [row["end_date"] for row in calendar] + list(exceptions)
    if not starts:
        return None, None
    return _gtfs_date(min(starts)), _gtfs_date(max(ends))


def _gtfs_date(text):
    """Turn a GTFS date like "20261014" into a date."""
    return date(int(text[:4]), int(text[4:6]), int(text[6:]))


def build_summary(
    feed_paths,
    agency,
    git_commit="unknown",
    now=None,
    *,
    agency_name=None,
    distance="stop_times",
    blocks="gtfs",
    operators=(),
    days_ahead=None,
    road_factor=None,
    calibration=None,
):
    """Return the summary dict for one agency's feed(s) (see the module docstring).

    feed_paths: one path or a list (Dublin combines two feeds). distance and blocks are
    DISTANCE_METHODS / BLOCK_METHODS keys; operators keeps only those agency_names; days_ahead
    builds only that many days from the build date; road_factor scales straight-line distances.
    """
    if isinstance(feed_paths, (str, Path)):
        feed_paths = [feed_paths]
    feed_paths = [Path(p) for p in feed_paths]
    now = now or datetime.now(UTC)
    window = None
    if days_ahead:
        window = (now.date(), now.date() + timedelta(days=days_ahead - 1))

    parts = [
        _FeedPart(path, distance, blocks, operators, window, road_factor) for path in feed_paths
    ]

    # Group dates by the exact set of bus services running on them, across every feed.
    groups = {}
    all_dates = sorted({d for part in parts for d in part.services_by_date})
    for day in all_dates:
        key = tuple(part.services_by_date.get(day, frozenset()) for part in parts)
        if any(key):
            groups.setdefault(key, []).append(day)

    service_days = []
    for key, dates in groups.items():
        merged = {}
        for part, services in zip(parts, key):
            if not services:
                continue
            for block_id, values in part.blocks_for(services).items():
                if block_id in merged:
                    raise ValueError(f"block_id {block_id} appears in more than one feed")
                merged[block_id] = values
        label = (lambda part, s: f"{part.path.stem}:{s}") if len(parts) > 1 else (lambda part, s: s)
        service_days.append(
            {
                "dates": [d.isoformat() for d in dates],
                "service_ids": sorted(label(p, s) for p, services in zip(parts, key) for s in services),
                "blocks": {b: merged[b] for b in sorted(merged)},
            }
        )
    service_days.sort(key=lambda g: g["dates"][0])

    service_dates = [d for g in service_days for d in g["dates"]]
    stamp = {
        "agency": agency,
        "agency_name": agency_name or agency,
        "feeds": [
            {"file": p.path.name, "sha256": file_sha256(p.path), "version": p.version} for p in parts
        ],
        "calendar_start": min(service_dates) if service_dates else None,
        "calendar_end": max(service_dates) if service_dates else None,
        "dates_built": f"next {days_ahead} days from the build date" if days_ahead else "whole timetable",
        "distance_method": DISTANCE_METHODS[distance],
        "block_method": BLOCK_METHODS[blocks],
        "built_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": git_commit,
    }
    if operators:
        stamp["operators_kept"] = list(operators)
    if road_factor is not None:
        stamp["road_factor"] = round(road_factor, 4)
    if calibration:
        stamp["road_factor_calibration"] = calibration
    return {"stamp": stamp, "service_days": service_days}


class _FeedPart:
    """One feed's dates, services, trip lengths, times and blocks, read once."""

    def __init__(self, path, distance, blocks, operators, window, road_factor):
        self.path = path
        self.blocks_method = blocks
        with zipfile.ZipFile(path) as zf:
            self.version = next(iter(_read_table(zf, "feed_info.txt")), {}).get("feed_version") or None
            bus_trips = _bus_trips(zf)
            routes = {r["route_id"]: r for r in _read_table(zf, "routes.txt")}
            if operators:
                names = {a.get("agency_id", ""): a["agency_name"] for a in _read_table(zf, "agency.txt")}
                kept = {rid for rid, r in routes.items() if names.get(r.get("agency_id", "")) in operators}
            else:
                kept = set(routes)
            trip_route, trip_shape = {}, {}
            for row in _read_table(zf, "trips.txt"):
                if row["trip_id"] in bus_trips and row["route_id"] in kept:
                    trip_route[row["trip_id"]] = row["route_id"]
                    trip_shape[row["trip_id"]] = (row.get("shape_id") or "").strip()
            self.bus_trips = {t: v for t, v in bus_trips.items() if t in trip_route}
            self.trip_route = trip_route
            self.route_names = _route_names(routes, set(trip_route.values()))

            # Which bus services run on each date (inside the window, if there is one).
            calendar, exceptions = _load_calendar(zf)
            bus_services = {s for s, _ in self.bus_trips.values()}
            first, last = _calendar_span(calendar, exceptions)
            if window and first:
                first, last = max(first, window[0]), min(last, window[1])
            self.services_by_date = {}
            day = first
            while first and day <= last:
                services = frozenset(_services_on(calendar, exceptions, day) & bus_services)
                if services:
                    self.services_by_date[day] = services
                day += timedelta(days=1)

            used = set().union(*self.services_by_date.values()) if self.services_by_date else set()
            needed = {t for t, (s, _) in self.bus_trips.items() if s in used}

            self.coords = {}
            self.walks = {}
            if distance == "straight_line" or blocks == "inferred":
                self.coords = stop_coords(zf)
                self.walks = walk_trips(zf, needed, self.coords)
            if distance == "stop_times":
                self.lengths, self.starts, self.ends = _trip_lengths_and_times(zf, needed)
            elif distance == "shapes":
                shape_km = shape_lengths_km(zf)
                self.lengths = {t: shape_km[trip_shape[t]] for t in needed if trip_shape[t] in shape_km}
                _, self.starts, self.ends = _trip_lengths_and_times(zf, needed)
            elif distance == "straight_line":
                if road_factor is None:
                    raise ValueError("straight_line distances need a road_factor")
                self.lengths = {t: w[4] * road_factor for t, w in self.walks.items()}
                self.starts = {t: w[2] for t, w in self.walks.items()}
                self.ends = {t: w[3] for t, w in self.walks.items()}
            else:
                raise ValueError(f"Unknown distance method {distance!r}")

    def blocks_for(self, services):
        """{block_id: {"km", "minutes"}} for one set of active services."""
        if self.blocks_method == "gtfs":
            trip_block = _blocks_for_services(self.bus_trips, services)  # coverage guard applies
        elif self.blocks_method == "inferred":
            # The explicit inferred path: blocks are built here, so the coverage guard is skipped.
            running = [t for t, (s, _) in self.bus_trips.items() if s in services]
            no_times = [t for t in running if t not in self.walks]
            if no_times:
                raise MissingDistanceError({t: "(inferred)" for t in no_times})
            info = {t: (self.trip_route[t], *self.walks[t][:4]) for t in running}
            trip_block = infer_blocks(info, self.route_names, self.coords)
        else:
            raise ValueError(f"Unknown block method {self.blocks_method!r}")
        distances = _block_distances(trip_block, self.lengths)
        check_trip_speeds(trip_block, self.lengths, self.starts, self.ends)  # speed guard applies
        spans = _block_spans(trip_block, self.starts, self.ends)
        # start/end: seconds after the service day's midnight (can pass 24:00 for late blocks).
        return {
            b: {
                "km": round(distances[b], 3),
                "minutes": round((spans[b][1] - spans[b][0]) / 60, 1),
                "start": spans[b][0],
                "end": spans[b][1],
            }
            for b in distances
        }


def _route_names(routes, route_ids):
    """Short route names for inferred block ids, adding the route_id where names repeat."""
    names = {rid: (routes[rid].get("route_short_name") or rid).strip() or rid for rid in route_ids}
    counts = defaultdict(int)
    for name in names.values():
        counts[name] += 1
    return {rid: name if counts[name] == 1 else f"{name}({rid})" for rid, name in names.items()}


def calibrate_road_factor(feed_paths, sample_date):
    """Road factor from feeds with exact shape distances, plus its error.

    Factor = total exact km / total straight-line km over every bus trip with a shape. Error is
    reported per trip and per block (blocks running on sample_date), after applying the factor.
    """
    exact, straight, trip_block_pairs = [], [], []
    for path in feed_paths:
        with zipfile.ZipFile(path) as zf:
            bus_trips = _bus_trips(zf)
            shape_km = shape_lengths_km(zf)
            trip_shape = {
                r["trip_id"]: (r.get("shape_id") or "").strip()
                for r in _read_table(zf, "trips.txt")
                if r["trip_id"] in bus_trips
            }
            walks = walk_trips(zf, set(trip_shape), stop_coords(zf))
            calendar, exceptions = _load_calendar(zf)
            on_sample = _services_on(calendar, exceptions, sample_date)
        for t, w in walks.items():
            if trip_shape.get(t) in shape_km and w[4] > 0.5:
                exact.append(shape_km[trip_shape[t]])
                straight.append(w[4])
                service, block = bus_trips[t]
                if service in on_sample and block:
                    trip_block_pairs.append((f"{path.stem}:{block}", shape_km[trip_shape[t]], w[4]))

    factor = road_factor_from(exact, straight)
    trip_errors = sorted(abs(s * factor - e) / e * 100 for e, s in zip(exact, straight))
    block_exact, block_est = defaultdict(float), defaultdict(float)
    for block, e, s in trip_block_pairs:
        block_exact[block] += e
        block_est[block] += s * factor
    block_errors = sorted(abs(block_est[b] - block_exact[b]) / block_exact[b] * 100 for b in block_exact)

    def pct(values, q):
        return round(values[min(len(values) - 1, int(len(values) * q))], 1)

    return factor, {
        "source": "Dublin Bus and Go-Ahead Ireland exact shape distances",
        "trips_used": len(exact),
        "trip_error_median_pct": pct(trip_errors, 0.5),
        "trip_error_p90_pct": pct(trip_errors, 0.9),
        "block_sample_date": sample_date.isoformat(),
        "blocks_used": len(block_exact),
        "block_error_median_pct": pct(block_errors, 0.5),
        "block_error_p90_pct": pct(block_errors, 0.9),
    }


def write_summary(summary, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{summary['stamp']['agency']}.json"
    # Compact JSON keeps the big summaries small (London's has ~9,000 blocks per day). Always
    # "\n" line endings, so the file is byte-identical whether built on Windows or Linux.
    text = json.dumps(summary, separators=(",", ":"))
    path.write_text(text + "\n", encoding="utf-8", newline="\n")
    return path


_cache = {}


def load_summary(path):
    """Read a summary file (cached until the file changes) and index its dates; None if missing."""
    path = Path(path)
    if not path.exists():
        return None
    # One cached copy per file (all agencies together take ~65 MB), replaced if the file changes.
    modified = path.stat().st_mtime_ns
    cached = _cache.get(str(path))
    if cached is None or cached[0] != modified:
        summary = json.loads(path.read_text(encoding="utf-8"))
        summary["by_date"] = {d: g for g in summary["service_days"] for d in g["dates"]}
        _cache[str(path)] = (modified, summary)
    return _cache[str(path)][1]


def service_day_for(summary, service_date):
    """The service-day group running on service_date, or None if no bus service that day."""
    return summary["by_date"].get(service_date.isoformat())


def design_day(summary, range_km):
    """Pick the planning day: the service-day group with the most blocks over range_km.

    Ties go to the group with the most blocks in service, then to the earliest date.
    Returns (group, blocks_over_range), or (None, 0) for an empty summary.
    """
    best, best_key = None, None
    # Groups are sorted by first date, and only a strictly better group replaces the current
    # pick, so on a full tie the earliest group is kept.
    for group in summary["service_days"]:
        over = sum(1 for b in group["blocks"].values() if b["km"] > range_km)
        key = (over, len(group["blocks"]))
        if best_key is None or key > best_key:
            best, best_key = group, key
    return (best, best_key[0]) if best else (None, 0)
