"""Build the pre-computed block summaries for one or more agencies.

Usage:
    python scripts/build_summaries.py halifax
    python scripts/build_summaries.py halifax dublin london
    python scripts/build_summaries.py            (all agencies)

Agencies, their raw feeds and methods are listed in src/agencies.py. Writes
data/summaries/<agency>.json. The git commit in the stamp comes from the GIT_COMMIT
environment variable if set, otherwise from git itself, with "-dirty" added when tracked code
has uncommitted changes.
"""

import argparse
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))  # so "src" can be imported when run as a script

from src.agencies import AGENCIES, get_agency
from src.provenance import current_git_commit
from src.summaries import build_summary, calibrate_road_factor, write_summary


def build(key, out_dir, commit):
    agency = get_agency(key)
    started = time.perf_counter()
    road_factor = calibration = None
    if agency.calibrate_with:
        source = get_agency(agency.calibrate_with)
        # Block errors are measured on today's Dublin service.
        road_factor, calibration = calibrate_road_factor(
            [PROJECT_ROOT / f for f in source.feeds], datetime.now(UTC).date()
        )
        print(f"  road factor {road_factor:.4f} from {calibration['trips_used']:,} {source.key} trips "
              f"({time.perf_counter() - started:.0f}s)")
    summary = build_summary(
        [PROJECT_ROOT / f for f in agency.feeds],
        agency.key,
        git_commit=commit,
        agency_name=agency.name,
        distance=agency.distance,
        blocks=agency.blocks,
        operators=agency.operators,
        days_ahead=agency.days_ahead,
        road_factor=road_factor,
        calibration=calibration,
    )
    path = write_summary(summary, out_dir)
    days = summary["service_days"]
    stamp = summary["stamp"]
    print(f"Wrote {path} ({path.stat().st_size / 1000:.0f} kB) in {time.perf_counter() - started:.1f}s")
    print(f"  {len(days)} distinct service days covering {sum(len(g['dates']) for g in days)} dates, "
          f"{stamp['calendar_start']} to {stamp['calendar_end']} ({stamp['dates_built']})")
    print(f"  git {stamp['git_commit']}; feeds: "
          + ", ".join(f"{f['file']} {f['version']} {f['sha256'][:12]}..." for f in stamp["feeds"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("agencies", nargs="*", default=list(AGENCIES), help="agency keys")
    parser.add_argument("--out", default=str(PROJECT_ROOT / "data" / "summaries"))
    args = parser.parse_args()
    commit = current_git_commit()
    for key in args.agencies:
        print(f"== {key}")
        build(key, args.out, commit)


if __name__ == "__main__":
    main()
