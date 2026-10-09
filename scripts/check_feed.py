"""Quick quality check for a GTFS feed.

Usage:
    python scripts/check_feed.py data/raw/some_feed.zip
    python scripts/check_feed.py https://example.com/google_transit.zip

Reports:
  - number of trips and routes
  - % of trips with a non-empty block_id (needed to chain trips into vehicle duties)
  - % of shapes.txt / stop_times.txt rows with shape_dist_traveled filled in
  - feed dates and licence/publisher info from feed_info.txt, if present

Uses only the Python standard library.
"""

import csv
import io
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path


def open_table(zf, name):
    """Return a csv.DictReader for a file in the zip, or None if it's missing.

    Matches by file name so feeds that put files inside a sub-folder still work.
    """
    for member in zf.namelist():
        if Path(member).name == name:
            raw = zf.open(member)
            # utf-8-sig strips the byte-order mark some agencies include.
            text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
            return csv.DictReader(text)
    return None


def filled_share(reader, column):
    """Return (rows with a non-empty value in column, total rows), or None if no column."""
    if reader is None or column not in (reader.fieldnames or []):
        return None
    filled = total = 0
    for row in reader:
        total += 1
        if (row.get(column) or "").strip():
            filled += 1
    return filled, total


def pct(result):
    if result is None:
        return "column not present"
    filled, total = result
    if total == 0:
        return "0 rows"
    return f"{100 * filled / total:.1f}% ({filled:,} of {total:,} rows)"


def count_rows(reader):
    return 0 if reader is None else sum(1 for _ in reader)


def check_feed(zip_path):
    with zipfile.ZipFile(zip_path) as zf:
        n_routes = count_rows(open_table(zf, "routes.txt"))
        block = filled_share(open_table(zf, "trips.txt"), "block_id")
        n_trips = count_rows(open_table(zf, "trips.txt"))

        shapes = open_table(zf, "shapes.txt")
        shapes_dist = "shapes.txt missing" if shapes is None else pct(
            filled_share(shapes, "shape_dist_traveled")
        )
        stop_times_dist = pct(filled_share(open_table(zf, "stop_times.txt"), "shape_dist_traveled"))

        feed_info = open_table(zf, "feed_info.txt")
        info = next(iter(feed_info), {}) if feed_info is not None else None

    print(f"Feed: {zip_path}")
    print(f"  Routes: {n_routes:,}")
    print(f"  Trips:  {n_trips:,}")
    print(f"  Trips with block_id: {pct(block)}")
    print(f"  shapes.txt shape_dist_traveled:     {shapes_dist}")
    print(f"  stop_times.txt shape_dist_traveled: {stop_times_dist}")

    if info is None:
        print("  feed_info.txt: not present (licence not stated in feed)")
        return
    # GTFS has no standard licence field, so look for any column mentioning one.
    licence = {k: v for k, v in info.items() if k and "licen" in k.lower()}
    print(f"  Licence in feed_info.txt: {licence or 'not stated'}")
    print(f"  Publisher: {info.get('feed_publisher_name', '')} {info.get('feed_publisher_url', '')}")
    print(f"  Feed dates: {info.get('feed_start_date', '?')} to {info.get('feed_end_date', '?')}")


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    source = sys.argv[1]

    if source.startswith(("http://", "https://")):
        # Download to a temporary file, check it, then let it be cleaned up.
        request = urllib.request.Request(source, headers={"User-Agent": "transit-ai-feed-check"})
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "feed.zip"
            with urllib.request.urlopen(request, timeout=120) as resp:
                zip_path.write_bytes(resp.read())
            check_feed(zip_path)
    else:
        check_feed(Path(source))


if __name__ == "__main__":
    main()
