"""Checks on the committed Halifax summary, which is what the deployed app answers from.

These run in CI, which has no raw feed, so Halifax's real numbers are checked on every push.
"""

from datetime import date
from pathlib import Path

import pytest

from src.summaries import file_sha256, load_summary, service_day_for

ROOT = Path(__file__).parent.parent
SUMMARY = ROOT / "data" / "summaries" / "halifax.json"
FEED = ROOT / "data" / "raw" / "halifax.zip"


@pytest.fixture
def summary():
    loaded = load_summary(SUMMARY)
    assert loaded is not None, f"{SUMMARY} is missing; build it with scripts/build_summaries.py"
    return loaded


def test_stamp_is_complete_and_from_committed_code(summary):
    stamp = summary["stamp"]
    assert stamp["agency"] == "halifax"
    assert len(stamp["feed_sha256"]) == 64
    assert stamp["feed_version"]
    assert stamp["calendar_start"] <= stamp["calendar_end"]
    # Built from committed code, so the commit in the stamp identifies the exact code used.
    assert stamp["git_commit"] != "unknown"
    assert not stamp["git_commit"].endswith("-dirty")


def test_known_halifax_block(summary):
    # Block 722145 on Wed 14 Oct 2026: 80.5 km, from 5:32 to 8:48 = 196 minutes.
    block = service_day_for(summary, date(2026, 10, 14))["blocks"]["722145"]
    assert block["km"] == pytest.approx(80.5, abs=0.1)
    assert block["minutes"] == 196.0


@pytest.mark.skipif(not FEED.exists(), reason="no local raw feed to compare against")
def test_summary_matches_the_local_feed(summary):
    # Locally, if the raw feed has changed since the summary was built, the summary is stale.
    assert summary["stamp"]["feed_sha256"] == file_sha256(FEED), (
        "data/raw/halifax.zip differs from the feed the summary was built from; rebuild it with "
        "scripts/build_summaries.py data/raw/halifax.zip halifax"
    )
