"""Build the pre-computed block summary for one agency's GTFS feed.

Usage:
    python scripts/build_summaries.py data/raw/halifax.zip halifax
    python scripts/build_summaries.py FEED_ZIP AGENCY --out data/summaries

Writes <out>/<agency>.json. The git commit in the stamp comes from the GIT_COMMIT environment
variable if set (the Docker build passes it, since the image has no .git folder), otherwise
from git itself, with "-dirty" added when there are uncommitted changes.
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))  # so "src" can be imported when run as a script

from src.summaries import build_summary, write_summary


def current_git_commit():
    if os.environ.get("GIT_COMMIT"):
        return os.environ["GIT_COMMIT"]
    try:
        def git(*args):
            return subprocess.run(
                ["git", *args], cwd=PROJECT_ROOT, capture_output=True, text=True, check=True
            ).stdout.strip()

        commit = git("rev-parse", "--short", "HEAD")
        # "-dirty" means tracked code differs from the commit. Summaries are this script's own
        # output, so changes to them don't count.
        changed = git("status", "--porcelain", "--untracked-files=no", "--", ".",
                      ":(exclude)data/summaries")
        return commit + ("-dirty" if changed else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("feed", help="path to the GTFS zip")
    parser.add_argument("agency", help="short agency name, used as the output file name")
    parser.add_argument("--out", default=str(PROJECT_ROOT / "data" / "summaries"))
    args = parser.parse_args()

    started = time.perf_counter()
    summary = build_summary(args.feed, args.agency, git_commit=current_git_commit())
    path = write_summary(summary, args.out)
    elapsed = time.perf_counter() - started

    stamp = summary["stamp"]
    days = summary["service_days"]
    print(f"Wrote {path} ({path.stat().st_size / 1000:.0f} kB) in {elapsed:.1f}s")
    print(f"  {len(days)} distinct service days covering {sum(len(g['dates']) for g in days)} dates, "
          f"{stamp['calendar_start']} to {stamp['calendar_end']}")
    print(f"  feed {stamp['feed_file']} version {stamp['feed_version']} sha256 {stamp['feed_sha256'][:12]}..., "
          f"git {stamp['git_commit']}")


if __name__ == "__main__":
    main()
