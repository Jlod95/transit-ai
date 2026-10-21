"""Pre-computed block summaries for one agency's feed, stamped with the feed they came from.

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
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from src.blocks import (
    _block_distances,
    _block_durations,
    _blocks_for_services,
    _bus_trips,
    _load_calendar,
    _read_table,
    _services_on,
    _trip_lengths_and_times,
)


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


def build_summary(feed_path, agency, git_commit="unknown", now=None):
    """Return the summary dict for one feed (see the module docstring)."""
    feed_path = Path(feed_path)
    with zipfile.ZipFile(feed_path) as zf:
        bus_trips = _bus_trips(zf)
        calendar, exceptions = _load_calendar(zf)
        feed_info = next(iter(_read_table(zf, "feed_info.txt")), {})
        bus_services = {service for service, _ in bus_trips.values()}

        # Group every date by the exact set of bus services running on it.
        groups = {}
        first, last = _calendar_span(calendar, exceptions)
        day = first
        while first and day <= last:
            services = frozenset(_services_on(calendar, exceptions, day) & bus_services)
            if services:
                groups.setdefault(services, []).append(day)
            day += timedelta(days=1)

        # One pass over stop_times for every bus trip that has a block.
        trips_with_block = {t for t, (_, b) in bus_trips.items() if b}
        lengths, starts, ends = _trip_lengths_and_times(zf, trips_with_block)

    service_days = []
    for services, dates in groups.items():
        # Same guards as the daily functions: block coverage, then missing distances.
        trip_block = _blocks_for_services(bus_trips, services)
        distances = _block_distances(trip_block, lengths)
        durations = _block_durations(trip_block, starts, ends)
        service_days.append(
            {
                "dates": [d.isoformat() for d in dates],
                "service_ids": sorted(services),
                "blocks": {
                    b: {"km": round(distances[b], 3), "minutes": round(durations[b], 1)}
                    for b in sorted(distances)
                },
            }
        )
    service_days.sort(key=lambda g: g["dates"][0])

    service_dates = [d for g in service_days for d in g["dates"]]
    return {
        "stamp": {
            "agency": agency,
            "feed_file": feed_path.name,
            "feed_sha256": file_sha256(feed_path),
            "feed_version": feed_info.get("feed_version") or None,
            "calendar_start": min(service_dates) if service_dates else None,
            "calendar_end": max(service_dates) if service_dates else None,
            "built_at": (now or datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "git_commit": git_commit,
        },
        "service_days": service_days,
    }


def write_summary(summary, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{summary['stamp']['agency']}.json"
    # Always "\n" line endings, so the file is byte-identical whether built on Windows or Linux.
    path.write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8", newline="\n")
    return path


_cache = {}


def load_summary(path):
    """Read a summary file (cached until the file changes) and index its dates; None if missing."""
    path = Path(path)
    if not path.exists():
        return None
    key = (str(path), path.stat().st_mtime_ns)
    if key not in _cache:
        summary = json.loads(path.read_text(encoding="utf-8"))
        summary["by_date"] = {d: g for g in summary["service_days"] for d in g["dates"]}
        _cache.clear()
        _cache[key] = summary
    return _cache[key]


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
